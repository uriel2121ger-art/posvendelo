import asyncio
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

_raw_url = os.getenv("DATABASE_URL")
if not _raw_url:
    raise RuntimeError("DATABASE_URL no está configurada para control-plane")

DATABASE_URL = _raw_url.replace("postgresql+asyncpg://", "postgresql://")

_pool: Optional[asyncpg.Pool] = None
_pool_lock = asyncio.Lock()


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool
    async with _pool_lock:
        if _pool is None:
            _pool = await asyncpg.create_pool(
                dsn=DATABASE_URL,
                min_size=1,
                max_size=10,
                command_timeout=30,
            )
            logger.info("control-plane asyncpg pool created")
    return _pool


async def close_pool() -> None:
    global _pool
    async with _pool_lock:
        if _pool is not None:
            await _pool.close()
            _pool = None
            logger.info("control-plane asyncpg pool closed")


def _named_to_positional(sql: str, params: Dict[str, Any]) -> tuple[str, list[Any]]:
    sql = sql.replace("::", "\x00CAST\x00")
    string_literals: list[str] = []

    def _save_literal(match: re.Match[str]) -> str:
        string_literals.append(match.group(0))
        return f"\x00STR{len(string_literals) - 1}\x00"

    sql = re.sub(r"'(?:''|[^'])*'", _save_literal, sql)
    param_order: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in param_order:
            param_order.append(name)
        return f"${param_order.index(name) + 1}"

    converted = re.sub(r":(\w+)", _replace, sql)
    for i, literal in enumerate(string_literals):
        converted = converted.replace(f"\x00STR{i}\x00", literal)
    converted = converted.replace("\x00CAST\x00", "::")

    args: list[Any] = []
    for name in param_order:
        value = params[name]
        if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}(T|$)", value.strip()):
            try:
                args.append(datetime.strptime(value.strip()[:10], "%Y-%m-%d"))
                continue
            except ValueError:
                pass
        args.append(value)
    return converted, args


class DB:
    __slots__ = ("_conn",)

    def __init__(self, conn: asyncpg.Connection):
        self._conn = conn

    async def fetch(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        merged = {**(params or {}), **kwargs}
        if merged:
            sql, args = _named_to_positional(sql, merged)
            rows = await self._conn.fetch(sql, *args)
        else:
            rows = await self._conn.fetch(sql)
        return [dict(r) for r in rows]

    async def fetchrow(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        merged = {**(params or {}), **kwargs}
        if merged:
            sql, args = _named_to_positional(sql, merged)
            row = await self._conn.fetchrow(sql, *args)
        else:
            row = await self._conn.fetchrow(sql)
        return dict(row) if row else None

    async def fetchval(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        merged = {**(params or {}), **kwargs}
        if merged:
            sql, args = _named_to_positional(sql, merged)
            return await self._conn.fetchval(sql, *args)
        return await self._conn.fetchval(sql)

    async def execute(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        merged = {**(params or {}), **kwargs}
        if merged:
            sql, args = _named_to_positional(sql, merged)
            return await self._conn.execute(sql, *args)
        return await self._conn.execute(sql)

    @property
    def connection(self) -> asyncpg.Connection:
        return self._conn


async def get_db() -> AsyncGenerator[DB, None]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield DB(conn)


@asynccontextmanager
async def get_connection() -> AsyncGenerator[DB, None]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield DB(conn)
