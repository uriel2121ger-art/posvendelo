"""
Custom Exceptions for TITAN POS
Provides specific exception types for better error handling
"""

class POSException(Exception):
    """Base exception for POS system"""
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

class DatabaseError(POSException):
    """Database operation failed"""
    pass

class ValidationError(POSException):
    """Input validation failed"""
    pass

class PermissionDeniedError(POSException):
    """User lacks required permission"""
    pass

class BusinessRuleError(POSException):
    """Business logic constraint violated"""
    pass

class TurnNotOpenError(BusinessRuleError):
    """Operation requires an open turn"""
    def __init__(self, user_id: int = None):
        super().__init__(
            "No hay un turno abierto. Por favor abra un turno antes de continuar.",
            {'user_id': user_id}
        )

class InsufficientStockError(BusinessRuleError):
    """Product stock insufficient"""
    def __init__(self, product_name: str, available: float, requested: float):
        super().__init__(
            f"Stock insuficiente para {product_name}",
            {
                'product': product_name,
                'available': available,
                'requested': requested
            }
        )

class InvalidPaymentError(BusinessRuleError):
    """Payment validation failed"""
    pass

class ProductNotFoundError(POSException):
    """Requested product doesn't exist"""
    def __init__(self, sku: str = None, product_id: int = None):
        super().__init__(
            "Producto no encontrado",
            {'sku': sku, 'product_id': product_id}
        )

class CustomerNotFoundError(POSException):
    """Requested customer doesn't exist"""
    def __init__(self, customer_id: int = None):
        super().__init__(
            "Cliente no encontrado",
            {'customer_id': customer_id}
        )

class DuplicateError(POSException):
    """Resource already exists"""
    def __init__(self, resource_type: str, identifier: str):
        super().__init__(
            f"{resource_type} ya existe: {identifier}",
            {'type': resource_type, 'identifier': identifier}
        )

class ConfigurationError(POSException):
    """System configuration issue"""
    pass

class PrinterError(POSException):
    """Printer-related error"""
    pass

class NetworkError(POSException):
    """Network communication error"""
    pass

class AuthenticationError(POSException):
    """Authentication failed"""
    pass

class SessionExpiredError(AuthenticationError):
    """User session has expired"""
    def __init__(self):
        super().__init__("Sesión expirada. Por favor inicie sesión nuevamente")
