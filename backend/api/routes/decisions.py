"""
Decision Graph API routes (L4).

Exposes the captured decision traces: the list for the L4 Decision Graph view,
the full trace for a single decision, and a demo-seed endpoint so the view has
data to show before any live workflow has run.
"""
from fastapi import APIRouter, HTTPException

from database.decision_repository import get_decision, list_decisions
from services.decision_trace_service import decision_trace_service

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.get("/", response_model=list)
async def get_decisions(limit: int = 50):
    """Most-recent-first list of captured placement decisions."""
    return await list_decisions(limit=limit)


@router.post("/demo-seed", response_model=dict)
async def seed_demo_decisions():
    """Insert mock decision traces for demoing the L4 view without a live workflow.

    Idempotent: if sample data already exists it is returned for replay rather than
    re-inserted, so repeated calls don't pile up duplicate rows.
    """
    return await decision_trace_service.seed_demo()


@router.delete("/demo-seed", response_model=dict)
async def clear_demo_decisions():
    """Remove ONLY seeded/sample rows (workflow_id LIKE 'demo-%') from the decision
    and precedent stores. Live placements and real precedent history are preserved."""
    return await decision_trace_service.clear_demo()


@router.get("/{decision_id}", response_model=dict)
async def get_decision_trace(decision_id: str):
    """Full trace (query → trajectory → decision → outcome) for one decision."""
    decision = await get_decision(decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id} not found")
    return decision
