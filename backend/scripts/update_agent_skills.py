"""
Apply the skills configured in agents/managed/registry.py to the agents that have
ALREADY been created (the IDs cached in managed_agents.json), in place.

Unlike setup_managed_agents.py, this does NOT create new agents — each agent keeps
its ID and is bumped to a new immutable version with the skills attached, so the
cached IDs and any running config stay valid. Safe to re-run (idempotent: it
re-applies whatever registry.py currently specifies).

    cd backend
    python -m scripts.update_agent_skills

Prerequisites:
  * managed_agents.json present (run scripts.setup_managed_agents first)
  * ANTHROPIC_API_KEY set, on an org with Managed Agents beta access
"""
import asyncio
import json
import os
import sys

# Allow `python scripts/update_agent_skills.py` from the backend dir too.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.managed.client import ManagedAgentsClient  # noqa: E402
from config import settings  # noqa: E402


async def main() -> None:
    if not settings.anthropic_api_key:
        print("ERROR: ANTHROPIC_API_KEY is not set.")
        sys.exit(1)
    if not os.path.exists(settings.managed_agents_ids_file):
        print(
            "ERROR: managed_agents.json not found at "
            f"{settings.managed_agents_ids_file}.\n"
            "Run `python -m scripts.setup_managed_agents` first."
        )
        sys.exit(1)

    print("Applying registry skills to existing agents (in place, new versions)...")
    client = ManagedAgentsClient()
    results = await client.update_skills()

    print("\n✅ Skills applied. Agent IDs unchanged; versions bumped:\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
