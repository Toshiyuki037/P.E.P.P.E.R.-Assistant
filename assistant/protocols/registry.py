from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, Optional
from assistant.protocols.good_morning import run_good_morning_protocol
ProtocolRunner = Callable[[], str]
@dataclass(frozen=True)
class ProtocolDefinition:
    name: str
    runner: ProtocolRunner
    schedule: str | None = None
    description: str | None = None
class ProtocolRegistry:
    def __init__(self): self._protocols: Dict[str, ProtocolDefinition] = {}
    @staticmethod
    def normalize_name(name): return ' '.join(str(name).strip().lower().replace('_',' ').split())
    def register(self,d):
        key=self.normalize_name(d.name)
        if not key: raise ValueError('protocol name cannot be empty')
        if key in self._protocols: raise ValueError(f'protocol already registered: {key}')
        self._protocols[key]=d
    def get(self,name): return self._protocols.get(self.normalize_name(name))
    def names(self): return tuple(sorted(self._protocols))
    def runner_map(self): return {n:d.runner for n,d in self._protocols.items()}
def _run_good_morning(): return run_good_morning_protocol(surface=False).spoken_text
PROTOCOL_REGISTRY=ProtocolRegistry()
PROTOCOL_REGISTRY.register(ProtocolDefinition('good morning',_run_good_morning,'daily at 7:00 AM local time','Daily morning briefing.'))
