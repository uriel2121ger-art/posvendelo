"""
TITAN Gateway - Pydantic Models

All data models for the Gateway API.
"""
from decimal import Decimal
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, condecimal

class BranchInfo(BaseModel):
    branch_id: int
    branch_name: str
    terminal_id: Optional[int] = 1
    tailscale_ip: Optional[str] = None

class SaleRecord(BaseModel):
    branch_id: int
    terminal_id: int
    sale_id: int
    folio: Optional[int] = None
    timestamp: str
    total: condecimal(max_digits=12, decimal_places=2, ge=Decimal('0'))
    items: List[Dict[str, Any]]
    payments: Optional[List[Dict[str, Any]]] = None
    payment_method: Optional[str] = "Efectivo"
    cashier_id: Optional[int] = None
    cashier: Optional[str] = None
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None

class SyncBatch(BaseModel):
    branch_id: int
    terminal_id: int
    timestamp: str
    sales: Optional[List[Dict]] = None
    inventory_changes: Optional[List[Dict]] = None
    customers: Optional[List[Dict]] = None

class ProductUpdate(BaseModel):
    sku: str
    terminal_id: int
    request_id: Optional[str] = None
    price: Optional[condecimal(max_digits=10, decimal_places=2, gt=Decimal('0'))] = None
    cost: Optional[condecimal(max_digits=10, decimal_places=2, ge=Decimal('0'))] = None
    stock: Optional[int] = None
    name: Optional[str] = None

class HeartbeatPayload(BaseModel):
    """Heartbeat data from terminals."""
    terminal_id: int
    terminal_name: Optional[str] = None
    branch_id: int
    timestamp: str
    status: str = "online"
    today_sales: Optional[int] = 0
    today_total: Optional[condecimal(max_digits=12, decimal_places=2, ge=Decimal('0'))] = Decimal('0')
    active_turn: Optional[Dict[str, Any]] = None
    pending_sync: Optional[int] = 0
    product_count: Optional[int] = 0

class StockAlertPayload(BaseModel):
    """Stock alert from a terminal."""
    terminal_id: int
    branch_id: int
    alerts: List[Dict[str, Any]]
    timestamp: str

class LogBatchPayload(BaseModel):
    """Log batch from a terminal."""
    terminal_id: int
    branch_id: int
    timestamp: str
    entries: List[Dict[str, Any]]

class ProductCreate(BaseModel):
    sku: str
    terminal_id: int
    request_id: Optional[str] = None
    name: str
    price: condecimal(max_digits=10, decimal_places=2, gt=Decimal('0'))
    cost: Optional[condecimal(max_digits=10, decimal_places=2, ge=Decimal('0'))] = Decimal('0')
    stock: Optional[int] = 0

class InventoryAdjust(BaseModel):
    branch_id: int  # FIX 2026-02-01: Cambiado de str a int
    terminal_id: int
    request_id: Optional[str] = None
    sku: str
    quantity: int
    reason: str

class CustomerCreate(BaseModel):
    name: str
    phone: Optional[str] = ""
    email: Optional[str] = ""
    rfc: Optional[str] = ""
    address: Optional[str] = ""
