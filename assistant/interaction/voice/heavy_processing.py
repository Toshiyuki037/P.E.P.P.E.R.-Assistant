from __future__ import annotations
import re

def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s./\\'-]", " ", str(text or "").lower()).split())

def contextual_heavy_acknowledgement(reason: str | None) -> str:
    # Short deterministic voice cue matched to the work underway.
    return {
        "vision": "One moment, sir, while I take a look at that.",
        "file_analysis": "One moment, sir, while I take a look.",
        "memory": "One moment, sir, while I check what I have on that.",
        "deep_reasoning": "Got it, sir. Let me think about that.",
    }.get(reason, "One moment, sir. I'm working on that.")


def heavy_processing_reason(text: str) -> str | None:
    t=_norm(text)
    # Phase 17B.5 - hands-on code diagnosis is file analysis
    _raw = str(text or "").lower()
    if (
        any(token in _raw for token in ("diagnose", "debug", "find the issue", "find what's wrong", "find what is wrong"))
        and any(token in _raw for token in (".py", "code", "file", "controller", "script", "folder", "workspace"))
    ):
        return "file_analysis"

    if not t: return None
    # Fresh visual perception / screenshot recognition.
    if any(x in t for x in ("my screen", "on screen", "screenshot", "look at this", "what am i looking at", "what's wrong on my screen", "what is wrong on my screen")):
        return "vision"
    # Explicit repository/file inspection, not generic coding questions.
    file_action=any(x in t for x in ("scan", "inspect", "search", "analyze", "analyse", "review", "read", "trace", "debug", "find"))
    file_object=any(x in t for x in ("file", "files", "folder", "directory", "repo", "repository", "codebase", "workspace", ".py", ".js", ".ts", ".cpp"))
    if file_action and file_object:
        return "file_analysis"
    # Memory operations known to invoke retrieval/mutation models.
    if any(x in t for x in ("what do you remember", "do you remember", "what did we discuss", "what did i tell you", "remember that", "forget that", "update my memory", "save this to memory")):
        return "memory"
    # Explicit deep/research work.
    if any(x in t for x in ("deep research", "research this", "investigate this", "analyze this project", "analyse this project")):
        return "deep_reasoning"
    return None
