"""
P.E.P.P.E.R. - Apple Bridge Provider Registration

Created: August 10, 2026
Author: Max Maehara

Phase:
    Phase 9H
"""

from __future__ import annotations

from assistant.capabilities.integrations.registry import (
    register_integration_capability,
)

from .client import (
    apple_bridge_health,
)


# ---------------------------------------------------------------------------
# Health Capability
# ---------------------------------------------------------------------------

def apple_bridge_status(
    account_id: str | None = None,
):
    """
    Returns bridge health information.

    account_id is accepted for compatibility with Phase 9 account
    routing but is not required by the local bridge itself.
    """

    return apple_bridge_health()


# ---------------------------------------------------------------------------
# Provider Registration
# ---------------------------------------------------------------------------

def load_apple_bridge_provider():

    register_integration_capability(
        provider=
            "apple_bridge",

        name=
            "device.bridge_status",

        function=
            apple_bridge_status,

        risk=
            "low",

        sensitivity=
            "personal",

        description=(
            "Checks whether P.E.P.P.E.R.'s trusted Apple bridge is available."
        ),
    )