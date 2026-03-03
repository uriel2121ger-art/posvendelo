"""TITAN POS - Shared Constants"""

from decimal import Decimal

PRIVILEGED_ROLES = ("admin", "manager", "owner")
OWNER_ROLES = ("admin", "owner")
RESICO_ANNUAL_LIMIT = Decimal("3500000")
DEFAULT_TAX_RATE = Decimal("0.16")

SALE_STATUS_COMPLETED = "completed"
SALE_STATUS_CANCELLED = "cancelled"
