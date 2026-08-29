"""
P.E.P.P.E.R. Event Bus
Phase 16D.1 / 16D.6

Small synchronous, thread-safe publish/subscribe primitive.

Properties:
- deterministic subscriber order
- exact-topic and wildcard subscriptions
- exception isolation
- unsubscribe support
- recursion/event-loop protection
- no background worker and no async architecture rewrite
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import count
from threading import RLock, local
from time import perf_counter
from typing import Any, Callable
from uuid import uuid4


EventHandler = Callable[["Event"], Any]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Event:
    topic: str
    payload: Any = None
    source: str = ""
    event_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=_utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Subscription:
    token: int
    topic: str
    handler: EventHandler


@dataclass
class HandlerResult:
    token: int
    topic: str
    success: bool
    elapsed_seconds: float
    error: str = ""


@dataclass
class PublishReport:
    event: Event
    delivered: int
    succeeded: int
    failed: int
    blocked: bool = False
    block_reason: str = ""
    handler_results: list[HandlerResult] = field(default_factory=list)


class EventBus:
    def __init__(self, *, max_publish_depth: int = 16):
        self._lock = RLock()
        self._subscriptions: dict[str, list[Subscription]] = {}
        self._tokens = count(1)
        self._local = local()
        self.max_publish_depth = max(1, int(max_publish_depth))

    @staticmethod
    def _normalize_topic(topic: str) -> str:
        value = str(topic or "").strip().lower()
        if not value:
            raise ValueError("Event topic cannot be empty.")
        return value

    def subscribe(self, topic: str, handler: EventHandler) -> int:
        normalized = self._normalize_topic(topic)
        if not callable(handler):
            raise TypeError("Event handler must be callable.")

        subscription = Subscription(
            token=next(self._tokens),
            topic=normalized,
            handler=handler,
        )

        with self._lock:
            self._subscriptions.setdefault(normalized, []).append(subscription)

        return subscription.token

    def unsubscribe(self, token: int) -> bool:
        with self._lock:
            for topic, subscriptions in list(self._subscriptions.items()):
                for index, subscription in enumerate(subscriptions):
                    if subscription.token == token:
                        del subscriptions[index]
                        if not subscriptions:
                            self._subscriptions.pop(topic, None)
                        return True
        return False

    def clear(self) -> None:
        with self._lock:
            self._subscriptions.clear()

    def subscriber_count(self, topic: str | None = None) -> int:
        with self._lock:
            if topic is None:
                return sum(len(items) for items in self._subscriptions.values())
            normalized = self._normalize_topic(topic)
            return len(self._subscriptions.get(normalized, []))

    def _matching_subscriptions(self, topic: str) -> list[Subscription]:
        with self._lock:
            exact = list(self._subscriptions.get(topic, []))
            wildcard = list(self._subscriptions.get("*", []))
        return exact + wildcard

    def _depth(self) -> int:
        return int(getattr(self._local, "publish_depth", 0))

    def publish(
        self,
        topic: str | Event,
        payload: Any = None,
        *,
        source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> PublishReport:
        if isinstance(topic, Event):
            event = topic
            normalized = self._normalize_topic(event.topic)
            if normalized != event.topic:
                event = Event(
                    topic=normalized,
                    payload=event.payload,
                    source=event.source,
                    event_id=event.event_id,
                    created_at=event.created_at,
                    metadata=dict(event.metadata),
                )
        else:
            event = Event(
                topic=self._normalize_topic(topic),
                payload=payload,
                source=str(source or "").strip(),
                metadata=dict(metadata or {}),
            )

        depth = self._depth()
        if depth >= self.max_publish_depth:
            return PublishReport(
                event=event,
                delivered=0,
                succeeded=0,
                failed=0,
                blocked=True,
                block_reason=f"max publish depth {self.max_publish_depth} reached",
            )

        subscriptions = self._matching_subscriptions(event.topic)
        results: list[HandlerResult] = []

        self._local.publish_depth = depth + 1
        try:
            for subscription in subscriptions:
                started = perf_counter()
                try:
                    subscription.handler(event)
                    results.append(
                        HandlerResult(
                            token=subscription.token,
                            topic=subscription.topic,
                            success=True,
                            elapsed_seconds=perf_counter() - started,
                        )
                    )
                except Exception as error:
                    results.append(
                        HandlerResult(
                            token=subscription.token,
                            topic=subscription.topic,
                            success=False,
                            elapsed_seconds=perf_counter() - started,
                            error=f"{type(error).__name__}: {error}",
                        )
                    )
        finally:
            self._local.publish_depth = depth

        succeeded = sum(1 for result in results if result.success)
        return PublishReport(
            event=event,
            delivered=len(results),
            succeeded=succeeded,
            failed=len(results) - succeeded,
            handler_results=results,
        )


EVENT_BUS = EventBus()


def subscribe(topic: str, handler: EventHandler) -> int:
    return EVENT_BUS.subscribe(topic, handler)


def unsubscribe(token: int) -> bool:
    return EVENT_BUS.unsubscribe(token)


def publish(
    topic: str | Event,
    payload: Any = None,
    *,
    source: str = "",
    metadata: dict[str, Any] | None = None,
) -> PublishReport:
    return EVENT_BUS.publish(
        topic,
        payload,
        source=source,
        metadata=metadata,
    )
