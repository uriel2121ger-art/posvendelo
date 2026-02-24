#!/usr/bin/env python3
# TODO [REFACTOR]: Este archivo tiene ~2300 lineas. Considerar dividir en:
# - gateway_auth.py: Autenticacion y tokens
# - gateway_sync.py: Sincronizacion de sucursales
# - gateway_reports.py: Endpoints de reportes y estadisticas
# - gateway_admin.py: Endpoints administrativos (backup, broadcast)
"""
TITAN Gateway - Servidor Central Multi-Sucursal

Este servidor recibe datos de todas las sucursales y los consolida.
Se ejecuta en el servidor central (VM en Proxmox o similar).

Ejecutar con: uvicorn titan_gateway:app --host 0.0.0.0 --port 8000
"""

import os
import secrets  # FIX 2026-02-01: Import for secure token generation and comparison
import sys
import json
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

# Intentar importar FastAPI
try:
    from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    from pydantic import BaseModel, field_validator
except ImportError:
    print("ERROR: FastAPI no instalado. Ejecuta: pip install fastapi uvicorn python-multipart")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("titan_gateway.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TITAN_GATEWAY")

# --- DATA STORAGE ---
SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = Path("./gateway_data")
DATA_DIR.mkdir(exist_ok=True)
(DATA_DIR / "backups").mkdir(exist_ok=True)
(DATA_DIR / "sales").mkdir(exist_ok=True)
(DATA_DIR / "branches").mkdir(exist_ok=True)

# Cache system for performance
CACHE = {}
CACHE_TTL = 60  # seconds

def get_cached(key: str):
    if key in CACHE:
        data, timestamp = CACHE[key]
        if (datetime.now() - timestamp).seconds < CACHE_TTL:
            return data
    return None

def set_cached(key: str, data):
    CACHE[key] = (data, datetime.now())

# Configuration
CONFIG_FILE = DATA_DIR / "config.json"
TOKENS_FILE = DATA_DIR / "tokens.json"

def load_config():
    if CONFIG_FILE.exists():
        # FIX 2026-02-01: Added JSONDecodeError handling
        try:
            config = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
            # Validate token strength on startup
            token = config.get("admin_token", "")
            if token in ("change_me_in_production", "") or len(token) < 20:
                logger.warning("SECURITY: admin_token is weak or placeholder. Regenerating...")
                config["admin_token"] = secrets.token_urlsafe(32)
                save_config(config)
                logger.warning("New admin_token generated and saved to config.json")
            return config
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON in config file, regenerating: %s", e)
    # FIX 2026-02-01: Generate secure random token instead of hardcoded default
    secure_token = secrets.token_urlsafe(32)
    logger.warning("SECURITY: Generated new admin_token. Save it securely!")
    logger.info("New admin token: %s", secure_token)
    return {"admin_token": secure_token, "branches": {}}

def save_config(config):
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')

def load_tokens():
    # FIX 2026-02-01: Added JSONDecodeError handling
    if TOKENS_FILE.exists():
        try:
            return json.loads(TOKENS_FILE.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON in tokens file: %s", e)
            return {}
    return {}

def save_tokens(tokens):
    TOKENS_FILE.write_text(json.dumps(tokens, indent=2, ensure_ascii=False), encoding='utf-8')


def _safe_parse_datetime(value: str, default: datetime = None) -> datetime:
    """Safely parse ISO format datetime string."""
    if default is None:
        default = datetime(2000, 1, 1)
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return default


def _safe_strptime(value: str, fmt: str, default: datetime = None) -> datetime:
    """Safely parse datetime with strptime."""
    if default is None:
        default = datetime.now()
    try:
        return datetime.strptime(value, fmt)
    except (ValueError, TypeError):
        return default


def _sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks."""
    import re
    # Only allow alphanumeric, underscores, and hyphens
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '', str(filename))
    # Ensure not empty
    return safe_name if safe_name else 'default'


def _safe_int(value, default: int = 0) -> int:
    """Safely convert value to int, returning default on error."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_float(value, default: float = 0.0) -> float:
    """Safely convert value to float, returning default on error."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

# --- MODELS ---
class BranchInfo(BaseModel):
    branch_id: int
    branch_name: str
    terminal_id: Optional[int] = 1
    tailscale_ip: Optional[str] = None

class SaleRecord(BaseModel):
    branch_id: int
    terminal_id: int
    sale_id: int
    folio: Optional[int] = None
    timestamp: str
    total: float
    items: List[Dict[str, Any]]
    payments: Optional[List[Dict[str, Any]]] = None
    payment_method: Optional[str] = "Efectivo"
    cashier_id: Optional[int] = None
    cashier: Optional[str] = None
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None

    @field_validator('total')
    @classmethod
    def validate_total(cls, v):
        import math
        if math.isnan(v) or math.isinf(v):
            raise ValueError('total must be a finite number')
        if v < 0:
            raise ValueError('total must be non-negative')
        return round(v, 2)

class SyncBatch(BaseModel):
    branch_id: int
    terminal_id: int
    timestamp: str
    sales: Optional[List[Dict]] = None
    inventory_changes: Optional[List[Dict]] = None
    customers: Optional[List[Dict]] = None

class ProductUpdate(BaseModel):
    sku: str
    price: Optional[float] = None
    cost: Optional[float] = None
    stock: Optional[int] = None
    name: Optional[str] = None

# --- AUTHENTICATION ---
async def verify_token(authorization: Optional[str] = Header(None)):
    """Verify Bearer token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Token requerido")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Formato de token inválido")
    
    token = authorization.replace("Bearer ", "")
    
    config = load_config()
    tokens = load_tokens()
    
    # FIX 2026-02-01: Use constant-time comparison to prevent timing attacks
    admin_token = config.get("admin_token", "")
    if admin_token and secrets.compare_digest(token, admin_token):
        return {"role": "admin", "branch_id": None}

    # Check branch tokens with constant-time comparison
    for branch_id, branch_token in tokens.items():
        if branch_token and secrets.compare_digest(token, branch_token):
            return {"role": "branch", "branch_id": _safe_int(branch_id)}
    
    raise HTTPException(status_code=401, detail="Token inválido")

# --- FASTAPI APP ---
app = FastAPI(
    title="TITAN Gateway",
    description="Servidor Central Multi-Sucursal para TITAN POS",
    version="1.0.0"
)

# FIX 2026-02-01: CORS - Default to empty list (secure), require explicit configuration
# Production: CORS_ORIGINS=http://100.81.7.8:8000,http://localhost:3000
# Development: CORS_ORIGINS=* (must be explicitly set)
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "")
if CORS_ORIGINS == "*":
    logger.warning("SECURITY WARNING: CORS configured to allow ALL origins (*). This is insecure for production!")
    cors_origin_list = ["*"]
elif CORS_ORIGINS:
    cors_origin_list = [origin.strip() for origin in CORS_ORIGINS.split(",")]
else:
    logger.warning("CORS_ORIGINS not configured. Set CORS_ORIGINS environment variable for cross-origin access.")
    cors_origin_list = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiter Middleware
try:
    from rate_limiter import RateLimitMiddleware, RateLimiter
    limiter = RateLimiter(requests_per_minute=300, burst_limit=100)
    app.add_middleware(RateLimitMiddleware, limiter=limiter)
    logger.info("✅ Rate limiter habilitado (300 rpm, burst 100)")
except ImportError as e:
    logger.warning("Rate limiter no disponible: %s", e)
except Exception as e:
    logger.warning("Error configurando rate limiter: %s", e)

# Security Headers Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware para agregar headers de seguridad HTTP"""
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        # Prevenir MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Prevenir clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # Protección XSS legacy (para navegadores antiguos)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Permisos restrictivos
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response

app.add_middleware(SecurityHeadersMiddleware)
logger.info("✅ Security headers middleware habilitado")

# Gateway Storage for persistence
try:
    from gateway_storage import get_storage
    STORAGE = get_storage()
    logger.info("✅ Persistencia SQLite habilitada")
except ImportError:
    STORAGE = None
    logger.warning("⚠️ Persistencia no disponible, usando almacenamiento en memoria")

# --- ENDPOINTS ---

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "TITAN Gateway",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "message": "TITAN Gateway operativo",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/dashboard")
async def dashboard():
    """Serve the visual dashboard."""
    dashboard_path = Path(__file__).parent / "dashboard.html"
    if dashboard_path.exists():
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=dashboard_path.read_text(encoding='utf-8'), status_code=200)
    return {"error": "Dashboard not found"}

# === PWA ROUTES ===

@app.get("/pwa")
@app.get("/pwa/")
async def pwa_index():
    """Serve the PWA main page."""
    pwa_path = SCRIPT_DIR / "pwa" / "dashboard.html"
    if pwa_path.exists():
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=pwa_path.read_text(encoding='utf-8'), status_code=200)
    # Fallback to index.html
    pwa_path = SCRIPT_DIR / "pwa" / "index.html"
    if pwa_path.exists():
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=pwa_path.read_text(encoding='utf-8'), status_code=200)
    return {"error": "PWA not found"}

@app.get("/pwa/js/{filename}")
async def pwa_js(filename: str):
    """Serve PWA JavaScript files."""
    if not filename.endswith('.js'):
        raise HTTPException(status_code=400, detail="Invalid file type")
    base_dir = (SCRIPT_DIR / "pwa" / "js").resolve()
    js_path = (base_dir / filename).resolve()
    if not js_path.is_relative_to(base_dir):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if js_path.exists():
        return FileResponse(js_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/pwa/css/{filename}")
async def pwa_css(filename: str):
    """Serve PWA CSS files."""
    if not filename.endswith('.css'):
        raise HTTPException(status_code=400, detail="Invalid file type")
    base_dir = (SCRIPT_DIR / "pwa" / "css").resolve()
    css_path = (base_dir / filename).resolve()
    if not css_path.is_relative_to(base_dir):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if css_path.exists():
        return FileResponse(css_path, media_type="text/css")
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/pwa/manifest.json")
async def pwa_manifest():
    """Serve PWA manifest."""
    manifest_path = SCRIPT_DIR / "pwa" / "manifest.json"
    if manifest_path.exists():
        return FileResponse(manifest_path, media_type="application/json")
    raise HTTPException(status_code=404, detail="Manifest not found")

@app.get("/pwa/sw.js")
async def pwa_service_worker():
    """Serve PWA service worker."""
    sw_path = SCRIPT_DIR / "pwa" / "sw.js"
    if sw_path.exists():
        return FileResponse(sw_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Service worker not found")

@app.get("/pwa/{filename}.png")
async def pwa_icons(filename: str):
    """Serve PWA icons."""
    # FIX 2026-02-01: Sanitize filename to prevent path traversal
    safe_filename = _sanitize_filename(filename)
    icon_path = SCRIPT_DIR / "pwa" / f"{safe_filename}.png"
    if icon_path.exists():
        return FileResponse(icon_path, media_type="image/png")
    raise HTTPException(status_code=404, detail="Icon not found")

@app.get("/api/status")
async def get_status(auth: dict = Depends(verify_token)):
    """Get server status and connected branches."""
    config = load_config()
    branches = config.get("branches", {})
    
    # Get last sync times
    branch_status = {}
    for branch_id, info in branches.items():
        sync_file = DATA_DIR / "branches" / f"{branch_id}_last_sync.json"
        if sync_file.exists():
            sync_data = json.loads(sync_file.read_text(encoding='utf-8'))
            last_sync = sync_data.get("timestamp", "Nunca")
        else:
            last_sync = "Nunca"
        
        branch_status[branch_id] = {
            **info,
            "last_sync": last_sync
        }
    
    return {
        "server_time": datetime.now().isoformat(),
        "branches_registered": len(branches),
        "branches": branch_status
    }

@app.get("/api/auth/test")
async def auth_test(auth: dict = Depends(verify_token)):
    """Compatibility endpoint for clients that need current auth scope."""
    return {
        "ok": True,
        "role": auth.get("role"),
        "branch_id": auth.get("branch_id"),
    }

@app.post("/api/branches/register")
async def register_branch(branch: BranchInfo, auth: dict = Depends(verify_token)):
    """Register a new branch."""
    import secrets
    # #region agent log
    try:
        with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "5e74cc",
                "runId": "post-fix",
                "hypothesisId": "H7_branch_register_role_gap",
                "location": "server/titan_gateway.py:register_branch",
                "message": "register_branch authorization check",
                "data": {
                    "auth_role": auth.get("role"),
                    "auth_branch_id": auth.get("branch_id"),
                    "target_branch_id": str(branch.branch_id),
                },
                "timestamp": int(datetime.now().timestamp() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    if auth.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin puede registrar sucursales")
    
    config = load_config()
    tokens = load_tokens()
    
    branch_id = str(branch.branch_id)
    
    # Generate token for this branch
    branch_token = secrets.token_urlsafe(32)
    
    config.setdefault("branches", {})[branch_id] = {
        "name": branch.branch_name,
        "terminal_id": branch.terminal_id,
        "tailscale_ip": branch.tailscale_ip,
        "registered_at": datetime.now().isoformat()
    }
    
    tokens[branch_id] = branch_token
    
    save_config(config)
    save_tokens(tokens)
    
    logger.info("Sucursal registrada: %s (ID: %s)", branch.branch_name, branch_id)
    
    return {
        "success": True,
        "branch_id": branch_id,
        "token": branch_token,
        "message": f"Sucursal '{branch.branch_name}' registrada exitosamente"
    }

# --- Heartbeat storage for terminal tracking ---
TERMINAL_HEARTBEATS: Dict[str, Dict[str, Any]] = {}

class HeartbeatPayload(BaseModel):
    """Heartbeat data from terminals."""
    terminal_id: int
    terminal_name: Optional[str] = None
    branch_id: int
    timestamp: str
    status: str = "online"
    today_sales: Optional[int] = 0
    today_total: Optional[float] = 0.0
    active_turn: Optional[Dict[str, Any]] = None
    pending_sync: Optional[int] = 0
    product_count: Optional[int] = 0

    @field_validator('today_total')
    @classmethod
    def validate_today_total(cls, v):
        if v is None:
            return 0.0
        import math
        if math.isnan(v) or math.isinf(v):
            raise ValueError('today_total must be a finite number')
        return round(v, 2)

@app.post("/api/v1/heartbeat")
async def receive_heartbeat(payload: HeartbeatPayload, auth: dict = Depends(verify_token)):
    """
    Receive heartbeat from a terminal.

    Tracks which terminals are online and their current status.
    """
    terminal_key = f"B{payload.branch_id}-T{payload.terminal_id}"
    
    TERMINAL_HEARTBEATS[terminal_key] = {
        "terminal_id": payload.terminal_id,
        "terminal_name": payload.terminal_name or f"Terminal {payload.terminal_id}",
        "branch_id": payload.branch_id,
        "status": payload.status,
        "last_seen": datetime.now().isoformat(),
        "received_at": datetime.now(),
        "today_sales": payload.today_sales,
        "today_total": payload.today_total,
        "active_turn": payload.active_turn,
        "pending_sync": payload.pending_sync,
        "product_count": payload.product_count
    }
    
    logger.debug("Heartbeat from %s: %d sales, $%.2f", terminal_key, payload.today_sales, payload.today_total)
    
    return {
        "received": True,
        "terminal": terminal_key,
        "server_time": datetime.now().isoformat()
    }

@app.get("/api/v1/terminals")
async def get_terminals(auth: dict = Depends(verify_token)):
    """
    Get all known terminals and their status.
    
    Returns terminals that have sent a heartbeat recently.
    """
    now = datetime.now()
    terminals = []
    
    for key, data in TERMINAL_HEARTBEATS.items():
        received_at = data.get("received_at", now)
        elapsed = (now - received_at).total_seconds()
        
        # Consider online if heartbeat within last 3 minutes
        is_online = elapsed < 180
        
        terminals.append({
            "key": key,
            "terminal_id": data.get("terminal_id"),
            "terminal_name": data.get("terminal_name"),
            "branch_id": data.get("branch_id"),
            "status": "online" if is_online else "offline",
            "last_seen": data.get("last_seen"),
            "seconds_ago": _safe_int(elapsed),
            "today_sales": data.get("today_sales", 0),
            "today_total": data.get("today_total", 0),
            "active_turn": data.get("active_turn"),
            "pending_sync": data.get("pending_sync", 0)
        })
    
    # Sort by branch_id, then terminal_id
    terminals.sort(key=lambda x: (x["branch_id"], x["terminal_id"]))
    
    online_count = sum(1 for t in terminals if t["status"] == "online")
    
    return {
        "terminals": terminals,
        "total": len(terminals),
        "online": online_count,
        "offline": len(terminals) - online_count,
        "timestamp": datetime.now().isoformat()
    }

# --- Stock Alerts Storage ---
STOCK_ALERTS: Dict[str, List[Dict[str, Any]]] = {}

class StockAlertPayload(BaseModel):
    """Stock alert from a terminal."""
    terminal_id: int
    branch_id: int
    alerts: List[Dict[str, Any]]
    timestamp: str

@app.post("/api/v1/alerts/stock")
async def receive_stock_alerts(payload: StockAlertPayload, auth: dict = Depends(verify_token)):
    """
    Receive stock alerts from a terminal.

    Terminals send alerts periodically when products fall below minimum.
    """
    terminal_key = f"B{payload.branch_id}-T{payload.terminal_id}"
    
    STOCK_ALERTS[terminal_key] = {
        "alerts": payload.alerts,
        "received_at": datetime.now().isoformat(),
        "terminal_id": payload.terminal_id,
        "branch_id": payload.branch_id
    }
    
    if payload.alerts:
        logger.info("%d stock alerts from %s", len(payload.alerts), terminal_key)
    
    return {
        "received": True,
        "count": len(payload.alerts),
        "terminal": terminal_key
    }

@app.get("/api/v1/alerts/stock")
async def get_stock_alerts(auth: dict = Depends(verify_token)):
    """
    Get all current stock alerts from all terminals.
    
    Returns aggregated view of stock alerts across all branches.
    """
    all_alerts = []
    
    for terminal_key, data in STOCK_ALERTS.items():
        for alert in data.get("alerts", []):
            all_alerts.append({
                **alert,
                "terminal_key": terminal_key,
                "terminal_id": data.get("terminal_id"),
                "branch_id": data.get("branch_id"),
                "reported_at": data.get("received_at")
            })
    
    # Sort by severity (out_of_stock first, then critical, then warning)
    severity_order = {"out_of_stock": 0, "critical": 1, "warning": 2}
    all_alerts.sort(key=lambda x: severity_order.get(x.get("severity", "warning"), 3))
    
    summary = {
        "out_of_stock": sum(1 for a in all_alerts if a.get("severity") == "out_of_stock"),
        "critical": sum(1 for a in all_alerts if a.get("severity") == "critical"),
        "warning": sum(1 for a in all_alerts if a.get("severity") == "warning")
    }
    
    return {
        "alerts": all_alerts,
        "total": len(all_alerts),
        "summary": summary,
        "terminals_reporting": len(STOCK_ALERTS),
        "timestamp": datetime.now().isoformat()
    }

# --- Centralized Logs Storage ---
CENTRALIZED_LOGS: List[Dict[str, Any]] = []
MAX_LOGS = 10000  # Keep last 10K logs in memory

class LogBatchPayload(BaseModel):
    """Log batch from a terminal."""
    terminal_id: int
    branch_id: int
    timestamp: str
    entries: List[Dict[str, Any]]

@app.post("/api/v1/logs")
async def receive_logs_main(payload: LogBatchPayload, auth: dict = Depends(verify_token)):
    """
    Receive log entries from a terminal.

    Stores logs for centralized analysis and debugging.
    """
    global CENTRALIZED_LOGS
    
    for entry in payload.entries:
        log_entry = {
            **entry,
            "terminal_id": payload.terminal_id,
            "branch_id": payload.branch_id,
            "received_at": datetime.now().isoformat()
        }
        CENTRALIZED_LOGS.append(log_entry)
    
    # Trim old logs
    if len(CENTRALIZED_LOGS) > MAX_LOGS:
        CENTRALIZED_LOGS = CENTRALIZED_LOGS[-MAX_LOGS:]
    
    # Log critical/error to server log
    critical_count = sum(1 for e in payload.entries if e.get("level") in ("error", "critical"))
    if critical_count:
        logger.warning("%d error/critical logs from B%d-T%d", critical_count, payload.branch_id, payload.terminal_id)
    
    return {
        "received": True,
        "count": len(payload.entries),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/logs")
async def get_logs(
    auth: dict = Depends(verify_token),
    level: Optional[str] = None,
    terminal_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    limit: int = 100
):
    """
    Query centralized logs.
    
    Args:
        level: Filter by log level (error, warning, info)
        terminal_id: Filter by terminal
        branch_id: Filter by branch
        limit: Max entries to return (default 100, max 1000)
    """
    limit = min(limit, 1000)
    
    filtered = CENTRALIZED_LOGS
    
    if level:
        filtered = [l for l in filtered if l.get("level") == level]
    if terminal_id is not None:
        filtered = [l for l in filtered if l.get("terminal_id") == terminal_id]
    if branch_id is not None:
        filtered = [l for l in filtered if l.get("branch_id") == branch_id]
    
    # Return most recent first
    filtered = sorted(filtered, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]
    
    return {
        "logs": filtered,
        "total": len(filtered),
        "total_stored": len(CENTRALIZED_LOGS),
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/sync")
async def sync_data(batch: SyncBatch, auth: dict = Depends(verify_token)):
    """Receive sync data from a branch."""
    # FIX 2026-02-01: Sanitize branch_id to prevent path traversal
    branch_id = _sanitize_filename(str(batch.branch_id))
    
    result = {
        "success": True,
        "sales_received": 0,
        "inventory_received": 0,
        "customers_received": 0,
        "accepted_ids": []
    }

    # Save sales with deduplication
    if batch.sales:
        sales_file = DATA_DIR / "sales" / f"{branch_id}_{datetime.now().strftime('%Y%m%d')}.jsonl"
        sales_file.parent.mkdir(parents=True, exist_ok=True)
        existing_keys = set()
        if sales_file.exists():
            try:
                with open(sales_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            r = json.loads(line)
                            existing_keys.add((r.get("_terminal_id"), r.get("id")))
                        except json.JSONDecodeError:
                            continue
            except Exception:
                pass
        saved = 0
        with open(sales_file, "a", encoding="utf-8") as f:
            for sale in batch.sales:
                sale_key = (batch.terminal_id, sale.get("id"))
                if sale_key in existing_keys:
                    if sale.get("id") is not None:
                        result["accepted_ids"].append(sale["id"])
                    continue
                sale["_branch_id"] = batch.branch_id
                sale["_terminal_id"] = batch.terminal_id
                sale["_received_at"] = datetime.now().isoformat()
                f.write(json.dumps(sale) + "\n")
                existing_keys.add(sale_key)
                saved += 1
                if sale.get("id") is not None:
                    result["accepted_ids"].append(sale["id"])
        result["sales_received"] = saved
        logger.info("Recibidas %d ventas de sucursal %s (dedup: %d)", saved, branch_id, len(batch.sales) - saved)
    
    # Save inventory changes
    if batch.inventory_changes:
        inv_file = DATA_DIR / "branches" / f"{branch_id}_inventory.json"
        existing = []
        if inv_file.exists():
            existing = json.loads(inv_file.read_text(encoding='utf-8'))
        existing.extend(batch.inventory_changes)
        inv_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding='utf-8')
        result["inventory_received"] = len(batch.inventory_changes)
    
    # Save customers
    if batch.customers:
        cust_file = DATA_DIR / "branches" / f"{branch_id}_customers.json"
        existing = []
        if cust_file.exists():
            existing = json.loads(cust_file.read_text(encoding='utf-8'))
        existing.extend(batch.customers)
        cust_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding='utf-8')
        result["customers_received"] = len(batch.customers)
    
    # Update last sync
    sync_file = DATA_DIR / "branches" / f"{branch_id}_last_sync.json"
    sync_file.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "terminal_id": batch.terminal_id,
        **result
    }, indent=2, ensure_ascii=False), encoding='utf-8')
    
    return result

# ==============================================================================
# NEW: Compatible sync endpoints for client /api/v1/sync/{table}
# ==============================================================================

class GenericSyncPayload(BaseModel):
    """Generic sync payload from client."""
    data: List[Dict[str, Any]]
    timestamp: str
    terminal_id: int
    request_id: Optional[str] = None

@app.post("/api/v1/sync/sales")
async def sync_sales_v1(payload: GenericSyncPayload, auth: dict = Depends(verify_token)):
    """
    Receive sales sync from client.
    Compatible with MultiCajaClient.sync_table() calls.
    """
    branch_id = auth.get("branch_id", 1) or 1
    if not payload.terminal_id or int(payload.terminal_id) <= 0:
        raise HTTPException(status_code=422, detail="terminal_id is required and must be positive")

    if not payload.data:
        return {"success": True, "records_received": 0, "accepted_ids": [], "message": "No data to sync"}

    sales_file = DATA_DIR / "sales" / f"{branch_id}_{datetime.now().strftime('%Y%m%d')}.jsonl"
    sales_file.parent.mkdir(parents=True, exist_ok=True)

    # Load existing keys for deduplication: (terminal_id, sale_id)
    existing_keys = set()
    if sales_file.exists():
        try:
            with open(sales_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                        existing_keys.add((r.get("_terminal_id"), r.get("id")))
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

    saved = 0
    duplicates = 0
    accepted_ids = []
    with open(sales_file, "a", encoding="utf-8") as f:
        for sale in payload.data:
            sale_key = (payload.terminal_id, sale.get("id"))
            if sale_key in existing_keys:
                duplicates += 1
                if sale.get("id") is not None:
                    accepted_ids.append(sale["id"])
                continue
            sale["_branch_id"] = branch_id
            sale["_terminal_id"] = payload.terminal_id
            sale["_received_at"] = datetime.now().isoformat()
            f.write(json.dumps(sale) + "\n")
            existing_keys.add(sale_key)
            saved += 1
            if sale.get("id") is not None:
                accepted_ids.append(sale["id"])

    logger.info("Sales sync: %d saved, %d duplicates from branch %s terminal %s",
                saved, duplicates, branch_id, payload.terminal_id)

    return {
        "success": True,
        "records_received": saved,
        "duplicates": duplicates,
        "accepted_ids": accepted_ids,
        "table": "sales",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/v1/sync/sale_items")
async def sync_sale_items_v1(payload: GenericSyncPayload, auth: dict = Depends(verify_token)):
    """Receive sale_items sync from client."""
    branch_id = auth.get("branch_id", 1) or 1
    if not payload.terminal_id or int(payload.terminal_id) <= 0:
        raise HTTPException(status_code=422, detail="terminal_id is required and must be positive")

    if not payload.data:
        return {"success": True, "records_received": 0, "accepted_ids": []}

    items_file = DATA_DIR / "sale_items" / f"{branch_id}_{datetime.now().strftime('%Y%m%d')}.jsonl"
    items_file.parent.mkdir(parents=True, exist_ok=True)

    accepted_ids = []
    with open(items_file, "a", encoding="utf-8") as f:
        for item in payload.data:
            item["_branch_id"] = branch_id
            item["_terminal_id"] = payload.terminal_id
            item["_received_at"] = datetime.now().isoformat()
            f.write(json.dumps(item) + "\n")
            if item.get("id") is not None:
                accepted_ids.append(item["id"])

    return {"success": True, "records_received": len(payload.data), "accepted_ids": accepted_ids, "table": "sale_items"}

@app.post("/api/v1/sync/products")
async def sync_products_v1(payload: GenericSyncPayload, auth: dict = Depends(verify_token)):
    """Receive products sync from client."""
    branch_id = auth.get("branch_id", 1) or 1
    if not payload.terminal_id or int(payload.terminal_id) <= 0:
        raise HTTPException(status_code=422, detail="terminal_id is required and must be positive")
    
    if not payload.data:
        return {"success": True, "records_received": 0}
    
    # Save/update products
    products_file = DATA_DIR / "products.json"
    existing = []
    if products_file.exists():
        existing = json.loads(products_file.read_text(encoding='utf-8'))
    
    # Merge by SKU
    existing_skus = {p.get("sku"): i for i, p in enumerate(existing)}
    
    for product in payload.data:
        sku = product.get("sku")
        if sku in existing_skus:
            # Update existing
            existing[existing_skus[sku]] = {**existing[existing_skus[sku]], **product}
        else:
            # Add new
            existing.append(product)
    
    products_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding='utf-8')
    
    logger.info("Products sync: %d records from branch %s", len(payload.data), branch_id)
    
    accepted_ids = [p.get("id") for p in payload.data if p.get("id") is not None]
    return {"success": True, "records_received": len(payload.data), "accepted_ids": accepted_ids, "table": "products"}

@app.post("/api/v1/sync/customers")
async def sync_customers_v1(payload: GenericSyncPayload, auth: dict = Depends(verify_token)):
    """Receive customers sync from client."""
    branch_id = auth.get("branch_id", 1) or 1
    if not payload.terminal_id or int(payload.terminal_id) <= 0:
        raise HTTPException(status_code=422, detail="terminal_id is required and must be positive")
    
    if not payload.data:
        return {"success": True, "records_received": 0}
    
    # Save customers
    customers_file = DATA_DIR / "customers.json"
    existing = []
    if customers_file.exists():
        existing = json.loads(customers_file.read_text(encoding='utf-8'))
    
    # Merge by ID
    existing_ids = {c.get("id"): i for i, c in enumerate(existing)}
    
    for customer in payload.data:
        cid = customer.get("id")
        if cid in existing_ids:
            existing[existing_ids[cid]] = {**existing[existing_ids[cid]], **customer}
        else:
            existing.append(customer)
    
    customers_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding='utf-8')

    accepted_ids = [c.get("id") for c in payload.data if c.get("id") is not None]
    return {"success": True, "records_received": len(payload.data), "accepted_ids": accepted_ids, "table": "customers"}

@app.post("/api/v1/sync/{table_name}")
async def sync_generic_table_v1(table_name: str, payload: GenericSyncPayload, auth: dict = Depends(verify_token)):
    """
    Generic sync endpoint for any table.
    Saves data to a table-specific file.
    """
    # SECURITY: Sanitize table_name to prevent path traversal
    safe_table = _sanitize_filename(table_name)
    if not safe_table or safe_table != table_name:
        raise HTTPException(status_code=400, detail=f"Invalid table name: {table_name}")

    branch_id = auth.get("branch_id", 1) or 1
    if not payload.terminal_id or int(payload.terminal_id) <= 0:
        raise HTTPException(status_code=422, detail="terminal_id is required and must be positive")

    if not payload.data:
        return {"success": True, "records_received": 0, "accepted_ids": []}

    table_dir = DATA_DIR / safe_table
    table_dir.mkdir(parents=True, exist_ok=True)

    table_file = table_dir / f"{branch_id}_{datetime.now().strftime('%Y%m%d')}.jsonl"

    accepted_ids = []
    with open(table_file, "a", encoding="utf-8") as f:
        for record in payload.data:
            record["_branch_id"] = branch_id
            record["_terminal_id"] = payload.terminal_id
            record["_received_at"] = datetime.now().isoformat()
            f.write(json.dumps(record) + "\n")
            if record.get("id") is not None:
                accepted_ids.append(record["id"])

    logger.info("%s sync: %d records from branch %s", safe_table, len(payload.data), branch_id)

    return {
        "success": True,
        "records_received": len(payload.data),
        "accepted_ids": accepted_ids,
        "table": safe_table,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/sync/products")
async def get_product_updates(
    since: Optional[str] = None,
    auth: dict = Depends(verify_token)
):
    """Get product/price updates for branches to download."""
    updates_file = DATA_DIR / "product_updates.json"
    
    if not updates_file.exists():
        return {"products": [], "last_update": None}
    
    updates = json.loads(updates_file.read_text(encoding='utf-8'))
    
    if since:
        since_dt = _safe_parse_datetime(since, datetime.now())
        updates = [u for u in updates if _safe_parse_datetime(u.get("updated_at", "2000-01-01")) > since_dt]
    
    return {
        "products": updates,
        "last_update": datetime.now().isoformat()
    }

@app.post("/api/products/update")
async def update_product(update: ProductUpdate, auth: dict = Depends(verify_token)):
    """Update a product (propagates to all branches)."""
    updates_file = DATA_DIR / "product_updates.json"
    
    existing = []
    if updates_file.exists():
        existing = json.loads(updates_file.read_text(encoding='utf-8'))
    
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
    
    logger.info("Producto actualizado: %s", update.sku)
    
    return {"success": True, "sku": update.sku}

@app.post("/api/backup/upload")
async def upload_backup(
    file: UploadFile = File(...),
    branch_id: int = 1,
    auth: dict = Depends(verify_token)
):
    """Upload a backup file from a branch."""
    # #region agent log
    try:
        with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "5e74cc",
                "runId": "pre-fix",
                "hypothesisId": "H5_client_backup_attempt",
                "location": "server/titan_gateway.py:upload_backup",
                "message": "Client backup upload blocked by server-only policy",
                "data": {"branch_id": branch_id, "role": auth.get("role")},
                "timestamp": int(datetime.now().timestamp() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    raise HTTPException(
        status_code=403,
        detail="Terminal backup upload disabled. Backups are server-only.",
    )

    backup_dir = DATA_DIR / "backups" / str(branch_id)
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Save with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{branch_id}_{timestamp}_{file.filename}"
    filepath = backup_dir / filename
    
    content = await file.read()
    filepath.write_bytes(content)
    
    # Calculate hash
    file_hash = hashlib.sha256(content).hexdigest()
    
    # Save metadata
    meta_file = backup_dir / f"{filename}.meta.json"
    meta_file.write_text(json.dumps({
        "original_name": file.filename,
        "size_bytes": len(content),
        "sha256": file_hash,
        "received_at": datetime.now().isoformat(),
        "branch_id": branch_id
    }, indent=2, ensure_ascii=False), encoding='utf-8')
    
    logger.info("Backup recibido de sucursal %s: %s (%d bytes)", branch_id, filename, len(content))
    
    return {
        "success": True,
        "filename": filename,
        "size": len(content),
        "hash": file_hash
    }

@app.get("/api/backups")
async def list_backups(branch_id: Optional[int] = None, auth: dict = Depends(verify_token)):
    """List available backups."""
    backups = []
    
    backup_base = DATA_DIR / "backups"
    
    if branch_id:
        dirs = [backup_base / str(branch_id)]
    else:
        dirs = [d for d in backup_base.iterdir() if d.is_dir()]
    
    for dir_path in dirs:
        if not dir_path.exists():
            continue
        for f in dir_path.glob("*.meta.json"):
            meta = json.loads(f.read_text(encoding='utf-8'))
            backups.append({
                "id": f.stem.replace(".meta", ""),
                "filename": meta.get("original_name"),
                "size": meta.get("size_bytes"),
                "branch_id": meta.get("branch_id"),
                "received_at": meta.get("received_at")
            })
    
    return {"backups": sorted(backups, key=lambda x: x.get("received_at", ""), reverse=True)}

@app.get("/api/reports/sales")
async def get_sales_report(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    branch_id: Optional[int] = None,
    auth: dict = Depends(verify_token)
):
    """Get consolidated sales report."""
    sales = []
    
    sales_dir = DATA_DIR / "sales"
    
    for f in sales_dir.glob("*.jsonl"):
        with open(f, encoding="utf-8") as file:
            for line in file:
                try:
                    sale = json.loads(line.strip())
                    
                    # Filter by branch
                    if branch_id and sale.get("_branch_id") != branch_id:
                        continue
                    
                    # Filter by date
                    sale_date = sale.get("timestamp", sale.get("_received_at", ""))[:10]
                    if date_from and sale_date < date_from:
                        continue
                    if date_to and sale_date > date_to:
                        continue
                    
                    sales.append(sale)
                # FIX 2026-02-01: Added logging to exception handler
                except Exception as e:
                    logger.debug("Error parsing sale line: %s", e)
                    continue

    # Calculate summary
    total_sales = sum(s.get("total", 0) for s in sales)
    
    return {
        "total_records": len(sales),
        "total_amount": total_sales,
        "date_from": date_from,
        "date_to": date_to,
        "branch_filter": branch_id,
        "sales": sales[:100]  # Limit for performance
    }

@app.get("/api/reports/branches")
async def get_branches_report(auth: dict = Depends(verify_token)):
    """Get report of all branches and their status."""
    config = load_config()
    branches = config.get("branches", {})
    
    report = []
    
    for branch_id, info in branches.items():
        sync_file = DATA_DIR / "branches" / f"{branch_id}_last_sync.json"
        
        if sync_file.exists():
            # FIX 2026-02-01: Added JSONDecodeError handling
            try:
                sync_data = json.loads(sync_file.read_text(encoding='utf-8'))
            except json.JSONDecodeError as e:
                logger.debug("Invalid JSON in sync file for branch %s: %s", branch_id, e)
                sync_data = {}
            last_sync = sync_data.get("timestamp")

            # Check if offline (no sync in last 5 minutes)
            try:
                last_dt = datetime.fromisoformat(last_sync)
                is_online = (datetime.now() - last_dt) < timedelta(minutes=5)
            # FIX 2026-02-01: Added logging to exception handler
            except Exception as e:
                logger.debug("Error parsing last_sync timestamp: %s", e)
                is_online = False
        else:
            last_sync = None
            is_online = False
        
        # Count today's sales
        today = datetime.now().strftime("%Y%m%d")
        sales_file = DATA_DIR / "sales" / f"{branch_id}_{today}.jsonl"
        sales_count = 0
        sales_total = 0
        if sales_file.exists():
            with open(sales_file, encoding="utf-8") as f:
                for line in f:
                    try:
                        sale = json.loads(line.strip())
                        sales_count += 1
                        sales_total += sale.get("total", 0)
                    # FIX 2026-02-01: Added logging to exception handler
                    except Exception as e:
                        logger.debug("Error parsing sale line for branch %s: %s", branch_id, e)
                        continue

        report.append({
            "branch_id": int(branch_id),
            "name": info.get("name"),
            "is_online": is_online,
            "last_sync": last_sync,
            "today_sales_count": sales_count,
            "today_sales_total": sales_total
        })
    
    return {"branches": report, "generated_at": datetime.now().isoformat()}

# === PWA ENDPOINTS ===

PRODUCTS_FILE = DATA_DIR / "products.json"

def load_products():
    # FIX 2026-02-01: Added JSONDecodeError handling
    if PRODUCTS_FILE.exists():
        try:
            return json.loads(PRODUCTS_FILE.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON in products file: %s", e)
            return []
    return []

def save_products(products):
    PRODUCTS_FILE.write_text(json.dumps(products, indent=2, ensure_ascii=False), encoding='utf-8')

@app.get("/api/products/search")
async def search_product(sku: str, auth: dict = Depends(verify_token)):
    """Search for a product by SKU with history."""
    products = load_products()
    
    product = None
    for p in products:
        if p.get("sku") == sku or p.get("sku", "").endswith(sku):
            product = p
            break
    
    if not product:
        return {"product": None, "history": []}
    
    # Obtener historial de cambios de precio
    history = []
    updates_file = DATA_DIR / "product_updates.json"
    if updates_file.exists():
        updates = json.loads(updates_file.read_text(encoding='utf-8'))
        for u in updates:
            if u.get("sku") == product.get("sku"):
                history.append({
                    "type": "precio",
                    "value": u.get("price"),
                    "date": u.get("updated_at", "")[:19],
                    "action": u.get("action", "update")
                })
    
    # Obtener historial de inventario
    adj_file = DATA_DIR / "inventory_adjustments.json"
    if adj_file.exists():
        adjustments = json.loads(adj_file.read_text(encoding='utf-8'))
        for a in adjustments:
            if a.get("sku") == product.get("sku"):
                history.append({
                    "type": "inventario",
                    "value": a.get("quantity"),
                    "date": a.get("timestamp", "")[:19],
                    "reason": a.get("reason", "")
                })
    
    # Ordenar por fecha descendente
    history.sort(key=lambda x: x.get("date", ""), reverse=True)
    
    return {"product": product, "history": history[:10]}

class ProductCreate(BaseModel):
    sku: str
    name: str
    price: float
    cost: Optional[float] = 0
    stock: Optional[int] = 0

@app.post("/api/products/create")
async def create_product(product: ProductCreate, auth: dict = Depends(verify_token)):
    """Create a new product."""
    products = load_products()
    
    # Check if exists
    for p in products:
        if p.get("sku") == product.sku:
            return {"success": False, "error": "SKU ya existe"}
    
    new_product = {
        "sku": product.sku,
        "name": product.name,
        "price": product.price,
        "cost": product.cost,
        "stock": product.stock,
        "created_at": datetime.now().isoformat()
    }
    
    products.append(new_product)
    save_products(products)
    
    # Add to product updates for sync to branches
    updates_file = DATA_DIR / "product_updates.json"
    existing = []
    if updates_file.exists():
        existing = json.loads(updates_file.read_text(encoding='utf-8'))
    existing.append({**new_product, "updated_at": datetime.now().isoformat(), "action": "create"})
    updates_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding='utf-8')
    
    logger.info("Producto creado: %s - %s", product.sku, product.name)
    
    return {"success": True, "product": new_product}

class InventoryAdjust(BaseModel):
    branch_id: str
    sku: str
    quantity: int
    reason: str

@app.post("/api/inventory/adjust")
async def adjust_inventory(adjust: InventoryAdjust, auth: dict = Depends(verify_token)):
    """Adjust inventory for a product in a branch."""
    
    # Record the adjustment
    adjustments_file = DATA_DIR / "inventory_adjustments.json"
    adjustments = []
    if adjustments_file.exists():
        adjustments = json.loads(adjustments_file.read_text(encoding='utf-8'))
    
    adjustment = {
        "branch_id": adjust.branch_id,
        "sku": adjust.sku,
        "quantity": adjust.quantity,
        "reason": adjust.reason,
        "timestamp": datetime.now().isoformat(),
        "synced": False
    }
    
    adjustments.append(adjustment)
    adjustments_file.write_text(json.dumps(adjustments, indent=2, ensure_ascii=False), encoding='utf-8')
    
    logger.info("Ajuste de inventario: %s %+d en sucursal %s", adjust.sku, adjust.quantity, adjust.branch_id)
    
    return {"success": True, "adjustment": adjustment}

@app.get("/api/inventory/adjustments")
async def get_pending_adjustments(branch_id: Optional[str] = None, auth: dict = Depends(verify_token)):
    """Get pending inventory adjustments for a branch."""
    adjustments_file = DATA_DIR / "inventory_adjustments.json"
    
    if not adjustments_file.exists():
        return {"adjustments": []}
    
    adjustments = json.loads(adjustments_file.read_text(encoding='utf-8'))
    
    # Filter by branch and unsynced
    pending = [a for a in adjustments if not a.get("synced")]
    if branch_id:
        pending = [a for a in pending if a.get("branch_id") == branch_id or a.get("branch_id") == "all"]
    
    return {"adjustments": pending}

# ==================== CUSTOMERS ====================
@app.get("/api/customers")
async def list_customers(search: Optional[str] = None, auth: dict = Depends(verify_token)):
    """List all synced customers with optional search."""
    customers_file = DATA_DIR / "customers.json"
    
    if not customers_file.exists():
        # Try to load from any branch sync
        all_customers = []
        for sync_file in (DATA_DIR / "branches").glob("*_customers.json"):
            try:
                branch_customers = json.loads(sync_file.read_text(encoding='utf-8'))
                all_customers.extend(branch_customers)
            except Exception as e:
                logger.debug("Error loading branch customers from %s: %s", sync_file, e)
                continue
        return {"customers": all_customers, "total": len(all_customers)}
    
    customers = json.loads(customers_file.read_text(encoding='utf-8'))
    
    if search:
        search_lower = search.lower()
        customers = [c for c in customers if 
            search_lower in c.get("name", "").lower() or
            search_lower in c.get("phone", "").lower() or
            search_lower in c.get("email", "").lower() or
            search_lower in str(c.get("id", ""))]
    
    return {"customers": customers, "total": len(customers)}

# Customer detail endpoint moved to line 1106 with purchase history

@app.post("/api/customers/sync")
async def sync_customers(customers: List[Dict[str, Any]], auth: dict = Depends(verify_token)):
    """Sync customers from a branch."""
    customers_file = DATA_DIR / "customers.json"
    
    # Merge with existing
    existing = []
    if customers_file.exists():
        existing = json.loads(customers_file.read_text(encoding='utf-8'))
    
    existing_ids = {c.get("id") for c in existing}
    
    for customer in customers:
        if customer.get("id") in existing_ids:
            # Update
            for i, c in enumerate(existing):
                if c.get("id") == customer.get("id"):
                    existing[i] = customer
                    break
        else:
            existing.append(customer)
    
    customers_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding='utf-8')
    
    return {"success": True, "total": len(existing)}

# ============== ADVANCED ENDPOINTS ==============

@app.get("/api/reports/sales/summary")
async def get_sales_summary(
    period: str = "week",  # day, week, month, last_month, custom
    branch_id: Optional[int] = None,
    start: Optional[str] = None,  # For custom: YYYYMMDD
    end: Optional[str] = None,    # For custom: YYYYMMDD
    auth: dict = Depends(verify_token)
):
    """Get sales summary with charts data."""
    sales_dir = DATA_DIR / "sales"
    
    # Calculate date range
    today = datetime.now()
    end_date = today.strftime("%Y%m%d")
    
    if period == "day":
        start_date = today.strftime("%Y%m%d")
        days = 1
    elif period == "week":
        start_date = (today - timedelta(days=7)).strftime("%Y%m%d")
        days = 7
    elif period == "last_month":
        # Mes anterior completo
        first_of_this_month = today.replace(day=1)
        last_of_prev_month = first_of_this_month - timedelta(days=1)
        first_of_prev_month = last_of_prev_month.replace(day=1)
        start_date = first_of_prev_month.strftime("%Y%m%d")
        end_date = last_of_prev_month.strftime("%Y%m%d")
        days = (last_of_prev_month - first_of_prev_month).days + 1
    elif period == "custom" and start and end:
        start_date = start
        end_date = end
        d1 = _safe_strptime(start, "%Y%m%d")
        d2 = _safe_strptime(end, "%Y%m%d")
        days = max((d2 - d1).days + 1, 1)  # Ensure at least 1 day
    else:  # month (este mes)
        start_date = (today - timedelta(days=30)).strftime("%Y%m%d")
        days = 30
    
    # Aggregate sales by day
    daily_sales = {}
    total_amount = 0
    total_transactions = 0
    products_sold = {}
    payment_methods = {}
    hourly_sales = {}
    
    for f in sales_dir.glob("*.jsonl"):
        file_date = f.stem.split("_")[-1]
        if file_date < start_date or file_date > end_date:
            continue
        
        with open(f, encoding="utf-8") as file:
            for line in file:
                try:
                    sale = json.loads(line.strip())
                    
                    if branch_id and sale.get("_branch_id") != branch_id:
                        continue
                    
                    sale_date = sale.get("timestamp", sale.get("_received_at", ""))[:10]
                    amount = sale.get("total", 0)
                    
                    # Daily aggregation
                    if sale_date not in daily_sales:
                        daily_sales[sale_date] = {"amount": 0, "count": 0}
                    daily_sales[sale_date]["amount"] += amount
                    daily_sales[sale_date]["count"] += 1
                    
                    total_amount += amount
                    total_transactions += 1
                    
                    # Payment method stats
                    pm = sale.get("payment_method", "Efectivo")
                    payment_methods[pm] = payment_methods.get(pm, 0) + amount
                    
                    # Products stats with amounts
                    for item in sale.get("items", []):
                        sku = item.get("sku", "unknown")
                        name = item.get("name", sku)
                        qty = item.get("quantity", 1)
                        item_total = item.get("total", item.get("price", 0) * qty)
                        
                        if sku not in products_sold:
                            products_sold[sku] = {"name": name, "qty": 0, "amount": 0}
                        products_sold[sku]["qty"] += qty
                        products_sold[sku]["amount"] += item_total
                    
                    # Hour stats
                    try:
                        hour = int(sale.get("timestamp", "12:00")[-8:-6])
                        hourly_sales[hour] = hourly_sales.get(hour, 0) + 1
                    # FIX 2026-02-01: Added logging to exception handler
                    except Exception as e:
                        logger.debug("Error parsing hour from timestamp: %s", e)

                # FIX 2026-02-01: Added logging to exception handler
                except Exception as e:
                    logger.debug("Error parsing sale in sales summary: %s", e)
                    continue
    
    # Format for charts
    chart_data = []
    for date in sorted(daily_sales.keys()):
        chart_data.append({
            "date": date,
            "amount": daily_sales[date]["amount"],
            "count": daily_sales[date]["count"]
        })
    
    # Top products with names
    top_products = sorted(products_sold.items(), key=lambda x: x[1]["qty"], reverse=True)[:10]
    
    # Best selling day
    best_day = None
    best_day_amount = 0
    for date, data in daily_sales.items():
        if data["amount"] > best_day_amount:
            best_day = date
            best_day_amount = data["amount"]
    
    # Peak hour
    peak_hour = max(hourly_sales.items(), key=lambda x: x[1])[0] if hourly_sales else 12
    
    # Calculate items sold
    total_items = sum(p["qty"] for p in products_sold.values())
    
    return {
        "period": period,
        "total_amount": round(total_amount, 2),
        "total_transactions": total_transactions,
        "total_items": total_items,
        "average_ticket": round(total_amount / max(total_transactions, 1), 2),
        "items_per_ticket": round(total_items / max(total_transactions, 1), 1),
        "chart_data": chart_data,
        "payment_methods": payment_methods,
        "top_products": [
            {"sku": k, "name": v["name"], "quantity": v["qty"], "amount": round(v["amount"], 2)} 
            for k, v in top_products
        ],
        "best_day": best_day,
        "best_day_amount": round(best_day_amount, 2),
        "peak_hour": peak_hour,
        "slowest_hour": min(hourly_sales.items(), key=lambda x: x[1])[0] if hourly_sales else 8,
        "hourly_distribution": {str(k): v for k, v in sorted(hourly_sales.items())},
        "days_with_sales": len(daily_sales),
        "days_in_period": days,
        "daily_average": round(total_amount / max(len(daily_sales), 1), 2),
        "generated_at": datetime.now().isoformat()
    }

@app.get("/api/reports/branch/{branch_id}/detail")
async def get_branch_detail(branch_id: int, auth: dict = Depends(verify_token)):
    """Get detailed report for a specific branch."""
    config = load_config()
    branches = config.get("branches", {})
    
    branch_info = branches.get(str(branch_id))
    if not branch_info:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    
    # Get sync info
    sync_file = DATA_DIR / "branches" / f"{branch_id}_last_sync.json"
    sync_data = {}
    if sync_file.exists():
        sync_data = json.loads(sync_file.read_text(encoding='utf-8'))
    
    # Get last 7 days of sales
    sales_history = []
    today = datetime.now()
    for i in range(7):
        date = (today - timedelta(days=i)).strftime("%Y%m%d")
        sales_file = DATA_DIR / "sales" / f"{branch_id}_{date}.jsonl"
        day_total = 0
        day_count = 0
        if sales_file.exists():
            with open(sales_file, encoding="utf-8") as f:
                for line in f:
                    try:
                        sale = json.loads(line.strip())
                        day_total += sale.get("total", 0)
                        day_count += 1
                    except Exception as e:
                        logger.debug("Error parsing sale line in branch detail: %s", e)
                        continue
        sales_history.append({
            "date": (today - timedelta(days=i)).strftime("%Y-%m-%d"),
            "amount": day_total,
            "count": day_count
        })
    
    return {
        "branch_id": branch_id,
        "name": branch_info.get("name"),
        "registered_at": branch_info.get("registered_at"),
        "last_sync": sync_data.get("timestamp"),
        "sales_history": sales_history,
        "total_week": sum(d["amount"] for d in sales_history),
        "transactions_week": sum(d["count"] for d in sales_history)
    }

# ============== SALES SEARCH ENDPOINTS ==============

@app.get("/api/sales/search")
async def search_sales(
    folio: Optional[str] = None,
    branch_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
    auth: dict = Depends(verify_token)
):
    """Search sales by folio, branch, or date range."""
    results = []
    
    # Determine date range
    default_start = datetime.now() - timedelta(days=7)
    default_end = datetime.now()

    start_date = _safe_strptime(date_from, "%Y-%m-%d", default_start) if date_from else default_start
    end_date = _safe_strptime(date_to, "%Y-%m-%d", default_end) if date_to else default_end
    
    # Collect sales files
    sales_dir = DATA_DIR / "sales"
    if not sales_dir.exists():
        return {"sales": [], "total": 0}
    
    # Get all branches or filter by branch_id
    config = load_config()
    branches = config.get("branches", {})
    branch_ids = [branch_id] if branch_id else [int(b) for b in branches.keys()]
    
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y%m%d")
        
        for bid in branch_ids:
            sales_file = sales_dir / f"{bid}_{date_str}.jsonl"
            if not sales_file.exists():
                continue
            
            with open(sales_file, encoding="utf-8") as f:
                for line in f:
                    try:
                        sale = json.loads(line.strip())
                        
                        # Filter by folio if specified
                        if folio:
                            sale_folio = str(sale.get("folio", ""))
                            if folio.lower() not in sale_folio.lower():
                                continue
                        
                        # Add branch info
                        sale["branch_id"] = bid
                        sale["branch_name"] = branches.get(str(bid), {}).get("name", f"Sucursal {bid}")
                        results.append(sale)
                        
                        if len(results) >= limit:
                            break
                    except Exception as e:
                        logger.debug("Error parsing sale in search: %s", e)
                        continue

            if len(results) >= limit:
                break
        
        current_date += timedelta(days=1)
        if len(results) >= limit:
            break
    
    # Sort by timestamp descending
    results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    
    return {
        "sales": results[:limit],
        "total": len(results),
        "filters": {
            "folio": folio,
            "branch_id": branch_id,
            "date_from": start_date.strftime("%Y-%m-%d"),
            "date_to": end_date.strftime("%Y-%m-%d")
        }
    }

@app.get("/api/sales/{sale_id}")
async def get_sale_detail(sale_id: str, auth: dict = Depends(verify_token)):
    """Get detailed information for a specific sale."""
    sales_dir = DATA_DIR / "sales"
    
    if not sales_dir.exists():
        raise HTTPException(status_code=404, detail="No sales data")
    
    # Search in all files
    for sales_file in sales_dir.glob("*.jsonl"):
        with open(sales_file, encoding="utf-8") as f:
            for line in f:
                try:
                    sale = json.loads(line.strip())
                    if str(sale.get("folio")) == sale_id or str(sale.get("id")) == sale_id:
                        # Extract branch from filename
                        parts = sales_file.stem.split("_")
                        if len(parts) >= 2:
                            sale["branch_id"] = int(parts[0])
                        return sale
                except Exception as e:
                    logger.debug("Error parsing sale in detail lookup: %s", e)
                    continue

    raise HTTPException(status_code=404, detail="Venta no encontrada")

@app.get("/api/branches/list")
async def list_branches(auth: dict = Depends(verify_token)):
    """List all registered branches."""
    config = load_config()
    branches = config.get("branches", {})
    
    result = []
    for bid, binfo in branches.items():
        # Get last sync time
        sync_file = DATA_DIR / "branches" / f"{bid}_last_sync.json"
        last_sync = None
        if sync_file.exists():
            try:
                sync_data = json.loads(sync_file.read_text(encoding='utf-8'))
                last_sync = sync_data.get("timestamp")
            except Exception as e:
                logger.debug("Error reading sync file for branch %s: %s", bid, e)
        
        result.append({
            "id": int(bid),
            "name": binfo.get("name", f"Sucursal {bid}"),
            "registered_at": binfo.get("registered_at"),
            "last_sync": last_sync
        })
    
    return {"branches": result, "total": len(result)}

# ============== CUSTOMERS ENDPOINTS ==============

CUSTOMERS_FILE = DATA_DIR / "customers.json"

def load_customers():
    if CUSTOMERS_FILE.exists():
        return json.loads(CUSTOMERS_FILE.read_text(encoding='utf-8'))
    return []

def save_customers(customers):
    CUSTOMERS_FILE.write_text(json.dumps(customers, indent=2, ensure_ascii=False), encoding='utf-8')

@app.get("/api/customers/search")
async def search_customers(
    q: str = "",
    limit: int = 20,
    auth: dict = Depends(verify_token)
):
    """Search customers by name, phone, or email."""
    customers = load_customers()
    
    if not q:
        return {"customers": customers[:limit]}
    
    q_lower = q.lower()
    results = []
    for c in customers:
        if (q_lower in c.get("name", "").lower() or
            q_lower in c.get("phone", "") or
            q_lower in c.get("email", "").lower() or
            q_lower in c.get("rfc", "").upper()):
            results.append(c)
            if len(results) >= limit:
                break
    
    return {"customers": results}

@app.get("/api/customers/{customer_id}")
async def get_customer(customer_id: int, auth: dict = Depends(verify_token)):
    """Get customer details with purchase history."""
    customers = load_customers()
    
    customer = None
    for c in customers:
        if c.get("id") == customer_id:
            customer = c
            break
    
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # Get purchase history
    purchases = []
    sales_dir = DATA_DIR / "sales"
    for f in sales_dir.glob("*.jsonl"):
        with open(f, encoding="utf-8") as file:
            for line in file:
                try:
                    sale = json.loads(line.strip())
                    if sale.get("customer_id") == customer_id:
                        purchases.append({
                            "date": sale.get("timestamp", "")[:10],
                            "total": sale.get("total", 0),
                            "items_count": len(sale.get("items", [])),
                            "branch_id": sale.get("_branch_id")
                        })
                except Exception as e:
                    logger.debug("Error parsing sale for customer history: %s", e)
                    continue

    # Sort by date descending
    purchases.sort(key=lambda x: x.get("date", ""), reverse=True)
    
    return {
        "customer": customer,
        "purchases": purchases[:20],
        "total_purchases": len(purchases),
        "total_spent": sum(p.get("total", 0) for p in purchases)
    }

class CustomerCreate(BaseModel):
    name: str
    phone: Optional[str] = ""
    email: Optional[str] = ""
    rfc: Optional[str] = ""
    address: Optional[str] = ""

@app.post("/api/customers/create")
async def create_customer(customer: CustomerCreate, auth: dict = Depends(verify_token)):
    """Create a new customer."""
    customers = load_customers()
    
    # Generate ID
    max_id = max([c.get("id", 0) for c in customers], default=0)
    
    new_customer = {
        "id": max_id + 1,
        "name": customer.name,
        "phone": customer.phone,
        "email": customer.email,
        "rfc": customer.rfc,
        "address": customer.address,
        "created_at": datetime.now().isoformat(),
        "loyalty_points": 0
    }
    
    customers.append(new_customer)
    save_customers(customers)
    
    logger.info("Cliente creado: %s", customer.name)
    
    return {"success": True, "customer": new_customer}

# ============== STOCK ALERTS ==============

@app.get("/api/alerts/low-stock")
async def get_low_stock_alerts(
    threshold: int = 10,
    auth: dict = Depends(verify_token)
):
    """Get products with low stock."""
    products = load_products()
    
    low_stock = []
    for p in products:
        stock = p.get("stock", 0)
        if stock <= threshold:
            low_stock.append({
                "sku": p.get("sku"),
                "name": p.get("name"),
                "stock": stock,
                "price": p.get("price"),
                "status": "critical" if stock <= 5 else "warning"
            })
    
    # Sort by stock ascending
    low_stock.sort(key=lambda x: x.get("stock", 0))
    
    return {
        "alerts": low_stock,
        "count": len(low_stock),
        "threshold": threshold
    }

@app.get("/api/alerts/offline-branches")
async def get_offline_branches(auth: dict = Depends(verify_token)):
    """Get branches that haven't synced recently."""
    config = load_config()
    branches = config.get("branches", {})
    
    offline = []
    for branch_id, info in branches.items():
        sync_file = DATA_DIR / "branches" / f"{branch_id}_last_sync.json"
        
        if sync_file.exists():
            sync_data = json.loads(sync_file.read_text(encoding='utf-8'))
            last_sync = sync_data.get("timestamp")
            try:
                if not last_sync:
                    raise ValueError("last_sync is None or empty")
                last_dt = datetime.fromisoformat(last_sync)
                minutes_ago = (datetime.now() - last_dt).total_seconds() / 60
                if minutes_ago > 5:  # More than 5 minutes
                    offline.append({
                        "branch_id": int(branch_id),
                        "name": info.get("name"),
                        "last_sync": last_sync,
                        "minutes_ago": int(minutes_ago)
                    })
            except Exception as e:
                logger.debug("Error parsing last_sync for branch %s: %s", branch_id, e)
                offline.append({
                    "branch_id": int(branch_id),
                    "name": info.get("name"),
                    "last_sync": last_sync,
                    "minutes_ago": -1
                })
        else:
            offline.append({
                "branch_id": int(branch_id),
                "name": info.get("name"),
                "last_sync": None,
                "minutes_ago": -1
            })
    
    return {"offline_branches": offline, "count": len(offline)}

# ============== PRODUCTS LIST ==============

@app.get("/api/products")
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
        search_lower = search.lower()
        products = [p for p in products if 
                   search_lower in p.get("sku", "").lower() or 
                   search_lower in p.get("name", "").lower()]
    
    total = len(products)
    start = (page - 1) * limit
    end = start + limit
    
    return {
        "products": products[start:end],
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }

# Serve PWA
from fastapi.staticfiles import StaticFiles

# Mount PWA if exists
pwa_dir = Path(__file__).parent.parent / "pwa"
if pwa_dir.exists():
    app.mount("/pwa", StaticFiles(directory=str(pwa_dir), html=True), name="pwa")

# ==================== TOOLS ENDPOINTS ====================

@app.get("/api/cache/clear")
async def clear_cache(auth: dict = Depends(verify_token)):
    """Clear gateway cache."""
    global CACHE
    CACHE = {}
    logger.info("Cache cleared by user")
    return {"success": True, "message": "Cache cleared"}

@app.post("/api/backup/create")
async def create_backup(auth: dict = Depends(verify_token)):
    """Create a backup of gateway data."""
    import shutil
    
    backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_dir = DATA_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / backup_name
    
    try:
        shutil.copytree(DATA_DIR, backup_path, ignore=shutil.ignore_patterns('backups'))
        logger.info("Backup created: %s", backup_name)
        return {"success": True, "backup": backup_name}
    except Exception as e:
        logger.error("Backup failed: %s", e)
        return {"success": False, "error": str(e)}

@app.get("/api/backup/list")
async def list_backups(auth: dict = Depends(verify_token)):
    """List available backups."""
    backups_dir = DATA_DIR / "backups"
    backups_dir.mkdir(exist_ok=True)
    backups = []
    
    for item in sorted(backups_dir.iterdir(), reverse=True):
        if item.is_dir() and item.name.startswith("backup_"):
            try:
                size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
            except Exception as e:
                logger.debug("Error calculating backup size for %s: %s", item.name, e)
                size = 0
            backups.append({
                "name": item.name,
                "date": item.name.replace("backup_", ""),
                "size": size
            })
    
    return {"backups": backups[:20]}

@app.post("/api/broadcast")
async def broadcast_message(data: Dict[str, Any], auth: dict = Depends(verify_token)):
    """Broadcast a message to all branches."""
    message = data.get("message", "")
    if not message:
        raise HTTPException(status_code=400, detail="Message required")
    
    broadcasts_file = DATA_DIR / "broadcasts.json"
    broadcasts = []
    if broadcasts_file.exists():
        try:
            broadcasts = json.loads(broadcasts_file.read_text(encoding='utf-8'))
        except Exception as e:
            logger.debug("Error loading broadcasts file: %s", e)
            broadcasts = []

    broadcasts.append({
        "id": len(broadcasts) + 1,
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "read_by": []
    })
    
    broadcasts_file.write_text(json.dumps(broadcasts[-100:], indent=2, ensure_ascii=False), encoding='utf-8')
    logger.info("Broadcast sent: %s...", message[:50])
    
    return {"success": True, "broadcast_id": len(broadcasts)}

@app.post("/api/products/price-adjust")
async def adjust_prices(data: Dict[str, Any], auth: dict = Depends(verify_token)):
    """Apply price adjustment to all products."""
    percent = data.get("percent", 0)
    adjust_type = data.get("type", "increase")
    
    if percent <= 0 or percent > 100:
        raise HTTPException(status_code=400, detail="Invalid percentage")
    
    adjustments_file = DATA_DIR / "price_adjustments.json"
    adjustments = []
    if adjustments_file.exists():
        try:
            adjustments = json.loads(adjustments_file.read_text(encoding='utf-8'))
        except Exception as e:
            logger.debug("Error loading price adjustments file: %s", e)
            adjustments = []

    adjustment = {
        "id": len(adjustments) + 1,
        "percent": percent,
        "type": adjust_type,
        "timestamp": datetime.now().isoformat(),
        "applied_by": []
    }
    
    adjustments.append(adjustment)
    adjustments_file.write_text(json.dumps(adjustments, indent=2, ensure_ascii=False), encoding='utf-8')
    
    logger.info("Price adjustment created: %s %d%%", adjust_type, percent)
    return {"success": True, "adjustment": adjustment}

@app.get("/api/inventory/force-sync")
async def force_inventory_sync(auth: dict = Depends(verify_token)):
    """Force inventory sync across all branches."""
    sync_flag = DATA_DIR / "force_sync_flag.json"
    sync_flag.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "type": "inventory"
    }))
    logger.info("Force inventory sync triggered")
    return {"success": True, "message": "Sync flag set"}

@app.get("/api/maintenance/purge-old")
async def purge_old_data(auth: dict = Depends(verify_token)):
    """Purge sales data older than 1 year."""
    from datetime import timedelta
    
    cutoff = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    sales_dir = DATA_DIR / "sales"
    purged = 0
    
    if sales_dir.exists():
        for f in sales_dir.glob("*.jsonl"):
            try:
                file_date = f.stem.split("_")[-1]
                if file_date < cutoff:
                    f.unlink()
                    purged += 1
            except Exception as e:
                logger.debug("Error purging old sales file %s: %s", f.name, e)
                continue

    logger.info("Purged %d old sales files", purged)
    return {"success": True, "purged_files": purged}

# --- EXPORT ENDPOINTS (Orchestrator Model) ---
# La app móvil dispara, el servidor genera

EXPORTS_DIR = DATA_DIR / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)

@app.post("/api/exports/sales-report")
async def export_sales_report(data: Dict[str, Any], auth: dict = Depends(verify_token)):
    """Genera reporte de ventas en Excel/CSV."""
    period = data.get("period", "month")
    
    # Calcular fechas
    today = datetime.now()
    if period == "week":
        start = today - timedelta(days=7)
    elif period == "month":
        start = today - timedelta(days=30)
    elif period == "year":
        start = today - timedelta(days=365)
    else:
        start = today - timedelta(days=30)
    
    # Recopilar ventas
    sales = []
    sales_dir = DATA_DIR / "sales"
    if sales_dir.exists():
        for f in sorted(sales_dir.glob("*.jsonl"), reverse=True):
            try:
                for line in f.read_text(encoding='utf-8').strip().split("\n"):
                    if line:
                        sale = json.loads(line)
                        sales.append(sale)
            except Exception as e:
                logger.debug("Error reading sales file %s for export: %s", f.name, e)
                continue

    # Generar CSV
    filename = f"ventas_{today.strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = EXPORTS_DIR / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("Folio,Fecha,Sucursal,Total,Items,Metodo Pago\n")
        for s in sales[:1000]:  # Limitar a 1000
            folio = s.get('folio', s.get('sale_id', '-'))
            fecha = s.get('timestamp', '-')[:19]
            sucursal = s.get('branch_name', f"Suc {s.get('branch_id', '?')}")
            total = s.get('total', 0)
            items = len(s.get('items', []))
            metodo = s.get('payment_method', 'Efectivo')
            f.write(f"{folio},{fecha},{sucursal},{total},{items},{metodo}\n")
    
    logger.info("Exported sales report: %s", filename)
    return {
        "success": True, 
        "filename": filename,
        "records": len(sales[:1000]),
        "download_url": f"/api/exports/download/{filename}",
        "message": f"Reporte generado con {len(sales[:1000])} ventas. Disponible en PWA."
    }

@app.post("/api/exports/catalog")
async def export_catalog(auth: dict = Depends(verify_token)):
    """Exporta catálogo de productos."""
    products = []
    
    # Cargar productos de todas las sucursales
    branches_dir = DATA_DIR / "branches"
    if branches_dir.exists():
        for bf in branches_dir.glob("branch_*.json"):
            try:
                data = json.loads(bf.read_text(encoding='utf-8'))
                for p in data.get("products", []):
                    products.append({
                        "sucursal": data.get("branch_id"),
                        **p
                    })
            except Exception as e:
                logger.debug("Error reading branch file %s for catalog export: %s", bf.name, e)
                continue

    # Generar CSV
    filename = f"catalogo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = EXPORTS_DIR / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("SKU,Nombre,Precio,Costo,Stock,Sucursal\n")
        for p in products:
            sku = p.get('sku', '-')
            nombre = p.get('name', '-').replace(',', ' ')
            precio = p.get('price', 0)
            costo = p.get('cost', 0)
            stock = p.get('stock', 0)
            suc = p.get('sucursal', '-')
            f.write(f"{sku},{nombre},{precio},{costo},{stock},{suc}\n")
    
    logger.info("Exported catalog: %s", filename)
    return {
        "success": True,
        "filename": filename,
        "products": len(products),
        "download_url": f"/api/exports/download/{filename}",
        "message": f"Catálogo exportado con {len(products)} productos."
    }

@app.post("/api/exports/tickets")
async def export_tickets(data: Dict[str, Any], auth: dict = Depends(verify_token)):
    """Exporta historial de tickets."""
    days = data.get("days", 30)
    
    # Similar a sales pero formato ticket
    sales = []
    sales_dir = DATA_DIR / "sales"
    if sales_dir.exists():
        for f in sorted(sales_dir.glob("*.jsonl"), reverse=True):
            try:
                for line in f.read_text(encoding='utf-8').strip().split("\n"):
                    if line:
                        sales.append(json.loads(line))
            except Exception as e:
                logger.debug("Error reading sales file %s for tickets export: %s", f.name, e)
                continue

    filename = f"tickets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = EXPORTS_DIR / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write("Ticket,Fecha,Sucursal,Cliente,Total,Items\n")
        for s in sales[:500]:
            ticket = s.get('folio', s.get('sale_id', '-'))
            fecha = s.get('timestamp', '-')[:10]
            suc = s.get('branch_name', '-')
            cliente = s.get('customer_name', 'Público General')
            total = s.get('total', 0)
            items = len(s.get('items', []))
            f.write(f"{ticket},{fecha},{suc},{cliente},{total},{items}\n")
    
    logger.info("Exported tickets: %s", filename)
    return {
        "success": True,
        "filename": filename,
        "tickets": len(sales[:500]),
        "download_url": f"/api/exports/download/{filename}"
    }

@app.get("/api/exports/download/{filename}")
async def download_export(filename: str, auth: dict = Depends(verify_token)):
    """Descarga un archivo exportado."""
    # Validar nombre de archivo
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    filepath = EXPORTS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="text/csv"
    )

@app.get("/api/exports/list")
async def list_exports(auth: dict = Depends(verify_token)):
    """Lista archivos exportados disponibles."""
    exports = []
    if EXPORTS_DIR.exists():
        for f in sorted(EXPORTS_DIR.glob("*"), reverse=True):
            if f.is_file():
                exports.append({
                    "filename": f.name,
                    "size": f.stat().st_size,
                    "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                    "download_url": f"/api/exports/download/{f.name}"
                })
    return {"exports": exports[:50]}

# ==============================================================================
# ENDPOINTS CFDI - FACTURACIÓN ELECTRÓNICA VIA FACTURAPI
# ==============================================================================

class CFDICustomer(BaseModel):
    legal_name: str
    tax_id: str
    tax_system: str = "601"
    email: Optional[str] = None
    zip: str

class CFDIItem(BaseModel):
    product_key: str = "01010101"
    description: str
    quantity: float = 1
    price: float
    tax_included: bool = True

class CFDICreateRequest(BaseModel):
    terminal_id: int
    sale_id: int
    request_id: Optional[str] = None
    customer: CFDICustomer
    items: List[CFDIItem]
    payment_form: str = "01"
    payment_method: str = "PUE"
    use: str = "G03"
    series: str = "A"
    folio_number: Optional[int] = None

FACTURAPI_CONFIG_FILE = DATA_DIR / "facturapi_config.json"

def load_facturapi_config():
    if FACTURAPI_CONFIG_FILE.exists():
        return json.loads(FACTURAPI_CONFIG_FILE.read_text(encoding='utf-8'))
    return {}

def get_facturapi():
    try:
        sys.path.insert(0, str(SCRIPT_DIR.parent))
        from app.fiscal.facturapi_connector import Facturapi
        config = load_facturapi_config()
        api_key = config.get("api_key") or os.getenv("FACTURAPI_API_KEY")
        return Facturapi(api_key) if api_key else None
    except Exception as e:
        logger.warning(f"Error cargando Facturapi: {e}")
        return None

@app.post("/api/cfdi/create")
async def create_cfdi(request: CFDICreateRequest, auth: dict = Depends(verify_token)):
    facturapi = get_facturapi()
    if not facturapi:
        raise HTTPException(status_code=503, detail="Facturapi no configurado")
    try:
        invoice = facturapi.invoices.create({
            "customer": {"legal_name": request.customer.legal_name, "tax_id": request.customer.tax_id.upper(),
                        "tax_system": request.customer.tax_system, "address": {"zip": request.customer.zip},
                        **({"email": request.customer.email} if request.customer.email else {})},
            "items": [{"product": {"description": i.description, "product_key": i.product_key,
                      "unit_key": "H87", "price": i.price, "tax_included": i.tax_included}, 
                      "quantity": i.quantity} for i in request.items],
            "payment_form": request.payment_form, "payment_method": request.payment_method,
            "use": request.use, "series": request.series, "folio_number": request.folio_number})
        logger.info(
            "CFDI created uuid=%s sale_id=%s terminal_id=%s",
            invoice.get("uuid"),
            request.sale_id,
            request.terminal_id,
        )
        return {
            "success": True,
            "uuid": invoice.get("uuid"),
            "id": invoice.get("id"),
            "total": invoice.get("total"),
            "sale_id": request.sale_id,
            "terminal_id": request.terminal_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/cfdi/{invoice_id}/pdf")
async def download_cfdi_pdf(invoice_id: str, auth: dict = Depends(verify_token)):
    facturapi = get_facturapi()
    if not facturapi:
        raise HTTPException(status_code=503, detail="Facturapi no configurado")
    from fastapi.responses import Response
    return Response(content=facturapi.invoices.download_pdf(invoice_id), media_type="application/pdf")

@app.get("/api/cfdi/{invoice_id}/xml")
async def download_cfdi_xml(invoice_id: str, auth: dict = Depends(verify_token)):
    facturapi = get_facturapi()
    if not facturapi:
        raise HTTPException(status_code=503, detail="Facturapi no configurado")
    xml = facturapi.invoices.download_xml(invoice_id)
    from fastapi.responses import Response
    return Response(content=xml if isinstance(xml, bytes) else xml.encode(), media_type="application/xml")

@app.post("/api/cfdi/{invoice_id}/email")
async def send_cfdi_email(invoice_id: str, email: str, auth: dict = Depends(verify_token)):
    facturapi = get_facturapi()
    if not facturapi:
        raise HTTPException(status_code=503, detail="Facturapi no configurado")
    facturapi.invoices.send_by_email(invoice_id, email)
    return {"success": True}

@app.get("/api/cfdi/list")
async def list_cfdis(limit: int = 50, auth: dict = Depends(verify_token)):
    facturapi = get_facturapi()
    if not facturapi:
        return {"success": True, "cfdis": []}
    return {"success": True, "cfdis": facturapi.invoices.list({"limit": limit}).get("data", [])}

@app.post("/api/cfdi/config")
async def configure_facturapi(api_key: str, auth: dict = Depends(verify_token)):
    if auth.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")
    config = load_facturapi_config()
    config["api_key"] = api_key
    FACTURAPI_CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')
    return {"success": True}

@app.get("/api/cfdi/status")
async def cfdi_status(auth: dict = Depends(verify_token)):
    return {"configured": bool(load_facturapi_config().get("api_key"))}

# --- MAIN ---
if __name__ == "__main__":
    import uvicorn
    
    # Create initial config if not exists
    if not CONFIG_FILE.exists():
        import secrets
        initial_config = {
            "admin_token": secrets.token_urlsafe(32),
            "branches": {}
        }
        save_config(initial_config)
        print(f"\n{'='*60}")
        print("TITAN Gateway - Configuración Inicial")
        print(f"{'='*60}")
        print(f"\n⚠️  Token de administrador generado:")
        print(f"\n    {initial_config['admin_token']}")
        print(f"\n⚠️  Guarda este token de forma segura!")
        print(f"{'='*60}\n")
    
    # Verificar si existen certificados SSL
    cert_file = Path(__file__).parent / "cert.pem"
    key_file = Path(__file__).parent / "key.pem"
    
    if cert_file.exists() and key_file.exists():
        print("🔒 Iniciando TITAN Gateway con HTTPS en https://0.0.0.0:8000")
        print("   ⚠️  Acepta el certificado en tu navegador")
        uvicorn.run(app, host="0.0.0.0", port=8000, 
                    ssl_certfile=str(cert_file), ssl_keyfile=str(key_file))
    else:
        print("Iniciando TITAN Gateway en http://0.0.0.0:8000")
        uvicorn.run(app, host="0.0.0.0", port=8000)
