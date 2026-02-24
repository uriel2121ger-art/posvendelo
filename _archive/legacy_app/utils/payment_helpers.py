"""
TITAN POS - Payment Processing Helpers
=======================================

Extracted helper functions for payment processing to reduce
complexity in sales_tab._handle_charge function.
"""

from typing import Dict, List, Optional, Tuple, Union
from decimal import Decimal, InvalidOperation
import logging

logger = logging.getLogger("PaymentHelpers")

# =============================================================================
# SAFE PARSING FUNCTIONS
# =============================================================================

def safe_float(text: str, default: float = 0.0) -> float:
    """
    Parse string to float safely.
    
    ⚠️ DEPRECATED for financial calculations.
    Use safe_decimal() for fiscal/monetary calculations to avoid
    precision errors like 0.1 + 0.2 = 0.30000000000000004
    
    Args:
        text: String to parse
        default: Default value if parsing fails
        
    Returns:
        Parsed float or default value
        
    Example:
        >>> safe_float("123.45")
        123.45
        >>> safe_float("abc", 0.0)
        0.0
    """
    if not text:
        return default
    try:
        return float(text)
    except (ValueError, TypeError):
        return default

def safe_decimal(text: str, default: Decimal = Decimal('0')) -> Decimal:
    """
    Parse string to Decimal safely.
    
    Args:
        text: String to parse
        default: Default value if parsing fails
        
    Returns:
        Parsed Decimal or default value
    """
    if not text:
        return default
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError, TypeError):
        return default

def format_currency(amount: Union[float, Decimal], symbol: str = "$") -> str:
    """
    Format amount as currency string.
    
    Args:
        amount: Amount to format
        symbol: Currency symbol (default: $)
        
    Returns:
        Formatted string like "$1,234.56"
    """
    try:
        return f"{symbol}{float(amount):,.2f}"
    except (ValueError, TypeError):
        return f"{symbol}0.00"

# =============================================================================
# REFERENCE BUILDING FUNCTIONS
# =============================================================================

def build_cheque_reference(bank: str, number: str, 
                           date: str, account_last4: str) -> str:
    """
    Build comprehensive cheque reference string.
    
    Args:
        bank: Bank name
        number: Cheque number
        date: Cheque date
        account_last4: Last 4 digits of account
        
    Returns:
        Formatted reference string
    """
    parts = []
    if bank:
        parts.append(f"Banco: {bank}")
    if number:
        parts.append(f"Cheque: {number}")
    if date:
        parts.append(f"Fecha: {date}")
    if account_last4:
        parts.append(f"Cuenta: ****{account_last4}")
    
    return " | ".join(parts) if parts else ""

def build_mixed_reference(breakdown: dict) -> str:
    """
    Build reference string for mixed payment.
    
    Args:
        breakdown: Dict with payment breakdown and references
        
    Returns:
        Composite reference string
    """
    refs = []
    
    if breakdown.get('card', 0) > 0:
        refs.append(f"Tarj: {breakdown.get('card_ref', '')}")
    
    if breakdown.get('transfer', 0) > 0:
        refs.append(f"Transf: {breakdown.get('transfer_ref', '')}")
    
    if breakdown.get('wallet', 0) > 0:
        refs.append(f"Puntos: ${breakdown['wallet']:.2f}")
    
    if breakdown.get('gift_card', 0) > 0:
        refs.append(f"Gift: {breakdown.get('gift_card_code', '')}")
    
    return "; ".join(refs)

# =============================================================================
# PAYMENT VALIDATION FUNCTIONS
# =============================================================================

def validate_payment_amount(total: float, paid: float, payment_method: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that payment amount is sufficient for the total.
    
    Args:
        total: Total amount due
        paid: Amount being paid
        payment_method: Payment method ('cash', 'card', 'credit', etc.)
        
    Returns:
        (is_valid, error_message) tuple
        
    Example:
        >>> validate_payment_amount(100.0, 100.0, 'cash')
        (True, None)
        >>> validate_payment_amount(100.0, 50.0, 'cash')
        (False, 'Payment insufficient. Total: $100.00, Paid: $50.00')
    """
    try:
        total_decimal = Decimal(str(total))
        paid_decimal = Decimal(str(paid))
        
        if total_decimal < 0:
            return False, "Total amount cannot be negative"
        
        if paid_decimal < 0:
            return False, "Payment amount cannot be negative"
        
        # For credit, exact amount required
        if payment_method == 'credit':
            if paid_decimal != total_decimal:
                return False, f"Credit requires exact amount. Due: ${total_decimal:.2f}"
        
        # For cash/card, allow overpayment
        elif paid_decimal < total_decimal:
            diff = total_decimal - paid_decimal
            return False, f"Payment insufficient. Total: ${total_decimal:.2f}, Paid: ${paid_decimal:.2f}, Short: ${diff:.2f}"
        
        return True, None
        
    except (InvalidOperation, ValueError) as e:
        return False, f"Invalid payment amount: {e}"

def calculate_change(total: float, paid: float) -> float:
    """
    Calculate change to return to customer.
    
    Args:
        total: Total amount due
        paid: Amount paid by customer
        
    Returns:
        Change amount (0 if paid <= total)
        
    Example:
        >>> calculate_change(95.50, 100.00)
        4.50
        >>> calculate_change(100.00, 95.50)
        0.0
    """
    total_decimal = Decimal(str(total))
    paid_decimal = Decimal(str(paid))
    
    change = paid_decimal - total_decimal
    
    return float(max(change, Decimal('0')))

def validate_multi_payment(total: float, payments: Dict[str, float]) -> Tuple[bool, Optional[str]]:
    """
    Validate multiple payment methods sum correctly.
    
    Args:
        total: Total amount due
        payments: Dict of {payment_method: amount}
        
    Returns:
        (is_valid, error_message) tuple
        
    Example:
        >>> validate_multi_payment(100.0, {'cash': 50.0, 'card': 50.0})
        (True, None)
        >>> validate_multi_payment(100.0, {'cash': 50.0, 'card': 40.0})
        (False, 'Payment total ($90.00) does not match sale total ($100.00)')
    """
    try:
        total_decimal = Decimal(str(total))
        payments_sum = Decimal('0')
        
        for method, amount in payments.items():
            if amount < 0:
                return False, f"Payment amount for {method} cannot be negative"
            payments_sum += Decimal(str(amount))
        
        # Allow small rounding differences (1 cent)
        diff = abs(payments_sum - total_decimal)
        if diff > Decimal('0.01'):
            return False, f"Payment total (${payments_sum:.2f}) does not match sale total (${total_decimal:.2f})"
        
        return True, None
        
    except (InvalidOperation, ValueError) as e:
        return False, f"Invalid payment data: {e}"

def calculate_discounts(subtotal: float, discount_percent: float = 0.0, discount_fixed: float = 0.0) -> Dict[str, float]:
    """
    Calculate discount amounts.
    
    Args:
        subtotal: Subtotal before discounts
        discount_percent: Percentage discount (0-100)
        discount_fixed: Fixed amount discount
        
    Returns:
        Dict with 'percent_amount', 'fixed_amount', 'total_discount', 'final_total'
        
    Example:
        >>> calculate_discounts(100.0, discount_percent=10.0, discount_fixed=5.0)
        {'percent_amount': 10.0, 'fixed_amount': 5.0, 'total_discount': 15.0, 'final_total': 85.0}
    """
    subtotal_decimal = Decimal(str(subtotal))
    
    # Calculate percentage discount
    percent_amount = Decimal('0')
    if discount_percent > 0:
        if discount_percent > 100:
            discount_percent = 100
        percent_amount = subtotal_decimal * (Decimal(str(discount_percent)) / Decimal('100'))
    
    # Fixed discount
    fixed_amount = Decimal(str(discount_fixed)) if discount_fixed > 0 else Decimal('0')
    
    # Total discount (cannot exceed subtotal)
    total_discount = min(percent_amount + fixed_amount, subtotal_decimal)
    
    # CRITICAL: Ensure discount is never negative (shouldn't happen, but defensive)
    if total_discount < 0:
        total_discount = Decimal('0')
    
    # Final total
    final_total = subtotal_decimal - total_discount
    
    # CRITICAL: Normalize -0.0 to 0.0 for all return values
    percent_amount_float = float(percent_amount)
    fixed_amount_float = float(fixed_amount)
    total_discount_float = float(total_discount)
    final_total_float = float(final_total)
    
    # CRITICAL: Normalize -0.0 to 0.0 using tolerance for floating-point comparison
    # Direct == comparison with 0.0/-0.0 is unreliable due to IEEE 754 representation
    if abs(percent_amount_float) < 1e-9:
        percent_amount_float = 0.0
    if abs(fixed_amount_float) < 1e-9:
        fixed_amount_float = 0.0
    if abs(total_discount_float) < 1e-9:
        total_discount_float = 0.0
    if abs(final_total_float) < 1e-9:
        final_total_float = 0.0
    
    return {
        'percent_amount': percent_amount_float,
        'fixed_amount': fixed_amount_float,
        'total_discount': total_discount_float,
        'final_total': final_total_float
    }

def validate_inventory_availability(items: List[Dict]) -> Tuple[bool, List[str]]:
    """
    Validate that all items have sufficient inventory.
    
    Args:
        items: List of dicts with keys: 'product_id', 'name', 'quantity', 'current_stock'
        
    Returns:
        (all_available, error_messages) tuple
        
    Example:
        >>> items = [{'product_id': 1, 'name': 'Product A', 'quantity': 2, 'current_stock': 5}]
        >>> validate_inventory_availability(items)
        (True, [])
    """
    errors = []
    
    for item in items:
        product_id = item.get('product_id')
        name = item.get('name', f'Product {product_id}')
        quantity = float(item.get('quantity', 0))
        current_stock = float(item.get('current_stock', 0))
        
        if quantity > current_stock:
            shortage = quantity - current_stock
            errors.append(
                f"{name}: Insufficient stock (need {quantity}, have {current_stock}, short {shortage})"
            )
    
    return (len(errors) == 0, errors)

def format_payment_receipt(sale_data: Dict) -> str:
    """
    Format payment data for receipt printing.
    
    Args:
        sale_data: Dict with sale information
        
    Returns:
        Formatted receipt string
    """
    lines = []
    
    # Header
    lines.append("=" * 40)
    lines.append("PAYMENT RECEIPT")
    lines.append("=" * 40)
    
    # Sale details
    sale_id = sale_data.get('sale_id', 'N/A')
    lines.append(f"Sale ID: {sale_id}")
    lines.append(f"Date: {sale_data.get('date', 'N/A')}")
    lines.append("")
    
    # Items
    items = sale_data.get('items', [])
    for item in items:
        name = item.get('name', '')
        qty = item.get('quantity', 0)
        price = item.get('unit_price', 0)
        subtotal = qty * price
        lines.append(f"{name}")
        lines.append(f"  {qty} x ${price:.2f} = ${subtotal:.2f}")
    
    lines.append("-" * 40)
    
    # Totals
    subtotal = sale_data.get('subtotal', 0)
    discount = sale_data.get('discount', 0)
    total = sale_data.get('total', 0)
    
    lines.append(f"Subtotal: ${subtotal:.2f}")
    if discount > 0:
        lines.append(f"Discount: -${discount:.2f}")
    lines.append(f"TOTAL: ${total:.2f}")
    
    # Payment
    lines.append("")
    payment_method = sale_data.get('payment_method', 'N/A')
    paid = sale_data.get('paid', 0)
    change = sale_data.get('change', 0)
    
    lines.append(f"Payment Method: {payment_method}")
    lines.append(f"Paid: ${paid:.2f}")
    if change > 0:
        lines.append(f"Change: ${change:.2f}")
    
    lines.append("=" * 40)
    lines.append("Thank you for your purchase!")
    lines.append("=" * 40)
    
    return "\n".join(lines)

def log_payment_transaction(sale_id: int, payment_data: Dict, success: bool):
    """
    Log payment transaction for audit trail.
    
    Args:
        sale_id: ID of the sale
        payment_data: Payment information
        success: Whether payment was successful
    """
    status = "SUCCESS" if success else "FAILED"
    method = payment_data.get('method', 'unknown')
    amount = payment_data.get('amount', 0)
    
    logger.info(
        f"Payment {status}: Sale #{sale_id}, Method: {method}, Amount: ${amount:.2f}"
    )
    
    if not success:
        reason = payment_data.get('error_reason', 'Unknown')
        logger.warning(f"Payment failure reason: {reason}")
