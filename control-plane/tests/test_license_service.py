from datetime import UTC, datetime, timedelta

from license_service import build_signed_license, get_license_public_key_pem


def test_build_signed_license_includes_public_key_and_status() -> None:
    now = datetime.now(UTC).replace(microsecond=0, tzinfo=None)
    tenant_license = {
        "id": 7,
        "license_type": "trial",
        "status": "active",
        "valid_from": now,
        "valid_until": now + timedelta(days=90),
        "support_until": now + timedelta(days=90),
        "trial_started_at": now,
        "trial_expires_at": now + timedelta(days=90),
        "grace_days": 0,
        "max_branches": 1,
        "max_devices": 1,
        "features": {"plan_label": "trial-90"},
    }
    branch = {
        "id": 11,
        "tenant_id": 3,
        "branch_slug": "main",
        "tenant_slug": "demo",
        "install_token": "tok-demo",
        "release_channel": "stable",
        "os_platform": "linux",
    }

    envelope = build_signed_license(tenant_license, branch, machine_id="machine-1")

    assert envelope["alg"] == "RS256"
    assert envelope["public_key"] == get_license_public_key_pem()
    assert envelope["payload"]["effective_status"] == "active"
    assert envelope["payload"]["branch_id"] == 11
    assert envelope["payload"]["machine_id"] == "machine-1"
