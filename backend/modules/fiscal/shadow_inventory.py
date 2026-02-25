from pathlib import Path

"""
Shadow Inventory - Inventario Fantasma Desacoplado
Stock real vs Stock fiscal separados
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from decimal import Decimal
import logging
import sys

logger = logging.getLogger(__name__)

class ShadowInventory:
    """
    Sistema de inventario desacoplado.
    
    Mantiene dos vistas del inventario:
    - Stock Real: Lo que realmente hay en la tienda
    - Stock Fiscal: Lo que el SAT cree que hay (basado en XMLs de compra)
    
    El POS usa el stock real para operar.
    Las auditorías ven el stock fiscal.
    """
    
    def __init__(self, core):
        self.core = core
        import asyncio
        try:
            asyncio.get_running_loop().create_task(self._ensure_schema())
        except RuntimeError:
            pass
    
    async def _ensure_schema(self):
        """Asegura que existan las columnas necesarias."""
        # Agregar columna de stock sombra si no existe
        try:
            await self.core.db.execute_write("""
                ALTER TABLE products ADD COLUMN shadow_stock REAL DEFAULT 0
            """)
        except Exception as e:
            logger.debug(f"shadow_stock column already exists or could not be added: {e}")
        
        # Tabla de movimientos sombra
        await self.core.db.execute_write("""
            CREATE TABLE IF NOT EXISTS shadow_movements (
                id BIGSERIAL PRIMARY KEY,
                product_id INTEGER NOT NULL,
                movement_type TEXT NOT NULL,
                quantity REAL NOT NULL,
                real_stock_after REAL,
                fiscal_stock_after REAL,
                source TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    async def get_dual_stock(self, product_id: int) -> Dict[str, Any]:
        """Obtiene stock real y fiscal de un producto."""
        product = list(await self.core.db.execute_query("""
            SELECT id, name, stock, shadow_stock, min_stock
            FROM products WHERE id = %s
        """, (product_id,)))
        
        if not product:
            return {'found': False}
        
        p = product[0]
        real_stock = float(p['stock'] or 0)
        shadow = float(p['shadow_stock'] or 0)
        
        # Stock fiscal = Stock real - Shadow (compras sin factura)
        fiscal_stock = real_stock - shadow
        
        return {
            'found': True,
            'product_id': product_id,
            'name': p['name'],
            'real_stock': real_stock,
            'shadow_stock': shadow,
            'fiscal_stock': max(0, fiscal_stock),
            'discrepancy': shadow
        }
    
    async def add_shadow_stock(self, product_id: int, quantity: float, 
                        source: str = None, notes: str = None) -> Dict[str, Any]:
        """
        Agrega stock sombra (mercancía sin factura).
        El stock real aumenta, pero el fiscal no.
        """
        # Actualizar stock real y shadow (Parte A Fase 1.4: registrar movimiento)
        await self.core.db.execute_write("""
            UPDATE products 
            SET stock = stock + %s, synced = 0,
                shadow_stock = COALESCE(shadow_stock, 0) + %s
            WHERE id = %s
        """, (quantity, quantity, product_id))
        try:
            await self.core.db.execute_write(
                """INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                   VALUES (%s, 'IN', 'shadow_add', %s, %s, 'shadow_inventory', NOW(), 0)""",
                (product_id, quantity, notes or "Stock sombra")
            )
        except Exception as e:
            logger.debug("shadow_inventory add movement: %s", e)
        
        # Registrar movimiento
        dual = await self.get_dual_stock(product_id)
        
        await self.core.db.execute_write("""
            INSERT INTO shadow_movements 
            (product_id, movement_type, quantity, real_stock_after, 
             fiscal_stock_after, source, notes, created_at)
            VALUES (%s, 'ADD_SHADOW', %s, %s, %s, %s, %s, %s)
        """, (product_id, quantity, dual['real_stock'], dual['fiscal_stock'],
              source, notes, datetime.now().isoformat()))
        
        # SECURITY: No loguear operaciones Serie B a disco
        # Las operaciones shadow quedan solo en tabla shadow_movements
        pass
        
        return {
            'success': True,
            'real_stock': dual['real_stock'],
            'fiscal_stock': dual['fiscal_stock'],
            'shadow_added': quantity
        }
    
    async def sell_with_attribution(self, product_id: int, quantity: float, 
                             serie: str = 'B') -> Dict[str, Any]:
        """
        Procesa una venta atribuyendo correctamente al stock.
        
        Serie A: Reduce stock fiscal (venta reportable)
        Serie B: Reduce stock sombra primero (venta no reportable)
        """
        dual = await self.get_dual_stock(product_id)
        
        if not dual['found']:
            return {'success': False, 'error': 'Producto no encontrado'}
        
        if dual['real_stock'] < quantity:
            return {'success': False, 'error': 'Stock insuficiente'}
        
        if serie == 'A':
            # Venta fiscal - reduce del stock fiscal (Parte A Fase 1.4: movimiento en venta ya lo hace pos_engine)
            await self.core.db.execute_write("""
                UPDATE products SET stock = stock - %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s
            """, (quantity, product_id))
            try:
                await self.core.db.execute_write(
                    """INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                       VALUES (%s, 'OUT', 'shadow_sale', %s, %s, 'shadow_inventory', NOW(), 0)""",
                    (product_id, quantity, f"Venta Serie {serie}")
                )
            except Exception as e:
                logger.debug("shadow_inventory sale A movement: %s", e)
            
            # No tocar shadow_stock
            
        else:
            # Venta Serie B - reduce del shadow_stock primero
            shadow_available = dual['shadow_stock']
            
            if shadow_available >= quantity:
                # Todo del shadow (Parte A Fase 1.4: movimiento OUT)
                await self.core.db.execute_write("""
                    UPDATE products 
                    SET stock = stock - %s, synced = 0,
                        shadow_stock = shadow_stock - %s
                    WHERE id = %s
                """, (quantity, quantity, product_id))
            else:
                # Parte del shadow, parte del fiscal
                from_shadow = shadow_available
                from_fiscal = quantity - shadow_available
                
                await self.core.db.execute_write("""
                    UPDATE products 
                    SET stock = stock - %s, synced = 0,
                        shadow_stock = 0
                    WHERE id = %s
                """, (quantity, product_id))
            
            try:
                await self.core.db.execute_write(
                    """INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                       VALUES (%s, 'OUT', 'shadow_sale', %s, %s, 'shadow_inventory', NOW(), 0)""",
                    (product_id, quantity, f"Venta Serie {serie}")
                )
            except Exception as e:
                logger.debug("shadow_inventory sale B movement: %s", e)
        
        # Registrar movimiento
        new_dual = await self.get_dual_stock(product_id)
        
        await self.core.db.execute_write("""
            INSERT INTO shadow_movements 
            (product_id, movement_type, quantity, real_stock_after, 
             fiscal_stock_after, source, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (product_id, f'SALE_{serie}', -quantity, 
              new_dual['real_stock'], new_dual['fiscal_stock'],
              f'Venta Serie {serie}', datetime.now().isoformat()))
        
        return {
            'success': True,
            'serie': serie,
            'quantity_sold': quantity,
            'real_stock': new_dual['real_stock'],
            'fiscal_stock': new_dual['fiscal_stock']
        }
    
    async def get_audit_view(self) -> List[Dict]:
        """
        Retorna vista de inventario para auditoría.
        Solo muestra stock fiscal.
        """
        products = list(await self.core.db.execute_query("""
            SELECT id, sku, name, 
                   (stock - COALESCE(shadow_stock, 0)) as stock_auditable,
                   price
            FROM products
            WHERE status != 'deleted'
            ORDER BY name
        """))
        
        return [{
            'sku': p['sku'],
            'name': p['name'],
            'stock': max(0, float(p['stock_auditable'] or 0)),
            'price': float(p['price'] or 0)
        } for p in products]
    
    async def get_real_view(self) -> List[Dict]:
        """
        Retorna vista de inventario real.
        Para uso operativo interno.
        """
        products = list(await self.core.db.execute_query("""
            SELECT id, sku, name, stock as stock_real, 
                   COALESCE(shadow_stock, 0) as shadow,
                   price
            FROM products
            WHERE status != 'deleted'
            ORDER BY name
        """))
        
        return [{
            'sku': p['sku'],
            'name': p['name'],
            'stock_real': float(p['stock_real'] or 0),
            'stock_shadow': float(p['shadow'] or 0),
            'stock_fiscal': max(0, float(p['stock_real'] or 0) - float(p['shadow'] or 0)),
            'price': float(p['price'] or 0)
        } for p in products]
    
    async def reconcile_fiscal(self, product_id: int, fiscal_stock: float) -> Dict:
        """
        Reconcilia el stock fiscal con un valor conocido.
        Ajusta el shadow_stock para que la diferencia cuadre.
        """
        dual = await self.get_dual_stock(product_id)
        
        if not dual['found']:
            return {'success': False, 'error': 'Producto no encontrado'}
        
        # El shadow debe ser: real - fiscal
        new_shadow = dual['real_stock'] - fiscal_stock
        
        await self.core.db.execute_write("""
            UPDATE products SET shadow_stock = %s, synced = 0 WHERE id = %s
        """, (max(0, new_shadow), product_id))
        
        return {
            'success': True,
            'real_stock': dual['real_stock'],
            'new_fiscal': fiscal_stock,
            'new_shadow': max(0, new_shadow)
        }
    
    async def get_discrepancy_report(self) -> Dict[str, Any]:
        """Genera reporte de discrepancias entre stock real y fiscal."""
        products = list(await self.core.db.execute_query("""
            SELECT id, sku, name, stock, COALESCE(shadow_stock, 0) as shadow
            FROM products
            WHERE COALESCE(shadow_stock, 0) > 0
            ORDER BY shadow_stock DESC
        """))
        
        total_shadow = sum(float(p['shadow'] or 0) for p in products)
        
        return {
            'products_with_shadow': len(products),
            'total_shadow_units': total_shadow,
            'details': [{
                'sku': p['sku'],
                'name': p['name'],
                'real': float(p['stock'] or 0),
                'shadow': float(p['shadow'] or 0),
                'fiscal': float(p['stock'] or 0) - float(p['shadow'] or 0)
            } for p in products[:20]]
        }

# Función de migración para activar inventario sombra
async def activate_shadow_inventory(core) -> Dict:
    """Activa el sistema de inventario sombra."""
    shadow = ShadowInventory(core)
    
    # Inicializar shadow_stock en 0 para todos los productos
    core.db.execute_write("""
        UPDATE products SET shadow_stock = 0, synced = 0
        WHERE shadow_stock IS NULL
    """)
    
    return {'status': 'activated', 'message': 'Shadow inventory habilitado'}
