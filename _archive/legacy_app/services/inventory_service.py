"""
TITAN POS - Inventory Service

Business logic for inventory management.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
import math

from app.services.base_service import BaseService
from app.utils.db_helpers import row_to_dict, rows_to_dicts


class InventoryService(BaseService):
    """
    Service for inventory-related operations.
    """
    
    def _ensure_column_exists(self, table_name: str, column_name: str, column_type: str = "TEXT") -> bool:
        """
        Helper function to ensure a column exists in a table before INSERT/UPDATE.
        Returns True if column exists, False otherwise.
        """
        try:
            table_info = self.db.get_table_info(table_name)
            if not table_info:
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
            
            return column_name in cols
        except Exception:
            return False
    
    def _validate_product_id(self, product_id: int) -> int:
        """Validate product_id parameter."""
        if product_id is None:
            raise ValueError("product_id es requerido")
        if isinstance(product_id, bool):
            raise ValueError("product_id no puede ser booleano")
        if isinstance(product_id, (list, dict, tuple, set)):
            raise ValueError(f"product_id inválido: tipo {type(product_id).__name__}")
        try:
            pid = int(product_id)
            if pid <= 0:
                raise ValueError(f"product_id debe ser mayor a 0: {pid}")
            if pid > 2**62:
                raise ValueError(f"product_id demasiado grande: {pid}")
            return pid
        except (TypeError, ValueError, OverflowError) as e:
            raise ValueError(f"product_id inválido: {e}")
    
    def _validate_quantity(self, quantity, allow_negative: bool = False) -> float:
        """Validate quantity parameter."""
        if quantity is None:
            raise ValueError("quantity es requerido")
        if isinstance(quantity, (list, dict, tuple, set)):
            raise ValueError(f"quantity inválido: tipo {type(quantity).__name__}")
        try:
            qty = float(quantity)
            if math.isnan(qty) or math.isinf(qty):
                raise ValueError("quantity no puede ser NaN o Infinito")
            if not allow_negative and qty < 0:
                raise ValueError(f"quantity no puede ser negativo: {qty}")
            return qty
        except (TypeError, ValueError) as e:
            raise ValueError(f"quantity inválido: {e}")
    
    def _validate_threshold(self, threshold: int) -> int:
        """Validate threshold parameter."""
        if threshold is None:
            return 10  # default
        if isinstance(threshold, (list, dict, tuple, set)):
            raise ValueError(f"threshold inválido: tipo {type(threshold).__name__}")
        try:
            th = int(threshold)
            if th < 0:
                raise ValueError(f"threshold no puede ser negativo: {th}")
            if th > 2**62:
                raise ValueError(f"threshold demasiado grande: {th}")
            return th
        except (TypeError, ValueError, OverflowError) as e:
            raise ValueError(f"threshold inválido: {e}")
    
    def get_movements(self, product_id: Optional[int] = None, 
                     limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get inventory movements.
        
        Args:
            product_id: Optional filter by product
            limit: Maximum number of results
            
        Returns:
            List of movements as dictionaries
        """
        query = "SELECT * FROM inventory_movements"
        params = ()
        
        if product_id is not None:
            pid = self._validate_product_id(product_id)
            query += " WHERE product_id = %s"
            params = (pid,)
        
        # SECURITY: Parameterize LIMIT to prevent SQL injection
        limit = max(1, min(int(limit), 1000))
        query += " ORDER BY timestamp DESC LIMIT %s"
        params = params + (limit,)

        results = self.execute_query(query, params)
        return rows_to_dicts(results)
    
    def add_stock(self, product_id: int, quantity: int, reason: str,
                 user_id: Optional[int] = None, branch_id: Optional[int] = None) -> int:
        """
        Add stock to a product.
        
        Args:
            product_id: Product ID
            quantity: Quantity to add
            reason: Reason for addition
            user_id: Optional user ID
            branch_id: Optional branch ID
            
        Returns:
            Movement ID
        """
        # Validaciones
        pid = self._validate_product_id(product_id)
        qty = self._validate_quantity(quantity)
        
        # CRITICAL FIX: Verificar si movement_type existe antes de INSERT
        has_movement_type = self._ensure_column_exists("inventory_movements", "movement_type", "TEXT")
        
        # CRITICAL FIX: Crear movement y actualizar stock en una sola transacción atómica
        ops = []
        
        # 1. Crear movement
        if has_movement_type:
            movement_query = """
                INSERT INTO inventory_movements (
                    product_id, movement_type, type, quantity, reason, user_id, branch_id, timestamp, synced
                ) VALUES (%s, 'IN', 'IN', %s, %s, %s, %s, NOW(), 0)
                RETURNING id
            """
            ops.append((movement_query, (pid, qty, reason, user_id, branch_id)))
        else:
            movement_query = """
                INSERT INTO inventory_movements (
                    product_id, type, quantity, reason, user_id, branch_id, timestamp, synced
                ) VALUES (%s, 'IN', %s, %s, %s, %s, NOW(), 0)
                RETURNING id
            """
            ops.append((movement_query, (pid, qty, reason, user_id, branch_id)))
        
        # 2. Update product stock
        update_query = """
            UPDATE products 
            SET stock = stock + %s 
            WHERE id = %s
        """
        ops.append((update_query, (qty, pid)))
        
        # Ejecutar en transacción atómica
        result = self.db.execute_transaction(ops, timeout=5)
        
        # Obtener movement_id del resultado
        if isinstance(result, dict) and result.get('inserted_ids'):
            movement_id = result['inserted_ids'][0] if result['inserted_ids'] else 0
        else:
            movement_id = 0
        
        return movement_id
    
    def remove_stock(self, product_id: int, quantity: int, reason: str,
                    user_id: Optional[int] = None, branch_id: Optional[int] = None) -> int:
        """
        Remove stock from a product.
        
        Args:
            product_id: Product ID
            quantity: Quantity to remove
            reason: Reason for removal
            user_id: Optional user ID
            branch_id: Optional branch ID
            
        Returns:
            Movement ID
        """
        # Validaciones
        pid = self._validate_product_id(product_id)
        qty = self._validate_quantity(quantity)

        # CRITICAL: Validate stock before removing to prevent negative stock
        current_product = self.get_by_id('products', pid)
        if current_product:
            current_stock = float(current_product.get('stock', 0) or 0)
            if current_stock < qty:
                raise ValueError(
                    f"Stock insuficiente: disponible {current_stock}, solicitado {qty}"
                )

        # CRITICAL FIX: Verificar si movement_type existe antes de INSERT
        has_movement_type = self._ensure_column_exists("inventory_movements", "movement_type", "TEXT")

        # CRITICAL FIX: Crear movement y actualizar stock en una sola transacción atómica
        ops = []

        # 1. Crear movement
        if has_movement_type:
            movement_query = """
                INSERT INTO inventory_movements (
                    product_id, movement_type, type, quantity, reason, user_id, branch_id, timestamp, synced
                ) VALUES (%s, 'OUT', 'OUT', %s, %s, %s, %s, NOW(), 0)
                RETURNING id
            """
            ops.append((movement_query, (pid, qty, reason, user_id, branch_id)))
        else:
            movement_query = """
                INSERT INTO inventory_movements (
                    product_id, type, quantity, reason, user_id, branch_id, timestamp, synced
                ) VALUES (%s, 'OUT', %s, %s, %s, %s, NOW(), 0)
                RETURNING id
            """
            ops.append((movement_query, (pid, qty, reason, user_id, branch_id)))

        # 2. Update product stock con metadata de sync (with CHECK constraint in WHERE)
        from datetime import datetime
        update_query = """
            UPDATE products
            SET stock = stock - %s,
                updated_at = %s,
                last_modified_by = %s,
                sync_version = sync_version + 1
            WHERE id = %s AND stock >= %s
        """
        terminal_id = self.core.get_terminal_identifier() if hasattr(self, 'core') and self.core else 'local'
        updated_at = datetime.now().isoformat()
        # Add qty twice: once for SET, once for WHERE constraint
        ops.append((update_query, (qty, updated_at, terminal_id, pid, qty)))
        
        # Ejecutar en transacción atómica
        result = self.db.execute_transaction(ops, timeout=5)
        
        # Obtener movement_id del resultado
        if isinstance(result, dict) and result.get('inserted_ids'):
            movement_id = result['inserted_ids'][0] if result['inserted_ids'] else 0
        else:
            movement_id = 0
        
        return movement_id
    
    def adjust_stock(self, product_id: int, new_quantity: int, reason: str,
                    user_id: Optional[int] = None, branch_id: Optional[int] = None) -> int:
        """
        Adjust stock to a specific quantity.

        Uses SELECT FOR UPDATE within a transaction to prevent race conditions
        when multiple users try to adjust the same product's stock simultaneously.

        Args:
            product_id: Product ID
            new_quantity: New stock quantity
            reason: Reason for adjustment
            user_id: Optional user ID
            branch_id: Optional branch ID

        Returns:
            Movement ID
        """
        # Validaciones
        pid = self._validate_product_id(product_id)
        new_qty = self._validate_quantity(new_quantity, allow_negative=True)  # Permitir 0

        # RACE CONDITION FIX: All operations in a single atomic transaction
        # 1. Lock the row with SELECT FOR UPDATE
        # 2. Insert movement record with computed difference
        # 3. Update stock to new value
        #
        # PostgreSQL CTE allows us to compute the difference atomically
        # while the row is locked, preventing race conditions.

        atomic_query = """
            WITH locked_product AS (
                SELECT id, stock FROM products WHERE id = %s FOR UPDATE
            ),
            movement_insert AS (
                INSERT INTO inventory_movements (
                    product_id, movement_type, type, quantity, reason, user_id, branch_id, timestamp, synced
                )
                SELECT
                    %s,
                    CASE WHEN %s - lp.stock >= 0 THEN 'IN' ELSE 'OUT' END,
                    CASE WHEN %s - lp.stock >= 0 THEN 'IN' ELSE 'OUT' END,
                    ABS(%s - lp.stock),
                    %s,
                    %s,
                    %s,
                    NOW(),
                    0
                FROM locked_product lp
                WHERE ABS(%s - lp.stock) > 0
                RETURNING id
            ),
            stock_update AS (
                UPDATE products p
                SET stock = %s, synced = 0
                FROM locked_product lp
                WHERE p.id = lp.id
            )
            SELECT COALESCE((SELECT id FROM movement_insert), 0) as movement_id,
                   (SELECT stock FROM locked_product) as old_stock
        """

        # Parameters: pid (lock), pid (insert), new_qty x4 (comparisons), reason, user_id, branch_id, new_qty (abs check), new_qty (update)
        params = (pid, pid, new_qty, new_qty, new_qty, reason, user_id, branch_id, new_qty, new_qty)

        try:
            result = self.db.execute_query(atomic_query, params)
            # FIX 2026-02-01: Validar result con len() antes de acceder a [0]
            if result and len(result) > 0 and result[0]:
                movement_id = result[0].get('movement_id', 0) or 0
                return int(movement_id)
            return 0
        except Exception as e:
            # Fallback for databases that don't support CTEs well
            # Use the simpler transaction approach
            product = self.get_by_id('products', pid)
            if not product:
                raise ValueError(f"Product {pid} not found")

            current_stock = float(product['stock'] or 0)
            difference = new_qty - current_stock

            # Use tolerance-based comparison for zero check (0.001 tolerance)
            if abs(difference) < 0.001:
                return 0

            movement_type = 'IN' if difference > 0 else 'OUT'

            # Atomic transaction: lock, insert movement, update stock
            ops = [
                ("SELECT id, stock FROM products WHERE id = %s FOR UPDATE", (pid,)),
                ("""INSERT INTO inventory_movements (
                        product_id, movement_type, type, quantity, reason, user_id, branch_id, timestamp, synced
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), 0)
                    RETURNING id""",
                 (pid, movement_type, movement_type, abs(difference), reason, user_id, branch_id)),
                ("UPDATE products SET stock = %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (new_qty, pid))
            ]

            result = self.db.execute_transaction(ops, timeout=5)
            if not result.get('success'):
                raise ValueError("Error ajustando stock: Transaction failed")

            inserted_ids = result.get('inserted_ids', [])
            return inserted_ids[0] if inserted_ids and inserted_ids[0] is not None else 0
    
    def get_low_stock_products(self, threshold: int = 10) -> List[Dict[str, Any]]:
        """
        Get products with low stock.
        
        Args:
            threshold: Stock threshold
            
        Returns:
            List of products with low stock
        """
        # Validación
        th = self._validate_threshold(threshold)
        
        query = """
            SELECT * FROM products
            WHERE stock <= %s AND is_active = 1
            ORDER BY stock ASC
        """
        results = self.execute_query(query, (th,))
        return rows_to_dicts(results)
    
    def get_stock_value(self, branch_id: Optional[int] = None) -> float:
        """
        Get total inventory value.
        
        Args:
            branch_id: Optional branch filter
            
        Returns:
            Total inventory value
        """
        query = "SELECT COALESCE(SUM(stock * cost), 0) FROM products WHERE is_active = 1"
        params = []
        
        if branch_id:
            query += " AND branch_id = %s"
            params.append(branch_id)
        
        result = self.execute_query(query, tuple(params))
        return float(result[0][0] or 0) if result and len(result) > 0 and len(result[0]) > 0 else 0.0
