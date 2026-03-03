"""
TITAN POS - Shared Turn Service

Funciones de dominio reutilizables para el módulo de turnos.
Encapsulan queries y cálculos compartidos entre turns/routes.py
y hardware/routes.py (reporte de turno).

Usage:
    from modules.shared.turn_service import calculate_turn_summary

    async with conn.transaction():
        summary = await calculate_turn_summary(turn_id, initial_cash, conn)
        expected = summary["expected_cash"]
"""

from decimal import Decimal, ROUND_HALF_UP


# ---------------------------------------------------------------------------
# Queries internas
# ---------------------------------------------------------------------------

_CASH_SALES_QUERY = """
    SELECT COALESCE(SUM(
        CASE WHEN payment_method = 'cash' THEN total
             WHEN payment_method = 'mixed' THEN COALESCE(mixed_cash, 0)
             ELSE 0
        END
    ), 0)
    FROM sales
    WHERE turn_id = $1 AND status = 'completed'
"""

_MOV_IN_QUERY = (
    "SELECT COALESCE(SUM(amount), 0) FROM cash_movements "
    "WHERE turn_id = $1 AND type = 'in'"
)

_MOV_OUT_QUERY = (
    "SELECT COALESCE(SUM(amount), 0) FROM cash_movements "
    "WHERE turn_id = $1 AND type IN ('out', 'expense')"
)

_SALES_BY_METHOD_QUERY = (
    "SELECT payment_method, COUNT(*) AS count, COALESCE(SUM(total), 0) AS total "
    "FROM sales WHERE turn_id = $1 AND status = 'completed' "
    "GROUP BY payment_method"
)


def _q(v) -> Decimal:
    """Convertir valor numérico de DB a Decimal con 2 decimales."""
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def calculate_turn_summary(turn_id: int, initial_cash, conn) -> dict:
    """Calcular el resumen financiero de un turno.

    Ejecuta las queries de efectivo, movimientos de caja y ventas para
    determinar el efectivo esperado al cierre del turno.

    Args:
        turn_id:      ID del turno a resumir.
        initial_cash: Efectivo inicial del turno (del row ``turns.initial_cash``).
        conn:         Conexión asyncpg raw (NO el wrapper db — pasar db.connection
                      o la ``conn`` de ``async with conn.transaction()``).

    Returns:
        dict con las siguientes claves (todos Decimal o float):
            - cash_sales      Decimal  Ventas cobradas en efectivo/mixto-cash
            - mov_in          Decimal  Suma de entradas de caja
            - mov_out         Decimal  Suma de salidas + gastos de caja
            - initial         Decimal  Efectivo inicial del turno
            - expected_cash   Decimal  initial + cash_sales + mov_in - mov_out
            - sales_count     int      Número total de ventas completadas
            - total_sales     Decimal  Suma total de ventas (todos los métodos)
            - sales_by_method list     Lista de dicts {payment_method, count, total}
    """
    # Queries paralelas donde el ORM permitiría gather — aquí asyncpg es secuencial
    # pero se mantiene la misma semántica que las implementaciones actuales.
    cash_sales_raw = await conn.fetchval(_CASH_SALES_QUERY, turn_id)
    movements_in_raw = await conn.fetchval(_MOV_IN_QUERY, turn_id)
    movements_out_raw = await conn.fetchval(_MOV_OUT_QUERY, turn_id)
    sales_by_method_rows = await conn.fetch(_SALES_BY_METHOD_QUERY, turn_id)

    # Convertir a Decimal con precisión monetaria
    initial = _q(initial_cash or 0)
    cash_sales = _q(cash_sales_raw)
    mov_in = _q(movements_in_raw)
    mov_out = _q(movements_out_raw)
    expected_cash = (initial + cash_sales + mov_in - mov_out).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # Calcular totales globales de ventas
    total_sales = sum(
        (_q(row["total"]) for row in sales_by_method_rows), Decimal("0")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sales_count = sum(int(row["count"]) for row in sales_by_method_rows)

    return {
        "cash_sales": cash_sales,
        "mov_in": mov_in,
        "mov_out": mov_out,
        "initial": initial,
        "expected_cash": expected_cash,
        "sales_count": sales_count,
        "total_sales": total_sales,
        "sales_by_method": [dict(row) for row in sales_by_method_rows],
    }
