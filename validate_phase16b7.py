"""
P.E.P.P.E.R. - Phase 16B World-State Validation

Phase 16B.7

Purpose:
    Deterministically validates the operational-RAM foundation built in
    Phase 16B without invoking providers, network integrations, screenshots,
    project indexing, or the reasoning model.

Validates:
    1. Core set/get
    2. Fresh-state classification
    3. Stale-usable classification
    4. Expired classification
    5. Absent classification
    6. Explicit single-key invalidation
    7. Prefix invalidation
    8. Computer/workspace adapter publication
    9. Integration adapter publication
    10. Failed integration results are not published
    11. Need-aware cache compatibility rules for Phase 16B.6 hardening
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from assistant.world_state.computer_adapter import (
    publish_live_context_snapshot,
)
from assistant.world_state.core import (
    clear_world_state,
    get_world_state,
    set_world_state,
)
from assistant.world_state.integration_adapter import (
    get_integration_world_state,
    publish_integration_execution,
)
from assistant.world_state.policy import (
    WorldStateStatus,
    evaluate_world_state,
    invalidate_world_state,
    invalidate_world_state_prefix,
)


def _check(
    condition: bool,
    label: str,
):
    if not condition:
        raise AssertionError(label)

    print(f"PASS: {label}")


def _iso_age(
    seconds: float,
) -> str:
    return (
        datetime.now(timezone.utc)
        - timedelta(seconds=seconds)
    ).isoformat()


def cached_context_satisfies_needs(
    cached_context: dict,
    requested_needs: dict,
) -> bool:
    """
    Phase 16B.7 compatibility rule.

    A cached computer.context snapshot is reusable only if it contains every
    optional context section required by the new request.

    Core system context is always present in normal perception snapshots.
    Optional sections are workspace, all_workspaces, applications, terminal,
    and clipboard.
    """

    if not isinstance(cached_context, dict):
        return False

    cached_needs = (
        cached_context.get("needs")
        if isinstance(cached_context.get("needs"), dict)
        else {}
    )

    for need in (
        "workspace",
        "all_workspaces",
        "applications",
        "terminal",
        "clipboard",
    ):
        if (
            requested_needs.get(need)
            and not cached_needs.get(need)
        ):
            return False

    if (
        requested_needs.get("workspace")
        and not isinstance(
            cached_context.get("workspace"),
            dict,
        )
    ):
        return False

    if (
        requested_needs.get("clipboard")
        and cached_context.get("clipboard") is None
    ):
        return False

    return True


def run():
    clear_world_state()

    # ------------------------------------------------------------------
    # Core + freshness policy
    # ------------------------------------------------------------------

    set_world_state(
        "diagnostic.fresh",
        {"ok": True},
        source="phase16b7",
        fresh_for_seconds=30,
    )

    fresh = evaluate_world_state(
        "diagnostic.fresh"
    )

    _check(
        fresh.status == WorldStateStatus.FRESH
        and fresh.usable,
        "fresh state is usable",
    )

    set_world_state(
        "integration.weather.current",
        {"temperature": 76},
        source="phase16b7",
        fresh_for_seconds=300,
        updated_at=_iso_age(500),
    )

    stale = evaluate_world_state(
        "integration.weather.current"
    )

    _check(
        stale.status == WorldStateStatus.STALE_USABLE
        and stale.usable,
        "bounded stale integration state remains usable",
    )

    set_world_state(
        "integration.email.important",
        {"count": 2},
        source="phase16b7",
        fresh_for_seconds=60,
        updated_at=_iso_age(500),
    )

    expired = evaluate_world_state(
        "integration.email.important"
    )

    _check(
        expired.status == WorldStateStatus.EXPIRED
        and not expired.usable,
        "expired state is rejected",
    )

    absent = evaluate_world_state(
        "diagnostic.missing"
    )

    _check(
        absent.status == WorldStateStatus.ABSENT
        and not absent.usable,
        "missing state is absent",
    )

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    _check(
        invalidate_world_state(
            "diagnostic.fresh"
        ),
        "single-key invalidation removes existing state",
    )

    _check(
        get_world_state(
            "diagnostic.fresh"
        ) is None,
        "single-key invalidation is observable",
    )

    set_world_state(
        "diagnostic.prefix.one",
        1,
        source="phase16b7",
        fresh_for_seconds=30,
    )
    set_world_state(
        "diagnostic.prefix.two",
        2,
        source="phase16b7",
        fresh_for_seconds=30,
    )

    removed = invalidate_world_state_prefix(
        "diagnostic.prefix."
    )

    _check(
        set(removed)
        == {
            "diagnostic.prefix.one",
            "diagnostic.prefix.two",
        },
        "prefix invalidation removes matching records",
    )

    # ------------------------------------------------------------------
    # Computer/workspace adapter
    # ------------------------------------------------------------------

    sample_context = {
        "timestamp": "2026-08-27T21:00:00",
        "needs": {
            "system": True,
            "workspace": True,
            "all_workspaces": True,
            "applications": True,
            "terminal": False,
            "clipboard": False,
        },
        "system": {
            "active_application": "Code.exe",
            "active_window": "brain.py - eve-assistant - Visual Studio Code",
            "active_file": "brain.py",
            "visible_applications": [
                {
                    "process": "Code.exe",
                    "title": "brain.py - eve-assistant - Visual Studio Code",
                }
            ],
        },
        "workspace": {
            "workspace_name": "eve-assistant",
            "workspace_path": r"C:\repo\eve-assistant",
            "git_repository": r"C:\repo\eve-assistant",
            "git_branch": "main",
            "modified_files": ["assistant/brain.py"],
            "detection_source": "active_window",
            "open_workspaces": [
                {
                    "workspace_name": "eve-assistant",
                    "workspace_path": r"C:\repo\eve-assistant",
                    "active": True,
                    "resolved": True,
                }
            ],
        },
        "clipboard": None,
    }

    publish_live_context_snapshot(
        sample_context
    )

    active_file = get_world_state(
        "computer.active_file"
    )

    open_workspaces = get_world_state(
        "workspace.open"
    )

    _check(
        active_file is not None
        and active_file.value == "brain.py",
        "computer adapter publishes active_file",
    )

    _check(
        open_workspaces is not None
        and isinstance(open_workspaces.value, list)
        and len(open_workspaces.value) == 1,
        "computer adapter publishes workspace.open",
    )

    # ------------------------------------------------------------------
    # Integration adapter
    # ------------------------------------------------------------------

    successful_execution = {
        "capability": "weather.current",
        "provider": "weather",
        "result": {
            "evidence": [
                {
                    "data": {
                        "temperature": 77,
                        "condition": "clear",
                    }
                }
            ]
        },
    }

    record = publish_integration_execution(
        successful_execution
    )

    _check(
        record is not None
        and record.key == "integration.weather.current",
        "successful integration execution publishes state",
    )

    integration_record = get_integration_world_state(
        "weather.current"
    )

    _check(
        integration_record is not None
        and integration_record.value.get("temperature") == 77,
        "published integration state is retrievable",
    )

    invalidate_world_state(
        "integration.weather.current"
    )

    failed_execution = {
        "capability": "weather.current",
        "provider": "weather",
        "success": False,
        "error": "diagnostic failure",
        "result": {},
    }

    failed_record = publish_integration_execution(
        failed_execution
    )

    _check(
        failed_record is None
        and get_integration_world_state(
            "weather.current"
        ) is None,
        "failed integration execution is not published",
    )

    # ------------------------------------------------------------------
    # Need-aware cache compatibility
    # ------------------------------------------------------------------

    cached_app_only = {
        "timestamp": "2026-08-27T21:00:00",
        "needs": {
            "system": True,
            "workspace": False,
            "all_workspaces": False,
            "applications": True,
            "terminal": False,
            "clipboard": False,
        },
        "system": {
            "active_window": "Visual Studio Code",
        },
        "workspace": None,
        "clipboard": None,
    }

    app_request = {
        "system": True,
        "workspace": False,
        "all_workspaces": False,
        "applications": True,
        "terminal": False,
        "clipboard": False,
    }

    clipboard_request = {
        "system": True,
        "workspace": False,
        "all_workspaces": False,
        "applications": False,
        "terminal": False,
        "clipboard": True,
    }

    _check(
        cached_context_satisfies_needs(
            cached_app_only,
            app_request,
        ),
        "compatible cached context may be reused",
    )

    _check(
        not cached_context_satisfies_needs(
            cached_app_only,
            clipboard_request,
        ),
        "incompatible cached context must be recollected",
    )

    print()
    print("PHASE 16B.7 VALIDATION PASSED")


if __name__ == "__main__":
    run()
