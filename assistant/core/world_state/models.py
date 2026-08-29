"""
P.E.P.P.E.R. - Unified World Model Records
Phase 17A.1

Deterministic schema only. No perception, persistence, LLM, or runtime wiring.
Phase 16 world state remains authoritative for atomic live observations.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any, name: str, *, lower: bool = False) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError(f"{name} cannot be empty.")
    return value.lower() if lower else value


def _confidence(value: float) -> float:
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError("confidence must be between 0.0 and 1.0.")
    return value


def _timestamp(value: str | None, name: str) -> str:
    value = str(value or utc_now_iso()).strip()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO-8601 timestamp.") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _mapping(value: dict[str, Any] | None, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dictionary.")
    return deepcopy(value)


@dataclass(frozen=True)
class WorldEvidence:
    world_state_key: str
    source: str
    status: str
    confidence: float = 1.0
    observed_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "world_state_key", _text(self.world_state_key, "world_state_key", lower=True))
        object.__setattr__(self, "source", _text(self.source, "source"))
        object.__setattr__(self, "status", _text(self.status, "status", lower=True))
        object.__setattr__(self, "confidence", _confidence(self.confidence))
        object.__setattr__(self, "observed_at", _timestamp(self.observed_at, "observed_at"))
        object.__setattr__(self, "metadata", _mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "world_state_key": self.world_state_key,
            "source": self.source,
            "status": self.status,
            "confidence": self.confidence,
            "observed_at": self.observed_at,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorldEvidence":
        if not isinstance(payload, dict):
            raise TypeError("WorldEvidence payload must be a dictionary.")
        return cls(**deepcopy(payload))


def _evidence(items) -> tuple[WorldEvidence, ...]:
    result = []
    for item in items or ():
        if isinstance(item, WorldEvidence):
            result.append(item)
        elif isinstance(item, dict):
            result.append(WorldEvidence.from_dict(item))
        else:
            raise TypeError("evidence items must be WorldEvidence or dictionaries.")
    return tuple(result)


@dataclass(frozen=True)
class WorldEntity:
    entity_id: str
    entity_type: str
    name: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    observed_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    evidence: tuple[WorldEvidence, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "entity_id", _text(self.entity_id, "entity_id", lower=True))
        object.__setattr__(self, "entity_type", _text(self.entity_type, "entity_type", lower=True))
        object.__setattr__(self, "name", str(self.name or "").strip())
        object.__setattr__(self, "attributes", _mapping(self.attributes, "attributes"))
        object.__setattr__(self, "confidence", _confidence(self.confidence))
        object.__setattr__(self, "observed_at", _timestamp(self.observed_at, "observed_at"))
        object.__setattr__(self, "updated_at", _timestamp(self.updated_at, "updated_at"))
        object.__setattr__(self, "evidence", _evidence(self.evidence))
        object.__setattr__(self, "metadata", _mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "name": self.name,
            "attributes": deepcopy(self.attributes),
            "confidence": self.confidence,
            "observed_at": self.observed_at,
            "updated_at": self.updated_at,
            "evidence": [item.to_dict() for item in self.evidence],
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorldEntity":
        if not isinstance(payload, dict):
            raise TypeError("WorldEntity payload must be a dictionary.")
        data = deepcopy(payload)
        data["evidence"] = _evidence(data.get("evidence", ()))
        return cls(**data)


@dataclass(frozen=True)
class WorldRelation:
    relation_id: str
    subject_id: str
    predicate: str
    object_id: str
    confidence: float = 1.0
    observed_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    evidence: tuple[WorldEvidence, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "relation_id", _text(self.relation_id, "relation_id", lower=True))
        object.__setattr__(self, "subject_id", _text(self.subject_id, "subject_id", lower=True))
        object.__setattr__(self, "predicate", _text(self.predicate, "predicate", lower=True).replace(" ", "_"))
        object.__setattr__(self, "object_id", _text(self.object_id, "object_id", lower=True))
        object.__setattr__(self, "confidence", _confidence(self.confidence))
        object.__setattr__(self, "observed_at", _timestamp(self.observed_at, "observed_at"))
        object.__setattr__(self, "updated_at", _timestamp(self.updated_at, "updated_at"))
        object.__setattr__(self, "evidence", _evidence(self.evidence))
        object.__setattr__(self, "metadata", _mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "subject_id": self.subject_id,
            "predicate": self.predicate,
            "object_id": self.object_id,
            "confidence": self.confidence,
            "observed_at": self.observed_at,
            "updated_at": self.updated_at,
            "evidence": [item.to_dict() for item in self.evidence],
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "WorldRelation":
        if not isinstance(payload, dict):
            raise TypeError("WorldRelation payload must be a dictionary.")
        data = deepcopy(payload)
        data["evidence"] = _evidence(data.get("evidence", ()))
        return cls(**data)


__all__ = ["WorldEntity", "WorldEvidence", "WorldRelation", "utc_now_iso"]
