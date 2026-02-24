"""
Request policies for centralized server-only operation.

Enforces:
- single-writer semantics through server API
- terminal_id presence for write operations
- idempotency keys for critical writes
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import Header, HTTPException

DATA_DIR = Path("./gateway_data")
DATA_DIR.mkdir(exist_ok=True)
IDEMPOTENCY_FILE = DATA_DIR / "idempotency_keys.json"
_idempotency_lock = threading.Lock()


def enforce_write_role(auth: dict) -> None:
    """
    Ensure caller is an authenticated server-side actor.
    Both admin and branch roles are allowed to write through API.
    """
    role = (auth or {}).get("role")
    if role not in {"admin", "branch"}:
        raise HTTPException(status_code=403, detail="Write operation not allowed for role")


def require_terminal_id(body_terminal_id: Optional[int], header_terminal_id: Optional[int]) -> int:
    """
    Return a valid terminal_id from body/header, fail if missing/invalid.
    """
    terminal_id = body_terminal_id if body_terminal_id is not None else header_terminal_id
    # #region agent log
    try:
        with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "5e74cc",
                "runId": "pre-fix",
                "hypothesisId": "H1_terminal_id_missing",
                "location": "server/request_policies.py:require_terminal_id",
                "message": "Evaluating terminal_id for write request",
                "data": {"body_terminal_id": body_terminal_id, "header_terminal_id": header_terminal_id},
                "timestamp": int(datetime.now().timestamp() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    if terminal_id is None:
        raise HTTPException(status_code=422, detail="terminal_id is required for write operations")
    if int(terminal_id) <= 0:
        raise HTTPException(status_code=422, detail="terminal_id must be a positive integer")
    return int(terminal_id)


def _load_idempotency_store() -> dict:
    if IDEMPOTENCY_FILE.exists():
        try:
            return json.loads(IDEMPOTENCY_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_idempotency_store(store: dict) -> None:
    IDEMPOTENCY_FILE.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")


def check_and_record_idempotency(key: Optional[str], route: str, terminal_id: int) -> bool:
    """
    Returns True if the request is duplicate, False if newly recorded.
    """
    if not key:
        # #region agent log
        try:
            with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "sessionId": "5e74cc",
                    "runId": "pre-fix",
                    "hypothesisId": "H2_missing_idempotency_key",
                    "location": "server/request_policies.py:check_and_record_idempotency",
                    "message": "No idempotency key provided",
                    "data": {"route": route, "terminal_id": terminal_id},
                    "timestamp": int(datetime.now().timestamp() * 1000),
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass
        # #endregion
        return False

    scoped_key = f"{route}:{terminal_id}:{key}"
    with _idempotency_lock:
        store = _load_idempotency_store()
        if scoped_key in store:
            # #region agent log
            try:
                with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "5e74cc",
                        "runId": "pre-fix",
                        "hypothesisId": "H3_idempotency_duplicate",
                        "location": "server/request_policies.py:check_and_record_idempotency",
                        "message": "Duplicate idempotency key detected",
                        "data": {"route": route, "terminal_id": terminal_id},
                        "timestamp": int(datetime.now().timestamp() * 1000),
                    }, ensure_ascii=False) + "\n")
            except Exception:
                pass
            # #endregion
            return True
        store[scoped_key] = {"recorded_at": datetime.now().isoformat()}
        _save_idempotency_store(store)
    # #region agent log
    try:
        with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "5e74cc",
                "runId": "pre-fix",
                "hypothesisId": "H3_idempotency_duplicate",
                "location": "server/request_policies.py:check_and_record_idempotency",
                "message": "Idempotency key recorded",
                "data": {"route": route, "terminal_id": terminal_id},
                "timestamp": int(datetime.now().timestamp() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    return False


def idempotency_header(
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
) -> Optional[str]:
    return x_idempotency_key


def terminal_header(
    x_terminal_id: Optional[int] = Header(default=None, alias="X-Terminal-Id"),
) -> Optional[int]:
    return x_terminal_id

