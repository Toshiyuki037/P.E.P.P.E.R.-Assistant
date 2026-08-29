"""
P.E.P.P.E.R. Good Morning Protocol - collection/composition layer.

Uses the existing Phase 16C prefetch path so weather, calendar, email and
market reads execute concurrently and successful results are published into
Phase 16B operational RAM.

This module deliberately does NOT own scheduling or TTS. Those are runtime
presentation concerns and are wired separately after this layer validates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from assistant.capabilities.integrations.aggregator import (
    aggregate_result_to_dict,
    execute_aggregate,
)
from assistant.observability.performance.parallel import (
    ParallelJob,
    execute_parallel,
)

CAPABILITIES = (
    "weather.current",
    "calendar.upcoming",
    "email.important",
    "finance.performance",
    "finance.market",
)

PREFETCH_PROMPT = (
    "Give me the weather, my calendar, important emails, and a market update."
)


@dataclass
class MorningBriefing:
    generated_at: str
    spoken_text: str
    sections: dict[str, str] = field(default_factory=dict)
    available: dict[str, bool] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


def _first(mapping: Any, *keys, default=None):
    if not isinstance(mapping, dict):
        return default
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", [], {}):
            return value
    return default


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _items(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        for key in ("items", "messages", "results", "events", "data"):
            candidate = value.get(key)
            if isinstance(candidate, list):
                return candidate
    return []


def _weather_sentence(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    current = value.get("current")
    if not isinstance(current, dict):
        current = value
    temperature = _first(current, "temperature_2m", "temperature_f", "temperature", "temp_f", "temp")
    precipitation = _first(current, "precipitation", "rain", "showers", "precipitation_probability", "precip_probability")
    weather_code = _first(current, "weather_code", "weathercode")
    condition = _first(current, "condition", "conditions", "weather", "description", "summary")
    if not condition and weather_code is not None:
        try:
            code = int(weather_code)
            if code == 0: condition = "clear"
            elif code in (1, 2): condition = "mostly clear"
            elif code == 3: condition = "overcast"
            elif code in (45, 48): condition = "foggy"
            elif code in (51, 53, 55, 56, 57): condition = "drizzly"
            elif code in (61, 63, 65, 66, 67, 80, 81, 82): condition = "rainy"
            elif code in (71, 73, 75, 77, 85, 86): condition = "snowy"
            elif code in (95, 96, 99): condition = "stormy"
        except (TypeError, ValueError):
            pass
    parts = []
    if temperature is not None:
        try: parts.append(f"It's currently {round(float(temperature))} degrees outside")
        except (TypeError, ValueError): parts.append(f"It's currently {temperature} degrees outside")
    if condition:
        if parts: parts[-1] += f" and {str(condition).strip().lower()}"
        else: parts.append(f"It's {str(condition).strip().lower()} outside")
    if precipitation is not None:
        try:
            if float(precipitation) <= 0: parts.append("No rain is being reported right now")
            else: parts.append("Rain is being reported right now")
        except (TypeError, ValueError):
            pass
    if not parts:
        return "Weather data is available, but no concise condition summary was found."
    return ". ".join(parts) + "."


def _calendar_sentence(value: Any) -> str:
    items = _items(value)
    count = len(items)

    if count == 0:
        explicit_count = _number(
            _first(value, "count", "event_count")
        ) if isinstance(value, dict) else None
        if explicit_count is not None:
            count = int(explicit_count)

    if count <= 0:
        return "You have no upcoming calendar events in the current briefing window."

    first = items[0] if items else {}
    title = _first(
        first,
        "title",
        "summary",
        "subject",
        "name",
    )
    start = _first(
        first,
        "start",
        "start_time",
        "time",
        "when",
    )

    base = (
        f"You have {count} upcoming calendar "
        f"{'event' if count == 1 else 'events'}"
    )

    if title and start:
        return f"{base}. First is {title} at {start}."
    if title:
        return f"{base}. First is {title}."
    return base + "."


def _email_sentence(value: Any) -> str:
    items = _items(value)
    count = len(items)

    if isinstance(value, dict):
        explicit = _number(
            _first(
                value,
                "count",
                "important_count",
                "unread_important_count",
            )
        )
        if explicit is not None:
            count = int(explicit)

    if count <= 0:
        return "You have no important emails requiring attention."

    return (
        f"You have {count} important "
        f"{'email' if count == 1 else 'emails'} requiring attention."
    )


def _portfolio_sentence(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    if value.get("unavailable"):
        return "Portfolio performance is currently unavailable."
    change = _number(value.get("day_profit_loss_percent"))
    if change is None:
        return ""
    change = float(change)
    magnitude = abs(change)
    if magnitude < 0.05:
        return "Your portfolio is roughly flat today."
    if change > 0:
        return f"Your portfolio is up {magnitude:.1f} percent today."
    return f"Your portfolio is down {magnitude:.1f} percent today."


def _market_sentence(value: Any) -> str:
    if not isinstance(value, dict):
        return ""

    if value.get("unavailable"):
        return "Market data is unavailable this morning."

    summary = _first(value, "summary", "market_summary", "headline", "description")
    if summary:
        text = str(summary).strip()
        return text if text.endswith((".", "!", "?")) else text + "."

    labels = (("SPY", "the S&P 500"), ("QQQ", "the Nasdaq"), ("DIA", "the Dow"))
    moves = []
    changes = []
    statuses = []

    for symbol, label in labels:
        item = value.get(symbol)
        if not isinstance(item, dict):
            continue
        quote = item.get("quote") if isinstance(item.get("quote"), dict) else {}
        regular = item.get("regular") if isinstance(item.get("regular"), dict) else {}

        change = _number(_first(regular, "regularMarketPercentChange"))
        if change is None:
            change = _number(_first(quote, "netPercentChange", "markPercentChange"))
        if change is None:
            continue

        change = float(change)
        changes.append(change)
        status = str(_first(quote, "securityStatus", "status") or "").strip().lower()
        if status:
            statuses.append(status)

        magnitude = abs(change)
        if magnitude < 0.05:
            moves.append(f"{label} roughly flat")
        elif change > 0:
            moves.append(f"{label} up {magnitude:.1f} percent")
        else:
            moves.append(f"{label} down {magnitude:.1f} percent")

    if moves:
        average = sum(changes) / len(changes)
        if all(abs(change) < 0.05 for change in changes):
            direction = "roughly flat"
        elif average > 0.05:
            direction = "higher"
        elif average < -0.05:
            direction = "lower"
        else:
            direction = "mixed"

        verb = "finished" if statuses and all(
            status in {"closed", "normal"} for status in statuses
        ) else "are"

        if len(moves) == 1:
            detail = moves[0]
        elif len(moves) == 2:
            detail = f"{moves[0]} and {moves[1]}"
        else:
            detail = f"{', '.join(moves[:-1])}, and {moves[-1]}"

        return f"Markets {verb} {direction}, with {detail}."

    direction = _first(value, "direction", "trend", "status")
    change = _first(value, "change_percent", "percent_change", "change")
    if direction and change is not None:
        return f"Markets are {direction}, about {change} percent."
    if direction:
        return f"Markets are {direction}."

    return "Market data is available, but no concise market summary was found."

def compose_good_morning_briefing(
    *,
    now: datetime | None = None,
    values: dict[str, Any] | None = None,
) -> MorningBriefing:
    now = now or datetime.now()
    values = dict(values or {})

    # Portable across Windows/Linux/macOS.
    time_text = (
        now.strftime("%I:%M %p").lstrip("0")
        if hasattr(now, "strftime")
        else ""
    )

    sections = {
        "time": f"Good morning, sir. The time is {time_text}.",
        "weather": _weather_sentence(values.get("weather.current")),
        "email": _email_sentence(values.get("email.important")),
        "calendar": _calendar_sentence(values.get("calendar.upcoming")),
        "portfolio": _portfolio_sentence(values.get("finance.performance")),
        "market": _market_sentence(values.get("finance.market")),
    }

    spoken = " ".join(
        text.strip()
        for text in sections.values()
        if str(text or "").strip()
    )

    return MorningBriefing(
        generated_at=now.isoformat(),
        spoken_text=spoken,
        sections=sections,
        available={
            capability: values.get(capability) is not None
            for capability in CAPABILITIES
        },
        raw=values,
    )


def _good_morning_weather_arguments() -> dict[str, Any]:
    try:
        from assistant.core.world_state.location import get_foreground_location
        location = get_foreground_location()
        if location is not None:
            if isinstance(location, dict):
                latitude = location.get("latitude", location.get("lat"))
                longitude = location.get("longitude", location.get("lon", location.get("lng")))
            else:
                latitude = getattr(location, "latitude", getattr(location, "lat", None))
                longitude = getattr(location, "longitude", getattr(location, "lon", getattr(location, "lng", None)))
            if latitude is not None and longitude is not None:
                return {"latitude": latitude, "longitude": longitude}
    except Exception as exc:
        print(f"[Good Morning] Foreground location unavailable: {exc}")

    try:
        from assistant.cognition.intelligence.preferences import get_default_weather_location
        saved_location = get_default_weather_location()
        if saved_location:
            return {"location": saved_location}
    except Exception as exc:
        print(f"[Good Morning] Saved weather location unavailable: {exc}")
    return {}


def _execute_briefing_read(capability: str, arguments: dict[str, Any], **routing):
    result = execute_aggregate(
        capability=capability,
        arguments=arguments,
        approved=False,
        **routing,
    )
    return aggregate_result_to_dict(result)


def _successful_data(result: Any):
    if not isinstance(result, dict) or not result.get("success"):
        return None
    for evidence in result.get("evidence") or []:
        if evidence.get("success"):
            return evidence.get("data")
    return None


def _normalize_email_data(data: Any):
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        candidate = data.get("items", data.get("messages", data.get("results", [])))
        items = candidate if isinstance(candidate, list) else []
    else:
        items = []
    important = []
    unread_important = []
    for message in items:
        if not isinstance(message, dict):
            continue
        labels = set(((message.get("metadata") or {}).get("label_ids") or []))
        if "IMPORTANT" in labels:
            important.append(message)
            if "UNREAD" in labels:
                unread_important.append(message)
    selected = unread_important or important
    return {"count": len(selected), "messages": selected}


def _normalize_market_data(data: Any, result: Any = None):
    if data is None:
        error = ""
        if isinstance(result, dict):
            for evidence in result.get("evidence") or []:
                if evidence.get("error"):
                    error = str(evidence.get("error"))
                    break
        return {"unavailable": True, "error": error}
    return data


def collect_good_morning_briefing(
    *,
    prefetch_fn: Callable[[str], Any] | None = None,
    now: datetime | None = None,
) -> MorningBriefing:
    # Preserve the original Step-1 injection hook used by its validator.
    if prefetch_fn is not None:
        prefetch_fn(PREFETCH_PROMPT)
        from assistant.core.world_state.integration_adapter import get_integration_world_state
        values = {}
        for capability in CAPABILITIES:
            record = get_integration_world_state(capability, require_fresh=True)
            values[capability] = None if record is None else record.value
        return compose_good_morning_briefing(now=now, values=values)

    jobs = [
        ParallelJob(name="weather.current", function=_execute_briefing_read, args=("weather.current", _good_morning_weather_arguments())),
        ParallelJob(name="calendar.read", function=_execute_briefing_read, args=("calendar.read", {}), kwargs={"provider": "google"}),
        ParallelJob(name="email.search", function=_execute_briefing_read, args=("email.search", {"query": "is:important is:unread newer_than:2d"}), kwargs={"provider": "google"}),
        ParallelJob(
            name="finance.performance",
            function=_execute_briefing_read,
            args=("finance.performance", {}),
            kwargs={"provider": "schwab", "account_id": "primary", "routing_mode": "explicit_account"},
        ),
        ParallelJob(
            name="market.quotes",
            function=_execute_briefing_read,
            args=("market.quotes", {"symbols": ["SPY", "QQQ", "DIA"]}),
            kwargs={"provider": "schwab", "account_id": "primary", "routing_mode": "explicit_account"},
        ),
    ]
    batch = execute_parallel(jobs, max_workers=5)
    results = {
        item.name: item.value
        for item in batch
        if getattr(item, "success", False)
    }

    weather = _successful_data(results.get("weather.current"))
    calendar = _successful_data(results.get("calendar.read"))
    email = _successful_data(results.get("email.search"))
    portfolio = _successful_data(results.get("finance.performance"))
    market = _successful_data(results.get("market.quotes"))

    values = {
        "weather.current": weather,
        "calendar.upcoming": calendar if calendar is not None else [],
        "email.important": _normalize_email_data(email),
        "finance.performance": portfolio if portfolio is not None else {"unavailable": True},
        "finance.market": _normalize_market_data(market, results.get("market.quotes")),
    }
    return compose_good_morning_briefing(now=now, values=values)


def run_good_morning_protocol(
    *,
    prefetch_fn: Callable[[str], Any] | None = None,
    now: datetime | None = None,
    surface: bool = True,
) -> MorningBriefing:
    briefing = collect_good_morning_briefing(
        prefetch_fn=prefetch_fn,
        now=now,
    )

    if surface:
        try:
            from assistant.core.proactive import PROACTIVE_ENGINE
            from assistant.core.proactive.models import ProactiveCandidate

            PROACTIVE_ENGINE.consider(
                ProactiveCandidate(
                    topic="briefing.good_morning",
                    message=briefing.spoken_text,
                    urgency=6,
                    dedupe_key=(
                        "briefing.good_morning:"
                        + (now or datetime.now()).strftime("%Y-%m-%d")
                    ),
                    source="assistant.protocols.good_morning",
                    metadata={
                        "generated_at": briefing.generated_at,
                        "available": dict(briefing.available),
                    },
                )
            )
        except Exception as error:
            # Briefing generation remains useful even if proactive surfacing
            # is unavailable. It must not fabricate success.
            print(
                "[Good Morning Protocol Warning] "
                f"proactive surface failed: {error}"
            )

    return briefing
