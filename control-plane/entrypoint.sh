#!/bin/bash
set -e

echo "[CP] Starting TITAN Control Plane..."
export DB_DSN="${DATABASE_URL//+asyncpg/}"

python3 -c "
import asyncio, asyncpg, os, sys
dsn = os.environ.get('DB_DSN', '')
async def check():
    for _ in range(45):
        try:
            conn = await asyncpg.connect(dsn)
            await conn.close()
            return
        except Exception:
            await asyncio.sleep(2)
    sys.exit(1)
asyncio.run(check())
"

exec python3 -m uvicorn main:app --host "${CP_HOST:-0.0.0.0}" --port "${CP_PORT:-9090}"
