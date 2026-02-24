"""
TITAN POS - Employees Microservice Database Connection

Connects to the same PostgreSQL database as the monolith (shared database pattern).
Uses asyncpg for async operations.
"""

import os
import logging
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# Database URL from environment or default (same DB as monolith)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://titan_user:POvBSlIvC9jB76ZtYBvaFw@localhost:5432/titan_pos"
)

engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    echo=os.getenv("SQL_DEBUG", "false").lower() == "true",
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency for database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_session():
    """Context manager for manual session management."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_health() -> bool:
    """Check if database connection is healthy."""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute("SELECT 1")
            return result is not None
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
