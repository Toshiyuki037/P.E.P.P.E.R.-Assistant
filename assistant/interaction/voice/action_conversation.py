from __future__ import annotations
from dataclasses import dataclass
import re
import threading

_LOCK = threading.RLock()
_PENDING_OPEN_REQUEST = None
_YES = {"yes","yeah","yep","sure","please","do it","go ahead","yes please","yeah please"}
_NO = {"no","nope","cancel","never mind","nevermind"}
_OPEN = re.compile(r"\b(open|launch)\b", re.I)
_FOLDER = re.compile(r"\b(folder|directory|workspace)\b", re.I)
_EXPLICIT_APP = re.compile(r"\b(vs\s*code|vscode|visual studio code|file explorer|explorer)\b", re.I)

@dataclass(frozen=True)
class ClarificationResult:
    handled: bool = False
    rewritten_text: str | None = None
    response: str | None = None

def _norm(text):
    return " ".join(re.sub(r"[^\w\s']", " ", str(text or "").lower()).split())

def resolve_pending_action(text):
    global _PENDING_OPEN_REQUEST
    normalized = _norm(text)
    with _LOCK:
        pending = _PENDING_OPEN_REQUEST
        if pending is None:
            return ClarificationResult()
        if normalized in _NO:
            _PENDING_OPEN_REQUEST = None
            return ClarificationResult(handled=True, response="No problem, sir.")
        # Phase 17B.10.16 - tolerate natural/STT-expanded confirmations.
        # Live example: "Yes, open an MBS code." (Whisper rendering of VS Code).
        affirmative = (
            normalized in _YES
            or normalized.startswith(("yes ", "yeah ", "yep ", "sure ", "please "))
        )
        code_confirmation = bool(
            affirmative
            and "code" in normalized
            and any(word in normalized for word in ("open", "launch", "yes", "yeah", "yep"))
        )
        if affirmative or _EXPLICIT_APP.search(normalized) or code_confirmation:
            _PENDING_OPEN_REQUEST = None
            suffix = " using File Explorer" if "explorer" in normalized else " using VS Code"
            return ClarificationResult(
                rewritten_text=pending.rstrip(" .!?") + suffix + "."
            )
        # Do not destroy pending state merely because STT expanded a short confirmation.
        if len(normalized.split()) >= 5:
            _PENDING_OPEN_REQUEST = None
    return ClarificationResult()

def maybe_request_action_clarification(text):
    global _PENDING_OPEN_REQUEST
    value = str(text or "").strip()
    if _OPEN.search(value) and _FOLDER.search(value) and not _EXPLICIT_APP.search(value):
        with _LOCK:
            _PENDING_OPEN_REQUEST = value
        return ClarificationResult(
            handled=True,
            response="Would you like me to open it in VS Code, sir?",
        )
    return ClarificationResult()

def naturalize_spoken_action(user_text, response):
    request = _norm(user_text)
    result = str(response or "").strip()
    low = result.lower()
    if not result:
        return result
    if any(x in low for x in (
        "failed","failure","error","could not","couldn't","unable",
        "approval","permission","warning","not found",
    )):
        return result
    if ("open" in request or "launch" in request) and any(
        x in low for x in ("opened","is open","launched","opening")
    ):
        return "It's open, sir."
    if any(x in request for x in ("fix","edit","change","update")) and any(
        x in low for x in ("fixed","updated","changed","written","saved","passed")
    ):
        return "There you go, sir."
    return result
