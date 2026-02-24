"""
Admin API - FastAPI endpoints para control remoto
Ghost Admin: Solo accesible via Tailscale o red local
"""

import json
import logging
import math
import os
import secrets
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, field_validator, Field

logger = logging.getLogger(__name__)

# SECURITY: Load admin credentials from environment variables (required)
_ADMIN_API_USER = os.environ.get('ADMIN_API_USER')
_ADMIN_API_PASSWORD = os.environ.get('ADMIN_API_PASSWORD')

if not _ADMIN_API_USER or not _ADMIN_API_PASSWORD:
    raise RuntimeError(
        "SECURITY ERROR: ADMIN_API_USER and ADMIN_API_PASSWORD environment variables are required. "
        "Set these variables before starting the Admin API."
    )

# FastAPI app
app = FastAPI(
    title="TITAN POS Admin API",
    description="API de administración remota para TITAN POS",
    version="1.0.0"
)

security = HTTPBasic()

# Global core reference (set at startup)
_core = None

def set_core(core):
    """Set the POSCore instance for API use."""
    global _core
    _core = core

def get_core():
    """Get core instance."""
    if _core is None:
        raise HTTPException(status_code=500, detail="Core not initialized")
    return _core

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify admin credentials using environment variables."""
    if not secrets.compare_digest(credentials.username, _ADMIN_API_USER):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not secrets.compare_digest(credentials.password, _ADMIN_API_PASSWORD):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return credentials.username

# ==========================================
# MODELS
# ==========================================

# FIX 2026-02-01: Nombre correcto de la clase (era PriceUpCAST)
class PriceUpdate(BaseModel):
    product_id: int = Field(..., gt=0, description="Product ID must be positive")
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

class AuthorizationRequest(BaseModel):
    action_type: str
    amount: float = Field(..., gt=0, description="Amount must be positive")
    reason: str

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        if math.isnan(v) or math.isinf(v):
            raise ValueError('amount cannot be NaN or Infinity')
        if v <= 0:
            raise ValueError('amount must be positive')
        if v > 100_000_000:
            raise ValueError('amount exceeds maximum allowed value')
        return round(v, 2)

class TurnClose(BaseModel):
    turn_id: int = Field(..., gt=0, description="Turn ID must be positive")
    counted_cash: float = Field(..., ge=0, description="Counted cash must be non-negative")

    @field_validator('counted_cash')
    @classmethod
    def validate_cash(cls, v):
        if math.isnan(v) or math.isinf(v):
            raise ValueError('counted_cash cannot be NaN or Infinity')
        if v < 0:
            raise ValueError('counted_cash must be non-negative')
        if v > 100_000_000:
            raise ValueError('counted_cash exceeds maximum allowed value')
        return round(v, 2)

# ==========================================
# ENDPOINTS
# ==========================================

@app.get("/")
async def root():
    """API health check."""
    return {"status": "ok", "service": "TITAN POS Admin API"}

@app.get("/api/dashboard")
async def get_dashboard(admin: str = Depends(verify_admin)):
    """Get real-time fiscal dashboard."""
    core = get_core()
    
    from app.fiscal.fiscal_dashboard import FiscalDashboard
    dashboard = FiscalDashboard(core)
    
    return dashboard.get_dashboard_data()

@app.get("/api/stats")
async def get_stats(admin: str = Depends(verify_admin)):
    """Get quick system statistics."""
    core = get_core()
    
    products = list(core.db.execute_query("SELECT COUNT(*) as c FROM products"))
    sales_today = list(core.db.execute_query(
        "SELECT COUNT(*) as c, COALESCE(SUM(total), 0) as t FROM sales WHERE timestamp::date = CURRENT_DATE"
    ))
    
    return {
        "products": products[0]['c'] if products else 0,
        "sales_today": sales_today[0]['c'] if sales_today else 0,
        "revenue_today": float(sales_today[0]['t'] or 0) if sales_today else 0
    }

@app.put("/api/prices/{product_id}")
async def update_price(product_id: int, update: PriceUpdate,
                       admin: str = Depends(verify_admin)):
    """Update product price remotely."""
    if product_id <= 0:
        raise HTTPException(status_code=400, detail="product_id must be positive")
    core = get_core()

    try:
        core.db.execute_write(
            "UPDATE products SET price = %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (update.new_price, product_id)
        )
        
        # Log the action
        core.db.execute_write(
            """INSERT INTO audit_log (timestamp, user_id, action, entity_type, entity_id, details)
               VALUES (NOW(), 0, 'REMOTE_PRICE_UPDATE', 'product', %s, %s)""",
            (product_id, f"New price: ${update.new_price:.2f}")
        )
        
        return {"success": True, "product_id": product_id, "new_price": update.new_price}

    except Exception as e:
        logger.error(f"Error en endpoint update_price: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.get("/api/products")
async def list_products(limit: int = 50, search: str = None,
                        admin: str = Depends(verify_admin)):
    """List products with search."""
    # Validar limite maximo para evitar queries excesivas
    limit = min(max(1, limit), 500)
    core = get_core()

    if search:
        products = list(core.db.execute_query(
            "SELECT id, sku, name, price, stock FROM products WHERE name LIKE %s LIMIT %s",
            (f"%{search}%", limit)
        ))
    else:
        products = list(core.db.execute_query(
            "SELECT id, sku, name, price, stock FROM products LIMIT %s",
            (limit,)
        ))
    
    return [dict(p) for p in products]

@app.post("/api/authorize")
async def generate_authorization(request: AuthorizationRequest,
                                 admin: str = Depends(verify_admin)):
    """Generate authorization code for cashier action."""
    core = get_core()
    
    from app.services.contingency_mode import ContingencyMode
    contingency = ContingencyMode(core)
    
    result = contingency.request_authorization(
        request.action_type,
        request.amount, 
        0,  # admin user
        request.reason
    )
    
    return result

@app.get("/api/authorize/{code}")
async def validate_authorization(code: str, admin: str = Depends(verify_admin)):
    """Validate an authorization code."""
    core = get_core()
    
    from app.services.contingency_mode import ContingencyMode
    contingency = ContingencyMode(core)
    
    return contingency.validate_authorization(code)

@app.get("/api/turns/active")
async def get_active_turns(admin: str = Depends(verify_admin)):
    """Get active turns."""
    core = get_core()
    
    turns = list(core.db.execute_query(
        """SELECT id, user_id, start_timestamp, initial_cash 
           FROM turns WHERE status = 'open'"""
    ))
    
    return [dict(t) for t in turns]

@app.post("/api/turns/{turn_id}/close")
async def close_turn(turn_id: int, close: TurnClose,
                     admin: str = Depends(verify_admin)):
    """Process blind turn close."""
    core = get_core()
    
    from app.services.contingency_mode import ContingencyMode
    contingency = ContingencyMode(core)
    
    result = contingency.process_blind_close(
        turn_id, 
        {'efectivo_contado': close.counted_cash}
    )
    
    return result

@app.get("/api/alerts")
async def get_alerts(admin: str = Depends(verify_admin)):
    """Get recent system alerts."""
    core = get_core()
    
    alerts = list(core.db.execute_query(
        """SELECT * FROM audit_log 
           WHERE action IN ('GENERIC_SALE', 'REMOTE_PRICE_UPDATE', 'AUTHORIZATION')
           ORDER BY timestamp DESC LIMIT 20"""
    ))
    
    return [dict(a) for a in alerts]

# ==========================================
# RUN SERVER
# ==========================================

def run_api(core, host="0.0.0.0", port=8080):
    """Start the API server."""
    import uvicorn
    set_core(core)
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    # For testing
    print("Admin API - Use run_api(core) to start")
