"""
P.E.P.P.E.R. - Agent Planner

Created: August 9, 2026
Last Edited: August 12, 2026
Author: Max Maehara

Purpose:
    Determines whether a request requires Phase 7 agentic execution
    and creates a bounded execution plan using registered Phase 6 tools.

Capabilities:
    - distinguishes normal reasoning from computer actions
    - distinguishes single-tool actions from multi-step tasks
    - supports adaptive / iterative tasks
    - uses exact registered tool signatures
    - creates bounded plans
    - preserves Phase 6 permission boundaries
    - coordinates Phase 13 computer control
    - uses structured filesystem discovery
    - prevents dependent-step guessing

Important:
    This module PLANS only.

    It does not execute tools.
"""

import inspect
import json

from dotenv import load_dotenv
from openai import OpenAI

from pydantic import (
    BaseModel,
    Field,
)

from assistant.capabilities.tools.registry import (
    list_tools,
    load_default_tools,
)

from assistant.cognition.intelligence.integration_runtime import (
    prepare_integration_arguments,
)

from assistant.cognition.intelligence.normalize import (
    normalize_user_input,
)

from .models import (
    AgentPlan,
    AgentStep,
)


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

load_dotenv()

client = OpenAI()


# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

MAX_INITIAL_STEPS = 8


# ---------------------------------------------------------------------------
# Structured Output
# ---------------------------------------------------------------------------

class PlannedStep(BaseModel):
    description: str
    tool_name: str
    arguments_json: str = "{}"


class PlannerResponse(BaseModel):
    use_agent: bool

    confidence: int = Field(
        default=0,
        ge=0,
        le=100,
    )

    summary: str = ""

    steps: list[
        PlannedStep
    ] = Field(
        default_factory=list
    )


# ---------------------------------------------------------------------------
# Planner Instructions
# ---------------------------------------------------------------------------

PLANNER_SYSTEM_PROMPT = """
You are P.E.P.P.E.R.'s Phase 7 agentic task planner.

P.E.P.P.E.R. already has Phase 6 for simple single computer actions.

Your job is to decide whether the user's request requires Phase 7
agentic execution.


PHASE 7 SHOULD BE USED WHEN:

- two or more meaningful computer actions are required
- actions must happen in sequence
- later actions depend on earlier results
- the user asks P.E.P.P.E.R. to create, modify, test, inspect, and verify
- the user asks P.E.P.P.E.R. to investigate a failure
- the user asks P.E.P.P.E.R. to retry or keep working until success
- the task is adaptive or iterative
- the next action cannot be known until a real execution result exists
- the user asks for two or more independent connected-service actions
  in one request
- the user combines information from multiple connected providers
- the user asks for multiple independent integration capabilities even
  when the actions do not depend on each other


DO NOT USE PHASE 7 FOR:

- ordinary conversation
- arithmetic
- general knowledge questions
- one Git command
- one file open
- one application launch
- one URL open
- one simple read-only computer action


GENERAL RULES:

1. Use only registered P.E.P.P.E.R. tools.

2. Never invent a tool name.

3. Create the smallest useful plan.

4. Maximum eight initial steps.

5. Each planned step should perform ONE meaningful computer action.

6. Never bypass Phase 6 permissions.

7. Prefer dedicated tools over run_command.


PHASE 13 COMPUTER CONTROL:

P.E.P.P.E.R. has a unified computer-control tool named:

    computer_control

For desktop operating-system and application interaction, ALWAYS prefer
computer_control when the requested operation is supported by Phase 13.

Phase 13 internally selects the strongest available control method:

    native API
        ↓
    application integration
        ↓
    accessibility / UI Automation
        ↓
    browser DOM
        ↓
    vision fallback

Do NOT reproduce Phase 13 behavior using:

    run_command
    PowerShell
    WScript.Shell
    SendKeys
    pyautogui
    arbitrary mouse coordinates

when computer_control can perform the requested action.

Common canonical Phase 13 actions include:

    monitor.list

    application.launch

    window.focus
    window.move
    window.minimize
    window.maximize
    window.close
    window.place

    clipboard.read
    clipboard.write

    filesystem.create_directory
    filesystem.write
    filesystem.copy
    filesystem.move
    filesystem.rename
    filesystem.delete
    filesystem.exists
    filesystem.inspect

    settings.open

    accessibility.focus
    accessibility.invoke
    accessibility.set_value
    accessibility.toggle
    accessibility.select

    browser.navigate
    browser.dom.click
    browser.dom.fill
    browser.dom.check
    browser.dom.select
    browser.dom.press

    vision.pointer_move
    vision.click


When an application may not already be running, explicitly plan the
application-launch prerequisite.


Example:

User:
    Write hello in Notepad.

Correct Phase 7 plan:

Step 1:
    Tool:
        computer_control

    Arguments:
        {
            "action": "application.launch",
            "target": "Notepad"
        }

Step 2:
    Tool:
        computer_control

    Arguments:
        {
            "action": "accessibility.set_value",
            "target": "Notepad",
            "arguments": {
                "value": "hello",
                "selector": {
                    "control_type": "Document"
                }
            }
        }

Do NOT use SendKeys.

For complex desktop requests, Phase 7 should compose multiple
computer_control actions.

Phase 7 reasons about WHAT actions and sequencing are required.
Phase 13 decides HOW each action is physically executed.


PHASE 13 FINAL RULES:

1. Use only canonical Phase 13 actions exposed in the registered
   computer_control contract.

2. NEVER include or invent approved.
   Approval belongs only to Phase 6.

3. Never invent actions such as:

       window.fullscreen
       application.close
       filesystem.verify

   unless they actually exist in the registered tool contract.

4. Exact important contracts:

       clipboard.write
           arguments={
               "text": "<text>"
           }

       accessibility.set_value
           arguments={
               "value": "<text>",
               "selector": {...}
           }

       filesystem.write
           target="<path>"
           arguments={
               "content": "<text>"
           }

       filesystem.exists
           target="<path>"
           arguments={}

       filesystem.inspect
           target="<known path>"
           arguments={}

       window.close
           target="<window>"

       window.place
           target="<window>"
           arguments={
               "monitor_index": <1-based integer>,
               "maximized": true
           }

       monitor.list
           target=""
           arguments={}

5. Friendly user paths are valid:

       Desktop/foo.txt
       Documents/foo.txt
       Downloads/foo.txt

   Phase 13 resolves them to real Windows user folders.

6. For multi-monitor requests:

   - use monitor.list when monitor availability matters
   - rely on actual monitor evidence
   - use window.place with the requested monitor_index
   - preserve the requested monitor numbers exactly
   - never assume monitor 2 or monitor 3 exists

7. Prefer dedicated VS Code tools for opening projects/workspaces/files.

8. After opening VS Code, use computer_control window.place for monitor
   positioning when requested.

9. Prefer browser tools / DOM for browser-page navigation and interaction.

10. YouTube video fullscreen is a page/player operation.
    Maximizing Chrome is NOT equivalent to fullscreening the video.


PROJECT / PATH DISCOVERY:

11. When the user names a project, workspace, folder, or file but its
    real filesystem path is unknown, DO NOT guess a path.

12. Never assume the requested project is relative to P.E.P.P.E.R.'s
    repository.

13. Prefer the registered:

        search_filesystem

    tool for locating projects, workspaces, folders, or files outside
    the active workspace.

14. search_filesystem is the standard Phase 7 filesystem-discovery tool.

15. Do NOT generate:

        run_python
        PowerShell
        os.walk
        pathlib traversal
        Get-ChildItem recursion
        custom filesystem crawling scripts

    when search_filesystem can perform the requested discovery.

16. Use filesystem.inspect only for ONE already-known path.

17. filesystem.inspect does NOT enumerate or search children.

18. list_directory is appropriate when the exact directory to enumerate
    is already known and lies within the tool's supported workspace.

19. search_filesystem is appropriate when the requested filesystem
    location itself is unknown.

20. For a named project such as FinalCollegePortfolio, a good discovery
    action is:

        search_filesystem(
            query="FinalCollegePortfolio",
            kind="directory"
        )

21. Once search_filesystem returns real matches, consume the exact:

        result.matches[].path

    value.

22. Never reconstruct, shorten, normalize from memory, or guess the
    discovered path.

23. Once a real absolute path is observed, preserve that exact path for
    later VS Code, filesystem, or application actions.


Example:

User:
    Open FinalCollegePortfolio in a new VS Code window.

If its path is unknown:

Correct INITIAL plan:

1.
    Tool:
        search_filesystem

    Arguments:
        {
            "query": "FinalCollegePortfolio",
            "kind": "directory"
        }

STOP the initial plan there.

After the real result is observed, continuation may use:

    open_workspace_in_vscode(
        workspace_path=<exact result.matches[].path>,
        new_window=True
    )


Incorrect:

    run_python(
        arguments=[
            "-c",
            "import os; os.walk(...)"
        ]
    )

Incorrect:

    list_directory(
        path="."
    )

followed immediately by:

    open_workspace_in_vscode(
        workspace_path="FinalCollegePortfolio"
    )

when the real path has not yet been observed.


DEPENDENT-STEP RULE:

24. When a later action requires a value that must first be discovered
    by an earlier REAL tool result, DO NOT pre-plan the dependent action
    with a guessed value.

25. Plan only the action or actions required to obtain the missing real
    information.

26. Allow Phase 7 continuation to consume the real result.

27. Then continuation may create the dependent action using the exact
    observed value.

28. Never pre-plan a dependent action using a:

        guessed path
        placeholder path
        relative project name
        guessed URL
        guessed process id
        guessed window handle
        guessed monitor
        guessed account
        guessed selector

    when an earlier action exists specifically to discover it.

29. Adaptive planning is expected.

30. It is completely valid for the initial Phase 7 plan to contain only
    one discovery action.


Example:

User:
    Find MyProject and open it in VS Code.

Correct INITIAL plan:

    search_filesystem(
        query="MyProject",
        kind="directory"
    )

STOP.

Continuation sees:

    C:\\Users\\Example\\Desktop\\MyProject

and then plans:

    open_workspace_in_vscode(
        workspace_path=
            "C:\\Users\\Example\\Desktop\\MyProject",
        new_window=True
    )


INSPECTION AND EXECUTION RULES:

31. Prefer inspection before modification when investigation is needed.

32. Do not invent tool results.

33. Do not assume future steps succeed.

34. Do not include conversational responses as plan steps.

35. Preserve the user's requested ordering.

36. Do not automatically commit or push unless explicitly requested.

37. When creating source code, include COMPLETE intended file contents
    in the create_file or write_file content argument.

38. create_file may create parent directories automatically, so do not
    add unnecessary directory-creation steps.

39. For normal Python execution, prefer run_python.

40. run_python is NOT a replacement for registered Phase 13 computer
    actions or search_filesystem.

41. Do NOT create conditional future plan steps such as:

        "If execution fails, inspect the file."

    Conditional behavior belongs to the recovery controller.

42. Do NOT add a separate verification step merely to inspect stdout.

    The Phase 7 verifier receives real tool results automatically.


PROJECT KNOWLEDGE QUESTIONS:

Do NOT use Phase 7 merely because the user asks where code is located,
how part of the current project works, what a file does, or where a
function/class is implemented.

Examples that should normally use_agent = false:

- "Where is memory retrieval implemented?"
- "What does assistant/tools/terminal.py do?"
- "Where is the Phase 7 planner?"
- "Explain the memory system."
- "What file handles screen capture?"

P.E.P.P.E.R. already has project knowledge retrieval for these questions.

Use Phase 7 only when the user explicitly asks P.E.P.P.E.R. to perform
computer actions such as opening, editing, executing, searching the
live filesystem when indexed knowledge is insufficient, testing,
debugging, or modifying something.


TOOL ARGUMENT CONTRACTS:

The registered tool descriptions include exact Python signatures.

You MUST use parameter names from those signatures exactly.

Never invent argument names.


Example:

If the registered signature is:

run_python(
    arguments=None,
    cwd=".",
    workspace_path=None,
    timeout=60
)

and the user wants to run:

    TypewriterTest/typewriter.py

correct:

{
    "arguments": [
        "TypewriterTest/typewriter.py"
    ]
}

incorrect:

{
    "path": "TypewriterTest/typewriter.py"
}


Example:

If the tool signature is:

open_file_in_vscode(
    path,
    line=None,
    workspace_path=None,
    new_window=False
)

and the user explicitly requests a new window:

{
    "path": "TypewriterTest/typewriter.py",
    "new_window": true
}


Example:

If the registered signature is:

search_filesystem(
    query,
    roots=None,
    kind="any",
    max_results=25,
    max_depth=6
)

and the user wants to locate FinalCollegePortfolio:

{
    "query": "FinalCollegePortfolio",
    "kind": "directory"
}


ADAPTIVE / ITERATIVE TASKS:

Phase 7 MUST be used when the request contains adaptive behavior,
even when only ONE immediate action is known initially.

Examples:

- "Run this and fix it if it fails."
- "Debug this until it works."
- "Run the tests and investigate any failures."
- "Try this and correct whatever goes wrong."
- "Keep working until it succeeds."
- "Run it, inspect errors, fix them, and rerun."
- "Verify the result and repair problems if necessary."
- "Run this script and keep debugging until it exits successfully."


For adaptive tasks it is valid for the INITIAL plan to contain only
one step.


Example:

User:

Run TypewriterTest/typewriter.py. If it fails, debug it until it works.

Correct initial plan:

1. run_python

Do NOT pre-plan a repair.

Do NOT assume what the error will be.

The recovery controller will inspect real stderr/stdout and generate
corrective work dynamically.


PHASE 10 MULTI-INTENT CONNECTED SERVICES:

Multiple independent connected-service requests in one user message
belong to Phase 7.

Each requested connected-service capability becomes its own
integration_execute step.


Example:

User:

    Check the weather in Honolulu and show my latest GitHub commits
    to E.V.-Assistant.

Correct plan:

Step 1:
    Tool:
        integration_execute

    Arguments:
        {
            "capability": "weather.current",
            "provider": "weather",
            "account_id": "public",
            "routing_mode": "explicit_account",
            "arguments": {
                "location": "Honolulu"
            }
        }

Step 2:
    Tool:
        integration_execute

    Arguments:
        {
            "capability": "github.commits",
            "provider": "github",
            "account_id": "primary",
            "routing_mode": "explicit_account",
            "arguments": {
                "repo": "E.V.-Assistant"
            }
        }


PHASE 10 MULTI-INTENT RULES:

1. Each integration_execute step performs exactly one capability.

2. Use canonical registered capability names when possible.

3. Never combine multiple capabilities into one integration_execute call.

4. Never bypass Phase 6 permissions.

5. Never include or invent approved.

6. Do not invent accounts.

7. Preserve explicit entities such as repository, location, page title,
   section, symbol, dates, and account identifiers.

8. Multiple independent connected-service reads are Phase 7 even when
   the second does not depend on the first.

9. Use the smallest number of steps required.

10. Final verification should synthesize successful integration results
    into one user-facing answer.


MULTI-STEP EXAMPLE:

User:

Create TypewriterTest/typewriter.py, open it in a new VS Code window,
and run it.

Correct Phase 7 plan:

Step 1:
    Tool:
        create_file

    Arguments:
        {
            "path":
                "TypewriterTest/typewriter.py",

            "content":
                "<complete Python source>"
        }

Step 2:
    Tool:
        open_file_in_vscode

    Arguments:
        {
            "path":
                "TypewriterTest/typewriter.py",

            "new_window":
                true
        }

Step 3:
    Tool:
        run_python

    Arguments:
        {
            "arguments":
                [
                    "TypewriterTest/typewriter.py"
                ]
        }

use_agent = true


SINGLE ACTION EXAMPLE:

User:

Show me my Git status.

Only one direct action is needed:

    git_status

Therefore:

    use_agent = false


NO COMPUTER ACTION EXAMPLE:

User:

What's 2 + 2?

Therefore:

    use_agent = false
"""


# ---------------------------------------------------------------------------
# Tool Description
# ---------------------------------------------------------------------------

def describe_agent_tools():
    """
    Returns registered Phase 6 tools with their exact callable
    signatures.

    This prevents the planner from inventing argument names.

    Executor-only computer_control approval state is intentionally hidden.
    """

    load_default_tools()

    blocks = []

    for tool in list_tools():

        try:

            signature = inspect.signature(
                tool.function
            )

            if tool.name == "computer_control":

                parameters = [
                    parameter
                    for name, parameter
                    in signature.parameters.items()
                    if name != "approved"
                ]

                signature = signature.replace(
                    parameters=parameters
                )

        except (
            TypeError,
            ValueError,
        ):

            signature = (
                "(signature unavailable)"
            )

        blocks.append(
            (
                f"Tool: {tool.name}\n"
                f"Category: {tool.category}\n"
                f"Risk: {tool.risk}\n"
                f"Signature: "
                f"{tool.name}{signature}\n"
                f"Description: "
                f"{tool.description}"
            )
        )

    return "\n\n".join(
        blocks
    )


# ---------------------------------------------------------------------------
# Parse Arguments
# ---------------------------------------------------------------------------

def parse_arguments(
    arguments_json: str,
):
    """
    Converts structured planner JSON into a Python dictionary.

    Invalid JSON safely becomes an empty dictionary.
    """

    if not arguments_json:

        return {}

    try:

        arguments = json.loads(
            arguments_json
        )

    except json.JSONDecodeError:

        return {}

    if not isinstance(
        arguments,
        dict,
    ):

        return {}

    return arguments


# ---------------------------------------------------------------------------
# Registered Tool Validation
# ---------------------------------------------------------------------------

def get_registered_tool_names():
    """
    Returns the currently registered tool names.
    """

    load_default_tools()

    return {
        tool.name
        for tool
        in list_tools()
    }


def tool_name_exists(
    tool_name: str,
):
    """
    Prevents a hallucinated tool from entering an AgentPlan.
    """

    return (
        tool_name
        in get_registered_tool_names()
    )


# ---------------------------------------------------------------------------
# Plan Task
# ---------------------------------------------------------------------------

def plan_task(
    user_message: str,
):
    """
    Converts a natural-language user goal into an AgentPlan.

    Outcomes:

        use_agent=False
            Normal reasoning or Phase 6 should handle the request.

        use_agent=True
            Phase 7 should take ownership of the goal.

    Adaptive Phase 7 plans may contain only one INITIAL step because
    additional steps are generated after real execution results.
    """

    load_default_tools()

    user_message = (
        user_message.strip()
    )

    if not user_message:

        return AgentPlan(
            goal="",

            use_agent=False,

            confidence=100,

            summary=(
                "No user request was provided."
            ),
        )

    # -----------------------------------------------------------------------
    # Normalize User Input
    # -----------------------------------------------------------------------

    normalized_user_message = (
        normalize_user_input(
            user_message
        )
    )

    prompt = (
        f"{PLANNER_SYSTEM_PROMPT}\n\n"

        "REGISTERED TOOL CONTRACTS:\n\n"

        f"{describe_agent_tools()}\n\n"

        "USER GOAL:\n"

        f"{normalized_user_message}"
    )

    try:

        response = (
            client.responses.parse(
                model=
                    "gpt-5.5",

                instructions=(
                    "Determine whether this is "
                    "a Phase 7 agentic task and "
                    "create the smallest valid "
                    "initial execution plan."
                ),

                input=
                    prompt,

                text_format=
                    PlannerResponse,
            )
        )

        parsed = (
            response.output_parsed
        )

    except Exception as error:

        return AgentPlan(
            goal=
                user_message,

            use_agent=False,

            confidence=0,

            summary=(
                "Agent planning failed: "
                f"{error}"
            ),
        )

    if parsed is None:

        return AgentPlan(
            goal=
                user_message,

            use_agent=False,

            confidence=0,

            summary=(
                "Agent planner returned "
                "no structured result."
            ),
        )

    # -----------------------------------------------------------------------
    # Phase 7 Not Required
    # -----------------------------------------------------------------------

    if not parsed.use_agent:

        return AgentPlan(
            goal=
                user_message,

            use_agent=False,

            confidence=
                parsed.confidence,

            summary=
                parsed.summary,
        )

    # -----------------------------------------------------------------------
    # Convert Planned Steps
    # -----------------------------------------------------------------------

    steps = []

    for planned in parsed.steps[
        :MAX_INITIAL_STEPS
    ]:

        tool_name = (
            planned.tool_name
            .strip()
            .lower()
        )

        if not tool_name_exists(
            tool_name
        ):

            continue

        arguments = (
            parse_arguments(
                planned.arguments_json
            )
        )

        # -------------------------------------------------------------------
        # Phase 10 Integration Argument Preparation
        # -------------------------------------------------------------------

        if (
            tool_name
            == "integration_execute"
        ):

            arguments = (
                prepare_integration_arguments(
                    arguments
                )
            )

        # -------------------------------------------------------------------
        # Security: Planner May Never Supply Approval
        # -------------------------------------------------------------------

        if (
            tool_name
            == "computer_control"
        ):

            arguments.pop(
                "approved",
                None,
            )

        steps.append(
            AgentStep(
                step_number=
                    len(steps)
                    + 1,

                description=
                    planned.description,

                tool_name=
                    tool_name,

                arguments=
                    arguments,
            )
        )

    # -----------------------------------------------------------------------
    # Agent Needs At Least One Initial Action
    # -----------------------------------------------------------------------

    if not steps:

        return AgentPlan(
            goal=
                user_message,

            use_agent=False,

            confidence=
                parsed.confidence,

            summary=(
                "No valid initial "
                "computer action was planned."
            ),
        )

    # -----------------------------------------------------------------------
    # Return Agent Plan
    # -----------------------------------------------------------------------

    return AgentPlan(
        goal=
            user_message,

        use_agent=True,

        steps=
            steps,

        confidence=
            parsed.confidence,

        summary=
            parsed.summary,
    )


# ---------------------------------------------------------------------------
# Format Plan
# ---------------------------------------------------------------------------

def format_plan(
    plan: AgentPlan,
):
    """
    Creates readable terminal output for Phase 7 debugging.
    """

    lines = [
        (
            f"Goal: "
            f"{plan.goal}"
        ),

        (
            f"Use agent: "
            f"{plan.use_agent}"
        ),

        (
            f"Confidence: "
            f"{plan.confidence}"
        ),
    ]

    if plan.summary:

        lines.append(
            (
                f"Summary: "
                f"{plan.summary}"
            )
        )

    if plan.steps:

        lines.append(
            ""
        )

        lines.append(
            "Steps:"
        )

        for step in plan.steps:

            lines.append(
                (
                    f"{step.step_number}. "
                    f"{step.description}"
                )
            )

            lines.append(
                (
                    "   Tool: "
                    f"{step.tool_name}"
                )
            )

            lines.append(
                (
                    "   Arguments: "
                    f"{step.arguments}"
                )
            )

    return "\n".join(
        lines
    )


# ---------------------------------------------------------------------------
# Standalone Test
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    print(
        "P.E.P.P.E.R. Agent Planner"
    )

    print(
        "-----------------------"
    )

    tests = (
        "What's 2 + 2?",

        "Show me my Git status.",

        (
            "Open FinalCollegePortfolio "
            "in a new VS Code window."
        ),

        (
            "Open VS Code in a new window for "
            "FinalCollegePortfolio, maximize it "
            "on monitor 1, open Chrome to the "
            "Hacksmith YouTube page, then open "
            "Canvas in another browser tab."
        ),

        (
            "Run TypewriterTest/typewriter.py. "
            "If it fails, inspect the actual "
            "error and keep debugging until "
            "it succeeds."
        ),
    )

    for message in tests:

        print()

        print(
            "User:",
            message,
        )

        plan = plan_task(
            message
        )

        print(
            format_plan(
                plan
            )
        )