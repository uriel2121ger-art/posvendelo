"""
Input Validators - Security and data integrity
Validates all user inputs to prevent SQL injection and data corruption
"""

from typing import Tuple, Union
from decimal import Decimal, InvalidOperation
import math
import re


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass

class Validators:
    """Collection of input validation methods"""
    
    @staticmethod
    def validate_sku(sku: str) -> Tuple[bool, str]:
        """
        Validate SKU format
        
        Args:
            sku: SKU string to validate
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not sku:
            return False, "SKU no puede estar vacío"
        
        if len(sku) < 6:
            return False, "SKU debe tener al menos 6 caracteres"
        
        if len(sku) > 13:
            return False, "SKU no puede exceder 13 caracteres"
        
        if not re.match(r'^[A-Z0-9-]+$', sku):
            return False, "SKU solo puede contener letras mayúsculas, números y guiones"
        
        return True, ""
    
    @staticmethod
    def validate_email(email: str) -> Tuple[bool, str]:
        """
        Validate email format
        
        Args:
            email: Email address
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not email:
            return True, ""  # Email is optional
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            return False, "Formato de email inválido"
        
        return True, ""
    
    @staticmethod
    def validate_phone(phone: str) -> Tuple[bool, str]:
        """
        Validate phone number (Mexican format)
        
        Args:
            phone: Phone number
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not phone:
            return True, ""  # Phone is optional
        
        # Remove all non-numeric characters
        cleaned = re.sub(r'\D', '', phone)
        
        if len(cleaned) != 10:
            return False, "Teléfono debe tener 10 dígitos"
        
        if not cleaned.startswith(('1', '2', '3', '4', '5', '6', '7', '8', '9')):
            return False, "Número de teléfono inválido"
        
        return True, ""
    
    @staticmethod
    def validate_rfc(rfc: str) -> Tuple[bool, str]:
        """
        Validate RFC (Mexican tax ID)
        
        Args:
            rfc: RFC string
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not rfc:
            return True, ""  # RFC is optional
        
        rfc = rfc.upper().strip()
        
        # RFC can be 12 (moral) or 13 (física) characters
        if len(rfc) not in (12, 13):
            return False, "RFC debe tener 12 o 13 caracteres"
        
        # Basic pattern validation
        if not re.match(r'^[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}$', rfc):
            return False, "Formato de RFC inválido"
        
        return True, ""
    
    @staticmethod
    def validate_price(price: float | Decimal | str) -> Tuple[bool, str]:
        """
        Validate price value
        
        Args:
            price: Price value
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            price_val = Decimal(str(price))
        except (InvalidOperation, ValueError):
            return False, "Precio debe ser un número válido"
        
        if price_val < 0:
            return False, "Precio no puede ser negativo"
        
        if price_val > 1000000:
            return False, "Precio excede el máximo permitido (1,000,000)"
        
        return True, ""
    
    @staticmethod
    def validate_stock(stock: float | str) -> Tuple[bool, str]:
        """
        Validate stock quantity
        
        Args:
            stock: Stock quantity
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            stock_val = float(stock)
        except (ValueError, TypeError):
            return False, "Stock debe ser un número válido"
        
        if stock_val < 0:
            return False, "Stock no puede ser negativo"
        
        if stock_val > 1000000:
            return False, "Stock excede el máximo permitido"
        
        return True, ""
    
    @staticmethod
    def sanitize_sql_input(value: str) -> str:
        """
        Remove potentially dangerous SQL characters
        
        Args:
            value: Input string
        
        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            return value
        
        # Remove SQL injection patterns
        dangerous_patterns = [
            '--',      # SQL comment
            '/*',      # Block comment start
            '*/',      # Block comment end
            ';',       # Statement terminator
            'DROP ',   # Dangerous command
            'DELETE ', # Dangerous command
            'UPDATE ', # Can be dangerous
            'INSERT ', # Can be dangerous
        ]
        
        cleaned = value
        for pattern in dangerous_patterns:
            cleaned = cleaned.replace(pattern, '')
        
        return cleaned.strip()
    
    @staticmethod
    def validate_barcode(barcode: str) -> Tuple[bool, str]:
        """
        Validate barcode format
        
        Args:
            barcode: Barcode string
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not barcode:
            return True, ""  # Barcode is optional
        
        # Accept various barcode formats (EAN-13, UPC, Code128, etc.)
        if len(barcode) < 8 or len(barcode) > 13:
            return False, "Código de barras debe tener entre 8 y 13 caracteres"
        
        if not barcode.isdigit():
            return False, "Código de barras solo puede contener números"
        
        return True, ""
    
    @staticmethod
    def validate_required(value: str, field_name: str) -> Tuple[bool, str]:
        """
        Validate required field
        
        Args:
            value: Field value
            field_name: Name of the field for error message
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not value or (isinstance(value, str) and not value.strip()):
            return False, f"{field_name} es requerido"
        
        return True, ""
    
    @staticmethod
    def validate_positive_number(value: float | int, field_name: str) -> Tuple[bool, str]:
        """
        Validate positive number

        Args:
            value: Number to validate
            field_name: Field name for error message

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            num = float(value)
            if num <= 0:
                return False, f"{field_name} debe ser mayor a cero"
            return True, ""
        except (ValueError, TypeError):
            return False, f"{field_name} debe ser un número válido"


def safe_float(value: Union[str, int, float, None], default: float = 0.0) -> float:
    """
    Safely convert a value to float, rejecting inf and nan.

    Args:
        value: Value to convert to float
        default: Default value if conversion fails or value is invalid

    Returns:
        Valid finite float or default value
    """
    if value is None:
        return default
    try:
        result = float(value)
        if not math.isfinite(result):
            return default
        return result
    except (ValueError, TypeError):
        return default


def safe_decimal(value: Union[str, int, float, Decimal, None], default: Decimal = Decimal("0")) -> Decimal:
    """
    Safely convert a value to Decimal, rejecting inf and nan strings.

    Args:
        value: Value to convert to Decimal
        default: Default value if conversion fails or value is invalid

    Returns:
        Valid Decimal or default value
    """
    if value is None:
        return default

    # Reject inf and nan string representations
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("inf", "-inf", "+inf", "infinity", "-infinity", "+infinity", "nan"):
            return default

    # Reject float inf and nan
    if isinstance(value, float):
        if not math.isfinite(value):
            return default

    try:
        result = Decimal(str(value))
        # Decimal can represent inf/nan, check for that
        if not result.is_finite():
            return default
        return result
    except (InvalidOperation, ValueError, TypeError):
        return default


def validate_branch_id(branch_id: Union[int, None]) -> int:
    """
    Validate branch_id is a non-negative integer.

    Args:
        branch_id: Branch ID to validate

    Returns:
        Validated branch_id

    Raises:
        ValueError: If branch_id is invalid
    """
    if branch_id is None:
        raise ValueError("branch_id cannot be None")
    if not isinstance(branch_id, int):
        raise ValueError(f"branch_id must be an integer, got {type(branch_id).__name__}")
    if branch_id < 0:
        raise ValueError(f"branch_id cannot be negative: {branch_id}")
    return branch_id


def validate_user_id(user_id: Union[int, None]) -> int:
    """
    Validate user_id is a non-negative integer.

    Args:
        user_id: User ID to validate

    Returns:
        Validated user_id

    Raises:
        ValueError: If user_id is invalid
    """
    if user_id is None:
        raise ValueError("user_id cannot be None")
    if not isinstance(user_id, int):
        raise ValueError(f"user_id must be an integer, got {type(user_id).__name__}")
    if user_id < 0:
        raise ValueError(f"user_id cannot be negative: {user_id}")
    return user_id
