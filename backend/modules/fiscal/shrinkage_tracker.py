"""
Materiality Engine - Actas circunstanciadas para mermas
Art. 32-F del Código Fiscal de la Federación
"""

from typing import Any, Dict, List
from datetime import datetime
from decimal import Decimal
import logging

from modules.shared.constants import money

logger = logging.getLogger(__name__)


class MaterialityEngine:
    def __init__(self, db):
        self.db = db

    async def setup_table(self):
        try:
            await self.db.execute("""
                CREATE TABLE IF NOT EXISTS loss_records (
                    id BIGSERIAL PRIMARY KEY, product_id INTEGER NOT NULL, product_name TEXT,
                    product_sku TEXT, quantity REAL NOT NULL, unit_cost REAL, total_value REAL,
                    reason TEXT NOT NULL, category TEXT DEFAULT 'deterioro', photo_path TEXT,
                    witness_name TEXT, witness_id TEXT, acta_number TEXT UNIQUE,
                    status TEXT DEFAULT 'pending', authorized_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP, authorized_at TEXT,
                    climate_justification TEXT
                )
            """)
        except Exception as e:
            logger.error(f"Error creating loss_records table: {e}")

    async def register_loss(self, product_id: int, quantity: float, reason: str,
                             category: str = 'deterioro', witness_name: str = None) -> Dict[str, Any]:
        try:
            conn = self.db.connection
            async with conn.transaction():
                p = await self.db.fetchrow(
                    "SELECT name, sku, price, stock FROM products WHERE id = :pid FOR UPDATE",
                    pid=product_id,
                )
                if not p:
                    return {'success': False, 'error': 'Producto no encontrado'}
                if Decimal(str(p['stock'] or 0)) < Decimal(str(quantity)):
                    return {'success': False, 'error': 'Stock insuficiente para merma'}

                unit_cost = float((Decimal(str(p['price'] or 0)) * Decimal("0.7")).quantize(Decimal("0.01")))
                total_value = unit_cost * quantity
                acta_number = await self._generate_acta_number()

                await self.db.execute("""
                    INSERT INTO loss_records (product_id, product_name, product_sku, quantity, unit_cost, total_value,
                        reason, category, witness_name, acta_number, status, created_at)
                    VALUES (:pid, :name, :sku, :qty, :uc, :tv, :reason, :cat, :wit, :acta, 'pending', :ts)
                """, pid=product_id, name=p['name'], sku=p['sku'], qty=quantity, uc=unit_cost, tv=total_value,
                    reason=reason, cat=category, wit=witness_name, acta=acta_number, ts=datetime.now().isoformat())

                await self.db.execute("UPDATE products SET stock = stock - :qty, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = :pid", qty=quantity, pid=product_id)

                try:
                    await self.db.execute("""
                        INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                        VALUES (:pid, 'OUT', 'loss', :qty, :reason, 'loss_record', NOW(), 0)
                    """, pid=product_id, qty=quantity, reason=reason or "Merma")
                except Exception:
                    pass

            return {'success': True, 'acta_number': acta_number, 'product': p['name'], 'quantity': quantity, 'total_value': total_value, 'status': 'pending'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _generate_acta_number(self) -> str:
        """Uses advisory lock to prevent duplicate acta numbers under concurrency."""
        now = datetime.now()
        await self.db.execute("SELECT pg_advisory_xact_lock(738202)")
        count = await self.db.fetchrow("SELECT COUNT(*) as c FROM loss_records WHERE EXTRACT(YEAR FROM created_at::timestamp) = :year", year=now.year)
        seq = (count['c'] or 0) + 1 if count else 1
        return f"MERMA-{now.year}-{seq:05d}"

    async def authorize_loss(self, acta_number: str, authorized_by: str) -> Dict[str, Any]:
        try:
            await self.db.execute("UPDATE loss_records SET status = 'authorized', authorized_by = :ab, authorized_at = :at WHERE acta_number = :acta",
                ab=authorized_by, at=datetime.now().isoformat(), acta=acta_number)
            return {'success': True, 'message': f'Acta {acta_number} autorizada'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def generate_acta_text(self, acta_number: str) -> str:
        r = await self.db.fetchrow("SELECT * FROM loss_records WHERE acta_number = :acta", acta=acta_number)
        if not r:
            return "Acta no encontrada"

        fecha = datetime.fromisoformat(r['created_at']).strftime('%d de %B de %Y')
        hora = datetime.fromisoformat(r['created_at']).strftime('%H:%M')

        return f"""ACTA CIRCUNSTANCIADA DE DESTRUCCIÓN - Art. 32-F CFF
Acta No.: {r['acta_number']}
Fecha: {fecha} | Hora: {hora}
Producto: {r['product_name']} (SKU: {r['product_sku']})
Cantidad: {r['quantity']} uds | Valor: ${r['total_value']:,.2f}
Causa: {r['category'].upper()} - {r['reason']}
Testigo: {r.get('witness_name') or 'N/A'}
Autorizado: {r.get('authorized_by') or 'Pendiente'}
Estado: {r['status'].upper()}"""

    async def get_pending_losses(self) -> List[Dict]:
        result = await self.db.fetch("SELECT * FROM loss_records WHERE status = 'pending' ORDER BY created_at DESC")
        return [dict(r) for r in result]

    async def get_loss_summary(self, year: int = None) -> Dict[str, Any]:
        year = year or datetime.now().year
        result = await self.db.fetch("""
            SELECT category, COUNT(*) as registros, COALESCE(SUM(quantity), 0) as unidades, COALESCE(SUM(total_value), 0) as valor
            FROM loss_records WHERE EXTRACT(YEAR FROM created_at::timestamp) = :year GROUP BY category
        """, year=year)

        by_category = {r['category']: dict(r) for r in result}
        total_valor = money(sum(Decimal(str(r['valor'] or 0)) for r in result))
        return {'year': year, 'by_category': by_category, 'total_value': total_valor, 'total_records': sum(r['registros'] for r in result)}
