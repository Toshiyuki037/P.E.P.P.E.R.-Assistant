"""
P.E.P.P.E.R. - Integration World-State Adapter

Phase 16B.4

Purpose:
    Publishes successful existing integration executions into Phase 16
    operational RAM without changing provider execution, routing, aggregation,
    or deterministic presentation.

Important:
    - Existing integrations remain authoritative.
    - This module performs no provider calls.
    - Importing this module performs no work.
    - Failed/invalid executions are never published as current live state.
"""

from __future__ import annotations

from typing import Any

from assistant.core.events import publish
from assistant.core.events.definitions import INTEGRATION_UPDATED


from .core import (
    get_world_state,
    get_world_state_snapshot,
    set_world_state,
)


DEFAULT_INTEGRATION_FRESH_SECONDS = 300.0

_CAPABILITY_FRESHNESS_SECONDS = {
    "weather.current": 300.0,
    "weather.forecast": 900.0,
    "calendar.upcoming": 60.0,
    "calendar.events": 60.0,
    "email.important": 60.0,
    "email.unread": 60.0,
    "finance.summary": 300.0,
    "finance.market": 300.0,
}


def _clean_text(
    value: Any,
) -> str:
    return str(
        value
        or ""
    ).strip()


def _normalize_capability(
    capability: Any,
) -> str:
    return (
        _clean_text(
            capability
        )
        .lower()
    )


def integration_world_state_key(
    capability: str,
) -> str:
    """
    Converts an integration capability into its stable RAM key.

    Examples:
        weather.current -> integration.weather.current
        email.important -> integration.email.important
    """

    normalized = (
        _normalize_capability(
            capability
        )
    )

    if not normalized:
        raise ValueError(
            "Integration capability cannot be empty."
        )

    return (
        f"integration.{normalized}"
    )


def _execution_result(
    execution: dict[str, Any],
) -> dict[str, Any]:
    result = execution.get(
        "result"
    )

    return (
        result
        if isinstance(
            result,
            dict,
        )
        else {}
    )


def _execution_succeeded(
    execution: dict[str, Any],
) -> bool:
    """
    Conservative success detection.

    Explicit failure flags/errors win. If the integration contract does not
    expose an explicit success flag, the presence of structured evidence/data
    is accepted as successful execution.
    """

    result = _execution_result(
        execution
    )

    for container in (
        execution,
        result,
    ):
        if container.get(
            "success"
        ) is False:
            return False

        if container.get(
            "ok"
        ) is False:
            return False

        if container.get(
            "error"
        ):
            return False

        status = (
            _clean_text(
                container.get(
                    "status"
                )
            )
            .lower()
        )

        if status in {
            "failed",
            "failure",
            "error",
        }:
            return False

    if (
        execution.get("success") is True
        or execution.get("ok") is True
        or result.get("success") is True
        or result.get("ok") is True
    ):
        return True

    evidence = result.get(
        "evidence"
    )

    if isinstance(
        evidence,
        list,
    ):
        for item in evidence:
            if (
                isinstance(
                    item,
                    dict,
                )
                and item.get(
                    "data"
                )
                is not None
            ):
                return True

    if result.get(
        "data"
    ) is not None:
        return True

    return False


def _extract_payload(
    execution: dict[str, Any],
):
    """
    Preserves the current Phase 16A integration contract:

        execution["result"]["evidence"][0]["data"]

    while tolerating result["data"] as a safe fallback.
    """

    result = _execution_result(
        execution
    )

    evidence = result.get(
        "evidence"
    )

    if isinstance(
        evidence,
        list,
    ):
        for item in evidence:
            if not isinstance(
                item,
                dict,
            ):
                continue

            if item.get(
                "data"
            ) is not None:
                return item.get(
                    "data"
                )

    if result.get(
        "data"
    ) is not None:
        return result.get(
            "data"
        )

    return None


def _extract_capability(
    execution: dict[str, Any],
    capability: str | None = None,
) -> str:
    candidates = (
        capability,
        execution.get(
            "capability"
        ),
        _execution_result(
            execution
        ).get(
            "capability"
        ),
    )

    for candidate in candidates:
        normalized = (
            _normalize_capability(
                candidate
            )
        )

        if normalized:
            return normalized

    raise ValueError(
        "Integration capability could not be determined."
    )


def _freshness_for_capability(
    capability: str,
    fresh_for_seconds: float | None,
) -> float:
    if fresh_for_seconds is not None:
        value = float(
            fresh_for_seconds
        )

        if value < 0:
            raise ValueError(
                "fresh_for_seconds cannot be negative."
            )

        return value

    return float(
        _CAPABILITY_FRESHNESS_SECONDS.get(
            capability,
            DEFAULT_INTEGRATION_FRESH_SECONDS,
        )
    )


def publish_integration_execution(
    execution: dict[str, Any] | None,
    *,
    capability: str | None = None,
    provider: str | None = None,
    account_id: str | None = None,
    routing_mode: str | None = None,
    fresh_for_seconds: float | None = None,
    confidence: float = 1.0,
):
    """
    Publishes one already-completed successful integration execution.

    No integration/provider call occurs here.

    Returns:
        WorldStateRecord on success.
        None when execution is absent, failed, or has no structured payload.
    """

    if not isinstance(
        execution,
        dict,
    ):
        return None

    if not _execution_succeeded(
        execution
    ):
        return None

    payload = _extract_payload(
        execution
    )

    if payload is None:
        return None

    resolved_capability = (
        _extract_capability(
            execution,
            capability=capability,
        )
    )

    result = _execution_result(
        execution
    )

    resolved_provider = (
        _clean_text(
            provider
            or execution.get(
                "provider"
            )
            or result.get(
                "provider"
            )
        )
        or "integration"
    )

    resolved_account_id = (
        _clean_text(
            account_id
            or execution.get(
                "account_id"
            )
            or result.get(
                "account_id"
            )
        )
    )

    resolved_routing_mode = (
        _clean_text(
            routing_mode
            or execution.get(
                "routing_mode"
            )
            or result.get(
                "routing_mode"
            )
        )
    )

    key = integration_world_state_key(
        resolved_capability
    )

    record = set_world_state(
        key,
        payload,
        source=resolved_provider,
        fresh_for_seconds=(
            _freshness_for_capability(
                resolved_capability,
                fresh_for_seconds,
            )
        ),
        confidence=confidence,
        metadata={
            "producer":
                "assistant.world_state.integration_adapter",

            "capability":
                resolved_capability,

            "provider":
                resolved_provider,

            "account_id":
                resolved_account_id,

            "routing_mode":
                resolved_routing_mode,
        },
    )

    publish(
        INTEGRATION_UPDATED,
        {
            "capability": resolved_capability,
            "world_state_key": key,
            "record": record.to_dict(),
            "provider": resolved_provider,
            "account_id": resolved_account_id,
            "routing_mode": resolved_routing_mode,
        },
        source="assistant.world_state.integration_adapter",
    )

    return record


def get_integration_world_state(
    capability: str,
    *,
    require_fresh: bool = False,
):
    return get_world_state(
        integration_world_state_key(
            capability
        ),
        require_fresh=require_fresh,
    )


def get_integration_world_state_snapshot(
    *,
    include_stale: bool = True,
):
    return get_world_state_snapshot(
        prefix="integration.",
        include_stale=include_stale,
    )


# ---------------------------------------------------------------------------
# Standalone Diagnostic
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sample_execution = {
        "capability":
            "weather.current",

        "provider":
            "weather",

        "account_id":
            "public",

        "routing_mode":
            "explicit_account",

        "result": {
            "evidence": [
                {
                    "data": {
                        "temperature":
                            76,

                        "condition":
                            "clear",
                    },
                },
            ],
        },
    }

    record = publish_integration_execution(
        sample_execution
    )

    print(
        "P.E.P.P.E.R. Integration -> World State Adapter"
    )

    print(
        "----------------------------------------------"
    )

    print(
        (
            record.to_dict()
            if record is not None
            else "Sample execution was not published."
        )
    )
