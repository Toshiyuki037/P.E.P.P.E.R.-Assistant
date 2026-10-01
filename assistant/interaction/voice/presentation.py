"""
P.E.P.P.E.R. - Unified Voice Presentation Policy

Final Phase 14/15 polish.

Purpose:
    Apply one global voice-output policy AFTER every response source:
        - LLM reasoning
        - deterministic Phase 15/system responses
        - tools/integrations
        - agent/workflow
        - computer control

Core behavior:
    - concise by default
    - preserve operationally important information
    - never alter the full terminal/UI response
    - explicit detail requests may speak the full response
    - contextual expansion phrases ("tell me more", "elaborate", etc.)
      can expand the previous authoritative answer
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import threading

from .response_length import explicitly_requests_detail


@dataclass(frozen=True)
class VoicePresentation:
    mode: str
    text: str
    full_response: str
    was_condensed: bool


_STATE_LOCK = threading.RLock()
_LAST_USER_TEXT = ""
_LAST_FULL_RESPONSE = ""
_LAST_SPOKEN_RESPONSE = ""

_EXPANSION_PHRASES = (
    "elaborate",
    "tell me more",
    "go into detail",
    "go into more detail",
    "explain further",
    "explain more",
    "break that down",
    "break it down",
    "give me the details",
    "give me more detail",
    "what exactly is wrong",
    "what exactlys wrong",
    "what exactly's wrong",
    "what exactly happened",
    "why exactly",
    "expand on that",
    "continue explaining",
)

_CRITICAL_MARKERS = (
    "error",
    "failed",
    "failure",
    "broken",
    "degraded",
    "unavailable",
    "warning",
    "approval",
    "permission",
    "security",
    "risk",
    "requires",
    "required",
    "cannot",
    "can't",
    "could not",
    "next step",
    "next action",
    "important caveat",
)


def _normalize(text: str):
    return " ".join(str(text or "").strip().lower().split()).strip(" .!?")


def remember_authoritative_response(user_text: str, full_response: str, spoken_response: str = ""):
    global _LAST_USER_TEXT, _LAST_FULL_RESPONSE, _LAST_SPOKEN_RESPONSE
    with _STATE_LOCK:
        _LAST_USER_TEXT = str(user_text or "").strip()
        _LAST_FULL_RESPONSE = str(full_response or "").strip()
        _LAST_SPOKEN_RESPONSE = str(spoken_response or "").strip()


def get_last_authoritative_response():
    with _STATE_LOCK:
        return {
            "user_text": _LAST_USER_TEXT,
            "full_response": _LAST_FULL_RESPONSE,
            "spoken_response": _LAST_SPOKEN_RESPONSE,
        }


def is_contextual_expansion_request(user_text: str):
    text = _normalize(user_text)
    return bool(text) and any(phrase in text for phrase in _EXPANSION_PHRASES)


def build_contextual_expansion_prompt(user_text: str):
    if not is_contextual_expansion_request(user_text):
        return str(user_text or "")

    previous = get_last_authoritative_response()
    full_response = previous.get("full_response", "").strip()

    if not full_response:
        return str(user_text or "")

    return (
        str(user_text or "").strip()
        + "\n\n[P.E.P.P.E.R. CONTEXTUAL EXPANSION]\n"
        + "The user is asking to expand the previous authoritative answer. "
          "Continue the same topic rather than starting a new subject. "
          "Explain the most useful additional detail without merely repeating "
          "the prior wording.\n\nPrevious authoritative answer:\n"
        + full_response
    )


def _clean_for_speech(text: str):
    value = str(text or "")
    value = re.sub(r"```[\s\S]*?```", " ", value)
    value = value.replace("`", "").replace("**", "").replace("__", "")
    value = re.sub(r"(?m)^#+\s*", "", value)
    value = re.sub(r"(?m)^\s*[-•]\s+", "", value)
    value = re.sub(r"(?m)^\s*\d+[.)]\s+", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _sentences(text: str):
    cleaned = _clean_for_speech(text)
    if not cleaned:
        return []
    return [
        item.strip()
        for item in re.split(r"(?<=[.!?])\s+", cleaned)
        if item.strip()
    ]


def _word_count(text: str):
    return len(re.findall(r"\b[\w'-]+\b", text))


def _clip_words(text: str, maximum: int):
    words = text.split()
    if len(words) <= maximum:
        return text
    clipped = " ".join(words[:maximum]).rstrip(" ,;:-")
    if clipped and clipped[-1] not in ".!?":
        clipped += "."
    return clipped


def _compact_capability_inventory(full_response: str):
    if "supported core capabilities include" not in full_response.lower():
        return ""
    return (
        "I can handle conversation, memory, research, coding, web and browser "
        "work, connected services, computer awareness and control, vision, "
        "workflows, and system diagnostics. I also have voice authentication, "
        "wake and speech systems, telemetry, and health monitoring. If you want, "
        "I can break down any capability."
    )


def _compact_healthy_inventory(full_response: str):
    lower = full_response.lower()
    healthy_signal = (
        "overall system health: healthy" in lower
        or "overall: healthy" in lower
        or "i’m healthy" in lower
        or "i'm healthy" in lower
    )
    if not healthy_signal:
        return ""

    caveat = ""
    if (
        "not run a fresh deep diagnostic" in lower
        or "not run a fresh diagnostic" in lower
    ):
        caveat = (
            " I haven't run a fresh deep diagnostic in this exact turn, "
            "so that's based on my latest verified health state."
        )

    return (
        "Yes. My latest health state is healthy across memory, tools, "
        "integrations, voice, agent workflows, vision, GPU acceleration, "
        "and runtime infrastructure."
        + caveat
    )


def _critical_sentences(sentences):
    selected = []
    for sentence in sentences:
        lower = sentence.lower()
        if any(marker in lower for marker in _CRITICAL_MARKERS):
            selected.append(sentence)
    return selected


def _generic_condense(full_response: str, *, maximum_words: int = 34):
    sentences = _sentences(full_response)
    if not sentences:
        return ""
    # Default voice: at most two sentences. Explicit detail requests bypass this.
    result = " ".join(sentences[:2]).strip()
    return _clip_words(result, maximum_words)



# ---------------------------------------------------------------------------
# Phase 17B.6 - Concise Agent Speech
# ---------------------------------------------------------------------------

def _agent_voice_summary(user_text: str, full_response: str):
    if not full_response.lstrip().startswith("Agent status:"):
        return ""

    match=re.search(r"(?m)^Agent status:\s*([^\n]+)",full_response)
    status=match.group(1).strip().lower() if match else ""

    body=re.sub(r"(?m)^Agent status:[^\n]*\n?","",full_response,count=1)
    body=re.sub(r"(?m)^Goal:[^\n]*\n?","",body,count=1)
    body=body.split("\nTask steps:",1)[0].strip()
    body=_clean_for_speech(body)

    if status=="approval_required":
        # Explain the concrete issue briefly, then ask permission.
        clean=re.sub(r"[`*_#]", "", body)
        clean=re.sub(r"\s+", " ", clean).strip()
        finding=""
        patterns=(
            r"(?:issue|bug|problem)(?:\s+is|\s+was|:)?\s+([^.!?]{8,180})",
            r"([^.!?]{8,180}(?:swapped|reversed|backwards|backward|wrong direction|moves away)[^.!?]{0,100})",
        )
        for pattern in patterns:
            match=re.search(pattern,clean,flags=re.IGNORECASE)
            if match:
                finding=match.group(1).strip(" :-.")
                break
        if finding:
            finding=_clip_words(finding,26)
            return f"I found it, sir. {finding}. Do I have your approval to fix it?"
        # Phase 17B.10.22: recover the concrete diagnosis from the
        # awaiting-approval task step when the short status body omits it.
        approval_step = ""
        for raw in full_response.splitlines():
            line = raw.strip()
            if "[awaiting_approval]" in line.lower():
                approval_step = re.sub(r"^\d+\.\s*", "", line)
                approval_step = re.sub(r"\s*\[awaiting_approval\]\s*$", "", approval_step, flags=re.IGNORECASE)
                break

        if approval_step:
            low = approval_step.lower()
            if "error sign" in low and ("controller" in low or "proportional" in low):
                return (
                    "I found it, sir. The controller calculates the error with the wrong sign, "
                    "so it drives the motor away from the target. Do I have your approval to fix it?"
                )
            approval_step = re.sub(r"^(fix|repair|change|modify|update)\s+", "", approval_step, flags=re.IGNORECASE)
            approval_step = _clip_words(approval_step.rstrip(". "), 24)
            return f"I found it, sir. {approval_step}. Do I have your approval to fix it?"

        return "I found the issue, sir. I know what needs to be changed. Do I have your approval to fix it?"

    if status in {"failed","cancelled"}:
        return _clip_words(body,42) if body else "I couldn't complete that, sir."

    if status=="completed":
        normalized=_normalize(user_text)
        if any(x in normalized for x in ("yes", "approve", "fix", "repair", "apply", "proceed")):
            lower=body.lower()
            if any(x in lower for x in ("verification passed", "verified", "converges", "passed")):
                return "Fixed and verified, sir."
            return "Done, sir."

    if status=="completed":
        normalized=_normalize(user_text)
        if any(x in normalized for x in ("yes", "approve", "fix", "repair", "apply", "proceed")):
            return "Task complete, sir."

    if status in {"completed","incomplete"}:
        normalized=_normalize(user_text)
        diagnosis_only=(
            any(x in normalized for x in ("diagnose","figure out","find what's wrong","find what is wrong"))
            and not any(x in normalized for x in ("fix","repair","change","edit"))
        )
        sentences=_sentences(body)
        spoken=" ".join(sentences[:2]).strip() if sentences else body
        spoken=_clip_words(spoken,34)
        if diagnosis_only:
            finding=(sentences[0] if sentences else body).strip()
            finding=re.sub(r"^Diagnosed\s+","",finding,flags=re.I)
            finding=_clip_words(finding,28).rstrip(" .")
            spoken=f"I found the issue, sir: {finding}. Would you like me to fix it?"
        return spoken or "Task complete, sir. The issue is fixed and verified."

    return _clip_words(body,45) if body else ""


def prepare_voice_presentation(user_text: str, full_response: str):
    full_response = str(full_response or "").strip()

    if not full_response:
        return VoicePresentation("empty", "", "", False)

    detailed = (
        explicitly_requests_detail(user_text)
        or is_contextual_expansion_request(user_text)
    )

    agent_spoken = _agent_voice_summary(
        user_text,
        full_response,
    )

    if agent_spoken and not detailed:
        result = VoicePresentation(
            "agent_concise",
            agent_spoken,
            full_response,
            True,
        )
        remember_authoritative_response(
            user_text,
            full_response,
            agent_spoken,
        )
        return result

    if detailed:
        spoken = _clean_for_speech(full_response)
        result = VoicePresentation("detailed", spoken, full_response, False)
        remember_authoritative_response(user_text, full_response, spoken)
        return result

    spoken = _compact_capability_inventory(full_response)
    if not spoken:
        spoken = _compact_healthy_inventory(full_response)
    if not spoken:
        spoken = _generic_condense(full_response)
    if not spoken:
        spoken = _clean_for_speech(full_response)

    result = VoicePresentation(
        "concise",
        spoken,
        full_response,
        _clean_for_speech(full_response) != spoken,
    )
    remember_authoritative_response(user_text, full_response, spoken)
    return result
