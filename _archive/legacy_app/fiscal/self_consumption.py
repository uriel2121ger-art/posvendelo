"""
Self Consumption Engine - Motor de autoconsumo y muestras gratuitas
Art. 25 LISR - Gastos de operación deducibles
"""

from typing import Any, Dict, List, Optional
from datetime import date, datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class SelfConsumptionEngine:
    """
    Motor de registro de autoconsumo y muestras.
    El autoconsumo es GASTO, no genera ingreso fiscal.
    """
    
    CATEGORIES = {
        'limpieza': 'Productos de limpieza del local',
        'empleados': 'Consumo autorizado por personal',
        'muestras': 'Muestras gratuitas para clientes',
        'operacion': 'Insumos de operación diaria',
        'oficina': 'Material de oficina',
        'otro': 'Otro tipo de consumo'
    }
    
    def __init__(self, core):
        self.core = core
        self._setup_table()
    
    def _setup_table(self):
        """Crea tabla de autoconsumo si no existe."""
        try:
            self.core.db.execute_write("""
                CREATE TABLE IF NOT EXISTS self_consumption (
                    id BIGSERIAL PRIMARY KEY,
                    product_id INTEGER NOT NULL,
                    product_name TEXT,
                    product_sku TEXT,
                    quantity REAL NOT NULL,
                    unit_cost REAL,
                    total_value REAL,
                    category TEXT DEFAULT 'operacion',
                    reason TEXT,
                    beneficiary TEXT,
                    authorized_by TEXT,
                    voucher_folio TEXT,
                    status TEXT DEFAULT 'registered',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.core.db.execute_write(
                "CREATE INDEX IF NOT EXISTS idx_selfcons_date ON self_consumption(created_at)"
            )
        except Exception as e:
            logger.error(f"Error creating self_consumption table: {e}")
    
    def register_consumption(self, product_id: int, quantity: float,
                              category: str, reason: str = None,
                              beneficiary: str = None) -> Dict[str, Any]:
        """
        Registra un consumo interno.
        
        Args:
            product_id: ID del producto consumido
            quantity: Cantidad consumida
            category: Categoría (limpieza, empleados, muestras, operacion)
            reason: Descripción opcional
            beneficiary: Quien recibe (empleado, cliente)
        """
        # Obtener producto
        product = list(self.core.db.execute_query(
            "SELECT id, name, sku, price, stock FROM products WHERE id = %s",
            (product_id,)
        ))
        
        if not product:
            return {'success': False, 'error': 'Producto no encontrado'}
        
        p = product[0]
        
        # Verificar stock
        if float(p['stock'] or 0) < quantity:
            return {'success': False, 'error': 'Stock insuficiente'}
        
        # Calcular valor (costo estimado = 70% del precio)
        unit_cost = float(p['price'] or 0) * 0.7
        total_value = unit_cost * quantity
        
        # Registrar consumo
        try:
            self.core.db.execute_write(
                """INSERT INTO self_consumption
                   (product_id, product_name, product_sku, quantity,
                    unit_cost, total_value, category, reason,
                    beneficiary, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (product_id, p['name'], p['sku'], quantity,
                 unit_cost, total_value, category, reason,
                 beneficiary, datetime.now().isoformat())
            )
            
            # Descontar stock (Parte A Fase 1.4: registrar movimiento para delta sync)
            self.core.db.execute_write(
                "UPDATE products SET stock = stock - %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (quantity, product_id)
            )
            try:
                self.core.db.execute_write(
                    """INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                       VALUES (%s, 'OUT', 'self_consumption', %s, %s, 'self_consumption', NOW(), 0)""",
                    (product_id, quantity, reason or "Autoconsumo")
                )
            except Exception as e:
                logger.debug("self_consumption movement: %s", e)
            
            # SECURITY: No loguear autoconsumo (ajustes de inventario)
            pass
            
            return {
                'success': True,
                'product': p['name'],
                'quantity': quantity,
                'value': total_value,
                'category': category,
                'message': f'Registrado como gasto de operación'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def register_sample(self, product_id: int, quantity: float,
                        recipient: str = 'Cliente') -> Dict[str, Any]:
        """
        Registra entrega de muestra gratuita.
        Atajo para registro tipo 'muestras'.
        """
        return self.register_consumption(
            product_id=product_id,
            quantity=quantity,
            category='muestras',
            reason='Muestra gratuita promocional',
            beneficiary=recipient
        )
    
    def register_employee_consumption(self, product_id: int, 
                                       quantity: float,
                                       employee_name: str) -> Dict[str, Any]:
        """
        Registra consumo de empleado.
        """
        return self.register_consumption(
            product_id=product_id,
            quantity=quantity,
            category='empleados',
            reason='Consumo autorizado',
            beneficiary=employee_name
        )
    
    def get_monthly_summary(self, year: int = None, 
                            month: int = None) -> Dict[str, Any]:
        """Resumen mensual de autoconsumo por categoría."""
        year = year or datetime.now().year
        month = month or datetime.now().month
        
        sql = """
            SELECT 
                category,
                COUNT(*) as registros,
                COALESCE(SUM(quantity), 0) as unidades,
                COALESCE(SUM(total_value), 0) as valor
            FROM self_consumption
            WHERE EXTRACT(YEAR FROM created_at::timestamp) = %s
            AND EXTRACT(MONTH FROM created_at::timestamp) = %s
            GROUP BY category
        """
        result = list(self.core.db.execute_query(sql, (str(year), f'{month:02d}')))
        
        by_category = {}
        total_value = 0
        
        for r in result:
            by_category[r['category']] = {
                'registros': r['registros'],
                'unidades': r['unidades'],
                'valor': float(r['valor'] or 0)
            }
            total_value += float(r['valor'] or 0)
        
        return {
            'year': year,
            'month': month,
            'by_category': by_category,
            'total_value': total_value,
            'total_registros': sum(c['registros'] for c in by_category.values())
        }
    
    def generate_monthly_voucher(self, year: int = None, 
                                  month: int = None) -> Dict[str, Any]:
        """
        Genera vale mensual de autoconsumo.
        Este documento justifica la baja de inventario sin ventas.
        """
        year = year or datetime.now().year
        month = month or datetime.now().month
        
        # Obtener todos los consumos del mes
        sql = """
            SELECT * FROM self_consumption
            WHERE EXTRACT(YEAR FROM created_at::timestamp) = %s
            AND EXTRACT(MONTH FROM created_at::timestamp) = %s
            ORDER BY category, created_at
        """
        items = list(self.core.db.execute_query(sql, (str(year), f'{month:02d}')))
        
        if not items:
            return {
                'success': False, 
                'error': 'Sin registros de autoconsumo este mes'
            }
        
        # Generar folio
        folio = f"VALE-AUTO-{year}{month:02d}"
        
        # Actualizar registros con folio
        self.core.db.execute_write(
            """UPDATE self_consumption 
               SET voucher_folio = %s
               WHERE EXTRACT(YEAR FROM created_at::timestamp) = %s
               AND EXTRACT(MONTH FROM created_at::timestamp) = %s""",
            (folio, str(year), f'{month:02d}')
        )
        
        # Preparar datos para documento
        voucher_items = []
        for item in items:
            voucher_items.append({
                'product': item['product_name'],
                'quantity': item['quantity'],
                'value': float(item['total_value'] or 0),
                'reason': f"{item['category']}: {item.get('reason', '')}"
            })
        
        # Generar documento
        from app.fiscal.legal_documents import LegalDocumentGenerator
        doc_gen = LegalDocumentGenerator(self.core)
        
        result = doc_gen.generate_selfconsumption_voucher(
            items=voucher_items,
            period=f'{year}-{month:02d}'
        )
        
        result['folio'] = folio
        result['items_count'] = len(items)
        
        # SECURITY: No loguear generación de vales de autoconsumo
        pass
        
        return result
    
    def get_pending_voucher_months(self) -> List[str]:
        """Obtiene meses con consumos sin vale generado."""
        sql = """
            SELECT DISTINCT TO_CHAR(created_at::timestamp, 'YYYY-MM') as period
            FROM self_consumption
            WHERE voucher_folio IS NULL
            ORDER BY period
        """
        result = list(self.core.db.execute_query(sql))
        return [r['period'] for r in result]
