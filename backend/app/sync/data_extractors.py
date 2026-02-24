"""
TITAN POS - Data Extractors

Extract local data for synchronization with remote server.
"""

from typing import Any, Dict, List
import logging

from app.startup.bootstrap import log_debug

logger = logging.getLogger(__name__)


class DataExtractor:
    """
    Extracts data from local database for synchronization.

    Provides methods to get products, sales, and customers
    that need to be synced with the server.
    """

    def __init__(self, core):
        """
        Initialize the data extractor.

        Args:
            core: POSCore instance with database access
        """
        self.core = core

    def get_products_for_sync(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get unsynced products for synchronization.

        Args:
            limit: Maximum number of products to return

        Returns:
            List of product dictionaries that need syncing
        """
        try:
            # LIMIT parametrizado (SEC-1): evita inyección si limit viene de config
            limit_safe = max(1, min(int(limit), 10000)) if limit else 1000
            rows = self.core.db.execute_query(
                """SELECT id, sku, name, price, stock, category, provider,
                   is_favorite, sale_type, min_stock, max_stock, updated_at
                   FROM products
                   WHERE synced = 0 OR synced IS NULL
                   ORDER BY updated_at DESC NULLS LAST
                   LIMIT %s""",
                (limit_safe,)
            )
            products = [dict(row) for row in rows]

            log_debug("data_extractors:get_products_for_sync", "Products retrieved", {
                "count": len(products)
            }, "D")

            return products

        except Exception as e:
            logger.error(f"Error getting products for sync: {e}")
            return []

    def get_sales_for_sync(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get unsynced sales from the last 24 hours.

        Args:
            limit: Maximum number of sales to return

        Returns:
            List of sale dictionaries
        """
        try:
            # Check stats (INTERVAL '1 day' = últimas 24h)
            stats_rows = self.core.db.execute_query("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN synced = 0 OR synced IS NULL THEN 1 ELSE 0 END) as unsynced
                FROM sales
                WHERE timestamp::timestamp >= NOW() - INTERVAL '1 day'
            """)
            stats = stats_rows[0] if stats_rows else None

            log_debug("data_extractors:get_sales_for_sync", "Sales sync query stats", {
                "total_sales": stats['total'] if stats else 0,
                "unsynced_sales": stats['unsynced'] if stats else 0
            }, "D")

            # Get unsynced sales (INTERVAL '1 day' = últimas 24h; LIMIT parametrizado SEC-1)
            # FIX: turn_id se extrae como NULL porque los turnos son locales a cada PC
            limit_safe = max(1, min(int(limit), 1000)) if limit else 100
            rows = self.core.db.execute_query(
                """SELECT id, uuid, timestamp, subtotal, tax, total, discount, payment_method,
                   customer_id, user_id, NULL as turn_id, serie, folio, folio_visible, branch_id, synced
                   FROM sales
                   WHERE (synced = 0 OR synced IS NULL)
                   AND timestamp::timestamp >= NOW() - INTERVAL '1 day'
                   ORDER BY id DESC
                   LIMIT %s""",
                (limit_safe,)
            )

            sales = [dict(row) for row in rows]

            # Agregar items a cada venta (FIX: sin items el servidor guarda ventas vacías)
            for sale in sales:
                items_rows = self.core.db.execute_query(
                    """SELECT id, product_id, qty, price, subtotal, discount,
                              name, total, sat_clave_prod_serv, sat_descripcion
                       FROM sale_items WHERE sale_id = %s""",
                    (sale['id'],)
                )
                sale['items'] = [dict(item) for item in items_rows] if items_rows else []

            log_debug("data_extractors:get_sales_for_sync", "Sales retrieved for sync", {
                "count": len(sales),
                "synced_count": sum(1 for s in sales if s.get('synced') == 1),
                "unsynced_count": sum(1 for s in sales if s.get('synced') == 0 or s.get('synced') is None)
            }, "D")

            return sales

        except Exception as e:
            log_debug("data_extractors:get_sales_for_sync", "Error", {"error": str(e)}, "D")
            logger.error(f"Error getting sales for sync: {e}")
            return []

    def get_customers_for_sync(self, limit: int = 500) -> List[Dict[str, Any]]:
        """
        Get unsynced customers for synchronization.

        Args:
            limit: Maximum number of customers to return

        Returns:
            List of customer dictionaries that need syncing
        """
        try:
            # LIMIT parametrizado (SEC-1)
            limit_safe = max(1, min(int(limit), 10000)) if limit else 500
            rows = self.core.db.execute_query(
                """SELECT id, name, phone, email, address, credit_limit,
                   loyalty_points, notes, updated_at
                   FROM customers
                   WHERE synced = 0 OR synced IS NULL
                   ORDER BY updated_at DESC NULLS LAST
                   LIMIT %s""",
                (limit_safe,)
            )
            customers = [dict(row) for row in rows]

            log_debug("data_extractors:get_customers_for_sync", "Customers retrieved", {
                "count": len(customers)
            }, "D")

            return customers

        except Exception as e:
            logger.error(f"Error getting customers for sync: {e}")
            return []

    def mark_products_synced(self, product_ids: List[int]) -> bool:
        """
        Mark products as synced after successful push.

        Args:
            product_ids: List of product IDs to mark as synced

        Returns:
            True if successful, False otherwise
        """
        if not product_ids:
            return True

        try:
            placeholders = ','.join(['%s'] * len(product_ids))
            self.core.db.execute_write(
                f"UPDATE products SET synced = 1 WHERE id IN ({placeholders})",
                tuple(product_ids)
            )
            logger.info(f"✅ Marked {len(product_ids)} products as synced")
            return True
        except Exception as e:
            logger.error(f"Error marking products as synced: {e}")
            return False

    def mark_sales_synced(self, sale_ids: List[int]) -> bool:
        """
        Mark sales as synced after successful push.

        Args:
            sale_ids: List of sale IDs to mark as synced

        Returns:
            True if successful, False otherwise
        """
        if not sale_ids:
            return True

        try:
            placeholders = ','.join(['%s'] * len(sale_ids))
            self.core.db.execute_write(
                f"UPDATE sales SET synced = 1 WHERE id IN ({placeholders})",
                tuple(sale_ids)
            )
            logger.info(f"✅ Marked {len(sale_ids)} sales as synced")
            return True
        except Exception as e:
            logger.error(f"Error marking sales as synced: {e}")
            return False

    def mark_customers_synced(self, customer_ids: List[int]) -> bool:
        """
        Mark customers as synced after successful push.

        Args:
            customer_ids: List of customer IDs to mark as synced

        Returns:
            True if successful, False otherwise
        """
        if not customer_ids:
            return True

        try:
            placeholders = ','.join(['%s'] * len(customer_ids))
            self.core.db.execute_write(
                f"UPDATE customers SET synced = 1 WHERE id IN ({placeholders})",
                tuple(customer_ids)
            )
            logger.info(f"✅ Marked {len(customer_ids)} customers as synced")
            return True
        except Exception as e:
            logger.error(f"Error marking customers as synced: {e}")
            return False

    def get_inventory_movements_for_sync(self, limit: int = 500) -> List[Dict[str, Any]]:
        """
        Get unsynced inventory movements for delta sync (Parte A Fase 2).

        Returns:
            List of movement dicts with id, product_id, sku, movement_type, quantity, reason, reference_type, reference_id, branch_id, timestamp.
        """
        try:
            # E3: Límite alineado con sync_config (50000)
            limit_safe = max(1, min(int(limit), 50000)) if limit else 500
            rows = self.core.db.execute_query(
                """SELECT m.id, m.product_id, p.sku, m.movement_type, m.type, m.quantity, m.reason,
                          m.reference_type, m.reference_id, m.branch_id, m.timestamp
                   FROM inventory_movements m
                   LEFT JOIN products p ON p.id = m.product_id
                   WHERE (m.synced = 0 OR m.synced IS NULL)
                   ORDER BY m.id ASC
                   LIMIT %s""",
                (limit_safe,)
            )
            return [dict(row) for row in rows] if rows else []
        except Exception as e:
            logger.debug(f"get_inventory_movements_for_sync: {e}")
            return []

    def mark_inventory_movements_synced(self, movement_ids: List[int]) -> bool:
        """Mark inventory movements as synced after successful push (Parte A Fase 2)."""
        if not movement_ids:
            return True
        try:
            placeholders = ','.join(['%s'] * len(movement_ids))
            self.core.db.execute_write(
                f"UPDATE inventory_movements SET synced = 1 WHERE id IN ({placeholders})",
                tuple(movement_ids)
            )
            logger.info(f"✅ Marked {len(movement_ids)} inventory movements as synced")
            return True
        except Exception as e:
            logger.error(f"Error marking inventory movements as synced: {e}")
            return False
