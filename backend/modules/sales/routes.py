"""
TITAN POS - Sales Module Routes

FastAPI routes for the sales domain module.
These can be included in the monolith or extracted to a microservice.
"""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from db.connection import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def list_sales(
    status: Optional[str] = "completed",
    branch_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List sales with filters."""
    sql = "SELECT * FROM sales WHERE 1=1"
    params: dict = {}

    if status and status != "all":
        sql += " AND status = :status"
        params["status"] = status
    if branch_id:
        sql += " AND branch_id = :branch_id"
        params["branch_id"] = branch_id
    if customer_id:
        sql += " AND customer_id = :customer_id"
        params["customer_id"] = customer_id
    if start_date:
        try:
            date.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="start_date debe ser formato ISO (YYYY-MM-DD)")
        sql += " AND timestamp >= :start_date"
        params["start_date"] = start_date
    if end_date:
        try:
            date.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="end_date debe ser formato ISO (YYYY-MM-DD)")
        sql += " AND timestamp <= :end_date"
        params["end_date"] = end_date

    sql += " ORDER BY id DESC LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    result = await db.execute(text(sql), params)
    rows = result.mappings().all()
    return {"success": True, "data": [dict(r) for r in rows]}


@router.get("/{sale_id}")
async def get_sale(sale_id: int, db: AsyncSession = Depends(get_db)):
    """Get sale by ID with items."""
    sale = await db.execute(
        text("SELECT * FROM sales WHERE id = :id"), {"id": sale_id}
    )
    sale_row = sale.mappings().first()
    if not sale_row:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    items = await db.execute(
        text("SELECT * FROM sale_items WHERE sale_id = :id ORDER BY id"),
        {"id": sale_id}
    )
    items_rows = items.mappings().all()

    return {
        "success": True,
        "data": {
            **dict(sale_row),
            "items": [dict(r) for r in items_rows],
        }
    }


@router.get("/{sale_id}/events")
async def get_sale_events(sale_id: int, db: AsyncSession = Depends(get_db)):
    """Get event sourcing events for a sale (Phase 5)."""
    result = await db.execute(
        text("""
            SELECT event_id, event_type, sequence, data, user_id, timestamp
            FROM sale_events
            WHERE sale_id = :sale_id
            ORDER BY sequence ASC
        """),
        {"sale_id": sale_id}
    )
    rows = result.mappings().all()
    return {"success": True, "data": [dict(r) for r in rows]}


@router.get("/reports/daily-summary")
async def daily_sales_summary(
    branch_id: Optional[int] = None,
    limit: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get daily sales summary from CQRS materialized view."""
    sql = "SELECT * FROM mv_daily_sales_summary WHERE 1=1"
    params: dict = {}

    if branch_id:
        sql += " AND branch_id = :branch_id"
        params["branch_id"] = branch_id

    sql += " ORDER BY sale_date DESC LIMIT :limit"
    params["limit"] = limit

    result = await db.execute(text(sql), params)
    rows = result.mappings().all()
    return {"success": True, "data": [dict(r) for r in rows]}


@router.get("/reports/product-ranking")
async def product_sales_ranking(
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get product sales ranking from CQRS materialized view."""
    result = await db.execute(
        text("SELECT * FROM mv_product_sales_ranking ORDER BY total_revenue DESC LIMIT :limit"),
        {"limit": limit}
    )
    rows = result.mappings().all()
    return {"success": True, "data": [dict(r) for r in rows]}


@router.get("/reports/hourly-heatmap")
async def hourly_heatmap(
    branch_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get hourly sales heatmap from CQRS materialized view."""
    sql = "SELECT * FROM mv_hourly_sales_heatmap WHERE 1=1"
    params: dict = {}

    if branch_id:
        sql += " AND branch_id = :branch_id"
        params["branch_id"] = branch_id

    sql += " ORDER BY day_of_week, hour_of_day"

    result = await db.execute(text(sql), params)
    rows = result.mappings().all()
    return {"success": True, "data": [dict(r) for r in rows]}
