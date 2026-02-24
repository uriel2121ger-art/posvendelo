"""
TITAN POS - Product Service

Business logic for product management.
"""

from typing import Any, Dict, List, Optional

from app.services.base_service import BaseService
from app.utils.db_helpers import row_to_dict, rows_to_dicts


class ProductService(BaseService):
    """
    Service for product-related operations.
    """
    
    def get_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """
        Get product by SKU or barcode.
        
        Args:
            sku: Product SKU or barcode
            
        Returns:
            Product data or None
        """
        query = "SELECT * FROM products WHERE barcode = %s OR sku = %s"
        results = self.execute_query(query, (sku, sku))
        return row_to_dict(results[0]) if results else None
    
    def get_by_id(self, product_id: int) -> Optional[Dict[str, Any]]:
        """
        Get product by ID.
        
        Args:
            product_id: Product ID
            
        Returns:
            Product data or None
        """
        row = super().get_by_id('products', product_id)
        return row_to_dict(row)
    
    def list(self, limit: int = 50, offset: int = 0, query: Optional[str] = None) -> List[Any]:
        """
        List products with optional search and pagination.
        
        Args:
            limit: Maximum number of results
            offset: Offset for pagination
            query: Optional search query
            
        Returns:
            List of product records
        """
        sql = "SELECT * FROM products"
        params = ()
        
        if query:
            sql += """ WHERE 
                name LIKE %s OR 
                barcode LIKE %s OR 
                sku LIKE %s OR 
                description LIKE %s
            """
            search_term = f"%{query}%"
            params = (search_term, search_term, search_term, search_term)
        
        # SECURITY: Parameterize LIMIT/OFFSET to prevent SQL injection
        limit = max(1, min(int(limit), 1000))
        offset = max(0, int(offset))
        sql += " ORDER BY name LIMIT %s OFFSET %s"
        params = params + (limit, offset)

        return self.execute_query(sql, params)
    
    def search(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search products and return as dictionaries.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of product dictionaries
        """
        results = self.list(limit=limit, query=query)
        return rows_to_dicts(results)
    
    def count(self, query: Optional[str] = None) -> int:
        """
        Count products with optional search query.
        
        Args:
            query: Optional search query
            
        Returns:
            Count of products
        """
        if query:
            where_clause = """
                name LIKE %s OR 
                barcode LIKE %s OR 
                sku LIKE %s OR 
                description LIKE %s
            """
            search_term = f"%{query}%"
            params = (search_term, search_term, search_term, search_term)
            return super().count('products', where_clause, params)
        else:
            return super().count('products')
    
    def list_for_export(self) -> List[Dict[str, Any]]:
        """
        List all products for export.
        
        Returns:
            List of all products as dictionaries
        """
        results = self.execute_query("SELECT * FROM products ORDER BY name")
        return rows_to_dicts(results)
