"""
Cart Helper Functions
Utility functions for cart operations, extracted from sales_tab.py
"""

from typing import Any, Dict, List
from decimal import ROUND_HALF_UP, Decimal
import logging

logger = logging.getLogger(__name__)

def calculate_cart_totals(items: List[Dict[str, Any]], tax_rate: float = 0.16) -> Dict[str, float]:
    """
    Calculate cart subtotal, tax, and total.
    
    Args:
        items: List of cart items with 'price', 'qty', and optional 'discount'
        tax_rate: Tax rate (default 16% IVA)
    
    Returns:
        Dict with 'subtotal', 'tax', 'total', 'discount'
    """
    subtotal = Decimal('0')
    total_discount = Decimal('0')
    
    for item in items:
        price = Decimal(str(item.get('price', 0)))
        qty = Decimal(str(item.get('qty', 1)))
        discount = Decimal(str(item.get('discount', 0)))
        
        line_total = price * qty
        total_discount += discount
        subtotal += line_total - discount
    
    tax = (subtotal * Decimal(str(tax_rate))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total = subtotal + tax
    
    return {
        'subtotal': float(subtotal),
        'tax': float(tax),
        'total': float(total),
        'discount': float(total_discount)
    }

def format_currency(amount: float, symbol: str = '$') -> str:
    """Format amount as currency with thousands separator."""
    return f"{symbol}{amount:,.2f}"

def validate_quantity(qty: Any, min_qty: float = 0.001, max_qty: float = 99999) -> float:
    """
    Validate and normalize quantity input.
    
    Args:
        qty: Quantity value (can be string, int, float)
        min_qty: Minimum allowed quantity
        max_qty: Maximum allowed quantity
    
    Returns:
        Valid quantity as float
    
    Raises:
        ValueError: If quantity is invalid
    """
    try:
        qty_float = float(qty)
        if qty_float < min_qty:
            raise ValueError(f"Cantidad mínima es {min_qty}")
        if qty_float > max_qty:
            raise ValueError(f"Cantidad máxima es {max_qty}")
        return qty_float
    except (TypeError, ValueError) as e:
        raise ValueError(f"Cantidad inválida: {qty}") from e

def validate_price(price: Any, min_price: float = 0.0, max_price: float = 999999.99) -> float:
    """
    Validate and normalize price input.
    
    Args:
        price: Price value (can be string, int, float)
        min_price: Minimum allowed price
        max_price: Maximum allowed price
    
    Returns:
        Valid price as float
    
    Raises:
        ValueError: If price is invalid
    """
    try:
        price_float = float(price)
        if price_float < min_price:
            raise ValueError(f"Precio mínimo es {min_price}")
        if price_float > max_price:
            raise ValueError(f"Precio máximo es {max_price}")
        return round(price_float, 2)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Precio inválido: {price}") from e

def find_existing_item(items: List[Dict[str, Any]], product_id: int) -> int:
    """
    Find index of existing product in cart.
    
    Args:
        items: List of cart items
        product_id: Product ID to find
    
    Returns:
        Index of item or -1 if not found
    """
    for i, item in enumerate(items):
        if item.get('product_id') == product_id:
            return i
    return -1

def calculate_change(total: float, received: float) -> float:
    """Calculate change to return."""
    change = received - total
    return max(0, round(change, 2))

def apply_discount_percentage(price: float, percent: float) -> float:
    """Apply percentage discount to price."""
    if percent < 0 or percent > 100:
        raise ValueError("Porcentaje debe estar entre 0 y 100")
    discount = price * (percent / 100)
    return round(price - discount, 2)

def apply_discount_fixed(price: float, amount: float) -> float:
    """Apply fixed amount discount to price."""
    if amount < 0:
        raise ValueError("Descuento no puede ser negativo")
    if amount > price:
        raise ValueError("Descuento no puede exceder el precio")
    return round(price - amount, 2)
