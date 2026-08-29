"""
P.E.P.P.E.R. - Tool Executor

Created: August 9, 2026
Last Edited: August 12, 2026
Author: Max Maehara

Purpose:
    Provides the single controlled execution gateway for P.E.P.P.E.R.'s
    computer tools.

How It Works:
    1. Look up requested tool.
    2. Determine effective risk.
    3. Check permission policy.
    4. Audit the request.
    5. Execute if allowed.
    6. Capture result or error.
    7. Audit the outcome.

Important:
    Future brain/tool integration should call execute_tool()
    rather than invoking tool functions directly.

Phase 9:
    integration_execute receives dynamic risk based on the requested
    normalized integration capability.

    Examples:

        email.search
            -> low

        calendar.read
            -> low

        tasks.read
            -> low

        calendar.create
            -> medium

        tasks.create
            -> medium

        tasks.complete
            -> medium

        email.send
            -> high


Phase 13:
    computer_control receives dynamic risk based on the requested
    canonical computer action.

    Examples:

        filesystem.inspect
            -> low

        filesystem.exists
            -> low

        monitor.list
            -> low

        window.focus
            -> low

        window.place
            -> low

        accessibility.set_value
            -> medium

        clipboard.write
            -> medium

        window.close
            -> medium

        filesystem.delete
            -> high


Security:
    Unknown Phase 9 capabilities fail closed as high risk.

    Unknown Phase 13 actions fail closed as high risk.

    Planner/user-supplied approval state is discarded.

    Only execute_tool() may inject trusted approval into
    integration_execute and computer_control.
"""

from __future__ import annotations


from assistant.capabilities.integrations.permissions import (
    get_permission as
    get_integration_permission,
)

from assistant.capabilities.computer.capabilities import (
    get_action_risk as
    get_computer_action_risk,
)

from assistant.capabilities.computer.models import (
    DeviceRisk,
)


from .audit import (
    log_tool_event,
)

from .permissions import (
    classify_command_risk,
    evaluate_permission,
    highest_risk,
)

from .registry import (
    get_tool,
    load_default_tools,
)


# ---------------------------------------------------------------------------
# Load Registered Tools
# ---------------------------------------------------------------------------

load_default_tools()


# ---------------------------------------------------------------------------
# Phase 9 Integration Risk
# ---------------------------------------------------------------------------

def determine_integration_risk(
    arguments: dict,
):
    """
    Determines Phase 6 action risk from a normalized Phase 9
    integration capability.

    Unknown capabilities fail closed as high risk.
    """

    capability = (
        str(
            arguments.get(
                "capability",
                "",
            )
        )
        .strip()
        .lower()
    )


    if not capability:

        return "high"


    permission = (
        get_integration_permission(
            capability
        )
    )


    if permission is None:

        # ---------------------------------------------------------------
        # Fail Closed
        # ---------------------------------------------------------------
        #
        # Future integration capabilities must receive an explicit
        # Phase 9 permission policy before they may execute.
        # ---------------------------------------------------------------

        return "high"


    risk = (
        str(
            permission.risk
        )
        .strip()
        .lower()
    )


    if risk not in {
        "low",
        "medium",
        "high",
    }:

        return "high"


    return risk


# ---------------------------------------------------------------------------
# Phase 13 Computer Risk
# ---------------------------------------------------------------------------

def determine_computer_risk(
    arguments: dict,
):
    """
    Maps Phase 13 DeviceRisk onto the Phase 6 risk model.

    Phase 13:

        READ
            -> low

        LOW
            -> low

        MEDIUM
            -> medium

        HIGH
            -> high

    Unknown actions fail closed as high risk.
    """

    action = (
        str(
            arguments.get(
                "action",
                "",
            )
        )
        .strip()
        .lower()
    )


    if not action:

        return "high"


    risk = (
        get_computer_action_risk(
            action
        )
    )


    if risk in {
        DeviceRisk.READ,
        DeviceRisk.LOW,
    }:

        return "low"


    if risk == DeviceRisk.MEDIUM:

        return "medium"


    if risk == DeviceRisk.HIGH:

        return "high"


    # -----------------------------------------------------------------------
    # Fail Closed
    # -----------------------------------------------------------------------

    return "high"


# ---------------------------------------------------------------------------
# Effective Risk
# ---------------------------------------------------------------------------

def determine_effective_risk(
    tool,
    arguments: dict,
):
    """
    Calculates the final Phase 6 risk for one tool invocation.

    Sources of risk:

        tool base risk

        run_command
            -> command-level risk

        integration_execute
            -> Phase 9 capability-level risk

        computer_control
            -> Phase 13 action-level risk
    """

    risk = (
        tool.risk
    )


    # -----------------------------------------------------------------------
    # Terminal Risk Escalation
    # -----------------------------------------------------------------------

    if (
        tool.name
        == "run_command"
    ):

        command_arguments = (
            arguments.get(
                "arguments"
            )
            or []
        )


        command_text = " ".join(
            str(
                item
            )

            for item
            in command_arguments
        )


        command_risk = (
            classify_command_risk(
                command_text
            )
        )


        risk = highest_risk(
            risk,
            command_risk,
        )


    # -----------------------------------------------------------------------
    # Phase 9 Integration Risk Escalation
    # -----------------------------------------------------------------------
    #
    # IMPORTANT:
    #
    # computer_control MUST NOT enter this block.
    #
    # Phase 9 expects a "capability" argument.
    # Phase 13 uses an "action" argument.
    #
    # Sending computer_control through determine_integration_risk()
    # would cause it to fail closed as high risk because no Phase 9
    # capability exists.
    # -----------------------------------------------------------------------

    if (
        tool.name
        == "integration_execute"
    ):

        integration_risk = (
            determine_integration_risk(
                arguments
            )
        )


        risk = highest_risk(
            risk,
            integration_risk,
        )


    # -----------------------------------------------------------------------
    # Phase 13 Computer Risk Escalation
    # -----------------------------------------------------------------------

    if (
        tool.name
        == "computer_control"
    ):

        computer_risk = (
            determine_computer_risk(
                arguments
            )
        )


        risk = highest_risk(
            risk,
            computer_risk,
        )


    return risk


# ---------------------------------------------------------------------------
# Execute Registered Function
# ---------------------------------------------------------------------------

def invoke_tool_function(
    tool,
    arguments: dict,
    approved: bool,
):
    """
    Invokes the registered implementation.

    integration_execute and computer_control receive trusted approval
    state injected only by the Phase 6 executor.

    Planner/user supplied approval is always removed first.
    """

    if tool.name in {
        "integration_execute",
        "computer_control",
    }:

        call_arguments = dict(
            arguments
        )


        # -------------------------------------------------------------------
        # Planner/User Input May Never Supply Approval State
        # -------------------------------------------------------------------

        call_arguments.pop(
            "approved",
            None,
        )


        # -------------------------------------------------------------------
        # Trusted Phase 6 Approval Injection
        # -------------------------------------------------------------------

        call_arguments[
            "approved"
        ] = bool(
            approved
        )


        return tool.function(
            **call_arguments
        )


    # -----------------------------------------------------------------------
    # Ordinary Registered Tools
    # -----------------------------------------------------------------------

    return tool.function(
        **arguments
    )


# ---------------------------------------------------------------------------
# Main Executor
# ---------------------------------------------------------------------------

def execute_tool(
    tool_name: str,
    arguments=None,
    approved: bool = False,
):
    """
    Executes a registered tool through P.E.P.P.E.R.'s permission
    and audit layers.

    Returns a structured result dictionary.
    """

    if arguments is None:

        arguments = {}


    if not isinstance(
        arguments,
        dict,
    ):

        return {
            "success":
                False,

            "executed":
                False,

            "tool":
                tool_name,

            "error":
                (
                    "Tool arguments must "
                    "be a dictionary."
                ),
        }


    # -----------------------------------------------------------------------
    # Tool Lookup
    # -----------------------------------------------------------------------

    tool = (
        get_tool(
            tool_name
        )
    )


    if tool is None:

        return {
            "success":
                False,

            "executed":
                False,

            "tool":
                tool_name,

            "error":
                "Unknown tool.",
        }


    # -----------------------------------------------------------------------
    # Risk
    # -----------------------------------------------------------------------

    effective_risk = (
        determine_effective_risk(
            tool,
            arguments,
        )
    )


    # -----------------------------------------------------------------------
    # Permission
    # -----------------------------------------------------------------------

    permission = (
        evaluate_permission(
            base_risk=
                effective_risk,

            approved=
                approved,
        )
    )


    # -----------------------------------------------------------------------
    # Audit Permission Decision
    # -----------------------------------------------------------------------

    log_tool_event(
        tool_name=
            tool.name,

        status=
            (
                "approved"
                if permission.allowed
                else "blocked"
            ),

        risk=
            permission.risk,

        arguments=
            arguments,

        result={
            "permission_reason":
                permission.reason
        },
    )


    # -----------------------------------------------------------------------
    # Permission Block
    # -----------------------------------------------------------------------

    if not permission.allowed:

        return {
            "success":
                False,

            "executed":
                False,

            "tool":
                tool.name,

            "risk":
                permission.risk,

            "requires_approval":
                permission.requires_approval,

            "reason":
                permission.reason,
        }


    # -----------------------------------------------------------------------
    # Execution
    # -----------------------------------------------------------------------

    try:

        result = (
            invoke_tool_function(
                tool=
                    tool,

                arguments=
                    arguments,

                approved=
                    approved,
            )
        )


        # -------------------------------------------------------------------
        # Audit Success
        # -------------------------------------------------------------------

        log_tool_event(
            tool_name=
                tool.name,

            status=
                "success",

            risk=
                permission.risk,

            arguments=
                arguments,

            result=
                result,
        )


        return {
            "success":
                True,

            "executed":
                True,

            "tool":
                tool.name,

            "risk":
                permission.risk,

            "result":
                result,
        }


    except Exception as error:

        # -------------------------------------------------------------------
        # Audit Failure
        # -------------------------------------------------------------------

        log_tool_event(
            tool_name=
                tool.name,

            status=
                "error",

            risk=
                permission.risk,

            arguments=
                arguments,

            error=
                error,
        )


        return {
            "success":
                False,

            "executed":
                True,

            "tool":
                tool.name,

            "risk":
                permission.risk,

            "error":
                str(
                    error
                ),
        }


# ---------------------------------------------------------------------------
# Standalone Tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    print(
        "P.E.P.P.E.R. Tool Executor"
    )


    print(
        "-----------------------"
    )


    # -----------------------------------------------------------------------
    # Test 1 - Low-risk filesystem
    # -----------------------------------------------------------------------

    print()

    print(
        "TEST 1 - list_directory"
    )


    result = execute_tool(
        "list_directory",
        {
            "path":
                "."
        },
    )


    print(
        result
    )


    # -----------------------------------------------------------------------
    # Test 2 - Low-risk Python
    # -----------------------------------------------------------------------

    print()

    print(
        "TEST 2 - run_python"
    )


    result = execute_tool(
        "run_python",
        {
            "arguments":
                [
                    "-c",
                    (
                        "print("
                        "'P.E.P.P.E.R. executor works'"
                        ")"
                    ),
                ]
        },
    )


    print(
        result
    )


    # -----------------------------------------------------------------------
    # Test 3 - Medium-risk filesystem
    # -----------------------------------------------------------------------

    print()

    print(
        "TEST 3 - create_file without approval"
    )


    result = execute_tool(
        "create_file",
        {
            "path":
                (
                    "runtime/"
                    "phase6_test.txt"
                ),

            "content":
                "Phase 6 tool test.",
        },

        approved=
            False,
    )


    print(
        result
    )


    # -----------------------------------------------------------------------
    # Test 4 - Phase 9 Read Risk
    # -----------------------------------------------------------------------

    print()

    print(
        "TEST 4 - Phase 9 read risk"
    )


    integration_tool = (
        get_tool(
            "integration_execute"
        )
    )


    if integration_tool is not None:

        print(
            determine_effective_risk(
                integration_tool,
                {
                    "capability":
                        "tasks.read"
                },
            )
        )


        # -------------------------------------------------------------------
        # Test 5 - Phase 9 Medium Risk
        # -------------------------------------------------------------------

        print()

        print(
            "TEST 5 - Phase 9 write risk"
        )


        print(
            determine_effective_risk(
                integration_tool,
                {
                    "capability":
                        "calendar.create"
                },
            )
        )


        # -------------------------------------------------------------------
        # Test 6 - Phase 9 High Risk
        # -------------------------------------------------------------------

        print()

        print(
            "TEST 6 - Phase 9 email send risk"
        )


        print(
            determine_effective_risk(
                integration_tool,
                {
                    "capability":
                        "email.send"
                },
            )
        )


    # -----------------------------------------------------------------------
    # Test 7 - Phase 13 Computer Risk
    # -----------------------------------------------------------------------

    computer_tool = (
        get_tool(
            "computer_control"
        )
    )


    if computer_tool is not None:

        print()

        print(
            "TEST 7 - Phase 13 read risk"
        )


        print(
            determine_effective_risk(
                computer_tool,
                {
                    "action":
                        "filesystem.inspect",

                    "target":
                        "Desktop",

                    "arguments":
                        {},
                },
            )
        )


        print()

        print(
            "TEST 8 - Phase 13 medium risk"
        )


        print(
            determine_effective_risk(
                computer_tool,
                {
                    "action":
                        "accessibility.set_value",

                    "target":
                        "Notepad",

                    "arguments": {
                        "value":
                            "Hello",

                        "selector": {
                            "control_type":
                                "Document"
                        },
                    },
                },
            )
        )


        print()

        print(
            "TEST 9 - Phase 13 high risk"
        )


        print(
            determine_effective_risk(
                computer_tool,
                {
                    "action":
                        "filesystem.delete",

                    "target":
                        (
                            "Desktop/"
                            "phase13-test.txt"
                        ),

                    "arguments":
                        {},
                },
            )
        )