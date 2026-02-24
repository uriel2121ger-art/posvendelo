"""
TITAN POS - Product Repository

Data access layer for products.
"""

from typing import Any, Dict, List, Optional

from app.repositories.base_repository import BaseRepository


class ProductRepository(BaseRepository):
    """
    Repository for product data access.
    """
    
    def __init__(self):
        """Initialize product repository."""
        super().__init__('products')
    
    def create(self, data: Dict[str, Any]) -> int:
        """
        Create a new product.
        
        Args:
            data: Product data
            
        Returns:
            New product ID
        """
        query = """
            INSERT INTO products (
                sku, barcode, name, description, price, cost,
                stock, min_stock, category_id, is_active, synced, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, NOW())
        """

        params = (
            data.get('sku', ''),
            data.get('barcode', ''),
            data.get('name', ''),
            data.get('description', ''),
            data.get('price', 0.0),
            data.get('cost', 0.0),
            data.get('stock', 0),
            data.get('min_stock', 0),
            data.get('category_id'),
            data.get('is_active', 1),
        )

        try:
            # Use DatabaseManager.execute_write() instead of direct conn access
            product_id = self.db.execute_write(query, params)
            
            return product_id
        except Exception as e:
            
            raise
    
    def update(self, id_value: int, data: Dict[str, Any]) -> bool:
        """
        Update a product.
        
        Args:
            id_value: Product ID
            data: Updated data
            
        Returns:
            True if updated
        """
        query = """
            UPDATE products SET
                sku = %s, barcode = %s, name = %s, description = %s,
                price = %s, cost = %s, stock = %s, min_stock = %s,
                category_id = %s, is_active = %s, synced = 0, updated_at = NOW()
            WHERE id = %s
        """

        params = (
            data.get('sku', ''),
            data.get('barcode', ''),
            data.get('name', ''),
            data.get('description', ''),
            data.get('price', 0.0),
            data.get('cost', 0.0),
            data.get('stock', 0),
            data.get('min_stock', 0),
            data.get('category_id'),
            data.get('is_active', 1),
            id_value
        )

        try:
            # Use DatabaseManager.execute_write() instead of direct conn access
            rows_affected = self.db.execute_write(query, params)
            
            return rows_affected > 0
        except Exception as e:
            
            raise
    
    def find_by_sku(self, sku: str) -> Optional[Any]:
        """Find product by SKU."""
        results = self.find_where("sku = %s", (sku,))
        return results[0] if results else None
    
    def find_by_barcode(self, barcode: str) -> Optional[Any]:
        """Find product by barcode."""
        results = self.find_where("barcode = %s", (barcode,))
        return results[0] if results else None
    
    def find_low_stock(self, threshold: int = 10) -> List[Any]:
        """Find products with low stock."""
        return self.find_where("stock <= %s", (threshold,))
    
    def search(self, query: str, limit: int = 50) -> List[Any]:
        """Search products by name, SKU, or barcode."""
        search_query = "name LIKE %s OR sku LIKE %s OR barcode LIKE %s"
        search_term = f"%{query}%"
        # SECURITY: Parameterize LIMIT to prevent SQL injection
        limit = max(1, min(int(limit), 1000))  # Clamp between 1-1000
        sql = f"SELECT * FROM {self.table_name} WHERE {search_query} LIMIT %s"
        return self.db.execute_query(sql, (search_term, search_term, search_term, limit))
