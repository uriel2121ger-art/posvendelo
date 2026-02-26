"""
Predictive Cash Extraction - IA para Retiro Suavizado
Optimiza flujo de retiros para evitar alertas bancarias
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import logging
import statistics
import random

logger = logging.getLogger(__name__)

class PredictiveExtraction:
    """
    IA de Retiro Suavizado.
    Analiza ventas Serie B y genera un plan de retiro distribuido.
    """
    
    # Límites de "normalidad" bancaria
    MAX_DAILY_CASH = 15000       # MXN
    MAX_WEEKLY_CASH = 50000      # MXN
    MAX_MONTHLY_CASH = 150000    # MXN
    ALERT_THRESHOLD = 50000      # MXN
    
    def __init__(self, db):
        self.db = db
    
    async def analyze_available(self) -> Dict[str, Any]:
        """Analiza efectivo disponible para retiro."""
        month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        
        row_b = await self.db.fetchrow("SELECT COALESCE(SUM(total), 0) as total FROM sales WHERE serie = 'B' AND timestamp >= :m_start AND status = 'completed'", m_start=month_start)
        total_serie_b = float(row_b['total'] or 0) if row_b else 0
        
        # In case cash_expenses doesn't exist, ignore softly
        try:
            row_exp = await self.db.fetchrow("SELECT COALESCE(SUM(amount), 0) as total FROM cash_expenses WHERE expense_date >= :m_start::date", m_start=month_start)
            total_expenses = float(row_exp['total'] or 0) if row_exp else 0
        except Exception:
            total_expenses = 0
            
        try:
            row_ext = await self.db.fetchrow("SELECT COALESCE(SUM(amount), 0) as total FROM cash_extractions WHERE extraction_date >= :m_start", m_start=month_start)
            total_extracted = float(row_ext['total'] or 0) if row_ext else 0
        except Exception:
            total_extracted = 0
            
        available = total_serie_b - total_expenses - total_extracted
        
        return {
            'serie_b_month': total_serie_b,
            'expenses_month': total_expenses,
            'extracted_month': total_extracted,
            'available': max(0, available),
            'remaining_monthly_limit': max(0, self.MAX_MONTHLY_CASH - total_extracted)
        }
    
    async def generate_extraction_plan(self, target_amount: float) -> Dict[str, Any]:
        """Genera un plan de extracción suavizado."""
        available = await self.analyze_available()
        
        if target_amount > available['available']:
            return {'success': False, 'error': f'Monto excede disponible (${available["available"]:,.0f})'}
        
        daily_amount = min(self.MAX_DAILY_CASH, target_amount)
        plan = []
        remaining = target_amount
        current_date = datetime.now()
        
        while remaining > 0:
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
            
            variance = daily_amount * 0.1
            amount = min(remaining, daily_amount + random.uniform(-variance, variance))
            amount = round(amount, -2)
            
            if amount <= 0: break
            
            plan.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'amount': amount,
                'method': await self._suggest_extraction_method(amount),
                'contract_type': 'donacion' if amount < 10000 else 'prestamo'
            })
            
            remaining -= amount
            current_date += timedelta(days=1)
        
        contracts = await self._prepare_contracts(plan)
        
        return {
            'success': True, 'target': target_amount, 'days': len(plan),
            'daily_average': target_amount / len(plan) if plan else 0,
            'plan': plan, 'contracts': contracts,
            'message': f'Plan generado. Promedio ${target_amount/len(plan):,.0f}/día'
        }
    
    async def _suggest_extraction_method(self, amount: float) -> str:
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
        except Exception:
            return [{'name': 'Cónyuge', 'relationship': 'spouse'}, {'name': 'Padre', 'relationship': 'parent'}]
    
    async def get_optimal_daily_amount(self) -> Dict[str, Any]:
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        try:
            daily_sales = await self.db.fetch("SELECT SUBSTRING(timestamp FROM 1 FOR 10) as day, COALESCE(SUM(total), 0) as total FROM sales WHERE serie = 'B' AND timestamp >= :thirty_days_ago AND status = 'completed' GROUP BY SUBSTRING(timestamp FROM 1 FOR 10)", thirty_days_ago=thirty_days_ago)
        except Exception:
            daily_sales = []
            
        if not daily_sales:
            return {'optimal_daily': self.MAX_DAILY_CASH / 2, 'basis': 'Sin datos históricos'}
        
        daily_totals = [float(d['total'] or 0) for d in daily_sales]
        avg_daily = statistics.mean(daily_totals) if daily_totals else 0
        optimal = min(avg_daily * 0.9, self.MAX_DAILY_CASH)
        
        return {
            'avg_daily_serie_b': avg_daily, 'optimal_daily': optimal, 'days_sampled': len(daily_sales),
            'recommendation': f'Retira ${optimal:,.0f}/día'
        }
