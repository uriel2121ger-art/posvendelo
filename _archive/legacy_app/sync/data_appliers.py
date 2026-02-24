"""
TITAN POS - Data Appliers

Apply data received from server to local database.
"""

from typing import Any, Dict, List
import logging
import time

from app.startup.bootstrap import log_debug
from app.sync.fk_validator import FKValidator

logger = logging.getLogger(__name__)


class DataApplier:
    """
    Applies server data to local database.

    Handles inventory, sales, and customer data synchronization
    with conflict resolution and batch processing.
    """

    def __init__(self, core):
        """
        Initialize the data applier.

        Args:
            core: POSCore instance with database access
        """
        self.core = core
        self.fk_validator = FKValidator(core.db)

    def apply_inventory(self, products: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Apply inventory data received from server to local database.

        Uses batch processing for optimal performance.

        Args:
            products: List of product dictionaries from server

        Returns:
            Dictionary with 'updated' and 'created' counts
        """
        start_time = time.time()
        result = {"updated": 0, "created": 0}

        log_debug("data_appliers:apply_inventory", "Started", {
            "products_count": len(products) if products else 0
        }, "B")

        try:
            if not products:
                return result

            # Get all existing SKUs in one query (optimized)
            skus_to_check = [p.get('sku') for p in products if p.get('sku')]
            if not skus_to_check:
                return result

            query_start = time.time()
            placeholders = ','.join(['%s'] * len(skus_to_check))
            existing_skus_result = self.core.db.execute_query(
                f"SELECT sku FROM products WHERE sku IN ({placeholders})",
                tuple(skus_to_check)
            )

            log_debug("data_appliers:apply_inventory", "SKU lookup completed", {
                "query_time_ms": (time.time() - query_start) * 1000,
                "existing_count": len(existing_skus_result) if existing_skus_result else 0
            }, "B")

            # Convert to set for O(1) lookup (backend returns dict-like rows via RealDictCursor)
            existing_skus = {row.get('sku') for row in (existing_skus_result or []) if row.get('sku')}

            operations = []

            for product in products:
                sku = product.get('sku')
                if not sku:
                    continue

                if sku in existing_skus:
                    # Update existing product (E12: normalizar None en stock/price)
                    operations.append((
                        """UPDATE products
                        SET name = %s, price = %s, stock = %s, category = %s,
                            provider = %s, is_favorite = %s, sale_type = %s,
                            min_stock = %s, max_stock = %s
                        WHERE sku = %s""",
                        (
                            product.get('name'),
                            (product.get('price') if product.get('price') is not None else 0),
                            (product.get('stock') if product.get('stock') is not None else 0),
                            product.get('category'),
                            product.get('provider'),
                            product.get('is_favorite', 0),
                            product.get('sale_type', 'unit'),
                            product.get('min_stock'),
                            product.get('max_stock'),
                            sku
                        )
                    ))
                    result["updated"] += 1
                else:
                    # Create new product (E12: normalizar None en stock/price)
                    # FIX: ON CONFLICT para evitar race conditions si otro proceso inserta el mismo SKU
                    operations.append((
                        """INSERT INTO products (
                            sku, name, price, stock, category, provider,
                            is_favorite, sale_type, min_stock, max_stock, synced
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
                        ON CONFLICT (sku) DO UPDATE SET
                            name = EXCLUDED.name,
                            price = EXCLUDED.price,
                            stock = EXCLUDED.stock,
                            category = EXCLUDED.category,
                            provider = EXCLUDED.provider,
                            is_favorite = EXCLUDED.is_favorite,
                            sale_type = EXCLUDED.sale_type,
                            min_stock = EXCLUDED.min_stock,
                            max_stock = EXCLUDED.max_stock,
                            synced = 1""",
                        (
                            sku,
                            product.get('name'),
                            (product.get('price') if product.get('price') is not None else 0),
                            (product.get('stock') if product.get('stock') is not None else 0),
                            product.get('category'),
                            product.get('provider'),
                            product.get('is_favorite', 0),
                            product.get('sale_type', 'unit'),
                            product.get('min_stock'),
                            product.get('max_stock')
                        )
                    ))
                    result["created"] += 1

            # Execute in batches
            if operations:
                batch_size = 1000
                batch_count = 0

                log_debug("data_appliers:apply_inventory", "Executing batches", {
                    "total_operations": len(operations),
                    "batch_size": batch_size
                }, "C")

                for i in range(0, len(operations), batch_size):
                    batch = operations[i:i + batch_size]
                    batch_count += 1
                    tx_result = self.core.db.execute_transaction(batch)
                    success = tx_result.get('success') if isinstance(tx_result, dict) else tx_result
                    if not success:
                        logger.error(f"Batch {batch_count} failed")

                total_time = time.time() - start_time
                logger.info(f"Inventory applied: {result['updated']} updated, {result['created']} created (took {total_time:.2f}s)")

        except Exception as e:
            logger.error(f"Error applying server inventory: {e}")
            log_debug("data_appliers:apply_inventory", "Error", {"error": str(e)}, "B")

        return result

    def apply_sales(self, sales: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Apply sales data received from server to local database.

        Handles UUID-based conflict resolution and sale items.

        Args:
            sales: List of sale dictionaries from server

        Returns:
            Dictionary with 'updated', 'created', and 'skipped' counts
        """
        result = {"updated": 0, "created": 0, "skipped": 0}

        try:
            operations = []

            for sale in sales:
                sale_id = sale.get('id')
                sale_uuid = sale.get('uuid')

                if not sale_uuid:
                    result["skipped"] += 1
                    continue

                # FIX: Validar FKs antes de procesar la venta
                sale = self.fk_validator.validate_sale(sale)

                # Check by UUID first (most reliable)
                # FIX: FOR UPDATE para evitar race conditions durante sync concurrente
                existing = self.core.db.execute_query(
                    "SELECT id, uuid FROM sales WHERE uuid = %s FOR UPDATE",
                    (sale_uuid,)
                )

                # Handle ID collision if not found by UUID
                use_uuid_insert = False
                final_sale_id = sale_id
                
                if not existing and sale_id:
                    # FIX: FOR UPDATE para evitar race conditions
                    existing_by_id = self.core.db.execute_query(
                        "SELECT id, uuid FROM sales WHERE id = %s FOR UPDATE",
                        (sale_id,)
                    )
                    if existing_by_id:
                        existing_uuid = existing_by_id[0]['uuid'] if existing_by_id else None
                        if existing_uuid == sale_uuid:
                            existing = existing_by_id
                            final_sale_id = sale_id
                        else:
                            # ID collision - different UUID = new sale, assign new ID
                            use_uuid_insert = True
                            final_sale_id = None  # Se asignará automáticamente
                            logger.info(f"⚠️ ID collision in PULL: local id={sale_id} has different UUID. Will assign new ID.")

                if existing:
                    # Update existing sale (found by UUID)
                    actual_sale_id = existing[0]['id']
                    operations.append(self._build_sale_update_query(sale, actual_sale_id))
                    result["updated"] += 1
                    sale_id_for_items = actual_sale_id
                else:
                    # Create new sale
                    if use_uuid_insert:
                        # Colisión de ID: insertar sin ID, usar UUID para encontrar el nuevo ID después
                        query, params = self._build_sale_insert_query(sale, None)  # None = AUTOINCREMENT
                        operations.append((query, params))
                        result["created"] += 1
                        sale_id_for_items = None  # Se actualizará después del INSERT
                    else:
                        # Insertar con ID normal
                        query, params = self._build_sale_insert_query(sale, sale_id)
                        operations.append((query, params))
                        result["created"] += 1
                        sale_id_for_items = sale_id

                # Process sale items (sale_items viene en el formato v2)
                # v2 envía como "sale_items", v1 como "items"
                items = sale.get('sale_items', sale.get('items', []))
                
                # Si usamos UUID insert, necesitamos obtener el nuevo ID después
                if use_uuid_insert and sale_uuid:
                    # Marcar para procesar items después de obtener el nuevo ID
                    sale['_needs_id_resolution'] = True
                    sale['_uuid_for_resolution'] = sale_uuid
                else:
                    # Procesar items normalmente
                    for item in items:
                        item_ops = self._build_item_operations(item, sale_id_for_items)
                        operations.extend(item_ops)

            # Execute all operations
            if operations:
                tx_result = self.core.db.execute_transaction(operations)
                success = tx_result.get('success') if isinstance(tx_result, dict) else tx_result
                if success:
                    logger.info(f"Sales applied: {result['updated']} updated, {result['created']} created, {result['skipped']} skipped")

                    # Resolver IDs para ventas que usaron UUID insert
                    deferred_sales = [s for s in sales if s.get('_needs_id_resolution')]
                    if deferred_sales:
                        self._resolve_sale_ids_and_items(deferred_sales)
                else:
                    logger.error("Sales transaction failed")

        except Exception as e:
            logger.error(f"Error applying server sales: {e}")

        return result

    def apply_customers(self, customers: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Apply customer data received from server to local database.

        Args:
            customers: List of customer dictionaries from server

        Returns:
            Dictionary with 'updated' and 'created' counts
        """
        result = {"updated": 0, "created": 0}

        try:
            operations = []

            for customer in customers:
                customer_id = customer.get('id')
                if not customer_id:
                    continue

                # FIX: FOR UPDATE para evitar race conditions durante sync
                existing = self.core.db.execute_query(
                    "SELECT id FROM customers WHERE id = %s FOR UPDATE",
                    (customer_id,)
                )

                # Server may send 'points' or 'loyalty_points'; local schema uses loyalty_points
                loyalty_points = customer.get('loyalty_points', customer.get('points', 0))
                if existing:
                    operations.append((
                        """UPDATE customers
                        SET name = %s, phone = %s, email = %s, address = %s,
                            credit_limit = %s, loyalty_points = %s, notes = %s
                        WHERE id = %s""",
                        (
                            customer.get('name'),
                            customer.get('phone'),
                            customer.get('email'),
                            customer.get('address'),
                            customer.get('credit_limit'),
                            loyalty_points,
                            customer.get('notes'),
                            customer_id
                        )
                    ))
                    result["updated"] += 1
                else:
                    operations.append((
                        """INSERT INTO customers (
                            id, name, phone, email, address,
                            credit_limit, loyalty_points, notes, is_active, synced
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, 1)""",
                        (
                            customer_id,
                            customer.get('name'),
                            customer.get('phone'),
                            customer.get('email'),
                            customer.get('address'),
                            customer.get('credit_limit', 0),
                            loyalty_points,
                            customer.get('notes')
                        )
                    ))
                    result["created"] += 1

            if operations:
                tx_result = self.core.db.execute_transaction(operations)
                success = tx_result.get('success') if isinstance(tx_result, dict) else tx_result
                if success:
                    logger.info(f"Customers applied: {result['updated']} updated, {result['created']} created")
                else:
                    logger.error("Customers transaction failed")

        except Exception as e:
            logger.error(f"Error applying server customers: {e}")

        return result

    def _build_sale_update_query(self, sale: Dict, sale_id: int) -> tuple:
        """Build SQL UPDATE query for existing sale."""
        return (
            """UPDATE sales SET
                uuid = COALESCE(%s, uuid),
                timestamp = COALESCE(%s, timestamp),
                subtotal = COALESCE(%s, subtotal),
                tax = COALESCE(%s, tax),
                total = COALESCE(%s, total),
                discount = COALESCE(%s, discount),
                payment_method = COALESCE(%s, payment_method),
                customer_id = COALESCE(%s, customer_id),
                user_id = COALESCE(%s, user_id),
                turn_id = NULL,  -- FIX: turn_id siempre NULL para ventas sync (turnos son locales)
                serie = COALESCE(%s, serie),
                folio = COALESCE(%s, folio),
                folio_visible = COALESCE(%s, folio_visible),
                branch_id = COALESCE(%s, branch_id),
                status = COALESCE(%s, status),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s""",
            (
                sale.get('uuid'),
                sale.get('timestamp'),
                sale.get('subtotal'),
                sale.get('tax'),
                sale.get('total'),
                sale.get('discount', 0),
                sale.get('payment_method'),
                sale.get('customer_id'),
                sale.get('user_id'),
                None,  # FIX: turn_id = NULL (turnos son locales, no sincronizar)
                sale.get('serie'),
                sale.get('folio'),
                sale.get('folio_visible'),
                sale.get('branch_id'),
                sale.get('status', 'completed'),
                sale_id
            )
        )

    def _build_sale_insert_query(self, sale: Dict, sale_id: int = None) -> tuple:
        """Build SQL INSERT query for new sale."""
        if sale_id:
            # FIX: turn_id siempre NULL para ventas sincronizadas (turnos son locales)
            return (
                """INSERT INTO sales (
                    id, uuid, timestamp, subtotal, tax, total, discount, payment_method,
                    customer_id, user_id, cashier_id, turn_id, serie, folio, folio_visible,
                    branch_id, status, synced, synced_from_terminal
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, 1, %s)""",
                (
                    sale_id,
                    sale.get('uuid'),
                    sale.get('timestamp'),
                    sale.get('subtotal', sale.get('total', 0.0) * 0.84),
                    sale.get('tax', sale.get('total', 0.0) * 0.16),
                    sale.get('total', 0.0),
                    sale.get('discount', 0.0),
                    sale.get('payment_method', 'cash'),
                    sale.get('customer_id'),
                    sale.get('user_id'),
                    sale.get('cashier_id') or sale.get('user_id'),
                    # turn_id es NULL directamente en el SQL
                    sale.get('serie', 'B'),
                    sale.get('folio'),
                    sale.get('folio_visible') or sale.get('folio'),
                    sale.get('branch_id', 1),
                    sale.get('status', 'completed'),
                    sale.get('synced_from_terminal', 'SERVER')
                )
            )
        else:
            # FIX: turn_id siempre NULL para ventas sincronizadas (turnos son locales)
            return (
                """INSERT INTO sales (
                    uuid, timestamp, subtotal, tax, total, discount, payment_method,
                    customer_id, user_id, cashier_id, turn_id, serie, folio, folio_visible,
                    branch_id, status, synced, synced_from_terminal
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, 1, %s)""",
                (
                    sale.get('uuid'),
                    sale.get('timestamp'),
                    sale.get('subtotal', sale.get('total', 0.0) * 0.84),
                    sale.get('tax', sale.get('total', 0.0) * 0.16),
                    sale.get('total', 0.0),
                    sale.get('discount', 0.0),
                    sale.get('payment_method', 'cash'),
                    sale.get('customer_id'),
                    sale.get('user_id'),
                    sale.get('cashier_id') or sale.get('user_id'),
                    # turn_id es NULL directamente en el SQL
                    sale.get('serie', 'B'),
                    sale.get('folio'),
                    sale.get('folio_visible') or sale.get('folio'),
                    sale.get('branch_id', 1),
                    sale.get('status', 'completed'),
                    sale.get('synced_from_terminal', 'SERVER')
                )
            )

    def _build_item_operations(self, item: Dict, sale_id: int) -> List[tuple]:
        """Build SQL operations for sale item."""
        operations = []
        item_id = item.get('id')

        # FIX: Validar que product_id existe antes de insertar
        product_id = item.get('product_id')
        if product_id:
            is_valid, _ = self.fk_validator.validate('product_id', product_id)
            if not is_valid:
                logger.warning(f"Skipping item: product_id={product_id} not found")
                return operations  # Skip this item

        if item_id:
            # FIX: FOR UPDATE para evitar race conditions
            existing = self.core.db.execute_query(
                "SELECT id FROM sale_items WHERE id = %s FOR UPDATE",
                (item_id,)
            )

            if existing:
                operations.append((
                    """UPDATE sale_items SET
                        sale_id = %s, product_id = %s, qty = %s, price = %s, subtotal = %s, name = %s
                    WHERE id = %s""",
                    (
                        sale_id,
                        item.get('product_id'),
                        item.get('qty', 1),
                        item.get('price', 0),
                        item.get('subtotal', 0),
                        item.get('name', ''),
                        item_id
                    )
                ))
            else:
                operations.append((
                    """INSERT INTO sale_items (
                        id, sale_id, product_id, qty, price, subtotal, name, synced
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, 1)""",
                    (
                        item_id,
                        sale_id,
                        item.get('product_id'),
                        item.get('qty', 1),
                        item.get('price', 0),
                        item.get('subtotal', 0),
                        item.get('name', '')
                    )
                ))
        else:
            operations.append((
                """INSERT INTO sale_items (
                    sale_id, product_id, qty, price, subtotal, name, synced
                ) VALUES (%s, %s, %s, %s, %s, %s, 1)""",
                (
                    sale_id,
                    item.get('product_id'),
                    item.get('qty', 1),
                    item.get('price', 0),
                    item.get('subtotal', 0),
                    item.get('name', '')
                )
            ))

        return operations

    def _resolve_sale_ids_and_items(self, sales: List[Dict]) -> None:
        """
        Resuelve IDs para ventas que usaron UUID insert y procesa sus items.
        
        Cuando hay colisión de ID, insertamos la venta sin ID (AUTOINCREMENT).
        Después necesitamos obtener el nuevo ID usando UUID y luego insertar los items.
        """
        operations = []
        
        for sale in sales:
            sale_uuid = sale.get('_uuid_for_resolution') or sale.get('uuid')
            if not sale_uuid:
                continue
            
            # Obtener el nuevo ID asignado usando UUID
            # FIX: FOR UPDATE para evitar race conditions al resolver IDs
            new_id_result = self.core.db.execute_query(
                "SELECT id FROM sales WHERE uuid = %s FOR UPDATE",
                (sale_uuid,)
            )
            
            if not new_id_result:
                logger.warning(f"Could not find new ID for sale with UUID {sale_uuid}")
                continue
            
            new_sale_id = new_id_result[0]['id']
            logger.info(f"✅ Resolved sale ID: {new_sale_id} for UUID {sale_uuid}")
            
            # Procesar items con el nuevo ID
            items = sale.get('sale_items', sale.get('items', []))
            for item in items:
                item_ops = self._build_item_operations(item, new_sale_id)
                operations.extend(item_ops)
        
        # Ejecutar todas las operaciones de items en una transacción
        if operations:
            result = self.core.db.execute_transaction(operations)
            success = result.get('success') if isinstance(result, dict) else result
            if success:
                logger.info(f"✅ Resolved and inserted items for {len(sales)} sales with ID collisions")
            else:
                logger.error("❌ Failed to insert items for sales with ID collisions")
    
    def _apply_deferred_items(self, sales: List[Dict]) -> None:
        """Apply items for sales that were inserted with ID collision (legacy method)."""
        # Este método ahora redirige a _resolve_sale_ids_and_items
        deferred_sales = [s for s in sales if s.get('uuid')]
        if deferred_sales:
            self._resolve_sale_ids_and_items(deferred_sales)
