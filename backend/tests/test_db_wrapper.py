"""Tests for db/connection.py — asyncpg DB wrapper and param conversion."""

import pytest
from db.connection import _named_to_positional, DB


# ============================================================================
# Named-to-positional param conversion
# ============================================================================

def test_basic_named_param():
    """Single named param converts to $1."""
    sql, args = _named_to_positional("SELECT * FROM t WHERE id = :id", {"id": 42})
    assert sql == "SELECT * FROM t WHERE id = $1"
    assert args == [42]


def test_multiple_distinct_params():
    """Multiple distinct params get sequential $N."""
    sql, args = _named_to_positional(
        "SELECT * FROM t WHERE a = :a AND b = :b LIMIT :limit",
        {"a": 1, "b": "x", "limit": 10}
    )
    assert "$1" in sql and "$2" in sql and "$3" in sql
    assert len(args) == 3


def test_same_param_reused():
    """Same param used multiple times maps to same $N."""
    sql, args = _named_to_positional(
        "AND (name ILIKE :s OR sku ILIKE :s OR barcode ILIKE :s)",
        {"s": "%test%"}
    )
    assert sql.count("$1") == 3
    assert "$2" not in sql
    assert args == ["%test%"]


def test_postgresql_cast_preserved():
    """PostgreSQL :: cast is not confused with named params."""
    sql, args = _named_to_positional(
        "INSERT INTO t (data) VALUES (:data::jsonb)",
        {"data": '{"key": 1}'}
    )
    assert "::jsonb" in sql
    assert "$1" in sql
    assert args == ['{"key": 1}']


def test_no_params():
    """SQL without params passes through unchanged."""
    sql, args = _named_to_positional("SELECT 1", {})
    assert sql == "SELECT 1"
    assert args == []


def test_multiple_casts():
    """Multiple casts in one query work correctly."""
    sql, args = _named_to_positional(
        "INSERT INTO t (a, b) VALUES (:a::jsonb, :b::text)",
        {"a": "{}", "b": "hello"}
    )
    assert "::jsonb" in sql
    assert "::text" in sql
    assert "$1" in sql and "$2" in sql


# ============================================================================
# DB wrapper — real database operations
# ============================================================================

async def test_db_fetch(db_session):
    """DB.fetch returns list of dicts."""
    rows = await db_session.fetch("SELECT 1 AS n, 'hello' AS greeting")
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0]["n"] == 1
    assert rows[0]["greeting"] == "hello"


async def test_db_fetchrow(db_session):
    """DB.fetchrow returns single dict."""
    row = await db_session.fetchrow("SELECT 42 AS answer")
    assert isinstance(row, dict)
    assert row["answer"] == 42


async def test_db_fetchrow_not_found(db_session):
    """DB.fetchrow returns None when no rows match."""
    row = await db_session.fetchrow("SELECT 1 WHERE FALSE")
    assert row is None


async def test_db_fetchval(db_session):
    """DB.fetchval returns single scalar value."""
    val = await db_session.fetchval("SELECT 99")
    assert val == 99


async def test_db_fetch_with_named_params(db_session):
    """DB.fetch with named params works against real DB."""
    rows = await db_session.fetch(
        "SELECT :a::int AS x, :b::text AS y",
        {"a": 7, "b": "test"}
    )
    assert rows[0]["x"] == 7
    assert rows[0]["y"] == "test"


async def test_db_fetch_products(db_session):
    """DB.fetch can query real products table with named params."""
    rows = await db_session.fetch(
        "SELECT id, name FROM products WHERE is_active = :active LIMIT :limit",
        {"active": 1, "limit": 3}
    )
    assert isinstance(rows, list)
    for row in rows:
        assert "id" in row
        assert "name" in row
