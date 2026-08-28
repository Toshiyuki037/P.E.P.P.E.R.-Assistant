"""
P.E.P.P.E.R. Recovery Policy
Phase 16H.3

Recovery is bounded and opt-in.
There are no automatic infinite retries.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryDecision:
    allowed: bool
    reason: str


class RecoveryPolicy:
    def __init__(
        self,
        *,
        max_attempts: int = 1,
    ):
        self.max_attempts = max(0, int(max_attempts))

    def evaluate(
        self,
        *,
        recovery_handler_name: str | None,
        attempt: int,
    ) -> RecoveryDecision:
        if not recovery_handler_name:
            return RecoveryDecision(
                allowed=False,
                reason="no recovery handler configured",
            )

        if attempt >= self.max_attempts:
            return RecoveryDecision(
                allowed=False,
                reason="recovery attempt budget exhausted",
            )

        return RecoveryDecision(
            allowed=True,
            reason="bounded recovery allowed",
        )
