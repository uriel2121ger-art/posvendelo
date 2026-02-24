"""
TITAN Gateway - Products Router

Product management endpoints.
"""
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends

from ..auth import verify_token
from ..models import ProductUpdate, ProductCreate, InventoryAdjust
from ..storage import get_cached, set_cached
from ..request_policies import (
    enforce_write_role,
    require_terminal_id,
    check_and_record_idempotency,
    idempotency_header,
    terminal_header,
)
from ..observability import emit_event

logger = logging.getLogger("TITAN_GATEWAY")
router = APIRouter(prefix="/api", tags=["Products"])
DATA_DIR = Path("./gateway_data")
PRODUCTS_FILE = DATA_DIR / "products.json"
_products_lock = asyncio.Lock()

def load_products():
    # FIX 2026-02-01: Added JSONDecodeError handling
    if PRODUCTS_FILE.exists():
        try:
            return json.loads(PRODUCTS_FILE.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in products file: {e}")
            return []
    return []

def save_products(products):
    PRODUCTS_FILE.write_text(json.dumps(products, indent=2, ensure_ascii=False), encoding='utf-8')

@router.get("/sync/products")
async def get_product_updates(
    since: Optional[str] = None,
    auth: dict = Depends(verify_token)
):
    """Get product/price updates for branches to download."""
    updates_file = DATA_DIR / "product_updates.json"
    
    if not updates_file.exists():
        return {"products": [], "last_update": None}
    
    # FIX 2026-02-01: Added JSONDecodeError handling
    try:
        updates = json.loads(updates_file.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in updates file: {e}")
        updates = []
    
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except (ValueError, TypeError):
            since_dt = datetime.now()
            logger.warning(f"Invalid date format for 'since' parameter: {since}")
        updates = [u for u in updates if _safe_parse_datetime(u.get("updated_at", "2000-01-01")) > since_dt]

    return {
        "products": updates,
        "last_update": datetime.now().isoformat()
    }


def _safe_parse_datetime(value: str) -> datetime:
    """Safely parse ISO format datetime string."""
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return datetime(2000, 1, 1)

@router.post("/products/update")
async def update_product(
    update: ProductUpdate,
    auth: dict = Depends(verify_token),
    idem_key: str | None = Depends(idempotency_header),
    hdr_terminal_id: int | None = Depends(terminal_header),
):
    """Update a product (propagates to all branches)."""
    enforce_write_role(auth)
    terminal_id = require_terminal_id(update.terminal_id, hdr_terminal_id)
    request_key = update.request_id or idem_key
    if check_and_record_idempotency(request_key, "/products/update", terminal_id):
        return {"success": True, "deduplicated": True, "sku": update.sku}

    updates_file = DATA_DIR / "product_updates.json"

    async with _products_lock:
        existing = []
        if updates_file.exists():
            try:
                existing = json.loads(updates_file.read_text(encoding='utf-8'))
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in updates file, resetting: {e}")
                existing = []

        # Find and update or add
        found = False
        for i, p in enumerate(existing):
            if p.get("sku") == update.sku:
                existing[i] = {**p, **update.model_dump(exclude_unset=True), "updated_at": datetime.now().isoformat()}
                found = True
                break

        if not found:
            existing.append({**update.model_dump(exclude_unset=True), "updated_at": datetime.now().isoformat()})

        updates_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding='utf-8')
    
    logger.info(f"Producto actualizado: {update.sku}")
    emit_event(
        "product_updated",
        terminal_id=terminal_id,
        role=auth.get("role"),
        sku=update.sku,
    )
    
    return {"success": True, "sku": update.sku}

@router.get("/products/search")
async def search_product(sku: str, auth: dict = Depends(verify_token)):
    """Search for a product by SKU with history."""
    products = load_products()
    
    found = None
    for p in products:
        if p.get("sku") == sku:
            found = p
            break
    
    if not found:
        return {"found": False, "sku": sku}
    
    return {
        "found": True,
        "product": found,
        "timestamp": datetime.now().isoformat()
    }

@router.post("/products/create")
async def create_product(
    product: ProductCreate,
    auth: dict = Depends(verify_token),
    idem_key: str | None = Depends(idempotency_header),
    hdr_terminal_id: int | None = Depends(terminal_header),
):
    """Create a new product."""
    enforce_write_role(auth)
    terminal_id = require_terminal_id(product.terminal_id, hdr_terminal_id)
    request_key = product.request_id or idem_key
    if check_and_record_idempotency(request_key, "/products/create", terminal_id):
        return {"success": True, "deduplicated": True, "sku": product.sku}

    async with _products_lock:
        products = load_products()

        # Check if SKU exists
        for p in products:
            if p.get("sku") == product.sku:
                return {"success": False, "error": "SKU ya existe"}

        new_product = {
            **product.model_dump(),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        products.append(new_product)
        save_products(products)
    
    logger.info(f"Producto creado: {product.sku}")
    emit_event(
        "product_created",
        terminal_id=terminal_id,
        role=auth.get("role"),
        sku=product.sku,
    )
    
    return {"success": True, "product": new_product}

@router.post("/inventory/adjust")
async def adjust_inventory(
    adjust: InventoryAdjust,
    auth: dict = Depends(verify_token),
    idem_key: str | None = Depends(idempotency_header),
    hdr_terminal_id: int | None = Depends(terminal_header),
):
    """Adjust inventory for a product in a branch."""
    enforce_write_role(auth)
    terminal_id = require_terminal_id(adjust.terminal_id, hdr_terminal_id)
    request_key = adjust.request_id or idem_key
    if check_and_record_idempotency(request_key, "/inventory/adjust", terminal_id):
        return {"success": True, "deduplicated": True, "adjustment": adjust.model_dump()}

    adjustments_file = DATA_DIR / "pending_adjustments.json"

    async with _products_lock:
        existing = []
        if adjustments_file.exists():
            try:
                existing = json.loads(adjustments_file.read_text(encoding='utf-8'))
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in adjustments file, resetting: {e}")
                existing = []

        existing.append({
            **adjust.model_dump(),
            "created_at": datetime.now().isoformat()
        })

        adjustments_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding='utf-8')
    
    logger.info(f"Ajuste de inventario: {adjust.sku} x{adjust.quantity} ({adjust.reason})")
    emit_event(
        "inventory_adjusted",
        terminal_id=terminal_id,
        role=auth.get("role"),
        sku=adjust.sku,
        quantity=adjust.quantity,
        reason=adjust.reason,
    )
    
    return {"success": True, "adjustment": adjust.model_dump()}

@router.get("/products")
async def list_products(
    page: int = 1,
    limit: int = 50,
    search: str = "",
    auth: dict = Depends(verify_token)
):
    """List all products with pagination."""
    products = load_products()
    
    # Filter by search
    if search:
        products = [p for p in products if search.lower() in p.get("name", "").lower() or search in p.get("sku", "")]
    
    # Paginate
    start = (page - 1) * limit
    end = start + limit
    
    return {
        "products": products[start:end],
        "total": len(products),
        "page": page,
        "limit": limit,
        "timestamp": datetime.now().isoformat()
    }
