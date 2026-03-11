"""POSVENDELO - Shared Constants & Money Helpers"""

from decimal import Decimal, ROUND_HALF_UP

PRIVILEGED_ROLES = ("admin", "manager", "owner")

# Orden de locks para evitar deadlocks (TURNS → SALES → PRODUCTS → CUSTOMERS).
# Documentado en AGENTS.md / CLAUDE.md; respetar en transacciones que toquen varias tablas.
LOCK_ORDER = ("turns", "sales", "products", "customers")

OWNER_ROLES = ("admin", "owner")
RESICO_ANNUAL_LIMIT = Decimal("3500000")
DEFAULT_TAX_RATE = Decimal("0.16")

SALE_STATUS_COMPLETED = "completed"
SALE_STATUS_CANCELLED = "cancelled"

TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


def dec(val) -> Decimal:
    """Convert any value to Decimal safely (for arithmetic)."""
    return Decimal(str(val)) if val is not None else Decimal("0")


def money(val, decimals: int = 2) -> str:
    """Decimal/DB value → string for JSON response, preserving precision."""
    if val is None:
        return "0.00" if decimals == 2 else f"0.{'0' * decimals}"
    places = TWO_PLACES if decimals == 2 else Decimal(f"0.{'0' * decimals}")
    return str(Decimal(str(val)).quantize(places, rounding=ROUND_HALF_UP))


def sanitize_row(row) -> dict:
    """Convert an asyncpg Record to dict, turning Decimal values to string for JSON precision."""
    if row is None:
        return {}
    d = dict(row)
    for key, val in d.items():
        if isinstance(val, Decimal):
            d[key] = str(val)
    return d


def sanitize_rows(rows) -> list[dict]:
    """Convert a list of asyncpg Records, turning Decimal values to string."""
    return [sanitize_row(r) for r in rows]
