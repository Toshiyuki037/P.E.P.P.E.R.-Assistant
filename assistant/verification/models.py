"""
P.E.P.P.E.R. Verification Models
Phase 16H.1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class VerificationResult:
    verified: bool
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(
        cls,
        reason: str = "verified",
        *,
        metadata: dict[str, Any] | None = None,
    ) -> "VerificationResult":
        return cls(
            verified=True,
            reason=str(reason or "verified"),
            metadata=dict(metadata or {}),
        )

    @classmethod
    def failure(
        cls,
        reason: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> "VerificationResult":
        return cls(
            verified=False,
            reason=str(reason or "verification failed"),
            metadata=dict(metadata or {}),
        )
