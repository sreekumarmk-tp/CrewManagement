# L1 SignalFabric

Continuous event-stream ingestion for the **Maritime Crew Orchestrator**. L1
observes the source systems (Slack, Gmail, ERP) and normalizes their events into
a single canonical stream — `SignalEvent` — that the L2 knowledge graph (OrgMap +
**SignOffEvent**) consumes.

> **Design principle:** continuous streams, *not* batch snapshots. Every event is
> an append-only, typed, timestamped `SignalEvent` with `operation = DELTA`.

See [`docs/DESIGN.md`](docs/DESIGN.md), [`docs/PLAN.md`](docs/PLAN.md), and
[`docs/TEST.md`](docs/TEST.md).

## Scope of this scaffold — Day 1 (Jun 08), Sreekumar's track

This is the **ingress / connector foundation**:

- `core/` — the agreed contracts:
  - `SignalEvent` canonical model + `SourceSystem` / `Operation` enums (`core/signal.py`)
  - `EventStreamConnector` interface — `verify / ingest / position / commit` (`core/connector.py`)
  - `EventBus` Protocol + `LoggingEventBus` **placeholder** (`core/bus.py`) — replaced
    by the InMemoryBus/RedisStreamsBus on the core track
  - `dedup_key()` and watermark stores (`core/dedup.py`, `core/watermark.py`)
- `connectors/slack/` — Slack Events API connector skeleton: **url_verification
  handshake**, HMAC signature verification (with a dev bypass), and message /
  reaction / channel-join mappers
- `connectors/erp/` — ERP connector skeleton: transactional-**outbox** fetch
  adapter (mimic) + watermark + per-table mappers (Crew DB / Contract-CLM /
  Vessel-Port DB)
- `api/` — FastAPI app exposing **`/healthz`** and **`POST /slack/events`**

Not in this scaffold (core track / later days): the real InMemoryBus & Redis
Streams, the L2 sink + OrgMap upsert, SSE `/stream`, the Gmail connector (Day 3).

## Quick start

```bash
# uses Python 3.11+
python -m pip install -r requirements.txt

make test        # 18 tests: contract, signal, API, signature, ERP watermark
make smoke       # in-process Day-1 ingress demo (no external services)
make run         # uvicorn on :8001
```

Then:

```bash
curl localhost:8001/healthz

# Slack URL-verification handshake (what Slack sends when you set the Request URL)
curl -sX POST localhost:8001/slack/events \
  -H 'content-type: application/json' \
  -d '{"type":"url_verification","challenge":"abc123"}'      # -> abc123

# A Slack message event
curl -sX POST localhost:8001/slack/events -H 'content-type: application/json' -d '{
  "type":"event_callback","event_id":"Ev01","team_id":"T001",
  "event":{"type":"message","channel":"C005","user":"U002","text":"hi","ts":"1719980964.000100"}
}'                                                            # -> {"ok":true,"ingested":1}
```

## Demo data & streaming

A large, deterministic, **streamable** maritime crew-ops dataset (~4,600 events
across Slack / Email / ERP) drives the demo — see [`demo/README.md`](demo/README.md).

```bash
make seed           # generate ./data (backlog + live runway + entities + meta)
make stream         # drain the historical backlog through the connectors (idempotent)
make stream-live    # replay the future runway on a virtual clock (world in motion)
```

### Live browser dashboard

```bash
make seed           # once, if you haven't
make dashboard      # serves on :8001
# open http://localhost:8001/  → click "Start live" (or "Load history")
```

`GET /` is a single-file dashboard ([`api/static/dashboard.html`](api/static/dashboard.html))
that subscribes to **`GET /stream`** (Server-Sent Events) and shows per-source
counters, a sign-off→L2 tally, a signals/sec gauge, and a live feed. The
`POST /demo/{start,stop,backlog}` routes drive the replay *inside the server* via
the `BroadcastBus` (an SSE-capable `EventBus`; swap in the real InMemoryBus later).

## Layout

```
L1SignalFabric/
  core/                 # SignalEvent, EventStreamConnector, EventBus, dedup, watermark
  connectors/
    slack/              # connector + signature verify + url_verification + mappers
    erp/                # connector + outbox fetch adapter + mappers
  api/
    app.py              # FastAPI factory (wires connectors + bus)
    routes/             # health.py (/healthz), slack.py (/slack/events)
    live.py             # BroadcastBus + /stream (SSE) + / (dashboard) + /demo/*
    static/dashboard.html  # single-file live dashboard
  demo/                 # generator + seed + stream (Freight-style demo data)
  data/                 # generated dataset (reproducible via `make seed`)
  scripts/smoke.py      # Day-1 ingress smoke
  tests/                # pytest suite
  docs/                 # PLAN / DESIGN / TEST (+ .docx, diagrams)
```

## The seam (how the two tracks meet)

Connectors emit `SignalEvent` and publish via the `EventBus` Protocol. The core
track implements that Protocol (`InMemoryBus`) and subscribes the L2 sink — no
change to any connector or route. The Slack route already publishes; swap the bus
in `create_app(bus=...)` to integrate.
