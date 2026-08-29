from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FastConversationResult:
    handled: bool
    response: str = ""
    reason: str = ""


def _normalize(text: str) -> str:
    value = str(text or "").strip().lower()

    # Remove a natural direct-address wake/greeting prefix if it survives
    # into request processing.
    #
    # Examples:
    #   Pepper, how are you?
    #   Hey Pepper, how are you?
    #   Hey, Pepper, how are you?
    #   Good morning, Pepper, how are you?
    value = re.sub(
        r"^(?:(?:hey|hi|hello|morning|good\s+morning|good\s+afternoon|good\s+evening)\s*[,;:\-]?\s*)?pepper\s*[,;:\-]?\s*",
        "",
        value,
        count=1,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"[^\w\s']",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    return value


_EXACT_RESPONSES = {
    # Thanks
    "thank you":
        "You're welcome, Max.",

    "thanks":
        "You're welcome, Max.",

    "thank you pepper":
        "You're welcome, Max.",

    "thanks pepper":
        "You're welcome, Max.",

    # Greetings
    "good morning":
        "Good morning, Max.",

    "good afternoon":
        "Good afternoon, Max.",

    "good evening":
        "Good evening, Max.",

    "hello":
        "Hey, Max.",

    "hi":
        "Hey, Max.",

    "hey":
        "Hey, Max.",

    # Presence / readiness
    "are you there":
        "I'm here.",

    "you there":
        "I'm here.",

    "are you ready":
        "Ready.",

    "ready":
        "Ready.",

    # Ordinary social conversation
    "how are you":
        "I'm doing well, Max. What can I help with?",

    "how are you doing":
        "I'm doing well, Max. What can I help with?",

    "how're you":
        "I'm doing well, Max. What can I help with?",

    "howre you":
        "I'm doing well, Max. What can I help with?",

    "how's it going":
        "Going well. What can I help with?",

    "hows it going":
        "Going well. What can I help with?",

    "how is it going":
        "Going well. What can I help with?",

    "how are things":
        "Everything's running normally. What can I help with?",

    "what's up":
        "Ready when you are.",

    "whats up":
        "Ready when you are.",

    "what is up":
        "Ready when you are.",
}


def handle_fast_conversation(
    user_text: str,
) -> FastConversationResult:

    normalized = _normalize(
        user_text
    )

    response = _EXACT_RESPONSES.get(
        normalized
    )

    if response is None:
        return FastConversationResult(
            handled=False,
        )

    return FastConversationResult(
        handled=True,
        response=response,
        reason="deterministic_social_turn",
    )
