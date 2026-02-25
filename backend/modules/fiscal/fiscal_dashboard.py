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
    
    async def get_dashboard_data(self, year: int = None) -> Dict[str, Any]:
        year = year or datetime.now().year
        
        serie_a = await self._get_serie_stats('A', year)
        serie_b = await self._get_serie_stats('B', year)
        gastos = await self._get_gastos_facturados(year)
        termometro = await self._calcular_termometro(year)
        resico = await self._check_resico_status(year)
        pendientes_global = await self._get_pendientes_global()
        recomendaciones = await self._generar_recomendaciones(year)
        
        return {
            'serie_a': serie_a,
            'serie_b': serie_b,
            'gastos': gastos,
            'termometro': termometro,
            'resico': resico,
            'pendientes_global': pendientes_global,
            'recomendaciones': recomendaciones,
        }
    
    async def _get_serie_stats(self, serie: str, year: int) -> Dict[str, Any]:
        sql = """
            SELECT COUNT(*) as ventas, COALESCE(SUM(total), 0) as total, COALESCE(SUM(subtotal), 0) as subtotal, COALESCE(SUM(tax), 0) as impuestos
            FROM sales 
            WHERE serie = %s AND EXTRACT(YEAR FROM timestamp::timestamp) = %s AND status != 'cancelled'
        """
        result = list(await self.core.db.execute_query(sql, (serie, str(year))))
        if result:
            r = result[0]
            return {'ventas': r['ventas'], 'total': float(r['total'] or 0), 'subtotal': float(r['subtotal'] or 0), 'impuestos': float(r['impuestos'] or 0)}
        return {'ventas': 0, 'total': 0, 'subtotal': 0, 'impuestos': 0}
    
    async def _get_gastos_facturados(self, year: int) -> Dict[str, Any]:
        meses_transcurridos = datetime.now().month
        gastos_mensuales = {'renta': 8000, 'luz': 2500, 'agua': 500, 'internet': 800, 'sueldos': 15000, 'otros': 3000}
        total_mensual = sum(gastos_mensuales.values())
        total_anual = total_mensual * meses_transcurridos
        
        return {
            'mensual_estimado': total_mensual,
            'anual_acumulado': total_anual,
            'detalle': gastos_mensuales,
            'nota': 'Estimación. Configura tus gastos reales en Configuración.'
        }
    
    async def _calcular_termometro(self, year: int) -> Dict[str, Any]:
        serie_a = await self._get_serie_stats('A', year)
        gastos = await self._get_gastos_facturados(year)
        ingresos_a = serie_a['total']
        gastos_total = gastos['anual_acumulado']
        diferencia = ingresos_a - gastos_total
        cobertura = (ingresos_a / gastos_total) * 100 if gastos_total > 0 else 100
        
        if cobertura >= 110: estado, mensaje = 'VERDE', 'Excelente: Ingresos Serie A cubren gastos con margen'
        elif cobertura >= 100: estado, mensaje = 'AMARILLO', 'Cuidado: Ingresos Serie A apenas cubren gastos'
        else: estado, mensaje = 'ROJO', f'Alerta: Faltan ${abs(diferencia):,.2f} para cubrir gastos'
        
        return {'ingresos_a': ingresos_a, 'gastos': gastos_total, 'diferencia': diferencia, 'cobertura_pct': round(cobertura, 1), 'estado': estado, 'mensaje': mensaje}
    
    async def _check_resico_status(self, year: int) -> Dict[str, Any]:
        serie_a = await self._get_serie_stats('A', year)
        facturado = Decimal(str(serie_a['total']))
        restante = self.RESICO_LIMIT - facturado
        porcentaje = (facturado / self.RESICO_LIMIT) * 100
        
        if facturado >= self.RESICO_LIMIT: estado, mensaje = 'EXCEDIDO', 'Has superado el límite RESICO. Consulta a tu contador.'
        elif facturado >= self.RESICO_WARNING: estado, mensaje = 'PELIGRO', f'Alerta: Solo puedes facturar ${float(restante):,.2f} más este año'
        else: estado, mensaje = 'OK', f'Disponible para facturar: ${float(restante):,.2f}'
        
        return {'limite': float(self.RESICO_LIMIT), 'facturado': float(facturado), 'restante': float(restante), 'porcentaje': float(round(porcentaje, 2)), 'estado': estado, 'mensaje': mensaje}
    
    async def _get_pendientes_global(self) -> Dict[str, Any]:
        sql = """
            SELECT COUNT(*) as tickets, COALESCE(SUM(total), 0) as total, MIN(timestamp) as mas_antiguo
            FROM sales s LEFT JOIN sale_cfdi_relation scr ON s.id = scr.sale_id
            WHERE s.serie = 'B' AND scr.id IS NULL AND s.status != 'cancelled'
        """
        result = list(await self.core.db.execute_query(sql))
        if result and result[0]['tickets']:
            r = result[0]
            return {'tickets': r['tickets'], 'total': float(r['total'] or 0), 'mas_antiguo': r['mas_antiguo'], 'mensaje': f'{r["tickets"]} tickets pendientes de global (${float(r["total"] or 0):,.2f})'}
        return {'tickets': 0, 'total': 0, 'mas_antiguo': None, 'mensaje': 'Sin pendientes'}
    
    async def _generar_recomendaciones(self, year: int) -> List[str]:
        recomendaciones = []
        termometro = await self._calcular_termometro(year)
        resico = await self._check_resico_status(year)
        pendientes = await self._get_pendientes_global()
        
        if termometro['estado'] == 'ROJO': recomendaciones.append(f"⚠️ Necesitas facturar ${abs(termometro['diferencia']):,.2f} más en Serie A para cubrir tus gastos")
        if resico['estado'] == 'PELIGRO': recomendaciones.append(f"🚨 Estás cerca del límite RESICO. Considera usar más Serie B para efectivo")
        if pendientes['tickets'] > 50: recomendaciones.append(f"📋 Tienes {pendientes['tickets']} tickets en Serie B. Genera factura global pronto")
        if not recomendaciones: recomendaciones.append("✅ Tu situación fiscal está en orden. ¡Sigue así!")
        
        return recomendaciones
    
    async def get_smart_global_selection(self, max_amount: float = None) -> List[Dict]:
        sql = """
            SELECT s.id, s.folio_visible, s.timestamp, s.total, STRING_AGG(p.name, ', ') as productos
            FROM sales s LEFT JOIN sale_cfdi_relation scr ON s.id = scr.sale_id
            LEFT JOIN sale_items si ON s.id = si.sale_id LEFT JOIN products p ON si.product_id = p.id
            WHERE s.serie = 'B' AND scr.id IS NULL AND s.status != 'cancelled'
            GROUP BY s.id ORDER BY s.timestamp ASC LIMIT 100
        """
        result = list(await self.core.db.execute_query(sql))
        
        if max_amount:
            selected, acumulado = [], 0
            for sale in result:
                if acumulado + float(sale['total']) <= max_amount:
                    selected.append(dict(sale))
                    acumulado += float(sale['total'])
            return selected
        
        return [dict(r) for r in result]
