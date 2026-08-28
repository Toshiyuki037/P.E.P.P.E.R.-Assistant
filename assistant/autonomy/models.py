"""
P.E.P.P.E.R. Autonomy Models
Phase 16I.1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AutonomyRequest:
    action: str
    category: str = "unknown"
    read_only: bool = False
    external_side_effect: bool = False
    destructive: bool = False
    approval_granted: bool = False
    background: bool = False
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AutonomyDecision:
    allowed: bool
    requires_approval: bool
    reason: str
    risk_level: str
    request: AutonomyRequest
