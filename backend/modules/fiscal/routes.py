"""
TITAN POS - Fiscal Module Routes
Endpoints for CFDI generation, global invoices, returns, and XML parsing.
"""

import logging
import os
import uuid

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from db.connection import get_db
from modules.shared.auth import verify_token

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CFDIRequest(BaseModel):
    sale_id: int
    customer_rfc: str
    customer_name: str = None
    customer_regime: str = "616"
    uso_cfdi: str = "G03"
    forma_pago: str = "01"
    customer_zip: str = "00000"


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
    sale_amount: float
    sale_id: int = None

class GhostWalletRedeemRequest(BaseModel):
    hash_id: str
    amount: float

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
    price_a: float
    price_b: float
    supplier_a: str = "Proveedor Factura"
    supplier_b: str = "Proveedor Efectivo"

class ExtractionPlanRequest(BaseModel):
    target_amount: float

class CryptoConversionRequest(BaseModel):
    amount_mxn: float
    stablecoin: str = "USDT"
    wallet_address: str = None
    cover_description: str = None

class LockdownRequest(BaseModel):
    branch_id: int

class ReleaseLockdownRequest(BaseModel):
    branch_id: int
    auth_code: str


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
    try:
        from modules.fiscal.nostradamus_fiscal import NostradamusFiscal
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
    """Get returns summary per period."""
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
    temp_path = f"/tmp/cfdi_{uuid.uuid4().hex}.xml"
    try:
        async with aiofiles.open(temp_path, 'wb') as out_file:
            content = await file.read()
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
    try:
        from modules.fiscal.general_guerra import GeneralDeGuerra
        auditor = GeneralDeGuerra(db)
        
        result = await auditor.run_full_audit()
        return {"success": True, "report": result}

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
    try:
        from modules.fiscal.ghost_wallet import GhostWallet
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
    try:
        from modules.fiscal.ghost_wallet import GhostWallet
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
    try:
        from modules.fiscal.ghost_wallet import GhostWallet
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
    try:
        from modules.fiscal.ghost_wallet import GhostWallet
        wallet = GhostWallet(db)
        
        stats = await wallet.get_wallet_stats()
        return {"success": True, "stats": stats}

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
    try:
        from modules.fiscal.federation_dashboard import FederationDashboard
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
    try:
        from modules.fiscal.federation_dashboard import FederationDashboard
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
    try:
        from modules.fiscal.federation_dashboard import FederationDashboard
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
    try:
        from modules.fiscal.federation_dashboard import FederationDashboard
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
    try:
        from modules.fiscal.federation_dashboard import FederationDashboard
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
    db=Depends(get_db),
):
    """Verify PIN and determine access mode (normal, duress, wipe)."""
    try:
        from modules.fiscal.stealth_layer import StealthLayer
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
    try:
        from modules.fiscal.stealth_layer import StealthLayer
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
    try:
        from modules.fiscal.stealth_layer import StealthLayer
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
    try:
        from modules.fiscal.supplier_matcher import SupplierMatcher
        matcher = SupplierMatcher(db)
        result = await matcher.analyze_purchase(
            product_id=request.product_id, quantity=request.quantity,
            price_a=request.price_a, price_b=request.price_b,
            supplier_a=request.supplier_a, supplier_b=request.supplier_b
        )
        return {"success": True, "analysis": result}
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
    try:
        from modules.fiscal.predictive_extraction import PredictiveExtraction
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
    try:
        from modules.fiscal.predictive_extraction import PredictiveExtraction
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
    try:
        from modules.fiscal.predictive_extraction import PredictiveExtraction
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
    try:
        from modules.fiscal.crypto_bridge import CryptoBridge
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
    try:
        from modules.fiscal.crypto_bridge import CryptoBridge
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
    try:
        from modules.fiscal.crypto_bridge import CryptoBridge
        bridge = CryptoBridge(db)
        return {"success": True, "data": await bridge.get_crypto_wealth()}
    except Exception as e:
        logger.error(f"Error crypto wealth: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error riqueza crypto")
