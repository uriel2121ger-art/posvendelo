"""Tests for health check and terminals endpoints."""

import pytest
from conftest import auth_header


class TestHealth:
    async def test_health_returns_healthy(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["data"]["status"] == "healthy"
        assert data["data"]["service"] == "titan-pos"

    async def test_terminals_requires_auth(self, client):
        r = await client.get("/api/v1/terminals")
        assert r.status_code == 401

    async def test_terminals_returns_branches(self, client, admin_token, seed_branch):
        r = await client.get(
            "/api/v1/terminals", headers=auth_header(admin_token)
        )
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert isinstance(data["terminals"], list)
        assert len(data["terminals"]) >= 1
        t = data["terminals"][0]
        assert "terminal_id" in t
        assert "terminal_name" in t
