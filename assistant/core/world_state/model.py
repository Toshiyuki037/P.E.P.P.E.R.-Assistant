"""
P.E.P.P.E.R. - Unified World Model Store

Phase 17A.2

Purpose:
    Deterministic, thread-safe in-memory store for Phase 17 world-model
    entities and relations.

Integrity guarantees:
    - Phase 16 world state remains authoritative for atomic observations.
    - No persistence, event subscriptions, perception collection, or LLM calls.
    - Relation endpoints are validated by default.
    - Objects crossing the store boundary are defensively copied so mutable
      nested dictionaries cannot mutate store internals.
"""

from __future__ import annotations

from dataclasses import replace
from threading import RLock
from typing import Iterable

from .models import (
    WorldEntity,
    WorldRelation,
    utc_now_iso,
)


def _copy_entity(
    entity: WorldEntity,
) -> WorldEntity:
    return WorldEntity.from_dict(
        entity.to_dict()
    )


def _copy_relation(
    relation: WorldRelation,
) -> WorldRelation:
    return WorldRelation.from_dict(
        relation.to_dict()
    )


class WorldModelStore:
    def __init__(self):
        self._lock = RLock()
        self._entities: dict[str, WorldEntity] = {}
        self._relations: dict[str, WorldRelation] = {}

    # ------------------------------------------------------------------
    # Entity operations
    # ------------------------------------------------------------------

    def upsert_entity(
        self,
        entity: WorldEntity,
    ) -> WorldEntity:
        if not isinstance(
            entity,
            WorldEntity,
        ):
            raise TypeError(
                "entity must be a WorldEntity."
            )

        incoming = _copy_entity(
            entity
        )

        with self._lock:
            if (
                incoming.entity_id
                in self._entities
            ):
                incoming = replace(
                    incoming,
                    updated_at=utc_now_iso(),
                )

            self._entities[
                incoming.entity_id
            ] = incoming

            return _copy_entity(
                incoming
            )

    def get_entity(
        self,
        entity_id: str,
    ) -> WorldEntity | None:
        normalized = self._normalize_id(
            entity_id,
            "entity_id",
        )

        with self._lock:
            entity = self._entities.get(
                normalized
            )

            return (
                _copy_entity(
                    entity
                )
                if entity is not None
                else None
            )

    def has_entity(
        self,
        entity_id: str,
    ) -> bool:
        normalized = self._normalize_id(
            entity_id,
            "entity_id",
        )

        with self._lock:
            return (
                normalized
                in self._entities
            )

    def delete_entity(
        self,
        entity_id: str,
        *,
        cascade_relations: bool = True,
    ) -> bool:
        normalized = self._normalize_id(
            entity_id,
            "entity_id",
        )

        with self._lock:
            if normalized not in self._entities:
                return False

            if not cascade_relations:
                for relation in self._relations.values():
                    if (
                        relation.subject_id
                        == normalized
                        or relation.object_id
                        == normalized
                    ):
                        raise ValueError(
                            "Cannot delete entity while relations "
                            "reference it unless cascade_relations=True."
                        )

            self._entities.pop(
                normalized,
                None,
            )

            if cascade_relations:
                relation_ids = [
                    relation_id
                    for relation_id, relation
                    in self._relations.items()
                    if (
                        relation.subject_id
                        == normalized
                        or relation.object_id
                        == normalized
                    )
                ]

                for relation_id in relation_ids:
                    self._relations.pop(
                        relation_id,
                        None,
                    )

            return True

    def list_entities(
        self,
        *,
        entity_type: str | None = None,
    ) -> list[WorldEntity]:
        normalized_type = (
            None
            if entity_type is None
            else self._normalize_id(
                entity_type,
                "entity_type",
            )
        )

        with self._lock:
            items = [
                _copy_entity(
                    entity
                )
                for entity
                in self._entities.values()
            ]

        if normalized_type is not None:
            items = [
                entity
                for entity in items
                if entity.entity_type
                == normalized_type
            ]

        return sorted(
            items,
            key=lambda item:
                item.entity_id,
        )

    # ------------------------------------------------------------------
    # Relation operations
    # ------------------------------------------------------------------

    def upsert_relation(
        self,
        relation: WorldRelation,
        *,
        require_endpoints: bool = True,
    ) -> WorldRelation:
        if not isinstance(
            relation,
            WorldRelation,
        ):
            raise TypeError(
                "relation must be a WorldRelation."
            )

        incoming = _copy_relation(
            relation
        )

        with self._lock:
            if require_endpoints:
                missing = []

                if (
                    incoming.subject_id
                    not in self._entities
                ):
                    missing.append(
                        incoming.subject_id
                    )

                if (
                    incoming.object_id
                    not in self._entities
                ):
                    missing.append(
                        incoming.object_id
                    )

                if missing:
                    raise KeyError(
                        "Relation endpoint entity missing: "
                        + ", ".join(
                            sorted(
                                set(
                                    missing
                                )
                            )
                        )
                    )

            if (
                incoming.relation_id
                in self._relations
            ):
                incoming = replace(
                    incoming,
                    updated_at=utc_now_iso(),
                )

            self._relations[
                incoming.relation_id
            ] = incoming

            return _copy_relation(
                incoming
            )

    def get_relation(
        self,
        relation_id: str,
    ) -> WorldRelation | None:
        normalized = self._normalize_id(
            relation_id,
            "relation_id",
        )

        with self._lock:
            relation = (
                self._relations.get(
                    normalized
                )
            )

            return (
                _copy_relation(
                    relation
                )
                if relation is not None
                else None
            )

    def has_relation(
        self,
        relation_id: str,
    ) -> bool:
        normalized = self._normalize_id(
            relation_id,
            "relation_id",
        )

        with self._lock:
            return (
                normalized
                in self._relations
            )

    def delete_relation(
        self,
        relation_id: str,
    ) -> bool:
        normalized = self._normalize_id(
            relation_id,
            "relation_id",
        )

        with self._lock:
            return (
                self._relations.pop(
                    normalized,
                    None,
                )
                is not None
            )

    def list_relations(
        self,
        *,
        subject_id: str | None = None,
        predicate: str | None = None,
        object_id: str | None = None,
    ) -> list[WorldRelation]:
        normalized_subject = (
            None
            if subject_id is None
            else self._normalize_id(
                subject_id,
                "subject_id",
            )
        )
        normalized_predicate = (
            None
            if predicate is None
            else self._normalize_predicate(
                predicate
            )
        )
        normalized_object = (
            None
            if object_id is None
            else self._normalize_id(
                object_id,
                "object_id",
            )
        )

        with self._lock:
            items = [
                _copy_relation(
                    relation
                )
                for relation
                in self._relations.values()
            ]

        if normalized_subject is not None:
            items = [
                relation
                for relation in items
                if relation.subject_id
                == normalized_subject
            ]

        if normalized_predicate is not None:
            items = [
                relation
                for relation in items
                if relation.predicate
                == normalized_predicate
            ]

        if normalized_object is not None:
            items = [
                relation
                for relation in items
                if relation.object_id
                == normalized_object
            ]

        return sorted(
            items,
            key=lambda item:
                item.relation_id,
        )

    def relations_for(
        self,
        entity_id: str,
    ) -> list[WorldRelation]:
        normalized = self._normalize_id(
            entity_id,
            "entity_id",
        )

        with self._lock:
            items = [
                _copy_relation(
                    relation
                )
                for relation
                in self._relations.values()
                if (
                    relation.subject_id
                    == normalized
                    or relation.object_id
                    == normalized
                )
            ]

        return sorted(
            items,
            key=lambda item:
                item.relation_id,
        )

    # ------------------------------------------------------------------
    # Bulk / snapshot operations
    # ------------------------------------------------------------------

    def add_entities(
        self,
        entities: Iterable[
            WorldEntity
        ],
    ) -> list[WorldEntity]:
        return [
            self.upsert_entity(
                entity
            )
            for entity in entities
        ]

    def add_relations(
        self,
        relations: Iterable[
            WorldRelation
        ],
        *,
        require_endpoints: bool = True,
    ) -> list[WorldRelation]:
        return [
            self.upsert_relation(
                relation,
                require_endpoints=require_endpoints,
            )
            for relation in relations
        ]

    def clear(self) -> None:
        with self._lock:
            self._relations.clear()
            self._entities.clear()

    def entity_count(self) -> int:
        with self._lock:
            return len(
                self._entities
            )

    def relation_count(self) -> int:
        with self._lock:
            return len(
                self._relations
            )

    def snapshot(
        self,
    ) -> dict[str, object]:
        with self._lock:
            return {
                "entities": [
                    entity.to_dict()
                    for entity
                    in sorted(
                        self._entities.values(),
                        key=lambda item:
                            item.entity_id,
                    )
                ],
                "relations": [
                    relation.to_dict()
                    for relation
                    in sorted(
                        self._relations.values(),
                        key=lambda item:
                            item.relation_id,
                    )
                ],
            }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_id(
        value: str,
        field_name: str,
    ) -> str:
        normalized = str(
            value
            or ""
        ).strip().lower()

        if not normalized:
            raise ValueError(
                f"{field_name} cannot be empty."
            )

        return normalized

    @classmethod
    def _normalize_predicate(
        cls,
        value: str,
    ) -> str:
        return cls._normalize_id(
            value,
            "predicate",
        ).replace(
            " ",
            "_",
        )


WORLD_MODEL = WorldModelStore()


__all__ = [
    "WORLD_MODEL",
    "WorldModelStore",
]
