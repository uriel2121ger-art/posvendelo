"""
POSVENDELO - Fiscal Module Routes
Endpoints for CFDI generation, global invoices, returns, and XML parsing.
"""

import asyncio
import logging
import os
import tempfile
from decimal import Decimal

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from typing import List, Optional

from starlette.requests import Request

from db.connection import get_db
from modules.shared.auth import verify_token, get_user_id
from modules.shared.constants import PRIVILEGED_ROLES, OWNER_ROLES
from modules.shared.rate_limit import check_pin_rate_limit
from modules.fiscal.schemas import (
    CFDIRequest, GlobalCFDIRequest, ReturnItem, ProcessReturnRequest,
    GhostWalletCreateRequest, GhostWalletAddPointsRequest, GhostWalletRedeemRequest,
    VerifyPinRequest, ConfigurePinsRequest, SurgicalDeleteRequest,
    SupplierAnalyzeRequest, ExtractionPlanRequest, CryptoConversionRequest,
    LockdownRequest, ReleaseLockdownRequest, GhostTransferItem,
    GhostTransferCreateRequest, GhostTransferReceiveRequest,
    ShadowStockAddRequest, ShadowSellRequest, ReconcileFiscalRequest,
    PanicTriggerRequest, DeadDriveRequest, FakeScreenRequest,
    # Cash Extraction
    AddRelatedPersonRequest, CreateExtractionRequest,
    # Cost Reconciliation
    RegisterPurchaseRequest,
    # Intercompany
    SelectOptimalRFCRequest, ProcessCrossInvoiceRequest,
    # Legal Documents
    DestructionActaData, ReturnDocumentData, SelfConsumptionVoucherItem,
    GenerateSelfConsumptionVoucherRequest,
    # Price Analytics
    CalculateSmartLossRequest, BatchVarianceItem, GenerateBatchVarianceRequest,
    # Discrepancy Monitor
    RegisterExpenseRequest,
    # RFC Rotation / Jitter
    TimbrarConProxyRequest, ConfigureProxiesRequest, DistributeTimbradosRequest,
    # Climate Shield
    EvaluateDegradationRiskRequest, GenerateShrinkageJustificationRequest,
    # Self Consumption
    RegisterConsumptionRequest, RegisterSampleRequest, RegisterEmployeeConsumptionRequest,
    # Shrinkage
    RegisterLossRequest, AuthorizeLossRequest,
    # Fiscal Noise
    GenerateNoiseTransactionRequest, StartDailyNoiseRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()


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
    if auth.get("role") not in PRIVILEGED_ROLES:
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
        raise HTTPException(status_code=400, detail="Error al procesar CFDI")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calling CFDIService: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al generar CFDI")


@router.get("/sales-pending-invoice")
async def get_sales_pending_invoice(
    branch_id: int = 1,
    limit: int = 100,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Lista ventas con requiere_factura=true que aún no tienen CFDI (para priorizar facturación)."""
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver ventas pendientes de factura")
    try:
        rows = await db.fetch(
            """
            SELECT s.id, s.folio_visible, s.total, s.timestamp, s.customer_id
            FROM sales s
            LEFT JOIN cfdis c ON c.sale_id = s.id
            WHERE s.requiere_factura = true AND c.id IS NULL
              AND COALESCE(s.status, 'completed') != 'cancelled'
              AND s.branch_id = :branch_id
            ORDER BY s.timestamp DESC
            LIMIT :limit
            """,
            {"branch_id": branch_id, "limit": min(limit, 200)},
        )
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    except Exception as e:
        err_msg = str(e).lower()
        if "requiere_factura" in err_msg or "column" in err_msg and "does not exist" in err_msg:
            logger.warning("sales.requiere_factura no existe (ejecutar migración 042); devolviendo lista vacía")
            return {"success": True, "data": []}
        logger.error(f"Error listing sales pending invoice: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al listar ventas pendientes de factura")


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
    if auth.get("role") not in PRIVILEGED_ROLES:
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
        raise HTTPException(status_code=400, detail=result.get("error", "Error al generar CFDI global"))

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
    if auth.get("role") not in PRIVILEGED_ROLES:
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
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para procesar devoluciones")
    try:
        from modules.fiscal.returns_engine import ReturnsEngine
        engine = ReturnsEngine(db)

        result = await engine.process_return(
            sale_id=request.sale_id,
            items=request.items,
            reason=request.reason,
            processed_by=str(get_user_id(auth)),
        )

        if result.get("success"):
            return result
        raise HTTPException(status_code=400, detail="Error al procesar devolución")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing return: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al procesar devolución")


@router.get("/returns/summary")
async def get_returns_summary(
    start_date: str = None,
    end_date: str = None,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get returns summary per period. Requires manager+ role."""
    if auth.get("role") not in PRIVILEGED_ROLES:
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
    """Parse a CFDI XML file to extract products. Requires defusedxml (see docs/referencia/PARSEAR_XML_FISCAL.md)."""
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para parsear XML fiscal")
    if not file.filename or not file.filename.lower().endswith(".xml"):
        raise HTTPException(status_code=400, detail="El archivo debe ser XML")

    MAX_XML_SIZE = 5 * 1024 * 1024  # 5 MB
    content = await file.read(MAX_XML_SIZE + 1)
    if len(content) > MAX_XML_SIZE:
        raise HTTPException(status_code=413, detail="Archivo XML demasiado grande (max 5MB)")

    fd, temp_path = tempfile.mkstemp(suffix=".xml", prefix="cfdi_")
    os.close(fd)
    try:
        async with aiofiles.open(temp_path, "wb") as out_file:
            await out_file.write(content)

        try:
            from modules.fiscal.xml_ingestor import XMLIngestor
        except ImportError as e:
            if "defusedxml" in str(e).lower():
                raise HTTPException(
                    status_code=503,
                    detail="Requisito no cumplido: instalar defusedxml. Ejecuta en backend: pip install -r requirements.txt (ver docs/referencia/PARSEAR_XML_FISCAL.md)",
                ) from e
            raise

        ingestor = XMLIngestor(db)
        data = ingestor.parse_cfdi(temp_path)
        if data.get("success"):
            return {"success": True, "data": data}
        raise HTTPException(
            status_code=400,
            detail=data.get("error", "Error al parsear XML"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parsing XML: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al parsear XML")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

# ---------------------------------------------------------------------------
# General de Guerra (AI Cross-Auditor)
# ---------------------------------------------------------------------------

@router.post("/audit/run")
async def run_general_guerra(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Run the AI Cross-Auditor to evaluate fiscal and materiality blind spots."""
    if auth.get("role") not in PRIVILEGED_ROLES:
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
    if auth.get("role") not in PRIVILEGED_ROLES:
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
    if auth.get("role") not in PRIVILEGED_ROLES:
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
    if auth.get("role") not in PRIVILEGED_ROLES:
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
    if auth.get("role") not in PRIVILEGED_ROLES:
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
    if auth.get("role") not in PRIVILEGED_ROLES:
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
    if auth.get("role") not in PRIVILEGED_ROLES:
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
    if auth.get("role") not in OWNER_ROLES:
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
    if auth.get("role") not in OWNER_ROLES:
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
    if auth.get("role") not in OWNER_ROLES:
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
    http_request: Request,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Verify PIN and determine access mode (normal, duress, wipe)."""
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede verificar PIN stealth")
    # Rate limit PIN attempts to prevent brute-force
    client_ip = http_request.client.host if http_request.client else "127.0.0.1"
    check_pin_rate_limit(client_ip)
    try:
        from modules.fiscal.data_privacy_layer import StealthLayer
        layer = StealthLayer(db)
        return await layer.verify_pin(request.pin)
    except HTTPException:
        raise
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
    if auth.get("role") not in OWNER_ROLES:
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
    if auth.get("role") not in OWNER_ROLES:
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
    if auth.get("role") not in PRIVILEGED_ROLES:
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
    if auth.get("role") not in OWNER_ROLES:
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
    if auth.get("role") not in OWNER_ROLES:
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
    if auth.get("role") not in OWNER_ROLES:
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
    if auth.get("role") not in OWNER_ROLES:
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
    if auth.get("role") not in OWNER_ROLES:
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
    if auth.get("role") not in OWNER_ROLES:
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
    if auth.get("role") not in OWNER_ROLES:
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
    if auth.get("role") not in OWNER_ROLES:
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
    if auth.get("role") not in OWNER_ROLES:
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
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para crear traspasos")
    try:
        from modules.fiscal.internal_transfer import GhostCarrier
        gc = GhostCarrier(db)
        result = await gc.create_transfer(request.origin, request.destination, request.items, get_user_id(auth), request.notes)
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
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para recibir traspasos")
    try:
        from modules.fiscal.internal_transfer import GhostCarrier
        gc = GhostCarrier(db)
        result = await gc.receive_transfer(request.transfer_code, get_user_id(auth))
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
    if auth.get("role") not in PRIVILEGED_ROLES:
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
    if auth.get("role") not in PRIVILEGED_ROLES:
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
    if auth.get("role") not in PRIVILEGED_ROLES:
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
    if auth.get("role") not in PRIVILEGED_ROLES:
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
    if auth.get("role") not in PRIVILEGED_ROLES:
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
    if auth.get("role") not in PRIVILEGED_ROLES:
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
    if auth.get("role") not in PRIVILEGED_ROLES:
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
    if auth.get("role") not in PRIVILEGED_ROLES:
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
    if auth.get("role") not in PRIVILEGED_ROLES:
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


# ---------------------------------------------------------------------------
# Section 15 — Cash Extraction
# ---------------------------------------------------------------------------

@router.post("/cash-extraction/related-person")
async def add_related_person(
    request: AddRelatedPersonRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede gestionar personas relacionadas")
    try:
        from modules.fiscal.cash_flow_manager import CashExtractionEngine
        engine = CashExtractionEngine(db)
        result = await engine.add_related_person(
            name=request.name, parentesco=request.parentesco,
            rfc=request.rfc, curp=request.curp,
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error add related person: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al agregar persona relacionada")


@router.get("/cash-extraction/balance")
async def get_serie_b_balance(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ver balance Serie B")
    try:
        from modules.fiscal.cash_flow_manager import CashExtractionEngine
        engine = CashExtractionEngine(db)
        result = await engine.get_serie_b_balance()
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get serie B balance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener balance Serie B")


@router.post("/cash-extraction/create")
async def create_extraction(
    request: CreateExtractionRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede crear extracciones")
    try:
        from modules.fiscal.cash_flow_manager import CashExtractionEngine
        engine = CashExtractionEngine(db)
        result = await engine.create_extraction(
            amount=request.amount,
            document_type=request.document_type,
            related_person_id=request.related_person_id,
            purpose=request.purpose,
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error create extraction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al crear extracción")


@router.get("/cash-extraction/contract/{extraction_id}")
async def get_extraction_contract(
    extraction_id: int,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ver contratos de extracción")
    try:
        from modules.fiscal.cash_flow_manager import CashExtractionEngine
        engine = CashExtractionEngine(db)
        result = await engine.generate_contract_text(extraction_id)
        return {"success": True, "data": {"text": result}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get extraction contract: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al generar contrato de extracción")


@router.get("/cash-extraction/annual-summary")
async def get_extraction_annual_summary(
    year: Optional[int] = None,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ver resumen anual")
    try:
        from modules.fiscal.cash_flow_manager import CashExtractionEngine
        engine = CashExtractionEngine(db)
        result = await engine.get_annual_summary(year=year)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get annual summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener resumen anual")


# ---------------------------------------------------------------------------
# Section 16 — Cost Reconciliation
# ---------------------------------------------------------------------------

@router.post("/cost/purchase")
async def register_purchase(
    request: RegisterPurchaseRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para registrar compras")
    try:
        from modules.fiscal.cost_reconciliation import SmartMerge
        engine = SmartMerge(db)
        result = await engine.register_purchase(
            product_id=request.product_id,
            quantity=request.quantity,
            unit_cost=request.unit_cost,
            serie=request.serie,
            supplier=request.supplier,
            invoice=request.invoice,
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error register purchase: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al registrar compra")


@router.get("/cost/dual-view/{product_id}")
async def get_dual_cost_view(
    product_id: int,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver costos duales")
    try:
        from modules.fiscal.cost_reconciliation import SmartMerge
        engine = SmartMerge(db)
        result = await engine.get_dual_cost_view(product_id)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get dual cost view: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener vista dual de costos")


@router.get("/cost/fiscal/{product_id}")
async def get_fiscal_cost(
    product_id: int,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver costo fiscal")
    try:
        from modules.fiscal.cost_reconciliation import SmartMerge
        engine = SmartMerge(db)
        result = await engine.get_fiscal_cost(product_id)
        return {"success": True, "data": {"fiscal_cost": result}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get fiscal cost: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener costo fiscal")


@router.get("/cost/real/{product_id}")
async def get_real_cost(
    product_id: int,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver costo real")
    try:
        from modules.fiscal.cost_reconciliation import SmartMerge
        engine = SmartMerge(db)
        result = await engine.get_real_cost(product_id)
        return {"success": True, "data": {"real_cost": result}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get real cost: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener costo real")


@router.get("/cost/profit/{sale_id}")
async def calculate_fiscal_vs_real_profit(
    sale_id: int,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver utilidad fiscal vs real")
    try:
        from modules.fiscal.cost_reconciliation import SmartMerge
        engine = SmartMerge(db)
        result = await engine.calculate_fiscal_vs_real_profit(sale_id)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculate profit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al calcular utilidad")


@router.get("/cost/global-report")
async def get_global_cost_report(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver reporte global de costos")
    try:
        from modules.fiscal.cost_reconciliation import SmartMerge
        engine = SmartMerge(db)
        result = await engine.get_global_cost_report()
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get global cost report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener reporte global de costos")


# ---------------------------------------------------------------------------
# Section 17 — Fiscal Dashboard
# ---------------------------------------------------------------------------

@router.get("/fiscal-dashboard/data")
async def get_fiscal_dashboard_data(
    year: Optional[int] = None,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver dashboard fiscal")
    try:
        from modules.fiscal.fiscal_dashboard import FiscalDashboard
        dashboard = FiscalDashboard(db)
        result = await dashboard.get_dashboard_data(year=year)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get fiscal dashboard data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener datos del dashboard fiscal")


@router.get("/fiscal-dashboard/smart-selection")
async def get_smart_global_selection(
    max_amount: Optional[Decimal] = None,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver selección inteligente")
    try:
        from modules.fiscal.fiscal_dashboard import FiscalDashboard
        dashboard = FiscalDashboard(db)
        result = await dashboard.get_smart_global_selection(
            max_amount=max_amount
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get smart global selection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener selección inteligente")


# ---------------------------------------------------------------------------
# Section 18 — Intercompany Billing
# ---------------------------------------------------------------------------

@router.post("/intercompany/select-rfc")
async def select_optimal_rfc(
    request: SelectOptimalRFCRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede seleccionar RFC óptimo")
    try:
        from modules.fiscal.intercompany_billing import CrossBranchBilling
        billing = CrossBranchBilling(db)
        result = await billing.select_optimal_rfc_with_facade(
            amount=request.amount,
            original_rfc=request.original_rfc,
            branch_name=request.branch_name,
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error select optimal RFC: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al seleccionar RFC óptimo")


@router.post("/intercompany/process-cross")
async def process_cross_invoice(
    request: ProcessCrossInvoiceRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede procesar factura cruzada")
    try:
        from modules.fiscal.intercompany_billing import CrossBranchBilling
        billing = CrossBranchBilling(db)
        result = await billing.process_cross_invoice(
            sale_id=request.sale_id,
            target_rfc=request.target_rfc,
            original_rfc=request.original_rfc,
            cross_concept=request.cross_concept,
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error process cross invoice: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al procesar factura cruzada")


# ---------------------------------------------------------------------------
# Section 19 — Legal Documents
# ---------------------------------------------------------------------------

@router.post("/legal/destruction-acta")
async def generate_destruction_acta(
    request: DestructionActaData,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para generar acta de destrucción")
    try:
        from modules.fiscal.legal_documents import LegalDocumentGenerator
        gen = LegalDocumentGenerator(db)
        result = await gen.generate_destruction_acta(data=request.model_dump())
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generate destruction acta: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al generar acta de destrucción")


@router.post("/legal/return-document")
async def generate_return_document(
    request: ReturnDocumentData,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para generar documento de devolución")
    try:
        from modules.fiscal.legal_documents import LegalDocumentGenerator
        gen = LegalDocumentGenerator(db)
        result = await gen.generate_return_document(data=request.model_dump())
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generate return document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al generar documento de devolución")


@router.post("/legal/selfconsumption-voucher")
async def generate_selfconsumption_voucher(
    request: GenerateSelfConsumptionVoucherRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para generar voucher de autoconsumo")
    try:
        from modules.fiscal.legal_documents import LegalDocumentGenerator
        gen = LegalDocumentGenerator(db)
        result = await gen.generate_selfconsumption_voucher(
            items=[i.model_dump() for i in request.items],
            period=request.period,
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generate selfconsumption voucher: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al generar voucher de autoconsumo")


@router.get("/legal/monthly-summary")
async def get_legal_monthly_summary(
    year: Optional[int] = None,
    month: Optional[int] = None,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver resumen legal mensual")
    try:
        from modules.fiscal.legal_documents import LegalDocumentGenerator
        gen = LegalDocumentGenerator(db)
        result = await gen.get_monthly_summary(year=year, month=month)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get legal monthly summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener resumen legal mensual")


# ---------------------------------------------------------------------------
# Section 20 — Price Analytics
# ---------------------------------------------------------------------------

@router.post("/variance/smart-loss")
async def calculate_smart_loss(
    request: CalculateSmartLossRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede calcular pérdida inteligente")
    try:
        from modules.fiscal.price_analytics import SmartVarianceEngine
        engine = SmartVarianceEngine(db)
        result = await engine.calculate_smart_loss(
            base_amount=request.base_amount,
            category=request.category,
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculate smart loss: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al calcular pérdida inteligente")


@router.post("/variance/optimal-cast")
async def suggest_optimal_cast(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ver CAST óptimo")
    try:
        from modules.fiscal.price_analytics import SmartVarianceEngine
        engine = SmartVarianceEngine(db)
        result = await engine.suggest_optimal_CAST()
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error suggest optimal CAST: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al sugerir CAST óptimo")


@router.post("/variance/batch")
async def generate_batch_variance(
    request: GenerateBatchVarianceRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede generar varianza batch")
    try:
        from modules.fiscal.price_analytics import SmartVarianceEngine
        engine = SmartVarianceEngine(db)
        result = await engine.generate_batch_variance(
            items=[i.model_dump() for i in request.items],
            total_target=request.total_target,
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generate batch variance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al generar varianza batch")


@router.get("/variance/seasonal-factor")
async def get_seasonal_factor(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ver factor estacional")
    try:
        from modules.fiscal.price_analytics import SmartVarianceEngine
        engine = SmartVarianceEngine(db)
        result = await engine.get_seasonal_factor()
        return {"success": True, "data": {"factor": result}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get seasonal factor: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener factor estacional")


# ---------------------------------------------------------------------------
# Section 21 — Discrepancy Monitor
# ---------------------------------------------------------------------------

@router.post("/discrepancy/expense")
async def register_discrepancy_expense(
    request: RegisterExpenseRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede registrar gastos en monitor")
    try:
        from modules.fiscal.reconciliation_monitor import DiscrepancyMonitor
        monitor = DiscrepancyMonitor(db)
        result = await monitor.register_expense(
            amount=request.amount,
            category=request.category,
            payment_method=request.payment_method,
            description=request.description,
            is_visible=request.is_visible,
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error register discrepancy expense: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al registrar gasto")


@router.get("/discrepancy/analysis")
async def get_discrepancy_analysis(
    year: Optional[int] = None,
    month: Optional[int] = None,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ver análisis de discrepancias")
    try:
        from modules.fiscal.reconciliation_monitor import DiscrepancyMonitor
        monitor = DiscrepancyMonitor(db)
        result = await monitor.get_discrepancy_analysis(year=year, month=month)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get discrepancy analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener análisis de discrepancias")


@router.get("/discrepancy/trend")
async def get_discrepancy_trend(
    year: Optional[int] = None,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ver tendencia de discrepancias")
    try:
        from modules.fiscal.reconciliation_monitor import DiscrepancyMonitor
        monitor = DiscrepancyMonitor(db)
        result = await monitor.get_monthly_trend(year=year)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get discrepancy trend: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener tendencia de discrepancias")


@router.get("/discrepancy/suggest-extraction")
async def suggest_extraction_amount(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ver sugerencia de extracción")
    try:
        from modules.fiscal.reconciliation_monitor import DiscrepancyMonitor
        monitor = DiscrepancyMonitor(db)
        result = await monitor.suggest_extraction_amount()
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error suggest extraction amount: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al sugerir monto de extracción")


@router.get("/discrepancy/expenses")
async def get_expense_breakdown(
    year: Optional[int] = None,
    month: Optional[int] = None,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ver desglose de gastos")
    try:
        from modules.fiscal.reconciliation_monitor import DiscrepancyMonitor
        monitor = DiscrepancyMonitor(db)
        result = await monitor.get_expense_breakdown(year=year, month=month)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get expense breakdown: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener desglose de gastos")


# ---------------------------------------------------------------------------
# Section 22 — RESICO Monitor
# ---------------------------------------------------------------------------

@router.get("/resico/health")
async def get_resico_health(
    year: Optional[int] = None,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver salud RESICO")
    try:
        from modules.fiscal.resico_monitor import RESICOMonitor
        monitor = RESICOMonitor(db)
        result = await monitor.get_health_status(year=year)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get RESICO health: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener salud RESICO")


@router.get("/resico/should-pause")
async def should_pause_fiscal(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver estado de pausa fiscal")
    try:
        from modules.fiscal.resico_monitor import RESICOMonitor
        monitor = RESICOMonitor(db)
        result = await monitor.should_pause_fiscal()
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error should pause fiscal: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al evaluar pausa fiscal")


@router.get("/resico/monthly-breakdown")
async def get_resico_monthly_breakdown(
    year: Optional[int] = None,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver desglose mensual RESICO")
    try:
        from modules.fiscal.resico_monitor import RESICOMonitor
        monitor = RESICOMonitor(db)
        result = await monitor.get_monthly_breakdown(year=year)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get RESICO monthly breakdown: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener desglose mensual RESICO")


# ---------------------------------------------------------------------------
# Section 23 — RFC Rotation / Jitter
# ---------------------------------------------------------------------------

@router.post("/proxy/timbrar")
async def proxy_timbrar(
    request: TimbrarConProxyRequest,
    auth: dict = Depends(verify_token),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede timbrar con proxy")
    try:
        from modules.fiscal.rfc_rotation import CFDIProxyRotator
        rotator = CFDIProxyRotator()
        result = await asyncio.to_thread(rotator.timbrar_con_proxy, request.xml_data, request.rfc, request.pac_url)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error proxy timbrar: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al timbrar con proxy")


@router.post("/proxy/configure")
async def configure_proxies(
    request: ConfigureProxiesRequest,
    auth: dict = Depends(verify_token),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede configurar proxies")
    try:
        from modules.fiscal.rfc_rotation import CFDIProxyRotator
        rotator = CFDIProxyRotator()
        result = rotator.configure_proxies(request.proxies)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error configure proxies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al configurar proxies")


@router.get("/jitter/random-time")
async def get_random_timbrado_time(
    auth: dict = Depends(verify_token),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ver tiempo de timbrado aleatorio")
    try:
        from modules.fiscal.rfc_rotation import GhostJitter
        jitter = GhostJitter()
        result = jitter.get_random_timbrado_time()
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get random timbrado time: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener tiempo aleatorio de timbrado")


@router.post("/jitter/distribute")
async def distribute_timbrados(
    request: DistributeTimbradosRequest,
    auth: dict = Depends(verify_token),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede distribuir timbrados")
    try:
        from modules.fiscal.rfc_rotation import GhostJitter
        jitter = GhostJitter()
        result = jitter.distribute_timbrados(request.count, request.hours)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error distribute timbrados: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al distribuir timbrados")


# ---------------------------------------------------------------------------
# Section 24 — Climate Shield
# ---------------------------------------------------------------------------

@router.get("/climate/current")
async def get_current_climate(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver clima actual")
    try:
        from modules.fiscal.risk_mitigation import ClimateShield
        shield = ClimateShield(db)
        result = await shield.get_current_climate()
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get current climate: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener clima actual")


@router.post("/climate/evaluate-risk")
async def evaluate_degradation_risk(
    request: EvaluateDegradationRiskRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para evaluar riesgo de degradación")
    try:
        from modules.fiscal.risk_mitigation import ClimateShield
        shield = ClimateShield(db)
        result = await shield.evaluate_degradation_risk(
            climate=request.climate,
            product_category=request.product_category,
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error evaluate degradation risk: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al evaluar riesgo de degradación")


@router.post("/climate/shrinkage-justification")
async def generate_climate_shrinkage_justification(
    request: GenerateShrinkageJustificationRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para generar justificación de merma")
    try:
        from modules.fiscal.risk_mitigation import ClimateShield
        shield = ClimateShield(db)
        result = await shield.generate_shrinkage_justification(
            merma_data={
                "product_name": request.product_name,
                "quantity": float(request.quantity),
                "category": request.category,
                "id": request.id,
            }
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generate shrinkage justification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al generar justificación de merma")


@router.post("/climate/attach-merma/{merma_id}")
async def attach_climate_to_merma(
    merma_id: int,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para adjuntar clima a merma")
    try:
        from modules.fiscal.risk_mitigation import ClimateShield
        shield = ClimateShield(db)
        result = await shield.attach_to_merma(merma_id)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error attach climate to merma: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al adjuntar clima a merma")


# ---------------------------------------------------------------------------
# Section 25 — SAT Catalog
# ---------------------------------------------------------------------------

@router.get("/sat-catalog/search")
async def sat_catalog_search(
    q: str,
    limit: int = 50,
    auth: dict = Depends(verify_token),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para buscar catálogo SAT")
    try:
        from modules.fiscal.sat_catalog_full import get_catalog_manager
        manager = get_catalog_manager()
        result = manager.search(query=q, limit=limit)
        return {"success": True, "data": [{"clave": c, "descripcion": d} for c, d in result]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error SAT catalog search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al buscar en catálogo SAT")


@router.get("/sat-catalog/description/{clave}")
async def sat_catalog_description(
    clave: str,
    auth: dict = Depends(verify_token),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para consultar catálogo SAT")
    try:
        from modules.fiscal.sat_catalog_full import get_catalog_manager
        manager = get_catalog_manager()
        result = manager.get_description(clave)
        if result is None:
            raise HTTPException(status_code=404, detail="Clave SAT no encontrada")
        return {"success": True, "data": {"clave": clave, "descripcion": result}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error SAT catalog description: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener descripción SAT")


# ---------------------------------------------------------------------------
# Section 26 — Self Consumption
# ---------------------------------------------------------------------------

@router.post("/self-consumption/register")
async def register_self_consumption(
    request: RegisterConsumptionRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para registrar autoconsumo")
    try:
        from modules.fiscal.self_consumption import SelfConsumptionEngine
        engine = SelfConsumptionEngine(db)
        result = await engine.register_consumption(
            product_id=request.product_id,
            quantity=float(request.quantity),
            category=request.category,
            reason=request.reason,
            beneficiary=request.beneficiary,
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error register self consumption: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al registrar autoconsumo")


@router.post("/self-consumption/sample")
async def register_sample(
    request: RegisterSampleRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para registrar muestra")
    try:
        from modules.fiscal.self_consumption import SelfConsumptionEngine
        engine = SelfConsumptionEngine(db)
        result = await engine.register_sample(
            product_id=request.product_id,
            quantity=float(request.quantity),
            recipient=request.recipient,
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error register sample: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al registrar muestra")


@router.post("/self-consumption/employee")
async def register_employee_consumption(
    request: RegisterEmployeeConsumptionRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para registrar consumo de empleado")
    try:
        from modules.fiscal.self_consumption import SelfConsumptionEngine
        engine = SelfConsumptionEngine(db)
        result = await engine.register_employee_consumption(
            product_id=request.product_id,
            quantity=float(request.quantity),
            employee_name=request.employee_name,
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error register employee consumption: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al registrar consumo de empleado")


@router.get("/self-consumption/summary")
async def get_self_consumption_summary(
    year: Optional[int] = None,
    month: Optional[int] = None,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver resumen de autoconsumo")
    try:
        from modules.fiscal.self_consumption import SelfConsumptionEngine
        engine = SelfConsumptionEngine(db)
        result = await engine.get_monthly_summary(year=year, month=month)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get self consumption summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener resumen de autoconsumo")


@router.post("/self-consumption/voucher")
async def generate_self_consumption_voucher(
    year: Optional[int] = None,
    month: Optional[int] = None,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para generar voucher de autoconsumo")
    try:
        from modules.fiscal.self_consumption import SelfConsumptionEngine
        engine = SelfConsumptionEngine(db)
        result = await engine.generate_monthly_voucher(year=year, month=month)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generate self consumption voucher: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al generar voucher de autoconsumo")


@router.get("/self-consumption/pending-months")
async def get_pending_voucher_months(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver meses pendientes de voucher")
    try:
        from modules.fiscal.self_consumption import SelfConsumptionEngine
        engine = SelfConsumptionEngine(db)
        result = await engine.get_pending_voucher_months()
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get pending voucher months: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener meses pendientes de voucher")


# ---------------------------------------------------------------------------
# Section 27 — Shrinkage / Materiality
# ---------------------------------------------------------------------------

@router.post("/shrinkage/register")
async def register_loss(
    request: RegisterLossRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para registrar pérdida")
    try:
        from modules.fiscal.shrinkage_tracker import MaterialityEngine
        engine = MaterialityEngine(db)
        result = await engine.register_loss(
            product_id=request.product_id,
            quantity=float(request.quantity),
            reason=request.reason,
            category=request.category,
            witness_name=request.witness_name,
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error register loss: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al registrar pérdida")


@router.post("/shrinkage/authorize")
async def authorize_loss(
    request: AuthorizeLossRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para autorizar pérdida")
    try:
        from modules.fiscal.shrinkage_tracker import MaterialityEngine
        engine = MaterialityEngine(db)
        result = await engine.authorize_loss(
            acta_number=request.acta_number,
            authorized_by=request.authorized_by,
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error authorize loss: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al autorizar pérdida")


@router.get("/shrinkage/acta/{acta_number}")
async def get_shrinkage_acta(
    acta_number: str,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver acta de pérdida")
    try:
        from modules.fiscal.shrinkage_tracker import MaterialityEngine
        engine = MaterialityEngine(db)
        result = await engine.generate_acta_text(acta_number)
        return {"success": True, "data": {"text": result}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get shrinkage acta: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener acta de pérdida")


@router.get("/shrinkage/pending")
async def get_pending_losses(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver pérdidas pendientes")
    try:
        from modules.fiscal.shrinkage_tracker import MaterialityEngine
        engine = MaterialityEngine(db)
        result = await engine.get_pending_losses()
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get pending losses: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener pérdidas pendientes")


@router.get("/shrinkage/summary")
async def get_loss_summary(
    year: Optional[int] = None,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver resumen de pérdidas")
    try:
        from modules.fiscal.shrinkage_tracker import MaterialityEngine
        engine = MaterialityEngine(db)
        result = await engine.get_loss_summary(year=year)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get loss summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener resumen de pérdidas")


# ---------------------------------------------------------------------------
# Section 28 — Fiscal Noise
# ---------------------------------------------------------------------------

@router.get("/noise/optimal")
async def get_optimal_noise(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede ver ruido óptimo")
    try:
        from modules.fiscal.transaction_normalizer import FiscalNoiseGenerator
        engine = FiscalNoiseGenerator(db)
        result = await engine.calculate_optimal_noise()
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error get optimal noise: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al calcular ruido óptimo")


@router.post("/noise/generate")
async def generate_noise_transaction(
    request: GenerateNoiseTransactionRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede generar transacciones de ruido")
    try:
        from modules.fiscal.transaction_normalizer import FiscalNoiseGenerator
        engine = FiscalNoiseGenerator(db)
        result = await engine.generate_noise_transaction(rfc=request.rfc)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generate noise transaction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al generar transacción de ruido")


@router.post("/noise/start-daily")
async def start_daily_noise(
    request: StartDailyNoiseRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    if auth.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Solo admin/owner puede iniciar ruido diario")
    try:
        from modules.fiscal.transaction_normalizer import FiscalNoiseGenerator
        engine = FiscalNoiseGenerator(db)
        await engine.start_daily_noise(target=request.target)
        return {"success": True, "data": {"message": "Ruido diario iniciado"}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error start daily noise: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al iniciar ruido diario")
