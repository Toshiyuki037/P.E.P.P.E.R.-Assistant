"""
P.E.P.P.E.R. - World-State Freshness / Invalidation Policy

Phase 16B.5

Purpose:
    Defines how Phase 16 operational RAM classifies live state as:
        - fresh
        - stale but still usable as fallback
        - expired
        - absent

This module does not collect state and does not change any existing producer.
It only interprets WorldStateRecord freshness metadata and provides explicit
invalidation helpers.

Design rule:
    Fresh state may be used directly.
    Stale-usable state may be used only as a fallback and should be identified
    as stale by callers when that distinction matters.
    Expired state should not be used for current-state decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .core import (
    WorldStateRecord,
    delete_world_state,
    get_world_state,
)


class WorldStateStatus(str, Enum):
    FRESH = "fresh"
    STALE_USABLE = "stale_usable"
    EXPIRED = "expired"
    ABSENT = "absent"


@dataclass(frozen=True)
class WorldStatePolicyDecision:
    key: str
    status: WorldStateStatus
    record: WorldStateRecord | None
    age_seconds: float | None
    fresh_for_seconds: float | None
    usable: bool
    reason: str

    @property
    def is_fresh(self) -> bool:
        return (
            self.status
            == WorldStateStatus.FRESH
        )

    @property
    def is_stale_usable(self) -> bool:
        return (
            self.status
            == WorldStateStatus.STALE_USABLE
        )

    @property
    def is_expired(self) -> bool:
        return (
            self.status
            == WorldStateStatus.EXPIRED
        )

    @property
    def is_absent(self) -> bool:
        return (
            self.status
            == WorldStateStatus.ABSENT
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "key":
                self.key,

            "status":
                self.status.value,

            "age_seconds":
                self.age_seconds,

            "fresh_for_seconds":
                self.fresh_for_seconds,

            "usable":
                self.usable,

            "reason":
                self.reason,

            "record":
                (
                    self.record.to_dict()
                    if self.record is not None
                    else None
                ),
        }


# ---------------------------------------------------------------------------
# Default stale-fallback policy
# ---------------------------------------------------------------------------

#
# Multipliers define how long a stale value can remain available as fallback
# after its normal freshness window.
#
# Example:
#   weather.current fresh_for=300 seconds
#   multiplier=3.0
#   -> fresh through 5 minutes
#   -> stale_usable until 15 minutes old
#   -> expired after 15 minutes
#
_NAMESPACE_STALE_MULTIPLIERS = {
    "computer.":
        2.0,

    "workspace.":
        4.0,

    "system.":
        4.0,

    "integration.weather.":
        3.0,

    "integration.calendar.":
        2.0,

    "integration.email.":
        2.0,

    "integration.finance.":
        3.0,

    "location.":
        4.0,
}

DEFAULT_STALE_MULTIPLIER = 2.0


def _stale_multiplier_for_key(
    key: str,
) -> float:
    normalized = (
        str(
            key
            or ""
        )
        .strip()
        .lower()
    )

    best_prefix = ""
    best_value = (
        DEFAULT_STALE_MULTIPLIER
    )

    for (
        prefix,
        multiplier,
    ) in _NAMESPACE_STALE_MULTIPLIERS.items():
        if (
            normalized.startswith(
                prefix
            )
            and len(
                prefix
            )
            > len(
                best_prefix
            )
        ):
            best_prefix = prefix
            best_value = float(
                multiplier
            )

    return best_value


def classify_world_state_record(
    record: WorldStateRecord | None,
    *,
    key: str | None = None,
    stale_multiplier: float | None = None,
) -> WorldStatePolicyDecision:
    """
    Classifies one world-state record without modifying it.
    """

    resolved_key = (
        str(
            key
            or (
                record.key
                if record is not None
                else ""
            )
        )
        .strip()
        .lower()
    )

    if record is None:
        return WorldStatePolicyDecision(
            key=resolved_key,
            status=WorldStateStatus.ABSENT,
            record=None,
            age_seconds=None,
            fresh_for_seconds=None,
            usable=False,
            reason="No world-state record exists.",
        )

    age_seconds = float(
        record.age_seconds
    )

    fresh_for_seconds = (
        None
        if record.fresh_for_seconds is None
        else float(
            record.fresh_for_seconds
        )
    )

    if fresh_for_seconds is None:
        return WorldStatePolicyDecision(
            key=record.key,
            status=WorldStateStatus.FRESH,
            record=record,
            age_seconds=age_seconds,
            fresh_for_seconds=None,
            usable=True,
            reason=(
                "Record has no automatic freshness deadline."
            ),
        )

    if (
        age_seconds
        <= fresh_for_seconds
    ):
        return WorldStatePolicyDecision(
            key=record.key,
            status=WorldStateStatus.FRESH,
            record=record,
            age_seconds=age_seconds,
            fresh_for_seconds=fresh_for_seconds,
            usable=True,
            reason="Record is within its freshness window.",
        )

    multiplier = (
        float(
            stale_multiplier
        )
        if stale_multiplier is not None
        else _stale_multiplier_for_key(
            record.key
        )
    )

    if multiplier < 1.0:
        raise ValueError(
            "stale_multiplier must be at least 1.0."
        )

    stale_limit_seconds = (
        fresh_for_seconds
        * multiplier
    )

    if (
        age_seconds
        <= stale_limit_seconds
    ):
        return WorldStatePolicyDecision(
            key=record.key,
            status=WorldStateStatus.STALE_USABLE,
            record=record,
            age_seconds=age_seconds,
            fresh_for_seconds=fresh_for_seconds,
            usable=True,
            reason=(
                "Record is stale but remains within "
                "its bounded fallback window."
            ),
        )

    return WorldStatePolicyDecision(
        key=record.key,
        status=WorldStateStatus.EXPIRED,
        record=record,
        age_seconds=age_seconds,
        fresh_for_seconds=fresh_for_seconds,
        usable=False,
        reason=(
            "Record exceeded both its freshness "
            "and stale-fallback windows."
        ),
    )


def evaluate_world_state(
    key: str,
    *,
    stale_multiplier: float | None = None,
) -> WorldStatePolicyDecision:
    """
    Reads and classifies one world-state key.
    """

    record = get_world_state(
        key
    )

    return classify_world_state_record(
        record,
        key=key,
        stale_multiplier=stale_multiplier,
    )


def get_usable_world_state(
    key: str,
    *,
    allow_stale: bool = True,
    stale_multiplier: float | None = None,
) -> WorldStateRecord | None:
    """
    Returns a record only when policy permits its use.

    allow_stale=False:
        only fresh records are returned.

    allow_stale=True:
        fresh and stale_usable records are returned.
    """

    decision = evaluate_world_state(
        key,
        stale_multiplier=stale_multiplier,
    )

    if decision.is_fresh:
        return decision.record

    if (
        allow_stale
        and decision.is_stale_usable
    ):
        return decision.record

    return None


def invalidate_world_state(
    key: str,
) -> bool:
    """
    Explicitly removes one state item from operational RAM.

    Producers should call this when they know a previously published state is
    no longer valid, such as account disconnect, workspace close, or provider
    failure that makes the old value unsafe to retain.
    """

    return delete_world_state(
        key
    )


def invalidate_world_state_prefix(
    prefix: str,
) -> list[str]:
    """
    Explicitly removes all RAM records whose keys begin with prefix.

    Returns the keys that were removed.
    """

    from .core import WORLD_STATE

    normalized_prefix = (
        str(
            prefix
            or ""
        )
        .strip()
        .lower()
    )

    if not normalized_prefix:
        raise ValueError(
            "World-state invalidation prefix cannot be empty."
        )

    keys = WORLD_STATE.keys(
        prefix=normalized_prefix
    )

    removed = []

    for key in keys:
        if delete_world_state(
            key
        ):
            removed.append(
                key
            )

    return removed


# ---------------------------------------------------------------------------
# Standalone Diagnostic
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from datetime import (
        datetime,
        timedelta,
        timezone,
    )

    from .core import (
        clear_world_state,
        set_world_state,
    )

    clear_world_state()

    now = datetime.now(
        timezone.utc
    )

    set_world_state(
        "computer.active_window",
        "Visual Studio Code",
        source="diagnostic",
        fresh_for_seconds=15,
        updated_at=(
            now
            - timedelta(
                seconds=5
            )
        ).isoformat(),
    )

    set_world_state(
        "integration.weather.current",
        {
            "temperature":
                76,
        },
        source="diagnostic",
        fresh_for_seconds=300,
        updated_at=(
            now
            - timedelta(
                seconds=500
            )
        ).isoformat(),
    )

    set_world_state(
        "integration.email.important",
        {
            "count":
                2,
        },
        source="diagnostic",
        fresh_for_seconds=60,
        updated_at=(
            now
            - timedelta(
                seconds=500
            )
        ).isoformat(),
    )

    print(
        "P.E.P.P.E.R. World-State Freshness Policy"
    )

    print(
        "----------------------------------------"
    )

    for key in (
        "computer.active_window",
        "integration.weather.current",
        "integration.email.important",
        "missing.example",
    ):
        decision = evaluate_world_state(
            key
        )

        print(
            f"{key}: {decision.status.value} "
            f"(usable={decision.usable})"
        )
