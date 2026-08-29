"""
P.E.P.P.E.R. Task Executive
Phase 16E.3 - 16E.6

Provides persistent goal/task lifecycle operations and emits Phase 16D events.

Important:
- This module does NOT run tasks in the background.
- It does NOT retry tools.
- It does NOT bypass approval.
- Phase 16F will add controlled background execution.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from assistant.core.events import publish
from assistant.core.events.definitions import (
    GOAL_COMPLETED,
    GOAL_CREATED,
    GOAL_UPDATED,
    TASK_CANCELLED,
    TASK_COMPLETED,
    TASK_CREATED,
    TASK_FAILED,
    TASK_STARTED,
    TASK_UPDATED,
)

from .models import Goal, Task, utc_now_iso
from .store import DEFAULT_STATE_PATH, ExecutiveStore


GOAL_STATUSES = frozenset({
    "active",
    "completed",
    "cancelled",
})

TASK_STATUSES = frozenset({
    "pending",
    "running",
    "blocked",
    "completed",
    "failed",
    "cancelled",
})


class TaskExecutive:
    def __init__(
        self,
        path: str | Path = DEFAULT_STATE_PATH,
    ):
        self.store = ExecutiveStore(path)
        self._lock = RLock()

    @staticmethod
    def _event_payload(record) -> dict[str, Any]:
        return record.to_dict()

    def create_goal(
        self,
        title: str,
        *,
        description: str = "",
        priority: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> Goal:
        goal = Goal.create(
            title,
            description=description,
            priority=priority,
            metadata=metadata,
        )
        saved = self.store.put_goal(goal)

        publish(
            GOAL_CREATED,
            self._event_payload(saved),
            source="assistant.core.executive",
        )

        return saved

    def update_goal(
        self,
        goal_id: str,
        **changes,
    ) -> Goal:
        with self._lock:
            goal = self.store.get_goal(goal_id)
            if goal is None:
                raise KeyError(f"Unknown goal: {goal_id}")

            allowed = {
                "title",
                "description",
                "priority",
                "metadata",
                "status",
            }

            unknown = set(changes) - allowed
            if unknown:
                raise ValueError(
                    f"Unsupported goal fields: {sorted(unknown)}"
                )

            if "title" in changes:
                title = str(changes["title"] or "").strip()
                if not title:
                    raise ValueError("Goal title cannot be empty.")
                goal.title = title

            if "description" in changes:
                goal.description = str(
                    changes["description"] or ""
                ).strip()

            if "priority" in changes:
                goal.priority = int(changes["priority"])

            if "metadata" in changes:
                goal.metadata = dict(
                    changes["metadata"] or {}
                )

            if "status" in changes:
                status = str(
                    changes["status"]
                ).strip().lower()
                if status not in GOAL_STATUSES:
                    raise ValueError(
                        f"Invalid goal status: {status}"
                    )
                goal.status = status
                goal.completed_at = (
                    utc_now_iso()
                    if status == "completed"
                    else None
                )

            goal.updated_at = utc_now_iso()
            saved = self.store.put_goal(goal)

        publish(
            GOAL_UPDATED,
            self._event_payload(saved),
            source="assistant.core.executive",
        )

        if saved.status == "completed":
            publish(
                GOAL_COMPLETED,
                self._event_payload(saved),
                source="assistant.core.executive",
            )

        return saved

    def complete_goal(
        self,
        goal_id: str,
    ) -> Goal:
        return self.update_goal(
            goal_id,
            status="completed",
        )

    def create_task(
        self,
        title: str,
        *,
        description: str = "",
        goal_id: str | None = None,
        priority: int = 0,
        due_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        if goal_id is not None:
            goal = self.store.get_goal(goal_id)
            if goal is None:
                raise KeyError(
                    f"Cannot attach task to unknown goal: {goal_id}"
                )

        task = Task.create(
            title,
            description=description,
            goal_id=goal_id,
            priority=priority,
            due_at=due_at,
            metadata=metadata,
        )
        saved = self.store.put_task(task)

        publish(
            TASK_CREATED,
            self._event_payload(saved),
            source="assistant.core.executive",
        )

        return saved

    def update_task(
        self,
        task_id: str,
        **changes,
    ) -> Task:
        with self._lock:
            task = self.store.get_task(task_id)
            if task is None:
                raise KeyError(f"Unknown task: {task_id}")

            allowed = {
                "title",
                "description",
                "goal_id",
                "priority",
                "due_at",
                "metadata",
                "status",
                "error",
            }

            unknown = set(changes) - allowed
            if unknown:
                raise ValueError(
                    f"Unsupported task fields: {sorted(unknown)}"
                )

            if "title" in changes:
                title = str(changes["title"] or "").strip()
                if not title:
                    raise ValueError("Task title cannot be empty.")
                task.title = title

            if "description" in changes:
                task.description = str(
                    changes["description"] or ""
                ).strip()

            if "goal_id" in changes:
                goal_id = changes["goal_id"]
                if goal_id is not None:
                    goal = self.store.get_goal(goal_id)
                    if goal is None:
                        raise KeyError(
                            f"Cannot attach task to unknown goal: {goal_id}"
                        )
                    task.goal_id = str(goal_id)
                else:
                    task.goal_id = None

            if "priority" in changes:
                task.priority = int(changes["priority"])

            if "due_at" in changes:
                task.due_at = (
                    str(changes["due_at"]).strip()
                    if changes["due_at"]
                    else None
                )

            if "metadata" in changes:
                task.metadata = dict(
                    changes["metadata"] or {}
                )

            if "error" in changes:
                task.error = str(
                    changes["error"] or ""
                )

            if "status" in changes:
                status = str(
                    changes["status"]
                ).strip().lower()

                if status not in TASK_STATUSES:
                    raise ValueError(
                        f"Invalid task status: {status}"
                    )

                task.status = status

                if status == "running" and task.started_at is None:
                    task.started_at = utc_now_iso()

                if status == "completed":
                    task.completed_at = utc_now_iso()
                    task.error = ""

                elif status in {
                    "pending",
                    "running",
                    "blocked",
                }:
                    task.completed_at = None

            task.updated_at = utc_now_iso()
            saved = self.store.put_task(task)

        publish(
            TASK_UPDATED,
            self._event_payload(saved),
            source="assistant.core.executive",
        )

        topic = {
            "running": TASK_STARTED,
            "completed": TASK_COMPLETED,
            "failed": TASK_FAILED,
            "cancelled": TASK_CANCELLED,
        }.get(saved.status)

        if topic:
            publish(
                topic,
                self._event_payload(saved),
                source="assistant.core.executive",
            )

        return saved

    def start_task(
        self,
        task_id: str,
    ) -> Task:
        return self.update_task(
            task_id,
            status="running",
        )

    def complete_task(
        self,
        task_id: str,
    ) -> Task:
        return self.update_task(
            task_id,
            status="completed",
            error="",
        )

    def fail_task(
        self,
        task_id: str,
        error: str,
    ) -> Task:
        return self.update_task(
            task_id,
            status="failed",
            error=str(error or ""),
        )

    def cancel_task(
        self,
        task_id: str,
    ) -> Task:
        return self.update_task(
            task_id,
            status="cancelled",
        )

    def block_task(
        self,
        task_id: str,
        reason: str = "",
    ) -> Task:
        return self.update_task(
            task_id,
            status="blocked",
            error=str(reason or ""),
        )

    def get_goal(
        self,
        goal_id: str,
    ) -> Goal | None:
        return self.store.get_goal(goal_id)

    def get_task(
        self,
        task_id: str,
    ) -> Task | None:
        return self.store.get_task(task_id)

    def list_goals(
        self,
        *,
        status: str | None = None,
    ) -> list[Goal]:
        return self.store.list_goals(
            status=status,
        )

    def list_tasks(
        self,
        *,
        status: str | None = None,
        goal_id: str | None = None,
    ) -> list[Task]:
        return self.store.list_tasks(
            status=status,
            goal_id=goal_id,
        )


EXECUTIVE = TaskExecutive()
