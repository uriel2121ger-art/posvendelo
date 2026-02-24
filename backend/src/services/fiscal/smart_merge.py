from pathlib import Path

"""
Smart Merge Inventory - Conciliación Inteligente de Costos A/B
Optimiza deducción fiscal promediando costos
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from decimal import Decimal
import logging
import sys

logger = logging.getLogger(__name__)

class SmartMerge:
    """
    Conciliación Inteligente de Costos A/B.
    
    Cuando compras mercancía:
    - Serie A: Con factura (costo deducible)
    - Serie B: Sin factura (efectivo, más barato)
    
    Este módulo:
    1. Promedia costos para utilidad real
    2. En reporte fiscal solo muestra costo A (maximiza deducción)
    3. Mantiene trazabilidad interna completa
    """
    
    def __init__(self, core):
        self.core = core
        self._ensure_schema()
    
    def _ensure_schema(self):
        """Asegura esquema para costos duales."""
        # Agregar columnas si no existen
        try:
            self.core.db.execute_write("""
                ALTER TABLE products ADD COLUMN cost_a REAL DEFAULT 0
            """)
        except Exception:
            pass  # Column already exists

        try:
            self.core.db.execute_write("""
                ALTER TABLE products ADD COLUMN cost_b REAL DEFAULT 0
            """)
        except Exception:
            pass  # Column already exists

        try:
            self.core.db.execute_write("""
                ALTER TABLE products ADD COLUMN qty_from_a REAL DEFAULT 0
            """)
        except Exception:
            pass  # Column already exists

        try:
            self.core.db.execute_write("""
                ALTER TABLE products ADD COLUMN qty_from_b REAL DEFAULT 0
            """)
        except Exception:
            pass  # Column already exists
        
        # Tabla de compras detallada
        self.core.db.execute_write("""
            CREATE TABLE IF NOT EXISTS purchase_costs (
                id SERIAL PRIMARY KEY,  -- FIX 2026-02-01: PostgreSQL
                product_id INTEGER NOT NULL,
                serie TEXT NOT NULL,
                quantity DECIMAL(15,2) NOT NULL,  -- FIX 2026-02-01: PostgreSQL
                unit_cost DECIMAL(15,2) NOT NULL,  -- FIX 2026-02-01: PostgreSQL
                total_cost DECIMAL(15,2) NOT NULL,  -- FIX 2026-02-01: PostgreSQL
                supplier TEXT,
                invoice_number TEXT,
                purchase_date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    def register_purchase(self, product_id: int, quantity: float, 
                         unit_cost: float, serie: str,
                         supplier: str = None,
                         invoice: str = None) -> Dict[str, Any]:
        """
        Registra una compra con su serie.
        
        serie='A': Compra con factura (costo fiscal deducible)
        serie='B': Compra en efectivo (no deducible pero más barato)
        """
        total_cost = quantity * unit_cost
        
        # Registrar en historial
        self.core.db.execute_write("""
            INSERT INTO purchase_costs 
            (product_id, serie, quantity, unit_cost, total_cost, supplier, invoice_number)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (product_id, serie, quantity, unit_cost, total_cost, supplier, invoice))
        
        # Actualizar producto
        if serie == 'A':
            self.core.db.execute_write("""
                UPDATE products 
                SET stock = stock + %s,
                    cost_a = ((cost_a * qty_from_a) + %s) / (qty_from_a + %s),
                    qty_from_a = qty_from_a + %s
                WHERE id = %s
            """, (quantity, total_cost, quantity, quantity, product_id))
        else:
            self.core.db.execute_write("""
                UPDATE products 
                SET stock = stock + %s,
                    cost_b = ((cost_b * qty_from_b) + %s) / (qty_from_b + %s),
                    qty_from_b = qty_from_b + %s
                WHERE id = %s
            """, (quantity, total_cost, quantity, quantity, product_id))
        
        # Recalcular costo promedio
        self._recalculate_blended_cost(product_id)
        
        # SECURITY: No loguear información de Serie
        pass
        
        return {
            'success': True,
            'product_id': product_id,
            'serie': serie,
            'quantity': quantity,
            'unit_cost': unit_cost,
            'total_cost': total_cost
        }
    
    def _recalculate_blended_cost(self, product_id: int):
        """
        Recalcula el costo promedio ponderado.
        
        CRITICAL FIX: Usa SELECT FOR UPDATE para bloquear el registro durante el cálculo.
        Esto previene race conditions donde otro proceso modifica los valores entre SELECT y UPDATE.
        """
        # CRITICAL FIX: Bloquear registro durante cálculo para evitar race conditions
        product = list(self.core.db.execute_query("""
            SELECT cost_a, cost_b, qty_from_a, qty_from_b
            FROM products WHERE id = %s
            FOR UPDATE
        """, (product_id,)))
        
        if not product:
            return
        
        p = product[0]
        cost_a = float(p['cost_a'] or 0)
        cost_b = float(p['cost_b'] or 0)
        qty_a = float(p['qty_from_a'] or 0)
        qty_b = float(p['qty_from_b'] or 0)
        
        total_qty = qty_a + qty_b
        if total_qty > 0:
            # Costo promedio real (interno)
            blended = (cost_a * qty_a + cost_b * qty_b) / total_qty
            
            # CRITICAL FIX: Actualizar en la misma transacción (el lock se mantiene)
            # Esto asegura que los valores usados para el cálculo no cambien antes del UPDATE
            self.core.db.execute_write("""
                UPDATE products SET cost = %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s
            """, (blended, product_id))
    
    def get_dual_cost_view(self, product_id: int) -> Dict[str, Any]:
        """Obtiene vista de costos duales de un producto."""
        product = list(self.core.db.execute_query("""
            SELECT name, sku, stock, cost, cost_a, cost_b, 
                   qty_from_a, qty_from_b, price
            FROM products WHERE id = %s
        """, (product_id,)))
        
        if not product:
            return {'found': False}
        
        p = product[0]
        cost_a = float(p['cost_a'] or 0)
        cost_b = float(p['cost_b'] or 0)
        cost_real = float(p['cost'] or 0)
        price = float(p['price'] or 0)
        
        return {
            'found': True,
            'name': p['name'],
            'sku': p['sku'],
            'stock': float(p['stock'] or 0),
            
            # Costos
            'cost_a': cost_a,          # Costo fiscal (deducible)
            'cost_b': cost_b,          # Costo real (más barato)
            'cost_blended': cost_real, # Promedio para utilidad real
            
            # Cantidades por origen
            'qty_from_a': float(p['qty_from_a'] or 0),
            'qty_from_b': float(p['qty_from_b'] or 0),
            
            # Márgenes
            'margin_fiscal': ((price - cost_a) / price * 100) if price > 0 else 0,
            'margin_real': ((price - cost_real) / price * 100) if price > 0 else 0,
            
            # Ahorro por compra B
            'savings': cost_a - cost_b if cost_a > cost_b else 0
        }
    
    def get_fiscal_cost(self, product_id: int) -> float:
        """
        Retorna el costo FISCAL de un producto.
        Este es el que se usa para calcular deducciones (Serie A).
        """
        product = list(self.core.db.execute_query("""
            SELECT cost_a, cost FROM products WHERE id = %s
        """, (product_id,)))
        
        if not product:
            return 0
        
        cost_a = float(product[0]['cost_a'] or 0)
        cost_default = float(product[0]['cost'] or 0)
        
        # Si hay costo A, usarlo; si no, usar costo default
        return cost_a if cost_a > 0 else cost_default
    
    def get_real_cost(self, product_id: int) -> float:
        """
        Retorna el costo REAL (promedio ponderado).
        Este es para calcular la utilidad interna.
        """
        product = list(self.core.db.execute_query("""
            SELECT cost FROM products WHERE id = %s
        """, (product_id,)))
        
        return float(product[0]['cost'] or 0) if product else 0
    
    def calculate_fiscal_vs_real_profit(self, sale_id: int) -> Dict[str, Any]:
        """
        Compara utilidad fiscal vs real de una venta.
        """
        # Obtener items de la venta
        items = list(self.core.db.execute_query("""
            SELECT si.product_id, si.qty, si.price, p.cost, p.cost_a
            FROM sale_items si
            JOIN products p ON si.product_id = p.id
            WHERE si.sale_id = %s
        """, (sale_id,)))
        
        total_revenue = 0
        total_cost_fiscal = 0
        total_cost_real = 0
        
        for item in items:
            qty = float(item['qty'] or 0)
            price = float(item['price'] or 0)
            cost_real = float(item['cost'] or 0)
            cost_a = float(item['cost_a'] or cost_real)
            
            total_revenue += qty * price
            total_cost_fiscal += qty * cost_a
            total_cost_real += qty * cost_real
        
        profit_fiscal = total_revenue - total_cost_fiscal
        profit_real = total_revenue - total_cost_real
        
        return {
            'sale_id': sale_id,
            'revenue': total_revenue,
            'cost_fiscal': total_cost_fiscal,
            'cost_real': total_cost_real,
            'profit_fiscal': profit_fiscal,   # Lo que el SAT ve
            'profit_real': profit_real,       # Tu utilidad real
            'tax_savings': profit_real - profit_fiscal  # Lo que te ahorras
        }
    
    def get_global_cost_report(self) -> Dict[str, Any]:
        """Reporte global de costos A vs B."""
        products = list(self.core.db.execute_query("""
            SELECT id, name, stock, cost, cost_a, cost_b, 
                   qty_from_a, qty_from_b, price
            FROM products
            WHERE (qty_from_a > 0 OR qty_from_b > 0)
        """))
        
        total_inventory_fiscal = 0
        total_inventory_real = 0
        total_products = len(products)
        
        for p in products:
            stock = float(p['stock'] or 0)
            cost_a = float(p['cost_a'] or 0)
            cost_real = float(p['cost'] or 0)
            
            total_inventory_fiscal += stock * cost_a
            total_inventory_real += stock * cost_real
        
        return {
            'products_with_dual_cost': total_products,
            'total_inventory_at_fiscal_cost': total_inventory_fiscal,
            'total_inventory_at_real_cost': total_inventory_real,
            'difference': total_inventory_fiscal - total_inventory_real,
            'message': f'Ahorro por compras B: ${total_inventory_fiscal - total_inventory_real:,.2f}'
        }

# Función de integración para pos_engine
def get_cost_for_sale(core, product_id: int, serie: str) -> float:
    """
    Obtiene el costo apropiado para una venta.
    
    Serie A: Usa costo fiscal (para calcular ISR)
    Serie B: Usa costo real (para utilidad interna)
    """
    sm = SmartMerge(core)
    
    if serie == 'A':
        return sm.get_fiscal_cost(product_id)
    else:
        return sm.get_real_cost(product_id)
