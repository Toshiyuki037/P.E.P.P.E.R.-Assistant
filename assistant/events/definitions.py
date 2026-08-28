"""
P.E.P.P.E.R. Core Event Definitions
Phase 16D.2
"""

from __future__ import annotations

WORLD_STATE_CHANGED = "world_state.changed"
WORLD_STATE_DELETED = "world_state.deleted"
WORLD_STATE_CLEARED = "world_state.cleared"

INTEGRATION_UPDATED = "integration.updated"
INTEGRATION_FAILED = "integration.failed"

RUNTIME_CONTEXT_BUILT = "runtime.context_built"
RUNTIME_REQUEST_COMPLETED = "runtime.request_completed"

CORE_EVENT_TOPICS = frozenset({
    WORLD_STATE_CHANGED,
    WORLD_STATE_DELETED,
    WORLD_STATE_CLEARED,
    INTEGRATION_UPDATED,
    INTEGRATION_FAILED,
    RUNTIME_CONTEXT_BUILT,
    RUNTIME_REQUEST_COMPLETED,
})
