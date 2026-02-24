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

_sysrandom = secrets.SystemRandom()

logger = logging.getLogger(__name__)

class SmartVarianceEngine:
    """
    Motor de variabilidad inteligente para cálculos fiscales.
    Introduce variación natural que refleja el comportamiento real del negocio.
    """
    
    def __init__(self, core=None):
        self.core = core
        self._seed = None
    
    def calculate_smart_loss(self, base_amount: float, 
                              category: str = 'general') -> Dict[str, Any]:
        """
        Calcula merma con variación natural basada en categoría de producto.
        
        Args:
            base_amount: Monto base de la merma
            category: Categoría del producto (perecedero, frágil, general)
        
        Returns:
            Dict con monto ajustado y justificación
        """
        # Factores de variación por categoría (basados en industria)
        variance_factors = {
            'perecedero': (0.02, 0.08),    # 2-8% para perecederos
            'fragil': (0.01, 0.04),        # 1-4% para frágiles
            'general': (0.005, 0.025),     # 0.5-2.5% para general
            'electronico': (0.001, 0.01),  # 0.1-1% para electrónicos
        }
        
        min_var, max_var = variance_factors.get(category, (0.005, 0.025))
        
        # Variación con distribución normal truncada (más realista)
        mean = (min_var + max_var) / 2
        std = (max_var - min_var) / 4
        variance = max(min_var, min(max_var, _sysrandom.gauss(mean, std)))
        
        # Calcular monto final
        adjusted_amount = base_amount * (1 + variance)
        
        # Redondear a centavos irregulares (más natural)
        final_amount = self._natural_round(adjusted_amount)
        
        return {
            'original': base_amount,
            'adjusted': final_amount,
            'variance_pct': round(variance * 100, 3),
            'category': category,
            'timestamp': datetime.now().isoformat(),
            'note': f'Ajuste por variación natural de {category}'
        }
    
    def _natural_round(self, amount: float) -> float:
        """
        Redondea a centavos con patrón natural (evita .00, .50 exactos).
        """
        cents = int(amount * 100) % 100
        
        # Si termina en multiplo de 10, añadir variación
        if cents % 10 == 0:
            adjustment = _sysrandom.choice([1, 2, 3, 7, 8, 9]) / 100
            if _sysrandom.random() > 0.5:
                amount += adjustment
            else:
                amount -= adjustment
        
        return round(amount, 2)
    
    def suggest_optimal_CAST(self, operation_type: str = 'global_invoice') -> Dict[str, Any]:
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
    
    def generate_batch_variance(self, items: List[Dict], 
                                 total_target: float) -> List[Dict]:
        """
        Distribuye variación entre múltiples items manteniendo total objetivo.
        """
        if not items:
            return []
        
        # Calcular total actual
        current_total = sum(item.get('amount', 0) for item in items)
        
        if current_total == 0:
            return items
        
        # Factor de ajuste base
        base_factor = total_target / current_total
        
        result = []
        accumulated = 0
        
        for i, item in enumerate(items[:-1]):
            # Variación individual
            individual_factor = base_factor * _sysrandom.uniform(0.97, 1.03)
            adjusted = self._natural_round(item.get('amount', 0) * individual_factor)
            accumulated += adjusted
            
            result.append({
                **item,
                'original_amount': item.get('amount', 0),
                'adjusted_amount': adjusted
            })
        
        # Último item ajusta para cuadrar exacto
        last_item = items[-1]
        last_adjusted = self._natural_round(total_target - accumulated)
        result.append({
            **last_item,
            'original_amount': last_item.get('amount', 0),
            'adjusted_amount': last_adjusted
        })
        
        return result
    
    def get_seasonal_factor(self, date: datetime = None) -> float:
        """
        Retorna factor estacional para el negocio.
        Útil para justificar variaciones en ventas/mermas.
        """
        date = date or datetime.now()
        month = date.month
        
        # Factores estacionales típicos de comercio en México
        seasonal_factors = {
            1: 0.85,   # Enero - cuesta de enero
            2: 0.90,   # Febrero - recuperación
            3: 0.95,   # Marzo
            4: 1.05,   # Abril - Semana Santa
            5: 1.10,   # Mayo - Día de las madres
            6: 0.95,   # Junio
            7: 0.90,   # Julio
            8: 0.95,   # Agosto - regreso a clases
            9: 1.00,   # Septiembre - fiestas patrias
            10: 0.95,  # Octubre
            11: 1.15,  # Noviembre - Buen Fin
            12: 1.35,  # Diciembre - Navidad
        }
        
        return seasonal_factors.get(month, 1.0)
