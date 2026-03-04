"""
TITAN POS - Dashboard Module Routes

SQL directo para resico/quick/expenses.
Wrappers asyncio.to_thread para wealth/ai/executive (legacy classes).
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from db.connection import get_db
from modules.shared.auth import verify_token
from modules.shared.constants import PRIVILEGED_ROLES, RESICO_ANNUAL_LIMIT, money, dec

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# SQL directo (asyncpg)
# ============================================================================

@router.get("/resico")
async def get_resico_dashboard(auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Dashboard de monitoreo RESICO - acumulado anual serie A vs B."""
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver dashboard RESICO")
    year = datetime.now(timezone.utc).year
    year_start = datetime(year, 1, 1, tzinfo=timezone.utc)
    year_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)

    result = await db.fetchrow(
        """SELECT
             COALESCE(SUM(CASE WHEN serie = 'A' THEN total ELSE 0 END), 0) as total_a,
             COALESCE(SUM(CASE WHEN serie = 'B' THEN total ELSE 0 END), 0) as total_b
           FROM sales
           WHERE timestamp >= :year_start AND timestamp < :year_end
           AND status = 'completed'""",
        {"year_start": year_start, "year_end": year_end},
    )
    facturado_a = money(result["total_a"]) if result else 0.0
    facturado_b = money(result["total_b"]) if result else 0.0

    limite = money(RESICO_ANNUAL_LIMIT)
    restante = limite - facturado_a
    porcentaje = (facturado_a / limite) * 100

    dias = (datetime.now(timezone.utc) - datetime(year, 1, 1, tzinfo=timezone.utc)).days
    dias = max(dias, 1)
    proyeccion = (facturado_a / dias) * 365

    if porcentaje >= 100:
        status = "EXCEEDED"
    elif porcentaje >= 90:
        status = "RED"
    elif porcentaje >= 70:
        status = "YELLOW"
    else:
        status = "GREEN"

    return {
        "success": True,
        "data": {
            "serie_a": facturado_a,
            "serie_b": facturado_b,
            "total": facturado_a + facturado_b,
            "limite_resico": limite,
            "restante": restante,
            "porcentaje": money(porcentaje),
            "proyeccion_anual": money(proyeccion),
            "status": status,
            "dias_restantes": 365 - dias,
        },
    }


@router.get("/quick")
async def get_quick_status(auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Quick status widget — ventas hoy, mermas pendientes."""
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver dashboard")
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    tomorrow_start = today_start + timedelta(days=1)
    sales = await db.fetchrow(
        """SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total
           FROM sales WHERE timestamp >= :today AND timestamp < :tomorrow
           AND status = 'completed'""",
        {"today": today_start, "tomorrow": tomorrow_start},
    )

    mermas = await db.fetchrow(
        "SELECT COUNT(*) as c FROM loss_records WHERE status = 'pending'"
    )

    return {
        "success": True,
        "data": {
            "ventas_hoy": sales["count"] if sales else 0,
            "total_hoy": money(sales["total"]) if sales else 0.0,
            "mermas_pendientes": mermas["c"] if mermas else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.get("/expenses")
async def get_expenses_dashboard(auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Dashboard de gastos en efectivo — mes y anio."""
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver gastos")
    now = datetime.now(timezone.utc)
    # cash_movements.timestamp is TIMESTAMP WITHOUT TIME ZONE — pass naive datetimes
    month_start = datetime(now.year, now.month, 1)
    if now.month == 12:
        month_end = datetime(now.year + 1, 1, 1)
    else:
        month_end = datetime(now.year, now.month + 1, 1)
    year_start = datetime(now.year, 1, 1)
    year_end = datetime(now.year + 1, 1, 1)

    try:
        month_row = await db.fetchrow(
            """SELECT COALESCE(SUM(amount), 0) as total FROM cash_movements
               WHERE type = 'expense'
               AND timestamp >= :month_start AND timestamp < :month_end""",
            {"month_start": month_start, "month_end": month_end},
        )
        year_row = await db.fetchrow(
            """SELECT COALESCE(SUM(amount), 0) as total FROM cash_movements
               WHERE type = 'expense'
               AND timestamp >= :year_start AND timestamp < :year_end""",
            {"year_start": year_start, "year_end": year_end},
        )
    except Exception as e:
        logger.warning("Error consultando gastos: %s", e)
        month_row = None
        year_row = None

    return {
        "success": True,
        "data": {
            "month": money(month_row["total"]) if month_row else 0.0,
            "year": money(year_row["total"]) if year_row else 0.0,
        },
    }


# ============================================================================
# Wrappers asyncio.to_thread (legacy classes)
# ============================================================================

@router.get("/wealth")
async def get_wealth_dashboard(auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Dashboard de riqueza real (asyncpg). RBAC: admin/owner."""
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver este dashboard")

    try:
        now = datetime.now(timezone.utc)
        # sales.timestamp es TIMESTAMPTZ (migración 035) — usar datetime con timezone
        year_start_ts = datetime(now.year, 1, 1, tzinfo=timezone.utc)
        year_end_ts = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        # cash_movements.timestamp es TIMESTAMP sin timezone — usar naive datetime
        year_start_naive = datetime(now.year, 1, 1)
        year_end_naive = datetime(now.year + 1, 1, 1)

        # Ingresos por serie
        income = await db.fetchrow(
            """SELECT
                   COALESCE(SUM(CASE WHEN serie = 'A' THEN total ELSE 0 END), 0) as serie_a,
                   COALESCE(SUM(CASE WHEN serie = 'B' THEN total ELSE 0 END), 0) as serie_b,
                   COALESCE(SUM(total), 0) as total
               FROM sales
               WHERE timestamp >= :year_start AND timestamp < :year_end
               AND status = 'completed'""",
            {"year_start": year_start_ts, "year_end": year_end_ts},
        )

        # Gastos
        try:
            expenses = await db.fetchrow(
                """SELECT COALESCE(SUM(amount), 0) as total FROM cash_movements
                   WHERE type IN ('out', 'expense')
                   AND timestamp >= :year_start AND timestamp < :year_end""",
                {"year_start": year_start_naive, "year_end": year_end_naive},
            )
        except Exception as e:
            logger.warning("Error consultando gastos wealth: %s", e)
            expenses = None

        ingresos = money(income["total"] if income else 0)
        serie_a = money(income["serie_a"] if income else 0)
        serie_b = money(income["serie_b"] if income else 0)
        gastos = money(expenses["total"] if expenses else 0)
        impuestos = money(serie_a - serie_a / 1.16)  # IVA extraido de precio IVA-incluido
        utilidad_bruta = money(ingresos - gastos)
        utilidad_neta = money(utilidad_bruta - impuestos)
        disponible = money(max(0.0, utilidad_neta))
        ratio = money((utilidad_neta / ingresos * 100) if ingresos > 0 else 0.0)

        return {
            "success": True,
            "data": {
                "ingresos_total": ingresos,
                "serie_a": serie_a,
                "serie_b": serie_b,
                "gastos": gastos,
                "impuestos": impuestos,
                "utilidad_bruta": utilidad_bruta,
                "utilidad_neta": utilidad_neta,
                "disponible_retiro": disponible,
                "ratio": ratio,
            },
        }
    except Exception as e:
        logger.error("WealthDashboard error: %s", e)
        raise HTTPException(status_code=500, detail="Error obteniendo dashboard de riqueza")


@router.get("/ai")
async def get_ai_dashboard(auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Dashboard de IA — alertas de stock inteligentes (asyncpg)."""
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver dashboard IA")
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    low_stock = await db.fetch(
        """SELECT p.id, p.name, p.stock, p.min_stock,
                  COALESCE(SUM(si.qty), 0) as sold_30d
           FROM products p
           LEFT JOIN sale_items si ON si.product_id = p.id
               AND si.sale_id IN (
                   SELECT id FROM sales WHERE status = 'completed' AND timestamp >= :since
               )
           WHERE p.stock <= p.min_stock AND p.stock >= 0 AND p.is_active = 1
           GROUP BY p.id, p.name, p.stock, p.min_stock
           ORDER BY p.stock ASC LIMIT 10""",
        {"since": thirty_days_ago},
    )

    top_products = await db.fetch(
        """SELECT p.name, COUNT(*) as sales_count, COALESCE(SUM(si.subtotal), 0) as revenue
           FROM sale_items si
           JOIN products p ON si.product_id = p.id
           JOIN sales s ON si.sale_id = s.id
           WHERE s.status = 'completed'
           AND s.timestamp >= :since_date
           GROUP BY p.name
           ORDER BY sales_count DESC
           LIMIT 5""",
        {"since_date": thirty_days_ago},
    )

    return {
        "success": True,
        "data": {
            "alerts": [{
                "product_name": p["name"],
                "urgency": "CRITICAL" if float(p.get("stock") or 0) <= 2 else "WARNING",
                "current_stock": float(p.get("stock") or 0),
                "days_until_stockout": max(1, int(float(p.get("stock") or 0) / max(float(p.get("sold_30d") or 0) / 30, 0.01))),
                "recommended_order": int(float(p.get("min_stock") or 5) * 2),
            } for p in low_stock],
            "top_products": [{
                "name": t["name"],
                "sales_count": t["sales_count"],
                "revenue": money(t["revenue"]),
            } for t in top_products],
            "anomalies": [],
        },
    }


@router.get("/executive")
async def get_executive_dashboard(auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Dashboard ejecutivo (asyncpg). RBAC: admin/manager/owner."""
    if auth.get("role") not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="Sin permisos para ver este dashboard")

    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    tomorrow_start = today_start + timedelta(days=1)

    kpis = await db.fetchrow(
        """SELECT COUNT(*) as transactions,
                  COALESCE(SUM(total), 0) as revenue,
                  CASE WHEN COUNT(*) > 0 THEN COALESCE(SUM(total), 0) / COUNT(*) ELSE 0 END as avg_ticket
           FROM sales
           WHERE timestamp >= :today AND timestamp < :tomorrow AND status = 'completed'""",
        {"today": today_start, "tomorrow": tomorrow_start},
    )

    hourly = await db.fetch(
        """SELECT EXTRACT(HOUR FROM timestamp)::int as hour,
                  COUNT(*) as count, COALESCE(SUM(total), 0) as total
           FROM sales
           WHERE timestamp >= :today AND timestamp < :tomorrow AND status = 'completed'
           AND timestamp IS NOT NULL
           GROUP BY hour ORDER BY hour""",
        {"today": today_start, "tomorrow": tomorrow_start},
    )

    top = await db.fetch(
        """SELECT p.name, COUNT(*) as qty, COALESCE(SUM(si.subtotal), 0) as revenue
           FROM sale_items si
           JOIN products p ON si.product_id = p.id
           JOIN sales s ON si.sale_id = s.id
           WHERE s.timestamp >= :today AND s.timestamp < :tomorrow AND s.status = 'completed'
           GROUP BY p.name ORDER BY qty DESC LIMIT 5""",
        {"today": today_start, "tomorrow": tomorrow_start},
    )

    return {
        "success": True,
        "data": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "kpis": {
                "transactions": kpis["transactions"] if kpis else 0,
                "revenue": money(kpis["revenue"]) if kpis else 0.0,
                "avg_ticket": money(kpis["avg_ticket"]) if kpis else 0.0,
            },
            "hourly_sales": [{"hour": h["hour"], "count": h["count"], "total": money(h["total"])} for h in hourly],
            "top_products": [{"name": t["name"], "qty": t["qty"], "revenue": money(t["revenue"])} for t in top],
        },
    }
