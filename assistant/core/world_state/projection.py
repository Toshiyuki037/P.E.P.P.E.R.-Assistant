"""
P.E.P.P.E.R. - World-State Projection

Phase 17A.3

Projects existing Phase 16 operational RAM records into the Phase 17 unified
world model.

Important:
    - Existing world-state producers remain authoritative.
    - Existing freshness policy remains authoritative.
    - This module performs no perception collection and no provider calls.
    - This module does not subscribe to events yet; event wiring is Phase 17A.7.
    - This module performs no LLM calls.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .core import (
    WorldStateRecord,
    get_world_state_snapshot,
)
from .model import (
    WORLD_MODEL,
    WorldModelStore,
)
from .models import (
    WorldEntity,
    WorldEvidence,
    WorldRelation,
)
from .policy import (
    classify_world_state_record,
)


SUPPORTED_PREFIXES = (
    "computer.",
    "workspace.",
    "system.",
    "location.",
    "integration.",
)


def _clean_text(
    value: Any,
) -> str:
    return str(
        value
        or ""
    ).strip()


def _token(
    value: Any,
) -> str:
    text = (
        _clean_text(
            value
        )
        .lower()
    )

    safe = []

    for character in text:
        if (
            character.isalnum()
            or character
            in {
                "-",
                "_",
                ".",
            }
        ):
            safe.append(
                character
            )
        else:
            safe.append(
                "-"
            )

    normalized = "".join(
        safe
    )

    while "--" in normalized:
        normalized = normalized.replace(
            "--",
            "-",
        )

    return normalized.strip(
        "-._"
    )


def _stable_id(
    entity_type: str,
    identity: Any,
) -> str:
    kind = _token(
        entity_type
    )

    raw = _clean_text(
        identity
    )

    readable = _token(
        raw
    )

    if (
        readable
        and len(readable) <= 72
    ):
        return (
            f"{kind}:{readable}"
        )

    digest = hashlib.sha256(
        raw.encode(
            "utf-8"
        )
    ).hexdigest()[:20]

    return (
        f"{kind}:{digest}"
    )


def _relation_id(
    subject_id: str,
    predicate: str,
    object_id: str,
) -> str:
    triple = (
        f"{subject_id}\0"
        f"{predicate}\0"
        f"{object_id}"
    )

    digest = hashlib.sha256(
        triple.encode(
            "utf-8"
        )
    ).hexdigest()[:24]

    return (
        f"relation:{digest}"
    )


def _record_status(
    record: WorldStateRecord,
) -> str:
    return (
        classify_world_state_record(
            record,
            key=record.key,
        )
        .status.value
    )


def _evidence(
    record: WorldStateRecord,
) -> WorldEvidence:
    return WorldEvidence(
        world_state_key=record.key,
        source=record.source,
        status=_record_status(
            record
        ),
        confidence=record.confidence,
        observed_at=record.updated_at,
        metadata={
            "fresh_for_seconds":
                record.fresh_for_seconds,
            "world_state_metadata":
                record.metadata
                or {},
        },
    )


def _entity(
    *,
    entity_id: str,
    entity_type: str,
    name: str,
    attributes: dict[str, Any],
    record: WorldStateRecord,
) -> WorldEntity:
    return WorldEntity(
        entity_id=entity_id,
        entity_type=entity_type,
        name=name,
        attributes=attributes,
        confidence=record.confidence,
        observed_at=record.updated_at,
        updated_at=record.updated_at,
        evidence=(
            _evidence(
                record
            ),
        ),
        metadata={
            "projection":
                "world_state",
            "world_state_key":
                record.key,
        },
    )


def _relation(
    *,
    subject_id: str,
    predicate: str,
    object_id: str,
    record: WorldStateRecord,
    metadata: dict[str, Any] | None = None,
) -> WorldRelation:
    return WorldRelation(
        relation_id=_relation_id(
            subject_id,
            predicate,
            object_id,
        ),
        subject_id=subject_id,
        predicate=predicate,
        object_id=object_id,
        confidence=record.confidence,
        observed_at=record.updated_at,
        updated_at=record.updated_at,
        evidence=(
            _evidence(
                record
            ),
        ),
        metadata={
            "projection":
                "world_state",
            "world_state_key":
                record.key,
            **(
                metadata
                or {}
            ),
        },
    )


def _workspace_identity(
    workspace: dict[str, Any],
) -> str:
    return (
        _clean_text(
            workspace.get(
                "workspace_path"
            )
        )
        or _clean_text(
            workspace.get(
                "workspace_name"
            )
        )
        or _clean_text(
            workspace.get(
                "workspace_hint"
            )
        )
    )


def _workspace_entity(
    workspace: dict[str, Any],
    record: WorldStateRecord,
) -> WorldEntity | None:
    identity = _workspace_identity(
        workspace
    )

    if not identity:
        return None

    name = (
        _clean_text(
            workspace.get(
                "workspace_name"
            )
        )
        or Path(
            identity
        ).name
        or identity
    )

    return _entity(
        entity_id=_stable_id(
            "workspace",
            identity,
        ),
        entity_type="workspace",
        name=name,
        attributes={
            "workspace_name":
                workspace.get(
                    "workspace_name"
                ),
            "workspace_path":
                workspace.get(
                    "workspace_path"
                ),
            "git_repository":
                workspace.get(
                    "git_repository"
                ),
            "git_branch":
                workspace.get(
                    "git_branch"
                ),
            "modified_files":
                workspace.get(
                    "modified_files"
                )
                or [],
            "active":
                bool(
                    workspace.get(
                        "active"
                    )
                ),
            "resolved":
                bool(
                    workspace.get(
                        "resolved"
                    )
                ),
            "detection_source":
                workspace.get(
                    "detection_source"
                ),
        },
        record=record,
    )


def _application_name(
    value: Any,
) -> str:
    if isinstance(
        value,
        dict,
    ):
        for key in (
            "name",
            "process_name",
            "application",
            "title",
        ):
            text = _clean_text(
                value.get(
                    key
                )
            )

            if text:
                return text

        return ""

    return _clean_text(
        value
    )


def _project_workspace_active(
    record: WorldStateRecord,
):
    value = record.value

    if not isinstance(
        value,
        dict,
    ):
        return [], []

    entity = _workspace_entity(
        value,
        record,
    )

    if entity is None:
        return [], []

    return [
        entity,
    ], []


def _project_workspace_open(
    record: WorldStateRecord,
):
    value = record.value

    if not isinstance(
        value,
        list,
    ):
        return [], []

    entities = []

    for workspace in value:
        if not isinstance(
            workspace,
            dict,
        ):
            continue

        entity = _workspace_entity(
            workspace,
            record,
        )

        if entity is not None:
            entities.append(
                entity
            )

    return entities, []


def _project_active_application(
    record: WorldStateRecord,
):
    name = _application_name(
        record.value
    )

    if not name:
        return [], []

    application = _entity(
        entity_id=_stable_id(
            "application",
            name,
        ),
        entity_type="application",
        name=name,
        attributes={
            "active":
                True,
            "raw":
                record.value,
        },
        record=record,
    )

    return [
        application,
    ], []


def _project_active_window(
    record: WorldStateRecord,
):
    title = _clean_text(
        record.value
    )

    if not title:
        return [], []

    window = _entity(
        entity_id=_stable_id(
            "window",
            title,
        ),
        entity_type="window",
        name=title,
        attributes={
            "title":
                title,
            "active":
                True,
        },
        record=record,
    )

    return [
        window,
    ], []


def _project_active_file(
    record: WorldStateRecord,
):
    path = _clean_text(
        record.value
    )

    if not path:
        return [], []

    file_entity = _entity(
        entity_id=_stable_id(
            "file",
            path,
        ),
        entity_type="file",
        name=(
            Path(
                path
            ).name
            or path
        ),
        attributes={
            "path":
                path,
            "active":
                True,
        },
        record=record,
    )

    return [
        file_entity,
    ], []


def _project_visible_applications(
    record: WorldStateRecord,
):
    value = record.value

    if not isinstance(
        value,
        list,
    ):
        return [], []

    entities = []

    for item in value:
        name = _application_name(
            item
        )

        if not name:
            continue

        entities.append(
            _entity(
                entity_id=_stable_id(
                    "application",
                    name,
                ),
                entity_type="application",
                name=name,
                attributes={
                    "visible":
                        True,
                    "raw":
                        item,
                },
                record=record,
            )
        )

    return entities, []


def _project_system_snapshot(
    record: WorldStateRecord,
):
    if not isinstance(
        record.value,
        dict,
    ):
        return [], []

    return [
        _entity(
            entity_id="computer:primary",
            entity_type="computer",
            name="Primary computer",
            attributes={
                "system_snapshot":
                    record.value,
            },
            record=record,
        )
    ], []


def _project_location(
    record: WorldStateRecord,
):
    if not isinstance(
        record.value,
        dict,
    ):
        return [], []

    value = record.value

    name = (
        _clean_text(
            value.get(
                "label"
            )
        )
        or _clean_text(
            value.get(
                "city"
            )
        )
        or "Current location"
    )

    return [
        _entity(
            entity_id="location:current",
            entity_type="location",
            name=name,
            attributes=value,
            record=record,
        )
    ], []


def _project_integration(
    record: WorldStateRecord,
):
    capability = (
        record.key[
            len(
                "integration."
            ):
        ]
    )

    if not capability:
        return [], []

    return [
        _entity(
            entity_id=_stable_id(
                "integration_state",
                capability,
            ),
            entity_type="integration_state",
            name=capability,
            attributes={
                "capability":
                    capability,
                "data":
                    record.value,
            },
            record=record,
        )
    ], []


def project_world_state_record(
    record: WorldStateRecord,
):
    """
    Pure projection for one existing WorldStateRecord.

    Returns:
        (entities, relations)
    """

    if not isinstance(
        record,
        WorldStateRecord,
    ):
        raise TypeError(
            "record must be a WorldStateRecord."
        )

    handlers = {
        "workspace.active":
            _project_workspace_active,
        "workspace.open":
            _project_workspace_open,
        "computer.active_application":
            _project_active_application,
        "computer.active_window":
            _project_active_window,
        "computer.active_file":
            _project_active_file,
        "computer.visible_applications":
            _project_visible_applications,
        "system.snapshot":
            _project_system_snapshot,
        "location.current":
            _project_location,
    }

    handler = handlers.get(
        record.key
    )

    if handler is not None:
        return handler(
            record
        )

    if record.key.startswith(
        "integration."
    ):
        return _project_integration(
            record
        )

    return [], []


def _add_context_relations(
    entities: list[WorldEntity],
    relations: list[WorldRelation],
    records: dict[str, WorldStateRecord],
):
    by_type: dict[
        str,
        list[WorldEntity],
    ] = {}

    for entity in entities:
        by_type.setdefault(
            entity.entity_type,
            [],
        ).append(
            entity
        )

    active_workspace = None

    for workspace in by_type.get(
        "workspace",
        [],
    ):
        if workspace.attributes.get(
            "active"
        ):
            active_workspace = workspace
            break

    active_application = None

    for application in by_type.get(
        "application",
        [],
    ):
        if application.attributes.get(
            "active"
        ):
            active_application = application
            break

    active_window = None

    for window in by_type.get(
        "window",
        [],
    ):
        if window.attributes.get(
            "active"
        ):
            active_window = window
            break

    active_file = None

    for file_entity in by_type.get(
        "file",
        [],
    ):
        if file_entity.attributes.get(
            "active"
        ):
            active_file = file_entity
            break

    computer = next(
        iter(
            by_type.get(
                "computer",
                [],
            )
        ),
        None,
    )

    def source_record(
        *keys: str,
    ):
        for key in keys:
            record = records.get(
                key
            )
            if record is not None:
                return record
        return None

    if (
        active_workspace is not None
        and active_application is not None
    ):
        record = source_record(
            "workspace.active",
            "computer.active_application",
        )

        if record is not None:
            relations.append(
                _relation(
                    subject_id=active_workspace.entity_id,
                    predicate="open_in",
                    object_id=active_application.entity_id,
                    record=record,
                )
            )

    if (
        active_file is not None
        and active_workspace is not None
    ):
        workspace_path = _clean_text(
            active_workspace.attributes.get(
                "workspace_path"
            )
        )

        file_path = _clean_text(
            active_file.attributes.get(
                "path"
            )
        )

        belongs = False

        if (
            workspace_path
            and file_path
        ):
            try:
                belongs = (
                    Path(
                        file_path
                    ).resolve()
                    .is_relative_to(
                        Path(
                            workspace_path
                        ).resolve()
                    )
                )
            except (
                OSError,
                ValueError,
            ):
                belongs = (
                    file_path.lower()
                    .startswith(
                        workspace_path
                        .rstrip(
                            "\\/"
                        )
                        .lower()
                        + "\\"
                    )
                )

        if belongs:
            record = source_record(
                "computer.active_file",
                "workspace.active",
            )

            if record is not None:
                relations.append(
                    _relation(
                        subject_id=active_file.entity_id,
                        predicate="belongs_to",
                        object_id=active_workspace.entity_id,
                        record=record,
                    )
                )

    if (
        active_window is not None
        and active_application is not None
    ):
        record = source_record(
            "computer.active_window",
            "computer.active_application",
        )

        if record is not None:
            relations.append(
                _relation(
                    subject_id=active_window.entity_id,
                    predicate="belongs_to",
                    object_id=active_application.entity_id,
                    record=record,
                )
            )

    if (
        computer is not None
        and active_application is not None
    ):
        record = source_record(
            "computer.active_application",
            "system.snapshot",
        )

        if record is not None:
            relations.append(
                _relation(
                    subject_id=computer.entity_id,
                    predicate="foreground_application",
                    object_id=active_application.entity_id,
                    record=record,
                )
            )


def project_world_state_snapshot(
    records: dict[
        str,
        WorldStateRecord,
    ] | None = None,
):
    """
    Projects a snapshot without mutating WORLD_MODEL.

    If records is omitted, reads the existing Phase 16 operational RAM.
    """

    if records is None:
        records = (
            get_world_state_snapshot(
                include_stale=True
            )
        )

    if not isinstance(
        records,
        dict,
    ):
        raise TypeError(
            "records must be a dictionary."
        )

    entities_by_id: dict[
        str,
        WorldEntity,
    ] = {}
    relations_by_id: dict[
        str,
        WorldRelation,
    ] = {}

    supported_records = {
        key:
            record
        for key, record
        in records.items()
        if any(
            key.startswith(
                prefix
            )
            for prefix
            in SUPPORTED_PREFIXES
        )
    }

    for key in sorted(
        supported_records
    ):
        record = (
            supported_records[
                key
            ]
        )

        entities, relations = (
            project_world_state_record(
                record
            )
        )

        for entity in entities:
            existing = (
                entities_by_id.get(
                    entity.entity_id
                )
            )

            if existing is None:
                entities_by_id[
                    entity.entity_id
                ] = entity
                continue

            # One real-world entity may be observed by multiple Phase 16
            # records in the same snapshot. For example, the foreground
            # application can also appear in visible_applications. Do not
            # let a later projection pass erase useful attributes such as
            # active=True. Merge the observations deterministically while
            # preserving all provenance.
            existing_time = (
                existing.observed_at
            )
            incoming_time = (
                entity.observed_at
            )

            if incoming_time >= existing_time:
                primary = entity
                secondary = existing
            else:
                primary = existing
                secondary = entity

            merged_attributes = dict(
                secondary.attributes
            )
            merged_attributes.update(
                primary.attributes
            )

            # Boolean state flags are additive across simultaneous
            # observations: an application that is both visible and active
            # should retain both facts.
            for flag in (
                "active",
                "visible",
                "resolved",
            ):
                if (
                    secondary.attributes.get(
                        flag
                    )
                    is True
                    or primary.attributes.get(
                        flag
                    )
                    is True
                ):
                    merged_attributes[
                        flag
                    ] = True

            evidence_by_identity = {}

            for item in (
                *secondary.evidence,
                *primary.evidence,
            ):
                evidence_by_identity[
                    (
                        item.world_state_key,
                        item.source,
                        item.observed_at,
                        item.status,
                    )
                ] = item

            merged_evidence = tuple(
                evidence_by_identity[
                    key
                ]
                for key in sorted(
                    evidence_by_identity
                )
            )

            merged_metadata = dict(
                secondary.metadata
            )
            merged_metadata.update(
                primary.metadata
            )

            entities_by_id[
                entity.entity_id
            ] = WorldEntity(
                entity_id=primary.entity_id,
                entity_type=primary.entity_type,
                name=(
                    primary.name
                    or secondary.name
                ),
                attributes=merged_attributes,
                confidence=max(
                    secondary.confidence,
                    primary.confidence,
                ),
                observed_at=max(
                    existing_time,
                    incoming_time,
                ),
                updated_at=max(
                    existing.updated_at,
                    entity.updated_at,
                ),
                evidence=merged_evidence,
                metadata=merged_metadata,
            )

        for relation in relations:
            relations_by_id[
                relation.relation_id
            ] = relation

    entities = list(
        entities_by_id.values()
    )
    relations = list(
        relations_by_id.values()
    )

    _add_context_relations(
        entities,
        relations,
        supported_records,
    )

    relations_by_id = {
        relation.relation_id:
            relation
        for relation in relations
    }

    return {
        "entities":
            sorted(
                entities,
                key=lambda item:
                    item.entity_id,
            ),
        "relations":
            sorted(
                relations_by_id.values(),
                key=lambda item:
                    item.relation_id,
            ),
    }


def refresh_world_model_from_world_state(
    *,
    store: WorldModelStore = WORLD_MODEL,
    replace_projected: bool = True,
):
    """
    Applies the current Phase 16 snapshot to a WorldModelStore.

    17A.3 is snapshot-driven. Continuous event-driven synchronization is
    deliberately deferred to Phase 17A.7.
    """

    projected = (
        project_world_state_snapshot()
    )

    if replace_projected:
        projected_entity_ids = {
            entity.entity_id
            for entity
            in store.list_entities()
            if entity.metadata.get(
                "projection"
            )
            == "world_state"
        }

        for entity_id in (
            projected_entity_ids
        ):
            store.delete_entity(
                entity_id,
                cascade_relations=True,
            )

    store.add_entities(
        projected[
            "entities"
        ]
    )

    store.add_relations(
        projected[
            "relations"
        ]
    )

    return store.snapshot()


__all__ = [
    "SUPPORTED_PREFIXES",
    "project_world_state_record",
    "project_world_state_snapshot",
    "refresh_world_model_from_world_state",
]
