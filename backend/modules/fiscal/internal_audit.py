"""
General de Guerra - AI Cross-Auditor
Auditoría cruzada en tiempo real (Materiality, Extracted Cash, Multi-Emitter limits)
Consolida lógica de general_guerra, cross_audit y weekly_intel.
"""

from typing import Any, Dict, List
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from ..shared.constants import RESICO_ANNUAL_LIMIT, dec, money

logger = logging.getLogger(__name__)

class GeneralDeGuerra:
    """
    Sistema de Análisis de Auditoría en Tiempo Real.
    Verifica que cada capa esté alineada y blindada ante el SAT.
    """

    RESICO_LIMIT = RESICO_ANNUAL_LIMIT
    MERMA_TOLERANCE = 2.0  # %
    
    def __init__(self, db):
        self.db = db
        self.findings = []
        self.report = {}
    
    async def run_full_audit(self) -> Dict[str, Any]:
        """Ejecuta la auditoría cruzada de todas las capas de defensa."""
        logger.info("🎖️ Iniciando Auditoría General de Guerra")
        self.findings = []
        
        # 1. Auditoría de Materialidad (Fotos de Merma)
        materiality_findings = await self._analyze_materiality()
        self.findings.extend(materiality_findings)
        
        # 2. Auditoría Fiscal (Límites RESICO Multi-RFC)
        fiscal_findings = await self._analyze_fiscal()
        self.findings.extend(fiscal_findings)
        
        # 3. Auditoría de Inventario (Real vs Teórico)
        inventory_findings = await self._analyze_inventory()
        self.findings.extend(inventory_findings)
        
        # 4. Auditoría de Efectivo (Cash Extraction)
        cash_findings = await self._analyze_cash_extraction()
        self.findings.extend(cash_findings)
        
        # Evaluación Global
        criticals = sum(1 for f in self.findings if f['severity'] == 'high')
        warnings = sum(1 for f in self.findings if f['severity'] == 'medium')
        
        self.report = {
            'timestamp': datetime.now().isoformat(),
            'status': 'DANGER' if criticals > 0 else ('WARNING' if warnings > 0 else 'SAFE'),
            'summary': {
                'critical_alerts': criticals,
                'warnings': warnings,
                'total_findings': len(self.findings)
            },
            'alerts': self.findings
        }
        
        return self.report

    async def _analyze_materiality(self) -> List[Dict]:
        """Verifica que TODA merma tenga evidencia fotográfica y actas legales."""
        findings = []
        try:
            row = await self.db.fetchrow("""
                SELECT COUNT(*) as count
                FROM loss_records
                WHERE (photo_path IS NULL OR photo_path = '')
                AND created_at::timestamp >= CURRENT_DATE - INTERVAL '7 days'
            """)
            count = int(row['count'] or 0) if row else 0
            
            if count > 0:
                findings.append({
                    'type': 'MATERIALITY',
                    'severity': 'high' if count > 5 else 'medium',
                    'title': f'{count} Mermas Indocumentadas',
                    'message': 'Sin fotos, el SAT puede clasificar la merma como inventario omitido (Serie B).',
                    'action': 'Contactar cajeras para cargar fotos de evidencia.'
                })
        except Exception as e:
            logger.error(f"Error materiality audit: {e}")
        return findings

    async def _analyze_fiscal(self) -> List[Dict]:
        """Analiza la capacidad restante de todos los RFCs de la Federación."""
        findings = []
        try:
            from modules.fiscal.multi_emitter import MultiEmitterManager
            mgr = MultiEmitterManager(self.db)
            emitters = await mgr.list_emitters()
            
            for e in emitters:
                rfc = e['rfc']
                total = Decimal(str(e['current_resico_amount']))
                percentage = (total / self.RESICO_LIMIT) * 100
                
                if percentage >= 85:
                    findings.append({
                        'type': 'FISCAL_RESICO',
                        'severity': 'high' if percentage >= 95 else 'medium',
                        'title': f'RFC {rfc[:4]}*** al {percentage:.1f}% de Límite RESICO',
                        'message': f'Riesgo de expulsión de régimen. Margen: ${(self.RESICO_LIMIT - total):,.2f}',
                        'action': 'Rotar facturas al siguiente RFC en Multi-Emitter.'
                    })
        except Exception as e:
            logger.error(f"Error fiscal audit: {e}")
        return findings
    
    async def _analyze_inventory(self) -> List[Dict]:
        """Detecta varianzas enormes de inventario que rompen el escudo fiscal."""
        findings = []
        try:
            # Query the difference between sold and registered shrinkage.
            rows = await self.db.fetch("""
                SELECT p.id, p.name, p.stock,
                    COALESCE((SELECT SUM(qty) FROM sale_items si JOIN sales s ON si.sale_id = s.id WHERE si.product_id = p.id AND s.timestamp::timestamp >= CURRENT_DATE - INTERVAL '7 days'), 0) as sold,
                    COALESCE((SELECT SUM(total_value) FROM loss_records lr WHERE lr.product_id = p.id AND lr.created_at::timestamp >= CURRENT_DATE - INTERVAL '7 days'), 0) as shrink
                FROM products p
                WHERE p.stock > 0
                LIMIT 100
            """)
            for p in rows:
                sold = dec(p['sold'])
                shrink = dec(p['shrink'])
                stock = dec(p['stock'])
                
                # If there's high shrinkage recorded compared to stock/sales, it's an anomaly 
                if shrink > (stock * 0.2) + sold:
                    findings.append({
                        'type': 'INVENTORY_ANOMALY',
                        'severity': 'medium',
                        'title': f'Varianza Crítica: {p["name"]}',
                        'message': f'Demasiada merma registrada vs ventas. El algoritmo SAT lo detectaría como fraude Serie B.',
                        'action': f'Revisar Kardex y justificar mermas de producto #{p["id"]}.'
                    })
        except Exception as e:
            logger.error(f"Error inventory audit: {e}")
        return findings

    async def _analyze_cash_extraction(self) -> List[Dict]:
        """Protección contra alertas bancarias por lavado/$50k+"""
        findings = []
        try:
            row = await self.db.fetchrow("""
                SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as ops
                FROM cash_movements
                WHERE type = 'out'
                AND timestamp >= DATE_TRUNC('month', CURRENT_DATE)
            """)
            if row:
                total = dec(row['total'])
                if total > 45000:
                    findings.append({
                        'type': 'ANTI_MONEY_LAUNDERING',
                        'severity': 'high',
                        'title': 'Peligro de Alerta Bancaria ($50k)',
                        'message': f'Extracciones mensuales de ${total:,.2f} MXN. Límite seguro es $45k.',
                        'action': 'Detener extracciones Fiat. Usar vía Crypto Bridge.'
                    })
        except Exception as e:
            # Silently ignore if expenses table or category doesn't exist yet
            pass
        return findings
