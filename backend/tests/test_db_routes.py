"""Tests for module routes with real database (integration tests).

These tests verify that the module routes can query the real database
and return correct results. They require a running PostgreSQL instance.
"""

import pytest


# ============================================================================
# Database connectivity
# ============================================================================

async def test_db_connection(db_session):
    """Verify async database connection works."""
    row = await db_session.fetchrow("SELECT 1 AS n")
    assert row["n"] == 1


async def test_sales_table_accessible(db_session):
    """Sales table is accessible and has expected columns."""
    await db_session.fetch(
        "SELECT id, folio, total, status, timestamp FROM sales LIMIT 1"
    )


async def test_products_table_accessible(db_session):
    """Products table is accessible with expected columns."""
    await db_session.fetch(
        "SELECT id, sku, name, stock, min_stock, is_active FROM products LIMIT 1"
    )


async def test_customers_table_accessible(db_session):
    """Customers table is accessible with expected columns."""
    await db_session.fetch(
        "SELECT id, name, phone, email, rfc, is_active FROM customers LIMIT 1"
    )


async def test_employees_table_accessible(db_session):
    """Employees table is accessible with expected columns."""
    await db_session.fetch(
        "SELECT id, name, position, base_salary, is_active FROM employees LIMIT 1"
    )


async def test_sale_events_table_exists(db_session):
    """sale_events table (event sourcing) exists."""
    await db_session.fetch(
        "SELECT event_id, sale_id, sequence, event_type, data FROM sale_events LIMIT 1"
    )


async def test_domain_events_table_exists(db_session):
    """domain_events table (outbox) exists."""
    await db_session.fetch(
        "SELECT event_id, event_type, aggregate_type, data, processed FROM domain_events LIMIT 1"
    )


async def test_inventory_movements_table_exists(db_session):
    """inventory_movements table exists."""
    await db_session.fetch(
        "SELECT id, product_id, quantity, movement_type FROM inventory_movements LIMIT 1"
    )


# ============================================================================
# Materialized views (CQRS)
# ============================================================================

async def test_daily_sales_view_exists(db_session):
    """mv_daily_sales_summary materialized view exists and is queryable."""
    rows = await db_session.fetch(
        "SELECT sale_date, total_transactions, total_revenue FROM mv_daily_sales_summary LIMIT 5"
    )
    assert isinstance(rows, list), "Daily sales summary view should be queryable"


async def test_product_ranking_view_exists(db_session):
    """mv_product_sales_ranking materialized view exists and is queryable."""
    rows = await db_session.fetch(
        "SELECT product_name, total_qty_sold, total_revenue FROM mv_product_sales_ranking LIMIT 5"
    )
    assert isinstance(rows, list), "Product ranking view should be queryable"


async def test_hourly_heatmap_view_exists(db_session):
    """mv_hourly_sales_heatmap materialized view exists and is queryable."""
    rows = await db_session.fetch(
        "SELECT day_of_week, hour_of_day, transaction_count FROM mv_hourly_sales_heatmap LIMIT 5"
    )
    assert isinstance(rows, list), "Hourly heatmap view should be queryable"


# ============================================================================
# Saga tables
# ============================================================================

async def test_saga_instances_table_exists(db_session):
    """saga_instances table exists."""
    await db_session.fetch(
        "SELECT saga_id, saga_type, state FROM saga_instances LIMIT 1"
    )


async def test_saga_steps_table_exists(db_session):
    """saga_steps table exists."""
    await db_session.fetch(
        "SELECT saga_id, step_number, step_name, status FROM saga_steps LIMIT 1"
    )
