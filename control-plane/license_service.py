import base64
import json
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

logger = logging.getLogger(__name__)

_dev_private_key: rsa.RSAPrivateKey | None = None


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0, tzinfo=None)


def _coerce_datetime(value: Any) -> datetime | None:
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


def _isoformat(value: Any) -> str | None:
    parsed = _coerce_datetime(value)
    return parsed.isoformat() if parsed else None


def _load_private_key() -> rsa.RSAPrivateKey:
    global _dev_private_key

    raw_key = os.getenv("CP_LICENSE_PRIVATE_KEY", "").strip()
    if raw_key:
        return serialization.load_pem_private_key(raw_key.replace("\\n", "\n").encode("utf-8"), password=None)

    if _dev_private_key is None:
        _dev_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        logger.warning(
            "CP_LICENSE_PRIVATE_KEY no configurada; se genero una clave efimera de desarrollo. "
            "Las licencias dejaran de validar despues de reiniciar el control-plane."
        )
    return _dev_private_key


def get_license_public_key_pem() -> str:
    private_key = _load_private_key()
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sign_payload(payload: dict[str, Any]) -> dict[str, Any]:
    private_key = _load_private_key()
    signature = private_key.sign(
        _canonical_bytes(payload),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return {
        "payload": payload,
        "signature": base64.b64encode(signature).decode("ascii"),
        "alg": "RS256",
        "key_id": os.getenv("CP_LICENSE_KEY_ID", "dev-rsa-1").strip() or "dev-rsa-1",
    }


def _status_with_dates(
    *,
    status: str,
    license_type: str,
    valid_until: Any,
    support_until: Any,
    grace_days: int,
) -> str:
    if status == "revoked":
        return "revoked"

    now = _utc_now()
    valid_until_dt = _coerce_datetime(valid_until)
    support_until_dt = _coerce_datetime(support_until)

    if valid_until_dt is not None:
        if now <= valid_until_dt:
            return "active"
        if license_type == "monthly" and grace_days > 0 and now <= valid_until_dt + timedelta(days=grace_days):
            return "grace"
        return "expired"

    if support_until_dt is not None and now > support_until_dt:
        return "support_expired"

    return "active"


def build_signed_license(
    tenant_license: dict[str, Any],
    branch: dict[str, Any],
    *,
    machine_id: str | None,
) -> dict[str, Any]:
    grace_days = int(tenant_license.get("grace_days") or 0)
    effective_status = _status_with_dates(
        status=str(tenant_license.get("status") or "active"),
        license_type=str(tenant_license.get("license_type") or "trial"),
        valid_until=tenant_license.get("valid_until"),
        support_until=tenant_license.get("support_until"),
        grace_days=grace_days,
    )
    payload = {
        "schema_version": 1,
        "issued_at": _utc_now().isoformat(),
        "license_id": tenant_license["id"],
        "tenant_id": branch["tenant_id"],
        "branch_id": branch["id"],
        "branch_slug": branch.get("branch_slug"),
        "tenant_slug": branch.get("tenant_slug"),
        "install_token": branch.get("install_token"),
        "machine_id": machine_id or branch.get("machine_id"),
        "license_type": tenant_license["license_type"],
        "status": str(tenant_license.get("status") or "active"),
        "effective_status": effective_status,
        "valid_from": _isoformat(tenant_license.get("valid_from")),
        "valid_until": _isoformat(tenant_license.get("valid_until")),
        "support_until": _isoformat(tenant_license.get("support_until")),
        "grace_days": grace_days,
        "trial_started_at": _isoformat(tenant_license.get("trial_started_at")),
        "trial_expires_at": _isoformat(tenant_license.get("trial_expires_at")),
        "max_branches": tenant_license.get("max_branches"),
        "max_devices": tenant_license.get("max_devices"),
        "features": tenant_license.get("features") or {},
        "metadata": {
            "release_channel": branch.get("release_channel"),
            "os_platform": branch.get("os_platform"),
        },
    }
    envelope = sign_payload(payload)
    envelope["public_key"] = get_license_public_key_pem()
    return envelope


async def ensure_trial_license(db, *, tenant_id: int) -> dict[str, Any]:
    existing = await db.fetchrow(
        """
        SELECT *
        FROM tenant_licenses
        WHERE tenant_id = :tenant_id
        ORDER BY created_at DESC
        LIMIT 1
        """,
        {"tenant_id": tenant_id},
    )
    if existing:
        return existing

    trial_days = max(1, int(os.getenv("CP_TRIAL_DAYS", "90")))
    now = _utc_now()
    expires_at = now + timedelta(days=trial_days)
    return await db.fetchrow(
        """
        INSERT INTO tenant_licenses (
            tenant_id,
            license_type,
            status,
            valid_from,
            valid_until,
            support_until,
            trial_started_at,
            trial_expires_at,
            grace_days,
            max_branches,
            max_devices,
            features,
            signature_version
        )
        VALUES (
            :tenant_id,
            'trial',
            'active',
            :valid_from,
            :valid_until,
            :support_until,
            :trial_started_at,
            :trial_expires_at,
            0,
            1,
            1,
            :features::jsonb,
            1
        )
        RETURNING *
        """,
        {
            "tenant_id": tenant_id,
            "valid_from": now.isoformat(),
            "valid_until": expires_at.isoformat(),
            "support_until": expires_at.isoformat(),
            "trial_started_at": now.isoformat(),
            "trial_expires_at": expires_at.isoformat(),
            "features": json.dumps({"plan_label": "trial-90"}, ensure_ascii=True),
        },
    )


async def get_current_license(db, *, tenant_id: int) -> dict[str, Any]:
    row = await db.fetchrow(
        """
        SELECT *
        FROM tenant_licenses
        WHERE tenant_id = :tenant_id
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        {"tenant_id": tenant_id},
    )
    if row:
        return row
    return await ensure_trial_license(db, tenant_id=tenant_id)


async def upsert_activation(
    db,
    *,
    license_id: int,
    tenant_id: int,
    branch_id: int,
    machine_id: str | None,
    os_platform: str | None,
    app_version: str | None,
    pos_version: str | None,
    install_token: str | None,
) -> dict[str, Any] | None:
    if not machine_id:
        return None
    return await db.fetchrow(
        """
        INSERT INTO license_activations (
            license_id,
            tenant_id,
            branch_id,
            install_token,
            machine_id,
            os_platform,
            app_version,
            pos_version,
            status,
            first_seen_at,
            last_seen_at
        )
        VALUES (
            :license_id,
            :tenant_id,
            :branch_id,
            :install_token,
            :machine_id,
            :os_platform,
            :app_version,
            :pos_version,
            'active',
            NOW(),
            NOW()
        )
        ON CONFLICT (license_id, branch_id, machine_id)
        DO UPDATE SET
            os_platform = EXCLUDED.os_platform,
            app_version = EXCLUDED.app_version,
            pos_version = EXCLUDED.pos_version,
            status = 'active',
            last_seen_at = NOW()
        RETURNING *
        """,
        {
            "license_id": license_id,
            "tenant_id": tenant_id,
            "branch_id": branch_id,
            "install_token": install_token,
            "machine_id": machine_id,
            "os_platform": os_platform,
            "app_version": app_version,
            "pos_version": pos_version,
        },
    )


async def append_license_event(
    db,
    *,
    license_id: int,
    event_type: str,
    actor: str,
    payload: dict[str, Any] | None = None,
) -> None:
    await db.execute(
        """
        INSERT INTO license_events (license_id, event_type, actor, payload)
        VALUES (:license_id, :event_type, :actor, :payload::jsonb)
        """,
        {
            "license_id": license_id,
            "event_type": event_type,
            "actor": actor,
            "payload": json.dumps(payload or {}, ensure_ascii=True),
        },
    )
