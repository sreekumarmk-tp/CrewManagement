"""BroadcastBus fan-out + dashboard / SSE routes."""

import asyncio
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from api.app import create_app
from api.live import BroadcastBus
from core.signal import SignalEvent, SourceSystem


def _event(signoff: bool = False) -> SignalEvent:
    md = {"l2Intent": "CREATE_SIGNOFF_EVENT"} if signoff else {}
    return SignalEvent(
        entity="message", key={"channel_id": "C1", "ts": "1.0"},
        source_system=SourceSystem.SLACK, tenant_id="t",
        data={"text": "hello"}, timestamp=datetime(2026, 6, 8, tzinfo=timezone.utc),
        metadata=md,
    )


def test_broadcastbus_fans_out_and_counts():
    async def run():
        bus = BroadcastBus()
        q = bus.subscribe()
        await bus.publish(_event())
        await bus.publish(_event(signoff=True))
        item1 = await asyncio.wait_for(q.get(), 1)
        item2 = await asyncio.wait_for(q.get(), 1)
        assert item1["source"] == "SLACK" and item1["summary"] == "hello"
        assert item2["signoff"] is True
        assert bus.total == 2 and bus.signoff == 1
        assert bus.totals()["by_source"]["SLACK"] == 2
    asyncio.run(run())


def test_dashboard_served():
    client = TestClient(create_app())
    r = client.get("/")
    assert r.status_code == 200
    assert "L1 SignalFabric" in r.text
    assert "/stream" in r.text  # the page wires up the SSE feed


def test_demo_status_idle():
    client = TestClient(create_app())
    r = client.get("/demo/status")
    assert r.status_code == 200
    body = r.json()
    assert body["running"] is False
    assert body["totals"]["total"] == 0
