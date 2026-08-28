"""
P.E.P.P.E.R. Proactive Policy
Phase 16G.2

Policy is intentionally conservative:
- suppress low-value candidates
- suppress duplicates during cooldown
- defer candidates while notifications are muted
- surface only candidates meeting the urgency threshold
"""

from __future__ import annotations

from threading import RLock
from time import monotonic

from .models import (
    ProactiveCandidate,
    ProactiveDecision,
)


class ProactivePolicy:
    def __init__(
        self,
        *,
        minimum_urgency: int = 5,
        dedupe_seconds: float = 300.0,
    ):
        self.minimum_urgency = int(minimum_urgency)
        self.dedupe_seconds = max(
            0.0,
            float(dedupe_seconds),
        )
        self._lock = RLock()
        self._last_surfaced: dict[str, float] = {}
        self._muted = False

    def set_muted(self, muted: bool) -> None:
        with self._lock:
            self._muted = bool(muted)

    @property
    def muted(self) -> bool:
        with self._lock:
            return self._muted

    def evaluate(
        self,
        candidate: ProactiveCandidate,
    ) -> ProactiveDecision:
        if not candidate.message.strip():
            return ProactiveDecision(
                action="suppress",
                reason="empty message",
                candidate=candidate,
            )

        with self._lock:
            if self._muted:
                return ProactiveDecision(
                    action="defer",
                    reason="proactive notifications muted",
                    candidate=candidate,
                )

            if candidate.urgency < self.minimum_urgency:
                return ProactiveDecision(
                    action="suppress",
                    reason="below urgency threshold",
                    candidate=candidate,
                )

            key = candidate.dedupe_key.strip()
            if key:
                last = self._last_surfaced.get(key)
                if (
                    last is not None
                    and monotonic() - last < self.dedupe_seconds
                ):
                    return ProactiveDecision(
                        action="suppress",
                        reason="duplicate cooldown",
                        candidate=candidate,
                    )

            return ProactiveDecision(
                action="surface",
                reason="candidate meets proactive policy",
                candidate=candidate,
            )

    def mark_surfaced(
        self,
        candidate: ProactiveCandidate,
    ) -> None:
        key = candidate.dedupe_key.strip()
        if not key:
            return

        with self._lock:
            self._last_surfaced[key] = monotonic()
