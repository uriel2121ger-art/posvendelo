# =============================================================================
# POS ENGINE — FACADE (Modular Monolith)
#
# REFACTORED: Methods extracted into domain-specific mixin modules:
#   - modules/sales/pos_sales.py       → POSSalesMixin (cart, checkout, series, folios)
#   - modules/sales/pos_layaways.py    → POSLayawaysMixin (apartados)
#   - modules/products/pos_products.py → POSProductsMixin (CRUD, search, kits)
#   - modules/customers/pos_customers.py → POSCustomersMixin (CRUD, wallet, credit)
#   - modules/turns/pos_turns.py       → POSTurnsMixin (open/close turn)
#
# POSEngine inherits from all mixins = backward compatible facade.
# create_sale_transaction remains here (950 LOC, deeply coupled).
# =============================================================================
"""
SERVICES: POS ENGINE (OPTIMIZED)
Orquestador principal con caché y monitoreo de performance.
Now uses mixin classes from modules/ for domain-specific logic.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
import math
import threading
import uuid

from src.core.finance import Money
import src.infra.database as db_module

# Domain mixins are available in modules/ for new code.
# POSEngine keeps its own methods for backward compatibility.
# New code should import from modules/ instead of pos_engine.py directly.
# Phase 2 will gradually migrate callers to use modules/ directly.

# Thread-local storage: cada hilo tiene su propia instancia de POSEngine (SEC-1/PEND-1)
_local = threading.local()


def get_pos_engine() -> "POSEngine":
    """Devuelve la instancia de POSEngine del hilo actual. Thread-safe."""
    if not hasattr(_local, "engine"):
        _local.engine = POSEngine()
    return _local.engine

# Importar sistema de caché y optimización
try:
    from app.utils.query_cache import cached_query, query_cache, timed_query
    CACHE_ENABLED = True
except ImportError:
    # Fallback sin caché
    CACHE_ENABLED = False
    def cached_query(ttl=300, invalidate_on=None):
        def decorator(func):
            return func
        return decorator
    def timed_query(func):
        return func

logger = logging.getLogger("POS_ENGINE")

class POSEngine:
    """
    POS Engine — original monolithic class.

    Domain-specific methods have been COPIED (not moved) to modules/:
      - modules/sales/pos_sales.py, pos_layaways.py
      - modules/products/pos_products.py
      - modules/customers/pos_customers.py
      - modules/turns/pos_turns.py

    Original methods remain here for backward compatibility.
    New code should import from modules/ instead.
    """
    TAX_RATE = 0.16 # IVA 16%

    def __init__(self):
        self.current_cart = []
        self.current_customer = None
        self.current_turn_id = None
        self.global_discount_pct = 0.0
        
    @property
    def db(self):
        """Acceso dinámico a la instancia de DB."""
        if db_module.db_instance is None:
             raise RuntimeError("Database not initialized!")
        return db_module.db_instance

    def _ensure_column_exists(self, table_name, column_name, column_type="INTEGER", default_value=None):
        """
        Helper function to ensure a column exists in a table before INSERT/UPDATE.
        Returns True if column exists (or was successfully added), False otherwise.
        Similar to POSCore._ensure_column_exists but works with DatabaseManager directly.
        """
        try:
            table_info = self.db.get_table_info(table_name)
            
            if not table_info:
                logger.warning(f"Could not get table info for {table_name}")
                return False
            
            # Extract column names from table_info
            cols = []
            for col in table_info:
                if isinstance(col, dict):
                    cols.append(col.get('name', ''))
                elif isinstance(col, (list, tuple)) and len(col) > 1:
                    cols.append(col[1])
                elif isinstance(col, str):
                    cols.append(col)
            
            if column_name in cols:
                return True
            
            # Column doesn't exist, try to add it
            try:
                if default_value is not None:
                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} DEFAULT {default_value}"
                else:
                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                
                self.db.execute_write(alter_sql)
                
                # Try to add foreign key if it's user_id
                if column_name == "user_id":
                    try:
                        fk_sql = f"ALTER TABLE {table_name} ADD CONSTRAINT fk_{table_name}_user FOREIGN KEY ({column_name}) REFERENCES users(id)"
                        self.db.execute_write(fk_sql)
                    except Exception as fk_e:
                        logger.debug(f"FK constraint skipped for {table_name}.{column_name}: {fk_e}")
                        # FK might already exist or users table might not exist
                
                logger.info(f"Added missing column: {table_name}.{column_name} ({column_type})")
                return True
            except Exception as e:
                error_str = str(e).lower()
                if "already exists" in error_str or "duplicate" in error_str:
                    # Column already exists, return True
                    logger.debug(f"Column {table_name}.{column_name} already exists")
                    return True
                else:
                    logger.warning(f"Could not add {table_name}.{column_name}: {e}")
                    return False
        except Exception as e:
            logger.debug(f"Could not check/add column {table_name}.{column_name}: {e}")
            return False

    def set_customer(self, customer_id: int):
        """Asigna un cliente a la venta actual. Valida customer_id (PEND-2)."""
        if customer_id is None:
            raise ValueError("customer_id no puede ser None")
        if not isinstance(customer_id, int):
            raise ValueError("customer_id debe ser un entero")
        if customer_id <= 0:
            raise ValueError("customer_id debe ser mayor que 0")
        rows = self.db.execute_query("SELECT * FROM customers WHERE id = %s", (customer_id,))
        if rows:
            self.current_customer = dict(rows[0])
            return True
        return False

    def set_global_discount(self, percentage: float):
        """Aplica un descuento global (0-100). Valida NaN/Inf (PEND-3)."""
        if math.isnan(percentage) or math.isinf(percentage):
            raise ValueError("El descuento no puede ser NaN ni infinito")
        if not (0 <= percentage <= 100):
            raise ValueError("El descuento debe estar entre 0 y 100")
        self.global_discount_pct = percentage

    # CACHE DISABLED: Stock data must always be fresh
    @timed_query
    def get_product_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        # EMERGENCY FIX 2026-01-10: Buscar en SKU o barcode (normalizado)
        # Cliente reporta que pistola láser no encuentra productos
        sku_clean = sku.strip() if sku else ""
        
        # Buscar primero exacto (más rápido)
        rows = self.db.execute_query(
            "SELECT * FROM products WHERE sku = %s OR barcode = %s LIMIT 1", 
            (sku_clean, sku_clean)
        )
        
        # Si no encuentra, intentar case-insensitive
        if not rows:
            rows = self.db.execute_query("""
                SELECT * FROM products 
                WHERE LOWER(TRIM(sku)) = LOWER(%s) 
                   OR LOWER(TRIM(barcode)) = LOWER(%s)
                LIMIT 1
            """, (sku_clean, sku_clean))
        
        if rows:
            return dict(rows[0])
        return None

    # CACHE DISABLED: Stock data must always be fresh
    @timed_query
    def get_product_by_id(self, product_id: int) -> Optional[Dict[str, Any]]:
        rows = self.db.execute_query("SELECT * FROM products WHERE id = %s", (product_id,))
        if rows:
            return dict(rows[0])
        return None

    def count_products(self, query: Optional[str] = None) -> int:
        sql = "SELECT COUNT(*) as count FROM products WHERE is_active = 1"
        params = []
        if query:
            sql += " AND (name LIKE %s OR sku LIKE %s OR barcode LIKE %s OR department LIKE %s OR provider LIKE %s)"
            params = [f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"]
        rows = self.db.execute_query(sql, tuple(params))
        return rows[0]["count"] if rows else 0

    def list_products(self, limit: int = 50, offset: int = 0, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista productos con paginación y búsqueda (solo productos activos y visibles)."""
        # CRITICAL: Force fresh query to avoid stale stock display
        # FIXED: Filter by is_active = 1 to hide deleted products
        # FIXED: Filter by visible != 0 to hide common/temporary products
        if query:
            sql = "SELECT * FROM products WHERE is_active = 1 AND (visible IS NULL OR visible != 0) AND (name LIKE %s OR sku LIKE %s OR barcode LIKE %s) ORDER BY name LIMIT %s OFFSET %s"
            rows = self.db.execute_query(sql, (f"%{query}%", f"%{query}%", f"%{query}%", limit, offset))
        else:
            sql = "SELECT * FROM products WHERE is_active = 1 AND (visible IS NULL OR visible != 0) ORDER BY name LIMIT %s OFFSET %s"
            rows = self.db.execute_query(sql, (limit, offset))
        return [dict(r) for r in rows]

    def list_products_for_export(self) -> List[Dict[str, Any]]:
        """Lista todos los productos sin paginación."""
        # INDEX RECOMMENDATION: CREATE INDEX idx_products_is_active ON products(is_active)
        # Safety limit to prevent memory issues with very large catalogs
        sql = "SELECT * FROM products WHERE is_active = 1 LIMIT 50000"
        return [dict(row) for row in self.db.execute_query(sql)]
    
    def get_products(self, limit=100, **kwargs):
        """Wrapper method for backwards compatibility - gets products."""
        return self.list_products(limit=limit, offset=0)
    
    def search_products(self, query: str = "", category_id: Optional[int] = None, limit: int = 50):
        """Busca productos por nombre, SKU o código de barras, opcionalmente filtrado por categoría."""
        sql = "SELECT * FROM products WHERE is_active = 1"
        params = []

        if query:
            sql += " AND (name LIKE %s OR sku LIKE %s OR barcode LIKE %s)"
            params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])
        
        if category_id:
            sql += " AND category_id = %s"
            params.append(category_id)
        
        sql += " ORDER BY name LIMIT %s"
        params.append(limit)

        rows = self.db.execute_query(sql, tuple(params))
        return [dict(r) for r in rows]

    # ... (add_product, open_turn, close_turn se mantienen igual) ...

    # ... (add_to_cart se mantiene igual) ...

    def calculate_cart_totals(self) -> Dict[str, Money]:
        """Calcula subtotales, descuentos, impuestos y total."""
        subtotal = Money(0)
        for item in self.current_cart:
            subtotal += item['total']
            
        # Aplicar Descuento Global
        discount_amount = subtotal * (self.global_discount_pct / 100.0)
        subtotal_after_discount = subtotal - discount_amount
            
        # Impuestos
        tax = subtotal_after_discount * self.TAX_RATE
        total = subtotal_after_discount + tax
        
        return {
            "subtotal": subtotal,
            "discount": discount_amount,
            "tax": tax,
            "total": total
        }

    def create_product(self, product_data: Dict[str, Any]) -> int:
        """
        Crea un nuevo producto con soporte para campos extendidos.
        
        VALIDACIONES AGREGADAS:
        - SKU y nombre obligatorios
        - Precio >= 0, no NaN/Inf
        - Stock >= 0, no NaN/Inf
        - Cost >= 0, no NaN/Inf
        - Tax rate válido (0-1)
        """
        # ===== INPUT VALIDATION =====
        # Verificar que sea un diccionario
        if not isinstance(product_data, dict):
            raise ValueError(f"product_data debe ser un diccionario, recibido: {type(product_data).__name__}")
        
        # Required fields
        sku = product_data.get('sku')
        if not sku or (isinstance(sku, str) and not sku.strip()):
            raise ValueError("SKU es obligatorio")
        if not isinstance(sku, (str, int)):
            raise ValueError(f"SKU inválido: tipo {type(sku).__name__}")
            
        name = product_data.get('name')
        if not name or (isinstance(name, str) and not name.strip()):
            raise ValueError("Nombre del producto es obligatorio")
        
        # Numeric validations con NaN/Inf check
        def validate_number(val, field_name, allow_negative=False):
            if val is None:
                return 0.0
            if isinstance(val, (list, dict, tuple, set)):
                raise ValueError(f"{field_name} inválido: tipo {type(val).__name__}")
            try:
                num = float(val)
                if math.isnan(num) or math.isinf(num):
                    raise ValueError(f"{field_name} no puede ser NaN o Infinito")
                if not allow_negative and num < 0:
                    raise ValueError(f"{field_name} no puede ser negativo: {num}")
                return num
            except (TypeError, ValueError) as e:
                raise ValueError(f"{field_name} inválido: {e}")
        
        price = validate_number(product_data.get('price', 0), 'Precio')
        stock = validate_number(product_data.get('stock', 0), 'Stock')
        cost = validate_number(product_data.get('cost', 0), 'Costo')
        min_stock = validate_number(product_data.get('min_stock', 5), 'Stock mínimo')
        
        # Tax rate validation
        tax_rate = product_data.get('tax_rate', 0.16)
        if tax_rate is not None:
            tax_rate = validate_number(tax_rate, 'Tax rate')
            if not (0 <= tax_rate <= 1):
                raise ValueError("Tax rate debe estar entre 0 y 1")
        
        # ===== ORIGINAL CODE =====
        keys = [
            "sku", "name", "price", "price_wholesale", "cost", 
            "stock", "min_stock", "department", "category",
            "provider", "tax_rate", "sale_type", "barcode", "is_favorite",
            "sat_clave_prod_serv", "sat_clave_unidad", "sat_descripcion"  # SAT catalog codes for CFDI 4.0
        ]
        
        # Filtrar solo claves válidas que vengan en product_data
        valid_data = {k: product_data.get(k) for k in keys if k in product_data}
        
        # Convertir is_favorite de boolean a integer si existe
        if "is_favorite" in valid_data and isinstance(valid_data["is_favorite"], bool):
            valid_data["is_favorite"] = 1 if valid_data["is_favorite"] else 0
        
        # Asegurar valores por defecto para campos críticos si no vienen
        if "price" not in valid_data: valid_data["price"] = 0.0
        if "cost" not in valid_data: valid_data["cost"] = 0.0
        if "stock" not in valid_data: valid_data["stock"] = 0.0
        
        # SECURITY: Validar que todas las columnas están en el whitelist
        ALLOWED_PRODUCT_COLUMNS = set(keys)
        for col in valid_data.keys():
            if col not in ALLOWED_PRODUCT_COLUMNS:
                raise ValueError(f"Columna no permitida en products: {col}")
        
        # Add synced = 0 to mark for sync (new products need to sync to server)
        valid_data["synced"] = 0

        columns = ", ".join(valid_data.keys())
        placeholders = ", ".join(["%s"] * len(valid_data))
        values = tuple(valid_data.values())

        # SECURITY: columns ahora validadas contra whitelist
        sql = f"INSERT INTO products ({columns}) VALUES ({placeholders})"
        result = self.db.execute_write(sql, values)

        # Cache invalidation after database write
        if CACHE_ENABLED:
            try:
                query_cache.clear()
            except Exception as e:
                logger.warning(f"Cache clear failed: {e}")

        return result

    def update_product(self, product_id: int, product_data: Dict[str, Any]):
        """Actualiza un producto existente."""
        keys = [
            "sku", "name", "price", "price_wholesale", "cost", 
            "stock", "min_stock", "department", "category",
            "provider", "tax_rate", "sale_type", "barcode", "is_favorite",
            "sat_clave_prod_serv", "sat_clave_unidad", "sat_descripcion"  # SAT catalog codes for CFDI 4.0
        ]
        
        valid_data = {k: product_data.get(k) for k in keys if k in product_data}
        
        if not valid_data:
            return
        
        # Convertir is_favorite de boolean a integer si existe
        if "is_favorite" in valid_data and isinstance(valid_data["is_favorite"], bool):
            valid_data["is_favorite"] = 1 if valid_data["is_favorite"] else 0
        
        # SECURITY: Validar whitelist
        ALLOWED_PRODUCT_COLUMNS = set(keys)
        for col in valid_data.keys():
            if col not in ALLOWED_PRODUCT_COLUMNS:
                raise ValueError(f"Columna no permitida en products: {col}")
            
        set_clause = ", ".join([f"{k} = %s" for k in valid_data.keys()])
        values = list(valid_data.values())
        values.append(product_id)
        
        # SECURITY: columns validadas
        # Add synced = 0 to mark for sync, updated_at for tracking
        sql = f"UPDATE products SET {set_clause}, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        # CRITICAL FIX 2026-02-03: Return rowcount so caller knows if update succeeded
        rowcount = self.db.execute_write(sql, tuple(values))

        # Clear cache to ensure fresh data is returned
        if CACHE_ENABLED:
            try:
                query_cache.clear()
            except Exception as e:
                # CRITICAL FIX: Don't let cache error mask successful DB update
                import logging
                logging.getLogger(__name__).warning(f"Cache clear failed (update succeeded): {e}")

        return rowcount

    def add_stock(self, product_id, qty, reason="ajuste manual"):
        # Parte A Fase 1: registrar movimiento para delta sync (ajuste desde UI)
        try:
            mov_sql = """INSERT INTO inventory_movements
                (product_id, movement_type, type, quantity, reason, reference_type, user_id, branch_id, timestamp, synced)
                VALUES (%s, 'IN', 'adjust', %s, %s, 'adjust', NULL, NULL, NOW(), 0)"""
            self.db.execute_write(mov_sql, (product_id, qty, reason or "ajuste manual"))
        except Exception as e:
            logger.debug("Could not insert inventory_movement for add_stock: %s", e)
        sql = "UPDATE products SET stock = stock + %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        self.db.execute_write(sql, (qty, product_id))
        if CACHE_ENABLED:
            query_cache.clear()

    def delete_product(self, product_id: int):
        """Marca un producto como inactivo (soft delete)."""
        sql = "UPDATE products SET is_active = 0, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        self.db.execute_write(sql, (product_id,))

        # Cache invalidation after database write
        if CACHE_ENABLED:
            try:
                query_cache.clear()
            except Exception as e:
                logger.warning(f"Cache clear failed: {e}")

        return True

    # ==================== DUAL SERIES FISCAL SYSTEM ====================
    
    def determine_serie(self, payment_method: str, cliente_pide_factura: bool = False, 
                        mixed_breakdown: dict = None) -> str:
        """
        Lógica Maestra de Asignación de Serie.
        
        Args:
            payment_method: Método de pago (cash, card, transfer, mixed, etc.)
            cliente_pide_factura: True si el cliente solicita factura
            mixed_breakdown: Diccionario con desglose de pago mixto
        
        Returns:
            'A' (Fiscal/SAT) or 'B' (Interno)
        
        Rules:
            1. REGLA SUPREMA: Si cliente EXIGE factura → SIEMPRE Serie A
            2. REGLA BANCARIA: Si deja rastro bancario → Serie A (aplica a mixto también)
            3. Solo Serie B si es 100% efectivo/monedero Y NO pide factura
        
        IMPORTANTE: Pagos con tarjeta o transferencia SIEMPRE dejan rastro fiscal.
                    El SAT puede auditar movimientos bancarios.
        """
        # 1. REGLA SUPREMA: Cliente pide factura → SIEMPRE Serie A
        if cliente_pide_factura:
            return 'A'
        
        # 2. REGLA BANCARIA: Métodos con rastro fiscal directo → Serie A
        metodos_fiscales = ['card', 'transfer', 'check', 'usd']
        if payment_method in metodos_fiscales:
            return 'A'
        
        # 3. REGLA MIXTO: Si es pago mixto, revisar si CUALQUIER componente es bancario
        if payment_method == 'mixed' and mixed_breakdown:
            # Si hay monto en tarjeta → Serie A (deja rastro)
            if float(mixed_breakdown.get('card', 0) or 0) > 0:
                return 'A'
            # Si hay monto en transferencia → Serie A (deja rastro)
            if float(mixed_breakdown.get('transfer', 0) or 0) > 0:
                return 'A'
            # Si hay monto en cheque → Serie A (documento negociable)
            if float(mixed_breakdown.get('check', 0) or 0) > 0:
                return 'A'
            # Si hay monto en USD → Serie A (operación cambiaria)
            if float(mixed_breakdown.get('usd', 0) or 0) > 0:
                return 'A'
        
        # 4. Solo cae en B si es 100% Efectivo/Monedero/GiftCard Y NO pidió factura
        return 'B'
    
    def get_next_folio(self, serie: str, terminal_id: int = 1) -> str:
        """
        Get next folio number atomically with terminal support.
        Returns format: A1-000001, B2-000001, etc. (Serie + Terminal + Numero)
        This ensures unique folios across multiple terminals.
        
        CRITICAL FIX: Usa UPDATE ... RETURNING para evitar condiciones de carrera.
        """
        # Ensure sequence exists atomically (ON CONFLICT eliminates TOCTOU race condition)
        try:
            self.db.execute_write(
                "INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion, synced) "
                "VALUES (%s, %s, 0, %s, 0) ON CONFLICT (serie, terminal_id) DO NOTHING",
                (serie, terminal_id, f"{serie} Terminal {terminal_id}")
            )
        except Exception as e:
            error_str = str(e).lower()
            if 'duplicate' not in error_str and 'unique' not in error_str:
                raise
        
        # CRITICAL FIX: Usar execute_write para que el UPDATE haga commit (execute_query no hace commit).
        # Atomic increment with RETURNING; execute_write hace commit y devuelve ultimo_numero.
        numero = self.db.execute_write(
            """UPDATE secuencias 
               SET ultimo_numero = ultimo_numero + 1 
               WHERE serie = %s AND terminal_id = %s
               RETURNING ultimo_numero""",
            (serie, terminal_id)
        )
        if numero:
            return f"{serie}{terminal_id}-{int(numero):06d}"

        # Fallback: si UPDATE no afectó fila, leer valor actual
        fallback_result = self.db.execute_query(
            "SELECT ultimo_numero FROM secuencias WHERE serie = %s AND terminal_id = %s",
            (serie, terminal_id)
        )
        if fallback_result:
            numero = fallback_result[0]['ultimo_numero']
            return f"{serie}{terminal_id}-{numero:06d}"
        return f"{serie}{terminal_id}-000001"

    def open_turn(self, user_id, initial_cash):
        """Abre un nuevo turno."""
        # ============================================================
        # VALIDACIONES
        # ============================================================
        # Validar user_id
        if user_id is None:
            raise ValueError("user_id es requerido")
        if isinstance(user_id, bool):
            raise ValueError("user_id no puede ser booleano")
        if isinstance(user_id, (list, dict, tuple, set)):
            raise ValueError(f"user_id inválido: tipo {type(user_id).__name__} no soportado")
        try:
            uid = int(user_id)
            if uid <= 0:
                raise ValueError(f"user_id debe ser mayor a 0, recibido: {uid}")
        except (TypeError, ValueError) as e:
            raise ValueError(f"user_id inválido: {e}")
        
        # Validar initial_cash
        if initial_cash is None:
            raise ValueError("initial_cash es requerido")
        if isinstance(initial_cash, (list, dict, tuple, set)):
            raise ValueError(f"initial_cash inválido: tipo {type(initial_cash).__name__} no soportado")
        try:
            cash = float(initial_cash)
            if math.isnan(cash) or math.isinf(cash):
                raise ValueError("initial_cash no puede ser NaN o Infinito")
            if cash < 0:
                raise ValueError(f"initial_cash no puede ser negativo: {cash}")
        except (TypeError, ValueError) as e:
            raise ValueError(f"initial_cash inválido: {e}")
        # ============================================================
        
        # Check if user already has an open turn
        rows = self.db.execute_query("SELECT id FROM turns WHERE user_id=%s AND status='OPEN'", (uid,))
        if rows:
            self.current_turn_id = rows[0]['id']
            return self.current_turn_id

        sql = """
            INSERT INTO turns (user_id, start_timestamp, initial_cash, status)
            VALUES (%s, %s, %s, 'OPEN')
        """
        self.current_turn_id = self.db.execute_write(sql, (uid, datetime.now().isoformat(), cash))

        # Cache invalidation after database write
        if CACHE_ENABLED:
            try:
                query_cache.clear()
            except Exception as e:
                logger.warning(f"Cache clear failed: {e}")

        return self.current_turn_id

    def close_turn(self, user_id, final_cash, notes=None):
        """Cierra el turno actual y calcula diferencias."""
        if not self.current_turn_id:
            # Buscar último abierto
            rows = self.db.execute_query("SELECT id, initial_cash FROM turns WHERE user_id=%s AND status='OPEN'", (user_id,))
            if rows:
                self.current_turn_id = rows[0]['id']
                initial_cash = rows[0]['initial_cash']
            else:
                raise ValueError("No open turn found")
        else:
             # Obtener initial cash
             rows = self.db.execute_query("SELECT initial_cash FROM turns WHERE id=%s", (self.current_turn_id,))
             initial_cash = rows[0]['initial_cash'] if rows else 0.0

        # Calcular ventas del sistema en este turno (solo efectivo para expected_cash)
        sales_rows = self.db.execute_query("""
            SELECT SUM(total) as total_sales 
            FROM sales 
            WHERE turn_id = %s AND payment_method = 'cash'
        """, (self.current_turn_id,))
        
        system_sales = sales_rows[0]['total_sales'] or 0.0 if sales_rows else 0.0
        
        # NUEVO: Obtener desglose por método de pago
        payment_breakdown_rows = self.db.execute_query("""
            SELECT 
                payment_method,
                COUNT(*) as transaction_count,
                SUM(total) as total_amount
            FROM sales
            WHERE turn_id = %s
            GROUP BY payment_method
        """, (self.current_turn_id,))
        
        # Convertir a diccionario para fácil acceso
        payment_breakdown = {}
        total_sales_all_methods = 0.0
        for row in payment_breakdown_rows:
            method = row['payment_method'] or 'cash'
            payment_breakdown[method] = {
                'count': row['transaction_count'],
                'total': float(row['total_amount'] or 0.0)
            }
            total_sales_all_methods += float(row['total_amount'] or 0.0)
        
        # Calcular movimientos de efectivo (Entradas - Salidas)
        movements_rows = self.db.execute_query("""
            SELECT 
                SUM(CASE WHEN type = 'in' THEN amount ELSE 0 END) as total_in,
                SUM(CASE WHEN type = 'out' THEN amount ELSE 0 END) as total_out
            FROM cash_movements
            WHERE turn_id = %s
        """, (self.current_turn_id,))
        
        total_in = movements_rows[0]['total_in'] or 0.0 if movements_rows else 0.0
        total_out = movements_rows[0]['total_out'] or 0.0 if movements_rows else 0.0
        
        expected_cash = initial_cash + system_sales + total_in - total_out
        difference = final_cash - expected_cash
        
        # Cerrar con notes
        sql = """
            UPDATE turns
            SET end_timestamp=%s, final_cash=%s, system_sales=%s, difference=%s, status='CLOSED', notes=%s
            WHERE id=%s
        """
        self.db.execute_write(sql, (
            datetime.now().isoformat(),
            final_cash,
            system_sales,
            difference,
            notes or "",
            self.current_turn_id
        ))

        # Cache invalidation after database write
        if CACHE_ENABLED:
            try:
                query_cache.clear()
            except Exception as e:
                logger.warning(f"Cache clear failed: {e}")

        self.current_turn_id = None
        return {
            "expected_cash": expected_cash,
            "difference": difference,
            "system_sales": system_sales,
            "total_in": total_in,
            "total_out": total_out,
            "initial_cash": initial_cash,
            "payment_breakdown": payment_breakdown,
            "total_sales_all_methods": total_sales_all_methods
        }

    def add_to_cart(self, identifier: str, qty: float = 1.0) -> Dict[str, Any]:
        """
        Agrega producto al carrito por SKU o ID.
        Valida existencia y stock disponible.
        """
        # 1. Buscar Producto
        rows = self.db.execute_query("SELECT * FROM products WHERE sku = %s", (identifier,))
        if not rows:
            try:
                rows = self.db.execute_query("SELECT * FROM products WHERE id = %s", (int(identifier),))
            except (ValueError, TypeError):
                # identifier is not numeric (e.g., a barcode string)
                # This is expected behavior - product lookup will fail below
                pass
            
        if not rows:
            raise ValueError(f"Producto no encontrado: {identifier}")
        
        product = dict(rows[0])

        # 2. Validar Stock
        current_stock = float(product.get('stock') or 0)
        sale_type = product.get('sale_type', 'unit')
        sku = product.get('sku', '')
        is_kit = product.get('is_kit', False) or sale_type == 'kit'
        is_common_product = sku.startswith('COM-') or sku.startswith('COMUN-')

        # Calcular cuánto ya tenemos en el carrito de este producto
        in_cart_qty = sum(item['qty'] for item in self.current_cart if item['product_id'] == product['id'])
        total_requested = in_cart_qty + qty

        # CRITICAL FIX: Validate stock for KIT products against their components
        if is_kit:
            components = self.get_kit_components(product['id'])
            for comp in components:
                comp_product_id = comp.get('child_product_id')
                comp_qty = float(comp.get('qty', 1.0))
                total_comp_qty = total_requested * comp_qty

                # Get component stock
                comp_product = self.get_product_by_id(comp_product_id)
                if comp_product:
                    comp_stock = float(comp_product.get('stock', 0))
                    comp_sku = comp_product.get('sku', '')
                    is_comp_common = comp_sku.startswith('COM-') or comp_sku.startswith('COMUN-')

                    if not is_comp_common and comp_stock < total_comp_qty:
                        comp_name = comp_product.get('name', f"ID {comp_product_id}")
                        raise ValueError(
                            f"Stock insuficiente de componente '{comp_name}' para KIT '{product['name']}'. "
                            f"Disponible: {comp_stock}, Necesario: {total_comp_qty}"
                        )
        elif not is_common_product and sale_type not in ['granel', 'weight']:
            # Regular product stock validation
            if total_requested > current_stock:
                raise ValueError(f"Stock insuficiente. Disponible: {current_stock}, Solicitado: {total_requested}")

        # 3. Agregar al Carrito
        price = Money(product['price'])
        
        item = {
            "product_id": product['id'],
            "sku": product['sku'],
            "name": product['name'],
            "qty": qty,
            "price": price,
            "total": price * qty
        }
        self.current_cart.append(item)
        return item

    def get_cart_total(self) -> float:
        totals = self.calculate_cart_totals()
        return float(totals['total'].amount)

    def checkout(self, payment_method: str, amount_paid: float) -> Dict[str, float]:
        if not self.current_cart:
            raise ValueError("Cart is empty")

        # CRITICAL FIX: Validate turn is open before creating sale
        # This matches validation in create_sale_transaction()
        if not self.current_turn_id:
            # Try to find any open turn for consistency
            turn_rows = self.db.execute_query(
                "SELECT id FROM turns WHERE status = 'OPEN' ORDER BY id DESC LIMIT 1"
            )
            if turn_rows:
                self.current_turn_id = turn_rows[0]['id']
            else:
                raise ValueError(
                    "No hay turno abierto. Debe abrir un turno antes de crear ventas. "
                    "Esto es necesario para registrar correctamente los movimientos de efectivo."
                )

        totals = self.calculate_cart_totals()
        total_val = float(totals['total'].amount)
        
        if amount_paid < total_val:
             raise ValueError("Insufficient payment")

        change = amount_paid - total_val
        
        # Guardar Venta
        # CRITICAL FIX: Todas las operaciones en una sola transacción atómica
        # Si falla cualquier operación, TODO se revierte (rollback)
        timestamp = datetime.now().isoformat()
        customer_id = self.current_customer['id'] if self.current_customer else None
        
        # Construir TODAS las operaciones en una lista
        ops = []
        
        # 1. Crear venta con RETURNING id
        sale_sql = """
            INSERT INTO sales (timestamp, subtotal, tax, total, payment_method, customer_id, synced)
            VALUES (%s, %s, %s, %s, %s, %s, 0)
            RETURNING id
        """
        ops.append((sale_sql, (
            timestamp,
            float(totals['subtotal'].amount),
            float(totals['tax'].amount),
            total_val,
            payment_method,
            customer_id
        )))
        
        # 2. Guardar Items y Actualizar Stock usando subquery para obtener sale_id
        item_sql = """INSERT INTO sale_items (sale_id, product_id, qty, price, subtotal, total, synced)
            VALUES ((SELECT id FROM sales WHERE timestamp = %s AND customer_id = %s ORDER BY id DESC LIMIT 1), %s, %s, %s, %s, 0)"""
        stock_sql = "UPDATE products SET stock = stock - %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s"

        for item in self.current_cart:
            item_total = float(item['total'].amount)
            ops.append((item_sql, (
                timestamp,
                customer_id,
                item['product_id'],
                item['qty'],
                float(item['price'].amount),
                item_total,
                item_total
            )))
            ops.append((stock_sql, (item['qty'], item['product_id'])))
        
        # Ejecutar TODO en una sola transacción atómica
        result = self.db.execute_transaction(ops, timeout=10)
        if not result.get('success'):
            raise RuntimeError("Transaction failed - sale not created")
        
        # Obtener sale_id del resultado
        inserted_ids = result.get('inserted_ids', [])
        if not inserted_ids or inserted_ids[0] is None:
            raise RuntimeError("Failed to get sale_id from transaction")
        
        sale_id = inserted_ids[0]
        
        # Reset State
        self.current_cart = []
        self.global_discount_pct = 0.0
        self.current_customer = None
        
        return {
            "sale_id": sale_id,
            "total": total_val,
            "change": change
        }

    def create_sale_transaction(self, items: List[Dict], payment_data: Dict, branch_id: int, discount: float, customer_id: Optional[int], user_id: int) -> int:
        """
        Crea una venta completa recibiendo los datos directos (sin depender del estado interno self.current_cart).
        """
        # ============================================================
        # VALIDACIONES A PRUEBA DE TONTOS (agregadas en auditoría)
        # ============================================================
        import math

        # Validar que items es una lista
        if not isinstance(items, list):
            raise ValueError("Items debe ser una lista")
        
        # Validar que hay items
        if not items or len(items) == 0:
            raise ValueError("No se puede crear una venta sin productos")
        
        # Límite razonable de items (evitar DOS)
        if len(items) > 2000:
            raise ValueError(f"Demasiados items: {len(items)}. Máximo 2000 por venta")
        
        # Validar método de pago
        valid_methods = {'cash', 'card', 'transfer', 'mixed', 'credit', 'wallet', 'gift_card'}
        payment_method = str(payment_data.get('method', 'cash')).lower()
        if payment_method not in valid_methods:
            raise ValueError(f"Método de pago inválido: '{payment_method}'. Válidos: {valid_methods}")
        
        # Validar cada item
        for idx, item in enumerate(items):
            try:
                qty = float(item.get('qty', 0))
                price = float(item.get('price', 0))
                product_id = item.get('product_id')
            except (TypeError, ValueError) as e:
                raise ValueError(f"Datos inválidos en item {idx+1}: {e}")
            
            # Validar product_id
            if product_id is None:
                raise ValueError(f"Product ID faltante en item {idx+1}")
            # Rechazar bool (True/False se pueden confundir con 1/0)
            if isinstance(product_id, bool):
                raise ValueError(f"Product ID inválido en item {idx+1}: no puede ser bool")
            # Debe ser entero positivo
            try:
                pid_int = int(product_id)
                if pid_int <= 0:
                    raise ValueError(f"Product ID inválido en item {idx+1}: debe ser mayor a 0")
            except (TypeError, ValueError):
                raise ValueError(f"Product ID inválido en item {idx+1}: '{product_id}'")
            
            # Validar que no sea NaN o Infinito
            if math.isnan(qty) or math.isinf(qty):
                raise ValueError(f"Cantidad inválida en item {idx+1}: No puede ser NaN o Infinito")
            if math.isnan(price) or math.isinf(price):
                raise ValueError(f"Precio inválido en item {idx+1}: No puede ser NaN o Infinito")
            
            # Cantidad debe ser mayor a cero (mínimo 0.001)
            if qty <= 0:
                raise ValueError(f"Cantidad inválida en item {idx+1}: {qty}. Debe ser mayor a 0")
            if qty < 0.001:
                raise ValueError(f"Cantidad muy pequeña en item {idx+1}: {qty}. Mínimo 0.001")
            
            # Límite de cantidad razonable (1 millón)
            if qty > 1000000:
                raise ValueError(f"Cantidad excesiva en item {idx+1}: {qty}. Máximo 1,000,000")
            
            # Precio no puede ser negativo
            if price < 0:
                raise ValueError(f"Precio inválido en item {idx+1}: {price}. No puede ser negativo")
            
            # Límite de precio razonable (100 millones MXN)
            if price > 100000000:
                raise ValueError(f"Precio excesivo en item {idx+1}: {price}. Máximo $100,000,000")
        
        # Validar branch_id
        if branch_id is not None and not isinstance(branch_id, int):
            try:
                branch_id = int(branch_id)
            except (ValueError, TypeError):
                raise ValueError(f"branch_id inválido: '{branch_id}'. Debe ser un número entero")
        
        # Validar discount
        if discount is not None:
            try:
                discount = float(discount)
                if math.isnan(discount) or math.isinf(discount):
                    raise ValueError("Descuento no puede ser NaN o Infinito")
                if discount < 0:
                    raise ValueError(f"Descuento inválido: {discount}. No puede ser negativo")
            except (TypeError, ValueError) as e:
                raise ValueError(f"Descuento inválido: {e}")
        
        # Validar customer_id
        if customer_id is not None:
            if isinstance(customer_id, bool):
                raise ValueError("customer_id no puede ser booleano")
            if isinstance(customer_id, (list, dict, tuple, set)):
                raise ValueError(f"customer_id inválido: tipo {type(customer_id).__name__} no soportado")
            if isinstance(customer_id, str) and not customer_id.strip():
                raise ValueError("customer_id no puede ser string vacío")
            try:
                cid = int(customer_id) if not isinstance(customer_id, int) else customer_id
                if math.isnan(float(customer_id)) or math.isinf(float(customer_id)):
                    raise ValueError("customer_id no puede ser NaN o Infinito")
                if cid <= 0:
                    raise ValueError(f"customer_id debe ser mayor a 0, recibido: {cid}")
            except (TypeError, ValueError) as e:
                raise ValueError(f"customer_id inválido: {e}")
        
        # ============================================================
        # FIN VALIDACIONES
        # ============================================================
        
        # ============================================================
        # CRITICAL FIX: Pre-bloquear productos con SELECT FOR UPDATE NOWAIT
        # Esto evita locks y deadlocks en producción
        # ============================================================
        product_ids = [item.get('product_id') for item in items if item.get('product_id')]
        if product_ids:
            try:
                placeholders = ','.join(['%s'] * len(product_ids))
                lock_query = f"""
                    SELECT id, name, stock, sku
                    FROM products 
                    WHERE id IN ({placeholders}) 
                    FOR UPDATE NOWAIT
                """
                locked_products = self.db.execute_query(lock_query, tuple(product_ids))
                
                # Verificar stock después de lock (doble verificación)
                locked_dict = {p['id']: p for p in locked_products}
                component_ids_to_check = []
                
                for item in items:
                    p_id = item.get('product_id')
                    if p_id and p_id in locked_dict:
                        product = locked_dict[p_id]
                        qty = float(item.get('qty', 0))
                        current_stock = float(product.get('stock', 0))
                        sale_type = product.get('sale_type', 'unit')
                        sku = product.get('sku', '')
                        is_kit = product.get('is_kit', False) or sale_type == 'kit'
                        
                        # EXCLUIR de validación productos comunes y granel
                        is_common_product = sku.startswith('COM-') or sku.startswith('COMUN-')
                        
                        if is_kit:
                            # CRITICAL FIX: Verificar stock de componentes KIT
                            components = self.get_kit_components(p_id)
                            for comp in components:
                                comp_product_id = comp.get('child_product_id')
                                comp_qty = float(comp.get('qty', 1.0))
                                total_comp_qty = qty * comp_qty  # qty_kits * qty_per_kit
                                component_ids_to_check.append((comp_product_id, total_comp_qty, p_id, qty))
                        elif not is_common_product and sale_type not in ['granel', 'weight']:
                            if current_stock < qty:
                                product_name = product.get('name', f"ID {p_id}")
                                raise ValueError(f"Stock insuficiente para '{product_name}'. Disponible: {current_stock}, Solicitado: {qty}")
                
                # CRITICAL FIX: Verificar stock de componentes KIT
                if component_ids_to_check:
                    comp_product_ids = list(set([comp_id for comp_id, _, _, _ in component_ids_to_check]))
                    if comp_product_ids:
                        comp_placeholders = ','.join(['%s'] * len(comp_product_ids))
                        comp_lock_query = f"""
                            SELECT id, name, stock, sku
                            FROM products 
                            WHERE id IN ({comp_placeholders}) 
                            FOR UPDATE NOWAIT
                        """
                        try:
                            locked_components = self.db.execute_query(comp_lock_query, tuple(comp_product_ids))
                            locked_components_dict = {c['id']: c for c in locked_components}
                            
                            for comp_product_id, total_comp_qty, kit_product_id, kit_qty in component_ids_to_check:
                                if comp_product_id in locked_components_dict:
                                    comp_product = locked_components_dict[comp_product_id]
                                    comp_stock = float(comp_product.get('stock', 0))
                                    comp_sku = comp_product.get('sku', '')
                                    is_comp_common = comp_sku.startswith('COM-') or comp_sku.startswith('COMUN-')
                                    
                                    if not is_comp_common and comp_stock < total_comp_qty:
                                        comp_name = comp_product.get('name', f"ID {comp_product_id}")
                                        kit_name = locked_dict.get(kit_product_id, {}).get('name', f"KIT {kit_product_id}")
                                        raise ValueError(
                                            f"Stock insuficiente de componente '{comp_name}' para KIT '{kit_name}'. "
                                            f"Disponible: {comp_stock}, Necesario: {total_comp_qty} (KITs: {kit_qty})"
                                        )
                        except Exception as comp_e:
                            error_str = str(comp_e).lower()
                            if any(keyword in error_str for keyword in ['lock', 'timeout', 'could not obtain', 'waiting', 'deadlock']):
                                raise RuntimeError(f"Producto bloqueado por otra transacción. Intente nuevamente.") from comp_e
                            raise RuntimeError(f"Error verificando componentes KIT: {type(comp_e).__name__}: {comp_e}") from comp_e
            except Exception as e:
                error_str = str(e).lower()
                if any(keyword in error_str for keyword in ['lock', 'timeout', 'could not obtain', 'waiting', 'deadlock']):
                    raise RuntimeError(
                        "Uno o más productos están siendo procesados por otra transacción. "
                        "Por favor, intente nuevamente en unos segundos."
                    ) from e
                raise RuntimeError(f"Error procesando venta: {type(e).__name__}: {e}") from e
        
        # ============================================================
        # FIN PRE-BLOQUEO
        # ============================================================
        
        # 1. Calcular Totales
        subtotal = 0.0
        tax_total = 0.0
        
        # Validar stock y calcular
        for item in items:
            qty = float(item.get('qty', 0))
            
            # FIXED: Use wholesale price when is_wholesale is True
            is_wholesale = item.get('is_wholesale', False)
            if is_wholesale and item.get('price_wholesale'):
                price = float(item.get('price_wholesale', 0))
            else:
                price = float(item.get('base_price', item.get('price', 0)))
            
            # CRITICAL FIX: Si price_includes_tax es True, el precio YA incluye IVA
            # Por lo tanto, debemos calcular el subtotal SIN IVA para que el IVA se calcule correctamente
            price_includes_tax = item.get('price_includes_tax', True)  # Default True
            if self.TAX_RATE <= -1:
                raise ValueError("Invalid TAX_RATE: cannot be <= -1 (would cause division by zero)")
            if price_includes_tax and price > 0:
                # El precio incluye IVA, calcular precio sin IVA para el subtotal
                price_without_tax = price / (1 + self.TAX_RATE)
            else:
                # El precio NO incluye IVA, usar tal cual
                price_without_tax = price
            
            # FIXED: Apply line discount using Decimal for monetary precision
            # CRITICAL: Normalize -0.0 to 0.0 and clamp negative discounts to 0
            from decimal import Decimal, ROUND_HALF_UP
            raw_line_discount_str = str(item.get('discount', 0)) if not is_wholesale else '0'
            raw_line_discount_dec = Decimal(raw_line_discount_str)
            # Use tolerance-based comparison for floating-point zero check
            if abs(raw_line_discount_dec) < Decimal('0.001'):
                line_discount = 0.0  # Normalize -0.0 and near-zero to 0.0
            else:
                line_discount = float(max(Decimal('0'), raw_line_discount_dec).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            
            # Recalcular total de item para seguridad (usar precio sin IVA para subtotal)
            item_total = (qty * price_without_tax) - line_discount
            subtotal += item_total
            
            # Validar stock ANTES de la transacción
            prod = self.get_product_by_id(item.get('product_id'))
            if prod:
                current_stock = float(prod.get('stock', 0))
                sale_type = prod.get('sale_type', 'unit')
                sku = prod.get('sku', '')
                
                # EXCLUIR de validación:
                # 1. Productos comunes (creados al momento de venta, SKU inicia con COM-)
                # 2. Productos a granel/peso
                # 3. Productos kit
                is_common_product = sku.startswith('COM-') or sku.startswith('COMUN-')
                
                if not is_common_product and sale_type not in ['granel', 'weight'] and not prod.get('is_kit'):
                    if current_stock < qty:
                        product_name = prod.get('name', f"ID {prod.get('id')}")
                        raise ValueError(f"Stock insuficiente para '{product_name}'. Disponible: {current_stock}, Solicitado: {qty}")

        # Aplicar Descuento Global usando Decimal para precisión monetaria
        # CRITICAL FIX: La UI pasa el MONTO del descuento global ya calculado sobre subtotal (SIN IVA)
        # El descuento global se calcula en _refresh_table() sobre subtotal (sin IVA) para consistencia
        from decimal import Decimal, ROUND_HALF_UP
        discount_amount = float(Decimal(str(discount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

        # CRITICAL FIX: El subtotal es SIN IVA (suma de item_total = (qty * price) - line_discount)
        # Aplicar descuento global sobre subtotal (sin IVA)
        subtotal_after_discount = max(subtotal - discount_amount, 0)
        
        # Calcular IVA sobre el subtotal después del descuento global
        tax_total = subtotal_after_discount * self.TAX_RATE
        total_gross = subtotal_after_discount + tax_total
        
        # Para BD: base_val es el subtotal después del descuento (sin IVA)
        base_val = subtotal_after_discount

        # Valores finales para DB
        total_val = float(total_gross)
        
        # 2. Crear UUID único para la venta
        sale_uuid = str(uuid.uuid4())
        
        # 3. CRITICAL FIX: Execute sale INSERT FIRST to get sale_id
        #    last_insert_rowid() doesn't work in batch transactions
        # FIXED: Dynamically get current turn for user instead of relying on stale self.current_turn_id
        turn_id = None
        if user_id:
            turn_rows = self.db.execute_query(
                "SELECT id FROM turns WHERE user_id = %s AND status = 'OPEN' ORDER BY id DESC LIMIT 1",
                (user_id,)
            )
            if turn_rows:
                turn_id = turn_rows[0]['id']
        
        # CRITICAL FIX: Validar que hay turno abierto antes de crear venta
        # Esto previene ventas con turn_id = None que causan problemas en reportes
        if not turn_id:
            raise ValueError(
                "No hay turno abierto. Debe abrir un turno antes de crear ventas. "
                "Esto es necesario para registrar correctamente los movimientos de efectivo y generar reportes precisos."
            )
        
        # Extract payment details from payment_data
        payment_method = payment_data.get('method', 'cash')
        cash_received = 0.0
        payment_reference = payment_data.get('reference', '')
        card_last4 = ''
        auth_code = ''
        transfer_reference = ''
        mixed_cash = 0.0
        mixed_card = 0.0
        mixed_transfer = 0.0
        mixed_wallet = 0.0
        mixed_gift_card = 0.0
        
        # Process payment-specific data
        if payment_method == 'cash':
            cash_received = float(payment_data.get('amount', 0))
        elif payment_method == 'card':
            # Extract last 4 digits from reference if present
            ref = payment_data.get('reference', '')
            if ref and len(ref) >= 4:
                card_last4 = ref[-4:]
            auth_code = ref
        elif payment_method == 'transfer':
            transfer_reference = payment_data.get('reference', '')
        elif payment_method == 'mixed':
            # Get mixed payment breakdown
            mixed_breakdown = payment_data.get('mixed_breakdown', {})
            mixed_cash = float(mixed_breakdown.get('cash', 0))
            mixed_card = float(mixed_breakdown.get('card', 0))
            mixed_transfer = float(mixed_breakdown.get('transfer', 0))
            mixed_wallet = float(mixed_breakdown.get('wallet', 0))
            mixed_gift_card = float(mixed_breakdown.get('gift_card', 0))

            # CRITICAL FIX: Validate mixed payment amounts (no negative, NaN, or Infinity)
            mixed_payment_types = [
                ('efectivo', mixed_cash),
                ('tarjeta', mixed_card),
                ('transferencia', mixed_transfer),
                ('monedero', mixed_wallet),
                ('tarjeta regalo', mixed_gift_card)
            ]
            for pay_type, pay_amount in mixed_payment_types:
                if math.isnan(pay_amount) or math.isinf(pay_amount):
                    raise ValueError(f"Monto de pago inválido (NaN/Infinito) no permitido: {pay_type}")
                if pay_amount < 0:
                    raise ValueError(f"Monto de pago negativo no permitido: {pay_type} = ${pay_amount:.2f}")

            # CRITICAL FIX: Validate sum of mixed payments equals total (with cent tolerance)
            mixed_sum = mixed_cash + mixed_card + mixed_transfer + mixed_wallet + mixed_gift_card
            tolerance = 0.02  # 2 centavos de tolerancia por redondeo
            if abs(mixed_sum - total_val) > tolerance:
                raise ValueError(
                    f"La suma de pagos mixtos (${mixed_sum:.2f}) no coincide con el total de la venta (${total_val:.2f}). "
                    f"Diferencia: ${abs(mixed_sum - total_val):.2f}"
                )

            # CRITICAL FIX: Validate wallet balance BEFORE processing if wallet payment is used
            if mixed_wallet > 0:
                if not customer_id:
                    raise ValueError(
                        "No se puede usar pago con monedero sin un cliente asignado a la venta"
                    )
                current_wallet_balance = self.get_wallet_balance(customer_id)
                if current_wallet_balance < mixed_wallet:
                    raise ValueError(
                        f"Saldo insuficiente en monedero del cliente. "
                        f"Disponible: ${current_wallet_balance:.2f}, Solicitado: ${mixed_wallet:.2f}"
                    )

            # Build payment reference from breakdown
            refs = []
            if mixed_breakdown.get('card_ref'):
                refs.append(f"Tarj: {mixed_breakdown['card_ref']}")
                card_last4 = mixed_breakdown['card_ref'][-4:] if len(mixed_breakdown['card_ref']) >= 4 else ''
            if mixed_breakdown.get('transfer_ref'):
                refs.append(f"Transf: {mixed_breakdown['transfer_ref']}")
            payment_reference = "; ".join(refs) if refs else payment_reference
        
        # DUAL SERIES FISCAL SYSTEM: Determine serie and get folio
        # Get invoice request flag from payment data
        cliente_pide_factura = payment_data.get('requiere_factura', False)
        # CRITICAL: Pass mixed_breakdown to ensure bank payments go to Serie A
        mixed_breakdown_for_serie = payment_data.get('mixed_breakdown', {}) if payment_method == 'mixed' else None
        serie = self.determine_serie(payment_method, cliente_pide_factura, mixed_breakdown_for_serie)
        
        # Get terminal_id from turn (for unique folios per terminal)
        terminal_id = 1  # Default
        if turn_id:
            turn_rows = self.db.execute_query(
                "SELECT terminal_id FROM turns WHERE id = %s", (turn_id,)
            )
            if turn_rows:
                turn_data = dict(turn_rows[0])  # Convert sqlite3.Row to dict
                if turn_data.get('terminal_id'):
                    terminal_id = turn_data['terminal_id']

        # FIX 2026-02-01: Folio se genera DENTRO de la transacción atómica (ver CTE más abajo)
        # Esto evita que se pierdan folios si la transacción falla
        # folio_visible se genera con CTE en el INSERT para máxima atomicidad

        # Asegurar que la secuencia exista atomically (ON CONFLICT eliminates TOCTOU race)
        try:
            self.db.execute_write(
                "INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion, synced) "
                "VALUES (%s, %s, 0, %s, 0) ON CONFLICT (serie, terminal_id) DO NOTHING",
                (serie, terminal_id, f"{serie} Terminal {terminal_id}")
            )
        except Exception as e:
            error_str = str(e).lower()
            if 'duplicate' not in error_str and 'unique' not in error_str:
                raise

        # ============================================================
        # CRITICAL FIX: Construir TODA la transacción atómica
        # Incluye: secuencia folio, venta, items, stock, crédito, historial
        # ============================================================
        ops = []

        # Obtener identificador de PC de origen
        try:
            from app.utils.machine_identifier import get_machine_identifier_safe
            origin_pc = get_machine_identifier_safe()
        except Exception as e:
            origin_pc = "UNKNOWN-PC"
            logger.debug("Error getting origin_pc, using fallback: %s", e)

        # Verificar si la columna origin_pc existe antes de incluirla en el INSERT
        origin_pc_column_exists = False
        try:
            check_result = self.db.execute_query("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'sales'
                AND column_name = 'origin_pc'
            """)
            origin_pc_column_exists = len(check_result) > 0
        except Exception as e:
            logger.debug("Error checking origin_pc column: %s", e)
            # Si falla la verificación, asumimos que no existe
        
        # A. Crear venta con RETURNING id (primera operación)
        # FIX 2026-02-01: Usar CTE para generar folio ATÓMICAMENTE dentro de la transacción
        # Si la transacción falla, el folio NO se pierde (todo se revierte)
        if origin_pc_column_exists:
            sale_sql = """
            WITH new_folio AS (
                UPDATE secuencias
                SET ultimo_numero = ultimo_numero + 1, synced = 0
                WHERE serie = %s AND terminal_id = %s
                RETURNING ultimo_numero
            )
            INSERT INTO sales (
                uuid, timestamp, subtotal, tax, total, discount, payment_method,
                customer_id, user_id, turn_id,
                cash_received, card_last4, auth_code, transfer_reference,
                mixed_cash, mixed_card, mixed_transfer, mixed_wallet, mixed_gift_card,
                payment_reference, serie, folio_visible, origin_pc, synced
            )
            SELECT %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                   %s || %s || '-' || LPAD((SELECT ultimo_numero FROM new_folio)::text, 6, '0'),
                   %s, 0
            RETURNING id"""

            sale_params = (
                serie, terminal_id,  # Para el CTE de secuencia
                sale_uuid, base_val, tax_total, total_val, discount,
                payment_method, customer_id, user_id, turn_id,
                cash_received, card_last4, auth_code, transfer_reference,
                mixed_cash, mixed_card, mixed_transfer, mixed_wallet, mixed_gift_card,
                payment_reference, serie,
                serie, terminal_id,  # Para construir el folio: A1-000001
                origin_pc
            )
        else:
            # Si la columna no existe, crear INSERT sin origin_pc
            sale_sql = """
            WITH new_folio AS (
                UPDATE secuencias
                SET ultimo_numero = ultimo_numero + 1, synced = 0
                WHERE serie = %s AND terminal_id = %s
                RETURNING ultimo_numero
            )
            INSERT INTO sales (
                uuid, timestamp, subtotal, tax, total, discount, payment_method,
                customer_id, user_id, turn_id,
                cash_received, card_last4, auth_code, transfer_reference,
                mixed_cash, mixed_card, mixed_transfer, mixed_wallet, mixed_gift_card,
                payment_reference, serie, folio_visible, synced
            )
            SELECT %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                   %s || %s || '-' || LPAD((SELECT ultimo_numero FROM new_folio)::text, 6, '0'),
                   0
            RETURNING id"""

            sale_params = (
                serie, terminal_id,  # Para el CTE de secuencia
                sale_uuid, base_val, tax_total, total_val, discount,
                payment_method, customer_id, user_id, turn_id,
                cash_received, card_last4, auth_code, transfer_reference,
                mixed_cash, mixed_card, mixed_transfer, mixed_wallet, mixed_gift_card,
                payment_reference, serie,
                serie, terminal_id  # Para construir el folio: A1-000001
            )

        ops.append((sale_sql, sale_params))
        
        # B. Preparar validaciones de stock (se ejecutarán dentro de la transacción)
        stock_validations = []  # Lista de (product_id, qty, product_name) para validar después
        
        # C. Insertar Items y Actualizar Stock usando el sale_id explícito
        # NOTA: item_sql es código legado, usamos item_sql_with_subquery abajo
        item_sql = "INSERT INTO sale_items (sale_id, product_id, qty, price, subtotal, total, sat_clave_prod_serv, sat_descripcion, discount, name, synced) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)"
        
        for item in items:
            p_id = item.get('product_id')
            qty = float(item.get('qty', 0))
            
            # FIXED: Use wholesale price when is_wholesale is True
            is_wholesale = item.get('is_wholesale', False)
            if is_wholesale and item.get('price_wholesale'):
                price = float(item.get('price_wholesale', 0))
            else:
                # FIXED: Usar base_price si está disponible (precio después de cambio manual)
                # Si no, usar price como fallback
                price = float(item.get('base_price', item.get('price', 0)))
            
            # CRITICAL FIX: Si price_includes_tax es True, el precio YA incluye IVA
            # Por lo tanto, debemos guardarlo SIN IVA (base_without_tax) para que se muestre correctamente
            # en tickets e historial. El precio mostrado será el precio con IVA (price), pero guardado sin IVA.
            price_includes_tax = item.get('price_includes_tax', True)  # Default True
            if self.TAX_RATE <= -1:
                raise ValueError("Invalid TAX_RATE: cannot be <= -1 (would cause division by zero)")
            if price_includes_tax and price > 0:
                # El precio incluye IVA, calcular precio sin IVA para guardar
                price = price / (1 + self.TAX_RATE)
            
            # FIXED: Apply line discount using Decimal for monetary precision
            # Cuando el precio se modifica manualmente, el descuento se establece en 0
            # porque el precio ya refleja el cambio (base_price = new_price)
            # CRITICAL: Normalize -0.0 to 0.0 and clamp negative discounts to 0
            from decimal import Decimal, ROUND_HALF_UP
            raw_line_discount_dec = Decimal(str(item.get('discount', 0)))
            # Use tolerance-based comparison for floating-point zero check
            if abs(raw_line_discount_dec) < Decimal('0.001'):
                line_discount = 0.0  # Normalize -0.0 and near-zero to 0.0
            else:
                line_discount = float(max(Decimal('0'), raw_line_discount_dec).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            total_line = (qty * price) - line_discount

            sale_type = item.get('sale_type', 'unit')
            
            # Get product name from item or fetch from product
            product_name = item.get('name')
            
            # Get SAT code and description from item or fetch from product
            sat_code = item.get('sat_clave_prod_serv')
            sat_desc = item.get('sat_descripcion')
            if (not sat_code or not sat_desc or not product_name) and p_id:
                product = self.get_product_by_id(p_id)
                if product:
                    sat_code = sat_code or product.get('sat_clave_prod_serv', '01010101')
                    sat_desc = sat_desc or product.get('sat_descripcion', '')
                    product_name = product_name or product.get('name', 'Producto')
            sat_code = sat_code or '01010101'
            sat_desc = sat_desc or ''
            product_name = product_name or 'Producto'
            
            # CRITICAL FIX: Usar subquery para obtener sale_id de la primera operación
            # Esto permite que todo esté en una sola transacción
            # NOTA: La subquery debe ejecutarse DESPUÉS del INSERT de sales en la misma transacción
            # PostgreSQL permite ver cambios no confirmados dentro de la misma transacción
            # ON CONFLICT: Si el producto ya existe en la venta, sumar cantidad y subtotal
            # Esto maneja el caso donde el carrito tiene el mismo producto en múltiples líneas
            item_sql_with_subquery = """INSERT INTO sale_items (sale_id, product_id, qty, price, subtotal, total, sat_clave_prod_serv, sat_descripcion, discount, name, synced)
                VALUES (
                    (SELECT id FROM sales WHERE uuid = %s ORDER BY id DESC LIMIT 1),
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, 0
                )
                ON CONFLICT (sale_id, product_id) DO UPDATE SET
                    qty = sale_items.qty + EXCLUDED.qty,
                    subtotal = sale_items.subtotal + EXCLUDED.subtotal,
                    total = sale_items.total + EXCLUDED.total,
                    discount = sale_items.discount + EXCLUDED.discount"""
            ops.append((item_sql_with_subquery, (sale_uuid, p_id, qty, price, total_line, total_line, sat_code, sat_desc, line_discount, product_name)))

            # Stock Deduction Logic
            # CRITICAL FIX: Validar stock DENTRO de la transacción usando SELECT FOR UPDATE
            # Esto previene condiciones de carrera entre validación y actualización
            prod = self.get_product_by_id(p_id)
            prod_sale_type = prod.get('sale_type', 'unit') if prod else 'unit'
            sku = prod.get('sku', '') if prod else ''
            is_common_product = sku.startswith('COM-') or sku.startswith('COMUN-')
            is_kit = prod.get('is_kit', False) if prod else False

            # EXCLUIR de validación de stock:
            # 1. Productos comunes (creados al momento de venta, SKU inicia con COM-)
            # 2. Productos a granel/peso
            # 3. Productos kit (se validan componentes después)
            if prod and not is_common_product and prod_sale_type not in ['granel', 'weight'] and not is_kit:
                # Bloquear fila y validar stock dentro de la transacción
                stock_check_sql = "SELECT stock, name FROM products WHERE id = %s FOR UPDATE"
                ops.append((stock_check_sql, (p_id,)))
                stock_validations.append((p_id, qty, product_name))

            # Determinar si es kit (usando tanto sale_type del item como is_kit del producto)
            is_kit_sale = sale_type == 'kit' or is_kit

            if is_kit_sale:
                # For KIT products, deduct stock from components instead
                components = self.get_kit_components(p_id)
                for comp in components:
                    comp_qty = float(comp.get('qty', 1.0))
                    comp_product_id = comp.get('child_product_id')
                    total_comp_qty = qty * comp_qty  # qty_kits * qty_per_kit

                    stock_sql = "UPDATE products SET stock = stock - %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
                    ops.append((stock_sql, (total_comp_qty, comp_product_id)))

                    movement_sql = """INSERT INTO inventory_movements
                        (product_id, movement_type, type, quantity, reason, reference_type, reference_id, user_id, branch_id, timestamp, synced)
                        VALUES (%s, 'OUT', 'sale', %s, %s, 'sale', (SELECT id FROM sales WHERE uuid = %s LIMIT 1), %s, %s, NOW(), 0)"""
                    ops.append((movement_sql, (comp_product_id, total_comp_qty, f"Venta Kit UUID:{sale_uuid[:8]}", sale_uuid, user_id, branch_id)))
            elif not is_common_product:
                # For regular products (NOT common products), deduct normally
                # Productos comunes tienen stock=999999 y no deben descontarse
                stock_sql = "UPDATE products SET stock = stock - %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
                ops.append((stock_sql, (qty, p_id)))

                movement_sql = """INSERT INTO inventory_movements
                    (product_id, movement_type, type, quantity, reason, reference_type, reference_id, user_id, branch_id, timestamp, synced)
                    VALUES (%s, 'OUT', 'sale', %s, %s, 'sale', (SELECT id FROM sales WHERE uuid = %s LIMIT 1), %s, %s, NOW(), 0)"""
                ops.append((movement_sql, (p_id, qty, f"Venta UUID:{sale_uuid[:8]}", sale_uuid, user_id, branch_id)))
            # else: Producto común - NO descontar stock (tienen stock=999999 artificial)

        # C. Actualizar Crédito/Monedero
        # CRITICAL FIX 2026-02-03: Información de crédito para validación dentro de la transacción
        credit_validation_info = None

        if payment_data.get('method') == 'credit' and customer_id:
            # PRE-VALIDACIÓN: Verificar que el cliente existe y tiene crédito habilitado
            # Esta verificación rápida evita iniciar transacciones innecesarias
            pre_check = self.db.execute_query(
                "SELECT credit_authorized FROM customers WHERE id = %s",
                (customer_id,)
            )
            if not pre_check:
                raise ValueError("Cliente no encontrado para venta a crédito")

            credit_enabled = pre_check[0].get('credit_authorized', True)
            if credit_enabled is False or credit_enabled == 0:
                raise ValueError("El cliente no tiene crédito habilitado")

            # CRITICAL FIX: Agregar SELECT FOR UPDATE a la transacción para obtener
            # balance y límite con lock, previniendo race conditions
            credit_lock_sql = "SELECT credit_balance, credit_limit FROM customers WHERE id = %s FOR UPDATE"
            ops.append((credit_lock_sql, (customer_id,)))

            # Guardar info para validación en callback
            credit_validation_info = {
                'customer_id': customer_id,
                'sale_amount': total_val
            }

            # Update credit balance (se ejecutará DESPUÉS de la validación)
            credit_sql = "UPDATE customers SET credit_balance = credit_balance + %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
            ops.append((credit_sql, (total_val, customer_id)))
            
            # Record in credit_history
            # CRITICAL FIX: Verificar si user_id existe antes de INSERT
            has_user_id = self._ensure_column_exists("credit_history", "user_id", "INTEGER")
            # CRITICAL FIX: Verificar si movement_type existe antes de INSERT
            has_movement_type = self._ensure_column_exists("credit_history", "movement_type", "TEXT")
            history_notes = f"Venta a crédito - UUID: {sale_uuid}"

            # CRITICAL FIX 2026-02-03: Usar subquery para obtener balance_before y calcular balance_after
            # dentro de la misma transacción, garantizando consistencia con el UPDATE de credit_balance
            # NOTA: balance_after = credit_balance actual (ya actualizado por el UPDATE anterior)
            #       balance_before = credit_balance - total_val (valor antes del UPDATE)
            if has_user_id:
                if has_movement_type:
                    history_sql = """INSERT INTO credit_history
                        (customer_id, transaction_type, movement_type, amount, balance_before, balance_after, timestamp, notes, user_id)
                        VALUES (%s, 'CHARGE', 'CHARGE', %s,
                            (SELECT credit_balance - %s FROM customers WHERE id = %s),
                            (SELECT credit_balance FROM customers WHERE id = %s),
                            NOW(), %s, %s)"""
                    ops.append((history_sql, (customer_id, total_val, total_val, customer_id, customer_id, history_notes, user_id)))
                else:
                    history_sql = """INSERT INTO credit_history
                        (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes, user_id)
                        VALUES (%s, 'CHARGE', %s,
                            (SELECT credit_balance - %s FROM customers WHERE id = %s),
                            (SELECT credit_balance FROM customers WHERE id = %s),
                            NOW(), %s, %s)"""
                    ops.append((history_sql, (customer_id, total_val, total_val, customer_id, customer_id, history_notes, user_id)))
            else:
                # Fallback: INSERT sin user_id
                if has_movement_type:
                    history_sql = """INSERT INTO credit_history
                        (customer_id, transaction_type, movement_type, amount, balance_before, balance_after, timestamp, notes)
                        VALUES (%s, 'CHARGE', 'CHARGE', %s,
                            (SELECT credit_balance - %s FROM customers WHERE id = %s),
                            (SELECT credit_balance FROM customers WHERE id = %s),
                            NOW(), %s)"""
                    ops.append((history_sql, (customer_id, total_val, total_val, customer_id, customer_id, history_notes)))
                else:
                    history_sql = """INSERT INTO credit_history
                        (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes)
                        VALUES (%s, 'CHARGE', %s,
                            (SELECT credit_balance - %s FROM customers WHERE id = %s),
                            (SELECT credit_balance FROM customers WHERE id = %s),
                            NOW(), %s)"""
                    ops.append((history_sql, (customer_id, total_val, total_val, customer_id, customer_id, history_notes)))
        
        # ============================================================
        # CRITICAL FIX: Ejecutar TODA la transacción atómica
        # Incluye: venta, items, stock, crédito, historial
        # Si falla CUALQUIER operación, TODO se revierte (rollback)
        # ============================================================
        logger.info(f">>> Executing atomic transaction: {len(ops)} operations (sale + items + stock + customer)")
        for idx, (sql, params) in enumerate(ops):
            logger.debug(f"Op {idx}: {sql[:80]}... params={params}")
        
        try:
            # CRITICAL FIX: Timeout proporcional al número de operaciones
            # Mínimo 5 segundos, 0.5 segundos por operación
            timeout = max(5, len(ops) * 0.5)

            # CRITICAL FIX: Validar stock y crédito ANTES de ejecutar UPDATEs usando resultados de SELECT FOR UPDATE
            # execute_transaction separa automáticamente SELECT FOR UPDATE del resto y los ejecuta primero
            # Esto previene que el trigger falle y haga rollback de toda la transacción
            def validate_stock_and_credit(select_results):
                """Valida stock y límite de crédito usando resultados de SELECT FOR UPDATE"""
                if not select_results:
                    return

                # Los SELECT FOR UPDATE se ejecutan en orden:
                # 1. Primero los de stock (productos)
                # 2. Último el de crédito (si existe)
                num_stock_validations = len(stock_validations) if stock_validations else 0

                # Validar stock
                if stock_validations:
                    for idx, (p_id, qty, prod_name) in enumerate(stock_validations):
                        if idx < len(select_results):
                            stock_data = select_results[idx]
                            if stock_data:
                                current_stock = float(stock_data.get('stock', 0))
                                if current_stock < qty:
                                    product_name = stock_data.get('name', prod_name)
                                    raise ValueError(f"Stock insuficiente para '{product_name}'. Disponible: {current_stock}, Solicitado: {qty}")

                # CRITICAL FIX 2026-02-03: Validar límite de crédito dentro de la transacción
                if credit_validation_info and len(select_results) > num_stock_validations:
                    credit_data = select_results[num_stock_validations]
                    if credit_data:
                        balance_before = float(credit_data.get('credit_balance') or 0.0)
                        credit_limit = float(credit_data.get('credit_limit') or 0.0)
                        sale_amount = credit_validation_info['sale_amount']
                        balance_after = balance_before + sale_amount

                        # Validar límite (0 = ilimitado)
                        if credit_limit > 0 and balance_after > credit_limit:
                            raise ValueError(
                                f"La venta excede el límite de crédito del cliente. "
                                f"Límite: ${credit_limit:.2f}, Balance actual: ${balance_before:.2f}, "
                                f"Venta: ${sale_amount:.2f}, Nuevo balance: ${balance_after:.2f}"
                            )

            # Determinar si necesitamos callback de validación
            needs_validation = bool(stock_validations) or bool(credit_validation_info)

            try:
                transaction_result = self.db.execute_transaction(
                    ops,
                    timeout=int(timeout),
                    validation_callback=validate_stock_and_credit if needs_validation else None
                )
            except ValueError as ve:
                # Re-lanzar ValueError de validación de stock
                raise
            except Exception as e:
                # Manejar error del trigger de stock negativo con mensaje más amigable
                error_str = str(e).lower()
                if 'stock cannot be negative' in error_str or 'prevent_negative_stock' in error_str:
                    # Intentar identificar el producto problemático
                    product_name = "producto"
                    if stock_validations:
                        # Usar el primer producto de la lista como referencia
                        p_id, qty, prod_name = stock_validations[0]
                        product_name = prod_name
                    raise ValueError(f"Stock insuficiente para '{product_name}'. El stock disponible no es suficiente para completar la venta.") from e
                raise

            if not transaction_result.get('success'):
                raise RuntimeError("Transaction failed - success flag is False")
            
            # Obtener sale_id del primer INSERT (venta)
            inserted_ids = transaction_result.get('inserted_ids', [])
            rowcounts = transaction_result.get('rowcounts', [])
            
            # CRITICAL FIX: Verificar rowcounts para diagnóstico
            if not inserted_ids or inserted_ids[0] is None:
                # Verificar si el INSERT no afectó ninguna fila
                if rowcounts and len(rowcounts) > 0 and rowcounts[0] == 0:
                    raise RuntimeError(
                        "INSERT de sales no afectó ninguna fila (posible error silencioso). "
                        "Verifique que la tabla 'sales' existe y tiene las columnas correctas."
                    )
                raise RuntimeError(
                    f"Failed to get sale_id from transaction. "
                    f"inserted_ids={inserted_ids}, rowcounts={rowcounts[:5] if rowcounts else []}"
                )
            
            sale_id = inserted_ids[0]
            # FIX 2026-02-01: Folio ahora se genera dentro del CTE, obtener de la venta creada
            folio_result = self.db.execute_query("SELECT folio_visible FROM sales WHERE id = %s", (sale_id,))
            folio_visible = folio_result[0]['folio_visible'] if folio_result else f"{serie}{terminal_id}-??????"
            logger.info(f">>> ATOMIC TRANSACTION SUCCESS: Sale ID={sale_id}, UUID={sale_uuid}, Folio={folio_visible}")
            logger.info(f">>> Items: {len(items)}, Customer: {customer_id}, User: {user_id}, Turn: {turn_id}")

        except Exception as e:
            logger.error(f">>> ATOMIC TRANSACTION FAILED: {e}")
            import traceback
            logger.error(f">>> Transaction error traceback: {traceback.format_exc()}")
            # Si falla, TODO se revierte automáticamente (rollback)
            raise RuntimeError(f"Transaction Failed (Stock or DB Error): {e}") from e
        
        # ============================================================
        # OPERACIONES POST-TRANSACCIÓN CON RETRY LOGIC
        # Estas operaciones se ejecutan después de la transacción principal
        # porque dependen de sistemas externos (audit_log, MIDAS, Gift Card)
        # CRITICAL FIX: Implementar retry logic para garantizar que se ejecuten
        # ============================================================
        
        # AUDIT LOG - Sale created successfully (con retry)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                from app.utils.audit_logger import get_audit_logger
                audit = get_audit_logger()
                if audit:
                    audit.log_sale(sale_id, total_val, {
                        'items_count': len(items),
                        'payment_method': payment_method,
                        'customer_id': customer_id,
                        'turn_id': turn_id,
                        'discount': discount_amount,
                        'subtotal': subtotal,
                        'serie': serie
                    })
                break  # Éxito, salir del loop de retry
            except Exception as e:
                if attempt < max_retries - 1:
                    import time
                    time.sleep(0.5 * (attempt + 1))  # Backoff exponencial
                    logger.warning(f"Audit log failed (attempt {attempt + 1}/{max_retries}), retrying: {e}")
                else:
                    logger.error(f"Audit log failed after {max_retries} attempts: {e}")
                    # No lanzar excepción, solo registrar error (venta ya está creada)
        
        # MIDAS - Acumular puntos de lealtad si hay cliente asignado (con retry)
        # IMPORTANT: Don't accumulate points on the wallet portion of cost (would be double-dipping)
        if customer_id and customer_id > 0:
            for attempt in range(max_retries):
                try:
                    from decimal import Decimal

                    from src.core.loyalty_engine import LoyaltyEngine

                    # Calculate how much of the payment was NOT wallet (that's what earns points)
                    # wallet_amount comes from mixed_wallet if payment_method is 'mixed', otherwise 0
                    wallet_amount = mixed_wallet if payment_method == 'mixed' else 0.0
                    amount_for_points = total_val - wallet_amount if wallet_amount > 0 else total_val
                    
                    # Skip if entire payment was with wallet (no new points earned)
                    if amount_for_points <= 0:
                        logger.info(f">>> MIDAS: Skipping accumulation - 100% wallet payment")
                        break
                    
                    # FIXED: Use same DB as POS (not separate loyalty.db)
                    midas = LoyaltyEngine(self.db.db_path)
                    
                    # Convertir items a formato carrito para calcular cashback
                    # BUT: Adjust prices proportionally to reflect only the non-wallet portion
                    proportion = Decimal(str(amount_for_points)) / Decimal(str(total_val)) if total_val > 0 else Decimal('0')
                    
                    carrito = []
                    for item in items:
                        adjusted_price = Decimal(str(item.get('price', 0))) * proportion
                        carrito.append({
                            'product_id': item.get('id'),
                            'qty': item.get('qty', 1),
                            'price': float(adjusted_price),
                            'category_id': item.get('category_id')
                        })
                    
                    # Calcular y acumular puntos (only on non-wallet portion)
                    resultado = midas.calcular_cashback_potencial(carrito, customer_id)
                    
                    if resultado.total_puntos > Decimal('0'):
                        success = midas.acumular_puntos(
                            customer_id=customer_id,
                            monto=resultado.total_puntos,
                            ticket_id=sale_id,
                            turn_id=turn_id,
                            user_id=user_id,
                            carrito=carrito,
                            descripcion=f"Compra - Ticket #{sale_id} (Excluyendo ${wallet_amount:.2f} pagados con puntos)"
                        )
                        
                        if success:
                            logger.info(f">>> MIDAS: Acumulados ${resultado.total_puntos} puntos para cliente {customer_id} (basado en ${amount_for_points:.2f})")
                            break  # Éxito, salir del loop de retry
                        else:
                            if attempt < max_retries - 1:
                                import time
                                time.sleep(0.5 * (attempt + 1))
                                logger.warning(f">>> MIDAS: Falló acumulación (attempt {attempt + 1}/{max_retries}), retrying...")
                            else:
                                logger.warning(f">>> MIDAS: Falló acumulación de puntos para cliente {customer_id} después de {max_retries} intentos")
                    else:
                        logger.info(f">>> MIDAS: No points to accumulate (resultado.total_puntos = 0)")
                        break  # No hay puntos para acumular, salir
                        
                except Exception as e:
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(0.5 * (attempt + 1))
                        logger.warning(f">>> MIDAS accumulation failed (attempt {attempt + 1}/{max_retries}), retrying: {e}")
                    else:
                        logger.error(f">>> MIDAS accumulation failed after {max_retries} attempts: {e}")
                        import traceback
                        traceback.print_exc()
                        # No lanzar excepción, solo registrar error (venta ya está creada)

        # Clear cache after sale transaction
        if CACHE_ENABLED:
            try:
                query_cache.clear()
            except Exception as e:
                logger.warning(f"Cache clear failed: {e}")

        return sale_id

    def get_customer_credit_info(self, customer_id: int) -> Dict[str, Any]:
        rows = self.db.execute_query("SELECT credit_limit, credit_balance FROM customers WHERE id = %s", (customer_id,))
        if rows:
            row = dict(rows[0])  # Convert sqlite3.Row to dict
            limit = row.get('credit_limit') or 0.0
            balance = row.get('credit_balance') or 0.0
            return {
                "credit_limit": limit,
                "credit_balance": balance,
                "credit_authorized": limit > 0
            }
        return {"credit_limit": 0, "credit_balance": 0, "credit_authorized": False}

    def get_wallet_balance(self, customer_id: int) -> float:
        rows = self.db.execute_query("SELECT wallet_balance FROM customers WHERE id = %s", (customer_id,))
        if rows:
            return float(rows[0]['wallet_balance'] or 0.0)
        return 0.0

    def deduct_from_wallet(self, customer_id: int, amount: float, reason: str, ref_id: int = None):
        """
        Deduce cantidad del monedero del cliente.

        CRITICAL FIX: SELECT FOR UPDATE + UPDATE + INSERT en UNA SOLA transacción atómica.
        El lock se mantiene durante toda la operación para prevenir race conditions.

        Usa validation_callback para verificar saldo suficiente DESPUÉS del lock
        pero ANTES del UPDATE, todo dentro de la misma transacción.
        """
        # Verificar columnas antes de la transacción (operación idempotente, cache interno)
        has_user_id = self._ensure_column_exists("credit_history", "user_id", "INTEGER")
        has_movement_type = self._ensure_column_exists("credit_history", "movement_type", "TEXT")

        def validate_sufficient_balance(select_results):
            """
            Valida saldo suficiente dentro de la transacción con lock activo.
            Si lanza excepción, la transacción hace rollback automático.
            """
            if not select_results or select_results[0] is None:
                raise ValueError(f"Cliente {customer_id} no encontrado")

            balance_before = float(select_results[0].get('wallet_balance') or 0.0)

            if balance_before < amount:
                raise ValueError(
                    f"Saldo insuficiente en monedero. "
                    f"Disponible: ${balance_before:.2f}, Solicitado: ${amount:.2f}"
                )

        # Construir operaciones usando SQL que calcula valores dinámicamente
        # Esto permite que todo ocurra en UNA sola transacción atómica
        ops = [
            # 1. SELECT FOR UPDATE - adquiere lock de fila
            ("SELECT wallet_balance FROM customers WHERE id = %s FOR UPDATE", (customer_id,)),
            # 2. UPDATE con cálculo directo en SQL (usa valor actual - amount)
            ("UPDATE customers SET wallet_balance = wallet_balance - %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (amount, customer_id)),
        ]

        # 3. INSERT de historial usando subquery para obtener balances
        # Usamos subquery porque necesitamos balance_before (antes del UPDATE)
        # pero el UPDATE ya se ejecutó. Solución: capturar en validation_callback
        # y usar SQL que referencia la tabla actualizada
        if has_movement_type and has_user_id:
            # Usamos balance_after calculado = wallet_balance actual (post-UPDATE)
            # balance_before = wallet_balance + amount (reconstruido)
            history_sql = """
                INSERT INTO credit_history
                (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes, user_id, movement_type)
                SELECT %s, 'WALLET_DEDUCT', %s, wallet_balance + %s, wallet_balance, NOW(), %s, %s, 'WALLET'
                FROM customers WHERE id = %s
            """
            ops.append((history_sql, (customer_id, -amount, amount, reason or 'Deducción de monedero', ref_id, customer_id)))
        elif has_user_id:
            history_sql = """
                INSERT INTO credit_history
                (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes, user_id)
                SELECT %s, 'WALLET_DEDUCT', %s, wallet_balance + %s, wallet_balance, NOW(), %s, %s
                FROM customers WHERE id = %s
            """
            ops.append((history_sql, (customer_id, -amount, amount, reason or 'Deducción de monedero', ref_id, customer_id)))
        else:
            history_sql = """
                INSERT INTO credit_history
                (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes)
                SELECT %s, 'WALLET_DEDUCT', %s, wallet_balance + %s, wallet_balance, NOW(), %s
                FROM customers WHERE id = %s
            """
            ops.append((history_sql, (customer_id, -amount, amount, reason or 'Deducción de monedero', customer_id)))

        # Ejecutar TODO en una sola transacción atómica:
        # 1. SELECT FOR UPDATE (adquiere lock)
        # 2. validation_callback valida saldo >= amount (si falla, rollback)
        # 3. UPDATE reduce balance
        # 4. INSERT registra historial
        # Todo con el lock activo - sin race conditions posibles
        result = self.db.execute_transaction(ops, timeout=5, validation_callback=validate_sufficient_balance)

        if not result.get('success'):
            raise RuntimeError("Error al deducir del monedero: transacción falló")

    def add_to_wallet(self, customer_id: int, amount: float, reason: str, ref_id: int = None):
        """
        Agrega cantidad al monedero del cliente.

        CRITICAL FIX: SELECT FOR UPDATE + UPDATE + INSERT en UNA SOLA transacción atómica.
        El lock se mantiene durante toda la operación para prevenir race conditions.

        Usa validation_callback para verificar que el cliente existe DESPUÉS del lock
        pero ANTES del UPDATE, todo dentro de la misma transacción.
        """
        # Verificar columnas antes de la transacción (operación idempotente, cache interno)
        has_user_id = self._ensure_column_exists("credit_history", "user_id", "INTEGER")
        has_movement_type = self._ensure_column_exists("credit_history", "movement_type", "TEXT")

        def validate_customer_exists(select_results):
            """
            Valida que el cliente existe dentro de la transacción con lock activo.
            Si lanza excepción, la transacción hace rollback automático.
            """
            if not select_results or select_results[0] is None:
                raise ValueError(f"Cliente {customer_id} no encontrado")

        # Construir operaciones usando SQL que calcula valores dinámicamente
        # Esto permite que todo ocurra en UNA sola transacción atómica
        ops = [
            # 1. SELECT FOR UPDATE - adquiere lock de fila
            ("SELECT wallet_balance FROM customers WHERE id = %s FOR UPDATE", (customer_id,)),
            # 2. UPDATE con cálculo directo en SQL (usa valor actual + amount)
            ("UPDATE customers SET wallet_balance = wallet_balance + %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (amount, customer_id)),
        ]

        # 3. INSERT de historial usando subquery para obtener balances
        # balance_after = wallet_balance actual (post-UPDATE)
        # balance_before = wallet_balance - amount (reconstruido)
        if has_movement_type and has_user_id:
            history_sql = """
                INSERT INTO credit_history
                (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes, user_id, movement_type)
                SELECT %s, 'WALLET_ADD', %s, wallet_balance - %s, wallet_balance, NOW(), %s, %s, 'WALLET'
                FROM customers WHERE id = %s
            """
            ops.append((history_sql, (customer_id, amount, amount, reason or 'Adición a monedero', ref_id, customer_id)))
        elif has_user_id:
            history_sql = """
                INSERT INTO credit_history
                (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes, user_id)
                SELECT %s, 'WALLET_ADD', %s, wallet_balance - %s, wallet_balance, NOW(), %s, %s
                FROM customers WHERE id = %s
            """
            ops.append((history_sql, (customer_id, amount, amount, reason or 'Adición a monedero', ref_id, customer_id)))
        else:
            history_sql = """
                INSERT INTO credit_history
                (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes)
                SELECT %s, 'WALLET_ADD', %s, wallet_balance - %s, wallet_balance, NOW(), %s
                FROM customers WHERE id = %s
            """
            ops.append((history_sql, (customer_id, amount, amount, reason or 'Adición a monedero', customer_id)))

        # Ejecutar TODO en una sola transacción atómica:
        # 1. SELECT FOR UPDATE (adquiere lock)
        # 2. validation_callback verifica cliente existe (si falla, rollback)
        # 3. UPDATE aumenta balance
        # 4. INSERT registra historial
        # Todo con el lock activo - sin race conditions posibles
        result = self.db.execute_transaction(ops, timeout=5, validation_callback=validate_customer_exists)

        if not result.get('success'):
            raise RuntimeError("Error al agregar al monedero: transacción falló")

    def create_customer(self, data: Dict[str, Any]) -> int:
        """
        Crea un nuevo cliente.
        
        VALIDACIONES AGREGADAS:
        - Nombre obligatorio
        - Email formato válido (si se proporciona)
        """
        # ===== INPUT VALIDATION =====
        if not data.get('name'):
            raise ValueError("El nombre del cliente es obligatorio")
        
        # Email format validation (if provided)
        email = data.get('email', '').strip()
        if email and '@' not in email:
            raise ValueError("Formato de email inválido")
        
        # Phone validation (basic)
        phone = data.get('phone', '').strip()
        if phone and len(phone) < 7:
            raise ValueError("Número de teléfono debe tener al menos 7 dígitos")
        
        # Credit limit validation
        credit_limit = data.get('credit_limit', 0)
        if credit_limit < 0:
            raise ValueError("Límite de crédito no puede ser negativo")
        
        # ===== ORIGINAL CODE =====
        keys = [
            "name", "rfc", "email", "phone", "credit_limit", "address", "notes", 
            "first_name", "last_name", "email_fiscal", "razon_social", "regimen_fiscal",
            "domicilio1", "domicilio2", "colonia", "municipio", "estado", "pais", "codigo_postal",
            "vip", "credit_authorized"
        ]
        valid_data = {k: data.get(k) for k in keys if k in data}
        
        # PostgreSQL: Convertir booleanos a INTEGER (0/1) para columnas vip y credit_authorized
        for bool_field in ["vip", "credit_authorized"]:
            if bool_field in valid_data:
                val = valid_data[bool_field]
                if isinstance(val, bool):
                    valid_data[bool_field] = 1 if val else 0
                elif isinstance(val, str):
                    val_str = str(val).lower().strip()
                    valid_data[bool_field] = 1 if val_str in ["sí", "si", "yes", "true", "1", "verdadero"] else 0
                elif val is None:
                    valid_data[bool_field] = 0
                # Si ya es int, dejarlo como está
        
        # SECURITY: Validar whitelist
        ALLOWED_CUSTOMER_COLUMNS = set(keys)
        for col in valid_data.keys():
            if col not in ALLOWED_CUSTOMER_COLUMNS:
                raise ValueError(f"Columna no permitida en customers: {col}")
        
        columns = ", ".join(valid_data.keys())
        # PostgreSQL usa %s en lugar de ?
        placeholders = ", ".join(["%s"] * len(valid_data))
        values = tuple(valid_data.values())
        
        # SECURITY: columns validadas
        # Add synced = 0 for sync
        sql = f"INSERT INTO customers ({columns}, synced) VALUES ({placeholders}, 0)"
        result = self.db.execute_write(sql, values)

        # Cache invalidation after database write
        if CACHE_ENABLED:
            try:
                query_cache.clear()
            except Exception as e:
                logger.warning(f"Cache clear failed: {e}")

        return result

    def update_customer(self, customer_id: int, data: Dict[str, Any]):
        keys = [
            "name", "rfc", "email", "phone", "credit_limit", "address", "notes", "is_active",
            "first_name", "last_name", "email_fiscal", "razon_social", "regimen_fiscal",
            "domicilio1", "domicilio2", "colonia", "municipio", "estado", "pais", "codigo_postal",
            "vip", "credit_authorized"
        ]
        valid_data = {k: data.get(k) for k in keys if k in data}
        
        if not valid_data: return
        
        # PostgreSQL: Convertir booleanos a INTEGER (0/1) para columnas vip, credit_authorized, is_active
        for bool_field in ["vip", "credit_authorized", "is_active"]:
            if bool_field in valid_data:
                val = valid_data[bool_field]
                if isinstance(val, bool):
                    valid_data[bool_field] = 1 if val else 0
                elif isinstance(val, str):
                    val_str = str(val).lower().strip()
                    valid_data[bool_field] = 1 if val_str in ["sí", "si", "yes", "true", "1", "verdadero"] else 0
                elif val is None:
                    valid_data[bool_field] = 0
                # Si ya es int, dejarlo como está
        
        # SECURITY: Validar whitelist
        ALLOWED_CUSTOMER_COLUMNS = set(keys)
        for col in valid_data.keys():
            if col not in ALLOWED_CUSTOMER_COLUMNS:
                raise ValueError(f"Columna no permitida en customers: {col}")
        
        set_clause = ", ".join([f"{k} = %s" for k in valid_data.keys()])
        values = tuple(valid_data.values()) + (customer_id,)

        # SECURITY: columns validadas
        # Add synced = 0 to mark for sync, updated_at for tracking
        sql = f"UPDATE customers SET {set_clause}, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        self.db.execute_write(sql, values)

        # Cache invalidation after database write
        if CACHE_ENABLED:
            try:
                query_cache.clear()
            except Exception as e:
                logger.warning(f"Cache clear failed: {e}")

    def get_customer(self, customer_id: int) -> Optional[Dict[str, Any]]:
        rows = self.db.execute_query("SELECT * FROM customers WHERE id = %s", (customer_id,))
        return dict(rows[0]) if rows else None
        
    def list_customers(self, query: str = None, limit: int = 300) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM customers WHERE is_active = 1"
        params = []
        if query:
            sql += " AND (name LIKE %s OR rfc LIKE %s)"
            params = [f"%{query}%", f"%{query}%"]
        
        sql += " LIMIT %s"
        params.append(limit)
        
        return [dict(row) for row in self.db.execute_query(sql, tuple(params))]

    def delete_customer(self, customer_id: int):
        sql = "UPDATE customers SET is_active = 0, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        self.db.execute_write(sql, (customer_id,))

    def search_customers(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM customers WHERE is_active = 1 AND (name LIKE %s OR rfc LIKE %s OR phone LIKE %s) LIMIT %s"
        params = [f"%{query}%", f"%{query}%", f"%{query}%", limit]
        return [dict(row) for row in self.db.execute_query(sql, tuple(params))]

    # --- LAYAWAY MODULE ---
    def create_layaway(self, customer_id: int, items: List[Dict], initial_payment: float, due_date: str, notes: str, user_id: int = 1) -> int:
        """
        Crea un nuevo apartado.
        1. Crea registro en layaways.
        2. Crea items en layaway_items.
        3. Descuenta stock (reserva).
        4. Registra el pago inicial en caja.
        """
        total_amount = sum(float(item['price']) * float(item['qty']) for item in items)
        balance_due = total_amount - initial_payment
        
        # CRITICAL FIX: Todas las operaciones en una sola transacción atómica
        # Si falla cualquier operación, TODO se revierte (rollback)
        created_at = datetime.now().isoformat()
        
        # Verificar si user_id existe antes de construir la transacción
        has_user_id = self._ensure_column_exists("inventory_log", "user_id", "INTEGER")
        
        # Construir TODAS las operaciones en una lista
        ops = []
        
        # 1. Crear apartado con RETURNING id
        layaway_sql = """
            INSERT INTO layaways (customer_id, total_amount, amount_paid, balance_due, status, created_at, due_date, notes, synced)
            VALUES (%s, %s, %s, %s, 'active', %s, %s, %s, 0)
            RETURNING id
        """
        ops.append((layaway_sql, (customer_id, total_amount, initial_payment, balance_due, created_at, due_date, notes)))
        
        # 2. Crear items, descontar stock y registrar movimientos de inventario
        for item in items:
            product_id = item['product_id']
            qty = float(item['qty'])
            price = float(item['price'])
            total = qty * price
            
            # Insert item usando subquery para obtener layaway_id
            item_sql = """INSERT INTO layaway_items (layaway_id, product_id, qty, price, total, synced)
                VALUES ((SELECT id FROM layaways WHERE customer_id = %s AND created_at = %s ORDER BY id DESC LIMIT 1), %s, %s, %s, %s, 0)"""
            ops.append((item_sql, (customer_id, created_at, product_id, qty, price, total)))
            
            # Deduct Stock (Reservation)
            ops.append(("UPDATE products SET stock = stock - %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (qty, product_id)))

            # Log Inventory Movement
            if has_user_id:
                log_sql = "INSERT INTO inventory_log (product_id, qty_change, reason, timestamp, user_id) VALUES (%s, %s, %s, %s, %s)"
                # Usar subquery para obtener layaway_id
                reason = "(SELECT CONCAT('Apartado #', id::text) FROM layaways WHERE customer_id = %s AND created_at = %s ORDER BY id DESC LIMIT 1)"
                ops.append((log_sql, (product_id, -qty, f"Apartado (pendiente ID)", created_at, user_id)))
            else:
                log_sql = "INSERT INTO inventory_log (product_id, qty_change, reason, timestamp) VALUES (%s, %s, %s, %s)"
                ops.append((log_sql, (product_id, -qty, f"Apartado (pendiente ID)", created_at)))
        
        # Ejecutar TODO en una sola transacción atómica
        result = self.db.execute_transaction(ops, timeout=10)
        if not result.get('success'):
            raise RuntimeError("Transaction failed - layaway not created")
        
        # Obtener layaway_id del resultado
        inserted_ids = result.get('inserted_ids', [])
        if not inserted_ids or inserted_ids[0] is None:
            raise RuntimeError("Failed to get layaway_id from transaction")
        
        layaway_id = inserted_ids[0]
        
        # Actualizar logs de inventario con el layaway_id real (post-transacción, no crítico)
        for item in items:
            product_id = item['product_id']
            qty = float(item['qty'])
            try:
                if has_user_id:
                    self.db.execute_write(
                        "UPDATE inventory_log SET reason = %s WHERE product_id = %s AND reason = %s AND timestamp = %s LIMIT 1",
                        (f"Apartado #{layaway_id}", product_id, "Apartado (pendiente ID)", created_at)
                    )
                else:
                    self.db.execute_write(
                        "UPDATE inventory_log SET reason = %s WHERE product_id = %s AND reason = %s AND timestamp = %s LIMIT 1",
                        (f"Apartado #{layaway_id}", product_id, "Apartado (pendiente ID)", created_at)
                    )
            except Exception as e:
                # No crítico, solo es para mejorar el log
                logger.warning(f"No se pudo actualizar reason en inventory_log: {e}")
            
        # 3. Register Initial Payment (if any)
        if initial_payment > 0:
            # Find open turn
            turn_rows = self.db.execute_query("SELECT id FROM turns WHERE user_id = %s AND status = 'OPEN' ORDER BY id DESC LIMIT 1", (user_id,))
            if turn_rows:
                turn_id = turn_rows[0]['id']
                # CRITICAL FIX: Verificar si user_id existe antes de INSERT
                has_user_id = self._ensure_column_exists("cash_movements", "user_id", "INTEGER")
                if has_user_id:
                    self.db.execute_write(
                        "INSERT INTO cash_movements (turn_id, type, amount, reason, timestamp, user_id) VALUES (%s, 'in', %s, %s, %s, %s)",
                        (turn_id, initial_payment, f"Abono Inicial Apartado #{layaway_id}", created_at, user_id)
                    )
                else:
                    # Fallback: INSERT sin user_id
                    self.db.execute_write(
                        "INSERT INTO cash_movements (turn_id, type, amount, reason, timestamp) VALUES (%s, 'in', %s, %s, %s)",
                        (turn_id, initial_payment, f"Abono Inicial Apartado #{layaway_id}", created_at)
                    )
                
        return layaway_id

    def add_layaway_payment(self, layaway_id: int, amount: float, user_id: int = 1, payment_data: Dict = None):
        """
        Registra un abono a un apartado con soporte para múltiples métodos de pago.
        """
        # 0. Ensure history table exists (Lazy setup)
        self.db.execute_write("""
            CREATE TABLE IF NOT EXISTS layaway_payments (
                id SERIAL PRIMARY KEY,  -- FIX 2026-02-01: PostgreSQL
                layaway_id INTEGER,
                amount REAL,
                method TEXT,
                reference TEXT,
                timestamp TEXT,
                user_id INTEGER
            )
        """)

        # Get current status
        rows = self.db.execute_query("SELECT * FROM layaways WHERE id = %s", (layaway_id,))
        if not rows: raise ValueError("Apartado no encontrado")
        layaway = dict(rows[0])
        
        # Determine payment details
        method = 'cash'
        reference = ''
        cash_portion = amount # Default for legacy calls
        
        if payment_data:
            method = payment_data.get('method', 'cash')
            reference = payment_data.get('reference', '')
            
            # Calculate cash portion correctly for drawer tracking
            if method == 'cash':
                cash_portion = amount
            elif method == 'mixed':
                breakdown = payment_data.get('mixed_breakdown', {})
                cash_portion = float(breakdown.get('cash', 0))
            else:
                cash_portion = 0 # Card, Transfer, etc. don't affect cash drawer
        
        new_paid = float(layaway['amount_paid']) + amount
        new_balance = float(layaway['total_amount']) - new_paid
        
        status = 'active'
        if new_balance <= 0.01: # Tolerance
            status = 'completed'
            new_balance = 0
            
        # 1. Update Layaway
        self.db.execute_write(
            "UPDATE layaways SET amount_paid = %s, balance_due = %s, status = %s, updated_at = CURRENT_TIMESTAMP, synced = 0 WHERE id = %s",
            (new_paid, new_balance, status, layaway_id)
        )
        
        timestamp = datetime.now().isoformat()
        
        # 2. Record Payment History
        # CRITICAL FIX: Verificar si user_id existe antes de INSERT
        has_user_id = self._ensure_column_exists("layaway_payments", "user_id", "INTEGER")
        if has_user_id:
            self.db.execute_write(
                "INSERT INTO layaway_payments (layaway_id, amount, method, reference, timestamp, user_id) VALUES (%s, %s, %s, %s, %s, %s)",
                (layaway_id, amount, method, reference, timestamp, user_id)
            )
        else:
            # Fallback: INSERT sin user_id
            self.db.execute_write(
                "INSERT INTO layaway_payments (layaway_id, amount, method, reference, timestamp) VALUES (%s, %s, %s, %s, %s)",
                (layaway_id, amount, method, reference, timestamp)
            )
        
        # 3. Register Cash Movement (Only if cash involved)
        if cash_portion > 0:
            turn_rows = self.db.execute_query("SELECT id FROM turns WHERE user_id = %s AND status = 'OPEN' ORDER BY id DESC LIMIT 1", (user_id,))
            if turn_rows:
                turn_id = turn_rows[0]['id']
                # CRITICAL FIX: Verificar si user_id existe antes de INSERT
                has_user_id = self._ensure_column_exists("cash_movements", "user_id", "INTEGER")
                if has_user_id:
                    self.db.execute_write(
                        "INSERT INTO cash_movements (turn_id, type, amount, reason, timestamp, user_id) VALUES (%s, 'in', %s, %s, %s, %s)",
                        (turn_id, cash_portion, f"Abono Apartado #{layaway_id} ({method})", timestamp, user_id)
                    )
                else:
                    # Fallback: INSERT sin user_id
                    self.db.execute_write(
                        "INSERT INTO cash_movements (turn_id, type, amount, reason, timestamp) VALUES (%s, 'in', %s, %s, %s)",
                        (turn_id, cash_portion, f"Abono Apartado #{layaway_id} ({method})", timestamp)
                    )
            
        return status

    def cancel_layaway(self, layaway_id: int, user_id: int = 1):
        """
        Cancela un apartado y devuelve items al inventario.
        NO devuelve el dinero automáticamente (política de cancelación).
        """
        rows = self.db.execute_query("SELECT * FROM layaways WHERE id = %s", (layaway_id,))
        if not rows: raise ValueError("Apartado no encontrado")
        layaway = dict(rows[0])
        
        if layaway['status'] != 'active':
            raise ValueError("Solo se pueden cancelar apartados activos")
            
        # CRITICAL FIX: Todas las operaciones en una sola transacción atómica
        # Si falla cualquier operación, TODO se revierte (rollback)
        timestamp = datetime.now().isoformat()
        
        # Obtener items antes de construir la transacción
        items = list(self.db.execute_query("SELECT * FROM layaway_items WHERE layaway_id = %s", (layaway_id,)))
        
        # Verificar si user_id existe antes de construir la transacción
        has_user_id = self._ensure_column_exists("inventory_log", "user_id", "INTEGER")
        
        # Construir TODAS las operaciones en una lista
        ops = []
        
        # 1. Actualizar status del apartado
        ops.append(("UPDATE layaways SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP, synced = 0 WHERE id = %s", (layaway_id,)))
        
        # 2. Restaurar inventario y registrar movimientos
        for item in items:
            qty = float(item['qty'])
            product_id = item['product_id']
            
            # Restaurar stock
            ops.append(("UPDATE products SET stock = stock + %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (qty, product_id)))

            # Log Inventory Movement
            if has_user_id:
                log_sql = "INSERT INTO inventory_log (product_id, qty_change, reason, timestamp, user_id) VALUES (%s, %s, %s, %s, %s)"
                ops.append((log_sql, (product_id, qty, f"Cancelación Apartado #{layaway_id}", timestamp, user_id)))
            else:
                log_sql = "INSERT INTO inventory_log (product_id, qty_change, reason, timestamp) VALUES (%s, %s, %s, %s)"
                ops.append((log_sql, (product_id, qty, f"Cancelación Apartado #{layaway_id}", timestamp)))
        
        # Ejecutar TODO en una sola transacción atómica
        result = self.db.execute_transaction(ops, timeout=10)
        if not result.get('success'):
            raise RuntimeError("Transaction failed - layaway not cancelled")

    def list_layaways(self, branch_id: int = 1, status: str = "active", date_range: tuple = None) -> List[Dict]:
        sql = """
            SELECT l.*, c.name as customer_name,
                   l.total_amount as total,
                   l.amount_paid as paid_total,
                   l.balance_due as balance_calc
            FROM layaways l
            LEFT JOIN customers c ON l.customer_id = c.id
            WHERE 1=1
        """
        params = []
        
        if status and status != "all":
            sql += " AND l.status = %s"
            params.append(status)
            
        if date_range:
            start, end = date_range
            sql += " AND date(l.created_at) BETWEEN %s AND %s"
            params.extend([start, end])
            
        sql += " ORDER BY l.created_at DESC"
        
        return [dict(row) for row in self.db.execute_query(sql, tuple(params))]

    def get_layaway(self, layaway_id: int) -> Optional[Dict]:
        rows = self.db.execute_query("""
            SELECT l.*, c.name as customer_name,
                   l.total_amount as total,
                   l.amount_paid as paid_total,
                   l.balance_due as balance_calc
            FROM layaways l
            LEFT JOIN customers c ON l.customer_id = c.id
            WHERE l.id = %s
        """, (layaway_id,))
        return dict(rows[0]) if rows else None

    def get_layaway_items(self, layaway_id: int) -> List[Dict]:
        sql = """
            SELECT li.*, p.name 
            FROM layaway_items li
            JOIN products p ON li.product_id = p.id
            WHERE li.layaway_id = %s
        """
        return [dict(row) for row in self.db.execute_query(sql, (layaway_id,))]

    def get_layaway_payments(self, layaway_id: int) -> List[Dict]:
        """
        Obtiene historial de pagos (nuevo y legacy).
        """
        # 1. Try new table
        sql_new = "SELECT * FROM layaway_payments WHERE layaway_id = %s ORDER BY timestamp DESC"
        rows_new = self.db.execute_query(sql_new, (layaway_id,))
        if rows_new:
            return [dict(r) for r in rows_new]
            
        # 2. Fallback to cash_movements (Legacy)
        sql_legacy = """
            SELECT * FROM cash_movements 
            WHERE reason LIKE %s OR reason LIKE %s
            ORDER BY timestamp DESC
        """
        pattern1 = f"Abono Apartado #{layaway_id}"
        pattern2 = f"Abono Inicial Apartado #{layaway_id}"
        return [dict(row) for row in self.db.execute_query(sql_legacy, (pattern1, pattern2))]

    # --- KIT PRODUCTS MODULE ---
    def add_kit_component(self, kit_product_id: int, component_product_id: int, quantity: float = 1.0):
        """Adds a component to a KIT product."""
        # Validate that component is not also a KIT (prevent recursion)
        component = self.get_product_by_id(component_product_id)
        if component and component.get('sale_type') == 'kit':
            raise ValueError("Cannot add a KIT product as a component of another KIT")

        sql = "INSERT INTO kit_items (parent_product_id, child_product_id, qty) VALUES (%s, %s, %s)"
        result = self.db.execute_write(sql, (kit_product_id, component_product_id, quantity))

        # Cache invalidation after database write
        if CACHE_ENABLED:
            try:
                query_cache.clear()
            except Exception as e:
                logger.warning(f"Cache clear failed: {e}")

        return result

    def get_kit_components(self, kit_product_id: int) -> List[Dict]:
        """Gets all components of a KIT product."""
        sql = """
            SELECT k.*, p.name, p.sku, p.price, p.stock 
            FROM kit_items k 
            JOIN products p ON k.child_product_id = p.id 
            WHERE k.parent_product_id = %s
        """
        return [dict(row) for row in self.db.execute_query(sql, (kit_product_id,))]
    
    def remove_kit_component(self, kit_product_id: int, component_product_id: int):
        """Removes a component from a KIT product."""
        sql = "DELETE FROM kit_items WHERE parent_product_id = %s AND child_product_id = %s"
        self.db.execute_write(sql, (kit_product_id, component_product_id))

        # Cache invalidation after database write
        if CACHE_ENABLED:
            try:
                query_cache.clear()
            except Exception as e:
                logger.warning(f"Cache clear failed: {e}")

    def update_kit_component_quantity(self, kit_product_id: int, component_product_id: int, new_quantity: float):
        """Updates the quantity of a component in a KIT."""
        sql = "UPDATE kit_items SET qty = %s WHERE parent_product_id = %s AND child_product_id = %s"
        self.db.execute_write(sql, (new_quantity, kit_product_id, component_product_id))

        # Cache invalidation after database write
        if CACHE_ENABLED:
            try:
                query_cache.clear()
            except Exception as e:
                logger.warning(f"Cache clear failed: {e}")

    def calculate_kit_suggested_price(self, kit_product_id: int) -> float:
        """Calculates suggested price for a KIT based on its components."""
        components = self.get_kit_components(kit_product_id)
        total = sum(float(c.get('price', 0)) * float(c.get('qty', 1)) for c in components)
        return total

# Proxy para compatibilidad: quien hace "from ... import pos_engine" y usa pos_engine.xxx
# obtiene la instancia del hilo actual (thread-safe).
class _POSEngineProxy:
    """Proxy que delega en get_pos_engine() para acceso thread-safe."""

    def __getattr__(self, name: str):
        return getattr(get_pos_engine(), name)


pos_engine = _POSEngineProxy()
