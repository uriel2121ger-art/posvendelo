"""
POS CORE (FACADE)
Este archivo existe por compatibilidad con la UI existente.
Redirige las llamadas a la nueva arquitectura en src/.
"""
from datetime import datetime
from decimal import Decimal
import logging
import os
import sys

from src.core.gift_card_engine import GiftCardEngine
from src.core.loan_engine import LoanEngine
from src.core.loyalty_engine import LoyaltyEngine
from src.infra.database import initialize_db
from src.services.pos_engine import pos_engine
from app.utils.path_utils import get_debug_log_path_str, agent_log_enabled
from app.utils.realtime_events import emit_sale_completed, emit_sale_cancelled

# Importar utilidades de ruta
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
try:
    from src.utils.paths import get_data_dir
    DATA_DIR = get_data_dir()
except ImportError:
    DATA_DIR = os.getcwd()

# Constantes Legacy
APP_NAME = "TITAN POS"

# Configurar Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("POS_CORE_FACADE")

class POSCore:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance of POSCore"""
        return cls._instance
    
    def __init__(self):
        import threading
        logger.info("Initializing POS Core Facade...")
        POSCore._instance = self
        # Issue 11: Estado consistente si __init__ sale temprano (sin DB). Evita AttributeError si se usa core antes del wizard.
        self.db_lock = threading.Lock()
        # FIX 2026-02-01: Thread-safe lock for schema cache updates
        self._schema_cache_lock = threading.Lock()
        self.engine = None
        self.loyalty_engine = None
        self.gift_card_engine = None
        self.loan_engine = None
        self.midas = None
        self.gift_engine = None
        self._schema_cache = {}
        # Bug B11 FIX: Inicializar caché al inicio para evitar AttributeError si __init__ sale temprano
        self._cache = {}
        self._cache_timestamps = {}
        self._cache_ttl = 60  # 60 seconds TTL

        # PostgreSQL: Buscar configuración en ubicaciones estándar
        config_path = None
        default_paths = [
            os.path.join(DATA_DIR, "data/config/database.json"),
            os.path.join(DATA_DIR, "data/local_config.json"),
            os.path.join(DATA_DIR, "config/database.json"),
        ]
        for path in default_paths:
            if os.path.exists(path):
                config_path = path
                break
        
        if not config_path:
            # Si no hay config, intentar usar local_config.json en la raíz del proyecto
            fallback_path = os.path.join(DATA_DIR, "data/local_config.json")
            if os.path.exists(fallback_path):
                config_path = fallback_path
            else:
                # No lanzar error inmediatamente - permitir que el wizard se ejecute
                # El wizard creará la configuración necesaria
                logger.warning(
                    f"Configuración PostgreSQL no encontrada.\n"
                    f"Busca en: {', '.join(default_paths)}\n"
                    f"El wizard de configuración inicial se ejecutará."
                )
                # Guardar config_path como None para que el wizard lo maneje
                self.db = None
                self._config_path = None
                return  # Salir temprano; atributos engine/loyalty/etc ya están en None (issue 11)
        
        # CRITICAL: Intentar conectar, pero si falla, permitir que el wizard corrija las credenciales
        try:
            self.db = initialize_db(config_path)
            if self.db is None:
                # Si initialize_db retorna None, la conexión falló
                logger.warning("No se pudo inicializar la base de datos. El wizard se ejecutará para corregir las credenciales.")
                self.db = None
                self._config_path = config_path
                return  # engine/loyalty/etc siguen en None (issue 11)
            # Si llegamos aquí, la conexión fue exitosa
            logger.info("Database initialized successfully")
        except Exception as e:
            # Si hay una excepción al inicializar (credenciales incorrectas, etc.), no crashear
            # Permitir que el wizard corrija las credenciales
            logger.error("Error inicializando base de datos: %s", e)
            logger.warning("El wizard de configuración inicial se ejecutará para corregir las credenciales.")
            self.db = None
            self._config_path = config_path
            return  # engine/loyalty/etc siguen en None (issue 11)

        # Run schema migrations to ensure DB is up-to-date
        try:
            from app.utils.schema_migrations import check_and_fix_columns
            check_and_fix_columns(self.db)
        except Exception as e:
            logger.warning("Schema migrations skipped: %s", e)

        # NOTE: db_lock is redundant - DatabaseManager already handles concurrency
        # with WAL mode and retry logic. Kept for backward compatibility.
        self.db_lock = threading.Lock()
        self.engine = pos_engine
        
        # CRITICAL FIX: Inicializar caché de esquema para optimizar _ensure_column_exists()
        self._schema_cache = {}
        # Engines ahora reciben DatabaseManager en lugar de DB_PATH
        # TODO: Adaptar engines para usar DatabaseManager en lugar de DB_PATH
        # Por ahora, mantener compatibilidad pasando None o config_path
        # Los engines deberán adaptarse para usar self.db
        # Engines: Por ahora mantener compatibilidad con DB_PATH para engines legacy
        # TODO: Migrar engines para usar DatabaseManager directamente
        # Los engines aún esperan DB_PATH (string), no DatabaseManager
        # Por ahora, pasar None y dejar que los engines manejen el error
        # O pasar config_path si los engines lo aceptan
        try:
            # Intentar pasar DatabaseManager (si los engines lo soportan)
            self.loyalty_engine = LoyaltyEngine(self.db)
        except (TypeError, AttributeError):
            # Fallback: engine aún espera DB_PATH (legacy) - pasar config_path
            logger.warning("LoyaltyEngine usando modo legacy - necesita adaptación para PostgreSQL")
            self.loyalty_engine = LoyaltyEngine(config_path)
        
        try:
            self.gift_card_engine = GiftCardEngine(self.db)
        except (TypeError, AttributeError):
            logger.warning("GiftCardEngine usando modo legacy - necesita adaptación para PostgreSQL")
            self.gift_card_engine = GiftCardEngine(config_path)
        
        try:
            self.loan_engine = LoanEngine(self.db)
        except (TypeError, AttributeError):
            logger.warning("LoanEngine usando modo legacy - necesita adaptación para PostgreSQL")
            self.loan_engine = LoanEngine(config_path)
        
        # Aliases for compatibility
        self.midas = self.loyalty_engine
        self.gift_engine = self.gift_card_engine
        
        # Initialize Audit Logger
        from app.utils.audit_logger import AuditLogger, set_audit_logger
        self.audit = AuditLogger(self.db)
        set_audit_logger(self.audit)  # Set global instance
        logger.info("Audit Logger initialized")
        
        # Initialize permission engine
        from src.core.permission_engine import PermissionEngine
        self.permission_engine = PermissionEngine(self.db)
        self.permission_engine.initialize_defaults()
        
        logger.info("MIDAS Loyalty Engine initialized")
        logger.info("Gift Card Engine initialized")
        logger.info("Employee Loan Engine initialized")
        logger.info("Permission Engine initialized")

        # Verify and fix audit_log table if needed
        self._verify_and_fix_audit_table()
        
        self._run_migrations()
    
    def initialize_database(self, config_path: str = None) -> bool:
        """
        Inicializa la base de datos si no está inicializada.
        
        Args:
            config_path: Ruta al archivo de configuración database.json.
                        Si no se proporciona, busca en ubicaciones estándar.
        
        Returns:
            True si la inicialización fue exitosa, False en caso contrario.
        """
        if self.db is not None:
            logger.info("Database already initialized")
            # Asegurar que engine esté inicializado aunque db ya exista
            if self.engine is None:
                from src.services.pos_engine import pos_engine
                self.engine = pos_engine
                logger.info("Engine initialized (was None)")
            return True
        
        try:
            from src.infra.database import initialize_db
            import os
            
            # Si no se proporciona config_path, buscar en ubicaciones estándar
            if not config_path:
                default_paths = [
                    os.path.join(DATA_DIR, "data/config/database.json"),
                    os.path.join(DATA_DIR, "data/local_config.json"),
                    os.path.join(DATA_DIR, "config/database.json"),
                ]
                for path in default_paths:
                    if os.path.exists(path):
                        config_path = path
                        break
            
            if not config_path or not os.path.exists(config_path):
                logger.error("Database config not found: %s", config_path)
                return False
            
            logger.info("Initializing database from %s", config_path)
            self.db = initialize_db(config_path)
            
            # Verificación: asegurar que la inicialización fue exitosa
            if self.db is None:
                logger.error("Database initialization returned None")
                return False
            
            # Inicializar atributos que normalmente se inicializan en __init__
            # pero que no se inicializaron porque __init__ retornó temprano
            if not hasattr(self, 'db_lock'):
                import threading
                self.db_lock = threading.Lock()
            
            if not hasattr(self, 'engine') or self.engine is None:
                from src.services.pos_engine import pos_engine
                self.engine = pos_engine
            
            if not hasattr(self, '_schema_cache'):
                self._schema_cache = {}
            
            if not hasattr(self, '_cache'):
                self._cache = {
                    'app_config': None,
                    'fiscal_config': None,
                    'categories': None,
                }
                self._cache_timestamps = {}
                self._cache_ttl = 60  # 60 seconds TTL
            
            # Run schema migrations to ensure DB is up-to-date
            try:
                from app.utils.schema_migrations import check_and_fix_columns, run_migrations
                check_and_fix_columns(self.db)
            except Exception as e:
                logger.warning("Schema migrations skipped: %s", e)
                # No es crítico, continuar
            
            # Inicializar engines y otros componentes que dependen de la DB
            try:
                self._initialize_engines(config_path)
            except Exception as e:
                logger.error("Error initializing engines: %s", e)
                # Engines pueden fallar, pero la DB está inicializada
                # Continuar sin engines (modo degradado)
            
            # Verify and fix audit_log table if needed
            try:
                if hasattr(self, '_verify_and_fix_audit_table'):
                    self._verify_and_fix_audit_table()
            except Exception as e:
                logger.warning("Error verifying audit table: %s", e)
                # No es crítico, continuar
            
            # Run migrations
            try:
                if hasattr(self, '_run_migrations'):
                    self._run_migrations()
            except Exception as e:
                logger.warning("Error running migrations: %s", e)
                # No es crítico, continuar
            
            # Verificación final: probar que la DB responde
            try:
                test_query = self.db.execute_query("SELECT 1")
                if not test_query:
                    logger.error("Database test query failed")
                    self.db = None
                    return False
            except Exception as e:
                logger.error("Database test query error: %s", e)
                self.db = None
                return False
            
            logger.info("Database initialized successfully")
            return True
        except Exception as e:
            logger.error("Error initializing database: %s", e)
            # Asegurar que self.db se establece en None si falla
            self.db = None
            return False
    
    def _initialize_engines(self, config_path: str = None):
        """Inicializa los engines que dependen de la base de datos."""
        # Solo inicializar si no están ya inicializados
        if not hasattr(self, 'loyalty_engine') or self.loyalty_engine is None:
            try:
                # Intentar pasar DatabaseManager (si los engines lo soportan)
                self.loyalty_engine = LoyaltyEngine(self.db)
            except (TypeError, AttributeError):
                # Fallback: engine aún espera DB_PATH (legacy) - pasar config_path
                logger.warning("LoyaltyEngine usando modo legacy - necesita adaptación para PostgreSQL")
                self.loyalty_engine = LoyaltyEngine(config_path)
        
        if not hasattr(self, 'gift_card_engine') or self.gift_card_engine is None:
            try:
                self.gift_card_engine = GiftCardEngine(self.db)
            except (TypeError, AttributeError):
                logger.warning("GiftCardEngine usando modo legacy - necesita adaptación para PostgreSQL")
                self.gift_card_engine = GiftCardEngine(config_path)
        
        if not hasattr(self, 'loan_engine') or self.loan_engine is None:
            try:
                self.loan_engine = LoanEngine(self.db)
            except (TypeError, AttributeError):
                logger.warning("LoanEngine usando modo legacy - necesita adaptación para PostgreSQL")
                self.loan_engine = LoanEngine(config_path)
        
        # Aliases for compatibility
        self.midas = self.loyalty_engine
        self.gift_engine = self.gift_card_engine
        
        # Initialize Audit Logger (solo si no está inicializado)
        if not hasattr(self, 'audit') or self.audit is None:
            from app.utils.audit_logger import AuditLogger, set_audit_logger
            self.audit = AuditLogger(self.db)
            set_audit_logger(self.audit)  # Set global instance
            logger.info("Audit Logger initialized")
        
        # Initialize permission engine (solo si no está inicializado)
        if not hasattr(self, 'permission_engine') or self.permission_engine is None:
            from src.core.permission_engine import PermissionEngine
            self.permission_engine = PermissionEngine(self.db)
            self.permission_engine.initialize_defaults()
            logger.info("Permission Engine initialized")
        
        logger.info("MIDAS Loyalty Engine initialized")
        logger.info("Gift Card Engine initialized")
        logger.info("Employee Loan Engine initialized")
        
    def connect(self):
        """Legacy connect method."""
        return self.db.get_connection()

    @property
    def conn(self):
        """
        ⚠️ DEPRECATED: Expose connection for direct access (legacy compatibility).

        IMPORTANTE: Esta propiedad está DEPRECATED.
        Use self.db.execute_query() o self.db.execute_write() en su lugar.

        Para código legacy que requiere conexión directa, ahora retorna
        la conexión de PostgreSQL del pool (si está disponible).
        """
        import warnings
        warnings.warn(
            "POSCore.conn is deprecated. "
            "Use self.db.execute_query() or self.db.execute_write() instead.",
            DeprecationWarning,
            stacklevel=2
        )

        # FIX 2026-02-01: Retornar conexión PostgreSQL en lugar de intentar SQLite
        # Esto evita errores silenciosos cuando el sistema usa PostgreSQL
        if self.db is None:
            raise RuntimeError("Database not initialized. Cannot get connection.")

        # Intentar obtener conexión del pool de PostgreSQL
        if hasattr(self.db, 'get_connection'):
            try:
                return self.db.get_connection()
            except Exception as e:
                logger.error("Could not get PostgreSQL connection: %s", e)
                raise RuntimeError(
                    f"Cannot get database connection. "
                    f"Use self.db.execute_query() or self.db.execute_write() instead. Error: {e}"
                ) from e

        # Si no hay método get_connection, lanzar error claro
        raise RuntimeError(
            "Direct connection access not supported. "
            "Use self.db.execute_query() or self.db.execute_write() instead."
        )
        
    # Métodos que la UI espera encontrar en POSCore
    # Se delegan al engine o a la db
    
    def get_product(self, sku):
        return self.engine.get_product_by_sku(sku)

    def get_product_by_id(self, product_id):
        return self.engine.get_product_by_id(product_id)
        
    def log_action(self, user, action, details):
        """Legacy log_action - now uses audit logger"""
        logger.info("ACTION: %s - %s - %s", user, action, details)
        # Log to audit_log table
        self.audit.log(action, 'system', details={'user': user, 'info': details})
        
    def read_local_config(self):
        """Lee la configuración local desde config.json."""
        import json
        config_path = os.path.join(DATA_DIR, "data/config/config.json")
        
        if not os.path.exists(config_path):
            return {}
            
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error("Error reading config: %s", e)
            return {}

    def write_local_config(self, config):
        """Escribe la configuración local."""
        import json
        config_path = os.path.join(DATA_DIR, "data/config/config.json")
        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            logger.error("Error writing config: %s", e)
            return False

    def get_app_config(self):
        """Get app config with caching (TTL: 60s)."""
        import time
        cache_key = 'app_config'
        now = time.time()
        
        # Check if cache is valid
        if (self._cache.get(cache_key) is not None and 
            cache_key in self._cache_timestamps and
            now - self._cache_timestamps[cache_key] < self._cache_ttl):
            return self._cache[cache_key]
        
        # Refresh cache
        config = self.read_local_config()
        self._cache[cache_key] = config
        self._cache_timestamps[cache_key] = now
        return config
        
    def read_config(self):
        """Alias para get_app_config (compatibilidad)."""
        return self.get_app_config()
    
    def invalidate_cache(self, key: str = None):
        """Invalidate cache. If key is None, invalidate all."""
        if key:
            self._cache[key] = None
            self._cache_timestamps.pop(key, None)
        else:
            for k in self._cache:
                self._cache[k] = None
            self._cache_timestamps.clear()

    def get_tax_rate(self, branch_id=None):
        """Retorna la tasa de impuesto (IVA) configurada."""
        cfg = self.read_local_config()
        return cfg.get("tax_rate", 0.16)  # 16% por defecto
        
    def get_products_count(self, query=None):
        """Cuenta productos (delegado a engine)."""
        # TODO: Implementar filtro real en engine
        return self.engine.count_products(query)
        
    def get_products(self, limit=50, offset=0, query=None):
        """Lista productos (delegado a engine)."""
        return self.engine.list_products(limit, offset, query)
        
    def get_products_for_search(self, query=None, limit=50, offset=0):
        """Alias para get_products usado en ProductsTab."""
        if query:
            return self.search_products(query, limit, offset)
        return self.get_products(limit, offset, query)

    def search_products(self, query, limit=50, offset=0):
        """Búsqueda inteligente de productos."""
        sql = """
            SELECT * FROM products
            WHERE name LIKE %s OR sku LIKE %s OR barcode LIKE %s
            LIMIT %s OFFSET %s
        """
        wildcard = f"%{query}%"
        return [dict(row) for row in self.db.execute_query(sql, (wildcard, wildcard, wildcard, limit, offset))]
        
    def list_products_for_export(self):
        """Lista todos los productos para exportación/inventario."""
        return self.engine.list_products_for_export()
        
    def get_product_by_sku_or_barcode(self, sku):
        return self.engine.get_product_by_sku(sku)

    def get_product_by_sku(self, sku: str):
        """Get product by SKU - alias for consistency."""
        return self.engine.get_product_by_sku(sku)

    def get_categories(self):
        """Get all product categories."""
        try:
            return list(self.db.execute_query(
                "SELECT * FROM product_categories WHERE is_active = 1 ORDER BY name"
            ))
        except Exception as e:
            logger.warning(f"Error fetching categories: {e}")
            return []

    def get_loyalty_transactions(self, customer_id: int = None, limit: int = 100):
        """Get loyalty transactions (from loyalty_ledger table)."""
        try:
            if customer_id:
                return list(self.db.execute_query(
                    "SELECT * FROM loyalty_ledger WHERE customer_id = %s ORDER BY fecha_hora DESC LIMIT %s",
                    (customer_id, limit)
                ))
            return list(self.db.execute_query(
                "SELECT * FROM loyalty_ledger ORDER BY fecha_hora DESC LIMIT %s",
                (limit,)
            ))
        except Exception as e:
            logger.warning(f"Error fetching loyalty transactions: {e}")
            return []

    def get_customer_credit_info(self, customer_id):
        return self.engine.get_customer_credit_info(customer_id)
        
    def get_wallet_balance(self, customer_id):
        return self.engine.get_wallet_balance(customer_id)
    
    def get_loyalty_balance(self, customer_id):
        """Get loyalty points balance for customer."""
        return self.loyalty_engine.get_balance(customer_id)
    
    def calcular_cashback(self, carrito, customer_id):
        """Calculate potential cashback for a shopping cart."""
        return self.loyalty_engine.calcular_cashback_potencial(carrito, customer_id)
    
    def acumular_puntos_venta(self, customer_id, monto, sale_id, turn_id, user_id, carrito):
        """Accumulate loyalty points for a completed sale."""
        from decimal import Decimal
        return self.loyalty_engine.acumular_puntos(
            customer_id=customer_id,
            monto=Decimal(str(monto)),
            ticket_id=sale_id,
            turn_id=turn_id,
            user_id=user_id,
            carrito=carrito,
            descripcion="Compra en tienda"
        )
        
    def create_sale(self, items, payment_data, branch_id, discount, customer_id):
        # Delegate to engine with proper user_id from STATE
        # Fixed: Was hardcoded to user_id=1, now uses actual logged-in user
        user_id = STATE.user_id or 1  # Fallback to 1 if STATE not initialized
        
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E2E1","location":"core.py:create_sale","message":"E2E Flow: Entry to create_sale","data":{"items_count":len(items) if items else 0,"payment_method":payment_data.get("method") if payment_data else None,"branch_id":branch_id,"discount":discount,"customer_id":customer_id,"user_id":user_id},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e: logger.debug("Writing debug log for create_sale entry: %s", e)
        # #endregion
        
        try:
            sale_id = self.engine.create_sale_transaction(items, payment_data, branch_id, discount, customer_id, user_id)
            
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E2E1","location":"core.py:create_sale","message":"E2E Flow: Sale created successfully","data":{"sale_id":sale_id},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logger.debug("Writing debug log for sale creation success: %s", e)
            # #endregion
            
            # E2E Verification: Verify sale was created correctly
            # #region agent log
            if agent_log_enabled():
                try:
                    sale_verification = self.get_sale(sale_id)
                    sale_items_verification = self.get_sale_items(sale_id)
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E2E1","location":"core.py:create_sale","message":"E2E Flow: Post-creation verification","data":{"sale_id":sale_id,"sale_exists":sale_verification is not None,"sale_status":sale_verification.get("status") if sale_verification else None,"items_count":len(sale_items_verification) if sale_items_verification else 0},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as verify_e:
                    try:
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E2E1","location":"core.py:create_sale","message":"E2E Flow: Verification error","data":{"sale_id":sale_id,"error":str(verify_e)},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e: logger.debug("Writing debug log for sale verification error: %s", e)
            # #endregion

            # FIX: Emitir evento de venta completada para PWA
            try:
                sale_data = self.get_sale(sale_id)
                if sale_data:
                    emit_sale_completed(
                        sale_id=sale_id,
                        total=float(sale_data.get('total', 0)),
                        items_count=len(items) if items else 0,
                        payment_method=payment_data.get('method', 'cash') if payment_data else 'cash',
                        folio=sale_data.get('folio_visible')
                    )
            except Exception as emit_e:
                logger.debug("Could not emit sale event: %s", emit_e)

            return sale_id
        except Exception as e:
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E2E1","location":"core.py:create_sale","message":"E2E Flow: Error creating sale","data":{"error":str(e),"error_type":type(e).__name__},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logger.debug("Writing debug log for sale creation error: %s", e)
            # #endregion
            logger.error("Error creating sale: %s", e)
            raise e
        
    def deduct_from_wallet(self, customer_id, amount, reason, ref_id):
        self.engine.deduct_from_wallet(customer_id, amount, reason, ref_id)
        
    def add_to_wallet(self, customer_id, amount, reason, ref_id):
        self.engine.add_to_wallet(customer_id, amount, reason, ref_id)

    def create_customer(self, data):
        # Input Sanitization
        if not data.get("name"):
            raise ValueError("El nombre del cliente es obligatorio")

        # FIX 2026-02-01: Auto-fix sequence on primary key violation (similar to products)
        max_retries = 3
        for intento in range(max_retries):
            try:
                return self.engine.create_customer(data)
            except Exception as e:
                error_msg = str(e)

                # Auto-fix sequence on primary key violation
                if "customers_pkey" in error_msg or ("llave duplicada" in error_msg and "customers" in error_msg):
                    logger.warning("Secuencia de clientes desincronizada, corrigiendo...")
                    if self._fix_customers_sequence():
                        continue  # Reintentar después de corregir secuencia

                # Otro tipo de error, propagar
                raise e

        raise RuntimeError(f"No se pudo crear el cliente después de {max_retries} intentos")
        
    def update_customer(self, customer_id, data):
        return self.engine.update_customer(customer_id, data)
        
    def get_customer(self, customer_id):
        return self.engine.get_customer(customer_id)
        
    def list_customers(self, query=None, limit=300):
        return self.engine.list_customers(query, limit)

    def delete_customer(self, customer_id):
        return self.engine.delete_customer(customer_id)

    def search_customers(self, query, limit=50):
        return self.engine.search_customers(query, limit)

    def get_customer_full_profile(self, customer_id):
        """Get full customer profile including credit history"""
        customer = self.get_customer(customer_id)
        if not customer:
            return None
        # Add additional profile data if needed
        return customer

    def get_db_config(self):
        """Devuelve la configuración de la app desde la base de datos (tabla config)."""
        # NOTA: Esta función lee de la tabla 'config' en la DB
        # Para configuración de archivos JSON, usar read_local_config() o get_app_config()
        self.db.execute_write("""
            CREATE TABLE IF NOT EXISTS config (
                id BIGSERIAL PRIMARY KEY,
                key TEXT UNIQUE NOT NULL,
                value TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        rows = self.db.execute_query("SELECT key, value FROM config")

        # FIX 2026-02-01: Validar rows antes de comprehension para evitar TypeError
        if rows:
            return {row['key']: row['value'] for row in (rows or []) if row}
        else:
            return {}

    def list_users(self):
        """Lista usuarios desde la DB."""
        return [dict(row) for row in self.db.execute_query("SELECT * FROM users")]

    def verify_user(self, username: str, password: str) -> dict | None:
        """
        Verifica credenciales de usuario para autenticación.

        Busca el usuario por username y verifica la contraseña usando
        bcrypt o SHA256 según el formato del hash almacenado.

        Args:
            username: Nombre de usuario
            password: Contraseña en texto plano

        Returns:
            Diccionario del usuario si las credenciales son válidas, None en caso contrario
        """
        import hashlib
        import secrets
        import bcrypt

        if not username or not password:
            return None

        # Buscar usuario por username
        rows = self.db.execute_query(
            "SELECT * FROM users WHERE username = %s",
            (username,)
        )

        if not rows:
            return None

        user = dict(rows[0])
        stored_hash = user.get("password_hash")

        if not stored_hash:
            return None

        # Verificar contraseña según el formato del hash
        auth_success = False

        if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
            # Bcrypt hash
            try:
                auth_success = bcrypt.checkpw(
                    password.encode('utf-8'),
                    stored_hash.encode('utf-8')
                )
            except Exception as e:
                logger.error("Bcrypt verification error: %s", e)
                return None
        elif len(stored_hash) == 64:
            # SHA256 hash (64 hex characters)
            password_sha256 = hashlib.sha256(password.encode()).hexdigest()
            auth_success = secrets.compare_digest(stored_hash, password_sha256)

        if auth_success:
            return user

        return None

    def list_branches(self):
        """Lista sucursales desde la DB."""
        return [dict(row) for row in self.db.execute_query("SELECT * FROM branches")]
        
    def delete_user(self, user_id):
        # Validación WTF
        if user_id is None:
            raise ValueError("user_id es requerido")
        if isinstance(user_id, (list, dict, tuple)):
            raise ValueError(f"user_id inválido: {type(user_id).__name__}")
        try:
            uid = int(user_id)
            if uid <= 0:
                raise ValueError(f"user_id debe ser mayor a 0: {uid}")
        except (TypeError, ValueError) as e:
            raise ValueError(f"user_id inválido: {e}")
        
        self.db.execute_write("DELETE FROM users WHERE id = %s", (uid,))

    def create_user(self, data):
        # Validación WTF
        if not data or not isinstance(data, dict):
            raise ValueError("data debe ser un diccionario")
        
        username = data.get("username")
        if not username or not isinstance(username, str):
            raise ValueError("username es requerido y debe ser string")
        username = username.strip()
        if not username:
            raise ValueError("username no puede estar vacío")
        if len(username) < 3:
            raise ValueError("username debe tener al menos 3 caracteres")
        
        import bcrypt
        password = data.get("password", "")
        # SECURITY FIX: Hash password with bcrypt before storing
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8') if password else ""
        
        role = data.get("role", "cashier")
        if not isinstance(role, str):
            raise ValueError(f"role debe ser string, recibido: {type(role).__name__}")
        
        # FIX 2026-02-01: Estructura try/except simplificada y corregida
        # Problema anterior: except duplicado que nunca se ejecutaba, y ALTER TABLE
        # solo se intentaba si fallaba el método 1 (no si la columna simplemente no existía)

        # Paso 1: Detectar si la columna "name" existe
        has_name_column = False
        try:
            # Método 1: Verificar directamente en la BD via information_schema (más confiable)
            result = self.db.execute_query(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s AND column_name = 'name'",
                ("users",)
            )
            has_name_column = bool(result and len(result) > 0)
        except Exception as e:
            logger.debug("information_schema check failed: %s, trying fallback method", e)
            # Método 2: Fallback usando get_table_info
            try:
                if hasattr(self.db, 'get_table_info'):
                    table_info = self.db.get_table_info("users")
                    if table_info:
                        has_name_column = any(
                            col.get('name') == 'name' or col.get('column_name') == 'name'
                            for col in table_info if isinstance(col, dict)
                        )
            except Exception as fallback_e:
                logger.debug("get_table_info fallback also failed: %s", fallback_e)

        # Paso 2: Si la columna no existe, intentar crearla (independiente del método de detección)
        if not has_name_column:
            try:
                self.db.execute_write("ALTER TABLE users ADD COLUMN name TEXT")
                has_name_column = True
                logger.info("Added missing 'name' column to users table")
            except Exception as alter_e:
                # Puede fallar si ya existe o por permisos - continuar sin la columna
                logger.warning("Could not add name column to users: %s", alter_e)
        
        # Construir SQL dinámicamente según columnas disponibles
        if has_name_column:
            sql = "INSERT INTO users (username, password_hash, role, name, is_active) VALUES (%s, %s, %s, %s, %s)"
            params = (
                username,
                password_hash,
                role,
                data.get("name", ""),
                data.get("is_active", 1)
            )
        else:
            # Fallback: INSERT sin columna name
            sql = "INSERT INTO users (username, password_hash, role, is_active) VALUES (%s, %s, %s, %s)"
            params = (
                username,
                password_hash,
                role,
                data.get("is_active", 1)
            )
        
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                from app.utils.path_utils import get_debug_log_path_str
                log_path = get_debug_log_path_str()
                if log_path:
                    try:
                        with open(log_path, "a", encoding="utf-8") as f:
                            log_data = {
                                "sessionId":"debug-session",
                                "runId":"run1",
                                "hypothesisId":"LOGIN_A",
                                "location":"core.py:create_user",
                                "message":"Creating user with password hash",
                                "data":{
                                    "username":username,
                                    "password_length":len(password) if password else 0,
                                    "password_hash_length":len(password_hash) if password_hash else 0,
                                    "password_hash_preview":password_hash[:20] if password_hash else None,
                                    "password_hash_full":password_hash,  # Guardar hash completo para verificación
                                    "password_hash_type":"bcrypt",  # FIX: Era "SHA256" pero usamos bcrypt
                                    "role":role
                                },
                                "timestamp":int(time.time()*1000)
                            }
                            f.write(json.dumps(log_data)+"\n")
                            f.flush()
                    except Exception as log_e:
                        logger.debug("Could not write debug log: %s", log_e)
            except Exception as e:
                logger.debug("Debug logging setup failed: %s", e)
        # #endregion
        
        result = self.db.execute_write(sql, params)
        
        # #region agent log
        if agent_log_enabled():
            try:
                from app.utils.path_utils import get_debug_log_path_str
                log_path = get_debug_log_path_str()
                if log_path:
                    try:
                        # Verificar que el hash se guardó correctamente leyendo de la BD
                        stored_user = None
                        try:
                            users = self.db.execute_query(
                                "SELECT username, password_hash FROM users WHERE username = %s",
                                (username,)
                            )
                            if users and len(users) > 0:
                                # RealDictCursor retorna dict directamente
                                row = users[0]
                                if isinstance(row, dict):
                                    stored_user = row
                                elif hasattr(row, '_asdict'):
                                    stored_user = dict(row)
                                elif isinstance(row, (tuple, list)) and len(row) >= 2:
                                    stored_user = {k: v for k, v in zip(['username', 'password_hash'], row)}
                                else:
                                    stored_user = None
                        except Exception as verify_e:
                            logger.debug("Could not verify stored hash: %s", verify_e)
                    
                        with open(log_path, "a", encoding="utf-8") as f:
                            log_data = {
                                "sessionId":"debug-session",
                                "runId":"run1",
                                "hypothesisId":"LOGIN_A",
                                "location":"core.py:create_user",
                                "message":"User created, verifying stored hash",
                                # FIX 2026-02-01: REMOVED logging of password hashes - security vulnerability
                                "data":{
                                    "username":username,
                                    "result":result,
                                    "stored_hash_length":len(stored_user.get('password_hash', '')) if stored_user and isinstance(stored_user, dict) else 0,
                                    "hash_present": bool(stored_user.get('password_hash', '')) if stored_user and isinstance(stored_user, dict) else False
                                },
                                "timestamp":int(time.time()*1000)
                            }
                            f.write(json.dumps(log_data)+"\n")
                            f.flush()
                    except Exception as log_e:
                        logger.debug("Could not write debug log: %s", log_e)
            except Exception as e:
                logger.debug("Debug logging setup failed: %s", e)
        # #endregion
        
        return result

    def update_user(self, user_id, data):
        # Build SQL dynamically
        fields = []
        params = []
        if "username" in data:
            fields.append("username = %s")
            params.append(data["username"])
        if "password" in data and data["password"]:
            import bcrypt
            password_hash = bcrypt.hashpw(data["password"].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            fields.append("password_hash = %s")
            params.append(password_hash)
        if "role" in data:
            fields.append("role = %s")
            params.append(data["role"])
        if "name" in data:
            fields.append("name = %s")
            params.append(data["name"])
        if "is_active" in data:
            fields.append("is_active = %s")
            params.append(data["is_active"])
            
        if not fields:
            return

        fields.append("updated_at = CURRENT_TIMESTAMP")
        fields.append("synced = 0")
        params.append(user_id)
        # Nota: Los campos son constantes hardcodeadas, no input de usuario - seguro
        sql = f"UPDATE users SET {', '.join(fields)} WHERE id = %s"
        self.db.execute_write(sql, tuple(params))
        
    def get_user(self, user_id):
        rows = self.db.execute_query("SELECT * FROM users WHERE id = %s", (user_id,))
        # FIX 2026-02-01: Validar rows antes de acceder a rows[0] para evitar IndexError
        if not rows or len(rows) == 0:
            return None
        return dict(rows[0])
        
    def list_recent_sales(self, limit=100):
        return [dict(row) for row in self.db.execute_query("SELECT * FROM sales ORDER BY id DESC LIMIT %s", (limit,))]
    
    def get_sales(self, limit=100, **kwargs):
        """Wrapper method for backwards compatibility - gets recent sales."""
        return self.list_recent_sales(limit=limit)
        
    def get_sale_items(self, sale_id):
        """Get sale items with product names, SKU, and SAT codes for CFDI."""
        # #region agent log
        if agent_log_enabled():
            import json, time
            with open(get_debug_log_path_str(), "a") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"core.py:get_sale_items","message":"Function entry","data":{"sale_id":sale_id},"timestamp":int(time.time()*1000)})+"\n")
        # #endregion
        sql = """
            SELECT si.*, p.name, p.sku, p.barcode, 
                   p.sat_clave_prod_serv, p.sat_clave_unidad
            FROM sale_items si
            LEFT JOIN products p ON si.product_id = p.id
            WHERE si.sale_id = %s
        """
        items = [dict(row) for row in self.db.execute_query(sql, (sale_id,))]
        # #region agent log
        if agent_log_enabled():
            with open(get_debug_log_path_str(), "a") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"core.py:get_sale_items","message":"Function exit","data":{"sale_id":sale_id,"items_count":len(items),"items":items[:3] if items else []},"timestamp":int(time.time()*1000)})+"\n")
        # #endregion
        return items
        
    def get_cfdi_for_sale(self, sale_id):
        return None # Mock
        
    def get_sale(self, sale_id):
        res = self.db.execute_query("SELECT * FROM sales WHERE id = %s", (sale_id,))
        return dict(res[0]) if res else None
    
    def get_config(self, key: str, default: str = None) -> str:
        """Get a configuration value from the database (WORKAROUND - works with any schema)."""
        # Validación WTF
        if not key or not isinstance(key, str):
            logger.warning("get_config: key inválido: %r", key)
            return default
        
        try:
            result = self.db.execute_query(
                "SELECT value FROM config WHERE key = %s", (key,)
            )
            if not result or len(result) == 0:
                return default
            return result[0]['value'] if result[0] else default
        except Exception as e:
            logger.error("Error getting config %s: %s", key, e)
            return default
    
    def set_config(self, key: str, value: str):
        """Set a configuration value in the database (WORKAROUND - works with any schema)."""
        # Validaciones WTF
        if not key or not isinstance(key, str):
            raise ValueError(f"key es requerido y debe ser string, recibido: {type(key).__name__}")
        key = key.strip()
        if not key:
            raise ValueError("key no puede estar vacío")
        
        if value is None:
            value = ""
        if not isinstance(value, str):
            # Intentar convertir a string si es un tipo simple
            if isinstance(value, (int, float, bool)):
                value = str(value)
            else:
                raise ValueError(f"value debe ser string, recibido: {type(value).__name__}")
        
        try:
            # PostgreSQL: Use ON CONFLICT DO UPDATE
            # SQLite fallback: Use INSERT OR REPLACE (handled by query_converter)
            self.db.execute_write(
                "INSERT INTO config (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (key, value)
            )
        except Exception as e:
            logger.error("Error setting config %s: %s", key, e)
            raise
    
    def get_sale_details(self, sale_id):
        """Get complete sale data with items for printing tickets."""
        sale = self.get_sale(sale_id)
        if not sale:
            return None
        
        # Get items with product names and SAT codes
        # FIXED: Use COALESCE with NULLIF to handle si.name being 'None' (legacy bug)
        # Prefer si.name if valid, fallback to p.name
        items_raw = self.db.execute_query("""
            SELECT si.id, si.sale_id, si.product_id, si.qty, si.price, si.subtotal, 
                   si.total, si.discount,
                   COALESCE(NULLIF(si.name, 'None'), p.name, 'Producto') as name,
                   p.barcode,
                   COALESCE(si.sat_clave_prod_serv, p.sat_clave_prod_serv, '01010101') as sat_clave_prod_serv,
                   COALESCE(si.sat_descripcion, p.sat_descripcion, '') as sat_descripcion,
                   p.sat_clave_unidad,
                   si.price as base_price
            FROM sale_items si
            LEFT JOIN products p ON si.product_id = p.id
            WHERE si.sale_id = %s
        """, (sale_id,))
        
        sale['items'] = [dict(row) for row in items_raw]
        
        # CRITICAL: Normalize discounts from database (-0.0 to 0.0, clamp negatives)
        # This ensures consistency when reading historical sales
        for item in sale['items']:
            discount = float(item.get('discount', 0.0))
            # Use abs() < tolerance instead of == 0.0 to handle floating point precision
            if abs(discount) < 1e-9:
                item['discount'] = 0.0  # Normalize -0.0 and near-zero to 0.0
            else:
                item['discount'] = max(0.0, discount)  # Clamp negative discounts to 0
            
            # CRITICAL DEBUG: Log price from database for debugging price discrepancies
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"PRICE_DB","location":"core.py:get_sale_details","message":"Price retrieved from database","data":{"sale_id":sale_id,"item_price":item.get('price'),"item_base_price":item.get('base_price'),"item_subtotal":item.get('subtotal'),"item_total":item.get('total'),"item_discount":item.get('discount'),"qty":item.get('qty'),"product_id":item.get('product_id')},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logger.debug("Writing debug log for price from database: %s", e)
            # #endregion
        
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                line_discounts_sum = sum(float(item.get('discount', 0)) for item in sale['items'])
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"K","location":"core.py:get_sale_details","message":"Retrieved sale details from DB","data":{"sale_id":sale_id,"subtotal":sale.get('subtotal'),"tax":sale.get('tax'),"discount":sale.get('discount'),"total":sale.get('total'),"items_count":len(sale['items']),"line_discounts_sum":line_discounts_sum},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e: logger.debug("Writing debug log for sale details retrieval: %s", e)
        # #endregion
        
        # Add created_at alias for timestamp if not present
        if 'timestamp' in sale and 'created_at' not in sale:
            sale['created_at'] = sale['timestamp']
        
        return sale

    def get_sales_by_range(self, date_from, date_to, branch_id=None):
        # Validaciones
        if not date_from or not isinstance(date_from, str):
            raise ValueError("date_from es requerido y debe ser string")
        if not date_to or not isinstance(date_to, str):
            raise ValueError("date_to es requerido y debe ser string")
        
        # Extraer solo la parte de fecha (YYYY-MM-DD) si viene con hora
        import re
        date_pattern = r'^(\d{4}-\d{2}-\d{2})'
        
        match_from = re.match(date_pattern, date_from)
        match_to = re.match(date_pattern, date_to)
        
        if not match_from:
            raise ValueError(f"date_from formato inválido: {date_from}")
        if not match_to:
            raise ValueError(f"date_to formato inválido: {date_to}")
        
        # Usar solo la parte de fecha
        date_from_clean = match_from.group(1)
        date_to_clean = match_to.group(1)
        
        sql = "SELECT * FROM sales WHERE timestamp BETWEEN %s AND %s"
        params = [f"{date_from_clean} 00:00:00", f"{date_to_clean} 23:59:59"]
        return [dict(row) for row in self.db.execute_query(sql, tuple(params))]

    def get_sale_items_count_batch(self, sale_ids):
        """Get item count for multiple sales in one query."""
        if not sale_ids:
            return {}
        placeholders = ",".join(["%s" for _ in sale_ids])
        sql = f"""
            SELECT sale_id, COUNT(*) as item_count
            FROM sale_items
            WHERE sale_id IN ({placeholders})
            GROUP BY sale_id
        """
        result = self.db.execute_query(sql, tuple(sale_ids))
        return {row['sale_id']: row['item_count'] for row in result}

    def get_sales_cfdi_batch(self, sale_ids):
        """Get CFDI status for multiple sales in one query."""
        if not sale_ids:
            return {}
        placeholders = ",".join(["%s" for _ in sale_ids])
        sql = f"""
            SELECT sale_id, uuid, estado
            FROM cfdis
            WHERE sale_id IN ({placeholders})
        """
        result = self.db.execute_query(sql, tuple(sale_ids))
        return {row['sale_id']: dict(row) for row in result}

    def get_sale_items_by_range(self, date_from, date_to, branch_id=None):
        sql = """
            SELECT si.*, p.name, si.subtotal as total
            FROM sale_items si
            JOIN sales s ON si.sale_id = s.id
            LEFT JOIN products p ON si.product_id = p.id
            WHERE s.timestamp BETWEEN %s AND %s
        """
        params = [f"{date_from} 00:00:00", f"{date_to} 23:59:59"]
        return [dict(row) for row in self.db.execute_query(sql, tuple(params))]

    def get_sales_grouped_by_date(self, date_from, date_to, branch_id = None):
        sql = """
            SELECT CAST(timestamp AS DATE) as day, COALESCE(SUM(total), 0) as total
            FROM sales
            WHERE timestamp BETWEEN %s AND %s
            GROUP BY day
            ORDER BY day
        """
        params = [f"{date_from} 00:00:00", f"{date_to} 23:59:59"]
        return [dict(row) for row in self.db.execute_query(sql, tuple(params))]

    def get_sales_by_method(self, date_from, date_to, branch_id=None):
        sql = """
            SELECT payment_method as method, COALESCE(SUM(total), 0) as amount
            FROM sales
            WHERE timestamp BETWEEN %s AND %s
            GROUP BY payment_method
        """
        params = [f"{date_from} 00:00:00", f"{date_to} 23:59:59"]
        return [dict(row) for row in self.db.execute_query(sql, tuple(params))]

    def get_credit_report(self, date_from, date_to, branch_id=None):
        # Get all customers with balance > 0
        sql = "SELECT * FROM customers WHERE credit_balance > 0"
        accounts = [dict(row) for row in self.db.execute_query(sql)]
        total_balance = sum(float(a["credit_balance"] or 0) for a in accounts)

        # FIX 2026-01-30: Calcular total_credit y total_paid de credit_history
        # total_credit = ventas a crédito en el período (transaction_type = 'SALE' o 'CREDIT')
        # total_paid = pagos recibidos en el período (transaction_type = 'PAYMENT')
        total_credit = 0.0
        total_paid = 0.0
        movements = []

        try:
            # Obtener ventas a crédito en el período
            credit_sql = """
                SELECT COALESCE(SUM(ABS(amount)), 0) as total
                FROM credit_history
                WHERE timestamp BETWEEN %s AND %s
                AND transaction_type IN ('SALE', 'CREDIT', 'CHARGE')
            """
            credit_result = self.db.execute_query(credit_sql, (f"{date_from} 00:00:00", f"{date_to} 23:59:59"))
            # FIX 2026-02-01: Validar credit_result con len() antes de acceder a [0]
            if credit_result and len(credit_result) > 0 and credit_result[0]:
                total_credit = float(credit_result[0].get('total', 0) or 0)

            # Obtener pagos recibidos en el período
            paid_sql = """
                SELECT COALESCE(SUM(ABS(amount)), 0) as total
                FROM credit_history
                WHERE timestamp BETWEEN %s AND %s
                AND transaction_type = 'PAYMENT'
            """
            paid_result = self.db.execute_query(paid_sql, (f"{date_from} 00:00:00", f"{date_to} 23:59:59"))
            # FIX 2026-02-01: Validar paid_result con len() antes de acceder a [0]
            if paid_result and len(paid_result) > 0 and paid_result[0]:
                total_paid = float(paid_result[0].get('total', 0) or 0)

            # Obtener movimientos del período
            movements_sql = """
                SELECT ch.*, c.name as customer_name
                FROM credit_history ch
                LEFT JOIN customers c ON ch.customer_id = c.id
                WHERE ch.timestamp BETWEEN %s AND %s
                ORDER BY ch.timestamp DESC
                LIMIT 100
            """
            movements = [dict(row) for row in self.db.execute_query(movements_sql, (f"{date_from} 00:00:00", f"{date_to} 23:59:59"))]
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Error calculating credit totals: {e}")

        # Add full_name if missing
        for acc in accounts:
            if not acc.get("full_name"):
                acc["full_name"] = acc.get("name", "Cliente")

        return {
            "total_credit": total_credit,
            "total_paid": total_paid,
            "balance_due": total_balance,
            "total": total_balance,
            "movements": movements,
            "accounts": accounts
        }

    def get_layaway_report(self, date_from, date_to, branch_id=None):
        sql = "SELECT l.*, c.name as customer_name FROM layaways l LEFT JOIN customers c ON l.customer_id = c.id WHERE l.created_at BETWEEN %s AND %s"
        params = [f"{date_from} 00:00:00", f"{date_to} 23:59:59"]
        layaways = [dict(row) for row in self.db.execute_query(sql, tuple(params))]
        
        total_balance = sum(float(l.get("balance_due", 0) or 0) for l in layaways)
        total_paid = sum(float(l.get("amount_paid", 0) or 0) for l in layaways)
        
        return {
            "total_new": len(layaways),
            "total_completed": 0,
            "total_cancelled": 0,
            "total_amount": sum(float(l.get("total_amount", 0) or 0) for l in layaways),
            "total_paid": total_paid,
            "balance_due": total_balance,
            "total_balance": total_balance,
            "total_deposits": total_paid,
            "layaways": layaways
        }

    def get_turns_by_range(self, date_from, date_to, branch_id=None):
        sql = "SELECT * FROM turns WHERE start_timestamp BETWEEN %s AND %s"
        params = [f"{date_from} 00:00:00", f"{date_to} 23:59:59"]
        return [dict(row) for row in self.db.execute_query(sql, tuple(params))]

    def list_backups(self):
        import glob
        backup_dir = os.path.join(DATA_DIR, "backups")
        if not os.path.exists(backup_dir):
            return []
        files = glob.glob(os.path.join(backup_dir, "*.db")) + glob.glob(os.path.join(backup_dir, "*.zip"))
        backups = []
        for f in files:
            backups.append({
                "filename": os.path.basename(f),
                "path": f,
                "size": os.path.getsize(f),
                "created_at": datetime.fromtimestamp(os.path.getmtime(f)).isoformat()
            })
        return sorted(backups, key=lambda x: x['created_at'], reverse=True)

    def list_cfdi(self, date_from=None, date_to=None, customer_id=None, status=None):
        """List CFDIs with optional filters."""
        sql = "SELECT * FROM cfdis WHERE 1=1"
        params = []
        
        if date_from:
            sql += " AND CAST(fecha_emision AS DATE) >= %s"
            params.append(date_from)
        if date_to:
            sql += " AND CAST(fecha_emision AS DATE) <= %s"
            params.append(date_to)
        if customer_id:
            sql += " AND customer_id = %s"
            params.append(customer_id)
        if status:
            sql += " AND estado = %s"
            params.append(status)
        
        sql += " ORDER BY id DESC"
        return list(self.db.execute_query(sql, tuple(params)))
    
    def update_cfdi_status(self, cfdi_id, new_status, reason=None):
        """Update CFDI status (timbrado, cancelado, etc.)."""
        from datetime import datetime
        
        if new_status == 'cancelado':
            self.db.execute_write(
                "UPDATE cfdis SET estado = %s, motivo_cancelacion = %s, fecha_cancelacion = %s, updated_at = CURRENT_TIMESTAMP, synced = 0 WHERE id = %s",
                (new_status, reason, datetime.now().isoformat(), cfdi_id)
            )
        else:
            self.db.execute_write(
                "UPDATE cfdis SET estado = %s, updated_at = CURRENT_TIMESTAMP, synced = 0 WHERE id = %s",
                (new_status, cfdi_id)
            )
        return True

    def get_fiscal_config(self, branch_id=None):
        """Get fiscal configuration for branch with decrypted passwords."""
        branch_id = branch_id or STATE.branch_id or 1
        
        result = self.db.execute_query(
            "SELECT * FROM fiscal_config WHERE branch_id = %s",
            (branch_id,)
        )
        
        if result and len(result) > 0 and result[0]:
            config = dict(result[0])
            # Decrypt sensitive fields
            if config.get('csd_key_password_encrypted'):
                try:
                    config['csd_key_password'] = self._decrypt_field(
                        config['csd_key_password_encrypted']
                    )
                except Exception as e:
                    logger.error(f"Error decrypting CSD key password: {e}")
                    config['csd_key_password'] = ''

            if config.get('pac_password_encrypted'):
                try:
                    config['pac_password'] = self._decrypt_field(
                        config['pac_password_encrypted']
                    )
                except Exception as e:
                    logger.error(f"Error decrypting PAC password: {e}")
                    config['pac_password'] = ''
            return config
        
        return {}  # Empty config for new setup

    def update_fiscal_config(self, config_data, branch_id=None):
        """Save fiscal configuration with encrypted passwords."""
        branch_id = branch_id or STATE.branch_id or 1

        # FIX 2026-02-01: Validar config_data no sea None antes de procesar
        if not config_data:
            logger.warning("update_fiscal_config called with empty config_data")
            return False

        # Prepare data for saving
        save_data = config_data.copy()
        
        # Handle sensitive fields - ALWAYS remove original keys as DB only has _encrypted columns
        # Only encrypt and store if value is not empty
        csd_pass = save_data.pop('csd_key_password', None)
        if csd_pass:
            save_data['csd_key_password_encrypted'] = self._encrypt_field(csd_pass)
        
        pac_pass = save_data.pop('pac_password', None)
        if pac_pass:
            save_data['pac_password_encrypted'] = self._encrypt_field(pac_pass)
        
        # Check if config exists
        existing = self.db.execute_query(
            "SELECT id FROM fiscal_config WHERE branch_id = %s",
            (branch_id,)
        )
        
        if existing:
            # UPDATE existing record
            set_fields = []
            values = []
            for key, value in save_data.items():
                if key not in ['id', 'branch_id', 'created_at']:
                    set_fields.append(f"{key} = %s")
                    values.append(value)
            
            set_fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(branch_id)
            
            sql = f"UPDATE fiscal_config SET {', '.join(set_fields)} WHERE branch_id = %s"
            self.db.execute_write(sql, tuple(values))
        else:
            # INSERT new record
            save_data['branch_id'] = branch_id
            columns = ', '.join(save_data.keys())
            placeholders = ', '.join(['%s' for _ in save_data])
            sql = f"INSERT INTO fiscal_config ({columns}) VALUES ({placeholders})"
            self.db.execute_write(sql, tuple(save_data.values()))
        
        logger.info("Fiscal config saved for branch %s", branch_id)

    def get_turn_summary(self, turn_id):
        # 1. Obtener datos del turno
        turn_rows = self.db.execute_query("SELECT * FROM turns WHERE id = %s", (turn_id,))
        if not turn_rows or len(turn_rows) == 0:
            return {}
        turn = dict(turn_rows[0]) if turn_rows[0] else {}
        initial_cash = float(turn.get('initial_cash') or 0.0)
        
        # 2. Calcular Ventas totales (excluyendo canceladas)
        # Necesitamos sumarizar correctamente los pagos mixtos
        
        # A. Ventas puras (agrupadas por método)
        payment_breakdown_rows = self.db.execute_query("""
            SELECT 
                payment_method,
                COUNT(*) as transaction_count,
                COALESCE(SUM(total), 0) as total_amount
            FROM sales
            WHERE turn_id = %s AND status != 'cancelled'
            GROUP BY payment_method
        """, (turn_id,))
        
        payment_breakdown = {}
        total_sales_all_methods = 0.0
        
        # Inicializar contadores base
        cash_total_amount = 0.0
        
        for row in payment_breakdown_rows:
            method = row['payment_method'] or 'cash'
            count = row['transaction_count']
            amount = float(row['total_amount'] or 0.0)
            
            payment_breakdown[method] = {
                'count': count,
                'total': amount
            }
            total_sales_all_methods += amount
            
            if method == 'cash':
                cash_total_amount += amount

        # B. Desglosar pagos mixtos para corregir el total de efectivo esperado
        # Si hubo pagos mixtos, hay una columna 'mixed_cash' y 'mixed_card' (u otros) en la tabla sales
        # (Asumiendo que existen esas columnas, si no, se toman de total)
        
        try:
            mixed_rows = self.db.execute_query("""
                SELECT 
                    SUM(COALESCE(mixed_cash, 0)) as total_mixed_cash,
                    SUM(COALESCE(mixed_card, 0)) as total_mixed_card,
                    COUNT(*) as count
                FROM sales
                WHERE turn_id = %s AND payment_method = 'mixed' AND status != 'cancelled'
            """, (turn_id,))
            
            if mixed_rows and len(mixed_rows) > 0 and mixed_rows[0] and mixed_rows[0].get('count', 0) > 0:
                mixed_cash = float(mixed_rows[0].get('total_mixed_cash') or 0.0)
                mixed_card = float(mixed_rows[0].get('total_mixed_card') or 0.0)
                
                # Actualizar el desglose financiero (Virtual)
                # No eliminamos la entrada 'mixed' del breakdown original (para que se sepa que hubo operaciones mixtas)
                # Pero ajustamos el "Cash Total" para el corte de caja
                cash_total_amount += mixed_cash
                
                # Opcional: Agregar desglose específico al diccionario para el reporte
                payment_breakdown['mixed_details'] = {
                    'cash_component': mixed_cash,
                    'card_component': mixed_card
                }
        except Exception as e:
            pass # Si no existen columnas mixed_, se ignora
            
        # 4. Calcular Movimientos de Caja
        movements_rows = self.db.execute_query("""
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'in' THEN amount ELSE 0 END), 0) as total_in,
                COALESCE(SUM(CASE WHEN type = 'out' THEN amount ELSE 0 END), 0) as total_out
            FROM cash_movements
            WHERE turn_id = %s
        """, (turn_id,))
        
        total_in = float(movements_rows[0].get('total_in') or 0.0) if movements_rows and len(movements_rows) > 0 and movements_rows[0] else 0.0
        total_out = float(movements_rows[0].get('total_out') or 0.0) if movements_rows and len(movements_rows) > 0 and movements_rows[0] else 0.0
        
        # 5. Calcular Gastos en Efectivo (cash_expenses) del día actual
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            expenses_rows = self.db.execute_query("""
                SELECT COALESCE(SUM(amount), 0) as total_expenses, COUNT(*) as count
                FROM cash_expenses
                WHERE timestamp::date = %s::date
            """, (today,))
            
            total_expenses = float(expenses_rows[0].get('total_expenses') or 0.0) if expenses_rows and len(expenses_rows) > 0 and expenses_rows[0] else 0.0
            expenses_count = int(expenses_rows[0].get('count') or 0) if expenses_rows and len(expenses_rows) > 0 and expenses_rows[0] else 0
        except Exception as e:
            logger.warning(f"Error fetching cash expenses: {e}")
            total_expenses = 0.0
            expenses_count = 0
        
        # Fórmula corregida: Final = Fondo + Ventas(Efectivo) + Entradas - Salidas - Gastos
        expected_cash = initial_cash + cash_total_amount + total_in - total_out - total_expenses
        
        return {
            "expected_cash": round(expected_cash, 2),
            "cash_sales": round(cash_total_amount, 2), # Ahora incluye lo mixto
            "initial_cash": round(initial_cash, 2),
            "total_in": round(total_in, 2),
            "total_out": round(total_out, 2),
            "total_expenses": round(total_expenses, 2),  # NUEVO
            "expenses_count": expenses_count,  # NUEVO
            "payment_breakdown": payment_breakdown,
            "total_sales_all_methods": round(total_sales_all_methods, 2),
            "turn_id": turn_id,
            "user_id": turn.get('user_id')
        }

    def get_turn_movements(self, turn_id):
        sql = """
            SELECT id, type as movement_type, amount, reason, timestamp as created_at 
            FROM cash_movements 
            WHERE turn_id = %s 
            ORDER BY id DESC
        """
        return [dict(row) for row in self.db.execute_query(sql, (turn_id,))]

    def list_all_customers_with_credit_meta(self):
        # Mock implementation
        return []

    def list_layaways(self, active_only=None, branch_id=None, status=None, date_range=None):
        # Handle legacy parameter
        if active_only is not None:
            status = 'active' if active_only else None
        return self.engine.list_layaways(branch_id=branch_id or 1, status=status or "active", date_range=date_range)
    
    def liquidate_layaway(self, layaway_id, user_id=None):
        """Complete a layaway and consume reserved stock."""
        return self.engine.liquidate_layaway(layaway_id, user_id=user_id or STATE.user_id)
    
    def _get_encryption_key(self):
        """Get or create encryption key for sensitive fiscal data."""
        config = self.read_local_config()
        if 'fiscal_encryption_key' not in config:
            from cryptography.fernet import Fernet
            config['fiscal_encryption_key'] = Fernet.generate_key().decode()
            self.write_local_config(config)
        # FIX 2026-02-01: Validar key antes de encode para evitar AttributeError
        key = config.get('fiscal_encryption_key')
        if not key:
            raise ValueError("Encryption key not configured - cannot proceed with encryption")
        return key.encode()
    
    def _encrypt_field(self, value):
        """Encrypt sensitive field value."""
        if not value:
            return ""
        try:
            from cryptography.fernet import Fernet
            f = Fernet(self._get_encryption_key())
            return f.encrypt(value.encode()).decode()
        except Exception as e:
            logger.error("Encryption failed: %s", e)
            return ""
    
    def _decrypt_field(self, encrypted_value):
        """Decrypt sensitive field value."""
        if not encrypted_value:
            return ""
        try:
            from cryptography.fernet import Fernet
            f = Fernet(self._get_encryption_key())
            return f.decrypt(encrypted_value.encode()).decode()
        except Exception as e:
            logger.error("Decryption failed: %s", e)
            return ""
    
    def issue_cfdi_for_sale(
        self,
        sale_id: int,
        customer_rfc: str,
        customer_name: str = None,
        customer_regime: str = '616',
        uso_cfdi: str = 'G03',
        forma_pago: str = '01',
        customer_zip: str = '00000'
    ):
        """
        Generate CFDI invoice for a sale.
        
        Args:
            sale_id: Sale ID to invoice
            customer_rfc: Customer's RFC
            customer_name: Customer's legal name
            customer_regime: Customer's fiscal regime
            uso_cfdi: CFDI use code
            forma_pago: Payment form SAT code
            customer_zip: Customer's postal code
            
        Returns:
            Result dictionary with success, uuid, xml_path, etc.
        """
        from app.fiscal.cfdi_service import CFDIService
        
        service = CFDIService(self)
        return service.generate_cfdi_for_sale(
            sale_id=sale_id,
            customer_rfc=customer_rfc,
            customer_name=customer_name,
            customer_regime=customer_regime,
            uso_cfdi=uso_cfdi,
            forma_pago=forma_pago,
            customer_zip=customer_zip
        )
    
    def get_cfdi_by_sale(self, sale_id: int):
        """Get CFDI record for a sale."""
        result = self.db.execute_query(
            "SELECT * FROM cfdis WHERE sale_id = %s",
            (sale_id,)
        )
        if result and len(result) > 0 and result[0]:
            return dict(result[0])
        return None

    def cancel_cfdi(self, uuid: str, motivo: str = '02', folio_sustitucion: str = None):
        """
        Cancel a CFDI invoice.
        
        Args:
            uuid: UUID of CFDI to cancel
            motivo: Cancellation reason code
            folio_sustitucion: Replacement UUID if applicable
            
        Returns:
            Result dictionary
        """
        from app.fiscal.cfdi_service import CFDIService
        
        service = CFDIService(self)
        return service.cancel_cfdi(uuid, motivo, folio_sustitucion)
    
    def list_cfdis(self, date_from=None, date_to=None, estado=None):
        """List CFDIs with optional filters."""
        conditions = []
        params = []
        
        if date_from:
            conditions.append("fecha_emision >= %s")
            params.append(date_from)
        
        if date_to:
            conditions.append("fecha_emision <= %s")
            params.append(date_to)
        
        if estado:
            conditions.append("estado = %s")
            params.append(estado)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        sql = f"SELECT * FROM cfdis WHERE {where_clause} ORDER BY created_at DESC"
        result = self.db.execute_query(sql, tuple(params))
        
        return [dict(row) for row in result] if result else []
    
    def get_next_folio(self):
        """Get next available folio number from secuencias table (atomic)."""
        try:
            self.db.execute_write(
                "INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion, synced) "
                "VALUES ('A', 1, 0, 'Fiscal default', 0) ON CONFLICT (serie, terminal_id) DO NOTHING",
                ()
            )
        except Exception:
            pass
        numero = self.db.execute_write(
            "UPDATE secuencias SET ultimo_numero = ultimo_numero + 1 "
            "WHERE serie = 'A' AND terminal_id = 1 RETURNING ultimo_numero",
            ()
        )
        if numero:
            return int(numero)
        result = self.db.execute_query(
            "SELECT COALESCE(MAX(folio), 1000) + 1 as next_folio FROM cfdis"
        )
        return result[0]['next_folio'] if result else 1001
    
    def get_current_turn(self, branch_id, user_id):
        # Simplificado: busca el último turno abierto del usuario
        rows = self.db.execute_query("SELECT * FROM turns WHERE user_id = %s AND status = 'OPEN' ORDER BY id DESC LIMIT 1", (user_id,))
        # FIX 2026-02-01: Validar rows antes de acceder a rows[0] para evitar IndexError
        if not rows or len(rows) == 0:
            return None
        return dict(rows[0])

    def open_turn(self, branch_id, user_id, initial_cash, notes=None):
        """Abre un nuevo turno con validaciones."""
        import math

        # Validar branch_id
        if branch_id is not None:
            if isinstance(branch_id, bool):
                raise ValueError("branch_id no puede ser booleano")
            if isinstance(branch_id, (list, dict, tuple, set)):
                raise ValueError(f"branch_id inválido: tipo {type(branch_id).__name__}")
            try:
                bid = int(branch_id)
                if bid <= 0:
                    raise ValueError(f"branch_id debe ser mayor a 0: {bid}")
            except (TypeError, ValueError) as e:
                raise ValueError(f"branch_id inválido: {e}")
        
        # Validar user_id
        if user_id is None:
            raise ValueError("user_id es requerido")
        if isinstance(user_id, bool):
            raise ValueError("user_id no puede ser booleano")
        if isinstance(user_id, (list, dict, tuple, set)):
            raise ValueError(f"user_id inválido: tipo {type(user_id).__name__}")
        try:
            uid = int(user_id)
            if uid <= 0:
                raise ValueError(f"user_id debe ser mayor a 0: {uid}")
        except (TypeError, ValueError) as e:
            raise ValueError(f"user_id inválido: {e}")
        
        # Validar initial_cash
        if initial_cash is None:
            raise ValueError("initial_cash es requerido")
        if isinstance(initial_cash, (list, dict, tuple, set)):
            raise ValueError(f"initial_cash inválido: tipo {type(initial_cash).__name__}")
        try:
            cash = float(initial_cash)
            if math.isnan(cash) or math.isinf(cash):
                raise ValueError("initial_cash no puede ser NaN o Infinito")
            if cash < 0:
                raise ValueError(f"initial_cash no puede ser negativo: {cash}")
        except (TypeError, ValueError) as e:
            raise ValueError(f"initial_cash inválido: {e}")
        
        turn_id = self.engine.open_turn(uid, cash)
        
        # AUDIT LOG - Turn opened
        try:
            self.audit.log_turn_open(turn_id, cash, user_id=uid)
        except Exception as e:
            logger.error("Audit log failed: %s", e)
        
        return turn_id

    def close_turn(self, turn_id, final_cash, notes=None, expected_cash=None):
        """Cierra un turno con validaciones."""
        import math

        # Validar turn_id
        if turn_id is None:
            raise ValueError("turn_id es requerido")
        if isinstance(turn_id, (list, dict, tuple, set)):
            raise ValueError(f"turn_id inválido: tipo {type(turn_id).__name__}")
        try:
            tid = int(turn_id)
            if tid <= 0:
                raise ValueError(f"turn_id debe ser mayor a 0: {tid}")
        except (TypeError, ValueError) as e:
            raise ValueError(f"turn_id inválido: {e}")
        
        # Validar final_cash
        if final_cash is None:
            raise ValueError("final_cash es requerido")
        if isinstance(final_cash, (list, dict, tuple, set)):
            raise ValueError(f"final_cash inválido: tipo {type(final_cash).__name__}")
        try:
            fcash = float(final_cash)
            if math.isnan(fcash) or math.isinf(fcash):
                raise ValueError("final_cash no puede ser NaN o Infinito")
            if fcash < 0:
                raise ValueError(f"final_cash no puede ser negativo: {fcash}")
        except (TypeError, ValueError) as e:
            raise ValueError(f"final_cash inválido: {e}")
        
        # Get turn summary for audit
        summary = self.get_turn_summary(tid)
        user_id = summary.get('user_id')
        expected = expected_cash if expected_cash is not None else summary.get('expected_cash', 0.0)
        difference = fcash - expected
        
        # Close the turn
        self.engine.close_turn(user_id, fcash, notes)
        
        # AUDIT LOG - Turn closed
        try:
            self.audit.log_turn_close(tid, fcash, expected, difference)
        except Exception as e:
            logger.error("Audit log failed: %s", e)
        
        return True

    def get_stock_info(self, product_id, branch_id=None):
        """Obtiene información de stock directamente de la DB (sin caché)."""
        # Query directly to avoid stale cache data
        rows = self.db.execute_query(
            "SELECT stock FROM products WHERE id = %s", 
            (product_id,)
        )
        if rows and len(rows) > 0 and rows[0]:
            return {"stock": float(rows[0].get("stock") or 0.0)}
        return {"stock": 0.0}

    def get_kit_items(self, product_id):
        """Obtiene los componentes de un kit."""
        return self.engine.get_kit_components(product_id)
    
    def add_kit_component(self, kit_id, component_id, qty=1.0):
        """Agrega un componente a un KIT."""
        return self.engine.add_kit_component(kit_id, component_id, qty)
    
    def remove_kit_component(self, kit_id, component_id):
        """Elimina un componente de un KIT."""
        return self.engine.remove_kit_component(kit_id, component_id)
    
    def update_kit_component_qty(self, kit_id, component_id, new_qty):
        """Actualiza cantidad de un componente en un KIT."""
        return self.engine.update_kit_component_quantity(kit_id, component_id, new_qty)
    
    def get_kit_suggested_price(self, kit_id):
        """Calcula precio sugerido para un KIT."""
        return self.engine.calculate_kit_suggested_price(kit_id)

    def get_inventory_movements(self, product_id, limit=50):
        """Obtiene historial de movimientos de inventario."""
        sql = "SELECT * FROM inventory_log WHERE product_id = %s ORDER BY id DESC LIMIT %s"
        return [dict(row) for row in self.db.execute_query(sql, (product_id, limit))]

    def _run_migrations(self):
        """Run database migrations with duplicate column checks"""
        # Helper to check if column exists
        def column_exists(table, column):
            try:
                # PostgreSQL: usar get_table_info en lugar de PRAGMA
                cols = self.db.get_table_info(table) if hasattr(self.db, 'get_table_info') else []
                return any(c['name'] == column for c in cols)
            except Exception:
                return False
        
        # 1. Sales columns
        if not column_exists('sales', 'status'):
            try:
                self.db.execute_write("ALTER TABLE sales ADD COLUMN status TEXT DEFAULT 'completed'")
            except Exception as e: logger.debug("Adding status column to sales: %s", e)
        
        if not column_exists('sales', 'notes'):
            try:
                self.db.execute_write("ALTER TABLE sales ADD COLUMN notes TEXT")
            except Exception as e: logger.debug("Adding notes column to sales: %s", e)

        if not column_exists('products', 'is_active'):
            try:
                self.db.execute_write("ALTER TABLE products ADD COLUMN is_active INTEGER DEFAULT 1")
            except Exception as e: logger.debug("Adding is_active column to products: %s", e)

        # 2. Customers columns
        if not column_exists('customers', 'credit_limit'):
            try:
                self.db.execute_write("ALTER TABLE customers ADD COLUMN credit_limit REAL DEFAULT 0")
            except Exception as e: logger.debug("Adding credit_limit column to customers: %s", e)
        
        if not column_exists('customers', 'credit_balance'):
            try:
                self.db.execute_write("ALTER TABLE customers ADD COLUMN credit_balance REAL DEFAULT 0")
            except Exception as e: logger.debug("Adding credit_balance column to customers: %s", e)
        
        if not column_exists('customers', 'credit_authorized'):
            try:
                self.db.execute_write("ALTER TABLE customers ADD COLUMN credit_authorized INTEGER DEFAULT 0")
            except Exception as e: logger.debug("Adding credit_authorized column to customers: %s", e)

        if not column_exists('customers', 'is_active'):
            try:
                self.db.execute_write("ALTER TABLE customers ADD COLUMN is_active INTEGER DEFAULT 1")
            except Exception as e: logger.debug("Adding is_active column to customers: %s", e)

        # 3. Employees columns
        if not column_exists('employees', 'is_active'):
            try:
                self.db.execute_write("ALTER TABLE employees ADD COLUMN is_active INTEGER DEFAULT 1")
            except Exception as e: logger.debug("Adding is_active column to employees: %s", e)
        
        # 4. Emitters table columns for Multi-Emitter Engine
        emitter_columns = [
            ('current_annual_sum', 'DECIMAL(15,2) DEFAULT 0'),
            ('limite_anual', 'DECIMAL(15,2) DEFAULT 3500000'),
            ('is_primary', 'INTEGER DEFAULT 0'),
            ('priority', 'INTEGER DEFAULT 1'),
            ('codigo_postal', 'TEXT'),
            ('domicilio', 'TEXT'),
            ('csd_cer_path', 'TEXT'),
            ('csd_key_path', 'TEXT'),
            ('csd_password', 'TEXT'),
            ('updated_at', 'TEXT'),
        ]
        # nosec B608 - col_name/col_def from hardcoded emitter_columns list, not user input
        for col_name, col_def in emitter_columns:
            if not column_exists('emitters', col_name):
                try:
                    self.db.execute_write(f"ALTER TABLE emitters ADD COLUMN {col_name} {col_def}")
                except Exception as e: logger.debug("Adding %s column to emitters: %s", col_name, e)
        
        # 5. Backups table - ensure timestamp column exists
        if not column_exists('backups', 'timestamp'):
            try:
                self.db.execute_write("ALTER TABLE backups ADD COLUMN timestamp TEXT")
            except Exception as e: logger.debug("Adding timestamp column to backups: %s", e)

        # 4. Products SAT columns (for CFDI 4.0)
        if not column_exists('products', 'sat_clave_prod_serv'):
            try:
                self.db.execute_write("ALTER TABLE products ADD COLUMN sat_clave_prod_serv TEXT DEFAULT '01010101'")
            except Exception as e: logger.debug("Adding sat_clave_prod_serv column to products: %s", e)
        
        if not column_exists('products', 'sat_clave_unidad'):
            try:
                self.db.execute_write("ALTER TABLE products ADD COLUMN sat_clave_unidad TEXT DEFAULT 'H87'")
            except Exception as e: logger.debug("Adding sat_clave_unidad column to products: %s", e)

        # 5. Dual Series Fiscal System
        # Create secuencias table with terminal support (matches schema_postgresql.sql)
        self.db.execute_write("""
            CREATE TABLE IF NOT EXISTS secuencias (
                serie TEXT NOT NULL,
                terminal_id INTEGER DEFAULT 1,
                ultimo_numero INTEGER DEFAULT 0,
                descripcion TEXT,
                synced INTEGER DEFAULT 0,
                PRIMARY KEY (serie, terminal_id)
            )
        """)
        # Insert default sequences for terminal 1 if not exist
        try:
            # PostgreSQL: usar ON CONFLICT DO NOTHING
            # Verificar si la columna synced existe antes de usarla
            try:
                self.db.execute_write("INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion) VALUES ('A', 1, 0, 'Fiscal/Pública T1') ON CONFLICT (serie, terminal_id) DO NOTHING")
                self.db.execute_write("INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion) VALUES ('B', 1, 0, 'Operativa/Interna T1') ON CONFLICT (serie, terminal_id) DO NOTHING")
            except Exception as e:
                logger.debug("Secuencias INSERT failed: %s", e)
        except Exception as e:
            logger.debug("Secuencias setup (ignored): %s", e)
        
        # Add serie and folio_visible columns to sales
        if not column_exists('sales', 'serie'):
            try:
                self.db.execute_write("ALTER TABLE sales ADD COLUMN serie TEXT DEFAULT 'A'")
            except Exception as e:
                logger.debug("ALTER sales.serie: %s", e)
        
        if not column_exists('sales', 'folio_visible'):
            try:
                self.db.execute_write("ALTER TABLE sales ADD COLUMN folio_visible TEXT")
            except Exception as e:
                logger.debug("ALTER sales.folio_visible: %s", e)

        # 4. New Tables
        self.db.execute_write("""
            CREATE TABLE IF NOT EXISTS cash_movements (
                id BIGSERIAL PRIMARY KEY,
                turn_id INTEGER,
                type TEXT, -- 'in', 'out'
                amount DOUBLE PRECISION,
                reason TEXT,
                timestamp TEXT,
                user_id INTEGER,
                branch_id INTEGER,
                description TEXT
            )
        """)

        self.db.execute_write("""
            CREATE TABLE IF NOT EXISTS inventory_log (
                id BIGSERIAL PRIMARY KEY,
                product_id INTEGER,
                qty_change DOUBLE PRECISION,
                reason TEXT,
                timestamp TEXT,
                user_id INTEGER
            )
        """)

        self.db.execute_write("""
            CREATE TABLE IF NOT EXISTS kit_items (
                id BIGSERIAL PRIMARY KEY,
                parent_product_id INTEGER,
                child_product_id INTEGER,
                qty DOUBLE PRECISION
            )
        """)
        
        # 4. Ensure Admin & Branch
        try:
            # Fix admin role if it exists
            self.db.execute_write("UPDATE users SET role='admin' WHERE username='admin'")
            
            # Ensure at least one branch
            branches = self.db.execute_query("SELECT count(*) as c FROM branches")
            if branches and len(branches) > 0 and branches[0] and branches[0].get('c', 0) == 0:
                self.db.execute_write("INSERT INTO branches (name, address, is_default) VALUES ('Sucursal Principal', 'Dirección Local', 1)")
        except Exception as e:
            logger.debug("Setup inicial branches (ignored): %s", e)

    def _verify_and_fix_audit_table(self):
        """Verify audit_log table is correctly created and fix if corrupted"""
        # #region agent log
        if agent_log_enabled():
            import json
            import time
            debug_log_path = get_debug_log_path_str()
            try:
                log_entry = {
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A",
                    "location": "app/core.py:_verify_and_fix_audit_table:entry",
                    "message": "Verificando tabla audit_log",
                    "data": {"has_get_table_info": hasattr(self.db, 'get_table_info')},
                    "timestamp": int(time.time() * 1000)
                }
                with open(debug_log_path, "a") as f:
                    f.write(json.dumps(log_entry) + "\n")
                    f.flush()
            except Exception as e:
                logger.debug("Audit debug log write: %s", e)
        # #endregion
        try:
            # Check if table exists and has correct structure
            # PostgreSQL: usar get_table_info en lugar de PRAGMA
            if hasattr(self.db, 'get_table_info'):
                # #region agent log
                if agent_log_enabled():
                    try:
                        log_entry = {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "B",
                            "location": "app/core.py:_verify_and_fix_audit_table:before_get_table_info",
                            "message": "Antes de llamar get_table_info",
                            "data": {},
                            "timestamp": int(time.time() * 1000)
                        }
                        with open(debug_log_path, "a") as f:
                            f.write(json.dumps(log_entry) + "\n")
                            f.flush()
                    except Exception as log_e:
                        logger.debug("Audit table debug log: %s", log_e)
                # #endregion
                cols = self.db.get_table_info('audit_log')
                # #region agent log
                if agent_log_enabled():
                    try:
                        log_entry = {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "C",
                            "location": "app/core.py:_verify_and_fix_audit_table:after_get_table_info",
                            "message": "Después de llamar get_table_info",
                            "data": {"cols_count": len(cols) if cols else 0, "cols": cols[:5] if cols else []},
                            "timestamp": int(time.time() * 1000)
                        }
                        with open(debug_log_path, "a") as f:
                            f.write(json.dumps(log_entry) + "\n")
                            f.flush()
                    except Exception as log_e:
                        logger.debug("Audit table debug log: %s", log_e)
                # #endregion
                col_names = [c['name'] for c in cols] if cols else []
            else:
                cols = []
                col_names = []
            
            # Verify required columns exist
            required_cols = ['username', 'success', 'timestamp', 'action', 'entity_type', 'entity_id', 'entity_name']
            missing_cols = [col for col in required_cols if col not in col_names]
            
            # #region agent log
            if agent_log_enabled():
                try:
                    log_entry = {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "D",
                        "location": "app/core.py:_verify_and_fix_audit_table:verification",
                        "message": "Resultado de verificación",
                        "data": {"cols_count": len(cols), "col_names": col_names, "missing_cols": missing_cols, "required_cols": required_cols},
                        "timestamp": int(time.time() * 1000)
                    }
                    with open(debug_log_path, "a") as f:
                        f.write(json.dumps(log_entry) + "\n")
                        f.flush()
                except Exception as log_e:
                    logger.debug("Audit table debug log: %s", log_e)
            # #endregion
            
            if len(cols) < 13 or missing_cols:  # Ajustado a 13 columnas según schema PostgreSQL
                logger.warning("audit_log table is corrupt or incomplete (has %d cols, missing: %s). Recreating...", len(cols), missing_cols)
                self._recreate_audit_table()
                logger.info("✅ audit_log table recreated successfully")
            else:
                logger.debug("audit_log table verified - %d columns present", len(cols))
        except Exception as e:
            # #region agent log
            if agent_log_enabled():
                try:
                    log_entry = {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "E",
                        "location": "app/core.py:_verify_and_fix_audit_table:exception",
                        "message": "Excepción durante verificación",
                        "data": {"error": str(e), "error_type": type(e).__name__},
                        "timestamp": int(time.time() * 1000)
                    }
                    with open(debug_log_path, "a") as f:
                        f.write(json.dumps(log_entry) + "\n")
                        f.flush()
                except Exception as log_e:
                    logger.debug("Audit table debug log: %s", log_e)
            # #endregion
            logger.error("Failed to verify audit table: %s", e)
            try:
                self._recreate_audit_table()
                logger.info("✅ audit_log table created after verification failure")
            except Exception as e2:
                logger.error("Failed to recreate audit table: %s", e2)

    def _recreate_audit_table(self):
        """Recreate audit_log table with correct schema matching PostgreSQL schema"""
        # #region agent log
        if agent_log_enabled():
            import json
            import time
            debug_log_path = get_debug_log_path_str()
            try:
                log_entry = {
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "F",
                    "location": "app/core.py:_recreate_audit_table:entry",
                    "message": "Iniciando recreación de tabla audit_log",
                    "data": {},
                    "timestamp": int(time.time() * 1000)
                }
                with open(debug_log_path, "a") as f:
                    f.write(json.dumps(log_entry) + "\n")
                    f.flush()
            except Exception as log_e:
                logger.debug("Audit table debug log: %s", log_e)
        # #endregion
        try:
            self.db.execute_write("DROP TABLE IF EXISTS audit_log CASCADE")
            # Usar schema que coincide con schema_postgresql.sql
            self.db.execute_write("""
                CREATE TABLE audit_log (
                    id BIGSERIAL PRIMARY KEY,
                    user_id INTEGER,
                    username TEXT,
                    action TEXT NOT NULL,
                    table_name TEXT,
                    entity_type TEXT,
                    entity_id INTEGER,
                    record_id INTEGER,
                    entity_name TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    ip_address TEXT,
                    success INTEGER DEFAULT 1,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT NOW(),
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)
            # #region agent log
            if agent_log_enabled():
                try:
                    log_entry = {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "G",
                        "location": "app/core.py:_recreate_audit_table:after_create",
                        "message": "Tabla audit_log creada, creando índices",
                        "data": {},
                        "timestamp": int(time.time() * 1000)
                    }
                    with open(debug_log_path, "a") as f:
                        f.write(json.dumps(log_entry) + "\n")
                        f.flush()
                except Exception as log_e:
                    logger.debug("Audit table debug log: %s", log_e)
            # #endregion
            self.db.execute_write("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)")
            self.db.execute_write("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)")
            self.db.execute_write("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)")
            self.db.execute_write("CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, record_id)")
            # #region agent log
            if agent_log_enabled():
                try:
                    log_entry = {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "H",
                        "location": "app/core.py:_recreate_audit_table:success",
                        "message": "Tabla audit_log recreada exitosamente",
                        "data": {},
                        "timestamp": int(time.time() * 1000)
                    }
                    with open(debug_log_path, "a") as f:
                        f.write(json.dumps(log_entry) + "\n")
                        f.flush()
                except Exception as log_e:
                    logger.debug("Audit table debug log: %s", log_e)
            # #endregion
        except Exception as e:
            # #region agent log
            if agent_log_enabled():
                try:
                    log_entry = {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "I",
                        "location": "app/core.py:_recreate_audit_table:error",
                        "message": "Error al recrear tabla audit_log",
                        "data": {"error": str(e), "error_type": type(e).__name__},
                        "timestamp": int(time.time() * 1000)
                    }
                    with open(debug_log_path, "a") as f:
                        f.write(json.dumps(log_entry) + "\n")
                        f.flush()
                except Exception as log_e:
                    logger.debug("Audit table debug log: %s", log_e)
            # #endregion
            logger.error("Failed to recreate audit_log table: %s", e)
            raise

    def _ensure_column_exists(self, table_name, column_name, column_type="INTEGER", default_value=None):
        """
        Helper function to ensure a column exists in a table before INSERT/UPDATE.
        Returns True if column exists (or was successfully added), False otherwise.
        
        CRITICAL FIX: Usa caché de esquema para evitar llamadas repetidas a get_table_info().
        """
        import json, time
        
        # Inicializar caché si no existe
        if not hasattr(self, '_schema_cache'):
            self._schema_cache = {}
        if not hasattr(self, '_schema_cache_lock'):
            import threading
            self._schema_cache_lock = threading.Lock()

        # FIX 2026-02-01: Thread-safe cache read
        cache_key = f"{table_name}"
        with self._schema_cache_lock:
            if cache_key in self._schema_cache:
                cols = self._schema_cache[cache_key]
                if column_name in cols:
                    return True
                # Si la columna no está en caché, verificar si fue agregada recientemente
                # (no recargar toda la tabla, solo verificar si existe)
        
        try:
            # Cargar esquema completo de la tabla (solo si no está en caché)
            table_info = self.db.get_table_info(table_name)
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"ENSURE_COLUMN_CHECK","location":"core.py:_ensure_column_exists","message":"Checking column existence","data":{"table_name":table_name,"column_name":column_name,"table_info_count":len(table_info) if table_info else 0},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logger.debug("Writing debug log for column existence check: %s", e)
            # #endregion
            
            # Handle different return formats from get_table_info
            if not table_info:
                logger.warning("Could not get table info for %s", table_name)
                # #region agent log
                if agent_log_enabled():
                    try:
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"ENSURE_COLUMN_NO_INFO","location":"core.py:_ensure_column_exists","message":"No table info returned","data":{"table_name":table_name},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e: logger.debug("Writing debug log for no table info: %s", e)
                # #endregion
                return False
            
            cols = []
            for col in table_info:
                if isinstance(col, dict):
                    cols.append(col.get('name', ''))
                elif isinstance(col, (list, tuple)) and len(col) > 1:
                    cols.append(col[1])
                elif isinstance(col, str):
                    cols.append(col)
            
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"ENSURE_COLUMN_COLS","location":"core.py:_ensure_column_exists","message":"Column list extracted","data":{"table_name":table_name,"column_name":column_name,"cols":cols[:10],"column_exists":column_name in cols},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logger.debug("Writing debug log for column list extraction: %s", e)
            # #endregion
            
            # FIX 2026-02-01: Thread-safe cache write
            with self._schema_cache_lock:
                self._schema_cache[cache_key] = cols

            if column_name in cols:
                return True
            
            # Column doesn't exist, try to add it
            try:
                if default_value is not None:
                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} DEFAULT {default_value}"
                else:
                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                
                # #region agent log
                if agent_log_enabled():
                    try:
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"ENSURE_COLUMN_ADD","location":"core.py:_ensure_column_exists","message":"Attempting to add column","data":{"table_name":table_name,"column_name":column_name,"alter_sql":alter_sql},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e: logger.debug("Writing debug log for column addition attempt: %s", e)
                # #endregion
                
                self.db.execute_write(alter_sql)
                
                # Try to add foreign key if it's user_id
                if column_name == "user_id":
                    try:
                        fk_sql = f"ALTER TABLE {table_name} ADD CONSTRAINT fk_{table_name}_user FOREIGN KEY ({column_name}) REFERENCES users(id)"
                        self.db.execute_write(fk_sql)
                    except Exception as fk_e:
                        logger.debug("FK constraint skipped for %s.%s: %s", table_name, column_name, fk_e)
                        # FK might already exist or users table might not exist
                
                logger.info("Added missing column: %s.%s (%s)", table_name, column_name, column_type)

                # FIX 2026-02-01: Thread-safe cache update to prevent race condition
                with self._schema_cache_lock:
                    if cache_key not in self._schema_cache:
                        self._schema_cache[cache_key] = []
                    self._schema_cache[cache_key].append(column_name)
                
                # #region agent log
                if agent_log_enabled():
                    try:
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"ENSURE_COLUMN_SUCCESS","location":"core.py:_ensure_column_exists","message":"Column added successfully","data":{"table_name":table_name,"column_name":column_name},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e: logger.debug("Writing debug log for column addition success: %s", e)
                # #endregion
                return True
            except Exception as e:
                error_str = str(e).lower()
                if "already exists" in error_str or "duplicate" in error_str:
                    # Column already exists, return True
                    logger.debug("Column %s.%s already exists", table_name, column_name)
                    return True
                else:
                    logger.warning("Could not add %s.%s: %s", table_name, column_name, e)
                    # #region agent log
                    if agent_log_enabled():
                        try:
                            with open(get_debug_log_path_str(), "a") as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"ENSURE_COLUMN_ERROR","location":"core.py:_ensure_column_exists","message":"Error adding column","data":{"table_name":table_name,"column_name":column_name,"error":str(e)},"timestamp":int(time.time()*1000)})+"\n")
                        except Exception as e: logger.debug("Writing debug log for column addition error: %s", e)
                    # #endregion
                    return False
        except Exception as e:
            logger.debug("Could not check/add column %s.%s: %s", table_name, column_name, e)
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"ENSURE_COLUMN_EXCEPTION","location":"core.py:_ensure_column_exists","message":"Exception in _ensure_column_exists","data":{"table_name":table_name,"column_name":column_name,"error":str(e)},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logger.debug("Writing debug log for ensure column exception: %s", e)
            # #endregion
            return False
    
    def register_cash_movement(self, turn_id, type_, amount, reason, branch_id=None, user_id=None):
        """Registra entrada/salida de efectivo."""
        import logging
        import json, time, traceback
        logger = logging.getLogger(__name__)
        
        logger.info("[CASH_MOVEMENT] Registrando: turn_id=%s, type=%s, amount=%s, user_id=%s", turn_id, type_, amount, user_id)
        
        # #region agent log
        if agent_log_enabled():
            try:
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"REGISTER_CASH_MOVEMENT_ENTRY","location":"core.py:register_cash_movement","message":"Function entry","data":{"turn_id":turn_id,"type":type_,"amount":amount,"reason":reason,"branch_id":branch_id,"user_id":user_id},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e: logger.debug("Writing debug log for cash movement entry: %s", e)
        # #endregion
        
        # Verificar y agregar columna user_id si no existe (migración automática en tiempo de ejecución)
        try:
            from app.utils.schema_migrations import check_and_fix_columns
            check_and_fix_columns(self.db)
        except Exception as e:
            logger.debug("Schema check skipped: %s", e)
        
        # CRITICAL FIX: Verificar explícitamente si la columna user_id existe en cash_movements
        has_user_id_column = self._ensure_column_exists("cash_movements", "user_id", "INTEGER")
        
        # #region agent log
        if agent_log_enabled():
            try:
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CHECK_USER_ID_COLUMN","location":"core.py:register_cash_movement","message":"Checking if user_id column exists","data":{"has_user_id_column":has_user_id_column},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e: logger.debug("Writing debug log for user_id column check: %s", e)
        # #endregion
        
        # Si turn_id es None, intentar obtener el actual del usuario
        if not turn_id and user_id:
             # #region agent log
             if agent_log_enabled():
                 try:
                     with open(get_debug_log_path_str(), "a") as f:
                         f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"GET_CURRENT_TURN","location":"core.py:register_cash_movement","message":"Calling get_current_turn","data":{"branch_id":branch_id,"user_id":user_id},"timestamp":int(time.time()*1000)})+"\n")
                 except Exception as e: logger.debug("Writing debug log for get_current_turn call: %s", e)
             # #endregion
             
             turn = self.get_current_turn(branch_id, user_id)
             logger.info("[CASH_MOVEMENT] get_current_turn result: %s", turn)
             
             # #region agent log
             if agent_log_enabled():
                 try:
                     with open(get_debug_log_path_str(), "a") as f:
                         f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"GET_CURRENT_TURN_RESULT","location":"core.py:register_cash_movement","message":"get_current_turn result","data":{"turn":turn,"turn_id":turn.get('id') if turn else None},"timestamp":int(time.time()*1000)})+"\n")
                 except Exception as e: logger.debug("Writing debug log for get_current_turn result: %s", e)
             # #endregion
             
             if turn:
                 turn_id = turn['id']
        
        if not turn_id:
            logger.error("[CASH_MOVEMENT] No hay turno abierto - user_id=%s, branch_id=%s", user_id, branch_id)
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"NO_TURN_ERROR","location":"core.py:register_cash_movement","message":"No turn found - raising ValueError","data":{"user_id":user_id,"branch_id":branch_id},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logger.debug("Writing debug log for no turn error: %s", e)
            # #endregion
            raise ValueError("No hay turno abierto para registrar movimiento")

        # #region agent log
        if agent_log_enabled():
            try:
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"BEFORE_SQL_INSERT","location":"core.py:register_cash_movement","message":"Before SQL INSERT","data":{"turn_id":turn_id,"type":type_,"amount":amount,"reason":reason,"branch_id":branch_id,"user_id":user_id,"timestamp":datetime.now().isoformat()},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e: logger.debug("Writing debug log before SQL insert: %s", e)
        # #endregion

        try:
            # PostgreSQL usa %s en lugar de ?
            # CRITICAL FIX: Construir SQL dinámicamente basado en si la columna user_id existe
            if has_user_id_column:
                # CRÍTICO: Incluir synced=0 para sincronización
                # Auditoría 2026-01-30: Agregado campo synced
                sql = "INSERT INTO cash_movements (turn_id, type, amount, reason, timestamp, user_id, branch_id, description, synced) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0)"
                params = (turn_id, type_, amount, reason, datetime.now().isoformat(), user_id, branch_id, reason)
            else:
                # Si no existe user_id, omitirla del INSERT
                # CRÍTICO: Incluir synced=0 para sincronización
                sql = "INSERT INTO cash_movements (turn_id, type, amount, reason, timestamp, branch_id, description, synced) VALUES (%s, %s, %s, %s, %s, %s, %s, 0)"
                params = (turn_id, type_, amount, reason, datetime.now().isoformat(), branch_id, reason)
            
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"SQL_EXECUTE","location":"core.py:register_cash_movement","message":"Executing SQL INSERT","data":{"sql":sql,"params":params,"params_count":len(params),"has_user_id_column":has_user_id_column},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logger.debug("Writing debug log for SQL execute: %s", e)
            # #endregion
            
            self.db.execute_write(sql, params)
            logger.info("[CASH_MOVEMENT] Movimiento registrado: turn_id=%s, %s=$%s", turn_id, type_, amount)
            
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"SQL_SUCCESS","location":"core.py:register_cash_movement","message":"SQL INSERT successful","data":{},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logger.debug("Writing debug log for SQL success: %s", e)
            # #endregion
        except Exception as e:
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"SQL_ERROR","location":"core.py:register_cash_movement","message":"SQL INSERT error","data":{"error":str(e),"error_type":type(e).__name__,"traceback":traceback.format_exc()},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logger.debug("Writing debug log for SQL error: %s", e)
            # #endregion
            raise

    def add_stock(self, product_id, qty, reason="ajuste manual"):
        # Transactional integrity
        try:
            res = self.engine.add_stock(product_id, qty, reason)
            # Log movement
            # CRITICAL FIX: Verificar si user_id existe antes de INSERT
            has_user_id = self._ensure_column_exists("inventory_log", "user_id", "INTEGER")
            
            if has_user_id:
                sql = "INSERT INTO inventory_log (product_id, qty_change, reason, timestamp, user_id) VALUES (%s, %s, %s, %s, %s)"
                self.db.execute_write(sql, (product_id, qty, reason, datetime.now().isoformat(), STATE.user_id))
            else:
                # Fallback: INSERT sin user_id
                sql = "INSERT INTO inventory_log (product_id, qty_change, reason, timestamp) VALUES (%s, %s, %s, %s)"
                self.db.execute_write(sql, (product_id, qty, reason, datetime.now().isoformat()))
            return res
        except Exception as e:
            logger.error("Error adding stock: %s", e)
            raise e

    def _fix_products_sequence(self):
        """Fix PostgreSQL sequence when out of sync with actual data."""
        try:
            self.db.execute_write(
                "SELECT setval('products_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM products), false)"
            )
            logger.info("✅ Secuencia products_id_seq corregida automáticamente")
            return True
        except Exception as e:
            logger.error("Error corrigiendo secuencia: %s", e)
            return False

    def _fix_customers_sequence(self):
        """Fix PostgreSQL sequence for customers when out of sync with actual data."""
        try:
            self.db.execute_write(
                "SELECT setval('customers_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM customers), false)"
            )
            logger.info("✅ Secuencia customers_id_seq corregida automáticamente")
            return True
        except Exception as e:
            logger.error("Error corrigiendo secuencia customers: %s", e)
            return False

    def _fix_sales_sequence(self):
        """Fix PostgreSQL sequence for sales when out of sync with actual data."""
        try:
            self.db.execute_write(
                "SELECT setval('sales_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM sales), false)"
            )
            logger.info("✅ Secuencia sales_id_seq corregida automáticamente")
            return True
        except Exception as e:
            logger.error("Error corrigiendo secuencia sales: %s", e)
            return False

    def create_product(self, product_data):
        """Crea un nuevo producto (delegado a engine)."""
        # Input Sanitization
        if not product_data.get("price") and product_data.get("price") != 0:
             raise ValueError("El precio es obligatorio")
        if not product_data.get("sku"):
             raise ValueError("El SKU es obligatorio")

        # Strip whitespace from SKU
        product_data["sku"] = product_data["sku"].strip()

        # 🔒 LOCK 3: Race Condition Handler (The 3rd Lock)
        max_retries = 3
        for intento in range(max_retries):
            try:
                return self.engine.create_product(product_data)
            except Exception as e:
                error_msg = str(e)

                # FIX 2026-01-31: Auto-fix sequence on primary key violation
                if "products_pkey" in error_msg or ("llave duplicada" in error_msg and "products" in error_msg):
                    logger.warning("Secuencia de productos desincronizada, corrigiendo...")
                    if self._fix_products_sequence():
                        continue  # Reintentar después de corregir secuencia

                # Si es error de SKU duplicado y tenemos intentos restantes
                if "UNIQUE constraint failed" in error_msg and "sku" in error_msg.lower():
                    if intento < max_retries - 1:
                        # Intentar generar nuevo SKU automáticamente
                        logger.warning("SKU %s duplicado, generando nuevo...", product_data['sku'])

                        # Detectar prefijo del SKU actual
                        sku_actual = product_data["sku"]
                        if len(sku_actual) >= 2 and sku_actual[:2].isdigit():
                            prefijo = sku_actual[:2]
                            try:
                                from app.utils.sku_generator import generar_sku_siguiente
                                nuevo_sku = generar_sku_siguiente(self.db, prefijo)
                                product_data["sku"] = nuevo_sku
                                logger.info("SKU actualizado automaticamente a: %s", nuevo_sku)
                                continue  # Reintentar con nuevo SKU
                            except Exception as gen_error:
                                logger.error("Error al generar nuevo SKU: %s", gen_error)

                    # Si llegamos aquí, ya no hay más reintentos
                    raise ValueError(f"El SKU {product_data['sku']} ya existe y no se pudo generar uno alternativo.")
                else:
                    # Otro tipo de error, propagar
                    raise e

        # Si agotamos todos los intentos
        raise RuntimeError(f"No se pudo crear el producto después de {max_retries} intentos")

    # ========== IDENTITY V2: SKU GENERATOR METHODS ==========
    
    def generate_next_sku(self, prefix='20'):
        """
        Genera el siguiente SKU único para un prefijo dado.
        
        🪄 EL GENERADOR MÁGICO - Magic Wand Feature
        
        Args:
            prefix: Prefijo de 2 dígitos ('20', '21', '22', '23', '24', '29')
            
        Returns:
            String de 13 dígitos con checksum EAN-13 válido
            
        Raises:
            ValueError: Si el prefijo no es válido
        """
        from app.utils.sku_generator import generar_sku_siguiente
        return generar_sku_siguiente(self.db, prefix)
    
    def validate_ean13(self, code):
        """
        Valida un código EAN-13 (formato y checksum).
        
        Args:
            code: String del código a validar
            
        Returns:
            True si válido, False en caso contrario
        """
        from app.utils.sku_generator import validar_ean13
        return validar_ean13(code)
    
    def get_available_prefixes(self):
        """
        Retorna lista de prefijos disponibles para generación de SKU.
        
        Returns:
            Lista de dicts: [{'codigo': '20', 'descripcion': 'Abarrotes / General'}, ...]
        """
        from app.utils.sku_generator import get_prefijos_disponibles
        return get_prefijos_disponibles()
    
    def is_internal_sku(self, sku):
        """
        Determina si un SKU es interno (generado por el sistema).
        
        Args:
            sku: Código a verificar
            
        Returns:
            True si es SKU interno, False si es externo
        """
        from app.utils.sku_generator import es_sku_interno
        return es_sku_interno(sku)
    
    def generate_bulk_skus(self, prefix='20', quantity=1):
        """
        Genera múltiples SKUs de manera eficiente en una sola transacción.
        
        🚀 BATCH GENERATION - High Performance Mode
        
        Args:
            prefix: Prefijo de 2 dígitos
            quantity: Número de SKUs a generar (máx 100)
            
        Returns:
            Lista de SKUs generados
            
        Raises:
            ValueError: Si quantity > 100 o prefix inválido
        """
        from app.config.constants import MAX_BULK_SKU_GENERATION
        
        if quantity > MAX_BULK_SKU_GENERATION:
            raise ValueError(f"Máximo {MAX_BULK_SKU_GENERATION} SKUs por lote")
        
        skus = []
        for i in range(quantity):
            sku = self.generate_next_sku(prefix)
            skus.append(sku)
            logger.debug("Bulk generation %d/%d: %s", i+1, quantity, sku)
        
        logger.info("Generated %d SKUs with prefix %s", quantity, prefix)
        return skus
    
    def get_sku_statistics(self, prefix=None):
        """
        Obtiene estadísticas de uso de SKU por prefijo.
        
        📊 SKU ANALYTICS
        
        Args:
            prefix: Prefijo específico o None para todos
            
        Returns:
            Dict con estadísticas de uso
        """
        if prefix:
            query = """
                SELECT 
                    SUBSTRING(sku, 1, 2) as prefix,
                    COUNT(*) as total,
                    MIN(sku) as first_sku,
                    MAX(sku) as last_sku
                FROM products
                WHERE sku LIKE %s AND CHAR_LENGTH(sku) = 13
                GROUP BY SUBSTRING(sku, 1, 2)
            """
            results = self.db.execute_query(query, (f"{prefix}%",))
        else:
            query = """
                SELECT 
                    SUBSTRING(sku, 1, 2) as prefix,
                    COUNT(*) as total,
                    MIN(sku) as first_sku,
                    MAX(sku) as last_sku
                FROM products
                WHERE CHAR_LENGTH(sku) = 13 AND SUBSTRING(sku, 1, 2) IN ('20', '21', '22', '23', '24', '29')
                GROUP BY SUBSTRING(sku, 1, 2)
            """
            results = self.db.execute_query(query)
        
        return [dict(row) for row in results]
    
    def get_next_available_sku_preview(self, prefix='20'):
        """
        Muestra el próximo SKU que se generaría SIN crearlo.
        
        Args:
            prefix: Prefijo a consultar
            
        Returns:
            String del próximo SKU disponible
        """
        from app.utils.sku_generator import generar_sku_siguiente

        # Nota: Esta llamada SÍ consulta la DB pero no inserta nada
        return generar_sku_siguiente(self.db, prefix)

    def update_product(self, product_id, product_data):
        """Actualiza un producto existente (delegado a engine)."""
        return self.engine.update_product(product_id, product_data)

    def delete_product(self, product_id):
        """Elimina (soft delete) un producto."""
        return self.engine.delete_product(product_id)

    def register_credit_payment(self, customer_id, amount, notes, user_id):
        """Registra un abono a cuenta de crédito."""
        # CRITICAL FIX: Todas las operaciones (UPDATE crédito + INSERT historial) se ejecutan en una sola transacción.
        # Si falla cualquier operación, TODO se revierte (rollback).
        try:
            # 0. Obtener saldo actual antes del abono
            customer_info = self.db.execute_query(
                "SELECT credit_balance FROM customers WHERE id = %s",
                (customer_id,)
            )
            balance_before = float(customer_info[0].get('credit_balance') or 0.0) if customer_info and len(customer_info) > 0 and customer_info[0] else 0.0
            balance_after = max(0, balance_before - amount)
            
            # CRITICAL FIX: Verificar si user_id y movement_type existen antes de construir la transacción
            has_user_id = self._ensure_column_exists("credit_history", "user_id", "INTEGER")
            has_movement_type = self._ensure_column_exists("credit_history", "movement_type", "TEXT")
            
            # ============================================================
            # CRITICAL FIX: Construir TODAS las operaciones en una lista
            # para ejecutarlas en una sola transacción atómica
            # ============================================================
            ops = []
            
            # 1. Actualizar saldo del cliente
            ops.append(("UPDATE customers SET credit_balance = %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (balance_after, customer_id)))
            
            # 2. Registrar en historial de crédito (para estados de cuenta)
            if has_user_id:
                if has_movement_type:
                    ops.append(("""
                        INSERT INTO credit_history (customer_id, transaction_type, movement_type, amount, balance_before, balance_after, timestamp, notes, user_id, synced)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
                    """, (customer_id, 'payment', 'PAYMENT', amount, balance_before, balance_after, datetime.now().isoformat(), notes or 'Abono a crédito', user_id)))
                else:
                    ops.append(("""
                        INSERT INTO credit_history (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes, user_id, synced)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0)
                    """, (customer_id, 'payment', amount, balance_before, balance_after, datetime.now().isoformat(), notes or 'Abono a crédito', user_id)))
            else:
                # Fallback: INSERT sin user_id
                if has_movement_type:
                    ops.append(("""
                        INSERT INTO credit_history (customer_id, transaction_type, movement_type, amount, balance_before, balance_after, timestamp, notes, synced)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0)
                    """, (customer_id, 'payment', 'PAYMENT', amount, balance_before, balance_after, datetime.now().isoformat(), notes or 'Abono a crédito')))
                else:
                    ops.append(("""
                        INSERT INTO credit_history (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes, synced)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 0)
                    """, (customer_id, 'payment', amount, balance_before, balance_after, datetime.now().isoformat(), notes or 'Abono a crédito')))
            
            # Ejecutar TODO en una sola transacción atómica
            result = self.db.execute_transaction(ops, timeout=5)
            if not result.get('success'):
                raise RuntimeError("Transaction failed - credit payment not registered")
            
            # 3. Registrar entrada de dinero en el turno actual (post-transacción, con retry si falla)
            turn = self.get_current_turn(STATE.branch_id, user_id)
            if turn:
                try:
                    self.register_cash_movement(turn['id'], 'in', amount, f"Abono Crédito Cliente #{customer_id} - {notes or ''}", STATE.branch_id, user_id)
                except Exception as e:
                    logger.warning("Error registering cash movement for credit payment (non-critical): %s", e)
                    # No lanzar excepción, el pago ya está registrado
            
            return True
        except Exception as e:
            logger.error("Error registering credit payment: %s", e)
            raise e

    def cancel_sale(self, sale_id, items, reason, restore_inventory, refund_amount, user_id, branch_id):
        """
        Cancela una venta (parcial o total) de forma transaccional.
        items: list of dict {product_id, qty, price}
        
        CRITICAL FIX: Todas las operaciones de rollback se ejecutan en una sola transacción.
        Si falla cualquier operación, TODO se revierte (rollback).
        """
        # #region agent log
        if agent_log_enabled():
            import json, time
            with open(get_debug_log_path_str(), "a") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"core.py:cancel_sale","message":"Function entry","data":{"sale_id":sale_id,"items_count":len(items) if items else 0,"items":items[:3] if items else [],"restore_inventory":restore_inventory,"refund_amount":refund_amount,"user_id":user_id,"branch_id":branch_id},"timestamp":int(time.time()*1000)})+"\n")
        # #endregion
        try:
            # 1. Obtener información de la venta
            sale = self.get_sale(sale_id)
            total_orig = float(sale["total"])
            
            is_total = (abs(refund_amount - total_orig) < 0.01)
            # #region agent log
            if agent_log_enabled():
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"core.py:cancel_sale","message":"Sale info retrieved","data":{"sale_id":sale_id,"total_orig":total_orig,"refund_amount":refund_amount,"is_total":is_total,"payment_method":sale.get("payment_method"),"customer_id":sale.get("customer_id")},"timestamp":int(time.time()*1000)})+"\n")
            # #endregion
            
            # ============================================================
            # CRITICAL FIX: Construir TODAS las operaciones de rollback
            # en una lista para ejecutarlas en una sola transacción
            # ============================================================
            ops = []
            
            # A. Marcar venta como cancelada
            if is_total:
                ops.append(("UPDATE sales SET status='cancelled', notes=%s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id=%s",
                           (f"Cancelado: {reason}", sale_id)))
            else:
                # Append note
                old_notes = sale.get("notes") or ""
                new_notes = f"{old_notes} | Cancelación Parcial: -${refund_amount:.2f} ({reason})"
                ops.append(("UPDATE sales SET notes=%s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id=%s", (new_notes, sale_id)))
            
            # B. Restaurar Inventario (todas las operaciones)
            # CRITICAL FIX: Validar cantidad a cancelar y manejar productos eliminados
            if restore_inventory and items:
                # #region agent log
                if agent_log_enabled():
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H5","location":"core.py:cancel_sale","message":"Adding inventory restore operations","data":{"items_count":len(items),"items":items},"timestamp":int(time.time()*1000)})+"\n")
                # #endregion
                
                # Validar que las cantidades a cancelar no excedan las originales (Parte A: omitir ítems sin product_id)
                for item in items:
                    product_id = item.get('product_id')
                    if product_id is None:
                        continue
                    qty_to_restore = float(item.get('qty', 0))
                    
                    # Verificar cantidad original en sale_items
                    original_item_rows = self.db.execute_query(
                        "SELECT qty FROM sale_items WHERE sale_id = %s AND product_id = %s",
                        (sale_id, product_id)
                    )
                    
                    # FIX 2026-02-01: Validar original_item_rows con len() antes de acceder a [0]
                    if original_item_rows and len(original_item_rows) > 0:
                        original_qty = float(original_item_rows[0].get('qty', 0))
                        if qty_to_restore > original_qty:
                            raise ValueError(
                                f"Cantidad a cancelar ({qty_to_restore}) excede cantidad original ({original_qty}) "
                                f"para producto ID {product_id} en venta #{sale_id}"
                            )
                    
                    # CRITICAL FIX: Verificar que el producto existe antes de intentar restaurar stock
                    # Si el producto fue eliminado, solo registrar en notas pero no restaurar stock
                    product_exists = self.db.execute_query(
                        "SELECT 1 FROM products WHERE id = %s",
                        (product_id,)
                    )
                    
                    if product_exists:
                        # Producto existe, restaurar stock normalmente
                        ops.append(("UPDATE products SET stock = stock + %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                                   (qty_to_restore, product_id)))

                        # FIX 2026-02-01: Registrar movimiento de inventario para delta sync
                        ops.append((
                            """INSERT INTO inventory_movements
                                (product_id, movement_type, type, quantity, reason, reference_type, reference_id, user_id, branch_id, timestamp, synced)
                                VALUES (%s, 'IN', 'cancel', %s, %s, 'sale_cancel', %s, %s, %s, NOW(), 0)""",
                            (product_id, qty_to_restore, f"Cancelación venta #{sale_id}: {reason}", sale_id, user_id, branch_id)
                        ))
                    else:
                        # CRITICAL FIX: Producto fue eliminado, registrar en notas pero no restaurar stock
                        logger.warning(
                            f"Producto ID {product_id} fue eliminado. "
                            f"No se puede restaurar stock para cancelación de venta #{sale_id}. "
                            f"Se registrará en notas de la venta."
                        )
                        # Acumular productos eliminados para agregar una sola nota al final
                        if not hasattr(self, '_deleted_products_for_cancel'):
                            self._deleted_products_for_cancel = []
                        self._deleted_products_for_cancel.append(product_id)
                
                # Agregar nota sobre productos eliminados si hay alguno
                if hasattr(self, '_deleted_products_for_cancel') and self._deleted_products_for_cancel:
                    deleted_ids_str = ", ".join(map(str, self._deleted_products_for_cancel))
                    deleted_note = f" | [ADVERTENCIA] Productos eliminados (IDs: {deleted_ids_str}), stock no restaurado"
                    
                    # Buscar si ya hay un UPDATE de sales en ops
                    sales_update_found = False
                    for idx, (sql, params) in enumerate(ops):
                        if sql.startswith("UPDATE sales SET") and "notes" in sql:
                            # Actualizar la nota existente
                            # Encontrar el índice del parámetro de notes
                            sql_lower = sql.lower()
                            note_param_pos = sql_lower.find("notes")
                            if note_param_pos >= 0:
                                # Contar %s antes de notes
                                before_notes = sql[:note_param_pos]
                                param_index = before_notes.count("%s")
                                if param_index < len(params):
                                    existing_note = str(params[param_index])
                                    new_note = existing_note + deleted_note
                                    new_params = list(params)
                                    new_params[param_index] = new_note
                                    ops[idx] = (sql, tuple(new_params))
                                    sales_update_found = True
                                    break
                    
                    if not sales_update_found:
                        # No hay UPDATE de sales con notes, agregar uno
                        old_notes = sale.get("notes") or ""
                        new_note = old_notes + deleted_note
                        # Insertar después del UPDATE de status (si existe) o al principio
                        insert_pos = 0
                        for idx, (sql, _) in enumerate(ops):
                            if sql.startswith("UPDATE sales SET"):
                                insert_pos = idx + 1
                                break
                        ops.insert(insert_pos, ("UPDATE sales SET notes = %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (new_note, sale_id)))
                    
                    # Limpiar la lista temporal
                    delattr(self, '_deleted_products_for_cancel')
            else:
                pass  # No se restaura inventario

            # C. Restaurar Crédito (si aplica)
            # CRITICAL FIX: Calcular balance dentro de la transacción usando subqueries
            # Esto previene condiciones de carrera y garantiza consistencia
            if sale['payment_method'] == 'credit' and sale.get('customer_id'):
                # Revertir crédito
                ops.append(("UPDATE customers SET credit_balance = credit_balance - %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                           (refund_amount, sale['customer_id'])))
                
                # Registrar reversión en credit_history
                # CRITICAL FIX: Calcular balance_before y balance_after usando subqueries dentro de la transacción
                # balance_before = balance ANTES del UPDATE (balance actual + refund_amount)
                # balance_after = balance DESPUÉS del UPDATE (balance actual)
                # Usamos subqueries para garantizar que se calculen dentro de la misma transacción
                has_user_id = self._ensure_column_exists("credit_history", "user_id", "INTEGER")
                has_movement_type = self._ensure_column_exists("credit_history", "movement_type", "TEXT")
                history_notes = f"Devolución Venta #{sale_id}: {reason}"
                
                if has_user_id:
                    if has_movement_type:
                        history_sql = """INSERT INTO credit_history
                            (customer_id, transaction_type, movement_type, amount, balance_before, balance_after, timestamp, notes, user_id, synced)
                            VALUES (
                                %s, 'REFUND', 'REFUND', %s,
                                (SELECT credit_balance FROM customers WHERE id = %s) + %s,  -- balance_before (antes de revertir)
                                (SELECT credit_balance FROM customers WHERE id = %s),  -- balance_after (después de revertir)
                                NOW(), %s, %s, 0
                            )"""
                        ops.append((history_sql, (
                            sale['customer_id'], -refund_amount,
                            sale['customer_id'], refund_amount,  # Para balance_before
                            sale['customer_id'],  # Para balance_after
                            history_notes, user_id
                        )))
                    else:
                        history_sql = """INSERT INTO credit_history
                            (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes, user_id, synced)
                            VALUES (
                                %s, 'REFUND', %s,
                                (SELECT credit_balance FROM customers WHERE id = %s) + %s,  -- balance_before (antes de revertir)
                                (SELECT credit_balance FROM customers WHERE id = %s),  -- balance_after (después de revertir)
                                NOW(), %s, %s, 0
                            )"""
                        ops.append((history_sql, (
                            sale['customer_id'], -refund_amount,
                            sale['customer_id'], refund_amount,  # Para balance_before
                            sale['customer_id'],  # Para balance_after
                            history_notes, user_id
                        )))
                else:
                    if has_movement_type:
                        history_sql = """INSERT INTO credit_history
                            (customer_id, transaction_type, movement_type, amount, balance_before, balance_after, timestamp, notes, synced)
                            VALUES (
                                %s, 'REFUND', 'REFUND', %s,
                                (SELECT credit_balance FROM customers WHERE id = %s) + %s,  -- balance_before
                                (SELECT credit_balance FROM customers WHERE id = %s),  -- balance_after
                                NOW(), %s, 0
                            )"""
                        ops.append((history_sql, (
                            sale['customer_id'], -refund_amount,
                            sale['customer_id'], refund_amount,  # Para balance_before
                            sale['customer_id'],  # Para balance_after
                            history_notes
                        )))
                    else:
                        history_sql = """INSERT INTO credit_history
                            (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes, synced)
                            VALUES (
                                %s, 'REFUND', %s,
                                (SELECT credit_balance FROM customers WHERE id = %s) + %s,  -- balance_before
                                (SELECT credit_balance FROM customers WHERE id = %s),  -- balance_after
                                NOW(), %s, 0
                            )"""
                        ops.append((history_sql, (
                            sale['customer_id'], -refund_amount,
                            sale['customer_id'], refund_amount,  # Para balance_before
                            sale['customer_id'],  # Para balance_after
                            history_notes
                        )))
            
            # D. Eliminar relaciones CFDI (si la venta está relacionada con un CFDI)
            # CRITICAL FIX: Si se cancela una venta que está relacionada con un CFDI,
            # debemos eliminar la relación para mantener la integridad de datos
            # Esto es parte del flujo inverso: si se creó una relación al facturar,
            # debe eliminarse al cancelar
            if is_total:
                # Solo eliminar relaciones si es cancelación total
                # En cancelación parcial, la relación CFDI sigue siendo válida
                ops.append(("DELETE FROM sale_cfdi_relation WHERE sale_id = %s", (sale_id,)))
            
            # E. Registrar salida de efectivo (si aplica)
            # CRITICAL FIX: Usar turn_id de la venta original en lugar del turno actual
            # Esto previene registrar devoluciones en turnos incorrectos
            if sale['payment_method'] == 'cash':
                original_turn_id = sale.get('turn_id')
                if original_turn_id:
                    # Verificar si user_id existe
                    has_user_id = self._ensure_column_exists("cash_movements", "user_id", "INTEGER")
                    # CRÍTICO: Incluir synced=0 para sincronización - Auditoría 2026-01-30
                    if has_user_id:
                        ops.append(("INSERT INTO cash_movements (turn_id, type, amount, reason, timestamp, user_id, synced) VALUES (%s, 'out', %s, %s, NOW(), %s, 0)",
                                   (original_turn_id, refund_amount, f"Devolución Venta #{sale_id}: {reason}", user_id)))
                    else:
                        ops.append(("INSERT INTO cash_movements (turn_id, type, amount, reason, timestamp, synced) VALUES (%s, 'out', %s, %s, NOW(), 0)",
                                   (original_turn_id, refund_amount, f"Devolución Venta #{sale_id}: {reason}")))
                else:
                    # Si no hay turn_id en la venta original, intentar obtener turno actual como fallback
                    # pero registrar en notas que es un fallback
                    turn = self.get_current_turn(branch_id, user_id)
                    if turn:
                        has_user_id = self._ensure_column_exists("cash_movements", "user_id", "INTEGER")
                        reason_with_note = f"Devolución Venta #{sale_id} (turno original desconocido): {reason}"
                        # CRÍTICO: Incluir synced=0 para sincronización - Auditoría 2026-01-30
                        if has_user_id:
                            ops.append(("INSERT INTO cash_movements (turn_id, type, amount, reason, timestamp, user_id, synced) VALUES (%s, 'out', %s, %s, NOW(), %s, 0)",
                                       (turn['id'], refund_amount, reason_with_note, user_id)))
                        else:
                            ops.append(("INSERT INTO cash_movements (turn_id, type, amount, reason, timestamp, synced) VALUES (%s, 'out', %s, %s, NOW(), 0)",
                                       (turn['id'], refund_amount, reason_with_note)))
            
            # ============================================================
            # CRITICAL FIX: Ejecutar TODAS las operaciones en una transacción
            # Si falla CUALQUIER operación, TODO se revierte (rollback)
            # ============================================================
            # #region agent log
            if agent_log_enabled():
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"core.py:cancel_sale","message":"Before transaction execution","data":{"sale_id":sale_id,"ops_count":len(ops),"ops_summary":[op[0][:50] for op in ops[:5]]},"timestamp":int(time.time()*1000)})+"\n")
            # #endregion
            if ops:
                try:
                    result = self.db.execute_transaction(ops, timeout=5)
                    # #region agent log
                    if agent_log_enabled():
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E2E2","location":"core.py:cancel_sale","message":"E2E Flow: Transaction executed (cancel)","data":{"sale_id":sale_id,"success":result.get("success") if isinstance(result, dict) else result,"ops_count":len(ops),"rowcounts":result.get("rowcounts",[]) if isinstance(result, dict) else []},"timestamp":int(time.time()*1000)})+"\n")
                    # #endregion
                    logger.info(">>> CANCEL SALE SUCCESS: Sale ID=%s, Operations=%d", sale_id, len(ops))
                    
                    # E2E Verification: Verify sale was cancelled correctly
                    # #region agent log
                    if agent_log_enabled():
                        try:
                            sale_after_cancel = self.get_sale(sale_id)
                            sale_items_after_cancel = self.get_sale_items(sale_id)
                            with open(get_debug_log_path_str(), "a") as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E2E2","location":"core.py:cancel_sale","message":"E2E Flow: Post-cancellation verification","data":{"sale_id":sale_id,"sale_status":sale_after_cancel.get("status") if sale_after_cancel else None,"items_count":len(sale_items_after_cancel) if sale_items_after_cancel else 0},"timestamp":int(time.time()*1000)})+"\n")
                        except Exception as verify_e:
                            try:
                                with open(get_debug_log_path_str(), "a") as f:
                                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E2E2","location":"core.py:cancel_sale","message":"E2E Flow: Verification error (cancel)","data":{"sale_id":sale_id,"error":str(verify_e)},"timestamp":int(time.time()*1000)})+"\n")
                            except Exception as e: logger.debug("Writing debug log for cancel sale verification error: %s", e)
                    # #endregion
                except Exception as e:
                    # #region agent log
                    if agent_log_enabled():
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"core.py:cancel_sale","message":"Transaction failed","data":{"sale_id":sale_id,"error":str(e),"error_type":type(e).__name__},"timestamp":int(time.time()*1000)})+"\n")
                    # #endregion
                    logger.error(">>> CANCEL SALE TRANSACTION FAILED: %s", e)
                    import traceback
                    logger.error(">>> Transaction error traceback: %s", traceback.format_exc())
                    raise RuntimeError(f"Error en rollback de venta: {e}") from e
            else:
                # #region agent log
                if agent_log_enabled():
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"core.py:cancel_sale","message":"No operations to execute","data":{"sale_id":sale_id},"timestamp":int(time.time()*1000)})+"\n")
                # #endregion
                logger.warning(">>> CANCEL SALE: No operations to execute")
            
            # ============================================================
            # OPERACIONES POST-TRANSACCIÓN CON RETRY LOGIC
            # Reversión de puntos de lealtad y monedero anónimo
            # ============================================================
            
            # E. Revertir puntos MIDAS acumulados y redimidos (si aplica)
            if sale.get('customer_id'):
                customer_id = sale['customer_id']
                max_retries = 3
                
                # Consultar transacciones de lealtad para esta venta
                try:
                    loyalty_transactions = self.db.execute_query(
                        "SELECT tipo, monto, customer_id FROM loyalty_ledger WHERE ticket_referencia_id = %s",
                        (sale_id,)
                    )
                    
                    # #region agent log
                    if agent_log_enabled():
                        import json, time
                        try:
                            with open(get_debug_log_path_str(), "a") as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"INVERSE1","location":"core.py:cancel_sale","message":"Found loyalty transactions to revert","data":{"sale_id":sale_id,"customer_id":customer_id,"transactions_count":len(loyalty_transactions),"transactions":[{"tipo":t.get("tipo"),"monto":float(t.get("monto",0))} for t in loyalty_transactions]},"timestamp":int(time.time()*1000)})+"\n")
                        except Exception as e: logger.debug("Writing debug log for loyalty transactions to revert: %s", e)
                    # #endregion
                    
                    # Revertir cada transacción
                    for trans in loyalty_transactions:
                        trans_type = trans.get('tipo')
                        trans_amount = abs(float(trans.get('monto', 0)))
                        trans_customer_id = trans.get('customer_id')
                        
                        if trans_type == 'EARN' and trans_amount > 0:
                            # Revertir puntos acumulados: crear transacción REFUND que resta puntos
                            for attempt in range(max_retries):
                                try:
                                    from decimal import Decimal
                                    # CRITICAL: Usar acumular_puntos con monto negativo NO funciona
                                    # En su lugar, crear una transacción REFUND manual en el ledger
                                    account = self.loyalty_engine.get_or_create_account(trans_customer_id)
                                    if account:
                                        saldo_anterior = Decimal(str(account.saldo_actual))
                                        saldo_nuevo = saldo_anterior - Decimal(str(trans_amount))
                                        
                                        # Crear transacción REFUND en el ledger
                                        operations = [
                                            (
                                                """
                                                INSERT INTO loyalty_ledger (
                                                    account_id, customer_id, fecha_hora, tipo, monto, 
                                                    saldo_anterior, saldo_nuevo, ticket_referencia_id, 
                                                    turn_id, user_id, descripcion
                                                ) VALUES (%s, %s, NOW(), 'REFUND', %s, %s, %s, %s, %s, %s, %s)
                                                """,
                                                (
                                                    account.id, trans_customer_id, float(-trans_amount),
                                                    float(saldo_anterior), float(saldo_nuevo), sale_id,
                                                    sale.get('turn_id'), user_id, f"Reversión cancelación venta #{sale_id}"
                                                )
                                            ),
                                            (
                                                "UPDATE loyalty_accounts SET saldo_actual = %s, fecha_ultima_actividad = NOW(), synced = 0 WHERE id = %s",
                                                (float(saldo_nuevo), account.id)
                                            ),
                                            (
                                                "UPDATE customers SET wallet_balance = %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                                                (float(saldo_nuevo), trans_customer_id)
                                            )
                                        ]
                                        self.db.execute_transaction(operations, timeout=5)
                                        logger.info(">>> MIDAS: Reverted %s points earned for sale %s", trans_amount, sale_id)
                                        break
                                except Exception as e:
                                    if attempt < max_retries - 1:
                                        import time
                                        time.sleep(0.5 * (attempt + 1))
                                        logger.warning("MIDAS reversal failed (attempt %d/%d), retrying: %s", attempt + 1, max_retries, e)
                                    else:
                                        logger.error("MIDAS reversal failed after %d attempts: %s", max_retries, e)
                        
                        elif trans_type == 'REDEEM' and trans_amount > 0:
                            # Revertir puntos redimidos: devolver puntos (acumular de vuelta)
                            for attempt in range(max_retries):
                                try:
                                    from decimal import Decimal
                                    # Revertir redención: acumular de vuelta los puntos que se quitaron
                                    success = self.loyalty_engine.acumular_puntos(
                                        customer_id=trans_customer_id,
                                        monto=Decimal(str(trans_amount)),  # Positivo para devolver
                                        ticket_id=sale_id,
                                        turn_id=sale.get('turn_id'),
                                        user_id=user_id,
                                        descripcion=f"Reversión cancelación venta #{sale_id} - Devolución puntos redimidos"
                                    )
                                    if success:
                                        logger.info(">>> MIDAS: Reverted %s points redeemed for sale %s", trans_amount, sale_id)
                                        break
                                except Exception as e:
                                    if attempt < max_retries - 1:
                                        import time
                                        time.sleep(0.5 * (attempt + 1))
                                        logger.warning("MIDAS redemption reversal failed (attempt %d/%d), retrying: %s", attempt + 1, max_retries, e)
                                    else:
                                        logger.error("MIDAS redemption reversal failed after %d attempts: %s", max_retries, e)
                except Exception as e:
                    logger.error("Error querying loyalty transactions for sale %s: %s", sale_id, e)
            
            # F. Revertir monedero anónimo (si aplica)
            try:
                # Consultar transacciones de monedero anónimo para esta venta
                wallet_transactions = self.db.execute_query(
                    "SELECT wallet_id, type, points FROM wallet_transactions WHERE sale_id = %s",
                    (sale_id,)
                )
                
                # #region agent log
                if agent_log_enabled():
                    import json, time
                    try:
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"INVERSE2","location":"core.py:cancel_sale","message":"Found anonymous wallet transactions to revert","data":{"sale_id":sale_id,"transactions_count":len(wallet_transactions),"transactions":[{"wallet_id":t.get("wallet_id"),"type":t.get("type"),"points":t.get("points")} for t in wallet_transactions]},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e: logger.debug("Writing debug log for anonymous wallet transactions: %s", e)
                # #endregion
                
                if wallet_transactions:
                    from app.services.anonymous_loyalty import AnonymousLoyalty
                    anon_loyalty = AnonymousLoyalty(self)
                    
                    for trans in wallet_transactions:
                        wallet_id = trans.get('wallet_id')
                        trans_type = trans.get('type')
                        trans_points = int(trans.get('points', 0))
                        
                        if trans_type == 'EARN' and trans_points > 0:
                            # Revertir puntos acumulados: crear transacción REFUND que resta puntos
                            for attempt in range(max_retries):
                                try:
                                    from decimal import Decimal
                                    # CRITICAL: earn_points no acepta negativos, crear transacción REFUND manual
                                    wallet = anon_loyalty.find_wallet(wallet_id)
                                    if wallet:
                                        points_before = wallet['points_balance']
                                        points_after = points_before - trans_points
                                        
                                        operations = [
                                            (
                                                """
                                                INSERT INTO wallet_transactions (wallet_id, type, points, sale_id, description, synced)
                                                VALUES (%s, 'REFUND', %s, %s, %s, 0)
                                                """,
                                                (wallet_id, -trans_points, sale_id, f"Reversión cancelación venta #{sale_id}")
                                            ),
                                            (
                                                "UPDATE anonymous_wallet SET points_balance = %s, synced = 0 WHERE wallet_id = %s",
                                                (points_after, wallet_id)
                                            )
                                        ]
                                        self.db.execute_transaction(operations, timeout=5)
                                        logger.info(">>> Anonymous Wallet: Reverted %d points earned for sale %s", trans_points, sale_id)
                                        break
                                except Exception as e:
                                    if attempt < max_retries - 1:
                                        import time
                                        time.sleep(0.5 * (attempt + 1))
                                        logger.warning("Anonymous wallet reversal failed (attempt %d/%d), retrying: %s", attempt + 1, max_retries, e)
                                    else:
                                        logger.error("Anonymous wallet reversal failed after %d attempts: %s", max_retries, e)
                        
                        elif trans_type == 'REDEEM' and trans_points > 0:
                            # Revertir puntos redimidos: devolver puntos (acumular de vuelta)
                            for attempt in range(max_retries):
                                try:
                                    from decimal import Decimal
                                    # Revertir redención: acumular de vuelta los puntos que se quitaron
                                    anon_loyalty.earn_points(wallet_id, Decimal(str(trans_points)), sale_id)
                                    logger.info(">>> Anonymous Wallet: Reverted %d points redeemed for sale %s", trans_points, sale_id)
                                    break
                                except Exception as e:
                                    if attempt < max_retries - 1:
                                        import time
                                        time.sleep(0.5 * (attempt + 1))
                                        logger.warning("Anonymous wallet redemption reversal failed (attempt %d/%d), retrying: %s", attempt + 1, max_retries, e)
                                    else:
                                        logger.error("Anonymous wallet redemption reversal failed after %d attempts: %s", max_retries, e)
            except Exception as e:
                logger.error("Error querying anonymous wallet transactions for sale %s: %s", sale_id, e)
            
            # G. Audit Log - Sale cancelled (con retry)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    from app.utils.audit_logger import get_audit_logger
                    audit = get_audit_logger()
                    if audit:
                        audit.log_sale_cancel(sale_id, reason, {
                            'refund_amount': refund_amount,
                            'is_total': is_total,
                            'items_count': len(items) if items else 0,
                            'customer_id': sale.get('customer_id'),
                            'turn_id': sale.get('turn_id'),
                            'payment_method': sale.get('payment_method')
                        })
                    break  # Éxito, salir del loop de retry
                except Exception as e:
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(0.5 * (attempt + 1))  # Backoff exponencial
                        logger.warning("Audit log cancellation failed (attempt %d/%d), retrying: %s", attempt + 1, max_retries, e)
                    else:
                        logger.error("Audit log cancellation failed after %d attempts: %s", max_retries, e)
                        # No lanzar excepción, solo registrar error (cancelación ya está hecha)

            # FIX: Emitir evento de venta cancelada para PWA
            try:
                emit_sale_cancelled(
                    sale_id=sale_id,
                    total=refund_amount,
                    reason=reason
                )
            except Exception as emit_e:
                logger.debug("Could not emit cancel event: %s", emit_e)

            return True
        except Exception as e:
            logger.error("Error cancelling sale: %s", e)
            raise e

    def create_layaway(self, customer_id, items, initial_payment, due_date, notes):
        return self.engine.create_layaway(customer_id, items, initial_payment, due_date, notes, STATE.user_id)

    def add_layaway_payment(self, layaway_id, amount, payment_data=None):
        return self.engine.add_layaway_payment(layaway_id, amount, STATE.user_id, payment_data)

    def cancel_layaway(self, layaway_id, reason=None):
        return self.engine.cancel_layaway(layaway_id, STATE.user_id, reason)

    def list_layaways(self, branch_id=1, status="active", date_range=None):
        return self.engine.list_layaways(branch_id, status, date_range)

    def get_layaway(self, layaway_id):
        return self.engine.get_layaway(layaway_id)

    def get_layaway_items(self, layaway_id):
        return self.engine.get_layaway_items(layaway_id)

    def get_layaway_payments(self, layaway_id):
        return self.engine.get_layaway_payments(layaway_id)
    
    # ========== TICKET CONFIGURATION METHODS (Multi-Branch Support) ==========
    
    def get_ticket_config(self, branch_id):
        """
        Get ticket configuration for a specific branch.
        
        Args:
            branch_id: Branch ID to get config for
            
        Returns:
            Dict with ticket configuration, or defaults if not found
        """
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                from app.utils.path_utils import get_debug_log_path_str
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_GET","location":"core.py:get_ticket_config","message":"Getting ticket config","data":{"branch_id":branch_id},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e: logger.debug("Writing debug log for getting ticket config: %s", e)
        # #endregion
        
        try:
            sql = "SELECT * FROM branch_ticket_config WHERE branch_id = %s"
            rows = self.db.execute_query(sql, (branch_id,))
            
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_GET","location":"core.py:get_ticket_config","message":"Query executed","data":{"branch_id":branch_id,"rows_found":len(rows) if rows else 0},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logger.debug("Writing debug log for ticket config query: %s", e)
            # #endregion
            
            if rows and len(rows) > 0 and rows[0]:
                result = dict(rows[0])
                # #region agent log
                if agent_log_enabled():
                    import json, time
                    try:
                        from app.utils.path_utils import get_debug_log_path_str
                        result_summary = {k: (str(v)[:50] if isinstance(v, str) and len(str(v)) > 50 else v) for k, v in result.items()}
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_GET","location":"core.py:get_ticket_config","message":"Config found in DB","data":{"branch_id":branch_id,"result_keys":list(result.keys()),"result_summary":result_summary},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e: logger.debug("Writing debug log for config found in DB: %s", e)
                # #endregion
                return result
            else:
                # Return defaults from app config
                app_cfg = self.get_app_config()
                return {
                    "branch_id": branch_id,
                    "business_name": app_cfg.get("store_name", "TITAN POS"),
                    "business_address": app_cfg.get("store_address", ""),
                    "business_phone": app_cfg.get("store_phone", ""),
                    "business_rfc": app_cfg.get("store_rfc", ""),
                    "website_url": "",
                    "show_phone": 1,
                    "show_rfc": 1,
                    "show_product_code": 0,
                    "show_unit": 0,
                    "price_decimals": 2,
                    "currency_symbol": "$",
                    "show_separators": 1,
                    "line_spacing": 1.0,
                    "margin_chars": 0,
                    "thank_you_message": "¡Gracias por su compra!",
                    "legal_text": "",
                    "qr_enabled": 0,
                    "qr_content_type": "url",
                    "cut_lines": 3,
                    "bold_headers": 1
                }
        except Exception as e:
            logger.error("Error getting ticket config: %s", e)
            return {}
    
    def save_ticket_config(self, branch_id, config):
        """
        Save ticket configuration for a specific branch.
        
        Args:
            branch_id: Branch ID to save config for
            config: Dict with configuration values
            
        Returns:
            True if successful, False otherwise
        """
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                from app.utils.path_utils import get_debug_log_path_str
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_SAVE_DB","location":"core.py:save_ticket_config","message":"Function entry","data":{"branch_id":branch_id,"config_keys":list(config.keys())},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e: logger.debug("Writing debug log for save_ticket_config entry: %s", e)
        # #endregion
        
        try:
            # Check if config exists
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_SAVE_DB","location":"core.py:save_ticket_config","message":"Checking if config exists","data":{"branch_id":branch_id},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logger.debug("Writing debug log for checking config exists: %s", e)
            # #endregion
            
            existing = self.db.execute_query(
                "SELECT branch_id FROM branch_ticket_config WHERE branch_id = %s",
                (branch_id,)
            )
            
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_SAVE_DB","location":"core.py:save_ticket_config","message":"Existing check result","data":{"exists":bool(existing),"branch_id":branch_id},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logger.debug("Writing debug log for existing check result: %s", e)
            # #endregion
            
            if existing:
                # Update existing - INCLUDE ALL FIELDS
                # PostgreSQL uses %s placeholders
                sql = """
                    UPDATE branch_ticket_config SET
                        business_name = %s,
                        business_address = %s,
                        business_phone = %s,
                        business_rfc = %s,
                        business_regime = %s,
                        business_razon_social = %s,
                        business_street = %s,
                        business_cross_streets = %s,
                        business_neighborhood = %s,
                        business_city = %s,
                        business_state = %s,
                        business_postal_code = %s,
                        website_url = %s,
                        show_phone = %s,
                        show_rfc = %s,
                        show_product_code = %s,
                        show_unit = %s,
                        price_decimals = %s,
                        currency_symbol = %s,
                        show_separators = %s,
                        line_spacing = %s,
                        margin_chars = %s,
                        margin_top = %s,
                        margin_bottom = %s,
                        thank_you_message = %s,
                        legal_text = %s,
                        qr_enabled = %s,
                        qr_content_type = %s,
                        cut_lines = %s,
                        bold_headers = %s,
                        show_invoice_code = %s,
                        invoice_url = %s,
                        invoice_days_limit = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE branch_id = %s
                """
                # Convert boolean values to integers for PostgreSQL compatibility
                params = (
                    config.get("business_name", ""),
                    config.get("business_address", ""),
                    config.get("business_phone", ""),
                    config.get("business_rfc", ""),
                    config.get("business_regime", ""),
                    config.get("business_razon_social", ""),
                    config.get("business_street", ""),
                    config.get("business_cross_streets", ""),
                    config.get("business_neighborhood", ""),
                    config.get("business_city", ""),
                    config.get("business_state", ""),
                    config.get("business_postal_code", ""),
                    config.get("website_url", ""),
                    1 if config.get("show_phone", True) else 0,  # Convert bool to int
                    1 if config.get("show_rfc", True) else 0,  # Convert bool to int
                    1 if config.get("show_product_code", False) else 0,  # Convert bool to int
                    1 if config.get("show_unit", False) else 0,  # Convert bool to int
                    config.get("price_decimals", 2),
                    config.get("currency_symbol", "$"),
                    1 if config.get("show_separators", True) else 0,  # Convert bool to int
                    config.get("line_spacing", 1.0),
                    config.get("margin_chars", 0),
                    config.get("margin_top", 0),
                    config.get("margin_bottom", 0),
                    config.get("thank_you_message", ""),
                    config.get("legal_text", ""),
                    1 if config.get("qr_enabled", False) else 0,  # Convert bool to int
                    config.get("qr_content_type", "url"),
                    config.get("cut_lines", 3),
                    1 if config.get("bold_headers", True) else 0,  # Convert bool to int
                    1 if config.get("show_invoice_code", True) else 0,  # Convert bool to int
                    config.get("invoice_url", ""),
                    config.get("invoice_days_limit", 3),
                    branch_id
                )
                self.db.execute_write(sql, params)
            else:
                # Insert new
                sql = """
                    INSERT INTO branch_ticket_config (
                        branch_id, business_name, business_address, business_phone, business_rfc,
                        business_razon_social, business_regime, business_street, business_cross_streets, business_neighborhood,
                        business_city, business_state, business_postal_code, website_url, show_phone, show_rfc, show_product_code, show_unit,
                        price_decimals, currency_symbol, show_separators, line_spacing, margin_chars,
                        thank_you_message, legal_text, qr_enabled, qr_content_type, cut_lines, bold_headers,
                        show_invoice_code, invoice_url, invoice_days_limit, margin_top, margin_bottom
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                # Convert boolean values to integers for PostgreSQL compatibility
                params = (
                    branch_id,
                    config.get("business_name", ""),
                    config.get("business_address", ""),
                    config.get("business_phone", ""),
                    config.get("business_rfc", ""),
                    config.get("business_razon_social", ""),  # FIXED: Added missing field
                    config.get("business_regime", ""),
                    config.get("business_street", ""),
                    config.get("business_cross_streets", ""),
                    config.get("business_neighborhood", ""),
                    config.get("business_city", ""),
                    config.get("business_state", ""),
                    config.get("business_postal_code", ""),
                    config.get("website_url", ""),
                    1 if config.get("show_phone", True) else 0,  # Convert bool to int
                    1 if config.get("show_rfc", True) else 0,  # Convert bool to int
                    1 if config.get("show_product_code", False) else 0,  # Convert bool to int
                    1 if config.get("show_unit", False) else 0,  # Convert bool to int
                    config.get("price_decimals", 2),
                    config.get("currency_symbol", "$"),
                    1 if config.get("show_separators", True) else 0,  # Convert bool to int
                    config.get("line_spacing", 1.0),
                    config.get("margin_chars", 0),
                    config.get("thank_you_message", ""),
                    config.get("legal_text", ""),
                    1 if config.get("qr_enabled", False) else 0,  # Convert bool to int
                    config.get("qr_content_type", "url"),
                    config.get("cut_lines", 3),
                    1 if config.get("bold_headers", True) else 0,  # Convert bool to int
                    1 if config.get("show_invoice_code", True) else 0,  # Convert bool to int
                    config.get("invoice_url", ""),
                    config.get("invoice_days_limit", 30),
                    config.get("margin_top", 0),
                    config.get("margin_bottom", 0)
                )
                self.db.execute_write(sql, params)
            
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_SAVE_DB","location":"core.py:save_ticket_config","message":"Database write completed","data":{"branch_id":branch_id,"operation":"INSERT" if not existing else "UPDATE"},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logger.debug("Writing debug log for database write completed: %s", e)
            # #endregion
            
            # Verify the save by reading it back
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_SAVE_DB","location":"core.py:save_ticket_config","message":"Verifying save by reading back","data":{"branch_id":branch_id},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logger.debug("Writing debug log for verifying save: %s", e)
            # #endregion
            
            # Verify the save by reading ALL fields back (not just 3)
            verify = self.db.execute_query(
                "SELECT * FROM branch_ticket_config WHERE branch_id = %s",
                (branch_id,)
            )
            
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    verify_data = dict(verify[0]) if verify and len(verify) > 0 and verify[0] else {}
                    # Compare saved values with what was sent
                    saved_business_name = verify_data.get("business_name", "")
                    saved_business_phone = verify_data.get("business_phone", "")
                    sent_business_name = config.get("business_name", "")
                    sent_business_phone = config.get("business_phone", "")
                    name_match = saved_business_name == sent_business_name
                    phone_match = saved_business_phone == sent_business_phone
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_SAVE_DB","location":"core.py:save_ticket_config","message":"Verification read completed","data":{"branch_id":branch_id,"verified":bool(verify),"name_match":name_match,"phone_match":phone_match,"saved_name":saved_business_name[:30],"sent_name":sent_business_name[:30],"saved_phone":saved_business_phone[:20],"sent_phone":sent_business_phone[:20],"all_fields":list(verify_data.keys())},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logger.debug("Writing debug log for verification read completed: %s", e)
            # #endregion
            
            logger.info("Ticket config saved for branch %s", branch_id)
            return True
            
        except Exception as e:
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_SAVE_DB","location":"core.py:save_ticket_config","message":"Exception during save","data":{"branch_id":branch_id,"error":str(e)},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logger.debug("Writing debug log for save exception: %s", e)
            # #endregion
            
            logger.error("Error saving ticket config: %s", e, exc_info=True)
            return False

# Instancia global legacy (lazy initialization)
# No crear al importar - permitir que el wizard se ejecute primero
core_instance = None

def get_core_instance():
    """Obtiene o crea la instancia global de POSCore (lazy)."""
    global core_instance
    if core_instance is None:
        core_instance = POSCore()
    return core_instance

class GlobalState:
    """Mantiene el estado global de la sesión (Usuario, Sucursal, Turno)."""
    def __init__(self):
        self.user_id = None
        self.username = "Guest"
        self.current_turn_id = None
        self.is_admin = False
        self.role = "cashier"
        
        # Cargar branch_id y terminal_id desde configuración
        try:
            # Usar get_core_instance() para lazy initialization
            core = get_core_instance()
            if core and core.db:  # Solo si core está inicializado
                cfg = core.get_app_config() or {}
                self.branch_id = int(cfg.get("branch_id", cfg.get("active_branch_id", 1)))
                self.terminal_id = int(cfg.get("terminal_id", 1))
                self.branch_name = cfg.get("branch_name", "Sucursal Principal")
            else:
                # Si no hay core (wizard inicial), usar defaults
                self.branch_id = 1
                self.terminal_id = 1
                self.branch_name = "Sucursal Principal"
        except Exception:
            # Si hay error, usar defaults
            self.branch_id = 1
            self.terminal_id = 1
            self.branch_name = "Sucursal Principal"

STATE = GlobalState()

