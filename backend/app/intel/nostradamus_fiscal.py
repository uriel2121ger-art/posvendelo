from pathlib import Path

"""
Nostradamus Fiscal - IA Prescriptiva de Optimización Fiscal
Te dice QUÉ HACER mañana para pagar $0 de impuestos legalmente
"""

from typing import Any, Dict, List
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import sys

logger = logging.getLogger(__name__)

class NostradamusFiscal:
    """
    Sistema de IA Prescriptiva para optimización fiscal.
    
    No te dice "gastaste mucho".
    Te dice "mueve $45,000 de Serie B a Serie A HOY".
    """
    
    # Constantes fiscales
    IVA_RATE = 0.16
    ISR_RATE_RESICO = 0.0125  # 1.25% promedio RESICO
    RESICO_ANNUAL_LIMIT = 3_500_000
    
    def __init__(self, core):
        self.core = core
        self.prescriptions = []
    
    def analyze_and_prescribe(self) -> Dict[str, Any]:
        """
        Ejecuta análisis completo y genera prescripciones.
        """
        # SECURITY: No loguear análisis fiscal
        pass
        
        self.prescriptions = []
        
        # 1. Analizar balance A/B
        balance = self._get_ab_balance()
        
        # 2. Analizar deducciones vs ingresos
        deductions = self._get_deduction_status()
        
        # 3. Analizar capacidad RESICO
        resico = self._get_resico_status()
        
        # 4. Generar prescripciones
        self._generate_prescriptions(balance, deductions, resico)
        
        # 5. Calcular ahorro potencial
        savings = self._calculate_potential_savings()
        
        return {
            'analysis_date': datetime.now().isoformat(),
            'balance': balance,
            'deductions': deductions,
            'resico': resico,
            'prescriptions': self.prescriptions,
            'potential_savings': savings,
            'top_action': self.prescriptions[0] if self.prescriptions else None
        }
    
    def _get_ab_balance(self) -> Dict[str, Any]:
        """Obtiene balance entre Serie A y B del mes actual."""
        month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        
        try:
            # Ventas Serie A
            result_a = list(self.core.db.execute_query("""
                SELECT COALESCE(SUM(total), 0) as total, COUNT(*) as count
                FROM sales WHERE serie = 'A' AND timestamp::date >= %s
            """, (month_start,)))

            # Ventas Serie B
            result_b = list(self.core.db.execute_query("""
                SELECT COALESCE(SUM(total), 0) as total, COUNT(*) as count
                FROM sales WHERE serie = 'B' AND timestamp::date >= %s
            """, (month_start,)))
            
            total_a = float(result_a[0]['total'] or 0) if result_a else 0
            total_b = float(result_b[0]['total'] or 0) if result_b else 0
            total = total_a + total_b
            
            ratio_b = (total_b / total * 100) if total > 0 else 0
            
            return {
                'serie_a': total_a,
                'serie_b': total_b,
                'total': total,
                'ratio_b_percentage': round(ratio_b, 1),
                'status': 'excess_b' if ratio_b > 70 else 'balanced' if ratio_b > 30 else 'excess_a'
            }
            
        except Exception as e:
            logger.error(f"Error en balance A/B: {e}")
            return {'serie_a': 0, 'serie_b': 0, 'total': 0, 'ratio_b_percentage': 50, 'status': 'unknown'}
    
    def _get_deduction_status(self) -> Dict[str, Any]:
        """Analiza estado de deducciones fiscales."""
        month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        
        try:
            # Gastos deducibles (Serie A)
            expenses = list(self.core.db.execute_query("""
                SELECT COALESCE(SUM(amount), 0) as total
                FROM expenses WHERE serie = 'A' AND expense_date::date >= %s
            """, (month_start,)))
            
            # Compras con factura
            purchases = list(self.core.db.execute_query("""
                SELECT COALESCE(SUM(total), 0) as total
                FROM purchases WHERE has_invoice = 1 AND purchase_date::date >= %s
            """, (month_start,)))
            
            # Mermas documentadas
            shrinkage = list(self.core.db.execute_query("""
                SELECT COALESCE(SUM(value), 0) as total
                FROM shrinkage WHERE approved = 1 AND timestamp::date >= %s
            """, (month_start,)))
            
            total_deductions = (
                (float(expenses[0]['total'] or 0) if expenses else 0) +
                (float(purchases[0]['total'] or 0) if purchases else 0) +
                (float(shrinkage[0]['total'] or 0) if shrinkage else 0)
            )
            
            # Ingresos facturados
            income_a = list(self.core.db.execute_query("""
                SELECT COALESCE(SUM(total), 0) as total
                FROM sales WHERE serie = 'A' AND timestamp::date >= %s
            """, (month_start,)))

            total_income = float(income_a[0]['total'] or 0) if income_a else 0
            
            # Calcular base gravable
            taxable_base = max(0, total_income - total_deductions)
            
            # Excedente de deducciones (oportunidad)
            excess_deductions = total_deductions - total_income if total_deductions > total_income else 0
            
            return {
                'total_deductions': total_deductions,
                'total_income_a': total_income,
                'taxable_base': taxable_base,
                'excess_deductions': excess_deductions,
                'deduction_ratio': round((total_deductions / total_income * 100) if total_income > 0 else 0, 1),
                'has_opportunity': excess_deductions > 0
            }
            
        except Exception as e:
            logger.error(f"Error en deducciones: {e}")
            return {'total_deductions': 0, 'total_income_a': 0, 'taxable_base': 0, 'excess_deductions': 0}
    
    def _get_resico_status(self) -> Dict[str, Any]:
        """Analiza capacidad restante RESICO."""
        year_start = datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d')
        
        try:
            # Por RFC
            rfcs = list(self.core.db.execute_query("""
                SELECT rfc, COALESCE(SUM(total), 0) as total
                FROM invoices WHERE CAST(fecha AS DATE) >= %s
                GROUP BY rfc
            """, (year_start,)))
            
            rfc_data = []
            total_invoiced = 0
            
            for rfc in rfcs:
                amount = float(rfc['total'])
                total_invoiced += amount
                remaining = self.RESICO_ANNUAL_LIMIT - amount
                percentage = (amount / self.RESICO_ANNUAL_LIMIT) * 100
                
                rfc_data.append({
                    'rfc': rfc['rfc'],
                    'invoiced': amount,
                    'remaining': remaining,
                    'percentage': round(percentage, 1)
                })
            
            # RFC con más espacio
            best_rfc = max(rfc_data, key=lambda x: x['remaining']) if rfc_data else None
            
            return {
                'rfcs': rfc_data,
                'total_invoiced': total_invoiced,
                'total_remaining': sum(r['remaining'] for r in rfc_data) if rfc_data else self.RESICO_ANNUAL_LIMIT,
                'best_rfc': best_rfc,
                'days_remaining_year': (datetime.now().replace(month=12, day=31) - datetime.now()).days
            }
            
        except Exception as e:
            logger.error(f"Error en RESICO: {e}")
            return {'rfcs': [], 'total_remaining': self.RESICO_ANNUAL_LIMIT}
    
    def _generate_prescriptions(self, balance: Dict, deductions: Dict, resico: Dict):
        """Genera prescripciones accionables."""
        today = datetime.now().strftime('%A')
        
        # PRESCRIPCIÓN 1: Aprovechar excedente de deducciones
        if deductions.get('has_opportunity') and deductions['excess_deductions'] > 10000:
            excess = deductions['excess_deductions']
            optimal_move = min(excess, balance.get('serie_b', 0))
            tax_saving = optimal_move * self.ISR_RATE_RESICO
            
            self.prescriptions.append({
                'priority': 'high',
                'type': 'move_b_to_a',
                'title': 'Optimizar Base Gravable',
                'message': f"Mano, hoy es {today}. Tienes ${excess:,.0f} de excedente en deducciones. "
                          f"Mueve las próximas ventas de ${optimal_move:,.0f} de Serie B a Serie A. "
                          f"Tu base gravable baja a $0.",
                'action': f"Mover ${optimal_move:,.0f} de B → A",
                'tax_saving': tax_saving,
                'urgency': 'today'
            })
        
        # PRESCRIPCIÓN 2: Equilibrar ratio A/B
        if balance.get('ratio_b_percentage', 0) > 75:
            amount_to_move = balance['serie_b'] * 0.2  # Mover 20%
            
            self.prescriptions.append({
                'priority': 'medium',
                'type': 'balance_ratio',
                'title': 'Equilibrar Flujo de Series',
                'message': f"El {balance['ratio_b_percentage']}% de tus ventas son Serie B. "
                          f"Mueve ${amount_to_move:,.0f} a Serie A para mejor balance fiscal.",
                'action': f"Facturar ${amount_to_move:,.0f} adicionales",
                'tax_saving': amount_to_move * 0.05,  # Estimado
                'urgency': 'this_week'
            })
        
        # PRESCRIPCIÓN 3: Rotar RFC
        if resico.get('best_rfc'):
            best = resico['best_rfc']
            if best['percentage'] < 50:
                current_heavy = max(resico['rfcs'], key=lambda x: x['percentage'])
                
                if current_heavy['percentage'] > 70:
                    self.prescriptions.append({
                        'priority': 'medium',
                        'type': 'rotate_rfc',
                        'title': 'Rotar Emisor Fiscal',
                        'message': f"RFC {current_heavy['rfc'][:4]}*** está al {current_heavy['percentage']}%. "
                                  f"Cambia a {best['rfc'][:4]}*** que solo está al {best['percentage']}%.",
                        'action': f"Cambiar a RFC {best['rfc'][:4]}***",
                        'tax_saving': 0,
                        'urgency': 'today'
                    })
        
        # PRESCRIPCIÓN 4: Generar gastos deducibles
        if deductions.get('taxable_base', 0) > 50000:
            gap = deductions['taxable_base']
            
            self.prescriptions.append({
                'priority': 'low',
                'type': 'generate_expenses',
                'title': 'Generar Gastos Deducibles',
                'message': f"Tu base gravable es ${gap:,.0f}. "
                          f"Si generas ${gap:,.0f} en gastos deducibles, pagas $0 de ISR.",
                'action': "Comprar inventario con factura o registrar gastos",
                'tax_saving': gap * self.ISR_RATE_RESICO,
                'urgency': 'before_month_end'
            })
    
    def _calculate_potential_savings(self) -> Dict[str, Any]:
        """Calcula ahorro potencial si sigues las prescripciones."""
        total_saving = sum(p.get('tax_saving', 0) for p in self.prescriptions)
        
        return {
            'total_tax_saving': total_saving,
            'monthly_projection': total_saving * 12,
            'message': f"Si sigues todas las recomendaciones, ahorras ${total_saving:,.0f} este mes"
        }
    
    def get_daily_prescription(self) -> Dict[str, Any]:
        """
        Genera la prescripción del día para notificación push.
        """
        result = self.analyze_and_prescribe()
        
        if result['top_action']:
            action = result['top_action']
            return {
                'has_action': True,
                'title': f"🔮 {action['title']}",
                'message': action['message'],
                'action_button': action['action'],
                'saving': action.get('tax_saving', 0)
            }
        
        return {
            'has_action': False,
            'title': '✅ Fiscalidad Óptima',
            'message': 'No hay acciones pendientes hoy'
        }

# Función para cron job diario
def run_daily_prescription(core):
    """Ejecutar cada mañana para generar notificación."""
    nostradamus = NostradamusFiscal(core)
    return nostradamus.get_daily_prescription()
