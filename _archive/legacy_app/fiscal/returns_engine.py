"""
Returns Engine - Motor de devoluciones y cancelaciones
Gestión de CFDI de Egreso para Serie A, notas internas para Serie B
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class ReturnsEngine:
    """
    Motor de procesamiento de devoluciones.
    Regla: Nunca borrar ventas, siempre generar documento de devolución.
    """
    
    def __init__(self, core):
        self.core = core
        self._setup_table()
    
    def _setup_table(self):
        """Crea tabla de devoluciones si no existe."""
        try:
            self.core.db.execute_write("""
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
                    quantity REAL,
                    unit_price REAL,
                    subtotal REAL,
                    tax REAL,
                    total REAL,
                    reason_category TEXT,
                    reason_detail TEXT,
                    product_condition TEXT DEFAULT 'integro',
                    restock INTEGER DEFAULT 1,
                    cfdi_egreso_uuid TEXT,
                    cfdi_egreso_status TEXT DEFAULT 'pending',
                    processed_by TEXT,
                    customer_id INTEGER,
                    status TEXT DEFAULT 'completed',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.core.db.execute_write(
                "CREATE INDEX IF NOT EXISTS idx_returns_sale ON returns(sale_id)"
            )
        except Exception as e:
            logger.error(f"Error creating returns table: {e}")
    
    def process_return(self, sale_id: int, items: List[Dict], 
                       reason: str, processed_by: str) -> Dict[str, Any]:
        """
        Procesa una devolución completa o parcial.
        
        Args:
            sale_id: ID de la venta original
            items: Lista de items a devolver [{product_id, quantity}]
            reason: Motivo de devolución
            processed_by: Usuario que procesa
        """
        # Obtener venta original
        sale = list(self.core.db.execute_query(
            "SELECT * FROM sales WHERE id = %s", (sale_id,)
        ))
        
        if not sale:
            return {'success': False, 'error': 'Venta no encontrada'}
        
        sale = sale[0]
        serie = sale['serie']
        original_folio = sale['folio_visible']
        
        # Generar folio de devolución
        return_folio = self._generate_return_folio()
        
        total_return = Decimal('0')
        processed_items = []
        
        for item in items:
            product_id = item.get('product_id')
            qty = item.get('quantity', 1)
            
            # Obtener item original
            original_item = list(self.core.db.execute_query(
                """SELECT si.*, p.name 
                   FROM sale_items si 
                   JOIN products p ON si.product_id = p.id
                   WHERE si.sale_id = %s AND si.product_id = %s""",
                (sale_id, product_id)
            ))
            
            if not original_item:
                continue
            
            oi = original_item[0]
            unit_price = float(oi['price'])
            subtotal = unit_price * qty
            tax = subtotal * 0.16
            total = subtotal + tax
            total_return += Decimal(str(total))
            
            # Registrar devolución
            self.core.db.execute_write(
                """INSERT INTO returns 
                   (sale_id, original_serie, original_folio, return_folio,
                    product_id, product_name, quantity, unit_price,
                    subtotal, tax, total, reason_category, reason_detail,
                    processed_by, customer_id, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (sale_id, serie, original_folio, return_folio,
                 product_id, oi['name'], qty, unit_price,
                 subtotal, tax, total, 'general', reason,
                 processed_by, sale.get('customer_id'), datetime.now().isoformat())
            )
            
            # Reintegrar stock (Parte A Fase 1.4: registrar movimiento para delta sync)
            self.core.db.execute_write(
                "UPDATE products SET stock = stock + %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (qty, product_id)
            )
            try:
                self.core.db.execute_write(
                    """INSERT INTO inventory_movements
                        (product_id, movement_type, type, quantity, reason, reference_type, reference_id, timestamp, synced)
                        VALUES (%s, 'IN', 'return', %s, %s, 'return', %s, NOW(), 0)""",
                    (product_id, qty, reason or "Devolución", sale_id)
                )
            except Exception as e:
                logger.debug("Could not insert inventory_movement for return: %s", e)
            
            processed_items.append({
                'product': oi['name'],
                'quantity': qty,
                'refund': total
            })
        
        # Determinar acciones requeridas
        requires_cfdi_egreso = serie == 'A'
        
        result = {
            'success': True,
            'return_folio': return_folio,
            'original_sale': sale_id,
            'original_serie': serie,
            'items_returned': len(processed_items),
            'total_refund': float(total_return),
            'requires_cfdi_egreso': requires_cfdi_egreso,
            'items': processed_items
        }
        
        if requires_cfdi_egreso:
            result['cfdi_action'] = {
                'type': 'EGRESO',
                'tipo_relacion': '01',
                'uuid_relacionado': sale.get('cfdi_uuid', 'PENDIENTE'),
                'message': 'Generar CFDI de Egreso (Nota de Crédito)'
            }
        
        # SECURITY: No loguear devoluciones (pueden ser Serie B)
        pass
        
        return result
    
    def _generate_return_folio(self) -> str:
        """Genera folio único de devolución."""
        count = list(self.core.db.execute_query(
            "SELECT COUNT(*) as c FROM returns WHERE EXTRACT(YEAR FROM created_at::timestamp) = %s",
            (str(datetime.now().year),)
        ))
        # FIX 2026-01-30: Validar que count no esté vacío antes de acceder a [0]
        seq = (count[0]['c'] or 0) + 1 if count else 1
        return f"DEV-{datetime.now().year}-{seq:05d}"
    
    def get_return_by_folio(self, folio: str) -> Optional[Dict]:
        """Obtiene devolución por folio."""
        result = list(self.core.db.execute_query(
            "SELECT * FROM returns WHERE return_folio = %s", (folio,)
        ))
        return dict(result[0]) if result else None
    
    def get_pending_cfdi_egresos(self) -> List[Dict]:
        """Obtiene devoluciones Serie A pendientes de CFDI Egreso."""
        result = list(self.core.db.execute_query(
            """SELECT * FROM returns 
               WHERE original_serie = 'A' 
               AND cfdi_egreso_status = 'pending'
               ORDER BY created_at"""
        ))
        return [dict(r) for r in result]
    
    def mark_cfdi_egreso_done(self, return_folio: str, uuid: str) -> Dict[str, Any]:
        """Marca CFDI de Egreso como generado."""
        try:
            self.core.db.execute_write(
                """UPDATE returns 
                   SET cfdi_egreso_uuid = %s, cfdi_egreso_status = 'completed'
                   WHERE return_folio = %s""",
                (uuid, return_folio)
            )
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_returns_summary(self, start_date: str = None, 
                            end_date: str = None) -> Dict[str, Any]:
        """Resumen de devoluciones por período."""
        start = start_date or datetime.now().strftime('%Y-01-01')
        end = end_date or datetime.now().strftime('%Y-12-31')
        
        sql = """
            SELECT 
                original_serie,
                COUNT(*) as count,
                COALESCE(SUM(total), 0) as total,
                COALESCE(SUM(CASE WHEN cfdi_egreso_status = 'pending' THEN 1 ELSE 0 END), 0) as pending_cfdi
            FROM returns
            WHERE created_at::date BETWEEN %s AND %s
            GROUP BY original_serie
        """
        result = list(self.core.db.execute_query(sql, (start, end)))
        
        return {
            'period': f'{start} a {end}',
            'by_serie': {r['original_serie']: dict(r) for r in result},
            'total_returns': sum(r['count'] for r in result),
            'total_amount': sum(float(r['total'] or 0) for r in result)
        }
