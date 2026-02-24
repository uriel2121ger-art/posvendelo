from pathlib import Path

"""
Interrogador de Datos - Chat Natural Language para Base de Datos
"¿Cuál es mi utilidad neta real de este mes%s"
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import logging
import re
import sys

logger = logging.getLogger(__name__)

class DataInterrogator:
    """
    Chat estilo GPT conectado a la base de datos local.
    Respuestas inmediatas a preguntas en lenguaje natural.
    """
    
    # Patrones de preguntas y sus handlers
    PATTERNS = {
        'utilidad': r'(utilidad|ganancia|profit)',
        'ventas': r'(ventas%s|vendido|facturado)',
        'efectivo': r'(efectivo|cash|retirar|extraer)',
        'cajera': r'(cajera%s|emplead[oa])',
        'inventario': r'(inventario|stock|existencia)',
        'faltante': r'(faltante|merma|perdid)',
        'comparar': r'(compar|vs|versus|anterior)',
        'sucursal': r'(sucursal|branch|tienda)',
        'mes': r'(mes|mensual)',
        'semana': r'(semana|semanal)',
        'hoy': r'(hoy|dia|diario)',
        'resico': r'(resico|limite|tope|fiscal)',
    }
    
    def __init__(self, core):
        self.core = core
    
    def ask(self, question: str) -> Dict[str, Any]:
        """
        Procesa una pregunta en lenguaje natural.
        
        Args:
            question: Pregunta del usuario
        
        Returns:
            Respuesta estructurada con datos
        """
        question_lower = question.lower()
        
        # Detectar intención
        intent = self._detect_intent(question_lower)
        
        # Ejecutar handler apropiado
        handlers = {
            'utilidad_mes': self._handle_utilidad,
            'utilidad_comparar': self._handle_utilidad_comparar,
            'ventas_hoy': self._handle_ventas_periodo('today'),
            'ventas_semana': self._handle_ventas_periodo('week'),
            'ventas_mes': self._handle_ventas_periodo('month'),
            'efectivo_disponible': self._handle_efectivo_disponible,
            'efectivo_retirar': self._handle_efectivo_retirar,
            'cajera_faltante': self._handle_cajera_faltante,
            'inventario_bajo': self._handle_inventario_bajo,
            'resico_status': self._handle_resico_status,
            'sucursal_top': self._handle_sucursal_top,
        }
        
        handler = handlers.get(intent)
        
        if handler:
            return handler(question_lower)
        else:
            return self._handle_fallback(question_lower)
    
    def _detect_intent(self, question: str) -> str:
        """Detecta la intención de la pregunta."""
        
        # Utilidad con comparación
        if re.search(self.PATTERNS['utilidad'], question) and re.search(self.PATTERNS['comparar'], question):
            return 'utilidad_comparar'
        
        # Utilidad simple
        if re.search(self.PATTERNS['utilidad'], question):
            return 'utilidad_mes'
        
        # Ventas por período
        if re.search(self.PATTERNS['ventas'], question):
            if re.search(self.PATTERNS['hoy'], question):
                return 'ventas_hoy'
            elif re.search(self.PATTERNS['semana'], question):
                return 'ventas_semana'
            else:
                return 'ventas_mes'
        
        # Efectivo
        if re.search(self.PATTERNS['efectivo'], question):
            if re.search(r'retirar|extraer|sacar', question):
                return 'efectivo_retirar'
            return 'efectivo_disponible'
        
        # Cajeras y faltantes
        if re.search(self.PATTERNS['cajera'], question) and re.search(self.PATTERNS['faltante'], question):
            return 'cajera_faltante'
        
        # Inventario
        if re.search(self.PATTERNS['inventario'], question):
            return 'inventario_bajo'
        
        # RESICO
        if re.search(self.PATTERNS['resico'], question):
            return 'resico_status'
        
        # Sucursales
        if re.search(self.PATTERNS['sucursal'], question):
            return 'sucursal_top'
        
        return 'unknown'
    
    def _handle_utilidad(self, question: str) -> Dict[str, Any]:
        """¿Cuál es mi utilidad neta real de este mes?"""
        month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        
        try:
            # Ventas totales (A + B)
            ventas = list(self.core.db.execute_query("""
                SELECT 
                    COALESCE(SUM(CASE WHEN serie = 'A' THEN total ELSE 0 END), 0) as ventas_a,
                    COALESCE(SUM(CASE WHEN serie = 'B' THEN total ELSE 0 END), 0) as ventas_b,
                    COALESCE(SUM(total), 0) as total
                FROM sales WHERE timestamp::date >= %s
            """, (month_start,)))
            
            # Costos (compras)
            costos = list(self.core.db.execute_query("""
                SELECT COALESCE(SUM(total), 0) as total
                FROM purchases WHERE purchase_date::date >= %s
            """, (month_start,)))
            
            # Gastos operativos
            gastos = list(self.core.db.execute_query("""
                SELECT 
                    COALESCE(SUM(CASE WHEN serie = 'A' THEN amount ELSE 0 END), 0) as gastos_a,
                    COALESCE(SUM(CASE WHEN serie = 'B' THEN amount ELSE 0 END), 0) as gastos_b
                FROM expenses WHERE expense_date::date >= %s
            """, (month_start,)))
            
            total_ventas = float(ventas[0]['total'] or 0) if ventas else 0
            ventas_a = float(ventas[0]['ventas_a'] or 0) if ventas else 0
            ventas_b = float(ventas[0]['ventas_b'] or 0) if ventas else 0
            total_costos = float(costos[0]['total'] or 0) if costos else 0
            gastos_a = float(gastos[0]['gastos_a'] or 0) if gastos else 0
            gastos_b = float(gastos[0]['gastos_b'] or 0) if gastos else 0
            
            utilidad_real = total_ventas - total_costos - gastos_a - gastos_b
            margen = (utilidad_real / total_ventas * 100) if total_ventas > 0 else 0
            
            return {
                'answer': f"Tu utilidad neta real de este mes es **${utilidad_real:,.0f}** (margen {margen:.1f}%)",
                'details': {
                    'ventas_totales': total_ventas,
                    'serie_a': ventas_a,
                    'serie_b': ventas_b,
                    'costos': total_costos,
                    'gastos': gastos_a + gastos_b,
                    'utilidad': utilidad_real,
                    'margen_porcentaje': round(margen, 1)
                }
            }
            
        except Exception as e:
            return {'answer': f"Error al calcular: {e}", 'error': True}
    
    def _handle_utilidad_comparar(self, question: str) -> Dict[str, Any]:
        """¿Cuál es mi utilidad comparada con el mes anterior?"""
        # Este mes
        this_month = self._handle_utilidad(question)
        
        # Mes anterior
        last_month_start = (datetime.now().replace(day=1) - timedelta(days=1)).replace(day=1)
        last_month_end = datetime.now().replace(day=1) - timedelta(days=1)
        
        try:
            ventas_prev = list(self.core.db.execute_query("""
                SELECT COALESCE(SUM(total), 0) as total FROM sales 
                WHERE timestamp::date BETWEEN %s AND %s
            """, (last_month_start.strftime('%Y-%m-%d'), last_month_end.strftime('%Y-%m-%d'))))
            
            costos_prev = list(self.core.db.execute_query("""
                SELECT COALESCE(SUM(total), 0) as total FROM purchases 
                WHERE purchase_date::date BETWEEN %s AND %s
            """, (last_month_start.strftime('%Y-%m-%d'), last_month_end.strftime('%Y-%m-%d'))))
            
            utilidad_prev = (float(ventas_prev[0]['total'] or 0) if ventas_prev else 0) - (float(costos_prev[0]['total'] or 0) if costos_prev else 0)
            utilidad_actual = this_month['details']['utilidad']
            
            diferencia = utilidad_actual - utilidad_prev
            cambio_pct = ((diferencia / utilidad_prev) * 100) if utilidad_prev != 0 else 0
            
            emoji = "📈" if diferencia > 0 else "📉"
            
            return {
                'answer': f"{emoji} Este mes: **${utilidad_actual:,.0f}** | Mes anterior: **${utilidad_prev:,.0f}** | "
                         f"Diferencia: **{'+' if diferencia > 0 else ''}{diferencia:,.0f}** ({cambio_pct:+.1f}%)",
                'details': {
                    'utilidad_actual': utilidad_actual,
                    'utilidad_anterior': utilidad_prev,
                    'diferencia': diferencia,
                    'cambio_porcentaje': round(cambio_pct, 1)
                }
            }
            
        except Exception as e:
            return {'answer': f"Error: {e}", 'error': True}
    
    def _handle_ventas_periodo(self, period: str):
        """Handler factory para ventas por período."""
        def handler(question: str) -> Dict[str, Any]:
            if period == 'today':
                date_filter = "timestamp::date = CURRENT_DATE"
                label = "hoy"
            elif period == 'week':
                date_filter = "timestamp::date >= CURRENT_DATE - INTERVAL '7 days'"
                label = "esta semana"
            else:
                date_filter = "timestamp::date >= CURRENT_DATE - INTERVAL '1 month'"
                label = "este mes"
            
            try:
                # nosec B608 - date_filter is hardcoded SQL fragment based on period, not user input
                result = list(self.core.db.execute_query(f"""
                    SELECT
                        COALESCE(SUM(total), 0) as total,
                        COUNT(*) as transacciones,
                        COALESCE(SUM(CASE WHEN serie = 'A' THEN total ELSE 0 END), 0) as serie_a,
                        COALESCE(SUM(CASE WHEN serie = 'B' THEN total ELSE 0 END), 0) as serie_b
                    FROM sales WHERE {date_filter}
                """))
                if not result:
                    return {'answer': f"No hay datos de ventas {label}", 'error': True}
                
                data = result[0]
                
                return {
                    'answer': f"Ventas {label}: **${float(data['total']):,.0f}** "
                             f"({data['transacciones']} transacciones). "
                             f"Serie A: ${float(data['serie_a']):,.0f} | Serie B: ${float(data['serie_b']):,.0f}",
                    'details': dict(data)
                }
                
            except Exception as e:
                return {'answer': f"Error: {e}", 'error': True}
        
        return handler
    
    def _handle_efectivo_disponible(self, question: str) -> Dict[str, Any]:
        """¿Cuánto efectivo tenemos?"""
        try:
            result = list(self.core.db.execute_query("""
                SELECT 
                    COALESCE(SUM(CASE WHEN serie = 'B' AND payment_method IN ('cash', 'efectivo') THEN total ELSE 0 END), 0) as efectivo_b,
                    COALESCE(SUM(CASE WHEN serie = 'A' AND payment_method IN ('cash', 'efectivo') THEN total ELSE 0 END), 0) as efectivo_a
                FROM sales WHERE timestamp::date >= CURRENT_DATE - INTERVAL '30 days'
            """))
            
            efectivo_b = float(result[0]['efectivo_b'] or 0) if result else 0
            efectivo_a = float(result[0]['efectivo_a'] or 0) if result else 0
            
            return {
                'answer': f"💵 Efectivo disponible: **${efectivo_b:,.0f}** (Serie B) + **${efectivo_a:,.0f}** (Serie A) = **${efectivo_b + efectivo_a:,.0f}**",
                'details': {
                    'efectivo_serie_b': efectivo_b,
                    'efectivo_serie_a': efectivo_a,
                    'total': efectivo_b + efectivo_a
                }
            }
            
        except Exception as e:
            return {'answer': f"Error: {e}", 'error': True}
    
    def _handle_efectivo_retirar(self, question: str) -> Dict[str, Any]:
        """¿Cuánto puedo retirar sin que se vea sospechoso?"""
        # Extraer sucursal de la pregunta
        branch = None
        for b in ['centro', 'norte', 'poniente']:
            if b in question.lower():
                branch = b
                break
        
        try:
            params = []
            where_clause = ""
            if branch:
                where_clause = "AND branch = %s"
                params.append(branch)
            
            # nosec B608 - where_clause is hardcoded "AND branch = %s" string, not user input
            result = list(self.core.db.execute_query(f"""
                SELECT COALESCE(SUM(total), 0) as total
                FROM sales
                WHERE serie = 'B'
                AND payment_method IN ('cash', 'efectivo')
                AND timestamp::date >= CURRENT_DATE - INTERVAL '30 days'
                {where_clause}
            """, tuple(params) if params else None))
            
            efectivo_b = float(result[0]['total'] or 0) if result else 0
            
            # Cálculo conservador: máximo 30% del efectivo B mensual
            safe_withdrawal = efectivo_b * 0.30
            daily_recommended = safe_withdrawal / 30
            
            return {
                'answer': f"🏧 {'Sucursal ' + branch.capitalize() + ': ' if branch else ''}"
                         f"Puedes retirar hasta **${safe_withdrawal:,.0f}** este mes sin llamar la atención. "
                         f"Recomendación diaria: **${daily_recommended:,.0f}**",
                'details': {
                    'efectivo_total': efectivo_b,
                    'retiro_seguro': safe_withdrawal,
                    'diario_recomendado': daily_recommended
                }
            }
            
        except Exception as e:
            return {'answer': f"Error: {e}", 'error': True}
    
    def _handle_cajera_faltante(self, question: str) -> Dict[str, Any]:
        """¿Qué cajera tiene más faltantes?"""
        try:
            result = list(self.core.db.execute_query("""
                SELECT u.name, 
                       COUNT(*) as faltantes,
                       COALESCE(SUM(s.value), 0) as monto_total
                FROM shrinkage s
                JOIN users u ON s.created_by = u.id
                WHERE s.timestamp::date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY s.created_by
                ORDER BY monto_total DESC
                LIMIT 5
            """))
            
            if not result:
                return {'answer': "✅ No hay faltantes registrados este mes", 'details': []}
            
            top = result[0]
            
            return {
                'answer': f"⚠️ **{top['name']}** tiene {top['faltantes']} faltantes por **${float(top['monto_total']):,.0f}** este mes",
                'details': [dict(r) for r in result]
            }
            
        except Exception as e:
            return {'answer': f"Error: {e}", 'error': True}
    
    def _handle_inventario_bajo(self, question: str) -> Dict[str, Any]:
        """¿Qué productos tienen inventario bajo?"""
        try:
            result = list(self.core.db.execute_query("""
                SELECT name, stock, min_stock
                FROM products
                WHERE stock <= min_stock AND stock > 0
                ORDER BY (stock * 1.0 / NULLIF(min_stock, 0)) ASC
                LIMIT 10
            """))
            
            if not result:
                return {'answer': "✅ Todos los productos tienen stock suficiente", 'details': []}
            
            return {
                'answer': f"⚠️ {len(result)} productos con stock bajo. "
                         f"Más urgente: **{result[0]['name']}** ({result[0]['stock']} piezas)",
                'details': [dict(r) for r in result]
            }
            
        except Exception as e:
            return {'answer': f"Error: {e}", 'error': True}
    
    def _handle_resico_status(self, question: str) -> Dict[str, Any]:
        """¿Cómo voy con el límite RESICO?"""
        try:
            result = list(self.core.db.execute_query("""
                SELECT rfc, COALESCE(SUM(total), 0) as total
                FROM invoices 
                WHERE EXTRACT(YEAR FROM fecha::timestamp) = EXTRACT(YEAR FROM 'now'::timestamp)
                GROUP BY rfc
            """))
            
            limit = 3_500_000
            lines = []
            
            for r in result:
                total = float(r['total'])
                pct = (total / limit) * 100
                remaining = limit - total
                lines.append(f"RFC {r['rfc'][:4]}***: ${total:,.0f} ({pct:.0f}%) - Disponible: ${remaining:,.0f}")
            
            return {
                'answer': "📊 **Estado RESICO:**\n" + "\n".join(lines) if lines else "Sin facturación registrada",
                'details': [dict(r) for r in result]
            }
            
        except Exception as e:
            return {'answer': f"Error: {e}", 'error': True}
    
    def _handle_sucursal_top(self, question: str) -> Dict[str, Any]:
        """¿Cuál es la sucursal con más ventas?"""
        try:
            result = list(self.core.db.execute_query("""
                SELECT branch, COALESCE(SUM(total), 0) as total, COUNT(*) as transacciones
                FROM sales 
                WHERE timestamp::date >= CURRENT_DATE - INTERVAL '1 month'
                GROUP BY branch
                ORDER BY total DESC
            """))
            
            if not result:
                return {'answer': "Sin ventas este mes", 'details': []}
            
            top = result[0]
            
            return {
                'answer': f"🏆 **{top['branch'].capitalize()}** lidera con **${float(top['total']):,.0f}** ({top['transacciones']} ventas)",
                'details': [dict(r) for r in result]
            }
            
        except Exception as e:
            return {'answer': f"Error: {e}", 'error': True}
    
    def _handle_fallback(self, question: str) -> Dict[str, Any]:
        """Respuesta cuando no se entiende la pregunta."""
        return {
            'answer': "🤔 No entendí tu pregunta. Intenta algo como:\n"
                     "• ¿Cuál es mi utilidad neta real?\n"
                     "• ¿Cuánto efectivo puedo retirar del Centro?\n"
                     "• ¿Qué cajera tiene más faltantes?\n"
                     "• ¿Cómo voy con el límite RESICO?",
            'suggestions': [
                "Utilidad del mes",
                "Ventas de hoy",
                "Efectivo disponible",
                "Inventario bajo"
            ]
        }

# Función para PWA
def ask_data(core, question: str) -> Dict[str, Any]:
    """Wrapper para consulta desde PWA."""
    interrogator = DataInterrogator(core)
    return interrogator.ask(question)
