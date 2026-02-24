"""
SAT Full Catalog Manager - CFDI 4.0
Downloads and manages the complete SAT c_ClaveProdServ catalog (~50,000 entries)
stored in a local SQLite database for fast autocomplete searches.
FIX 2026-02-01: Usar sqlite3 directamente en lugar de SQLiteBackend inexistente
"""
from typing import List, Optional, Tuple
import json
import logging
import os
from pathlib import Path
import sqlite3

logger = logging.getLogger("SAT_CATALOG")

# Database path for SAT catalog (SQLite fallback)
SAT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "sat_catalog.db"

# Common categories embedded for immediate use (before full download)
COMMON_CODES = [
    # General
    ("01010101", "No existe en el catálogo"),
    
    # Abarrotes
    ("50101500", "Frutas"),
    ("50101700", "Verduras frescas"),
    ("50102300", "Lácteos"),
    ("50112000", "Carne y aves"),
    ("50131600", "Pan y productos de panadería"),
    ("50151500", "Aceites y grasas comestibles"),
    ("50161800", "Bebidas no alcohólicas"),
    ("50171900", "Cereales"),
    ("50181900", "Botanas"),
    ("50192100", "Productos enlatados"),
    ("50201700", "Especias y condimentos"),
    ("50202201", "Café"),
    ("50161700", "Refrescos"),
    ("50171550", "Azúcar"),
    ("50161509", "Agua embotellada"),
    
    # Ferretería
    ("30111600", "Cemento y cal"),
    ("30131500", "Bloques y ladrillos"),
    ("31162800", "Clavos y tornillos"),
    ("27111700", "Herramientas de mano"),
    ("31211500", "Pinturas"),
    ("40141700", "Tubería PVC"),
    ("26121600", "Cables eléctricos"),
    ("39121700", "Lámparas"),
    
    # Ropa
    ("53101500", "Camisas y blusas"),
    ("53101600", "Pantalones"),
    ("53101800", "Ropa interior"),
    ("53111500", "Zapatos"),
    ("53111600", "Botas"),
    ("53102500", "Uniformes"),
    
    # Electrónica
    ("43211500", "Computadoras"),
    ("43211700", "Notebooks"),
    ("43211800", "Tablets"),
    ("43191500", "Teléfonos móviles"),
    ("43212100", "Impresoras"),
    ("52161505", "Televisores"),
    
    # Farmacia
    ("51241500", "Medicamentos de venta libre"),
    ("42311500", "Vendajes y gasas"),
    ("51181500", "Vitaminas y suplementos"),
    
    # Cosméticos y Skincare
    ("53131500", "Productos para el cuidado de la piel"),
    ("53131501", "Cremas faciales"),
    ("53131502", "Cremas corporales"),
    ("53131503", "Lociones"),
    ("53131504", "Protector solar"),
    ("53131505", "Exfoliantes"),
    ("53131506", "Mascarillas faciales"),
    ("53131507", "Sérum facial"),
    ("53131508", "Tónicos faciales"),
    ("53131509", "Contorno de ojos"),
    ("53131510", "Limpiadores faciales"),
    
    # Maquillaje
    ("53131600", "Productos de maquillaje"),
    ("53131601", "Base de maquillaje"),
    ("53131602", "Polvo facial"),
    ("53131603", "Rubor / Blush"),
    ("53131604", "Sombras de ojos"),
    ("53131605", "Delineador de ojos"),
    ("53131606", "Rímel / Máscara de pestañas"),
    ("53131607", "Labiales"),
    ("53131608", "Brillo labial / Gloss"),
    ("53131609", "Corrector / Concealer"),
    ("53131610", "Iluminador / Highlighter"),
    ("53131611", "Contorno / Bronzer"),
    ("53131612", "Primer / Prebase"),
    ("53131613", "Setting spray"),
    ("53131614", "Brochas de maquillaje"),
    ("53131615", "Esponjas de maquillaje"),
    
    # Perfumes
    ("53131700", "Perfumes y fragancias"),
    ("53131701", "Perfume de mujer"),
    ("53131702", "Perfume de hombre"),
    ("53131703", "Agua de colonia"),
    ("53131704", "Body mist"),
    ("53131705", "Desodorante"),
    ("53131706", "Antitranspirante"),
    
    # Cabello
    ("53131800", "Productos para el cabello"),
    ("53131801", "Shampoo"),
    ("53131802", "Acondicionador"),
    ("53131803", "Tratamiento capilar"),
    ("53131804", "Mascarilla capilar"),
    ("53131805", "Aceite para cabello"),
    ("53131806", "Tinte para cabello"),
    ("53131807", "Gel para cabello"),
    ("53131808", "Mousse para cabello"),
    ("53131809", "Spray fijador"),
    ("53131810", "Plancha para cabello"),
    ("53131811", "Secadora de cabello"),
    ("53131812", "Rizador de cabello"),
    
    # Uñas
    ("53131900", "Productos para uñas"),
    ("53131901", "Esmalte de uñas"),
    ("53131902", "Removedor de esmalte"),
    ("53131903", "Uñas postizas"),
    ("53131904", "Gel para uñas"),
    ("53131905", "Acrílico para uñas"),
    ("53131906", "Lima de uñas"),
    ("53131907", "Cortauñas"),
    
    # Higiene personal
    ("53132000", "Productos de higiene personal"),
    ("53132001", "Jabón corporal"),
    ("53132002", "Gel de baño"),
    ("53132003", "Crema de afeitar"),
    ("53132004", "Rastrillos / Afeitadoras"),
    ("53132005", "Pasta dental"),
    ("53132006", "Enjuague bucal"),
    ("53132007", "Hilo dental"),
    ("53132008", "Cepillo dental"),
    
    # Servicios
    ("84111506", "Servicios de facturación"),
    ("80111500", "Servicios de asesoría"),
    ("80111600", "Servicios de consultoría"),
    ("81112100", "Servicios de mantenimiento"),
    ("90111800", "Servicios de alimentación"),
    ("91111800", "Servicios personales"),
    ("91111801", "Servicio de maquillaje"),
    ("91111802", "Servicio de peinado"),
    ("91111803", "Manicure"),
    ("91111804", "Pedicure"),
    ("91111805", "Tratamiento facial"),
    ("91111806", "Masaje"),
    ("91111807", "Depilación"),
    
    # Papelería
    ("44121600", "Papel"),
    ("44121700", "Cuadernos"),
    ("44121800", "Sobres"),
    ("44111500", "Bolígrafos"),
    ("44121500", "Carpetas"),
    ("44111900", "Lápices"),
    
    # Limpieza
    ("47131800", "Productos de limpieza"),
    ("47131700", "Jabones"),
    ("47131600", "Detergentes"),
    ("47131500", "Desinfectantes"),
    
    # Automotriz
    ("25191500", "Aceites lubricantes"),
    ("25171900", "Filtros automotrices"),
    ("25172300", "Frenos"),
    ("25172100", "Baterías automotrices"),
    
    # Bebés
    ("53111900", "Ropa de bebé"),
    ("42231500", "Pañales"),
    ("42231600", "Toallitas húmedas"),
    ("50192200", "Fórmula para bebé"),
    
    # Mascotas
    ("10121500", "Alimento para perros"),
    ("10121600", "Alimento para gatos"),
    ("10151700", "Accesorios para mascotas"),
]

class _SQLiteCacheWrapper:
    """
    Wrapper simple para sqlite3 que imita la interfaz de DatabaseManager.
    FIX 2026-02-01: Reemplaza SQLiteBackend inexistente para caché local.
    Convierte automáticamente placeholders PostgreSQL (%s) a SQLite (?)
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = None

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _convert_query(self, query: str) -> str:
        """Convierte placeholders PostgreSQL (%s) a SQLite (?)."""
        # Reemplazar %s con ?
        converted = query.replace('%s', '?')
        # Convertir ON CONFLICT a INSERT OR REPLACE (simplificado)
        if 'ON CONFLICT' in converted:
            # SQLite moderno soporta ON CONFLICT, pero para compatibilidad
            # convertimos patrones simples
            converted = converted.replace(
                'ON CONFLICT (clave) DO NOTHING',
                'OR IGNORE'
            ).replace(
                'ON CONFLICT (clave) DO UPDATE SET descripcion = EXCLUDED.descripcion, categoria = EXCLUDED.categoria',
                'OR REPLACE'
            )
            if 'INSERT' in converted and 'OR IGNORE' in converted:
                converted = converted.replace('INSERT INTO', 'INSERT OR IGNORE INTO').replace('OR IGNORE INTO', 'INTO')
            if 'INSERT' in converted and 'OR REPLACE' in converted:
                converted = converted.replace('INSERT INTO', 'INSERT OR REPLACE INTO').replace('OR REPLACE INTO', 'INTO')
        return converted

    def execute_query(self, query: str, params: tuple = ()) -> list:
        conn = self._get_conn()
        converted_query = self._convert_query(query)
        cursor = conn.execute(converted_query, params)
        return cursor.fetchall()

    def execute_write(self, query: str, params: tuple = ()) -> int:
        conn = self._get_conn()
        converted_query = self._convert_query(query)
        cursor = conn.execute(converted_query, params)
        conn.commit()
        return cursor.lastrowid

    def execute_transaction(self, operations: list) -> bool:
        conn = self._get_conn()
        try:
            for query, params in operations:
                converted_query = self._convert_query(query)
                conn.execute(converted_query, params)
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False

    def list_tables(self) -> list:
        result = self.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        return [row[0] for row in result]


class SATCatalogManager:
    """Manages the SAT product/service catalog with database storage."""

    def __init__(self, db_manager=None, db_path: str = None):
        """
        Initialize SAT catalog manager.

        Args:
            db_manager: DatabaseManager instance (optional, will create SQLite cache if not provided)
            db_path: Path to SQLite database (only used if db_manager is None)
        """
        if db_manager:
            self.db = db_manager
            self.db_path = getattr(db_manager, 'db_path', None)
            self._use_sqlite = False
        else:
            # FIX 2026-02-01: Usar sqlite3 directamente para caché local
            db_path = db_path or str(SAT_DB_PATH)
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self.db_path = db_path
            self.db = _SQLiteCacheWrapper(db_path)
            self._use_sqlite = True

        self._ensure_db()
    
    def _ensure_db(self):
        """Create database and tables if they don't exist."""
        # Check if table exists
        try:
            tables = self.db.list_tables()
            table_exists = 'c_ClaveProdServ' in tables
        except Exception:
            table_exists = False

        if not table_exists:
            # FIX 2026-02-01: Usar sintaxis SQLite para caché local
            # El wrapper _SQLiteCacheWrapper ya maneja la conversión si se usa PostgreSQL
            if self._use_sqlite:
                self.db.execute_write("""
                    CREATE TABLE IF NOT EXISTS c_ClaveProdServ (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        clave TEXT UNIQUE NOT NULL,
                        descripcion TEXT NOT NULL,
                        categoria TEXT
                    )
                """)
            else:
                # PostgreSQL usa SERIAL
                self.db.execute_write("""
                    CREATE TABLE IF NOT EXISTS c_ClaveProdServ (
                        id SERIAL PRIMARY KEY,
                        clave TEXT UNIQUE NOT NULL,
                        descripcion TEXT NOT NULL,
                        categoria TEXT
                    )
                """)

            # Create indexes for fast search
            self.db.execute_write("CREATE INDEX IF NOT EXISTS idx_clave ON c_ClaveProdServ(clave)")
            self.db.execute_write("CREATE INDEX IF NOT EXISTS idx_desc ON c_ClaveProdServ(descripcion)")

        # Check if we need to load initial data
        result = self.db.execute_query("SELECT COUNT(*) FROM c_ClaveProdServ")
        count = result[0][0] if result and result[0] else 0

        if count == 0:
            self._load_common_codes()

    def _load_common_codes(self):
        """Load the embedded common codes into the database."""
        operations = []
        for clave, descripcion in COMMON_CODES:
            # FIX 2026-02-01: Usar sintaxis PostgreSQL (%s), el wrapper convierte si es SQLite
            operations.append((
                "INSERT INTO c_ClaveProdServ (clave, descripcion) VALUES (%s, %s) ON CONFLICT (clave) DO NOTHING",
                (clave, descripcion)
            ))
        
        if operations:
            self.db.execute_transaction(operations)
        logger.info(f"Loaded {len(COMMON_CODES)} common SAT codes")
    
    def search(self, query: str, limit: int = 50) -> List[Tuple[str, str]]:
        """Search for SAT codes by code or description."""
        if not query or len(query) < 2:
            return []
        
        query = query.strip()
        like_query = f"%{query}%"
        
        results = self.db.execute_query("""
            SELECT clave, descripcion FROM c_ClaveProdServ
            WHERE clave LIKE %s OR descripcion LIKE %s
            ORDER BY clave LIMIT %s
        """, (like_query, like_query, limit))
        
        # Convert to list of tuples
        if results:
            if isinstance(results[0], dict):
                return [(row.get('clave'), row.get('descripcion')) for row in results]
            else:
                return [(row[0], row[1]) for row in results]
        return []
    
    def get_description(self, clave: str) -> Optional[str]:
        """Get description for a specific code."""
        result = self.db.execute_query(
            "SELECT descripcion FROM c_ClaveProdServ WHERE clave = %s",
            (clave,)
        )
        
        if result:
            row = result[0]
            if isinstance(row, dict):
                return row.get('descripcion')
            else:
                return row[0]
        return None
    
    def add_code(self, clave: str, descripcion: str, categoria: str = None):
        """Add a custom code to the catalog."""
        # Use INSERT ... ON CONFLICT for PostgreSQL compatibility
        self.db.execute_write("""
            INSERT INTO c_ClaveProdServ (clave, descripcion, categoria)
            VALUES (%s, %s, %s)
            ON CONFLICT (clave) DO UPDATE SET descripcion = EXCLUDED.descripcion, categoria = EXCLUDED.categoria
        """, (clave, descripcion, categoria))
        
        # Note: FTS rebuild removed as it's SQLite-specific
        # If full-text search is needed, consider using PostgreSQL's tsvector
    
    def import_from_csv(self, csv_path: str) -> int:
        """
        Import SAT catalog from CSV file.
        Expected format: clave,descripcion
        Returns number of codes imported.
        """
        import csv
        
        operations = []
        count = 0
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                
                for row in reader:
                    if len(row) >= 2:
                        clave = row[0].strip()
                        descripcion = row[1].strip()
                        
                        if clave and descripcion:
                            try:
                                # Use INSERT ... ON CONFLICT for PostgreSQL compatibility
                                operations.append((
                                    """
                                    INSERT INTO c_ClaveProdServ (clave, descripcion)
                                    VALUES (%s, %s)
                                    ON CONFLICT (clave) DO UPDATE SET descripcion = EXCLUDED.descripcion
                                    """,
                                    (clave, descripcion)
                                ))
                                count += 1
                            except Exception as e:
                                logger.error(f"Error preparing import for {clave}: {e}")
            
            # Execute all operations in a transaction
            if operations:
                self.db.execute_transaction(operations)
            
            logger.info(f"Imported {count} SAT codes from {csv_path}")
            
        except Exception as e:
            logger.error(f"Error importing CSV: {e}")
        
        return count
    
    def get_count(self) -> int:
        """Get total number of codes in catalog."""
        result = self.db.execute_query("SELECT COUNT(*) FROM c_ClaveProdServ")
        if result:
            row = result[0]
            if isinstance(row, dict):
                return row.get('COUNT(*)', 0) or 0
            else:
                return row[0] or 0
        return 0
    
    def get_all_for_autocomplete(self) -> List[str]:
        """Get all codes formatted for autocomplete (code - description)."""
        rows = self.db.execute_query("SELECT clave, descripcion FROM c_ClaveProdServ ORDER BY clave")
        
        if rows:
            if isinstance(rows[0], dict):
                return [f"{row.get('clave')} - {row.get('descripcion')}" for row in rows]
            else:
                return [f"{row[0]} - {row[1]}" for row in rows]
        return []

# Singleton instance
_catalog_manager = None

def get_catalog_manager() -> SATCatalogManager:
    """Get or create the singleton catalog manager."""
    global _catalog_manager
    if _catalog_manager is None:
        _catalog_manager = SATCatalogManager()
    return _catalog_manager

def search_sat_catalog(query: str, limit: int = 50) -> List[Tuple[str, str]]:
    """Convenience function to search the SAT catalog."""
    return get_catalog_manager().search(query, limit)

def get_sat_description(clave: str) -> Optional[str]:
    """Convenience function to get description for a code."""
    return get_catalog_manager().get_description(clave)
