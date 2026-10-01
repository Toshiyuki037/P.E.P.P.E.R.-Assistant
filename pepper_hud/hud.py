from __future__ import annotations
import json, socket, sys, time
from collections import deque
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView

HOST, PORT = "127.0.0.1", 45844

class HUD(QWebEngineView):
    W, H = 425, 187
    def __init__(self):
        super().__init__()
        self.ready=False; self.active_id=None; self.visible_text=""; self.queue=deque()
        self.chunk_text=""; self.chunk_base=""; self.chunk_start=0.0; self.chunk_duration=.1
        self.finish_requested=False; self.done_at=None; self.pending=[]
        self.setFixedSize(self.W,self.H)
        self.setAttribute(Qt.WA_TranslucentBackground,True)
        self.page().setBackgroundColor(Qt.transparent)
        self.setWindowFlags(Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.Tool)
        self.setAttribute(Qt.WA_TransparentForMouseEvents,True)
        if hasattr(Qt,"WindowTransparentForInput"): self.setWindowFlag(Qt.WindowTransparentForInput,True)
        g=QGuiApplication.primaryScreen().availableGeometry(); self.move(g.left()+41,g.top()+44)
        self.loadFinished.connect(self.loaded)
        self.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent/'hud.html')))
        self.timer=QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(16)
    def loaded(self,ok):
        if not ok: print('[HUD] ERROR: hud.html failed to load.'); return
        self.page().runJavaScript("typeof window.pepper !== 'undefined' && typeof pepper.show === 'function'",self.api_ready)
    def api_ready(self,ok):
        self.ready=bool(ok)
        if not self.ready: print('[HUD] ERROR: HUD JavaScript API did not initialize.'); return
        print('[HUD] READY',flush=True)
        q=self.pending; self.pending=[]
        for code in q:self.page().runJavaScript(code)
    def js(self,code):
        if self.ready:self.page().runJavaScript(code)
        else:self.pending.append(code)
    def begin(self,rid):
        if not rid:return
        # Same-ID BEGIN is a harmless lifecycle heartbeat: re-show, never erase.
        if rid == self.active_id:
            self.done_at=None
            self.js("pepper.show();")
            self.show(); self.raise_()
            return
        # Every NEW response is a clean visual transaction.
        self.active_id=rid; self.visible_text=""; self.queue.clear(); self.chunk_text=""; self.chunk_base=""
        self.finish_requested=False; self.done_at=None
        self.js("pepper.clear();pepper.text('');pepper.idle();pepper.show();")
        self.show(); self.raise_()
    def add_chunk(self,rid,text,duration):
        if not rid:return
        if self.active_id is None:self.begin(rid)
        if rid!=self.active_id:return
        text=" ".join(str(text or '').split())
        if not text:return
        self.queue.append((text,max(.05,float(duration or .05))))
        if not self.chunk_text:self.next_chunk()
    def next_chunk(self):
        if not self.queue:
            self.chunk_text=""
            if self.finish_requested and self.done_at is None:self.complete_now()
            return
        text,duration=self.queue.popleft(); self.chunk_base=self.visible_text+("" if not self.visible_text else " ")
        self.chunk_text=text; self.chunk_duration=duration; self.chunk_start=time.perf_counter()
    def level(self,rid,value):
        if rid==self.active_id:self.js(f"pepper.level({max(0,min(1,float(value))):.5f});")
    def finish(self,rid):
        if rid!=self.active_id:return
        self.finish_requested=True
        if not self.chunk_text and not self.queue:self.complete_now()
    def complete_now(self):
        self.js("pepper.idle();"); self.done_at=time.perf_counter()
    def render(self,text):self.js(f"pepper.text({json.dumps(text)});")
    def tick(self):
        now=time.perf_counter()
        if self.chunk_text:
            p=min(1.0,(now-self.chunk_start)/max(.05,self.chunk_duration)); n=round(len(self.chunk_text)*(p**1.03))
            self.render(self.chunk_base+self.chunk_text[:n])
            if p>=1:
                self.visible_text=self.chunk_base+self.chunk_text; self.chunk_text=""; self.render(self.visible_text); self.next_chunk()
        if self.done_at is not None and now-self.done_at>=5.2:
            self.js("pepper.hide();"); self.done_at=None

class Bridge:
    def __init__(self,hud):
        self.hud=hud; self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); self.sock.bind((HOST,PORT)); self.sock.setblocking(False)
        self.timer=QTimer(); self.timer.timeout.connect(self.poll); self.timer.start(8)
    def poll(self):
        while True:
            try:data,addr=self.sock.recvfrom(65535)
            except BlockingIOError:break
            try:m=json.loads(data.decode('utf-8'))
            except Exception:continue
            op=m.get('op'); rid=m.get('id')
            if op=='ping':
                try:self.sock.sendto(b'{"op":"ready"}',addr)
                except OSError:pass
            elif op=='begin':self.hud.begin(rid)
            elif op=='chunk':self.hud.add_chunk(rid,m.get('text',''),m.get('duration',.1))
            elif op=='level':self.hud.level(rid,m.get('value',0))
            elif op=='finish':self.hud.finish(rid)

if __name__=='__main__':
    app=QApplication(sys.argv); hud=HUD(); bridge=Bridge(hud); sys.exit(app.exec())
