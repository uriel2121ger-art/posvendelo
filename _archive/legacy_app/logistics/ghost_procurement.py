from pathlib import Path

"""
Ghost Procurement - Simulador de Abasto Serie B
Genera entradas espejo para compras sin factura
"""

from typing import Any, Dict, List
from datetime import datetime, timedelta
import logging
import random
import sys

logger = logging.getLogger(__name__)

class GhostProcurement:
    """
    Generador de Entradas Espejo para Serie B.
    
    Cuando compras mercancía sin factura:
    - El inventario físico sube
    - Fiscalmente parece "Devolución" o "Ajuste de almacén"
    
    El SAT ve: "Mercancía recuperada vía garantía"
    Realidad: Compraste en efectivo sin factura
    """
    
    # Conceptos de entrada que parecen legítimos
    ENTRY_CONCEPTS = [
        'Devolución de cliente - producto no abierto',
        'Recuperación de garantía de proveedor',
        'Ajuste de inventario por error de conteo',
        'Mercancía en consignación devuelta',
        'Producto recuperado de exhibición',
        'Devolución por cambio de modelo',
        'Ingreso por localización de faltante',
        'Reingreso por cancelación de venta',
        'Ajuste por diferencia de auditoría física',
        'Mercancía de muestrario reintegrada',
    ]
    
    def __init__(self, core):
        self.core = core
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Crea tablas para entradas fantasma."""
        self.core.db.execute_write("""
            CREATE TABLE IF NOT EXISTS ghost_entries (
                id BIGSERIAL PRIMARY KEY,
                entry_code TEXT UNIQUE NOT NULL,
                concept TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                items_json TEXT,
                total_items INTEGER,
                total_value DOUBLE PRECISION,
                branch TEXT,
                linked_purchase_id INTEGER,
                justification TEXT
            )
        """)
    
    def create_mirror_entry(self, 
                           purchase_items: List[Dict],
                           branch: str,
                           purchase_id: int = None) -> Dict[str, Any]:
        """
        Crea entrada espejo para compra Serie B.
        
        Args:
            purchase_items: Lista de {product_id, quantity, cost}
            branch: Sucursal
            purchase_id: ID de compra B relacionada (opcional)
        
        Returns:
            Datos de la entrada espejo creada
        """
        import json

        # Generar código único
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        entry_code = f"AJ-{timestamp}-{random.randint(100, 999)}"
        
        # Seleccionar concepto aleatorio pero creíble
        concept = random.choice(self.ENTRY_CONCEPTS)
        
        # Calcular totales
        total_items = sum(item['quantity'] for item in purchase_items)
        total_value = sum(
            item['quantity'] * item.get('cost', 0) 
            for item in purchase_items
        )
        
        # Generar justificación narrativa
        justification = self._generate_justification(concept, total_items)
        
        # Preparar items para guardar
        items_with_narrative = []
        for item in purchase_items:
            product = self._get_product(item['product_id'])
            items_with_narrative.append({
                'product_id': item['product_id'],
                'sku': product.get('barcode', ''),
                'name': product.get('name', ''),
                'quantity': item['quantity'],
                'concept': concept,
                'justification': self._get_item_justification(concept)
            })
        
        # Guardar entrada
        self.core.db.execute_query("""
            INSERT INTO ghost_entries 
            (entry_code, concept, items_json, total_items, total_value, 
             branch, linked_purchase_id, justification)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            entry_code, concept, json.dumps(items_with_narrative),
            total_items, total_value, branch, purchase_id, justification
        ), commit=True)
        
        # Actualizar inventario (Parte A Fase 1.4: registrar movimiento para delta sync)
        for item in purchase_items:
            pid, qty = item['product_id'], item['quantity']
            self.core.db.execute_query("""
                UPDATE products SET stock = stock + %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s
            """, (qty, pid), commit=True)
            try:
                self.core.db.execute_write(
                    """INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                       VALUES (%s, 'IN', 'ghost_procurement', %s, %s, 'ghost_procurement', NOW(), 0)""",
                    (pid, qty, concept or "Entrada espejo")
                )
            except Exception as e:
                logger.debug("ghost_procurement movement: %s", e)
        
        # SECURITY: No loguear operaciones Ghost Entry
        pass
        
        return {
            'success': True,
            'entry_code': entry_code,
            'concept': concept,
            'total_items': total_items,
            'total_value': total_value,
            'justification': justification
        }
    
    def _generate_justification(self, concept: str, quantity: int) -> str:
        """Genera justificación narrativa creíble."""
        
        if 'devolución' in concept.lower():
            return (f"Cliente devolvió {quantity} unidades en condiciones originales. "
                    f"Producto verificado sin uso. Se procede a reingreso a inventario "
                    f"conforme a política de devoluciones (15 días hábiles).")
        
        elif 'garantía' in concept.lower():
            return (f"Proveedor aceptó devolución de {quantity} unidades por defecto de fábrica. "
                    f"Se recibe mercancía de reemplazo sin costo. "
                    f"Ref: Acuerdo comercial de garantía vigente.")
        
        elif 'ajuste' in concept.lower() or 'error' in concept.lower():
            return (f"Auditoría física detectó diferencia positiva de {quantity} unidades. "
                    f"Se ajusta inventario conforme a conteo del día. "
                    f"Posible error en registro de entrada anterior.")
        
        elif 'consignación' in concept.lower():
            return (f"Mercancía en consignación no vendida regresa a inventario propio. "
                    f"{quantity} unidades reintegradas conforme a contrato.")
        
        elif 'exhibición' in concept.lower() or 'muestrario' in concept.lower():
            return (f"Productos de exhibición/muestrario retirados de área de ventas. "
                    f"Se reintegran {quantity} unidades a inventario disponible.")
        
        else:
            return (f"Reingreso de {quantity} unidades por concepto de: {concept}. "
                    f"Documentación de soporte archivada.")
    
    def _get_item_justification(self, concept: str) -> str:
        """Justificación breve para cada item."""
        justifications = {
            'devolución': 'Producto en condiciones originales, sin uso',
            'garantía': 'Reemplazo de proveedor por defecto',
            'ajuste': 'Diferencia física detectada en auditoría',
            'consignación': 'Mercancía no vendida, regresa a stock',
            'exhibición': 'Retiro de área de demostración',
        }
        
        for key, value in justifications.items():
            if key in concept.lower():
                return value
        
        return 'Reingreso documentado'
    
    def _get_product(self, product_id: int) -> Dict:
        """Obtiene datos del producto."""
        products = list(self.core.db.execute_query("""
            SELECT * FROM products WHERE id = %s
        """, (product_id,)))
        return dict(products[0]) if products else {}
    
    def auto_balance_inventory(self, branch: str = None) -> Dict[str, Any]:
        """
        Analiza discrepancias entre Serie A (fiscal) y stock real,
        y genera entradas espejo automáticas para balancear.
        """
        try:
            # Detectar productos con más stock del que debería según ventas A
            query = """
                SELECT p.id, p.name, p.stock as current_stock,
                       COALESCE(SUM(CASE WHEN s.serie = 'A' THEN si.qty ELSE 0 END), 0) as sold_a,
                       COALESCE((SELECT SUM(quantity) FROM purchase_items pi 
                                 JOIN purchases pu ON pi.purchase_id = pu.id 
                                 WHERE pi.product_id = p.id AND pu.has_invoice = 1), 0) as bought_a
                FROM products p
                LEFT JOIN sale_items si ON si.product_id = p.id
                LEFT JOIN sales s ON si.sale_id = s.id
                GROUP BY p.id
                HAVING current_stock > (bought_a - sold_a + 10)
            """
            
            discrepancies = list(self.core.db.execute_query(query))
            
            entries_created = 0
            for product in discrepancies:
                expected = product['bought_a'] - product['sold_a']
                actual = product['current_stock']
                difference = actual - expected
                
                if difference > 5:  # Solo si la diferencia es significativa
                    self.create_mirror_entry(
                        [{'product_id': product['id'], 'quantity': difference, 'cost': 0}],
                        branch or 'general'
                    )
                    entries_created += 1
            
            return {
                'success': True,
                'entries_created': entries_created,
                'message': f'{entries_created} ajustes de inventario generados'
            }
            
        except Exception as e:
            logger.error(f"Error en auto-balance: {e}")
            return {'success': False, 'error': str(e)}
    
    def generate_entry_report(self, entry_code: str) -> Dict[str, Any]:
        """
        Genera reporte PDF de la entrada (para archivo legal).
        """
        import json
        
        entries = list(self.core.db.execute_query("""
            SELECT * FROM ghost_entries WHERE entry_code = %s
        """, (entry_code,)))
        
        if not entries:
            return None
        
        entry = dict(entries[0])
        items = json.loads(entry['items_json'])
        
        return {
            'document_type': 'NOTA DE AJUSTE DE INVENTARIO',
            'document_number': entry_code,
            'date': datetime.fromisoformat(entry['created_at']).strftime('%d/%m/%Y'),
            'concept': entry['concept'],
            'justification': entry['justification'],
            'branch': entry['branch'],
            'items': [
                {
                    'sku': item['sku'],
                    'name': item['name'],
                    'quantity': item['quantity'],
                    'reason': item['justification']
                }
                for item in items
            ],
            'total_items': entry['total_items'],
            'signatures': {
                'prepared_by': '________________________',
                'verified_by': '________________________',
                'authorized_by': '________________________'
            },
            'footer': 'Documento interno de control de inventario'
        }

# Función de conveniencia
def create_mirror_entry(core, items, branch, purchase_id=None):
    """Wrapper para crear entrada espejo."""
    ghost = GhostProcurement(core)
    return ghost.create_mirror_entry(items, branch, purchase_id)
