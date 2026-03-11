"""POSVENDELO - Dashboard Module Schemas"""

from decimal import Decimal
from pydantic import BaseModel

from modules.shared.constants import RESICO_ANNUAL_LIMIT


class ResicoDashboard(BaseModel):
    serie_a: Decimal
    serie_b: Decimal
    total: Decimal
    limite_resico: Decimal = RESICO_ANNUAL_LIMIT
    restante: Decimal
    porcentaje: Decimal
    proyeccion_anual: Decimal
    status: str
    dias_restantes: int


class QuickStatus(BaseModel):
    ventas_hoy: int
    total_hoy: Decimal
    mermas_pendientes: int
    timestamp: str


class ExpensesSummary(BaseModel):
    month: Decimal
    year: Decimal
