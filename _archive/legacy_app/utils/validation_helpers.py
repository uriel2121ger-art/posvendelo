"""
TITAN POS - Validation Helper Functions
========================================

Centralized validation functions for common data types.
"""

from typing import Optional, Tuple
from decimal import Decimal, InvalidOperation
import re


def validate_sku(sku: str) -> Tuple[bool, Optional[str]]:
    """
    Validate SKU format.
    
    Args:
        sku: SKU string to validate
        
    Returns:
        (is_valid, error_message)
    """
    if not sku:
        return False, "SKU cannot be empty"
    
    if not isinstance(sku, str):
        return False, "SKU must be a string"
    
    # Remove whitespace
    sku = sku.strip()
    
    # Check length
    if len(sku) < 3:
        return False, "SKU too short (minimum 3 characters)"
    
    if len(sku) > 50:
        return False, "SKU too long (maximum 50 characters)"
    
    # Allow alphanumeric and hyphens
    if not re.match(r'^[A-Za-z0-9\-]+$', sku):
        return False, "SKU can only contain letters, numbers, and hyphens"
    
    return True, None

def validate_price(price: any, min_price: float = 0.0, max_price: float = 1000000.0) -> Tuple[bool, Optional[str]]:
    """
    Validate price value.
    
    Args:
        price: Price to validate
        min_price: Minimum acceptable price
        max_price: Maximum acceptable price
        
    Returns:
        (is_valid, error_message)
    """
    try:
        # Convert to Decimal for precise comparison
        price_decimal = Decimal(str(price))
        
        if price_decimal < Decimal(str(min_price)):
            return False, f"Price cannot be less than {min_price}"
        
        if price_decimal > Decimal(str(max_price)):
            return False, f"Price cannot exceed {max_price}"
        
        # Check decimal places (max 2)
        if abs(price_decimal.as_tuple().exponent) > 2:
            return False, "Price cannot have more than 2 decimal places"
        
        return True, None
        
    except (InvalidOperation, ValueError, TypeError):
        return False, "Invalid price format"

def validate_quantity(quantity: any, min_qty: float = 0.0, max_qty: float = 100000.0) -> Tuple[bool, Optional[str]]:
    """
    Validate quantity value.
    
    Args:
        quantity: Quantity to validate
        min_qty: Minimum acceptable quantity
        max_qty: Maximum acceptable quantity
        
    Returns:
        (is_valid, error_message)
    """
    try:
        qty = float(quantity)
        
        if qty < min_qty:
            return False, f"Quantity cannot be less than {min_qty}"
        
        if qty > max_qty:
            return False, f"Quantity cannot exceed {max_qty}"
        
        return True, None
        
    except (ValueError, TypeError):
        return False, "Invalid quantity format"

def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Validate email format.
    
    Args:
        email: Email address to validate
        
    Returns:
        (is_valid, error_message)
    """
    if not email:
        return True, None  # Email is optional
    
    if not isinstance(email, str):
        return False, "Email must be a string"
    
    email = email.strip().lower()
    
    # Basic email regex
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email):
        return False, "Invalid email format"
    
    if len(email) > 254:  # RFC 5321
        return False, "Email address too long"
    
    return True, None

def validate_phone(phone: str) -> Tuple[bool, Optional[str]]:
    """
    Validate phone number format.
    
    Args:
        phone: Phone number to validate
        
    Returns:
        (is_valid, error_message)
    """
    if not phone:
        return True, None  # Phone is optional
    
    if not isinstance(phone, str):
        return False, "Phone must be a string"
    
    # Remove common formatting
    phone_clean = re.sub(r'[\s\-\(\)\.]', '', phone)
    
    # Check if it's all digits (after removing formatting)
    if not phone_clean.isdigit():
        return False, "Phone can only contain digits and formatting characters"
    
    # Check length (10-15 digits is typical)
    if len(phone_clean) < 10:
        return False, "Phone number too short"
    
    if len(phone_clean) > 15:
        return False, "Phone number too long"
    
    return True, None

def validate_barcode(barcode: str) -> Tuple[bool, Optional[str]]:
    """
    Validate barcode format.
    
    Args:
        barcode: Barcode to validate
        
    Returns:
        (is_valid, error_message)
    """
    if not barcode:
        return True, None  # Barcode is optional
    
    if not isinstance(barcode, str):
        return False, "Barcode must be a string"
    
    barcode = barcode.strip()
    
    # Should be numeric
    if not barcode.isdigit():
        return False, "Barcode must contain only digits"
    
    # Common barcode lengths: 8 (EAN-8), 12 (UPC-A), 13 (EAN-13), 14 (ITF-14)
    valid_lengths = [8, 12, 13, 14]
    
    if len(barcode) not in valid_lengths:
        return False, f"Barcode length must be one of: {valid_lengths}"
    
    return True, None

def sanitize_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitize user input to prevent SQL injection and XSS.
    
    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
    """
    if not isinstance(text, str):
        return ""
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Trim to max length
    text = text[:max_length]
    
    # Remove control characters except newline and tab
    text = ''.join(char for char in text if char >= ' ' or char in '\n\t')
    
    return text.strip()

def validate_date_range(date_from: str, date_to: str) -> Tuple[bool, Optional[str]]:
    """
    Validate date range.
    
    Args:
        date_from: Start date (ISO format)
        date_to: End date (ISO format)
        
    Returns:
        (is_valid, error_message)
    """
    from datetime import datetime
    
    try:
        # Parse dates
        dt_from = datetime.fromisoformat(date_from)
        dt_to = datetime.fromisoformat(date_to)
        
        # Check order
        if dt_from > dt_to:
            return False, "Start date must be before end date"
        
        # Check reasonable range (e.g., max 5 years)
        delta = dt_to - dt_from
        if delta.days > 1825:  # ~5 years
            return False, "Date range too large (maximum 5 years)"
        
        return True, None
        
    except ValueError:
        return False, "Invalid date format (use ISO format: YYYY-MM-DD)"
