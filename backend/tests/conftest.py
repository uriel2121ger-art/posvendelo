"""
TITAN POS — Test Configuration & Fixtures

Per-test transaction rollback with asyncpg.  Every test runs inside a
BEGIN…ROLLBACK block so the real dev DB stays clean.

Usage:
    cd backend && source .venv/bin/activate
    DATABASE_URL="postgresql://titan_user:PASSWORD@localhost:5433/titan_pos" \
    JWT_SECRET="test-secret" \
    python3 -m pytest tests/ -v
"""

import os

# ── Environment (MUST be set before importing app modules) ───────
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://titan_user:XqaDwbaY6TE9J6OIz7Sodplp@localhost:5433/titan_pos",
)
os.environ.setdefault(
    "JWT_SECRET",
    "43ac79b9031e3d5ca50db87d77eed47f5a358bd1938f5ac77dd0b0a513f1cf2a",
)
os.environ.setdefault("DEBUG", "true")

import asyncpg
import httpx
import pytest
from contextlib import asynccontextmanager

from main import app
from db.connection import get_db, DB
from modules.shared.auth import create_token

# ── Test IDs (90 000+ range — safe from collisions) ─────────────
ADMIN_ID = 90001
CASHIER_ID = 90002
MANAGER_ID = 90003
BRANCH_ID = 90001
PRODUCT_ID = 90001
PRODUCT_NOSTOCK_ID = 90002
CUSTOMER_ID = 90001
TURN_ID = 90001
TERMINAL_ID = 1  # keep simple — secuencias PK is (serie, terminal_id)
EMPLOYEE_ID = 90001


# ── Helper ───────────────────────────────────────────────────────

def auth_header(token: str) -> dict:
    """Build Authorization header dict."""
    return {"Authorization": f"Bearer {token}"}


# ── DSN for asyncpg (strip SQLAlchemy dialect) ────────────────
_DSN = os.environ["DATABASE_URL"].replace(
    "postgresql+asyncpg://", "postgresql://"
)


# ── Mock pool for monkeypatching get_pool ────────────────────────

class _MockAcquire:
    """Async context manager yielding a fixed connection."""
    __slots__ = ("_conn",)

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *a):
        pass


class _MockPool:
    """Always yields the same transactional connection."""
    __slots__ = ("_conn",)

    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _MockAcquire(self._conn)


# ── Core fixtures ────────────────────────────────────────────────

@pytest.fixture
async def db_conn():
    """Per-test asyncpg connection wrapped in a transaction.

    Everything done during the test (including via HTTP endpoints) is
    rolled back when the test finishes.  Uses a direct connection
    (no pool) to avoid event-loop lifecycle issues with pytest-asyncio.
    """
    conn = await asyncpg.connect(dsn=_DSN, server_settings={"timezone": "UTC"})
    tx = conn.transaction()
    await tx.start()
    yield conn
    await tx.rollback()
    await conn.close()


@pytest.fixture
async def client(db_conn, monkeypatch):
    """httpx.AsyncClient with all DB access routed through db_conn."""
    db = DB(db_conn)

    # 1. Override FastAPI dependency: get_db
    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db

    # 2. Monkeypatch get_connection (used by sales, expenses)
    @asynccontextmanager
    async def _override_get_connection():
        yield db

    monkeypatch.setattr("db.connection.get_connection", _override_get_connection)

    # 3. Monkeypatch get_pool (used by health check)
    mock_pool = _MockPool(db_conn)

    async def _override_get_pool():
        return mock_pool

    monkeypatch.setattr("db.connection.get_pool", _override_get_pool)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


# ── Auth tokens ──────────────────────────────────────────────────

@pytest.fixture
def admin_token():
    return create_token(str(ADMIN_ID), "admin")


@pytest.fixture
def cashier_token():
    return create_token(str(CASHIER_ID), "cashier")


@pytest.fixture
def manager_token():
    return create_token(str(MANAGER_ID), "manager")


# ── Seed fixtures ────────────────────────────────────────────────

@pytest.fixture
async def seed_branch(db_conn):
    """Insert test branch."""
    await db_conn.execute(
        "INSERT INTO branches (id, name, code, is_active, created_at, updated_at) "
        "VALUES ($1, $2, $3, 1, NOW(), NOW())",
        BRANCH_ID, "Test Matriz", "TMTZ",
    )


@pytest.fixture
async def seed_users(db_conn, seed_branch):
    """Insert admin + cashier + manager users with known bcrypt hash."""
    import bcrypt

    pw = bcrypt.hashpw(b"test1234", bcrypt.gensalt(rounds=4)).decode()
    for uid, uname, role in [
        (ADMIN_ID, "test_admin_90001", "admin"),
        (CASHIER_ID, "test_cajero_90002", "cashier"),
        (MANAGER_ID, "test_mgr_90003", "manager"),
    ]:
        await db_conn.execute(
            "INSERT INTO users "
            "(id, username, password_hash, role, is_active, branch_id, created_at, updated_at) "
            "VALUES ($1, $2, $3, $4, 1, $5, NOW(), NOW())",
            uid, uname, pw, role, BRANCH_ID,
        )


@pytest.fixture
async def seed_product(db_conn, seed_branch):
    """Insert two test products: one with stock, one without."""
    await db_conn.execute(
        "INSERT INTO products "
        "(id, sku, name, price, price_wholesale, cost, stock, category, "
        " min_stock, max_stock, tax_rate, sale_type, is_active, created_at, updated_at, synced) "
        "VALUES ($1, 'TEST-001', 'Producto Test', 116.00, 100.00, 50.00, 100, 'Bebidas', "
        " 5, 1000, 0.16, 'unit', 1, NOW(), NOW(), 0)",
        PRODUCT_ID,
    )
    await db_conn.execute(
        "INSERT INTO products "
        "(id, sku, name, price, stock, category, min_stock, "
        " is_active, created_at, updated_at, synced) "
        "VALUES ($1, 'TEST-002', 'Producto Sin Stock', 50.00, 0, 'Bebidas', 5, "
        " 1, NOW(), NOW(), 0)",
        PRODUCT_NOSTOCK_ID,
    )


@pytest.fixture
async def seed_customer(db_conn, seed_branch):
    """Insert test customer with credit enabled."""
    await db_conn.execute(
        "INSERT INTO customers "
        "(id, name, phone, email, credit_limit, credit_balance, "
        " credit_authorized, is_active, created_at, updated_at, synced) "
        "VALUES ($1, 'Cliente Test', '9991234567', 'test@test.com', 5000, 0, "
        " 1, 1, NOW(), NOW(), 0)",
        CUSTOMER_ID,
    )


@pytest.fixture
async def seed_turn(db_conn, seed_users):
    """Insert open turn for admin user."""
    await db_conn.execute(
        "INSERT INTO turns "
        "(id, user_id, branch_id, terminal_id, initial_cash, "
        " status, start_timestamp, synced) "
        "VALUES ($1, $2, $3, $4, 1000, 'open', NOW(), 0)",
        TURN_ID, ADMIN_ID, BRANCH_ID, TERMINAL_ID,
    )


@pytest.fixture
async def seed_employee(db_conn, seed_branch):
    """Insert test employee."""
    await db_conn.execute(
        "INSERT INTO employees "
        "(id, employee_code, name, position, base_salary, commission_rate, "
        " is_active, created_at) "
        "VALUES ($1, 'EMP-TEST-001', 'Empleado Test', 'Vendedor', 5000, 0.05, "
        " 1, NOW()::text)",
        EMPLOYEE_ID,
    )


@pytest.fixture
async def seed_all(seed_users, seed_product, seed_customer, seed_turn):
    """Convenience fixture: everything needed for sales tests."""
    pass
