from unittest.mock import patch
from types import SimpleNamespace

import assistant.brain as brain
from assistant.world_state.core import WORLD_STATE


def test_weather_location_enrichment():
    captured = []
    fake_location = SimpleNamespace(latitude=21.3069, longitude=-157.8583)

    def fake_prefetch(requests, max_workers=4):
        captured.extend(requests)
        return []

    with patch.object(brain, "get_foreground_location", return_value=fake_location), patch.object(
        brain, "prefetch_integrations_to_world_state", side_effect=fake_prefetch
    ):
        brain.prefetch_relevant_integrations("what's the weather right now?")

    request = captured[0]
    assert request.capability == "weather.current"
    assert request.provider == "weather"
    assert request.account_id == "public"
    assert request.routing_mode == "explicit_account"
    assert request.arguments == {"latitude": 21.3069, "longitude": -157.8583}
    print("PASS weather prefetch receives trusted lat/lon")


def test_weather_preference_fallback():
    captured = []

    def fake_prefetch(requests, max_workers=4):
        captured.extend(requests)
        return []

    with patch.object(brain, "get_foreground_location", return_value=None), patch.object(
        brain, "get_default_weather_location", return_value="Honolulu"
    ), patch.object(
        brain, "prefetch_integrations_to_world_state", side_effect=fake_prefetch
    ):
        brain.prefetch_relevant_integrations("weather right now")

    request = captured[0]
    assert request.arguments == {"location": "Honolulu"}
    assert request.provider == "weather"
    assert request.account_id == "public"
    print("PASS weather prefetch falls back to saved preference")


def test_active_window_ram_fastpath():
    WORLD_STATE.set(
        "computer.active_window",
        "Test Window - Google Chrome",
        source="runtime-cleanup-validator",
        fresh_for_seconds=60,
        confidence=1.0,
    )

    with patch.object(
        brain,
        "plan_tool_request",
        side_effect=AssertionError("semantic planner must not run"),
    ):
        result = brain.handle_tool_request("what window is currently active")

    assert result["handled"] is True
    assert "Test Window - Google Chrome" in result["response"]
    WORLD_STATE.delete("computer.active_window")
    print("PASS active-window question bypasses semantic planner")


def main():
    print("P.E.P.P.E.R. Phase 16 Runtime Cleanup Validation")
    print("------------------------------------------------")
    test_weather_location_enrichment()
    test_weather_preference_fallback()
    test_active_window_ram_fastpath()
    print()
    print("PHASE 16 RUNTIME CLEANUP VALIDATION PASSED")


if __name__ == "__main__":
    main()
