"""
POSVENDELO - Fiscal Module Schemas
Pydantic request/response models for fiscal endpoints.
"""

from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class CFDIRequest(BaseModel):
    sale_id: int = Field(..., ge=1)
    customer_rfc: str = Field(..., min_length=12, max_length=13, pattern=r'^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$')
    customer_name: Optional[str] = Field(default=None, max_length=300)
    customer_regime: str = Field(default="616", pattern=r'^\d{3}$')
    uso_cfdi: str = Field(default="G03", pattern=r'^[A-Z]{1,2}\d{2}$')
    forma_pago: str = Field(default="01", pattern=r'^\d{2}$')
    customer_zip: str = Field(default="00000", pattern=r'^\d{5}$')


class GlobalCFDIRequest(BaseModel):
    period_type: str = Field(..., pattern=r'^(daily|weekly|monthly)$')
    date: Optional[str] = Field(default=None, pattern=r'^\d{4}-\d{2}-\d{2}$')


class ReturnItem(BaseModel):
    product_id: int = Field(..., ge=1)
    quantity: Decimal = Field(..., gt=0)
    reason: Optional[str] = None


class ProcessReturnRequest(BaseModel):
    sale_id: int = Field(..., ge=1)
    items: List[ReturnItem] = Field(..., min_length=1, max_length=500)
    reason: str = Field(..., min_length=1, max_length=500)
    # processed_by derived from JWT in endpoint, not from client


class GhostWalletCreateRequest(BaseModel):
    seed: Optional[str] = Field(default=None, max_length=200)


class GhostWalletAddPointsRequest(BaseModel):
    hash_id: str = Field(..., min_length=1, max_length=200)
    sale_amount: Decimal = Field(..., gt=0)
    sale_id: Optional[int] = None


class GhostWalletRedeemRequest(BaseModel):
    hash_id: str = Field(..., min_length=1, max_length=200)
    amount: Decimal = Field(..., gt=0)


class VerifyPinRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=20)


class ConfigurePinsRequest(BaseModel):
    normal_pin: str = Field(..., min_length=4, max_length=20)
    duress_pin: str = Field(..., min_length=4, max_length=20)
    wipe_pin: Optional[str] = Field(default=None, min_length=4, max_length=20)


class SurgicalDeleteRequest(BaseModel):
    sale_ids: List[int] = Field(..., min_length=1, max_length=100)
    confirm_phrase: str = Field(..., min_length=1, max_length=100)


class SupplierAnalyzeRequest(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0, le=1000000)
    price_a: Decimal = Field(..., gt=0)
    price_b: Decimal = Field(..., gt=0)
    supplier_a: str = Field(default="Proveedor Factura", max_length=200)
    supplier_b: str = Field(default="Proveedor Efectivo", max_length=200)


class ExtractionPlanRequest(BaseModel):
    target_amount: Decimal = Field(..., gt=0)


class CryptoConversionRequest(BaseModel):
    amount_mxn: Decimal = Field(..., gt=0)
    stablecoin: str = Field(default="USDT", pattern=r'^[A-Z]{2,10}$')
    wallet_address: Optional[str] = Field(default=None, max_length=200)
    cover_description: Optional[str] = Field(default=None, max_length=500)


class LockdownRequest(BaseModel):
    branch_id: int = Field(..., ge=1)


class ReleaseLockdownRequest(BaseModel):
    branch_id: int = Field(..., ge=1)
    auth_code: str = Field(..., min_length=1, max_length=100)


class GhostTransferItem(BaseModel):
    product_id: int = Field(..., ge=1)
    quantity: Decimal = Field(..., gt=0)


class GhostTransferCreateRequest(BaseModel):
    origin: str = Field(..., min_length=1, max_length=200)
    destination: str = Field(..., min_length=1, max_length=200)
    items: List[GhostTransferItem] = Field(..., min_length=1, max_length=500)
    # user_id derived from JWT in endpoint, not from client
    notes: str = Field(default="", max_length=500)


class GhostTransferReceiveRequest(BaseModel):
    transfer_code: str = Field(..., min_length=1, max_length=100)
    # user_id derived from JWT in endpoint, not from client


class ShadowStockAddRequest(BaseModel):
    product_id: int = Field(..., ge=1)
    quantity: Decimal = Field(..., gt=0)
    source: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=500)


class ShadowSellRequest(BaseModel):
    product_id: int = Field(..., ge=1)
    quantity: Decimal = Field(..., gt=0)
    serie: str = 'B'


class ReconcileFiscalRequest(BaseModel):
    product_id: int = Field(..., ge=1)
    fiscal_stock: Decimal = Field(..., ge=0)


class PanicTriggerRequest(BaseModel):
    immediate: bool = False


class DeadDriveRequest(BaseModel):
    device: str = Field(..., min_length=1, max_length=100)
    confirm: str = Field(..., min_length=1, max_length=100)


class FakeScreenRequest(BaseModel):
    screen_type: str = Field(default='windows_update', pattern=r'^[a-z_]{1,50}$')


# --- Cash Extraction ---
class AddRelatedPersonRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    parentesco: str = Field(..., min_length=1, max_length=100)
    rfc: Optional[str] = Field(default=None, max_length=13)
    curp: Optional[str] = Field(default=None, max_length=18)

class CreateExtractionRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    document_type: str = Field(..., min_length=1, max_length=50)
    related_person_id: Optional[int] = None
    purpose: Optional[str] = Field(default=None, max_length=500)


# --- Cost Reconciliation ---
class RegisterPurchaseRequest(BaseModel):
    product_id: int = Field(..., ge=1)
    quantity: Decimal = Field(..., gt=0)
    unit_cost: Decimal = Field(..., gt=0)
    serie: str = Field(..., pattern=r'^[AB]$')
    supplier: Optional[str] = Field(default=None, max_length=200)
    invoice: Optional[str] = Field(default=None, max_length=100)


# --- Intercompany ---
class SelectOptimalRFCRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    original_rfc: Optional[str] = Field(default=None, max_length=13)
    branch_name: Optional[str] = Field(default=None, max_length=200)

class ProcessCrossInvoiceRequest(BaseModel):
    sale_id: int
    target_rfc: str = Field(..., min_length=12, max_length=13)
    original_rfc: str = Field(..., min_length=12, max_length=13)
    cross_concept: str = Field(..., min_length=1, max_length=500)


# --- Legal Documents ---
class DestructionActaData(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=200)
    sku: Optional[str] = Field(default=None, max_length=50)
    sat_key: Optional[str] = Field(default=None, max_length=20)
    quantity: Decimal = Field(..., gt=0)
    unit: str = Field(default="PZA", max_length=20)
    unit_cost: Decimal = Field(..., ge=0)
    total_value: Decimal = Field(..., ge=0)
    category: str = Field(default="deterioro", max_length=50)
    reason: str = Field(default="Deterioro natural", max_length=500)
    witness_name: Optional[str] = Field(default=None, max_length=200)
    supervisor_name: Optional[str] = Field(default=None, max_length=200)
    authorized_by: Optional[str] = Field(default=None, max_length=200)

class ReturnDocumentData(BaseModel):
    original_folio: Optional[str] = Field(default=None, max_length=50)
    product_name: str = Field(..., min_length=1, max_length=200)
    sku: Optional[str] = Field(default=None, max_length=50)
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    subtotal: Decimal = Field(..., ge=0)
    tax: Decimal = Field(default=Decimal("0"), ge=0)
    total: Decimal = Field(..., ge=0)
    serie: str = Field(default="A", pattern=r'^[AB]$')
    return_reason: Optional[str] = Field(default=None, max_length=500)

class SelfConsumptionVoucherItem(BaseModel):
    product: str = Field(..., min_length=1, max_length=200)
    quantity: Decimal = Field(..., gt=0)
    value: Decimal = Field(..., ge=0)
    reason: Optional[str] = Field(default=None, max_length=200)

class GenerateSelfConsumptionVoucherRequest(BaseModel):
    items: List[SelfConsumptionVoucherItem] = Field(..., min_length=1, max_length=500)
    period: Optional[str] = Field(default=None, max_length=20)


# --- Price Analytics ---
class CalculateSmartLossRequest(BaseModel):
    base_amount: Decimal = Field(..., gt=0)
    category: str = Field(default="general", max_length=50)

class BatchVarianceItem(BaseModel):
    amount: Decimal = Field(..., gt=0)
    model_config = {"extra": "forbid"}

class GenerateBatchVarianceRequest(BaseModel):
    items: List[BatchVarianceItem] = Field(..., min_length=1, max_length=1000)
    total_target: Decimal = Field(..., gt=0)


# --- Discrepancy Monitor ---
class RegisterExpenseRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    category: str = Field(..., min_length=1, max_length=100)
    payment_method: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(default=None, max_length=500)
    is_visible: bool = True


# --- RFC Rotation / Jitter ---
class TimbrarConProxyRequest(BaseModel):
    xml_data: str = Field(..., min_length=1)
    rfc: str = Field(..., min_length=12, max_length=13)
    pac_url: str = Field(..., min_length=1, max_length=500)

class ConfigureProxiesRequest(BaseModel):
    proxies: List[dict] = Field(..., min_length=1, max_length=50)

class DistributeTimbradosRequest(BaseModel):
    count: int = Field(..., gt=0, le=1000)
    hours: int = Field(default=8, gt=0, le=24)


# --- Climate Shield ---
class EvaluateDegradationRiskRequest(BaseModel):
    climate: dict
    product_category: Optional[str] = Field(default=None, max_length=100)

class GenerateShrinkageJustificationRequest(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=200)
    quantity: Decimal = Field(..., gt=0)
    category: str = Field(default="deterioro", max_length=50)
    id: Optional[int] = None


# --- Self Consumption ---
class RegisterConsumptionRequest(BaseModel):
    product_id: int = Field(..., ge=1)
    quantity: Decimal = Field(..., gt=0)
    category: str = Field(..., min_length=1, max_length=100)
    reason: Optional[str] = Field(default=None, max_length=500)
    beneficiary: Optional[str] = Field(default=None, max_length=200)

class RegisterSampleRequest(BaseModel):
    product_id: int = Field(..., ge=1)
    quantity: Decimal = Field(..., gt=0)
    recipient: str = Field(default="Cliente", max_length=200)

class RegisterEmployeeConsumptionRequest(BaseModel):
    product_id: int = Field(..., ge=1)
    quantity: Decimal = Field(..., gt=0)
    employee_name: str = Field(..., min_length=1, max_length=200)


# --- Shrinkage ---
class RegisterLossRequest(BaseModel):
    product_id: int = Field(..., ge=1)
    quantity: Decimal = Field(..., gt=0)
    reason: str = Field(..., min_length=1, max_length=500)
    category: str = Field(default="deterioro", max_length=50)
    witness_name: Optional[str] = Field(default=None, max_length=200)

class AuthorizeLossRequest(BaseModel):
    acta_number: str = Field(..., min_length=1, max_length=50)
    authorized_by: str = Field(..., min_length=1, max_length=200)


# --- Fiscal Noise ---
class GenerateNoiseTransactionRequest(BaseModel):
    rfc: Optional[str] = Field(default=None, max_length=13)

class StartDailyNoiseRequest(BaseModel):
    target: Optional[int] = Field(default=None, gt=0, le=100)
