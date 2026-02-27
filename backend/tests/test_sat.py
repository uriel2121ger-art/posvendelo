"""Tests for SAT catalog: search + get code."""

import pytest
from conftest import auth_header


class TestSearchSATCodes:
    async def test_search_sat_codes(self, client, admin_token, seed_branch):
        r = await client.get(
            "/api/v1/sat/search?q=producto",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert "results" in d
        assert isinstance(d["results"], list)

    async def test_search_sat_codes_short_query(self, client, admin_token):
        r = await client.get(
            "/api/v1/sat/search?q=a",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 422  # min_length=2


class TestGetSATCode:
    async def test_get_sat_code(self, client, admin_token, seed_branch):
        r = await client.get(
            "/api/v1/sat/01010101",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["code"] == "01010101"

    async def test_get_sat_code_not_found(self, client, admin_token):
        r = await client.get(
            "/api/v1/sat/99999999",
            headers=auth_header(admin_token),
        )
        assert r.status_code == 404
