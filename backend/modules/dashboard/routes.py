"""
TITAN POS - Dashboard Module Routes

SQL directo para resico/quick/expenses.
Wrappers asyncio.to_thread para wealth/ai/executive (legacy classes).
"""

import logging
from datetime import datetime, timezone

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
    facturado_a = float(result["total_a"]) if result else 0.0
    facturado_b = float(result["total_b"]) if result else 0.0

    limite = 3_500_000.0
    restante = limite - facturado_a
    porcentaje = (facturado_a / limite) * 100

    dias = (datetime.now(timezone.utc) - datetime(year, 1, 1, tzinfo=timezone.utc)).days
    dias = max(dias, 1)
    proyeccion = (facturado_a / dias) * 365

    if porcentaje < 70:
        status = "GREEN"
    elif porcentaje < 90:
        status = "YELLOW"
    else:
        status = "RED"

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
    sales = await db.fetchrow(
        """SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total
           FROM sales WHERE timestamp >= CURRENT_DATE::text
           AND timestamp < (CURRENT_DATE + 1)::text AND status = 'completed'"""
    )

    mermas = await db.fetchrow(
        "SELECT COUNT(*) as c FROM loss_records WHERE status = 'pending'"
    )

    return {
        "success": True,
        "data": {
            "ventas_hoy": sales["count"] if sales else 0,
            "total_hoy": float(sales["total"]) if sales else 0.0,
            "mermas_pendientes": mermas["c"] if mermas else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.get("/expenses")
async def get_expenses_dashboard(auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Dashboard de gastos en efectivo — mes y anio."""
    now = datetime.now(timezone.utc)
    month_start = f"{now.year}-{now.month:02d}-01"
    if now.month == 12:
        month_end = f"{now.year + 1}-01-01"
    else:
        month_end = f"{now.year}-{now.month + 1:02d}-01"
    year_start = f"{now.year}-01-01"
    year_end = f"{now.year + 1}-01-01"

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
    except Exception:
        month_row = None
        year_row = None

    return {
        "success": True,
        "data": {
            "month": float(month_row["total"]) if month_row else 0.0,
            "year": float(year_row["total"]) if year_row else 0.0,
        },
    }


# ============================================================================
# Wrappers asyncio.to_thread (legacy classes)
# ============================================================================

@router.get("/wealth")
async def get_wealth_dashboard(auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Dashboard de riqueza real (asyncpg). RBAC: admin/owner."""
    if auth.get("role") not in ("admin", "manager", "owner", "gerente", "dueño"):
        raise HTTPException(status_code=403, detail="Solo gerentes/admin")

    try:
        year = datetime.now(timezone.utc).year
        year_start = f"{year}-01-01"
        year_end = f"{year + 1}-01-01"

        # Ingresos por serie
        income = await db.fetchrow(
            """SELECT
                   COALESCE(SUM(CASE WHEN serie = 'A' THEN total ELSE 0 END), 0) as serie_a,
                   COALESCE(SUM(CASE WHEN serie = 'B' THEN total ELSE 0 END), 0) as serie_b,
                   COALESCE(SUM(total), 0) as total
               FROM sales
               WHERE timestamp >= :year_start AND timestamp < :year_end
               AND status = 'completed'""",
            {"year_start": year_start, "year_end": year_end},
        )

        # Gastos
        try:
            expenses = await db.fetchrow(
                """SELECT COALESCE(SUM(amount), 0) as total FROM cash_movements
                   WHERE type IN ('out', 'expense')
                   AND timestamp >= :year_start AND timestamp < :year_end""",
                {"year_start": year_start, "year_end": year_end},
            )
        except Exception:
            expenses = None

        ingresos = float(income["total"]) if income else 0.0
        serie_a = float(income["serie_a"]) if income else 0.0
        serie_b = float(income["serie_b"]) if income else 0.0
        gastos = float(expenses["total"]) if expenses else 0.0
        impuestos = round(serie_a - serie_a / 1.16, 2)  # IVA extraido de precio IVA-incluido
        utilidad_bruta = ingresos - gastos
        utilidad_neta = utilidad_bruta - impuestos
        disponible = max(0.0, utilidad_neta)
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
    low_stock = await db.fetch(
        """SELECT id, name, stock, min_stock FROM products
           WHERE stock <= min_stock AND stock >= 0 AND is_active = 1
           ORDER BY stock ASC LIMIT 10"""
    )

    top_products = await db.fetch(
        """SELECT p.name, COUNT(*) as sales_count, COALESCE(SUM(si.subtotal), 0) as revenue
           FROM sale_items si
           JOIN products p ON si.product_id = p.id
           JOIN sales s ON si.sale_id = s.id
           WHERE s.status = 'completed'
           AND s.timestamp >= to_char(NOW() - INTERVAL '30 days', 'YYYY-MM-DD')
           GROUP BY p.name
           ORDER BY sales_count DESC
           LIMIT 5"""
    )

    return {
        "success": True,
        "data": {
            "alerts": [{
                "product_name": p["name"],
                "urgency": "CRITICAL" if float(p.get("stock") or 0) <= 2 else "WARNING",
                "current_stock": float(p.get("stock") or 0),
                "days_until_stockout": max(1, int(float(p.get("stock") or 0))),
                "recommended_order": int((float(p.get("min_stock") or 5)) * 2),
            } for p in low_stock],
            "top_products": [{
                "name": t["name"],
                "sales_count": t["sales_count"],
                "revenue": float(t["revenue"]),
            } for t in top_products],
            "anomalies": [],
        },
    }


@router.get("/executive")
async def get_executive_dashboard(auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Dashboard ejecutivo (asyncpg). RBAC: admin/manager/owner."""
    if auth.get("role") not in ("admin", "manager", "owner", "gerente", "dueño"):
        raise HTTPException(status_code=403, detail="Solo admin/manager")

    kpis = await db.fetchrow(
        """SELECT COUNT(*) as transactions,
                  COALESCE(SUM(total), 0) as revenue,
                  CASE WHEN COUNT(*) > 0 THEN COALESCE(SUM(total), 0) / COUNT(*) ELSE 0 END as avg_ticket
           FROM sales
           WHERE timestamp >= CURRENT_DATE::text AND timestamp < (CURRENT_DATE + 1)::text AND status = 'completed'"""
    )

    hourly = await db.fetch(
        """SELECT EXTRACT(HOUR FROM timestamp::timestamp)::int as hour,
                  COUNT(*) as count, COALESCE(SUM(total), 0) as total
           FROM sales
           WHERE timestamp >= CURRENT_DATE::text AND timestamp < (CURRENT_DATE + 1)::text AND status = 'completed'
           GROUP BY hour ORDER BY hour"""
    )

    top = await db.fetch(
        """SELECT p.name, COUNT(*) as qty, COALESCE(SUM(si.subtotal), 0) as revenue
           FROM sale_items si
           JOIN products p ON si.product_id = p.id
           JOIN sales s ON si.sale_id = s.id
           WHERE s.timestamp >= CURRENT_DATE::text AND s.timestamp < (CURRENT_DATE + 1)::text AND s.status = 'completed'
           GROUP BY p.name ORDER BY qty DESC LIMIT 5"""
    )

    return {
        "success": True,
        "data": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "kpis": {
                "transactions": kpis["transactions"] if kpis else 0,
                "revenue": float(kpis["revenue"]) if kpis else 0.0,
                "avg_ticket": float(kpis["avg_ticket"]) if kpis else 0.0,
            },
            "hourly_sales": [{"hour": h["hour"], "count": h["count"], "total": float(h["total"])} for h in hourly],
            "top_products": [{"name": t["name"], "qty": t["qty"], "revenue": float(t["revenue"])} for t in top],
        },
    }
