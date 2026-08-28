"""
P.E.P.P.E.R. Autonomy / Security Policy
Phase 16I.2

Conservative default:
- known local/read-only actions may run without approval
- external side effects require approval
- destructive actions require approval
- unknown categories fail closed
- background execution cannot consume interactive approval implicitly
"""

from __future__ import annotations

from .models import AutonomyDecision, AutonomyRequest


class AutonomyPolicy:
    SAFE_CATEGORIES = frozenset({
        "local_read",
        "integration_read",
        "world_state_read",
        "computation",
        "verification",
    })

    def evaluate(
        self,
        request: AutonomyRequest,
    ) -> AutonomyDecision:
        action = str(request.action or "").strip()
        category = str(request.category or "unknown").strip()

        if not action:
            return AutonomyDecision(
                allowed=False,
                requires_approval=False,
                reason="empty action",
                risk_level="blocked",
                request=request,
            )

        if request.destructive:
            if request.background:
                return AutonomyDecision(
                    allowed=False,
                    requires_approval=True,
                    reason=(
                        "destructive background actions are not "
                        "authorized implicitly"
                    ),
                    risk_level="high",
                    request=request,
                )
            if not request.approval_granted:
                return AutonomyDecision(
                    allowed=False,
                    requires_approval=True,
                    reason="destructive action requires approval",
                    risk_level="high",
                    request=request,
                )
            return AutonomyDecision(
                allowed=True,
                requires_approval=True,
                reason="destructive action explicitly approved",
                risk_level="high",
                request=request,
            )

        if request.external_side_effect:
            if request.background:
                return AutonomyDecision(
                    allowed=False,
                    requires_approval=True,
                    reason=(
                        "background external side effect requires "
                        "an explicit authorization design"
                    ),
                    risk_level="high",
                    request=request,
                )
            if not request.approval_granted:
                return AutonomyDecision(
                    allowed=False,
                    requires_approval=True,
                    reason="external side effect requires approval",
                    risk_level="high",
                    request=request,
                )
            return AutonomyDecision(
                allowed=True,
                requires_approval=True,
                reason="external side effect explicitly approved",
                risk_level="high",
                request=request,
            )

        if category not in self.SAFE_CATEGORIES:
            return AutonomyDecision(
                allowed=False,
                requires_approval=False,
                reason=f"unknown or untrusted category: {category}",
                risk_level="blocked",
                request=request,
            )

        if not request.read_only and category not in {
            "computation",
            "verification",
        }:
            return AutonomyDecision(
                allowed=False,
                requires_approval=False,
                reason=(
                    "non-read-only action lacks an approved "
                    "autonomy classification"
                ),
                risk_level="blocked",
                request=request,
            )

        return AutonomyDecision(
            allowed=True,
            requires_approval=False,
            reason="safe autonomous action",
            risk_level="low",
            request=request,
        )


AUTONOMY_POLICY = AutonomyPolicy()
