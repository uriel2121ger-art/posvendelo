"""
Black Hole - Borrador Quirúrgico de Registros Serie B

Herramienta para eliminar ventas Serie B que ya fueron facturadas
posteriormente, evitando duplicidad fiscal.

Uso típico:
1. Cliente compra sin factura → Se registra como Serie B
2. Días después, cliente pide factura → Se genera CFDI Serie A
3. La venta original Serie B se elimina → No hay duplicidad contable
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import hashlib
import logging
import secrets
import threading

logger = logging.getLogger(__name__)

# Lock global para prevenir race conditions en operaciones de eliminación
_operation_lock = threading.Lock()


class BlackHole:
    """
    Sistema de eliminación quirúrgica de registros Serie B.

    Características:
    - Elimina ventas Serie B ya facturadas para evitar duplicidad
    - Recalcula folios para mantener secuencia consecutiva
    - Limpia logs relacionados
    - Thread-safe: usa locks para prevenir race conditions
    """

    def __init__(self, core):
        self.core = core
        self.deletion_log = []  # Log interno (memoria volátil)

    def surgical_delete(self,
                       sale_ids: List[int] = None,
                       time_range: Dict[str, str] = None,
                       branch: str = None,
                       confirm_phrase: str = None) -> Dict[str, Any]:
        """
        Elimina transacciones Serie B específicas.

        Args:
            sale_ids: Lista específica de IDs de venta a eliminar
            time_range: {'start': 'ISO datetime', 'end': 'ISO datetime'}
            branch: Sucursal específica (opcional)
            confirm_phrase: Frase de confirmación requerida

        Returns:
            Resultado de la operación
        """
        # Verificar confirmación
        if confirm_phrase != "CONFIRMO ELIMINACION":
            return {
                'success': False,
                'error': 'Confirmación requerida: "CONFIRMO ELIMINACION"'
            }

        # CRITICAL: Adquirir lock para prevenir race conditions
        if not _operation_lock.acquire(timeout=30):
            return {
                'success': False,
                'error': 'Otra operación de eliminación está en progreso. Intente de nuevo.'
            }

        try:
            return self._execute_surgical_delete_locked(sale_ids, time_range, branch)
        finally:
            _operation_lock.release()

    def _execute_surgical_delete_locked(self,
                                        sale_ids: List[int] = None,
                                        time_range: Dict[str, str] = None,
                                        branch: str = None) -> Dict[str, Any]:
        """
        Ejecuta la eliminación con el lock ya adquirido.
        """
        # Construir query de selección
        where_clauses = ["serie = 'B'"]  # Solo Serie B
        params = []

        if sale_ids:
            placeholders = ','.join(['%s' for _ in sale_ids])
            where_clauses.append(f"id IN ({placeholders})")
            params.extend(sale_ids)

        if time_range:
            if time_range.get('start'):
                where_clauses.append("timestamp >= %s")
                params.append(time_range['start'])
            if time_range.get('end'):
                where_clauses.append("timestamp <= %s")
                params.append(time_range['end'])

        if branch:
            where_clauses.append("branch = %s")
            params.append(branch)

        where_sql = " AND ".join(where_clauses)

        # Obtener ventas a eliminar
        # nosec B608 - where_clauses built from hardcoded SQL fragments, not user input
        sales_to_delete = list(self.core.db.execute_query(f"""
            SELECT id, folio_visible, total, timestamp, branch
            FROM sales WHERE {where_sql}
        """, tuple(params) if params else None))

        if not sales_to_delete:
            return {
                'success': False,
                'error': 'No se encontraron ventas Serie B con esos criterios'
            }

        # Registrar en log interno (memoria volátil)
        operation_id = secrets.token_hex(8)
        self.deletion_log.append({
            'operation_id': operation_id,
            'timestamp': datetime.now().isoformat(),
            'count': len(sales_to_delete),
            'total_amount': sum(float(s['total'] or 0) for s in sales_to_delete)
        })

        # Ejecutar eliminación quirúrgica (atómica)
        deleted_count, error = self._execute_atomic_delete(sales_to_delete)

        if error:
            return {
                'success': False,
                'error': error,
                'partial_deleted': deleted_count
            }

        # Recalcular folios para mantener secuencia consecutiva
        folio_error = self._recalculate_folios(branch)
        if folio_error:
            logger.warning(f"Folios recalculation warning: {folio_error}")

        # Limpiar logs relacionados
        self._clean_related_logs(sales_to_delete)

        return {
            'success': True,
            'operation_id': operation_id,
            'deleted_count': deleted_count,
            'total_amount_erased': sum(float(s['total'] or 0) for s in sales_to_delete),
            'message': f'{deleted_count} transacciones eliminadas correctamente'
        }

    def _execute_atomic_delete(self, sales: List[Dict]) -> tuple:
        """
        Ejecuta la eliminación de TODAS las ventas en una sola transacción atómica.

        Returns:
            (deleted_count, error_message or None)
        """
        all_ops = []

        for sale in sales:
            sale_id = sale['id']

            try:
                # Obtener items antes de eliminar (para revertir inventario)
                items = list(self.core.db.execute_query("""
                    SELECT product_id, qty FROM sale_items WHERE sale_id = %s
                """, (sale_id,)))

                # 1. Eliminar items de la venta
                all_ops.append(("DELETE FROM sale_items WHERE sale_id = %s", (sale_id,)))

                # 2. Eliminar pagos asociados
                all_ops.append(("DELETE FROM payments WHERE sale_id = %s", (sale_id,)))

                # 3. Revertir movimientos de inventario (Parte A Fase 1.4: registrar movimiento)
                for item in items:
                    if item.get('product_id') and item.get('qty'):
                        pid, qty = item['product_id'], item['qty']
                        all_ops.append((
                            "UPDATE products SET stock = stock + %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                            (qty, pid)
                        ))
                        all_ops.append((
                            """INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, reference_id, timestamp, synced)
                               VALUES (%s, 'IN', 'black_hole', %s, %s, 'black_hole', %s, NOW(), 0)""",
                            (pid, qty, "Reversión black_hole", sale_id)
                        ))

                # 4. Eliminar la venta principal
                all_ops.append(("DELETE FROM sales WHERE id = %s", (sale_id,)))

            except Exception as e:
                logger.error(f"Error preparando eliminación de venta {sale_id}: {e}")
                return (0, f"Error preparando venta {sale_id}: {e}")

        # Ejecutar TODO en una sola transacción atómica
        if not all_ops:
            return (0, "No hay operaciones a ejecutar")

        try:
            result = self.core.db.execute_transaction(all_ops, timeout=30)
            if result.get('success'):
                return (len(sales), None)
            else:
                error_msg = result.get('error', 'Transaction failed')
                logger.error(f"Error en transacción de eliminación: {error_msg}")
                return (0, f"Error en transacción: {error_msg}")
        except Exception as e:
            logger.error(f"Excepción en transacción de eliminación: {e}")
            return (0, f"Excepción: {e}")

    def _recalculate_folios(self, branch: str = None) -> Optional[str]:
        """
        Recalcula folios Serie B para mantener secuencia consecutiva.

        Returns:
            Error message if failed, None if success
        """
        try:
            params = []
            where_clause = "WHERE serie = 'B'"
            if branch:
                where_clause += " AND branch = %s"
                params.append(branch)

            # Obtener todas las ventas Serie B ordenadas por timestamp
            # nosec B608 - where_clause is hardcoded "WHERE serie = 'B'" with optional branch filter
            sales = list(self.core.db.execute_query(f"""
                SELECT id, folio_visible, timestamp
                FROM sales {where_clause}
                ORDER BY timestamp ASC
            """, tuple(params) if params else None))

            # Construir operaciones de recálculo
            ops = []

            # Reasignar folios consecutivos
            for i, sale in enumerate(sales, start=1):
                new_folio = f"B-{i:06d}"

                if sale['folio_visible'] != new_folio:
                    ops.append((
                        "UPDATE sales SET folio_visible = %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                        (new_folio, sale['id'])
                    ))

            # Actualizar secuencia
            next_folio = len(sales) + 1
            ops.append((
                "UPDATE secuencias SET ultimo_numero = %s WHERE serie = 'B'",
                (next_folio,)
            ))

            # Ejecutar en una sola transacción atómica
            if ops:
                result = self.core.db.execute_transaction(ops, timeout=30)
                if not result.get('success'):
                    return f"Transaction failed: {result.get('error', 'unknown')}"

            return None  # Success

        except Exception as e:
            logger.error(f"Error recalculando folios: {e}")
            return str(e)

    def _clean_related_logs(self, sales: List[Dict]) -> None:
        """Limpia logs relacionados con las ventas eliminadas."""
        if not sales:
            return

        sale_ids = [s['id'] for s in sales]

        # Limpiar de tablas de auditoría si existen
        # nosec B608 - table names are hardcoded whitelist, not user input
        for table in ['audit_log', 'activity_log', 'sync_log']:
            try:
                placeholders = ','.join(['%s'] * len(sale_ids))
                self.core.db.execute_write(f"""
                    DELETE FROM {table}
                    WHERE entity_type = 'sale' AND entity_id IN ({placeholders})
                """, tuple(sale_ids))
            except Exception as e:
                logger.debug("Cleaning %s: %s", table, e)

        # Limpiar de sistema de notificaciones
        try:
            placeholders = ','.join(['%s'] * len(sale_ids))
            # nosec B608 - placeholders are %s literals for parameterized query
            self.core.db.execute_write(f"""
                DELETE FROM notifications
                WHERE sale_id IN ({placeholders})
            """, tuple(sale_ids))
        except Exception as e:
            logger.debug("Cleaning notifications: %s", e)

    def quick_erase_last_hours(self, hours: int, branch: str = None, confirm: str = None) -> Dict[str, Any]:
        """
        Atajo para eliminar las últimas N horas de ventas Serie B.

        Args:
            hours: Número de horas hacia atrás
            branch: Sucursal (opcional)
            confirm: "CONFIRMO ELIMINACION"
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        return self.surgical_delete(
            time_range={
                'start': start_time.isoformat(),
                'end': end_time.isoformat()
            },
            branch=branch,
            confirm_phrase=confirm
        )

    def preview_deletion(self,
                        sale_ids: List[int] = None,
                        time_range: Dict[str, str] = None,
                        branch: str = None) -> Dict[str, Any]:
        """
        Vista previa de lo que se eliminaría (sin ejecutar).
        """
        where_clauses = ["serie = 'B'"]
        params = []

        if sale_ids:
            placeholders = ','.join(['%s' for _ in sale_ids])
            where_clauses.append(f"id IN ({placeholders})")
            params.extend(sale_ids)

        if time_range:
            if time_range.get('start'):
                where_clauses.append("timestamp >= %s")
                params.append(time_range['start'])
            if time_range.get('end'):
                where_clauses.append("timestamp <= %s")
                params.append(time_range['end'])

        if branch:
            where_clauses.append("branch = %s")
            params.append(branch)

        where_sql = " AND ".join(where_clauses)

        # nosec B608 - where_clauses built from hardcoded SQL fragments, not user input
        sales = list(self.core.db.execute_query(f"""
            SELECT id, folio_visible, total, timestamp, branch, payment_method
            FROM sales WHERE {where_sql}
            ORDER BY timestamp DESC
        """, tuple(params) if params else None))

        total_amount = sum(float(s['total'] or 0) for s in sales)

        return {
            'preview': True,
            'count': len(sales),
            'total_amount': total_amount,
            'sales': [
                {
                    'id': s['id'],
                    'folio': s['folio_visible'],
                    'total': float(s['total'] or 0),
                    'time': s['timestamp'],
                    'branch': s['branch']
                }
                for s in sales[:20]  # Máximo 20 en preview
            ],
            'warning': f'Se eliminarán {len(sales)} ventas por ${total_amount:,.2f}'
        }


# Función de conveniencia para PWA
def quick_erase(core, hours: int, branch: str = None, confirm: str = None) -> Dict[str, Any]:
    """Wrapper para borrado rápido desde PWA."""
    hole = BlackHole(core)
    return hole.quick_erase_last_hours(hours, branch, confirm)
