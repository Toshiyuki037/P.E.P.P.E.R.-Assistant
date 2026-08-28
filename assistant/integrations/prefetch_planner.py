"""
P.E.P.P.E.R. - Integration Prefetch Planner

Phase 16C.4

Purpose:
    Deterministically decide which independent integration reads are relevant
    to a user request before any provider work is launched.

Design:
    - no provider calls
    - no world-state writes
    - no LLM call
    - no approval/write capabilities
    - deduplicated capability list
    - conservative phrase matching
"""

from __future__ import annotations

from dataclasses import (
    asdict,
    dataclass,
)


@dataclass(frozen=True)
class PrefetchIntent:
    capability: str
    reason: str

    def to_dict(self):
        return asdict(self)


_WEATHER_PHRASES = (
    "weather",
    "temperature",
    "outside",
    "rain",
    "raining",
    "forecast",
    "umbrella",
)

_CALENDAR_PHRASES = (
    "calendar",
    "schedule",
    "meeting",
    "meetings",
    "appointment",
    "appointments",
    "what do i have today",
    "what's on my day",
    "whats on my day",
    "anything today",
    "busy today",
)

_EMAIL_PHRASES = (
    "email",
    "emails",
    "inbox",
    "message in my inbox",
    "messages in my inbox",
    "important email",
    "important emails",
    "unread email",
    "unread emails",
)

_MARKET_PHRASES = (
    "market",
    "markets",
    "stock market",
    "stocks",
    "portfolio market",
    "market report",
    "market update",
)


def _normalize_text(
    text: str,
):
    return " ".join(
        str(
            text or ""
        )
        .strip()
        .lower()
        .split()
    )


def _contains_any(
    text: str,
    phrases: tuple[str, ...],
):
    return any(
        phrase in text
        for phrase in phrases
    )


def plan_integration_prefetch(
    user_message: str,
):
    """
    Return a conservative list of integration reads relevant to the request.

    This function intentionally does not infer broad unrelated bundles. For
    example, asking about weather does not automatically fetch email or market
    data.
    """

    text = _normalize_text(
        user_message
    )

    intents = []

    if _contains_any(
        text,
        _WEATHER_PHRASES,
    ):
        intents.append(
            PrefetchIntent(
                capability="weather.current",
                reason="Request references current weather or outdoor conditions.",
            )
        )

    if _contains_any(
        text,
        _CALENDAR_PHRASES,
    ):
        intents.append(
            PrefetchIntent(
                capability="calendar.upcoming",
                reason="Request references schedule, meetings, or today's agenda.",
            )
        )

    if _contains_any(
        text,
        _EMAIL_PHRASES,
    ):
        intents.append(
            PrefetchIntent(
                capability="email.important",
                reason="Request references inbox, email, or important messages.",
            )
        )

    if _contains_any(
        text,
        _MARKET_PHRASES,
    ):
        intents.append(
            PrefetchIntent(
                capability="finance.market",
                reason="Request references markets, stocks, or a market update.",
            )
        )

    # Preserve deterministic order while removing duplicates.
    deduplicated = []
    seen = set()

    for intent in intents:
        if intent.capability in seen:
            continue

        seen.add(
            intent.capability
        )
        deduplicated.append(
            intent
        )

    return deduplicated


def planned_capabilities(
    user_message: str,
):
    return [
        intent.capability
        for intent in plan_integration_prefetch(
            user_message
        )
    ]


if __name__ == "__main__":
    diagnostics = (
        (
            "What's Ohm's Law?",
            [],
        ),
        (
            "What's the weather outside?",
            [
                "weather.current",
            ],
        ),
        (
            "What's the weather and what meetings do I have today?",
            [
                "weather.current",
                "calendar.upcoming",
            ],
        ),
        (
            "Do I have important emails and how are the markets doing?",
            [
                "email.important",
                "finance.market",
            ],
        ),
        (
            "Give me the weather, my calendar, important emails, and a market update.",
            [
                "weather.current",
                "calendar.upcoming",
                "email.important",
                "finance.market",
            ],
        ),
    )

    print(
        "P.E.P.P.E.R. Phase 16C.4 Prefetch Planner"
    )
    print(
        "----------------------------------------"
    )

    failed = False

    for message, expected in diagnostics:
        actual = planned_capabilities(
            message
        )

        passed = (
            actual == expected
        )

        print(
            (
                f"{'PASS' if passed else 'FAIL'}: "
                f"{message}"
            )
        )
        print(
            f"  planned={actual}"
        )

        if not passed:
            print(
                f"  expected={expected}"
            )
            failed = True

    if failed:
        raise SystemExit(
            "Phase 16C.4 diagnostic failed."
        )

    print()
    print(
        "PHASE 16C.4 PLANNER DIAGNOSTIC PASSED"
    )
