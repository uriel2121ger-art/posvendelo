import base64
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

_CACHE: dict[str, Any] = {"path": None, "mtime": None, "state": None}


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0, tzinfo=None)


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(microsecond=0, tzinfo=None)
    if isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(tz=None).replace(tzinfo=None)
        return parsed.replace(microsecond=0)
    return None


def _days_remaining(target: datetime | None) -> int | None:
    if target is None:
        return None
    delta = target - _utc_now()
    return int(delta.total_seconds() // 86400)


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _load_blob() -> tuple[dict[str, Any] | None, str | None]:
    raw_blob = os.getenv("POSVENDELO_LICENSE_BLOB", "").strip()
    if raw_blob:
        try:
            return json.loads(raw_blob), None
        except json.JSONDecodeError:
            return None, "POSVENDELO_LICENSE_BLOB inválido"

    _config_path_raw = os.getenv("POSVENDELO_AGENT_CONFIG_PATH", "/runtime/posvendelo-agent.json").strip()
    config_path = Path(_config_path_raw)
    if not config_path.exists() or not config_path.is_file():
        return None, "Archivo posvendelo-agent.json no encontrado"
    try:
        override_path = Path(os.getenv("POSVENDELO_LICENSE_FILE_PATH", str(config_path.with_name("posvendelo-license.json"))))
        if override_path.exists():
            return json.loads(override_path.read_text(encoding="utf-8")), None
        stat = config_path.stat()
        if (
            _CACHE["path"] == str(config_path)
            and _CACHE["mtime"] == stat.st_mtime
            and _CACHE["state"] is not None
        ):
            return _CACHE["state"], None
        data = json.loads(config_path.read_text(encoding="utf-8"))
        blob = data.get("license")
        if isinstance(blob, dict):
            _CACHE["path"] = str(config_path)
            _CACHE["mtime"] = stat.st_mtime
            _CACHE["state"] = blob
            return blob, None
        return None, "Licencia no encontrada en posvendelo-agent.json"
    except Exception as exc:
        return None, str(exc)


def _verify_signature(blob: dict[str, Any]) -> tuple[bool, str | None]:
    payload = blob.get("payload")
    signature = blob.get("signature")
    public_key_pem = blob.get("public_key") or os.getenv("POSVENDELO_LICENSE_PUBLIC_KEY", "").strip()
    if not isinstance(payload, dict):
        return False, "Payload de licencia inválido"
    if not isinstance(signature, str) or not signature.strip():
        return False, "Firma de licencia ausente"
    if not isinstance(public_key_pem, str) or not public_key_pem.strip():
        return False, "Clave pública de licencia ausente"
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        public_key.verify(
            base64.b64decode(signature),
            _canonical_bytes(payload),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True, None
    except (ValueError, TypeError, InvalidSignature) as exc:
        return False, f"Firma inválida: {exc}"


def _effective_status(payload: dict[str, Any]) -> str:
    base_status = str(payload.get("status") or "active")
    if base_status == "revoked":
        return "revoked"

    license_type = str(payload.get("license_type") or "trial")
    valid_until = _parse_dt(payload.get("valid_until"))
    support_until = _parse_dt(payload.get("support_until"))
    grace_days = int(payload.get("grace_days") or 0)
    now = _utc_now()

    if valid_until is not None:
        if now <= valid_until:
            return "active"
        if license_type == "monthly" and grace_days > 0 and now <= valid_until + timedelta(days=grace_days):
            return "grace"
        return "expired"

    if support_until is not None and now > support_until:
        return "support_expired"

    return base_status if base_status in {"active", "grace", "expired"} else "active"


def get_license_state() -> dict[str, Any]:
    blob, error = _load_blob()
    if blob is None:
        return {
            "present": False,
            "valid_signature": False,
            "enforcement_enabled": license_enforcement_enabled(),
            "effective_status": "missing",
            "operation_mode": "allow" if not license_enforcement_enabled() else "restricted",
            "message": error or "Licencia no configurada",
        }

    valid_signature, signature_error = _verify_signature(blob)
    payload = blob.get("payload") if isinstance(blob.get("payload"), dict) else {}
    effective_status = _effective_status(payload)
    valid_until = _parse_dt(payload.get("valid_until"))
    support_until = _parse_dt(payload.get("support_until"))
    license_type = str(payload.get("license_type") or "trial")
    operation_mode = "allow"
    if not valid_signature:
        operation_mode = "restricted" if license_enforcement_enabled() else "allow"
    elif effective_status in {"revoked", "expired"} and license_type in {"trial", "monthly"}:
        operation_mode = "restricted"
    elif effective_status == "grace":
        operation_mode = "grace"
    elif effective_status == "support_expired":
        operation_mode = "support_expired"

    return {
        "present": True,
        "valid_signature": valid_signature,
        "enforcement_enabled": license_enforcement_enabled(),
        "license_type": license_type,
        "effective_status": effective_status,
        "status": payload.get("status"),
        "operation_mode": operation_mode,
        "message": signature_error or _build_message(license_type, effective_status, valid_until, support_until),
        "valid_until": valid_until.isoformat() if valid_until else None,
        "support_until": support_until.isoformat() if support_until else None,
        "days_remaining": _days_remaining(valid_until),
        "support_days_remaining": _days_remaining(support_until),
        "branch_id": payload.get("branch_id"),
        "tenant_id": payload.get("tenant_id"),
        "machine_id": payload.get("machine_id"),
        "payload": payload,
    }


def _build_message(
    license_type: str,
    effective_status: str,
    valid_until: datetime | None,
    support_until: datetime | None,
) -> str:
    if effective_status == "grace":
        return "Licencia mensual en gracia. Renueva para evitar bloqueo comercial."
    if effective_status == "expired" and license_type == "monthly":
        return "Licencia mensual vencida. Operación comercial restringida."
    if effective_status == "expired" and license_type == "trial":
        return "Periodo de prueba vencido. Activa una licencia para continuar operando."
    if effective_status == "support_expired":
        support_label = support_until.date().isoformat() if support_until else "fecha no disponible"
        return f"Soporte vencido desde {support_label}. El sistema sigue operando sin updates."
    if effective_status == "active" and valid_until:
        return f"Licencia activa hasta {valid_until.date().isoformat()}."
    return "Licencia operativa."


def license_enforcement_enabled() -> bool:
    return os.getenv("POSVENDELO_LICENSE_ENFORCEMENT", "false").strip().lower() in {"1", "true", "yes", "on"}


def should_block_request(path: str, method: str) -> tuple[bool, dict[str, Any]]:
    state = get_license_state()
    if not state["enforcement_enabled"]:
        return False, state

    exempt_paths = {
        "/health",
        "/api/v1/auth/login",
        "/api/v1/auth/verify",
        "/api/v1/license/status",
        "/docs",
        "/openapi.json",
    }
    if path in exempt_paths or path.startswith("/docs"):
        return False, state

    if not state["valid_signature"]:
        return True, state

    if state["operation_mode"] == "restricted":
        return method.upper() not in {"GET", "HEAD", "OPTIONS"}, state

    return False, state
