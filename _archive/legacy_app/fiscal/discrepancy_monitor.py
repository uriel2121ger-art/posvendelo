"""
Discrepancy Monitor - Monitor de discrepancia fiscal personal
Cruza ingresos declarados vs gastos bancarios para prevenir alertas SAT
Art. 91 LISR - Discrepancia fiscal
"""

from typing import Any, Dict, List, Optional
from datetime import date, datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class DiscrepancyMonitor:
    """
    Monitor de discrepancia fiscal personal.
    Previene el riesgo del Art. 91 LISR.
    """
    
    def __init__(self, core):
        self.core = core
        self._setup_table()
    
    def _setup_table(self):
        """Crea tabla de gastos personales."""
        try:
            self.core.db.execute_write("""
                CREATE TABLE IF NOT EXISTS personal_expenses (
                    id BIGSERIAL PRIMARY KEY,
                    expense_date TEXT NOT NULL,
                    amount DECIMAL(15,2) NOT NULL,
                    category TEXT NOT NULL,
                    payment_method TEXT NOT NULL,
                    description TEXT,
                    is_visible_to_sat INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.core.db.execute_write(
                "CREATE INDEX IF NOT EXISTS idx_expenses_date ON personal_expenses(expense_date)"
            )
            
        except Exception as e:
            logger.error(f"Error creating table: {e}")
    
    def register_expense(self, amount: float, category: str,
                         payment_method: str, description: str = None,
                         is_visible: bool = True) -> Dict[str, Any]:
        """
        Registra un gasto personal.
        
        Args:
            amount: Monto del gasto
            category: vivienda, transporte, alimentacion, entretenimiento, otro
            payment_method: tarjeta, transferencia, efectivo
            description: Descripción
            is_visible: Si el SAT puede verlo (tarjeta/banco = True)
        """
        try:
            self.core.db.execute_write(
                """INSERT INTO personal_expenses
                   (expense_date, amount, category, payment_method, 
                    description, is_visible_to_sat, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (datetime.now().strftime('%Y-%m-%d'), amount, category,
                 payment_method, description, 1 if is_visible else 0,
                 datetime.now().isoformat())
            )
            
            return {'success': True, 'amount': amount, 'category': category}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_discrepancy_analysis(self, year: int = None, 
                                  month: int = None) -> Dict[str, Any]:
        """
        Análisis de discrepancia fiscal.
        Compara: Ingresos Declarados vs Gastos visibles al SAT.
        """
        year = year or datetime.now().year
        
        if month:
            date_filter = f"{year}-{month:02d}"
            period_type = 'month'
        else:
            date_filter = str(year)
            period_type = 'year'
        
        # 1. Ingresos Declarados (Serie A)
        if period_type == 'month':
            ingresos_sql = """
                SELECT COALESCE(SUM(total), 0) as total
                FROM sales
                WHERE serie = 'A'
                AND TO_CHAR(timestamp::timestamp, 'YYYY-MM') = %s
                AND status = 'completed'
            """
        else:
            ingresos_sql = """
                SELECT COALESCE(SUM(total), 0) as total
                FROM sales
                WHERE serie = 'A'
                AND EXTRACT(YEAR FROM timestamp::timestamp) = %s
                AND status = 'completed'
            """
        
        ingresos = list(self.core.db.execute_query(ingresos_sql, (date_filter,)))
        total_ingresos = Decimal(str(ingresos[0]['total'] or 0)) if ingresos else Decimal('0')
        
        # 2. Gastos visibles al SAT (tarjeta/banco)
        if period_type == 'month':
            gastos_sql = """
                SELECT COALESCE(SUM(amount), 0) as total
                FROM personal_expenses
                WHERE TO_CHAR(expense_date::timestamp, 'YYYY-MM') = %s
                AND is_visible_to_sat = 1
            """
        else:
            gastos_sql = """
                SELECT COALESCE(SUM(amount), 0) as total
                FROM personal_expenses
                WHERE EXTRACT(YEAR FROM expense_date::timestamp) = %s
                AND is_visible_to_sat = 1
            """
        
        gastos = list(self.core.db.execute_query(gastos_sql, (date_filter,)))
        total_gastos_visible = Decimal(str(gastos[0]['total'] or 0)) if gastos else Decimal('0')
        
        # 3. Extracciones de Serie B (ya registradas)
        try:
            if period_type == 'month':
                ext_sql = """
                    SELECT COALESCE(SUM(amount), 0) as total
                    FROM cash_extractions
                    WHERE TO_CHAR(extraction_date::timestamp, 'YYYY-MM') = %s
                """
            else:
                ext_sql = """
                    SELECT COALESCE(SUM(amount), 0) as total
                    FROM cash_extractions
                    WHERE EXTRACT(YEAR FROM extraction_date::timestamp) = %s
                """
            extracciones = list(self.core.db.execute_query(ext_sql, (date_filter,)))
            total_extracciones = Decimal(str(extracciones[0]['total'] or 0)) if extracciones else Decimal('0')
        except Exception:
            total_extracciones = Decimal('0')
        
        # 4. Calcular discrepancia
        # Ingresos justificados = Serie A + Extracciones documentadas
        ingresos_justificados = total_ingresos + total_extracciones
        
        # Discrepancia = Gastos visibles - Ingresos justificados
        discrepancia = total_gastos_visible - ingresos_justificados
        
        # 5. Determinar estado
        if discrepancia > 0:
            porcentaje_riesgo = (discrepancia / max(total_gastos_visible, Decimal('1'))) * 100
            if porcentaje_riesgo > 30:
                estado = 'CRITICO'
                semaforo = 'ROJO'
            elif porcentaje_riesgo > 15:
                estado = 'ALERTA'
                semaforo = 'AMARILLO'
            else:
                estado = 'PRECAUCION'
                semaforo = 'AMARILLO'
        else:
            estado = 'SANO'
            semaforo = 'VERDE'
            porcentaje_riesgo = 0
        
        return {
            'period': date_filter,
            'period_type': period_type,
            'ingresos_serie_a': float(total_ingresos),
            'extracciones_documentadas': float(total_extracciones),
            'ingresos_justificados': float(ingresos_justificados),
            'gastos_visibles_sat': float(total_gastos_visible),
            'discrepancia': float(discrepancia),
            'porcentaje_riesgo': round(float(porcentaje_riesgo), 2),
            'estado': estado,
            'semaforo': semaforo,
            'recomendaciones': self._get_recommendations(
                estado, discrepancia, total_extracciones
            )
        }
    
    def _get_recommendations(self, estado: str, discrepancia: Decimal,
                             extracciones: Decimal) -> List[str]:
        """Genera recomendaciones basadas en el estado."""
        recs = []
        
        if estado == 'CRITICO':
            recs.append("🚨 URGENTE: Generar contratos de donación/mutuo")
            recs.append(f"🚨 Monto a documentar: ${float(discrepancia):,.2f}")
            recs.append("🚨 Considerar reducir gastos con tarjeta")
        
        elif estado == 'ALERTA':
            recs.append(f"⚠️ Documentar ${float(discrepancia):,.2f} con contratos")
            recs.append("⚠️ Revisar gastos de tarjeta del mes")
        
        elif estado == 'PRECAUCION':
            recs.append("📊 Monitorear balance mensualmente")
        
        else:
            recs.append("✅ Balance fiscal saludable")
            recs.append(f"✅ Extracciones documentadas: ${float(extracciones):,.2f}")
        
        return recs
    
    def get_monthly_trend(self, year: int = None) -> List[Dict[str, Any]]:
        """Tendencia mensual de discrepancia."""
        year = year or datetime.now().year
        
        months = []
        for m in range(1, 13):
            if datetime(year, m, 1) > datetime.now():
                break
            
            analysis = self.get_discrepancy_analysis(year, m)
            months.append({
                'month': m,
                'ingresos': analysis['ingresos_justificados'],
                'gastos': analysis['gastos_visibles_sat'],
                'discrepancia': analysis['discrepancia'],
                'semaforo': analysis['semaforo']
            })
        
        return months
    
    def suggest_extraction_amount(self) -> Dict[str, Any]:
        """Sugiere monto de extracción para equilibrar."""
        analysis = self.get_discrepancy_analysis()
        
        if analysis['discrepancia'] > 0:
            return {
                'recommend_extraction': True,
                'amount': analysis['discrepancia'],
                'reason': 'Cubrir brecha de discrepancia',
                'urgency': 'ALTA' if analysis['estado'] == 'CRITICO' else 'MEDIA'
            }
        
        return {
            'recommend_extraction': False,
            'balance': abs(analysis['discrepancia']),
            'message': 'No hay discrepancia, balance positivo'
        }
    
    def get_expense_breakdown(self, year: int = None, 
                               month: int = None) -> Dict[str, Any]:
        """Desglose de gastos por categoría."""
        year = year or datetime.now().year
        
        if month:
            sql = """
                SELECT category, payment_method,
                       COALESCE(SUM(amount), 0) as total,
                       COUNT(*) as count
                FROM personal_expenses
                WHERE TO_CHAR(expense_date::timestamp, 'YYYY-MM') = %s
                GROUP BY category, payment_method
            """
            result = list(self.core.db.execute_query(sql, (f"{year}-{month:02d}",)))
        else:
            sql = """
                SELECT category, payment_method,
                       COALESCE(SUM(amount), 0) as total,
                       COUNT(*) as count
                FROM personal_expenses
                WHERE EXTRACT(YEAR FROM expense_date::timestamp) = %s
                GROUP BY category, payment_method
            """
            result = list(self.core.db.execute_query(sql, (str(year),)))
        
        breakdown = {}
        for r in result:
            cat = r['category']
            if cat not in breakdown:
                breakdown[cat] = {'total': 0, 'by_method': {}}
            breakdown[cat]['total'] += float(r['total'] or 0)
            breakdown[cat]['by_method'][r['payment_method']] = float(r['total'] or 0)
        
        return {
            'period': f'{year}-{month:02d}' if month else str(year),
            'by_category': breakdown,
            'total': sum(c['total'] for c in breakdown.values())
        }
