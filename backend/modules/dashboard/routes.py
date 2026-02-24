"""
TITAN POS - Dashboard Module Routes

SQL directo para resico/quick/expenses.
Wrappers asyncio.to_thread para wealth/ai/executive (legacy classes).
"""

import asyncio
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
    year = datetime.now().year

    result_a = await db.fetchrow(
        """SELECT COALESCE(SUM(total), 0) as total FROM sales
           WHERE serie = 'A' AND EXTRACT(YEAR FROM timestamp::timestamp) = :year
           AND status = 'completed'""",
        {"year": year},
    )
    facturado_a = float(result_a["total"]) if result_a else 0.0

    result_b = await db.fetchrow(
        """SELECT COALESCE(SUM(total), 0) as total FROM sales
           WHERE serie = 'B' AND EXTRACT(YEAR FROM timestamp::timestamp) = :year
           AND status = 'completed'""",
        {"year": year},
    )
    facturado_b = float(result_b["total"]) if result_b else 0.0

    limite = 3_500_000.0
    restante = limite - facturado_a
    porcentaje = (facturado_a / limite) * 100

    dias = (datetime.now() - datetime(year, 1, 1)).days
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
    today = datetime.now().strftime("%Y-%m-%d")

    sales = await db.fetchrow(
        """SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total
           FROM sales WHERE CAST(timestamp AS DATE) = CAST(:today AS DATE) AND status = 'completed'""",
        {"today": today},
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
    month_row = await db.fetchrow(
        """SELECT COALESCE(SUM(amount), 0) as total FROM cash_movements
           WHERE type = 'expense'
           AND TO_CHAR(timestamp::timestamp, 'YYYY-MM') = TO_CHAR(NOW(), 'YYYY-MM')"""
    )
    year_row = await db.fetchrow(
        """SELECT COALESCE(SUM(amount), 0) as total FROM cash_movements
           WHERE type = 'expense'
           AND EXTRACT(YEAR FROM timestamp::timestamp) = EXTRACT(YEAR FROM NOW())"""
    )

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

def _get_core():
    """Lazy load POSCore singleton (sync)."""
    from app.core import get_core_instance
    return get_core_instance()


@router.get("/wealth")
async def get_wealth_dashboard(auth: dict = Depends(verify_token)):
    """Dashboard de riqueza real. RBAC: admin/owner."""
    if auth.get("role") not in ("admin", "owner", "dueño"):
        raise HTTPException(status_code=403, detail="Solo admin/owner")

    try:
        def _run():
            from app.fiscal.wealth_dashboard import WealthDashboard
            core = _get_core()
            wealth = WealthDashboard(core)
            return wealth.get_real_wealth()

        data = await asyncio.to_thread(_run)

        return {
            "success": True,
            "data": {
                "ingresos_total": data["ingresos"]["total"],
                "serie_a": data["ingresos"]["serie_a"]["total"],
                "serie_b": data["ingresos"]["serie_b"]["total"],
                "gastos": data["gastos"]["total"],
                "impuestos": data["impuestos"]["total"],
                "utilidad_bruta": data["utilidad_bruta"],
                "utilidad_neta": data["utilidad_neta"],
                "disponible_retiro": data["disponible_retiro"],
                "ratio": data["ratio_utilidad"],
            },
        }
    except Exception as e:
        logger.error("WealthDashboard error: %s", e)
        raise HTTPException(status_code=500, detail="Error obteniendo dashboard de riqueza")


@router.get("/ai")
async def get_ai_dashboard(auth: dict = Depends(verify_token), db=Depends(get_db)):
    """Dashboard de IA — alertas de stock inteligentes. Fallback a SQL directo."""
    try:
        def _run():
            from app.utils.ai_analytics import AIAnalytics
            core = _get_core()
            ai = AIAnalytics(core)
            predictions = ai.predict_stockouts(7)
            alerts = [{
                "product_name": p.product_name,
                "urgency": p.urgency.value.upper(),
                "current_stock": p.current_stock,
                "days_until_stockout": p.days_until_stockout,
                "recommended_order": p.recommended_order,
            } for p in predictions[:10]]
            top = ai.get_smart_top_products(5)
            anomalies = [a.to_dict() for a in ai.detect_anomalies()]
            return {"alerts": alerts, "top_products": top, "anomalies": anomalies}

        data = await asyncio.to_thread(_run)
        return {"success": True, "data": data}
    except Exception:
        # Fallback: SQL directo
        low_stock = await db.fetch(
            """SELECT id, name, stock, min_stock FROM products
               WHERE stock <= min_stock AND stock >= 0 AND is_active = 1
               ORDER BY stock ASC LIMIT 10"""
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
                "top_products": [],
                "anomalies": [],
            },
        }


@router.get("/executive")
async def get_executive_dashboard(auth: dict = Depends(verify_token)):
    """Dashboard ejecutivo completo. RBAC: admin/manager/owner."""
    if auth.get("role") not in ("admin", "manager", "owner", "gerente", "dueño"):
        raise HTTPException(status_code=403, detail="Solo admin/manager")

    try:
        def _run():
            from app.utils.ai_analytics import AIAnalytics
            core = _get_core()
            ai = AIAnalytics(core)
            return ai.get_executive_dashboard()

        data = await asyncio.to_thread(_run)
        return {"success": True, "data": data}
    except Exception as e:
        logger.error("Executive dashboard error: %s", e)
        return {
            "success": False,
            "error": "Dashboard ejecutivo no disponible",
            "data": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "kpis": {"transactions": 0, "revenue": 0, "avg_ticket": 0},
                "hourly_sales": [],
                "comparison": {},
                "stock_predictions": [],
                "anomalies": [],
                "top_products": [],
            },
        }
