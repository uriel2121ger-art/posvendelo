"""
CORE: FINANCE MODULE
Módulo financiero blindado matemáticamente.
Validado por Protocolo DEUS EX MACHINA.
"""
from typing import Union
from decimal import ROUND_HALF_UP, Decimal, getcontext

# Configuración de precisión global
getcontext().prec = 28

class Money:
    """
    Representación inmutable de dinero para evitar errores de punto flotante.
    """
    def __init__(self, amount: Union[str, int, float, Decimal, 'Money']):
        if isinstance(amount, Money):
            self._amount = amount._amount
        else:
            # Convertir siempre a string primero para evitar artefactos binarios de float
            self._amount = Decimal(str(amount))

    @property
    def amount(self) -> Decimal:
        return self._amount

    def __add__(self, other):
        if not isinstance(other, (Money, int, float, Decimal)):
            return NotImplemented
        other_val = other.amount if isinstance(other, Money) else Decimal(str(other))
        return Money(self._amount + other_val)

    def __sub__(self, other):
        if not isinstance(other, (Money, int, float, Decimal)):
            return NotImplemented
        other_val = other.amount if isinstance(other, Money) else Decimal(str(other))
        return Money(self._amount - other_val)

    def __mul__(self, other):
        if not isinstance(other, (int, float, Decimal)):
            return NotImplemented
        # Multiplicación por escalar
        return Money(self._amount * Decimal(str(other)))

    def __truediv__(self, other):
        if not isinstance(other, (int, float, Decimal)):
            return NotImplemented
        # Use tolerance-based comparison for zero check (1e-9 tolerance)
        other_val = Decimal(str(other)) if not isinstance(other, Decimal) else other
        if abs(other_val) < Decimal('1e-9'):
            raise ZeroDivisionError("Cannot divide money by zero")
        return Money(self._amount / other_val)

    def __eq__(self, other):
        if not isinstance(other, (Money, int, float, Decimal)):
            return False
        other_val = other.amount if isinstance(other, Money) else Decimal(str(other))
        return self._amount == other_val

    def __lt__(self, other):
        other_val = other.amount if isinstance(other, Money) else Decimal(str(other))
        return self._amount < other_val

    def __le__(self, other):
        other_val = other.amount if isinstance(other, Money) else Decimal(str(other))
        return self._amount <= other_val

    def __gt__(self, other):
        other_val = other.amount if isinstance(other, Money) else Decimal(str(other))
        return self._amount > other_val

    def __ge__(self, other):
        other_val = other.amount if isinstance(other, Money) else Decimal(str(other))
        return self._amount >= other_val

    def __str__(self):
        return f"{self._amount:,.2f}"

    def __repr__(self):
        return f"Money('{self._amount}')"

    def round(self):
        """Redondeo bancario estándar a 2 decimales."""
        return Money(self._amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def calculate_total(base: Money, tax_rate: Decimal, discount_rate: Decimal = Decimal(0)) -> Money:
    """
    Calcula el total con impuestos y descuentos.
    Orden correcto para México: primero descuento, luego impuesto.
    Fórmula: (Base * (1 - Discount)) * (1 + Tax)

    El descuento se aplica ANTES del IVA porque:
    1. El descuento reduce la base gravable
    2. El IVA se calcula sobre la base ya descontada
    """
    discount_multiplier = Decimal(1) - discount_rate
    tax_multiplier = Decimal(1) + tax_rate

    # Correct order: discount first, then tax
    discounted_base = base * discount_multiplier
    total = discounted_base * tax_multiplier
    return total.round()
