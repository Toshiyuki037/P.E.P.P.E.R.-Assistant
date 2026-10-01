from __future__ import annotations
import json, socket, subprocess, sys, threading, time, uuid
from pathlib import Path

HOST, PORT = "127.0.0.1", 45844
ROOT = Path(__file__).resolve().parents[3]
HUD = ROOT / "pepper_hud" / "hud.py"

_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
_sock.bind((HOST, 0))
_sock.settimeout(.06)

_process = None
_current_response_id = None
_lock = threading.RLock()

def _send(payload):
    try:
        _sock.sendto(
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            (HOST, PORT),
        )
        return True
    except OSError:
        return False

def _probe():
    _send({"op":"ping"})
    try:
        data,_ = _sock.recvfrom(1024)
        return json.loads(data.decode("utf-8")).get("op") == "ready"
    except Exception:
        return False

def ensure():
    global _process
    with _lock:
        # Once our HUD child is alive, NEVER add a network wait to speech.
        if _process is not None and _process.poll() is None:
            return True

        # Reuse a HUD already listening on this port.
        if _probe():
            return True

        if not HUD.exists():
            return False

        _process = subprocess.Popen(
            [sys.executable, str(HUD)],
            cwd=str(ROOT),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        # Startup handshake only. This never runs for later responses.
        deadline=time.perf_counter()+2.0
        while time.perf_counter()<deadline:
            if _probe():
                return True
            time.sleep(.03)
        return False

def hud_speak(text=None,duration=None):
    global _current_response_id
    rid=uuid.uuid4().hex
    with _lock:
        _current_response_id=rid

    if not ensure():
        return rid

    _send({"op":"begin","id":rid})

    # A single same-ID retry only re-shows the existing response; it cannot clear it.
    def reinforce():
        time.sleep(.10)
        with _lock:
            if _current_response_id==rid:
                _send({"op":"begin","id":rid})
    threading.Thread(target=reinforce,daemon=True).start()

    if text:
        hud_chunk(
            str(text),
            duration or max(1.0,len(str(text).split())/165*60),
            rid,
        )
    return rid

def hud_chunk(text,duration,response_id=None):
    with _lock:
        rid=response_id or _current_response_id
    if rid:
        _send({
            "op":"chunk",
            "id":rid,
            "text":__import__("re").sub(r"\bV\s+S\s+Code\b", "VS Code", str(text or ""), flags=__import__("re").IGNORECASE),
            "duration":max(.05,float(duration or .05)),
        })

def hud_level(value,response_id=None):
    # Existing speak.py calls hud_level(value), so preserve the active response ID.
    with _lock:
        rid=response_id or _current_response_id
    if rid:
        _send({"op":"level","id":rid,"value":float(value)})

def hud_finish(response_id=None):
    with _lock:
        rid=response_id or _current_response_id
    if rid:
        _send({"op":"finish","id":rid})
