# TODO [REFACTOR]: Este archivo tiene ~1900 lineas. Considerar dividir en:
# - database_manager.py: Clase DatabaseManager principal
# - database_schema.py: Aplicacion de schema y validacion
# - database_migrations.py: Sistema de migraciones de columnas
# - database_views.py: Creacion y mantenimiento de vistas
"""
INFRA: DATABASE MODULE
Manejador de base de datos PostgreSQL.
Implementa Timeouts, Retry Logic y Auto-Schema.

Estructura:
1. DatabaseManager - Clase principal para operaciones de DB
2. initialize_db() - Función para inicializar la base de datos
3. _apply_schema() - Aplica el schema_postgresql.sql
4. _run_migrations() - Ejecuta migraciones de columnas
5. _apply_concurrency_safeguards() - Aplica triggers de seguridad
"""
from typing import List, Optional, Tuple, Any, Dict
from contextlib import contextmanager
import json
import logging
from pathlib import Path
# SQLite eliminado - Solo PostgreSQL
import time
import re

# Get project root directory dynamically for debug logging
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
_DEBUG_LOG_PATH = _PROJECT_ROOT / '.cursor' / 'debug.log'

def log_debug(location: str, message: str, data: dict = None, hypothesis_id: str = "A") -> None:
    """Log debug information to debug.log file."""
    try:
        _DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        log_entry = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000)
        }
        with open(_DEBUG_LOG_PATH, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
            f.flush()
    except Exception as e:
        logger.debug("Debug logging failed: %s", e)

logger = logging.getLogger("DB_MANAGER")

# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════
db_instance: Optional["DatabaseManager"] = None

# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE MANAGER CLASS
# ═══════════════════════════════════════════════════════════════════════════════
class DatabaseManager:
    """
    Manejador de base de datos PostgreSQL exclusivamente.
    
    Sistema usa solo PostgreSQL para evitar errores de sincronización.
    """
    
    def __init__(self, backend = None, config_path: str = None):
        """
        Inicializa DatabaseManager con backend PostgreSQL.
        
        Args:
            backend: Backend PostgreSQL (PostgreSQLBackend) - REQUERIDO
            config_path: Ruta a configuración (si no se proporciona backend)
        
        Raises:
            ValueError: Si no se proporciona backend ni config_path
            TypeError: Si backend no es PostgreSQLBackend
        """
        from src.infra.database_central import DatabaseInterface, PostgreSQLBackend
        
        if backend:
            # Usar backend proporcionado
            if not isinstance(backend, DatabaseInterface):
                raise TypeError(f"backend debe ser instancia de DatabaseInterface, recibido: {type(backend)}")
            if not isinstance(backend, PostgreSQLBackend):
                raise TypeError(f"backend debe ser PostgreSQLBackend. SQLite no está soportado.")
            self.backend = backend
        elif config_path:
            # Crear backend desde configuración
            from src.infra.database_central import create_database_backend
            self.backend = create_database_backend(config_path)
        else:
            raise ValueError(
                "backend o config_path debe ser proporcionado.\n"
                "PostgreSQL es requerido. Proporciona config_path con credenciales PostgreSQL."
            )

    def _ensure_directory(self):
        """Asegura que el directorio de la base de datos exista."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def _init_db_settings(self):
        """Aplica configuraciones de rendimiento PostgreSQL."""
        # PostgreSQL no requiere PRAGMA, las configuraciones se hacen a nivel de servidor
        # Aquí podríamos ejecutar SET statements si fuera necesario
        pass

    @contextmanager
    def get_connection(self):
        """Obtiene una conexión segura que se cierra automáticamente."""
        # Delegar al backend
        with self.backend.get_connection() as conn:
            yield conn

    def execute_query(self, query: str, params: tuple = ()) -> List[Any]:
        """Ejecuta una consulta de lectura (SELECT)."""
        # Delegar al backend
        try:
            return self.backend.execute_query(query, params)
        except Exception as e:
            # SECURITY: Don't log full query - may contain sensitive data
            # Log only the query type/table for debugging
            query_preview = query.strip()[:50].replace('\n', ' ')
            logger.error("Query Error: %s | Query preview: %s...", e, query_preview)
            raise RuntimeError(f"Database query failed: {e}") from e

    def execute_write(self, query: str, params: tuple = ()) -> int:
        """Ejecuta una consulta de escritura (INSERT/UPDATE/DELETE)."""
        # Delegar al backend (ya tiene retry logic)
        try:
            return self.backend.execute_write(query, params)
        except Exception as e:
            logger.error("Write Error: %s", e)
            raise RuntimeError(f"Database write failed: {e}") from e

    def execute_transaction(self, operations: List[Tuple[str, tuple]], timeout: int = None, validation_callback=None) -> Dict[str, Any]:
        """
        Ejecuta múltiples escrituras en una sola transacción atómica.
        
        Args:
            operations: Lista de tuplas (query, params)
            timeout: Timeout en segundos (opcional)
            validation_callback: Función opcional para validar resultados de SELECT FOR UPDATE
        
        Returns:
            Dict con success, inserted_ids, rowcounts, select_results
        """
        # Delegar al backend
        try:
            return self.backend.execute_transaction(operations, timeout=timeout, validation_callback=validation_callback)
        except Exception as e:
            logger.error("Transaction Failed: %s", e)
            raise RuntimeError(f"Database transaction failed: {e}") from e
    
    def list_tables(self) -> List[str]:
        """Lista todas las tablas en la base de datos."""
        return self.backend.list_tables()
    
    def get_table_info(self, table_name: str) -> List[dict]:
        """Obtiene información de columnas de una tabla."""
        return self.backend.get_table_info(table_name)

# ═══════════════════════════════════════════════════════════════════════════════
# INITIALIZATION FUNCTION (PUBLIC API)
# ═══════════════════════════════════════════════════════════════════════════════
def initialize_db(config_path: str = None) -> DatabaseManager:
    """
    Inicializa la base de datos PostgreSQL completa.
    
    1. Crea el DatabaseManager PostgreSQL
    2. Aplica el schema_postgresql.sql (crea todas las tablas)
    3. Ejecuta migraciones de columnas faltantes
    4. Aplica triggers de seguridad
    
    Args:
        config_path: Ruta al archivo de configuración database.json (requerido)
        
    Returns:
        DatabaseManager instance
        
    Raises:
        ValueError: Si config_path no está proporcionado o no existe
        ConnectionError: Si no se puede conectar a PostgreSQL
    """
    global db_instance
    
    # Buscar configuración en ubicaciones estándar si no se proporciona
    if not config_path:
        default_paths = [
            "data/config/database.json",
            "data/local_config.json",
            "config/database.json",
        ]
        for path in default_paths:
            if Path(path).exists():
                config_path = path
                break
    
    if not config_path or not Path(config_path).exists():
        raise ValueError(
            f"Archivo de configuración PostgreSQL no encontrado.\n"
            f"Busca en: {', '.join(default_paths) if 'default_paths' in locals() else 'data/config/database.json'}\n"
            f"PostgreSQL es requerido. Ver docs/INSTALACION_POSTGRESQL.md"
        )
    
    try:
        from src.infra.database_config import create_database_manager_from_config
        logger.info("Usando configuracion PostgreSQL desde: %s", config_path)
        db_instance = create_database_manager_from_config(config_path)
    except Exception as e:
        logger.error("Error inicializando PostgreSQL: %s", e)
        raise ConnectionError(
            f"No se pudo inicializar PostgreSQL.\n"
            f"Error: {e}\n"
            f"Verifica la configuración en {config_path} y que PostgreSQL esté corriendo."
        )
    
    # Aplicar schema (crea tablas)
    _apply_schema(db_instance)
    
    # Ejecutar migraciones (agrega columnas faltantes)
    _run_migrations(db_instance)
    
    # Aplicar triggers de seguridad
    _apply_concurrency_safeguards(db_instance)
    
    logger.info("Database initialization complete")
    return db_instance

# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMA APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

def _split_sql_statements(sql_text: str) -> list:
    """
    Divide el SQL en statements individuales, manejando correctamente:
    - CREATE TABLE con múltiples líneas (puede tener ); en misma línea o separado
    - Bloques DO $$ ... END $$
    - Funciones y vistas
    - Comentarios
    """
    statements = []
    lines = sql_text.split('\n')
    current_statement = []
    in_create_table = False
    in_do_block = False
    in_function = False
    in_view = False
    paren_count = 0
    dollar_quote_tag = None
    last_line_ended_with_paren = False
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        original_line = line  # Guardar línea original para detectar ); separado
        found_semicolon_in_table = False  # Flag para saber si ya agregamos la línea con );
        
        # Saltar líneas vacías y comentarios (pero mantenerlas si estamos en CREATE TABLE, VIEW o FUNCTION)
        if not line or line.startswith('--'):
            # Si estamos en CREATE TABLE, VIEW o FUNCTION, mantener comentarios dentro de la definición
            # (pero los filtraremos antes de hacer join)
            if (in_create_table or in_view or in_function) and line.startswith('--'):
                current_statement.append(line)
            # Para funciones, también mantener líneas vacías (pueden contener $$)
            elif in_function and not line:
                current_statement.append(line)
            i += 1
            continue
        
        # Detectar inicio de CREATE TABLE
        if line.upper().startswith('CREATE TABLE'):
            in_create_table = True
            paren_count = 0
            last_line_ended_with_paren = False
        
        # Detectar inicio de CREATE FUNCTION
        if line.upper().startswith('CREATE FUNCTION') or line.upper().startswith('CREATE OR REPLACE FUNCTION'):
            in_function = True
        
        # Detectar inicio de CREATE VIEW
        if line.upper().startswith('CREATE VIEW') or line.upper().startswith('CREATE OR REPLACE VIEW'):
            in_view = True
        
        # Detectar inicio de DO $$
        if line.upper().startswith('DO $$') or (line.upper().startswith('DO') and '$$' in line):
            in_do_block = True
            # Extraer tag del dollar quote (puede ser $$ o $tag$)
            dollar_match = re.search(r'\$(\w*)\$', line)
            if dollar_match:
                dollar_quote_tag = dollar_match.group(1)
            else:
                dollar_quote_tag = ''  # $$ sin tag
        
        # CRITICAL: Verificar fin de función ANTES de agregar line a current_statement
        # Las funciones terminan con END; seguido de $$ LANGUAGE plpgsql;
        if in_function:
            # Si encontramos $$ LANGUAGE plpgsql; en esta línea, cerrar función
            if '$$' in line and 'LANGUAGE' in line.upper() and line.endswith(';'):
                current_statement.append(line)
                # Filtrar comentarios antes de hacer join
                import re
                filtered_lines = []
                for stmt_line in current_statement:
                    # CRITICAL: Preservar líneas que solo tienen $$ (dollar quotes) o contienen $$ (como AS $$)
                    stmt_line_stripped = stmt_line.strip()
                    if stmt_line_stripped == '$$' or stmt_line_stripped.startswith('$$') or '$$' in stmt_line_stripped:
                        # Si la línea contiene $$, preservarla completa (no filtrar)
                        filtered_lines.append(stmt_line_stripped)
                        continue
                    if stmt_line.strip().startswith('--'):
                        continue
                    if '--' in stmt_line:
                        code_part = stmt_line.split('--')[0].strip()
                        if code_part:
                            filtered_lines.append(code_part)
                    else:
                        filtered_lines.append(stmt_line.strip())
                stmt = ' '.join(filtered_lines).strip()
                stmt = re.sub(r'  +', ' ', stmt)
                if stmt:
                    statements.append(stmt)
                current_statement = []
                in_function = False
                i += 1
                continue
            # Si encontramos END; pero aún no vemos $$ LANGUAGE, verificar próxima línea
            elif line.rstrip().endswith('END;'):
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if '$$' in next_line and 'LANGUAGE' in next_line.upper():
                        # Agregar END; y $$ LANGUAGE plpgsql;
                        current_statement.append(line)
                        current_statement.append(next_line)
                        # Filtrar comentarios antes de hacer join
                        import re
                        filtered_lines = []
                        for stmt_line in current_statement:
                            # CRITICAL: Preservar líneas que solo tienen $$ (dollar quotes) o contienen $$ (como AS $$)
                            stmt_line_stripped = stmt_line.strip()
                            if stmt_line_stripped == '$$' or stmt_line_stripped.startswith('$$') or '$$' in stmt_line_stripped:
                                # Si la línea contiene $$, preservarla completa (no filtrar)
                                filtered_lines.append(stmt_line_stripped)
                                continue
                            if stmt_line_stripped.startswith('--'):
                                continue
                            if '--' in stmt_line:
                                code_part = stmt_line.split('--')[0].strip()
                                if code_part:
                                    filtered_lines.append(code_part)
                            else:
                                filtered_lines.append(stmt_line_stripped)
                        stmt = ' '.join(filtered_lines).strip()
                        stmt = re.sub(r'  +', ' ', stmt)
                        if stmt:
                            statements.append(stmt)
                        current_statement = []
                        in_function = False
                        i += 2  # Saltar tanto END; como $$ LANGUAGE plpgsql; (2 líneas)
                        continue
        
        # Contar paréntesis para CREATE TABLE
        if in_create_table:
            paren_count += line.count('(') - line.count(')')
            line_clean = line.rstrip()
            
            # Detectar ); en la misma línea
            if line_clean.endswith(');'):
                last_line_ended_with_paren = False
                # Cerrar la tabla si paréntesis balanceados
                if paren_count <= 0:
                    current_statement.append(line)
                    # CRITICAL: Filtrar comentarios antes de hacer join
                    import re
                    filtered_lines = []
                    for stmt_line in current_statement:
                        # Si la línea es solo un comentario, eliminarla
                        if stmt_line.strip().startswith('--'):
                            continue
                        # Si la línea tiene código Y comentario, mantener solo el código
                        if '--' in stmt_line:
                            code_part = stmt_line.split('--')[0].strip()
                            if code_part:
                                filtered_lines.append(code_part)
                        else:
                            filtered_lines.append(stmt_line.strip())
                    stmt = ' '.join(filtered_lines).strip()
                    # Limpiar espacios múltiples
                    stmt = re.sub(r'  +', ' ', stmt)
                    if stmt:
                        statements.append(stmt)
                    current_statement = []
                    in_create_table = False
                    paren_count = 0
                    last_line_ended_with_paren = False
                    i += 1
                    continue
            # Detectar ) sin ; (puede estar en línea siguiente, incluso con línea vacía)
            elif line_clean.endswith(')'):
                # CRITICAL: Buscar ); en las siguientes líneas ANTES de agregar esta línea
                for j in range(i + 1, min(i + 5, len(lines))):  # Buscar hasta 4 líneas adelante
                    next_line_raw = lines[j]
                    next_line = next_line_raw.strip()
                    # Si encontramos ); completo
                    if next_line == ');':
                        # CRITICAL: Agregar esta línea (que termina con )) al statement
                        current_statement.append(line_clean)  # Línea con )
                        
                        # #region agent log
                        try:
                            log_debug("database.py:_split_sql_statements", "Before join - current_statement content", {"len":len(current_statement),"last_3":current_statement[-3:] if len(current_statement) >= 3 else current_statement}, "A")
                        except Exception as e:
                            logger.debug("Debug logging for SQL statement content failed: %s", e)
                        # #endregion
                        
                        # CRITICAL: Filtrar comentarios antes de hacer join
                        # Los comentarios SQL (-- ...) deben eliminarse porque se unen con código siguiente
                        import re
                        filtered_lines = []
                        for stmt_line in current_statement:
                            # Si la línea es solo un comentario, eliminarla
                            if stmt_line.strip().startswith('--'):
                                continue
                            # Si la línea tiene código Y comentario, mantener solo el código
                            if '--' in stmt_line:
                                # Extraer solo la parte antes del comentario
                                code_part = stmt_line.split('--')[0].strip()
                                if code_part:  # Solo agregar si hay código
                                    filtered_lines.append(code_part)
                            else:
                                filtered_lines.append(stmt_line.strip())
                        
                        # Hacer join solo con líneas de código (sin comentarios)
                        stmt = ' '.join(filtered_lines) + ');'
                        # Limpiar espacios múltiples
                        stmt = re.sub(r'  +', ' ', stmt)
                        stmt = stmt.strip()
                        
                        # #region agent log
                        try:
                            log_debug("database.py:_split_sql_statements", "After join - stmt fragment", {"stmt_end":stmt[-100:],"has_comment_issue":"--" in stmt and not stmt.strip().startswith("--")}, "A")
                        except Exception as e:
                            logger.debug("Debug logging for SQL statement fragment failed: %s", e)
                        # #endregion
                        
                        if stmt:
                            statements.append(stmt)
                        current_statement = []
                        in_create_table = False
                        paren_count = 0
                        last_line_ended_with_paren = False
                        i = j  # Saltar hasta la línea del );
                        found_semicolon_in_table = True
                        break
                    # Si encontramos solo ; (y no es comentario)
                    elif next_line == ';' or (next_line.startswith(';') and not next_line.startswith('--')):
                        # Agregar esta línea con ; ya incluido
                        current_statement.append(line_clean + ';')
                        stmt = ' '.join(current_statement).strip()
                        if stmt:
                            statements.append(stmt)
                        current_statement = []
                        in_create_table = False
                        paren_count = 0
                        last_line_ended_with_paren = False
                        i = j  # Saltar hasta la línea del ;
                        found_semicolon_in_table = True
                        break
                    # Si encontramos una línea no vacía que no es ;, dejar de buscar
                    elif next_line and not next_line.startswith('--'):
                        break
                
                if found_semicolon_in_table:
                    i += 1  # Incrementar i antes de continue
                    continue
                # Si no encontramos ;, marcar que terminó con ) y agregar la línea normalmente
                last_line_ended_with_paren = True
            else:
                last_line_ended_with_paren = False
        
        # Agregar línea a current_statement (después de todas las verificaciones)
        # EXCEPTO si ya la agregamos arriba (cuando encontramos );)
        # EXCEPTO si estamos en vista y la línea termina con ; (ya la procesamos arriba)
        # EXCEPTO si estamos en función y ya procesamos END; + $$ LANGUAGE (ya las agregamos arriba)
        if not found_semicolon_in_table and not (in_view and line.endswith(';')) and not (in_function and '$$' in line and 'LANGUAGE' in line.upper()):
            # CRITICAL: Agregar la línea original (con espacios/indentación) no line_clean
            # para preservar la estructura, especialmente comentarios
            current_statement.append(line)
        
        # Detectar fin de DO block: END $$;
        if in_do_block:
            if dollar_quote_tag:
                end_pattern = f'END ${dollar_quote_tag}$'
            else:
                end_pattern = 'END $$'
            
            # Buscar END $$ seguido de ; (puede estar en misma línea o siguiente)
            if end_pattern.upper() in line.upper():
                # Si termina con ; en la misma línea
                if line.endswith(';'):
                    stmt = ' '.join(current_statement).strip()
                    if stmt:
                        statements.append(stmt)
                    current_statement = []
                    in_do_block = False
                    dollar_quote_tag = None
                # Si ; está en la siguiente línea
                elif i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line == ';' or next_line.startswith(';'):
                        current_statement.append(';')
                        stmt = ' '.join(current_statement).strip()
                        if stmt:
                            statements.append(stmt)
                        current_statement = []
                        in_do_block = False
                        dollar_quote_tag = None
                        i += 1  # Saltar la línea del ;
                        continue
        
        # Detectar fin de función: $$ LANGUAGE plpgsql; (ya manejado arriba)
        
        # Detectar fin de vista: termina con ;
        elif in_view:
            if line.endswith(';'):
                current_statement.append(line)
                # Filtrar comentarios antes de hacer join (similar a CREATE TABLE)
                import re
                filtered_lines = []
                for stmt_line in current_statement:
                    # Si la línea es solo un comentario, eliminarla
                    if stmt_line.strip().startswith('--'):
                        continue
                    # Si la línea tiene código Y comentario, mantener solo el código
                    if '--' in stmt_line:
                        code_part = stmt_line.split('--')[0].strip()
                        if code_part:
                            filtered_lines.append(code_part)
                    else:
                        filtered_lines.append(stmt_line.strip())
                stmt = ' '.join(filtered_lines).strip()
                # Limpiar espacios múltiples
                stmt = re.sub(r'  +', ' ', stmt)
                if stmt:
                    statements.append(stmt)
                current_statement = []
                in_view = False
        
        # Para otros statements: terminar con ;
        elif not in_create_table and not in_do_block and not in_function and not in_view:
            if line.endswith(';'):
                stmt = ' '.join(current_statement).rstrip(';').strip()
                if stmt:
                    statements.append(stmt)
                current_statement = []
        
        i += 1
    
    # Si queda algo sin terminar, agregarlo
    if current_statement:
        stmt = ' '.join(current_statement).strip()
        if stmt:
            statements.append(stmt)
    
    return statements

def _get_statement_type(statement: str) -> str:
    """Identifica el tipo de statement SQL."""
    statement_upper = statement.upper().strip()
    if statement_upper.startswith('CREATE TABLE'):
        return 'CREATE TABLE'
    elif statement_upper.startswith('CREATE INDEX'):
        return 'CREATE INDEX'
    elif statement_upper.startswith('CREATE EXTENSION'):
        return 'CREATE EXTENSION'
    elif statement_upper.startswith('ALTER TABLE'):
        return 'ALTER TABLE'
    elif statement_upper.startswith('INSERT'):
        return 'INSERT'
    elif statement_upper.startswith('DO $$') or statement_upper.startswith('DO $'):
        return 'DO BLOCK (FOREIGN KEY)'
    elif statement_upper.startswith('CREATE FUNCTION'):
        return 'CREATE FUNCTION'
    elif statement_upper.startswith('CREATE TRIGGER'):
        return 'CREATE TRIGGER'
    elif statement_upper.startswith('CREATE OR REPLACE VIEW'):
        return 'CREATE VIEW'
    elif statement_upper.startswith('CREATE OR REPLACE FUNCTION'):
        return 'CREATE FUNCTION'
    else:
        return 'OTHER'

def _apply_schema(db: DatabaseManager) -> bool:
    """Aplica el schema_postgresql.sql (o schema.sql como fallback) para crear todas las tablas."""

    # Intentar usar schema PostgreSQL primero, luego schema.sql genérico
    schema_path = Path(__file__).parent / "schema_postgresql.sql"
    if not schema_path.exists():
        schema_path = Path(__file__).parent / "schema.sql"
    
    if not schema_path.exists():
        logger.error("Schema file not found at %s", schema_path)
        logger.error("   Current working directory: %s", Path.cwd())
        logger.error("   File parent: %s", Path(__file__).parent)
        
        return False
    
    try:
        logger.info("Applying schema from: %s", schema_path)
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        
        logger.info("Schema SQL size: %d bytes", len(schema_sql))

        with db.get_connection() as conn:
            logger.info("📋 Executing schema script...")
            
            # PostgreSQL: ejecutar SQL usando cursor (no tiene executescript)
            # Convertir sintaxis SQLite a PostgreSQL antes de ejecutar
            schema_sql = schema_sql.replace('INSERT OR IGNORE', 'INSERT')
            schema_sql = schema_sql.replace('AUTOINCREMENT', 'SERIAL')
            
            # CRITICAL: PostgreSQL requiere autocommit=False y manejo explícito de transacciones
            # Cada statement debe ejecutarse en su propia transacción para evitar bloqueos
            conn.autocommit = False
            
            cursor = conn.cursor()
            # CRITICAL: Parser mejorado que maneja CREATE TABLE, DO $$, funciones, etc.
            statements = _split_sql_statements(schema_sql)
            
            logger.info("Executing %d statements...", len(statements))
            success_count = 0
            error_count = 0
            error_details = []  # Lista para guardar detalles de errores
            
            for i, statement in enumerate(statements):
                if not statement:
                    continue
                
                # #region agent log
                try:
                    log_debug("database.py:_apply_schema", "About to execute statement", {"stmt_num":i+1,"stmt_type":"CREATE TABLE" if statement.upper().startswith("CREATE TABLE") else "OTHER","stmt_start":statement[:80],"stmt_end":statement[-80:],"stmt_len":len(statement)}, "B")
                except Exception as e:
                    logger.debug("Debug logging for statement execution failed: %s", e)
                # #endregion
                
                # Convertir INSERT OR IGNORE a INSERT ... ON CONFLICT DO NOTHING
                if 'INSERT' in statement.upper() and 'IGNORE' in statement.upper():
                    # Extraer la tabla y los valores
                    import re
                    # Fixed regex pattern - removed malformed %s placeholders
                    match = re.search(r'INSERT\s+OR\s+IGNORE\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)', statement, re.IGNORECASE)
                    if match:
                        table = match.group(1)
                        columns = match.group(2)
                        values = match.group(3)
                        # SECURITY: Validate table name format (alphanumeric + underscore only)
                        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table):
                            logger.error(f"Invalid table name in INSERT OR IGNORE: {table}")
                            continue
                        statement = f"INSERT INTO {table} ({columns}) VALUES ({values}) ON CONFLICT DO NOTHING"
                
                # CRITICAL: Ejecutar cada statement en su propia transacción
                # PostgreSQL requiere que cada statement tenga su propio commit/rollback
                # para evitar que un error aborte todas las operaciones posteriores
                try:
                    # #region agent log
                    try:
                        log_debug("database.py:_apply_schema", "Executing statement in PostgreSQL", {"stmt_num":i+1}, "C")
                    except Exception as e:
                        logger.debug("Debug logging for PostgreSQL statement execution failed: %s", e)
                    # #endregion
                    
                    # Asegurar que estamos en una transacción limpia
                    try:
                        conn.rollback()
                    except Exception as e:
                        logger.debug("Rollback before statement execution failed: %s", e)
                    
                    cursor.execute(statement)
                    conn.commit()
                    success_count += 1
                    
                    # #region agent log
                    try:
                        log_debug("database.py:_apply_schema", "Statement executed successfully", {"stmt_num":i+1}, "C")
                    except Exception as e:
                        logger.debug("Debug logging for successful statement failed: %s", e)
                    # #endregion
                except Exception as e:
                    # CRITICAL: Siempre hacer rollback antes de continuar
                    try:
                        conn.rollback()
                    except Exception as rollback_e:
                        logger.debug("Rollback after statement error failed: %s", rollback_e)

                    error_msg = str(e).lower()
                    statement_upper = statement.upper().strip()
                    
                    # GUARDAR DETALLE DEL ERROR (SIEMPRE, antes de verificar si se ignora)
                    error_detail = {
                        'statement_num': i + 1,
                        'error': str(e),
                        'error_type': type(e).__name__,
                        'statement_preview': statement[:500] if len(statement) > 500 else statement,
                        'statement_full': statement,  # Guardar statement completo para diagnóstico
                        'statement_type': _get_statement_type(statement)
                    }
                    error_details.append(error_detail)
                    
                    # Ignorar errores de "already exists" para tablas/constraints
                    if "already exists" in error_msg or "duplicate" in error_msg:
                        success_count += 1  # No es realmente un error
                        continue
                    # Si hay un error de transacción abortada, ya hicimos rollback
                    if "current transaction is aborted" in error_msg:
                        # Intentar resetear la conexión cerrando y reabriendo el cursor
                        try:
                            cursor.close()
                            cursor = conn.cursor()
                            conn.rollback()
                        except Exception as reset_e:
                            logger.debug("Resetting connection after aborted transaction failed: %s", reset_e)
                        continue
                    # CRITICAL: NO ignorar errores de "does not exist" - pueden ser críticos
                    # Solo ignorar si es un DROP o ALTER que referencia algo que no existe
                    if "does not exist" in error_msg:
                        # Si es un DROP o ALTER, es seguro ignorarlo
                        if statement_upper.startswith('DROP') or statement_upper.startswith('ALTER'):
                            logger.debug("Ignorando error 'does not exist' en DROP/ALTER: %s", statement[:100])
                            continue
                        # Si es CREATE INDEX y la columna no existe, es seguro ignorarlo
                        # (las columnas se agregarán en migraciones posteriores)
                        if statement_upper.startswith('CREATE INDEX'):
                            logger.debug("Ignorando error 'does not exist' en CREATE INDEX (columna se agregara en migracion): %s", statement[:200])
                            continue
                        # Si es CREATE VIEW y la columna no existe, es seguro ignorarlo
                        if statement_upper.startswith('CREATE') and 'VIEW' in statement_upper:
                            logger.debug("Ignorando error 'does not exist' en CREATE VIEW (columna se agregara en migracion): %s", statement[:200])
                            continue
                        # Si es COMMENT ON VIEW y la vista no existe, es seguro ignorarlo
                        if statement_upper.startswith('COMMENT') and 'VIEW' in statement_upper:
                            logger.debug("Ignorando error 'does not exist' en COMMENT ON VIEW (vista se creara despues): %s", statement[:200])
                            continue
                        # Para otros casos (CREATE TABLE, FOREIGN KEY, etc.), es CRÍTICO
                        logger.error("ERROR CRITICO en statement #%d/%d:", i+1, len(statements))
                        logger.error("   Error: %s", e)
                        logger.error("   Tipo: %s", error_detail['statement_type'])
                        logger.error("   SQL: %s...", statement[:300])
                        error_count += 1
                    else:
                        # Para otros errores, hacer rollback y continuar (evitar bloquear todo)
                        logger.error("ERROR en statement #%d/%d:", i+1, len(statements))
                        logger.error("   Error: %s", e)
                        logger.error("   Tipo: %s", error_detail['statement_type'])
                        logger.error("   SQL: %s...", statement[:300])
                        error_count += 1
            
            cursor.close()
            logger.info("Schema execution: %d successful, %d errors", success_count, error_count)
            
            # GUARDAR ERRORES EN ARCHIVO SI HAY ALGUNOS
            if error_details:
                # Usar ruta relativa al proyecto (sin hardcodeo)
                project_root = Path(__file__).parent.parent.parent
                error_log_path = project_root / "data" / "logs" / "schema_errors.log"
                error_log_path.parent.mkdir(parents=True, exist_ok=True)
                
                try:
                    from datetime import datetime
                    with open(error_log_path, 'w', encoding='utf-8') as f:
                        f.write("=" * 70 + "\n")
                        f.write("ERRORES DE SCHEMA POSTGRESQL\n")
                        f.write(f"Fecha: {datetime.now().isoformat()}\n")
                        f.write(f"Total errores: {len(error_details)}\n")
                        f.write("=" * 70 + "\n\n")
                        
                        for err in error_details:
                            f.write(f"\n{'='*70}\n")
                            f.write(f"Statement #{err['statement_num']}\n")
                            f.write(f"Tipo: {err['statement_type']}\n")
                            f.write(f"Error Type: {err.get('error_type', 'Unknown')}\n")
                            f.write(f"Error: {err['error']}\n")
                            f.write(f"\nSQL (Preview):\n{err['statement_preview']}\n")
                            f.write(f"\nSQL (Completo):\n{err.get('statement_full', err['statement_preview'])}\n")
                            f.write(f"{'='*70}\n")
                    
                    logger.error("%d errores detallados guardados en: %s", len(error_details), error_log_path)
                    logger.error("   Revisa el archivo para ver los errores especificos")
                except Exception as log_e:
                    logger.warning("No se pudo guardar log de errores: %s", log_e)
            
            # Agregar columnas faltantes desde el schema a tablas existentes
            logger.info("📋 Adding missing columns from schema to existing tables...")
            try:
                import re
                cursor = conn.cursor()
                # Verificar si origin_pc existe en sales
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'sales' 
                    AND column_name = 'origin_pc'
                """)
                if not cursor.fetchone():
                    # Intentar agregar la columna
                    try:
                        cursor.execute("ALTER TABLE sales ADD COLUMN IF NOT EXISTS origin_pc TEXT")
                        conn.commit()
                        logger.info("✅ Added missing column: sales.origin_pc")
                    except Exception as col_e:
                        conn.rollback()
                        error_msg = str(col_e).lower()
                        if "must be owner" in error_msg or "permission denied" in error_msg:
                            logger.warning("Cannot add sales.origin_pc: permission denied. Column will be added by migration when permissions are fixed.")
                        elif "already exists" in error_msg:
                            logger.debug("Column sales.origin_pc already exists")
                        else:
                            logger.debug("Could not add sales.origin_pc: %s", col_e)
                else:
                    conn.commit()  # Cerrar transacción implícita del SELECT
                    logger.debug("Column sales.origin_pc already exists")
                cursor.close()
            except Exception as e:
                logger.debug("Error checking/adding origin_pc column: %s", e)
            
            logger.info("📋 Schema script executed, checking tables...")
            
            # Verify tables were created (PostgreSQL usa information_schema)
            cursor = conn.cursor()
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
            tables = cursor.fetchall()
            table_names = [t[0] for t in tables]
            
            # CRITICAL: Verificar que las tablas críticas existan
            critical_tables = ['users', 'branches', 'products', 'sales', 'sale_items', 'turns', 'employees']
            missing_critical = []
            for table in critical_tables:
                if table not in table_names:
                    missing_critical.append(table)
                    logger.error("TABLA CRITICA FALTANTE: %s", table)
            
            if missing_critical:
                logger.error("ERROR CRITICO: %d tablas criticas NO se crearon:", len(missing_critical))
                for table in missing_critical:
                    logger.error("   - %s", table)
                logger.error("   Esto puede causar errores en la aplicacion")
                if error_details:
                    error_log_path = project_root / "data" / "logs" / "schema_errors.log"
                    logger.error("   Revisa el archivo de errores: %s", error_log_path)
                else:
                    logger.error("   Revisa los logs para mas detalles")
            else:
                logger.info("Todas las tablas criticas fueron creadas correctamente")
            
            conn.commit()  # Cerrar transacción implícita del SELECT
            cursor.close()
            logger.info("Database Schema Applied - %d tables created", len(tables))
            if len(tables) > 0:
                logger.info("   Sample tables: %s", [t[0] for t in tables[:10]])
            
            # Si hay tablas críticas faltantes, retornar False
            if missing_critical:
                return False

        return True
        
    except Exception as e:
        logger.error("Failed to apply schema: %s", e)
        import traceback
        logger.error("Traceback: %s", traceback.format_exc())
        
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# COLUMN MIGRATIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Lista de migraciones: (tabla, columna, definición)
# Estas columnas se agregan si no existen en las tablas
COLUMN_MIGRATIONS = [
    # Products
    ("products", "price_wholesale", "REAL DEFAULT 0.0"),
    ("products", "department", "TEXT"),
    ("products", "provider", "TEXT"),
    ("products", "tax_rate", "REAL DEFAULT 0.16"),
    ("products", "sale_type", "TEXT DEFAULT 'unit'"),
    ("products", "barcode", "TEXT"),
    ("products", "is_favorite", "INTEGER DEFAULT 0"),
    ("products", "min_stock", "REAL DEFAULT 5"),
    ("products", "stock", "REAL DEFAULT 0"),
    ("products", "category", "TEXT"),
    ("products", "max_stock", "REAL DEFAULT 1000"),
    ("products", "description", "TEXT"),
    ("products", "shadow_stock", "REAL DEFAULT 0"),
    ("products", "notes", "TEXT"),
    ("products", "cost_price", "REAL DEFAULT 0"),
    ("products", "sat_descripcion", "TEXT DEFAULT ''"),
    ("products", "visible", "INTEGER DEFAULT 1"),
    ("products", "entry_date", "TEXT"),
    ("products", "sat_code", "TEXT DEFAULT '01010101'"),
    ("products", "sat_unit", "TEXT DEFAULT 'H87'"),
    
    # Customers
    ("customers", "credit_limit", "REAL DEFAULT 0.0"),
    ("customers", "credit_balance", "REAL DEFAULT 0.0"),
    ("customers", "wallet_balance", "REAL DEFAULT 0.0"),
    ("customers", "address", "TEXT"),
    ("customers", "notes", "TEXT"),
    ("customers", "is_active", "INTEGER DEFAULT 1"),
    ("customers", "first_name", "TEXT"),
    ("customers", "last_name", "TEXT"),
    ("customers", "email_fiscal", "TEXT"),
    ("customers", "razon_social", "TEXT"),
    ("customers", "regimen_fiscal", "TEXT"),
    ("customers", "domicilio1", "TEXT"),
    ("customers", "domicilio2", "TEXT"),
    ("customers", "colonia", "TEXT"),
    ("customers", "municipio", "TEXT"),
    ("customers", "estado", "TEXT"),
    ("customers", "pais", "TEXT"),
    ("customers", "codigo_postal", "TEXT"),
    ("customers", "vip", "INTEGER DEFAULT 0"),
    ("customers", "credit_authorized", "INTEGER DEFAULT 0"),
    ("customers", "loyalty_points", "INTEGER DEFAULT 0"),
    ("customers", "fiscal_name", "TEXT"),
    ("customers", "city", "TEXT"),
    ("customers", "state", "TEXT"),
    ("customers", "postal_code", "TEXT"),
    ("customers", "loyalty_level", "TEXT DEFAULT 'BRONZE'"),
    
    # Users
    ("users", "name", "TEXT"),
    ("users", "branch_id", "INTEGER DEFAULT 1"),
    ("users", "email", "TEXT"),
    ("users", "phone", "TEXT"),
    ("users", "pin", "TEXT"),
    ("users", "last_login", "TEXT"),
    ("users", "created_at", "TEXT"),
    ("users", "updated_at", "TEXT"),
    ("users", "status", "TEXT DEFAULT 'active'"),
    
    # Turns
    ("turns", "notes", "TEXT"),
    ("turns", "pos_id", "INTEGER"),
    ("turns", "branch_id", "INTEGER"),
    ("turns", "terminal_id", "INTEGER"),
    
    # Sales
    ("sales", "mixed_card", "REAL DEFAULT 0"),
    ("sales", "pos_id", "TEXT"),
    ("sales", "branch_id", "INTEGER DEFAULT 1"),
    ("sales", "synced_from_terminal", "TEXT"),
    ("sales", "discount", "REAL DEFAULT 0"),
    ("sales", "notes", "TEXT"),
    ("sales", "origin_pc", "TEXT"),
    ("sales", "is_noise", "INTEGER DEFAULT 0"),
    ("sales", "rfc_used", "TEXT"),
    ("sales", "mixed_transfer", "REAL DEFAULT 0"),
    ("sales", "mixed_wallet", "REAL DEFAULT 0"),
    ("sales", "mixed_gift_card", "REAL DEFAULT 0"),
    ("sales", "card_last4", "TEXT"),
    ("sales", "auth_code", "TEXT"),
    ("sales", "transfer_reference", "TEXT"),
    ("sales", "payment_reference", "TEXT"),
    ("sales", "sync_status", "TEXT"),
    ("sales", "visible", "INTEGER DEFAULT 1"),
    ("sales", "is_cross_billed", "INTEGER DEFAULT 0"),
    
    # Sale Items
    ("sale_items", "name", "TEXT"),
    ("sale_items", "total", "REAL"),
    ("sale_items", "discount", "REAL DEFAULT 0"),
    ("sale_items", "sat_clave_prod_serv", "TEXT DEFAULT '01010101'"),
    ("sale_items", "sat_descripcion", "TEXT DEFAULT ''"),
    
    # Branches
    ("branches", "lockdown_active", "INTEGER DEFAULT 0"),
    ("branches", "lockdown_at", "TEXT"),
    ("branches", "code", "TEXT"),
    ("branches", "is_active", "INTEGER DEFAULT 1"),
    ("branches", "server_url", "TEXT"),
    ("branches", "api_token", "TEXT"),
    ("branches", "created_at", "TEXT"),
    ("branches", "updated_at", "TEXT"),
    
    # Employees
    ("employees", "is_active", "INTEGER DEFAULT 1"),
    
    # CFDIs
    ("cfdis", "rfc_emisor", "TEXT"),
    ("cfdis", "rfc_receptor", "TEXT"),
    ("cfdis", "subtotal", "REAL"),
    ("cfdis", "impuestos", "REAL"),
    ("cfdis", "forma_pago", "TEXT"),
    ("cfdis", "metodo_pago", "TEXT"),
    ("cfdis", "uso_cfdi", "TEXT"),
    ("cfdis", "fecha_emision", "TEXT"),
    ("cfdis", "estado", "TEXT DEFAULT 'pendiente'"),
    ("cfdis", "fecha_cancelacion", "TEXT"),
    ("cfdis", "motivo_cancelacion", "TEXT"),
    ("cfdis", "uuid", "TEXT"),
    ("cfdis", "xml_path", "TEXT"),
    ("cfdis", "pdf_path", "TEXT"),
    ("cfdis", "total", "REAL"),
    ("cfdis", "customer_id", "INTEGER"),
    ("cfdis", "sale_id", "INTEGER"),
    ("cfdis", "facturapi_id", "TEXT DEFAULT ''"),
    ("cfdis", "sync_status", "TEXT"),
    ("cfdis", "nombre_receptor", "TEXT"),
    ("cfdis", "regimen_receptor", "TEXT"),
    ("cfdis", "xml_original", "TEXT"),
    ("cfdis", "xml_timbrado", "TEXT"),
    
    # Fiscal Config
    ("fiscal_config", "branch_id", "INTEGER DEFAULT 1"),
    ("fiscal_config", "created_at", "TEXT"),
    ("fiscal_config", "updated_at", "TEXT"),
    ("fiscal_config", "csd_key_password_encrypted", "TEXT"),
    ("fiscal_config", "pac_password_encrypted", "TEXT"),
    ("fiscal_config", "rfc_emisor", "TEXT"),
    ("fiscal_config", "razon_social_emisor", "TEXT"),
    ("fiscal_config", "pac_base_url", "TEXT"),
    ("fiscal_config", "pac_user", "TEXT"),
    ("fiscal_config", "csd_cert_path", "TEXT"),
    ("fiscal_config", "csd_key_path", "TEXT"),
    ("fiscal_config", "csd_key_password", "TEXT"),
    ("fiscal_config", "pac_password", "TEXT"),
    ("fiscal_config", "facturapi_enabled", "INTEGER DEFAULT 0"),
    ("fiscal_config", "facturapi_api_key", "TEXT DEFAULT ''"),
    ("fiscal_config", "facturapi_organization_id", "TEXT DEFAULT ''"),
    ("fiscal_config", "facturapi_sandbox", "INTEGER DEFAULT 1"),
    ("fiscal_config", "facturapi_key", "TEXT"),
    ("fiscal_config", "facturapi_mode", "TEXT DEFAULT 'test'"),
    ("fiscal_config", "active", "INTEGER DEFAULT 1"),
    ("fiscal_config", "codigo_postal", "TEXT"),
    
    # Customers
    ("customers", "ciudad", "TEXT"),
    
    # CFDIs
    ("cfdis", "cancelado", "INTEGER DEFAULT 0"),
    ("cfdis", "lugar_expedicion", "TEXT"),
    ("cfdis", "regimen_fiscal", "TEXT"),
    ("cfdis", "sync_date", "TEXT"),
    ("cfdis", "synced", "INTEGER DEFAULT 0"),

    # Ticket Config
    ("branch_ticket_config", "business_razon_social", "TEXT"),
    ("branch_ticket_config", "business_regime", "TEXT"),
    ("branch_ticket_config", "business_street", "TEXT"),
    ("branch_ticket_config", "business_cross_streets", "TEXT"),
    ("branch_ticket_config", "business_neighborhood", "TEXT"),
    ("branch_ticket_config", "business_city", "TEXT"),
    ("branch_ticket_config", "business_state", "TEXT"),
    ("branch_ticket_config", "business_postal_code", "TEXT"),
    ("branch_ticket_config", "margin_top", "INTEGER DEFAULT 0"),
    ("branch_ticket_config", "margin_bottom", "INTEGER DEFAULT 0"),
    ("branch_ticket_config", "show_invoice_code", "INTEGER DEFAULT 0"),
    ("branch_ticket_config", "invoice_url", "TEXT"),
    ("branch_ticket_config", "invoice_days_limit", "INTEGER DEFAULT 30"),
    
    # Loss Records
    ("loss_records", "product_name", "TEXT"),
    ("loss_records", "product_sku", "TEXT"),
    ("loss_records", "category", "TEXT"),
    ("loss_records", "witness_name", "TEXT"),
    ("loss_records", "status", "TEXT DEFAULT 'pending'"),
    ("loss_records", "authorized_at", "TEXT"),
    ("loss_records", "climate_justification", "TEXT"),
    ("loss_records", "photo_path", "TEXT"),
    
    # Inventory Transfers
    ("inventory_transfers", "completed_at", "TEXT"),
    ("inventory_transfers", "transfer_id", "TEXT"),
    ("inventory_transfers", "from_branch", "TEXT"),
    ("inventory_transfers", "to_branch", "TEXT"),
    ("inventory_transfers", "items_count", "INTEGER DEFAULT 0"),
    
    # Cash Expenses
    ("cash_expenses", "branch_id", "INTEGER DEFAULT 1"),
    ("cash_expenses", "vendor_name", "TEXT"),
    ("cash_expenses", "vendor_phone", "TEXT"),
    ("cash_expenses", "registered_by", "INTEGER"),
    
    # Cash Movements
    ("cash_movements", "branch_id", "INTEGER"),
    ("cash_movements", "description", "TEXT"),
    
    # Inventory Log
    ("inventory_log", "change_type", "TEXT"),
    ("inventory_log", "quantity", "REAL"),
    ("inventory_log", "notes", "TEXT"),
    
    # Inventory Movements
    ("inventory_movements", "type", "TEXT"),
    
    # Credit Movements
    ("credit_movements", "balance_after", "REAL DEFAULT 0"),
    ("credit_movements", "sale_id", "INTEGER"),
    ("credit_movements", "type", "TEXT"),
    
    # Cash Extractions
    ("cash_extractions", "document_type", "TEXT"),
    ("cash_extractions", "related_person_id", "INTEGER"),
    ("cash_extractions", "beneficiary_name", "TEXT"),
    ("cash_extractions", "purpose", "TEXT"),
    ("cash_extractions", "contract_hash", "TEXT"),
    ("cash_extractions", "contract_path", "TEXT"),
    ("cash_extractions", "requires_notary", "INTEGER DEFAULT 0"),
    ("cash_extractions", "notary_date", "TEXT"),
    ("cash_extractions", "notary_number", "TEXT"),
    ("cash_extractions", "banked", "INTEGER DEFAULT 0"),
    ("cash_extractions", "bank_date", "TEXT"),
    ("cash_extractions", "status", "TEXT DEFAULT 'pending'"),
    ("cash_extractions", "created_at", "TEXT"),
    
    # Audit Log
    ("audit_log", "username", "TEXT"),
    ("audit_log", "entity_type", "TEXT"),
    ("audit_log", "success", "INTEGER DEFAULT 1"),
    ("audit_log", "details", "TEXT"),
    
    # Loyalty Accounts
    ("loyalty_accounts", "saldo_actual", "REAL DEFAULT 0.00"),
    ("loyalty_accounts", "saldo_pendiente", "REAL DEFAULT 0.00"),
    ("loyalty_accounts", "status", "TEXT DEFAULT 'ACTIVE'"),
    ("loyalty_accounts", "flags_fraude", "INTEGER DEFAULT 0"),
    ("loyalty_accounts", "ultima_alerta", "TEXT"),
    ("loyalty_accounts", "fecha_ultima_actividad", "TEXT"),
    
    # Layaways
    ("layaways", "branch_id", "INTEGER"),
    
    # Returns
    ("returns", "branch_id", "INTEGER"),
    
    # ========== SYNC AUTOMÁTICO CON SCHEMA.SQL (2026-01-07) ==========
    # Cash Extractions
    ("cash_extractions", "turn_id", "INTEGER"),
    ("cash_extractions", "authorized_by", "INTEGER"),
    ("cash_extractions", "branch_id", "INTEGER DEFAULT 1"),
    ("cash_expenses", "user_id", "INTEGER"),
    ("credit_movements", "created_at", "TEXT"),
    ("inventory_transfers", "created_by", "INTEGER"),
    
    # Loyalty
    ("loyalty_accounts", "total_points", "INTEGER DEFAULT 0"),
    ("loyalty_accounts", "available_points", "INTEGER DEFAULT 0"),
    ("loyalty_accounts", "total_spent", "REAL DEFAULT 0"),
    ("loyalty_accounts", "visits", "INTEGER DEFAULT 0"),
    ("loyalty_accounts", "created_at", "TEXT"),
    
    # Backups
    ("backups", "backup_type", "TEXT DEFAULT 'local'"),
    ("backups", "expires_at", "TEXT"),
    
    # Related Persons
    ("related_persons", "tipo_relacion", "TEXT"),
    ("related_persons", "is_active", "INTEGER DEFAULT 1"),
    
    # Personal Expenses
    ("personal_expenses", "justified", "INTEGER DEFAULT 0"),
    
    # Shadow Movements
    ("shadow_movements", "shadow_stock_after", "REAL"),
    
    # Card Transactions
    ("card_transactions", "gift_card_id", "INTEGER"),
    ("card_transactions", "transaction_type", "TEXT"),
    ("card_transactions", "created_at", "TEXT"),
    
    # Anonymous Wallet
    ("anonymous_wallet", "wallet_hash", "TEXT"),
    ("anonymous_wallet", "last_activity", "TEXT"),
    ("anonymous_wallet", "balance", "REAL DEFAULT 0"),
    ("anonymous_wallet", "total_spent", "REAL DEFAULT 0"),
    
    # Branch Ticket Config
    ("branch_ticket_config", "regimen_fiscal", "TEXT"),
    
    # Time Clock
    ("time_clock_entries", "entry_id", "INTEGER"),
    ("time_clock_entries", "entry_date", "TEXT"),
    ("time_clock_entries", "source", "TEXT DEFAULT 'manual'"),
    
    # Ghost Wallets
    ("ghost_wallets", "wallet_code", "TEXT"),
    ("ghost_wallets", "hash_id", "TEXT"),
    ("ghost_wallets", "total_earned", "REAL DEFAULT 0"),
    ("ghost_wallets", "total_spent", "REAL DEFAULT 0"),
    ("ghost_wallets", "transactions_count", "INTEGER DEFAULT 0"),
    ("ghost_wallets", "source", "TEXT"),
    
    # Ghost Transactions
    ("ghost_transactions", "wallet_hash", "TEXT"),
    ("ghost_transactions", "type", "TEXT"),
    ("ghost_transactions", "sale_id", "INTEGER"),
    ("ghost_transactions", "transaction_type", "TEXT"),
    
    # Shelf
    ("shelf_reference_photos", "location_qr", "TEXT"),
    ("shelf_reference_photos", "reference_photo_path", "TEXT"),
    ("shelf_reference_photos", "expected_units", "INTEGER"),
    ("shelf_reference_photos", "products_json", "TEXT"),
    ("shelf_audits", "location_qr", "TEXT"),
    ("shelf_audits", "audit_photo_path", "TEXT"),
    ("shelf_audits", "fill_level_pct", "REAL"),
    ("shelf_audits", "discrepancy_detected", "INTEGER DEFAULT 0"),
    ("shelf_audits", "notes", "TEXT"),
    ("shelf_audits", "created_at", "TEXT"),
    
    # Resurrection Bundles
    ("resurrection_bundles", "bundle_name", "TEXT"),
    ("resurrection_bundles", "products_json", "TEXT"),
    ("resurrection_bundles", "discount_pct", "REAL"),
    
    # Transfer Suggestions
    ("transfer_suggestions", "from_branch_id", "INTEGER"),
    ("transfer_suggestions", "to_branch_id", "INTEGER"),
    
    # Warehouse
    ("warehouse_pickups", "location_code", "TEXT"),
    ("warehouse_pickups", "order_reference", "TEXT"),
    
    # Invoice OCR
    ("invoice_ocr_history", "extracted_data", "TEXT"),
    ("invoice_ocr_history", "confidence_score", "REAL"),
    ("invoice_ocr_history", "created_at", "TEXT"),
    
    # Crypto
    ("crypto_conversions", "sale_id", "INTEGER"),
    ("crypto_conversions", "crypto_type", "TEXT"),
    ("crypto_conversions", "fiat_equivalent", "REAL"),
    ("crypto_conversions", "created_at", "TEXT"),
    ("cold_wallets", "address", "TEXT"),
    ("cold_wallets", "label", "TEXT"),
    
    # Dead Man's Switch
    ("dead_mans_switch", "activation_code_hash", "TEXT"),
    ("dead_mans_switch", "action_type", "TEXT"),
    ("dead_mans_switch", "is_armed", "INTEGER DEFAULT 0"),
    ("dead_mans_switch", "last_check_in", "TEXT"),
    ("dead_mans_switch", "timeout_hours", "INTEGER DEFAULT 24"),
    ("dead_mans_switch", "created_at", "TEXT"),
    
    # Ghost Entries/Transfers
    ("ghost_entries", "document_reference", "TEXT"),
    ("ghost_transfers", "from_location", "TEXT"),
    ("ghost_transfers", "to_location", "TEXT"),
    ("ghost_transfers", "carrier_code", "TEXT"),
    ("ghost_transfers", "expected_arrival", "TEXT"),
    ("ghost_transfers", "actual_arrival", "TEXT"),
    
    # Kit Components
    ("kit_components", "kit_product_id", "INTEGER"),
    ("kit_components", "component_product_id", "INTEGER"),
    
    # Credit History
    ("credit_history", "description", "TEXT"),
    ("credit_history", "reference_id", "INTEGER"),
    ("credit_history", "movement_type", "TEXT"),
    ("credit_history", "created_at", "TEXT"),
    
    # Turn Movements
    ("turn_movements", "reason", "TEXT"),
    ("turn_movements", "user_id", "INTEGER"),
    
    # Invoices
    ("invoices", "customer_id", "INTEGER"),
    ("invoices", "total", "REAL"),
    ("invoices", "subtotal", "REAL"),
    ("invoices", "tax", "REAL"),
    ("invoices", "invoice_date", "TEXT"),
    ("invoices", "due_date", "TEXT"),
    
    # Purchases
    ("purchases", "purchase_number", "TEXT"),
    ("purchases", "subtotal", "REAL"),
    ("purchases", "tax", "REAL"),
    ("purchases", "purchase_date", "TEXT"),
    ("purchases", "received_date", "TEXT"),
    ("purchases", "notes", "TEXT"),
    ("purchases", "created_by", "INTEGER"),
    
    # Sale Voids
    ("sale_voids", "void_reason", "TEXT"),
    ("sale_voids", "authorized_by", "INTEGER"),
    ("sale_voids", "void_date", "TEXT"),
    ("sale_voids", "notes", "TEXT"),
    
    # Payments
    ("payments", "status", "TEXT DEFAULT 'completed'"),
    
    # App Config
    ("app_config", "category", "TEXT"),
    
    # Session Cache
    ("session_cache", "data", "TEXT"),
    ("session_cache", "created_at", "TEXT"),
    
    # Activity Log
    ("activity_log", "entity_type", "TEXT"),
    ("activity_log", "entity_id", "INTEGER"),
    ("activity_log", "ip_address", "TEXT"),
    
    # Sync Commands
    ("sync_commands", "command_type", "TEXT"),
    
    # Branch Inventory
    ("branch_inventory", "stock", "REAL DEFAULT 0"),
    
    # Online Orders
    ("online_orders", "shipping", "REAL DEFAULT 0"),
    ("online_orders", "notes", "TEXT"),
    
    # Cart Sessions
    ("cart_sessions", "session_token", "TEXT"),
    ("cart_sessions", "items_json", "TEXT"),
    
    # Shipping Addresses
    ("shipping_addresses", "address_line1", "TEXT"),
    ("shipping_addresses", "address_line2", "TEXT"),
    
    # C Clave Prod Serv
    ("c_claveprodserv", "incluye_iva", "TEXT"),
    ("c_claveprodserv", "incluye_ieps", "TEXT"),
    ("c_claveprodserv", "complemento", "TEXT"),
    
    # Ghost Procurements
    ("ghost_procurements", "supplier_estimate", "TEXT"),
    ("ghost_procurements", "branch", "INTEGER"),
    ("ghost_procurements", "linked_purchase_id", "INTEGER"),
    ("ghost_procurements", "justification", "TEXT"),
    ("ghost_procurements", "status", "TEXT DEFAULT 'pending'"),
    
    # Wallet Sessions
    ("wallet_sessions", "device_info", "TEXT"),
    ("wallet_sessions", "ip_address", "TEXT"),
    
    # Cart Items
    ("cart_items", "cart_id", "INTEGER"),
    ("cart_items", "unit_price", "REAL"),
    
    # Wallet Transactions
    ("wallet_transactions", "amount", "REAL"),
    ("wallet_transactions", "transaction_type", "TEXT"),
    
    # Transfer Items
    ("transfer_items", "qty_sent", "REAL"),
    ("transfer_items", "qty_received", "REAL"),
    ("transfer_items", "quantity", "REAL"),
    
    # Audit Log
    ("audit_log", "record_id", "INTEGER"),
    ("audit_log", "table_name", "TEXT"),
    
    # Loss Records
    ("loss_records", "approved_at", "TEXT"),
    ("loss_records", "approved_by", "INTEGER"),
    ("loss_records", "batch_number", "TEXT"),
    ("loss_records", "created_by", "INTEGER"),
    ("loss_records", "notes", "TEXT"),
    
    # Promotions
    ("promotions", "description", "TEXT"),
    ("promotions", "buy_qty", "INTEGER"),
    ("promotions", "get_qty", "INTEGER"),
    ("promotions", "category_id", "INTEGER"),
    ("promotions", "max_discount", "REAL"),
    ("promotions", "product_id", "INTEGER"),
    
    # Purchase Orders
    ("purchase_orders", "order_number", "TEXT"),
    ("purchase_orders", "subtotal", "REAL"),
    ("purchase_orders", "tax", "REAL"),
    ("purchase_orders", "created_by", "INTEGER"),
    ("purchase_orders", "expected_date", "TEXT"),
    ("purchase_orders", "received_at", "TEXT"),
    
    # Purchase Order Items
    ("purchase_order_items", "order_id", "INTEGER"),
    ("purchase_order_items", "received_qty", "REAL DEFAULT 0"),
    
    # Employee Loans
    ("employee_loans", "start_date", "TEXT"),
    ("employee_loans", "cancelled_at", "TEXT"),
    
    # Loan Payments
    ("loan_payments", "created_at", "TEXT"),
    
    # Attendance
    ("attendance_rules", "late_tolerance_minutes", "INTEGER DEFAULT 15"),
    ("attendance_rules", "overtime_after_hours", "REAL DEFAULT 8"),
    ("attendance_rules", "work_start_time", "TEXT DEFAULT '09:00'"),
    ("attendance_rules", "work_end_time", "TEXT DEFAULT '18:00'"),
    ("attendance_summary", "absences", "INTEGER DEFAULT 0"),
    ("attendance_summary", "days_worked", "INTEGER DEFAULT 0"),
    ("attendance_summary", "hours_worked", "REAL DEFAULT 0"),
    ("attendance_summary", "late_arrivals", "INTEGER DEFAULT 0"),
    ("attendance_summary", "period_start", "TEXT"),
    ("attendance_summary", "period_end", "TEXT"),
    
    # Inventory
    ("inventory_movements", "notes", "TEXT"),
    ("inventory_transfers", "approved_at", "TEXT"),
    ("inventory_transfers", "shipment_date", "TEXT"),
    ("inventory_transfers", "tracking_number", "TEXT"),
    ("inventory_transfers", "sync_hash", "TEXT"),
    ("inventory_transfers", "synced", "INTEGER DEFAULT 0"),
    ("inventory_transfers", "total_qty", "REAL DEFAULT 0"),
    ("inventory_transfers", "total_value", "REAL DEFAULT 0"),
    
    # Gift Cards
    ("gift_cards", "last_used", "TEXT"),
    
    # ========== SYNC COLUMNS - Added 2026-01-14 ==========
    # These columns are REQUIRED for LAN synchronization to work
    # All tables in SYNC_TABLES must have 'synced' column
    
    # Sale Items and Transactions
    ("sale_items", "synced", "INTEGER DEFAULT 0"),
    ("payments", "synced", "INTEGER DEFAULT 0"),
    ("returns", "synced", "INTEGER DEFAULT 0"),
    ("return_items", "synced", "INTEGER DEFAULT 0"),
    ("sale_voids", "synced", "INTEGER DEFAULT 0"),
    ("card_transactions", "synced", "INTEGER DEFAULT 0"),
    ("sale_cfdi_relation", "synced", "INTEGER DEFAULT 0"),
    
    # Customers and Loyalty
    ("gift_cards", "synced", "INTEGER DEFAULT 0"),
    ("wallet_transactions", "synced", "INTEGER DEFAULT 0"),
    ("loyalty_ledger", "synced", "INTEGER DEFAULT 0"),
    ("loyalty_transactions", "synced", "INTEGER DEFAULT 0"),
    ("loyalty_accounts", "synced", "INTEGER DEFAULT 0"),
    ("loyalty_fraud_log", "synced", "INTEGER DEFAULT 0"),
    ("loyalty_tier_history", "synced", "INTEGER DEFAULT 0"),
    ("credit_history", "synced", "INTEGER DEFAULT 0"),
    ("anonymous_wallet", "synced", "INTEGER DEFAULT 0"),
    
    # Loans and Expenses
    ("employee_loans", "synced", "INTEGER DEFAULT 0"),
    ("loan_payments", "synced", "INTEGER DEFAULT 0"),
    ("cash_movements", "synced", "INTEGER DEFAULT 0"),
    ("cash_expenses", "synced", "INTEGER DEFAULT 0"),
    ("cash_extractions", "synced", "INTEGER DEFAULT 0"),
    ("personal_expenses", "synced", "INTEGER DEFAULT 0"),
    
    # Turns
    ("turn_movements", "synced", "INTEGER DEFAULT 0"),
    ("turns", "synced", "INTEGER DEFAULT 0"),
    
    # Products and Inventory
    ("products", "synced", "INTEGER DEFAULT 0"),
    ("inventory_movements", "synced", "INTEGER DEFAULT 0"),
    ("inventory_log", "synced", "INTEGER DEFAULT 0"),
    ("product_lots", "synced", "INTEGER DEFAULT 0"),
    ("kit_components", "synced", "INTEGER DEFAULT 0"),
    ("shadow_movements", "synced", "INTEGER DEFAULT 0"),
    ("branch_inventory", "synced", "INTEGER DEFAULT 0"),
    ("loss_records", "synced", "INTEGER DEFAULT 0"),
    ("self_consumption", "synced", "INTEGER DEFAULT 0"),
    ("transfer_items", "synced", "INTEGER DEFAULT 0"),
    
    # Purchases and Suppliers
    ("warehouse_pickups", "synced", "INTEGER DEFAULT 0"),
    ("purchases", "synced", "INTEGER DEFAULT 0"),
    ("purchase_orders", "synced", "INTEGER DEFAULT 0"),
    ("purchase_order_items", "synced", "INTEGER DEFAULT 0"),
    ("suppliers", "synced", "INTEGER DEFAULT 0"),
    ("purchase_costs", "synced", "INTEGER DEFAULT 0"),
    ("transfer_suggestions", "synced", "INTEGER DEFAULT 0"),
    
    # Layaways
    ("layaways", "synced", "INTEGER DEFAULT 0"),
    ("layaway_items", "synced", "INTEGER DEFAULT 0"),
    ("layaway_payments", "synced", "INTEGER DEFAULT 0"),
    
    # Fiscal
    ("invoices", "synced", "INTEGER DEFAULT 0"),
    ("pending_invoices", "synced", "INTEGER DEFAULT 0"),
    ("cfdi_relations", "synced", "INTEGER DEFAULT 0"),
    ("cross_invoices", "synced", "INTEGER DEFAULT 0"),
    ("emitters", "synced", "INTEGER DEFAULT 0"),
    
    # Catalogs and Promotions
    ("promotions", "synced", "INTEGER DEFAULT 0"),
    ("categories", "synced", "INTEGER DEFAULT 0"),
    ("online_orders", "synced", "INTEGER DEFAULT 0"),
    ("order_items", "synced", "INTEGER DEFAULT 0"),
    ("shipping_addresses", "synced", "INTEGER DEFAULT 0"),
    ("product_categories", "synced", "INTEGER DEFAULT 0"),
    
    # System and Config
    ("activity_log", "synced", "INTEGER DEFAULT 0"),
    ("audit_log", "synced", "INTEGER DEFAULT 0"),
    ("employees", "synced", "INTEGER DEFAULT 0"),
    ("users", "synced", "INTEGER DEFAULT 0"),
    ("role_permissions", "synced", "INTEGER DEFAULT 0"),
    ("branches", "synced", "INTEGER DEFAULT 0"),
    ("secuencias", "synced", "INTEGER DEFAULT 0"),
    
    # Other Tables
    ("loyalty_rules", "synced", "INTEGER DEFAULT 0"),
    ("price_change_history", "synced", "INTEGER DEFAULT 0"),
    ("kit_items", "synced", "INTEGER DEFAULT 0"),
    ("bin_locations", "synced", "INTEGER DEFAULT 0"),
    ("shelf_reference_photos", "synced", "INTEGER DEFAULT 0"),
    ("ghost_entries", "synced", "INTEGER DEFAULT 0"),
    ("ghost_procurements", "synced", "INTEGER DEFAULT 0"),
    ("ghost_transactions", "synced", "INTEGER DEFAULT 0"),
    ("ghost_transfers", "synced", "INTEGER DEFAULT 0"),
    ("ghost_wallets", "synced", "INTEGER DEFAULT 0"),
    ("resurrection_bundles", "synced", "INTEGER DEFAULT 0"),

    # ========== SYNC CONFLICTS - Columnas para logging de conflictos ==========
    ("sync_conflicts", "record_identifier", "TEXT"),
    ("sync_conflicts", "conflict_type", "TEXT"),
    ("sync_conflicts", "existing_timestamp", "TEXT"),
    ("sync_conflicts", "new_timestamp", "TEXT"),
    ("sync_conflicts", "existing_sync_version", "INTEGER"),
    ("sync_conflicts", "new_sync_version", "INTEGER"),
    ("sync_conflicts", "conflict_reason", "TEXT"),
    ("sync_conflicts", "resolved_action", "TEXT"),
    ("sync_conflicts", "terminal_id", "TEXT"),
    ("sync_conflicts", "branch_id", "INTEGER"),
]

def _create_missing_indexes(db: DatabaseManager) -> None:
    """Crea índices que pudieron fallar por columnas faltantes."""
    # Índices que dependen de columnas que pueden no existir inicialmente
    missing_indexes = [
        ("turns", "terminal_id", "CREATE INDEX IF NOT EXISTS idx_turns_terminal_branch ON turns(terminal_id, branch_id)"),
        ("turns", "terminal_id", "CREATE INDEX IF NOT EXISTS idx_turns_terminal_id ON turns(terminal_id)"),
        ("sales", "timestamp", "CREATE INDEX IF NOT EXISTS idx_sales_timestamp ON sales(timestamp)"),
        ("sales", "pos_id", "CREATE INDEX IF NOT EXISTS idx_sales_pos_id ON sales(pos_id) WHERE pos_id IS NOT NULL"),
        ("sales", "pos_id", "CREATE INDEX IF NOT EXISTS idx_sales_branch_pos ON sales(branch_id, pos_id) WHERE pos_id IS NOT NULL"),
        ("sales", "timestamp", "CREATE INDEX IF NOT EXISTS idx_sales_pos_timestamp ON sales(pos_id, timestamp) WHERE pos_id IS NOT NULL AND status = 'completed'"),
        ("sales", "synced_from_terminal", "CREATE INDEX IF NOT EXISTS idx_sales_synced_from ON sales(synced_from_terminal) WHERE synced_from_terminal IS NOT NULL"),
        ("sales", "pos_id", "CREATE INDEX IF NOT EXISTS idx_sales_branch_pos_date ON sales(branch_id, pos_id, created_at) WHERE pos_id IS NOT NULL AND status = 'completed'"),
        ("sales", "origin_pc", "CREATE INDEX IF NOT EXISTS idx_sales_origin_pc ON sales(origin_pc) WHERE origin_pc IS NOT NULL"),
        ("inventory_log", "timestamp", "CREATE INDEX IF NOT EXISTS idx_inventory_log_timestamp ON inventory_log(timestamp)"),
        ("cash_extractions", "extraction_date", "CREATE INDEX IF NOT EXISTS idx_extractions_date ON cash_extractions(extraction_date)"),
        ("cfdis", "facturapi_id", "CREATE INDEX IF NOT EXISTS idx_cfdis_facturapi ON cfdis(facturapi_id)"),
        ("audit_log", "timestamp", "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)"),
        ("time_clock_entries", "entry_date", "CREATE INDEX IF NOT EXISTS idx_time_entries_date ON time_clock_entries(entry_date)"),
    ]
    
    created_count = 0
    for table, column, index_sql in missing_indexes:
        try:
            with db.get_connection() as conn:
                try:
                    conn.rollback()
                except Exception as e:
                    logger.debug("Rollback before index creation failed: %s", e)

                cursor = conn.cursor()
                try:
                    # Verificar que la columna existe
                    cursor.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = %s
                        AND column_name = %s
                    """, (table, column))
                    column_exists = cursor.fetchone() is not None
                    
                    if column_exists:
                        # Extraer nombre del índice del SQL
                        # Formato: CREATE INDEX IF NOT EXISTS idx_name ON table(...)
                        index_name = None
                        if "idx_" in index_sql:
                            # Buscar el nombre del índice después de "idx_"
                            parts = index_sql.split("idx_")
                            if len(parts) > 1:
                                index_name_part = parts[1].split()[0]  # Primera palabra después de idx_
                                index_name = f"idx_{index_name_part}"
                        
                        if index_name:
                            # Verificar que el índice no existe
                            cursor.execute("""
                                SELECT indexname 
                                FROM pg_indexes 
                                WHERE schemaname = 'public' 
                                AND tablename = %s 
                                AND indexname = %s
                            """, (table, index_name))
                            index_exists = cursor.fetchone() is not None
                            
                            if not index_exists:
                                cursor.execute(index_sql)
                                conn.commit()
                                created_count += 1
                                logger.debug("Created missing index: %s on %s.%s", index_name, table, column)
                            else:
                                conn.commit()  # Cerrar transacción implícita del SELECT
                        else:
                            # Si no se pudo extraer el nombre, intentar crear de todas formas
                            try:
                                cursor.execute(index_sql)
                                conn.commit()
                                created_count += 1
                                logger.debug("Created index on %s.%s", table, column)
                            except Exception as idx_e:
                                # El índice puede ya existir
                                logger.debug("Index may already exist: %s", idx_e)
                    else:
                        conn.commit()  # Cerrar transacción implícita del SELECT
                        logger.debug("Skipping index creation: column %s.%s does not exist yet", table, column)
                except Exception as e:
                    try:
                        conn.rollback()
                    except Exception as rollback_e:
                        logger.debug("Rollback after index creation error failed: %s", rollback_e)
                    # Ignorar errores silenciosamente (el índice puede ya existir)
                    logger.debug("Could not create index for %s.%s: %s", table, column, e)
                finally:
                    cursor.close()
        except Exception as e:
            logger.debug("Error creating missing indexes: %s", e)
    
    if created_count > 0:
        logger.info("Created %d missing indexes after migrations", created_count)

def _create_missing_views(db: DatabaseManager) -> None:
    """Recrea vistas que pudieron fallar por columnas faltantes."""
    # Vista que depende de columnas que pueden no existir inicialmente
    view_sql = """
    CREATE OR REPLACE VIEW v_sales_with_origin AS
    SELECT 
        -- Información básica de la venta
        s.id AS sale_id,
        s.uuid,
        s.timestamp,
        s.created_at,
        s.updated_at,
        s.total,
        s.subtotal,
        s.tax,
        s.discount,
        s.status,
        
        -- IDENTIFICACIÓN DEL TERMINAL/PC (prioridad: pos_id > terminal_id > synced_from)
        COALESCE(
            s.pos_id,
            CASE WHEN t.terminal_id IS NOT NULL THEN 'T' || t.terminal_id::TEXT ELSE NULL END,
            s.synced_from_terminal,
            'DESCONOCIDO'
        ) AS terminal_identifier,
        
        -- Información detallada del terminal
        s.pos_id AS pos_id_sale,
        t.terminal_id,
        t.pos_id AS pos_id_turn,
        s.synced_from_terminal,
        
        -- Información de sucursal
        s.branch_id,
        b.name AS branch_name,
        b.code AS branch_code,
        
        -- Información del turno
        s.turn_id,
        t.start_timestamp AS turn_start,
        t.end_timestamp AS turn_end,
        
        -- Información del usuario
        s.user_id,
        u.username,
        u.name AS user_name,
        
        -- Información del cliente
        s.customer_id,
        c.name AS customer_name,
        
        -- Información fiscal
        s.serie,
        s.folio_visible,
        
        -- Método de pago
        s.payment_method,
        
        -- Información de sincronización
        s.synced,
        s.sync_status
        
    FROM sales s
    LEFT JOIN turns t ON s.turn_id = t.id
    LEFT JOIN branches b ON s.branch_id = b.id
    LEFT JOIN users u ON s.user_id = u.id
    LEFT JOIN customers c ON s.customer_id = c.id
    WHERE s.visible = 1;
    """
    
    try:
        with db.get_connection() as conn:
            try:
                conn.rollback()
            except Exception as e:
                logger.debug("Rollback before view creation failed: %s", e)

            cursor = conn.cursor()
            try:
                # Verificar que las columnas críticas existen
                cursor.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = 'sales'
                    AND column_name IN ('uuid', 'timestamp', 'pos_id', 'synced_from_terminal')
                """)
                sales_columns = {row[0] for row in cursor.fetchall()}
                
                # Si faltan columnas críticas, usar una versión simplificada de la vista
                if not all(col in sales_columns for col in ['uuid', 'timestamp']):
                    conn.commit()  # Cerrar transacción implícita del SELECT
                    logger.debug("Skipping view creation: missing critical columns in sales table")
                    return
                
                # Intentar crear la vista
                cursor.execute(view_sql)
                conn.commit()
                logger.debug("Created/recreated view: v_sales_with_origin")
                
                # Intentar agregar el comentario
                try:
                    cursor.execute("""
                        COMMENT ON VIEW v_sales_with_origin IS
                        'Vista optimizada que identifica el origen (PC/terminal) de cada venta.
                        Incluye timestamp y toda la información relevante para rastrear ventas por terminal.';
                    """)
                    conn.commit()
                except Exception as e:
                    logger.debug("Adding comment to view v_sales_with_origin failed: %s", e)
                    
            except Exception as e:
                try:
                    conn.rollback()
                except Exception as rollback_err:
                    logger.debug("Rollback also failed: %s", rollback_err)
                # Ignorar errores silenciosamente (la vista puede tener problemas de columnas)
                logger.debug("Could not create view v_sales_with_origin: %s", e)
            finally:
                cursor.close()
    except Exception as e:
        logger.debug("Error creating missing views: %s", e)

def _run_migrations(db: DatabaseManager) -> None:
    """Ejecuta migraciones de columnas para asegurar integridad del esquema."""
    logger.info("Running column migrations...")
    
    added_count = 0
    
    # CRITICAL: Ejecutar cada migración en su propia transacción
    # para evitar que un error aborte todas las demás
    for table, column, type_def in COLUMN_MIGRATIONS:
        try:
            with db.get_connection() as conn:
                # CRITICAL: Asegurar que la conexión está en estado limpio
                try:
                    conn.rollback()
                except Exception as rollback_err:
                    logger.debug("Pre-migration rollback failed (expected if clean): %s", rollback_err)

                cursor = conn.cursor()
                try:
                    # Verificar si la columna existe (PostgreSQL usa information_schema)
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = %s 
                        AND column_name = %s
                    """, (table, column))
                    exists = cursor.fetchone() is not None
                    
                    # #region agent log
                    if table == "sales" and column == "origin_pc":
                        try:
                            import json, time
                            from app.utils.path_utils import get_debug_log_path_str
                            with open(get_debug_log_path_str(), "a") as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"REV4","location":"database.py:_run_migrations","message":"Checking origin_pc column","data":{"table":table,"column":column,"exists":exists},"timestamp":int(time.time()*1000)})+"\n")
                        except Exception as e:
                            logger.debug("Debug logging for origin_pc column check failed: %s", e)
                    # #endregion
                    
                    if not exists:
                        # Convertir tipos SQLite a PostgreSQL
                        pg_type_def = type_def.replace('TEXT', 'TEXT').replace('REAL', 'DOUBLE PRECISION').replace('INTEGER', 'INTEGER')
                        # Validate identifiers before dynamic SQL (defense-in-depth)
                        _valid_ident = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
                        if not _valid_ident.match(table) or not _valid_ident.match(column):
                            raise ValueError(f"Invalid SQL identifier in migration: {table}.{column}")
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {pg_type_def}")
                        conn.commit()
                        added_count += 1
                        logger.info("Added column: %s.%s (%s)", table, column, pg_type_def)
                        
                        # #region agent log
                        if table == "sales" and column == "origin_pc":
                            try:
                                import json, time
                                from app.utils.path_utils import get_debug_log_path_str
                                with open(get_debug_log_path_str(), "a") as f:
                                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"REV4","location":"database.py:_run_migrations","message":"origin_pc column added","data":{"table":table,"column":column,"type":pg_type_def},"timestamp":int(time.time()*1000)})+"\n")
                            except Exception as e:
                                logger.debug("Debug logging for origin_pc column addition failed: %s", e)
                        # #endregion
                    else:
                        conn.commit()
                        
                except Exception as e:
                    # CRITICAL: Hacer rollback de la transacción actual antes de continuar
                    try:
                        conn.rollback()
                    except Exception as rollback_e:
                        logger.debug("Rollback after migration error failed: %s", rollback_e)

                    error_msg = str(e).lower()
                    # Tabla no existe, ignorar
                    if "does not exist" in error_msg or "no such table" in error_msg:
                        logger.warning("Table %s does not exist, skipping column %s", table, column)
                        continue
                    # Si la transacción está abortada, ya hicimos rollback, continuar
                    if "current transaction is aborted" in error_msg:
                        logger.warning("Migration skipped for %s.%s: current transaction is aborted, commands ignored until end of transaction block", table, column)
                        # Intentar resetear la conexión
                        try:
                            conn.rollback()
                        except Exception as reset_e:
                            logger.debug("Rollback during transaction reset failed: %s", reset_e)
                        continue
                    logger.warning("Migration skipped for %s.%s: %s", table, column, e)
                finally:
                    cursor.close()
                    
        except Exception as e:
            # Error al obtener conexión, continuar con la siguiente migración
            error_msg = str(e).lower()
            if "does not exist" in error_msg or "no such table" in error_msg:
                logger.warning("Table %s does not exist, skipping column %s", table, column)
                continue
            logger.warning("Migration skipped for %s.%s: %s", table, column, e)
            
    # POST-MIGRATION: Crear índices y vistas que pudieron fallar por columnas faltantes
    logger.info("Creating missing indexes and views after column migrations...")
    _create_missing_indexes(db)
    _create_missing_views(db)
    
    # POST-MIGRATION VERIFICATION: Verificar que las columnas agregadas existen
    if added_count > 0:
        logger.info("Verifying %d newly added columns...", added_count)
        verification_failed = []
        for table, column, type_def in COLUMN_MIGRATIONS:
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = %s
                        AND column_name = %s
                    """, (table, column))
                    exists = cursor.fetchone() is not None
                    conn.commit()  # Cerrar transacción implícita del SELECT
                    cursor.close()
                    if not exists:
                        verification_failed.append(f"{table}.{column}")
            except Exception as verify_e:
                logger.warning("Could not verify %s.%s: %s", table, column, verify_e)
        
        if verification_failed:
            logger.error("POST-MIGRATION VERIFICATION FAILED: %d columns not found: %s", len(verification_failed), ', '.join(verification_failed))
        else:
            logger.info("POST-MIGRATION VERIFICATION SUCCESS: All %d columns verified", added_count)
    
    if added_count > 0:
        logger.info("Added %d missing columns", added_count)
    else:
        logger.info("All columns up-to-date")

# ═══════════════════════════════════════════════════════════════════════════════
# CONCURRENCY SAFEGUARDS
# ═══════════════════════════════════════════════════════════════════════════════
def _apply_concurrency_safeguards(db: DatabaseManager) -> None:
    """Aplica triggers para prevenir stock negativo y condiciones de carrera."""
    try:
        # PostgreSQL trigger syntax
        trigger_sql = """
        CREATE OR REPLACE FUNCTION prevent_negative_stock()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.stock < 0 THEN
                RAISE EXCEPTION 'Stock cannot be negative';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        
        DROP TRIGGER IF EXISTS prevent_negative_stock_trigger ON products;
        CREATE TRIGGER prevent_negative_stock_trigger
        BEFORE UPDATE ON products
        FOR EACH ROW
        EXECUTE FUNCTION prevent_negative_stock();
        """
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(trigger_sql)
            conn.commit()
            cursor.close()
        logger.info("Concurrency Safeguards Applied")
    except Exception as e:
        logger.debug("Failed to apply safeguards (may already exist): %s", e)
