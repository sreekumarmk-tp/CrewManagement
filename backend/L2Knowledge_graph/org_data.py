"""
OrgMap source data — the organizational hierarchy ABOVE the vessel.

The crew table has no company / fleet / manning information, so (exactly as the L2
design §5.2 anticipates) that structure is authored here and the OrgMap builder
(org_map.py) overlays it onto the EXISTING EntityMap `Vessel` nodes — it never
re-creates vessels (§5.3 shared-node contract).

Three things are defined:
  1. ORG_TREE   — Company → Fleet → [Vessel]   (vessels match EntityMap by name)
  2. MANNING    — Rank → required headcount per vessel (standard manning template)
  3. helpers    — flat views the builder and queries consume.

Vessel names MUST match mock_data.crew_data.VESSELS so the OPERATES edges attach to
real EntityMap vessel nodes.
"""
from typing import Dict, List

# ── 1. Ownership hierarchy: Company → Fleet → Vessels ───────────────────────────
# The 5 EntityMap vessels distributed across 2 companies / 4 fleets.
ORG_TREE: Dict[str, Dict[str, List[str]]] = {
    "Oceanic Shipping Lines": {
        "Pacific Fleet": ["MV Pacific Star", "MV Indian Ocean Pride"],
        "Atlantic Fleet": ["MV Atlantic Voyager"],
    },
    "Meridian Maritime": {
        "Tanker Division": ["MT Crude Titan"],
        "Mediterranean Fleet": ["MV Mediterranean Queen"],
    },
}

# ── 2. Manning template: required headcount per rank, per vessel ────────────────
# A standard manning scale applied to every vessel (vessels aren't typed in the
# seed data, so one template fits all). Ranks are a subset of mock_data RANKS.
MANNING: Dict[str, int] = {
    "Master": 1,
    "Chief Officer": 1,
    "Second Officer": 1,
    "Third Officer": 1,
    "Chief Engineer": 1,
    "Second Engineer": 1,
    "Third Engineer": 1,
    "Bosun": 1,
    "AB Seaman": 2,
    "Electrician": 1,
    "Cook": 1,
}


# ── 3. Flat views ───────────────────────────────────────────────────────────────
def companies() -> List[str]:
    return list(ORG_TREE.keys())


def fleets() -> List[str]:
    return [fleet for company in ORG_TREE.values() for fleet in company]


def company_of_fleet() -> Dict[str, str]:
    """fleet name -> owning company name."""
    return {fleet: company for company, fleets_ in ORG_TREE.items() for fleet in fleets_}


def fleet_of_vessel() -> Dict[str, str]:
    """vessel name -> operating fleet name."""
    out: Dict[str, str] = {}
    for fleets_ in ORG_TREE.values():
        for fleet, vessels in fleets_.items():
            for v in vessels:
                out[v] = fleet
    return out


def vessels() -> List[str]:
    return list(fleet_of_vessel().keys())


def manning_ranks() -> List[str]:
    return list(MANNING.keys())
