"""
TITAN POS - POS Product Methods (extracted from pos_engine.py)

Contains all product-related methods from the original POSEngine:
- Product CRUD (create, update, delete)
- Product search and listing
- Stock management
- Kit/combo operations
"""

from typing import Any, Dict, List, Optional
import logging
import math

logger = logging.getLogger("POS_ENGINE.products")

# Import cache system
try:
    from app.utils.query_cache import query_cache, timed_query, CACHE_ENABLED
except ImportError:
    CACHE_ENABLED = False
    query_cache = None
    def timed_query(func):
        return func


class POSProductsMixin:
    """
    Mixin class containing all product-related methods extracted from POSEngine.

    Requires from POSEngine:
        - self.db: Database access
        - self._ensure_column_exists(): Column existence checker
    """

    @timed_query
    def get_product_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """Buscar producto por SKU o barcode."""
        sku_clean = sku.strip() if sku else ""
        rows = self.db.execute_query(
            "SELECT * FROM products WHERE sku = %s OR barcode = %s LIMIT 1",
            (sku_clean, sku_clean)
        )
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
            params = [f"%{query}%"] * 5
        rows = self.db.execute_query(sql, tuple(params))
        return rows[0]["count"] if rows else 0

    def list_products(self, limit: int = 50, offset: int = 0, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista productos con paginación y búsqueda."""
        if query:
            sql = "SELECT * FROM products WHERE is_active = 1 AND (visible IS NULL OR visible != 0) AND (name LIKE %s OR sku LIKE %s OR barcode LIKE %s) ORDER BY name LIMIT %s OFFSET %s"
            rows = self.db.execute_query(sql, (f"%{query}%", f"%{query}%", f"%{query}%", limit, offset))
        else:
            sql = "SELECT * FROM products WHERE is_active = 1 AND (visible IS NULL OR visible != 0) ORDER BY name LIMIT %s OFFSET %s"
            rows = self.db.execute_query(sql, (limit, offset))
        return [dict(r) for r in rows]

    def list_products_for_export(self) -> List[Dict[str, Any]]:
        """Lista todos los productos sin paginación."""
        sql = "SELECT * FROM products WHERE is_active = 1 LIMIT 50000"
        return [dict(row) for row in self.db.execute_query(sql)]

    def get_products(self, limit=100, **kwargs):
        """Wrapper method for backwards compatibility."""
        return self.list_products(limit=limit, offset=0)

    def search_products(self, query: str = "", category_id: Optional[int] = None, limit: int = 50):
        """Busca productos por nombre, SKU o código de barras."""
        sql = "SELECT * FROM products WHERE is_active = 1"
        params = []
        if query:
            sql += " AND (name LIKE %s OR sku LIKE %s OR barcode LIKE %s)"
            params.extend([f"%{query}%"] * 3)
        if category_id:
            sql += " AND category_id = %s"
            params.append(category_id)
        sql += " ORDER BY name LIMIT %s"
        params.append(limit)
        rows = self.db.execute_query(sql, tuple(params))
        return [dict(r) for r in rows]

    def create_product(self, product_data: Dict[str, Any]) -> int:
        """Crea un nuevo producto con validaciones completas."""
        if not isinstance(product_data, dict):
            raise ValueError(f"product_data debe ser un diccionario, recibido: {type(product_data).__name__}")

        sku = product_data.get('sku')
        if not sku or (isinstance(sku, str) and not sku.strip()):
            raise ValueError("SKU es obligatorio")
        if not isinstance(sku, (str, int)):
            raise ValueError(f"SKU inválido: tipo {type(sku).__name__}")

        name = product_data.get('name')
        if not name or (isinstance(name, str) and not name.strip()):
            raise ValueError("Nombre del producto es obligatorio")

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

        validate_number(product_data.get('price', 0), 'Precio')
        validate_number(product_data.get('stock', 0), 'Stock')
        validate_number(product_data.get('cost', 0), 'Costo')
        validate_number(product_data.get('min_stock', 5), 'Stock mínimo')

        tax_rate = product_data.get('tax_rate', 0.16)
        if tax_rate is not None:
            tax_rate = validate_number(tax_rate, 'Tax rate')
            if not (0 <= tax_rate <= 1):
                raise ValueError("Tax rate debe estar entre 0 y 1")

        keys = [
            "sku", "name", "price", "price_wholesale", "cost",
            "stock", "min_stock", "department", "category",
            "provider", "tax_rate", "sale_type", "barcode", "is_favorite",
            "sat_clave_prod_serv", "sat_clave_unidad", "sat_descripcion"
        ]

        valid_data = {k: product_data.get(k) for k in keys if k in product_data}

        if "is_favorite" in valid_data and isinstance(valid_data["is_favorite"], bool):
            valid_data["is_favorite"] = 1 if valid_data["is_favorite"] else 0

        if "price" not in valid_data: valid_data["price"] = 0.0
        if "cost" not in valid_data: valid_data["cost"] = 0.0
        if "stock" not in valid_data: valid_data["stock"] = 0.0

        ALLOWED_PRODUCT_COLUMNS = set(keys)
        for col in valid_data.keys():
            if col not in ALLOWED_PRODUCT_COLUMNS:
                raise ValueError(f"Columna no permitida en products: {col}")

        valid_data["synced"] = 0
        columns = ", ".join(valid_data.keys())
        placeholders = ", ".join(["%s"] * len(valid_data))
        values = tuple(valid_data.values())

        sql = f"INSERT INTO products ({columns}) VALUES ({placeholders})"
        result = self.db.execute_write(sql, values)

        if CACHE_ENABLED and query_cache:
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
            "sat_clave_prod_serv", "sat_clave_unidad", "sat_descripcion"
        ]

        valid_data = {k: product_data.get(k) for k in keys if k in product_data}
        if not valid_data:
            return

        if "is_favorite" in valid_data and isinstance(valid_data["is_favorite"], bool):
            valid_data["is_favorite"] = 1 if valid_data["is_favorite"] else 0

        ALLOWED_PRODUCT_COLUMNS = set(keys)
        for col in valid_data.keys():
            if col not in ALLOWED_PRODUCT_COLUMNS:
                raise ValueError(f"Columna no permitida en products: {col}")

        set_clause = ", ".join([f"{k} = %s" for k in valid_data.keys()])
        values = list(valid_data.values())
        values.append(product_id)

        sql = f"UPDATE products SET {set_clause}, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        rowcount = self.db.execute_write(sql, tuple(values))

        if CACHE_ENABLED and query_cache:
            try:
                query_cache.clear()
            except Exception as e:
                logger.warning(f"Cache clear failed (update succeeded): {e}")

        return rowcount

    def add_stock(self, product_id, qty, reason="ajuste manual"):
        """Add stock via inventory movement."""
        try:
            mov_sql = """INSERT INTO inventory_movements
                (product_id, movement_type, type, quantity, reason, reference_type, user_id, branch_id, timestamp, synced)
                VALUES (%s, 'IN', 'adjust', %s, %s, 'adjust', NULL, NULL, NOW(), 0)"""
            self.db.execute_write(mov_sql, (product_id, qty, reason or "ajuste manual"))
        except Exception as e:
            logger.debug("Could not insert inventory_movement for add_stock: %s", e)
        sql = "UPDATE products SET stock = stock + %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        self.db.execute_write(sql, (qty, product_id))
        if CACHE_ENABLED and query_cache:
            query_cache.clear()

    def delete_product(self, product_id: int):
        """Marca un producto como inactivo (soft delete)."""
        sql = "UPDATE products SET is_active = 0, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        self.db.execute_write(sql, (product_id,))
        if CACHE_ENABLED and query_cache:
            try:
                query_cache.clear()
            except Exception as e:
                logger.warning(f"Cache clear failed: {e}")
        return True

    # --- KIT PRODUCTS ---
    def add_kit_component(self, kit_product_id: int, component_product_id: int, quantity: float = 1.0):
        component = self.get_product_by_id(component_product_id)
        if component and component.get('sale_type') == 'kit':
            raise ValueError("Cannot add a KIT product as a component of another KIT")
        sql = "INSERT INTO kit_items (parent_product_id, child_product_id, qty) VALUES (%s, %s, %s)"
        result = self.db.execute_write(sql, (kit_product_id, component_product_id, quantity))
        if CACHE_ENABLED and query_cache:
            try: query_cache.clear()
            except Exception: pass
        return result

    def get_kit_components(self, kit_product_id: int) -> List[Dict]:
        sql = """
            SELECT k.*, p.name, p.sku, p.price, p.stock
            FROM kit_items k
            JOIN products p ON k.child_product_id = p.id
            WHERE k.parent_product_id = %s
        """
        return [dict(row) for row in self.db.execute_query(sql, (kit_product_id,))]

    def remove_kit_component(self, kit_product_id: int, component_product_id: int):
        sql = "DELETE FROM kit_items WHERE parent_product_id = %s AND child_product_id = %s"
        self.db.execute_write(sql, (kit_product_id, component_product_id))
        if CACHE_ENABLED and query_cache:
            try: query_cache.clear()
            except Exception: pass

    def update_kit_component_quantity(self, kit_product_id: int, component_product_id: int, new_quantity: float):
        sql = "UPDATE kit_items SET qty = %s WHERE parent_product_id = %s AND child_product_id = %s"
        self.db.execute_write(sql, (new_quantity, kit_product_id, component_product_id))
        if CACHE_ENABLED and query_cache:
            try: query_cache.clear()
            except Exception: pass

    def calculate_kit_suggested_price(self, kit_product_id: int) -> float:
        components = self.get_kit_components(kit_product_id)
        total = sum(float(c.get('price', 0)) * float(c.get('qty', 1)) for c in components)
        return total


__all__ = ["POSProductsMixin"]
