"""
P.E.P.P.E.R. Phase 16G Final Validation
"""

from __future__ import annotations

from assistant.events import EVENT_BUS, publish
from assistant.events.definitions import (
    BACKGROUND_JOB_FINISHED,
    PROACTIVE_DEFERRED,
    PROACTIVE_SURFACED,
    PROACTIVE_SUPPRESSED,
)
from assistant.proactive import (
    ProactiveCandidate,
    ProactiveEngine,
    ProactivePolicy,
)


def candidate(
    *,
    message="Something requires attention.",
    urgency=7,
    dedupe_key="test:item",
):
    return ProactiveCandidate(
        topic="validation",
        message=message,
        urgency=urgency,
        dedupe_key=dedupe_key,
        source="validator",
    )


def test_surface():
    engine = ProactiveEngine(
        policy=ProactivePolicy(
            minimum_urgency=5,
            dedupe_seconds=300,
        )
    )

    decision = engine.consider(candidate())
    assert decision.action == "surface"
    pending = engine.pending()
    assert len(pending) == 1
    assert pending[0].message == "Something requires attention."

    print("PASS 16G surface policy + proactive inbox")


def test_low_value_suppression():
    engine = ProactiveEngine(
        policy=ProactivePolicy(
            minimum_urgency=5,
        )
    )

    decision = engine.consider(
        candidate(
            urgency=2,
            dedupe_key="low",
        )
    )

    assert decision.action == "suppress"
    assert engine.pending() == []

    print("PASS 16G low-value suppression")


def test_deduplication():
    engine = ProactiveEngine(
        policy=ProactivePolicy(
            minimum_urgency=5,
            dedupe_seconds=300,
        )
    )

    first = engine.consider(
        candidate(dedupe_key="same")
    )
    second = engine.consider(
        candidate(dedupe_key="same")
    )

    assert first.action == "surface"
    assert second.action == "suppress"
    assert second.reason == "duplicate cooldown"
    assert len(engine.pending()) == 1

    print("PASS 16G duplicate cooldown")


def test_muted_defer():
    policy = ProactivePolicy(
        minimum_urgency=5,
    )
    engine = ProactiveEngine(policy=policy)

    policy.set_muted(True)
    decision = engine.consider(
        candidate(dedupe_key="muted")
    )

    assert decision.action == "defer"
    assert engine.pending() == []

    policy.set_muted(False)
    decision = engine.consider(
        candidate(dedupe_key="muted")
    )

    assert decision.action == "surface"

    print("PASS 16G mute/defer behavior")


def test_event_emission():
    engine = ProactiveEngine(
        policy=ProactivePolicy(
            minimum_urgency=5,
        )
    )
    seen = []

    tokens = [
        EVENT_BUS.subscribe(
            PROACTIVE_SURFACED,
            lambda event: seen.append(event.topic),
        ),
        EVENT_BUS.subscribe(
            PROACTIVE_SUPPRESSED,
            lambda event: seen.append(event.topic),
        ),
        EVENT_BUS.subscribe(
            PROACTIVE_DEFERRED,
            lambda event: seen.append(event.topic),
        ),
    ]

    try:
        engine.consider(
            candidate(
                urgency=7,
                dedupe_key="surface-event",
            )
        )
        engine.consider(
            candidate(
                urgency=1,
                dedupe_key="suppress-event",
            )
        )
        engine.policy.set_muted(True)
        engine.consider(
            candidate(
                urgency=9,
                dedupe_key="defer-event",
            )
        )
    finally:
        for token in tokens:
            EVENT_BUS.unsubscribe(token)

    assert PROACTIVE_SURFACED in seen
    assert PROACTIVE_SUPPRESSED in seen
    assert PROACTIVE_DEFERRED in seen

    print("PASS 16G proactive decision events")


def test_background_failure_subscription():
    engine = ProactiveEngine(
        policy=ProactivePolicy(
            minimum_urgency=5,
        )
    )
    engine.install_default_subscriptions()

    try:
        publish(
            BACKGROUND_JOB_FINISHED,
            {
                "task_id": "task_validation",
                "success": True,
                "error": "",
            },
            source="validator",
        )

        assert engine.pending() == []

        publish(
            BACKGROUND_JOB_FINISHED,
            {
                "task_id": "task_validation",
                "success": False,
                "error": "controlled failure",
            },
            source="validator",
        )

        pending = engine.pending()
        assert len(pending) == 1
        assert pending[0].topic == "background.task_failed"
        assert "controlled failure" in pending[0].message

        # Same task failure is suppressed by dedupe.
        publish(
            BACKGROUND_JOB_FINISHED,
            {
                "task_id": "task_validation",
                "success": False,
                "error": "controlled failure",
            },
            source="validator",
        )

        assert len(engine.pending()) == 1
    finally:
        engine.unsubscribe_all()

    print("PASS 16G event-driven background failure surfacing")


def test_inbox_bound():
    engine = ProactiveEngine(
        policy=ProactivePolicy(
            minimum_urgency=1,
            dedupe_seconds=0,
        ),
        inbox_limit=3,
    )

    for index in range(5):
        engine.consider(
            candidate(
                message=f"Notice {index}",
                urgency=5,
                dedupe_key=f"notice:{index}",
            )
        )

    pending = engine.pending()

    assert len(pending) == 3
    assert [item.message for item in pending] == [
        "Notice 2",
        "Notice 3",
        "Notice 4",
    ]

    print("PASS 16G bounded proactive inbox")


def main():
    print("P.E.P.P.E.R. Phase 16G Final Validation")
    print("--------------------------------------")

    test_surface()
    test_low_value_suppression()
    test_deduplication()
    test_muted_defer()
    test_event_emission()
    test_background_failure_subscription()
    test_inbox_bound()

    print()
    print("PHASE 16G FINAL VALIDATION PASSED")


if __name__ == "__main__":
    main()
