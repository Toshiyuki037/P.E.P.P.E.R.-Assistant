"""
P.E.P.P.E.R. - Phase 16C.6 Validation

Validates:
    1. Independent work overlaps in wall-clock time.
    2. One failing sibling does not discard successful siblings.
    3. Successful prefetch-style results can publish into Phase 16B RAM.
    4. A failed sibling does not overwrite an existing good RAM value.

This test is controlled and offline. It does not call real providers.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter, sleep
from unittest.mock import patch

from assistant.performance.parallel import ParallelJob, execute_parallel
from assistant.world_state.core import WORLD_STATE


TEST_PREFIX = "validation.phase16c6."


@dataclass
class FakeRecord:
    key: str


def clear_test_state():
    for key in list(WORLD_STATE.keys()):
        if str(key).startswith(TEST_PREFIX):
            WORLD_STATE.delete(key)


def fake_publish(capability: str, value):
    key = TEST_PREFIX + capability
    return WORLD_STATE.set(
        key=key,
        value=value,
        source="phase16c6.validation",
        fresh_for_seconds=60.0,
        confidence=1.0,
        metadata={"controlled_test": True},
    )


def read_test_value(capability: str):
    record = WORLD_STATE.get(
        TEST_PREFIX + capability
    )
    return None if record is None else record.value


def delayed_success(name: str, delay: float = 0.35):
    sleep(delay)
    return {
        "name": name,
        "payload": f"{name}-data",
    }


def delayed_failure(name: str, delay: float = 0.35):
    sleep(delay)
    raise RuntimeError(
        f"controlled failure: {name}"
    )


def test_parallel_overlap():
    jobs = [
        ParallelJob(
            name="weather",
            function=delayed_success,
            args=("weather",),
        ),
        ParallelJob(
            name="email",
            function=delayed_success,
            args=("email",),
        ),
        ParallelJob(
            name="calendar",
            function=delayed_success,
            args=("calendar",),
        ),
        ParallelJob(
            name="market",
            function=delayed_success,
            args=("market",),
        ),
    ]

    started = perf_counter()
    results = execute_parallel(
        jobs,
        max_workers=4,
    )
    elapsed = perf_counter() - started

    assert all(
        result.success
        for result in results
    ), results

    # Sequential time is ~1.4s. Keep generous CI/Windows headroom while still
    # proving the jobs were not run serially.
    assert elapsed < 1.0, (
        f"Expected parallel overlap; wall time was {elapsed:.3f}s"
    )

    print(
        f"PASS overlap: {elapsed:.3f}s wall for four 0.35s jobs"
    )


def test_exception_isolation():
    jobs = [
        ParallelJob(
            name="weather",
            function=delayed_success,
            args=("weather", 0.20),
        ),
        ParallelJob(
            name="email",
            function=delayed_failure,
            args=("email", 0.20),
        ),
        ParallelJob(
            name="calendar",
            function=delayed_success,
            args=("calendar", 0.20),
        ),
        ParallelJob(
            name="market",
            function=delayed_success,
            args=("market", 0.20),
        ),
    ]

    results = execute_parallel(
        jobs,
        max_workers=4,
    )

    by_name = {
        result.name: result
        for result in results
    }

    assert by_name["weather"].success is True
    assert by_name["calendar"].success is True
    assert by_name["market"].success is True

    assert by_name["email"].success is False
    assert "controlled failure" in by_name["email"].error

    print(
        "PASS exception isolation: 3 siblings survived 1 controlled failure"
    )


def test_success_publication_and_failed_preservation():
    clear_test_state()

    # Seed a known-good email value. The simulated failed refresh must not
    # replace or erase it.
    fake_publish(
        "email.important",
        {
            "status": "known-good",
            "count": 2,
        },
    )

    jobs = [
        ParallelJob(
            name="weather.current",
            function=delayed_success,
            args=("weather.current", 0.15),
        ),
        ParallelJob(
            name="email.important",
            function=delayed_failure,
            args=("email.important", 0.15),
        ),
        ParallelJob(
            name="calendar.upcoming",
            function=delayed_success,
            args=("calendar.upcoming", 0.15),
        ),
        ParallelJob(
            name="finance.market",
            function=delayed_success,
            args=("finance.market", 0.15),
        ),
    ]

    results = execute_parallel(
        jobs,
        max_workers=4,
    )

    for result in results:
        if not result.success:
            # This mirrors the 16C.3 rule: failed reads are not published.
            continue

        fake_publish(
            result.name,
            result.value,
        )

    weather = read_test_value(
        "weather.current"
    )
    email = read_test_value(
        "email.important"
    )
    calendar = read_test_value(
        "calendar.upcoming"
    )
    market = read_test_value(
        "finance.market"
    )

    assert weather is not None
    assert calendar is not None
    assert market is not None

    assert email == {
        "status": "known-good",
        "count": 2,
    }, (
        "Failed refresh overwrote or erased the existing good email RAM value."
    )

    print(
        "PASS RAM publication: successful siblings published independently"
    )
    print(
        "PASS failed preservation: failed email refresh left good RAM untouched"
    )

    clear_test_state()


def main():
    print(
        "P.E.P.P.E.R. Phase 16C.6 Validation"
    )
    print(
        "----------------------------------"
    )

    clear_test_state()

    try:
        test_parallel_overlap()
        test_exception_isolation()
        test_success_publication_and_failed_preservation()
    finally:
        clear_test_state()

    print()
    print(
        "PHASE 16C.6 VALIDATION PASSED"
    )


if __name__ == "__main__":
    main()
