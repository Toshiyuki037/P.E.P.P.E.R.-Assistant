"""
P.E.P.P.E.R. Executive Models
Phase 16E.1

Persistent goal/task records only.
No background execution is performed here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


@dataclass
class Goal:
    goal_id: str
    title: str
    description: str = ""
    status: str = "active"
    priority: int = 0
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    completed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        title: str,
        *,
        description: str = "",
        priority: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> "Goal":
        normalized = str(title or "").strip()
        if not normalized:
            raise ValueError("Goal title cannot be empty.")

        return cls(
            goal_id=new_id("goal"),
            title=normalized,
            description=str(description or "").strip(),
            priority=int(priority),
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Goal":
        return cls(**dict(payload))


@dataclass
class Task:
    task_id: str
    title: str
    description: str = ""
    goal_id: str | None = None
    status: str = "pending"
    priority: int = 0
    due_at: str | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    started_at: str | None = None
    completed_at: str | None = None
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        title: str,
        *,
        description: str = "",
        goal_id: str | None = None,
        priority: int = 0,
        due_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "Task":
        normalized = str(title or "").strip()
        if not normalized:
            raise ValueError("Task title cannot be empty.")

        return cls(
            task_id=new_id("task"),
            title=normalized,
            description=str(description or "").strip(),
            goal_id=(str(goal_id).strip() if goal_id else None),
            priority=int(priority),
            due_at=(str(due_at).strip() if due_at else None),
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Task":
        return cls(**dict(payload))
