"""
P.E.P.P.E.R. - Location World-State Adapter

Phase 16B.2

Purpose:
    Bridges the existing Phase 16A location subsystem into the generalized
    Phase 16B operational RAM without changing location acquisition,
    persistence, trust, fallback, or planner behavior.

The existing location.py remains authoritative.
"""

from __future__ import annotations

from .core import (
    get_world_state,
    set_world_state,
)
from .location import (
    DEFAULT_FRESH_SECONDS,
    LocationState,
    get_foreground_location,
    get_last_known_location,
    refresh_current_location,
)


LOCATION_WORLD_STATE_KEY = (
    "location.current"
)


def _location_confidence(
    state: LocationState,
) -> float:
    """
    Conservative confidence derived from reported Windows accuracy.

    This does not change LocationState trust policy. It only gives the
    generalized world-state record a useful confidence value.
    """

    accuracy = state.accuracy_m

    if accuracy is None:
        return 0.75

    try:
        accuracy = float(
            accuracy
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0.75

    if accuracy <= 25:
        return 1.0

    if accuracy <= 100:
        return 0.95

    if accuracy <= 500:
        return 0.90

    if accuracy <= 1_000:
        return 0.80

    return 0.70


def publish_location_state(
    state: LocationState | None,
    *,
    fresh_for_seconds: float = DEFAULT_FRESH_SECONDS,
):
    """
    Publishes one already-trusted LocationState into operational RAM.

    No location lookup occurs here.
    """

    if (
        state is None
        or not state.is_trusted()
    ):
        return None

    return set_world_state(
        LOCATION_WORLD_STATE_KEY,
        state.to_dict(),
        source=(
            state.source
            or "location"
        ),
        fresh_for_seconds=(
            fresh_for_seconds
        ),
        confidence=(
            _location_confidence(
                state
            )
        ),
        metadata={
            "producer":
                "assistant.core.world_state.location",

            "captured_at":
                state.captured_at,

            "accuracy_m":
                state.accuracy_m,
        },
        updated_at=state.captured_at,
    )


def sync_cached_location_to_world_state(
    *,
    fresh_for_seconds: float = DEFAULT_FRESH_SECONDS,
):
    """
    Copies the existing trusted location cache into operational RAM.

    This may read the existing local location cache, but it never performs
    a blocking Windows location request.
    """

    state = get_last_known_location()

    if state is None:
        return None

    publish_location_state(
        state,
        fresh_for_seconds=(
            fresh_for_seconds
        ),
    )

    return state


def get_world_location(
    *,
    require_fresh: bool = False,
):
    """
    Reads the generalized RAM record without invoking a location provider.
    """

    return get_world_state(
        LOCATION_WORLD_STATE_KEY,
        require_fresh=require_fresh,
    )


def get_foreground_location_with_world_state(
    *,
    fresh_seconds: float = DEFAULT_FRESH_SECONDS,
    max_cached_age_seconds: float | None = None,
) -> LocationState | None:
    """
    Compatibility wrapper around the existing nonblocking foreground lookup.

    Existing location behavior is preserved; a returned trusted state is also
    published into generalized operational RAM.
    """

    kwargs = {
        "fresh_seconds":
            fresh_seconds,
    }

    if max_cached_age_seconds is not None:
        kwargs[
            "max_cached_age_seconds"
        ] = max_cached_age_seconds

    state = get_foreground_location(
        **kwargs
    )

    if state is not None:
        publish_location_state(
            state,
            fresh_for_seconds=(
                fresh_seconds
            ),
        )

    return state


def refresh_location_with_world_state():
    """
    Uses the existing blocking refresh path, then publishes a successful fix.

    Intended for explicit refresh/background producer use, not latency-sensitive
    foreground request routing.
    """

    state = refresh_current_location()

    if state is not None:
        publish_location_state(
            state
        )

    return state


# ---------------------------------------------------------------------------
# Standalone Diagnostic
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    state = sync_cached_location_to_world_state()

    print(
        "P.E.P.P.E.R. Location -> World State Adapter"
    )

    print(
        "------------------------------------------"
    )

    if state is None:
        print(
            "No trusted cached location available."
        )
    else:
        record = get_world_location()

        print(
            (
                record.to_dict()
                if record is not None
                else "Location was not published."
            )
        )
