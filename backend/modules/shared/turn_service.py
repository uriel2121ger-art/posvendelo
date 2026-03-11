"""
POSVENDELO - Shared Turn Service

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

_SALES_QUERY = """
    SELECT
        COALESCE(SUM(
            CASE WHEN payment_method = 'cash' THEN total
                 WHEN payment_method = 'mixed' THEN COALESCE(mixed_cash, 0)
                 ELSE 0
            END
        ), 0) AS cash_sales,
        COALESCE(SUM(total), 0) AS total_sales
    FROM sales
    WHERE turn_id = $1 AND status = 'completed'
"""

_SALES_BY_METHOD_QUERY = (
    "SELECT payment_method, COUNT(*) AS count, COALESCE(SUM(total), 0) AS total "
    "FROM sales WHERE turn_id = $1 AND status = 'completed' "
    "GROUP BY payment_method"
)

_MOVEMENTS_QUERY = """
    SELECT
        COALESCE(SUM(CASE WHEN type = 'in' THEN amount ELSE 0 END), 0) AS mov_in,
        COALESCE(SUM(CASE WHEN type IN ('out', 'expense') THEN amount ELSE 0 END), 0) AS mov_out
    FROM cash_movements
    WHERE turn_id = $1
"""


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
    # 2 queries instead of 4: one for sales aggregates, one for cash movement aggregates
    sales_row = await conn.fetchrow(_SALES_QUERY, turn_id)
    movements_row = await conn.fetchrow(_MOVEMENTS_QUERY, turn_id)
    sales_by_method_rows = await conn.fetch(_SALES_BY_METHOD_QUERY, turn_id)

    # Convertir a Decimal con precisión monetaria
    initial = _q(initial_cash or 0)
    cash_sales = _q(sales_row["cash_sales"])
    total_sales_raw = _q(sales_row["total_sales"])
    mov_in = _q(movements_row["mov_in"])
    mov_out = _q(movements_row["mov_out"])
    expected_cash = (initial + cash_sales + mov_in - mov_out).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # Calcular totales globales de ventas desde sales_by_method (para sales_count)
    total_sales = total_sales_raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
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
