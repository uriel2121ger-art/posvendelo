"""
TITAN POS - Customer Service

Business logic for customer management.
"""

from typing import Any, Dict, List, Optional

from app.services.base_service import BaseService
from app.utils.db_helpers import row_to_dict, rows_to_dicts
from app.utils.event_bus import EventTypes, publish


class CustomerService(BaseService):
    """
    Service for customer-related operations.
    """
    
    def create(self, data: Dict[str, Any]) -> int:
        """
        Create a new customer.
        
        Args:
            data: Customer data dictionary
            
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
        
        customer_id = self.execute_write(query, params)
        
        # Publish event
        publish(EventTypes.CUSTOMER_CREATED, {
            'customer_id': customer_id,
            'name': data.get('name', ''),
            'email': data.get('email', '')
        }, source='CustomerService')
        
        return customer_id
    
    def update(self, customer_id: int, data: Dict[str, Any]) -> bool:
        """
        Update an existing customer.
        
        Args:
            customer_id: Customer ID
            data: Customer data dictionary
            
        Returns:
            True if updated successfully
        """
        query = """
            UPDATE customers SET
                first_name = %s, last_name = %s, name = %s, email = %s, phone = %s,
                rfc = %s, fiscal_name = %s, address = %s, city = %s, state = %s,
                postal_code = %s, credit_authorized = %s, credit_limit = %s,
                vip = %s, notes = %s, loyalty_level = %s, points = %s, synced = 0,
                updated_at = CURRENT_TIMESTAMP
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
            customer_id
        )
        
        rows_affected = self.execute_write(query, params)
        
        # Publish event
        if rows_affected > 0:
            publish(EventTypes.CUSTOMER_UPDATED, {
                'customer_id': customer_id,
                'name': data.get('name', ''),
                'email': data.get('email', '')
            }, source='CustomerService')
        
        return rows_affected > 0
    
    def get(self, customer_id: int) -> Optional[Dict[str, Any]]:
        """
        Get customer by ID.
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Customer data or None
        """
        row = self.get_by_id('customers', customer_id)
        return row_to_dict(row)
    
    def list(self, query: Optional[str] = None, limit: int = 300) -> List[Any]:
        """
        List customers with optional search query.
        
        Args:
            query: Optional search query
            limit: Maximum number of results
            
        Returns:
            List of customer records
        """
        sql = "SELECT * FROM customers WHERE is_active = 1"
        params = ()

        if query:
            sql += """ AND (
                name LIKE %s OR
                first_name LIKE %s OR
                last_name LIKE %s OR
                email LIKE %s OR
                phone LIKE %s OR
                rfc LIKE %s
            )"""
            search_term = f"%{query}%"
            params = (search_term, search_term, search_term, search_term, search_term, search_term)
        
        # SECURITY: Parameterize LIMIT to prevent SQL injection
        limit = max(1, min(int(limit), 1000))
        sql += " ORDER BY name LIMIT %s"
        params = params + (limit,)

        return self.execute_query(sql, params)
    
    def search(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search customers and return as dictionaries.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of customer dictionaries
        """
        results = self.list(query, limit)
        return rows_to_dicts(results)
    
    def delete(self, customer_id: int) -> bool:
        """
        Delete a customer.
        
        Args:
            customer_id: Customer ID
            
        Returns:
            True if deleted successfully
        """
        # Get customer data before deletion for event
        customer = self.get(customer_id)
        
        deleted = self.delete_by_id('customers', customer_id)
        
        # Publish event
        if deleted and customer:
            publish(EventTypes.CUSTOMER_DELETED, {
                'customer_id': customer_id,
                'name': customer.get('name', '')
            }, source='CustomerService')
        
        return deleted
    
    def get_credit_info(self, customer_id: int) -> Dict[str, Any]:
        """
        Get customer credit information.
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Credit info dictionary
        """
        customer = self.get(customer_id)
        if not customer:
            return {
                'credit_limit': 0.0,
                'credit_balance': 0.0,
                'available_credit': 0.0,
                'credit_authorized': False
            }
        
        credit_limit = float(customer.get('credit_limit', 0) or 0)
        credit_balance = float(customer.get('credit_balance', 0) or 0)
        
        return {
            'credit_limit': credit_limit,
            'credit_balance': credit_balance,
            'available_credit': max(0.0, credit_limit - credit_balance),
            'credit_authorized': bool(customer.get('credit_authorized'))
        }
    
    def update_credit_balance(self, customer_id: int, new_balance: float) -> bool:
        """
        Update customer credit balance.
        
        Args:
            customer_id: Customer ID
            new_balance: New credit balance
            
        Returns:
            True if updated successfully
        """
        query = "UPDATE customers SET credit_balance = %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        rows_affected = self.execute_write(query, (new_balance, customer_id))
        return rows_affected > 0
    
    def get_full_profile(self, customer_id: int) -> Optional[Dict[str, Any]]:
        """
        Get full customer profile including credit history.
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Full profile dictionary or None
        """
        customer = self.get(customer_id)
        if not customer:
            return None
        
        # Get credit history
        credit_history_query = """
            SELECT * FROM credit_history 
            WHERE customer_id = %s 
            ORDER BY timestamp DESC 
            LIMIT 50
        """
        credit_history = self.execute_query(credit_history_query, (customer_id,))
        
        return {
            **customer,
            'credit_history': rows_to_dicts(credit_history)
        }
