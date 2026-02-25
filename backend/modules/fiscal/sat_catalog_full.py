"""
SAT Full Catalog Manager - CFDI 4.0
Downloads and manages the complete SAT c_ClaveProdServ catalog (~50,000 entries)
stored in a local SQLite database for fast autocomplete searches.
Modified to use aiosqlite for async operations.

Dependencies: aiosqlite (pip install aiosqlite) - required for catalog storage
"""
from typing import List, Optional, Tuple
import logging
import os
from pathlib import Path

logger = logging.getLogger("SAT_CATALOG")

try:
    import aiosqlite
    HAS_AIOSQLITE = True
except ImportError:
    HAS_AIOSQLITE = False
    logger.warning("aiosqlite no instalado. Ejecutar: pip install aiosqlite")

SAT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "sat_catalog.db"

COMMON_CODES = [
    ("01010101", "No existe en el catálogo"),
    ("50101500", "Frutas"),
    ("50101700", "Verduras frescas"),
    ("50102300", "Lácteos"),
    ("50112000", "Carne y aves"),
    ("50131600", "Pan y productos de panadería"),
    ("50161800", "Bebidas no alcohólicas"),
    ("30111600", "Cemento y cal"),
    ("30131500", "Bloques y ladrillos"),
    ("53101500", "Camisas y blusas"),
    ("43211500", "Computadoras"),
    ("43211700", "Notebooks"),
    ("51241500", "Medicamentos de venta libre"),
    ("84111506", "Servicios de facturación"),
    ("80111500", "Servicios de asesoría"),
]

class SATCatalogManager:
    """Manages the SAT product/service catalog with SQLite storage."""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(SAT_DB_PATH)
    
    async def _ensure_db(self):
        if not HAS_AIOSQLITE: return
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS c_ClaveProdServ (
                    id INTEGER PRIMARY KEY,
                    clave TEXT UNIQUE NOT NULL,
                    descripcion TEXT NOT NULL,
                    categoria TEXT
                )
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_clave ON c_ClaveProdServ(clave)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_desc ON c_ClaveProdServ(descripcion)")
            await conn.commit()
            
            async with conn.execute("SELECT COUNT(*) FROM c_ClaveProdServ") as cursor:
                result = await cursor.fetchone()
                count = result[0] if result else 0

            if count == 0:
                await self._load_common_codes(conn)
    
    async def _load_common_codes(self, conn):
        for clave, descripcion in COMMON_CODES:
            await conn.execute(
                "INSERT OR IGNORE INTO c_ClaveProdServ (clave, descripcion) VALUES (?, ?)",
                (clave, descripcion)
            )
        await conn.commit()
        logger.info(f"Loaded {len(COMMON_CODES)} common SAT codes")
    
    async def search(self, query: str, limit: int = 50) -> List[Tuple[str, str]]:
        if not HAS_AIOSQLITE or not query or len(query) < 2: return []
        await self._ensure_db()
        
        query = query.strip()
        like_query = f"%{query}%"
        
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute("""
                SELECT clave, descripcion FROM c_ClaveProdServ
                WHERE clave LIKE ? OR descripcion LIKE ?
                ORDER BY clave LIMIT ?
            """, (like_query, like_query, limit)) as cursor:
                return await cursor.fetchall()
    
    async def get_description(self, clave: str) -> Optional[str]:
        if not HAS_AIOSQLITE: return None
        await self._ensure_db()
        
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute(
                "SELECT descripcion FROM c_ClaveProdServ WHERE clave = ?",
                (clave,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
    
    async def add_code(self, clave: str, descripcion: str, categoria: str = None):
        if not HAS_AIOSQLITE: return
        await self._ensure_db()
        
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT INTO c_ClaveProdServ (clave, descripcion, categoria)
                VALUES (?, ?, ?)
                ON CONFLICT (clave) DO UPDATE SET
                    descripcion = EXCLUDED.descripcion,
                    categoria = EXCLUDED.categoria
            """, (clave, descripcion, categoria))
            await conn.commit()
    
    async def import_from_csv(self, csv_path: str) -> int:
        import csv
        if not HAS_AIOSQLITE: return 0
        await self._ensure_db()
        
        count = 0
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    for row in reader:
                        if len(row) >= 2:
                            clave = row[0].strip()
                            descripcion = row[1].strip()
                            if clave and descripcion:
                                await conn.execute("""
                                    INSERT INTO c_ClaveProdServ (clave, descripcion)
                                    VALUES (?, ?)
                                    ON CONFLICT (clave) DO UPDATE SET
                                        descripcion = EXCLUDED.descripcion
                                """, (clave, descripcion))
                                count += 1
                await conn.commit()
                logger.info(f"Imported {count} SAT codes")
        except Exception as e:
            logger.error(f"Error importing CSV: {e}")
        return count

_catalog_manager = None

def get_catalog_manager() -> SATCatalogManager:
    global _catalog_manager
    if _catalog_manager is None:
        _catalog_manager = SATCatalogManager()
    return _catalog_manager

async def search_sat_catalog(query: str, limit: int = 50) -> List[Tuple[str, str]]:
    return await get_catalog_manager().search(query, limit)

async def get_sat_description(clave: str) -> Optional[str]:
    return await get_catalog_manager().get_description(clave)
