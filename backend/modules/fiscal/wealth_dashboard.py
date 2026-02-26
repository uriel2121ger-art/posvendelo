"""
Wealth Dashboard - Riqueza real (solo admin)
Utilidad neta de bolsillo considerando todas las series
"""

from typing import Any, Dict, List
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class WealthDashboard:
    def __init__(self, db):
        self.db = db

    async def get_real_wealth(self, year: int = None, month: int = None) -> Dict[str, Any]:
        year = year or datetime.now().year
        if month:
            date_filter, period_type = f"{year}-{month:02d}", 'month'
        else:
            date_filter, period_type = str(year), 'year'

        ingresos = await self._get_total_income(date_filter, period_type)
        gastos = await self._get_operating_expenses(date_filter, period_type)
        impuestos = await self._calculate_taxes(ingresos, period_type)
        extracciones = await self._get_extractions(date_filter, period_type)

        utilidad_bruta = ingresos['total'] - gastos['total']
        utilidad_neta = utilidad_bruta - impuestos['total']
        disponible = utilidad_neta - extracciones['total']

        return {
            'period': date_filter, 'period_type': period_type, 'ingresos': ingresos,
            'gastos': gastos, 'impuestos': impuestos, 'extracciones': extracciones,
            'utilidad_bruta': round(float(utilidad_bruta), 2), 'utilidad_neta': round(float(utilidad_neta), 2),
            'disponible_retiro': round(float(disponible), 2),
            'ratio_utilidad': round((float(utilidad_neta) / float(ingresos['total'])) * 100, 2) if ingresos['total'] > 0 else 0
        }

    async def _get_total_income(self, date_filter: str, period_type: str) -> Dict[str, Any]:
        if period_type == 'month':
            result = await self.db.fetch("SELECT serie, COALESCE(SUM(total), 0) as total, COUNT(*) as transactions FROM sales WHERE TO_CHAR(timestamp::timestamp, 'YYYY-MM') = :df AND status = 'completed' GROUP BY serie", df=date_filter)
        else:
            result = await self.db.fetch("SELECT serie, COALESCE(SUM(total), 0) as total, COUNT(*) as transactions FROM sales WHERE EXTRACT(YEAR FROM timestamp::timestamp) = :df AND status = 'completed' GROUP BY serie", df=int(date_filter))

        by_serie = {}
        total = Decimal('0')
        for r in result:
            s = r['serie'] or 'A'
            amt = Decimal(str(r['total'] or 0))
            by_serie[s] = {'total': round(float(amt), 2), 'transactions': r['transactions']}
            total += amt
        return {'serie_a': by_serie.get('A', {'total': 0, 'transactions': 0}), 'serie_b': by_serie.get('B', {'total': 0, 'transactions': 0}), 'total': round(float(total), 2)}

    async def _get_operating_expenses(self, date_filter: str, period_type: str) -> Dict[str, Any]:
        if period_type == 'month':
            r = await self.db.fetchrow("SELECT COALESCE(SUM(total), 0) as total FROM sales WHERE TO_CHAR(timestamp::timestamp, 'YYYY-MM') = :df AND status = 'completed'", df=date_filter)
        else:
            r = await self.db.fetchrow("SELECT COALESCE(SUM(total), 0) as total FROM sales WHERE EXTRACT(YEAR FROM timestamp::timestamp) = :df AND status = 'completed'", df=int(date_filter))
        ventas = Decimal(str(r['total'] or 0)) if r else Decimal('0')
        costo_venta = ventas * Decimal('0.65')
        gastos_fijos = ventas * Decimal('0.10')
        return {'costo_venta': round(float(costo_venta), 2), 'gastos_fijos': round(float(gastos_fijos), 2), 'total': round(float(costo_venta + gastos_fijos), 2)}

    async def _calculate_taxes(self, ingresos: Dict, period_type: str) -> Dict[str, Any]:
        serie_a = Decimal(str(ingresos['serie_a']['total']))
        isr = serie_a * Decimal('0.015')
        iva_cobrado = serie_a * Decimal('0.16') / Decimal('1.16')
        iva_acreditable = iva_cobrado * Decimal('0.70')
        iva_neto = iva_cobrado - iva_acreditable
        return {'isr': round(float(isr), 2), 'iva_cobrado': round(float(iva_cobrado), 2), 'iva_acreditable': round(float(iva_acreditable), 2), 'iva_neto': round(float(iva_neto), 2), 'total': round(float(isr + iva_neto), 2)}

    async def _get_extractions(self, date_filter: str, period_type: str) -> Dict[str, Any]:
        try:
            if period_type == 'month':
                r = await self.db.fetchrow("SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count FROM cash_extractions WHERE TO_CHAR(extraction_date::timestamp, 'YYYY-MM') = :df", df=date_filter)
            else:
                r = await self.db.fetchrow("SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count FROM cash_extractions WHERE EXTRACT(YEAR FROM extraction_date::timestamp) = :df", df=int(date_filter))
            return {'total': round(float(r['total'] or 0), 2) if r else 0, 'count': (r['count'] or 0) if r else 0}
        except Exception:
            return {'total': 0, 'count': 0}

    async def get_monthly_trend(self, year: int = None) -> List[Dict[str, Any]]:
        year = year or datetime.now().year
        months = []
        for m in range(1, 13):
            if datetime(year, m, 1) > datetime.now(): break
            data = await self.get_real_wealth(year, m)
            months.append({'month': m, 'ingresos': data['ingresos']['total'], 'utilidad_neta': data['utilidad_neta'], 'disponible': data['disponible_retiro']})
        return months

    async def get_quick_summary(self) -> Dict[str, Any]:
        year = datetime.now().year
        monthly = await self.get_real_wealth(year, datetime.now().month)
        yearly = await self.get_real_wealth(year)
        return {
            'mes_actual': {'ingresos': monthly['ingresos']['total'], 'utilidad': monthly['utilidad_neta'], 'disponible': monthly['disponible_retiro']},
            'año_actual': {'ingresos': yearly['ingresos']['total'], 'utilidad': yearly['utilidad_neta'], 'disponible': yearly['disponible_retiro'], 'ratio': yearly['ratio_utilidad']},
            'timestamp': datetime.now().isoformat()
        }
