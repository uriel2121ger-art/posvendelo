"""
INFRA: DATABASE CENTRAL MODULE
Manejador de base de datos PostgreSQL para multi-caja.
Sistema usa exclusivamente PostgreSQL para evitar errores de sincronización.
"""
from typing import Any, Dict, List, Tuple
try:
    from app.utils.path_utils import get_debug_log_path_str, get_debug_log_path
except ImportError:
    get_debug_log_path_str = None
    get_debug_log_path = None
from abc import ABC, abstractmethod
from contextlib import contextmanager
import json
import logging
import os
import time

logger = logging.getLogger("DB_CENTRAL")

# =============================================================================
# INTERFAZ BASE
# =============================================================================

class DatabaseInterface(ABC):
    """Interfaz abstracta para cualquier backend de base de datos."""
    
    @abstractmethod
    def execute_query(self, query: str, params: tuple = ()) -> List[Any]:
        """Ejecuta una consulta SELECT."""
        pass
    
    @abstractmethod
    def execute_write(self, query: str, params: tuple = ()) -> int:
        """Ejecuta INSERT/UPDATE/DELETE. Retorna ID insertado o rowcount."""
        pass
    
    @abstractmethod
    def execute_transaction(self, operations: List[Tuple[str, tuple]]) -> bool:
        """Ejecuta múltiples operaciones en una transacción."""
        pass
    
    @abstractmethod
    @contextmanager
    def get_connection(self):
        """Obtiene una conexión (context manager)."""
        pass
    
    @abstractmethod
    def get_table_info(self, table_name: str) -> List[dict]:
        """Obtiene información de columnas de una tabla."""
        pass
    
    @abstractmethod
    def list_tables(self) -> List[str]:
        """Lista todas las tablas en la base de datos."""
        pass

# =============================================================================
# POSTGRESQL BACKEND (Único Backend)
# =============================================================================

class PostgreSQLBackend(DatabaseInterface):
    """Backend PostgreSQL para multi-caja con DB central."""

    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            self.psycopg2 = psycopg2
            self.RealDictCursor = RealDictCursor
        except ImportError:
            raise ImportError("psycopg2 no instalado. Ejecutar: pip install psycopg2-binary")

        self.connection_params = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password
        }
        self.connection_pool = None
        self._test_connection()

        # CRITICAL FIX: Inicializar connection pool
        try:
            from psycopg2 import pool
            self.connection_pool = pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=20,
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                connect_timeout=10
            )
            logger.info("Database connection pool initialized (min=2, max=20)")
        except Exception as e:
            logger.warning("Could not create connection pool, using individual connections: %s", e)
            self.connection_pool = None
    
    def _test_connection(self):
        """Verifica la conexión al arrancar."""
        # #region agent log
        import json, time
        try:
            if get_debug_log_path_str:
                log_path = get_debug_log_path_str()
                if log_path:
                    with open(log_path, "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"DB_CONNECT_START","location":"database_central.py:_test_connection","message":"Starting database connection test","data":{"host":self.connection_params.get('host'),"port":self.connection_params.get('port'),"database":self.connection_params.get('database'),"user":self.connection_params.get('user'),"password_length":len(self.connection_params.get('password',''))},"timestamp":int(time.time()*1000)})+"\n")
        except Exception as e:
            logger.debug("Debug logging for connection test start failed: %s", e)
        # #endregion
        
        try:
            conn = self.psycopg2.connect(**self.connection_params)
            conn.close()
            
            # #region agent log
            try:
                if get_debug_log_path_str:
                    log_path = get_debug_log_path_str()
                    if log_path:
                        with open(log_path, "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"DB_CONNECT_SUCCESS","location":"database_central.py:_test_connection","message":"Database connection successful","data":{},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                logger.debug("Debug logging for connection success failed: %s", e)
            # #endregion

            logger.info(f"✅ Conectado a PostgreSQL: {self.connection_params['host']}")
        except Exception as e:
            # #region agent log
            try:
                if get_debug_log_path_str:
                    log_path = get_debug_log_path_str()
                    if log_path:
                        with open(log_path, "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"DB_CONNECT_FAILED","location":"database_central.py:_test_connection","message":"Database connection failed","data":{"error":str(e),"error_type":type(e).__name__},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as log_e:
                logger.debug("Debug logging for connection failure failed: %s", log_e)
            # #endregion

            error_str = str(e).lower()
            
            # Mejorar mensaje de error para autenticación
            if "password authentication failed" in error_str:
                logger.error(f"❌ Error conectando a PostgreSQL: {e}")
                logger.error("💡 SOLUCIÓN: La contraseña no coincide. Ejecuta:")
                logger.error("   bash scripts/sync_postgresql_password.sh")
                logger.error("   O cambia la contraseña manualmente con:")
                logger.error(f"   sudo -u postgres psql -c \"ALTER USER {self.connection_params.get('user')} WITH PASSWORD 'TU_PASSWORD';\"")
            else:
                logger.error(f"❌ Error conectando a PostgreSQL: {e}")

            raise RuntimeError(f"Database connection failed: {e}") from e

    def close(self):
        """Close all connections in the pool."""
        if self.connection_pool:
            try:
                self.connection_pool.closeall()
                logger.info("Database connection pool closed")
            except Exception as e:
                logger.error("Error closing connection pool: %s", e)

    @contextmanager
    def get_connection(self):
        """Obtiene conexión del pool o crea nueva.

        CRITICAL FIX 2026-02-03: Removed unconditional rollback from finally block.
        The previous implementation rolled back ALL transactions when returning
        connections to the pool, including COMMITTED transactions, causing data loss.

        Now we only rollback if the connection is in an error state (TRANSACTION_STATUS_INERROR).
        """
        if self.connection_pool:
            conn = self.connection_pool.getconn()
            try:
                yield conn
            finally:
                # CRITICAL FIX 2026-02-03: Rollback uncommitted transactions before returning to pool
                # DO NOT rollback committed transactions (status=IDLE after commit)!
                try:
                    # psycopg2 transaction status constants:
                    # 0=IDLE (no transaction, clean), 1=ACTIVE (command executing),
                    # 2=INTRANS (in transaction block, NOT committed), 3=INERROR (error state), 4=UNKNOWN
                    if conn.closed == 0:  # Connection is open
                        status = conn.get_transaction_status()
                        if status == 3:  # INERROR - must rollback
                            conn.rollback()
                            logger.debug("Rolled back errored transaction before returning to pool")
                        elif status == 2:  # INTRANS - uncommitted transaction! MUST rollback
                            # CRITICAL: This prevents data loss from uncommitted transactions
                            # If code opened a transaction but forgot to commit, we rollback here
                            conn.rollback()
                            logger.warning(
                                "⚠️ Rolled back UNCOMMITTED transaction before returning to pool. "
                                "This indicates a bug: code should always commit or rollback explicitly!"
                            )
                except Exception as e:
                    logger.debug("Error checking transaction status: %s", e)
                self.connection_pool.putconn(conn)
        else:
            conn = self.psycopg2.connect(**self.connection_params)
            try:
                yield conn
            finally:
                # For non-pooled connections, just close
                # Any uncommitted changes will be rolled back by PostgreSQL on close
                # DO NOT explicitly rollback - let committed transactions persist!
                try:
                    conn.close()
                except Exception as e:
                    logger.debug("Error closing connection: %s", e)
    
    def _convert_query(self, query: str) -> str:
        """Convierte sintaxis SQLite a PostgreSQL."""
        from src.infra.query_converter import convert_sqlite_to_postgresql
        return convert_sqlite_to_postgresql(query)
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Any]:
        converted_query = self._convert_query(query)
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=self.RealDictCursor) as cursor:
                cursor.execute(converted_query, params)
                result = cursor.fetchall()
            # CRITICAL FIX: Commit after SELECT to close implicit transaction
            # PostgreSQL opens implicit transactions even for SELECTs when autocommit=False
            # This prevents "Rolled back UNCOMMITTED transaction" warnings
            conn.commit()
            return result
    
    def execute_write(self, query: str, params: tuple = ()) -> int:
        """Ejecuta INSERT/UPDATE/DELETE. Retorna ID insertado o rowcount."""
        from src.infra.query_converter import convert_insert_returning
        import re
        
        converted_query = self._convert_query(query)
        
        # CRITICAL FIX: Tablas que NO tienen columna 'id' (usan otras columnas como PK)
        # Estas tablas NO deben tener RETURNING id agregado
        tables_without_id = ['branch_ticket_config']
        
        # Extraer nombre de tabla de la query
        table_name = None
        if "INSERT" in query.upper():
            match = re.search(r"INSERT\s+INTO\s+(\w+)", query, re.IGNORECASE)
            if match:
                table_name = match.group(1)
        
        # Si es INSERT, agregar RETURNING id si no lo tiene
        # PERO solo si la tabla NO está en la lista de exclusiones
        if ("INSERT" in query.upper() and 
            "RETURNING" not in query.upper() and 
            "RETURNING" not in converted_query.upper()):
            
            # Verificar si la tabla está en la lista de exclusiones
            should_exclude = False
            if table_name:
                should_exclude = table_name.lower() in [t.lower() for t in tables_without_id]
            
            # También verificar en el texto de la query (por si acaso)
            query_upper = query.upper()
            converted_upper = converted_query.upper()
            for excluded_table in tables_without_id:
                if excluded_table.upper() in query_upper or excluded_table.upper() in converted_upper:
                    should_exclude = True
                    break
            
            # #region agent log
            import json, time
            try:
                from app.utils.path_utils import get_debug_log_path_str
                if get_debug_log_path_str:
                    log_path = get_debug_log_path_str()
                    if log_path:
                        with open(log_path, "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"EXECUTE_WRITE_RETURNING","location":"database_central.py:execute_write","message":"Checking RETURNING id","data":{"table_name":table_name,"should_exclude":should_exclude,"is_insert":bool("INSERT" in query.upper()),"has_returning":bool("RETURNING" in query.upper() or "RETURNING" in converted_query.upper())},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                logger.debug("Debug logging for RETURNING id check failed: %s", e)
            # #endregion
            
            if not should_exclude:
                converted_query = convert_insert_returning(converted_query, table_name=table_name, exclude_tables=tables_without_id)
            # else: tabla excluida, no modificar query

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(converted_query, params)

                # Si tiene RETURNING, obtener resultado ANTES de commit
                if "RETURNING" in converted_query.upper():
                    result = cursor.fetchone()
                    conn.commit()
                    return result[0] if result else 0

                # Si no tiene RETURNING, commit y usar rowcount
                conn.commit()
                return cursor.rowcount
    
    def execute_transaction(self, operations: List[Tuple[str, tuple]], timeout: int = None, validation_callback=None) -> Dict[str, Any]:
        """
        Ejecuta múltiples operaciones en transacción.
        
        Args:
            operations: Lista de tuplas (query, params)
            timeout: Timeout en segundos (opcional)
            validation_callback: Función opcional (select_results, validation_data) -> None
                                Se ejecuta después de los SELECT FOR UPDATE pero antes de los UPDATEs
        
        Returns:
            Dict con:
                - success: bool
                - inserted_ids: List[int] - IDs de INSERTs con RETURNING
                - rowcounts: List[int] - Rowcounts de cada operación
                - select_results: List[dict] - Resultados de SELECT queries
        """
        results = {
            'success': False,
            'inserted_ids': [],
            'rowcounts': [],
            'select_results': []
        }
        
        with self.get_connection() as conn:
            try:
                with conn.cursor() as cursor:
                    # Establecer timeout en el mismo cursor que ejecuta las operaciones
                    if timeout:
                        cursor.execute("SET statement_timeout = %s", (timeout * 1000,))
                        cursor.execute("SET lock_timeout = %s", (min(timeout * 500, 5000),))  # Max 5 segundos
                    
                    # Separar SELECT FOR UPDATE del resto de operaciones
                    select_ops = []
                    other_ops = []
                    
                    for query, params in operations:
                        if "SELECT" in query.upper() and "FOR UPDATE" in query.upper():
                            select_ops.append((query, params))
                        else:
                            other_ops.append((query, params))
                    
                    # Ejecutar SELECT FOR UPDATE primero
                    for query, params in select_ops:
                        converted_query = self._convert_query(query)
                        cursor.execute(converted_query, params)
                        result = cursor.fetchone()
                        if result:
                            # Convertir a dict usando nombres de columnas
                            columns = [desc[0] for desc in cursor.description]
                            results['select_results'].append(dict(zip(columns, result)))
                        else:
                            results['select_results'].append(None)
                        results['rowcounts'].append(cursor.rowcount)
                    
                    # CRITICAL: Validar stock ANTES de ejecutar UPDATEs
                    if validation_callback and results['select_results']:
                        validation_callback(results['select_results'])
                    
                    # Ejecutar resto de operaciones (INSERT, UPDATE)
                    for query, params in other_ops:
                        converted_query = self._convert_query(query)
                        cursor.execute(converted_query, params)
                        
                        # Si es INSERT con RETURNING, capturar ID
                        if "INSERT" in query.upper() and "RETURNING" in query.upper():
                            result = cursor.fetchone()
                            if result:
                                results['inserted_ids'].append(result[0])
                            else:
                                results['inserted_ids'].append(None)
                        
                        # Capturar rowcount
                        results['rowcounts'].append(cursor.rowcount)
                
                conn.commit()
                results['success'] = True
                return results
            except Exception as e:
                conn.rollback()
                results['success'] = False
                results['error'] = str(e)
                error_str = str(e).lower()
                if timeout and 'timeout' in error_str:
                    raise RuntimeError(f"Operación tardó más de {timeout} segundos. Intente nuevamente.") from e
                # CRITICAL FIX: Return results dict even on error so caller can check success
                # Re-raise only if caller needs exception handling
                raise RuntimeError(f"Transaction failed: {e}") from e
    
    def get_table_info(self, table_name: str) -> List[dict]:
        """Obtiene información de columnas usando information_schema."""
        # #region agent log
        import json
        import time
        debug_log_path = get_debug_log_path_str()
        try:
            log_entry = {
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "J",
                "location": "src/infra/database_central.py:get_table_info:entry",
                "message": "Iniciando get_table_info",
                "data": {"table_name": table_name},
                "timestamp": int(time.time() * 1000)
            }
            with open(debug_log_path, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
                f.flush()
        except Exception as e:
            logger.debug("Debug logging for get_table_info entry failed: %s", e)
        # #endregion
        from src.infra.query_converter import convert_pragma_table_info
        query = convert_pragma_table_info(table_name)
        # #region agent log
        try:
            log_entry = {
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "K",
                "location": "src/infra/database_central.py:get_table_info:before_query",
                "message": "Antes de ejecutar query",
                "data": {"query": query[:200], "table_name": table_name},
                "timestamp": int(time.time() * 1000)
            }
            with open(debug_log_path, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
                f.flush()
        except Exception as e:
            logger.debug("Debug logging for get_table_info before query failed: %s", e)
        # #endregion
        rows = self.execute_query(query, (table_name,))
        # #region agent log
        try:
            log_entry = {
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "L",
                "location": "src/infra/database_central.py:get_table_info:after_query",
                "message": "Después de ejecutar query",
                "data": {"rows_count": len(rows) if rows else 0, "rows_sample": [dict(r) for r in rows[:3]] if rows else []},
                "timestamp": int(time.time() * 1000)
            }
            with open(debug_log_path, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
                f.flush()
        except Exception as e:
            logger.debug("Debug logging for get_table_info after query failed: %s", e)
        # #endregion
        return [dict(row) for row in rows]
    
    def list_tables(self) -> List[str]:
        """Lista todas las tablas usando information_schema."""
        from src.infra.query_converter import convert_sqlite_master
        query = convert_sqlite_master()
        rows = self.execute_query(query)
        return [row['name'] for row in rows]

# =============================================================================
# FACTORY PARA CREAR EL BACKEND CORRECTO
# =============================================================================

def create_database_backend(config_path: str = "data/local_config.json") -> DatabaseInterface:
    """
    Crea el backend PostgreSQL (único backend disponible).
    
    Requiere configuración PostgreSQL válida en config_path.
    
    Raises:
        ValueError: Si la configuración PostgreSQL no está completa
        ConnectionError: Si no se puede conectar a PostgreSQL
    """
    # #region agent log
    import time
    try:
        if get_debug_log_path_str:
            log_path = get_debug_log_path_str()
            if log_path:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CREATE_BACKEND_START","location":"database_central.py:create_database_backend","message":"Starting backend creation","data":{"config_path":config_path},"timestamp":int(time.time()*1000)})+"\n")
    except Exception as e:
        logger.debug("Debug logging for backend creation start failed: %s", e)
    # #endregion
    
    # Leer configuración
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # #region agent log
            try:
                if get_debug_log_path_str:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CONFIG_LOADED","location":"database_central.py:create_database_backend","message":"Configuration loaded from file","data":{"has_postgresql":"postgresql" in config,"config_keys":list(config.keys())},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as log_e:
                logger.debug("Debug logging for config loaded failed: %s", log_e)
            # #endregion
        except Exception as e:
            # #region agent log
            try:
                if get_debug_log_path_str:
                    if get_debug_log_path_str:
                        log_path = get_debug_log_path_str()
                        if log_path:
                            with open(log_path, "a") as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CONFIG_LOAD_ERROR","location":"database_central.py:create_database_backend","message":"Error loading configuration","data":{"error":str(e)},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as log_e:
                logger.debug("Debug logging for config load error failed: %s", log_e)
            # #endregion
            logger.error(f"Error cargando configuración: {e}")
            raise ValueError(f"No se pudo cargar configuración desde {config_path}")
    else:
        # #region agent log
        try:
            if get_debug_log_path_str:
                log_path = get_debug_log_path_str()
                if log_path:
                    with open(log_path, "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CONFIG_NOT_FOUND","location":"database_central.py:create_database_backend","message":"Configuration file not found","data":{"config_path":config_path},"timestamp":int(time.time()*1000)})+"\n")
        except Exception as e:
            logger.debug("Debug logging for config not found failed: %s", e)
        # #endregion
        raise ValueError(f"Archivo de configuración no encontrado: {config_path}. PostgreSQL es requerido.")
    
    pg_config = config.get('postgresql', {})
    
    host = pg_config.get('host', '')
    port = pg_config.get('port', 5432)
    database = pg_config.get('database', 'titan_pos')
    user = pg_config.get('user', 'titan')
    password = pg_config.get('password', '')
    
    # #region agent log
    try:
        if get_debug_log_path_str:
            log_path = get_debug_log_path_str()
            if log_path:
                with open(log_path, "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CONFIG_EXTRACTED","location":"database_central.py:create_database_backend","message":"Configuration extracted","data":{"host":host,"port":port,"database":database,"user":user,"password_length":len(password),"password_empty":not password},"timestamp":int(time.time()*1000)})+"\n")
    except Exception as e:
        logger.debug("Debug logging for config extraction failed: %s", e)
    # #endregion

    if not host or not user or not password:
        # #region agent log
        try:
            if get_debug_log_path_str:
                log_path = get_debug_log_path_str()
                if log_path:
                    with open(log_path, "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CONFIG_INCOMPLETE","location":"database_central.py:create_database_backend","message":"Configuration incomplete","data":{"host":host,"user":user,"has_password":bool(password)},"timestamp":int(time.time()*1000)})+"\n")
        except Exception as e:
            logger.debug("Debug logging for incomplete config failed: %s", e)
        # #endregion
        raise ValueError(
            "Configuración PostgreSQL incompleta. Se requieren: host, user, password.\n"
            f"Configuración actual: host={host}, user={user}, password={'***' if password else 'NO CONFIGURADO'}"
        )
    
    try:
        logger.info(f"🔌 Conectando a PostgreSQL: {host}:{port}/{database}")
        backend = PostgreSQLBackend(host, port, database, user, password)
        
        # #region agent log
        try:
            if get_debug_log_path_str:
                log_path = get_debug_log_path_str()
                if log_path:
                    with open(log_path, "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"BACKEND_CREATED","location":"database_central.py:create_database_backend","message":"Backend created successfully","data":{},"timestamp":int(time.time()*1000)})+"\n")
        except Exception as e:
            logger.debug("Debug logging for backend creation success failed: %s", e)
        # #endregion

        return backend
    except Exception as e:
        # #region agent log
        try:
            if get_debug_log_path_str:
                log_path = get_debug_log_path_str()
                if log_path:
                    with open(log_path, "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"BACKEND_CREATE_FAILED","location":"database_central.py:create_database_backend","message":"Backend creation failed","data":{"error":str(e),"error_type":type(e).__name__},"timestamp":int(time.time()*1000)})+"\n")
        except Exception as log_e:
            logger.debug("Debug logging for backend creation failure failed: %s", log_e)
        # #endregion
        
        error_str = str(e).lower()
        
        # Mejorar mensaje de error para autenticación
        if "password authentication failed" in error_str:
            logger.error(f"❌ No se pudo conectar a PostgreSQL: {e}")
            error_msg = (
                f"No se pudo conectar a PostgreSQL en {host}:{port}.\n"
                f"Error: {e}\n\n"
                f"💡 SOLUCIÓN: La contraseña del usuario '{user}' no coincide.\n\n"
                f"Ejecuta uno de estos comandos:\n"
                f"   bash scripts/sync_postgresql_password.sh\n\n"
                f"O cambia la contraseña manualmente:\n"
                f"   sudo -u postgres psql -c \"ALTER USER {user} WITH PASSWORD 'TU_PASSWORD';\"\n\n"
                f"Luego actualiza la contraseña en data/config/database.json"
            )
            raise ConnectionError(error_msg)
        else:
            logger.error(f"❌ No se pudo conectar a PostgreSQL: {e}")
            raise ConnectionError(
                f"No se pudo conectar a PostgreSQL en {host}:{port}.\n"
                f"Error: {e}\n"
                "Verifica que PostgreSQL esté instalado y corriendo."
            )

# =============================================================================
# WRAPPER COMPATIBLE CON DatabaseManager EXISTENTE
# =============================================================================

class CentralDatabaseManager:
    """
    Wrapper que mantiene compatibilidad con el código existente.
    Usa exclusivamente PostgreSQL (sin fallbacks).
    """
    
    def __init__(self, config_path: str = "data/local_config.json"):
        """
        Inicializa el backend PostgreSQL.
        
        Args:
            config_path: Ruta al archivo de configuración con credenciales PostgreSQL
        
        Raises:
            ValueError: Si la configuración no está completa
            ConnectionError: Si no se puede conectar a PostgreSQL
        """
        self._backend = create_database_backend(config_path)
        logger.info("✅ Conectado a PostgreSQL")

    def close(self):
        """Close the database connection pool."""
        if hasattr(self._backend, 'close'):
            self._backend.close()

    def execute_query(self, query: str, params: tuple = ()) -> List[Any]:
        """Ejecuta una consulta SELECT."""
        return self._backend.execute_query(query, params)
    
    def execute_write(self, query: str, params: tuple = ()) -> int:
        """Ejecuta INSERT/UPDATE/DELETE."""
        return self._backend.execute_write(query, params)
    
    def execute_transaction(self, operations: List[Tuple[str, tuple]]) -> bool:
        """Ejecuta múltiples operaciones en transacción."""
        return self._backend.execute_transaction(operations)
    
    def is_central_mode(self) -> bool:
        """Retorna True (siempre PostgreSQL)."""
        return True
    
    def is_offline(self) -> bool:
        """Retorna False (PostgreSQL siempre requiere conexión)."""
        return False
    
    def get_backend_type(self) -> str:
        """Retorna el tipo de backend (siempre 'postgresql')."""
        return 'postgresql'
    
    @contextmanager
    def get_connection(self):
        """Obtiene una conexión (context manager)."""
        with self._backend.get_connection() as conn:
            yield conn
    
    def get_table_info(self, table_name: str) -> List[dict]:
        """Obtiene información de columnas de una tabla."""
        return self._backend.get_table_info(table_name)
    
    def list_tables(self) -> List[str]:
        """Lista todas las tablas."""
        return self._backend.list_tables()
    
    def get_backend_info(self) -> Dict[str, Any]:
        """Retorna información del backend actual."""
        return {
            'type': 'postgresql',
            'host': self._backend.connection_params['host'],
            'database': self._backend.connection_params['database'],
            'offline': False,
            'pending_sync': 0
        }

# Para testing
if __name__ == "__main__":
    print("Testing CentralDatabaseManager...")
    
    try:
        dm = CentralDatabaseManager("data/config/database.json")
        info = dm.get_backend_info()
        print(f"Backend: {info}")
    except Exception as e:
        print(f"Error: {e}")
        print("Configura PostgreSQL primero. Ver docs/INSTALACION_POSTGRESQL.md")
