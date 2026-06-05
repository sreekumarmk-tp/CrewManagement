"""Live view: an SSE-broadcasting EventBus + a browser dashboard.

This is a lightweight, self-contained way to *see* the signal stream in a browser
today. `BroadcastBus` implements the same `core.EventBus` Protocol the connectors
publish to, and additionally fans every event out to connected Server-Sent-Events
clients while keeping authoritative running totals.

It is a viewer bus — no durability/ordering/Redis — and is meant to be replaced by
Sruthy's `InMemoryBus`/`RedisStreamsBus` (same Protocol) without touching anything
here. The `/demo/*` routes drive the existing demo replay *inside* the server
process so the dashboard shows the world in motion.
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter, deque
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, StreamingResponse

from core.signal import SignalEvent

_STATIC = Path(__file__).parent / "static"


class BroadcastBus:
    """EventBus that fans out to SSE subscribers and tracks running totals."""

    def __init__(self, keep_last: int = 200, queue_max: int = 5000) -> None:
        self._subs: set[asyncio.Queue] = set()
        self.recent: deque[dict] = deque(maxlen=keep_last)
        self.by_source: Counter = Counter()
        self.by_entity: Counter = Counter()
        self.total = 0
        self.signoff = 0
        self._queue_max = queue_max

    # --- EventBus Protocol ---
    async def publish(self, event: SignalEvent) -> None:
        self.total += 1
        self.by_source[event.source_system.value] += 1
        self.by_entity[event.entity] += 1
        is_signoff = event.metadata.get("l2Intent") == "CREATE_SIGNOFF_EVENT"
        if is_signoff:
            self.signoff += 1
        payload = self._payload(event, is_signoff)
        self.recent.append(payload)
        for q in list(self._subs):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass  # slow client: drop the line, totals stay authoritative

    @property
    def count(self) -> int:
        return self.total

    # --- SSE plumbing ---
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._queue_max)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)

    def totals(self) -> dict[str, Any]:
        return {"total": self.total, "by_source": dict(self.by_source),
                "by_entity": dict(self.by_entity), "signoff": self.signoff}

    def snapshot(self) -> dict[str, Any]:
        return {"type": "snapshot", "totals": self.totals(),
                "recent": list(self.recent)[-60:]}

    @staticmethod
    def _summary(ev: SignalEvent) -> str:
        d = ev.data or {}
        if "text" in d:
            return str(d["text"])[:120]
        if "subject" in d:
            return str(d["subject"])[:120]
        if ev.entity == "reaction":
            return f":{d.get('reaction', '?')}: on {d.get('channel', '')}"
        if ev.entity == "channel_join":
            return f"{d.get('user', '?')} joined {d.get('channel', '')}"
        op = (ev.metadata or {}).get("op", "")
        return f"{op} {ev.entity} {ev.key}".strip()

    def _payload(self, ev: SignalEvent, is_signoff: bool) -> dict[str, Any]:
        return {
            "type": "signal",
            "source": ev.source_system.value,
            "entity": ev.entity,
            "key": ev.key,
            "summary": self._summary(ev),
            "signoff": is_signoff,
            "ts": ev.timestamp.isoformat(),
            "totals": self.totals(),
        }


router = APIRouter(tags=["live"])


@router.get("/")
async def dashboard() -> FileResponse:
    return FileResponse(_STATIC / "dashboard.html")


@router.get("/stream")
async def stream(request: Request) -> StreamingResponse:
    bus = request.app.state.bus
    if not isinstance(bus, BroadcastBus):
        # the configured bus isn't SSE-capable (e.g. LoggingEventBus in tests)
        async def empty():
            yield "event: error\ndata: {\"error\":\"bus is not SSE-capable\"}\n\n"
        return StreamingResponse(empty(), media_type="text/event-stream")

    q = bus.subscribe()

    async def gen():
        yield f"event: snapshot\ndata: {json.dumps(bus.snapshot())}\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(item)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"  # comment line keeps the connection warm
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


# ----------------------------- demo drivers ----------------------------- #
def _streamer(request: Request, data_dir: str):
    """Build a DemoStreamer bound to the server's broadcast bus (lazy import so
    the API package doesn't hard-depend on the demo package)."""
    from demo.stream import DemoStreamer
    return DemoStreamer(data_dir, bus=request.app.state.bus)


@router.post("/demo/start")
async def demo_start(request: Request, speed: float = 6000.0, data: str = "./data") -> dict:
    state = request.app.state
    if getattr(state, "demo_task", None) and not state.demo_task.done():
        return {"running": True, "note": "already running"}
    if not (Path(data) / "seed_meta.json").exists():
        return {"error": f"no dataset at {data} — run `make seed` first"}

    streamer = _streamer(request, data)

    async def run():
        try:
            await streamer.run_live(speed=speed, tick=0.3)
        except asyncio.CancelledError:
            pass

    state.demo_task = asyncio.create_task(run())
    return {"started": True, "mode": "live", "speed": speed}


@router.post("/demo/backlog")
async def demo_backlog(request: Request, data: str = "./data") -> dict:
    """Burst the historical backlog into the dashboard (fast)."""
    if not (Path(data) / "seed_meta.json").exists():
        return {"error": f"no dataset at {data} — run `make seed` first"}
    result = await _streamer(request, data).run_backlog()
    return {"loaded": result["signals_emitted"], "by_source": result["by_source_system"]}


@router.post("/demo/stop")
async def demo_stop(request: Request) -> dict:
    t = getattr(request.app.state, "demo_task", None)
    if t and not t.done():
        t.cancel()
        return {"stopped": True}
    return {"stopped": False, "note": "nothing running"}


@router.get("/demo/status")
async def demo_status(request: Request) -> dict:
    t = getattr(request.app.state, "demo_task", None)
    bus = request.app.state.bus
    return {
        "running": bool(t and not t.done()),
        "totals": bus.totals() if isinstance(bus, BroadcastBus) else None,
    }
