"""POSVENDELO - Shared Constants & Money Helpers"""

from decimal import Decimal, ROUND_HALF_UP

PRIVILEGED_ROLES = ("admin", "manager", "owner")
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


def money(val, decimals: int = 2) -> float:
    """Decimal/DB value → float for JSON response, rounded to `decimals` places."""
    if val is None:
        return 0.0
    places = TWO_PLACES if decimals == 2 else Decimal(f"0.{'0' * decimals}")
    return float(Decimal(str(val)).quantize(places, rounding=ROUND_HALF_UP))
