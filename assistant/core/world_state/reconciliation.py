"""
P.E.P.P.E.R. - World Model Reconciliation

Phase 17A.4

Purpose:
    Deterministically reconcile competing Phase 17 world-model observations
    without introducing a second freshness policy.

Rules:
    1. Existing Phase 16 freshness classification remains authoritative.
    2. FRESH outranks STALE_USABLE, which outranks EXPIRED, which outranks ABSENT.
    3. Within the same freshness class, newer observed_at wins.
    4. If timestamps tie, higher confidence wins.
    5. Lower-ranked candidates may fill missing attributes/metadata, but never
       overwrite fields supplied by the winning candidate.
    6. Evidence from all candidates is preserved deterministically.
    7. No LLM, persistence, event subscription, or runtime wiring is added here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Sequence, TypeVar

from .models import (
    WorldEntity,
    WorldEvidence,
    WorldRelation,
)


_STATUS_RANK = {
    "fresh": 3,
    "stale_usable": 2,
    "expired": 1,
    "absent": 0,
}

T = TypeVar(
    "T",
    WorldEntity,
    WorldRelation,
)


def _parse_timestamp(
    value: str,
) -> datetime:
    text = str(
        value
        or ""
    ).strip()

    if not text:
        return datetime.min.replace(
            tzinfo=timezone.utc
        )

    try:
        parsed = datetime.fromisoformat(
            text
        )
    except ValueError:
        return datetime.min.replace(
            tzinfo=timezone.utc
        )

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def _status_rank(
    evidence: Sequence[
        WorldEvidence
    ],
) -> int:
    if not evidence:
        return _STATUS_RANK[
            "absent"
        ]

    return max(
        _STATUS_RANK.get(
            str(
                item.status
                or ""
            ).strip().lower(),
            _STATUS_RANK[
                "absent"
            ],
        )
        for item in evidence
    )


def _candidate_rank(
    item: T,
):
    return (
        _status_rank(
            item.evidence
        ),
        _parse_timestamp(
            item.observed_at
        ),
        float(
            item.confidence
        ),
        _parse_timestamp(
            item.updated_at
        ),
    )


def _merge_evidence(
    candidates: Iterable[
        WorldEntity | WorldRelation
    ],
) -> tuple[
    WorldEvidence,
    ...,
]:
    by_identity = {}

    for candidate in candidates:
        for evidence in candidate.evidence:
            identity = (
                evidence.world_state_key,
                evidence.source,
                evidence.status,
                evidence.observed_at,
                float(
                    evidence.confidence
                ),
            )
            by_identity[
                identity
            ] = evidence

    return tuple(
        by_identity[
            key
        ]
        for key in sorted(
            by_identity
        )
    )


def _merge_mappings(
    winner: dict,
    losers: Iterable[
        dict
    ],
) -> dict:
    merged = dict(
        winner
    )

    for mapping in losers:
        for key, value in mapping.items():
            if key not in merged:
                merged[
                    key
                ] = value

    return merged


def reconcile_entity_candidates(
    candidates: Sequence[
        WorldEntity
    ],
) -> WorldEntity:
    if not candidates:
        raise ValueError(
            "At least one entity candidate is required."
        )

    first_id = (
        candidates[
            0
        ].entity_id
    )

    if any(
        item.entity_id
        != first_id
        for item in candidates
    ):
        raise ValueError(
            "Entity candidates must share the same stable entity_id."
        )

    ordered = sorted(
        candidates,
        key=_candidate_rank,
        reverse=True,
    )

    winner = ordered[
        0
    ]
    losers = ordered[
        1:
    ]

    attributes = _merge_mappings(
        winner.attributes,
        (
            item.attributes
            for item in losers
        ),
    )

    metadata = _merge_mappings(
        winner.metadata,
        (
            item.metadata
            for item in losers
        ),
    )

    return WorldEntity(
        entity_id=winner.entity_id,
        entity_type=winner.entity_type,
        name=(
            winner.name
            or next(
                (
                    item.name
                    for item in losers
                    if item.name
                ),
                "",
            )
        ),
        attributes=attributes,
        confidence=winner.confidence,
        observed_at=winner.observed_at,
        updated_at=max(
            (
                item.updated_at
                for item in ordered
            ),
            key=_parse_timestamp,
        ),
        evidence=_merge_evidence(
            ordered
        ),
        metadata=metadata,
    )


def reconcile_relation_candidates(
    candidates: Sequence[
        WorldRelation
    ],
) -> WorldRelation:
    if not candidates:
        raise ValueError(
            "At least one relation candidate is required."
        )

    first_id = (
        candidates[
            0
        ].relation_id
    )

    if any(
        item.relation_id
        != first_id
        for item in candidates
    ):
        raise ValueError(
            "Relation candidates must share the same stable relation_id."
        )

    endpoints = {
        (
            item.subject_id,
            item.predicate,
            item.object_id,
        )
        for item in candidates
    }

    if len(
        endpoints
    ) != 1:
        raise ValueError(
            "Candidates sharing a relation_id must also share endpoints."
        )

    ordered = sorted(
        candidates,
        key=_candidate_rank,
        reverse=True,
    )

    winner = ordered[
        0
    ]
    losers = ordered[
        1:
    ]

    metadata = _merge_mappings(
        winner.metadata,
        (
            item.metadata
            for item in losers
        ),
    )

    return WorldRelation(
        relation_id=winner.relation_id,
        subject_id=winner.subject_id,
        predicate=winner.predicate,
        object_id=winner.object_id,
        confidence=winner.confidence,
        observed_at=winner.observed_at,
        updated_at=max(
            (
                item.updated_at
                for item in ordered
            ),
            key=_parse_timestamp,
        ),
        evidence=_merge_evidence(
            ordered
        ),
        metadata=metadata,
    )


def reconcile_world_model_candidates(
    *,
    entities: Iterable[
        WorldEntity
    ] = (),
    relations: Iterable[
        WorldRelation
    ] = (),
):
    entity_groups: dict[
        str,
        list[
            WorldEntity
        ],
    ] = {}

    relation_groups: dict[
        str,
        list[
            WorldRelation
        ],
    ] = {}

    for entity in entities:
        if not isinstance(
            entity,
            WorldEntity,
        ):
            raise TypeError(
                "entities must contain WorldEntity records."
            )

        entity_groups.setdefault(
            entity.entity_id,
            [],
        ).append(
            entity
        )

    for relation in relations:
        if not isinstance(
            relation,
            WorldRelation,
        ):
            raise TypeError(
                "relations must contain WorldRelation records."
            )

        relation_groups.setdefault(
            relation.relation_id,
            [],
        ).append(
            relation
        )

    reconciled_entities = [
        reconcile_entity_candidates(
            group
        )
        for _, group
        in sorted(
            entity_groups.items()
        )
    ]

    reconciled_relations = [
        reconcile_relation_candidates(
            group
        )
        for _, group
        in sorted(
            relation_groups.items()
        )
    ]

    return {
        "entities":
            reconciled_entities,
        "relations":
            reconciled_relations,
    }


__all__ = [
    "reconcile_entity_candidates",
    "reconcile_relation_candidates",
    "reconcile_world_model_candidates",
]
