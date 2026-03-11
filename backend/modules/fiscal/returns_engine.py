"""
Returns Engine - Motor de devoluciones y cancelaciones
Gestion de CFDI de Egreso para Serie A, notas internas para Serie B

Refactored: receives `db` (DB wrapper) instead of `core`.
- Removed create_task from __init__; use ensure_tables() explicitly.
- Changed REAL -> NUMERIC(12,2) and created_at TEXT -> TIMESTAMP DEFAULT NOW().
- Uses :name params and db.fetch/db.fetchrow/db.execute.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from decimal import Decimal
import logging
from modules.fiscal.constants import IVA_RATE
from modules.shared.constants import money, sanitize_row

logger = logging.getLogger(__name__)


class ReturnsEngine:
    """
    Motor de procesamiento de devoluciones.
    Regla: Nunca borrar ventas, siempre generar documento de devolucion.
    """

    def __init__(self, db):
        self.db = db

    async def ensure_tables(self):
        """Crea tabla de devoluciones si no existe.
        Call this once at app startup, NOT in __init__.
        """
        try:
            await self.db.execute("""
                CREATE TABLE IF NOT EXISTS returns (
                    id BIGSERIAL PRIMARY KEY,
                    sale_id INTEGER NOT NULL,
                    original_serie TEXT,
                    original_folio TEXT,
                    original_uuid TEXT,
                    return_folio TEXT UNIQUE,
                    return_type TEXT DEFAULT 'partial',
                    product_id INTEGER,
                    product_name TEXT,
                    quantity NUMERIC(12,2),
                    unit_price NUMERIC(12,2),
                    subtotal NUMERIC(12,2),
                    tax NUMERIC(12,2),
                    total NUMERIC(12,2),
                    reason_category TEXT,
                    reason_detail TEXT,
                    product_condition TEXT DEFAULT 'integro',
                    restock INTEGER DEFAULT 1,
                    cfdi_egreso_uuid TEXT,
                    cfdi_egreso_status TEXT DEFAULT 'pending',
                    processed_by TEXT,
                    customer_id INTEGER,
                    status TEXT DEFAULT 'completed',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            await self.db.execute(
                "CREATE INDEX IF NOT EXISTS idx_returns_sale ON returns(sale_id)"
            )

            # Ensure columns exist (table may have been created by Alembic without these)
            for col, typ, dflt in [
                ("cfdi_egreso_status", "TEXT", "'pending'"),
                ("cfdi_egreso_uuid", "TEXT", "NULL"),
                ("original_uuid", "TEXT", "NULL"),
                ("return_type", "TEXT", "'partial'"),
                ("product_condition", "TEXT", "'integro'"),
                ("restock", "INTEGER", "1"),
                ("reason_detail", "TEXT", "NULL"),
                ("reason_category", "TEXT", "NULL"),
            ]:
                try:
                    await self.db.execute(
                        f"ALTER TABLE returns ADD COLUMN IF NOT EXISTS {col} {typ} DEFAULT {dflt}"
                    )
                except Exception:
                    pass  # Column already exists or DB doesn't support IF NOT EXISTS
        except Exception as e:
            logger.error(f"Error creating returns table: {e}")

    async def process_return(
        self,
        sale_id: int,
        items: List[Dict],
        reason: str,
        processed_by: str,
    ) -> Dict[str, Any]:
        """
        Procesa una devolucion completa o parcial.

        Args:
            sale_id: ID de la venta original
            items: Lista de items a devolver [{product_id, quantity}]
            reason: Motivo de devolucion
            processed_by: Usuario que procesa
        """
        conn = self.db.connection
        async with conn.transaction():
            sale = await self.db.fetchrow(
                "SELECT * FROM sales WHERE id = :sid", {"sid": sale_id}
            )

            if not sale:
                return {'success': False, 'error': 'Venta no encontrada'}

            serie = sale['serie']
            original_folio = sale['folio_visible']

            return_folio = await self._generate_return_folio()

            total_return = Decimal('0')
            processed_items = []
            iva_rate = Decimal(str(IVA_RATE))

            for item in items:
                product_id = item.get('product_id')
                qty = Decimal(str(item.get('quantity', 1)))

                original_item = await self.db.fetchrow(
                    """SELECT si.*, p.name
                       FROM sale_items si
                       JOIN products p ON si.product_id = p.id
                       WHERE si.sale_id = :sid AND si.product_id = :pid""",
                    {"sid": sale_id, "pid": product_id},
                )

                if not original_item:
                    continue

                # Validate qty does not exceed original sold quantity
                original_qty = Decimal(str(original_item.get('qty', 0)))
                if qty > original_qty:
                    return {
                        'success': False,
                        'error': f"Cantidad a devolver ({qty}) excede la vendida ({original_qty}) para producto {original_item['name']}",
                    }

                unit_price = Decimal(str(original_item['price'])).quantize(Decimal('0.01'))
                subtotal = (unit_price * qty).quantize(Decimal('0.01'))
                tax = (subtotal * iva_rate).quantize(Decimal('0.01'))
                total = subtotal + tax
                total_return += total

                await self.db.execute(
                    """INSERT INTO returns
                       (sale_id, original_serie, original_folio, return_folio,
                        product_id, product_name, quantity, unit_price,
                        subtotal, tax, total, reason_category, reason_detail,
                        processed_by, customer_id, created_at)
                       VALUES (:sale_id, :serie, :folio, :rfolio,
                        :pid, :pname, :qty, :uprice,
                        :sub, :tax, :total, 'general', :reason,
                        :proc_by, :cust_id, NOW())""",
                    {
                        "sale_id": sale_id,
                        "serie": serie,
                        "folio": original_folio,
                        "rfolio": return_folio,
                        "pid": product_id,
                        "pname": original_item['name'],
                        "qty": qty,
                        "uprice": unit_price,
                        "sub": subtotal,
                        "tax": tax,
                        "total": total,
                        "reason": reason,
                        "proc_by": processed_by,
                        "cust_id": sale.get('customer_id'),
                    },
                )

                # Reintegrar stock
                await self.db.execute(
                    "UPDATE products SET stock = stock + :qty, synced = 0, "
                    "updated_at = CURRENT_TIMESTAMP WHERE id = :pid",
                    {"qty": qty, "pid": product_id},
                )
                try:
                    await self.db.execute(
                        """INSERT INTO inventory_movements
                            (product_id, movement_type, type, quantity, reason,
                             reference_type, reference_id, timestamp, synced)
                            VALUES (:pid, 'IN', 'return', :qty, :reason,
                             'return', :ref_id, NOW(), 0)""",
                        {"pid": product_id, "qty": qty, "reason": reason or "Devolucion", "ref_id": sale_id},
                    )
                except Exception as e:
                    logger.debug("Could not insert inventory_movement for return: %s", e)

                processed_items.append({
                    'product': original_item['name'],
                    'quantity': qty,
                    'refund': money(total),
                })

        requires_cfdi_egreso = serie == 'A'

        result = {
            'success': True,
            'return_folio': return_folio,
            'original_sale': sale_id,
            'original_serie': serie,
            'items_returned': len(processed_items),
            'total_refund': money(total_return),
            'requires_cfdi_egreso': requires_cfdi_egreso,
            'items': processed_items,
        }

        if requires_cfdi_egreso:
            result['cfdi_action'] = {
                'type': 'EGRESO',
                'tipo_relacion': '01',
                'uuid_relacionado': sale.get('cfdi_uuid', 'PENDIENTE'),
                'message': 'Generar CFDI de Egreso (Nota de Credito)',
            }

        return result

    async def _generate_return_folio(self) -> str:
        """Genera folio unico de devolucion.
        Uses advisory lock to prevent duplicate folios under concurrency.
        Must be called within a transaction (process_return provides one).
        """
        # Advisory lock serializes folio generation (released on tx commit/rollback)
        await self.db.execute("SELECT pg_advisory_xact_lock(738201)")
        row = await self.db.fetchrow(
            "SELECT COUNT(*) as c FROM returns WHERE EXTRACT(YEAR FROM created_at) = :yr",
            {"yr": datetime.now().year},
        )
        seq = (row['c'] or 0) + 1 if row else 1
        return f"DEV-{datetime.now().year}-{seq:05d}"

    async def get_return_by_folio(self, folio: str) -> Optional[Dict]:
        """Obtiene devolucion por folio."""
        return await self.db.fetchrow(
            "SELECT * FROM returns WHERE return_folio = :folio", {"folio": folio}
        )

    async def get_pending_cfdi_egresos(self) -> List[Dict]:
        """Obtiene devoluciones Serie A pendientes de CFDI Egreso."""
        return await self.db.fetch(
            """SELECT * FROM returns
               WHERE original_serie = 'A'
               AND cfdi_egreso_status = 'pending'
               ORDER BY created_at"""
        )

    async def mark_cfdi_egreso_done(self, return_folio: str, uuid: str) -> Dict[str, Any]:
        """Marca CFDI de Egreso como generado."""
        try:
            await self.db.execute(
                """UPDATE returns
                   SET cfdi_egreso_uuid = :uuid, cfdi_egreso_status = 'completed'
                   WHERE return_folio = :folio""",
                {"uuid": uuid, "folio": return_folio},
            )
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def get_returns_summary(
        self, start_date: str = None, end_date: str = None
    ) -> Dict[str, Any]:
        """Resumen de devoluciones por periodo."""
        start = start_date or datetime.now().strftime('%Y-01-01')
        end = end_date or datetime.now().strftime('%Y-12-31')

        rows = await self.db.fetch(
            """SELECT
                original_serie,
                COUNT(*) as count,
                COALESCE(SUM(total), 0) as total,
                0 as pending_cfdi
               FROM returns
               WHERE created_at::date BETWEEN :d1 AND :d2
               GROUP BY original_serie""",
            {"d1": datetime.strptime(start, '%Y-%m-%d').date(), "d2": datetime.strptime(end, '%Y-%m-%d').date()},
        )

        return {
            'period': f'{start} a {end}',
            'by_serie': {r['original_serie']: sanitize_row(r) for r in rows},
            'total_returns': sum(r['count'] for r in rows),
            'total_amount': money(sum(Decimal(str(r['total'] or 0)) for r in rows)),
        }
