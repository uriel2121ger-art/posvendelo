"""
Discrepancy Monitor - Monitor de discrepancia fiscal personal
Art. 91 LISR
"""

from typing import Any, Dict, List
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class DiscrepancyMonitor:
    def __init__(self, db):
        self.db = db

    async def setup_table(self):
        try:
            await self.db.execute("""
                CREATE TABLE IF NOT EXISTS personal_expenses (
                    id BIGSERIAL PRIMARY KEY, expense_date TEXT NOT NULL, amount DECIMAL(15,2) NOT NULL,
                    category TEXT NOT NULL, payment_method TEXT NOT NULL, description TEXT,
                    is_visible_to_sat INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self.db.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON personal_expenses(expense_date)")
        except Exception as e:
            logger.error(f"Error creating table: {e}")

    async def register_expense(self, amount: float, category: str, payment_method: str,
                                description: str = None, is_visible: bool = True) -> Dict[str, Any]:
        try:
            await self.db.execute("""
                INSERT INTO personal_expenses (expense_date, amount, category, payment_method, description, is_visible_to_sat, created_at)
                VALUES (:dt, :amt, :cat, :pm, :desc, :vis, :ts)
            """, dt=datetime.now().strftime('%Y-%m-%d'), amt=amount, cat=category, pm=payment_method,
                desc=description, vis=1 if is_visible else 0, ts=datetime.now().isoformat())
            return {'success': True, 'amount': amount, 'category': category}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def get_discrepancy_analysis(self, year: int = None, month: int = None) -> Dict[str, Any]:
        year = year or datetime.now().year
        if month:
            date_filter = f"{year}-{month:02d}"
            period_type = 'month'
        else:
            date_filter = str(year)
            period_type = 'year'

        if period_type == 'month':
            ing = await self.db.fetchrow("SELECT COALESCE(SUM(total), 0) as total FROM sales WHERE serie = 'A' AND TO_CHAR(timestamp::timestamp, 'YYYY-MM') = :df AND status = 'completed'", df=date_filter)
            gast = await self.db.fetchrow("SELECT COALESCE(SUM(amount), 0) as total FROM personal_expenses WHERE TO_CHAR(expense_date::timestamp, 'YYYY-MM') = :df AND is_visible_to_sat = 1", df=date_filter)
        else:
            ing = await self.db.fetchrow("SELECT COALESCE(SUM(total), 0) as total FROM sales WHERE serie = 'A' AND EXTRACT(YEAR FROM timestamp::timestamp) = :df AND status = 'completed'", df=int(date_filter))
            gast = await self.db.fetchrow("SELECT COALESCE(SUM(amount), 0) as total FROM personal_expenses WHERE EXTRACT(YEAR FROM expense_date::timestamp) = :df AND is_visible_to_sat = 1", df=int(date_filter))

        total_ingresos = Decimal(str(ing['total'] or 0)) if ing else Decimal('0')
        total_gastos_visible = Decimal(str(gast['total'] or 0)) if gast else Decimal('0')

        try:
            if period_type == 'month':
                ext = await self.db.fetchrow("SELECT COALESCE(SUM(amount), 0) as total FROM cash_extractions WHERE TO_CHAR(extraction_date::timestamp, 'YYYY-MM') = :df", df=date_filter)
            else:
                ext = await self.db.fetchrow("SELECT COALESCE(SUM(amount), 0) as total FROM cash_extractions WHERE EXTRACT(YEAR FROM extraction_date::timestamp) = :df", df=int(date_filter))
            total_extracciones = Decimal(str(ext['total'] or 0)) if ext else Decimal('0')
        except Exception:
            total_extracciones = Decimal('0')

        ingresos_justificados = total_ingresos + total_extracciones
        discrepancia = total_gastos_visible - ingresos_justificados

        if discrepancia > 0:
            porcentaje_riesgo = (discrepancia / max(total_gastos_visible, Decimal('1'))) * 100
            if porcentaje_riesgo > 30: estado, semaforo = 'CRITICO', 'ROJO'
            elif porcentaje_riesgo > 15: estado, semaforo = 'ALERTA', 'AMARILLO'
            else: estado, semaforo = 'PRECAUCION', 'AMARILLO'
        else:
            estado, semaforo, porcentaje_riesgo = 'SANO', 'VERDE', 0

        return {
            'period': date_filter, 'period_type': period_type, 'ingresos_serie_a': round(float(total_ingresos), 2),
            'extracciones_documentadas': round(float(total_extracciones), 2), 'ingresos_justificados': round(float(ingresos_justificados), 2),
            'gastos_visibles_sat': round(float(total_gastos_visible), 2), 'discrepancia': round(float(discrepancia), 2),
            'porcentaje_riesgo': round(float(porcentaje_riesgo), 2), 'estado': estado, 'semaforo': semaforo
        }

    async def get_monthly_trend(self, year: int = None) -> List[Dict[str, Any]]:
        year = year or datetime.now().year
        months = []
        for m in range(1, 13):
            if datetime(year, m, 1) > datetime.now(): break
            a = await self.get_discrepancy_analysis(year, m)
            months.append({'month': m, 'ingresos': a['ingresos_justificados'], 'gastos': a['gastos_visibles_sat'], 'discrepancia': a['discrepancia'], 'semaforo': a['semaforo']})
        return months

    async def suggest_extraction_amount(self) -> Dict[str, Any]:
        a = await self.get_discrepancy_analysis()
        if a['discrepancia'] > 0:
            return {'recommend_extraction': True, 'amount': a['discrepancia'], 'urgency': 'ALTA' if a['estado'] == 'CRITICO' else 'MEDIA'}
        return {'recommend_extraction': False, 'balance': abs(a['discrepancia'])}

    async def get_expense_breakdown(self, year: int = None, month: int = None) -> Dict[str, Any]:
        year = year or datetime.now().year
        if month:
            result = await self.db.fetch("SELECT category, payment_method, COALESCE(SUM(amount), 0) as total, COUNT(*) as count FROM personal_expenses WHERE TO_CHAR(expense_date::timestamp, 'YYYY-MM') = :df GROUP BY category, payment_method", df=f"{year}-{month:02d}")
        else:
            result = await self.db.fetch("SELECT category, payment_method, COALESCE(SUM(amount), 0) as total, COUNT(*) as count FROM personal_expenses WHERE EXTRACT(YEAR FROM expense_date::timestamp) = :year GROUP BY category, payment_method", year=year)

        breakdown = {}
        for r in result:
            cat = r['category']
            if cat not in breakdown: breakdown[cat] = {'total': 0, 'by_method': {}}
            breakdown[cat]['total'] += round(float(r['total'] or 0), 2)
            breakdown[cat]['by_method'][r['payment_method']] = round(float(r['total'] or 0), 2)

        return {'period': f'{year}-{month:02d}' if month else str(year), 'by_category': breakdown, 'total': sum(c['total'] for c in breakdown.values())}
