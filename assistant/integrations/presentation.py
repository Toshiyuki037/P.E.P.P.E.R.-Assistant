"""
P.E.P.P.E.R. - Deterministic Integration Presentation

Phase 16A

Purpose:
    Render high-confidence structured integration results locally so simple
    integration reads do not require a second language-model call.

Safety:
    - Never executes tools.
    - Never changes permission or approval state.
    - Only renders successful integration evidence.
    - Unsupported or malformed results return None.
    - brain.py retains its existing GPT-backed renderer as fallback.

Canonical execution shape:
    execution["result"]["evidence"][i]["data"]
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def render_integration_response(
    *,
    arguments: dict,
    execution: dict,
) -> str | None:
    capability = (
        str(
            (arguments or {}).get(
                "capability",
                "",
            )
        )
        .strip()
        .lower()
    )

    if not capability:
        return None

    aggregate = _get_aggregate_result(execution)

    if aggregate is None:
        return None

    aggregate_capability = (
        str(
            aggregate.get("capability", "")
        )
        .strip()
        .lower()
    )

    if (
        aggregate_capability
        and aggregate_capability != capability
    ):
        return None

    if capability == "weather.current":
        data = _first_successful_evidence_data(
            aggregate,
            capability=capability,
        )

        if data is None:
            return None

        return _render_weather_current(data)

    return None


def _get_aggregate_result(
    execution: dict,
) -> dict | None:
    if not isinstance(execution, Mapping):
        return None

    if not execution.get("success"):
        return None

    if not execution.get("executed"):
        return None

    if (
        str(execution.get("tool", ""))
        .strip()
        .lower()
        != "integration_execute"
    ):
        return None

    aggregate = execution.get("result")

    if not isinstance(aggregate, Mapping):
        return None

    aggregate = dict(aggregate)

    if not aggregate.get("success"):
        return None

    evidence = aggregate.get("evidence")

    if not isinstance(evidence, list):
        return None

    return aggregate


def _first_successful_evidence_data(
    aggregate: dict,
    *,
    capability: str,
) -> dict | None:
    evidence_items = aggregate.get("evidence") or []

    for evidence in evidence_items:
        if not isinstance(evidence, Mapping):
            continue

        if not evidence.get("success"):
            continue

        if not evidence.get("executed"):
            continue

        evidence_capability = (
            str(evidence.get("capability", ""))
            .strip()
            .lower()
        )

        if (
            evidence_capability
            and evidence_capability != capability
        ):
            continue

        data = evidence.get("data")

        if isinstance(data, Mapping):
            return dict(data)

    return None


def _number(
    value: Any,
    *,
    digits: int = 1,
) -> str | None:
    if value is None:
        return None

    try:
        number = round(float(value), digits)
    except (TypeError, ValueError):
        return None

    if number.is_integer():
        return str(int(number))

    return (
        f"{number:.{digits}f}"
        .rstrip("0")
        .rstrip(".")
    )


def _degrees_to_compass(
    value: Any,
) -> str | None:
    try:
        degrees = float(value) % 360.0
    except (TypeError, ValueError):
        return None

    directions = (
        "N", "NNE", "NE", "ENE",
        "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW",
        "W", "WNW", "NW", "NNW",
    )

    index = int((degrees + 11.25) // 22.5) % 16
    return directions[index]


_WEATHER_CODES = {
    0: "clear",
    1: "mostly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "foggy with rime",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    56: "light freezing drizzle",
    57: "freezing drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "freezing rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    77: "snow grains",
    80: "light rain showers",
    81: "rain showers",
    82: "heavy rain showers",
    85: "light snow showers",
    86: "heavy snow showers",
    95: "thunderstorms",
    96: "thunderstorms with light hail",
    99: "thunderstorms with heavy hail",
}


def _weather_description(
    value: Any,
) -> str | None:
    try:
        code = int(value)
    except (TypeError, ValueError):
        return None

    return _WEATHER_CODES.get(code)


def _has_precipitation(
    current: dict,
) -> bool:
    for key in (
        "precipitation",
        "rain",
        "showers",
        "snowfall",
    ):
        value = current.get(key)

        try:
            if value is not None and float(value) > 0:
                return True
        except (TypeError, ValueError):
            continue

    return False


def _render_weather_current(
    data: dict,
) -> str | None:
    if not isinstance(data, Mapping):
        return None

    current = data.get("current")

    if not isinstance(current, Mapping):
        return None

    current = dict(current)

    temperature = _number(
        current.get("temperature_2m")
    )

    if temperature is None:
        return None

    location = str(
        data.get("location") or ""
    ).strip()

    apparent = _number(
        current.get("apparent_temperature")
    )

    humidity = _number(
        current.get("relative_humidity_2m"),
        digits=0,
    )

    cloud_cover = _number(
        current.get("cloud_cover"),
        digits=0,
    )

    wind_speed = _number(
        current.get("wind_speed_10m")
    )

    wind_gusts = _number(
        current.get("wind_gusts_10m")
    )

    wind_direction = _degrees_to_compass(
        current.get("wind_direction_10m")
    )

    description = _weather_description(
        current.get("weather_code")
    )

    subject = (
        f"Current weather in {location}"
        if location
        else "Current weather"
    )

    response = f"{subject}: {temperature}°F"

    if description:
        response += f", {description}"

    if (
        apparent is not None
        and apparent != temperature
    ):
        response += f", feels like {apparent}°F"

    response += "."

    details = []

    if cloud_cover is not None:
        details.append(
            f"Cloud cover is {cloud_cover}%"
        )

    if humidity is not None:
        details.append(
            f"humidity is {humidity}%"
        )

    if wind_speed is not None:
        wind = f"winds are {wind_speed} mph"

        if wind_direction:
            wind += f" from the {wind_direction}"

        if wind_gusts is not None:
            wind += f", gusting to {wind_gusts} mph"

        details.append(wind)

    if details:
        response += " " + ", ".join(details) + "."

    if not _has_precipitation(current):
        response += " No precipitation is being reported."

    return response
