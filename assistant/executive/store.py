"""
P.E.P.P.E.R. Persistent Executive Store
Phase 16E.2

Thread-safe persistent storage for goals and tasks.

Persistence:
    runtime/executive/state.json

Writes use a temporary file + os.replace for atomic replacement.
The store does not execute tasks; Phase 16F will add background execution.
"""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
from threading import RLock
from typing import Any

from .models import Goal, Task


DEFAULT_STATE_PATH = Path("runtime/executive/state.json")


class ExecutiveStore:
    def __init__(self, path: str | Path = DEFAULT_STATE_PATH):
        self.path = Path(path)
        self._lock = RLock()
        self._goals: dict[str, Goal] = {}
        self._tasks: dict[str, Task] = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self.path.exists():
                return

            raw = json.loads(
                self.path.read_text(encoding="utf-8")
            )

            self._goals = {
                item["goal_id"]: Goal.from_dict(item)
                for item in raw.get("goals", [])
            }
            self._tasks = {
                item["task_id"]: Task.from_dict(item)
                for item in raw.get("tasks", [])
            }

    def _snapshot_unlocked(self) -> dict[str, Any]:
        return {
            "version": 1,
            "goals": [
                goal.to_dict()
                for goal in self._goals.values()
            ],
            "tasks": [
                task.to_dict()
                for task in self._tasks.values()
            ],
        }

    def _persist_unlocked(self) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = self._snapshot_unlocked()
        temporary = self.path.with_suffix(
            self.path.suffix + ".tmp"
        )

        temporary.write_text(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        os.replace(
            temporary,
            self.path,
        )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(
                self._snapshot_unlocked()
            )

    def get_goal(self, goal_id: str) -> Goal | None:
        with self._lock:
            goal = self._goals.get(str(goal_id))
            return deepcopy(goal) if goal else None

    def get_task(self, task_id: str) -> Task | None:
        with self._lock:
            task = self._tasks.get(str(task_id))
            return deepcopy(task) if task else None

    def list_goals(
        self,
        *,
        status: str | None = None,
    ) -> list[Goal]:
        with self._lock:
            values = list(self._goals.values())

        if status is not None:
            normalized = str(status).strip().lower()
            values = [
                item
                for item in values
                if item.status.lower() == normalized
            ]

        values.sort(
            key=lambda item: (
                -item.priority,
                item.created_at,
                item.goal_id,
            )
        )

        return deepcopy(values)

    def list_tasks(
        self,
        *,
        status: str | None = None,
        goal_id: str | None = None,
    ) -> list[Task]:
        with self._lock:
            values = list(self._tasks.values())

        if status is not None:
            normalized = str(status).strip().lower()
            values = [
                item
                for item in values
                if item.status.lower() == normalized
            ]

        if goal_id is not None:
            normalized_goal_id = str(goal_id)
            values = [
                item
                for item in values
                if item.goal_id == normalized_goal_id
            ]

        values.sort(
            key=lambda item: (
                -item.priority,
                item.created_at,
                item.task_id,
            )
        )

        return deepcopy(values)

    def put_goal(self, goal: Goal) -> Goal:
        with self._lock:
            self._goals[goal.goal_id] = deepcopy(goal)
            self._persist_unlocked()
            return deepcopy(goal)

    def put_task(self, task: Task) -> Task:
        with self._lock:
            self._tasks[task.task_id] = deepcopy(task)
            self._persist_unlocked()
            return deepcopy(task)

    def delete_goal(self, goal_id: str) -> bool:
        with self._lock:
            if str(goal_id) not in self._goals:
                return False
            self._goals.pop(str(goal_id), None)
            self._persist_unlocked()
            return True

    def delete_task(self, task_id: str) -> bool:
        with self._lock:
            if str(task_id) not in self._tasks:
                return False
            self._tasks.pop(str(task_id), None)
            self._persist_unlocked()
            return True

    def clear(self) -> None:
        with self._lock:
            self._goals.clear()
            self._tasks.clear()
            self._persist_unlocked()
