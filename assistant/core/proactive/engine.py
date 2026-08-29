"""
P.E.P.P.E.R. Proactive Engine
Phase 16G.3 - 16G.6

Consumes explicit candidates and selected Phase 16D events, applies policy,
and places surfaced notifications into a bounded in-memory inbox.

It does NOT speak by itself. Voice presentation remains a separate concern.
"""

from __future__ import annotations

from collections import deque
from threading import RLock
from typing import Callable

from assistant.core.events import EVENT_BUS, Event, publish
from assistant.core.events.definitions import (
    BACKGROUND_JOB_FINISHED,
    PROACTIVE_DEFERRED,
    PROACTIVE_SURFACED,
    PROACTIVE_SUPPRESSED,
)

from .models import (
    ProactiveCandidate,
    ProactiveDecision,
    ProactiveNotification,
)
from .policy import ProactivePolicy


CandidateBuilder = Callable[[Event], ProactiveCandidate | None]


class ProactiveEngine:
    def __init__(
        self,
        *,
        policy: ProactivePolicy | None = None,
        inbox_limit: int = 100,
    ):
        self.policy = policy or ProactivePolicy()
        self._lock = RLock()
        self._inbox = deque(
            maxlen=max(1, int(inbox_limit))
        )
        self._subscriptions: list[int] = []

    def consider(
        self,
        candidate: ProactiveCandidate,
    ) -> ProactiveDecision:
        decision = self.policy.evaluate(candidate)

        if decision.action == "surface":
            notification = (
                ProactiveNotification.from_candidate(
                    candidate
                )
            )

            with self._lock:
                self._inbox.append(notification)

            self.policy.mark_surfaced(candidate)

            publish(
                PROACTIVE_SURFACED,
                {
                    "notification_id":
                        notification.notification_id,
                    "topic": notification.topic,
                    "message": notification.message,
                    "urgency": notification.urgency,
                    "dedupe_key": notification.dedupe_key,
                    "source": notification.source,
                    "metadata": dict(notification.metadata),
                },
                source="assistant.proactive",
            )

        elif decision.action == "defer":
            publish(
                PROACTIVE_DEFERRED,
                {
                    "topic": candidate.topic,
                    "message": candidate.message,
                    "urgency": candidate.urgency,
                    "dedupe_key": candidate.dedupe_key,
                    "reason": decision.reason,
                },
                source="assistant.proactive",
            )

        else:
            publish(
                PROACTIVE_SUPPRESSED,
                {
                    "topic": candidate.topic,
                    "urgency": candidate.urgency,
                    "dedupe_key": candidate.dedupe_key,
                    "reason": decision.reason,
                },
                source="assistant.proactive",
            )

        return decision

    def pending(self) -> list[ProactiveNotification]:
        with self._lock:
            return list(self._inbox)

    def pop_next(self) -> ProactiveNotification | None:
        with self._lock:
            if not self._inbox:
                return None
            return self._inbox.popleft()

    def clear(self) -> None:
        with self._lock:
            self._inbox.clear()

    def subscribe(
        self,
        topic: str,
        builder: CandidateBuilder,
    ) -> int:
        def handler(event: Event):
            candidate = builder(event)
            if candidate is not None:
                self.consider(candidate)

        token = EVENT_BUS.subscribe(
            topic,
            handler,
        )
        self._subscriptions.append(token)
        return token

    def unsubscribe_all(self) -> None:
        for token in self._subscriptions:
            EVENT_BUS.unsubscribe(token)
        self._subscriptions.clear()

    def install_default_subscriptions(self) -> None:
        if self._subscriptions:
            return

        self.subscribe(
            BACKGROUND_JOB_FINISHED,
            self._background_failure_candidate,
        )

    @staticmethod
    def _background_failure_candidate(
        event: Event,
    ) -> ProactiveCandidate | None:
        payload = dict(event.payload or {})

        if payload.get("success") is not False:
            return None

        task_id = str(
            payload.get("task_id") or ""
        ).strip()
        error = str(
            payload.get("error") or "unknown error"
        ).strip()

        return ProactiveCandidate(
            topic="background.task_failed",
            message=(
                f"A background task failed: {error}"
            ),
            urgency=7,
            dedupe_key=(
                f"background.task_failed:{task_id}"
                if task_id
                else "background.task_failed"
            ),
            source="assistant.background",
            metadata={
                "task_id": task_id,
                "error": error,
            },
        )


PROACTIVE_ENGINE = ProactiveEngine()
