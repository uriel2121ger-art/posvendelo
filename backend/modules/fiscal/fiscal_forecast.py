"""
Nostradamus Fiscal - IA Prescriptiva de Optimización Fiscal
El Orquestador Maestro (The Ticket Shaper).
Analiza la posición fiscal y ejecuta activamente las facturas globales cruzadas 
necesarias para mantener el régimen RESICO balanceado y pagar el mínimo ISR legal.
"""

from typing import Any, Dict, List
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class NostradamusFiscal:
    """
    Sistema de IA Prescriptiva para optimización fiscal.
    Actúa como Orquestador Maestro del Shaper.
    """
    
    # Constantes fiscales
    IVA_RATE = 0.16
    ISR_RATE_RESICO = 0.0125  # 1.25% promedio RESICO
    RESICO_ANNUAL_LIMIT = 3_500_000
    
    def __init__(self, db):
        self.db = db
        self.prescriptions = []
    
    async def analyze_and_prescribe(self) -> Dict[str, Any]:
        """
        Ejecuta análisis completo y genera prescripciones.
        """
        self.prescriptions = []
        
        # 1. Analizar balance A/B
        balance = await self._get_ab_balance()
        
        # 2. Analizar deducciones vs ingresos
        deductions = await self._get_deduction_status()
        
        # 3. Analizar capacidad RESICO
        resico = await self._get_resico_status()
        
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
    
    async def _get_ab_balance(self) -> Dict[str, Any]:
        """Obtiene balance entre Serie A y B del mes actual."""
        month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        
        try:
            result_a = await self.db.fetch(
                "SELECT COALESCE(SUM(total), 0) as total, COUNT(*) as count FROM sales WHERE serie = 'A' AND timestamp::date >= :ms",
                {"ms": month_start}
            )
            result_b = await self.db.fetch(
                "SELECT COALESCE(SUM(total), 0) as total, COUNT(*) as count FROM sales WHERE serie = 'B' AND timestamp::date >= :ms",
                {"ms": month_start}
            )
            
            total_a = round(float(result_a[0]['total'] or 0), 2) if result_a else 0
            total_b = round(float(result_b[0]['total'] or 0), 2) if result_b else 0
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
            logger.error(f"Error en balance A/B: {e}", exc_info=True)
            return {'serie_a': 0, 'serie_b': 0, 'total': 0, 'ratio_b_percentage': 50, 'status': 'unknown'}
    
    async def _get_deduction_status(self) -> Dict[str, Any]:
        """Analiza estado de deducciones fiscales."""
        month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        
        try:
            # Gastos deducibles
            expenses = await self.db.fetch(
                "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE serie = 'A' AND expense_date::date >= :ms",
                {"ms": month_start}
            )
            
            purchases = await self.db.fetch(
                "SELECT COALESCE(SUM(total), 0) as total FROM purchases WHERE has_invoice = 1 AND purchase_date::date >= :ms",
                {"ms": month_start}
            )
            
            shrinkage = await self.db.fetch(
                "SELECT COALESCE(SUM(value), 0) as total FROM shrinkage WHERE approved = 1 AND timestamp::date >= :ms",
                {"ms": month_start}
            )
            
            total_deductions = (
                (round(float(expenses[0]['total'] or 0), 2) if expenses else 0) +
                (round(float(purchases[0]['total'] or 0), 2) if purchases else 0) +
                (round(float(shrinkage[0]['total'] or 0), 2) if shrinkage else 0)
            )
            
            income_a = await self.db.fetch(
                "SELECT COALESCE(SUM(total), 0) as total FROM sales WHERE serie = 'A' AND timestamp::date >= :ms",
                {"ms": month_start}
            )
            total_income = round(float(income_a[0]['total'] or 0), 2) if income_a else 0
            
            taxable_base = max(0, total_income - total_deductions)
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
    
    async def _get_resico_status(self) -> Dict[str, Any]:
        """Analiza capacidad restante RESICO integrando MultiEmitterManager si es posible."""
        try:
            from modules.fiscal.multi_emitter import MultiEmitterManager
            mgr = MultiEmitterManager(self.db)
            emitters = await mgr.list_emitters()
            rfc_data = []
            total_invoiced = 0

            for emp in emitters:
                amount = round(float(emp['current_resico_amount']), 2)
                total_invoiced += amount
                remaining = self.RESICO_ANNUAL_LIMIT - amount
                percentage = (amount / self.RESICO_ANNUAL_LIMIT) * 100
                
                rfc_data.append({
                    'rfc': emp['rfc'],
                    'invoiced': amount,
                    'remaining': remaining,
                    'percentage': round(percentage, 1),
                })
            
            best_rfc = max(rfc_data, key=lambda x: x['remaining']) if rfc_data else None
            
            return {
                'rfcs': rfc_data,
                'total_invoiced': total_invoiced,
                'total_remaining': sum(r['remaining'] for r in rfc_data) if rfc_data else self.RESICO_ANNUAL_LIMIT,
                'best_rfc': best_rfc,
                'days_remaining_year': (datetime.now().replace(month=12, day=31) - datetime.now()).days
            }
        except Exception as e:
            logger.error(f"Error en RESICO: {e}", exc_info=True)
            return {'rfcs': [], 'total_remaining': self.RESICO_ANNUAL_LIMIT}
    
    def _generate_prescriptions(self, balance: Dict, deductions: Dict, resico: Dict):
        """Genera prescripciones accionables."""
        today = datetime.now().strftime('%A')
        
        # PRESCRIPCIÓN 1: Aprovechar excedente de deducciones (Optimización Automática)
        if deductions.get('has_opportunity') and deductions['excess_deductions'] > 500:
            excess = deductions['excess_deductions']
            optimal_move = min(excess, balance.get('serie_b', 0))
            if optimal_move > 0:
                tax_saving = optimal_move * self.ISR_RATE_RESICO
                self.prescriptions.append({
                    'priority': 'high',
                    'type': 'move_b_to_a',
                    'title': 'Optimizar Base Gravable (Facturar Serie B Pendiente)',
                    'message': f"Tienes ${excess:,.0f} MXN de exceso en deducciones de Serie A. "
                            f"Se recomienda mover automáticamente (Factura Global) ${optimal_move:,.0f} MXN de Serie B a A.",
                    'action': f"Facturar Global ${optimal_move:,.0f} B→A",
                    'tax_saving': tax_saving,
                    'urgency': 'today'
                })
    
    def _calculate_potential_savings(self) -> Dict[str, Any]:
        """Calcula ahorro potencial si sigues las prescripciones."""
        total_saving = sum(p.get('tax_saving', 0) for p in self.prescriptions)
        return {
            'total_tax_saving': total_saving,
            'monthly_projection': total_saving * 12,
            'message': f"Ahorras ${total_saving:,.0f} de forma automatizada."
        }
    
    async def get_daily_prescription(self) -> Dict[str, Any]:
        """Genera la prescripción del día para notificación push."""
        result = await self.analyze_and_prescribe()
        if result.get('top_action'):
            action = result['top_action']
            return {
                'has_action': True,
                'title': f"🔮 {action['title']}",
                'message': action['message'],
                'action_button': action['action'],
                'saving': action.get('tax_saving', 0)
            }
        return {'has_action': False, 'title': '✅ Fiscalidad Óptima', 'message': 'Operaciones blindadas'}

    async def execute_daily_strategy(self) -> Dict[str, Any]:
        """
        [ORCHESTRATOR ENTRY POINT]
        Ejecuta de forma autónoma la prescripción de alta prioridad, moviendo 
        tickets elegidos por CerebroContable hacia GlobalInvoicing apoyado por MultiEmitter.
        """
        logger.info("Iniciando Autonomous Ticket Shaper Orchestrator...")
        analysis = await self.analyze_and_prescribe()
        
        if not analysis['prescriptions']:
            return {"status": "skipped", "reason": "No optimal prescriptions for today."}
        
        top_action = analysis['prescriptions'][0]
        
        # Acciones automáticas soportadas por el Shaper:
        if top_action['type'] == 'move_b_to_a' and top_action['priority'] == 'high':
            logger.info("Ejecutando prescripción: move_b_to_a")
            
            # 1. Obtener la selección óptima de CerebroContable
            from modules.fiscal.accounting_engine import CerebroContable
            from modules.fiscal.global_invoicing import GlobalInvoicingService
            
            cerebro = CerebroContable(self.db)
            sale_ids = await cerebro.get_optimal_global_selection()
            
            if not sale_ids:
                return {"status": "skipped", "reason": "CerebroContable no pudo identificar tickets óptimos."}
                
            # 2. Generar y procesar la factura global (esto desencadena internamente a MultiEmitterManager)
            # Utilizamos las fechas del mes actual para la factura global
            start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            end_date = datetime.now().strftime('%Y-%m-%d')
            
            shaper = GlobalInvoicingService(self.db)
            result = await shaper.generate_global_cfdi_from_selection(sale_ids, start_date, end_date)
            
            if result.get('success'):
                logger.info(f"Orquestación exitosa: CFDI Generado con UUID {result.get('uuid')}")
                return {
                    "status": "success",
                    "action_executed": "move_b_to_a",
                    "sales_processed": len(sale_ids),
                    "cfdi": result
                }
            else:
                logger.error(f"Error al generar la factura orquestada: {result.get('error')}")
                return {
                    "status": "error",
                    "action_executed": "move_b_to_a",
                    "error": result.get('error')
                }

        return {"status": "skipped", "reason": "La principal prescripción no es ejecutable automáticamente."}
