"""
P.E.P.P.E.R. Proactive Models
Phase 16G.1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ProactiveCandidate:
    topic: str
    message: str
    urgency: int = 0
    dedupe_key: str = ""
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProactiveDecision:
    action: str
    reason: str
    candidate: ProactiveCandidate


@dataclass(frozen=True)
class ProactiveNotification:
    notification_id: str
    topic: str
    message: str
    urgency: int
    dedupe_key: str
    source: str
    created_at: str
    metadata: dict[str, Any]

    @classmethod
    def from_candidate(
        cls,
        candidate: ProactiveCandidate,
    ) -> "ProactiveNotification":
        return cls(
            notification_id=f"notice_{uuid4().hex}",
            topic=candidate.topic,
            message=candidate.message,
            urgency=candidate.urgency,
            dedupe_key=candidate.dedupe_key,
            source=candidate.source,
            created_at=utc_now_iso(),
            metadata=dict(candidate.metadata),
        )
