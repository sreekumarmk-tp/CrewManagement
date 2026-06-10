"""
Additively feed a small batch of sign-off crew into a LIVE Postgres `crew` table
so the sign-off workflow can be demoed end-to-end.

Unlike `scripts.seed_crew` (which DROPS and recreates the whole table), this script
is non-destructive: it upserts a handful of fresh `pool="signoff"` rows via
`session.merge`, leaving every existing crew row untouched. Safe to re-run.

These crew carry realistic "relief due" signals (long time onboard, some with an
expiring medical/visa) so they read as natural sign-off candidates.

Run from the backend directory:

    python -m scripts.seed_signoff_live
"""
import asyncio
from datetime import date, timedelta

from database.crew_orm import Crew
from database.db import AsyncSessionLocal


def _future(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _past(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


# New IDs in the SOF-3xxx band so they never collide with the SOF-2xxx demo seed.
SIGN_OFF_CREW = [
    {
        "crew_id": "SOF-3001",
        "name": "Emilio Navarro",
        "rank": "Chief Officer",
        "grade": "Grade A",
        "nationality": "Filipino",
        "vessel": "MV Pacific Star",
        "port": "Singapore",
        "joining_date": _past(255),          # ~8.5 months onboard — relief due
        "medical_expiry": _future(25),       # expiring soon
        "passport_expiry": _future(300),
        "stcw_status": "Valid",
        "visa_status": "Valid",
        "status": "Onboard",
    },
    {
        "crew_id": "SOF-3002",
        "name": "Oleksandr Tkachenko",
        "rank": "Second Engineer",
        "grade": "Grade A",
        "nationality": "Ukrainian",
        "vessel": "MT Crude Titan",
        "port": "Rotterdam",
        "joining_date": _past(210),
        "medical_expiry": _future(110),
        "passport_expiry": _future(420),
        "stcw_status": "Valid",
        "visa_status": "Expiring Soon",
        "status": "Onboard",
    },
    {
        "crew_id": "SOF-3003",
        "name": "Deepak Menon",
        "rank": "Master",
        "grade": "Grade A",
        "nationality": "Indian",
        "vessel": "MV Indian Ocean Pride",
        "port": "Dubai",
        "joining_date": _past(280),          # longest onboard — top relief priority
        "medical_expiry": _future(60),
        "passport_expiry": _future(540),
        "stcw_status": "Valid",
        "visa_status": "Valid",
        "status": "Onboard",
    },
    {
        "crew_id": "SOF-3004",
        "name": "Andreas Pappas",
        "rank": "Bosun",
        "grade": "Grade B",
        "nationality": "Greek",
        "vessel": "MV Mediterranean Queen",
        "port": "Piraeus",
        "joining_date": _past(175),
        "medical_expiry": _future(140),
        "passport_expiry": _future(360),
        "stcw_status": "Expiring Soon",
        "visa_status": "Valid",
        "status": "Onboard",
    },
    {
        "crew_id": "SOF-3005",
        "name": "Ferdinand Aquino",
        "rank": "Cook",
        "grade": "Grade C",
        "nationality": "Filipino",
        "vessel": "MV Atlantic Voyager",
        "port": "Manila",
        "joining_date": _past(190),
        "medical_expiry": _future(45),
        "passport_expiry": _future(280),
        "stcw_status": "Valid",
        "visa_status": "Valid",
        "status": "Onboard",
    },
]


def _to_row(data: dict) -> Crew:
    return Crew(
        crew_id=data["crew_id"],
        pool="signoff",
        name=data["name"],
        rank=data.get("rank"),
        grade=data.get("grade"),
        nationality=data.get("nationality"),
        vessel=data.get("vessel"),
        port=data.get("port"),
        joining_date=data.get("joining_date"),
        medical_expiry=data.get("medical_expiry"),
        passport_expiry=data.get("passport_expiry"),
        stcw_status=data.get("stcw_status", "Valid"),
        visa_status=data.get("visa_status", "Valid"),
        availability=data.get("availability"),
        experience_years=data.get("experience_years"),
        certifications=data.get("certifications"),
        match_score=data.get("match_score"),
        match_reason=data.get("match_reason"),
        status=data.get("status", "Onboard"),
    )


async def seed() -> None:
    # Upsert each row by primary key — non-destructive and re-runnable.
    async with AsyncSessionLocal() as session:
        for c in SIGN_OFF_CREW:
            await session.merge(_to_row(c))
        await session.commit()

    # Fill embeddings only for rows that lack one (force=False) and invalidate the
    # crew cache so the next sign-off list reflects the new rows.
    from database.embedding_repository import backfill_embeddings
    embedded = await backfill_embeddings()

    ids = ", ".join(c["crew_id"] for c in SIGN_OFF_CREW)
    print(
        f"Upserted {len(SIGN_OFF_CREW)} sign-off crew into Postgres "
        f"({embedded} embeddings backfilled).\n  {ids}"
    )


if __name__ == "__main__":
    asyncio.run(seed())
