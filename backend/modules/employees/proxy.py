"""
TITAN POS - Employees Strangler Fig Proxy

Routes employee API requests to either:
  - The employees microservice (localhost:8001) when EMPLOYEES_MICROSERVICE=true
  - Local engine logic (LoanEngine/TimeClockEngine) when flag is off or microservice is down

Usage:
    from modules.employees.proxy import employees_proxy_router
    app.include_router(employees_proxy_router, prefix="/api/v1/employees", tags=["employees"])
"""

import os
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

employees_proxy_router = APIRouter()

# Feature flag
EMPLOYEES_MICROSERVICE = os.getenv("EMPLOYEES_MICROSERVICE", "false").lower() == "true"
EMPLOYEES_SVC_URL = os.getenv("EMPLOYEES_SVC_URL", "http://localhost:8001")

# Reusable async HTTP client (connection pooling)
_http_client: Optional[httpx.AsyncClient] = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            base_url=EMPLOYEES_SVC_URL,
            timeout=httpx.Timeout(5.0, connect=2.0),
        )
    return _http_client


async def _proxy_to_microservice(
    method: str,
    path: str,
    params: Optional[dict] = None,
    json_body: Optional[dict] = None,
) -> Optional[dict]:
    """
    Proxy a request to the employees microservice.
    Returns the JSON response or None if microservice is unavailable.
    """
    if not EMPLOYEES_MICROSERVICE:
        return None

    client = _get_http_client()
    url = f"/api/v1/employees{path}"

    try:
        response = await client.request(
            method=method,
            url=url,
            params=params,
            json=json_body,
        )
        response.raise_for_status()
        return response.json()
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.warning(
            f"Employees microservice unavailable ({e.__class__.__name__}), "
            f"falling back to local logic"
        )
        return None
    except httpx.HTTPStatusError as e:
        # Propagate HTTP errors from microservice (404, 400, etc.)
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.json().get("detail", str(e)),
        )


# ---------------------------------------------------------------------------
# Local fallback — lazy import to avoid circular deps when microservice is ON
# ---------------------------------------------------------------------------

def _get_local_db():
    """Get the monolith's database instance for local fallback."""
    from src.infra.database import db_instance
    return db_instance


def _get_loan_engine():
    from src.core.loan_engine import LoanEngine
    return LoanEngine(_get_local_db())


def _get_time_clock_engine():
    from src.core.time_clock_engine import TimeClockEngine
    return TimeClockEngine(_get_local_db())


# ============================================================================
# Employee CRUD
# ============================================================================

@employees_proxy_router.get("/")
async def list_employees(
    search: Optional[str] = None,
    is_active: Optional[int] = Query(1, ge=0, le=1),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List employees — proxies to microservice or falls back to local DB."""
    result = await _proxy_to_microservice(
        "GET", "/",
        params={"search": search, "is_active": is_active, "limit": limit, "offset": offset},
    )
    if result is not None:
        return result

    # Local fallback
    db = _get_local_db()
    sql = "SELECT * FROM employees WHERE 1=1"
    params_list = []

    if is_active is not None:
        sql += " AND is_active = ?"
        params_list.append(is_active)
    if search:
        sql += " AND (name LIKE ? OR phone LIKE ? OR email LIKE ?)"
        params_list.extend([f"%{search}%"] * 3)

    sql += " ORDER BY name LIMIT ? OFFSET ?"
    params_list.extend([limit, offset])

    rows = db.execute_query(sql, tuple(params_list))
    return {"success": True, "data": [dict(r) for r in rows]}


@employees_proxy_router.get("/{employee_id}")
async def get_employee(employee_id: int):
    """Get employee by ID."""
    result = await _proxy_to_microservice("GET", f"/{employee_id}")
    if result is not None:
        return result

    db = _get_local_db()
    rows = db.execute_query("SELECT * FROM employees WHERE id = ?", (employee_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    return {"success": True, "data": dict(rows[0])}


@employees_proxy_router.post("/")
async def create_employee(request: Request):
    """Create a new employee."""
    body = await request.json()

    result = await _proxy_to_microservice("POST", "/", json_body=body)
    if result is not None:
        return result

    # Local fallback via LoanEngine
    engine = _get_loan_engine()
    emp_id = engine.create_employee(
        name=body.get("name", ""),
        position=body.get("role", "cajero"),
        phone=body.get("phone", ""),
        email=body.get("email", ""),
        base_salary=body.get("salary", 0.0),
    )
    return {"success": True, "data": {"id": emp_id}}


@employees_proxy_router.put("/{employee_id}")
async def update_employee(employee_id: int, request: Request):
    """Update an existing employee."""
    body = await request.json()

    result = await _proxy_to_microservice("PUT", f"/{employee_id}", json_body=body)
    if result is not None:
        return result

    # Local fallback
    db = _get_local_db()
    update_data = {k: v for k, v in body.items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    set_clause = ", ".join([f"{k} = ?" for k in update_data.keys()])
    values = list(update_data.values()) + [employee_id]

    rowcount = db.execute_update(
        f"UPDATE employees SET {set_clause} WHERE id = ?",
        tuple(values),
    )
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    return {"success": True, "data": {"updated": True}}


@employees_proxy_router.delete("/{employee_id}")
async def delete_employee(employee_id: int):
    """Soft delete an employee."""
    result = await _proxy_to_microservice("DELETE", f"/{employee_id}")
    if result is not None:
        return result

    db = _get_local_db()
    rowcount = db.execute_update(
        "UPDATE employees SET is_active = 0 WHERE id = ?",
        (employee_id,),
    )
    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")
    return {"success": True, "data": {"deleted": True}}


# ============================================================================
# Time Clock
# ============================================================================

@employees_proxy_router.post("/time-clock")
async def clock_action(request: Request):
    """Register a time clock action."""
    body = await request.json()

    result = await _proxy_to_microservice("POST", "/time-clock", json_body=body)
    if result is not None:
        return result

    # Local fallback
    engine = _get_time_clock_engine()
    action = body.get("action", "clock_in")
    employee_id = body.get("employee_id")

    if action == "clock_in":
        entry = engine.clock_in(employee_id, notes=body.get("notes"))
    elif action == "clock_out":
        entry = engine.clock_out(employee_id, notes=body.get("notes"))
    elif action == "break_start":
        entry = engine.start_break(employee_id, notes=body.get("notes"))
    elif action == "break_end":
        entry = engine.end_break(employee_id, notes=body.get("notes"))
    else:
        raise HTTPException(status_code=400, detail=f"Acción inválida: {action}")

    return {"success": True, "data": entry}


@employees_proxy_router.get("/{employee_id}/time-clock")
async def get_time_clock_entries(
    employee_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
):
    """Get time clock entries for an employee."""
    params = {"start_date": start_date, "end_date": end_date, "limit": limit}
    result = await _proxy_to_microservice("GET", f"/{employee_id}/time-clock", params=params)
    if result is not None:
        return result

    # Local fallback
    engine = _get_time_clock_engine()
    entries = engine.get_attendance_history(employee_id, limit=limit)
    return {"success": True, "data": entries}


# ============================================================================
# Loans
# ============================================================================

@employees_proxy_router.post("/loans")
async def create_loan(request: Request):
    """Create a new employee loan."""
    body = await request.json()

    result = await _proxy_to_microservice("POST", "/loans", json_body=body)
    if result is not None:
        return result

    # Local fallback
    engine = _get_loan_engine()
    loan_id = engine.create_loan(
        employee_id=body["employee_id"],
        amount=body["amount"],
        installments=body.get("installments", 12),
        reason=body.get("reason", "Préstamo personal"),
    )
    return {"success": True, "data": {"id": loan_id}}


@employees_proxy_router.get("/{employee_id}/loans")
async def get_employee_loans(
    employee_id: int,
    status: Optional[str] = "active",
):
    """Get loans for an employee."""
    result = await _proxy_to_microservice(
        "GET", f"/{employee_id}/loans", params={"status": status}
    )
    if result is not None:
        return result

    # Local fallback
    engine = _get_loan_engine()
    loans = engine.get_employee_loans(employee_id)
    if status and status != "all":
        loans = [l for l in loans if l.get("status") == status]
    return {"success": True, "data": loans}


@employees_proxy_router.post("/loans/payment")
async def make_loan_payment(request: Request):
    """Make a payment on an employee loan."""
    body = await request.json()

    result = await _proxy_to_microservice("POST", "/loans/payment", json_body=body)
    if result is not None:
        return result

    # Local fallback
    engine = _get_loan_engine()
    payment = engine.make_payment(
        loan_id=body["loan_id"],
        amount=body["amount"],
    )
    return {"success": True, "data": payment}
