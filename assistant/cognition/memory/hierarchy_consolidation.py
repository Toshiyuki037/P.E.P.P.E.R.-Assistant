"""
P.E.P.P.E.R. Phase 17B - Deterministic Memory Consolidation

No LLM loop. Consolidation performs bounded, explainable maintenance:
- expire temporary records
- collapse exact duplicate active records
- preserve explicit supersession chains
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .hierarchy_models import MemoryRecord
from .hierarchy_store import HIERARCHICAL_MEMORY_STORE, HierarchicalMemoryStore


def _norm(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _parse(value: str | None):
    if not value:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result


def consolidate_hierarchical_memory(
    *,
    store: HierarchicalMemoryStore = HIERARCHICAL_MEMORY_STORE,
    max_records: int = 500,
) -> dict[str, Any]:
    active = store.list(status="active", limit=max_records)
    now = datetime.now(timezone.utc)

    expired_ids = []
    duplicate_ids = []
    kept_ids = []
    seen = {}

    # Newest records arrive first from the store. Keep the newest exact fact.
    for record in active:
        expiry = _parse(record.expires_at)
        if expiry is not None and expiry <= now:
            store.set_status(record.memory_id, "expired")
            expired_ids.append(record.memory_id)
            continue

        duplicate_key = (
            _norm(record.content),
            record.layer,
            record.kind,
            _norm(record.subject or ""),
            _norm(record.project or ""),
        )

        prior = seen.get(duplicate_key)
        if prior is None:
            seen[duplicate_key] = record
            kept_ids.append(record.memory_id)
            continue

        # Duplicate is older because list() is ordered newest-first.
        store.set_status(
            record.memory_id,
            "superseded",
            superseded_by=prior.memory_id,
        )
        duplicate_ids.append(record.memory_id)

    return {
        "reviewed": len(active),
        "expired": expired_ids,
        "duplicates_superseded": duplicate_ids,
        "kept": kept_ids,
    }
