"""
TITAN POS — Hardware Module Schemas

Pydantic models for hardware configuration endpoints.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field


class PrinterInfo(BaseModel):
    name: str
    enabled: bool
    status: str
    is_default: bool


class PrinterConfigUpdate(BaseModel):
    receipt_printer_name: Optional[str] = Field(None, max_length=100)
    receipt_printer_enabled: Optional[bool] = None
    receipt_paper_width: Optional[Literal[58, 80]] = None
    receipt_char_width: Optional[int] = Field(None, ge=20, le=64)
    receipt_auto_print: Optional[bool] = None
    receipt_mode: Optional[Literal["basic", "fiscal"]] = None
    receipt_cut_type: Optional[Literal["full", "partial"]] = None


class BusinessInfoUpdate(BaseModel):
    business_name: Optional[str] = Field(None, max_length=100)
    business_address: Optional[str] = Field(None, max_length=200)
    business_rfc: Optional[str] = Field(None, max_length=13)
    business_regimen: Optional[str] = Field(None, max_length=200)
    business_phone: Optional[str] = Field(None, max_length=20)
    business_footer: Optional[str] = Field(None, max_length=200)


class ScannerConfigUpdate(BaseModel):
    scanner_enabled: Optional[bool] = None
    scanner_prefix: Optional[str] = Field(None, max_length=20)
    scanner_suffix: Optional[str] = Field(None, max_length=20)
    scanner_min_speed_ms: Optional[int] = Field(None, ge=10, le=500)
    scanner_auto_submit: Optional[bool] = None


class DrawerConfigUpdate(BaseModel):
    cash_drawer_enabled: Optional[bool] = None
    printer_name: Optional[str] = Field(None, max_length=100)
    cash_drawer_auto_open_cash: Optional[bool] = None
    cash_drawer_auto_open_card: Optional[bool] = None
    cash_drawer_auto_open_transfer: Optional[bool] = None


class PrintReceiptRequest(BaseModel):
    sale_id: int = Field(..., gt=0)
