"""
TITAN POS — Standalone Migration Runner
Applies pending SQL migrations from backend/migrations/ in order.
Standalone: does NOT import db/connection.py to avoid side-effects.

Usage:
    python3 db/migrate.py          # from backend/ directory
    DATABASE_URL must be set in environment.

Exit codes:
    0 = success (all migrations applied or already up to date)
    1 = failure (migration error, connection error, etc.)
"""
import os
import re
import sys
import glob
import asyncio
import logging

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="[MIGRATE] %(message)s",
)
log = logging.getLogger("migrate")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "migrations")

# Schema version table DDL (idempotent)
SCHEMA_VERSION_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (
    id BIGSERIAL PRIMARY KEY,
    version INTEGER NOT NULL UNIQUE,
    description TEXT,
    applied_at TIMESTAMP DEFAULT NOW()
);
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_VERSION_RE = re.compile(r"^(\d+)_")


def _parse_version(filename: str) -> int | None:
    """Extract numeric version from migration filename like '025_folio_index.sql'."""
    m = _VERSION_RE.match(os.path.basename(filename))
    return int(m.group(1)) if m else None


def _has_explicit_transaction(sql: str) -> bool:
    """Detect if the SQL already contains BEGIN; to avoid double-wrapping."""
    return bool(re.search(r"(?mi)^\s*BEGIN\s*;", sql))


def _get_dsn() -> str:
    """Read DATABASE_URL from env and strip +asyncpg suffix for asyncpg."""
    raw = os.environ.get("DATABASE_URL", "")
    if not raw:
        log.error("DATABASE_URL not set")
        sys.exit(1)
    return raw.replace("postgresql+asyncpg://", "postgresql://")


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
async def run_migrations() -> None:
    dsn = _get_dsn()
    conn: asyncpg.Connection = await asyncpg.connect(dsn)
    try:
        # 1. Ensure schema_version table exists
        await conn.execute(SCHEMA_VERSION_DDL)

        # 2. Get already-applied versions
        rows = await conn.fetch("SELECT version FROM schema_version")
        applied: set[int] = {r["version"] for r in rows}

        # 3. Discover migration files
        pattern = os.path.join(MIGRATIONS_DIR, "*.sql")
        files = sorted(glob.glob(pattern))
        pending: list[tuple[int, str]] = []
        for fpath in files:
            ver = _parse_version(fpath)
            if ver is not None and ver not in applied:
                pending.append((ver, fpath))
        pending.sort(key=lambda x: x[0])

        if not pending:
            log.info("Database up to date (latest: v%s)", max(applied) if applied else 0)
            return

        # 4. Apply each pending migration
        for ver, fpath in pending:
            fname = os.path.basename(fpath)
            sql = open(fpath, "r", encoding="utf-8").read()

            if _has_explicit_transaction(sql):
                # SQL manages its own transaction — execute as-is
                await conn.execute(sql)
            else:
                # Wrap in a transaction for atomicity
                async with conn.transaction():
                    await conn.execute(sql)

            log.info("Applied %s (v%d)", fname, ver)

        log.info(
            "All migrations applied (%d new, %d total)",
            len(pending),
            len(applied) + len(pending),
        )
    finally:
        await conn.close()


def main() -> None:
    try:
        asyncio.run(run_migrations())
    except asyncpg.PostgresError as exc:
        log.error("PostgreSQL error: %s", exc)
        sys.exit(1)
    except Exception as exc:
        log.error("Unexpected error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
