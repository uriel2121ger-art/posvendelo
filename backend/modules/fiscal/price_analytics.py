"""
Smart Variance Engine - Generador de variabilidad natural
Aplica variación estocástica para reflejar comportamiento humano real
Conforme a prácticas contables estándar de estimación
"""

from typing import Any, Dict, List, Tuple
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
import logging
import math
import secrets

from modules.shared.constants import dec, money

_sysrandom = secrets.SystemRandom()

logger = logging.getLogger(__name__)

_TWO_PLACES = Decimal('0.01')


class SmartVarianceEngine:
    """
    Motor de variabilidad inteligente para cálculos fiscales.
    Introduce variación natural que refleja el comportamiento real del negocio.
    """

    def __init__(self, db=None):
        self.db = db
        self._seed = None

    async def calculate_smart_loss(self, base_amount: Decimal,
                              category: str = 'general') -> Dict[str, Any]:
        """
        Calcula merma con variación natural basada en categoría de producto.

        Args:
            base_amount: Monto base de la merma (Decimal)
            category: Categoría del producto (perecedero, frágil, general)

        Returns:
            Dict con monto ajustado y justificación
        """
        base_amount = dec(base_amount)

        # Factores de variación por categoría (basados en industria)
        variance_factors = {
            'perecedero': (Decimal('0.02'), Decimal('0.08')),    # 2-8% para perecederos
            'fragil': (Decimal('0.01'), Decimal('0.04')),        # 1-4% para frágiles
            'general': (Decimal('0.005'), Decimal('0.025')),     # 0.5-2.5% para general
            'electronico': (Decimal('0.001'), Decimal('0.01')),  # 0.1-1% para electrónicos
        }

        min_var, max_var = variance_factors.get(category, (Decimal('0.005'), Decimal('0.025')))

        # Variación con distribución normal truncada (más realista)
        # gauss returns float — used only for the variance factor, not for money math
        min_var_f = float(min_var)
        max_var_f = float(max_var)
        mean_f = (min_var_f + max_var_f) / 2
        std_f = (max_var_f - min_var_f) / 4
        variance_f = max(min_var_f, min(max_var_f, _sysrandom.gauss(mean_f, std_f)))
        variance = Decimal(str(round(variance_f, 6)))

        # Calcular monto final en Decimal
        adjusted_amount = base_amount * (Decimal('1') + variance)

        # Redondear a centavos irregulares (más natural)
        final_amount = await self._natural_round(adjusted_amount)

        return {
            'original': money(base_amount),
            'adjusted': money(final_amount),
            'variance_pct': float((variance * Decimal('100')).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)),
            'category': category,
            'timestamp': datetime.now().isoformat(),
            'note': f'Ajuste por variación natural de {category}'
        }

    async def _natural_round(self, amount: Decimal) -> Decimal:
        """
        Redondea a centavos con patrón natural (evita .00, .50 exactos).
        """
        amount = dec(amount)
        cents = int(amount * 100) % 100

        # Si termina en multiplo de 10, añadir variación
        if cents % 10 == 0:
            adjustment = Decimal(_sysrandom.choice([1, 2, 3, 7, 8, 9])) / Decimal('100')
            if _sysrandom.random() > 0.5:
                amount += adjustment
            else:
                amount -= adjustment

        return amount.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

    async def suggest_optimal_CAST(self, operation_type: str = 'global_invoice') -> Dict[str, Any]:
        """
        Sugiere fecha óptima para operaciones fiscales.
        Evita patrones detectables (siempre fin de mes, siempre viernes).
        """
        today = datetime.now()

        # Días preferentes según tipo de operación
        if operation_type == 'global_invoice':
            # Variar entre día 28-5 del mes siguiente
            day_offset = _sysrandom.randint(-3, 5)
            target_day = 28 + day_offset
            if target_day > 28:
                target = today.replace(day=1) + timedelta(days=32)
                target = target.replace(day=min(target_day - 28, 5))
            else:
                target = today.replace(day=max(1, target_day))

        elif operation_type == 'loss_report':
            # Distribuir a lo largo del mes, evitando inicio/fin
            target_day = _sysrandom.randint(5, 25)
            target = today.replace(day=target_day)

        else:
            target = today + timedelta(days=_sysrandom.randint(1, 7))

        return {
            'suggested_date': target.strftime('%Y-%m-%d'),
            'day_of_week': target.strftime('%A'),
            'operation': operation_type,
            'note': 'Fecha sugerida para distribución natural'
        }

    async def generate_batch_variance(self, items: List[Dict],
                                 total_target: Decimal) -> List[Dict]:
        """
        Distribuye variación entre múltiples items manteniendo total objetivo.
        """
        if not items:
            return []

        total_target = dec(total_target)

        # Calcular total actual
        current_total = dec(sum(dec(item.get('amount', 0)) for item in items))

        if current_total == Decimal('0'):
            return items

        # Factor de ajuste base
        base_factor = total_target / current_total

        result = []
        accumulated = Decimal('0')

        for i, item in enumerate(items[:-1]):
            # Variación individual — uniform() is float, used as factor only
            factor_f = float(base_factor) * _sysrandom.uniform(0.97, 1.03)
            individual_factor = Decimal(str(round(factor_f, 8)))
            adjusted = await self._natural_round(dec(item.get('amount', 0)) * individual_factor)
            accumulated += adjusted

            result.append({
                **item,
                'original_amount': money(item.get('amount', 0)),
                'adjusted_amount': money(adjusted),
            })

        # Último item ajusta para cuadrar exacto
        last_item = items[-1]
        last_adjusted = await self._natural_round(total_target - accumulated)
        result.append({
            **last_item,
            'original_amount': money(last_item.get('amount', 0)),
            'adjusted_amount': money(last_adjusted),
        })

        return result

    async def get_seasonal_factor(self, date: datetime = None) -> Decimal:
        """
        Retorna factor estacional para el negocio.
        Útil para justificar variaciones en ventas/mermas.
        """
        date = date or datetime.now()
        month = date.month

        # Factores estacionales típicos de comercio en México
        seasonal_factors = {
            1: Decimal('0.85'),   # Enero - cuesta de enero
            2: Decimal('0.90'),   # Febrero - recuperación
            3: Decimal('0.95'),   # Marzo
            4: Decimal('1.05'),   # Abril - Semana Santa
            5: Decimal('1.10'),   # Mayo - Día de las madres
            6: Decimal('0.95'),   # Junio
            7: Decimal('0.90'),   # Julio
            8: Decimal('0.95'),   # Agosto - regreso a clases
            9: Decimal('1.00'),   # Septiembre - fiestas patrias
            10: Decimal('0.95'),  # Octubre
            11: Decimal('1.15'),  # Noviembre - Buen Fin
            12: Decimal('1.35'),  # Diciembre - Navidad
        }

        return seasonal_factors.get(month, Decimal('1.0'))
