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

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# SQL directo (asyncpg)
# ============================================================================

@router.get("/resico")
async def get_resico_dashboard(auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Dashboard de monitoreo RESICO - acumulado anual serie A vs B."""
    year = datetime.now(timezone.utc).year
    year_start = f"{year}-01-01"
    year_end = f"{year + 1}-01-01"

    result = await db.fetchrow(
        """SELECT
             COALESCE(SUM(CASE WHEN serie = 'A' THEN total ELSE 0 END), 0) as total_a,
             COALESCE(SUM(CASE WHEN serie = 'B' THEN total ELSE 0 END), 0) as total_b
           FROM sales
           WHERE timestamp >= :year_start AND timestamp < :year_end
           AND status = 'completed'""",
        {"year_start": year_start, "year_end": year_end},
    )
    facturado_a = round(float(result["total_a"]), 2) if result else 0.0
    facturado_b = round(float(result["total_b"]), 2) if result else 0.0

    limite = 3_500_000.0
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
            "porcentaje": round(porcentaje, 2),
            "proyeccion_anual": round(proyeccion, 2),
            "status": status,
            "dias_restantes": 365 - dias,
        },
    }


@router.get("/quick")
async def get_quick_status(auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Quick status widget — ventas hoy, mermas pendientes."""
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    sales = await db.fetchrow(
        """SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total
           FROM sales WHERE timestamp >= :today AND timestamp < :tomorrow
           AND status = 'completed'""",
        {"today": today_str, "tomorrow": tomorrow_str},
    )

    mermas = await db.fetchrow(
        "SELECT COUNT(*) as c FROM loss_records WHERE status = 'pending'"
    )

    return {
        "success": True,
        "data": {
            "ventas_hoy": sales["count"] if sales else 0,
            "total_hoy": round(float(sales["total"]), 2) if sales else 0.0,
            "mermas_pendientes": mermas["c"] if mermas else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.get("/expenses")
async def get_expenses_dashboard(auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Dashboard de gastos en efectivo — mes y anio."""
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
            "month": round(float(month_row["total"]), 2) if month_row else 0.0,
            "year": round(float(year_row["total"]), 2) if year_row else 0.0,
        },
    }


# ============================================================================
# Wrappers asyncio.to_thread (legacy classes)
# ============================================================================

@router.get("/wealth")
async def get_wealth_dashboard(auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Dashboard de riqueza real (asyncpg). RBAC: admin/owner."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Solo gerentes/admin")

    try:
        now = datetime.now(timezone.utc)
        # sales.timestamp is TEXT — use strings
        year_start_str = f"{now.year}-01-01"
        year_end_str = f"{now.year + 1}-01-01"
        # cash_movements.timestamp is TIMESTAMP WITHOUT TIME ZONE — use naive datetimes
        year_start_ts = datetime(now.year, 1, 1)
        year_end_ts = datetime(now.year + 1, 1, 1)

        # Ingresos por serie
        income = await db.fetchrow(
            """SELECT
                   COALESCE(SUM(CASE WHEN serie = 'A' THEN total ELSE 0 END), 0) as serie_a,
                   COALESCE(SUM(CASE WHEN serie = 'B' THEN total ELSE 0 END), 0) as serie_b,
                   COALESCE(SUM(total), 0) as total
               FROM sales
               WHERE timestamp >= :year_start AND timestamp < :year_end
               AND status = 'completed'""",
            {"year_start": year_start_str, "year_end": year_end_str},
        )

        # Gastos
        try:
            expenses = await db.fetchrow(
                """SELECT COALESCE(SUM(amount), 0) as total FROM cash_movements
                   WHERE type IN ('out', 'expense')
                   AND timestamp >= :year_start AND timestamp < :year_end""",
                {"year_start": year_start_ts, "year_end": year_end_ts},
            )
        except Exception as e:
            logger.warning("Error consultando gastos wealth: %s", e)
            expenses = None

        ingresos = round(float(income["total"]) if income else 0.0, 2)
        serie_a = round(float(income["serie_a"]) if income else 0.0, 2)
        serie_b = round(float(income["serie_b"]) if income else 0.0, 2)
        gastos = round(float(expenses["total"]) if expenses else 0.0, 2)
        impuestos = round(serie_a - serie_a / 1.16, 2)  # IVA extraido de precio IVA-incluido
        utilidad_bruta = round(ingresos - gastos, 2)
        utilidad_neta = round(utilidad_bruta - impuestos, 2)
        disponible = round(max(0.0, utilidad_neta), 2)
        ratio = round((utilidad_neta / ingresos * 100) if ingresos > 0 else 0.0, 2)

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
    thirty_days_ago_ts = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
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
        {"since": thirty_days_ago_ts},
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
        {"since_date": thirty_days_ago_ts},
    )

    return {
        "success": True,
        "data": {
            "alerts": [{
                "product_name": p["name"],
                "urgency": "CRITICAL" if round(float(p.get("stock") or 0), 2) <= 2 else "WARNING",
                "current_stock": round(float(p.get("stock") or 0), 2),
                "days_until_stockout": max(1, int(float(p.get("stock") or 0) / max(float(p.get("sold_30d") or 0) / 30, 0.01))),
                "recommended_order": int(float(p.get("min_stock") or 5) * 2),
            } for p in low_stock],
            "top_products": [{
                "name": t["name"],
                "sales_count": t["sales_count"],
                "revenue": round(float(t["revenue"]), 2),
            } for t in top_products],
            "anomalies": [],
        },
    }


@router.get("/executive")
async def get_executive_dashboard(auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Dashboard ejecutivo (asyncpg). RBAC: admin/manager/owner."""
    if auth.get("role") not in ("admin", "manager", "owner"):
        raise HTTPException(status_code=403, detail="Solo admin/manager")

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    kpis = await db.fetchrow(
        """SELECT COUNT(*) as transactions,
                  COALESCE(SUM(total), 0) as revenue,
                  CASE WHEN COUNT(*) > 0 THEN COALESCE(SUM(total), 0) / COUNT(*) ELSE 0 END as avg_ticket
           FROM sales
           WHERE timestamp >= :today AND timestamp < :tomorrow AND status = 'completed'""",
        {"today": today_str, "tomorrow": tomorrow_str},
    )

    hourly = await db.fetch(
        """SELECT CAST(SUBSTRING(timestamp FROM 12 FOR 2) AS int) as hour,
                  COUNT(*) as count, COALESCE(SUM(total), 0) as total
           FROM sales
           WHERE timestamp >= :today AND timestamp < :tomorrow AND status = 'completed'
           AND LENGTH(timestamp) >= 13
           GROUP BY hour ORDER BY hour""",
        {"today": today_str, "tomorrow": tomorrow_str},
    )

    top = await db.fetch(
        """SELECT p.name, COUNT(*) as qty, COALESCE(SUM(si.subtotal), 0) as revenue
           FROM sale_items si
           JOIN products p ON si.product_id = p.id
           JOIN sales s ON si.sale_id = s.id
           WHERE s.timestamp >= :today AND s.timestamp < :tomorrow AND s.status = 'completed'
           GROUP BY p.name ORDER BY qty DESC LIMIT 5""",
        {"today": today_str, "tomorrow": tomorrow_str},
    )

    return {
        "success": True,
        "data": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "kpis": {
                "transactions": kpis["transactions"] if kpis else 0,
                "revenue": round(float(kpis["revenue"]), 2) if kpis else 0.0,
                "avg_ticket": round(float(kpis["avg_ticket"]), 2) if kpis else 0.0,
            },
            "hourly_sales": [{"hour": h["hour"], "count": h["count"], "total": round(float(h["total"]), 2)} for h in hourly],
            "top_products": [{"name": t["name"], "qty": t["qty"], "revenue": round(float(t["revenue"]), 2)} for t in top],
        },
    }
