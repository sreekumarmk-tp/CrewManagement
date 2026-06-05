"""
Async SQLAlchemy engine + session factory for PostgreSQL.

The connection string comes from `settings.database_url`
(`postgresql+asyncpg://...`), which is loaded from backend/.env.
"""
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from config import settings

log = structlog.get_logger()

# `create_async_engine` requires the asyncpg driver URL (postgresql+asyncpg://).
engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


async def init_db() -> None:
    """Create tables that don't exist yet. Safe to call on every startup."""
    # Import models so they register on Base.metadata before create_all.
    from database import crew_orm  # noqa: F401
    from database import decision_orm  # noqa: F401 — L4 decision_traces table
    from database import placement_precedent_orm  # noqa: F401 — L4 precedent index

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Lightweight, idempotent migrations. create_all only CREATES missing tables —
    # it never ADDs columns to a table that already exists. The L4 #2 columns were
    # added to decision_traces after Phase 1 created it, so older databases need
    # them backfilled. Postgres supports ADD COLUMN IF NOT EXISTS; run best-effort
    # in its own transaction so a failure here can't roll back create_all.
    migrations = (
        "ALTER TABLE decision_traces ADD COLUMN IF NOT EXISTS is_repeat_query BOOLEAN DEFAULT FALSE",
        "ALTER TABLE decision_traces ADD COLUMN IF NOT EXISTS consulted_precedents JSON",
    )
    try:
        async with engine.begin() as conn:
            for stmt in migrations:
                await conn.execute(text(stmt))
    except Exception as exc:  # noqa: BLE001 - non-fatal; log and continue
        log.warning("db_migrate_failed", error=str(exc))

    log.info("db_initialized", url=settings.database_url.rsplit("@", 1)[-1])
