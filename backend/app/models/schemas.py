"""
TypedDict schemas for TITAN POS
Provides type safety for data structures
"""
from decimal import Decimal
from enum import Enum
from typing import Literal, Optional, TypedDict


# Enums for consistent status values
class TurnStatus(str, Enum):
    """Turn status enum"""
    OPEN = "OPEN"
    CLOSED = "CLOSED"

class PaymentMethod(str, Enum):
    """Payment method enum"""
    CASH = "cash"
    CARD = "card"
    TRANSFER = "transfer"
    CREDIT = "credit"
    USD = "usd"
    MIXED = "mixed"
    WALLET = "wallet"
    GIFT_CARD = "gift_card"

class SaleStatus(str, Enum):
    """Sale status enum"""
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    PENDING = "pending"
    LAYAWAY = "layaway"

class EmployeeStatus(str, Enum):
    """Employee status enum"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"

class UserRole(str, Enum):
    """User role enum"""
    ADMIN = "admin"
    MANAGER = "manager"
    ENCARGADO = "encargado"
    CASHIER = "cashier"

# TypedDicts for data structures
class ProductSchema(TypedDict, total=False):
    """Product data schema"""
    id: int
    sku: str
    name: str
    price: Decimal
    price_wholesale: Optional[Decimal]
    cost: Decimal
    stock: float
    category_id: Optional[int]
    department: Optional[str]
    provider: Optional[str]
    min_stock: float
    is_active: bool
    is_kit: bool
    tax_scheme: Optional[str]
    tax_rate: Optional[Decimal]
    sale_type: Optional[str]
    barcode: Optional[str]
    is_favorite: bool
    # SAT Catalog fields for CFDI 4.0
    sat_clave_prod_serv: Optional[str]
    sat_clave_unidad: Optional[str]

class CustomerSchema(TypedDict, total=False):
    """Customer data schema"""
    id: int
    name: str
    first_name: Optional[str]
    last_name: Optional[str]
    rfc: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    points: int
    tier: Optional[str]
    credit_limit: float
    credit_balance: float
    wallet_balance: float
    address: Optional[str]
    notes: Optional[str]
    is_active: bool
    vip: bool
    credit_authorized: bool

class SaleSchema(TypedDict, total=False):
    """Sale data schema"""
    id: int
    uuid: str
    timestamp: str
    subtotal: float
    tax: float
    total: float
    payment_method: str
    customer_id: Optional[int]
    user_id: int
    turn_id: int
    status: str
    notes: Optional[str]
    cash_received: Optional[float]
    mixed_cash: Optional[float]
    mixed_card: Optional[float]
    mixed_transfer: Optional[float]

class TurnSchema(TypedDict, total=False):
    """Turn data schema"""
    id: int
    user_id: int
    start_timestamp: str
    end_timestamp: Optional[str]
    initial_cash: float
    final_cash: Optional[float]
    system_sales: Optional[float]
    difference: Optional[float]
    status: str
    notes: Optional[str]

class EmployeeSchema(TypedDict, total=False):
    """Employee data schema"""
    id: int
    employee_code: str
    name: str
    position: Optional[str]
    hire_date: Optional[str]
    status: str
    phone: Optional[str]
    email: Optional[str]
    base_salary: Optional[float]
    commission_rate: Optional[float]
    loan_limit: float
    current_loan_balance: float
    user_id: Optional[int]
    notes: Optional[str]
    created_at: str
    is_active: bool

class SaleItemSchema(TypedDict):
    """Sale item schema"""
    product_id: int
    sku: str
    name: str
    quantity: float
    price: float
    tax_rate: float
    discount: float
    subtotal: float

class CartItemSchema(TypedDict):
    """Shopping cart item schema"""
    sku: str
    name: str
    qty: float
    price: float
    discount: float
    tax: float
    subtotal: float
    product_id: int
