"""
POSVENDELO — Main Application Entrypoint

App factory + module routers + lifespan.

Run: cd backend && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
"""

import asyncio
import json
import logging
import os
import platform
import sys
import tempfile
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import httpx
import psutil
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
_heartbeat_interval_seconds = int(os.getenv("CONTROL_PLANE_HEARTBEAT_INTERVAL_SECONDS", "300"))
_command_poll_interval_seconds = int(os.getenv("COMMAND_POLL_INTERVAL_SECONDS", "30"))


def _csv_env(name: str) -> list[str]:
    return [value.strip() for value in os.environ.get(name, "").split(",") if value.strip()]


def _get_last_backup_at() -> str | None:
    backup_dir = Path(os.getenv("POSVENDELO_BACKUP_DIR", "/backups"))
    if not backup_dir.exists() or not backup_dir.is_dir():
        return None

    newest_file = None
    newest_mtime = 0.0
    for child in backup_dir.iterdir():
        if not child.is_file():
            continue
        stat = child.stat()
        if stat.st_mtime > newest_mtime:
            newest_mtime = stat.st_mtime
            newest_file = child

    if newest_file is None:
        return None
    return datetime.fromtimestamp(newest_file.stat().st_mtime, tz=timezone.utc).isoformat()


async def _get_sales_today() -> float:
    try:
        from db.connection import get_pool

        pool = await get_pool()
        async with pool.acquire() as conn:
            total = await conn.fetchval(
                """
                SELECT COALESCE(SUM(total), 0)
                FROM sales
                WHERE status = 'completed'
                  AND DATE("timestamp") = CURRENT_DATE
                """
            )
        return str(total or 0)
    except Exception as exc:
        logger.warning("Heartbeat sales query failed (non-fatal): %s", exc)
        return "0"


async def _build_heartbeat_payload() -> dict | None:
    control_plane_url = os.getenv("CONTROL_PLANE_URL", "").strip().rstrip("/")
    branch_id_raw = os.getenv("POSVENDELO_BRANCH_ID", "").strip()
    if not control_plane_url or not branch_id_raw:
        return None

    try:
        branch_id = int(branch_id_raw)
    except ValueError:
        logger.warning("Invalid POSVENDELO_BRANCH_ID for heartbeat: %s", branch_id_raw)
        return None

    return {
        "url": f"{control_plane_url}/api/v1/heartbeat",
        "payload": {
            "branch_id": branch_id,
            "pos_version": runtime_version,
            "app_version": os.getenv("POSVENDELO_APP_VERSION", runtime_version),
            "disk_used_pct": round(psutil.disk_usage("/").percent, 2),
            "sales_today": await _get_sales_today(),
            "last_backup_at": _get_last_backup_at(),
            "status": "ok",
        },
    }


def _load_agent_install_context() -> tuple[str | None, str | None]:
    control_plane_url = os.getenv("CONTROL_PLANE_URL", "").strip().rstrip("/") or None
    config_path_raw = os.getenv("POSVENDELO_AGENT_CONFIG_PATH", "").strip()
    if not config_path_raw:
        return control_plane_url, None
    config_path = Path(config_path_raw).expanduser()
    if not config_path.exists():
        return control_plane_url, None
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return control_plane_url, None
    next_cp = str(payload.get("controlPlaneUrl") or control_plane_url or "").strip().rstrip("/")
    install_token = str(payload.get("installToken") or "").strip()
    return (next_cp or None, install_token or None)


def _parse_iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed.replace(microsecond=0)


def _remote_request_notification(request_type: str) -> tuple[str, str]:
    normalized = request_type.strip().lower()
    if normalized in {"update_product_price", "change_price"}:
        return (
            "Cambio de precio pendiente",
            "El dueño envió un cambio de precio que requiere confirmación local.",
        )
    if normalized in {"update_stock", "stock_adjust"}:
        return (
            "Ajuste de inventario pendiente",
            "Hay un ajuste remoto de inventario esperando confirmación local.",
        )
    return (
        "Solicitud remota pendiente",
        f"Hay una solicitud remota de tipo {request_type} esperando confirmación.",
    )


async def _heartbeat_loop() -> None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            try:
                heartbeat = await _build_heartbeat_payload()
                if heartbeat is None:
                    return
                response = await client.post(
                    heartbeat["url"],
                    json=heartbeat["payload"],
                )
                if response.status_code >= 400:
                    logger.warning(
                        "Heartbeat rejected by control-plane: %s %s",
                        response.status_code,
                        response.text,
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Heartbeat delivery failed (non-fatal): %s", exc)
            await asyncio.sleep(_heartbeat_interval_seconds)


async def _remote_requests_poll_loop() -> None:
    async with httpx.AsyncClient(timeout=7.0) as client:
        while True:
            try:
                control_plane_url, install_token = _load_agent_install_context()
                if not control_plane_url or not install_token:
                    await asyncio.sleep(_command_poll_interval_seconds)
                    continue

                response = await client.get(
                    f"{control_plane_url}/api/v1/cloud/node/remote-requests/pending",
                    headers={"X-Install-Token": install_token},
                )
                if response.status_code >= 400:
                    logger.warning(
                        "Remote requests poll rejected by control-plane: %s %s",
                        response.status_code,
                        response.text,
                    )
                    await asyncio.sleep(_command_poll_interval_seconds)
                    continue

                body = response.json()
                requests = body.get("data") if isinstance(body, dict) else None
                if not isinstance(requests, list) or not requests:
                    await asyncio.sleep(_command_poll_interval_seconds)
                    continue

                from db.connection import DB, get_pool

                pool = await get_pool()
                async with pool.acquire() as conn:
                    db = DB(conn)
                    for item in requests:
                        remote_request_id = int(item.get("id") or 0)
                        if remote_request_id <= 0:
                            continue
                        request_type = str(item.get("request_type") or "").strip()
                        approval_mode = str(item.get("approval_mode") or "local_confirmation").strip()
                        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
                        created_at = _parse_iso_datetime(item.get("created_at"))
                        expires_at = _parse_iso_datetime(item.get("expires_at"))
                        inserted = await db.execute(
                            """
                            INSERT INTO pending_remote_changes (
                                remote_request_id,
                                request_type,
                                approval_mode,
                                status,
                                payload,
                                requested_at,
                                expires_at,
                                created_at,
                                updated_at
                            )
                            VALUES (
                                :remote_request_id,
                                :request_type,
                                :approval_mode,
                                'pending_confirmation',
                                :payload::jsonb,
                                NOW(),
                                :expires_at,
                                COALESCE(:created_at, NOW()),
                                NOW()
                            )
                            ON CONFLICT (remote_request_id) DO NOTHING
                            """,
                            {
                                "remote_request_id": remote_request_id,
                                "request_type": request_type,
                                "approval_mode": approval_mode,
                                "payload": json.dumps(payload, ensure_ascii=True),
                                "created_at": created_at,
                                "expires_at": expires_at,
                            },
                        )
                        if str(inserted).endswith("1"):
                            title, body_text = _remote_request_notification(request_type)
                            await db.execute(
                                """
                                INSERT INTO remote_notifications (title, body, notification_type, sent, created_at)
                                VALUES (:title, :body, 'remote_request', 0, NOW())
                                """,
                                {"title": title, "body": body_text},
                            )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Remote requests poll failed (non-fatal): %s", exc)
            await asyncio.sleep(_command_poll_interval_seconds)

async def _auto_register_if_needed() -> None:
    """Pre-register with control-plane on first boot if no installToken.

    Non-fatal: if this fails (no internet, CP down), the POS works offline.
    Will retry on next boot.
    """
    global runtime_branch_id
    config_path_raw = os.getenv("POSVENDELO_AGENT_CONFIG_PATH", "").strip()
    if not config_path_raw:
        return

    config_path = Path(config_path_raw).expanduser()
    if not config_path.is_file():
        logger.info("Auto-register: agent config not found at %s, skipping", config_path)
        return

    try:
        agent_config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        logger.warning("Auto-register: cannot read agent config: %s", e)
        return

    # Already registered?
    if agent_config.get("installToken"):
        return

    cp_url = str(agent_config.get("controlPlaneUrl", "")).strip().rstrip("/")
    if not cp_url:
        cp_url = os.getenv("CONTROL_PLANE_URL", "").strip().rstrip("/")
    if not cp_url:
        logger.info("Auto-register: no controlPlaneUrl configured, skipping")
        return

    from modules.registration import collect_hw_info
    hw_info = collect_hw_info()

    logger.info("Auto-register: attempting pre-registration with %s", cp_url)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Pre-register with hardware fingerprint
            resp = await client.post(
                f"{cp_url}/api/v1/branches/pre-register",
                json={
                    "hw_info": hw_info,
                    "os_platform": platform.system().lower(),
                    "branch_name": "Sucursal Principal",
                },
            )
            if resp.status_code >= 400:
                logger.warning(
                    "Auto-register: pre-register rejected %s: %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return

            data = resp.json().get("data", {})
            install_token = data.get("install_token")
            branch_id = data.get("branch_id")

            if not install_token:
                logger.warning("Auto-register: no install_token in response")
                return

            # 2. Get bootstrap config (includes signed license)
            bootstrap_resp = await client.get(
                f"{cp_url}/api/v1/branches/bootstrap-config",
                params={"install_token": install_token},
            )
            bootstrap_data = {}
            if bootstrap_resp.status_code < 400:
                bootstrap_data = bootstrap_resp.json().get("data", {})

            # 3. Update agent config
            agent_config["installToken"] = install_token
            if branch_id:
                agent_config["branchId"] = branch_id
            if bootstrap_data.get("license"):
                agent_config["license"] = bootstrap_data["license"]

            # Write back — atomic via tmp + rename (prevents corruption on crash)
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=str(config_path.parent), suffix=".tmp"
            )
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                    json.dump(agent_config, f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, str(config_path))
            except BaseException:
                with suppress(OSError):
                    os.unlink(tmp_path)
                raise

            # 4. Set env var so heartbeat starts working this session
            if branch_id:
                os.environ["POSVENDELO_BRANCH_ID"] = str(branch_id)
                # Also update module-level var used by heartbeat
                runtime_branch_id = str(branch_id)

            logger.info(
                "Auto-register: success — branch_id=%s, token=%s...",
                branch_id,
                install_token[:8] if install_token else "?",
            )
    except Exception as e:
        logger.warning("Auto-register failed (will retry next boot): %s", e)


# ---------------------------------------------------------------------------
# Lifespan (event system + auto-migrations)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(application):
    global runtime_branch_id
    heartbeat_task: asyncio.Task | None = None
    remote_requests_task: asyncio.Task | None = None
    discovery_task: asyncio.Task | None = None

    # Event bridge (legacy EventBus → DomainEvents)
    try:
        from modules.shared.event_bridge import setup_event_bridge
        await setup_event_bridge()
    except Exception as e:
        logger.warning("Event bridge setup failed (non-fatal): %s", e)

    # Sale event hooks (Event Sourcing)
    try:
        from modules.sales.event_hooks import register_sale_event_hooks
        register_sale_event_hooks()
    except Exception as e:
        logger.warning("Sale event hooks failed (non-fatal): %s", e)

    # Seed SAT catalog (idempotent — skips if table already has data)
    try:
        from db.connection import get_pool, DB
        pool = await get_pool()
        async with pool.acquire() as conn:
            db = DB(conn)
            from modules.sat.sat_catalog import seed_sat_catalog
            await seed_sat_catalog(db)
    except Exception as e:
        logger.warning("SAT catalog seed failed (non-fatal): %s", e)

    # Clean up expired JTI revocations from previous sessions
    jti_cleanup_task = None
    try:
        from modules.shared.auth import cleanup_expired_revocations
        await cleanup_expired_revocations()
    except Exception as e:
        logger.warning("JTI revocation cleanup failed (non-fatal): %s", e)

    # Periodic JTI cleanup every hour (table grows with logouts)
    async def _jti_cleanup_loop():
        while True:
            await asyncio.sleep(3600)
            try:
                from modules.shared.auth import cleanup_expired_revocations
                await cleanup_expired_revocations()
            except Exception:
                logger.warning("Periodic JTI cleanup failed (non-fatal)")

    jti_cleanup_task = asyncio.create_task(_jti_cleanup_loop())

    # Auto-register with control-plane if not yet registered
    try:
        await _auto_register_if_needed()
    except Exception as e:
        logger.warning("Auto-register failed (non-fatal): %s", e)

    # Re-read branch_id and CP URL from agent.json if env vars are empty
    # (auto-register writes to agent.json but can't update Docker .env)
    if not runtime_branch_id or not os.getenv("CONTROL_PLANE_URL", "").strip():
        _cp_url, _install_token = _load_agent_install_context()
        config_path_raw = os.getenv("POSVENDELO_AGENT_CONFIG_PATH", "").strip()
        if config_path_raw:
            try:
                _agent = json.loads(Path(config_path_raw).read_text(encoding="utf-8"))
                _bid = _agent.get("branchId")
                if _bid and not runtime_branch_id:
                    runtime_branch_id = str(_bid)
                    os.environ["POSVENDELO_BRANCH_ID"] = runtime_branch_id
                if _cp_url and not os.getenv("CONTROL_PLANE_URL", "").strip():
                    os.environ["CONTROL_PLANE_URL"] = _cp_url
            except Exception as exc:
                logger.warning("Re-read agent.json for branch_id failed: %s", exc)

    if os.getenv("CONTROL_PLANE_URL", "").strip() and runtime_branch_id:
        heartbeat_task = asyncio.create_task(_heartbeat_loop())
        remote_requests_task = asyncio.create_task(_remote_requests_poll_loop())

    # UDP discovery broadcast — siempre activo para que terminales LAN encuentren el servidor
    try:
        from modules.discovery.broadcast import start_discovery_broadcast
        discovery_task = asyncio.create_task(start_discovery_broadcast())
    except Exception as e:
        logger.warning("Discovery broadcast startup failed (non-fatal): %s", e)

    yield

    if jti_cleanup_task is not None:
        jti_cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await jti_cleanup_task
    if heartbeat_task is not None:
        heartbeat_task.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat_task
    if remote_requests_task is not None:
        remote_requests_task.cancel()
        with suppress(asyncio.CancelledError):
            await remote_requests_task
    if discovery_task is not None:
        discovery_task.cancel()
        with suppress(asyncio.CancelledError):
            await discovery_task

    # Teardown: close asyncpg pool
    try:
        from db.connection import close_pool
        await close_pool()
    except Exception as e:
        logger.warning("Pool close failed (non-fatal): %s", e)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

debug = os.getenv("DEBUG", "false").lower() == "true"
runtime_version = os.getenv("POSVENDELO_VERSION", "2.0.0")
runtime_branch_id = os.getenv("POSVENDELO_BRANCH_ID", "").strip()

app = FastAPI(
    title="POSVENDELO",
    description="API POS Retail",
    version=runtime_version,
    docs_url="/docs" if debug else None,
    redoc_url=None,
    lifespan=lifespan,
)

# Rate limiting (required — app fails at startup if slowapi is not installed)
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from modules.shared.rate_limit import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
origins = _csv_env("CORS_ALLOWED_ORIGINS")
if not origins:
    cors_hosts = _csv_env("POSVENDELO_DEV_ALLOWED_ORIGIN_HOSTS") or ["localhost", "127.0.0.1"]
    cors_ports = _csv_env("POSVENDELO_DEV_ALLOWED_ORIGIN_PORTS") or ["3000", "5173", "5174", "8080"]
    origins = [f"http://{host}:{port}" for host in cors_hosts for port in cors_ports]

# SECURITY: "null" origin removed — it allows sandboxed/file:// pages to bypass CORS.
# Electron must handle CORS at the app layer (e.g., via session.webRequest.onBeforeSendHeaders).

# POS LAN: detectar IP local y agregar orígenes para terminales en red
try:
    import socket
    _lan_ip = socket.gethostbyname(socket.gethostname())
    if not _lan_ip.startswith("127."):
        for _p in _csv_env("POSVENDELO_DEV_ALLOWED_ORIGIN_PORTS") or ["3000", "5173", "5174", "8080"]:
            _o = f"http://{_lan_ip}:{_p}"
            if _o not in origins:
                origins.append(_o)
except Exception as e:
    logger.warning("LAN IP discovery failed (non-fatal): %s", e)

logger.info("CORS allowed origins: %s", origins)

# Wildcard "*" + credentials=True is a browser spec violation — reject it
_use_credentials = "*" not in origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=_use_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Terminal-Id"],
)


# Null-byte sanitizer — pure ASGI middleware to strip \x00 and %00 from
# query strings and request bodies before they reach asyncpg (PG TEXT rejects \x00)
class NullByteSanitizer:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # Sanitize query string (%00 is URL-encoded null, \x00 is raw null)
        qs = scope.get("query_string", b"")
        if b"%00" in qs or b"\x00" in qs:
            scope["query_string"] = qs.replace(b"%00", b"").replace(b"\x00", b"")

        # Wrap receive to sanitize body — strip raw \x00 and JSON \u0000 escapes
        body_done = False

        async def sanitized_receive():
            nonlocal body_done
            if body_done:
                return {"type": "http.disconnect"}
            msg = await receive()
            if msg["type"] == "http.request":
                chunk = msg.get("body", b"")
                if b"\x00" in chunk:
                    chunk = chunk.replace(b"\x00", b"")
                if b"\\u0000" in chunk:
                    chunk = chunk.replace(b"\\u0000", b"")
                msg["body"] = chunk
                if not msg.get("more_body", False):
                    body_done = True
            return msg

        return await self.app(scope, sanitized_receive, send)


app.add_middleware(NullByteSanitizer)


# Security headers middleware
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


app.add_middleware(SecurityHeadersMiddleware)


class LicenseEnforcementMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        from modules.shared.license_state import should_block_request

        blocked, state = should_block_request(request.url.path, request.method)
        if blocked:
            return JSONResponse(
                status_code=402,
                content={
                    "success": False,
                    "detail": state.get("message") or "Licencia vencida o inválida",
                    "data": state,
                },
            )

        response = await call_next(request)
        if state.get("present"):
            response.headers["X-PosVendelo-License-Status"] = str(state.get("effective_status") or "unknown")
        return response


app.add_middleware(LicenseEnforcementMiddleware)

# ---------------------------------------------------------------------------
# Module routers
# ---------------------------------------------------------------------------

from modules.products.routes import router as products_router
from modules.customers.routes import router as customers_router
from modules.sales.routes import router as sales_router
from modules.inventory.routes import router as inventory_router
from modules.turns.routes import router as turns_router
from modules.employees.routes import router as employees_router
from modules.sync.routes import router as sync_router
from modules.auth.routes import router as auth_router
from modules.dashboard.routes import router as dashboard_router
from modules.mermas.routes import router as mermas_router
from modules.expenses.routes import router as expenses_router
from modules.remote.routes import router as remote_router
from modules.sat.routes import router as sat_router
from modules.fiscal.routes import router as fiscal_router
from modules.hardware.routes import router as hardware_router
from modules.shared.license_routes import router as license_router
from modules.system.routes import router as system_router
from modules.cloud.routes import router as cloud_router

app.include_router(products_router, prefix="/api/v1/products", tags=["products"])
app.include_router(customers_router, prefix="/api/v1/customers", tags=["customers"])
app.include_router(sales_router, prefix="/api/v1/sales", tags=["sales"])
app.include_router(inventory_router, prefix="/api/v1/inventory", tags=["inventory"])
app.include_router(turns_router, prefix="/api/v1/turns", tags=["turns"])
app.include_router(employees_router, prefix="/api/v1/employees", tags=["employees"])
app.include_router(sync_router, prefix="/api/v1/sync", tags=["sync"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(mermas_router, prefix="/api/v1/mermas", tags=["mermas"])
app.include_router(expenses_router, prefix="/api/v1/expenses", tags=["expenses"])
app.include_router(remote_router, prefix="/api/v1/remote", tags=["remote"])
app.include_router(sat_router, prefix="/api/v1/sat", tags=["sat"])
app.include_router(fiscal_router, prefix="/api/v1/fiscal", tags=["fiscal"])
app.include_router(hardware_router, prefix="/api/v1/hardware", tags=["hardware"])
app.include_router(license_router, prefix="/api/v1/license", tags=["license"])
app.include_router(system_router, prefix="/api/v1/system", tags=["system"])
app.include_router(cloud_router, prefix="/api/v1/cloud", tags=["cloud"])

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["system"])
async def health_check():
    """Health check for load balancers. Does not log stack traces to avoid leaking internals."""
    try:
        from db.connection import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {
            "success": True,
            "data": {
                "status": "healthy",
                "service": "posvendelo",
                "version": app.version,
                "branch_id": runtime_branch_id or None,
                "os_platform": sys.platform,
            },
        }
    except Exception as e:
        if debug:
            logger.warning("Health check failed: %s", e)
        raise HTTPException(status_code=503, detail="Service unavailable")


# ---------------------------------------------------------------------------
# Terminals endpoint (migrated from mobile_api.py)
# ---------------------------------------------------------------------------

from modules.shared.auth import verify_token
from db.connection import get_db


@app.get("/api/v1/terminals", tags=["system"])
async def get_terminals(
    user: Dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Lista de sucursales/terminales."""
    try:
        branches = await db.fetch(
            "SELECT id, name, code, is_active FROM branches "
            "WHERE is_active = 1 ORDER BY id"
        )
        return {
            "success": True,
            "terminals": [
                {
                    "terminal_id": b["id"],
                    "terminal_name": b["name"],
                    "branch_id": b["id"],
                    "code": b.get("code"),
                    "is_active": bool(b.get("is_active", 1)),
                }
                for b in branches
            ],
        }
    except Exception:
        logger.exception("Error fetching terminals")
        raise HTTPException(status_code=500, detail="Error obteniendo terminales")
