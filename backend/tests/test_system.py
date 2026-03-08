from conftest import auth_header


class TestSystemBackups:
    async def test_system_status_reports_backups(self, client, admin_token, monkeypatch, tmp_path):
        backup_file = tmp_path / "titan_20260308_0530.dump"
        backup_file.write_bytes(b"backup-data")
        monkeypatch.setenv("TITAN_BACKUP_DIR", str(tmp_path))

        response = await client.get("/api/v1/system/status", headers=auth_header(admin_token))
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["backup_count"] == 1
        assert data["latest_backup"] == backup_file.name
        assert data["restore_supported"] is True

    async def test_restore_plan_requires_existing_backup(self, client, admin_token, monkeypatch, tmp_path):
        monkeypatch.setenv("TITAN_BACKUP_DIR", str(tmp_path))
        missing = await client.post(
            "/api/v1/system/restore-plan",
            headers=auth_header(admin_token),
            json={"backup_file": "no-existe.dump"},
        )
        assert missing.status_code == 404

        backup_file = tmp_path / "restore_me.dump"
        backup_file.write_bytes(b"backup-data")
        response = await client.post(
            "/api/v1/system/restore-plan",
            headers=auth_header(admin_token),
            json={"backup_file": backup_file.name},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["backup_file"] == backup_file.name
        assert any("pg_restore" in command for command in data["commands"])
