"""
POSVENDELO - Async Database Connection (asyncpg direct)

Provides a connection pool and a thin DB wrapper that:
- Converts named params (:name) to positional ($N) for asyncpg
- Returns plain dicts instead of asyncpg Records
- Handles PostgreSQL :: casts correctly

Usage in routes:
    from db.connection import get_db
    @router.get("/")
    async def list_items(db=Depends(get_db)):
        rows = await db.fetch("SELECT * FROM items WHERE id = :id", {"id": 1})
"""

import asyncio
import os
import re
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

# Parse DATABASE_URL — strip +asyncpg suffix if present (from SQLAlchemy format)
_raw_url = os.getenv("DATABASE_URL")
if not _raw_url:
    raise RuntimeError(
        "DATABASE_URL no está configurada. "
        "Exporta la variable de entorno antes de iniciar el servidor. "
        "Ejemplo: export DATABASE_URL='postgresql://user:pass@localhost:5432/posvendelo'"
    )
DATABASE_URL = _raw_url.replace("postgresql+asyncpg://", "postgresql://")

# Global connection pool (with lock to prevent double-creation on concurrent startup)
_pool: Optional[asyncpg.Pool] = None
_pool_lock = asyncio.Lock()


async def get_pool() -> asyncpg.Pool:
    """Get or create the global connection pool."""
    global _pool
    if _pool is not None:
        return _pool
    async with _pool_lock:
        if _pool is None:
            _pool = await asyncpg.create_pool(
                dsn=DATABASE_URL,
                min_size=2,
                max_size=10,
                command_timeout=30,
            )
            logger.info("asyncpg connection pool created")
    return _pool


async def close_pool():
    """Close the connection pool (call at app shutdown)."""
    global _pool
    async with _pool_lock:
        if _pool is not None:
            await _pool.close()
            _pool = None
            logger.info("asyncpg connection pool closed")


def _named_to_positional(sql: str, params: Dict[str, Any]) -> tuple:
    """Convert :name params to $N positional params for asyncpg.

    Handles PostgreSQL :: casts (e.g., :data::jsonb) correctly by
    temporarily replacing :: before processing named params.
    """
    # Temporarily replace :: casts to avoid confusing them with params
    sql = sql.replace("::", "\x00CAST\x00")

    # Protect string literals from param substitution
    # Extract 'quoted strings' before processing params, then restore them
    string_literals: list = []

    def _save_literal(match):
        string_literals.append(match.group(0))
        return f"\x00STR{len(string_literals) - 1}\x00"

    sql = re.sub(r"'(?:''|[^'])*'", _save_literal, sql)

    param_order: list = []

    def replacer(match):
        name = match.group(1)
        if name not in param_order:
            param_order.append(name)
        idx = param_order.index(name) + 1
        return f"${idx}"

    converted = re.sub(r":(\w+)", replacer, sql)

    # Restore string literals
    for i, literal in enumerate(string_literals):
        converted = converted.replace(f"\x00STR{i}\x00", literal)

    # Restore :: casts
    converted = converted.replace("\x00CAST\x00", "::")

    try:
        raw_args = [params[name] for name in param_order]
    except KeyError as e:
        raise KeyError(
            f"SQL param {e} not found in params dict. "
            f"Available: {list(params.keys())}, Required: {param_order}"
        ) from e
    # asyncpg requires native Python objects for date/datetime columns.
    # Strings like "2026-03-10" → date, "2026-03-10T14:30:00" → datetime (naive UTC).
    args = []
    for v in raw_args:
        if isinstance(v, str) and re.match(r"^\d{4}-\d{2}-\d{2}(T| |$)", v.strip()):
            try:
                stripped = v.strip()
                if len(stripped) > 10 and ("T" in stripped or " " in stripped[10:11]):
                    # Full datetime string — preserve time, normalize to naive UTC
                    normalized = stripped.replace("Z", "+00:00")
                    parsed = datetime.fromisoformat(normalized)
                    if parsed.tzinfo is not None:
                        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
                    args.append(parsed)
                else:
                    # Date-only string — convert to date object
                    args.append(date.fromisoformat(stripped[:10]))
                continue
            except ValueError:
                pass
        args.append(v)
    return converted, args


class DB:
    """Thin wrapper around asyncpg connection for named parameters."""

    __slots__ = ("_conn",)

    def __init__(self, conn: asyncpg.Connection):
        self._conn = conn

    async def fetch(self, sql: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> List[Dict[str, Any]]:
        """Execute query with named params, return list of dicts."""
        merged = {**(params or {}), **kwargs}
        if merged:
            sql, args = _named_to_positional(sql, merged)
            rows = await self._conn.fetch(sql, *args)
        else:
            rows = await self._conn.fetch(sql)
        return [dict(r) for r in rows]

    async def fetchrow(self, sql: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """Execute query with named params, return single dict or None."""
        merged = {**(params or {}), **kwargs}
        if merged:
            sql, args = _named_to_positional(sql, merged)
            row = await self._conn.fetchrow(sql, *args)
        else:
            row = await self._conn.fetchrow(sql)
        return dict(row) if row else None

    async def fetchval(self, sql: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """Execute query with named params, return single value."""
        merged = {**(params or {}), **kwargs}
        if merged:
            sql, args = _named_to_positional(sql, merged)
            return await self._conn.fetchval(sql, *args)
        return await self._conn.fetchval(sql)

    async def execute(self, sql: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        """Execute a write query with named params. Returns status string."""
        merged = {**(params or {}), **kwargs}
        if merged:
            sql, args = _named_to_positional(sql, merged)
            return await self._conn.execute(sql, *args)
        return await self._conn.execute(sql)

    @property
    def connection(self) -> asyncpg.Connection:
        """Access the underlying asyncpg connection for transactions etc."""
        return self._conn


async def get_db() -> AsyncGenerator:
    """FastAPI dependency — yields a DB wrapper around an asyncpg connection."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield DB(conn)


@asynccontextmanager
async def get_connection():
    """Context manager for direct connection access (for saga steps, etc.).

    Usage:
        async with get_connection() as db:
            await db.execute("UPDATE ...")
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield DB(conn)


async def check_db_health() -> bool:
    """Check database connectivity."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


def escape_like(term: str) -> str:
    """Escape ILIKE special characters to prevent wildcard injection.

    Use when building ILIKE patterns from user input:
        params["search"] = f"%{escape_like(user_input)}%"
    """
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
