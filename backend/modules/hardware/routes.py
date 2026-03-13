"""
POSVENDELO — Hardware Module Routes

Endpoints for printer/scanner/drawer configuration, discovery, and control.
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from db.connection import get_db
from modules.shared.auth import verify_token, get_user_id
from modules.shared.constants import PRIVILEGED_ROLES, money
from modules.shared.turn_service import calculate_turn_summary
from modules.hardware.schemas import (
    PrinterConfigUpdate,
    BusinessInfoUpdate,
    ScannerConfigUpdate,
    DrawerConfigUpdate,
    PrintReceiptRequest,
    PrintShiftReportRequest,
    InitialSetupPayload,
)
from modules.hardware import printer as printer_svc
from modules.hardware.escpos import build_sale_receipt, build_test_receipt, build_shift_report

logger = logging.getLogger(__name__)
router = APIRouter()

# Columns we read from app_config for hardware
_HW_COLUMNS = [
    # printer
    "receipt_printer_name", "receipt_printer_enabled", "receipt_paper_width",
    "receipt_char_width", "receipt_auto_print", "receipt_mode", "receipt_cut_type",
    # business
    "business_name", "business_legal_name", "business_address", "business_rfc",
    "business_regimen", "business_phone", "business_footer",
    # scanner
    "scanner_enabled", "scanner_prefix", "scanner_suffix",
    "scanner_min_speed_ms", "scanner_auto_submit",
    # drawer (existing + extended)
    "cash_drawer_enabled", "printer_name", "cash_drawer_pulse_bytes",
    "cash_drawer_auto_open_cash", "cash_drawer_auto_open_card",
    "cash_drawer_auto_open_transfer",
]

async def _ensure_hw_row(db) -> int:
    """Ensure app_config has a hardware row. Return its id (single upsert)."""
    row = await db.fetchrow(
        "INSERT INTO app_config (key, value, category, updated_at) "
        "VALUES ('hardware', 'default', 'system', NOW()) "
        "ON CONFLICT (key) DO UPDATE SET updated_at = NOW() "
        "RETURNING id"
    )
    return row["id"]


async def _get_hw_config(db) -> dict:
    """Read hardware-related columns from app_config (single upsert query)."""
    row = await db.fetchrow(
        "INSERT INTO app_config (key, value, category, updated_at) "
        "VALUES ('hardware', 'default', 'system', NOW()) "
        "ON CONFLICT (key) DO UPDATE SET updated_at = NOW() "
        "RETURNING id, receipt_printer_name, receipt_printer_enabled, receipt_paper_width, "
        "receipt_char_width, receipt_auto_print, receipt_mode, receipt_cut_type, "
        "business_name, business_legal_name, business_address, business_rfc, "
        "business_regimen, business_phone, business_footer, "
        "scanner_enabled, scanner_prefix, scanner_suffix, "
        "scanner_min_speed_ms, scanner_auto_submit, "
        "cash_drawer_enabled, printer_name, cash_drawer_pulse_bytes, "
        "cash_drawer_auto_open_cash, cash_drawer_auto_open_card, "
        "cash_drawer_auto_open_transfer"
    )
    if not row:
        return {}
    cfg = dict(row)
    return {k: cfg.get(k) for k in _HW_COLUMNS if k in cfg}


async def _get_initial_setup_status(db) -> dict:
    """Return first-run setup status stored in app_config."""
    # Sequential — asyncpg doesn't support concurrent ops on the same connection
    cfg = await _get_hw_config(db)
    marker = await db.fetchrow("SELECT value, updated_at FROM app_config WHERE key = 'initial_setup' LIMIT 1")

    completed = False
    completed_at = None
    if marker and marker.get("value"):
        try:
            payload = json.loads(marker["value"])
        except (TypeError, ValueError):
            payload = {}
        completed = bool(payload.get("completed", False))
        completed_at = payload.get("completed_at")

    if not completed:
        completed = bool((cfg.get("business_name") or "").strip())

    return {
        "completed": completed,
        "completed_at": completed_at,
        "business_name": cfg.get("business_name", ""),
        "printer_name": cfg.get("receipt_printer_name", ""),
    }


def _require_admin(auth: dict):
    if auth.get("role") not in PRIVILEGED_ROLES:
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
                "legal_name": cfg.get("business_legal_name", ""),
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
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items() if k in _HW_COLUMNS}
    if not updates:
        raise HTTPException(status_code=400, detail="Nada que actualizar")

    row_id = await _ensure_hw_row(db)
    sets = ", ".join(f"{k} = :{k}" for k in updates)
    updates["_row_id"] = row_id
    await db.execute(f"UPDATE app_config SET {sets} WHERE id = :_row_id", updates)
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
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items() if k in _HW_COLUMNS}
    if not updates:
        raise HTTPException(status_code=400, detail="Nada que actualizar")

    row_id = await _ensure_hw_row(db)
    sets = ", ".join(f"{k} = :{k}" for k in updates)
    updates["_row_id"] = row_id
    await db.execute(f"UPDATE app_config SET {sets} WHERE id = :_row_id", updates)
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
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items() if k in _HW_COLUMNS}
    if not updates:
        raise HTTPException(status_code=400, detail="Nada que actualizar")

    row_id = await _ensure_hw_row(db)
    sets = ", ".join(f"{k} = :{k}" for k in updates)
    updates["_row_id"] = row_id
    await db.execute(f"UPDATE app_config SET {sets} WHERE id = :_row_id", updates)
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
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items() if k in _HW_COLUMNS}
    if not updates:
        raise HTTPException(status_code=400, detail="Nada que actualizar")

    row_id = await _ensure_hw_row(db)
    sets = ", ".join(f"{k} = :{k}" for k in updates)
    updates["_row_id"] = row_id
    await db.execute(f"UPDATE app_config SET {sets} WHERE id = :_row_id", updates)
    return {"success": True, "data": {"message": "Configuracion de cajon actualizada"}}


@router.get("/setup-status")
async def get_initial_setup_status(
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Check if initial setup wizard has been completed."""
    status = await _get_initial_setup_status(db)
    return {"success": True, "data": status}


@router.post("/setup-wizard")
async def complete_initial_setup(
    body: InitialSetupPayload,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Persist initial setup and mark installation as configured."""
    _require_admin(auth)

    updates = {
        "business_name": body.business_name.strip(),
        "business_legal_name": (body.business_legal_name or "").strip(),
        "business_address": (body.business_address or "").strip(),
        "business_rfc": (body.business_rfc or "").strip().upper(),
        "business_regimen": (body.business_regimen or "").strip(),
        "business_phone": (body.business_phone or "").strip(),
        "business_footer": (body.business_footer or "").strip() or "Gracias por su compra",
        "receipt_printer_name": (body.receipt_printer_name or "").strip(),
        "receipt_printer_enabled": bool(body.receipt_printer_enabled),
        "receipt_auto_print": bool(body.receipt_auto_print),
        "scanner_enabled": bool(body.scanner_enabled),
        "cash_drawer_enabled": bool(body.cash_drawer_enabled),
    }

    row_id = await _ensure_hw_row(db)
    updates["_row_id"] = row_id
    sets = ", ".join(f"{k} = :{k}" for k in updates if k != "_row_id")

    marker = json.dumps(
        {
            "completed": True,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "completed_by": str(auth.get("sub") or ""),
        },
        ensure_ascii=True,
    )

    async with db.connection.transaction():
        await db.execute(
            f"UPDATE app_config SET {sets}, updated_at = NOW() WHERE id = :_row_id",
            updates,
        )
        await db.execute(
            """
            INSERT INTO app_config (key, value, category, updated_at)
            VALUES ('initial_setup', :value, 'system', NOW())
            ON CONFLICT (key)
            DO UPDATE SET value = :value, updated_at = NOW()
            """,
            {"value": marker},
        )

    return {
        "success": True,
        "data": {
            "message": "Configuracion inicial guardada",
            "completed": True,
        },
    }


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
        raise HTTPException(status_code=500, detail="Error al imprimir. Verifique la impresora.")

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

    drawer_printer = cfg.get("printer_name", "") or cfg.get("receipt_printer_name", "")
    if not drawer_printer:
        raise HTTPException(status_code=400, detail="Impresora de cajón no configurada")

    pulse = cfg.get("cash_drawer_pulse_bytes", "1B700019FA")
    try:
        await printer_svc.open_drawer(drawer_printer, pulse)
    except Exception as e:
        logger.error("Test drawer failed: %s", e)
        raise HTTPException(status_code=500, detail="Error abriendo cajón. Verifique la conexión.")

    return {"success": True, "data": {"message": "Cajón de prueba abierto"}}


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
        "SELECT id, folio_visible, timestamp, payment_method, "
        "subtotal, discount, tax, total, cash_received, change_given "
        "FROM sales WHERE id = :sid AND status = 'completed'",
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
        raise HTTPException(status_code=500, detail="Error al imprimir ticket. Verifique la impresora.")

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

    drawer_printer = cfg.get("printer_name", "") or cfg.get("receipt_printer_name", "")
    if not drawer_printer:
        return {"success": True, "data": {"message": "Impresora no configurada", "opened": False}}

    pulse = cfg.get("cash_drawer_pulse_bytes", "1B700019FA")
    try:
        await printer_svc.open_drawer(drawer_printer, pulse)
    except Exception as e:
        logger.warning("Non-fatal drawer open error: %s", e)
        return {"success": True, "data": {"message": "Error abriendo cajon. Verifique la conexion.", "opened": False}}

    try:
        await db.execute(
            """INSERT INTO audit_log (action, entity_type, record_id, user_id, details, timestamp)
               VALUES ('SALE_DRAWER_OPEN', 'cash_drawer', 0, :uid, '{"source": "sale_flow"}', NOW())""",
            {"uid": get_user_id(auth)},
        )
    except Exception as audit_err:
        logger.error("Audit log failed for SALE_DRAWER_OPEN: %s", audit_err)

    return {"success": True, "data": {"message": "Cajon abierto", "opened": True}}


# ---------------------------------------------------------------------------
# POST /print-shift-report — print shift cut to thermal printer
# ---------------------------------------------------------------------------

@router.post("/print-shift-report")
async def print_shift_report(
    body: PrintShiftReportRequest,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Print shift cut report on configured thermal printer."""
    cfg = await _get_hw_config(db)

    printer_name = cfg.get("receipt_printer_name", "")
    if not printer_name:
        raise HTTPException(status_code=400, detail="Impresora no configurada")
    if not cfg.get("receipt_printer_enabled"):
        raise HTTPException(status_code=400, detail="Impresora no habilitada")

    # Fetch turn data
    turn = await db.fetchrow(
        "SELECT id, initial_cash, final_cash, status, start_timestamp, end_timestamp "
        "FROM turns WHERE id = :tid",
        {"tid": body.turn_id},
    )
    if not turn:
        raise HTTPException(status_code=404, detail="Turno no encontrado")

    # Build summary using shared service
    ts = await calculate_turn_summary(body.turn_id, turn["initial_cash"], db.connection)

    summary = {
        "sales_count": ts["sales_count"],
        "total_sales": money(ts["total_sales"]),
        "sales_by_method": ts["sales_by_method"],
        "initial_cash": money(ts["initial"]),
        "cash_in": money(ts["mov_in"]),
        "cash_out": money(ts["mov_out"]),
        "expected_cash": money(ts["expected_cash"]),
    }

    char_width = cfg.get("receipt_char_width", 48) or 48
    report_bytes = build_shift_report(dict(turn), summary, cfg, char_width)

    try:
        await printer_svc.print_raw(printer_name, report_bytes)
    except Exception as e:
        logger.error("Print shift report failed for turn %d: %s", body.turn_id, e)
        raise HTTPException(status_code=500, detail="Error al imprimir corte. Verifique la impresora.")

    return {"success": True, "data": {"message": f"Corte de turno #{body.turn_id} impreso"}}
