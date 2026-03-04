"""
Wealth Dashboard - Riqueza real (solo admin)
Utilidad neta de bolsillo considerando todas las series
"""

from typing import Any, Dict, List
from datetime import datetime
from decimal import Decimal
import logging

from modules.shared.constants import money

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

        utilidad_bruta = Decimal(str(ingresos['total'])) - Decimal(str(gastos['total']))
        utilidad_neta = utilidad_bruta - Decimal(str(impuestos['total']))
        disponible = utilidad_neta - Decimal(str(extracciones['total']))

        return {
            'period': date_filter, 'period_type': period_type, 'ingresos': ingresos,
            'gastos': gastos, 'impuestos': impuestos, 'extracciones': extracciones,
            'utilidad_bruta': money(utilidad_bruta), 'utilidad_neta': money(utilidad_neta),
            'disponible_retiro': money(disponible),
            'ratio_utilidad': money(utilidad_neta / Decimal(str(ingresos['total'])) * 100) if ingresos['total'] > 0 else 0
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
            by_serie[s] = {'total': money(amt), 'transactions': r['transactions']}
            total += amt
        return {'serie_a': by_serie.get('A', {'total': 0, 'transactions': 0}), 'serie_b': by_serie.get('B', {'total': 0, 'transactions': 0}), 'total': money(total)}

    async def _get_operating_expenses(self, date_filter: str, period_type: str) -> Dict[str, Any]:
        if period_type == 'month':
            r = await self.db.fetchrow("SELECT COALESCE(SUM(total), 0) as total FROM sales WHERE TO_CHAR(timestamp::timestamp, 'YYYY-MM') = :df AND status = 'completed'", df=date_filter)
        else:
            r = await self.db.fetchrow("SELECT COALESCE(SUM(total), 0) as total FROM sales WHERE EXTRACT(YEAR FROM timestamp::timestamp) = :df AND status = 'completed'", df=int(date_filter))
        ventas = Decimal(str(r['total'] or 0)) if r else Decimal('0')
        costo_venta = ventas * Decimal('0.65')
        gastos_fijos = ventas * Decimal('0.10')
        return {'costo_venta': money(costo_venta), 'gastos_fijos': money(gastos_fijos), 'total': money(costo_venta + gastos_fijos)}

    async def _calculate_taxes(self, ingresos: Dict, period_type: str) -> Dict[str, Any]:
        serie_a = Decimal(str(ingresos['serie_a']['total']))
        isr = serie_a * Decimal('0.015')
        iva_cobrado = serie_a * Decimal('0.16') / Decimal('1.16')
        iva_acreditable = iva_cobrado * Decimal('0.70')
        iva_neto = iva_cobrado - iva_acreditable
        return {'isr': money(isr), 'iva_cobrado': money(iva_cobrado), 'iva_acreditable': money(iva_acreditable), 'iva_neto': money(iva_neto), 'total': money(isr + iva_neto)}

    async def _get_extractions(self, date_filter: str, period_type: str) -> Dict[str, Any]:
        try:
            if period_type == 'month':
                r = await self.db.fetchrow("SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count FROM cash_extractions WHERE TO_CHAR(extraction_date::timestamp, 'YYYY-MM') = :df", df=date_filter)
            else:
                r = await self.db.fetchrow("SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count FROM cash_extractions WHERE EXTRACT(YEAR FROM extraction_date::timestamp) = :df", df=int(date_filter))
            return {'total': money(r['total']) if r else 0, 'count': (r['count'] or 0) if r else 0}
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
