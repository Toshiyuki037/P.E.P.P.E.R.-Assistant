"""
P.E.P.P.E.R. - Computer / Workspace World-State Adapter

Phase 16B.3

Purpose:
    Publishes snapshots from the existing live perception subsystem into
    Phase 16 operational RAM.

Important:
    - Existing perception/context.py remains authoritative.
    - Existing workspace.py remains authoritative.
    - This adapter does not replace or alter perception collection.
    - Publishing is explicit; importing this module performs no collection.
"""

from __future__ import annotations

from typing import Any

from assistant.interaction.perception.context import get_live_context

from .core import (
    get_world_state,
    get_world_state_snapshot,
    set_world_state,
)


COMPUTER_CONTEXT_KEY = "computer.context"
COMPUTER_ACTIVE_APPLICATION_KEY = "computer.active_application"
COMPUTER_ACTIVE_WINDOW_KEY = "computer.active_window"
COMPUTER_ACTIVE_FILE_KEY = "computer.active_file"
COMPUTER_VISIBLE_APPLICATIONS_KEY = "computer.visible_applications"

WORKSPACE_ACTIVE_KEY = "workspace.active"
WORKSPACE_OPEN_KEY = "workspace.open"

SYSTEM_SNAPSHOT_KEY = "system.snapshot"


DEFAULT_COMPUTER_FRESH_SECONDS = 15.0
DEFAULT_WORKSPACE_FRESH_SECONDS = 30.0
DEFAULT_SYSTEM_FRESH_SECONDS = 30.0


def _publish(
    key: str,
    value: Any,
    *,
    source: str,
    fresh_for_seconds: float,
    metadata: dict[str, Any] | None = None,
):
    if value is None:
        return None

    return set_world_state(
        key,
        value,
        source=source,
        fresh_for_seconds=fresh_for_seconds,
        confidence=1.0,
        metadata=metadata or {},
    )


def publish_live_context_snapshot(
    context: dict[str, Any] | None,
):
    """
    Publishes one already-collected perception snapshot.

    This function itself performs no system collection.
    """

    if not isinstance(
        context,
        dict,
    ):
        return {}

    published = {}

    root = _publish(
        COMPUTER_CONTEXT_KEY,
        context,
        source="perception.context",
        fresh_for_seconds=DEFAULT_COMPUTER_FRESH_SECONDS,
        metadata={
            "producer":
                "assistant.interaction.perception.context",
            "snapshot_timestamp":
                context.get(
                    "timestamp"
                ),
        },
    )

    if root is not None:
        published[
            COMPUTER_CONTEXT_KEY
        ] = root

    system = (
        context.get("system")
        if isinstance(
            context.get("system"),
            dict,
        )
        else {}
    )

    workspace = (
        context.get("workspace")
        if isinstance(
            context.get("workspace"),
            dict,
        )
        else {}
    )

    scalar_records = (
        (
            COMPUTER_ACTIVE_APPLICATION_KEY,
            system.get(
                "active_application"
            ),
            DEFAULT_COMPUTER_FRESH_SECONDS,
        ),
        (
            COMPUTER_ACTIVE_WINDOW_KEY,
            system.get(
                "active_window"
            ),
            DEFAULT_COMPUTER_FRESH_SECONDS,
        ),
        (
            COMPUTER_ACTIVE_FILE_KEY,
            system.get(
                "active_file"
            ),
            DEFAULT_COMPUTER_FRESH_SECONDS,
        ),
        (
            COMPUTER_VISIBLE_APPLICATIONS_KEY,
            system.get(
                "visible_applications"
            ),
            DEFAULT_COMPUTER_FRESH_SECONDS,
        ),
        (
            WORKSPACE_OPEN_KEY,
            workspace.get(
                "open_workspaces"
            ),
            DEFAULT_WORKSPACE_FRESH_SECONDS,
        ),
    )

    for (
        key,
        value,
        freshness,
    ) in scalar_records:
        record = _publish(
            key,
            value,
            source="perception.context",
            fresh_for_seconds=freshness,
        )

        if record is not None:
            published[
                key
            ] = record

    if workspace:
        record = _publish(
            WORKSPACE_ACTIVE_KEY,
            workspace,
            source="perception.workspace",
            fresh_for_seconds=DEFAULT_WORKSPACE_FRESH_SECONDS,
            metadata={
                "producer":
                    "assistant.interaction.perception.workspace",
                "detection_source":
                    workspace.get(
                        "detection_source"
                    ),
            },
        )

        if record is not None:
            published[
                WORKSPACE_ACTIVE_KEY
            ] = record

    if system:
        record = _publish(
            SYSTEM_SNAPSHOT_KEY,
            system,
            source="perception.system",
            fresh_for_seconds=DEFAULT_SYSTEM_FRESH_SECONDS,
            metadata={
                "producer":
                    "assistant.interaction.perception.system",
            },
        )

        if record is not None:
            published[
                SYSTEM_SNAPSHOT_KEY
            ] = record

    return published


def collect_and_publish_live_context(
    user_message: str = "",
):
    """
    Uses the existing perception router once, then publishes that same snapshot.

    No duplicate workspace/system collection is introduced here.
    """

    context = get_live_context(
        user_message
    )

    publish_live_context_snapshot(
        context
    )

    return context


def get_computer_world_state(
    key: str,
    *,
    require_fresh: bool = False,
):
    return get_world_state(
        key,
        require_fresh=require_fresh,
    )


def get_computer_world_state_snapshot(
    *,
    include_stale: bool = True,
):
    result = {}

    for prefix in (
        "computer.",
        "workspace.",
        "system.",
    ):
        result.update(
            get_world_state_snapshot(
                prefix=prefix,
                include_stale=include_stale,
            )
        )

    return dict(
        sorted(
            result.items()
        )
    )


if __name__ == "__main__":
    collect_and_publish_live_context(
        "What application and workspace am I using?"
    )

    print(
        "P.E.P.P.E.R. Computer / Workspace -> World State Adapter"
    )

    print(
        "------------------------------------------------------"
    )

    snapshot = (
        get_computer_world_state_snapshot()
    )

    if not snapshot:
        print(
            "No computer/workspace state was published."
        )
    else:
        for key, record in snapshot.items():
            print(
                f"{key}: {record.to_dict()}"
            )
