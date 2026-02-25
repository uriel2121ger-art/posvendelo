"""Tests for modules/sat SAT catalog (PostgreSQL)."""

import pytest


async def test_seed_sat_catalog(db_session):
    """seed_sat_catalog populates table when empty."""
    from modules.sat.sat_catalog import seed_sat_catalog, get_sat_count

    # Ensure table exists (migration must have run)
    await db_session.execute(
        "CREATE TABLE IF NOT EXISTS sat_clave_prod_serv ("
        "clave TEXT PRIMARY KEY, descripcion TEXT NOT NULL, "
        "categoria TEXT, iva_trasladado BOOLEAN DEFAULT TRUE, "
        "ieps_trasladado BOOLEAN DEFAULT FALSE)"
    )

    count_before = await get_sat_count(db_session)
    inserted = await seed_sat_catalog(db_session)

    if count_before == 0:
        assert inserted > 0
    else:
        # Already seeded (from migration), should skip
        assert inserted == 0

    total = await get_sat_count(db_session)
    assert total >= 130  # 137 common codes in COMMON_CODES list


async def test_seed_idempotent(db_session):
    """seed_sat_catalog is idempotent — second call inserts 0."""
    from modules.sat.sat_catalog import seed_sat_catalog

    await db_session.execute(
        "CREATE TABLE IF NOT EXISTS sat_clave_prod_serv ("
        "clave TEXT PRIMARY KEY, descripcion TEXT NOT NULL, "
        "categoria TEXT, iva_trasladado BOOLEAN DEFAULT TRUE, "
        "ieps_trasladado BOOLEAN DEFAULT FALSE)"
    )

    await seed_sat_catalog(db_session)
    second = await seed_sat_catalog(db_session)
    assert second == 0


async def test_search_sat_codes(db_session):
    """search_sat_codes returns matching results."""
    from modules.sat.sat_catalog import search_sat_codes, seed_sat_catalog

    await db_session.execute(
        "CREATE TABLE IF NOT EXISTS sat_clave_prod_serv ("
        "clave TEXT PRIMARY KEY, descripcion TEXT NOT NULL, "
        "categoria TEXT, iva_trasladado BOOLEAN DEFAULT TRUE, "
        "ieps_trasladado BOOLEAN DEFAULT FALSE)"
    )
    await seed_sat_catalog(db_session)

    results = await search_sat_codes(db_session, "refresco")
    assert len(results) >= 1
    assert any(r["clave"] == "50161700" for r in results)


async def test_search_by_code(db_session):
    """search_sat_codes can find by partial code."""
    from modules.sat.sat_catalog import search_sat_codes, seed_sat_catalog

    await db_session.execute(
        "CREATE TABLE IF NOT EXISTS sat_clave_prod_serv ("
        "clave TEXT PRIMARY KEY, descripcion TEXT NOT NULL, "
        "categoria TEXT, iva_trasladado BOOLEAN DEFAULT TRUE, "
        "ieps_trasladado BOOLEAN DEFAULT FALSE)"
    )
    await seed_sat_catalog(db_session)

    results = await search_sat_codes(db_session, "01010101")
    assert len(results) == 1
    assert results[0]["descripcion"] == "No existe en el catálogo"


async def test_search_short_query(db_session):
    """search_sat_codes rejects queries shorter than 2 chars."""
    from modules.sat.sat_catalog import search_sat_codes

    results = await search_sat_codes(db_session, "a")
    assert results == []

    results = await search_sat_codes(db_session, "")
    assert results == []


async def test_get_sat_description(db_session):
    """get_sat_description returns description for known code."""
    from modules.sat.sat_catalog import get_sat_description, seed_sat_catalog

    await db_session.execute(
        "CREATE TABLE IF NOT EXISTS sat_clave_prod_serv ("
        "clave TEXT PRIMARY KEY, descripcion TEXT NOT NULL, "
        "categoria TEXT, iva_trasladado BOOLEAN DEFAULT TRUE, "
        "ieps_trasladado BOOLEAN DEFAULT FALSE)"
    )
    await seed_sat_catalog(db_session)

    desc = await get_sat_description(db_session, "50161700")
    assert desc == "Refrescos"


async def test_get_sat_description_not_found(db_session):
    """get_sat_description returns None for unknown code."""
    from modules.sat.sat_catalog import get_sat_description

    await db_session.execute(
        "CREATE TABLE IF NOT EXISTS sat_clave_prod_serv ("
        "clave TEXT PRIMARY KEY, descripcion TEXT NOT NULL, "
        "categoria TEXT, iva_trasladado BOOLEAN DEFAULT TRUE, "
        "ieps_trasladado BOOLEAN DEFAULT FALSE)"
    )

    desc = await get_sat_description(db_session, "99999999")
    assert desc is None


async def test_add_sat_code(db_session):
    """add_sat_code inserts and upserts correctly."""
    from modules.sat.sat_catalog import add_sat_code, get_sat_description

    await db_session.execute(
        "CREATE TABLE IF NOT EXISTS sat_clave_prod_serv ("
        "clave TEXT PRIMARY KEY, descripcion TEXT NOT NULL, "
        "categoria TEXT, iva_trasladado BOOLEAN DEFAULT TRUE, "
        "ieps_trasladado BOOLEAN DEFAULT FALSE)"
    )

    await add_sat_code(db_session, "99990001", "Test producto")
    desc = await get_sat_description(db_session, "99990001")
    assert desc == "Test producto"

    # Upsert — update description
    await add_sat_code(db_session, "99990001", "Test actualizado", "custom")
    desc = await get_sat_description(db_session, "99990001")
    assert desc == "Test actualizado"


async def test_search_limit(db_session):
    """search_sat_codes respects limit parameter."""
    from modules.sat.sat_catalog import search_sat_codes, seed_sat_catalog

    await db_session.execute(
        "CREATE TABLE IF NOT EXISTS sat_clave_prod_serv ("
        "clave TEXT PRIMARY KEY, descripcion TEXT NOT NULL, "
        "categoria TEXT, iva_trasladado BOOLEAN DEFAULT TRUE, "
        "ieps_trasladado BOOLEAN DEFAULT FALSE)"
    )
    await seed_sat_catalog(db_session)

    results = await search_sat_codes(db_session, "53131", limit=5)
    assert len(results) <= 5


async def test_fallback_codes():
    """Route fallback _COMMON_CODES filters correctly."""
    from modules.sat.routes import _COMMON_CODES

    q = "piel"
    filtered = [
        {"code": code, "description": desc}
        for code, desc in _COMMON_CODES
        if q.lower() in desc.lower()
    ]
    assert len(filtered) >= 1
    assert filtered[0]["code"] == "53131500"
