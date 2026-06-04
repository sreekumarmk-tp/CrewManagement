"""Crew management API routes."""
from fastapi import APIRouter, HTTPException, Response
from typing import List

from config import settings
from database.models import CrewMember
from database.crew_repository import get_sign_on_crew, get_sign_off_crew, get_crew_by_id

router = APIRouter(prefix="/crew", tags=["crew"])

# Step 4: short browser-cache window for the read-only crew lists. Lets the
# browser short-circuit repeated GETs (navigations/remounts) under the SWR client
# cache, without holding stale data long enough to fight the live event refresh.
_CREW_CACHE_CONTROL = f"public, max-age={settings.crew_http_cache_max_age_seconds}"


@router.get("/sign-on", response_model=List[dict])
async def list_sign_on_crew(response: Response):
    """Return all crew available for sign-on."""
    response.headers["Cache-Control"] = _CREW_CACHE_CONTROL
    return await get_sign_on_crew()


@router.get("/sign-off", response_model=List[dict])
async def list_sign_off_crew(response: Response):
    """Return all crew currently onboard (available for sign-off)."""
    response.headers["Cache-Control"] = _CREW_CACHE_CONTROL
    return await get_sign_off_crew()


@router.get("/{crew_id}", response_model=dict)
async def get_crew_member(crew_id: str):
    crew = await get_crew_by_id(crew_id)
    if not crew:
        raise HTTPException(status_code=404, detail=f"Crew member {crew_id} not found")
    return crew
