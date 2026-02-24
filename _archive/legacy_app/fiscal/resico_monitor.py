"""
RESICO Monitor - Monitor de salud fiscal para Régimen Simplificado de Confianza
Proyecciones, alertas y recomendaciones automáticas
"""

from typing import Any, Dict, List, Optional
from datetime import date, datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class RESICOMonitor:
    """
    Monitor de cumplimiento RESICO con proyecciones y alertas.
    Límite 2024-2025: $3,500,000 MXN anuales.
    """
    
    # Límites RESICO
    LIMITE_ANUAL = Decimal('3500000.00')
    ALERTA_AMARILLA = Decimal('3000000.00')  # 85%
    ALERTA_ROJA = Decimal('3250000.00')      # 93%
    
    # Tasas ISR RESICO por nivel de ingresos mensuales
    TASAS_RESICO = [
        (25000, 0.0100),
        (50000, 0.0110),
        (83333.33, 0.0120),
        (208333.33, 0.0140),
        (291666.67, 0.0170),
        (416666.67, 0.0210),
        (float('inf'), 0.0250),
    ]
    
    def __init__(self, core):
        self.core = core
    
    def get_health_status(self, year: int = None) -> Dict[str, Any]:
        """
        Obtiene estado de salud fiscal RESICO completo.
        """
        year = year or datetime.now().year
        
        # Obtener ventas Serie A
        ventas_a = self._get_ventas_serie_a(year)
        
        # Calcular días transcurridos
        today = datetime.now()
        start_of_year = datetime(year, 1, 1)
        days_elapsed = (today - start_of_year).days + 1
        days_in_year = 366 if year % 4 == 0 else 365
        
        # Proyección lineal
        if days_elapsed > 0:
            daily_average = ventas_a / days_elapsed
            proyeccion_anual = daily_average * days_in_year
        else:
            proyeccion_anual = Decimal('0')
        
        # Determinar estado
        estado = self._determinar_estado(ventas_a, proyeccion_anual)
        
        # Calcular límites
        restante = max(Decimal('0'), self.LIMITE_ANUAL - ventas_a)
        porcentaje_usado = (ventas_a / self.LIMITE_ANUAL) * 100
        
        # Días para llegar al límite al ritmo actual
        if daily_average > 0:
            dias_para_limite = int(restante / daily_average)
        else:
            dias_para_limite = 999
        
        return {
            'year': year,
            'ventas_serie_a': float(ventas_a),
            'limite_anual': float(self.LIMITE_ANUAL),
            'restante': float(restante),
            'porcentaje_usado': round(float(porcentaje_usado), 2),
            'proyeccion_anual': float(proyeccion_anual),
            'promedio_diario': float(daily_average) if days_elapsed > 0 else 0,
            'dias_transcurridos': days_elapsed,
            'dias_para_limite': dias_para_limite,
            'estado': estado,
            'recomendaciones': self._generar_recomendaciones(estado, ventas_a, restante, dias_para_limite),
            'tasa_isr_actual': self._get_tasa_mensual(ventas_a / max(1, today.month)),
            'timestamp': datetime.now().isoformat()
        }
    
    def _get_ventas_serie_a(self, year: int) -> Decimal:
        """Obtiene total de ventas Serie A del año."""
        sql = """
            SELECT COALESCE(SUM(subtotal), 0) as total
            FROM sales 
            WHERE serie = 'A' 
            AND EXTRACT(YEAR FROM timestamp::timestamp) = %s
            AND status = 'completed'
        """
        result = list(self.core.db.execute_query(sql, (str(year),)))
        return Decimal(str(result[0]['total'] or 0)) if result else Decimal('0')
    
    def _determinar_estado(self, actual: Decimal, proyeccion: Decimal) -> Dict[str, Any]:
        """Determina estado del semáforo fiscal."""
        if actual >= self.LIMITE_ANUAL:
            return {
                'semaforo': 'NEGRO',
                'codigo': 'EXCEDIDO',
                'mensaje': '¡LÍMITE EXCEDIDO! Consulta a tu contador inmediatamente.',
                'accion': 'URGENTE: Suspender facturación Serie A'
            }
        elif actual >= self.ALERTA_ROJA or proyeccion >= self.LIMITE_ANUAL:
            return {
                'semaforo': 'ROJO',
                'codigo': 'CRITICO',
                'mensaje': 'Zona crítica. Al ritmo actual excederás el límite.',
                'accion': 'Recomendar: Pausar métodos de pago tarjeta/transferencia'
            }
        elif actual >= self.ALERTA_AMARILLA:
            return {
                'semaforo': 'AMARILLO',
                'codigo': 'PRECAUCION',
                'mensaje': 'Precaución. Estás al 85%+ del límite anual.',
                'accion': 'Monitorear diariamente. Considerar estrategia de cierre.'
            }
        else:
            return {
                'semaforo': 'VERDE',
                'codigo': 'SALUDABLE',
                'mensaje': 'Situación fiscal saludable.',
                'accion': 'Continuar operación normal'
            }
    
    def _generar_recomendaciones(self, estado: Dict, actual: Decimal, 
                                  restante: Decimal, dias: int) -> List[str]:
        """Genera recomendaciones basadas en el estado."""
        recs = []
        
        if estado['codigo'] == 'EXCEDIDO':
            recs.append("🚨 Contacta a tu contador para migrar a Régimen General")
            recs.append("🚨 Las ventas adicionales tributarán a tasa mayor")
        
        elif estado['codigo'] == 'CRITICO':
            recs.append(f"⚠️ Solo puedes facturar ${float(restante):,.2f} más este año")
            recs.append("⚠️ Considera pausar pagos con tarjeta/transferencia")
            recs.append(f"⚠️ A este ritmo, llegarás al límite en {dias} días")
        
        elif estado['codigo'] == 'PRECAUCION':
            recs.append(f"📊 Te quedan ${float(restante):,.2f} de capacidad")
            recs.append("📊 Revisa tu estrategia de facturación global")
        
        else:
            recs.append("✅ Continúa con tu operación normal")
            recs.append(f"✅ Capacidad restante: ${float(restante):,.2f}")
        
        return recs
    
    def _get_tasa_mensual(self, promedio_mensual: Decimal) -> float:
        """Obtiene tasa ISR según promedio mensual."""
        promedio = float(promedio_mensual)
        for limite, tasa in self.TASAS_RESICO:
            if promedio <= limite:
                return tasa
        return 0.025
    
    def should_pause_fiscal(self) -> Dict[str, Any]:
        """
        Determina si se debe pausar facturación fiscal.
        Retorna estado y mensaje para mostrar a cajeras.
        """
        status = self.get_health_status()
        
        if status['estado']['codigo'] in ['EXCEDIDO', 'CRITICO']:
            return {
                'pause': True,
                'reason': status['estado']['mensaje'],
                'message_for_cashier': (
                    'Terminal bancaria en mantenimiento. '
                    'Solo efectivo disponible temporalmente.'
                ),
                'allow_cash': True,
                'allow_card': False,
                'allow_transfer': False
            }
        
        return {
            'pause': False,
            'allow_cash': True,
            'allow_card': True,
            'allow_transfer': True
        }
    
    def get_monthly_breakdown(self, year: int = None) -> List[Dict[str, Any]]:
        """Obtiene desglose mensual de ventas Serie A."""
        year = year or datetime.now().year
        
        sql = """
            SELECT 
                EXTRACT(MONTH FROM timestamp::timestamp) as mes,
                COUNT(*) as transacciones,
                COALESCE(SUM(subtotal), 0) as subtotal,
                COALESCE(SUM(tax), 0) as iva,
                COALESCE(SUM(total), 0) as total
            FROM sales
            WHERE serie = 'A'
            AND EXTRACT(YEAR FROM timestamp::timestamp) = %s
            AND status = 'completed'
            GROUP BY EXTRACT(MONTH FROM timestamp::timestamp)
            ORDER BY mes
        """
        
        result = list(self.core.db.execute_query(sql, (str(year),)))
        
        months = []
        acumulado = 0
        for row in result:
            subtotal = float(row['subtotal'] or 0)
            acumulado += subtotal
            months.append({
                'mes': int(row['mes']),
                'transacciones': row['transacciones'],
                'subtotal': subtotal,
                'iva': float(row['iva'] or 0),
                'total': float(row['total'] or 0),
                'acumulado': acumulado,
                'porcentaje_limite': round((acumulado / float(self.LIMITE_ANUAL)) * 100, 2)
            })
        
        return months
