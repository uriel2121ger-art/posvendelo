import base64
import json
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from modules.shared.license_state import get_license_state, should_block_request


def _write_license_file(tmp_path, *, license_type: str, valid_until: datetime | None, grace_days: int = 0):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    payload = {
        "license_type": license_type,
        "status": "active",
        "effective_status": "active",
        "tenant_id": 1,
        "branch_id": 1,
        "machine_id": "demo-machine",
        "valid_until": valid_until.isoformat() if valid_until else None,
        "support_until": (valid_until.isoformat() if valid_until else None),
        "grace_days": grace_days,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    signature = private_key.sign(canonical, padding.PKCS1v15(), hashes.SHA256())
    agent_path = tmp_path / "posvendelo-agent.json"
    agent_path.write_text(
        json.dumps(
            {
                "license": {
                    "payload": payload,
                    "signature": base64.b64encode(signature).decode("ascii"),
                    "public_key": public_key,
                }
            }
        ),
        encoding="utf-8",
    )
    return agent_path


def test_get_license_state_active(tmp_path, monkeypatch) -> None:
    agent_path = _write_license_file(
        tmp_path,
        license_type="trial",
        valid_until=datetime.now(UTC).replace(microsecond=0, tzinfo=None) + timedelta(days=30),
    )
    monkeypatch.setenv("POSVENDELO_AGENT_CONFIG_PATH", str(agent_path))
    monkeypatch.setenv("POSVENDELO_LICENSE_ENFORCEMENT", "true")

    state = get_license_state()

    assert state["present"] is True
    assert state["valid_signature"] is True
    assert state["effective_status"] == "active"
    assert state["operation_mode"] == "allow"


def test_should_block_request_for_expired_monthly_write(tmp_path, monkeypatch) -> None:
    agent_path = _write_license_file(
        tmp_path,
        license_type="monthly",
        valid_until=datetime.now(UTC).replace(microsecond=0, tzinfo=None) - timedelta(days=10),
        grace_days=3,
    )
    monkeypatch.setenv("POSVENDELO_AGENT_CONFIG_PATH", str(agent_path))
    monkeypatch.setenv("POSVENDELO_LICENSE_ENFORCEMENT", "true")

    blocked, state = should_block_request("/api/v1/sales", "POST")

    assert blocked is True
    assert state["effective_status"] == "expired"
    assert state["operation_mode"] == "restricted"
