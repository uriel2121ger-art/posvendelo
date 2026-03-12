"""
Self Consumption Engine - Autoconsumo y muestras gratuitas
Art. 25 LISR - Gastos de operación deducibles
"""

from typing import Any, Dict, List
from datetime import datetime
from decimal import Decimal
import logging

from modules.shared.constants import dec, money

logger = logging.getLogger(__name__)


class SelfConsumptionEngine:
    CATEGORIES = {
        'limpieza': 'Productos de limpieza del local', 'empleados': 'Consumo autorizado por personal',
        'muestras': 'Muestras gratuitas para clientes', 'operacion': 'Insumos de operación diaria',
        'oficina': 'Material de oficina', 'otro': 'Otro tipo de consumo'
    }

    def __init__(self, db):
        self.db = db

    async def setup_table(self):
        try:
            await self.db.execute("""
                CREATE TABLE IF NOT EXISTS self_consumption (
                    id BIGSERIAL PRIMARY KEY, product_id INTEGER NOT NULL, product_name TEXT,
                    product_sku TEXT, quantity REAL NOT NULL, unit_cost REAL, total_value REAL,
                    category TEXT DEFAULT 'operacion', reason TEXT, beneficiary TEXT,
                    authorized_by TEXT, voucher_folio TEXT, status TEXT DEFAULT 'registered',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self.db.execute("CREATE INDEX IF NOT EXISTS idx_selfcons_date ON self_consumption(created_at)")
        except Exception as e:
            logger.error(f"Error creating self_consumption table: {e}")

    async def register_consumption(self, product_id: int, quantity: float, category: str,
                                    reason: str = None, beneficiary: str = None) -> Dict[str, Any]:
        try:
            conn = self.db.connection
            async with conn.transaction():
                p = await self.db.fetchrow(
                    "SELECT id, name, sku, price, stock FROM products WHERE id = :pid FOR UPDATE",
                    pid=product_id,
                )
                if not p:
                    return {'success': False, 'error': 'Producto no encontrado'}
                if Decimal(str(p['stock'] or 0)) < Decimal(str(quantity)):
                    return {'success': False, 'error': 'Stock insuficiente'}

                unit_cost = (Decimal(str(p['price'] or 0)) * Decimal("0.7")).quantize(Decimal("0.01"))
                total_value = (unit_cost * Decimal(str(quantity))).quantize(Decimal("0.01"))

                await self.db.execute("""
                    INSERT INTO self_consumption (product_id, product_name, product_sku, quantity, unit_cost, total_value, category, reason, beneficiary, created_at)
                    VALUES (:pid, :name, :sku, :qty, :uc, :tv, :cat, :reason, :ben, :ts)
                """, pid=product_id, name=p['name'], sku=p['sku'], qty=quantity, uc=unit_cost, tv=total_value, cat=category, reason=reason, ben=beneficiary, ts=datetime.now().isoformat())

                await self.db.execute("UPDATE products SET stock = stock - :qty, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = :pid", qty=quantity, pid=product_id)

                try:
                    await self.db.execute("""
                        INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                        VALUES (:pid, 'OUT', 'self_consumption', :qty, :reason, 'self_consumption', NOW(), 0)
                    """, pid=product_id, qty=quantity, reason=reason or "Autoconsumo")
                except Exception:
                    pass

            return {'success': True, 'product': p['name'], 'quantity': quantity, 'value': total_value, 'category': category}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def register_sample(self, product_id: int, quantity: float, recipient: str = 'Cliente') -> Dict[str, Any]:
        return await self.register_consumption(product_id, quantity, 'muestras', 'Muestra gratuita', recipient)

    async def register_employee_consumption(self, product_id: int, quantity: float, employee_name: str) -> Dict[str, Any]:
        return await self.register_consumption(product_id, quantity, 'empleados', 'Consumo autorizado', employee_name)

    async def get_monthly_summary(self, year: int = None, month: int = None) -> Dict[str, Any]:
        year = year or datetime.now().year
        month = month or datetime.now().month

        result = await self.db.fetch("""
            SELECT category, COUNT(*) as registros, COALESCE(SUM(quantity), 0) as unidades, COALESCE(SUM(total_value), 0) as valor
            FROM self_consumption WHERE EXTRACT(YEAR FROM created_at::timestamp) = :year AND EXTRACT(MONTH FROM created_at::timestamp) = :month GROUP BY category
        """, year=year, month=month)

        by_category = {}
        total_value = Decimal('0')
        for r in result:
            by_category[r['category']] = {'registros': r['registros'], 'unidades': r['unidades'], 'valor': money(r['valor'])}
            total_value += dec(r['valor'])

        return {'year': year, 'month': month, 'by_category': by_category, 'total_value': money(total_value), 'total_registros': sum(c['registros'] for c in by_category.values())}

    async def generate_monthly_voucher(self, year: int = None, month: int = None) -> Dict[str, Any]:
        year = year or datetime.now().year
        month = month or datetime.now().month

        items = await self.db.fetch("""
            SELECT * FROM self_consumption WHERE EXTRACT(YEAR FROM created_at::timestamp) = :year
            AND EXTRACT(MONTH FROM created_at::timestamp) = :month ORDER BY category, created_at
            LIMIT 1000
        """, year=year, month=month)

        if not items:
            return {'success': False, 'error': 'Sin registros este mes'}

        folio = f"VALE-AUTO-{year}{month:02d}"
        await self.db.execute("""
            UPDATE self_consumption SET voucher_folio = :folio
            WHERE EXTRACT(YEAR FROM created_at::timestamp) = :year AND EXTRACT(MONTH FROM created_at::timestamp) = :month
        """, folio=folio, year=year, month=month)

        voucher_items = [{'product': it['product_name'], 'quantity': it['quantity'], 'value': money(it['total_value']), 'reason': f"{it['category']}: {it.get('reason', '')}"} for it in items]

        return {'success': True, 'folio': folio, 'items_count': len(items), 'items': voucher_items}

    async def get_pending_voucher_months(self) -> List[str]:
        result = await self.db.fetch("SELECT DISTINCT TO_CHAR(created_at::timestamp, 'YYYY-MM') as period FROM self_consumption WHERE voucher_folio IS NULL ORDER BY period LIMIT 120")
        return [r['period'] for r in result]
