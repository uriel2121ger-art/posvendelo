"""Tests for first-run setup wizard persistence."""

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
