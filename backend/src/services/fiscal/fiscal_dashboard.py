"""
Fiscal Dashboard - Inteligencia de Brecha Serie A vs B
Centro de comando para monitoreo fiscal en tiempo real
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class FiscalDashboard:
    """Dashboard de inteligencia fiscal para monitoreo Serie A/B."""
    
    # Límite RESICO 2024-2025
    RESICO_LIMIT = Decimal('3500000.00')
    RESICO_WARNING = Decimal('3200000.00')  # Alerta temprana
    
    def __init__(self, core):
        self.core = core
    
    def get_dashboard_data(self, year: int = None) -> Dict[str, Any]:
        """
        Obtiene datos completos del dashboard fiscal.
        
        Returns:
            Dict con métricas de Serie A, B, gastos, estado RESICO
        """
        year = year or datetime.now().year
        
        return {
            'serie_a': self._get_serie_stats('A', year),
            'serie_b': self._get_serie_stats('B', year),
            'gastos': self._get_gastos_facturados(year),
            'termometro': self._calcular_termometro(year),
            'resico': self._check_resico_status(year),
            'pendientes_global': self._get_pendientes_global(),
            'recomendaciones': self._generar_recomendaciones(year),
        }
    
    def _get_serie_stats(self, serie: str, year: int) -> Dict[str, Any]:
        """Estadísticas por serie."""
        sql = """
            SELECT
                COUNT(*) as ventas,
                COALESCE(SUM(total), 0) as total,
                COALESCE(SUM(subtotal), 0) as subtotal,
                COALESCE(SUM(tax), 0) as impuestos
            FROM sales
            WHERE serie = %s
            AND EXTRACT(YEAR FROM timestamp)::TEXT = %s
            AND status != 'cancelled'
        """
        result = list(self.core.db.execute_query(sql, (serie, str(year))))
        
        if result:
            r = result[0]
            return {
                'ventas': r['ventas'],
                'total': float(r['total'] or 0),
                'subtotal': float(r['subtotal'] or 0),
                'impuestos': float(r['impuestos'] or 0),
            }
        return {'ventas': 0, 'total': 0, 'subtotal': 0, 'impuestos': 0}
    
    def _get_gastos_facturados(self, year: int) -> Dict[str, Any]:
        """
        Estima gastos facturados del negocio.
        Nota: Requiere tabla de gastos o estimación.
        """
        # Por ahora estimamos gastos fijos mensuales
        # En producción esto vendría de una tabla de gastos/compras
        meses_transcurridos = datetime.now().month
        
        # Estimación conservadora de gastos mensuales
        gastos_mensuales = {
            'renta': 8000,
            'luz': 2500,
            'agua': 500,
            'internet': 800,
            'sueldos': 15000,
            'otros': 3000,
        }
        
        total_mensual = sum(gastos_mensuales.values())
        total_anual = total_mensual * meses_transcurridos
        
        return {
            'mensual_estimado': total_mensual,
            'anual_acumulado': total_anual,
            'detalle': gastos_mensuales,
            'nota': 'Estimación. Configura tus gastos reales en Configuración.'
        }
    
    def _calcular_termometro(self, year: int) -> Dict[str, Any]:
        """
        Calcula el termómetro fiscal: Serie A debe cubrir gastos.
        """
        serie_a = self._get_serie_stats('A', year)
        gastos = self._get_gastos_facturados(year)
        
        ingresos_a = serie_a['total']
        gastos_total = gastos['anual_acumulado']
        
        # Diferencia: positivo es bueno
        diferencia = ingresos_a - gastos_total
        
        # Porcentaje de cobertura
        if gastos_total > 0:
            cobertura = (ingresos_a / gastos_total) * 100
        else:
            cobertura = 100
        
        # Estado del termómetro
        if cobertura >= 110:
            estado = 'VERDE'
            mensaje = 'Excelente: Ingresos Serie A cubren gastos con margen'
        elif cobertura >= 100:
            estado = 'AMARILLO'
            mensaje = 'Cuidado: Ingresos Serie A apenas cubren gastos'
        else:
            estado = 'ROJO'
            mensaje = f'Alerta: Faltan ${abs(diferencia):,.2f} para cubrir gastos'
        
        return {
            'ingresos_a': ingresos_a,
            'gastos': gastos_total,
            'diferencia': diferencia,
            'cobertura_pct': round(cobertura, 1),
            'estado': estado,
            'mensaje': mensaje
        }
    
    def _check_resico_status(self, year: int) -> Dict[str, Any]:
        """
        Verifica estado vs límite RESICO.
        """
        serie_a = self._get_serie_stats('A', year)
        facturado = Decimal(str(serie_a['total']))
        
        restante = self.RESICO_LIMIT - facturado
        porcentaje = (facturado / self.RESICO_LIMIT) * 100
        
        if facturado >= self.RESICO_LIMIT:
            estado = 'EXCEDIDO'
            mensaje = 'Has superado el límite RESICO. Consulta a tu contador.'
        elif facturado >= self.RESICO_WARNING:
            estado = 'PELIGRO'
            mensaje = f'Alerta: Solo puedes facturar ${float(restante):,.2f} más este año'
        else:
            estado = 'OK'
            mensaje = f'Disponible para facturar: ${float(restante):,.2f}'
        
        return {
            'limite': float(self.RESICO_LIMIT),
            'facturado': float(facturado),
            'restante': float(restante),
            'porcentaje': float(round(porcentaje, 2)),
            'estado': estado,
            'mensaje': mensaje
        }
    
    def _get_pendientes_global(self) -> Dict[str, Any]:
        """
        Obtiene tickets Serie B sin factura global.
        """
        sql = """
            SELECT 
                COUNT(*) as tickets,
                COALESCE(SUM(total), 0) as total,
                MIN(timestamp) as mas_antiguo
            FROM sales s
            LEFT JOIN sale_cfdi_relation scr ON s.id = scr.sale_id
            WHERE s.serie = 'B'
            AND scr.id IS NULL
            AND s.status != 'cancelled'
        """
        result = list(self.core.db.execute_query(sql))
        
        if result and result[0]['tickets']:
            r = result[0]
            return {
                'tickets': r['tickets'],
                'total': float(r['total'] or 0),
                'mas_antiguo': r['mas_antiguo'],
                'mensaje': f'{r["tickets"]} tickets pendientes de global (${float(r["total"] or 0):,.2f})'
            }
        return {'tickets': 0, 'total': 0, 'mas_antiguo': None, 'mensaje': 'Sin pendientes'}
    
    def _generar_recomendaciones(self, year: int) -> List[str]:
        """Genera recomendaciones automáticas basadas en los datos."""
        recomendaciones = []
        
        termometro = self._calcular_termometro(year)
        resico = self._check_resico_status(year)
        pendientes = self._get_pendientes_global()
        
        if termometro['estado'] == 'ROJO':
            recomendaciones.append(
                f"⚠️ Necesitas facturar ${abs(termometro['diferencia']):,.2f} más en Serie A para cubrir tus gastos"
            )
        
        if resico['estado'] == 'PELIGRO':
            recomendaciones.append(
                f"🚨 Estás cerca del límite RESICO. Considera usar más Serie B para efectivo"
            )
        
        if pendientes['tickets'] > 50:
            recomendaciones.append(
                f"📋 Tienes {pendientes['tickets']} tickets en Serie B. Genera factura global pronto"
            )
        
        if not recomendaciones:
            recomendaciones.append("✅ Tu situación fiscal está en orden. ¡Sigue así!")
        
        return recomendaciones
    
    def get_smart_global_selection(self, max_amount: float = None) -> List[Dict]:
        """
        Selector inteligente de tickets para factura global.
        Prioriza: más antiguos y productos con potencial merma.
        """
        sql = """
            SELECT 
                s.id, s.folio_visible, s.timestamp, s.total,
                STRING_AGG(p.name, ', ') as productos  -- FIX 2026-02-01: PostgreSQL
            FROM sales s
            LEFT JOIN sale_cfdi_relation scr ON s.id = scr.sale_id
            LEFT JOIN sale_items si ON s.id = si.sale_id
            LEFT JOIN products p ON si.product_id = p.id
            WHERE s.serie = 'B'
            AND scr.id IS NULL
            AND s.status != 'cancelled'
            GROUP BY s.id
            ORDER BY s.timestamp ASC
            LIMIT 100
        """
        
        result = list(self.core.db.execute_query(sql))
        
        if max_amount:
            selected = []
            acumulado = 0
            for sale in result:
                if acumulado + float(sale['total']) <= max_amount:
                    selected.append(dict(sale))
                    acumulado += float(sale['total'])
            return selected
        
        return [dict(r) for r in result]
