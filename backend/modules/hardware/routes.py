"""
TITAN POS — Hardware Module Routes

Endpoints for printer/scanner/drawer configuration, discovery, and control.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from db.connection import get_db
from modules.shared.auth import verify_token, get_user_id
from modules.hardware.schemas import (
    PrinterConfigUpdate,
    BusinessInfoUpdate,
    ScannerConfigUpdate,
    DrawerConfigUpdate,
    PrintReceiptRequest,
)
from modules.hardware import printer as printer_svc
from modules.hardware.escpos import build_sale_receipt, build_test_receipt

logger = logging.getLogger(__name__)
router = APIRouter()

# Columns we read from app_config for hardware
_HW_COLUMNS = [
    # printer
    "receipt_printer_name", "receipt_printer_enabled", "receipt_paper_width",
    "receipt_char_width", "receipt_auto_print", "receipt_mode", "receipt_cut_type",
    # business
    "business_name", "business_address", "business_rfc", "business_regimen",
    "business_phone", "business_footer",
    # scanner
    "scanner_enabled", "scanner_prefix", "scanner_suffix",
    "scanner_min_speed_ms", "scanner_auto_submit",
    # drawer (existing + extended)
    "cash_drawer_enabled", "printer_name", "cash_drawer_pulse_bytes",
    "cash_drawer_auto_open_cash", "cash_drawer_auto_open_card",
    "cash_drawer_auto_open_transfer",
]

_ADMIN_ROLES = ("admin", "manager", "owner")


async def _get_hw_config(db) -> dict:
    """Read hardware-related columns from app_config (single-row pattern)."""
    row = await db.fetchrow("SELECT * FROM app_config LIMIT 1")
    if not row:
        return {}
    cfg = dict(row)
    return {k: cfg.get(k) for k in _HW_COLUMNS if k in cfg}


def _require_admin(auth: dict):
    if auth.get("role") not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para configurar hardware")


# ---------------------------------------------------------------------------
# GET /config — full hardware configuration
# ---------------------------------------------------------------------------

@router.get("/config")
async def get_hardware_config(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Return complete hardware configuration. Any authenticated user."""
    cfg = await _get_hw_config(db)
    return {
        "success": True,
        "data": {
            "printer": {
                "name": cfg.get("receipt_printer_name", ""),
                "enabled": bool(cfg.get("receipt_printer_enabled", False)),
                "paper_width": cfg.get("receipt_paper_width", 80),
                "char_width": cfg.get("receipt_char_width", 48),
                "auto_print": bool(cfg.get("receipt_auto_print", False)),
                "mode": cfg.get("receipt_mode", "basic"),
                "cut_type": cfg.get("receipt_cut_type", "partial"),
            },
            "business": {
                "name": cfg.get("business_name", ""),
                "address": cfg.get("business_address", ""),
                "rfc": cfg.get("business_rfc", ""),
                "regimen": cfg.get("business_regimen", ""),
                "phone": cfg.get("business_phone", ""),
                "footer": cfg.get("business_footer", "Gracias por su compra"),
            },
            "scanner": {
                "enabled": bool(cfg.get("scanner_enabled", False)),
                "prefix": cfg.get("scanner_prefix", ""),
                "suffix": cfg.get("scanner_suffix", ""),
                "min_speed_ms": cfg.get("scanner_min_speed_ms", 50),
                "auto_submit": bool(cfg.get("scanner_auto_submit", True)),
            },
            "drawer": {
                "enabled": bool(cfg.get("cash_drawer_enabled", False)),
                "printer_name": cfg.get("printer_name", ""),
                "auto_open_cash": bool(cfg.get("cash_drawer_auto_open_cash", True)),
                "auto_open_card": bool(cfg.get("cash_drawer_auto_open_card", False)),
                "auto_open_transfer": bool(cfg.get("cash_drawer_auto_open_transfer", False)),
            },
        },
    }


# ---------------------------------------------------------------------------
# PUT /config/printer
# ---------------------------------------------------------------------------

@router.put("/config/printer")
async def update_printer_config(
    body: PrinterConfigUpdate,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Update receipt printer settings. RBAC: admin/manager/owner."""
    _require_admin(auth)
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Nada que actualizar")

    sets = ", ".join(f"{k} = :{k}" for k in updates)
    await db.execute(
        f"UPDATE app_config SET {sets} WHERE id = (SELECT id FROM app_config LIMIT 1)",
        updates,
    )
    return {"success": True, "data": {"message": "Configuracion de impresora actualizada"}}


# ---------------------------------------------------------------------------
# PUT /config/business
# ---------------------------------------------------------------------------

@router.put("/config/business")
async def update_business_info(
    body: BusinessInfoUpdate,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Update business information for receipts. RBAC: admin/manager/owner."""
    _require_admin(auth)
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Nada que actualizar")

    sets = ", ".join(f"{k} = :{k}" for k in updates)
    await db.execute(
        f"UPDATE app_config SET {sets} WHERE id = (SELECT id FROM app_config LIMIT 1)",
        updates,
    )
    return {"success": True, "data": {"message": "Datos del negocio actualizados"}}


# ---------------------------------------------------------------------------
# PUT /config/scanner
# ---------------------------------------------------------------------------

@router.put("/config/scanner")
async def update_scanner_config(
    body: ScannerConfigUpdate,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Update barcode scanner settings. RBAC: admin/manager/owner."""
    _require_admin(auth)
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Nada que actualizar")

    sets = ", ".join(f"{k} = :{k}" for k in updates)
    await db.execute(
        f"UPDATE app_config SET {sets} WHERE id = (SELECT id FROM app_config LIMIT 1)",
        updates,
    )
    return {"success": True, "data": {"message": "Configuracion de scanner actualizada"}}


# ---------------------------------------------------------------------------
# PUT /config/drawer
# ---------------------------------------------------------------------------

@router.put("/config/drawer")
async def update_drawer_config(
    body: DrawerConfigUpdate,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Update cash drawer settings. RBAC: admin/manager/owner."""
    _require_admin(auth)
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Nada que actualizar")

    sets = ", ".join(f"{k} = :{k}" for k in updates)
    await db.execute(
        f"UPDATE app_config SET {sets} WHERE id = (SELECT id FROM app_config LIMIT 1)",
        updates,
    )
    return {"success": True, "data": {"message": "Configuracion de cajon actualizada"}}


# ---------------------------------------------------------------------------
# GET /printers — discover CUPS printers
# ---------------------------------------------------------------------------

@router.get("/printers")
async def discover_printers(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """List available CUPS printers. RBAC: admin/manager/owner."""
    _require_admin(auth)
    try:
        printers = await printer_svc.list_printers()
    except Exception as e:
        logger.error("Error discovering printers: %s", e)
        raise HTTPException(status_code=500, detail="Error detectando impresoras")
    return {"success": True, "data": {"printers": printers}}


# ---------------------------------------------------------------------------
# POST /test-print — print a test receipt
# ---------------------------------------------------------------------------

@router.post("/test-print")
async def test_print(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Print a test receipt. RBAC: admin/manager/owner."""
    _require_admin(auth)
    cfg = await _get_hw_config(db)

    printer_name = cfg.get("receipt_printer_name", "")
    if not printer_name:
        raise HTTPException(status_code=400, detail="Impresora no configurada")

    char_width = cfg.get("receipt_char_width", 48) or 48
    data = build_test_receipt(cfg, char_width)

    try:
        await printer_svc.print_raw(printer_name, data)
    except Exception as e:
        logger.error("Test print failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Error al imprimir: {e}")

    return {"success": True, "data": {"message": "Ticket de prueba enviado"}}


# ---------------------------------------------------------------------------
# POST /test-drawer — test cash drawer kick
# ---------------------------------------------------------------------------

@router.post("/test-drawer")
async def test_drawer(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Test cash drawer open. RBAC: admin/manager/owner."""
    _require_admin(auth)
    cfg = await _get_hw_config(db)

    drawer_printer = cfg.get("printer_name", "")
    if not drawer_printer:
        raise HTTPException(status_code=400, detail="Impresora de cajon no configurada")

    pulse = cfg.get("cash_drawer_pulse_bytes", "1B700019FA")
    try:
        await printer_svc.open_drawer(drawer_printer, pulse)
    except Exception as e:
        logger.error("Test drawer failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Error abriendo cajon: {e}")

    return {"success": True, "data": {"message": "Cajon de prueba abierto"}}


# ---------------------------------------------------------------------------
# POST /print-receipt — print a sale receipt
# ---------------------------------------------------------------------------

@router.post("/print-receipt")
async def print_receipt(
    body: PrintReceiptRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Print receipt for a completed sale. Any authenticated user."""
    cfg = await _get_hw_config(db)

    printer_name = cfg.get("receipt_printer_name", "")
    if not printer_name:
        raise HTTPException(status_code=400, detail="Impresora no configurada")
    if not cfg.get("receipt_printer_enabled"):
        raise HTTPException(status_code=400, detail="Impresora no habilitada")

    sale = await db.fetchrow(
        "SELECT * FROM sales WHERE id = :sid AND status = 'completed'",
        {"sid": body.sale_id},
    )
    if not sale:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    items = await db.fetch(
        """SELECT si.qty, si.price, si.subtotal,
                  COALESCE(p.name, si.name, 'Producto') as product_name
           FROM sale_items si
           LEFT JOIN products p ON p.id = si.product_id
           WHERE si.sale_id = :sid""",
        {"sid": body.sale_id},
    )

    char_width = cfg.get("receipt_char_width", 48) or 48
    receipt_bytes = build_sale_receipt(dict(sale), [dict(i) for i in items], cfg, char_width)

    try:
        await printer_svc.print_raw(printer_name, receipt_bytes)
    except Exception as e:
        logger.error("Print receipt failed for sale %d: %s", body.sale_id, e)
        raise HTTPException(status_code=500, detail=f"Error al imprimir ticket: {e}")

    return {"success": True, "data": {"message": f"Ticket de venta #{body.sale_id} impreso"}}


# ---------------------------------------------------------------------------
# POST /open-drawer — open drawer during sale flow (non-fatal)
# ---------------------------------------------------------------------------

@router.post("/open-drawer")
async def open_drawer_for_sale(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Open cash drawer during sale flow. Any authenticated user. Non-fatal on error."""
    cfg = await _get_hw_config(db)

    if not cfg.get("cash_drawer_enabled"):
        return {"success": True, "data": {"message": "Cajon no habilitado", "opened": False}}

    drawer_printer = cfg.get("printer_name", "")
    if not drawer_printer:
        return {"success": True, "data": {"message": "Impresora no configurada", "opened": False}}

    pulse = cfg.get("cash_drawer_pulse_bytes", "1B700019FA")
    try:
        await printer_svc.open_drawer(drawer_printer, pulse)
    except Exception as e:
        logger.warning("Non-fatal drawer open error: %s", e)
        return {"success": True, "data": {"message": f"Error abriendo cajon: {e}", "opened": False}}

    try:
        await db.execute(
            """INSERT INTO audit_log (action, entity_type, record_id, user_id, details, timestamp)
               VALUES ('SALE_DRAWER_OPEN', 'cash_drawer', 0, :uid, '{"source": "sale_flow"}', NOW())""",
            {"uid": get_user_id(auth)},
        )
    except Exception as audit_err:
        logger.error("Audit log failed for SALE_DRAWER_OPEN: %s", audit_err)

    return {"success": True, "data": {"message": "Cajon abierto", "opened": True}}
