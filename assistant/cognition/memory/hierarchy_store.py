"""
P.E.P.P.E.R. Phase 17B - Persistent Hierarchical Memory Store

Adds Phase 17B tables to the existing memory SQLite database without altering
the legacy Phase 4/16 memory tables.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Callable
import json
import sqlite3
import threading

from .hierarchy_models import MemoryRecord, utc_now_iso


CREATE_RECORDS = """
CREATE TABLE IF NOT EXISTS memory_hierarchy_v2 (
    memory_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    layer TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    category TEXT NOT NULL,
    subject TEXT,
    project TEXT,
    source TEXT NOT NULL,
    confidence REAL NOT NULL,
    importance INTEGER NOT NULL,
    permanence INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_accessed_at TEXT,
    expires_at TEXT,
    supersedes_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
)
"""

CREATE_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_memory_hierarchy_layer ON memory_hierarchy_v2(layer)",
    "CREATE INDEX IF NOT EXISTS idx_memory_hierarchy_status ON memory_hierarchy_v2(status)",
    "CREATE INDEX IF NOT EXISTS idx_memory_hierarchy_subject ON memory_hierarchy_v2(subject)",
    "CREATE INDEX IF NOT EXISTS idx_memory_hierarchy_project ON memory_hierarchy_v2(project)",
    "CREATE INDEX IF NOT EXISTS idx_memory_hierarchy_updated ON memory_hierarchy_v2(updated_at)",
)


def _default_connection():
    from .database import get_connection
    return get_connection()


class HierarchicalMemoryStore:
    def __init__(self, connection_factory: Callable[[], sqlite3.Connection] | None = None):
        self._connection_factory = connection_factory or _default_connection
        self._lock = threading.RLock()
        self._initialized = False

    def _connect(self):
        conn = self._connection_factory()
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self):
        with self._lock:
            if self._initialized:
                return
            with self._connect() as conn:
                conn.execute(CREATE_RECORDS)
                for statement in CREATE_INDEXES:
                    conn.execute(statement)
            self._initialized = True

    def _row_to_record(self, row) -> MemoryRecord:
        return MemoryRecord(
            memory_id=row["memory_id"],
            content=row["content"],
            layer=row["layer"],
            kind=row["kind"],
            status=row["status"],
            category=row["category"],
            subject=row["subject"],
            project=row["project"],
            source=row["source"],
            confidence=row["confidence"],
            importance=row["importance"],
            permanence=row["permanence"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_accessed_at=row["last_accessed_at"],
            expires_at=row["expires_at"],
            supersedes_id=row["supersedes_id"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def upsert(self, record: MemoryRecord) -> MemoryRecord:
        self.initialize()
        payload = record.to_dict()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_hierarchy_v2 (
                    memory_id, content, layer, kind, status, category,
                    subject, project, source, confidence, importance,
                    permanence, created_at, updated_at, last_accessed_at,
                    expires_at, supersedes_id, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    content=excluded.content,
                    layer=excluded.layer,
                    kind=excluded.kind,
                    status=excluded.status,
                    category=excluded.category,
                    subject=excluded.subject,
                    project=excluded.project,
                    source=excluded.source,
                    confidence=excluded.confidence,
                    importance=excluded.importance,
                    permanence=excluded.permanence,
                    updated_at=excluded.updated_at,
                    last_accessed_at=excluded.last_accessed_at,
                    expires_at=excluded.expires_at,
                    supersedes_id=excluded.supersedes_id,
                    metadata_json=excluded.metadata_json
                """,
                (
                    payload["memory_id"], payload["content"], payload["layer"],
                    payload["kind"], payload["status"], payload["category"],
                    payload["subject"], payload["project"], payload["source"],
                    payload["confidence"], payload["importance"], payload["permanence"],
                    payload["created_at"], payload["updated_at"],
                    payload["last_accessed_at"], payload["expires_at"],
                    payload["supersedes_id"], json.dumps(payload["metadata"], sort_keys=True),
                ),
            )
        return MemoryRecord.from_dict(payload)

    def get(self, memory_id: str) -> MemoryRecord | None:
        self.initialize()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM memory_hierarchy_v2 WHERE memory_id = ?",
                (str(memory_id).strip().lower(),),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def list(
        self,
        *,
        layer: str | None = None,
        status: str | None = "active",
        subject: str | None = None,
        project: str | None = None,
        limit: int = 250,
    ) -> list[MemoryRecord]:
        self.initialize()
        clauses = []
        args = []

        if layer:
            clauses.append("layer = ?")
            args.append(str(layer).strip().lower())
        if status:
            clauses.append("status = ?")
            args.append(str(status).strip().lower())
        if subject:
            clauses.append("subject = ?")
            args.append(str(subject).strip())
        if project:
            clauses.append("project = ?")
            args.append(str(project).strip())

        sql = "SELECT * FROM memory_hierarchy_v2"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY updated_at DESC, memory_id ASC LIMIT ?"
        args.append(max(1, int(limit)))

        with self._lock, self._connect() as conn:
            rows = conn.execute(sql, tuple(args)).fetchall()
        return [self._row_to_record(row) for row in rows]

    def set_status(
        self,
        memory_id: str,
        status: str,
        *,
        superseded_by: str | None = None,
    ) -> MemoryRecord | None:
        current = self.get(memory_id)
        if current is None:
            return None

        metadata = deepcopy(current.metadata)
        if superseded_by:
            metadata["superseded_by"] = str(superseded_by).strip().lower()

        updated = MemoryRecord(
            **{
                **current.to_dict(),
                "status": status,
                "updated_at": utc_now_iso(),
                "metadata": metadata,
            }
        )
        return self.upsert(updated)

    def touch(self, memory_id: str) -> None:
        self.initialize()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE memory_hierarchy_v2
                SET last_accessed_at = ?
                WHERE memory_id = ?
                """,
                (utc_now_iso(), str(memory_id).strip().lower()),
            )

    def delete_all_for_tests(self):
        self.initialize()
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM memory_hierarchy_v2")


HIERARCHICAL_MEMORY_STORE = HierarchicalMemoryStore()
