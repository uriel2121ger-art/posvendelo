"""
Predictive Cash Extraction - IA para Retiro Suavizado
Optimiza flujo de retiros para evitar alertas bancarias
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import logging
import statistics
import random

from modules.shared.constants import money

logger = logging.getLogger(__name__)

class PredictiveExtraction:
    """
    IA de Retiro Suavizado.
    Analiza ventas Serie B y genera un plan de retiro distribuido.
    """
    
    # Límites de "normalidad" bancaria
    MAX_DAILY_CASH = Decimal('15000')
    MAX_WEEKLY_CASH = Decimal('50000')
    MAX_MONTHLY_CASH = Decimal('150000')
    ALERT_THRESHOLD = Decimal('50000')
    
    def __init__(self, db):
        self.db = db
    
    async def analyze_available(self) -> Dict[str, Any]:
        """Analiza efectivo disponible para retiro."""
        month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        Q = Decimal('0.01')

        row_b = await self.db.fetchrow("SELECT COALESCE(SUM(total), 0) as total FROM sales WHERE serie = 'B' AND timestamp >= :m_start AND status = 'completed'", m_start=month_start)
        total_serie_b = Decimal(str(row_b['total'] or 0)).quantize(Q, rounding=ROUND_HALF_UP) if row_b else Decimal('0')

        try:
            row_exp = await self.db.fetchrow("SELECT COALESCE(SUM(amount), 0) as total FROM cash_expenses WHERE expense_date >= :m_start::date", m_start=month_start)
            total_expenses = Decimal(str(row_exp['total'] or 0)).quantize(Q, rounding=ROUND_HALF_UP) if row_exp else Decimal('0')
        except Exception as e:
            logger.warning("cash_expenses table not available: %s", e)
            total_expenses = Decimal('0')

        try:
            row_ext = await self.db.fetchrow("SELECT COALESCE(SUM(amount), 0) as total FROM cash_extractions WHERE extraction_date >= :m_start", m_start=month_start)
            total_extracted = Decimal(str(row_ext['total'] or 0)).quantize(Q, rounding=ROUND_HALF_UP) if row_ext else Decimal('0')
        except Exception as e:
            logger.warning("cash_extractions table not available: %s", e)
            total_extracted = Decimal('0')

        available = total_serie_b - total_expenses - total_extracted

        return {
            'serie_b_month': money(total_serie_b),
            'expenses_month': money(total_expenses),
            'extracted_month': money(total_extracted),
            'available': money(max(Decimal('0'), available)),
            'remaining_monthly_limit': money(max(Decimal('0'), self.MAX_MONTHLY_CASH - total_extracted))
        }
    
    async def generate_extraction_plan(self, target_amount: float) -> Dict[str, Any]:
        """Genera un plan de extracción suavizado."""
        available = await self.analyze_available()
        target = Decimal(str(target_amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if target > Decimal(str(available['available'])):
            return {'success': False, 'error': f'Monto excede disponible (${available["available"]:,.0f})'}

        daily_amount = min(self.MAX_DAILY_CASH, target)
        plan = []
        remaining = target
        current_date = datetime.now()

        while remaining > 0:
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            variance = daily_amount * Decimal('0.1')
            rand_offset = Decimal(str(random.uniform(float(-variance), float(variance)))).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            amount = min(remaining, daily_amount + rand_offset)
            # Round to nearest 100
            amount = (amount / 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * 100

            if amount <= 0: break

            plan.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'amount': money(amount),
                'method': await self._suggest_extraction_method(amount),
                'contract_type': 'donacion' if amount < 10000 else 'prestamo'
            })

            remaining -= amount
            current_date += timedelta(days=1)

        contracts = await self._prepare_contracts(plan)

        return {
            'success': True, 'target': money(target), 'days': len(plan),
            'daily_average': money(target / len(plan)) if plan else 0,
            'plan': plan, 'contracts': contracts,
            'message': f'Plan generado. Promedio ${money(target/len(plan)):,.0f}/día' if plan else 'Plan vacío'
        }
    
    async def _suggest_extraction_method(self, amount: Decimal) -> str:
        if amount < 5000: return 'Gasto menor (sin documentar)'
        elif amount < 15000: return 'Donación familiar'
        elif amount < 50000: return 'Préstamo familiar'
        return 'Préstamo con pagaré formal'
    
    async def _prepare_contracts(self, plan: List[Dict]) -> List[Dict]:
        contracts = []
        related_persons = await self._get_related_persons()
        donations = [p for p in plan if p['contract_type'] == 'donacion']
        loans = [p for p in plan if p['contract_type'] == 'prestamo']
        
        for i, d in enumerate(donations):
            person = related_persons[i % len(related_persons)] if related_persons else {'name': 'Familiar'}
            contracts.append({'type': 'donacion', 'date': d['date'], 'amount': d['amount'], 'recipient': person.get('name', 'Familiar'), 'reference': 'Art. 93 Fr. XXIII LISR'})
            
        for l in loans:
            contracts.append({'type': 'prestamo', 'date': l['date'], 'amount': l['amount'], 'term_months': 12, 'interest_rate': 0, 'reference': 'Préstamo entre particulares'})
        return contracts
    
    async def _get_related_persons(self) -> List[Dict]:
        try:
            rows = await self.db.fetch("SELECT name, parentesco as relationship FROM related_persons WHERE is_active = 1")
            return [dict(p) for p in rows]
        except Exception as e:
            logger.warning("related_persons table not available: %s", e)
            return [{'name': 'Cónyuge', 'relationship': 'spouse'}, {'name': 'Padre', 'relationship': 'parent'}]
    
    async def get_optimal_daily_amount(self) -> Dict[str, Any]:
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        Q = Decimal('0.01')

        try:
            daily_sales = await self.db.fetch("SELECT SUBSTRING(timestamp FROM 1 FOR 10) as day, COALESCE(SUM(total), 0) as total FROM sales WHERE serie = 'B' AND timestamp >= :thirty_days_ago AND status = 'completed' GROUP BY SUBSTRING(timestamp FROM 1 FOR 10)", thirty_days_ago=thirty_days_ago)
        except Exception as e:
            logger.warning("Failed to fetch daily sales for optimal amount: %s", e)
            daily_sales = []

        if not daily_sales:
            half = (self.MAX_DAILY_CASH / 2).quantize(Q, rounding=ROUND_HALF_UP)
            return {'optimal_daily': money(half), 'basis': 'Sin datos históricos'}

        daily_totals = [Decimal(str(d['total'] or 0)).quantize(Q, rounding=ROUND_HALF_UP) for d in daily_sales]
        avg_daily = sum(daily_totals) / len(daily_totals)
        optimal = min(avg_daily * Decimal('0.9'), self.MAX_DAILY_CASH).quantize(Q, rounding=ROUND_HALF_UP)

        return {
            'avg_daily_serie_b': money(avg_daily),
            'optimal_daily': money(optimal),
            'days_sampled': len(daily_sales),
            'recommendation': f'Retira ${money(optimal):,.0f}/día'
        }
