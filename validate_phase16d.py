"""
P.E.P.P.E.R. Phase 16D Final Validator

Run from repository root:
    python -m py_compile .\assistant\events\bus.py
    python .\validate_phase16d.py
"""

from __future__ import annotations

from threading import Thread

from assistant.events import EventBus, EVENT_BUS
from assistant.events.definitions import (
    INTEGRATION_UPDATED,
    WORLD_STATE_CHANGED,
    WORLD_STATE_CLEARED,
    WORLD_STATE_DELETED,
)
from assistant.world_state.core import WORLD_STATE
from assistant.world_state.integration_adapter import publish_integration_execution


PREFIX = "validation.phase16d."


def clear_validation_state():
    for key in list(WORLD_STATE.keys(prefix=PREFIX)):
        WORLD_STATE.delete(key)


def test_order_and_unsubscribe():
    bus = EventBus()
    seen = []

    first = bus.subscribe("test.order", lambda event: seen.append("first"))
    bus.subscribe("test.order", lambda event: seen.append("second"))

    report = bus.publish("test.order", {"ok": True}, source="validator")
    assert seen == ["first", "second"], seen
    assert report.delivered == 2 and report.failed == 0

    assert bus.unsubscribe(first) is True
    seen.clear()
    bus.publish("test.order")
    assert seen == ["second"], seen
    print("PASS 16D.1 deterministic ordering + unsubscribe")


def test_failure_isolation():
    bus = EventBus()
    seen = []

    def broken(event):
        raise RuntimeError("controlled subscriber failure")

    bus.subscribe("test.failure", broken)
    bus.subscribe("test.failure", lambda event: seen.append("survived"))

    report = bus.publish("test.failure")
    assert seen == ["survived"]
    assert report.delivered == 2
    assert report.succeeded == 1
    assert report.failed == 1
    print("PASS 16D.6 subscriber failure isolation")


def test_recursion_guard():
    bus = EventBus(max_publish_depth=4)
    reports = []

    def recursive(event):
        reports.append(bus.publish("test.loop"))

    bus.subscribe("test.loop", recursive)
    root = bus.publish("test.loop")

    blocked = [report for report in reports if report.blocked]
    assert root.blocked is False
    assert blocked, "Expected recursion guard to block nested publication."
    print("PASS 16D.6 recursion/event-loop protection")


def test_thread_safety():
    bus = EventBus()
    seen = []
    bus.subscribe("test.thread", lambda event: seen.append(event.payload))

    threads = [
        Thread(target=bus.publish, args=("test.thread", index))
        for index in range(20)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(seen) == list(range(20))
    print("PASS 16D.1 thread-safe concurrent publication")


def test_world_state_events():
    clear_validation_state()
    seen = []

    tokens = [
        EVENT_BUS.subscribe(WORLD_STATE_CHANGED, lambda event: seen.append((event.topic, event.payload))),
        EVENT_BUS.subscribe(WORLD_STATE_DELETED, lambda event: seen.append((event.topic, event.payload))),
        EVENT_BUS.subscribe(WORLD_STATE_CLEARED, lambda event: seen.append((event.topic, event.payload))),
    ]

    try:
        WORLD_STATE.set(
            PREFIX + "alpha",
            {"value": 1},
            source="phase16d.validator",
            fresh_for_seconds=60,
        )
        WORLD_STATE.set(
            PREFIX + "alpha",
            {"value": 2},
            source="phase16d.validator",
            fresh_for_seconds=60,
        )
        WORLD_STATE.delete(PREFIX + "alpha")

        WORLD_STATE.set(
            PREFIX + "beta",
            {"value": 3},
            source="phase16d.validator",
            fresh_for_seconds=60,
        )
        WORLD_STATE.clear()

        topics = [topic for topic, _ in seen]
        assert topics.count(WORLD_STATE_CHANGED) >= 3
        assert WORLD_STATE_DELETED in topics
        assert WORLD_STATE_CLEARED in topics

        alpha_updates = [
            payload for topic, payload in seen
            if topic == WORLD_STATE_CHANGED and payload["key"] == PREFIX + "alpha"
        ]
        assert alpha_updates[0]["previous_record"] is None
        assert alpha_updates[1]["previous_record"] is not None
    finally:
        for token in tokens:
            EVENT_BUS.unsubscribe(token)
        clear_validation_state()

    print("PASS 16D.3 world-state mutation events")


def test_integration_updated_event():
    seen = []
    token = EVENT_BUS.subscribe(
        INTEGRATION_UPDATED,
        lambda event: seen.append(event),
    )

    capability = "validation.phase16d.integration"
    key = "integration." + capability

    try:
        execution = {
            "success": True,
            "capability": capability,
            "provider": "phase16d-validator",
            "routing_mode": "all_available",
            "result": {
                "success": True,
                "evidence": [
                    {
                        "success": True,
                        "data": {
                            "message": "controlled integration payload"
                        },
                    }
                ],
            },
        }

        record = publish_integration_execution(
            execution,
            capability=capability,
            provider="phase16d-validator",
            routing_mode="all_available",
            fresh_for_seconds=60,
        )

        assert record is not None
        assert seen, "integration.updated was not emitted."
        event = seen[-1]
        assert event.payload["capability"] == capability
        assert event.payload["world_state_key"] == key
        assert WORLD_STATE.get(key) is not None
    finally:
        EVENT_BUS.unsubscribe(token)
        WORLD_STATE.delete(key)

    print("PASS 16D.4 integration-result event")


def test_runtime_subscription_pattern():
    bus = EventBus()
    reactions = []

    token = bus.subscribe(
        "integration.updated",
        lambda event: reactions.append(
            event.payload["capability"]
        ),
    )

    bus.publish(
        "integration.updated",
        {"capability": "weather.current"},
        source="validator",
    )
    bus.publish(
        "integration.updated",
        {"capability": "calendar.upcoming"},
        source="validator",
    )

    bus.unsubscribe(token)

    assert reactions == [
        "weather.current",
        "calendar.upcoming",
    ]
    print("PASS 16D.5 runtime subscription pattern")


def main():
    print("P.E.P.P.E.R. Phase 16D Final Validation")
    print("--------------------------------------")

    test_order_and_unsubscribe()
    test_failure_isolation()
    test_recursion_guard()
    test_thread_safety()
    test_world_state_events()
    test_integration_updated_event()
    test_runtime_subscription_pattern()

    print()
    print("PHASE 16D FINAL VALIDATION PASSED")


if __name__ == "__main__":
    main()
