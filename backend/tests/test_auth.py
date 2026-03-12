"""Tests for auth module: login + verify + RBAC."""

import jwt as pyjwt
import pytest
from datetime import datetime, timedelta, timezone

from modules.shared.auth import SECRET_KEY, ALGORITHM, create_token
from conftest import auth_header, ADMIN_ID, CASHIER_ID


class TestLogin:
    async def test_login_success(self, client, seed_users):
        r = await client.post(
            "/api/v1/auth/login",
            json={"username": "test_admin_90001", "password": "test1234"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
        assert data["branch_id"] is not None

    async def test_login_wrong_password(self, client, seed_users):
        r = await client.post(
            "/api/v1/auth/login",
            json={"username": "test_admin_90001", "password": "WRONG"},
        )
        assert r.status_code == 401

    async def test_login_nonexistent_user(self, client, seed_users):
        r = await client.post(
            "/api/v1/auth/login",
            json={"username": "ghost_user_xyz", "password": "test1234"},
        )
        assert r.status_code == 401

    async def test_login_inactive_user(self, client, db_conn, seed_users):
        await db_conn.execute(
            "UPDATE users SET is_active = 0 WHERE id = $1", ADMIN_ID
        )
        r = await client.post(
            "/api/v1/auth/login",
            json={"username": "test_admin_90001", "password": "test1234"},
        )
        assert r.status_code == 401

    async def test_login_empty_body(self, client):
        r = await client.post("/api/v1/auth/login", json={})
        assert r.status_code == 422

    async def test_login_short_password(self, client):
        r = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "ab"},
        )
        assert r.status_code == 422  # min_length=4


class TestVerify:
    async def test_verify_valid_token(self, client, admin_token):
        r = await client.get(
            "/api/v1/auth/verify", headers=auth_header(admin_token)
        )
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["data"]["valid"] is True
        assert data["data"]["user"] == str(ADMIN_ID)
        assert data["data"]["role"] == "admin"
        assert data["data"]["branch_id"] is not None

    async def test_verify_expired_token(self, client):
        payload = {
            "sub": str(ADMIN_ID),
            "role": "admin",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "nbf": datetime.now(timezone.utc) - timedelta(hours=2),
            "jti": "expired-test",
        }
        token = pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        r = await client.get(
            "/api/v1/auth/verify", headers=auth_header(token)
        )
        assert r.status_code == 401

    async def test_verify_invalid_token(self, client):
        r = await client.get(
            "/api/v1/auth/verify",
            headers=auth_header("not.a.valid.jwt"),
        )
        assert r.status_code == 401

    async def test_verify_missing_claims(self, client):
        payload = {
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        r = await client.get(
            "/api/v1/auth/verify", headers=auth_header(token)
        )
        assert r.status_code == 401

    async def test_verify_no_auth_header(self, client):
        r = await client.get("/api/v1/auth/verify")
        assert r.status_code == 401


class TestDevicePairing:
    async def test_pair_token_create_and_pair_device(self, client, admin_token, seed_users):
        token_response = await client.post(
            "/api/v1/auth/pair-token",
            headers=auth_header(admin_token),
            json={"branch_id": 90001, "terminal_id": 3, "device_label": "Tablet pasillo"},
        )
        assert token_response.status_code == 200
        pairing_token = token_response.json()["data"]["pairing_token"]

        pair_response = await client.post(
            "/api/v1/auth/pair",
            headers=auth_header(admin_token),
            json={
                "pairing_token": pairing_token,
                "device_id": "device-xyz",
                "device_name": "Moto G",
                "platform": "android",
                "app_version": "1.0.0",
                "hardware_fingerprint": "abc123",
            },
        )
        assert pair_response.status_code == 200
        data = pair_response.json()["data"]
        assert data["branch_id"] == 90001
        assert data["terminal_id"] == 3

        used_again = await client.post(
            "/api/v1/auth/pair",
            headers=auth_header(admin_token),
            json={"pairing_token": pairing_token, "device_id": "device-xyz"},
        )
        assert used_again.status_code == 409

    async def test_pair_qr_payload(self, client, admin_token, seed_users):
        response = await client.get(
            "/api/v1/auth/pair-qr?branch_id=90001&terminal_id=4",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["branch_id"] == 90001
        assert data["terminal_id"] == 4
        assert data["pairing_token"]

    async def test_list_and_revoke_devices(self, client, admin_token, seed_users):
        token_response = await client.post(
            "/api/v1/auth/pair-token",
            headers=auth_header(admin_token),
            json={"branch_id": 90001, "terminal_id": 1},
        )
        pairing_token = token_response.json()["data"]["pairing_token"]
        paired = await client.post(
            "/api/v1/auth/pair",
            headers=auth_header(admin_token),
            json={"pairing_token": pairing_token, "device_id": "device-revoke"},
        )
        pairing_id = paired.json()["data"]["pairing_id"]

        listed = await client.get("/api/v1/auth/devices", headers=auth_header(admin_token))
        assert listed.status_code == 200
        assert any(item["id"] == pairing_id for item in listed.json()["data"])

        revoked = await client.delete(f"/api/v1/auth/devices/{pairing_id}", headers=auth_header(admin_token))
        assert revoked.status_code == 200
