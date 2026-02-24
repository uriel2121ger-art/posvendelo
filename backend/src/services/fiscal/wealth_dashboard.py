"""
Wealth Dashboard - Dashboard de riqueza real (solo admin)
Calcula utilidad neta de bolsillo considerando todas las series
"""

from typing import Any, Dict, List, Optional
from datetime import date, datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class WealthDashboard:
    """
    Dashboard privado de riqueza real.
    Muestra la utilidad neta disponible para retiro.
    """
    
    def __init__(self, core):
        self.core = core
    
    def get_real_wealth(self, year: int = None, 
                        month: int = None) -> Dict[str, Any]:
        """
        Calcula la riqueza real: (Ventas A + B) - (Gastos + Impuestos).
        
        Args:
            year: Año a calcular
            month: Mes específico (opcional)
        """
        year = year or datetime.now().year
        
        if month:
            date_filter = f"{year}-{month:02d}"
            period_type = 'month'
        else:
            date_filter = str(year)
            period_type = 'year'
        
        # 1. INGRESOS TOTALES (A + B)
        ingresos = self._get_total_income(date_filter, period_type)
        
        # 2. GASTOS OPERATIVOS
        gastos = self._get_operating_expenses(date_filter, period_type)
        
        # 3. IMPUESTOS (ISR + IVA pagado)
        impuestos = self._calculate_taxes(ingresos, period_type)
        
        # 4. EXTRACCIONES YA REALIZADAS
        extracciones = self._get_extractions(date_filter, period_type)
        
        # 5. UTILIDAD BRUTA
        utilidad_bruta = ingresos['total'] - gastos['total']
        
        # 6. UTILIDAD NETA (después de impuestos)
        utilidad_neta = utilidad_bruta - impuestos['total']
        
        # 7. DISPONIBLE PARA RETIRO
        disponible = utilidad_neta - extracciones['total']
        
        return {
            'period': date_filter,
            'period_type': period_type,
            'ingresos': ingresos,
            'gastos': gastos,
            'impuestos': impuestos,
            'extracciones': extracciones,
            'utilidad_bruta': float(utilidad_bruta),
            'utilidad_neta': float(utilidad_neta),
            'disponible_retiro': float(disponible),
            'ratio_utilidad': round((float(utilidad_neta) / float(ingresos['total'])) * 100, 2) if ingresos['total'] > 0 else 0,
            'recomendaciones': self._get_recommendations(disponible, utilidad_neta)
        }
    
    def _get_total_income(self, date_filter: str, 
                          period_type: str) -> Dict[str, Any]:
        """Obtiene ingresos totales por serie."""
        if period_type == 'month':
            sql = """
                SELECT 
                    serie,
                    COALESCE(SUM(total), 0) as total,
                    COUNT(*) as transactions
                FROM sales
                WHERE TO_CHAR(timestamp, 'YYYY-MM') = %s  -- FIX 2026-02-01: PostgreSQL
                AND status = 'completed'
                GROUP BY serie
            """
        else:
            sql = """
                SELECT 
                    serie,
                    COALESCE(SUM(total), 0) as total,
                    COUNT(*) as transactions
                FROM sales
                WHERE EXTRACT(YEAR FROM timestamp)::TEXT = %s  -- FIX 2026-02-01: PostgreSQL
                AND status = 'completed'
                GROUP BY serie
            """
        
        result = list(self.core.db.execute_query(sql, (date_filter,)))
        
        by_serie = {}
        total = Decimal('0')
        
        for r in result:
            serie = r['serie'] or 'A'
            amount = Decimal(str(r['total'] or 0))
            by_serie[serie] = {
                'total': float(amount),
                'transactions': r['transactions']
            }
            total += amount
        
        return {
            'serie_a': by_serie.get('A', {'total': 0, 'transactions': 0}),
            'serie_b': by_serie.get('B', {'total': 0, 'transactions': 0}),
            'total': float(total)
        }
    
    def _get_operating_expenses(self, date_filter: str,
                                 period_type: str) -> Dict[str, Any]:
        """Obtiene gastos operativos estimados."""
        # Estimar gastos como % de ventas (en producción, usar datos reales)
        # Típicamente: 60-70% en comercio
        
        if period_type == 'month':
            sql = """
                SELECT COALESCE(SUM(total), 0) as total
                FROM sales
                WHERE TO_CHAR(timestamp, 'YYYY-MM') = %s  -- FIX 2026-02-01: PostgreSQL
                AND status = 'completed'
            """
        else:
            sql = """
                SELECT COALESCE(SUM(total), 0) as total
                FROM sales
                WHERE EXTRACT(YEAR FROM timestamp)::TEXT = %s  -- FIX 2026-02-01: PostgreSQL
                AND status = 'completed'
            """
        
        result = list(self.core.db.execute_query(sql, (date_filter,)))
        ventas = Decimal(str(result[0].get('total') or 0)) if result and len(result) > 0 and result[0] else Decimal('0')
        
        # Estimación de gastos (costo de venta 65%)
        costo_venta = ventas * Decimal('0.65')
        
        # Gastos fijos estimados
        gastos_fijos = ventas * Decimal('0.10')
        
        return {
            'costo_venta': float(costo_venta),
            'gastos_fijos': float(gastos_fijos),
            'total': float(costo_venta + gastos_fijos),
            'nota': 'Estimación basada en promedios de industria'
        }
    
    def _calculate_taxes(self, ingresos: Dict, 
                         period_type: str) -> Dict[str, Any]:
        """Calcula impuestos a pagar."""
        serie_a = Decimal(str(ingresos['serie_a']['total']))
        
        # ISR RESICO (basado en tabla progresiva)
        # Simplificado: usar tasa promedio de 1.5%
        isr = serie_a * Decimal('0.015')
        
        # IVA neto (16% sobre Serie A - IVA acreditable estimado)
        iva_cobrado = serie_a * Decimal('0.16') / Decimal('1.16')
        iva_acreditable = iva_cobrado * Decimal('0.70')  # Estimado 70%
        iva_neto = iva_cobrado - iva_acreditable
        
        return {
            'isr': float(isr),
            'iva_cobrado': float(iva_cobrado),
            'iva_acreditable': float(iva_acreditable),
            'iva_neto': float(iva_neto),
            'total': float(isr + iva_neto)
        }
    
    def _get_extractions(self, date_filter: str,
                         period_type: str) -> Dict[str, Any]:
        """Obtiene extracciones ya realizadas."""
        try:
            if period_type == 'month':
                sql = """
                    SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count
                    FROM cash_extractions
                    WHERE TO_CHAR(extraction_date, 'YYYY-MM') = %s  -- FIX 2026-02-01: PostgreSQL
                """
            else:
                sql = """
                    SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count
                    FROM cash_extractions
                    WHERE EXTRACT(YEAR FROM extraction_date)::TEXT = %s  -- FIX 2026-02-01: PostgreSQL
                """
            
            result = list(self.core.db.execute_query(sql, (date_filter,)))
            
            return {
                'total': float(result[0].get('total') or 0) if result and len(result) > 0 and result[0] else 0,
                'count': (result[0].get('count') or 0) if result and len(result) > 0 and result[0] else 0
            }
        except Exception:
            return {'total': 0, 'count': 0}
    
    def _get_recommendations(self, disponible: float,
                              utilidad: float) -> List[str]:
        """Genera recomendaciones según disponibilidad."""
        recs = []
        
        if disponible < 0:
            recs.append("🚨 Déficit de liquidez - No retirar")
            recs.append("🚨 Revisar gastos operativos")
        elif disponible < utilidad * 0.3:
            recs.append("⚠️ Colchón de seguridad bajo")
            recs.append(f"⚠️ Disponible: ${disponible:,.2f}")
        else:
            recs.append(f"✅ Disponible para retiro: ${disponible:,.2f}")
            recs.append("✅ Usar módulo de Cash Extraction")
        
        return recs
    
    def get_monthly_trend(self, year: int = None) -> List[Dict[str, Any]]:
        """Tendencia mensual de riqueza."""
        year = year or datetime.now().year
        
        months = []
        for m in range(1, 13):
            if datetime(year, m, 1) > datetime.now():
                break
            
            data = self.get_real_wealth(year, m)
            months.append({
                'month': m,
                'ingresos': data['ingresos']['total'],
                'utilidad_neta': data['utilidad_neta'],
                'disponible': data['disponible_retiro'],
                'ratio': data['ratio_utilidad']
            })
        
        return months
    
    def get_quick_summary(self) -> Dict[str, Any]:
        """Resumen rápido del estado actual."""
        year = datetime.now().year
        monthly = self.get_real_wealth(year, datetime.now().month)
        yearly = self.get_real_wealth(year)
        
        return {
            'mes_actual': {
                'ingresos': monthly['ingresos']['total'],
                'utilidad': monthly['utilidad_neta'],
                'disponible': monthly['disponible_retiro']
            },
            'año_actual': {
                'ingresos': yearly['ingresos']['total'],
                'utilidad': yearly['utilidad_neta'],
                'disponible': yearly['disponible_retiro'],
                'ratio': yearly['ratio_utilidad']
            },
            'timestamp': datetime.now().isoformat()
        }
