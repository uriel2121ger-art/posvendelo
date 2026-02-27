#!/bin/bash
set -e

# ============================================================
# TITAN POS — Container Entrypoint
# 1. Wait for PostgreSQL
# 2. Bootstrap base schema on fresh DB
# 3. Run migrations
# 4. Start uvicorn
# ============================================================

echo "[ENTRYPOINT] Starting TITAN POS API..."

# -----------------------------------------------------------
# 1. Wait for PostgreSQL (max 30 attempts × 2s = 60s)
# -----------------------------------------------------------
MAX_RETRIES=30
RETRY=0
DB_DSN="${DATABASE_URL//+asyncpg/}"

until python3 -c "
import asyncio, asyncpg, sys
async def check():
    try:
        conn = await asyncpg.connect('${DB_DSN}')
        await conn.close()
    except Exception:
        sys.exit(1)
asyncio.run(check())
" 2>/dev/null; do
    RETRY=$((RETRY + 1))
    if [ "$RETRY" -ge "$MAX_RETRIES" ]; then
        echo "[ENTRYPOINT] ERROR: PostgreSQL not available after ${MAX_RETRIES} attempts"
        exit 1
    fi
    echo "[ENTRYPOINT] Waiting for PostgreSQL... ($RETRY/$MAX_RETRIES)"
    sleep 2
done

echo "[ENTRYPOINT] PostgreSQL is ready"

# -----------------------------------------------------------
# 2. Bootstrap base schema if fresh DB (check if 'products' table exists)
# -----------------------------------------------------------
TABLE_EXISTS=$(python3 -c "
import asyncio, asyncpg
async def check():
    conn = await asyncpg.connect('${DB_DSN}')
    try:
        row = await conn.fetchval(
            \"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='products')\"
        )
        print('yes' if row else 'no')
    finally:
        await conn.close()
asyncio.run(check())
")

if [ "$TABLE_EXISTS" = "no" ]; then
    echo "[ENTRYPOINT] Fresh database detected — applying base schema..."
    SCHEMA_FILE="/app/db/schema.sql"
    if [ -f "$SCHEMA_FILE" ]; then
        python3 -c "
import asyncio, asyncpg
async def apply():
    conn = await asyncpg.connect('${DB_DSN}')
    try:
        sql = open('${SCHEMA_FILE}', 'r').read()
        await conn.execute(sql)
        print('[ENTRYPOINT] Base schema applied successfully')
    finally:
        await conn.close()
asyncio.run(apply())
"
    else
        echo "[ENTRYPOINT] WARNING: Schema file not found at ${SCHEMA_FILE}"
        echo "[ENTRYPOINT] Migrations will attempt to create tables incrementally"
    fi
fi

# -----------------------------------------------------------
# 3. Run migrations
# -----------------------------------------------------------
echo "[ENTRYPOINT] Running migrations..."
python3 db/migrate.py

# -----------------------------------------------------------
# 4. Start uvicorn (exec replaces shell — PID 1 = uvicorn)
# -----------------------------------------------------------
echo "[ENTRYPOINT] Starting uvicorn..."
exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
