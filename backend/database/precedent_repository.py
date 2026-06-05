"""
Precedent-index data-access layer — async, Postgres-backed.

Stores and queries the `placement_precedents` table (the L4 placement history).
The key query is `find_precedents`: given a vacancy profile (rank, optionally
port/grade), return the most recent prior placements for it — this is what the
matching layer consults at the start of a sign-off.
"""
from typing import Optional

from sqlalchemy import func, select

from database.db import AsyncSessionLocal
from database.placement_precedent_orm import PlacementPrecedent


async def insert_precedent(record: dict) -> dict:
    """Append one completed placement to the history store."""
    async with AsyncSessionLocal() as session:
        row = PlacementPrecedent(**record)
        session.add(row)
        await session.commit()
        return row.to_dict()


async def find_precedents(
    rank: str,
    *,
    port: Optional[str] = None,
    grade: Optional[str] = None,
    limit: int = 5,
) -> list[dict]:
    """Most-recent-first prior placements matching the vacancy profile.

    Matches on rank (required) and, when provided, port — the core vacancy key.
    grade is matched too when supplied. Case-insensitive.
    """
    async with AsyncSessionLocal() as session:
        q = select(PlacementPrecedent)
        if rank:
            q = q.where(func.lower(PlacementPrecedent.rank) == rank.lower())
        if port:
            q = q.where(func.lower(PlacementPrecedent.port) == port.lower())
        if grade:
            q = q.where(func.lower(PlacementPrecedent.grade) == grade.lower())
        q = q.order_by(PlacementPrecedent.created_at.desc()).limit(limit)
        rows = (await session.execute(q)).scalars().all()
        return [r.to_dict() for r in rows]


async def list_precedents(limit: int = 100) -> list[dict]:
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(PlacementPrecedent)
                .order_by(PlacementPrecedent.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
        return [r.to_dict() for r in rows]


async def count_precedents() -> int:
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(PlacementPrecedent.precedent_id))).all()
        return len(rows)
