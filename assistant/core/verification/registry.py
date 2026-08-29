"""
P.E.P.P.E.R. Verification + Recovery Registries
Phase 16H.2

Only explicitly registered verifiers/recovery handlers may execute.
"""

from __future__ import annotations

from threading import RLock
from typing import Any, Callable

from .models import VerificationResult


Verifier = Callable[[Any, Any], VerificationResult | bool]
RecoveryHandler = Callable[[Any, Any, VerificationResult, int], Any]


class _NamedRegistry:
    def __init__(self, label: str):
        self.label = label
        self._lock = RLock()
        self._items: dict[str, Callable] = {}

    @staticmethod
    def _normalize(name: str) -> str:
        value = str(name or "").strip()
        if not value:
            raise ValueError("Registry name cannot be empty.")
        return value

    def register(
        self,
        name: str,
        handler: Callable,
        *,
        replace: bool = False,
    ) -> None:
        normalized = self._normalize(name)
        if not callable(handler):
            raise TypeError(f"{self.label} must be callable.")

        with self._lock:
            if normalized in self._items and not replace:
                raise KeyError(
                    f"{self.label} already registered: {normalized}"
                )
            self._items[normalized] = handler

    def unregister(self, name: str) -> bool:
        normalized = self._normalize(name)
        with self._lock:
            return self._items.pop(normalized, None) is not None

    def get(self, name: str):
        normalized = self._normalize(name)
        with self._lock:
            return self._items.get(normalized)

    def names(self) -> list[str]:
        with self._lock:
            return sorted(self._items)


class VerifierRegistry(_NamedRegistry):
    def __init__(self):
        super().__init__("Verifier")


class RecoveryRegistry(_NamedRegistry):
    def __init__(self):
        super().__init__("Recovery handler")


VERIFIERS = VerifierRegistry()
RECOVERIES = RecoveryRegistry()
