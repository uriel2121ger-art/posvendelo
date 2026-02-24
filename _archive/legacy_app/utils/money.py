"""
💰 Utilidades de Precisión Financiera
Todas las operaciones monetarias deben usar Decimal, no float.

Problema con float:
    >>> 0.1 + 0.2
    0.30000000000000004  # ❌ El SAT rechaza esto

Solución:
    >>> Decimal('0.1') + Decimal('0.2')
    Decimal('0.3')  # ✅ Correcto

Uso:
    from app.utils.money import Money, to_money, round_sat
    
    price = to_money(product['price'])
    tax = price * Money('0.16')
    total = round_sat(price + tax)
"""
from typing import Optional, Union
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
import logging

logger = logging.getLogger("MONEY")

# Tipo alias para claridad
Money = Decimal

# Configuración de redondeo del SAT
SAT_DECIMALS = 2
ROUND_MODE = ROUND_HALF_UP

def to_money(value: Union[str, int, float, Decimal, None], default: Decimal = Decimal('0')) -> Decimal:
    """
    Convierte cualquier valor a Decimal de forma segura.
    
    SIEMPRE usar esta función en lugar de float() para valores monetarios.
    
    Args:
        value: Valor a convertir (str, int, float, Decimal, None)
        default: Valor por defecto si la conversión falla
    
    Returns:
        Decimal con el valor
    
    Examples:
        >>> to_money('123.45')
        Decimal('123.45')
        >>> to_money(100)
        Decimal('100')
        >>> to_money(100.50)  # float se convierte via str para evitar errores
        Decimal('100.5')
        >>> to_money(None)
        Decimal('0')
        >>> to_money('invalid')
        Decimal('0')
    """
    if value is None:
        return default
    
    if isinstance(value, Decimal):
        return value
    
    if isinstance(value, str):
        # Limpiar string
        clean = value.strip().replace(',', '').replace('$', '').replace(' ', '')
        if not clean or clean == '-':
            return default
        try:
            return Decimal(clean)
        except InvalidOperation:
            logger.warning(f"No se pudo convertir '{value}' a Decimal")
            return default
    
    if isinstance(value, (int, float)):
        # Convertir via string para evitar problemas de precisión float
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return default
    
    # Intentar conversión genérica
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default

def round_sat(amount: Decimal, decimals: int = SAT_DECIMALS) -> Decimal:
    """
    Redondea según las reglas del SAT (ROUND_HALF_UP).
    
    Args:
        amount: Cantidad a redondear
        decimals: Número de decimales (default: 2)
    
    Returns:
        Decimal redondeado
    
    Example:
        >>> round_sat(Decimal('123.456'))
        Decimal('123.46')
        >>> round_sat(Decimal('123.454'))
        Decimal('123.45')
        >>> round_sat(Decimal('123.455'))
        Decimal('123.46')  # Se redondea hacia arriba
    """
    if not isinstance(amount, Decimal):
        amount = to_money(amount)
    
    quantize_str = '0.' + '0' * decimals
    return amount.quantize(Decimal(quantize_str), rounding=ROUND_MODE)

def format_currency(amount: Union[Decimal, float, str, None], 
                    symbol: str = '$', 
                    decimals: int = 2) -> str:
    """
    Formatea un monto como moneda para display.
    
    Args:
        amount: Cantidad a formatear
        symbol: Símbolo de moneda
        decimals: Decimales a mostrar
    
    Returns:
        String formateado (ej: "$1,234.56")
    
    Example:
        >>> format_currency(Decimal('1234.5'))
        '$1,234.50'
    """
    money = to_money(amount)
    rounded = round_sat(money, decimals)
    
    # Formatear con separador de miles
    formatted = f"{rounded:,.{decimals}f}"
    return f"{symbol}{formatted}"

def calculate_tax(subtotal: Decimal, rate: Decimal = Decimal('0.16')) -> Decimal:
    """
    Calcula impuesto con precisión.
    
    Args:
        subtotal: Monto base
        rate: Tasa de impuesto (default: 16% IVA)
    
    Returns:
        Monto del impuesto redondeado
    """
    tax = subtotal * rate
    return round_sat(tax)

def calculate_total(subtotal: Decimal, tax_rate: Decimal = Decimal('0.16')) -> dict:
    """
    Calcula subtotal, impuesto y total.
    
    Returns:
        {
            'subtotal': Decimal,
            'tax': Decimal,
            'total': Decimal
        }
    """
    subtotal = round_sat(subtotal)
    tax = calculate_tax(subtotal, tax_rate)
    total = subtotal + tax
    
    return {
        'subtotal': subtotal,
        'tax': tax,
        'total': round_sat(total)
    }

def extract_tax_from_total(total_with_tax: Decimal, tax_rate: Decimal = Decimal('0.16')) -> dict:
    """
    Extrae el impuesto de un total que ya lo incluye.
    Útil para desglosar precios públicos.
    
    Args:
        total_with_tax: Precio total incluyendo impuesto
        tax_rate: Tasa de impuesto
    
    Returns:
        {
            'subtotal': Decimal (antes de impuesto),
            'tax': Decimal,
            'total': Decimal
        }
    
    Example:
        >>> extract_tax_from_total(Decimal('116'))
        {'subtotal': Decimal('100.00'), 'tax': Decimal('16.00'), 'total': Decimal('116.00')}
    """
    # subtotal = total / (1 + tasa)
    divisor = Decimal('1') + tax_rate
    subtotal = total_with_tax / divisor
    subtotal = round_sat(subtotal)
    
    tax = round_sat(total_with_tax - subtotal)
    
    return {
        'subtotal': subtotal,
        'tax': tax,
        'total': round_sat(total_with_tax)
    }

def safe_divide(numerator: Decimal, denominator: Decimal, 
                default: Decimal = Decimal('0')) -> Decimal:
    """
    División segura que maneja división por cero.
    """
    if denominator == 0:
        return default
    return numerator / denominator

def calculate_discount(original: Decimal, discount_percent: Decimal) -> dict:
    """
    Calcula precio con descuento.
    
    Returns:
        {
            'original': Decimal,
            'discount_amount': Decimal,
            'final': Decimal,
            'discount_percent': Decimal
        }
    """
    discount_rate = discount_percent / Decimal('100')
    discount_amount = round_sat(original * discount_rate)
    final = round_sat(original - discount_amount)
    
    return {
        'original': original,
        'discount_amount': discount_amount,
        'final': final,
        'discount_percent': discount_percent
    }

def sum_money(values: list) -> Decimal:
    """
    Suma una lista de valores monetarios de forma segura.
    
    Args:
        values: Lista de valores (pueden ser Decimal, float, str, None)
    
    Returns:
        Suma total como Decimal
    """
    total = Decimal('0')
    for v in values:
        total += to_money(v)
    return round_sat(total)

# Constantes útiles
ZERO = Decimal('0')
ONE = Decimal('1')
IVA_RATE = Decimal('0.16')
IEPS_RATE = Decimal('0.08')

# Validación
def validate_money_amount(amount: Decimal, 
                          min_value: Decimal = None, 
                          max_value: Decimal = None) -> dict:
    """
    Valida que un monto esté dentro de rangos permitidos.
    
    Returns:
        {
            'valid': bool,
            'amount': Decimal,
            'error': str or None
        }
    """
    result = {'valid': True, 'amount': amount, 'error': None}
    
    if amount < ZERO:
        result['valid'] = False
        result['error'] = 'El monto no puede ser negativo'
        return result
    
    if min_value is not None and amount < min_value:
        result['valid'] = False
        result['error'] = f'El monto mínimo es {format_currency(min_value)}'
        return result
    
    if max_value is not None and amount > max_value:
        result['valid'] = False
        result['error'] = f'El monto máximo es {format_currency(max_value)}'
        return result
    
    return result

if __name__ == "__main__":
    print("💰 Money Utils Test\n")
    
    # Test conversión
    print("Conversión:")
    print(f"  to_money('123.45') = {to_money('123.45')}")
    print(f"  to_money(100.50) = {to_money(100.50)}")
    print(f"  to_money(None) = {to_money(None)}")
    
    # Test redondeo SAT
    print("\nRedondeo SAT:")
    print(f"  round_sat(123.456) = {round_sat(Decimal('123.456'))}")
    print(f"  round_sat(123.455) = {round_sat(Decimal('123.455'))}")
    
    # Test cálculo de impuestos
    print("\nCálculo de impuestos:")
    result = calculate_total(Decimal('1000'))
    print(f"  Subtotal: {result['subtotal']}")
    print(f"  IVA 16%: {result['tax']}")
    print(f"  Total: {result['total']}")
    
    # Test extracción de impuesto
    print("\nExtracción de impuesto:")
    result = extract_tax_from_total(Decimal('1160'))
    print(f"  Total con IVA: $1,160")
    print(f"  Subtotal: {result['subtotal']}")
    print(f"  IVA: {result['tax']}")
    
    # Problema con float
    print("\n⚠️ Problema con float:")
    print(f"  float: 0.1 + 0.2 = {0.1 + 0.2}")
    print(f"  Decimal: 0.1 + 0.2 = {Decimal('0.1') + Decimal('0.2')}")
