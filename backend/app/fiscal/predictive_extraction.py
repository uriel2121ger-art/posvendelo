from pathlib import Path

"""
Predictive Cash Extraction - IA para Retiro Suavizado
Optimiza flujo de retiros para evitar alertas bancarias
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import statistics
import sys

logger = logging.getLogger(__name__)

class PredictiveExtraction:
    """
    IA de Retiro Suavizado.
    
    Analiza ventas Serie B y genera un plan de retiro
    distribuido en el tiempo para evitar alertas.
    
    Características:
    - Suavizado de flujo (no picos)
    - Generación automática de contratos de donación
    - Respeta límites de normalidad bancaria
    """
    
    # Límites de "normalidad" bancaria
    MAX_DAILY_CASH = 15000       # MXN - Retiro diario máximo
    MAX_WEEKLY_CASH = 50000      # MXN - Retiro semanal
    MAX_MONTHLY_CASH = 150000    # MXN - Retiro mensual
    ALERT_THRESHOLD = 50000      # MXN - Umbral de reporte bancario
    
    # Fracciones para donaciones (Art. 93 LISR)
    DONATION_ANNUAL_LIMIT = 300000  # Por persona relacionada
    
    def __init__(self, core):
        self.core = core
    
    def analyze_available(self) -> Dict[str, Any]:
        """Analiza efectivo disponible para retiro."""
        # Obtener ventas Serie B del mes
        month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        
        serie_b = list(self.core.db.execute_query("""
            SELECT COALESCE(SUM(total), 0) as total
            FROM sales
            WHERE serie = 'B' AND timestamp::date >= %s
        """, (month_start,)))
        
        total_serie_b = float(serie_b[0]['total'] or 0) if serie_b else 0
        
        # Gastos en efectivo ya registrados
        expenses = list(self.core.db.execute_query("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM cash_expenses
            WHERE expense_date::date >= %s
        """, (month_start,)))
        
        total_expenses = float(expenses[0]['total'] or 0) if expenses else 0
        
        # Extracciones ya hechas
        extractions = list(self.core.db.execute_query("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM cash_extractions
            WHERE extraction_date::date >= %s
        """, (month_start,)))
        
        total_extracted = float(extractions[0]['total'] or 0) if extractions else 0
        
        # Disponible
        available = total_serie_b - total_expenses - total_extracted
        
        return {
            'serie_b_month': total_serie_b,
            'expenses_month': total_expenses,
            'extracted_month': total_extracted,
            'available': max(0, available),
            'remaining_monthly_limit': max(0, self.MAX_MONTHLY_CASH - total_extracted)
        }
    
    def generate_extraction_plan(self, target_amount: float) -> Dict[str, Any]:
        """
        Genera un plan de extracción suavizado.
        
        En lugar de retirar $200k de golpe, distribuye en días.
        """
        available = self.analyze_available()
        
        if target_amount > available['available']:
            return {
                'success': False,
                'error': f'Monto excede disponible (${available["available"]:,.0f})'
            }
        
        # Calcular días necesarios
        daily_amount = min(self.MAX_DAILY_CASH, target_amount)
        days_needed = int(target_amount / daily_amount) + 1
        
        # Generar plan día por día
        plan = []
        remaining = target_amount
        current_date = datetime.now()
        
        while remaining > 0:
            # Saltar fines de semana (más sospechoso)
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
            
            # Variar montos para no ser predecible
            variance = daily_amount * 0.1  # ±10%
            import random
            amount = min(remaining, daily_amount + random.uniform(-variance, variance))
            amount = round(amount, -2)  # Redondear a centenas
            
            if amount <= 0:
                break
            
            plan.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'amount': amount,
                'method': self._suggest_extraction_method(amount),
                'contract_type': 'donacion' if amount < 10000 else 'prestamo'
            })
            
            remaining -= amount
            current_date += timedelta(days=1)
        
        # Preparar contratos
        contracts = self._prepare_contracts(plan)
        
        return {
            'success': True,
            'target': target_amount,
            'days': len(plan),
            'daily_average': target_amount / len(plan) if plan else 0,
            'plan': plan,
            'contracts': contracts,
            'message': f'Plan de {len(plan)} días generado. Retiro promedio de ${target_amount/len(plan):,.0f}/día'
        }
    
    def _suggest_extraction_method(self, amount: float) -> str:
        """Sugiere método de extracción según monto."""
        if amount < 5000:
            return 'Gasto menor (sin documentar)'
        elif amount < 15000:
            return 'Donación familiar'
        elif amount < 50000:
            return 'Préstamo familiar'
        else:
            return 'Préstamo con pagaré formal'
    
    def _prepare_contracts(self, plan: List[Dict]) -> List[Dict]:
        """Prepara contratos para el plan de extracción."""
        contracts = []
        
        # Agrupar por tipo de contrato
        donations = [p for p in plan if p['contract_type'] == 'donacion']
        loans = [p for p in plan if p['contract_type'] == 'prestamo']
        
        # Para donaciones, usar diferentes personas relacionadas
        related_persons = self._get_related_persons()
        
        for i, d in enumerate(donations):
            person = related_persons[i % len(related_persons)] if related_persons else {'name': 'Familiar'}
            contracts.append({
                'type': 'donacion',
                'date': d['date'],
                'amount': d['amount'],
                'recipient': person.get('name', 'Familiar'),
                'reference': f'Art. 93 Fr. XXIII LISR'
            })
        
        # Para préstamos, generar pagaré
        for l in loans:
            contracts.append({
                'type': 'prestamo',
                'date': l['date'],
                'amount': l['amount'],
                'term_months': 12,
                'interest_rate': 0,  # Sin intereses (familiar)
                'reference': 'Préstamo entre particulares'
            })
        
        return contracts
    
    def _get_related_persons(self) -> List[Dict]:
        """Obtiene personas relacionadas para donaciones."""
        try:
            persons = list(self.core.db.execute_query("""
                SELECT name, relationship, annual_limit
                FROM related_persons
                WHERE status = 'active'
            """))
            return [dict(p) for p in persons]
        except Exception:
            return [
                {'name': 'Cónyuge', 'relationship': 'spouse'},
                {'name': 'Padre', 'relationship': 'parent'},
                {'name': 'Madre', 'relationship': 'parent'},
            ]
    
    def get_optimal_daily_amount(self) -> Dict[str, Any]:
        """
        Calcula el monto óptimo de retiro diario.
        
        Basado en:
        - Ventas promedio diarias Serie B
        - Límites bancarios
        - Patrones históricos
        """
        # Promedio diario de ventas B últimos 30 días
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        daily_sales = list(self.core.db.execute_query("""
            SELECT timestamp::date as day, COALESCE(SUM(total), 0) as total
            FROM sales
            WHERE serie = 'B' AND timestamp::date >= %s
            GROUP BY timestamp::date
        """, (thirty_days_ago,)))
        
        if not daily_sales:
            return {
                'optimal_daily': self.MAX_DAILY_CASH / 2,
                'basis': 'Sin datos históricos'
            }
        
        daily_totals = [float(d['total'] or 0) for d in daily_sales]
        avg_daily = statistics.mean(daily_totals) if daily_totals else 0
        
        # El óptimo es no acumular: retirar aproximadamente lo que generas
        optimal = min(avg_daily * 0.9, self.MAX_DAILY_CASH)
        
        return {
            'avg_daily_serie_b': avg_daily,
            'optimal_daily': optimal,
            'days_sampled': len(daily_sales),
            'recommendation': f'Retira ${optimal:,.0f}/día para mantener flujo constante'
        }
    
    def simulate_extraction(self, amount: float, 
                           days: int = None) -> Dict[str, Any]:
        """
        Simula una extracción antes de ejecutarla.
        
        Muestra cómo se verá el flujo bancario.
        """
        if days is None:
            days = int(amount / self.MAX_DAILY_CASH) + 1
        
        daily = amount / days
        
        # Verificar si genera alertas
        alerts = []
        
        if daily > self.ALERT_THRESHOLD:
            alerts.append(f'⚠️ Retiro diario (${daily:,.0f}) excede umbral de reporte')
        
        if amount > self.MAX_MONTHLY_CASH:
            alerts.append(f'⚠️ Total mensual excede límite recomendado')
        
        # Calcular riesgo
        risk_score = 0
        if daily > 10000:
            risk_score += 2
        if days < 5:
            risk_score += 3
        if amount > 100000:
            risk_score += 2
        
        risk_level = 'BAJO' if risk_score < 3 else 'MEDIO' if risk_score < 5 else 'ALTO'
        
        return {
            'amount': amount,
            'days': days,
            'daily_average': daily,
            'alerts': alerts,
            'risk_score': risk_score,
            'risk_level': risk_level,
            'recommendation': 'Proceder' if risk_level == 'BAJO' else 'Extender período' if risk_level == 'MEDIO' else 'Reducir monto o usar crypto'
        }

def get_extraction_recommendation(core) -> Dict:
    """Obtiene recomendación de extracción basada en estado actual."""
    pe = PredictiveExtraction(core)
    available = pe.analyze_available()
    optimal = pe.get_optimal_daily_amount()
    
    return {
        'available': available['available'],
        'optimal_daily': optimal['optimal_daily'],
        'recommendation': optimal['recommendation']
    }
