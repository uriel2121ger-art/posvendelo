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
# 1. Wait for PostgreSQL (max 45 attempts × 2s = 90s; da más margen al arranque)
# -----------------------------------------------------------
# Pausa breve para que la red entre contenedores esté lista tras depends_on
sleep 3
MAX_RETRIES=45
RETRY=0
# DSN para asyncpg (sin +asyncpg); se pasa por env para evitar problemas con caracteres en la contraseña
export DB_DSN="${DATABASE_URL//+asyncpg/}"

until python3 -c "
import asyncio, asyncpg, os, sys
dsn = os.environ.get('DB_DSN', '')
if not dsn:
    print('[ENTRYPOINT] ERROR: DB_DSN not set', file=sys.stderr)
    sys.exit(2)
async def check():
    try:
        conn = await asyncpg.connect(dsn)
        await conn.close()
    except Exception as e:
        print(f'[ENTRYPOINT] Connection failed: {type(e).__name__}: {e}', file=sys.stderr)
        sys.exit(1)
asyncio.run(check())
" 2>/tmp/pg_err.txt; do
    RETRY=$((RETRY + 1))
    if [ "$RETRY" -ge "$MAX_RETRIES" ]; then
        echo "[ENTRYPOINT] ERROR: PostgreSQL not available after ${MAX_RETRIES} attempts"
        cat /tmp/pg_err.txt 2>/dev/null || true
        exit 1
    fi
    echo "[ENTRYPOINT] Waiting for PostgreSQL... ($RETRY/$MAX_RETRIES)"
    cat /tmp/pg_err.txt 2>/dev/null || true
    sleep 2
done

echo "[ENTRYPOINT] PostgreSQL is ready"

# -----------------------------------------------------------
# 2. Bootstrap base schema if fresh DB (check if 'products' table exists)
# -----------------------------------------------------------
TABLE_EXISTS=$(python3 -c "
import asyncio, asyncpg, os
dsn = os.environ.get('DB_DSN', '')
async def check():
    conn = await asyncpg.connect(dsn)
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
import asyncio, asyncpg, os
dsn = os.environ.get('DB_DSN', '')
async def apply():
    conn = await asyncpg.connect(dsn)
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
