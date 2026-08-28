from unittest.mock import patch
import assistant.brain as brain
from assistant.world_state.core import WORLD_STATE

WEATHER_PAYLOAD = {
    "location": "Honolulu",
    "current": {
        "temperature_2m": 80.0,
        "apparent_temperature": 82.0,
        "relative_humidity_2m": 70,
        "cloud_cover": 25,
        "wind_speed_10m": 12.0,
        "wind_gusts_10m": 18.0,
        "wind_direction_10m": 70,
        "weather_code": 1,
        "precipitation": 0.0,
    },
}

def publish_weather():
    WORLD_STATE.set(
        "integration.weather.current",
        WEATHER_PAYLOAD,
        source="weather",
        fresh_for_seconds=300,
        confidence=1.0,
        metadata={"capability": "weather.current"},
    )

def test_prefetched_weather_renders():
    publish_weather()
    response = brain.render_prefetched_integration_response(
        "what's the weather right now?"
    )
    assert response
    assert "80" in response
    assert "Honolulu" in response
    print("PASS fresh prefetched weather renders deterministically")

def test_chat_does_not_call_reasoning_model_for_weather():
    WORLD_STATE.delete("integration.weather.current")

    def fake_prefetch(message):
        publish_weather()
        return []

    with patch.object(
        brain,
        "prefetch_relevant_integrations",
        side_effect=fake_prefetch,
    ), patch.object(
        brain.client.responses,
        "create",
        side_effect=AssertionError("reasoning model must not run"),
    ):
        response = brain.chat("what's the weather right now?")

    assert "80" in response
    print("PASS weather chat consumes prefetch without reasoning hallucination")

def test_non_weather_still_falls_back():
    response = brain.render_prefetched_integration_response(
        "what is the capital of japan?"
    )
    assert response is None
    print("PASS unrelated conversation remains on normal reasoning path")

def main():
    print("P.E.P.P.E.R. Phase 16 Weather Delivery Validation")
    print("-------------------------------------------------")
    test_prefetched_weather_renders()
    test_chat_does_not_call_reasoning_model_for_weather()
    test_non_weather_still_falls_back()
    WORLD_STATE.delete("integration.weather.current")
    print()
    print("PHASE 16 WEATHER DELIVERY VALIDATION PASSED")

if __name__ == "__main__":
    main()
