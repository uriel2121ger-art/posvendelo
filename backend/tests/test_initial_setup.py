"""Tests for first-run setup wizard persistence and first-user setup flow."""

import json

from conftest import auth_header


class TestInitialSetupWizard:
    async def test_setup_status_incomplete_when_no_marker(self, client, db_conn, admin_token, seed_users):
        await db_conn.execute(
            "UPDATE app_config SET business_name = '', receipt_printer_name = '' WHERE key = 'hardware'"
        )
        await db_conn.execute("DELETE FROM app_config WHERE key = 'initial_setup'")

        response = await client.get('/api/v1/hardware/setup-status', headers=auth_header(admin_token))

        assert response.status_code == 200
        body = response.json()
        assert body['success'] is True
        assert body['data']['completed'] is False

    async def test_setup_wizard_persists_and_reflects_in_config(
        self, client, db_conn, admin_token, seed_users
    ):
        await db_conn.execute("DELETE FROM app_config WHERE key = 'initial_setup'")

        payload = {
            'business_name': 'Mi Tienda Wizard',
            'business_legal_name': 'Mi Tienda Wizard SA de CV',
            'business_address': 'Av Siempre Viva 123',
            'business_rfc': 'XAXX010101000',
            'business_phone': '5512345678',
            'business_footer': 'Vuelve pronto',
            'receipt_printer_name': 'POS-80',
            'receipt_printer_enabled': True,
            'receipt_auto_print': True,
            'scanner_enabled': True,
            'cash_drawer_enabled': True,
        }

        save = await client.post(
            '/api/v1/hardware/setup-wizard',
            headers=auth_header(admin_token),
            json=payload,
        )
        assert save.status_code == 200
        assert save.json()['success'] is True

        cfg = await client.get('/api/v1/hardware/config', headers=auth_header(admin_token))
        assert cfg.status_code == 200
        cfg_data = cfg.json()['data']
        assert cfg_data['business']['name'] == 'Mi Tienda Wizard'
        assert cfg_data['business']['legal_name'] == 'Mi Tienda Wizard SA de CV'
        assert cfg_data['business']['address'] == 'Av Siempre Viva 123'
        assert cfg_data['business']['rfc'] == 'XAXX010101000'
        assert cfg_data['business']['phone'] == '5512345678'
        assert cfg_data['business']['footer'] == 'Vuelve pronto'
        assert cfg_data['printer']['name'] == 'POS-80'
        assert cfg_data['printer']['enabled'] is True
        assert cfg_data['printer']['auto_print'] is True
        assert cfg_data['scanner']['enabled'] is True
        assert cfg_data['drawer']['enabled'] is True

        marker = await db_conn.fetchrow("SELECT value FROM app_config WHERE key = 'initial_setup'")
        assert marker is not None
        marker_payload = json.loads(marker['value'])
        assert marker_payload['completed'] is True
        assert marker_payload.get('completed_at')

        status = await client.get('/api/v1/hardware/setup-status', headers=auth_header(admin_token))
        assert status.status_code == 200
        assert status.json()['data']['completed'] is True


class TestNeedsSetup:
    async def test_needs_setup_true_when_no_users(self, client):
        r = await client.get("/api/v1/auth/needs-setup")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["data"]["needs_first_user"] is True

    async def test_needs_setup_false_when_user_exists(self, client, seed_users):
        r = await client.get("/api/v1/auth/needs-setup")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["data"]["needs_first_user"] is False


class TestSetupOwner:
    async def test_setup_owner_creates_user_returns_token(self, client):
        r = await client.post(
            "/api/v1/auth/setup-owner",
            json={"username": "primer_admin", "password": "segura1234", "name": "Admin Principal"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
        assert data["role"] == "admin"

    async def test_setup_owner_blocked_when_user_exists(self, client, seed_users):
        r = await client.post(
            "/api/v1/auth/setup-owner",
            json={"username": "segundo_admin", "password": "segura1234"},
        )
        assert r.status_code == 409

    async def test_setup_owner_rejects_weak_password(self, client):
        r = await client.post(
            "/api/v1/auth/setup-owner",
            json={"username": "admin", "password": "corta"},
        )
        assert r.status_code == 422

    async def test_setup_owner_rejects_invalid_username(self, client):
        r = await client.post(
            "/api/v1/auth/setup-owner",
            json={"username": "user name!", "password": "segura1234"},
        )
        assert r.status_code == 422

    async def test_setup_owner_token_is_valid(self, client):
        """Token returned by setup-owner should pass /verify."""
        r = await client.post(
            "/api/v1/auth/setup-owner",
            json={"username": "admin_verify", "password": "verifica1234"},
        )
        assert r.status_code == 200
        token = r.json()["access_token"]

        verify = await client.get("/api/v1/auth/verify", headers=auth_header(token))
        assert verify.status_code == 200
        assert verify.json()["data"]["role"] == "admin"
