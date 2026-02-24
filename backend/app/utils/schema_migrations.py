"""
Schema Migrations - Automatic database schema updates
Ensures database schema is always up-to-date across installations
"""

from datetime import datetime
import json
import logging
import time
from app.startup import DATA_DIR
from pathlib import Path
from typing import Union

from app.utils.path_utils import agent_log_enabled

logger = logging.getLogger("MIGRATIONS")

# Migration version - increment when adding new migrations
SCHEMA_VERSION = 9

MIGRATIONS = [
    # Version 1: Initial schema fixes
    {
        "version": 1,
        "description": "Add missing columns to core tables",
        "queries": [
            # backups table - ensure correct schema
            """CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY,
                filename TEXT NOT NULL,
                path TEXT NOT NULL,
                size INTEGER,
                checksum TEXT,
                timestamp TEXT,
                created_at TEXT,
                compressed INTEGER DEFAULT 0,
                encrypted INTEGER DEFAULT 0,
                notes TEXT,
                status TEXT DEFAULT 'active'
            )""",
            # branch_ticket_config - ensure business_razon_social exists
            "ALTER TABLE branch_ticket_config ADD COLUMN business_razon_social TEXT DEFAULT ''",
        ]
    },
    # Version 2: Sale items name column
    {
        "version": 2,
        "description": "Ensure sale_items has name column",
        "queries": [
            "ALTER TABLE sale_items ADD COLUMN name TEXT DEFAULT 'Producto'",
            "ALTER TABLE sale_items ADD COLUMN discount REAL DEFAULT 0",
        ]
    },
    # Version 3: Emitters table columns for Multi-Emitter Engine
    {
        "version": 3,
        "description": "Add missing columns to emitters table for Multi-Emitter Engine",
        "queries": [
            "ALTER TABLE emitters ADD COLUMN current_annual_sum DECIMAL(15,2) DEFAULT 0",
            "ALTER TABLE emitters ADD COLUMN limite_anual DECIMAL(15,2) DEFAULT 3500000",
            "ALTER TABLE emitters ADD COLUMN is_primary INTEGER DEFAULT 0",
            "ALTER TABLE emitters ADD COLUMN priority INTEGER DEFAULT 1",
            "ALTER TABLE emitters ADD COLUMN codigo_postal TEXT",
            "ALTER TABLE emitters ADD COLUMN domicilio TEXT",
            "ALTER TABLE emitters ADD COLUMN csd_cer_path TEXT",
            "ALTER TABLE emitters ADD COLUMN csd_key_path TEXT",
            "ALTER TABLE emitters ADD COLUMN csd_password TEXT",
            "ALTER TABLE emitters ADD COLUMN updated_at TEXT",
        ]
    },
    # Version 4: Ensure backups table has timestamp column
    {
        "version": 4,
        "description": "Ensure backups table has timestamp column",
        "queries": [
            "ALTER TABLE backups ADD COLUMN timestamp TEXT",
        ]
    },
    # Version 5: Add missing columns to backups and related_persons
    {
        "version": 5,
        "description": "Add missing columns to backups (compressed, encrypted, status, backup_type, expires_at, notes) and related_persons (relationship)",
        "queries": [
            "ALTER TABLE backups ADD COLUMN compressed INTEGER DEFAULT 0",
            "ALTER TABLE backups ADD COLUMN encrypted INTEGER DEFAULT 0",
            "ALTER TABLE backups ADD COLUMN status TEXT DEFAULT 'active'",
            "ALTER TABLE backups ADD COLUMN backup_type TEXT DEFAULT 'local'",
            "ALTER TABLE backups ADD COLUMN expires_at TEXT",
            "ALTER TABLE backups ADD COLUMN notes TEXT",
            "ALTER TABLE related_persons ADD COLUMN relationship TEXT",
        ]
    },
    # Version 6: Add synced_to_central column to sales table
    {
        "version": 6,
        "description": "Add synced_to_central column to sales table for central server synchronization tracking",
        "queries": [
            "ALTER TABLE sales ADD COLUMN synced_to_central INTEGER DEFAULT 0",
        ]
    },
    # Version 7: Add sync_version to synchronizable tables for conflict resolution
    {
        "version": 7,
        "description": "Add sync_version column to synchronizable tables for conflict resolution with timestamp comparison",
        "queries": [
            # Verificar existencia de tablas antes de agregar columnas
            # Tablas que siempre existen
            "ALTER TABLE products ADD COLUMN sync_version INTEGER DEFAULT 0",
            "ALTER TABLE products ADD COLUMN last_modified_by TEXT",
            "ALTER TABLE customers ADD COLUMN sync_version INTEGER DEFAULT 0",
            "ALTER TABLE customers ADD COLUMN last_modified_by TEXT",
            "ALTER TABLE employees ADD COLUMN sync_version INTEGER DEFAULT 0",
            "ALTER TABLE employees ADD COLUMN last_modified_by TEXT",
            "ALTER TABLE product_categories ADD COLUMN sync_version INTEGER DEFAULT 0",
            "ALTER TABLE product_categories ADD COLUMN last_modified_by TEXT",
            # Tablas opcionales (verificar existencia antes de modificar)
            # Estas se aplicarán condicionalmente en el código
            """CREATE TABLE IF NOT EXISTS sync_conflicts (
                id BIGSERIAL PRIMARY KEY,
                table_name TEXT NOT NULL,
                record_id INTEGER,
                record_identifier TEXT,
                conflict_type TEXT,
                existing_timestamp TEXT,
                new_timestamp TEXT,
                existing_sync_version INTEGER,
                new_sync_version INTEGER,
                conflict_reason TEXT,
                resolved_action TEXT DEFAULT 'skipped',
                terminal_id INTEGER,
                branch_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""",
            "CREATE INDEX IF NOT EXISTS idx_sync_conflicts_table_record ON sync_conflicts(table_name, record_id)",
            "CREATE INDEX IF NOT EXISTS idx_sync_conflicts_created ON sync_conflicts(created_at)",
            # Índices optimizados para sync incremental (CRÍTICO para 20k+ productos)
            # Nota: Solo crear índices en tablas que tienen updated_at
            "CREATE INDEX IF NOT EXISTS idx_products_sync ON products(updated_at, sync_version)",
            "CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku)",
            "CREATE INDEX IF NOT EXISTS idx_customers_sync ON customers(updated_at, sync_version)",
            # employees puede no tener updated_at, se maneja condicionalmente
            # "CREATE INDEX IF NOT EXISTS idx_employees_sync ON employees(updated_at, sync_version)",
            "CREATE INDEX IF NOT EXISTS idx_sales_sync ON sales(updated_at, sync_version)",
            "CREATE INDEX IF NOT EXISTS idx_sales_uuid ON sales(uuid)",
            # Tabla de checkpoints para sync incremental
            """CREATE TABLE IF NOT EXISTS sync_checkpoints (
                table_name TEXT PRIMARY KEY,
                last_sync_version INTEGER DEFAULT 0,
                last_sync_timestamp TEXT,
                last_sync_success INTEGER DEFAULT 1,
                sync_count INTEGER DEFAULT 0,
                last_error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""",
            "CREATE INDEX IF NOT EXISTS idx_sync_checkpoints_updated ON sync_checkpoints(updated_at)",
            # ============================================================
            # TRIGGERS POSTGRESQL para sync_version y synced
            # ============================================================
            # NOTA: PostgreSQL requiere:
            # 1. Crear una FUNCTION que retorna TRIGGER
            # 2. Crear el TRIGGER que ejecuta esa función
            # 3. Usar BEFORE UPDATE para modificar NEW directamente (evita recursión)
            # 4. No existe "CREATE TRIGGER IF NOT EXISTS", usamos DO $$ block
            # ============================================================

            # Función genérica para incrementar sync_version
            # Se usa BEFORE UPDATE para modificar NEW antes de escribir (sin recursión)
            """CREATE OR REPLACE FUNCTION fn_increment_sync_version()
            RETURNS TRIGGER AS $$
            BEGIN
                -- Solo incrementar si sync_version no cambió manualmente
                IF NEW.sync_version = OLD.sync_version THEN
                    NEW.sync_version = OLD.sync_version + 1;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql""",

            # Función para resetear synced cuando cambian datos importantes de producto
            """CREATE OR REPLACE FUNCTION fn_reset_product_synced()
            RETURNS TRIGGER AS $$
            BEGIN
                -- Solo resetear si hay cambios en campos importantes
                IF (OLD.synced = 1 OR NEW.synced = 1) AND (
                    NEW.name IS DISTINCT FROM OLD.name OR
                    NEW.price IS DISTINCT FROM OLD.price OR
                    NEW.cost IS DISTINCT FROM OLD.cost OR
                    NEW.stock IS DISTINCT FROM OLD.stock OR
                    NEW.description IS DISTINCT FROM OLD.description OR
                    NEW.category IS DISTINCT FROM OLD.category OR
                    NEW.sku IS DISTINCT FROM OLD.sku
                ) THEN
                    NEW.synced = 0;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql""",

            # Crear triggers (con DROP previo para idempotencia)
            # Products - sync_version
            "DROP TRIGGER IF EXISTS trg_products_sync_version ON products",
            """CREATE TRIGGER trg_products_sync_version
                BEFORE UPDATE ON products
                FOR EACH ROW
                WHEN (NEW.sync_version IS NOT DISTINCT FROM OLD.sync_version)
                EXECUTE FUNCTION fn_increment_sync_version()""",

            # Products - reset synced
            "DROP TRIGGER IF EXISTS trg_products_synced_reset ON products",
            """CREATE TRIGGER trg_products_synced_reset
                BEFORE UPDATE ON products
                FOR EACH ROW
                EXECUTE FUNCTION fn_reset_product_synced()""",

            # Customers - sync_version
            "DROP TRIGGER IF EXISTS trg_customers_sync_version ON customers",
            """CREATE TRIGGER trg_customers_sync_version
                BEFORE UPDATE ON customers
                FOR EACH ROW
                WHEN (NEW.sync_version IS NOT DISTINCT FROM OLD.sync_version)
                EXECUTE FUNCTION fn_increment_sync_version()""",

            # Employees - sync_version
            "DROP TRIGGER IF EXISTS trg_employees_sync_version ON employees",
            """CREATE TRIGGER trg_employees_sync_version
                BEFORE UPDATE ON employees
                FOR EACH ROW
                WHEN (NEW.sync_version IS NOT DISTINCT FROM OLD.sync_version)
                EXECUTE FUNCTION fn_increment_sync_version()""",

            # Product Categories - sync_version
            "DROP TRIGGER IF EXISTS trg_product_categories_sync_version ON product_categories",
            """CREATE TRIGGER trg_product_categories_sync_version
                BEFORE UPDATE ON product_categories
                FOR EACH ROW
                WHEN (NEW.sync_version IS NOT DISTINCT FROM OLD.sync_version)
                EXECUTE FUNCTION fn_increment_sync_version()""",
        ]
    },
    # Version 8: Persistent sync queue table
    {
        "version": 8,
        "description": "Add sync_queue table for persistent sync operations (FIX 2026-02-01)",
        "queries": [
            # Tabla para cola de sincronización persistente
            # Evita pérdida de datos si la app se reinicia durante sync
            """CREATE TABLE IF NOT EXISTS sync_queue (
                id BIGSERIAL PRIMARY KEY,
                table_name VARCHAR(50) NOT NULL,
                record_id INTEGER NOT NULL,
                payload JSONB,
                node_id VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                synced BOOLEAN DEFAULT FALSE,
                retry_count INTEGER DEFAULT 0,
                last_error TEXT
            )""",
            "CREATE INDEX IF NOT EXISTS idx_sync_queue_pending ON sync_queue(synced, created_at) WHERE synced = FALSE",
            "CREATE INDEX IF NOT EXISTS idx_sync_queue_table ON sync_queue(table_name, record_id)",
        ]
    },
    # Version 9: Idempotencia movimientos (Parte A Fase 2.4) + inventory_movements.synced
    {
        "version": 9,
        "description": "applied_inventory_movements for idempotency; inventory_movements.synced",
        "queries": [
            """CREATE TABLE IF NOT EXISTS applied_inventory_movements (
                id BIGSERIAL PRIMARY KEY,
                terminal_id VARCHAR(64) NOT NULL,
                movement_local_id BIGINT NOT NULL,
                applied_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(terminal_id, movement_local_id)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_applied_movements_key ON applied_inventory_movements(terminal_id, movement_local_id)",
            "ALTER TABLE inventory_movements ADD COLUMN IF NOT EXISTS synced INTEGER DEFAULT 0",
        ]
    },
]

def get_current_version(db_manager) -> int:
    """Get current schema version from database."""
    # #region agent log
    if agent_log_enabled():
        import json, time, os
        try:
            with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"schema_migrations.py:90","message":"get_current_version entry","data":{},"timestamp":int(time.time()*1000)})+"\n")
        except Exception as e: logger.debug("Writing get_current_version entry log: %s", e)
    # #endregion
    try:
        # Create version table if not exists
        db_manager.execute_write("""
            CREATE TABLE IF NOT EXISTS schema_version (
                id BIGSERIAL PRIMARY KEY,
                version INTEGER NOT NULL,
                applied_at TEXT NOT NULL
            )
        """)
        
        result = db_manager.execute_query("SELECT MAX(version) FROM schema_version")

        # FIX 2026-02-01: Simplificar lógica de validación para evitar IndexError
        # Validar que result tenga datos antes de acceder
        if not result or len(result) == 0:
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"schema_migrations.py:109","message":"get_current_version result","data":{"current_version":0,"reason":"no records in schema_version"},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logger.debug("Writing get_current_version no records log: %s", e)
            # #endregion
            return 0

        row = result[0]
        # Extraer el valor MAX(version) de forma segura
        if isinstance(row, dict):
            max_version = row.get('MAX(version)') or row.get('max') or row.get('max(version)')
        else:
            max_version = row[0] if row else None

        if max_version is None:
            return 0

        current_ver = int(max_version)
        # #region agent log
        if agent_log_enabled():
            try:
                with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"schema_migrations.py:115","message":"get_current_version result","data":{"current_version":current_ver,"target_version":SCHEMA_VERSION},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e: logger.debug("Writing get_current_version result log: %s", e)
        # #endregion
        return current_ver
        
    except Exception as e:
        # #region agent log
        if agent_log_enabled():
            try:
                with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"schema_migrations.py:122","message":"get_current_version error","data":{"error":str(e),"error_type":type(e).__name__},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e2: logger.debug("Writing get_current_version error log: %s", e2)
        # #endregion
        logger.error(f"Error getting schema version: {e}")
        return 0

def apply_migration(db_manager, migration: dict) -> bool:
    """Apply a single migration."""
    # #region agent log
    if agent_log_enabled():
        import json, time, os
        try:
            with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"schema_migrations.py:116","message":"apply_migration entry","data":{"version":migration["version"],"description":migration.get("description","")},"timestamp":int(time.time()*1000)})+"\n")
        except Exception as e: logger.debug("Writing apply_migration entry log: %s", e)
    # #endregion
    version = migration["version"]
    description = migration["description"]
    
    logger.info(f"Applying migration v{version}: {description}")
    
    operations = []
    for query in migration["queries"]:
        # #region agent log
        if agent_log_enabled():
            try:
                with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"schema_migrations.py:127","message":"Executing migration query","data":{"version":version,"query_preview":query[:200] if query else ""},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e: logger.debug("Writing migration query log: %s", e)
        # #endregion
        try:
            # Try to execute query
            db_manager.execute_write(query)
            logger.debug(f"  ✓ Executed: {query[:50]}...")
        except Exception as e:
            error_msg = str(e).lower()
            # Ignore "already exists" or "duplicate column" errors
            if "already exists" in error_msg or "duplicate" in error_msg:
                logger.debug(f"  ⏭ Skipped (already exists): {query[:50]}...")
                continue
            # Ignore "no such table" errors (tablas opcionales)
            elif "no such table" in error_msg:
                table_name = _extract_table_name_from_query(query)
                logger.debug(f"  ⚠️  Skipped (table '{table_name}' does not exist - optional table): {query[:50]}...")
                continue
            # Ignore "no such column" errors (columnas opcionales, como updated_at en employees)
            elif "no such column" in error_msg:
                column_name = _extract_column_name_from_query(query, error_msg)
                logger.debug(f"  ⚠️  Skipped (column '{column_name}' does not exist - optional column): {query[:50]}...")
                continue
            else:
                logger.error(f"  ✗ Failed: {query[:50]}... Error: {e}")
                return False
    
    # Record migration
    db_manager.execute_write(
        "INSERT INTO schema_version (version, applied_at) VALUES (%s, %s)",
        (version, datetime.now().isoformat())
    )
    
    # #region agent log
    if agent_log_enabled():
        try:
            with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"schema_migrations.py:186","message":"Migration completed successfully","data":{"version":version},"timestamp":int(time.time()*1000)})+"\n")
        except Exception as e: logger.debug("Writing migration completed log: %s", e)
    # #endregion
    logger.info(f"✅ Migration v{version} applied successfully")
    return True

def run_migrations(db_manager_or_path: Union[str, object]) -> dict:
    # #region agent log
    if agent_log_enabled():
        import json, time, os
        try:
            db_path_str = db_manager_or_path if isinstance(db_manager_or_path, str) else getattr(db_manager_or_path, 'db_path', 'unknown')
            with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"schema_migrations.py:146","message":"run_migrations entry","data":{"db_path":db_path_str,"SCHEMA_VERSION":SCHEMA_VERSION},"timestamp":int(time.time()*1000)})+"\n")
        except Exception as e: logger.debug("Writing run_migrations entry log: %s", e)
    # #endregion
    """
    Run all pending migrations on the database.
    
    Args:
        db_manager_or_path: DatabaseManager instance or path to SQLite database (for backward compatibility)
        
    Returns:
        Dictionary with migration results
    """
    result = {
        "success": True,
        "current_version": 0,
        "new_version": 0,
        "migrations_applied": 0,
        "errors": []
    }
    
    try:
        # Support both DatabaseManager and db_path (backward compatibility)
        if isinstance(db_manager_or_path, str):
            # Legacy: create DatabaseManager from path
            from src.infra.database import DatabaseManager
            from src.infra.database_central import SQLiteBackend
            backend = SQLiteBackend(db_manager_or_path)
            db_manager = DatabaseManager(backend=backend)
        else:
            # New: use provided DatabaseManager
            db_manager = db_manager_or_path
        
        current_version = get_current_version(db_manager)
        result["current_version"] = current_version
        
        # #region agent log
        if agent_log_enabled():
            try:
                with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"schema_migrations.py:214","message":"Migration version check","data":{"current_version":current_version,"target_version":SCHEMA_VERSION,"needs_migration":current_version < SCHEMA_VERSION},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e: logger.debug("Writing migration version check log: %s", e)
        # #endregion
        
        if current_version >= SCHEMA_VERSION:
            logger.info(f"Schema is up-to-date (v{current_version})")
            result["new_version"] = current_version
            return result
        
        logger.info(f"Current schema: v{current_version}, Target: v{SCHEMA_VERSION}")
        
        # Apply pending migrations
        for migration in MIGRATIONS:
            if migration["version"] > current_version:
                # #region agent log
                if agent_log_enabled():
                    try:
                        with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"schema_migrations.py:228","message":"Applying migration","data":{"version":migration["version"],"description":migration.get("description","")},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e: logger.debug("Writing applying migration log: %s", e)
                # #endregion
                success = apply_migration(db_manager, migration)
                if success:
                    # #region agent log
                    if agent_log_enabled():
                        try:
                            with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"schema_migrations.py:234","message":"Migration applied successfully","data":{"version":migration["version"]},"timestamp":int(time.time()*1000)})+"\n")
                        except Exception as e: logger.debug("Writing migration applied success log: %s", e)
                    # #endregion
                    result["migrations_applied"] += 1
                    current_version = migration["version"]
                else:
                    # #region agent log
                    if agent_log_enabled():
                        try:
                            with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"schema_migrations.py:241","message":"Migration failed","data":{"version":migration["version"]},"timestamp":int(time.time()*1000)})+"\n")
                        except Exception as e: logger.debug("Writing migration failed log: %s", e)
                    # #endregion
                    result["success"] = False
                    result["errors"].append(f"Migration v{migration['version']} failed")
                    break
        
        result["new_version"] = current_version
        # Nota: db_manager (DatabaseManager) gestiona sus propias conexiones; no hay conn que cerrar aquí.

        # #region agent log
        if agent_log_enabled():
            try:
                with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"schema_migrations.py:250","message":"run_migrations completed","data":{"final_version":current_version,"migrations_applied":result["migrations_applied"],"success":result["success"]},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e: logger.debug("Writing run_migrations completed log: %s", e)
        # #endregion
        
        if result["migrations_applied"] > 0:
            logger.info(f"🎉 {result['migrations_applied']} migrations applied. Schema now at v{current_version}")
        
        return result
        
    except Exception as e:
        logger.error(f"Migration error: {e}")
        result["success"] = False
        result["errors"].append(str(e))
        return result

def check_and_fix_columns(db_manager):
    """
    Quick check and fix for common column issues.
    Called during app startup for safety.
    """
    fixes = [
        # (table, column, default_value)
        ("branch_ticket_config", "business_razon_social", "''"),
        ("sale_items", "name", "'Producto'"),
        ("sale_items", "discount", "0"),
        ("products", "visible", "1"),
        # Emitters table columns for Multi-Emitter Engine
        ("emitters", "current_annual_sum", "0"),
        ("emitters", "limite_anual", "3500000"),
        ("emitters", "is_primary", "0"),
        ("emitters", "priority", "1"),
        ("emitters", "codigo_postal", "NULL"),
        ("emitters", "domicilio", "NULL"),
        ("emitters", "csd_cer_path", "NULL"),
        ("emitters", "csd_key_path", "NULL"),
        ("emitters", "csd_password", "NULL"),
        ("emitters", "updated_at", "NULL"),
        # Backups table - ensure all columns exist
        ("backups", "timestamp", "NULL"),
        ("backups", "compressed", "0"),
        ("backups", "encrypted", "0"),
        ("backups", "status", "'active'"),
        ("backups", "backup_type", "'local'"),
        ("backups", "expires_at", "NULL"),
        ("backups", "notes", "NULL"),
        # Sales table - ensure synced_to_central column exists
        ("sales", "synced_to_central", "0"),
        # Related persons table - ensure relationship column exists
        ("related_persons", "relationship", "NULL"),
        # Cash movements table - ensure user_id column exists (PostgreSQL)
        ("cash_movements", "user_id", "NULL"),
    ]
    
    for table, column, default in fixes:
        try:
            # Check if column exists using get_table_info
            table_info = db_manager.get_table_info(table)
            cols = [col.get('name') if isinstance(col, dict) else col[1] for col in table_info]
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"schema_migrations.py:242","message":"Checking column","data":{"table":table,"column":column,"exists":column in cols,"all_columns":cols},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logger.debug("Writing checking column log: %s", e)
            # #endregion
            if column not in cols:
                # #region agent log
                if agent_log_enabled():
                    try:
                        with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"schema_migrations.py:246","message":"Adding missing column","data":{"table":table,"column":column,"default":default},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e: logger.debug("Writing adding missing column log: %s", e)
                # #endregion
                # PostgreSQL: user_id needs INTEGER type, not just NULL default
                if table == "cash_movements" and column == "user_id":
                    try:
                        # nosec B608 - table/column from hardcoded fixes list, not user input
                        db_manager.execute_write(f"ALTER TABLE {table} ADD COLUMN {column} INTEGER")
                        # Add foreign key constraint if users table exists
                        try:
                            # nosec B608 - table/column from hardcoded fixes list
                            db_manager.execute_write(f"ALTER TABLE {table} ADD CONSTRAINT fk_{table}_user FOREIGN KEY ({column}) REFERENCES users(id)")
                        except Exception as fk_error:
                            # Foreign key might already exist or users table might not exist
                            logger.debug(f"Could not add foreign key constraint: {fk_error}")
                        logger.info(f"Added missing column: {table}.{column} (INTEGER)")
                    except Exception as e:
                        if "already exists" not in str(e).lower() and "duplicate" not in str(e).lower():
                            logger.warning(f"Could not add {table}.{column}: {e}")
                else:
                    # PostgreSQL requires data type before DEFAULT
                    # Infer type from default value
                    if default in ("0", "1") or (default.isdigit() if isinstance(default, str) else isinstance(default, (int, float))):
                        col_type = "INTEGER"
                    elif default in ("NULL", "''", "''"):
                        col_type = "TEXT"
                    elif default.startswith("'") and default.endswith("'"):
                        col_type = "TEXT"
                    else:
                        col_type = "TEXT"  # Default to TEXT for safety
                    
                    # nosec B608 - table/column/col_type/default from hardcoded fixes list, not user input
                    if default == "NULL":
                        db_manager.execute_write(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                    else:
                        db_manager.execute_write(f"ALTER TABLE {table} ADD COLUMN {column} {col_type} DEFAULT {default}")
                    logger.info(f"Added missing column: {table}.{column} ({col_type})")
                # #region agent log
                if agent_log_enabled():
                    try:
                        with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"schema_migrations.py:252","message":"Column added successfully","data":{"table":table,"column":column},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e: logger.debug("Writing column added success log: %s", e)
                # #endregion
        except Exception as e:
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"schema_migrations.py:256","message":"Column check error","data":{"table":table,"column":column,"error":str(e),"error_type":type(e).__name__},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e2: logger.debug("Writing column check error log: %s", e2)
            # #endregion
            if "no such table" not in str(e).lower():
                logger.debug(f"Column check skipped for {table}.{column}: {e}")


def _extract_table_name_from_query(query: str) -> str:
    """Extrae el nombre de la tabla de una query ALTER TABLE, CREATE TRIGGER o CREATE INDEX."""
    import re
    # Para ALTER TABLE
    match = re.search(r'ALTER TABLE\s+(\w+)', query, re.IGNORECASE)
    if match:
        return match.group(1)
    # Para CREATE TRIGGER ... ON
    match = re.search(r'ON\s+(\w+)', query, re.IGNORECASE)
    if match:
        return match.group(1)
    # Para CREATE INDEX ... ON
    match = re.search(r'CREATE INDEX.*ON\s+(\w+)', query, re.IGNORECASE)
    if match:
        return match.group(1)
    return "unknown"


def _extract_column_name_from_query(query: str, error_msg: str) -> str:
    """Extrae el nombre de la columna de un mensaje de error."""
    import re
    # Buscar en el mensaje de error: "no such column: column_name"
    match = re.search(r'no such column:\s*(\w+)', error_msg, re.IGNORECASE)
    if match:
        return match.group(1)
    # Buscar en la query: CREATE INDEX ... ON table(column_name, ...)
    match = re.search(r'\((\w+)', query)
    if match:
        return match.group(1)
    return "unknown"


if __name__ == "__main__":
    # Test migrations
    logging.basicConfig(level=logging.DEBUG)
    db_path = "data/databases/pos.db"
    result = run_migrations(db_path)
    print(f"Migration result: {result}")
