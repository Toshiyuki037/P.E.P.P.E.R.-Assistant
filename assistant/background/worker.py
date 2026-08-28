"""
P.E.P.P.E.R. Controlled Background Worker
Phase 16F.2 - 16F.6

Design:
- bounded worker pool
- explicit handler allow-list through registry
- persistent task lifecycle through Phase 16E
- no automatic retries
- no approval bypass
- no async rewrite
- duplicate in-flight task protection
- graceful shutdown
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import Event as ThreadEvent, RLock
from time import perf_counter
from typing import Any

from assistant.events import publish
from assistant.events.definitions import (
    BACKGROUND_JOB_FINISHED,
    BACKGROUND_JOB_STARTED,
    BACKGROUND_WORKER_STARTED,
    BACKGROUND_WORKER_STOPPED,
)
from assistant.executive import EXECUTIVE, TaskExecutive

from .registry import HANDLERS, BackgroundHandlerRegistry


@dataclass
class BackgroundJobResult:
    task_id: str
    success: bool
    elapsed_seconds: float
    value: Any = None
    error: str = ""


class BackgroundWorker:
    def __init__(
        self,
        *,
        executive: TaskExecutive = EXECUTIVE,
        registry: BackgroundHandlerRegistry = HANDLERS,
        max_workers: int = 4,
    ):
        self.executive = executive
        self.registry = registry
        self.max_workers = max(1, int(max_workers))
        self._executor: ThreadPoolExecutor | None = None
        self._lock = RLock()
        self._inflight: dict[str, Future] = {}
        self._stopping = ThreadEvent()

    @property
    def running(self) -> bool:
        with self._lock:
            return self._executor is not None and not self._stopping.is_set()

    def start(self) -> None:
        with self._lock:
            if self._executor is not None:
                return

            self._stopping.clear()
            self._executor = ThreadPoolExecutor(
                max_workers=self.max_workers,
                thread_name_prefix="pepper-background",
            )

        publish(
            BACKGROUND_WORKER_STARTED,
            {"max_workers": self.max_workers},
            source="assistant.background",
        )

    def stop(
        self,
        *,
        wait: bool = True,
        cancel_pending: bool = False,
    ) -> None:
        with self._lock:
            executor = self._executor
            if executor is None:
                return

            self._stopping.set()
            self._executor = None

        executor.shutdown(
            wait=wait,
            cancel_futures=cancel_pending,
        )

        with self._lock:
            self._inflight = {
                task_id: future
                for task_id, future in self._inflight.items()
                if not future.done()
            }

        publish(
            BACKGROUND_WORKER_STOPPED,
            {
                "waited": bool(wait),
                "cancel_pending": bool(cancel_pending),
            },
            source="assistant.background",
        )

    def _handler_name_for_task(self, task) -> str:
        metadata = dict(task.metadata or {})
        name = str(
            metadata.get("background_handler") or ""
        ).strip()
        if not name:
            raise ValueError(
                "Task has no metadata['background_handler']; "
                "background execution is not authorized for this task."
            )
        return name

    def _run_task(self, task_id: str) -> BackgroundJobResult:
        started = perf_counter()

        try:
            task = self.executive.get_task(task_id)
            if task is None:
                raise KeyError(f"Unknown task: {task_id}")

            if task.status not in {"pending", "blocked", "failed"}:
                raise RuntimeError(
                    f"Task is not runnable from status '{task.status}'."
                )

            handler_name = self._handler_name_for_task(task)
            handler = self.registry.get(handler_name)

            if handler is None:
                raise KeyError(
                    f"Unregistered background handler: {handler_name}"
                )

            running_task = self.executive.start_task(task_id)

            publish(
                BACKGROUND_JOB_STARTED,
                {
                    "task_id": task_id,
                    "handler": handler_name,
                },
                source="assistant.background",
            )

            value = handler(running_task)

            self.executive.complete_task(task_id)

            result = BackgroundJobResult(
                task_id=task_id,
                success=True,
                elapsed_seconds=perf_counter() - started,
                value=value,
            )

        except Exception as error:
            message = f"{type(error).__name__}: {error}"

            task = self.executive.get_task(task_id)
            if task is not None and task.status not in {
                "completed",
                "cancelled",
            }:
                try:
                    self.executive.fail_task(
                        task_id,
                        message,
                    )
                except Exception:
                    pass

            result = BackgroundJobResult(
                task_id=task_id,
                success=False,
                elapsed_seconds=perf_counter() - started,
                error=message,
            )

        publish(
            BACKGROUND_JOB_FINISHED,
            {
                "task_id": result.task_id,
                "success": result.success,
                "elapsed_seconds": result.elapsed_seconds,
                "error": result.error,
            },
            source="assistant.background",
        )

        return result

    def _cleanup(self, task_id: str, future: Future) -> None:
        with self._lock:
            current = self._inflight.get(task_id)
            if current is future:
                self._inflight.pop(task_id, None)

    def submit(self, task_id: str) -> Future:
        with self._lock:
            if self._executor is None or self._stopping.is_set():
                raise RuntimeError("Background worker is not running.")

            existing = self._inflight.get(str(task_id))
            if existing is not None and not existing.done():
                raise RuntimeError(
                    f"Task is already running in background: {task_id}"
                )

            task = self.executive.get_task(task_id)
            if task is None:
                raise KeyError(f"Unknown task: {task_id}")

            # Validate authorization before consuming a worker slot.
            handler_name = self._handler_name_for_task(task)
            if self.registry.get(handler_name) is None:
                raise KeyError(
                    f"Unregistered background handler: {handler_name}"
                )

            future = self._executor.submit(
                self._run_task,
                str(task_id),
            )
            self._inflight[str(task_id)] = future
            future.add_done_callback(
                lambda completed, tid=str(task_id):
                    self._cleanup(tid, completed)
            )
            return future

    def inflight_task_ids(self) -> list[str]:
        with self._lock:
            return sorted(
                task_id
                for task_id, future in self._inflight.items()
                if not future.done()
            )


BACKGROUND_WORKER = BackgroundWorker()
