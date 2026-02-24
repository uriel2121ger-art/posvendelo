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
                    id SERIAL PRIMARY KEY,  -- FIX 2026-02-01: PostgreSQL
                    sale_id INTEGER NOT NULL,
                    original_serie TEXT,
                    original_folio TEXT,
                    original_uuid TEXT,
                    return_folio TEXT UNIQUE,
                    return_type TEXT DEFAULT 'partial',
                    product_id INTEGER,
                    product_name TEXT,
                    quantity DECIMAL(15,2),  -- FIX 2026-02-01: PostgreSQL
                    unit_price DECIMAL(15,2),  -- FIX 2026-02-01: PostgreSQL
                    subtotal DECIMAL(15,2),  -- FIX 2026-02-01: PostgreSQL
                    tax DECIMAL(15,2),  -- FIX 2026-02-01: PostgreSQL
                    total DECIMAL(15,2),  -- FIX 2026-02-01: PostgreSQL
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
        Valida que TODOS los items estén en la venta original ANTES de procesar.

        Args:
            sale_id: ID de la venta original
            items: Lista de items a devolver [{product_id, quantity}]
            reason: Motivo de devolución
            processed_by: Usuario que procesa
        """
        # 1. Validar que la venta existe
        sale = list(self.core.db.execute_query(
            "SELECT * FROM sales WHERE id = %s", (sale_id,)
        ))

        if not sale:
            return {'success': False, 'error': 'Venta no encontrada'}

        sale = sale[0]
        serie = sale['serie']
        original_folio = sale['folio_visible']

        # 2. Obtener items de la venta original
        original_items = list(self.core.db.execute_query(
            """SELECT si.product_id, si.quantity as qty, si.price, p.name
               FROM sale_items si
               JOIN products p ON si.product_id = p.id
               WHERE si.sale_id = %s""",
            (sale_id,)
        ))
        original_items_map = {
            item['product_id']: {
                'qty': item['qty'],
                'price': item['price'],
                'name': item['name']
            }
            for item in original_items
        }

        # 3. Validar que TODOS los items a devolver estén en la venta original
        for item in items:
            product_id = item.get('product_id')
            qty_to_return = item.get('quantity', 1)

            if product_id not in original_items_map:
                return {
                    'success': False,
                    'error': f'Producto ID {product_id} no está en la venta original #{sale_id}'
                }

            original_qty = original_items_map[product_id]['qty']
            if qty_to_return > original_qty:
                return {
                    'success': False,
                    'error': f'Cantidad a devolver ({qty_to_return}) excede la cantidad vendida ({original_qty})'
                }

        # 4. Generar folio de devolución
        return_folio = self._generate_return_folio()

        total_return = Decimal('0')
        processed_items = []

        # 5. Procesar cada item (ya validados)
        for item in items:
            product_id = item.get('product_id')
            qty = item.get('quantity', 1)

            oi = original_items_map[product_id]
            unit_price = float(oi['price'])
            subtotal = unit_price * qty
            tax = subtotal * 0.16
            total = subtotal + tax
            total_return += Decimal(str(total))
            
            # CRITICAL FIX: Registrar devolución y reintegrar stock en una sola transacción
            # Si falla cualquier operación, TODO se revierte (rollback)
            ops = []
            ops.append((
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
            ))
            
            # Reintegrar stock
            ops.append((
                "UPDATE products SET stock = stock + %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (qty, product_id)
            ))
            
            # Ejecutar TODO en una sola transacción atómica
            result = self.core.db.execute_transaction(ops, timeout=5)
            if not result.get('success'):
                raise RuntimeError("Transaction failed - return not processed")
            
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
        """
        Genera folio único de devolución.
        
        CRITICAL FIX: Usa tabla de secuencias para evitar race conditions.
        Similar a get_next_folio(), usa UPDATE ... RETURNING para atomicidad.
        """
        year = datetime.now().year
        serie = f"DEV-{year}"
        
        # Asegurar que existe secuencia para este año
        existing = self.core.db.execute_query(
            "SELECT 1 FROM secuencias WHERE serie = %s AND terminal_id = 0",
            (serie,)
        )
        if not existing:
            try:
                self.core.db.execute_write(
                    "INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion) VALUES (%s, 0, 0, %s)",
                    (serie, f"Devoluciones {year}")
                )
            except Exception as e:
                # Si falla por duplicado (otra transacción lo creó), continuar
                error_str = str(e).lower()
                if 'duplicate' not in error_str and 'unique' not in error_str:
                    raise
        
        # CRITICAL FIX: Incremento atómico con UPDATE ... RETURNING
        result = self.core.db.execute_query(
            """UPDATE secuencias 
               SET ultimo_numero = ultimo_numero + 1 
               WHERE serie = %s AND terminal_id = 0
               RETURNING ultimo_numero""",
            (serie,)
        )
        
        if result and result[0]:
            seq = result[0]['ultimo_numero']
        else:
            # Fallback: leer directamente
            fallback_result = self.core.db.execute_query(
                "SELECT ultimo_numero FROM secuencias WHERE serie = %s AND terminal_id = 0",
                (serie,)
            )
            seq = (fallback_result[0]['ultimo_numero'] or 0) if fallback_result else 0
        
        return f"DEV-{year}-{seq:05d}"
    
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
            WHERE DATE(created_at) BETWEEN %s AND %s
            GROUP BY original_serie
        """
        result = list(self.core.db.execute_query(sql, (start, end)))
        
        return {
            'period': f'{start} a {end}',
            'by_serie': {r['original_serie']: dict(r) for r in result},
            'total_returns': sum(r['count'] for r in result),
            'total_amount': sum(float(r['total'] or 0) for r in result)
        }
