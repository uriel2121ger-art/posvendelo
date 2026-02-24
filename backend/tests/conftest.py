"""
TITAN POS - Test Configuration

Provides async database fixtures and test utilities for the modules/ tests.
"""

import os
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Use test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://titan_user:POvBSlIvC9jB76ZtYBvaFw@localhost:5432/titan_pos",
)


@pytest.fixture
async def db_session():
    """Provide a fresh async database session per test.

    Creates a new engine connection per test to avoid asyncpg
    'another operation in progress' errors between tests.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    session = AsyncSession(bind=engine, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()
