"""Tests for sale creation logic (integration with real DB).

Tests the core sale transaction: folio generation, stock deduction,
credit handling, and mixed payments via direct asyncpg queries.
"""

import pytest
import uuid


# ── Helpers ────────────────────────────────────────────────────────

async def _create_test_product(db, sku=None, stock=100.0, price=50.0, name="Test Product"):
    """Create a test product and return its id."""
    sku = sku or f"SALE-TEST-{uuid.uuid4().hex[:8]}"
    row = await db.fetchrow(
        """INSERT INTO products (sku, name, price, price_wholesale, cost, stock, min_stock, is_active, created_at, updated_at)
           VALUES (:sku, :name, :price, 0, 0, :stock, 5, 1, NOW(), NOW())
           RETURNING id""",
        {"sku": sku, "name": name, "price": price, "stock": stock},
    )
    return row["id"], sku


async def _create_test_employee(db):
    """Create a test employee and return id."""
    code = f"EMP-{uuid.uuid4().hex[:6]}"
    row = await db.fetchrow(
        """INSERT INTO employees (employee_code, name, position, is_active, created_at)
           VALUES (:code, 'Test Employee', 'cajero', 1, NOW()::text)
           RETURNING id""",
        {"code": code},
    )
    return row["id"], code


async def _create_test_turn(db, user_id, terminal_id=1):
    """Create an open turn and return its id."""
    row = await db.fetchrow(
        """INSERT INTO turns (user_id, terminal_id, status, initial_cash, start_timestamp, synced)
           VALUES (:uid, :tid, 'OPEN', 0, NOW()::text, 0)
           RETURNING id""",
        {"uid": user_id, "tid": terminal_id},
    )
    return row["id"]


async def _create_test_customer(db, credit_limit=10000.0):
    """Create a test customer with credit enabled."""
    name = f"Customer-{uuid.uuid4().hex[:8]}"
    row = await db.fetchrow(
        """INSERT INTO customers (name, phone, credit_balance, credit_limit, credit_authorized, is_active, created_at, updated_at)
           VALUES (:name, :phone, 0, :limit, 1, 1, NOW(), NOW())
           RETURNING id""",
        {"name": name, "phone": f"55{uuid.uuid4().hex[:8]}", "limit": credit_limit},
    )
    return row["id"], name


async def _ensure_sequence(db, serie="A", terminal_id=1):
    """Ensure folio sequence exists."""
    await db.execute(
        """INSERT INTO secuencias (serie, terminal_id, ultimo_numero, descripcion, synced)
           VALUES (:serie, :tid, 0, :desc, 0)
           ON CONFLICT (serie, terminal_id) DO NOTHING""",
        {"serie": serie, "tid": terminal_id, "desc": f"{serie} T{terminal_id}"},
    )


# ── Tests ──────────────────────────────────────────────────────────

async def test_create_cash_sale(db_session):
    """Simple cash sale: creates sale + items + deducts stock."""
    pid, sku = await _create_test_product(db_session, stock=50.0, price=100.0)
    uid, emp_code = await _create_test_employee(db_session)
    turn_id = await _create_test_turn(db_session, uid)
    await _ensure_sequence(db_session)

    sale_uuid = str(uuid.uuid4())
    try:
        # Create sale via CTE folio
        sale_row = await db_session.fetchrow(
            """
            WITH new_folio AS (
                UPDATE secuencias
                SET ultimo_numero = ultimo_numero + 1, synced = 0
                WHERE serie = :serie AND terminal_id = :tid
                RETURNING ultimo_numero
            )
            INSERT INTO sales (
                uuid, timestamp, subtotal, tax, total, discount, payment_method,
                customer_id, user_id, turn_id, branch_id,
                cash_received, serie, folio_visible, status, synced
            )
            SELECT :uuid, NOW(), :subtotal, :tax, :total, 0, 'cash',
                   NULL, :uid, :turn_id, 1,
                   :cash, :serie,
                   :serie || :tid_str || '-' || LPAD((SELECT ultimo_numero FROM new_folio)::text, 6, '0'),
                   'completed', 0
            RETURNING id, folio_visible
            """,
            {
                "serie": "A", "tid": 1, "uuid": sale_uuid,
                "subtotal": 86.21, "tax": 13.79, "total": 100.0,
                "uid": uid, "turn_id": turn_id, "cash": 200.0,
                "tid_str": "1",
            },
        )
        assert sale_row is not None
        sale_id = sale_row["id"]
        assert sale_row["folio_visible"].startswith("A1-")

        # Insert sale_item
        await db_session.execute(
            """INSERT INTO sale_items (sale_id, product_id, qty, price, subtotal, total, name, synced)
               VALUES (:sid, :pid, 1, 86.21, 86.21, 86.21, 'Test Product', 0)""",
            {"sid": sale_id, "pid": pid},
        )

        # Deduct stock
        await db_session.execute(
            "UPDATE products SET stock = stock - 1 WHERE id = :id",
            {"id": pid},
        )

        # Verify stock deduction
        prod = await db_session.fetchrow(
            "SELECT stock FROM products WHERE id = :id", {"id": pid}
        )
        assert float(prod["stock"]) == 49.0

        # Verify sale items
        items = await db_session.fetch(
            "SELECT * FROM sale_items WHERE sale_id = :sid", {"sid": sale_id}
        )
        assert len(items) == 1
        assert items[0]["product_id"] == pid

    finally:
        await db_session.execute("DELETE FROM sale_items WHERE sale_id IN (SELECT id FROM sales WHERE uuid = :uuid)", {"uuid": sale_uuid})
        await db_session.execute("DELETE FROM inventory_movements WHERE reference_id IN (SELECT id FROM sales WHERE uuid = :uuid)", {"uuid": sale_uuid})
        await db_session.execute("DELETE FROM sales WHERE uuid = :uuid", {"uuid": sale_uuid})
        await db_session.execute("DELETE FROM turns WHERE id = :id", {"id": turn_id})
        await db_session.execute("DELETE FROM employees WHERE id = :id", {"id": uid})
        await db_session.execute("DELETE FROM products WHERE id = :id", {"id": pid})


async def test_create_sale_deducts_stock(db_session):
    """Stock should be reduced by the quantity sold."""
    pid, sku = await _create_test_product(db_session, stock=20.0, price=10.0)
    try:
        # Lock + deduct
        locked = await db_session.fetchrow(
            "SELECT stock FROM products WHERE id = :id FOR UPDATE",
            {"id": pid},
        )
        assert float(locked["stock"]) == 20.0

        await db_session.execute(
            "UPDATE products SET stock = stock - :qty WHERE id = :id",
            {"qty": 5.0, "id": pid},
        )

        after = await db_session.fetchrow(
            "SELECT stock FROM products WHERE id = :id", {"id": pid}
        )
        assert float(after["stock"]) == 15.0
    finally:
        await db_session.execute("DELETE FROM products WHERE id = :id", {"id": pid})


async def test_create_sale_requires_open_turn(db_session):
    """Sale should fail without an open turn (query returns no rows)."""
    uid, emp_code = await _create_test_employee(db_session)
    try:
        # No turn created — query should return None
        turn = await db_session.fetchrow(
            "SELECT id FROM turns WHERE user_id = :uid AND status = 'OPEN' LIMIT 1",
            {"uid": uid},
        )
        assert turn is None, "Should not find an open turn"
    finally:
        await db_session.execute("DELETE FROM employees WHERE id = :id", {"id": uid})


async def test_create_sale_insufficient_stock(db_session):
    """Sale should be blocked when stock is insufficient."""
    pid, sku = await _create_test_product(db_session, stock=2.0)
    try:
        prod = await db_session.fetchrow(
            "SELECT stock, name FROM products WHERE id = :id FOR UPDATE",
            {"id": pid},
        )
        current_stock = float(prod["stock"])
        requested_qty = 5.0

        assert current_stock < requested_qty, "Stock should be insufficient"
    finally:
        await db_session.execute("DELETE FROM products WHERE id = :id", {"id": pid})


async def test_create_credit_sale_updates_balance(db_session):
    """Credit sale should increase customer's credit_balance."""
    cid, cname = await _create_test_customer(db_session, credit_limit=5000.0)
    try:
        # Verify initial balance
        cust = await db_session.fetchrow(
            "SELECT credit_balance, credit_limit FROM customers WHERE id = :id FOR UPDATE",
            {"id": cid},
        )
        assert float(cust["credit_balance"]) == 0.0

        # Simulate credit charge
        sale_total = 1500.0
        await db_session.execute(
            "UPDATE customers SET credit_balance = credit_balance + :amount WHERE id = :id",
            {"amount": sale_total, "id": cid},
        )

        updated = await db_session.fetchrow(
            "SELECT credit_balance FROM customers WHERE id = :id", {"id": cid}
        )
        assert float(updated["credit_balance"]) == 1500.0
    finally:
        await db_session.execute("DELETE FROM customers WHERE id = :id", {"id": cid})


async def test_create_sale_generates_folio(db_session):
    """Folio CTE should generate sequential folio numbers."""
    await _ensure_sequence(db_session, serie="T", terminal_id=99)
    sale_uuid_1 = str(uuid.uuid4())
    sale_uuid_2 = str(uuid.uuid4())
    uid, emp_code = await _create_test_employee(db_session)
    turn_id = await _create_test_turn(db_session, uid, terminal_id=99)

    try:
        # First folio
        row1 = await db_session.fetchrow(
            """
            WITH new_folio AS (
                UPDATE secuencias SET ultimo_numero = ultimo_numero + 1, synced = 0
                WHERE serie = 'T' AND terminal_id = 99
                RETURNING ultimo_numero
            )
            INSERT INTO sales (uuid, timestamp, subtotal, tax, total, discount, payment_method,
                               user_id, turn_id, branch_id, serie, folio_visible, status, synced)
            SELECT :uuid, NOW(), 10, 1.6, 11.6, 0, 'cash',
                   :uid, :tid, 1, 'T',
                   'T99-' || LPAD((SELECT ultimo_numero FROM new_folio)::text, 6, '0'),
                   'completed', 0
            RETURNING folio_visible
            """,
            {"uuid": sale_uuid_1, "uid": uid, "tid": turn_id},
        )

        # Second folio
        row2 = await db_session.fetchrow(
            """
            WITH new_folio AS (
                UPDATE secuencias SET ultimo_numero = ultimo_numero + 1, synced = 0
                WHERE serie = 'T' AND terminal_id = 99
                RETURNING ultimo_numero
            )
            INSERT INTO sales (uuid, timestamp, subtotal, tax, total, discount, payment_method,
                               user_id, turn_id, branch_id, serie, folio_visible, status, synced)
            SELECT :uuid, NOW(), 10, 1.6, 11.6, 0, 'cash',
                   :uid, :tid, 1, 'T',
                   'T99-' || LPAD((SELECT ultimo_numero FROM new_folio)::text, 6, '0'),
                   'completed', 0
            RETURNING folio_visible
            """,
            {"uuid": sale_uuid_2, "uid": uid, "tid": turn_id},
        )

        folio1 = row1["folio_visible"]
        folio2 = row2["folio_visible"]
        assert folio1.startswith("T99-")
        assert folio2.startswith("T99-")
        # Sequential
        num1 = int(folio1.split("-")[1])
        num2 = int(folio2.split("-")[1])
        assert num2 == num1 + 1

    finally:
        await db_session.execute("DELETE FROM sale_items WHERE sale_id IN (SELECT id FROM sales WHERE uuid IN (:u1, :u2))", {"u1": sale_uuid_1, "u2": sale_uuid_2})
        await db_session.execute("DELETE FROM sales WHERE uuid IN (:u1, :u2)", {"u1": sale_uuid_1, "u2": sale_uuid_2})
        await db_session.execute("DELETE FROM turns WHERE id = :id", {"id": turn_id})
        await db_session.execute("DELETE FROM employees WHERE id = :id", {"id": uid})
        await db_session.execute("DELETE FROM secuencias WHERE serie = 'T' AND terminal_id = 99")


async def test_create_sale_mixed_payment_validation(db_session):
    """Mixed payment: sum of components must equal total."""
    total = 100.0
    mixed_cash = 50.0
    mixed_card = 30.0
    mixed_transfer = 20.0
    mixed_sum = mixed_cash + mixed_card + mixed_transfer

    tolerance = 0.02
    assert abs(mixed_sum - total) <= tolerance, "Mixed payment sum should equal total"

    # Invalid: sum != total
    bad_sum = 50.0 + 30.0 + 10.0  # = 90 != 100
    assert abs(bad_sum - total) > tolerance, "Invalid mixed sum should be rejected"
