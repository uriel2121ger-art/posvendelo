"""
Shadow Inventory - Stock real vs Stock fiscal desacoplados
"""

from typing import Any, Dict, List
from datetime import datetime
from decimal import Decimal
import logging

from modules.shared.constants import money, dec

logger = logging.getLogger(__name__)


class ShadowInventory:
    def __init__(self, db):
        self.db = db

    async def ensure_schema(self):
        try:
            await self.db.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS shadow_stock REAL DEFAULT 0")
        except Exception:
            pass

        await self.db.execute("""
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
        p = await self.db.fetchrow("SELECT id, name, stock, shadow_stock, min_stock FROM products WHERE id = :pid", pid=product_id)
        if not p:
            return {'found': False}

        real = dec(p['stock'])
        shadow = dec(p['shadow_stock'])
        fiscal = real - shadow

        return {
            'found': True, 'product_id': product_id, 'name': p['name'],
            'real_stock': money(real), 'shadow_stock': money(shadow),
            'fiscal_stock': money(max(Decimal('0'), fiscal)), 'discrepancy': money(shadow)
        }

    async def add_shadow_stock(self, product_id: int, quantity: float, source: str = None, notes: str = None) -> Dict[str, Any]:
        conn = self.db.connection
        async with conn.transaction():
            await self.db.fetchrow(
                "SELECT id FROM products WHERE id = :pid FOR UPDATE", pid=product_id)

            await self.db.execute("""
                UPDATE products SET stock = stock + :qty, synced = 0, shadow_stock = COALESCE(shadow_stock, 0) + :qty WHERE id = :pid
            """, qty=quantity, pid=product_id)

            try:
                await self.db.execute("""
                    INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                    VALUES (:pid, 'IN', 'shadow_add', :qty, :notes, 'shadow_inventory', NOW(), 0)
                """, pid=product_id, qty=quantity, notes=notes or "Stock sombra")
            except Exception:
                pass

            dual = await self.get_dual_stock(product_id)

            await self.db.execute("""
                INSERT INTO shadow_movements (product_id, movement_type, quantity, real_stock_after, fiscal_stock_after, source, notes, created_at)
                VALUES (:pid, 'ADD_SHADOW', :qty, :real, :fiscal, :src, :notes, :ts)
            """, pid=product_id, qty=quantity, real=dual['real_stock'], fiscal=dual['fiscal_stock'],
                src=source, notes=notes, ts=datetime.now().isoformat())

        return {'success': True, 'real_stock': dual['real_stock'], 'fiscal_stock': dual['fiscal_stock'], 'shadow_added': quantity}

    async def sell_with_attribution(self, product_id: int, quantity: float, serie: str = 'B') -> Dict[str, Any]:
        conn = self.db.connection
        async with conn.transaction():
            # Lock the product row to prevent concurrent stock modifications
            p = await self.db.fetchrow(
                "SELECT id, name, stock, shadow_stock, min_stock FROM products WHERE id = :pid FOR UPDATE",
                pid=product_id,
            )
            if not p:
                return {'success': False, 'error': 'Producto no encontrado'}

            real_stock = dec(p['stock'])
            shadow_stock = dec(p['shadow_stock'])

            if real_stock < quantity:
                return {'success': False, 'error': 'Stock insuficiente'}

            qty_dec = dec(str(quantity))
            if serie == 'A':
                await self.db.execute("UPDATE products SET stock = stock - :qty, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = :pid", qty=quantity, pid=product_id)
                real_after = real_stock - qty_dec
                shadow_after = shadow_stock
            else:
                if shadow_stock >= quantity:
                    await self.db.execute("UPDATE products SET stock = stock - :qty, synced = 0, shadow_stock = shadow_stock - :qty WHERE id = :pid", qty=quantity, pid=product_id)
                    shadow_after = shadow_stock - qty_dec
                else:
                    await self.db.execute("UPDATE products SET stock = stock - :qty, synced = 0, shadow_stock = 0 WHERE id = :pid", qty=quantity, pid=product_id)
                    shadow_after = Decimal('0')
                real_after = real_stock - qty_dec
            fiscal_after = max(Decimal('0'), real_after - shadow_after)

            try:
                await self.db.execute("""
                    INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                    VALUES (:pid, 'OUT', 'shadow_sale', :qty, :reason, 'shadow_inventory', NOW(), 0)
                """, pid=product_id, qty=quantity, reason=f"Venta Serie {serie}")
            except Exception:
                pass

            await self.db.execute("""
                INSERT INTO shadow_movements (product_id, movement_type, quantity, real_stock_after, fiscal_stock_after, source, created_at)
                VALUES (:pid, :mt, :qty, :real, :fiscal, :src, :ts)
            """, pid=product_id, mt=f'SALE_{serie}', qty=-quantity,
                real=money(real_after), fiscal=money(fiscal_after),
                src=f'Venta Serie {serie}', ts=datetime.now().isoformat())

        new_dual = await self.get_dual_stock(product_id)
        return {'success': True, 'serie': serie, 'quantity_sold': quantity, 'real_stock': new_dual['real_stock'], 'fiscal_stock': new_dual['fiscal_stock']}

    async def get_audit_view(self) -> List[Dict]:
        await self.ensure_schema()
        products = await self.db.fetch("""
            SELECT id, sku, name, (stock - COALESCE(shadow_stock, 0)) as stock_auditable, price
            FROM products WHERE is_active = 1 ORDER BY name LIMIT 5000
        """)
        return [{'sku': p['sku'], 'name': p['name'], 'stock': money(max(Decimal('0'), dec(p['stock_auditable']))), 'price': money(p['price'])} for p in products]

    async def get_real_view(self) -> List[Dict]:
        await self.ensure_schema()
        products = await self.db.fetch("""
            SELECT id, sku, name, stock as stock_real, COALESCE(shadow_stock, 0) as shadow, price
            FROM products WHERE is_active = 1 ORDER BY name LIMIT 5000
        """)
        return [{
            'sku': p['sku'], 'name': p['name'],
            'stock_real': money(p['stock_real']), 'stock_shadow': money(p['shadow']),
            'stock_fiscal': money(max(Decimal('0'), dec(p['stock_real']) - dec(p['shadow']))),
            'price': money(p['price'])
        } for p in products]

    async def reconcile_fiscal(self, product_id: int, fiscal_stock: float) -> Dict:
        conn = self.db.connection
        async with conn.transaction():
            row = await self.db.fetchrow(
                "SELECT stock, shadow_stock FROM products WHERE id = :pid FOR UPDATE",
                pid=product_id,
            )
            if not row:
                return {'success': False, 'error': 'Producto no encontrado'}

            real_stock = dec(row['stock'])
            new_shadow = max(Decimal('0'), real_stock - Decimal(str(fiscal_stock)))
            await self.db.execute("UPDATE products SET shadow_stock = :sh, synced = 0 WHERE id = :pid", sh=new_shadow, pid=product_id)
        return {'success': True, 'real_stock': money(real_stock), 'new_fiscal': fiscal_stock, 'new_shadow': money(new_shadow)}

    async def get_discrepancy_report(self) -> Dict[str, Any]:
        products = await self.db.fetch("""
            SELECT id, sku, name, stock, COALESCE(shadow_stock, 0) as shadow
            FROM products WHERE COALESCE(shadow_stock, 0) > 0 ORDER BY shadow_stock DESC
        """)
        total_shadow = money(sum(Decimal(str(p['shadow'] or 0)) for p in products))
        return {
            'products_with_shadow': len(products),
            'total_shadow_units': total_shadow,
            'details': [{'sku': p['sku'], 'name': p['name'], 'real': money(p['stock']),
                          'shadow': money(p['shadow']), 'fiscal': money(Decimal(str(p['stock'] or 0)) - Decimal(str(p['shadow'] or 0)))} for p in products[:20]]
        }
