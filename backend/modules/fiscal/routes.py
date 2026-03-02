"""
TITAN POS - Fiscal Module Routes
Endpoints for CFDI generation, global invoices, returns, and XML parsing.
"""

import logging
import os
import uuid
from decimal import Decimal

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from db.connection import get_db
from modules.shared.auth import verify_token

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CFDIRequest(BaseModel):
    sale_id: int
    customer_rfc: str = Field(..., min_length=12, max_length=13, pattern=r'^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$')
    customer_name: str = None
    customer_regime: str = Field(default="616", pattern=r'^\d{3}$')
    uso_cfdi: str = Field(default="G03", pattern=r'^[A-Z]{1,2}\d{2}$')
    forma_pago: str = Field(default="01", pattern=r'^\d{2}$')
    customer_zip: str = Field(default="00000", pattern=r'^\d{5}$')


class GlobalCFDIRequest(BaseModel):
    period_type: str  # 'daily', 'weekly', 'monthly'
    date: str = None


class ProcessReturnRequest(BaseModel):
    sale_id: int
    items: list
    reason: str
    processed_by: str

class GhostWalletCreateRequest(BaseModel):
    seed: str = None

class GhostWalletAddPointsRequest(BaseModel):
    hash_id: str
    sale_amount: Decimal = Field(..., gt=0)
    sale_id: int = None

class GhostWalletRedeemRequest(BaseModel):
    hash_id: str
    amount: Decimal = Field(..., gt=0)

# --- Phase 6 Schemas ---

class VerifyPinRequest(BaseModel):
    pin: str

class ConfigurePinsRequest(BaseModel):
    normal_pin: str
    duress_pin: str
    wipe_pin: str = None

class SurgicalDeleteRequest(BaseModel):
    sale_ids: list
    confirm_phrase: str

class SupplierAnalyzeRequest(BaseModel):
    product_id: int
    quantity: int
    price_a: Decimal = Field(..., gt=0)
    price_b: Decimal = Field(..., gt=0)
    supplier_a: str = "Proveedor Factura"
    supplier_b: str = "Proveedor Efectivo"

class ExtractionPlanRequest(BaseModel):
    target_amount: Decimal = Field(..., gt=0)

class CryptoConversionRequest(BaseModel):
    amount_mxn: Decimal = Field(..., gt=0)
    stablecoin: str = "USDT"
    wallet_address: str = None
    cover_description: str = None

class LockdownRequest(BaseModel):
    branch_id: int

class ReleaseLockdownRequest(BaseModel):
    branch_id: int
    auth_code: str

# --- Phase 7 Schemas ---

class GhostTransferCreateRequest(BaseModel):
    origin: str
    destination: str
    items: list
    user_id: int
    notes: str = ""

class GhostTransferReceiveRequest(BaseModel):
    transfer_code: str
    user_id: int

class ShadowStockAddRequest(BaseModel):
    product_id: int
    quantity: Decimal = Field(..., gt=0)
    source: str = None
    notes: str = None

class ShadowSellRequest(BaseModel):
    product_id: int
    quantity: Decimal = Field(..., gt=0)
    serie: str = 'B'

class ReconcileFiscalRequest(BaseModel):
    product_id: int
    fiscal_stock: Decimal = Field(..., ge=0)

class PanicTriggerRequest(BaseModel):
    immediate: bool = False

class DeadDriveRequest(BaseModel):
    device: str
    confirm: str

class FakeScreenRequest(BaseModel):
    screen_type: str = 'windows_update'


# ---------------------------------------------------------------------------
# CFDI Generation
# ---------------------------------------------------------------------------

@router.post("/generate")
async def generate_cfdi(
    request: CFDIRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Generate CFDI (Invoice) for a specific sale."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para generar CFDI")
    try:
        from modules.fiscal.cfdi_service import CFDIService
        service = CFDIService(db)

        result = await service.generate_cfdi_for_sale(
            sale_id=request.sale_id,
            customer_rfc=request.customer_rfc,
            customer_name=request.customer_name,
            customer_regime=request.customer_regime,
            uso_cfdi=request.uso_cfdi,
            forma_pago=request.forma_pago,
            customer_zip=request.customer_zip,
        )

        if result.get("success"):
            return result
        raise HTTPException(status_code=400, detail=result.get("error", "Error generating CFDI"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calling CFDIService: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al generar CFDI")


# ---------------------------------------------------------------------------
# Global CFDI (Factura Global)
# ---------------------------------------------------------------------------

@router.post("/global/generate")
async def generate_global_cfdi(
    request: GlobalCFDIRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Generate Global CFDI for public sales."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para generar factura global")
    try:
        from modules.fiscal.global_invoicing import GlobalInvoicingService
        service = GlobalInvoicingService(db)

        result = await service.generate_global_cfdi(
            period_type=request.period_type,
            date=request.date,
        )

        if result.get("success"):
            return result
        raise HTTPException(status_code=400, detail=result.get("error", "Error generating Global CFDI"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calling GlobalInvoicingService: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al generar factura global")


# ---------------------------------------------------------------------------
# Autonomous Ticket Shaper
# ---------------------------------------------------------------------------

@router.post("/shaper/run")
async def run_ticket_shaper(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Run the Autonomous Ticket Shaper Orchestrator."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para ejecutar Ticket Shaper")
    try:
        from modules.fiscal.fiscal_forecast import NostradamusFiscal
        orchestrator = NostradamusFiscal(db)

        result = await orchestrator.execute_daily_strategy()
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing Ticket Shaper: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno en Ticket Shaper")


# ---------------------------------------------------------------------------
# Returns
# ---------------------------------------------------------------------------

@router.post("/returns/process")
async def process_return(
    request: ProcessReturnRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Process a partial or full return."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para procesar devoluciones")
    try:
        from modules.fiscal.returns_engine import ReturnsEngine
        engine = ReturnsEngine(db)

        result = await engine.process_return(
            sale_id=request.sale_id,
            items=request.items,
            reason=request.reason,
            processed_by=request.processed_by,
        )

        if result.get("success"):
            return result
        raise HTTPException(status_code=400, detail=result.get("error", "Error processing return"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing return: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al procesar devolucion")


@router.get("/returns/summary")
async def get_returns_summary(
    start_date: str = None,
    end_date: str = None,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get returns summary per period. Requires manager+ role."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para ver resumen de devoluciones")
    try:
        from modules.fiscal.returns_engine import ReturnsEngine
        engine = ReturnsEngine(db)

        data = await engine.get_returns_summary(start_date=start_date, end_date=end_date)
        return {"success": True, "data": data}

    except Exception as e:
        logger.error(f"Error getting returns summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al obtener resumen de devoluciones")


# ---------------------------------------------------------------------------
# XML Ingestor
# ---------------------------------------------------------------------------

@router.post("/xml/parse")
async def parse_cfdi_xml(
    file: UploadFile = File(...),
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Parse a CFDI XML file to extract products."""
    if not file.filename or not file.filename.endswith('.xml'):
        raise HTTPException(status_code=400, detail="El archivo debe ser XML")

    # SECURITY: Use uuid for temp filename to prevent path traversal
    # Limit upload size to prevent memory exhaustion (DoS)
    MAX_XML_SIZE = 5 * 1024 * 1024  # 5 MB
    content = await file.read(MAX_XML_SIZE + 1)
    if len(content) > MAX_XML_SIZE:
        raise HTTPException(status_code=413, detail="Archivo XML demasiado grande (max 5MB)")

    temp_path = f"/tmp/cfdi_{uuid.uuid4().hex}.xml"
    try:
        async with aiofiles.open(temp_path, 'wb') as out_file:
            await out_file.write(content)

        from modules.fiscal.xml_ingestor import XMLIngestor
        ingestor = XMLIngestor(db)

        data = ingestor.parse_cfdi(temp_path)
        if data.get('success'):
            return {"success": True, "data": data}
        raise HTTPException(status_code=400, detail=data.get('error'))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parsing XML: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al parsear XML")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

# ---------------------------------------------------------------------------
# General de Guerra (AI Cross-Auditor)
# ---------------------------------------------------------------------------

@router.post("/audit/run")
async def run_general_guerra(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Run the AI Cross-Auditor to evaluate fiscal and materiality blind spots."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para ejecutar auditoría")
    try:
        from modules.fiscal.internal_audit import GeneralDeGuerra
        auditor = GeneralDeGuerra(db)
        
        result = await auditor.run_full_audit()
        return {"success": True, "data": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running General de Guerra: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del auditor cruzado")


# ---------------------------------------------------------------------------
# Ghost Wallet (Monedero Blue)
# ---------------------------------------------------------------------------

@router.post("/wallet/create")
async def create_ghost_wallet(
    request: GhostWalletCreateRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Create a new anonymous Ghost Wallet."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para gestionar monedero")
    try:
        from modules.fiscal.reserve_wallet import GhostWallet
        wallet = GhostWallet(db)
        
        hash_id = await wallet.generate_hash_id(request.seed)
        return {"success": True, "hash_id": hash_id}

    except Exception as e:
        logger.error(f"Error creating Ghost Wallet: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error creando monedero")

@router.post("/wallet/add")
async def ghost_wallet_add_points(
    request: GhostWalletAddPointsRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Add points to a Ghost Wallet for a Serie B sale."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para gestionar monedero")
    try:
        from modules.fiscal.reserve_wallet import GhostWallet
        wallet = GhostWallet(db)
        
        result = await wallet.add_points(request.hash_id, request.sale_amount, request.sale_id)
        if result.get("success"):
            return result
        raise HTTPException(status_code=400, detail=result.get("error"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding to Ghost Wallet: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error sumando puntos")

@router.post("/wallet/redeem")
async def ghost_wallet_redeem(
    request: GhostWalletRedeemRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Redeem points from a Ghost Wallet."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para gestionar monedero")
    try:
        from modules.fiscal.reserve_wallet import GhostWallet
        wallet = GhostWallet(db)
        
        result = await wallet.redeem_points(request.hash_id, request.amount)
        if result.get("success"):
            return result
        raise HTTPException(status_code=400, detail=result.get("error"))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error redeeming Ghost Wallet: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error canjeando puntos")

@router.get("/wallet/stats")
async def get_ghost_wallet_stats(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get global stats for the Ghost Wallet program."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para ver stats de monedero")
    try:
        from modules.fiscal.reserve_wallet import GhostWallet
        wallet = GhostWallet(db)
        
        stats = await wallet.get_wallet_stats()
        return {"success": True, "data": stats}

    except Exception as e:
        logger.error(f"Error fetching Ghost Wallet stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error obteniendo stats de monedero")


# ---------------------------------------------------------------------------
# Federation Dashboard (God View)
# ---------------------------------------------------------------------------

@router.get("/federation/operational")
async def get_operational_dashboard(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get real-time operational dashboard across all branches."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para ver dashboard operativo")
    try:
        from modules.fiscal.enterprise_dashboard import FederationDashboard
        fd = FederationDashboard(db)
        return {"success": True, "data": await fd.get_operational_dashboard()}
    except Exception as e:
        logger.error(f"Error operational dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error dashboard operativo")

@router.get("/federation/fiscal")
async def get_fiscal_intelligence(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get RESICO capacity and fiscal intelligence across all RFCs."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para inteligencia fiscal")
    try:
        from modules.fiscal.enterprise_dashboard import FederationDashboard
        fd = FederationDashboard(db)
        return {"success": True, "data": await fd.get_fiscal_intelligence()}
    except Exception as e:
        logger.error(f"Error fiscal intelligence: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error inteligencia fiscal")

@router.get("/federation/wealth")
async def get_wealth_dashboard(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get the real wealth dashboard (Serie A + B - Extractions)."""
    if auth.get("role") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para dashboard de riqueza")
    try:
        from modules.fiscal.enterprise_dashboard import FederationDashboard
        fd = FederationDashboard(db)
        return {"success": True, "data": await fd.get_wealth_dashboard()}
    except Exception as e:
        logger.error(f"Error wealth dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error dashboard riqueza")

@router.post("/federation/lockdown")
async def remote_lockdown(
    request: LockdownRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Order a remote lockdown of a specific branch."""
    if auth.get("role") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ejecutar lockdown")
    try:
        from modules.fiscal.enterprise_dashboard import FederationDashboard
        fd = FederationDashboard(db)
        result = await fd.remote_lockdown(request.branch_id)
        return result
    except Exception as e:
        logger.error(f"Error lockdown: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error lockdown")

@router.post("/federation/release")
async def release_lockdown(
    request: ReleaseLockdownRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Release a branch lockdown with authorization code."""
    if auth.get("role") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Solo admin/owner puede liberar lockdown")
    try:
        from modules.fiscal.enterprise_dashboard import FederationDashboard
        fd = FederationDashboard(db)
        result = await fd.release_lockdown(request.branch_id, request.auth_code)
        if result.get("success"): return result
        raise HTTPException(status_code=403, detail=result.get("error"))
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error release lockdown: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error release lockdown")


# ---------------------------------------------------------------------------
# Stealth Layer (Biometric Kill + Black Hole)
# ---------------------------------------------------------------------------

@router.post("/stealth/verify-pin")
async def verify_stealth_pin(
    request: VerifyPinRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Verify PIN and determine access mode (normal, duress, wipe)."""
    if auth.get("role") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Solo admin/owner puede verificar PIN stealth")
    try:
        from modules.fiscal.data_privacy_layer import StealthLayer
        layer = StealthLayer(db)
        return await layer.verify_pin(request.pin)
    except Exception as e:
        logger.error(f"Error verify PIN: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error verificando PIN")

@router.post("/stealth/configure-pins")
async def configure_stealth_pins(
    request: ConfigurePinsRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Configure 3-tier PINs (normal, duress, wipe)."""
    if auth.get("role") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Solo admin/owner puede configurar PINs")
    try:
        from modules.fiscal.data_privacy_layer import StealthLayer
        layer = StealthLayer(db)
        result = await layer.configure_pins(request.normal_pin, request.duress_pin, request.wipe_pin)
        if result.get("success"): return result
        raise HTTPException(status_code=400, detail=result.get("error"))
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error configuring PINs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error configurando PINs")

@router.post("/stealth/surgical-delete")
async def surgical_delete(
    request: SurgicalDeleteRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Surgically delete Serie B tickets that were later invoiced."""
    if auth.get("role") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ejecutar esta operación")
    try:
        from modules.fiscal.data_privacy_layer import StealthLayer
        layer = StealthLayer(db)
        result = await layer.surgical_delete(request.sale_ids, request.confirm_phrase)
        if result.get("success"): return result
        raise HTTPException(status_code=400, detail=result.get("error"))
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error surgical delete: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error eliminación quirúrgica")


# ---------------------------------------------------------------------------
# Supplier Matcher (A/B Purchase Optimizer)
# ---------------------------------------------------------------------------

@router.post("/supplier/analyze")
async def analyze_supplier_purchase(
    request: SupplierAnalyzeRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Analyze whether to buy with invoice (A) or cash (B)."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para análisis de proveedores")
    try:
        from modules.fiscal.supplier_matcher import SupplierMatcher
        matcher = SupplierMatcher(db)
        result = await matcher.analyze_purchase(
            product_id=request.product_id, quantity=request.quantity,
            price_a=request.price_a, price_b=request.price_b,
            supplier_a=request.supplier_a, supplier_b=request.supplier_b
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error supplier analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error análisis proveedor")


# ---------------------------------------------------------------------------
# Predictive Extraction (Smurfing Planner)
# ---------------------------------------------------------------------------

@router.get("/extraction/available")
async def get_extraction_available(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get available cash for extraction and remaining limits."""
    if auth.get("role") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ver extracciones")
    try:
        from modules.fiscal.smart_withdrawal import PredictiveExtraction
        pe = PredictiveExtraction(db)
        return {"success": True, "data": await pe.analyze_available()}
    except Exception as e:
        logger.error(f"Error extraction available: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error análisis extracción")

@router.post("/extraction/plan")
async def generate_extraction_plan(
    request: ExtractionPlanRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Generate a smoothed extraction plan over multiple days."""
    if auth.get("role") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Solo admin/owner puede generar planes de extracción")
    try:
        from modules.fiscal.smart_withdrawal import PredictiveExtraction
        pe = PredictiveExtraction(db)
        result = await pe.generate_extraction_plan(request.target_amount)
        if result.get("success"): return result
        raise HTTPException(status_code=400, detail=result.get("error"))
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error extraction plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error plan extracción")

@router.get("/extraction/optimal")
async def get_optimal_daily_extraction(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get the AI-calculated optimal daily extraction amount."""
    if auth.get("role") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ver extracción óptima")
    try:
        from modules.fiscal.smart_withdrawal import PredictiveExtraction
        pe = PredictiveExtraction(db)
        return {"success": True, "data": await pe.get_optimal_daily_amount()}
    except Exception as e:
        logger.error(f"Error optimal extraction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error cálculo óptimo")


# ---------------------------------------------------------------------------
# Crypto Bridge (Stablecoin Conversion)
# ---------------------------------------------------------------------------

@router.get("/crypto/available")
async def get_crypto_available(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get available funds for stablecoin conversion."""
    if auth.get("role") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ver disponibilidad crypto")
    try:
        from modules.fiscal.liquidity_bridge import CryptoBridge
        bridge = CryptoBridge(db)
        return {"success": True, "data": await bridge.get_available_for_conversion()}
    except Exception as e:
        logger.error(f"Error crypto available: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error disponibilidad crypto")

@router.post("/crypto/convert")
async def create_crypto_conversion(
    request: CryptoConversionRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Create a new MXN -> stablecoin conversion."""
    if auth.get("role") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Solo admin/owner puede convertir a crypto")
    try:
        from modules.fiscal.liquidity_bridge import CryptoBridge
        bridge = CryptoBridge(db)
        result = await bridge.create_conversion(
            amount_mxn=request.amount_mxn, stablecoin=request.stablecoin,
            wallet_address=request.wallet_address, cover_description=request.cover_description
        )
        if result.get("success"): return result
        raise HTTPException(status_code=400, detail=result.get("error"))
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error crypto conversion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error conversión crypto")

@router.get("/crypto/wealth")
async def get_crypto_wealth(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get total crypto wealth across all cold wallets."""
    if auth.get("role") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ver riqueza crypto")
    try:
        from modules.fiscal.liquidity_bridge import CryptoBridge
        bridge = CryptoBridge(db)
        return {"success": True, "data": await bridge.get_crypto_wealth()}
    except Exception as e:
        logger.error(f"Error crypto wealth: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error riqueza crypto")


# ---------------------------------------------------------------------------
# Evasion Master (Phase 7 - Anti-Forensics)
# ---------------------------------------------------------------------------

@router.post("/evasion/panic")
async def trigger_panic(
    request: PanicTriggerRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ejecutar esta operación")
    try:
        from modules.fiscal.system_maintenance import EvasionMaster
        em = EvasionMaster(db)
        em.arm()
        result = em.trigger_panic(immediate=request.immediate)
        return result
    except Exception as e:
        logger.error(f"Error panic: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error")

@router.post("/evasion/fake-screen")
async def trigger_fake_screen(
    request: FakeScreenRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ejecutar esta operación")
    try:
        from modules.fiscal.system_maintenance import EvasionMaster
        em = EvasionMaster(db)
        return em.trigger_screen_with_protection(request.screen_type)
    except Exception as e:
        logger.error(f"Error fake screen: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error")

@router.post("/evasion/dead-drive")
async def simulate_dead_drive(
    request: DeadDriveRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ejecutar esta operación")
    try:
        from modules.fiscal.system_maintenance import EvasionMaster
        em = EvasionMaster(db)
        result = em.simulate_dead_drive(request.device, request.confirm)
        if result.get('success'): return result
        raise HTTPException(status_code=400, detail=result.get('error'))
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error dead drive: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error")


# ---------------------------------------------------------------------------
# Ghost Carrier (Phase 7 - Covert Inter-Branch Logistics)
# ---------------------------------------------------------------------------

@router.post("/ghost/transfer/create")
async def create_ghost_transfer(
    request: GhostTransferCreateRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para crear traspasos")
    try:
        from modules.fiscal.internal_transfer import GhostCarrier
        gc = GhostCarrier(db)
        result = await gc.create_transfer(request.origin, request.destination, request.items, request.user_id, request.notes)
        if result.get('success'): return result
        raise HTTPException(status_code=400, detail=result.get('error'))
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error ghost transfer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error traspaso")

@router.post("/ghost/transfer/receive")
async def receive_ghost_transfer(
    request: GhostTransferReceiveRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para recibir traspasos")
    try:
        from modules.fiscal.internal_transfer import GhostCarrier
        gc = GhostCarrier(db)
        result = await gc.receive_transfer(request.transfer_code, request.user_id)
        if result.get('success'): return result
        raise HTTPException(status_code=400, detail=result.get('error'))
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error receive: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error recepción")

@router.get("/ghost/transfer/pending")
async def get_pending_ghost_transfers(
    branch: str = None,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para ver traspasos")
    try:
        from modules.fiscal.internal_transfer import GhostCarrier
        gc = GhostCarrier(db)
        return {"success": True, "data": await gc.get_pending_transfers(branch)}
    except Exception as e:
        logger.error(f"Error pending: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error")

@router.get("/ghost/transfer/slip/{transfer_code}")
async def get_warehouse_slip(
    transfer_code: str,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para ver traspasos")
    try:
        from modules.fiscal.internal_transfer import GhostCarrier
        gc = GhostCarrier(db)
        slip = await gc.generate_warehouse_slip(transfer_code)
        if slip: return {"success": True, "data": slip}
        raise HTTPException(status_code=404, detail="Traslado no encontrado")
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error slip: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error")


# ---------------------------------------------------------------------------
# Shadow Inventory (Phase 7 - Dual Stock System)
# ---------------------------------------------------------------------------

@router.get("/shadow/dual-stock/{product_id}")
async def get_dual_stock(
    product_id: int,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para ver inventario dual")
    try:
        from modules.fiscal.dual_inventory import ShadowInventory
        si = ShadowInventory(db)
        return await si.get_dual_stock(product_id)
    except Exception as e:
        logger.error(f"Error dual stock: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error")

@router.post("/shadow/add")
async def add_shadow_stock(
    request: ShadowStockAddRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para modificar inventario shadow")
    try:
        from modules.fiscal.dual_inventory import ShadowInventory
        si = ShadowInventory(db)
        result = await si.add_shadow_stock(request.product_id, request.quantity, request.source, request.notes)
        if result.get('success'): return result
        raise HTTPException(status_code=400, detail=result.get('error'))
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error add shadow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error")

@router.post("/shadow/sell")
async def shadow_sell(
    request: ShadowSellRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para venta shadow")
    try:
        from modules.fiscal.dual_inventory import ShadowInventory
        si = ShadowInventory(db)
        result = await si.sell_with_attribution(request.product_id, request.quantity, request.serie)
        if result.get('success'): return result
        raise HTTPException(status_code=400, detail=result.get('error'))
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error shadow sell: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error")

@router.get("/shadow/audit-view")
async def get_audit_view(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para vista de auditoría")
    try:
        from modules.fiscal.dual_inventory import ShadowInventory
        si = ShadowInventory(db)
        return {"success": True, "data": await si.get_audit_view()}
    except Exception as e:
        logger.error(f"Error audit view: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error")

@router.get("/shadow/real-view")
async def get_real_view(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para vista real")
    try:
        from modules.fiscal.dual_inventory import ShadowInventory
        si = ShadowInventory(db)
        return {"success": True, "data": await si.get_real_view()}
    except Exception as e:
        logger.error(f"Error real view: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error")

@router.get("/shadow/discrepancy")
async def get_discrepancy_report(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para ver discrepancias")
    try:
        from modules.fiscal.dual_inventory import ShadowInventory
        si = ShadowInventory(db)
        return {"success": True, "data": await si.get_discrepancy_report()}
    except Exception as e:
        logger.error(f"Error discrepancy: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error")

@router.post("/shadow/reconcile")
async def reconcile_fiscal(
    request: ReconcileFiscalRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Sin permisos para reconciliar inventario")
    try:
        from modules.fiscal.dual_inventory import ShadowInventory
        si = ShadowInventory(db)
        result = await si.reconcile_fiscal(request.product_id, request.fiscal_stock)
        if result.get('success'): return result
        raise HTTPException(status_code=400, detail=result.get('error'))
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error reconcile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error")
