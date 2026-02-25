"""
TITAN POS - Test Configuration

Provides async database fixtures using asyncpg direct.
"""

import os
import pytest
import asyncpg

from db.connection import DB

# Use test database URL
_raw_url = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://titan_user:POvBSlIvC9jB76ZtYBvaFw@localhost:5432/titan_pos",
)
TEST_DATABASE_URL = _raw_url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.fixture
async def db_session():
    """Provide a DB wrapper inside a transaction that rolls back after each test."""
    conn = await asyncpg.connect(dsn=TEST_DATABASE_URL)
    tr = conn.transaction()
    await tr.start()
    try:
        yield DB(conn)
    finally:
        await tr.rollback()
        await conn.close()
