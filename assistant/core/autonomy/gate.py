"""
P.E.P.P.E.R. Autonomy Gate
Phase 16I.3 - 16I.5

Single deterministic gate for autonomy/security decisions.
This layer does not replace existing approval checks; it adds a reusable
policy boundary for Phase 16 execution paths.
"""

from __future__ import annotations

from dataclasses import replace

from assistant.core.events import publish
from assistant.core.events.definitions import (
    AUTONOMY_ALLOWED,
    AUTONOMY_BLOCKED,
    AUTONOMY_APPROVAL_REQUIRED,
)

from .models import AutonomyDecision, AutonomyRequest
from .policy import AUTONOMY_POLICY, AutonomyPolicy


class AutonomyGate:
    def __init__(
        self,
        *,
        policy: AutonomyPolicy = AUTONOMY_POLICY,
    ):
        self.policy = policy

    def evaluate(
        self,
        request: AutonomyRequest,
    ) -> AutonomyDecision:
        decision = self.policy.evaluate(request)

        payload = {
            "action": request.action,
            "category": request.category,
            "allowed": decision.allowed,
            "requires_approval": decision.requires_approval,
            "risk_level": decision.risk_level,
            "reason": decision.reason,
            "background": request.background,
            "source": request.source,
        }

        if decision.allowed:
            topic = AUTONOMY_ALLOWED
        elif decision.requires_approval:
            topic = AUTONOMY_APPROVAL_REQUIRED
        else:
            topic = AUTONOMY_BLOCKED

        publish(
            topic,
            payload,
            source="assistant.core.autonomy",
        )

        return decision

    def require_allowed(
        self,
        request: AutonomyRequest,
    ) -> AutonomyDecision:
        decision = self.evaluate(request)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        return decision

    def with_approval(
        self,
        request: AutonomyRequest,
    ) -> AutonomyRequest:
        return replace(
            request,
            approval_granted=True,
        )


AUTONOMY_GATE = AutonomyGate()
