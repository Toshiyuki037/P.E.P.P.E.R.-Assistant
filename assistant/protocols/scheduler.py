from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

STATE_PATH = Path(__file__).resolve().parents[2] / "runtime" / "briefings" / "state.json"


class GoodMorningScheduler:
    def __init__(self, *, deliver_fn: Callable[[], None],
                 is_busy_fn: Callable[[], bool] | None = None,
                 hour: int = 7, minute: int = 0,
                 poll_seconds: float = 15.0,
                 state_path: Path = STATE_PATH):
        self.deliver_fn = deliver_fn
        self.is_busy_fn = is_busy_fn or (lambda: False)
        self.hour = int(hour)
        self.minute = int(minute)
        self.poll_seconds = max(1.0, float(poll_seconds))
        self.state_path = Path(state_path)
        if not 0 <= self.hour <= 23:
            raise ValueError("hour must be between 0 and 23")
        if not 0 <= self.minute <= 59:
            raise ValueError("minute must be between 0 and 59")
        self._stop_event = threading.Event()
        self._thread = None
        self._delivery_lock = threading.Lock()

    @property
    def running(self):
        return bool(self._thread is not None and self._thread.is_alive())

    def start(self):
        if self.running:
            return False
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True,
            name="pepper-good-morning-scheduler",
        )
        self._thread.start()
        print(f"[Good Morning Scheduler] armed for {self.hour:02d}:{self.minute:02d} local time")
        return True

    def stop(self):
        self._stop_event.set()

    def _load_state(self):
        try:
            if not self.state_path.exists():
                return {}
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def _write_state(self, payload):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self.state_path)

    def _already_delivered(self, local_date):
        return self._load_state().get("last_success_date") == local_date

    def _mark_success(self, now):
        self._write_state({
            "last_success_date": now.date().isoformat(),
            "last_success_at": now.isoformat(timespec="seconds"),
            "scheduled_local_time": f"{self.hour:02d}:{self.minute:02d}",
        })

    def _is_due(self, now):
        scheduled = now.replace(
            hour=self.hour, minute=self.minute, second=0, microsecond=0
        )
        return now >= scheduled

    def _try_delivery(self, now):
        local_date = now.date().isoformat()
        if self._already_delivered(local_date):
            return
        try:
            if self.is_busy_fn():
                return
        except Exception as error:
            print(f"[Good Morning Scheduler] busy-state check failed closed: {error}")
            return
        if not self._delivery_lock.acquire(blocking=False):
            return
        try:
            if self._already_delivered(local_date):
                return
            try:
                if self.is_busy_fn():
                    return
            except Exception:
                return
            print("[Good Morning Scheduler] running scheduled briefing")
            self.deliver_fn()
            self._mark_success(datetime.now())
            print("[Good Morning Scheduler] scheduled briefing completed")
        except Exception as error:
            print(
                "[Good Morning Scheduler] delivery failed; will retry: "
                f"{type(error).__name__}: {error}"
            )
        finally:
            self._delivery_lock.release()

    def status(self):
        state = self._load_state()
        return {
            "name": "Good Morning Protocol",
            "enabled": self.running,
            "running_now": self._delivery_lock.locked(),
            "schedule": "daily",
            "local_time": f"{self.hour:02d}:{self.minute:02d}",
            "last_success_date": state.get("last_success_date"),
            "last_success_at": state.get("last_success_at"),
        }

    def _run(self):
        while not self._stop_event.is_set():
            now = datetime.now()
            if self._is_due(now):
                self._try_delivery(now)
            self._stop_event.wait(self.poll_seconds)


def protocol_status(scheduler=None):
    if scheduler is None:
        return {"name": "Good Morning Protocol", "enabled": False, "running_now": False, "schedule": "daily", "local_time": "07:00", "last_success_date": None, "last_success_at": None}
    return scheduler.status()
