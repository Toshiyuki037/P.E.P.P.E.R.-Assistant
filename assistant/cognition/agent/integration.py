"""
P.E.P.P.E.R. - Agent Runtime Integration

Created: August 9, 2026
Last Edited: August 12, 2026
Author: Max Maehara

Purpose:
    Connects Phase 7 task execution to P.E.P.P.E.R.'s normal prompt loop.

Phase 14A:
    Adds a cheap deterministic fast gate so obviously non-agentic
    requests do not pay for the expensive Phase 7 planner.

Phase 14 Routing Hardening:
    - unfinished Phase 7 tasks only own a new turn when the user clearly
      approves, rejects, cancels, resumes, or retries that task
    - unrelated new requests cancel stale unfinished task state and fall
      through to normal routing
    - natural compound desktop requests such as:
          "open YouTube in Chrome and fullscreen it"
          "open VS Code and maximize it"
          "pull up YouTube full screen"
      are recognized as Phase 7 candidates

This preserves Phase 6 as the single-action layer and Phase 7 as the
multi-step/adaptive coordinator.
"""

from __future__ import annotations

import re

from assistant.capabilities.tools.session import (
    parse_approval_response,
)

from .controller import (
    agent_task_active,
    approve_agent_action,
    cancel_agent,
    execute_agent_request,
    get_agent_task,
    reject_agent_action,
    resume_agent,
)

from .state import (
    load_last_completed_task,
)


# ---------------------------------------------------------------------------
# Command Normalization
# ---------------------------------------------------------------------------

def _normalized_command(
    text: str,
) -> str:

    return (
        " ".join(
            str(
                text
                or ""
            )
            .strip()
            .lower()
            .split()
        )
        .rstrip(
            ".!?"
        )
    )


# ---------------------------------------------------------------------------
# Explicit Task-Control Commands
# ---------------------------------------------------------------------------

def is_cancel_request(
    text: str,
):

    normalized = (
        _normalized_command(
            text
        )
    )

    return normalized in {
        "cancel task",
        "cancel the task",
        "cancel that",
        "stop task",
        "stop the task",
        "stop working on that",
        "abort task",
        "abort the task",
        "never mind",
        "nevermind",
        "forget it",
    }


def is_resume_request(
    text: str,
):

    normalized = (
        _normalized_command(
            text
        )
    )

    return normalized in {
        "resume task",
        "resume the task",
        "resume that",
        "continue task",
        "continue the task",
        "continue that",
        "continue",
        "keep going",
        "keep working",
        "keep working on that",
        "try again",
        "retry",
        "retry that",
        "retry the task",
        "run it again",
        "go ahead",
        "proceed",
    }


# ---------------------------------------------------------------------------
# Existing Task Helpers
# ---------------------------------------------------------------------------

_ACTIVE_UNFINISHED_STATUSES = {
    "running",
    "planned",
    "incomplete",
    "awaiting_approval",
}


def _unfinished_agent_task():

    task = (
        get_agent_task()
    )

    if (
        task is not None
        and getattr(
            task,
            "status",
            None,
        )
        in _ACTIVE_UNFINISHED_STATUSES
    ):

        return task

    return None


def _cancel_stale_task_silently():
    """
    The user moved on to a new request.

    Cancel the old unfinished task without surfacing the cancellation text.
    The CURRENT request should continue normally through P.E.P.P.E.R.'s router.
    """

    try:

        if agent_task_active():

            cancel_agent()


    except Exception as error:

        print(
            (
                "[Agent stale-task cleanup warning] "
                f"{error}"
            )
        )


# ---------------------------------------------------------------------------
# Phase 14A - Cheap Agent Gate
# ---------------------------------------------------------------------------

_AGENTIC_PHRASES = (
    # Sequential / dependency language
    " and then ",
    " then ",
    " after that ",
    " once that ",
    " when that ",

    # Adaptive / recovery language
    " if it fails",
    " if that fails",
    " if this fails",
    " if necessary",
    " keep trying",
    " keep working",
    " until it works",
    " until it succeeds",
    " until successful",
    " debug it",
    " fix it",
    " repair it",
    " investigate",
    " diagnose",

    # Verification / development language
    " verify that",
    " verify it",
    " run the tests",
    " run tests",
    " full regression",
    " regression suite",
    " inspect the changes",
    " inspect current",
    " commit everything",
    " stage all",

    # Common natural desktop compound phrasing
    " and open ",
    " and launch ",
    " and pull up ",
    " and maximize ",
    " and minimise ",
    " and minimize ",
    " and full screen ",
    " and fullscreen ",
    " then open ",
    " then launch ",
    " then maximize ",
    " then full screen ",
    " then fullscreen ",
)


_MULTI_ACTION_VERBS = (
    "open",
    "launch",
    "focus",
    "move",
    "maximize",
    "maximise",
    "minimize",
    "minimise",
    "fullscreen",
    "press",
    "close",
    "type",
    "write",
    "copy",
    "save",
    "create",
    "delete",
    "rename",
    "run",
    "test",
    "search",
    "find",
    "inspect",
    "read",
    "commit",
    "stage",
    "push",
    "navigate",
    "click",
    "fill",
)


def _contains_open_like_action(
    normalized: str,
) -> bool:

    return bool(
        re.search(
            r"\b("
            r"open|open up|launch|pull up|start"
            r")\b",
            normalized,
        )
    )


def _contains_display_followup_action(
    normalized: str,
) -> bool:

    return bool(
        re.search(
            r"\b("
            r"full\s*screen|fullscreen|"
            r"maximize|maximise|"
            r"minimize|minimise|"
            r"move|focus"
            r")\b",
            normalized,
        )
    )


def should_consider_agent(
    user_message: str,
) -> bool:
    """
    Cheap pre-planner gate.

    True means:
        the request has enough evidence of multiple dependent actions,
        adaptive behavior, or compound computer control to justify Phase 7.

    False means:
        continue to Phase 6 / integrations / memory / normal reasoning.

    This is NOT the final agent decision. The Phase 7 planner remains
    authoritative once this fast gate allows the request through.
    """

    text = (
        str(
            user_message
            or ""
        )
        .strip()
    )

    if not text:

        return False


    normalized = (
        " "
        + re.sub(
            r"\s+",
            " ",
            text.lower(),
        )
        + " "
    )


    # -----------------------------------------------------------------------
    # Phase 17B.10.19 - hands-on workspace engineering must reach Phase 7.
    # -----------------------------------------------------------------------

    workspace_action = re.search(
        r"\b(figure\s+out|find|inspect|investigate|debug|diagnose|fix|repair|edit|change|modify|update)\b",
        normalized,
        flags=re.IGNORECASE,
    )
    workspace_object = re.search(
        r"\b(code|source|file|controller|script|project|workspace|function|class|module|bug|issue|error|test)\b",
        normalized,
        flags=re.IGNORECASE,
    )
    if workspace_action and workspace_object:
        return True

    # -----------------------------------------------------------------------
    # Strong Explicit Agentic Signals
    # -----------------------------------------------------------------------

    if any(
        phrase in normalized
        for phrase in _AGENTIC_PHRASES
    ):

        return True


    # -----------------------------------------------------------------------
    # Natural Application + Window/Display Compound Commands
    # -----------------------------------------------------------------------
    #
    # Examples:
    #     "Open YouTube in Chrome full screen."
    #     "Pull up YouTube fullscreen please."
    #     "Open VS Code and maximize it."
    #     "Launch Chrome then move it to monitor 2."
    #
    # These often contain no literal "and then", but they still require
    # more than one real computer action.
    # -----------------------------------------------------------------------

    if (
        _contains_open_like_action(
            normalized
        )
        and _contains_display_followup_action(
            normalized
        )
    ):

        return True


    # -----------------------------------------------------------------------
    # Multiple Explicit Action Verbs
    # -----------------------------------------------------------------------

    action_hits = 0

    for verb in _MULTI_ACTION_VERBS:

        if re.search(
            rf"\b{re.escape(verb)}\b",
            normalized,
        ):

            action_hits += 1


    if (
        action_hits >= 2
        and (
            " and " in normalized
            or " then " in normalized
            or "," in normalized
            or ";" in normalized
        )
    ):

        return True


    # -----------------------------------------------------------------------
    # Common Explicit Two-Step Forms
    # -----------------------------------------------------------------------

    if re.search(
        r"\b("
        r"open|launch|run|create|write|search|find|inspect|pull up"
        r")\b"
        r".+"
        r"\b(and|then)\b"
        r".+"
        r"\b("
        r"open|launch|run|create|write|search|find|inspect|verify|"
        r"maximize|maximise|minimize|minimise|fullscreen|move|focus"
        r")\b",
        normalized,
    ):

        return True


    # -----------------------------------------------------------------------
    # Otherwise Phase 6 / integrations / memory / reasoning should handle it.
    # -----------------------------------------------------------------------

    return False



# ---------------------------------------------------------------------------
# Phase 17B.6 - Completed Diagnostic Follow-Up
# ---------------------------------------------------------------------------

_SHORT_ACTION_FOLLOWUPS = {
    "fix it", "fix that", "repair it", "repair that",
    "do it", "make the fix", "apply the fix",
    "can you fix it", "can you fix it for me",
    "could you fix it", "could you fix it for me",
    "please fix it", "fix it for me",
}

def _completed_task_followup(user_message: str):
    normalized=_normalized_command(user_message)
    if normalized not in _SHORT_ACTION_FOLLOWUPS:
        return None
    previous=load_last_completed_task()
    if previous is None:
        return None
    summary=str(getattr(previous,"final_summary","") or "").strip()
    workspace=str(getattr(previous,"workspace_path","") or "").strip()
    if not summary or not workspace:
        return None
    evidence=[]
    for step in getattr(previous,"steps",[]) or []:
        result=getattr(step,"result",None)
        if result:
            evidence.append(
                f"Step {getattr(step,'step_number','?')} "
                f"({getattr(step,'tool_name','')}): {str(result)[:1800]}"
            )
    return (
        "Continue the immediately previous completed Phase 7 diagnosis. "
        "The user explicitly asked to apply the identified fix. "
        "Do not restart discovery or rerun generic pytest merely to rediscover "
        "facts already established below. Read the target file if needed, "
        "perform the real edit through the registered filesystem mutation tool "
        "and its normal approval gate, then run the previously relevant verification. "
        f"\n\nAuthoritative workspace: {workspace}"
        f"\nPrevious diagnosis: {summary}"
        f"\nPrior execution evidence:\n" + "\n".join(evidence[-4:])
    )


# ---------------------------------------------------------------------------
# Handle Agent Message
# ---------------------------------------------------------------------------


def _normalize_pending_agent_approval(user_message: str) -> str:
    """Map natural affirmative approval to the existing explicit approval path."""
    text = " ".join(str(user_message or "").lower().split())
    text = re.sub(r"[^a-z0-9\s']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if re.search(r"\b(no|nope|cancel|stop|reject)\b", text):
        return user_message
    if "do not" in text or "don't" in text or "never mind" in text or "nevermind" in text:
        return user_message

    if re.search(r"\b(yes|yeah|yep|sure|okay|ok|approve|approved|proceed)\b", text):
        return "yes"

    if re.search(r"\b(go ahead|do it|fix it|fix that|repair it|repair that|apply it|apply the fix|make the fix)\b", text):
        return "yes"

    return user_message


def handle_agent_message(
    user_message: str,
):
    """
    Returns:

        {
            "handled": bool,
            "response": str | None,
            "follow_up": str,
        }

    Important routing behavior:

        awaiting approval + "approved"
            -> continue old task

        unfinished task + "continue that"
            -> continue old task

        unfinished task + unrelated NEW request
            -> silently cancel stale task
            -> route new request normally

    This prevents stale Phase 7 tasks from hijacking later weather,
    Schwab, Spotify, memory, computer, or reasoning requests.
    """

    task = (
        _unfinished_agent_task()
    )


    # -----------------------------------------------------------------------
    # Existing Task Awaiting Approval
    # -----------------------------------------------------------------------

    if (
        task is not None
        and task.status
        == "awaiting_approval"
    ):

        approval = (
            parse_approval_response(
                _normalize_pending_agent_approval(user_message)
            )
        )


        if approval.decision == "approve":

            result = (
                approve_agent_action()
            )

            return {
                "handled":
                    True,

                "response":
                    result[
                        "response"
                    ],

                "follow_up":
                    approval.remainder,
            }


        if approval.decision == "reject":

            result = (
                reject_agent_action()
            )

            return {
                "handled":
                    True,

                "response":
                    result[
                        "response"
                    ],

                "follow_up":
                    approval.remainder,
            }


        # A completely unrelated request while approval is pending means
        # the user has moved on. Do not let the pending task hijack it.
        if not (
            is_cancel_request(
                user_message
            )
            or is_resume_request(
                user_message
            )
        ):

            _cancel_stale_task_silently()

            task = None


    # -----------------------------------------------------------------------
    # Explicit Cancel
    # -----------------------------------------------------------------------

    if (
        task is not None
        and is_cancel_request(
            user_message
        )
    ):

        result = (
            cancel_agent()
        )

        return {
            "handled":
                True,

            "response":
                result[
                    "response"
                ],

            "follow_up":
                "",
        }


    # -----------------------------------------------------------------------
    # Explicit Resume / Retry
    # -----------------------------------------------------------------------

    if (
        task is not None
        and is_resume_request(
            user_message
        )
    ):

        result = (
            resume_agent()
        )

        return {
            "handled":
                True,

            "response":
                result[
                    "response"
                ],

            "follow_up":
                "",
        }


    # -----------------------------------------------------------------------
    # Existing Non-Approval Task + New Request
    # -----------------------------------------------------------------------
    #
    # Previous broken behavior automatically resumed running/planned/
    # incomplete tasks for every new utterance.
    #
    # New behavior:
    #     only explicit task-continuation language resumes the old task.
    #     every other request is treated as a new user objective.
    # -----------------------------------------------------------------------

    if (
        task is not None
        and task.status
        in {
            "running",
            "planned",
            "incomplete",
        }
    ):

        _cancel_stale_task_silently()

        task = None


    # -----------------------------------------------------------------------
    # Phase 17B.6 - short action inherits completed diagnosis.
    # -----------------------------------------------------------------------

    continuity_context = _completed_task_followup(
        user_message
    )

    if continuity_context:
        result = execute_agent_request(
            continuity_context
        )
        if result["handled"]:
            return {
                "handled": True,
                "response": result["response"],
                "follow_up": "",
            }

    # -----------------------------------------------------------------------
    # Phase 14A Fast Gate
    # -----------------------------------------------------------------------

    if not should_consider_agent(
        user_message
    ):

        return {
            "handled":
                False,

            "response":
                None,

            "follow_up":
                "",
        }


    # -----------------------------------------------------------------------
    # New Phase 7 Request
    # -----------------------------------------------------------------------

    result = (
        execute_agent_request(
            user_message
        )
    )


    if not result[
        "handled"
    ]:

        return {
            "handled":
                False,

            "response":
                None,

            "follow_up":
                "",
        }


    return {
        "handled":
            True,

        "response":
            result[
                "response"
            ],

        "follow_up":
            "",
    }
