"""
P.E.P.P.E.R. Phase 17B - Hierarchical Memory Models

Pure deterministic schemas for layered memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from copy import deepcopy
import json


MEMORY_LAYERS = {
    "working",
    "recent_episodic",
    "project",
    "long_term_semantic",
    "relationship",
}

MEMORY_KINDS = {
    "fact",
    "assumption",
    "preference",
    "temporary",
    "decision",
    "goal",
    "commitment",
    "event",
}

MEMORY_STATUSES = {
    "active",
    "superseded",
    "expired",
    "forgotten",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def normalize_optional(value: Any) -> str | None:
    text = normalize_text(value)
    return text or None


def validate_timestamp(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    text = normalize_text(value)
    if not text:
        return None
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be ISO-8601") from exc
    return text


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    content: str
    layer: str
    kind: str = "fact"
    status: str = "active"
    category: str = "general"
    subject: str | None = None
    project: str | None = None
    source: str = "phase17b"
    confidence: float = 1.0
    importance: int = 50
    permanence: int = 50
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    last_accessed_at: str | None = None
    expires_at: str | None = None
    supersedes_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        memory_id = normalize_text(self.memory_id).lower()
        content = normalize_text(self.content)
        layer = normalize_text(self.layer).lower()
        kind = normalize_text(self.kind).lower()
        status = normalize_text(self.status).lower()
        category = normalize_text(self.category).lower() or "general"
        source = normalize_text(self.source) or "phase17b"

        if not memory_id:
            raise ValueError("memory_id is required")
        if not content:
            raise ValueError("content is required")
        if layer not in MEMORY_LAYERS:
            raise ValueError(f"invalid memory layer: {layer}")
        if kind not in MEMORY_KINDS:
            raise ValueError(f"invalid memory kind: {kind}")
        if status not in MEMORY_STATUSES:
            raise ValueError(f"invalid memory status: {status}")

        confidence = float(self.confidence)
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

        importance = int(self.importance)
        permanence = int(self.permanence)
        if not 0 <= importance <= 100:
            raise ValueError("importance must be between 0 and 100")
        if not 0 <= permanence <= 100:
            raise ValueError("permanence must be between 0 and 100")

        object.__setattr__(self, "memory_id", memory_id)
        object.__setattr__(self, "content", content)
        object.__setattr__(self, "layer", layer)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "subject", normalize_optional(self.subject))
        object.__setattr__(self, "project", normalize_optional(self.project))
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "importance", importance)
        object.__setattr__(self, "permanence", permanence)
        object.__setattr__(
            self,
            "created_at",
            validate_timestamp(self.created_at, "created_at") or utc_now_iso(),
        )
        object.__setattr__(
            self,
            "updated_at",
            validate_timestamp(self.updated_at, "updated_at") or utc_now_iso(),
        )
        object.__setattr__(
            self,
            "last_accessed_at",
            validate_timestamp(self.last_accessed_at, "last_accessed_at"),
        )
        object.__setattr__(
            self,
            "expires_at",
            validate_timestamp(self.expires_at, "expires_at"),
        )
        object.__setattr__(self, "supersedes_id", normalize_optional(self.supersedes_id))
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata or {})))

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "content": self.content,
            "layer": self.layer,
            "kind": self.kind,
            "status": self.status,
            "category": self.category,
            "subject": self.subject,
            "project": self.project,
            "source": self.source,
            "confidence": self.confidence,
            "importance": self.importance,
            "permanence": self.permanence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_accessed_at": self.last_accessed_at,
            "expires_at": self.expires_at,
            "supersedes_id": self.supersedes_id,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryRecord":
        return cls(**deepcopy(data))


@dataclass(frozen=True)
class MemoryQueryResult:
    record: MemoryRecord
    score: float
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = self.record.to_dict()
        payload["_memory_score"] = float(self.score)
        payload["_memory_reasons"] = list(self.reasons)
        return payload
