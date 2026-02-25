"""
TITAN POS - Test Configuration

Provides async database fixtures using asyncpg direct.
"""

import os
import pytest
import asyncpg

from db.connection import DB

# Use test database URL (falls back to DATABASE_URL if TEST_DATABASE_URL not set)
_raw_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
if not _raw_url:
    raise RuntimeError(
        "TEST_DATABASE_URL o DATABASE_URL debe estar configurada para ejecutar tests."
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
