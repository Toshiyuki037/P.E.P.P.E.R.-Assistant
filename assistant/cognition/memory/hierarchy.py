"""
P.E.P.P.E.R. Phase 17B - Hierarchical / Consolidating Memory

Layered recall across:
- working memory
- recent episodic memory
- project memory
- long-term semantic memory
- relationship/preference memory

The existing semantic memory system remains authoritative and is consumed as a
legacy long-term source rather than replaced.
"""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import hashlib
import math
import re
import threading
from typing import Any

from .hierarchy_models import (
    MemoryQueryResult,
    MemoryRecord,
    utc_now_iso,
)
from .hierarchy_store import (
    HIERARCHICAL_MEMORY_STORE,
    HierarchicalMemoryStore,
)


_TOKEN_RE = re.compile(r"[a-z0-9_'-]+", re.I)

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but",
    "by", "can", "could", "did", "do", "does", "for", "from", "had",
    "has", "have", "he", "her", "here", "hers", "him", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "me", "my", "of",
    "on", "or", "our", "ours", "she", "so", "that", "the", "their",
    "theirs", "them", "then", "there", "these", "they", "this", "those",
    "to", "too", "up", "us", "was", "we", "were", "what", "when",
    "where", "which", "who", "why", "will", "with", "would", "you",
    "your", "yours",
}


_LAYER_WEIGHT = {
    "working": 1.00,
    "recent_episodic": 0.92,
    "project": 0.95,
    "relationship": 0.96,
    "long_term_semantic": 0.86,
}

_KIND_WEIGHT = {
    "preference": 1.00,
    "decision": 0.98,
    "commitment": 0.98,
    "goal": 0.96,
    "fact": 0.94,
    "event": 0.90,
    "temporary": 0.84,
    "assumption": 0.70,
}

_RELATIONSHIP_MARKERS = (
    "prefer", "preference", "likes", "dislikes", "call me",
    "from now on", "always", "never", "verbosity", "style",
)

_PROJECT_MARKERS = (
    "project", "repo", "repository", "research", "application",
    "phase", "branch", "workspace", "prototype", "codebase",
)


def _normalize_token(token: str) -> str:
    token = str(token or "").strip().lower()
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def _tokens(text: str) -> set[str]:
    tokens = set()
    for match in _TOKEN_RE.finditer(str(text or "")):
        raw = match.group(0).lower()
        if len(raw) <= 1 or raw in _STOPWORDS:
            continue
        token = _normalize_token(raw)
        if token and token not in _STOPWORDS:
            tokens.add(token)
    return tokens


def _lexical_score(query: str, content: str) -> float:
    q = _tokens(query)
    c = _tokens(content)
    if not q or not c:
        return 0.0
    overlap = len(q & c)
    return overlap / math.sqrt(len(q) * len(c))


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_expired(record: MemoryRecord, now: datetime | None = None) -> bool:
    if record.status != "active":
        return True
    if not record.expires_at:
        return False
    expiry = _parse_time(record.expires_at)
    if expiry is None:
        return False
    now = now or datetime.now(timezone.utc)
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry <= now


def _stable_id(prefix: str, *parts: Any) -> str:
    material = "|".join(str(part or "").strip().lower() for part in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}:{digest}"


def infer_kind(content: str, category: str = "general") -> str:
    text = f"{category} {content}".lower()

    if any(word in text for word in ("prefer", "preference", "i like", "i dislike")):
        return "preference"
    if any(word in text for word in ("decided", "decision", "we will", "we're going to")):
        return "decision"
    if any(word in text for word in ("must", "commitment", "promised", "deadline")):
        return "commitment"
    if any(word in text for word in ("goal", "target", "objective", "aim")):
        return "goal"
    if any(word in text for word in ("maybe", "probably", "likely", "assume", "assumption")):
        return "assumption"
    if any(word in text for word in ("temporary", "for now", "today only", "this session")):
        return "temporary"
    return "fact"


def infer_layer(
    content: str,
    *,
    category: str = "general",
    project: str | None = None,
    kind: str | None = None,
) -> str:
    text = f"{category} {content}".lower()
    resolved_kind = kind or infer_kind(content, category)

    if resolved_kind == "preference" or any(marker in text for marker in _RELATIONSHIP_MARKERS):
        return "relationship"
    if project or any(marker in text for marker in _PROJECT_MARKERS):
        return "project"
    return "long_term_semantic"


class WorkingMemory:
    def __init__(self, max_items: int = 24):
        self._items = deque(maxlen=max(1, int(max_items)))
        self._lock = threading.RLock()

    def remember(
        self,
        content: str,
        *,
        kind: str = "temporary",
        category: str = "working",
        source: str = "runtime",
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        now = utc_now_iso()
        record = MemoryRecord(
            memory_id=_stable_id("working", now, content),
            content=content,
            layer="working",
            kind=kind,
            category=category,
            source=source,
            confidence=confidence,
            importance=30,
            permanence=0,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        with self._lock:
            self._items.append(record)
        return record

    def list(self) -> list[MemoryRecord]:
        with self._lock:
            return [MemoryRecord.from_dict(item.to_dict()) for item in self._items]

    def clear(self):
        with self._lock:
            self._items.clear()


WORKING_MEMORY = WorkingMemory()


def remember_structured(
    content: str,
    *,
    layer: str | None = None,
    kind: str | None = None,
    category: str = "general",
    subject: str | None = None,
    project: str | None = None,
    source: str = "phase17b",
    confidence: float = 1.0,
    importance: int = 50,
    permanence: int = 50,
    expires_at: str | None = None,
    supersede_prior: bool = False,
    metadata: dict[str, Any] | None = None,
    store: HierarchicalMemoryStore = HIERARCHICAL_MEMORY_STORE,
) -> MemoryRecord:
    resolved_kind = kind or infer_kind(content, category)
    resolved_layer = layer or infer_layer(
        content,
        category=category,
        project=project,
        kind=resolved_kind,
    )
    now = utc_now_iso()

    prior = None
    if supersede_prior and subject:
        candidates = store.list(
            layer=resolved_layer,
            status="active",
            subject=subject,
            project=project,
            limit=50,
        )
        candidates = [item for item in candidates if item.kind == resolved_kind]
        if candidates:
            prior = candidates[0]

    record = MemoryRecord(
        memory_id=_stable_id("memory", now, content, subject, project),
        content=content,
        layer=resolved_layer,
        kind=resolved_kind,
        category=category,
        subject=subject,
        project=project,
        source=source,
        confidence=confidence,
        importance=importance,
        permanence=permanence,
        created_at=now,
        updated_at=now,
        expires_at=expires_at,
        supersedes_id=prior.memory_id if prior else None,
        metadata=metadata or {},
    )
    store.upsert(record)

    if prior:
        store.set_status(
            prior.memory_id,
            "superseded",
            superseded_by=record.memory_id,
        )

    return record


def _legacy_memories_fast(query: str, limit: int) -> list[dict[str, Any]]:
    """Low-latency legacy-memory projection from the existing SQLite table."""
    try:
        import sqlite3
        from .database import get_connection

        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='memories'"
            ).fetchone()
            if table is None:
                return []

            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(memories)").fetchall()
            }
            if "content" not in columns:
                return []

            selected = [
                name for name in (
                    "id", "content", "category", "importance", "permanence",
                    "confidence", "source", "project", "subject",
                    "created_at", "updated_at", "status", "active", "archived_at",
                )
                if name in columns
            ]

            sql = "SELECT " + ", ".join(selected) + " FROM memories"
            clauses = []
            if "status" in columns:
                clauses.append("(status IS NULL OR lower(status) IN ('active','current'))")
            if "active" in columns:
                clauses.append("(active IS NULL OR active = 1)")
            if "archived_at" in columns:
                clauses.append("archived_at IS NULL")
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)
            if "id" in columns:
                sql += " ORDER BY id DESC"
            sql += " LIMIT 1000"
            rows = conn.execute(sql).fetchall()

        query_tokens = _tokens(query)
        ranked = []
        for row in rows:
            memory = dict(row)
            content = str(memory.get("content") or "").strip()
            if not content:
                continue

            lexical = _lexical_score(query, content)
            category = str(memory.get("category") or "general")
            category_overlap = query_tokens & _tokens(category)
            if lexical <= 0.0 and not category_overlap:
                continue

            importance = float(memory.get("importance") or 50)
            permanence = float(memory.get("permanence") or 50)
            confidence = float(memory.get("confidence") or 100)
            if confidence > 1.0:
                confidence /= 100.0
            confidence = min(1.0, max(0.0, confidence))

            score = (
                lexical * 0.72
                + min(1.0, importance / 100.0) * 0.08
                + min(1.0, permanence / 100.0) * 0.06
                + confidence * 0.08
                + (0.06 if category_overlap else 0.0)
            )
            ranked.append((score, memory))

        ranked.sort(
            key=lambda item: (
                -item[0],
                -(int(item[1].get("id") or 0)
                  if str(item[1].get("id") or "").isdigit()
                  else 0),
            )
        )
        return [memory for _, memory in ranked[:max(1, int(limit))]]

    except Exception as error:
        print(f"[Phase 17B Memory Warning] fast legacy retrieval unavailable: {error}")
        return []


def _legacy_memories_semantic(query: str, limit: int) -> list[dict[str, Any]]:
    """Explicit compatibility path for heavyweight semantic legacy retrieval."""
    try:
        from .retriever import retrieve_memories
        return list(retrieve_memories(query=query, limit=limit) or [])
    except Exception as error:
        print(f"[Phase 17B Memory Warning] semantic legacy retrieval unavailable: {error}")
        return []


def _recent_conversations(limit: int) -> list[tuple[str, str]]:
    try:
        from .database import get_recent_conversations
        return list(get_recent_conversations(limit=limit) or [])
    except Exception as error:
        print(f"[Phase 17B Memory Warning] episodic retrieval unavailable: {error}")
        return []


def _structured_candidates(
    query: str,
    *,
    store: HierarchicalMemoryStore,
    limit: int,
    project: str | None,
) -> list[MemoryQueryResult]:
    now = datetime.now(timezone.utc)
    results = []

    for record in store.list(status="active", limit=max(100, limit * 10)):
        if _is_expired(record, now):
            continue

        lexical = _lexical_score(query, record.content)
        query_tokens = _tokens(query)

        relation_bonus = 0.0
        if record.subject and _tokens(record.subject) & query_tokens:
            relation_bonus += 0.14
        if project and record.project and project.lower() == record.project.lower():
            relation_bonus += 0.18

        score = (
            lexical * 0.58
            + _LAYER_WEIGHT.get(record.layer, 0.8) * 0.14
            + _KIND_WEIGHT.get(record.kind, 0.8) * 0.10
            + record.confidence * 0.08
            + (record.importance / 100.0) * 0.05
            + (record.permanence / 100.0) * 0.05
            + relation_bonus
        )

        if lexical <= 0.0 and relation_bonus <= 0.0:
            continue

        results.append(
            MemoryQueryResult(
                record=record,
                score=score,
                reasons=("structured", record.layer, record.kind),
            )
        )

    results.sort(
        key=lambda item: (
            -item.score,
            item.record.memory_id,
        )
    )
    return results[:limit]


def _working_candidates(query: str, limit: int) -> list[MemoryQueryResult]:
    results = []
    for record in WORKING_MEMORY.list():
        lexical = _lexical_score(query, record.content)
        if lexical <= 0.0:
            continue
        results.append(
            MemoryQueryResult(
                record=record,
                score=0.60 + lexical * 0.40,
                reasons=("working",),
            )
        )
    results.sort(key=lambda item: (-item.score, item.record.memory_id))
    return results[:limit]


def _episodic_candidates(
    query: str,
    conversations: list[tuple[str, str]],
    limit: int,
) -> list[MemoryQueryResult]:
    scored = []
    total = len(conversations)

    for index, item in enumerate(conversations):
        if not isinstance(item, (tuple, list)) or len(item) < 2:
            continue
        user_text = str(item[0] or "").strip()
        response = str(item[1] or "").strip()
        content = f"User: {user_text} P.E.P.P.E.R.: {response}".strip()
        lexical = _lexical_score(query, content)
        shared_terms = _tokens(query) & _tokens(content)
        if lexical <= 0.0 or not shared_terms:
            continue

        recency = (index + 1) / max(1, total)
        now = utc_now_iso()
        record = MemoryRecord(
            memory_id=_stable_id("episode", user_text, response),
            content=content,
            layer="recent_episodic",
            kind="event",
            category="conversation",
            source="conversation_history",
            confidence=1.0,
            importance=40,
            permanence=10,
            created_at=now,
            updated_at=now,
            metadata={"conversation_index": index},
        )
        score = lexical * 0.72 + recency * 0.18 + 0.10
        scored.append(
            MemoryQueryResult(
                record=record,
                score=score,
                reasons=("recent_episodic", "conversation_history"),
            )
        )

    scored.sort(key=lambda item: (-item.score, item.record.memory_id))
    return scored[:limit]


def _legacy_candidates(
    query: str,
    memories: list[dict[str, Any]],
    limit: int,
) -> list[MemoryQueryResult]:
    results = []

    for memory in memories:
        content = str(memory.get("content") or "").strip()
        if not content:
            continue
        category = str(memory.get("category") or "general")
        kind = infer_kind(content, category)
        project = memory.get("project")
        layer = infer_layer(
            content,
            category=category,
            project=project,
            kind=kind,
        )
        confidence_raw = memory.get("confidence", 100)
        confidence = float(confidence_raw)
        if confidence > 1.0:
            confidence /= 100.0
        confidence = min(1.0, max(0.0, confidence))

        importance = int(memory.get("importance", 50) or 50)
        permanence = int(memory.get("permanence", 50) or 50)
        legacy_id = memory.get("id")

        record = MemoryRecord(
            memory_id=f"legacy:{legacy_id}" if legacy_id is not None else _stable_id("legacy", content),
            content=content,
            layer=layer,
            kind=kind,
            category=category,
            subject=memory.get("subject"),
            project=project,
            source=str(memory.get("source") or "legacy_memory"),
            confidence=confidence,
            importance=min(100, max(0, importance)),
            permanence=min(100, max(0, permanence)),
            created_at=str(memory.get("created_at") or utc_now_iso()),
            updated_at=str(memory.get("updated_at") or memory.get("created_at") or utc_now_iso()),
            metadata={
                "legacy_memory_id": legacy_id,
                "phase17b_projection": True,
            },
        )

        lexical = _lexical_score(query, content)
        score = (
            lexical * 0.64
            + _LAYER_WEIGHT.get(layer, 0.8) * 0.12
            + _KIND_WEIGHT.get(kind, 0.8) * 0.08
            + confidence * 0.08
            + (importance / 100.0) * 0.04
            + (permanence / 100.0) * 0.04
        )

        results.append(
            MemoryQueryResult(
                record=record,
                score=score,
                reasons=("legacy_semantic", layer, kind),
            )
        )

    results.sort(key=lambda item: (-item.score, item.record.memory_id))
    return results[:limit]


def retrieve_hierarchical_memory_records(
    query: str,
    limit: int = 8,
    *,
    project: str | None = None,
    store: HierarchicalMemoryStore = HIERARCHICAL_MEMORY_STORE,
    legacy_memories: list[dict[str, Any]] | None = None,
    recent_conversations: list[tuple[str, str]] | None = None,
    deep_legacy_semantic: bool = False,
) -> list[MemoryQueryResult]:
    query = str(query or "").strip()
    if not query:
        return []

    limit = max(1, int(limit))
    legacy = (
        (
            _legacy_memories_semantic(query, max(limit, 8))
            if deep_legacy_semantic
            else _legacy_memories_fast(query, max(limit, 8))
        )
        if legacy_memories is None
        else list(legacy_memories)
    )
    conversations = (
        _recent_conversations(max(10, limit * 2))
        if recent_conversations is None
        else list(recent_conversations)
    )

    candidates = []
    candidates.extend(_working_candidates(query, limit))
    candidates.extend(
        _structured_candidates(
            query,
            store=store,
            limit=limit,
            project=project,
        )
    )
    candidates.extend(
        _episodic_candidates(
            query,
            conversations,
            limit,
        )
    )
    candidates.extend(
        _legacy_candidates(
            query,
            legacy,
            limit,
        )
    )

    # Deduplicate by normalized content, preferring the stronger/higher layer score.
    best = {}
    for candidate in candidates:
        key = " ".join(candidate.record.content.lower().split())
        prior = best.get(key)
        if prior is None or candidate.score > prior.score:
            best[key] = candidate

    ranked = sorted(
        best.values(),
        key=lambda item: (
            -item.score,
            item.record.memory_id,
        ),
    )[:limit]

    for result in ranked:
        if not result.record.memory_id.startswith(("legacy:", "episode:", "working:")):
            try:
                store.touch(result.record.memory_id)
            except Exception:
                pass

    return ranked


def retrieve_hierarchical_memories(
    query: str,
    limit: int = 5,
    **kwargs,
) -> list[dict[str, Any]]:
    """
    Compatibility-shaped retrieval for assistant.brain.build_memory_context().

    Returns dictionaries containing the legacy keys `category` and `content`,
    plus Phase 17B provenance fields.
    """
    results = retrieve_hierarchical_memory_records(
        query=query,
        limit=limit,
        **kwargs,
    )

    output = []
    for result in results:
        record = result.record
        output.append(
            {
                "id": record.memory_id,
                "category": f"{record.layer}/{record.kind}/{record.category}",
                "content": record.content,
                "confidence": record.confidence,
                "importance": record.importance,
                "permanence": record.permanence,
                "_memory_layer": record.layer,
                "_memory_kind": record.kind,
                "_memory_status": record.status,
                "_memory_score": result.score,
                "_memory_reasons": list(result.reasons),
                "_memory_source": record.source,
                "_memory_project": record.project,
                "_memory_subject": record.subject,
            }
        )
    return output


def forget_structured(
    memory_id: str,
    *,
    store: HierarchicalMemoryStore = HIERARCHICAL_MEMORY_STORE,
) -> MemoryRecord | None:
    return store.set_status(memory_id, "forgotten")


def explain_memory(
    memory_id: str,
    *,
    store: HierarchicalMemoryStore = HIERARCHICAL_MEMORY_STORE,
) -> dict[str, Any] | None:
    record = store.get(memory_id)
    return record.to_dict() if record else None
