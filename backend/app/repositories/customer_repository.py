"""
TITAN POS - Customer Repository

Data access layer for customers.
"""

from typing import Any, Dict, List, Optional

from app.repositories.base_repository import BaseRepository


class CustomerRepository(BaseRepository):
    """
    Repository for customer data access.
    """
    
    def __init__(self):
        """Initialize customer repository."""
        super().__init__('customers')
    
    def create(self, data: Dict[str, Any]) -> int:
        """
        Create a new customer.
        
        Args:
            data: Customer data
            
        Returns:
            New customer ID
        """
        query = """
            INSERT INTO customers (
                first_name, last_name, name, email, phone, rfc,
                fiscal_name, address, city, state, postal_code,
                credit_authorized, credit_limit, credit_balance,
                vip, notes, loyalty_level, points, synced, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, NOW())
        """
        
        params = (
            data.get('first_name', ''),
            data.get('last_name', ''),
            data.get('name', ''),
            data.get('email', ''),
            data.get('phone', ''),
            data.get('rfc', ''),
            data.get('fiscal_name', ''),
            data.get('address', ''),
            data.get('city', ''),
            data.get('state', ''),
            data.get('postal_code', ''),
            data.get('credit_authorized', 0),
            data.get('credit_limit', 0.0),
            data.get('credit_balance', 0.0),
            data.get('vip', 0),
            data.get('notes', ''),
            data.get('loyalty_level', 'Bronze'),
            data.get('points', 0),
        )

        try:
            # Use DatabaseManager.execute_write() instead of direct conn access
            customer_id = self.db.execute_write(query, params)
            
            return customer_id
        except Exception as e:
            
            raise
    
    def update(self, id_value: int, data: Dict[str, Any]) -> bool:
        """
        Update a customer.
        
        Args:
            id_value: Customer ID
            data: Updated data
            
        Returns:
            True if updated
        """
        query = """
            UPDATE customers SET
                first_name = %s, last_name = %s, name = %s, email = %s, phone = %s,
                rfc = %s, fiscal_name = %s, address = %s, city = %s, state = %s,
                postal_code = %s, credit_authorized = %s, credit_limit = %s,
                vip = %s, notes = %s, loyalty_level = %s, points = %s,
                synced = 0, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        
        params = (
            data.get('first_name', ''),
            data.get('last_name', ''),
            data.get('name', ''),
            data.get('email', ''),
            data.get('phone', ''),
            data.get('rfc', ''),
            data.get('fiscal_name', ''),
            data.get('address', ''),
            data.get('city', ''),
            data.get('state', ''),
            data.get('postal_code', ''),
            data.get('credit_authorized', 0),
            data.get('credit_limit', 0.0),
            data.get('vip', 0),
            data.get('notes', ''),
            data.get('loyalty_level', 'Bronze'),
            data.get('points', 0),
            id_value
        )

        try:
            # Use DatabaseManager.execute_write() instead of direct conn access
            rows_affected = self.db.execute_write(query, params)
            
            return rows_affected > 0
        except Exception as e:
            
            raise
    
    def find_by_rfc(self, rfc: str) -> Optional[Any]:
        """
        Find customer by RFC.
        
        Args:
            rfc: RFC value
            
        Returns:
            Customer record or None
        """
        results = self.find_where("rfc = %s", (rfc,))
        return results[0] if results else None
    
    def find_by_email(self, email: str) -> Optional[Any]:
        """
        Find customer by email.
        
        Args:
            email: Email address
            
        Returns:
            Customer record or None
        """
        results = self.find_where("email = %s", (email,))
        return results[0] if results else None
    
    def search(self, query: str, limit: int = 50) -> List[Any]:
        """
        Search customers by name, email, phone, or RFC.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of matching customers
        """
        search_query = """
            name LIKE %s OR 
            first_name LIKE %s OR 
            last_name LIKE %s OR 
            email LIKE %s OR 
            phone LIKE %s OR 
            rfc LIKE %s
        """
        search_term = f"%{query}%"
        params = (search_term, search_term, search_term, search_term, search_term, search_term)
        
        # SECURITY: Parameterize LIMIT to prevent SQL injection
        limit = max(1, min(int(limit), 1000))  # Clamp between 1-1000
        sql = f"SELECT * FROM {self.table_name} WHERE {search_query} LIMIT %s"
        return self.db.execute_query(sql, params + (limit,))
    
    def find_vip_customers(self) -> List[Any]:
        """
        Find all VIP customers.
        
        Returns:
            List of VIP customers
        """
        return self.find_where("vip = 1", ())
    
    def find_with_credit(self) -> List[Any]:
        """
        Find customers with authorized credit.
        
        Returns:
            List of customers with credit
        """
        return self.find_where("credit_authorized = 1", ())
