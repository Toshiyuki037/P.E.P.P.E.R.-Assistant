"""
P.E.P.P.E.R. Core Event Definitions
Phase 16D + 16E
"""

from __future__ import annotations

WORLD_STATE_CHANGED = "world_state.changed"
WORLD_STATE_DELETED = "world_state.deleted"
WORLD_STATE_CLEARED = "world_state.cleared"

INTEGRATION_UPDATED = "integration.updated"
INTEGRATION_FAILED = "integration.failed"

RUNTIME_CONTEXT_BUILT = "runtime.context_built"
RUNTIME_REQUEST_COMPLETED = "runtime.request_completed"

GOAL_CREATED = "goal.created"
GOAL_UPDATED = "goal.updated"
GOAL_COMPLETED = "goal.completed"

TASK_CREATED = "task.created"
TASK_UPDATED = "task.updated"
TASK_STARTED = "task.started"
TASK_COMPLETED = "task.completed"
TASK_FAILED = "task.failed"
TASK_CANCELLED = "task.cancelled"

CORE_EVENT_TOPICS = frozenset({
    WORLD_STATE_CHANGED,
    WORLD_STATE_DELETED,
    WORLD_STATE_CLEARED,
    INTEGRATION_UPDATED,
    INTEGRATION_FAILED,
    RUNTIME_CONTEXT_BUILT,
    RUNTIME_REQUEST_COMPLETED,
    GOAL_CREATED,
    GOAL_UPDATED,
    GOAL_COMPLETED,
    TASK_CREATED,
    TASK_UPDATED,
    TASK_STARTED,
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_CANCELLED,
})
