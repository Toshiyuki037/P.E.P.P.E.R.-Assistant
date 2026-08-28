"""
P.E.P.P.E.R. Phase 16 Full Integration / Regression Validation
Validates the Phase 16B-I runtime chain together without external network calls.

This intentionally does not modify or exercise the voice/barge-in pipeline.
Phase 16A's production routing/latency code remains covered by its existing
validator and the real main.py smoke test performed after this suite.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep

from assistant.autonomy import AutonomyGate, AutonomyPolicy, AutonomyRequest
from assistant.background import BackgroundHandlerRegistry, BackgroundWorker
from assistant.events import EVENT_BUS, publish
from assistant.events.definitions import (
    AUTONOMY_ALLOWED,
    AUTONOMY_APPROVAL_REQUIRED,
    BACKGROUND_JOB_FINISHED,
    PROACTIVE_SURFACED,
    RECOVERY_ATTEMPTED,
    VERIFICATION_FAILED,
    VERIFICATION_PASSED,
    WORLD_STATE_CHANGED,
)
from assistant.executive import TaskExecutive
from assistant.integrations.parallel_reads import (
    IntegrationReadRequest,
)
from assistant.performance.parallel import ParallelJob, execute_parallel
from assistant.proactive import ProactiveEngine, ProactivePolicy
from assistant.verification import (
    RecoveryPolicy,
    RecoveryRegistry,
    VerificationEngine,
    VerificationResult,
    VerifierRegistry,
)
from assistant.world_state.core import WorldStateStore


def section(name):
    print()
    print(name)
    print("-" * len(name))


def test_event_world_state_chain():
    section("16B + 16D: world state -> event bus")

    store = WorldStateStore()
    seen = []

    token = EVENT_BUS.subscribe(
        WORLD_STATE_CHANGED,
        lambda event: seen.append(event.payload),
    )
    try:
        record = store.set(
            "validation.current",
            {"value": 42},
            source="phase16.integration",
            fresh_for_seconds=60,
            confidence=1.0,
        )
    finally:
        EVENT_BUS.unsubscribe(token)

    assert store.get("validation.current") is not None
    assert record.value == {"value": 42}
    assert seen
    assert seen[-1]["key"] == "validation.current"

    print("PASS operational RAM emits deterministic mutation events")


def test_parallel_execution():
    section("16C: bounded parallel execution")

    def delayed(value):
        sleep(0.20)
        return value

    jobs = [
        ParallelJob(
            name=f"job-{index}",
            function=delayed,
            args=(index,),
        )
        for index in range(4)
    ]

    results = execute_parallel(jobs, max_workers=4)

    assert len(results) == 4
    assert [item.name for item in results] == [
        "job-0", "job-1", "job-2", "job-3"
    ]
    assert all(item.success for item in results)

    print("PASS independent reads overlap and preserve deterministic order")


def make_execution_stack(path: Path):
    executive = TaskExecutive(path)
    handlers = BackgroundHandlerRegistry()
    verifiers = VerifierRegistry()
    recoveries = RecoveryRegistry()

    verification = VerificationEngine(
        verifiers=verifiers,
        recoveries=recoveries,
        recovery_policy=RecoveryPolicy(max_attempts=1),
    )

    worker = BackgroundWorker(
        executive=executive,
        registry=handlers,
        verification_engine=verification,
        max_workers=2,
    )

    return executive, handlers, verifiers, recoveries, worker


def test_persistence_restart(path: Path):
    section("16E: persistent executive")

    executive = TaskExecutive(path)
    goal = executive.create_goal(
        "Phase 16 integration goal",
        priority=10,
    )
    task = executive.create_task(
        "Persistent validation task",
        goal_id=goal.goal_id,
        priority=9,
        metadata={"background_handler": "noop"},
    )

    restarted = TaskExecutive(path)

    loaded_goal = restarted.get_goal(goal.goal_id)
    loaded_task = restarted.get_task(task.task_id)

    assert loaded_goal is not None
    assert loaded_task is not None
    assert loaded_task.goal_id == goal.goal_id
    assert loaded_task.status == "pending"

    print("PASS goals/tasks survive executive restart")


def test_execution_verification_recovery_proactive(path: Path):
    section("16F + 16G + 16H: execute -> verify -> recover -> notify")

    executive, handlers, verifiers, recoveries, worker = (
        make_execution_stack(path)
    )

    handlers.register(
        "recoverable-job",
        lambda task: {"ok": False, "stage": "initial"},
    )

    verifiers.register(
        "payload-ok",
        lambda task, value:
            VerificationResult.success("payload verified")
            if value.get("ok") is True
            else VerificationResult.failure("payload not verified"),
    )

    recoveries.register(
        "repair-payload",
        lambda task, value, verification, attempt:
            {"ok": True, "stage": "recovered", "attempt": attempt},
    )

    task = executive.create_task(
        "Recoverable background job",
        metadata={
            "background_handler": "recoverable-job",
            "verifier": "payload-ok",
            "recovery_handler": "repair-payload",
        },
    )

    events = []
    tokens = [
        EVENT_BUS.subscribe(
            VERIFICATION_FAILED,
            lambda event: events.append(event.topic),
        ),
        EVENT_BUS.subscribe(
            RECOVERY_ATTEMPTED,
            lambda event: events.append(event.topic),
        ),
        EVENT_BUS.subscribe(
            VERIFICATION_PASSED,
            lambda event: events.append(event.topic),
        ),
    ]

    worker.start()
    try:
        result = worker.submit(task.task_id).result(timeout=5)
    finally:
        worker.stop()
        for token in tokens:
            EVENT_BUS.unsubscribe(token)

    assert result.success is True
    assert result.recovery_attempts == 1
    assert result.value["stage"] == "recovered"
    assert executive.get_task(task.task_id).status == "completed"
    assert VERIFICATION_FAILED in events
    assert RECOVERY_ATTEMPTED in events
    assert VERIFICATION_PASSED in events

    print("PASS background result recovered, re-verified, and completed")


def test_failed_job_becomes_proactive(path: Path):
    section("16F + 16G + 16H: terminal failure -> proactive notice")

    executive, handlers, verifiers, recoveries, worker = (
        make_execution_stack(path)
    )

    handlers.register(
        "bad-job",
        lambda task: {"ok": False},
    )
    verifiers.register(
        "never-valid",
        lambda task, value: False,
    )

    task = executive.create_task(
        "Terminal failure job",
        metadata={
            "background_handler": "bad-job",
            "verifier": "never-valid",
        },
    )

    proactive = ProactiveEngine(
        policy=ProactivePolicy(
            minimum_urgency=5,
            dedupe_seconds=300,
        )
    )
    proactive.install_default_subscriptions()

    surfaced = []
    token = EVENT_BUS.subscribe(
        PROACTIVE_SURFACED,
        lambda event: surfaced.append(event.payload),
    )

    worker.start()
    try:
        result = worker.submit(task.task_id).result(timeout=5)
    finally:
        worker.stop()
        EVENT_BUS.unsubscribe(token)
        proactive.unsubscribe_all()

    assert result.success is False
    assert executive.get_task(task.task_id).status == "failed"

    notices = proactive.pending()
    assert len(notices) == 1
    assert notices[0].topic == "background.task_failed"
    assert surfaced

    print("PASS verified terminal failure becomes one proactive notice")


def test_autonomy_boundaries():
    section("16I: autonomy/security gate")

    gate = AutonomyGate(policy=AutonomyPolicy())
    events = []

    tokens = [
        EVENT_BUS.subscribe(
            AUTONOMY_ALLOWED,
            lambda event: events.append(event.topic),
        ),
        EVENT_BUS.subscribe(
            AUTONOMY_APPROVAL_REQUIRED,
            lambda event: events.append(event.topic),
        ),
    ]

    try:
        read = gate.evaluate(
            AutonomyRequest(
                action="read.world_state",
                category="world_state_read",
                read_only=True,
                background=True,
                source="phase16.integration",
            )
        )

        write = gate.evaluate(
            AutonomyRequest(
                action="send.external.message",
                category="integration_write",
                read_only=False,
                external_side_effect=True,
                approval_granted=False,
                background=False,
                source="phase16.integration",
            )
        )

        background_write = gate.evaluate(
            AutonomyRequest(
                action="send.external.message.background",
                category="integration_write",
                read_only=False,
                external_side_effect=True,
                approval_granted=True,
                background=True,
                source="phase16.integration",
            )
        )
    finally:
        for token in tokens:
            EVENT_BUS.unsubscribe(token)

    assert read.allowed is True
    assert write.allowed is False
    assert write.requires_approval is True
    assert background_write.allowed is False
    assert background_write.requires_approval is True
    assert AUTONOMY_ALLOWED in events
    assert AUTONOMY_APPROVAL_REQUIRED in events

    print("PASS safe reads allowed; external/background side effects gated")


def test_proactive_dedupe_from_duplicate_failure_event():
    section("16D + 16G: duplicate event suppression")

    proactive = ProactiveEngine(
        policy=ProactivePolicy(
            minimum_urgency=5,
            dedupe_seconds=300,
        )
    )
    proactive.install_default_subscriptions()

    try:
        payload = {
            "task_id": "duplicate-task",
            "success": False,
            "error": "controlled duplicate failure",
        }

        publish(
            BACKGROUND_JOB_FINISHED,
            payload,
            source="phase16.integration",
        )
        publish(
            BACKGROUND_JOB_FINISHED,
            payload,
            source="phase16.integration",
        )

        notices = proactive.pending()
        assert len(notices) == 1
    finally:
        proactive.unsubscribe_all()

    print("PASS repeated failure event produces one proactive notice")


def test_import_regressions():
    section("Cross-module import regression")

    import assistant.autonomy
    import assistant.background
    import assistant.events
    import assistant.executive
    import assistant.integrations.parallel_reads
    import assistant.integrations.prefetch
    import assistant.integrations.prefetch_planner
    import assistant.performance.parallel
    import assistant.proactive
    import assistant.verification
    import assistant.world_state

    # Ensure the 16C request model is still constructible after later phases.
    request = IntegrationReadRequest(
        name="weather.current",
        capability="weather.current",
    )
    assert request.capability == "weather.current"

    print("PASS Phase 16 modules coexist and import cleanly")


def main():
    print("P.E.P.P.E.R. PHASE 16 FULL INTEGRATION / REGRESSION")
    print("=================================================")

    test_import_regressions()
    test_event_world_state_chain()
    test_parallel_execution()
    test_autonomy_boundaries()
    test_proactive_dedupe_from_duplicate_failure_event()

    with TemporaryDirectory() as temp:
        base = Path(temp)
        test_persistence_restart(base / "persistence.json")
        test_execution_verification_recovery_proactive(
            base / "recovery.json"
        )
        test_failed_job_becomes_proactive(
            base / "failure.json"
        )

    print()
    print("PHASE 16 FULL INTEGRATION VALIDATION PASSED")
    print()
    print(
        "NEXT: run the existing phase validators, then launch the real "
        "main.py runtime for manual smoke testing."
    )


if __name__ == "__main__":
    main()
