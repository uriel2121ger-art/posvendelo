import json
import sys
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
SERVER_DIR = ROOT / "server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SERVER_DIR))

from request_policies import require_terminal_id, check_and_record_idempotency  # noqa: E402
from app.utils.network_client import MultiCajaClient  # noqa: E402
from titan_gateway import app  # noqa: E402


def _write_gateway_auth_files():
    data_dir = SERVER_DIR / "gateway_data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "config.json").write_text(
        json.dumps(
            {
                "admin_token": "admintoken_test_12345678901234567890",
                "branches": {"1": {"name": "Sucursal 1"}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (data_dir / "tokens.json").write_text(
        json.dumps({"1": "branchtoken_test_12345678901234567890"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@pytest.fixture(scope="module")
def test_client():
    _write_gateway_auth_files()
    return TestClient(app)


def test_terminal_id_validation():
    with pytest.raises(HTTPException) as e1:
        require_terminal_id(None, None)
    assert e1.value.status_code == 422

    with pytest.raises(HTTPException) as e2:
        require_terminal_id(0, None)
    assert e2.value.status_code == 422

    assert require_terminal_id(1, None) == 1


def test_idempotency_duplicate_detection():
    key = f"pytest-dup-key-{uuid.uuid4().hex}"
    first = check_and_record_idempotency(key, "/pytest/write", 1)
    second = check_and_record_idempotency(key, "/pytest/write", 1)
    assert first is False
    assert second is True


def test_idempotency_without_key_is_not_duplicate():
    result = check_and_record_idempotency(None, "/pytest/write", 1)
    assert result is False


def test_connectivity_gate_blocks_write_when_server_unreachable():
    mc = MultiCajaClient("http://127.0.0.1:65534", token="dummy", terminal_id=99)
    ok, message, _data = mc.sync_table("products", [{"id": 1, "sku": "X"}])
    assert ok is False
    assert "solo lectura" in message.lower()


def test_backup_upload_is_blocked_for_server_only_policy(test_client):
    headers = {"Authorization": "Bearer admintoken_test_12345678901234567890"}
    response = test_client.post(
        "/api/backup/upload?branch_id=1",
        headers=headers,
        files={"file": ("a.txt", b"abc", "text/plain")},
    )
    assert response.status_code == 403
    assert "server-only" in response.json()["detail"].lower()

