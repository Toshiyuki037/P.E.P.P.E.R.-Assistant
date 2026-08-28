"""
P.E.P.P.E.R. Phase 16I Final Validation
"""

from __future__ import annotations

from assistant.autonomy import (
    AutonomyGate,
    AutonomyPolicy,
    AutonomyRequest,
)
from assistant.events import EVENT_BUS
from assistant.events.definitions import (
    AUTONOMY_ALLOWED,
    AUTONOMY_APPROVAL_REQUIRED,
    AUTONOMY_BLOCKED,
)


def request(**kwargs):
    defaults = {
        "action": "validation.action",
        "category": "local_read",
        "read_only": True,
        "external_side_effect": False,
        "destructive": False,
        "approval_granted": False,
        "background": False,
        "source": "validator",
    }
    defaults.update(kwargs)
    return AutonomyRequest(**defaults)


def test_safe_read_allowed():
    gate = AutonomyGate(policy=AutonomyPolicy())

    decision = gate.evaluate(
        request(
            action="read.world_state",
            category="world_state_read",
        )
    )

    assert decision.allowed is True
    assert decision.requires_approval is False
    assert decision.risk_level == "low"

    print("PASS 16I safe read-only autonomy")


def test_external_side_effect_requires_approval():
    gate = AutonomyGate(policy=AutonomyPolicy())

    pending = gate.evaluate(
        request(
            action="send.email",
            category="integration_write",
            read_only=False,
            external_side_effect=True,
        )
    )

    assert pending.allowed is False
    assert pending.requires_approval is True

    approved = gate.evaluate(
        request(
            action="send.email",
            category="integration_write",
            read_only=False,
            external_side_effect=True,
            approval_granted=True,
        )
    )

    assert approved.allowed is True
    assert approved.requires_approval is True

    print("PASS 16I external side effects require explicit approval")


def test_destructive_requires_approval():
    gate = AutonomyGate(policy=AutonomyPolicy())

    decision = gate.evaluate(
        request(
            action="delete.file",
            category="local_write",
            read_only=False,
            destructive=True,
        )
    )

    assert decision.allowed is False
    assert decision.requires_approval is True
    assert decision.risk_level == "high"

    print("PASS 16I destructive action boundary")


def test_background_cannot_consume_approval():
    gate = AutonomyGate(policy=AutonomyPolicy())

    decision = gate.evaluate(
        request(
            action="send.email.background",
            category="integration_write",
            read_only=False,
            external_side_effect=True,
            approval_granted=True,
            background=True,
        )
    )

    assert decision.allowed is False
    assert decision.requires_approval is True

    print("PASS 16I background side-effect boundary")


def test_unknown_fails_closed():
    gate = AutonomyGate(policy=AutonomyPolicy())

    decision = gate.evaluate(
        request(
            action="mystery.action",
            category="unknown",
            read_only=True,
        )
    )

    assert decision.allowed is False
    assert decision.requires_approval is False
    assert decision.risk_level == "blocked"

    print("PASS 16I unknown actions fail closed")


def test_non_read_only_safe_category_fails_closed():
    gate = AutonomyGate(policy=AutonomyPolicy())

    decision = gate.evaluate(
        request(
            action="mutate.world_state",
            category="world_state_read",
            read_only=False,
        )
    )

    assert decision.allowed is False

    print("PASS 16I mislabeled mutation fails closed")


def test_computation_allowed():
    gate = AutonomyGate(policy=AutonomyPolicy())

    decision = gate.evaluate(
        request(
            action="compute.summary",
            category="computation",
            read_only=False,
        )
    )

    assert decision.allowed is True
    assert decision.requires_approval is False

    print("PASS 16I local computation autonomy")


def test_gate_enforcement():
    gate = AutonomyGate(policy=AutonomyPolicy())

    gate.require_allowed(
        request(
            action="verify.result",
            category="verification",
            read_only=False,
        )
    )

    try:
        gate.require_allowed(
            request(
                action="send.message",
                category="integration_write",
                read_only=False,
                external_side_effect=True,
            )
        )
    except PermissionError:
        pass
    else:
        raise AssertionError(
            "Blocked action was not rejected by require_allowed()."
        )

    print("PASS 16I enforceable autonomy gate")


def test_events():
    gate = AutonomyGate(policy=AutonomyPolicy())
    seen = []

    topics = [
        AUTONOMY_ALLOWED,
        AUTONOMY_APPROVAL_REQUIRED,
        AUTONOMY_BLOCKED,
    ]

    tokens = [
        EVENT_BUS.subscribe(
            topic,
            lambda event, topic=topic: seen.append(topic),
        )
        for topic in topics
    ]

    try:
        gate.evaluate(
            request(
                action="read.system",
                category="local_read",
            )
        )
        gate.evaluate(
            request(
                action="send.email",
                category="integration_write",
                read_only=False,
                external_side_effect=True,
            )
        )
        gate.evaluate(
            request(
                action="unknown",
                category="unknown",
            )
        )
    finally:
        for token in tokens:
            EVENT_BUS.unsubscribe(token)

    assert AUTONOMY_ALLOWED in seen
    assert AUTONOMY_APPROVAL_REQUIRED in seen
    assert AUTONOMY_BLOCKED in seen

    print("PASS 16I autonomy decision events")


def main():
    print("P.E.P.P.E.R. Phase 16I Final Validation")
    print("--------------------------------------")

    test_safe_read_allowed()
    test_external_side_effect_requires_approval()
    test_destructive_requires_approval()
    test_background_cannot_consume_approval()
    test_unknown_fails_closed()
    test_non_read_only_safe_category_fails_closed()
    test_computation_allowed()
    test_gate_enforcement()
    test_events()

    print()
    print("PHASE 16I FINAL VALIDATION PASSED")


if __name__ == "__main__":
    main()
