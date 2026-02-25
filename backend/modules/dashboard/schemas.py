"""TITAN POS - Dashboard Module Schemas"""

from pydantic import BaseModel


class ResicoDashboard(BaseModel):
    serie_a: float
    serie_b: float
    total: float
    limite_resico: float = 3_500_000.0
    restante: float
    porcentaje: float
    proyeccion_anual: float
    status: str
    dias_restantes: int


class QuickStatus(BaseModel):
    ventas_hoy: int
    total_hoy: float
    mermas_pendientes: int
    timestamp: str


class ExpensesSummary(BaseModel):
    month: float
    year: float
