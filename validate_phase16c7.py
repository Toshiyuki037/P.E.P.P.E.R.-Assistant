"""
P.E.P.P.E.R. - Phase 16C.7 Final Validation + Benchmark

Validates the completed Phase 16C stack without calling real providers.

Coverage:
    1. Planner does zero work for unrelated requests.
    2. Planner deduplicates repeated integration intent.
    3. Four independent integration reads run materially faster in parallel
       than sequential execution.
    4. Each requested capability executes exactly once.
    5. A failed sibling does not discard successful siblings.
    6. Approval-required capabilities are rejected from the parallel read path.
    7. Successful prefetch results publish into Phase 16B world state.
    8. Failed refreshes do not overwrite an existing good RAM value.

This is intentionally offline and deterministic.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from time import perf_counter, sleep
from unittest.mock import patch

from assistant.integrations.prefetch_planner import (
    planned_capabilities,
)
from assistant.integrations.parallel_reads import (
    IntegrationReadRequest,
    execute_parallel_integration_reads,
)
from assistant.integrations.prefetch import (
    prefetch_integrations_to_world_state,
)
from assistant.world_state.core import WORLD_STATE


TEST_PREFIX = "validation.phase16c7."


@dataclass
class FakeEvidence:
    provider: str
    account_id: str
    capability: str
    success: bool
    data: object = None
    error: str = ""
    executed: bool = True
    requires_approval: bool = False
    risk: str = "low"


@dataclass
class FakeAggregate:
    success: bool
    capability: str
    routing_mode: str
    sources_attempted: int
    sources_succeeded: int
    evidence: list
    requires_approval: bool = False
    approval_reason: str = ""


CALLS = Counter()


def clear_test_state():
    for key in list(WORLD_STATE.keys()):
        if str(key).startswith(TEST_PREFIX):
            WORLD_STATE.delete(key)


def fake_aggregate_result_to_dict(result):
    return {
        "success": result.success,
        "capability": result.capability,
        "routing_mode": result.routing_mode,
        "sources_attempted": result.sources_attempted,
        "sources_succeeded": result.sources_succeeded,
        "evidence": [
            {
                "provider": item.provider,
                "account_id": item.account_id,
                "capability": item.capability,
                "success": item.success,
                "data": item.data,
                "error": item.error,
                "executed": item.executed,
                "requires_approval": item.requires_approval,
                "risk": item.risk,
            }
            for item in result.evidence
        ],
        "requires_approval": result.requires_approval,
        "approval_reason": result.approval_reason,
    }


def fake_execute_aggregate(
    capability,
    arguments,
    routing_mode="all_available",
    provider=None,
    account_id=None,
    approved=False,
):
    CALLS[capability] += 1

    delays = {
        "weather.current": 0.30,
        "calendar.upcoming": 0.30,
        "email.important": 0.30,
        "finance.market": 0.30,
    }

    sleep(delays.get(capability, 0.05))

    if capability == "email.important":
        return FakeAggregate(
            success=False,
            capability=capability,
            routing_mode=routing_mode,
            sources_attempted=1,
            sources_succeeded=0,
            evidence=[
                FakeEvidence(
                    provider="fake",
                    account_id="fake-account",
                    capability=capability,
                    success=False,
                    data=None,
                    error="controlled provider failure",
                    executed=True,
                )
            ],
        )

    return FakeAggregate(
        success=True,
        capability=capability,
        routing_mode=routing_mode,
        sources_attempted=1,
        sources_succeeded=1,
        evidence=[
            FakeEvidence(
                provider="fake",
                account_id="fake-account",
                capability=capability,
                success=True,
                data={
                    "capability": capability,
                    "value": f"{capability}-data",
                },
                executed=True,
            )
        ],
    )


def fake_permission_check(capability):
    return capability == "dangerous.write"


def fake_publish_integration_execution(
    execution,
    capability=None,
    provider=None,
    account_id=None,
    routing_mode=None,
):
    capability = capability or execution.get(
        "capability"
    )

    evidence = (
        execution
        .get("result", {})
        .get("evidence", [])
    )

    if not evidence:
        return None

    first = evidence[0]

    if not first.get("success"):
        return None

    key = TEST_PREFIX + capability

    return WORLD_STATE.set(
        key=key,
        value=first.get("data"),
        source="phase16c7.validation",
        fresh_for_seconds=60.0,
        confidence=1.0,
        metadata={
            "controlled_test": True,
        },
    )


def read_test_value(capability):
    record = WORLD_STATE.get(
        TEST_PREFIX + capability
    )
    return None if record is None else record.value


def test_planner():
    assert planned_capabilities(
        "Explain Ohms law"
    ) == []

    duplicate_message = (
        "Weather weather forecast and rain, "
        "plus my calendar meetings and calendar."
    )

    actual = planned_capabilities(
        duplicate_message
    )

    assert actual == [
        "weather.current",
        "calendar.upcoming",
    ], actual

    print(
        "PASS planner: irrelevant requests do zero work and repeated intent is deduplicated"
    )


def test_parallel_benchmark_and_exactly_once():
    requests = [
        IntegrationReadRequest(
            name="weather",
            capability="weather.current",
        ),
        IntegrationReadRequest(
            name="calendar",
            capability="calendar.upcoming",
        ),
        IntegrationReadRequest(
            name="email",
            capability="email.important",
        ),
        IntegrationReadRequest(
            name="market",
            capability="finance.market",
        ),
    ]

    # Sequential baseline using the exact same controlled provider function.
    CALLS.clear()
    started = perf_counter()

    for request in requests:
        fake_execute_aggregate(
            capability=request.capability,
            arguments={},
            routing_mode=request.routing_mode,
            provider=request.provider,
            account_id=request.account_id,
            approved=False,
        )

    sequential_elapsed = (
        perf_counter() - started
    )

    # Parallel path through the real Phase 16C.2 layer.
    CALLS.clear()

    with patch(
        "assistant.integrations.parallel_reads.execute_aggregate",
        side_effect=fake_execute_aggregate,
    ), patch(
        "assistant.integrations.parallel_reads.capability_requires_approval",
        side_effect=fake_permission_check,
    ):
        started = perf_counter()

        results = (
            execute_parallel_integration_reads(
                requests,
                max_workers=4,
            )
        )

        parallel_elapsed = (
            perf_counter() - started
        )

    expected_calls = Counter(
        {
            "weather.current": 1,
            "calendar.upcoming": 1,
            "email.important": 1,
            "finance.market": 1,
        }
    )

    assert CALLS == expected_calls, (
        f"Duplicate or missing calls detected: {CALLS}"
    )

    by_capability = {
        result.capability: result
        for result in results
    }

    assert (
        by_capability[
            "weather.current"
        ].success
        is True
    )
    assert (
        by_capability[
            "calendar.upcoming"
        ].success
        is True
    )
    assert (
        by_capability[
            "finance.market"
        ].success
        is True
    )
    assert (
        by_capability[
            "email.important"
        ].success
        is False
    )

    assert parallel_elapsed < (
        sequential_elapsed * 0.60
    ), (
        "Parallel execution was not materially faster: "
        f"sequential={sequential_elapsed:.3f}s "
        f"parallel={parallel_elapsed:.3f}s"
    )

    speedup = (
        sequential_elapsed
        / max(
            parallel_elapsed,
            0.000001,
        )
    )

    print(
        "PASS exactly-once: every requested capability executed once"
    )
    print(
        "PASS partial failure: successful siblings survived the controlled email failure"
    )
    print(
        (
            "PASS benchmark: "
            f"sequential={sequential_elapsed:.3f}s "
            f"parallel={parallel_elapsed:.3f}s "
            f"speedup={speedup:.2f}x"
        )
    )


def test_approval_boundary():
    request = IntegrationReadRequest(
        name="dangerous",
        capability="dangerous.write",
    )

    with patch(
        "assistant.integrations.parallel_reads.capability_requires_approval",
        side_effect=fake_permission_check,
    ):
        try:
            execute_parallel_integration_reads(
                [request],
                max_workers=1,
            )
        except PermissionError:
            print(
                "PASS approval boundary: approval-required capability rejected before parallel execution"
            )
            return

    raise AssertionError(
        "Approval-required capability was not rejected."
    )


def test_world_state_publication_and_preservation():
    clear_test_state()

    # Seed known-good email RAM. The controlled failed email refresh must not
    # erase or overwrite it.
    WORLD_STATE.set(
        key=TEST_PREFIX + "email.important",
        value={
            "status": "known-good",
            "count": 2,
        },
        source="phase16c7.validation",
        fresh_for_seconds=60.0,
        confidence=1.0,
        metadata={
            "controlled_test": True,
        },
    )

    requests = [
        IntegrationReadRequest(
            name="weather",
            capability="weather.current",
        ),
        IntegrationReadRequest(
            name="calendar",
            capability="calendar.upcoming",
        ),
        IntegrationReadRequest(
            name="email",
            capability="email.important",
        ),
        IntegrationReadRequest(
            name="market",
            capability="finance.market",
        ),
    ]

    CALLS.clear()

    # prefetch.py imported execute_parallel_integration_reads and
    # publish_integration_execution directly, so patch those call sites.
    with patch(
        "assistant.integrations.parallel_reads.execute_aggregate",
        side_effect=fake_execute_aggregate,
    ), patch(
        "assistant.integrations.parallel_reads.capability_requires_approval",
        side_effect=fake_permission_check,
    ), patch(
        "assistant.integrations.prefetch.aggregate_result_to_dict",
        side_effect=fake_aggregate_result_to_dict,
    ), patch(
        "assistant.integrations.prefetch.publish_integration_execution",
        side_effect=fake_publish_integration_execution,
    ):
        results = (
            prefetch_integrations_to_world_state(
                requests,
                max_workers=4,
            )
        )

    by_capability = {
        result.capability: result
        for result in results
    }

    assert (
        by_capability[
            "weather.current"
        ].published
        is True
    )
    assert (
        by_capability[
            "calendar.upcoming"
        ].published
        is True
    )
    assert (
        by_capability[
            "finance.market"
        ].published
        is True
    )
    assert (
        by_capability[
            "email.important"
        ].published
        is False
    )

    assert read_test_value(
        "weather.current"
    ) is not None

    assert read_test_value(
        "calendar.upcoming"
    ) is not None

    assert read_test_value(
        "finance.market"
    ) is not None

    assert read_test_value(
        "email.important"
    ) == {
        "status": "known-good",
        "count": 2,
    }

    print(
        "PASS world state: successful reads published independently"
    )
    print(
        "PASS RAM preservation: failed refresh did not overwrite known-good state"
    )

    clear_test_state()


def main():
    print(
        "P.E.P.P.E.R. Phase 16C.7 Final Validation"
    )
    print(
        "----------------------------------------"
    )

    clear_test_state()

    try:
        test_planner()
        test_parallel_benchmark_and_exactly_once()
        test_approval_boundary()
        test_world_state_publication_and_preservation()
    finally:
        clear_test_state()

    print()
    print(
        "PHASE 16C.7 FINAL VALIDATION PASSED"
    )


if __name__ == "__main__":
    main()
