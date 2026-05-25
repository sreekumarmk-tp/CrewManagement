"""
Raw dump of the most recent session's events + threads (read-only).
Shows the exact event shapes so we can see what the coordinator actually did.

    cd backend && python -m scripts.dump_session            # most recent session
    cd backend && python -m scripts.dump_session SESSION_ID # a specific session
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic  # noqa: E402
from config import settings  # noqa: E402


def _d(obj):
    for attr in ("model_dump", "to_dict"):
        if hasattr(obj, attr):
            try:
                return getattr(obj, attr)(mode="json") if attr == "model_dump" else getattr(obj, attr)()
            except TypeError:
                try:
                    return getattr(obj, attr)()
                except Exception:
                    pass
            except Exception:
                pass
    return str(obj)


async def main() -> None:
    print("anthropic:", getattr(anthropic, "__version__", "?"))
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    sid = sys.argv[1] if len(sys.argv) > 1 else None
    if not sid:
        sessions = await client.beta.sessions.list()
        items = getattr(sessions, "data", None) or []
        if not items:
            print("no sessions"); return
        sid = items[0].id
    print("SESSION:", sid)
    sess = _d(await client.beta.sessions.retrieve(sid))
    if isinstance(sess, dict):
        print("status:", sess.get("status"), "| title:", sess.get("title"))

    print("\n=== THREADS (raw) ===")
    async for t in client.beta.sessions.threads.list(sid):
        td = _d(t)
        if isinstance(td, dict):
            ag = td.get("agent") or {}
            print(f"  {td.get('id')} | agent={ag.get('name') if isinstance(ag, dict) else ag} | "
                  f"status={td.get('status')} | parent={td.get('parent_thread_id')}")

    print("\n=== EVENTS (raw, in order) ===")
    data = []
    async for e in client.beta.sessions.events.list(session_id=sid):
        data.append(e)
    print(f"({len(data)} events)\n")
    for i, e in enumerate(data):
        ed = _d(e)
        # keep it readable: print type + the whole event compactly
        etype = ed.get("type") if isinstance(ed, dict) else None
        print(f"[{i}] type={etype}")
        print(json.dumps(ed, indent=2, default=str)[:1500])
        print("-" * 60)


if __name__ == "__main__":
    asyncio.run(main())
