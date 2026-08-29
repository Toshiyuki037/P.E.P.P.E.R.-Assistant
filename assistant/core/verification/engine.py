"""
P.E.P.P.E.R. Verification / Recovery Engine
Phase 16H.4

Execution contract:
1. Background handler produces a result.
2. Optional explicit verifier validates the result.
3. If verification fails, optional explicit recovery handler may run.
4. Recovery output is re-verified.
5. Recovery is bounded by policy.

This engine does not re-run arbitrary original actions automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from assistant.core.events import publish
from assistant.core.events.definitions import (
    RECOVERY_ATTEMPTED,
    RECOVERY_EXHAUSTED,
    VERIFICATION_FAILED,
    VERIFICATION_PASSED,
)

from .models import VerificationResult
from .policy import RecoveryPolicy
from .registry import (
    RECOVERIES,
    VERIFIERS,
    RecoveryRegistry,
    VerifierRegistry,
)


@dataclass(frozen=True)
class VerifiedExecutionResult:
    success: bool
    value: Any
    verification: VerificationResult
    recovery_attempts: int = 0
    error: str = ""


class VerificationEngine:
    def __init__(
        self,
        *,
        verifiers: VerifierRegistry = VERIFIERS,
        recoveries: RecoveryRegistry = RECOVERIES,
        recovery_policy: RecoveryPolicy | None = None,
    ):
        self.verifiers = verifiers
        self.recoveries = recoveries
        self.recovery_policy = (
            recovery_policy or RecoveryPolicy(max_attempts=1)
        )

    @staticmethod
    def _normalize_verification(raw) -> VerificationResult:
        if isinstance(raw, VerificationResult):
            return raw

        if isinstance(raw, bool):
            return (
                VerificationResult.success()
                if raw
                else VerificationResult.failure(
                    "verifier returned false"
                )
            )

        raise TypeError(
            "Verifier must return VerificationResult or bool."
        )

    def _verify(
        self,
        *,
        task,
        value,
        verifier_name: str | None,
    ) -> VerificationResult:
        if not verifier_name:
            return VerificationResult.success(
                "no verifier configured; legacy completion preserved"
            )

        verifier = self.verifiers.get(verifier_name)
        if verifier is None:
            return VerificationResult.failure(
                f"unregistered verifier: {verifier_name}"
            )

        try:
            return self._normalize_verification(
                verifier(task, value)
            )
        except Exception as error:
            return VerificationResult.failure(
                f"verifier exception: {type(error).__name__}: {error}"
            )

    def execute(
        self,
        *,
        task,
        value,
        verifier_name: str | None,
        recovery_handler_name: str | None,
    ) -> VerifiedExecutionResult:
        verification = self._verify(
            task=task,
            value=value,
            verifier_name=verifier_name,
        )

        if verification.verified:
            publish(
                VERIFICATION_PASSED,
                {
                    "task_id": task.task_id,
                    "reason": verification.reason,
                    "recovery_attempts": 0,
                },
                source="assistant.core.verification",
            )
            return VerifiedExecutionResult(
                success=True,
                value=value,
                verification=verification,
            )

        publish(
            VERIFICATION_FAILED,
            {
                "task_id": task.task_id,
                "reason": verification.reason,
                "attempt": 0,
            },
            source="assistant.core.verification",
        )

        attempt = 0
        current_value = value

        while True:
            decision = self.recovery_policy.evaluate(
                recovery_handler_name=recovery_handler_name,
                attempt=attempt,
            )

            if not decision.allowed:
                publish(
                    RECOVERY_EXHAUSTED,
                    {
                        "task_id": task.task_id,
                        "reason": decision.reason,
                        "attempts": attempt,
                        "verification_reason":
                            verification.reason,
                    },
                    source="assistant.core.verification",
                )
                return VerifiedExecutionResult(
                    success=False,
                    value=current_value,
                    verification=verification,
                    recovery_attempts=attempt,
                    error=verification.reason,
                )

            recovery = self.recoveries.get(
                recovery_handler_name
            )
            if recovery is None:
                reason = (
                    f"unregistered recovery handler: "
                    f"{recovery_handler_name}"
                )
                verification = VerificationResult.failure(
                    reason
                )
                publish(
                    RECOVERY_EXHAUSTED,
                    {
                        "task_id": task.task_id,
                        "reason": reason,
                        "attempts": attempt,
                        "verification_reason":
                            verification.reason,
                    },
                    source="assistant.core.verification",
                )
                return VerifiedExecutionResult(
                    success=False,
                    value=current_value,
                    verification=verification,
                    recovery_attempts=attempt,
                    error=reason,
                )

            attempt += 1

            publish(
                RECOVERY_ATTEMPTED,
                {
                    "task_id": task.task_id,
                    "handler": recovery_handler_name,
                    "attempt": attempt,
                    "verification_reason":
                        verification.reason,
                },
                source="assistant.core.verification",
            )

            try:
                current_value = recovery(
                    task,
                    current_value,
                    verification,
                    attempt,
                )
            except Exception as error:
                verification = VerificationResult.failure(
                    f"recovery exception: "
                    f"{type(error).__name__}: {error}"
                )
                continue

            verification = self._verify(
                task=task,
                value=current_value,
                verifier_name=verifier_name,
            )

            if verification.verified:
                publish(
                    VERIFICATION_PASSED,
                    {
                        "task_id": task.task_id,
                        "reason": verification.reason,
                        "recovery_attempts": attempt,
                    },
                    source="assistant.core.verification",
                )
                return VerifiedExecutionResult(
                    success=True,
                    value=current_value,
                    verification=verification,
                    recovery_attempts=attempt,
                )

            publish(
                VERIFICATION_FAILED,
                {
                    "task_id": task.task_id,
                    "reason": verification.reason,
                    "attempt": attempt,
                },
                source="assistant.core.verification",
            )


VERIFICATION_ENGINE = VerificationEngine()
