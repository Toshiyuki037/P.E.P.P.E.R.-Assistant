"""
P.E.P.P.E.R. - Temporal World-Model Change Tracking

Phase 17A.5

Tracks meaningful changes between reconciled world-model states.

Important:
    - Pure deterministic comparison.
    - No perception/provider calls.
    - No event subscriptions yet (Phase 17A.7).
    - No persistence yet.
    - Timestamp/evidence refresh alone is not treated as a semantic change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
from copy import deepcopy

from .models import (
    WorldEntity,
    WorldRelation,
    utc_now_iso,
)


ENTITY_ADDED = "entity_added"
ENTITY_CHANGED = "entity_changed"
ENTITY_REMOVED = "entity_removed"

RELATION_ADDED = "relation_added"
RELATION_CHANGED = "relation_changed"
RELATION_REMOVED = "relation_removed"


@dataclass(frozen=True)
class WorldModelChange:
    change_type: str
    record_id: str
    record_kind: str
    detected_at: str = field(
        default_factory=utc_now_iso
    )
    changed_fields: tuple[str, ...] = ()
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "change_type":
                self.change_type,
            "record_id":
                self.record_id,
            "record_kind":
                self.record_kind,
            "detected_at":
                self.detected_at,
            "changed_fields":
                list(
                    self.changed_fields
                ),
            "before":
                deepcopy(
                    self.before
                ),
            "after":
                deepcopy(
                    self.after
                ),
            "metadata":
                deepcopy(
                    self.metadata
                ),
        }


def _entity_material(
    entity: WorldEntity,
) -> dict[str, Any]:
    return {
        "entity_type":
            entity.entity_type,
        "name":
            entity.name,
        "attributes":
            deepcopy(
                entity.attributes
            ),
        "confidence":
            float(
                entity.confidence
            ),
        "metadata":
            deepcopy(
                entity.metadata
            ),
    }


def _relation_material(
    relation: WorldRelation,
) -> dict[str, Any]:
    return {
        "subject_id":
            relation.subject_id,
        "predicate":
            relation.predicate,
        "object_id":
            relation.object_id,
        "confidence":
            float(
                relation.confidence
            ),
        "metadata":
            deepcopy(
                relation.metadata
            ),
    }


def _changed_fields(
    before: dict[str, Any],
    after: dict[str, Any],
) -> tuple[str, ...]:
    keys = sorted(
        set(
            before
        )
        | set(
            after
        )
    )

    return tuple(
        key
        for key in keys
        if before.get(
            key
        )
        != after.get(
            key
        )
    )


def _entity_map(
    entities: Iterable[
        WorldEntity
    ],
) -> dict[
    str,
    WorldEntity,
]:
    result = {}

    for entity in entities:
        if not isinstance(
            entity,
            WorldEntity,
        ):
            raise TypeError(
                "entities must contain WorldEntity records."
            )

        if entity.entity_id in result:
            raise ValueError(
                f"Duplicate entity_id in one temporal state: {entity.entity_id}"
            )

        result[
            entity.entity_id
        ] = entity

    return result


def _relation_map(
    relations: Iterable[
        WorldRelation
    ],
) -> dict[
    str,
    WorldRelation,
]:
    result = {}

    for relation in relations:
        if not isinstance(
            relation,
            WorldRelation,
        ):
            raise TypeError(
                "relations must contain WorldRelation records."
            )

        if relation.relation_id in result:
            raise ValueError(
                f"Duplicate relation_id in one temporal state: {relation.relation_id}"
            )

        result[
            relation.relation_id
        ] = relation

    return result


def compare_world_model_states(
    *,
    previous_entities: Iterable[
        WorldEntity
    ] = (),
    previous_relations: Iterable[
        WorldRelation
    ] = (),
    current_entities: Iterable[
        WorldEntity
    ] = (),
    current_relations: Iterable[
        WorldRelation
    ] = (),
    detected_at: str | None = None,
) -> list[
    WorldModelChange
]:
    """
    Compare two reconciled model states.

    Temporal-only fields (`observed_at`, `updated_at`, evidence timestamps) are
    deliberately ignored for semantic-change detection. A repeated observation
    of the same fact therefore does not create false churn.
    """

    timestamp = (
        str(
            detected_at
            or utc_now_iso()
        )
    )

    previous_entity_map = (
        _entity_map(
            previous_entities
        )
    )
    current_entity_map = (
        _entity_map(
            current_entities
        )
    )

    previous_relation_map = (
        _relation_map(
            previous_relations
        )
    )
    current_relation_map = (
        _relation_map(
            current_relations
        )
    )

    changes: list[
        WorldModelChange
    ] = []

    entity_ids = sorted(
        set(
            previous_entity_map
        )
        | set(
            current_entity_map
        )
    )

    for entity_id in entity_ids:
        before_entity = (
            previous_entity_map.get(
                entity_id
            )
        )
        after_entity = (
            current_entity_map.get(
                entity_id
            )
        )

        if before_entity is None:
            changes.append(
                WorldModelChange(
                    change_type=ENTITY_ADDED,
                    record_id=entity_id,
                    record_kind="entity",
                    detected_at=timestamp,
                    changed_fields=(
                        "added",
                    ),
                    before=None,
                    after=(
                        after_entity.to_dict()
                        if after_entity
                        is not None
                        else None
                    ),
                )
            )
            continue

        if after_entity is None:
            changes.append(
                WorldModelChange(
                    change_type=ENTITY_REMOVED,
                    record_id=entity_id,
                    record_kind="entity",
                    detected_at=timestamp,
                    changed_fields=(
                        "removed",
                    ),
                    before=(
                        before_entity.to_dict()
                    ),
                    after=None,
                )
            )
            continue

        before_material = (
            _entity_material(
                before_entity
            )
        )
        after_material = (
            _entity_material(
                after_entity
            )
        )

        fields = _changed_fields(
            before_material,
            after_material,
        )

        if fields:
            changes.append(
                WorldModelChange(
                    change_type=ENTITY_CHANGED,
                    record_id=entity_id,
                    record_kind="entity",
                    detected_at=timestamp,
                    changed_fields=fields,
                    before=(
                        before_entity.to_dict()
                    ),
                    after=(
                        after_entity.to_dict()
                    ),
                )
            )

    relation_ids = sorted(
        set(
            previous_relation_map
        )
        | set(
            current_relation_map
        )
    )

    for relation_id in relation_ids:
        before_relation = (
            previous_relation_map.get(
                relation_id
            )
        )
        after_relation = (
            current_relation_map.get(
                relation_id
            )
        )

        if before_relation is None:
            changes.append(
                WorldModelChange(
                    change_type=RELATION_ADDED,
                    record_id=relation_id,
                    record_kind="relation",
                    detected_at=timestamp,
                    changed_fields=(
                        "added",
                    ),
                    before=None,
                    after=(
                        after_relation.to_dict()
                        if after_relation
                        is not None
                        else None
                    ),
                )
            )
            continue

        if after_relation is None:
            changes.append(
                WorldModelChange(
                    change_type=RELATION_REMOVED,
                    record_id=relation_id,
                    record_kind="relation",
                    detected_at=timestamp,
                    changed_fields=(
                        "removed",
                    ),
                    before=(
                        before_relation.to_dict()
                    ),
                    after=None,
                )
            )
            continue

        before_material = (
            _relation_material(
                before_relation
            )
        )
        after_material = (
            _relation_material(
                after_relation
            )
        )

        fields = _changed_fields(
            before_material,
            after_material,
        )

        if fields:
            changes.append(
                WorldModelChange(
                    change_type=RELATION_CHANGED,
                    record_id=relation_id,
                    record_kind="relation",
                    detected_at=timestamp,
                    changed_fields=fields,
                    before=(
                        before_relation.to_dict()
                    ),
                    after=(
                        after_relation.to_dict()
                    ),
                )
            )

    return changes


class WorldModelChangeTracker:
    """
    Small in-memory temporal tracker for explicit observations.

    The tracker does not mutate a WorldModelStore and does not subscribe to the
    event bus. Runtime integration is deferred to Phase 17A.7.
    """

    def __init__(
        self,
        *,
        max_history: int = 256,
    ):
        if int(
            max_history
        ) < 1:
            raise ValueError(
                "max_history must be at least 1."
            )

        self.max_history = int(
            max_history
        )

        self._entities: dict[
            str,
            WorldEntity,
        ] = {}

        self._relations: dict[
            str,
            WorldRelation,
        ] = {}

        self._history: list[
            WorldModelChange
        ] = []

        self._initialized = False

    @property
    def initialized(
        self,
    ) -> bool:
        return self._initialized

    def clear(
        self,
    ) -> None:
        self._entities.clear()
        self._relations.clear()
        self._history.clear()
        self._initialized = False

    def history(
        self,
        *,
        limit: int | None = None,
    ) -> list[
        WorldModelChange
    ]:
        values = list(
            self._history
        )

        if limit is not None:
            count = int(
                limit
            )

            if count < 0:
                raise ValueError(
                    "limit cannot be negative."
                )

            values = (
                values[
                    -count:
                ]
                if count
                else []
            )

        return [
            WorldModelChange(
                change_type=item.change_type,
                record_id=item.record_id,
                record_kind=item.record_kind,
                detected_at=item.detected_at,
                changed_fields=tuple(
                    item.changed_fields
                ),
                before=deepcopy(
                    item.before
                ),
                after=deepcopy(
                    item.after
                ),
                metadata=deepcopy(
                    item.metadata
                ),
            )
            for item in values
        ]

    def observe(
        self,
        *,
        entities: Iterable[
            WorldEntity
        ] = (),
        relations: Iterable[
            WorldRelation
        ] = (),
        detected_at: str | None = None,
        emit_initial_additions: bool = False,
    ) -> list[
        WorldModelChange
    ]:
        current_entities = (
            _entity_map(
                entities
            )
        )
        current_relations = (
            _relation_map(
                relations
            )
        )

        if (
            not self._initialized
            and not emit_initial_additions
        ):
            changes = []
        else:
            changes = (
                compare_world_model_states(
                    previous_entities=(
                        self._entities.values()
                    ),
                    previous_relations=(
                        self._relations.values()
                    ),
                    current_entities=(
                        current_entities.values()
                    ),
                    current_relations=(
                        current_relations.values()
                    ),
                    detected_at=detected_at,
                )
            )

        self._entities = {
            key:
                WorldEntity.from_dict(
                    value.to_dict()
                )
            for key, value
            in current_entities.items()
        }

        self._relations = {
            key:
                WorldRelation.from_dict(
                    value.to_dict()
                )
            for key, value
            in current_relations.items()
        }

        self._initialized = True

        if changes:
            self._history.extend(
                changes
            )

            overflow = (
                len(
                    self._history
                )
                - self.max_history
            )

            if overflow > 0:
                del self._history[
                    :overflow
                ]

        return [
            WorldModelChange(
                change_type=item.change_type,
                record_id=item.record_id,
                record_kind=item.record_kind,
                detected_at=item.detected_at,
                changed_fields=tuple(
                    item.changed_fields
                ),
                before=deepcopy(
                    item.before
                ),
                after=deepcopy(
                    item.after
                ),
                metadata=deepcopy(
                    item.metadata
                ),
            )
            for item in changes
        ]


__all__ = [
    "ENTITY_ADDED",
    "ENTITY_CHANGED",
    "ENTITY_REMOVED",
    "RELATION_ADDED",
    "RELATION_CHANGED",
    "RELATION_REMOVED",
    "WorldModelChange",
    "WorldModelChangeTracker",
    "compare_world_model_states",
]
