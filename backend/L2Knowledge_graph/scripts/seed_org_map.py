"""
Seed the L2 OrgMap dimension into the Apache AGE `maritime` graph.

Overlays the organizational hierarchy (Company / Fleet / Rank nodes + OWNS /
OPERATES / REQUIRES_RANK / HAS_RANK edges) onto the EXISTING EntityMap Vessel/Crew
nodes (L2 design §5.2). It MATCHes those nodes and never re-creates them (§5.3).

Prerequisites:
    1. An AGE-enabled Postgres holding the `crew` table.
    2. GRAPH_BACKEND=age.
    3. EntityMap seeded first (it owns the Vessel/Crew nodes OrgMap attaches to):
           python -m scripts.seed_crew
           python -m L2Knowledge_graph.scripts.seed_entity_map

Usage:
    python -m L2Knowledge_graph.scripts.seed_org_map
"""
import asyncio
import json

from L2Knowledge_graph.org_map import build_org_map


async def main() -> None:
    summary = await build_org_map()
    print("OrgMap seeded into AGE graph 'maritime'.")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
