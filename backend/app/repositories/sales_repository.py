"""
TITAN POS - Sales Repository

Data access layer for sales.
"""

from typing import Any, Dict, List, Optional

from app.repositories.base_repository import BaseRepository


class SalesRepository(BaseRepository):
    """
    Repository for sales data access.
    """
    
    def __init__(self):
        """Initialize sales repository."""
        super().__init__('sales')
    
    def create(self, data: Dict[str, Any]) -> int:
        """
        Create a new sale.
        
        Args:
            data: Sale data
            
        Returns:
            New sale ID
        """
        # Obtener origin_pc
        try:
            from app.utils.machine_identifier import get_machine_identifier_safe
            origin_pc = data.get('origin_pc') or get_machine_identifier_safe()
        except Exception:
            origin_pc = data.get('origin_pc', 'UNKNOWN-PC')
        
        query = """
            INSERT INTO sales (
                customer_id, user_id, branch_id, turn_id,
                subtotal, tax, discount, total,
                payment_method, status, synced, timestamp, origin_pc
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, NOW(), %s)
        """
        
        params = (
            data.get('customer_id'),
            data.get('user_id'),
            data.get('branch_id'),
            data.get('turn_id'),
            data.get('subtotal', 0.0),
            data.get('tax', 0.0),
            data.get('discount', 0.0),
            data.get('total', 0.0),
            data.get('payment_method', 'cash'),
            data.get('status', 'completed'),
            origin_pc,
        )

        try:
            # Use DatabaseManager.execute_write() instead of direct conn access
            sale_id = self.db.execute_write(query, params)
            
            return sale_id
        except Exception as e:
            
            raise
    
    def update(self, id_value: int, data: Dict[str, Any]) -> bool:
        """
        Update a sale.
        
        Args:
            id_value: Sale ID
            data: Updated data
            
        Returns:
            True if updated
        """
        query = """
            UPDATE sales SET
                status = %s, notes = %s, synced = 0, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        
        params = (
            data.get('status', 'completed'),
            data.get('notes', ''),
            id_value
        )

        try:
            # Use DatabaseManager.execute_write() instead of direct conn access
            rows_affected = self.db.execute_write(query, params)
            
            return rows_affected > 0
        except Exception as e:
            
            raise
    
    def find_by_customer(self, customer_id: int, limit: int = 100) -> List[Any]:
        """Find sales by customer."""
        # SECURITY: Use parameterized query for limit and specify columns
        limit = max(1, min(int(limit), 10000))
        sql = f"""
            SELECT id, folio, customer_id, user_id, branch_id, turn_id, subtotal, tax, discount, total,
                   payment_method, status, synced, timestamp, origin_pc, notes
            FROM {self.table_name}
            WHERE customer_id = %s
            ORDER BY timestamp DESC
            LIMIT %s
        """
        return self.db.execute_query(sql, (customer_id, limit))
    
    def find_by_date_range(self, start_date: str, end_date: str) -> List[Any]:
        """Find sales by date range."""
        return self.find_where(
            "timestamp BETWEEN %s AND %s",
            (start_date, end_date)
        )
    
    def find_by_status(self, status: str) -> List[Any]:
        """Find sales by status."""
        return self.find_where("status = %s", (status,))
