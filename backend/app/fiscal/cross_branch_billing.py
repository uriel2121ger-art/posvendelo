from pathlib import Path

"""
Cross-Branch Billing - Balanceo de Carga Fiscal
Distribuye facturación entre RFCs automáticamente
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
import sys

logger = logging.getLogger(__name__)

class CrossBranchBilling:
    """
    Sistema de balanceo de carga fiscal entre RFCs.
    
    Cuando un RFC se acerca al límite RESICO:
    - Redirige facturas a otro RFC con capacidad
    - Justificación: "Venta en Línea con Entrega en Sucursal"
    
    Mantiene todos los RFCs en niveles "saludables".
    """
    
    RESICO_ANNUAL_LIMIT = 3_500_000
    WARNING_THRESHOLD = 0.70  # 70% = comenzar a balancear
    CRITICAL_THRESHOLD = 0.85  # 85% = balanceo urgente
    
    # Conceptos para justificar facturación cruzada
    CROSS_BILLING_CONCEPTS = [
        'Venta en línea con entrega en sucursal',
        'Pedido de matriz con envío a sucursal',
        'Venta por catálogo con entrega local',
        'Orden de transferencia comercial',
        'Facturación consolidada de grupo',
    ]
    
    def __init__(self, core):
        self.core = core
        self.rfc_status = {}
    
    def get_rfc_load_status(self) -> Dict[str, Any]:
        """
        Obtiene estado de carga de todos los RFCs.
        """
        try:
            rfcs = list(self.core.db.execute_query("""
                SELECT 
                    rfc,
                    COALESCE(SUM(total), 0) as invoiced,
                    COUNT(*) as invoice_count
                FROM invoices
                WHERE EXTRACT(YEAR FROM fecha::timestamp) = EXTRACT(YEAR FROM 'now'::timestamp)
                GROUP BY rfc
            """))
            
            status = {}
            for rfc_data in rfcs:
                rfc = rfc_data['rfc']
                invoiced = float(rfc_data['invoiced'])
                remaining = self.RESICO_ANNUAL_LIMIT - invoiced
                percentage = (invoiced / self.RESICO_ANNUAL_LIMIT) * 100
                
                if percentage >= self.CRITICAL_THRESHOLD * 100:
                    health = 'CRITICAL'
                elif percentage >= self.WARNING_THRESHOLD * 100:
                    health = 'WARNING'
                else:
                    health = 'HEALTHY'
                
                status[rfc] = {
                    'invoiced': invoiced,
                    'remaining': remaining,
                    'percentage': round(percentage, 1),
                    'invoice_count': rfc_data['invoice_count'],
                    'health': health,
                    'can_receive': health != 'CRITICAL'
                }
            
            self.rfc_status = status
            return status
            
        except Exception as e:
            logger.error(f"Error obteniendo status RFC: {e}")
            return {}
    
    def select_optimal_rfc(self, 
                          amount: float, 
                          original_rfc: str = None,
                          branch: str = None) -> Dict[str, Any]:
        """
        Selecciona el RFC óptimo para facturar.
        
        Args:
            amount: Monto a facturar
            original_rfc: RFC original de la sucursal
            branch: Sucursal origen
        
        Returns:
            RFC recomendado y justificación si es cruzado
        """
        status = self.get_rfc_load_status()
        
        if not status:
            return {
                'rfc': original_rfc,
                'is_cross': False,
                'reason': 'No hay datos de RFCs'
            }
        
        # Verificar RFC original
        if original_rfc and original_rfc in status:
            original_status = status[original_rfc]
            
            # Si el RFC original está sano, usarlo
            if original_status['health'] == 'HEALTHY':
                return {
                    'rfc': original_rfc,
                    'is_cross': False,
                    'remaining': original_status['remaining']
                }
            
            # Si está en warning pero puede recibir este monto
            if original_status['health'] == 'WARNING':
                if original_status['remaining'] > amount * 2:
                    return {
                        'rfc': original_rfc,
                        'is_cross': False,
                        'warning': f"RFC al {original_status['percentage']}%",
                        'remaining': original_status['remaining']
                    }
        
        # Buscar RFC con más capacidad
        best_rfc = None
        best_remaining = 0
        
        for rfc, data in status.items():
            if data['can_receive'] and data['remaining'] > best_remaining:
                best_rfc = rfc
                best_remaining = data['remaining']
        
        if best_rfc and best_rfc != original_rfc:
            # Facturación cruzada
            concept = self._select_cross_concept(branch)
            
            return {
                'rfc': best_rfc,
                'is_cross': True,
                'original_rfc': original_rfc,
                'cross_concept': concept,
                'remaining': best_remaining,
                'reason': f"RFC {original_rfc[:4]}*** al límite, redirigido a {best_rfc[:4]}***"
            }
        
        # No hay RFC disponible con capacidad
        return {
            'rfc': original_rfc,
            'is_cross': False,
            'warning': 'TODOS LOS RFCs CERCA DEL LÍMITE',
            'action_required': True
        }
    
    def _select_cross_concept(self, branch: str = None) -> str:
        """Selecciona concepto para justificar facturación cruzada."""
        import random
        
        if branch:
            return f"Venta en línea con entrega en sucursal {branch.capitalize()}"
        
        return random.choice(self.CROSS_BILLING_CONCEPTS)
    
    def process_cross_invoice(self,
                             sale_id: int,
                             target_rfc: str,
                             original_rfc: str,
                             cross_concept: str) -> Dict[str, Any]:
        """
        Procesa una factura cruzada.
        
        Registra la factura en el RFC seleccionado con la justificación
        apropiada.
        """
        try:
            # Obtener datos de la venta
            sales = list(self.core.db.execute_query("""
                SELECT * FROM sales WHERE id = %s
            """, (sale_id,)))
            
            if not sales:
                return {'success': False, 'error': 'Venta no encontrada'}
            
            sale = dict(sales[0])
            
            # Crear registro de factura cruzada
            self.core.db.execute_query("""
                INSERT INTO cross_invoices (
                    sale_id, original_rfc, target_rfc, 
                    cross_concept, amount, timestamp
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                sale_id, original_rfc, target_rfc,
                cross_concept, sale['total'],
                datetime.now().isoformat()
            ))
            
            # Actualizar la venta con el RFC usado
            self.core.db.execute_write("""
                UPDATE sales SET rfc_used = %s, is_cross_billed = 1, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s
            """, (target_rfc, sale_id))
            
            # SECURITY: No loguear operaciones de cross-billing
            pass
            
            return {
                'success': True,
                'sale_id': sale_id,
                'target_rfc': target_rfc,
                'concept': cross_concept,
                'amount': sale['total']
            }
            
        except Exception as e:
            logger.error(f"Error en cross-billing: {e}")
            return {'success': False, 'error': str(e)}
    
    def auto_rebalance(self) -> Dict[str, Any]:
        """
        Ejecuta rebalanceo automático de carga fiscal.
        
        Analiza el estado de todos los RFCs y distribuye
        la carga equitativamente.
        """
        status = self.get_rfc_load_status()
        
        if not status:
            return {'success': False, 'error': 'No hay datos'}
        
        # Calcular carga promedio objetivo
        total_invoiced = sum(s['invoiced'] for s in status.values())
        num_rfcs = len(status)
        target_per_rfc = total_invoiced / num_rfcs
        
        recommendations = []
        
        for rfc, data in status.items():
            diff = data['invoiced'] - target_per_rfc
            
            if diff > 50000:  # Más de 50k sobre el promedio
                recommendations.append({
                    'rfc': rfc,
                    'action': 'REDUCE',
                    'excess': diff,
                    'message': f"Reducir facturación en {rfc[:4]}*** (exceso: ${diff:,.0f})"
                })
            elif diff < -50000:  # Más de 50k bajo el promedio
                recommendations.append({
                    'rfc': rfc,
                    'action': 'INCREASE',
                    'deficit': abs(diff),
                    'message': f"Aumentar facturación en {rfc[:4]}*** (disponible: ${abs(diff):,.0f})"
                })
        
        return {
            'success': True,
            'total_invoiced': total_invoiced,
            'target_per_rfc': target_per_rfc,
            'recommendations': recommendations,
            'symmetry_score': self._calculate_symmetry_score(status)
        }
    
    def _calculate_symmetry_score(self, status: Dict) -> Dict[str, Any]:
        """Calcula score de simetría entre RFCs."""
        if not status:
            return {'score': 0, 'status': 'NO_DATA'}
        
        percentages = [s['percentage'] for s in status.values()]
        
        if not percentages:
            return {'score': 0, 'status': 'NO_DATA'}
        
        avg = sum(percentages) / len(percentages)
        variance = sum((p - avg) ** 2 for p in percentages) / len(percentages)
        std_dev = variance ** 0.5
        
        # Score: 100 si perfecta simetría, baja con varianza alta
        score = max(0, 100 - std_dev * 5)
        
        if score >= 80:
            status_text = 'EXCELLENT'
        elif score >= 60:
            status_text = 'GOOD'
        elif score >= 40:
            status_text = 'FAIR'
        else:
            status_text = 'POOR'
        
        return {
            'score': round(score, 1),
            'status': status_text,
            'std_deviation': round(std_dev, 1)
        }
    
    def _ensure_tables(self):
        """Crea tabla para tracking de cross-billing."""
        self.core.db.execute_write("""
            CREATE TABLE IF NOT EXISTS cross_invoices (
                id BIGSERIAL PRIMARY KEY,
                sale_id INTEGER,
                original_rfc TEXT,
                target_rfc TEXT,
                cross_concept TEXT,
                amount DOUBLE PRECISION,
                timestamp TEXT
            )
        """)

# Función de conveniencia
def select_billing_rfc(core, amount, original_rfc=None, branch=None):
    """Wrapper para selección de RFC óptimo."""
    billing = CrossBranchBilling(core)
    return billing.select_optimal_rfc(amount, original_rfc, branch)
