"""
P.E.P.P.E.R. Phase 16H Final Validation
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from assistant.background import (
    BackgroundHandlerRegistry,
    BackgroundWorker,
)
from assistant.events import EVENT_BUS
from assistant.events.definitions import (
    RECOVERY_ATTEMPTED,
    RECOVERY_EXHAUSTED,
    VERIFICATION_FAILED,
    VERIFICATION_PASSED,
)
from assistant.executive import TaskExecutive
from assistant.verification import (
    RecoveryPolicy,
    RecoveryRegistry,
    VerificationEngine,
    VerificationResult,
    VerifierRegistry,
)


def make_stack(path: Path, *, max_attempts=1):
    executive = TaskExecutive(path)
    handlers = BackgroundHandlerRegistry()
    verifiers = VerifierRegistry()
    recoveries = RecoveryRegistry()
    verification_engine = VerificationEngine(
        verifiers=verifiers,
        recoveries=recoveries,
        recovery_policy=RecoveryPolicy(
            max_attempts=max_attempts
        ),
    )
    worker = BackgroundWorker(
        executive=executive,
        registry=handlers,
        verification_engine=verification_engine,
        max_workers=2,
    )
    return (
        executive,
        handlers,
        verifiers,
        recoveries,
        worker,
    )


def create_task(
    executive,
    *,
    handler,
    verifier=None,
    recovery=None,
):
    metadata = {
        "background_handler": handler,
    }
    if verifier:
        metadata["verifier"] = verifier
    if recovery:
        metadata["recovery_handler"] = recovery

    return executive.create_task(
        "Validation task",
        metadata=metadata,
    )


def test_verified_success(path: Path):
    executive, handlers, verifiers, recoveries, worker = (
        make_stack(path)
    )

    handlers.register(
        "produce",
        lambda task: {"ok": True},
    )
    verifiers.register(
        "is-ok",
        lambda task, value:
            VerificationResult.success("payload valid")
            if value.get("ok") is True
            else VerificationResult.failure("payload invalid"),
    )

    task = create_task(
        executive,
        handler="produce",
        verifier="is-ok",
    )

    worker.start()
    try:
        result = worker.submit(task.task_id).result(timeout=3)
    finally:
        worker.stop()

    assert result.success is True
    assert result.verification_reason == "payload valid"
    assert executive.get_task(task.task_id).status == "completed"

    print("PASS 16H verified execution completes")


def test_verification_failure(path: Path):
    executive, handlers, verifiers, recoveries, worker = (
        make_stack(path)
    )

    handlers.register(
        "produce-bad",
        lambda task: {"ok": False},
    )
    verifiers.register(
        "is-ok",
        lambda task, value: bool(value.get("ok")),
    )

    task = create_task(
        executive,
        handler="produce-bad",
        verifier="is-ok",
    )

    worker.start()
    try:
        result = worker.submit(task.task_id).result(timeout=3)
    finally:
        worker.stop()

    assert result.success is False
    failed = executive.get_task(task.task_id)
    assert failed.status == "failed"
    assert "Verification failed" in failed.error

    print("PASS 16H failed verification prevents false completion")


def test_bounded_recovery_success(path: Path):
    executive, handlers, verifiers, recoveries, worker = (
        make_stack(path, max_attempts=1)
    )

    handlers.register(
        "produce",
        lambda task: {"ok": False},
    )
    verifiers.register(
        "is-ok",
        lambda task, value: bool(value.get("ok")),
    )
    recoveries.register(
        "repair",
        lambda task, value, verification, attempt:
            {"ok": True, "attempt": attempt},
    )

    task = create_task(
        executive,
        handler="produce",
        verifier="is-ok",
        recovery="repair",
    )

    worker.start()
    try:
        result = worker.submit(task.task_id).result(timeout=3)
    finally:
        worker.stop()

    assert result.success is True
    assert result.recovery_attempts == 1
    assert result.value["ok"] is True
    assert executive.get_task(task.task_id).status == "completed"

    print("PASS 16H bounded recovery + re-verification")


def test_recovery_budget(path: Path):
    executive, handlers, verifiers, recoveries, worker = (
        make_stack(path, max_attempts=1)
    )

    calls = {"count": 0}

    handlers.register(
        "produce",
        lambda task: {"ok": False},
    )
    verifiers.register(
        "never",
        lambda task, value: False,
    )

    def failed_repair(task, value, verification, attempt):
        calls["count"] += 1
        return {"ok": False}

    recoveries.register(
        "failed-repair",
        failed_repair,
    )

    task = create_task(
        executive,
        handler="produce",
        verifier="never",
        recovery="failed-repair",
    )

    worker.start()
    try:
        result = worker.submit(task.task_id).result(timeout=3)
    finally:
        worker.stop()

    assert result.success is False
    assert calls["count"] == 1
    assert executive.get_task(task.task_id).status == "failed"

    print("PASS 16H recovery attempt budget enforced")


def test_verifier_exception_isolated(path: Path):
    executive, handlers, verifiers, recoveries, worker = (
        make_stack(path)
    )

    handlers.register(
        "produce",
        lambda task: {"ok": True},
    )

    def explode(task, value):
        raise RuntimeError("controlled verifier failure")

    verifiers.register("explode", explode)

    task = create_task(
        executive,
        handler="produce",
        verifier="explode",
    )

    worker.start()
    try:
        result = worker.submit(task.task_id).result(timeout=3)
    finally:
        worker.stop()

    assert result.success is False
    failed = executive.get_task(task.task_id)
    assert failed.status == "failed"
    assert "verifier exception" in failed.error

    print("PASS 16H verifier exceptions fail closed")


def test_legacy_16f_compatibility(path: Path):
    executive, handlers, verifiers, recoveries, worker = (
        make_stack(path)
    )

    handlers.register(
        "legacy",
        lambda task: "done",
    )

    task = create_task(
        executive,
        handler="legacy",
    )

    worker.start()
    try:
        result = worker.submit(task.task_id).result(timeout=3)
    finally:
        worker.stop()

    assert result.success is True
    assert executive.get_task(task.task_id).status == "completed"
    assert "legacy completion preserved" in result.verification_reason

    print("PASS 16H Phase 16F backward compatibility")


def test_events(path: Path):
    executive, handlers, verifiers, recoveries, worker = (
        make_stack(path, max_attempts=1)
    )

    handlers.register(
        "produce",
        lambda task: {"ok": False},
    )
    verifiers.register(
        "is-ok",
        lambda task, value: bool(value.get("ok")),
    )
    recoveries.register(
        "repair",
        lambda task, value, verification, attempt:
            {"ok": True},
    )

    seen = []
    topics = [
        VERIFICATION_FAILED,
        RECOVERY_ATTEMPTED,
        VERIFICATION_PASSED,
        RECOVERY_EXHAUSTED,
    ]

    tokens = [
        EVENT_BUS.subscribe(
            topic,
            lambda event, topic=topic: seen.append(topic),
        )
        for topic in topics
    ]

    task = create_task(
        executive,
        handler="produce",
        verifier="is-ok",
        recovery="repair",
    )

    worker.start()
    try:
        result = worker.submit(task.task_id).result(timeout=3)
    finally:
        worker.stop()
        for token in tokens:
            EVENT_BUS.unsubscribe(token)

    assert result.success is True
    assert VERIFICATION_FAILED in seen
    assert RECOVERY_ATTEMPTED in seen
    assert VERIFICATION_PASSED in seen
    assert RECOVERY_EXHAUSTED not in seen

    print("PASS 16H verification/recovery events")


def run_isolated(test):
    with TemporaryDirectory() as temp:
        test(Path(temp) / "executive.json")


def main():
    print("P.E.P.P.E.R. Phase 16H Final Validation")
    print("--------------------------------------")

    for test in [
        test_verified_success,
        test_verification_failure,
        test_bounded_recovery_success,
        test_recovery_budget,
        test_verifier_exception_isolated,
        test_legacy_16f_compatibility,
        test_events,
    ]:
        run_isolated(test)

    print()
    print("PHASE 16H FINAL VALIDATION PASSED")


if __name__ == "__main__":
    main()
