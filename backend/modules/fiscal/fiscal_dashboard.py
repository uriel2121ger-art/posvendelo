"""
Fiscal Dashboard - Inteligencia de Brecha Serie A vs B
"""

from typing import Any, Dict, List
from datetime import datetime
from decimal import Decimal
import logging

from ..shared.constants import RESICO_ANNUAL_LIMIT, money

logger = logging.getLogger(__name__)


class FiscalDashboard:
    RESICO_LIMIT = RESICO_ANNUAL_LIMIT
    RESICO_WARNING = Decimal('3200000.00')

    def __init__(self, db):
        self.db = db

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
            'serie_a': serie_a, 'serie_b': serie_b, 'gastos': gastos,
            'termometro': termometro, 'resico': resico,
            'pendientes_global': pendientes_global, 'recomendaciones': recomendaciones,
        }

    async def _get_serie_stats(self, serie: str, year: int) -> Dict[str, Any]:
        r = await self.db.fetchrow("""
            SELECT COUNT(*) as ventas, COALESCE(SUM(total), 0) as total, COALESCE(SUM(subtotal), 0) as subtotal, COALESCE(SUM(tax), 0) as impuestos
            FROM sales WHERE serie = :serie AND EXTRACT(YEAR FROM timestamp::timestamp) = :year AND status != 'cancelled'
        """, serie=serie, year=year)
        if r:
            return {'ventas': r['ventas'], 'total': money(r['total']), 'subtotal': money(r['subtotal']), 'impuestos': money(r['impuestos'])}
        return {'ventas': 0, 'total': 0, 'subtotal': 0, 'impuestos': 0}

    async def _get_gastos_facturados(self, year: int) -> Dict[str, Any]:
        meses = datetime.now().month
        gastos = {'renta': 8000, 'luz': 2500, 'agua': 500, 'internet': 800, 'sueldos': 15000, 'otros': 3000}
        total_m = sum(gastos.values())
        return {'mensual_estimado': total_m, 'anual_acumulado': total_m * meses, 'detalle': gastos, 'nota': 'Estimación.'}

    async def _calcular_termometro(self, year: int) -> Dict[str, Any]:
        serie_a = await self._get_serie_stats('A', year)
        gastos = await self._get_gastos_facturados(year)
        ingresos_a, gastos_total = serie_a['total'], gastos['anual_acumulado']
        diferencia = ingresos_a - gastos_total
        cobertura = (ingresos_a / gastos_total) * 100 if gastos_total > 0 else 100

        if cobertura >= 110: estado, mensaje = 'VERDE', 'Excelente'
        elif cobertura >= 100: estado, mensaje = 'AMARILLO', 'Cuidado'
        else: estado, mensaje = 'ROJO', f'Faltan ${abs(diferencia):,.2f}'

        return {'ingresos_a': ingresos_a, 'gastos': gastos_total, 'diferencia': diferencia, 'cobertura_pct': round(cobertura, 1), 'estado': estado, 'mensaje': mensaje}

    async def _check_resico_status(self, year: int) -> Dict[str, Any]:
        serie_a = await self._get_serie_stats('A', year)
        facturado = Decimal(str(serie_a['total']))
        restante = self.RESICO_LIMIT - facturado
        porcentaje = (facturado / self.RESICO_LIMIT) * 100

        if facturado >= self.RESICO_LIMIT: estado = 'EXCEDIDO'
        elif facturado >= self.RESICO_WARNING: estado = 'PELIGRO'
        else: estado = 'OK'

        return {'limite': money(self.RESICO_LIMIT), 'facturado': money(facturado), 'restante': money(restante), 'porcentaje': money(porcentaje), 'estado': estado}

    async def _get_pendientes_global(self) -> Dict[str, Any]:
        r = await self.db.fetchrow("""
            SELECT COUNT(*) as tickets, COALESCE(SUM(total), 0) as total, MIN(timestamp) as mas_antiguo
            FROM sales s LEFT JOIN sale_cfdi_relation scr ON s.id = scr.sale_id
            WHERE s.serie = 'B' AND scr.id IS NULL AND s.status != 'cancelled'
        """)
        if r and r['tickets']:
            return {'tickets': r['tickets'], 'total': money(r['total']), 'mas_antiguo': r['mas_antiguo']}
        return {'tickets': 0, 'total': 0, 'mas_antiguo': None}

    async def _generar_recomendaciones(self, year: int) -> List[str]:
        recs = []
        t = await self._calcular_termometro(year)
        res = await self._check_resico_status(year)
        pend = await self._get_pendientes_global()

        if t['estado'] == 'ROJO': recs.append(f"Facturar ${abs(t['diferencia']):,.2f} más en Serie A")
        if res['estado'] == 'PELIGRO': recs.append("Cerca del límite RESICO")
        if pend['tickets'] > 50: recs.append(f"{pend['tickets']} tickets pendientes de global")
        if not recs: recs.append("Situación fiscal en orden")
        return recs

    async def get_smart_global_selection(self, max_amount: float = None) -> List[Dict]:
        rows = await self.db.fetch("""
            SELECT s.id, s.folio_visible, s.timestamp, s.total, STRING_AGG(p.name, ', ') as productos
            FROM sales s LEFT JOIN sale_cfdi_relation scr ON s.id = scr.sale_id
            LEFT JOIN sale_items si ON s.id = si.sale_id LEFT JOIN products p ON si.product_id = p.id
            WHERE s.serie = 'B' AND scr.id IS NULL AND s.status != 'cancelled'
            GROUP BY s.id ORDER BY s.timestamp ASC LIMIT 100
        """)
        if max_amount:
            selected, acc = [], 0.0
            for s in rows:
                if acc + money(s['total']) <= max_amount:
                    selected.append(dict(s))
                    acc += money(s['total'])
            return selected
        return [dict(r) for r in rows]
