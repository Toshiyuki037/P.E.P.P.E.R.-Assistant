from __future__ import annotations

import re


SLEEP_COMMANDS = {
    "go to sleep",
    "sleep",
    "stand by",
    "standby",
    "go to standby",

    "that's all",
    "thats all",

    "that's all pepper",
    "thats all pepper",

    "that's all piper",
    "thats all piper",

    "you can go to sleep",
    "you can sleep now",

    "go back to sleep",
}


_WAKE_PATTERN = re.compile(
    r"""
    ^
    (?:
        (?:
            hey|
            hi|
            hello|
            morning|
            good\s+morning|
            good\s+afternoon|
            good\s+evening
        )
        \s*[,;:\-]?\s*
    )?
    (?:pepper|piper)
    (?:
        \s*[,;:\-]?\s*
        (?P<request>.*)
    )?
    $
    """,
    re.IGNORECASE | re.VERBOSE,
)


def normalize_voice_text(
    text: str,
) -> str:
    return (
        " ".join(
            str(text or "")
            .strip()
            .lower()
            .split()
        )
        .rstrip(".!?")
    )


def is_sleep_command(
    text: str,
) -> bool:
    return (
        normalize_voice_text(text)
        in SLEEP_COMMANDS
    )


def extract_wake_request(
    text: str,
) -> tuple[bool, str]:
    normalized = normalize_voice_text(
        text
    )

    if not normalized:
        return False, ""

    match = _WAKE_PATTERN.fullmatch(
        normalized
    )

    if match is None:
        return False, ""

    request = (
        match.group("request")
        or ""
    )

    request = (
        request
        .strip(" \t,;:-")
        .strip()
    )

    return True, request
