"""
P.E.P.P.E.R. - Unified World Model Runtime Bridge

Phase 17A.7

Connects the existing Phase 16 world-state event stream to the Phase 17 unified
world model without adding another collector or changing producer behavior.

Important:
    - Existing WORLD_STATE remains authoritative operational RAM.
    - Existing EventBus remains authoritative event transport.
    - The bridge rebuilds from the authoritative snapshot on relevant changes.
    - No LLM calls.
    - No provider/perception calls.
    - No persistence.
    - Start/stop are explicit and idempotent.
"""

from __future__ import annotations

from threading import RLock
from typing import Any

from assistant.core.events import (
    subscribe,
    unsubscribe,
)
from assistant.core.events.definitions import (
    WORLD_STATE_CHANGED,
    WORLD_STATE_DELETED,
    WORLD_STATE_CLEARED,
)

from .core import (
    get_world_state_snapshot,
)
from .model import (
    WORLD_MODEL,
    WorldModelStore,
)
from .projection import (
    project_world_state_snapshot,
)
from .reconciliation import (
    reconcile_world_model_candidates,
)
from .temporal import (
    WorldModelChange,
    WorldModelChangeTracker,
)


class WorldModelRuntimeBridge:
    """
    Synchronous event-driven bridge from operational RAM to unified model.

    Rebuilding from the authoritative RAM snapshot is intentional in 17A.7:
    world-state is small, the event bus is synchronous, and snapshot rebuilds
    make deletion/clear semantics correct without maintaining a second shadow
    source-of-truth.
    """

    def __init__(
        self,
        *,
        store: WorldModelStore = WORLD_MODEL,
        change_tracker: WorldModelChangeTracker | None = None,
    ):
        self.store = store
        self.change_tracker = (
            change_tracker
            if change_tracker is not None
            else WorldModelChangeTracker()
        )

        self._lock = RLock()
        self._tokens: list[int] = []
        self._running = False
        self._last_changes: list[
            WorldModelChange
        ] = []

    @property
    def running(
        self,
    ) -> bool:
        with self._lock:
            return self._running

    def subscription_tokens(
        self,
    ) -> tuple[int, ...]:
        with self._lock:
            return tuple(
                self._tokens
            )

    def last_changes(
        self,
    ) -> list[
        WorldModelChange
    ]:
        with self._lock:
            return [
                WorldModelChange(
                    change_type=item.change_type,
                    record_id=item.record_id,
                    record_kind=item.record_kind,
                    detected_at=item.detected_at,
                    changed_fields=tuple(
                        item.changed_fields
                    ),
                    before=(
                        dict(
                            item.before
                        )
                        if item.before
                        is not None
                        else None
                    ),
                    after=(
                        dict(
                            item.after
                        )
                        if item.after
                        is not None
                        else None
                    ),
                    metadata=dict(
                        item.metadata
                    ),
                )
                for item in self._last_changes
            ]

    @staticmethod
    def _is_world_state_projection(
        metadata: dict[str, Any],
    ) -> bool:
        return (
            str(
                metadata.get(
                    "projection",
                    ""
                )
            )
            .strip()
            .lower()
            == "world_state"
        )

    def _replace_projected_model(
        self,
        *,
        entities,
        relations,
    ) -> None:
        """
        Replace only world-state-projected records.

        Any future non-world-state model entities/relations are preserved.
        Relations are removed before entities so endpoint integrity is never
        temporarily violated.
        """

        for relation in self.store.list_relations():
            if self._is_world_state_projection(
                relation.metadata
            ):
                self.store.delete_relation(
                    relation.relation_id
                )

        for entity in self.store.list_entities():
            if self._is_world_state_projection(
                entity.metadata
            ):
                self.store.delete_entity(
                    entity.entity_id,
                    cascade_relations=True,
                )

        self.store.add_entities(
            entities
        )

        self.store.add_relations(
            relations
        )

    def refresh(
        self,
        *,
        emit_initial_changes: bool = False,
    ) -> list[
        WorldModelChange
    ]:
        with self._lock:
            snapshot = (
                get_world_state_snapshot(
                    include_stale=True
                )
            )

            projected = (
                project_world_state_snapshot(
                    snapshot
                )
            )

            reconciled = (
                reconcile_world_model_candidates(
                    entities=projected[
                        "entities"
                    ],
                    relations=projected[
                        "relations"
                    ],
                )
            )

            changes = (
                self.change_tracker.observe(
                    entities=reconciled[
                        "entities"
                    ],
                    relations=reconciled[
                        "relations"
                    ],
                    emit_initial_additions=(
                        emit_initial_changes
                    ),
                )
            )

            self._replace_projected_model(
                entities=reconciled[
                    "entities"
                ],
                relations=reconciled[
                    "relations"
                ],
            )

            self._last_changes = list(
                changes
            )

            return self.last_changes()

    def _handle_world_state_event(
        self,
        _event,
    ) -> None:
        self.refresh()

    def start(
        self,
        *,
        initial_refresh: bool = True,
    ) -> bool:
        """
        Start subscriptions once.

        Returns True only when this call actually starts the bridge.
        """

        with self._lock:
            if self._running:
                return False

            tokens = []

            try:
                for topic in (
                    WORLD_STATE_CHANGED,
                    WORLD_STATE_DELETED,
                    WORLD_STATE_CLEARED,
                ):
                    tokens.append(
                        subscribe(
                            topic,
                            self._handle_world_state_event,
                        )
                    )

                self._tokens = tokens
                self._running = True

            except Exception:
                for token in tokens:
                    try:
                        unsubscribe(
                            token
                        )
                    except Exception:
                        pass

                self._tokens = []
                self._running = False
                raise

        if initial_refresh:
            try:
                self.refresh()
            except Exception:
                self.stop()
                raise

        return True

    def stop(
        self,
    ) -> bool:
        """
        Stop subscriptions once.

        Returns True only when this call actually stops a running bridge.
        """

        with self._lock:
            if not self._running:
                return False

            tokens = list(
                self._tokens
            )

            self._tokens = []
            self._running = False

        for token in tokens:
            unsubscribe(
                token
            )

        return True


WORLD_MODEL_RUNTIME = (
    WorldModelRuntimeBridge()
)


def start_world_model_runtime(
    *,
    initial_refresh: bool = True,
) -> bool:
    return WORLD_MODEL_RUNTIME.start(
        initial_refresh=initial_refresh
    )


def stop_world_model_runtime() -> bool:
    return WORLD_MODEL_RUNTIME.stop()


def refresh_world_model_runtime():
    return WORLD_MODEL_RUNTIME.refresh()


__all__ = [
    "WORLD_MODEL_RUNTIME",
    "WorldModelRuntimeBridge",
    "refresh_world_model_runtime",
    "start_world_model_runtime",
    "stop_world_model_runtime",
]
