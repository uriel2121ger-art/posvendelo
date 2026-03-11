"""
Smart Merge Inventory - Conciliación Inteligente de Costos A/B
"""

from typing import Any, Dict, List
from datetime import datetime
from decimal import Decimal
import logging

from modules.shared.constants import money

logger = logging.getLogger(__name__)


class SmartMerge:
    def __init__(self, db):
        self.db = db

    async def ensure_schema(self):
        for col in ['cost_a REAL DEFAULT 0', 'cost_b REAL DEFAULT 0', 'qty_from_a REAL DEFAULT 0', 'qty_from_b REAL DEFAULT 0']:
            try:
                await self.db.execute(f"ALTER TABLE products ADD COLUMN IF NOT EXISTS {col}")
            except Exception:
                pass

        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS purchase_costs (
                id BIGSERIAL PRIMARY KEY,
                product_id INTEGER NOT NULL,
                serie TEXT NOT NULL,
                quantity NUMERIC(12,2) NOT NULL,
                unit_cost NUMERIC(12,2) NOT NULL,
                total_cost NUMERIC(12,2) NOT NULL,
                supplier TEXT,
                invoice_number TEXT,
                purchase_date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

    async def register_purchase(self, product_id: int, quantity: float, unit_cost: float, serie: str,
                                 supplier: str = None, invoice: str = None) -> Dict[str, Any]:
        quantity = Decimal(str(quantity))
        unit_cost = Decimal(str(unit_cost))
        total_cost = (quantity * unit_cost).quantize(Decimal("0.01"))

        conn = self.db.connection
        async with conn.transaction():
            await self.db.fetchrow(
                "SELECT id FROM products WHERE id = :pid FOR UPDATE", pid=product_id)

            await self.db.execute("""
                INSERT INTO purchase_costs (product_id, serie, quantity, unit_cost, total_cost, supplier, invoice_number)
                VALUES (:pid, :serie, :qty, :uc, :tc, :sup, :inv)
            """, pid=product_id, serie=serie, qty=quantity, uc=unit_cost, tc=total_cost, sup=supplier, inv=invoice)

            if serie == 'A':
                await self.db.execute("""
                    UPDATE products SET stock = stock + :qty, synced = 0,
                        cost_a = ((cost_a * qty_from_a) + :tc) / (qty_from_a + :qty),
                        qty_from_a = qty_from_a + :qty
                    WHERE id = :pid
                """, qty=quantity, tc=total_cost, pid=product_id)
            else:
                await self.db.execute("""
                    UPDATE products SET stock = stock + :qty, synced = 0,
                        cost_b = ((cost_b * qty_from_b) + :tc) / (qty_from_b + :qty),
                        qty_from_b = qty_from_b + :qty
                    WHERE id = :pid
                """, qty=quantity, tc=total_cost, pid=product_id)

            try:
                await self.db.execute("""
                    INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                    VALUES (:pid, 'IN', 'smart_merge', :qty, :reason, 'smart_merge', NOW(), 0)
                """, pid=product_id, qty=quantity, reason=f"Compra {serie} {invoice or ''}")
            except Exception:
                pass

            await self._recalculate_blended_cost(product_id)

        return {'success': True, 'product_id': product_id, 'serie': serie, 'quantity': quantity, 'unit_cost': unit_cost, 'total_cost': total_cost}

    async def _recalculate_blended_cost(self, product_id: int):
        p = await self.db.fetchrow("SELECT cost_a, cost_b, qty_from_a, qty_from_b FROM products WHERE id = :pid", pid=product_id)
        if not p:
            return

        cost_a = Decimal(str(p['cost_a'] or 0))
        cost_b = Decimal(str(p['cost_b'] or 0))
        qty_a = Decimal(str(p['qty_from_a'] or 0))
        qty_b = Decimal(str(p['qty_from_b'] or 0))
        total_qty = qty_a + qty_b

        if total_qty > 0:
            blended = ((cost_a * qty_a + cost_b * qty_b) / total_qty).quantize(Decimal("0.01"))
            await self.db.execute("UPDATE products SET cost = :cost, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = :pid", cost=blended, pid=product_id)

    async def get_dual_cost_view(self, product_id: int) -> Dict[str, Any]:
        p = await self.db.fetchrow("SELECT name, sku, stock, cost, cost_a, cost_b, qty_from_a, qty_from_b, price FROM products WHERE id = :pid", pid=product_id)
        if not p:
            return {'found': False}

        cost_a, cost_b, cost_real, price = money(p['cost_a']), money(p['cost_b']), money(p['cost']), money(p['price'])

        return {
            'found': True, 'name': p['name'], 'sku': p['sku'], 'stock': money(p['stock']),
            'cost_a': cost_a, 'cost_b': cost_b, 'cost_blended': cost_real,
            'qty_from_a': money(p['qty_from_a']), 'qty_from_b': money(p['qty_from_b']),
            'margin_fiscal': ((price - cost_a) / price * 100) if price > 0 else 0,
            'margin_real': ((price - cost_real) / price * 100) if price > 0 else 0,
            'savings': cost_a - cost_b if cost_a > cost_b else 0
        }

    async def get_fiscal_cost(self, product_id: int) -> float:
        p = await self.db.fetchrow("SELECT cost_a, cost FROM products WHERE id = :pid", pid=product_id)
        if not p:
            return 0
        cost_a = money(p['cost_a'])
        return cost_a if cost_a > 0 else money(p['cost'])

    async def get_real_cost(self, product_id: int) -> float:
        p = await self.db.fetchrow("SELECT cost FROM products WHERE id = :pid", pid=product_id)
        return money(p['cost']) if p else 0

    async def calculate_fiscal_vs_real_profit(self, sale_id: int) -> Dict[str, Any]:
        items = await self.db.fetch("""
            SELECT si.product_id, si.qty, si.price, p.cost, p.cost_a
            FROM sale_items si JOIN products p ON si.product_id = p.id WHERE si.sale_id = :sid
        """, sid=sale_id)

        total_revenue, total_cost_fiscal, total_cost_real = 0.0, 0.0, 0.0
        for item in items:
            qty, price = money(item['qty']), money(item['price'])
            cost_real = money(item['cost'])
            cost_a = money(item['cost_a'] if item['cost_a'] else cost_real)
            total_revenue += qty * price
            total_cost_fiscal += qty * cost_a
            total_cost_real += qty * cost_real

        return {
            'sale_id': sale_id, 'revenue': total_revenue,
            'cost_fiscal': total_cost_fiscal, 'cost_real': total_cost_real,
            'profit_fiscal': total_revenue - total_cost_fiscal,
            'profit_real': total_revenue - total_cost_real,
            'tax_savings': (total_revenue - total_cost_real) - (total_revenue - total_cost_fiscal)
        }

    async def get_global_cost_report(self) -> Dict[str, Any]:
        products = await self.db.fetch("SELECT id, name, stock, cost, cost_a, cost_b, qty_from_a, qty_from_b, price FROM products WHERE (qty_from_a > 0 OR qty_from_b > 0)")

        total_fiscal, total_real = 0.0, 0.0
        for p in products:
            stock = money(p['stock'])
            total_fiscal += stock * money(p['cost_a'])
            total_real += stock * money(p['cost'])

        return {
            'products_with_dual_cost': len(products),
            'total_inventory_at_fiscal_cost': total_fiscal,
            'total_inventory_at_real_cost': total_real,
            'difference': total_fiscal - total_real
        }
