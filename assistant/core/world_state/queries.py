"""
P.E.P.P.E.R. - Unified World Model Query / Explanation API

Phase 17A.6

Purpose:
    Provide deterministic read APIs over the Phase 17 unified world model.

Important:
    - No LLM calls.
    - No perception/provider calls.
    - No event subscriptions or runtime wiring yet.
    - No persistence.
    - Explanations expose provenance; they do not invent causes.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from .model import (
    WORLD_MODEL,
    WorldModelStore,
)
from .models import (
    WorldEntity,
    WorldEvidence,
    WorldRelation,
)


def _text(
    value: Any,
) -> str:
    return str(
        value
        or ""
    ).strip()


def _status_rank(
    status: str,
) -> int:
    return {
        "fresh": 3,
        "stale_usable": 2,
        "expired": 1,
        "absent": 0,
    }.get(
        _text(
            status
        ).lower(),
        0,
    )


def _best_evidence_status(
    evidence: Iterable[
        WorldEvidence
    ],
) -> str:
    values = list(
        evidence
    )

    if not values:
        return "absent"

    return max(
        values,
        key=lambda item:
            (
                _status_rank(
                    item.status
                ),
                item.observed_at,
                float(
                    item.confidence
                ),
            ),
    ).status


def find_entities(
    *,
    store: WorldModelStore = WORLD_MODEL,
    entity_type: str | None = None,
    name_contains: str | None = None,
    attribute_equals: dict[str, Any] | None = None,
) -> list[
    WorldEntity
]:
    entity_type_filter = (
        _text(
            entity_type
        ).lower()
    )

    name_filter = (
        _text(
            name_contains
        ).lower()
    )

    attributes = dict(
        attribute_equals
        or {}
    )

    results = []

    for entity in store.list_entities():
        if (
            entity_type_filter
            and entity.entity_type
            != entity_type_filter
        ):
            continue

        if (
            name_filter
            and name_filter
            not in entity.name.lower()
        ):
            continue

        if any(
            entity.attributes.get(
                key
            )
            != value
            for key, value
            in attributes.items()
        ):
            continue

        results.append(
            entity
        )

    return sorted(
        results,
        key=lambda item:
            item.entity_id,
    )


def find_relations(
    *,
    store: WorldModelStore = WORLD_MODEL,
    subject_id: str | None = None,
    predicate: str | None = None,
    object_id: str | None = None,
) -> list[
    WorldRelation
]:
    subject_filter = (
        _text(
            subject_id
        ).lower()
    )

    predicate_filter = (
        _text(
            predicate
        )
        .lower()
        .replace(
            " ",
            "_",
        )
    )

    object_filter = (
        _text(
            object_id
        ).lower()
    )

    results = []

    for relation in store.list_relations():
        if (
            subject_filter
            and relation.subject_id
            != subject_filter
        ):
            continue

        if (
            predicate_filter
            and relation.predicate
            != predicate_filter
        ):
            continue

        if (
            object_filter
            and relation.object_id
            != object_filter
        ):
            continue

        results.append(
            relation
        )

    return sorted(
        results,
        key=lambda item:
            item.relation_id,
    )


def get_neighbors(
    entity_id: str,
    *,
    store: WorldModelStore = WORLD_MODEL,
    predicate: str | None = None,
    direction: str = "both",
) -> list[
    dict[str, Any]
]:
    normalized_id = (
        _text(
            entity_id
        ).lower()
    )

    if not normalized_id:
        raise ValueError(
            "entity_id cannot be empty."
        )

    normalized_direction = (
        _text(
            direction
        ).lower()
        or "both"
    )

    if normalized_direction not in {
        "incoming",
        "outgoing",
        "both",
    }:
        raise ValueError(
            "direction must be incoming, outgoing, or both."
        )

    predicate_filter = (
        _text(
            predicate
        )
        .lower()
        .replace(
            " ",
            "_",
        )
    )

    results = []

    for relation in store.list_relations():
        if (
            predicate_filter
            and relation.predicate
            != predicate_filter
        ):
            continue

        outgoing = (
            relation.subject_id
            == normalized_id
        )

        incoming = (
            relation.object_id
            == normalized_id
        )

        if (
            normalized_direction
            == "outgoing"
            and not outgoing
        ):
            continue

        if (
            normalized_direction
            == "incoming"
            and not incoming
        ):
            continue

        if (
            normalized_direction
            == "both"
            and not (
                outgoing
                or incoming
            )
        ):
            continue

        other_id = (
            relation.object_id
            if outgoing
            else relation.subject_id
        )

        results.append(
            {
                "direction":
                    (
                        "outgoing"
                        if outgoing
                        else "incoming"
                    ),
                "relation":
                    relation,
                "entity":
                    store.get_entity(
                        other_id
                    ),
            }
        )

    return sorted(
        results,
        key=lambda item:
            (
                item[
                    "relation"
                ].predicate,
                item[
                    "relation"
                ].relation_id,
            ),
    )


def explain_entity(
    entity_id: str,
    *,
    store: WorldModelStore = WORLD_MODEL,
) -> dict[str, Any] | None:
    entity = store.get_entity(
        entity_id
    )

    if entity is None:
        return None

    evidence = [
        item.to_dict()
        for item
        in entity.evidence
    ]

    return {
        "entity":
            entity.to_dict(),
        "current_status":
            _best_evidence_status(
                entity.evidence
            ),
        "confidence":
            float(
                entity.confidence
            ),
        "observed_at":
            entity.observed_at,
        "evidence":
            evidence,
        "evidence_keys":
            sorted(
                {
                    item.world_state_key
                    for item
                    in entity.evidence
                }
            ),
        "sources":
            sorted(
                {
                    item.source
                    for item
                    in entity.evidence
                }
            ),
        "relations":
            [
                item[
                    "relation"
                ].to_dict()
                for item
                in get_neighbors(
                    entity.entity_id,
                    store=store,
                )
            ],
    }


def explain_relation(
    relation_id: str,
    *,
    store: WorldModelStore = WORLD_MODEL,
) -> dict[str, Any] | None:
    relation = store.get_relation(
        relation_id
    )

    if relation is None:
        return None

    return {
        "relation":
            relation.to_dict(),
        "current_status":
            _best_evidence_status(
                relation.evidence
            ),
        "confidence":
            float(
                relation.confidence
            ),
        "observed_at":
            relation.observed_at,
        "evidence":
            [
                item.to_dict()
                for item
                in relation.evidence
            ],
        "evidence_keys":
            sorted(
                {
                    item.world_state_key
                    for item
                    in relation.evidence
                }
            ),
        "sources":
            sorted(
                {
                    item.source
                    for item
                    in relation.evidence
                }
            ),
        "subject":
            (
                store.get_entity(
                    relation.subject_id
                ).to_dict()
                if store.get_entity(
                    relation.subject_id
                )
                is not None
                else None
            ),
        "object":
            (
                store.get_entity(
                    relation.object_id
                ).to_dict()
                if store.get_entity(
                    relation.object_id
                )
                is not None
                else None
            ),
    }


# Phase 17A.8 current-state usability gate
def _entity_is_current(entity: WorldEntity) -> bool:
    return _best_evidence_status(entity.evidence) in {
        "fresh",
        "stale_usable",
    }


def get_current_context(
    *,
    store: WorldModelStore = WORLD_MODEL,
) -> dict[str, Any]:
    """
    Return a compact deterministic view of what the model currently represents.

    This does not infer an active workspace when the projected workspace carries
    active=False. That distinction is important because the existing perception
    layer can retain a fallback workspace even when it is not current.
    """

    active_applications = [
        item
        for item in find_entities(
            store=store,
            entity_type="application",
            attribute_equals={
                "active":
                    True,
            },
        )
        if _entity_is_current(item)
    ]

    active_workspaces = [
        item
        for item in find_entities(
            store=store,
            entity_type="workspace",
            attribute_equals={
                "active":
                    True,
            },
        )
        if _entity_is_current(item)
    ]

    active_files = [
        item
        for item in find_entities(
            store=store,
            entity_type="file",
            attribute_equals={
                "active":
                    True,
            },
        )
        if _entity_is_current(item)
    ]

    active_windows = [
        item
        for item in find_entities(
            store=store,
            entity_type="window",
            attribute_equals={
                "active":
                    True,
            },
        )
        if _entity_is_current(item)
    ]

    locations = [
        item
        for item in find_entities(
            store=store,
            entity_type="location",
        )
        if _entity_is_current(item)
    ]

    integrations = [
        item
        for item in find_entities(
            store=store,
            entity_type="integration_state",
        )
        if _entity_is_current(item)
    ]

    return {
        "active_application":
            (
                active_applications[
                    0
                ].to_dict()
                if active_applications
                else None
            ),
        "active_workspace":
            (
                active_workspaces[
                    0
                ].to_dict()
                if active_workspaces
                else None
            ),
        "active_file":
            (
                active_files[
                    0
                ].to_dict()
                if active_files
                else None
            ),
        "active_window":
            (
                active_windows[
                    0
                ].to_dict()
                if active_windows
                else None
            ),
        "current_location":
            (
                locations[
                    0
                ].to_dict()
                if locations
                else None
            ),
        "integration_states":
            [
                item.to_dict()
                for item
                in integrations
            ],
    }


def explain_current_context(
    *,
    store: WorldModelStore = WORLD_MODEL,
) -> dict[str, Any]:
    context = get_current_context(
        store=store
    )

    explanations = {}

    for key in (
        "active_application",
        "active_workspace",
        "active_file",
        "active_window",
        "current_location",
    ):
        record = context.get(
            key
        )

        explanations[
            key
        ] = (
            explain_entity(
                record[
                    "entity_id"
                ],
                store=store,
            )
            if record
            is not None
            else None
        )

    explanations[
        "integration_states"
    ] = [
        explain_entity(
            item[
                "entity_id"
            ],
            store=store,
        )
        for item
        in context[
            "integration_states"
        ]
    ]

    return {
        "context":
            deepcopy(
                context
            ),
        "explanations":
            explanations,
    }


def summarize_current_work(
    *,
    store: WorldModelStore = WORLD_MODEL,
) -> dict[str, Any]:
    """
    Structured answer target for future natural-language handling of
    "What am I currently working on?"

    The function deliberately returns evidence-backed structure rather than
    generating prose or guessing a project.
    """

    context = get_current_context(
        store=store
    )

    workspace = context[
        "active_workspace"
    ]
    file_record = context[
        "active_file"
    ]
    application = context[
        "active_application"
    ]

    return {
        "workspace":
            workspace,
        "file":
            file_record,
        "application":
            application,
        "has_active_work_context":
            bool(
                workspace
                or file_record
            ),
        "basis":
            {
                "workspace":
                    (
                        explain_entity(
                            workspace[
                                "entity_id"
                            ],
                            store=store,
                        )
                        if workspace
                        else None
                    ),
                "file":
                    (
                        explain_entity(
                            file_record[
                                "entity_id"
                            ],
                            store=store,
                        )
                        if file_record
                        else None
                    ),
                "application":
                    (
                        explain_entity(
                            application[
                                "entity_id"
                            ],
                            store=store,
                        )
                        if application
                        else None
                    ),
            },
    }


__all__ = [
    "explain_current_context",
    "explain_entity",
    "explain_relation",
    "find_entities",
    "find_relations",
    "get_current_context",
    "get_neighbors",
    "summarize_current_work",
]
