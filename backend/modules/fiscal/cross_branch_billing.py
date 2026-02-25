"""
Cross-Branch Billing - Balanceo de Carga Fiscal (Facade Engine)
Distribuye facturación entre RFCs automáticamente y agrega justificaciones comerciales.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
from decimal import Decimal
from modules.fiscal.multi_emitter import MultiEmitterManager

logger = logging.getLogger(__name__)

class CrossBranchBilling:
    """
    Sistema de balanceo de carga fiscal entre RFCs.
    
    Cuando un RFC se acerca al límite RESICO:
    - Redirige facturas a otro RFC con capacidad (vía MultiEmitterManager)
    - Justificación: "Venta en Línea con Entrega en Sucursal"
    """
    
    # Conceptos para justificar facturación cruzada
    CROSS_BILLING_CONCEPTS = [
        'Venta en línea con entrega en sucursal',
        'Pedido de matriz con envío a sucursal',
        'Venta por catálogo con entrega local',
        'Orden de transferencia comercial',
        'Facturación consolidada de grupo',
    ]
    
    def __init__(self, db):
        self.db = db
        self.emitter_mgr = MultiEmitterManager(self.db)
    
    async def select_optimal_rfc_with_facade(self, 
                          amount: float, 
                          original_rfc: str = None,
                          branch_name: str = None) -> Dict[str, Any]:
        """
        Selecciona el RFC óptimo para facturar y agrega una justificación si es cruzada.
        
        Args:
            amount: Monto a facturar
            original_rfc: RFC original de la sucursal
            branch_name: Nombre de la sucursal origen
        
        Returns:
            Dict con RFC recomendado y justificación si es cruzado.
        """
        dec_amount = Decimal(str(amount))
        optimal_emitter = await self.emitter_mgr.select_optimal_rfc(dec_amount)
        
        if not optimal_emitter:
             return {
                'rfc': original_rfc,
                'is_cross': False,
                'warning': 'TODOS LOS RFCs CERCA DEL LÍMITE RESICO',
                'action_required': True
            }

        best_rfc = optimal_emitter['rfc']
        
        # Si el RFC óptimo no es el original, inyectamos la fachada comercial
        if best_rfc and best_rfc != original_rfc and original_rfc:
            concept = await self._select_cross_concept(branch_name)
            
            return {
                'rfc': best_rfc,
                'is_cross': True,
                'original_rfc': original_rfc,
                'cross_concept': concept,
                'reason': f"Facturación cruzada: Redirigido a {best_rfc[:4]}***"
            }
        
        return {
            'rfc': best_rfc or original_rfc,
            'is_cross': False
        }
    
    async def _select_cross_concept(self, branch: str = None) -> str:
        """Selecciona concepto para justificar facturación cruzada."""
        import random
        if branch:
            return f"Venta en línea con entrega en sucursal {branch.capitalize()}"
        return random.choice(self.CROSS_BILLING_CONCEPTS)
    
    async def process_cross_invoice(self,
                             sale_id: int,
                             target_rfc: str,
                             original_rfc: str,
                             cross_concept: str) -> Dict[str, Any]:
        """
        Registra la fachada comercial de una factura cruzada localmente en la DB.
        """
        try:
            sale = await self.db.fetchrow("SELECT * FROM sales WHERE id = :sid", {"sid": sale_id})
            if not sale:
                return {'success': False, 'error': 'Venta no encontrada'}
            
            # Asegurar tabla (usualmente esto iria en migraciones, lo mantenemos por robustez)
            await self._ensure_tables()

            await self.db.execute("""
                INSERT INTO cross_invoices (
                    sale_id, original_rfc, target_rfc, 
                    cross_concept, amount, timestamp
                ) VALUES (:sid, :orig, :targ, :conc, :amt, CURRENT_TIMESTAMP)
            """, {
                "sid": sale_id, "orig": original_rfc, "targ": target_rfc,
                "conc": cross_concept, "amt": sale['total']
            })
            
            await self.db.execute("""
                UPDATE sales SET rfc_used = :targ, is_cross_billed = 1, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = :sid
            """, {"targ": target_rfc, "sid": sale_id})
            
            return {
                'success': True,
                'sale_id': sale_id,
                'target_rfc': target_rfc,
                'concept': cross_concept,
                'amount': sale['total']
            }
            
        except Exception as e:
            logger.error(f"Error en cross-billing: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def _ensure_tables(self):
        """Crea tabla para tracking de cross-billing."""
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS cross_invoices (
                id BIGSERIAL PRIMARY KEY,
                sale_id INTEGER,
                original_rfc TEXT,
                target_rfc TEXT,
                cross_concept TEXT,
                amount DOUBLE PRECISION,
                timestamp TIMESTAMP
            )
        """)

