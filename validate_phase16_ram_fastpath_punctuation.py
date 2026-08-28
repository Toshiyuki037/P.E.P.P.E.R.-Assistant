from unittest.mock import patch

import assistant.brain as brain
from assistant.world_state.core import WORLD_STATE


def publish_window():
    WORLD_STATE.set(
        "computer.active_window",
        {"title": "Latency Test Window"},
        source="phase16-validator",
        fresh_for_seconds=60.0,
        confidence=1.0,
    )


def assert_fast(message):
    publish_window()

    with patch.object(
        brain,
        "plan_tool_request",
        side_effect=AssertionError(
            "semantic Phase 6 planner must not run for deterministic window state"
        ),
    ):
        result = brain.handle_tool_request(message)

    assert result["handled"] is True
    assert "Latency Test Window" in result["response"]


def main():
    print("P.E.P.P.E.R. Phase 16 RAM Fast-Path Punctuation Validation")
    print("-----------------------------------------------------------")

    variants = (
        "What window is currently active?",
        "What window is currently active.",
        "What window is currently active!",
        "what window is currently active",
        "What's the active window?",
        "Which window is active?",
    )

    for message in variants:
        assert_fast(message)

    print("PASS punctuation variants bypass semantic Phase 6 planning")
    WORLD_STATE.delete("computer.active_window")
    print()
    print("PHASE 16 RAM FAST-PATH PUNCTUATION VALIDATION PASSED")


if __name__ == "__main__":
    main()
