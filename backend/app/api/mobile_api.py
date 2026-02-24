"""
Mobile API - API REST para PWA Antigravity Remote Command
Expone endpoints seguros para control remoto vía Tailscale
"""

import json
import logging
import math
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from pydantic import BaseModel, field_validator, Field

# Auth: import from shared module (single source of truth)
from modules.shared.auth import (
    verify_token as _shared_verify_token,
    create_token as _shared_create_token,
    SECRET_KEY as _shared_secret,
    ALGORITHM as _shared_algorithm,
    TOKEN_EXPIRE_MINUTES as _shared_token_expire,
    security as _shared_security,
)

# SECURITY: Rate limiting to prevent brute force attacks
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    _limiter = Limiter(key_func=get_remote_address)
    HAS_RATE_LIMIT = True
except ImportError:
    HAS_RATE_LIMIT = False
    logger.warning("slowapi not installed - rate limiting disabled. Install with: pip install slowapi")

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================

# Auth config: delegated to modules/shared/auth.py (single source of truth)
SECRET_KEY = _shared_secret
ALGORITHM = _shared_algorithm
TOKEN_EXPIRE_MINUTES = _shared_token_expire

# SECURITY: CORS origins from environment (restrict in production)
# Default includes common Tailscale ranges and localhost for development
_cors_env = os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
if not _cors_env or _cors_env == ['']:
    # Default seguro: solo localhost para desarrollo
    ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080"
    ]
else:
    ALLOWED_ORIGINS = [origin.strip() for origin in _cors_env if origin.strip()]

# If running in Tailscale, you can add your Tailscale IPs here
# Example: export CORS_ALLOWED_ORIGINS="http://100.x.y.z:3000,http://localhost:3000"

app = FastAPI(
    title="Antigravity Remote Command",
    description="API para control remoto del sistema POS",
    version="1.0.0",
    docs_url=None,  # Desactivar docs en producción
    redoc_url=None
)

# SECURITY: Add rate limiting if available
if HAS_RATE_LIMIT:
    from slowapi import _rate_limit_exceeded_handler
    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configurado por entorno - NO usar "*" en producción
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # SECURITY: Whitelist from environment
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

security = _shared_security

# ==============================================================================
# MODELOS
# ==============================================================================

class LoginRequest(BaseModel):
    username: str
    password: str
    # otp: Optional[str] = None  # Para YubiKey OTP

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class ProductScanResponse(BaseModel):
    found: bool
    product: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[Dict]] = None

class StockUpdateRequest(BaseModel):
    sku: str
    quantity: float = Field(..., description="Quantity must be a valid positive number")
    operation: str  # 'add', 'subtract', 'set'
    reason: Optional[str] = None

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v):
        if math.isnan(v) or math.isinf(v):
            raise ValueError('quantity cannot be NaN or Infinity')
        if v < 0:
            raise ValueError('quantity must be non-negative')
        return v

    @field_validator('operation')
    @classmethod
    def validate_operation(cls, v):
        if v not in ('add', 'subtract', 'set'):
            raise ValueError("operation must be 'add', 'subtract', or 'set'")
        return v

class MermaApprovalRequest(BaseModel):
    merma_id: int
    approved: bool
    notes: Optional[str] = None

# ==============================================================================
# AUTENTICACIÓN
# ==============================================================================

# Auth functions: delegated to modules/shared/auth.py
create_token = _shared_create_token
verify_token = _shared_verify_token

def get_core():
    """Lazy load del POSCore (singleton). Evita crear una instancia por request."""
    from app.core import get_core_instance
    return get_core_instance()

# ==============================================================================
# ENDPOINTS DE AUTENTICACIÓN
# ==============================================================================

@app.post("/api/auth/login", response_model=TokenResponse, deprecated=True)
@_limiter.limit("5/minute")
async def login(body: LoginRequest, request: Request):
    """
    DEPRECATED: Use POST /api/v1/auth/login instead.
    Login con credenciales + opcional YubiKey OTP.

    SECURITY: Rate limited to 5 attempts per minute per IP to prevent brute force.
    """
    logger.warning("DEPRECATED: /api/auth/login — use /api/v1/auth/login")
    core = get_core()

    # Try to verify user from employees table
    try:
        user = core.verify_user(body.username, body.password)
        if user:
            token = create_token(str(user.get('id', 1)), user.get('role', 'admin'))
            return TokenResponse(
                access_token=token,
                expires_in=TOKEN_EXPIRE_MINUTES * 60
            )
    except Exception as e:
        logger.debug("Login failed: %s", e)

    raise HTTPException(status_code=401, detail="Credenciales inválidas")

@app.get("/api/auth/verify", deprecated=True)
async def verify_auth(user: Dict = Depends(verify_token)):
    """DEPRECATED: Use GET /api/v1/auth/verify instead."""
    logger.warning("DEPRECATED: /api/auth/verify — use /api/v1/auth/verify")
    return {"valid": True, "user": user["sub"], "role": user["role"]}

# ==============================================================================
# ENDPOINTS DE PRODUCTOS Y ESCÁNER
# ==============================================================================

@app.get("/api/products/scan/{sku}", response_model=ProductScanResponse, deprecated=True)
async def scan_product(sku: str, user: Dict = Depends(verify_token)):
    """DEPRECATED: Use GET /api/v1/products/scan/{sku} instead."""
    logger.warning("DEPRECATED: /api/products/scan — use /api/v1/products/scan")
    core = get_core()
    
    # Buscar por SKU exacto
    product = core.get_product_by_sku(sku)
    
    if product:
        return ProductScanResponse(
            found=True,
            product={
                "id": product['id'],
                "name": product['name'],
                "sku": product['sku'],
                "price": float(product['price']),
                "stock": float(product.get('stock', 0)),
                "sat_code": product.get('sat_clave_prod_serv'),
                "unit": product.get('sat_clave_unidad', 'H87')
            }
        )
    
    # Buscar similares
    similar = core.search_products(sku, limit=5)
    
    return ProductScanResponse(
        found=False,
        suggestions=[{
            "id": p['id'],
            "name": p['name'],
            "sku": p.get('sku', ''),
            "stock": float(p.get('stock', 0))
        } for p in similar]
    )

@app.post("/api/products/stock", deprecated=True)
async def update_stock(request: StockUpdateRequest, user: Dict = Depends(verify_token)):
    """DEPRECATED: Use POST /api/v1/products/stock instead."""
    logger.warning("DEPRECATED: /api/products/stock — use /api/v1/products/stock")
    core = get_core()
    
    product = core.get_product_by_sku(request.sku)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    current_stock = float(product.get('stock', 0))
    
    if request.operation == 'add':
        new_stock = current_stock + request.quantity
    elif request.operation == 'subtract':
        new_stock = current_stock - request.quantity
    else:  # set
        new_stock = request.quantity
    
    # CRITICAL FIX: Actualizar stock y crear log en una sola transacción
    # Verificar si user_id existe antes de construir la transacción
    try:
        table_info = core.db.get_table_info("inventory_log")
        available_cols = [col.get('name') if isinstance(col, dict) else col[1] for col in table_info]
        has_user_id = "user_id" in available_cols
    except Exception as e:
        logger.warning(f"Could not get inventory_log table info: {e}")
        has_user_id = False
    
    # Construir operaciones transaccionales
    ops = []
    
    # 1. Actualizar stock
    ops.append(("UPDATE products SET stock = %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (new_stock, product['id'])))
    
    # 1b. Parte A Fase 1: registrar en inventory_movements para delta sync (api_stock)
    qty_signed = request.quantity if request.operation == 'add' else (-request.quantity if request.operation == 'subtract' else (request.quantity - current_stock))
    mov_type = 'IN' if qty_signed >= 0 else 'OUT'
    ops.append(("""INSERT INTO inventory_movements
        (product_id, movement_type, type, quantity, reason, reference_type, user_id, timestamp, synced)
        VALUES (%s, %s, 'api_stock', %s, %s, 'api_stock', %s, NOW(), 0)""",
        (product['id'], mov_type, abs(float(qty_signed)), request.reason or 'Actualización remota', user.get('sub'),)))
    
    # 2. Log de auditoría
    if has_user_id:
        ops.append(("""INSERT INTO inventory_log 
                   (product_id, change_type, quantity, notes, user_id, timestamp)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                   (product['id'], request.operation, request.quantity, 
                    request.reason or 'Actualización remota', user['sub'], 
                    datetime.now().isoformat())))
    else:
        # Fallback: INSERT sin user_id
        ops.append(("""INSERT INTO inventory_log 
                   (product_id, change_type, quantity, notes, timestamp)
                   VALUES (%s, %s, %s, %s, %s)""",
                   (product['id'], request.operation, request.quantity, 
                    request.reason or 'Actualización remota', 
                    datetime.now().isoformat())))
    
    # Ejecutar en transacción atómica
    result = core.db.execute_transaction(ops, timeout=5)
    if not result.get('success'):
        raise HTTPException(status_code=500, detail="Error actualizando stock y registro de auditoría")
    
    return {
        "success": True,
        "product_id": product['id'],
        "previous_stock": current_stock,
        "new_stock": new_stock
    }

# ==============================================================================
# ENDPOINTS DE MERMAS
# ==============================================================================

@app.get("/api/mermas/pending", deprecated=True)
async def get_pending_mermas(user: Dict = Depends(verify_token)):
    """DEPRECATED: Use GET /api/v1/mermas/pending instead."""
    logger.warning("DEPRECATED: /api/mermas/pending — use /api/v1/mermas/pending")
    core = get_core()
    
    sql = """
        SELECT id, product_name, quantity, reason, category,
               photo_path, witness_name, created_at, status
        FROM loss_records
        WHERE status = 'pending'
        ORDER BY created_at DESC
        LIMIT 20
    """
    
    mermas = list(core.db.execute_query(sql))
    
    return {
        "count": len(mermas),
        "mermas": [{
            "id": m['id'],
            "product": m['product_name'],
            "quantity": float(m['quantity']),
            "reason": m['reason'],
            "category": m['category'],
            "has_photo": m['photo_path'] is not None,
            "witness": m['witness_name'],
            "created_at": m['created_at']
        } for m in mermas]
    }

@app.post("/api/mermas/approve", deprecated=True)
async def approve_merma(request: MermaApprovalRequest, user: Dict = Depends(verify_token)):
    """DEPRECATED: Use POST /api/v1/mermas/approve instead."""
    logger.warning("DEPRECATED: /api/mermas/approve — use /api/v1/mermas/approve")
    core = get_core()
    
    new_status = 'approved' if request.approved else 'rejected'
    
    core.db.execute_write(
        """UPDATE loss_records 
           SET status = %s, authorized_by = %s, authorized_at = %s
           WHERE id = %s""",
        (new_status, user['sub'], datetime.now().isoformat(), request.merma_id)
    )
    
    # TODO: Generate destruction acta PDF when approved (see LegalDocumentGenerator)

    return {"success": True, "status": new_status}

# ==============================================================================
# ENDPOINTS DE DASHBOARD RESICO
# ==============================================================================

@app.get("/api/dashboard/resico", deprecated=True)
async def get_resico_dashboard(user: Dict = Depends(verify_token)):
    """DEPRECATED: Use GET /api/v1/dashboard/resico instead."""
    logger.warning("DEPRECATED: /api/dashboard/resico — use /api/v1/dashboard/resico")
    core = get_core()
    year = datetime.now().year
    
    # Total facturado Serie A
    sql_a = """
        SELECT COALESCE(SUM(total), 0) as total
        FROM sales WHERE serie = 'A' 
        AND EXTRACT(YEAR FROM timestamp::timestamp) = %s
        AND status = 'completed'
    """
    result_a = list(core.db.execute_query(sql_a, (year,)))
    facturado_a = float(result_a[0]['total'] or 0) if result_a else 0
    
    # Total Serie B
    sql_b = """
        SELECT COALESCE(SUM(total), 0) as total
        FROM sales WHERE serie = 'B'
        AND EXTRACT(YEAR FROM timestamp::timestamp) = %s
        AND status = 'completed'
    """
    result_b = list(core.db.execute_query(sql_b, (year,)))
    facturado_b = float(result_b[0]['total'] or 0) if result_b else 0
    
    limite = 3500000
    restante = limite - facturado_a
    porcentaje = (facturado_a / limite) * 100
    
    # Proyección
    # FIX 2026-02-01: Ensure divisor is never zero
    dias = (datetime.now() - datetime(year, 1, 1)).days
    dias = max(dias, 1)  # Ensure at least 1 day to prevent division by zero
    proyeccion = (facturado_a / dias) * 365
    
    return {
        "serie_a": facturado_a,
        "serie_b": facturado_b,
        "total": facturado_a + facturado_b,
        "limite_resico": limite,
        "restante": restante,
        "porcentaje": round(porcentaje, 2),
        "proyeccion_anual": round(proyeccion, 2),
        "status": "GREEN" if porcentaje < 70 else ("YELLOW" if porcentaje < 90 else "RED"),
        "dias_restantes": 365 - dias
    }

@app.get("/api/dashboard/wealth", deprecated=True)
async def get_wealth_dashboard(user: Dict = Depends(verify_token)):
    """DEPRECATED: Use GET /api/v1/dashboard/wealth instead."""
    logger.warning("DEPRECATED: /api/dashboard/wealth — use /api/v1/dashboard/wealth")
    if user['role'] not in ['admin', 'owner']:
        raise HTTPException(status_code=403, detail="Solo admin/owner")
    
    core = get_core()
    
    from app.fiscal.wealth_dashboard import WealthDashboard
    wealth = WealthDashboard(core)
    
    data = wealth.get_real_wealth()
    
    return {
        "ingresos_total": data['ingresos']['total'],
        "serie_a": data['ingresos']['serie_a']['total'],
        "serie_b": data['ingresos']['serie_b']['total'],
        "gastos": data['gastos']['total'],
        "impuestos": data['impuestos']['total'],
        "utilidad_bruta": data['utilidad_bruta'],
        "utilidad_neta": data['utilidad_neta'],
        "disponible_retiro": data['disponible_retiro'],
        "ratio": data['ratio_utilidad']
    }

@app.get("/api/dashboard/quick", deprecated=True)
async def get_quick_status(user: Dict = Depends(verify_token)):
    """DEPRECATED: Use GET /api/v1/dashboard/quick instead."""
    logger.warning("DEPRECATED: /api/dashboard/quick — use /api/v1/dashboard/quick")
    core = get_core()
    
    # Ventas de hoy
    today = datetime.now().strftime('%Y-%m-%d')
    sql = """
        SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total
        FROM sales WHERE CAST(timestamp AS DATE) = %s AND status = 'completed'
    """
    result = list(core.db.execute_query(sql, (today,)))
    
    # Mermas pendientes
    mermas = list(core.db.execute_query(
        "SELECT COUNT(*) as c FROM loss_records WHERE status = 'pending'"
    ))
    
    return {
        "ventas_hoy": result[0]['count'] if result else 0,
        "total_hoy": float(result[0]['total']) if result else 0,
        "mermas_pendientes": mermas[0]['c'] if mermas else 0,
        "timestamp": datetime.now().isoformat()
    }

# ==============================================================================
# ENDPOINTS DE PRECIOS
# ==============================================================================

class SimplePriceUpdateRequest(BaseModel):
    sku: str
    new_price: float = Field(..., gt=0, description="Price must be positive")

    @field_validator('new_price')
    @classmethod
    def validate_price(cls, v):
        if math.isnan(v) or math.isinf(v):
            raise ValueError('new_price cannot be NaN or Infinity')
        if v <= 0:
            raise ValueError('new_price must be positive')
        if v > 10_000_000:
            raise ValueError('new_price exceeds maximum allowed value')
        return round(v, 2)

@app.post("/api/products/price", deprecated=True)
async def update_price(
    request: SimplePriceUpdateRequest,
    user: Dict = Depends(verify_token)
):
    """DEPRECATED: Use POST /api/v1/products/price instead."""
    logger.warning("DEPRECATED: /api/products/price — use /api/v1/products/price")
    if user['role'] not in ['admin', 'manager', 'owner']:
        raise HTTPException(status_code=403, detail="Sin permisos")

    core = get_core()

    product = core.get_product_by_sku(request.sku)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    old_price = float(product['price'])

    core.db.execute_write(
        "UPDATE products SET price = %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (request.new_price, product['id'])
    )

    return {
        "success": True,
        "product_id": product['id'],
        "old_price": old_price,
        "new_price": request.new_price
    }

# ==============================================================================
# HEALTH CHECK
# ==============================================================================

@app.get("/api/health")
async def health_check():
    """Health check (sin autenticación)."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

# ==============================================================================
# AI DASHBOARD
# ==============================================================================

@app.get("/api/dashboard/ai", deprecated=True)
async def get_ai_dashboard(user: Dict = Depends(verify_token)):
    """DEPRECATED: Use GET /api/v1/dashboard/ai instead."""
    logger.warning("DEPRECATED: /api/dashboard/ai — use /api/v1/dashboard/ai")
    core = get_core()
    
    try:
        from app.utils.ai_analytics import AIAnalytics
        ai = AIAnalytics(core)
        
        predictions = ai.predict_stockouts(7)
        alerts = [{
            "product_name": p.product_name,
            "urgency": p.urgency.value.upper(),
            "current_stock": p.current_stock,
            "days_until_stockout": p.days_until_stockout,
            "recommended_order": p.recommended_order,
            "avg_daily_sales": p.avg_daily_sales
        } for p in predictions[:10]]
        
        top_products = ai.get_smart_top_products(5)
        anomalies = [a.to_dict() for a in ai.detect_anomalies()]
        
        return {
            "alerts": alerts,
            "top_products": top_products,
            "anomalies": anomalies
        }
    except Exception as e:
        # Fallback a versión simple si falla
        sql_low = """
            SELECT id, name, stock, min_stock
            FROM products WHERE stock <= min_stock AND stock >= 0
            ORDER BY stock ASC LIMIT 10
        """
        low_stock = list(core.db.execute_query(sql_low))
        
        # FIX 2026-02-01: Safely convert stock values with try/except
        def _safe_int(value, default=0):
            try:
                return int(value) if value is not None else default
            except (ValueError, TypeError):
                return default

        def _safe_float(value, default=0.0):
            try:
                return float(value) if value is not None else default
            except (ValueError, TypeError):
                return default

        return {
            "alerts": [{
                "product_name": p['name'],
                "urgency": "CRITICAL" if _safe_float(p.get('stock')) <= 2 else "WARNING",
                "current_stock": _safe_float(p.get('stock')),
                "days_until_stockout": max(1, _safe_int(p.get('stock'))),
                "recommended_order": _safe_int((_safe_float(p.get('min_stock')) or 5) * 2)
            } for p in low_stock],
            "top_products": [],
            "anomalies": []
        }

@app.get("/api/dashboard/executive", deprecated=True)
async def get_executive_dashboard(user: Dict = Depends(verify_token)):
    """DEPRECATED: Use GET /api/v1/dashboard/executive instead."""
    logger.warning("DEPRECATED: /api/dashboard/executive — use /api/v1/dashboard/executive")
    if user['role'] not in ['admin', 'manager', 'owner']:
        raise HTTPException(status_code=403, detail="Solo admin/manager")
    
    core = get_core()
    
    try:
        from app.utils.ai_analytics import AIAnalytics
        ai = AIAnalytics(core)
        return ai.get_executive_dashboard()
    except Exception as e:
        return {
            "error": str(e),
            "generated_at": datetime.now().isoformat(),
            "kpis": {"transactions": 0, "revenue": 0, "avg_ticket": 0},
            "hourly_sales": [],
            "comparison": {},
            "stock_predictions": [],
            "anomalies": [],
            "top_products": []
        }

# ==============================================================================
# EXPENSES
# ==============================================================================

@app.get("/api/dashboard/expenses", deprecated=True)
async def get_expenses_dashboard(user: Dict = Depends(verify_token)):
    """DEPRECATED: Use GET /api/v1/dashboard/expenses (or /api/v1/expenses/summary)."""
    logger.warning("DEPRECATED: /api/dashboard/expenses — use /api/v1/expenses/summary")
    core = get_core()
    
    # Gastos del mes
    sql_month = """
        SELECT COALESCE(SUM(amount), 0) as total
        FROM cash_movements 
        WHERE type = 'expense' 
        AND TO_CHAR(timestamp::timestamp, 'YYYY-MM') = TO_CHAR(NOW(), 'YYYY-MM')
    """
    
    # Gastos del año
    sql_year = """
        SELECT COALESCE(SUM(amount), 0) as total
        FROM cash_movements 
        WHERE type = 'expense'
        AND EXTRACT(YEAR FROM timestamp::timestamp) = EXTRACT(YEAR FROM NOW())
    """
    
    try:
        month_result = list(core.db.execute_query(sql_month))
        year_result = list(core.db.execute_query(sql_year))
        month_total = float(month_result[0]['total']) if month_result else 0
        year_total = float(year_result[0]['total']) if year_result else 0
    except Exception as e:
        logger.error(f"Error fetching monthly/yearly sales totals: {e}")
        month_total = 0
        year_total = 0
    
    return {
        "month": month_total,
        "year": year_total
    }

class ExpenseRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Expense amount must be positive")
    description: str

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        if math.isnan(v) or math.isinf(v):
            raise ValueError('amount cannot be NaN or Infinity')
        if v <= 0:
            raise ValueError('amount must be positive')
        if v > 10_000_000:  # Reasonable max for single expense
            raise ValueError('amount exceeds maximum allowed value')
        return round(v, 2)  # Round to 2 decimal places

@app.post("/api/expenses/register", deprecated=True)
async def register_expense(request: ExpenseRequest, user: Dict = Depends(verify_token)):
    """DEPRECATED: Use POST /api/v1/expenses/ instead."""
    logger.warning("DEPRECATED: /api/expenses/register — use POST /api/v1/expenses/")
    core = get_core()
    
    try:
        # CRITICAL FIX: Verificar si user_id existe antes de INSERT
        try:
            table_info = core.db.get_table_info("cash_movements")
            available_cols = [col.get('name') if isinstance(col, dict) else col[1] for col in table_info]
            has_user_id = "user_id" in available_cols
        except Exception as e:
            logger.warning(f"Could not get cash_movements table info: {e}")
            has_user_id = False
        
        if has_user_id:
            core.db.execute_write(
                """INSERT INTO cash_movements (type, amount, description, user_id, timestamp)
                   VALUES ('expense', %s, %s, %s, %s)""",
                (request.amount, request.description, user['sub'], datetime.now().isoformat())
            )
        else:
            # Fallback: INSERT sin user_id
            core.db.execute_write(
                """INSERT INTO cash_movements (type, amount, description, timestamp)
                   VALUES ('expense', %s, %s, %s)""",
                (request.amount, request.description, datetime.now().isoformat())
            )
        return {"success": True}
    except Exception as e:
        logger.error(f"Error en endpoint register_expense: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")

# ==============================================================================
# COMANDOS REMOTOS - Control del POS desde PWA
# ==============================================================================

@app.post("/api/commands/open-drawer", deprecated=True)
async def remote_open_drawer(user: Dict = Depends(verify_token)):
    """DEPRECATED: Use POST /api/v1/remote/open-drawer instead."""
    logger.warning("DEPRECATED: /api/commands/open-drawer — use /api/v1/remote/open-drawer")
    if user['role'] not in ['admin', 'manager', 'owner']:
        raise HTTPException(status_code=403, detail="Sin permisos para abrir cajón remotamente")
    
    core = get_core()
    cfg = core.get_app_config() or {}
    
    if not cfg.get("cash_drawer_enabled"):
        raise HTTPException(status_code=400, detail="Cajón no habilitado")
    
    printer = cfg.get("printer_name", "")
    if not printer:
        raise HTTPException(status_code=400, detail="Impresora no configurada")
    
    try:
        from app.utils import ticket_engine
        pulse_str = cfg.get("cash_drawer_pulse_bytes", "\\x1B\\x70\\x00\\x19\\xFA")
        ticket_engine.open_cash_drawer(printer, pulse_str)
        
        # Log de auditoría
        core.db.execute_write(
            """INSERT INTO audit_log (action, entity_type, entity_id, user_id, details, timestamp)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            ('REMOTE_DRAWER_OPEN', 'cash_drawer', 0, user['sub'], 
             '{"source": "PWA Remote Command"}', datetime.now().isoformat())
        )
        
        return {"success": True, "message": "Cajón abierto remotamente"}
    except Exception as e:
        logger.error(f"Error en endpoint remote_open_drawer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.get("/api/commands/turn-status", deprecated=True)
async def get_turn_status(user: Dict = Depends(verify_token)):
    """DEPRECATED: Use GET /api/v1/remote/turn-status instead."""
    logger.warning("DEPRECATED: /api/commands/turn-status — use /api/v1/remote/turn-status")
    core = get_core()
    
    try:
        # Buscar turno activo
        sql = """
            SELECT t.id, t.user_id, t.initial_cash, t.created_at, u.username
            FROM turns t
            LEFT JOIN users u ON t.user_id = u.id
            WHERE t.status = 'open'
            ORDER BY t.created_at DESC
            LIMIT 1
        """
        turns = list(core.db.execute_query(sql))
        
        if not turns:
            return {"active": False, "message": "Sin turno activo"}
        
        turn = turns[0]
        summary = core.get_turn_summary(turn['id'])
        
        return {
            "active": True,
            "turn_id": turn['id'],
            "user": turn['username'] or f"Usuario #{turn['user_id']}",
            "started_at": turn['created_at'],
            "initial_cash": float(turn['initial_cash'] or 0),
            "cash_sales": float(summary.get('cash_sales', 0)),
            "card_sales": float(summary.get('card_sales', 0)),
            "total_in": float(summary.get('total_in', 0)),
            "total_out": float(summary.get('total_out', 0)),
            "expected_cash": float(summary.get('expected_cash', 0))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/commands/live-sales", deprecated=True)
async def get_live_sales(user: Dict = Depends(verify_token), limit: int = 10):
    """DEPRECATED: Use GET /api/v1/remote/live-sales instead."""
    logger.warning("DEPRECATED: /api/commands/live-sales — use /api/v1/remote/live-sales")
    # Validar limite maximo para evitar queries excesivas
    limit = min(max(1, limit), 100)
    core = get_core()
    
    sql = """
        SELECT s.id, s.folio_visible, s.total, s.payment_method, s.serie,
               s.timestamp, c.name as customer_name
        FROM sales s
        LEFT JOIN customers c ON s.customer_id = c.id
        WHERE s.status = 'completed'
        ORDER BY s.timestamp DESC
        LIMIT %s
    """
    
    sales = list(core.db.execute_query(sql, (limit,)))
    
    return {
        "count": len(sales),
        "sales": [{
            "id": s['id'],
            "folio": s['folio_visible'] or f"#{s['id']}",
            "total": float(s['total'] or 0),
            "payment": s['payment_method'],
            "serie": s['serie'],
            "customer": s['customer_name'] or 'Público General',
            "timestamp": s['timestamp']
        } for s in sales]
    }

class NotificationRequest(BaseModel):
    title: str
    message: str
    priority: str = "normal"  # low, normal, high, urgent

@app.post("/api/commands/send-notification", deprecated=True)
async def send_notification_to_pos(request: NotificationRequest, user: Dict = Depends(verify_token)):
    """DEPRECATED: Use POST /api/v1/remote/notification instead (with corrected DB schema)."""
    logger.warning("DEPRECATED: /api/commands/send-notification — use /api/v1/remote/notification")
    if user['role'] not in ['admin', 'manager', 'owner']:
        raise HTTPException(status_code=403, detail="Sin permisos")
    
    core = get_core()
    
    # Guardar notificación en BD para que el POS la recoja
    try:
        core.db.execute_write(
            """INSERT INTO remote_notifications 
               (title, message, priority, sender_id, created_at, read)
               VALUES (%s, %s, %s, %s, %s, 0)""",
            (request.title, request.message, request.priority, 
             user['sub'], datetime.now().isoformat())
        )
        return {"success": True, "message": "Notificación enviada al POS"}
    except Exception as e:
        # Tabla puede no existir, crearla
        try:
            core.db.execute_write("""
                CREATE TABLE IF NOT EXISTS remote_notifications (
                    id INTEGER PRIMARY KEY,
                    title TEXT,
                    message TEXT,
                    priority TEXT DEFAULT 'normal',
                    sender_id INTEGER,
                    created_at TEXT,
                    read INTEGER DEFAULT 0
                )
            """)
            core.db.execute_write(
                """INSERT INTO remote_notifications 
                   (title, message, priority, sender_id, created_at, read)
                   VALUES (%s, %s, %s, %s, %s, 0)""",
                (request.title, request.message, request.priority, 
                 user['sub'], datetime.now().isoformat())
            )
            return {"success": True, "message": "Notificación enviada al POS"}
        except Exception as e2:
            raise HTTPException(status_code=500, detail=str(e2))

@app.get("/api/commands/pending-notifications", deprecated=True)
async def get_pending_notifications(user: Dict = Depends(verify_token)):
    """DEPRECATED: Use GET /api/v1/remote/notifications/pending instead."""
    logger.warning("DEPRECATED: /api/commands/pending-notifications — use /api/v1/remote/notifications/pending")
    core = get_core()
    
    try:
        notifications = list(core.db.execute_query(
            """SELECT id, title, message, priority, created_at 
               FROM remote_notifications 
               WHERE read = 0 
               ORDER BY created_at DESC"""
        ))
        
        # Marcar como leídas
        if notifications:
            core.db.execute_write("UPDATE remote_notifications SET read = 1, updated_at = CURRENT_TIMESTAMP WHERE read = 0")
        
        return {
            "count": len(notifications),
            "notifications": [{
                "id": n['id'],
                "title": n['title'],
                "message": n['message'],
                "priority": n['priority'],
                "timestamp": n['created_at']
            } for n in notifications]
        }
    except Exception:
        return {"count": 0, "notifications": []}

class PriceChangeRequest(BaseModel):
    sku: str
    new_price: float = Field(..., gt=0, description="Price must be positive")
    reason: Optional[str] = None

    @field_validator('new_price')
    @classmethod
    def validate_price(cls, v):
        if math.isnan(v) or math.isinf(v):
            raise ValueError('new_price cannot be NaN or Infinity')
        if v <= 0:
            raise ValueError('new_price must be positive')
        if v > 10_000_000:  # Reasonable max price
            raise ValueError('new_price exceeds maximum allowed value')
        return round(v, 2)  # Round to 2 decimal places

@app.post("/api/commands/change-price", deprecated=True)
async def remote_change_price(request: PriceChangeRequest, user: Dict = Depends(verify_token)):
    """DEPRECATED: Use POST /api/v1/remote/change-price instead."""
    logger.warning("DEPRECATED: /api/commands/change-price — use /api/v1/remote/change-price")
    if user['role'] not in ['admin', 'manager', 'owner']:
        raise HTTPException(status_code=403, detail="Sin permisos para cambiar precios")
    
    core = get_core()
    product = core.get_product_by_sku(request.sku)
    
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    old_price = float(product['price'])
    
    # Actualizar precio
    core.db.execute_write(
        "UPDATE products SET price = %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (request.new_price, product['id'])
    )

    # Log de auditoría
    core.db.execute_write(
        """INSERT INTO audit_log (action, entity_type, entity_id, user_id, details, timestamp)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        ('REMOTE_PRICE_CHANGE', 'product', product['id'], user['sub'],
         f'{{"old_price": {old_price}, "new_price": {request.new_price}, "reason": "{request.reason or "PWA Remote"}"}}',
         datetime.now().isoformat())
    )
    
    return {
        "success": True,
        "product_id": product['id'],
        "product_name": product['name'],
        "old_price": old_price,
        "new_price": request.new_price
    }

@app.get("/api/commands/system-status", deprecated=True)
async def get_system_status(user: Dict = Depends(verify_token)):
    """DEPRECATED: Use GET /api/v1/remote/system-status instead."""
    logger.warning("DEPRECATED: /api/commands/system-status — use /api/v1/remote/system-status")
    core = get_core()
    
    try:
        # Status de turno
        turn_sql = "SELECT COUNT(*) as c FROM turns WHERE status = 'open'"
        turn_result = list(core.db.execute_query(turn_sql))
        turn_active = turn_result[0]['c'] > 0 if turn_result else False
        
        # Ventas de hoy
        today = datetime.now().strftime('%Y-%m-%d')
        sales_sql = """
            SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total
            FROM sales WHERE timestamp::date = %s AND status = 'completed'
        """
        sales_result = list(core.db.execute_query(sales_sql, (today,)))
        
        # Productos con stock bajo
        low_stock_sql = "SELECT COUNT(*) as c FROM products WHERE stock <= min_stock AND stock >= 0"
        low_stock_result = list(core.db.execute_query(low_stock_sql))
        
        # Config de impresora
        cfg = core.get_app_config() or {}
        
        return {
            "pos_online": True,
            "turn_active": turn_active,
            "sales_today": sales_result[0]['count'] if sales_result else 0,
            "total_today": float(sales_result[0]['total']) if sales_result else 0,
            "low_stock_alerts": low_stock_result[0]['c'] if low_stock_result else 0,
            "printer_configured": bool(cfg.get("printer_name")),
            "drawer_enabled": bool(cfg.get("cash_drawer_enabled")),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "pos_online": True,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# ==============================================================================
# ENDPOINTS CRUD DE PRODUCTOS (Para PWA)
# ==============================================================================

class ProductCreateRequest(BaseModel):
    sku: str
    name: str
    price: float = Field(..., ge=0, description="Price must be non-negative")
    cost: float = Field(default=0, ge=0, description="Cost must be non-negative")
    stock: float = Field(default=0, ge=0, description="Stock must be non-negative")
    min_stock: float = Field(default=5, ge=0, description="Min stock must be non-negative")
    category: Optional[str] = None
    sat_clave_prod_serv: str = "01010101"
    sat_clave_unidad: str = "H87"
    branch_id: Optional[int] = None
    sync_all_branches: bool = False

    @field_validator('price', 'cost', 'stock', 'min_stock')
    @classmethod
    def validate_numeric_fields(cls, v, info):
        if math.isnan(v) or math.isinf(v):
            raise ValueError(f'{info.field_name} cannot be NaN or Infinity')
        if v < 0:
            raise ValueError(f'{info.field_name} must be non-negative')
        if v > 100_000_000:  # Reasonable max
            raise ValueError(f'{info.field_name} exceeds maximum allowed value')
        return round(v, 2) if info.field_name in ('price', 'cost') else v

class ProductUpdateRequest(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = Field(default=None, ge=0, description="Price must be non-negative")
    cost: Optional[float] = Field(default=None, ge=0, description="Cost must be non-negative")
    stock: Optional[float] = Field(default=None, ge=0, description="Stock must be non-negative")
    min_stock: Optional[float] = Field(default=None, ge=0, description="Min stock must be non-negative")
    category: Optional[str] = None
    sat_clave_prod_serv: Optional[str] = None
    sat_clave_unidad: Optional[str] = None
    sync_all_branches: bool = False
    prices_by_branch: Optional[List[Dict]] = None  # [{branch_id, price}]

    @field_validator('price', 'cost', 'stock', 'min_stock')
    @classmethod
    def validate_numeric_fields(cls, v, info):
        if v is None:
            return v
        if math.isnan(v) or math.isinf(v):
            raise ValueError(f'{info.field_name} cannot be NaN or Infinity')
        if v < 0:
            raise ValueError(f'{info.field_name} must be non-negative')
        if v > 100_000_000:  # Reasonable max
            raise ValueError(f'{info.field_name} exceeds maximum allowed value')
        return round(v, 2) if info.field_name in ('price', 'cost') else v

@app.get("/api/products")
async def list_products(
    branch_id: Optional[int] = None,
    search: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    user: Dict = Depends(verify_token)
):
    """Lista productos con filtros opcionales."""
    # Validar limites para evitar queries excesivas
    limit = min(max(1, limit), 500)
    offset = max(0, offset)
    core = get_core()

    # SECURITY: Build WHERE clause safely using parameterized queries
    # - conditions[] contains ONLY hardcoded SQL fragments with %s placeholders
    # - params[] contains the actual user values that will be escaped by the DB driver
    # - NEVER interpolate user input directly into conditions[]
    conditions = ["is_active = 1"]
    params = []

    if search:
        conditions.append("(name LIKE %s OR sku LIKE %s OR barcode LIKE %s)")
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])

    if category:
        conditions.append("category = %s")
        params.append(category)

    where_clause = " AND ".join(conditions)
    
    sql = f"""
        SELECT id, sku, barcode, name, price, cost, stock, min_stock,
               category, sat_clave_prod_serv, sat_clave_unidad, sat_descripcion,
               is_active, created_at, updated_at
        FROM products
        WHERE {where_clause}
        ORDER BY name ASC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])
    
    try:
        products = list(core.db.execute_query(sql, tuple(params)))

        # Count total (reuse same where_clause with params excluding LIMIT/OFFSET)
        # SECURITY: where_clause uses %s placeholders, values passed via params tuple
        count_sql = f"SELECT COUNT(*) as total FROM products WHERE {where_clause}"
        count_params = tuple(params[:-2])  # Exclude limit and offset
        count_result = list(core.db.execute_query(count_sql, count_params))
        total = count_result[0]['total'] if count_result else len(products)
        
        return {
            "success": True,
            "products": [{
                "id": p['id'],
                "sku": p['sku'],
                "barcode": p.get('barcode'),
                "name": p['name'],
                "price": float(p['price'] or 0),
                "cost": float(p.get('cost') or 0),
                "stock": float(p.get('stock') or 0),
                "min_stock": float(p.get('min_stock') or 5),
                "category": p.get('category'),
                "sat_code": p.get('sat_clave_prod_serv', '01010101'),
                "sat_unit": p.get('sat_clave_unidad', 'H87'),
                "sat_desc": p.get('sat_descripcion', ''),
                "is_active": bool(p.get('is_active', 1))
            } for p in products],
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products/{product_id}")
async def get_product(product_id: int, user: Dict = Depends(verify_token)):
    """Obtiene un producto por ID."""
    if product_id <= 0:
        raise HTTPException(status_code=400, detail="product_id debe ser positivo")
    core = get_core()

    sql = """
        SELECT id, sku, barcode, name, price, cost, stock, min_stock,
               category, sat_clave_prod_serv, sat_clave_unidad, sat_descripcion,
               is_active, created_at, updated_at
        FROM products WHERE id = %s
    """
    
    try:
        result = list(core.db.execute_query(sql, (product_id,)))
        if not result:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        
        p = result[0]
        return {
            "success": True,
            "product": {
                "id": p['id'],
                "sku": p['sku'],
                "barcode": p.get('barcode'),
                "name": p['name'],
                "price": float(p['price'] or 0),
                "cost": float(p.get('cost') or 0),
                "stock": float(p.get('stock') or 0),
                "min_stock": float(p.get('min_stock') or 5),
                "category": p.get('category'),
                "sat_code": p.get('sat_clave_prod_serv', '01010101'),
                "sat_unit": p.get('sat_clave_unidad', 'H87'),
                "sat_desc": p.get('sat_descripcion', '')
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/products")
async def create_product(request: ProductCreateRequest, user: Dict = Depends(verify_token)):
    """Crea un nuevo producto."""
    if user['role'] not in ['admin', 'manager', 'owner']:
        raise HTTPException(status_code=403, detail="Sin permisos para crear productos")
    
    core = get_core()
    
    # Verificar SKU único
    existing = list(core.db.execute_query("SELECT id FROM products WHERE sku = %s", (request.sku,)))
    if existing:
        raise HTTPException(status_code=400, detail="SKU ya existe")
    
    sql = """
        INSERT INTO products (sku, name, price, cost, stock, min_stock, category,
                              sat_clave_prod_serv, sat_clave_unidad, sat_code, sat_unit,
                              is_active, synced, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, 0, %s, %s)
    """
    
    now = datetime.now().isoformat()
    
    try:
        # Use RETURNING id for PostgreSQL compatibility
        sql_with_returning = sql.replace(")", " RETURNING id)")
        try:
            # Try with RETURNING (PostgreSQL)
            result = core.db.execute_query(sql_with_returning, (
                request.sku,
                request.name,
                request.price,
                request.cost,
                request.stock,
                request.min_stock,
                request.category,
                request.sat_clave_prod_serv,
                request.sat_clave_unidad,
                request.sat_clave_prod_serv,  # sat_code duplicado
                request.sat_clave_unidad,      # sat_unit duplicado
                now, now
            ))
            product_id = result[0]['id'] if result else None
        except Exception:
            # Fallback: execute_write returns the ID in DatabaseManager
            product_id = core.db.execute_write(sql, (
                request.sku,
                request.name,
                request.price,
                request.cost,
                request.stock,
                request.min_stock,
                request.category,
                request.sat_clave_prod_serv,
                request.sat_clave_unidad,
                request.sat_clave_prod_serv,  # sat_code duplicado
                request.sat_clave_unidad,      # sat_unit duplicado
                now, now
            ))
        
        # Log de auditoría
        details = json.dumps({"sku": request.sku, "name": request.name, "source": "PWA"})
        core.db.execute_write(
            """INSERT INTO audit_log (action, entity_type, entity_id, user_id, details, timestamp)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            ('PRODUCT_CREATED', 'product', product_id, user['sub'], details, now)
        )

        return {
            "success": True,
            "product_id": product_id,
            "message": "Producto creado exitosamente"
        }
    except Exception as e:
        logger.error(f"Error en endpoint create_product: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.put("/api/products/{product_id}")
async def update_product(product_id: int, request: ProductUpdateRequest, user: Dict = Depends(verify_token)):
    """Actualiza un producto existente."""
    if product_id <= 0:
        raise HTTPException(status_code=400, detail="product_id debe ser positivo")
    if user['role'] not in ['admin', 'manager', 'owner']:
        raise HTTPException(status_code=403, detail="Sin permisos para editar productos")

    core = get_core()
    
    # Verificar que existe
    existing = list(core.db.execute_query("SELECT * FROM products WHERE id = %s", (product_id,)))
    if not existing:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Construir UPDATE dinámico
    updates = []
    params = []
    
    if request.name is not None:
        updates.append("name = %s")
        params.append(request.name)
    if request.price is not None:
        updates.append("price = %s")
        params.append(request.price)
    if request.cost is not None:
        updates.append("cost = %s")
        params.append(request.cost)
    if request.stock is not None:
        updates.append("stock = %s")
        params.append(request.stock)
    if request.min_stock is not None:
        updates.append("min_stock = %s")
        params.append(request.min_stock)
    if request.category is not None:
        updates.append("category = %s")
        params.append(request.category)
    if request.sat_clave_prod_serv is not None:
        updates.append("sat_clave_prod_serv = %s")
        updates.append("sat_code = %s")
        params.append(request.sat_clave_prod_serv)
        params.append(request.sat_clave_prod_serv)
    if request.sat_clave_unidad is not None:
        updates.append("sat_clave_unidad = %s")
        updates.append("sat_unit = %s")
        params.append(request.sat_clave_unidad)
        params.append(request.sat_clave_unidad)
    
    if not updates:
        return {"success": True, "message": "Sin cambios"}

    # Marcar para sincronización
    # FIX 2026-02-01: Eliminada duplicación de columna synced
    updates.append("synced = %s")
    params.append(0)
    updates.append("updated_at = %s")
    now = datetime.now().isoformat()
    params.append(now)
    params.append(product_id)

    sql = f"UPDATE products SET {', '.join(updates)} WHERE id = %s"
    
    try:
        core.db.execute_write(sql, tuple(params))
        
        # Log de auditoría
        core.db.execute_write(
            """INSERT INTO audit_log (action, entity_type, entity_id, user_id, details, timestamp)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            ('PRODUCT_UPDATED', 'product', product_id, user['sub'], 
             f'{{"source": "PWA", "sync_all": {str(request.sync_all_branches).lower()}}}', now)
        )
        
        return {"success": True, "message": "Producto actualizado"}
    except Exception as e:
        logger.error(f"Error en endpoint update_product: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.delete("/api/products/{product_id}")
async def delete_product(product_id: int, branch_id: Optional[int] = None, user: Dict = Depends(verify_token)):
    """Elimina (desactiva) un producto."""
    if product_id <= 0:
        raise HTTPException(status_code=400, detail="product_id debe ser positivo")
    if user['role'] not in ['admin', 'manager', 'owner']:
        raise HTTPException(status_code=403, detail="Sin permisos para eliminar productos")

    core = get_core()
    
    # Verificar que existe
    existing = list(core.db.execute_query("SELECT name FROM products WHERE id = %s", (product_id,)))
    if not existing:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    product_name = existing[0]['name']
    now = datetime.now().isoformat()
    
    try:
        # Soft delete (desactivar) - marcar synced = 0 para sincronizar la eliminación
        core.db.execute_write(
            "UPDATE products SET is_active = 0, visible = 0, synced = 0, updated_at = %s WHERE id = %s",
            (now, product_id)
        )
        
        # Log de auditoría
        core.db.execute_write(
            """INSERT INTO audit_log (action, entity_type, entity_id, user_id, details, timestamp)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            ('PRODUCT_DELETED', 'product', product_id, user['sub'], 
             f'{{"name": "{product_name}", "source": "PWA"}}', now)
        )
        
        return {"success": True, "message": "Producto eliminado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products/{product_id}/stock-by-branch", deprecated=True)
async def get_product_stock_by_branch(product_id: int, user: Dict = Depends(verify_token)):
    """DEPRECATED: Use GET /api/v1/products/{product_id}/stock-by-branch instead."""
    logger.warning("DEPRECATED: /api/products/{id}/stock-by-branch — use /api/v1/products/{id}/stock-by-branch")
    if product_id <= 0:
        raise HTTPException(status_code=400, detail="product_id debe ser positivo")
    core = get_core()

    # Verificar que existe
    product = list(core.db.execute_query(
        "SELECT id, name, stock, price FROM products WHERE id = %s", (product_id,)
    ))
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    p = product[0]
    
    # Obtener sucursales
    branches = list(core.db.execute_query(
        "SELECT id, name FROM branches WHERE is_active = 1"
    ))
    
    # Por ahora, devolver stock global (sin multi-sucursal real)
    # En una implementación completa, habría una tabla product_branch_stock
    branch_data = []
    for branch in branches:
        branch_data.append({
            "branch_id": branch['id'],
            "branch_name": branch['name'],
            "stock": float(p['stock'] or 0),  # Mismo stock para todas por ahora
            "price": float(p['price'] or 0)   # Mismo precio para todas por ahora
        })
    
    # Si no hay sucursales, crear una por defecto
    if not branch_data:
        branch_data = [{
            "branch_id": 1,
            "branch_name": "Sucursal Principal",
            "stock": float(p['stock'] or 0),
            "price": float(p['price'] or 0)
        }]
    
    return {
        "success": True,
        "product_id": product_id,
        "product_name": p['name'],
        "branches": branch_data
    }

@app.get("/api/products/categories", deprecated=True)
async def get_product_categories(user: Dict = Depends(verify_token)):
    """DEPRECATED: Use GET /api/v1/products/categories/list instead."""
    logger.warning("DEPRECATED: /api/products/categories — use /api/v1/products/categories/list")
    core = get_core()
    
    try:
        # Obtener de tabla categories
        categories = list(core.db.execute_query(
            "SELECT DISTINCT name FROM categories WHERE is_active = 1 ORDER BY name"
        ))
        
        if categories:
            return {
                "success": True,
                "categories": [c['name'] for c in categories if c['name']]
            }
        
        # Fallback: obtener de productos
        categories = list(core.db.execute_query(
            "SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category != '' ORDER BY category"
        ))
        
        return {
            "success": True,
            "categories": [c['category'] for c in categories if c['category']]
        }
    except Exception as e:
        return {
            "success": True,
            "categories": ["Rostro", "Cabello", "Cuerpo", "Maquillaje", "Uñas", "Accesorios", "Otros"]
        }

@app.get("/api/v1/terminals")
async def get_terminals(user: Dict = Depends(verify_token)):
    """Obtiene lista de sucursales/terminales."""
    core = get_core()
    
    try:
        branches = list(core.db.execute_query(
            "SELECT id, name, code, is_active FROM branches WHERE is_active = 1 ORDER BY id"
        ))
        
        return {
            "success": True,
            "terminals": [{
                "terminal_id": b['id'],
                "terminal_name": b['name'],
                "branch_id": b['id'],
                "code": b.get('code'),
                "is_active": bool(b.get('is_active', 1))
            } for b in branches]
        }
    except Exception:
        return {
            "success": True,
            "terminals": [
                {"terminal_id": 1, "terminal_name": "Sucursal Principal", "branch_id": 1, "is_active": True}
            ]
        }

# ==============================================================================
# ENDPOINTS CATÁLOGO SAT (Para PWA)
# ==============================================================================

@app.get("/api/sat/search", deprecated=True)
async def search_sat_codes(
    query: str,
    limit: int = 20,
    user: Dict = Depends(verify_token)
):
    """DEPRECATED: Use GET /api/v1/sat/search instead."""
    logger.warning("DEPRECATED: /api/sat/search — use /api/v1/sat/search")
    # Validar limite maximo
    limit = min(max(1, limit), 100)
    if not query or len(query) < 2:
        return {"success": True, "results": [], "total": 0}
    
    try:
        from app.fiscal.sat_catalog_full import get_catalog_manager, search_sat_catalog

        # Buscar en catálogo
        results = search_sat_catalog(query, limit=limit)
        
        return {
            "success": True,
            "results": [
                {"code": code, "description": desc}
                for code, desc in results
            ],
            "total": len(results)
        }
    except Exception as e:
        # Fallback: búsqueda básica en códigos comunes
        common_codes = [
            ("01010101", "No existe en el catálogo"),
            ("53131500", "Productos para el cuidado de la piel"),
            ("53131501", "Cremas faciales"),
            ("53131502", "Cremas corporales"),
            ("53131600", "Productos para el cabello"),
            ("53131601", "Shampoo"),
            ("53131602", "Acondicionador"),
            ("53131700", "Perfumes y fragancias"),
            ("53131800", "Productos para el cabello"),
            ("53131801", "Shampoo"),
            ("53131802", "Acondicionador"),
            ("53131900", "Productos de maquillaje"),
            ("53131901", "Labiales"),
            ("53131902", "Bases de maquillaje"),
            ("53132000", "Productos de higiene personal"),
            ("50181900", "Dulces y chocolates"),
            ("50192100", "Bebidas"),
            ("50101500", "Frutas"),
            ("50101700", "Verduras frescas"),
            ("44121600", "Papelería"),
            ("46181500", "Ropa"),
        ]
        
        query_lower = query.lower()
        filtered = [
            {"code": code, "description": desc}
            for code, desc in common_codes
            if query_lower in code.lower() or query_lower in desc.lower()
        ][:limit]
        
        return {
            "success": True,
            "results": filtered,
            "total": len(filtered),
            "fallback": True
        }

@app.get("/api/sat/code/{code}", deprecated=True)
async def get_sat_code_info(code: str, user: Dict = Depends(verify_token)):
    """DEPRECATED: Use GET /api/v1/sat/{code} instead."""
    logger.warning("DEPRECATED: /api/sat/code — use /api/v1/sat/{code}")
    try:
        from app.fiscal.sat_catalog_full import get_sat_description
        
        description = get_sat_description(code)
        
        if description:
            return {
                "success": True,
                "code": code,
                "description": description
            }
        else:
            return {
                "success": False,
                "code": code,
                "description": "No existe en el catálogo",
                "message": "Código no encontrado"
            }
    except Exception as e:
        return {
            "success": False,
            "code": code,
            "description": "No existe en el catálogo",
            "error": str(e)
        }

# Run: uvicorn app.api.mobile_api:app --host 0.0.0.0 --port 8080
