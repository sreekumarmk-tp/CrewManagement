"""
One-time setup for Managed Agents.

Creates the persisted environment, the four specialist agents, and the multiagent
coordinator on your Anthropic organization, then caches their IDs to
managed_agents.json (read automatically by config.py at startup).

Run ONCE (re-running creates duplicate agents):

    cd backend
    python -m scripts.setup_managed_agents

Prerequisites:
  * anthropic>=0.92.0 installed (see requirements.txt)
  * ANTHROPIC_API_KEY set, on an org with Managed Agents beta access
"""
import asyncio
import json
import os
import sys

# Allow `python scripts/setup_managed_agents.py` from the backend dir too.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.managed.client import ManagedAgentsClient  # noqa: E402
from config import settings  # noqa: E402


async def main() -> None:
    if not settings.anthropic_api_key:
        print("ERROR: ANTHROPIC_API_KEY is not set.")
        sys.exit(1)

    print("Creating Managed Agents resources (environment, 4 specialists, coordinator)...")
    client = ManagedAgentsClient()
    ids = await client.setup()

    out_path = settings.managed_agents_ids_file
    with open(out_path, "w") as f:
        json.dump(ids, f, indent=2)

    print("\n✅ Setup complete. IDs cached to:", out_path)
    print(json.dumps(ids, indent=2))
    print("\nThese now appear in the Console (Sessions are created per workflow run):")
    print("  https://platform.claude.com/workspaces/default/sessions")
    print("\nThe app loads these IDs from the cache file automatically. For container")
    print("deploys, set instead:")
    print(f"  MANAGED_ENVIRONMENT_ID={ids['environment_id']}")
    print(f"  MANAGED_COORDINATOR_AGENT_ID={ids['coordinator_agent_id']}")


if __name__ == "__main__":
    asyncio.run(main())
