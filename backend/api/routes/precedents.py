"""
Precedent Index API routes (L4 #2).

Exposes the placement history store: the full list for inspection, and a lookup
that performs the same query the matching layer runs at the start of a sign-off
(prior placements for a given vacancy profile).
"""
from typing import Optional

from fastapi import APIRouter

from database.precedent_repository import list_precedents
from services.precedent_service import precedent_service

router = APIRouter(prefix="/precedents", tags=["precedents"])


@router.get("/", response_model=list)
async def get_precedents(limit: int = 100):
    """All recorded placements, most recent first."""
    return await list_precedents(limit=limit)


@router.get("/lookup", response_model=dict)
async def lookup_precedents(
    rank: str,
    port: Optional[str] = None,
    grade: Optional[str] = None,
    limit: int = 5,
):
    """Consult the index for a vacancy profile — the same lookup the matching layer
    runs at the start of a sign-off. `is_repeat` is true when prior placements exist."""
    return await precedent_service.consult(rank, grade=grade, port=port, limit=limit)
