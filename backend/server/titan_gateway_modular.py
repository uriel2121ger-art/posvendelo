#!/usr/bin/env python3
"""
TITAN Gateway - Servidor Central Multi-Sucursal (REFACTORED)

Este servidor recibe datos de todas las sucursales y los consolida.
Se ejecuta en el servidor central (VM en Proxmox o similar).

Ejecutar con: uvicorn titan_gateway:app --host 0.0.0.0 --port 8000
"""

import os
import logging
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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

# Intentar importar FastAPI
try:
    from fastapi import FastAPI, Depends, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError:
    print("ERROR: FastAPI no instalado. Ejecuta: pip install fastapi uvicorn python-multipart")
    import sys
    sys.exit(1)

# --- DATA STORAGE SETUP ---
DATA_DIR = Path("./gateway_data")
DATA_DIR.mkdir(exist_ok=True)
(DATA_DIR / "backups").mkdir(exist_ok=True)
(DATA_DIR / "sales").mkdir(exist_ok=True)
(DATA_DIR / "branches").mkdir(exist_ok=True)

# --- FASTAPI APP ---
app = FastAPI(
    title="TITAN Gateway",
    description="Servidor Central Multi-Sucursal para TITAN POS",
    version="2.0.0"
)

# FIX 2026-02-01: CORS - Default to empty list (secure), require explicit configuration
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
except ImportError:
    logger.warning("⚠️ Rate limiter no disponible")
except Exception as e:
    logger.warning(f"⚠️ Error configurando rate limiter: {e}")

# Security Headers Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware para agregar headers de seguridad HTTP"""
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
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

# --- INCLUDE ROUTERS ---
import sys
backend_root = str(Path(__file__).resolve().parent.parent)
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

try:
    from server.routers import (
        terminals_router,
        branches_router,
        sales_router,
        products_router,
        alerts_router,
        logs_router,
        backups_router,
        pwa_router,
        tools_router,
    )
except Exception as package_err:
    # #region agent log
    try:
        import time
        with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "5e74cc",
                "runId": "post-fix",
                "hypothesisId": "H25_router_import_strategy",
                "location": "server/titan_gateway_modular.py:router_import",
                "message": "Package import failed, trying local routers import",
                "data": {"error": str(package_err), "backend_root": backend_root},
                "timestamp": int(time.time() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    from routers import (
        terminals_router,
        branches_router,
        sales_router,
        products_router,
        alerts_router,
        logs_router,
        backups_router,
        pwa_router,
        tools_router,
    )

app.include_router(terminals_router)
app.include_router(branches_router)
app.include_router(sales_router)
app.include_router(products_router)
app.include_router(alerts_router)
app.include_router(logs_router)
app.include_router(backups_router)
app.include_router(pwa_router)
app.include_router(tools_router)

logger.info("✅ Routers cargados: terminals, branches, sales, products, alerts, logs, backups, pwa, tools")

# --- COMPATIBILITY IMPORTS ---
try:
    from auth import verify_token
    from request_policies import (
        enforce_write_role,
        require_terminal_id,
        check_and_record_idempotency,
        idempotency_header,
        terminal_header,
    )
except Exception:
    from server.auth import verify_token
    from server.request_policies import (
        enforce_write_role,
        require_terminal_id,
        check_and_record_idempotency,
        idempotency_header,
        terminal_header,
    )


class GenericSyncPayload(BaseModel):
    """Generic sync payload from client."""
    data: List[Dict[str, Any]]
    timestamp: str
    terminal_id: int
    request_id: Optional[str] = None


def _update_last_sync(branch_id: int, table: str, records_received: int, terminal_id: int) -> None:
    """Persist last sync status consumed by /api/v1/sync/status."""
    sync_file = DATA_DIR / "branches" / f"{branch_id}_last_sync.json"
    content = {
        "timestamp": datetime.now().isoformat(),
        "table": table,
        "records_received": records_received,
        "terminal_id": terminal_id,
    }
    sync_file.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
    # #region agent log
    try:
        import time
        with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "5e74cc",
                "runId": "post-fix",
                "hypothesisId": "H23_sync_status_not_updated",
                "location": "server/titan_gateway_modular.py:_update_last_sync",
                "message": "last_sync file updated",
                "data": {"branch_id": branch_id, "table": table, "records_received": records_received, "terminal_id": terminal_id},
                "timestamp": int(time.time() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion


@app.post("/api/v1/sync/sales")
async def sync_sales_v1_compat(
    payload: GenericSyncPayload,
    auth: dict = Depends(verify_token),
    idem_key: str | None = Depends(idempotency_header),
    hdr_terminal_id: int | None = Depends(terminal_header),
):
    """Compatibility endpoint for MultiCajaClient sales sync."""
    enforce_write_role(auth)
    terminal_id = require_terminal_id(payload.terminal_id, hdr_terminal_id)
    request_key = payload.request_id or idem_key
    if check_and_record_idempotency(request_key, "/api/v1/sync/sales", terminal_id):
        return {"success": True, "deduplicated": True, "records_received": 0, "table": "sales"}

    branch_id = int(auth.get("branch_id", 1) or 1)
    sales_file = DATA_DIR / "sales" / f"{branch_id}_{datetime.now().strftime('%Y%m%d')}.jsonl"
    sales_file.parent.mkdir(parents=True, exist_ok=True)

    accepted_ids: List[int] = []
    with open(sales_file, "a", encoding="utf-8") as f:
        for row in payload.data:
            row_id = row.get("id")
            if isinstance(row_id, int):
                accepted_ids.append(row_id)
            row["_branch_id"] = branch_id
            row["_terminal_id"] = terminal_id
            row["_received_at"] = datetime.now().isoformat()
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # #region agent log
    try:
        import time
        with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "5e74cc",
                "runId": "post-fix",
                "hypothesisId": "H12_modular_v1_sync_missing",
                "location": "server/titan_gateway_modular.py:sync_sales_v1_compat",
                "message": "v1 sales compatibility endpoint processed payload",
                "data": {"branch_id": branch_id, "terminal_id": terminal_id, "records_received": len(payload.data)},
                "timestamp": int(time.time() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    _update_last_sync(branch_id, "sales", len(payload.data), terminal_id)
    return {
        "success": True,
        "records_received": len(payload.data),
        "duplicates": 0,
        "accepted_ids": accepted_ids,
        "table": "sales",
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/v1/sync/{table_name}")
async def sync_generic_table_v1_compat(
    table_name: str,
    payload: GenericSyncPayload,
    auth: dict = Depends(verify_token),
    idem_key: str | None = Depends(idempotency_header),
    hdr_terminal_id: int | None = Depends(terminal_header),
):
    """Compatibility endpoint for MultiCajaClient generic sync."""
    enforce_write_role(auth)
    terminal_id = require_terminal_id(payload.terminal_id, hdr_terminal_id)
    safe_table = table_name.strip().lower()
    if not re.fullmatch(r"[a-z0-9_-]+", safe_table):
        raise HTTPException(status_code=400, detail=f"Invalid table name: {table_name}")

    request_key = payload.request_id or idem_key
    if check_and_record_idempotency(request_key, f"/api/v1/sync/{safe_table}", terminal_id):
        return {"success": True, "deduplicated": True, "records_received": 0, "table": safe_table}

    branch_id = int(auth.get("branch_id", 1) or 1)
    branch_dir = DATA_DIR / "branches"
    branch_dir.mkdir(parents=True, exist_ok=True)

    if safe_table == "inventory":
        target_file = branch_dir / f"{branch_id}_inventory.json"
    elif safe_table == "customers":
        target_file = branch_dir / f"{branch_id}_customers.json"
    else:
        target_file = branch_dir / f"{branch_id}_{safe_table}.json"

    existing: List[Dict[str, Any]] = []
    if target_file.exists():
        try:
            existing = json.loads(target_file.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []

    for row in payload.data:
        row["_branch_id"] = branch_id
        row["_terminal_id"] = terminal_id
        row["_received_at"] = datetime.now().isoformat()
    existing.extend(payload.data)
    target_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    accepted_ids = [r.get("id") for r in payload.data if isinstance(r.get("id"), int)]
    # #region agent log
    try:
        import time
        with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "5e74cc",
                "runId": "post-fix",
                "hypothesisId": "H12_modular_v1_sync_missing",
                "location": "server/titan_gateway_modular.py:sync_generic_table_v1_compat",
                "message": "v1 generic compatibility endpoint processed payload",
                "data": {
                    "table": safe_table,
                    "branch_id": branch_id,
                    "terminal_id": terminal_id,
                    "records_received": len(payload.data),
                },
                "timestamp": int(time.time() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    _update_last_sync(branch_id, safe_table, len(payload.data), terminal_id)
    return {
        "success": True,
        "records_received": len(payload.data),
        "accepted_ids": accepted_ids,
        "table": safe_table,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/v1/sync/status")
async def sync_status_v1_compat(auth: dict = Depends(verify_token)):
    """Compatibility endpoint for client get_last_sync_status()."""
    branch_id = int(auth.get("branch_id", 1) or 1)
    sync_file = DATA_DIR / "branches" / f"{branch_id}_last_sync.json"
    if sync_file.exists():
        try:
            content = json.loads(sync_file.read_text(encoding="utf-8"))
        except Exception:
            content = {}
    else:
        content = {}
    # #region agent log
    try:
        import time
        with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "5e74cc",
                "runId": "post-fix",
                "hypothesisId": "H14_sync_status_route_missing",
                "location": "server/titan_gateway_modular.py:sync_status_v1_compat",
                "message": "sync status compatibility endpoint served",
                "data": {"branch_id": branch_id, "has_content": bool(content)},
                "timestamp": int(time.time() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    return {
        "branch_id": branch_id,
        "status": "ok",
        "last_sync": content.get("timestamp"),
        "details": content,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/v1/sync/{table_name}")
async def pull_generic_table_v1_compat(
    table_name: str,
    limit: int = 500,
    since: Optional[str] = None,
    auth: dict = Depends(verify_token),
):
    """Compatibility endpoint for client pull_table()."""
    branch_id = int(auth.get("branch_id", 1) or 1)
    safe_table = table_name.strip().lower()
    if not re.fullmatch(r"[a-z0-9_-]+", safe_table):
        raise HTTPException(status_code=400, detail=f"Invalid table name: {table_name}")

    if safe_table == "sales":
        data = []
        sales_dir = DATA_DIR / "sales"
        for f in sales_dir.glob(f"{branch_id}_*.jsonl"):
            try:
                with open(f, encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            row = json.loads(line.strip())
                        except Exception:
                            continue
                        if since:
                            row_ts = str(row.get("timestamp", row.get("_received_at", "")))
                            if row_ts and row_ts < since:
                                continue
                        data.append(row)
            except Exception:
                continue
        data = data[-max(1, limit):]
        # #region agent log
        try:
            import time
            with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "sessionId": "5e74cc",
                    "runId": "post-fix",
                    "hypothesisId": "H22_sales_pull_source_mismatch",
                    "location": "server/titan_gateway_modular.py:pull_generic_table_v1_compat",
                    "message": "sales pull reads jsonl source",
                    "data": {"branch_id": branch_id, "records": len(data), "limit": limit, "since": bool(since)},
                    "timestamp": int(time.time() * 1000),
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass
        # #endregion
        return {
            "success": True,
            "table": safe_table,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }

    if safe_table == "products":
        # Keep backward compatibility with product_updates.json, but also include
        # generic branch-scoped products synced through /api/v1/sync/products.
        data = []
        updates_file = DATA_DIR / "product_updates.json"
        branch_products_file = DATA_DIR / "branches" / f"{branch_id}_products.json"
        for src in (updates_file, branch_products_file):
            if src.exists():
                try:
                    raw = json.loads(src.read_text(encoding="utf-8"))
                    if isinstance(raw, list):
                        data.extend(raw)
                except Exception:
                    continue
        def _semantic_product_key(row: Dict[str, Any]) -> Optional[str]:
            sku = row.get("sku")
            if isinstance(sku, str) and sku.strip():
                return f"sku:{sku.strip().lower()}"
            pid = row.get("id")
            if pid is not None:
                return f"id:{pid}"
            return None

        source_duplicate_keys = {}
        try:
            key_counts = {}
            for row in data:
                if not isinstance(row, dict):
                    continue
                key = _semantic_product_key(row)
                if not key:
                    continue
                key_counts[key] = key_counts.get(key, 0) + 1
            source_duplicate_keys = {k: v for k, v in key_counts.items() if v > 1}
        except Exception:
            source_duplicate_keys = {}
        # Deduplicate by semantic key. Branch-scoped records should override
        # generic updates when they share the same sku/id.
        merged_by_key: Dict[str, Dict[str, Any]] = {}
        passthrough_rows: List[Dict[str, Any]] = []
        for row in data:
            if not isinstance(row, dict):
                continue
            key = _semantic_product_key(row)
            if not key:
                passthrough_rows.append(row)
                continue
            merged_by_key[key] = row
        data = list(merged_by_key.values()) + passthrough_rows
        output_duplicate_keys = {}
        try:
            out_counts = {}
            for row in data:
                if not isinstance(row, dict):
                    continue
                key = _semantic_product_key(row)
                if not key:
                    continue
                out_counts[key] = out_counts.get(key, 0) + 1
            output_duplicate_keys = {k: v for k, v in out_counts.items() if v > 1}
        except Exception:
            output_duplicate_keys = {}
        # #region agent log
        try:
            import time
            with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "sessionId": "5e74cc",
                    "runId": "post-fix",
                    "hypothesisId": "H26_products_pull_source_split",
                    "location": "server/titan_gateway_modular.py:pull_generic_table_v1_compat",
                    "message": "products pull merged updates and branch sources",
                    "data": {
                        "branch_id": branch_id,
                        "records": len(data),
                        "source_duplicate_keys": source_duplicate_keys,
                        "output_duplicate_keys": output_duplicate_keys,
                    },
                    "timestamp": int(time.time() * 1000),
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass
        # #endregion
        return {
            "success": True,
            "table": safe_table,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }
    elif safe_table == "inventory":
        target_file = DATA_DIR / "branches" / f"{branch_id}_inventory.json"
    elif safe_table == "customers":
        target_file = DATA_DIR / "branches" / f"{branch_id}_customers.json"
    else:
        target_file = DATA_DIR / "branches" / f"{branch_id}_{safe_table}.json"

    data: List[Dict[str, Any]] = []
    if target_file.exists():
        try:
            raw = json.loads(target_file.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                data = raw
        except Exception:
            data = []

    # #region agent log
    try:
        import time
        with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "5e74cc",
                "runId": "post-fix",
                "hypothesisId": "H15_pull_table_get_not_supported",
                "location": "server/titan_gateway_modular.py:pull_generic_table_v1_compat",
                "message": "pull table compatibility endpoint served",
                "data": {"table": safe_table, "branch_id": branch_id, "records": len(data)},
                "timestamp": int(time.time() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    return {
        "success": True,
        "table": safe_table,
        "data": data,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/auth/test")
async def auth_test_compat(auth: dict = Depends(verify_token)):
    """Compatibility endpoint for client token validation."""
    # #region agent log
    try:
        import time
        with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "5e74cc",
                "runId": "post-fix",
                "hypothesisId": "H21_auth_test_route_missing",
                "location": "server/titan_gateway_modular.py:auth_test_compat",
                "message": "auth test compatibility endpoint served",
                "data": {"role": auth.get("role"), "branch_id": auth.get("branch_id")},
                "timestamp": int(time.time() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    return {
        "ok": True,
        "role": auth.get("role"),
        "branch_id": auth.get("branch_id"),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/info")
async def api_info_compat(auth: dict = Depends(verify_token)):
    """Compatibility endpoint for client get_server_info()."""
    # #region agent log
    try:
        import time
        with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "5e74cc",
                "runId": "post-fix",
                "hypothesisId": "H24_get_server_info_status_missing",
                "location": "server/titan_gateway_modular.py:api_info_compat",
                "message": "api info compatibility endpoint served",
                "data": {"role": auth.get("role"), "branch_id": auth.get("branch_id")},
                "timestamp": int(time.time() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    return {
        "name": "TITAN Gateway",
        "version": "2.0.0",
        "status": "running",
        "mode": "modular",
        "role": auth.get("role"),
        "branch_id": auth.get("branch_id"),
        "timestamp": datetime.now().isoformat(),
    }

# --- ROOT ENDPOINTS ---
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "TITAN Gateway",
        "version": "2.0.0",
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

# --- MAIN ---
if __name__ == "__main__":
    import uvicorn
    from auth import load_config, save_config, CONFIG_FILE
    import secrets
    
    # Create initial config if not exists
    if not CONFIG_FILE.exists():
        initial_config = {
            "admin_token": secrets.token_urlsafe(32),
            "branches": {}
        }
        save_config(initial_config)
        # FIX 2026-02-01: Do not print token to stdout - write to secure file instead
        logger.warning("SECURITY: New admin token generated. Check config.json securely.")
    
    # Check for SSL
    cert_file = Path("certs/gateway.crt")
    key_file = Path("certs/gateway.key")
    
    if cert_file.exists() and key_file.exists():
        print("Iniciando TITAN Gateway con SSL en https://0.0.0.0:8000")
        uvicorn.run(app, host="0.0.0.0", port=8000, 
                    ssl_certfile=str(cert_file), ssl_keyfile=str(key_file))
    else:
        print("Iniciando TITAN Gateway en http://0.0.0.0:8000")
        uvicorn.run(app, host="0.0.0.0", port=8000)
