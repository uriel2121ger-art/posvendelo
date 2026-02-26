"""TITAN POS - Dashboard Module Schemas"""

from decimal import Decimal
from pydantic import BaseModel


class ResicoDashboard(BaseModel):
    serie_a: Decimal
    serie_b: Decimal
    total: Decimal
    limite_resico: Decimal = Decimal("3500000")
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
