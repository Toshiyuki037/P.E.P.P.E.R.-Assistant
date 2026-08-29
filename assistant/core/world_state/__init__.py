"""
P.E.P.P.E.R. - World State

Shared live-state services used by deterministic routing, integrations,
and the Phase 16 executive runtime.
"""

from .core import (
    WORLD_STATE,
    WorldStateRecord,
    WorldStateStore,
    clear_world_state,
    delete_world_state,
    get_world_state,
    get_world_state_snapshot,
    get_world_state_snapshot_dict,
    get_world_state_value,
    set_world_state,
)

from .location import (
    LocationState,
    get_current_location,
    get_foreground_location,
    get_last_known_location,
    refresh_current_location,
    request_location_refresh_in_background,
)


__all__ = [
    "WORLD_STATE",
    "WorldStateRecord",
    "WorldStateStore",
    "clear_world_state",
    "delete_world_state",
    "get_world_state",
    "get_world_state_snapshot",
    "get_world_state_snapshot_dict",
    "get_world_state_value",
    "set_world_state",
    "LocationState",
    "get_current_location",
    "get_foreground_location",
    "get_last_known_location",
    "refresh_current_location",
    "request_location_refresh_in_background",
]
