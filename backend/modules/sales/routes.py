"""
TITAN POS - Sales Module Routes
"""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

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
    db=Depends(get_db),
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

    rows = await db.fetch(sql, params)
    return {"success": True, "data": rows}


@router.get("/{sale_id}")
async def get_sale(sale_id: int, db=Depends(get_db)):
    """Get sale by ID with items."""
    sale_row = await db.fetchrow(
        "SELECT * FROM sales WHERE id = :id", {"id": sale_id}
    )
    if not sale_row:
        raise HTTPException(status_code=404, detail="Venta no encontrada")

    items = await db.fetch(
        "SELECT * FROM sale_items WHERE sale_id = :id ORDER BY id",
        {"id": sale_id}
    )

    return {
        "success": True,
        "data": {
            **sale_row,
            "items": items,
        }
    }


@router.get("/{sale_id}/events")
async def get_sale_events(sale_id: int, db=Depends(get_db)):
    """Get event sourcing events for a sale."""
    rows = await db.fetch(
        """
        SELECT event_id, event_type, sequence, data, user_id, timestamp
        FROM sale_events
        WHERE sale_id = :sale_id
        ORDER BY sequence ASC
        """,
        {"sale_id": sale_id}
    )
    return {"success": True, "data": rows}


@router.get("/reports/daily-summary")
async def daily_sales_summary(
    branch_id: Optional[int] = None,
    limit: int = Query(30, ge=1, le=365),
    db=Depends(get_db),
):
    """Get daily sales summary from CQRS materialized view."""
    sql = "SELECT * FROM mv_daily_sales_summary WHERE 1=1"
    params: dict = {}

    if branch_id:
        sql += " AND branch_id = :branch_id"
        params["branch_id"] = branch_id

    sql += " ORDER BY sale_date DESC LIMIT :limit"
    params["limit"] = limit

    rows = await db.fetch(sql, params)
    return {"success": True, "data": rows}


@router.get("/reports/product-ranking")
async def product_sales_ranking(
    limit: int = Query(50, ge=1, le=500),
    db=Depends(get_db),
):
    """Get product sales ranking from CQRS materialized view."""
    rows = await db.fetch(
        "SELECT * FROM mv_product_sales_ranking ORDER BY total_revenue DESC LIMIT :limit",
        {"limit": limit}
    )
    return {"success": True, "data": rows}


@router.get("/reports/hourly-heatmap")
async def hourly_heatmap(
    branch_id: Optional[int] = None,
    db=Depends(get_db),
):
    """Get hourly sales heatmap from CQRS materialized view."""
    sql = "SELECT * FROM mv_hourly_sales_heatmap WHERE 1=1"
    params: dict = {}

    if branch_id:
        sql += " AND branch_id = :branch_id"
        params["branch_id"] = branch_id

    sql += " ORDER BY day_of_week, hour_of_day"

    rows = await db.fetch(sql, params)
    return {"success": True, "data": rows}
