"""
Read-only diagnostic for multiagent delegation. Run after a sign-off attempt:

    cd backend && python -m scripts.diagnose_multiagent

Prints:
  1. The coordinator's persisted config — did `multiagent` (roster) + `tools` persist?
  2. Whether the roster IDs match the specialists in managed_agents.json.
  3. The most recent session: its threads, its event stream, and the coordinator's
     own text output — so we can see whether it delegated or just answered.
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic  # noqa: E402
from config import settings  # noqa: E402


def _dump(obj):
    for attr in ("model_dump", "to_dict"):
        if hasattr(obj, attr):
            try:
                return getattr(obj, attr)()
            except Exception:
                pass
    return obj if isinstance(obj, dict) else str(obj)


async def main() -> None:
    print("anthropic:", getattr(anthropic, "__version__", "?"))
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    with open(settings.managed_agents_ids_file) as f:
        ids = json.load(f)
    roster_expected = {s["agent_id"] for s in ids["specialists"].values()}

    cid = settings.managed_coordinator_agent_id
    print("\n=== COORDINATOR AGENT:", cid, "===")
    agent = _dump(await client.beta.agents.retrieve(cid))
    if isinstance(agent, dict):
        print("name       :", agent.get("name"))
        print("version    :", agent.get("version"))
        print("tools      :", json.dumps(agent.get("tools"), default=str))
        ma = agent.get("multiagent")
        print("multiagent :", json.dumps(ma, indent=2, default=str))
        roster_got = set()
        if isinstance(ma, dict):
            for e in ma.get("agents") or []:
                roster_got.add(e if isinstance(e, str) else (e.get("id") if isinstance(e, dict) else None))
        print("roster matches specialists?:", roster_got == roster_expected,
              "| got:", roster_got, "| expected:", roster_expected)
        print("system[:200]:", (agent.get("system") or "")[:200])
    else:
        print(agent)

    print("\n=== MOST RECENT SESSION ===")
    sessions = await client.beta.sessions.list()
    items = getattr(sessions, "data", None) or list(sessions)
    if not items:
        print("no sessions found"); return
    s = items[0]
    sid = getattr(s, "id", None)
    print("session:", sid, "| status:", getattr(s, "status", None),
          "| agent:", _dump(getattr(s, "agent", None)))

    # Threads — if delegation happened there will be >1 (primary + sub-agents)
    print("\n=== THREADS ===")
    try:
        threads = await client.beta.sessions.threads.list(sid)
        titems = getattr(threads, "data", None) or list(threads)
        for t in titems:
            ag = getattr(t, "agent", None)
            name = getattr(ag, "name", None) if ag else None
            print(f"  thread {getattr(t,'id',None)} | agent={name} | status={getattr(t,'status',None)} | parent={getattr(t,'parent_thread_id',None)}")
        print("thread count:", len(titems), "(1 ⇒ ONLY the coordinator ran; no delegation)")
    except Exception as e:
        print("threads.list failed:", e)

    print("\n=== PRIMARY-THREAD EVENTS ===")
    events = await client.beta.sessions.events.list(session_id=sid)
    evs = getattr(events, "data", None) or list(events)
    coord_text = []
    counts = {}
    for e in evs:
        et = getattr(e, "type", "?")
        counts[et] = counts.get(et, 0) + 1
        if et in ("agent.message", "agent.thinking"):
            c = getattr(e, "content", None)
            if isinstance(c, list):
                coord_text.append(" ".join(getattr(b, "text", "") for b in c if getattr(b, "type", "") == "text"))
        elif et == "session.error":
            print("  session.error ::", _dump(getattr(e, "error", e)))
        elif et in ("agent.thread_message_sent", "agent.thread_message_received"):
            print(f"  {et} :: to/from={getattr(e,'to_agent_name',None) or getattr(e,'from_agent_name',None)}")
        elif et == "session.thread_created":
            print(f"  session.thread_created :: agent={getattr(e,'agent_name',None)}")
    print("\nevent type counts:", json.dumps(counts, indent=2))
    print("\nCOORDINATOR TEXT OUTPUT (what it said instead of/while delegating):")
    print("  " + (" ".join(coord_text)[:1200] or "<none>"))


if __name__ == "__main__":
    asyncio.run(main())
