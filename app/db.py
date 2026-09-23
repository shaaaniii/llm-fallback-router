"""
PHASE 5 — Async database session management.

Default DATABASE_URL is a local SQLite file — the app runs with zero
external services out of the box. Point DATABASE_URL at Postgres
(docker-compose provides one) for anything beyond a single laptop:
SQLite doesn't handle concurrent writers well, which a real multi-worker
API needs.
"""

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base

engine = create_async_engine(settings.DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """
    Create tables if they don't exist.

    Convenient for local dev / SQLite. In a real deployment, use Alembic
    migrations (see alembic/) instead — this call is skipped in that case
    so migrations remain the single source of truth for schema changes.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session():
    async with SessionLocal() as session:
        yield session