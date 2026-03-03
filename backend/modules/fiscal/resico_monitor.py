"""
RESICO Monitor - Monitor de salud fiscal para Regimen Simplificado de Confianza
Proyecciones, alertas y recomendaciones automaticas

Refactored: receives `db` (DB wrapper) instead of `core`.
- Pure-logic functions are now sync (no async without await).
- Uses :name params and db.fetch/db.fetchrow/db.execute.
"""

from typing import Any, Dict, List, Optional
from datetime import date, datetime
from decimal import Decimal
import logging

from ..shared.constants import RESICO_ANNUAL_LIMIT

logger = logging.getLogger(__name__)


class RESICOMonitor:
    """
    Monitor de cumplimiento RESICO con proyecciones y alertas.
    Limite 2024-2025: $3,500,000 MXN anuales.
    """

    # Limites RESICO
    LIMITE_ANUAL = RESICO_ANNUAL_LIMIT
    ALERTA_AMARILLA = Decimal('3000000.00')  # 85%
    ALERTA_ROJA = Decimal('3250000.00')      # 93%

    # Tasas ISR RESICO por nivel de ingresos mensuales (Decimal para precisión fiscal)
    TASAS_RESICO = [
        (Decimal('25000'), Decimal('0.0100')),
        (Decimal('50000'), Decimal('0.0110')),
        (Decimal('83333.33'), Decimal('0.0120')),
        (Decimal('208333.33'), Decimal('0.0140')),
        (Decimal('291666.67'), Decimal('0.0170')),
        (Decimal('416666.67'), Decimal('0.0210')),
        (Decimal('999999999'), Decimal('0.0250')),
    ]

    def __init__(self, db):
        self.db = db

    async def get_health_status(self, year: int = None) -> Dict[str, Any]:
        """Obtiene estado de salud fiscal RESICO completo."""
        year = year or datetime.now().year

        ventas_a = await self._get_ventas_serie_a(year)

        today = datetime.now()
        start_of_year = datetime(year, 1, 1)
        days_elapsed = (today - start_of_year).days + 1
        days_in_year = 366 if year % 4 == 0 else 365

        if days_elapsed > 0:
            daily_average = ventas_a / days_elapsed
            proyeccion_anual = daily_average * days_in_year
        else:
            daily_average = Decimal('0')
            proyeccion_anual = Decimal('0')

        estado = self._determinar_estado(ventas_a, proyeccion_anual)

        restante = max(Decimal('0'), self.LIMITE_ANUAL - ventas_a)
        porcentaje_usado = (ventas_a / self.LIMITE_ANUAL) * 100

        if daily_average > 0:
            dias_para_limite = int(restante / daily_average)
        else:
            dias_para_limite = 999

        return {
            'year': year,
            'ventas_serie_a': round(float(ventas_a), 2),
            'limite_anual': round(float(self.LIMITE_ANUAL), 2),
            'restante': round(float(restante), 2),
            'porcentaje_usado': round(float(porcentaje_usado), 2),
            'proyeccion_anual': round(float(proyeccion_anual), 2),
            'promedio_diario': round(float(daily_average), 2) if days_elapsed > 0 else 0,
            'dias_transcurridos': days_elapsed,
            'dias_para_limite': dias_para_limite,
            'estado': estado,
            'recomendaciones': self._generar_recomendaciones(estado, ventas_a, restante, dias_para_limite),
            'tasa_isr_actual': float(self._get_tasa_mensual((ventas_a / Decimal(str(max(1, days_elapsed)))) * Decimal('30'))),
            'timestamp': datetime.now().isoformat(),
        }

    async def _get_ventas_serie_a(self, year: int) -> Decimal:
        """Obtiene total de ventas Serie A del anio."""
        row = await self.db.fetchrow(
            """SELECT COALESCE(SUM(subtotal), 0) as total
               FROM sales
               WHERE serie = 'A'
                 AND EXTRACT(YEAR FROM timestamp::timestamp) = :yr
                 AND status = 'completed'""",
            {"yr": year},
        )
        return Decimal(str(row['total'] or 0)) if row else Decimal('0')

    def _determinar_estado(self, actual: Decimal, proyeccion: Decimal) -> Dict[str, Any]:
        """Determina estado del semaforo fiscal (pure logic, no DB)."""
        if actual >= self.LIMITE_ANUAL:
            return {
                'semaforo': 'NEGRO',
                'codigo': 'EXCEDIDO',
                'mensaje': 'LIMITE EXCEDIDO! Consulta a tu contador inmediatamente.',
                'accion': 'URGENTE: Suspender facturacion Serie A',
            }
        elif actual >= self.ALERTA_ROJA or proyeccion >= self.LIMITE_ANUAL:
            return {
                'semaforo': 'ROJO',
                'codigo': 'CRITICO',
                'mensaje': 'Zona critica. Al ritmo actual excederas el limite.',
                'accion': 'Recomendar: Pausar metodos de pago tarjeta/transferencia',
            }
        elif actual >= self.ALERTA_AMARILLA:
            return {
                'semaforo': 'AMARILLO',
                'codigo': 'PRECAUCION',
                'mensaje': 'Precaucion. Estas al 85%+ del limite anual.',
                'accion': 'Monitorear diariamente. Considerar estrategia de cierre.',
            }
        else:
            return {
                'semaforo': 'VERDE',
                'codigo': 'SALUDABLE',
                'mensaje': 'Situacion fiscal saludable.',
                'accion': 'Continuar operacion normal',
            }

    def _generar_recomendaciones(
        self, estado: Dict, actual: Decimal, restante: Decimal, dias: int
    ) -> List[str]:
        """Genera recomendaciones basadas en el estado (pure logic, no DB)."""
        recs = []

        if estado['codigo'] == 'EXCEDIDO':
            recs.append("Contacta a tu contador para migrar a Regimen General")
            recs.append("Las ventas adicionales tributaran a tasa mayor")
        elif estado['codigo'] == 'CRITICO':
            recs.append(f"Solo puedes facturar ${round(float(restante), 2):,.2f} mas este anio")
            recs.append("Considera pausar pagos con tarjeta/transferencia")
            recs.append(f"A este ritmo, llegaras al limite en {dias} dias")
        elif estado['codigo'] == 'PRECAUCION':
            recs.append(f"Te quedan ${round(float(restante), 2):,.2f} de capacidad")
            recs.append("Revisa tu estrategia de facturacion global")
        else:
            recs.append("Continua con tu operacion normal")
            recs.append(f"Capacidad restante: ${round(float(restante), 2):,.2f}")

        return recs

    def _get_tasa_mensual(self, promedio_mensual: Decimal) -> Decimal:
        """Obtiene tasa ISR segun promedio mensual (pure logic, no DB)."""
        for limite, tasa in self.TASAS_RESICO:
            if promedio_mensual <= limite:
                return tasa
        return Decimal('0.0250')

    async def should_pause_fiscal(self) -> Dict[str, Any]:
        """
        Determina si se debe pausar facturacion fiscal.
        Retorna estado y mensaje para mostrar a cajeras.
        """
        status = await self.get_health_status()

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
                'allow_transfer': False,
            }

        return {
            'pause': False,
            'allow_cash': True,
            'allow_card': True,
            'allow_transfer': True,
        }

    async def get_monthly_breakdown(self, year: int = None) -> List[Dict[str, Any]]:
        """Obtiene desglose mensual de ventas Serie A."""
        year = year or datetime.now().year

        rows = await self.db.fetch(
            """SELECT
                EXTRACT(MONTH FROM timestamp::timestamp) as mes,
                COUNT(*) as transacciones,
                COALESCE(SUM(subtotal), 0) as subtotal,
                COALESCE(SUM(tax), 0) as iva,
                COALESCE(SUM(total), 0) as total
               FROM sales
               WHERE serie = 'A'
                 AND EXTRACT(YEAR FROM timestamp::timestamp) = :yr
                 AND status = 'completed'
               GROUP BY EXTRACT(MONTH FROM timestamp::timestamp)
               ORDER BY mes""",
            {"yr": year},
        )

        months = []
        acumulado = Decimal('0')
        for row in rows:
            subtotal = Decimal(str(row['subtotal'] or 0))
            acumulado += subtotal
            months.append({
                'mes': int(row['mes']),
                'transacciones': row['transacciones'],
                'subtotal': round(float(subtotal), 2),
                'iva': round(float(Decimal(str(row['iva'] or 0))), 2),
                'total': round(float(Decimal(str(row['total'] or 0))), 2),
                'acumulado': round(float(acumulado), 2),
                'porcentaje_limite': round(float((acumulado / self.LIMITE_ANUAL) * 100), 2),
            })

        return months
