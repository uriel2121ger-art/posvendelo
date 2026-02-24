"""
TITAN POS - Sales Service

Business logic for sales management.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from app.services.base_service import BaseService
from app.utils.db_helpers import row_to_dict, rows_to_dicts


class SalesService(BaseService):
    """
    Service for sales-related operations.
    """
    
    def get_by_id(self, sale_id: int) -> Optional[Dict[str, Any]]:
        """
        Get sale by ID.
        
        Args:
            sale_id: Sale ID
            
        Returns:
            Sale data or None
        """
        row = super().get_by_id('sales', sale_id)
        return row_to_dict(row)
    
    def list_by_customer(self, customer_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """
        List sales for a specific customer.
        
        Args:
            customer_id: Customer ID
            limit: Maximum number of results
            
        Returns:
            List of sales as dictionaries
        """
        # SECURITY: Parameterize LIMIT to prevent SQL injection
        limit = max(1, min(int(limit), 1000))
        query = """
            SELECT * FROM sales
            WHERE customer_id = %s
            ORDER BY timestamp DESC
            LIMIT %s
        """
        results = self.execute_query(query, (customer_id, limit))
        return rows_to_dicts(results)
    
    def list_by_date_range(self, start_date: str, end_date: str, 
                          branch_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        List sales within a date range.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            branch_id: Optional branch filter
            
        Returns:
            List of sales as dictionaries
        """
        query = "SELECT * FROM sales WHERE timestamp BETWEEN %s AND %s"
        params = [start_date, end_date]
        
        if branch_id:
            query += " AND branch_id = %s"
            params.append(branch_id)
        
        query += " ORDER BY timestamp DESC"
        
        results = self.execute_query(query, tuple(params))
        return rows_to_dicts(results)
    
    def get_total_sales(self, start_date: Optional[str] = None, 
                       end_date: Optional[str] = None,
                       branch_id: Optional[int] = None) -> float:
        """
        Get total sales amount for a period.
        
        Args:
            start_date: Optional start date
            end_date: Optional end date
            branch_id: Optional branch filter
            
        Returns:
            Total sales amount
        """
        query = "SELECT COALESCE(SUM(total), 0) FROM sales WHERE status = 'completed'"
        params = []

        if start_date and end_date:
            query += " AND timestamp BETWEEN %s AND %s"
            params.extend([start_date, end_date])

        if branch_id:
            query += " AND branch_id = %s"
            params.append(branch_id)
        
        result = self.execute_query(query, tuple(params))
        if result and len(result) > 0 and len(result[0]) > 0:
            raw_value = result[0][0] or 0
            return float(Decimal(str(raw_value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        return 0.0
    
    def get_customer_purchase_stats(self, customer_id: int) -> Dict[str, Any]:
        """
        Get purchase statistics for a customer.
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Statistics dictionary
        """
        # Total purchased
        total_query = """
            SELECT COALESCE(SUM(total), 0), COUNT(*), COALESCE(AVG(total), 0)
            FROM sales
            WHERE customer_id = %s AND status = 'completed'
        """
        result = self.execute_query(total_query, (customer_id,))
        
        if result and len(result) > 0 and len(result[0]) >= 3 and result[0][0] is not None:
            total = float(Decimal(str(result[0][0])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            count = int(result[0][1])
            average = float(Decimal(str(result[0][2])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        else:
            total = 0.0
            count = 0
            average = 0.0
        
        # Last purchase
        last_query = """
            SELECT timestamp
            FROM sales
            WHERE customer_id = %s AND status = 'completed'
            ORDER BY timestamp DESC
            LIMIT 1
        """
        last_result = self.execute_query(last_query, (customer_id,))
        last_purchase = last_result[0][0] if last_result and len(last_result) > 0 and len(last_result[0]) > 0 else None
        
        return {
            'total_purchased': total,
            'purchase_count': count,
            'average_ticket': average,
            'last_purchase': last_purchase
        }
