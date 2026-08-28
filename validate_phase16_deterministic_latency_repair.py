from types import SimpleNamespace
from unittest.mock import patch

import assistant.brain as brain
from assistant.world_state.core import WORLD_STATE


def weather_test():
    intent = SimpleNamespace(capability="weather.current")

    with patch.object(
        brain,
        "plan_integration_prefetch",
        return_value=[intent],
    ), patch.object(
        brain,
        "prefetch_relevant_integrations",
        return_value=None,
    ) as prefetch, patch.object(
        brain,
        "render_prefetched_integration_response",
        return_value="Current weather test response.",
    ), patch.object(
        brain,
        "plan_tool_request",
        side_effect=AssertionError(
            "semantic planner must not run for deterministic current weather"
        ),
    ):
        result = brain.handle_tool_request(
            "What's the weather right now?"
        )

    assert result["handled"] is True
    assert result["response"] == "Current weather test response."
    prefetch.assert_called_once()


def local_state_refresh_test():
    WORLD_STATE.delete("computer.active_window")

    refreshed = {
        "timestamp": "validator",
        "needs": {
            "system": True,
            "workspace": False,
            "all_workspaces": False,
            "applications": False,
            "terminal": False,
            "clipboard": False,
        },
        "system": {
            "active_window": "Validator Window",
            "active_window_title": "Validator Window",
            "active_process": {
                "name": "validator.exe",
            },
            "visible_applications": [],
        },
        "workspace": None,
        "clipboard": None,
    }

    def publish_refresh(_context):
        WORLD_STATE.set(
            "computer.active_window",
            "Validator Window",
            source="validator",
            fresh_for_seconds=15.0,
            confidence=1.0,
        )

    with patch.object(
        brain,
        "plan_integration_prefetch",
        return_value=[],
    ), patch.object(
        brain,
        "get_live_context",
        return_value=refreshed,
    ) as refresh, patch.object(
        brain,
        "publish_live_context_snapshot",
        side_effect=publish_refresh,
    ), patch.object(
        brain,
        "plan_tool_request",
        side_effect=AssertionError(
            "semantic planner must not run after local state refresh"
        ),
    ):
        result = brain.handle_tool_request(
            "What window is currently active?"
        )

    assert result["handled"] is True
    assert "Validator Window" in result["response"]
    refresh.assert_called_once()
    WORLD_STATE.delete("computer.active_window")


def normal_fallback_test():
    with patch.object(
        brain,
        "plan_integration_prefetch",
        return_value=[],
    ), patch.object(
        brain,
        "_deterministic_current_computer_state_response",
        return_value=None,
    ), patch.object(
        brain,
        "should_consider_tools",
        return_value=False,
    ):
        result = brain.handle_tool_request(
            "What is the capital of Japan?"
        )

    assert result["handled"] is False


def main():
    print("P.E.P.P.E.R. Phase 16 Deterministic Latency Repair Validation")
    print("--------------------------------------------------------------")

    weather_test()
    print("PASS weather.current bypasses semantic Phase 6 planner")

    local_state_refresh_test()
    print("PASS expired active-window RAM refreshes locally and bypasses planner")

    normal_fallback_test()
    print("PASS unrelated factual question keeps normal fast reasoning fallback")

    print()
    print("PHASE 16 DETERMINISTIC LATENCY REPAIR VALIDATION PASSED")


if __name__ == "__main__":
    main()
