"""
P.E.P.P.E.R. Background Handler Registry
Phase 16F.1

Tasks carry a handler name in metadata rather than serializing executable code.
Only explicitly registered handlers may run.
"""

from __future__ import annotations

from threading import RLock
from typing import Any, Callable


BackgroundHandler = Callable[[Any], Any]


class BackgroundHandlerRegistry:
    def __init__(self):
        self._lock = RLock()
        self._handlers: dict[str, BackgroundHandler] = {}

    @staticmethod
    def _normalize(name: str) -> str:
        value = str(name or "").strip()
        if not value:
            raise ValueError("Background handler name cannot be empty.")
        return value

    def register(
        self,
        name: str,
        handler: BackgroundHandler,
        *,
        replace: bool = False,
    ) -> None:
        normalized = self._normalize(name)
        if not callable(handler):
            raise TypeError("Background handler must be callable.")

        with self._lock:
            if normalized in self._handlers and not replace:
                raise KeyError(
                    f"Background handler already registered: {normalized}"
                )
            self._handlers[normalized] = handler

    def unregister(self, name: str) -> bool:
        normalized = self._normalize(name)
        with self._lock:
            return self._handlers.pop(normalized, None) is not None

    def get(self, name: str) -> BackgroundHandler | None:
        normalized = self._normalize(name)
        with self._lock:
            return self._handlers.get(normalized)

    def names(self) -> list[str]:
        with self._lock:
            return sorted(self._handlers)


HANDLERS = BackgroundHandlerRegistry()
