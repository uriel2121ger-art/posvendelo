"""Tests for module routes with real database (integration tests).

These tests verify that the module routes can query the real database
and return correct results. They require a running PostgreSQL instance.
"""

import pytest
from sqlalchemy import text


# ============================================================================
# Database connectivity
# ============================================================================

async def test_db_connection(db_session):
    """Verify async database connection works."""
    result = await db_session.execute(text("SELECT 1 AS n"))
    row = result.mappings().first()
    assert row["n"] == 1


async def test_sales_table_accessible(db_session):
    """Sales table is accessible and has expected columns."""
    result = await db_session.execute(
        text("SELECT id, folio, total, status, timestamp FROM sales LIMIT 1")
    )
    # Just verify it doesn't error — table exists with these columns
    result.mappings().all()


async def test_products_table_accessible(db_session):
    """Products table is accessible with expected columns."""
    result = await db_session.execute(
        text("SELECT id, sku, name, stock, min_stock, is_active FROM products LIMIT 1")
    )
    result.mappings().all()


async def test_customers_table_accessible(db_session):
    """Customers table is accessible with expected columns."""
    result = await db_session.execute(
        text("SELECT id, name, phone, email, rfc, is_active FROM customers LIMIT 1")
    )
    result.mappings().all()


async def test_employees_table_accessible(db_session):
    """Employees table is accessible with expected columns."""
    result = await db_session.execute(
        text("SELECT id, name, position, base_salary, is_active FROM employees LIMIT 1")
    )
    result.mappings().all()


async def test_sale_events_table_exists(db_session):
    """sale_events table (event sourcing) exists."""
    result = await db_session.execute(
        text("SELECT event_id, sale_id, sequence, event_type, data FROM sale_events LIMIT 1")
    )
    result.mappings().all()


async def test_domain_events_table_exists(db_session):
    """domain_events table (outbox) exists."""
    result = await db_session.execute(
        text("SELECT event_id, event_type, aggregate_type, data, processed FROM domain_events LIMIT 1")
    )
    result.mappings().all()


async def test_inventory_movements_table_exists(db_session):
    """inventory_movements table exists."""
    result = await db_session.execute(
        text("SELECT id, product_id, quantity, movement_type FROM inventory_movements LIMIT 1")
    )
    result.mappings().all()


# ============================================================================
# Materialized views (CQRS)
# ============================================================================

async def test_daily_sales_view_exists(db_session):
    """mv_daily_sales_summary materialized view exists and has data."""
    result = await db_session.execute(
        text("SELECT sale_date, total_transactions, total_revenue FROM mv_daily_sales_summary LIMIT 5")
    )
    rows = result.mappings().all()
    assert len(rows) > 0, "Daily sales summary view should have data"


async def test_product_ranking_view_exists(db_session):
    """mv_product_sales_ranking materialized view exists and has data."""
    result = await db_session.execute(
        text("SELECT product_name, total_qty_sold, total_revenue FROM mv_product_sales_ranking LIMIT 5")
    )
    rows = result.mappings().all()
    assert len(rows) > 0, "Product ranking view should have data"


async def test_hourly_heatmap_view_exists(db_session):
    """mv_hourly_sales_heatmap materialized view exists and has data."""
    result = await db_session.execute(
        text("SELECT day_of_week, hour_of_day, transaction_count FROM mv_hourly_sales_heatmap LIMIT 5")
    )
    rows = result.mappings().all()
    assert len(rows) > 0, "Hourly heatmap view should have data"


# ============================================================================
# Saga tables
# ============================================================================

async def test_saga_instances_table_exists(db_session):
    """saga_instances table exists."""
    result = await db_session.execute(
        text("SELECT saga_id, saga_type, state FROM saga_instances LIMIT 1")
    )
    result.mappings().all()


async def test_saga_steps_table_exists(db_session):
    """saga_steps table exists."""
    result = await db_session.execute(
        text("SELECT saga_id, step_number, step_name, status FROM saga_steps LIMIT 1")
    )
    result.mappings().all()
