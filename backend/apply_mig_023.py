import asyncio
from db.connection import get_pool
import os

async def apply_migration():
    os.environ["DATABASE_URL"] = "postgresql://admin:admin@localhost:5432/titan_db"
    pool = await get_pool()
    with open("migrations/023_add_facturapi_api_key_to_emitters.sql", "r") as f:
        sql = f.read()
    
    async with pool.acquire() as conn:
        print("Applying migration 023...")
        await conn.execute(sql)
        print("Migration applied successfully.")
    
    await pool.close()

if __name__ == "__main__":
    asyncio.run(apply_migration())
