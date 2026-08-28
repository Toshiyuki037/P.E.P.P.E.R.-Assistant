"""
P.E.P.P.E.R. - World State Core

Phase 16B.1

Purpose:
    Provides P.E.P.P.E.R.'s generalized in-memory operational state store.

This is the shared "RAM" layer for live state such as:
    - current location
    - computer / workspace state
    - system health
    - integration snapshots
    - active tasks and future executive state

Important:
    - This module does not collect any state by itself.
    - Existing subsystems remain the authoritative producers.
    - State is in-memory by default.
    - Persistence belongs to individual producers only when appropriate.
    - Reads and writes are thread-safe.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------

def _utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _parse_datetime(
    value: str,
) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            value
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed


# ---------------------------------------------------------------------------
# State Record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WorldStateRecord:
    """
    One named item in P.E.P.P.E.R.'s live operational state.

    key:
        Stable dotted identifier such as:
            location.current
            computer.active_window
            workspace.active
            system.health
            weather.current

    value:
        Structured producer-owned state.

    source:
        Subsystem that produced the value.

    updated_at:
        UTC ISO timestamp for when the value was published.

    fresh_for_seconds:
        Optional freshness policy.
        None means the record has no automatic freshness deadline.

    confidence:
        Producer-reported confidence from 0.0 to 1.0.

    metadata:
        Optional structured details such as provider/account/capability.
    """

    key: str
    value: Any
    source: str
    updated_at: str

    fresh_for_seconds: float | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] | None = None

    @property
    def age_seconds(self) -> float:
        updated = _parse_datetime(
            self.updated_at
        )

        if updated is None:
            return float("inf")

        return max(
            0.0,
            (
                _utc_now()
                - updated
            ).total_seconds(),
        )

    @property
    def is_fresh(self) -> bool:
        if self.fresh_for_seconds is None:
            return True

        return (
            self.age_seconds
            <= float(
                self.fresh_for_seconds
            )
        )

    @property
    def is_stale(self) -> bool:
        return not self.is_fresh

    def to_dict(self) -> dict[str, Any]:
        data = asdict(
            self
        )

        data["age_seconds"] = (
            self.age_seconds
        )

        data["is_fresh"] = (
            self.is_fresh
        )

        return data


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class WorldStateStore:
    """
    Thread-safe in-memory store for live P.E.P.P.E.R. state.

    This class deliberately contains no collectors, providers, disk I/O,
    or reasoning logic. It is only the common state contract.
    """

    def __init__(self):
        self._lock = RLock()
        self._records: dict[
            str,
            WorldStateRecord,
        ] = {}

    @staticmethod
    def _normalize_key(
        key: str,
    ) -> str:
        normalized = (
            str(
                key
                or ""
            )
            .strip()
            .lower()
        )

        if not normalized:
            raise ValueError(
                "World-state key cannot be empty."
            )

        return normalized

    @staticmethod
    def _normalize_confidence(
        confidence: float,
    ) -> float:
        value = float(
            confidence
        )

        if not (
            0.0
            <= value
            <= 1.0
        ):
            raise ValueError(
                "World-state confidence must be between 0.0 and 1.0."
            )

        return value

    @staticmethod
    def _normalize_freshness(
        fresh_for_seconds: float | None,
    ) -> float | None:
        if fresh_for_seconds is None:
            return None

        value = float(
            fresh_for_seconds
        )

        if value < 0:
            raise ValueError(
                "fresh_for_seconds cannot be negative."
            )

        return value

    def set(
        self,
        key: str,
        value: Any,
        *,
        source: str,
        fresh_for_seconds: float | None = None,
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
        updated_at: str | None = None,
    ) -> WorldStateRecord:
        normalized_key = (
            self._normalize_key(
                key
            )
        )

        normalized_source = (
            str(
                source
                or ""
            )
            .strip()
        )

        if not normalized_source:
            raise ValueError(
                "World-state source cannot be empty."
            )

        record = WorldStateRecord(
            key=normalized_key,
            value=deepcopy(
                value
            ),
            source=normalized_source,
            updated_at=(
                str(
                    updated_at
                    or _utc_now_iso()
                )
            ),
            fresh_for_seconds=(
                self._normalize_freshness(
                    fresh_for_seconds
                )
            ),
            confidence=(
                self._normalize_confidence(
                    confidence
                )
            ),
            metadata=(
                deepcopy(
                    metadata
                )
                if metadata is not None
                else {}
            ),
        )

        with self._lock:
            self._records[
                normalized_key
            ] = record

        return deepcopy(
            record
        )

    def get(
        self,
        key: str,
        *,
        require_fresh: bool = False,
    ) -> WorldStateRecord | None:
        normalized_key = (
            self._normalize_key(
                key
            )
        )

        with self._lock:
            record = (
                self._records.get(
                    normalized_key
                )
            )

            if record is None:
                return None

            result = deepcopy(
                record
            )

        if (
            require_fresh
            and result.is_stale
        ):
            return None

        return result

    def get_value(
        self,
        key: str,
        *,
        require_fresh: bool = False,
        default: Any = None,
    ) -> Any:
        record = self.get(
            key,
            require_fresh=require_fresh,
        )

        if record is None:
            return deepcopy(
                default
            )

        return deepcopy(
            record.value
        )

    def contains(
        self,
        key: str,
        *,
        require_fresh: bool = False,
    ) -> bool:
        return (
            self.get(
                key,
                require_fresh=require_fresh,
            )
            is not None
        )

    def delete(
        self,
        key: str,
    ) -> bool:
        normalized_key = (
            self._normalize_key(
                key
            )
        )

        with self._lock:
            return (
                self._records.pop(
                    normalized_key,
                    None,
                )
                is not None
            )

    def clear(
        self,
    ) -> None:
        with self._lock:
            self._records.clear()

    def keys(
        self,
        *,
        prefix: str = "",
    ) -> list[str]:
        normalized_prefix = (
            str(
                prefix
                or ""
            )
            .strip()
            .lower()
        )

        with self._lock:
            keys = list(
                self._records.keys()
            )

        if normalized_prefix:
            keys = [
                key
                for key in keys
                if key.startswith(
                    normalized_prefix
                )
            ]

        return sorted(
            keys
        )

    def snapshot(
        self,
        *,
        prefix: str = "",
        include_stale: bool = True,
    ) -> dict[str, WorldStateRecord]:
        normalized_prefix = (
            str(
                prefix
                or ""
            )
            .strip()
            .lower()
        )

        with self._lock:
            records = {
                key:
                    deepcopy(
                        record
                    )
                for key, record
                in self._records.items()
            }

        if normalized_prefix:
            records = {
                key:
                    record
                for key, record
                in records.items()
                if key.startswith(
                    normalized_prefix
                )
            }

        if not include_stale:
            records = {
                key:
                    record
                for key, record
                in records.items()
                if record.is_fresh
            }

        return dict(
            sorted(
                records.items()
            )
        )

    def snapshot_dict(
        self,
        *,
        prefix: str = "",
        include_stale: bool = True,
    ) -> dict[str, dict[str, Any]]:
        return {
            key:
                record.to_dict()
            for key, record
            in self.snapshot(
                prefix=prefix,
                include_stale=include_stale,
            ).items()
        }


# ---------------------------------------------------------------------------
# Shared Runtime Store
# ---------------------------------------------------------------------------

WORLD_STATE = WorldStateStore()


# ---------------------------------------------------------------------------
# Convenience API
# ---------------------------------------------------------------------------

def set_world_state(
    key: str,
    value: Any,
    *,
    source: str,
    fresh_for_seconds: float | None = None,
    confidence: float = 1.0,
    metadata: dict[str, Any] | None = None,
    updated_at: str | None = None,
) -> WorldStateRecord:
    return WORLD_STATE.set(
        key,
        value,
        source=source,
        fresh_for_seconds=fresh_for_seconds,
        confidence=confidence,
        metadata=metadata,
        updated_at=updated_at,
    )


def get_world_state(
    key: str,
    *,
    require_fresh: bool = False,
) -> WorldStateRecord | None:
    return WORLD_STATE.get(
        key,
        require_fresh=require_fresh,
    )


def get_world_state_value(
    key: str,
    *,
    require_fresh: bool = False,
    default: Any = None,
) -> Any:
    return WORLD_STATE.get_value(
        key,
        require_fresh=require_fresh,
        default=default,
    )


def delete_world_state(
    key: str,
) -> bool:
    return WORLD_STATE.delete(
        key
    )


def clear_world_state() -> None:
    WORLD_STATE.clear()


def get_world_state_snapshot(
    *,
    prefix: str = "",
    include_stale: bool = True,
) -> dict[str, WorldStateRecord]:
    return WORLD_STATE.snapshot(
        prefix=prefix,
        include_stale=include_stale,
    )


def get_world_state_snapshot_dict(
    *,
    prefix: str = "",
    include_stale: bool = True,
) -> dict[str, dict[str, Any]]:
    return WORLD_STATE.snapshot_dict(
        prefix=prefix,
        include_stale=include_stale,
    )


# ---------------------------------------------------------------------------
# Standalone Diagnostic
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    set_world_state(
        "system.example",
        {
            "status":
                "healthy",
        },
        source="phase16b_diagnostic",
        fresh_for_seconds=60,
        confidence=1.0,
    )

    record = get_world_state(
        "system.example",
        require_fresh=True,
    )

    print(
        "P.E.P.P.E.R. World State Core"
    )

    print(
        "-----------------------------"
    )

    print(
        (
            record.to_dict()
            if record is not None
            else "No record."
        )
    )
