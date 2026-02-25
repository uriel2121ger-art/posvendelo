"""
Multi-Emitter Module - Arquitectura Multi-RFC para RESICO
Permite facturar desde multiples RFCs para no exceder limite de $3.5M
"""

from typing import Any, Dict, List, Optional
from decimal import Decimal
import logging
from asyncpg.pool import Pool

logger = logging.getLogger(__name__)

class MultiEmitterManager:
    """
    Gestor de múltiples emisores RFC para régimen RESICO.

    Permite registrar múltiples RFCs y rotar automáticamente
    cuando se alcanza el límite de $3.5M anuales.
    """

    RESICO_ANNUAL_LIMIT = Decimal("3500000.00")

    def __init__(self, db_pool: Pool):
        self.db = db_pool

    async def register_emitter(self, rfc: str, legal_name: str, certificate_path: str = "", key_path: str = "", csd_password_encrypted: str = "", facturapi_api_key: str = "") -> Dict[str, Any]:
        """
        Registra un nuevo emisor RFC.
        """
        async with self.db.acquire() as conn:
            query = """
                INSERT INTO rfc_emitters (rfc, legal_name, certificate_path, key_path, csd_password_encrypted, facturapi_api_key, is_active, current_resico_amount)
                VALUES ($1, $2, $3, $4, $5, $6, true, 0)
                ON CONFLICT (rfc) DO UPDATE
                SET legal_name = EXCLUDED.legal_name,
                    certificate_path = EXCLUDED.certificate_path,
                    key_path = EXCLUDED.key_path,
                    csd_password_encrypted = EXCLUDED.csd_password_encrypted,
                    facturapi_api_key = EXCLUDED.facturapi_api_key,
                    is_active = true
                RETURNING id;
            """
            emitter_id = await conn.fetchval(query, rfc, legal_name, certificate_path, key_path, csd_password_encrypted, facturapi_api_key)
            return {"success": True, "emitter_id": emitter_id, "rfc": rfc}

    async def get_active_emitter(self) -> Optional[Dict[str, Any]]:
        """
        Obtiene el emisor activo primario (el de mayor capacidad restante que no exceda el límite).
        """
        async with self.db.acquire() as conn:
            query = """
                SELECT id, rfc, legal_name, certificate_path, key_path, facturapi_api_key, current_resico_amount
                FROM rfc_emitters
                WHERE is_active = true AND current_resico_amount < $1
                ORDER BY current_resico_amount ASC
                LIMIT 1;
            """
            row = await conn.fetchrow(query, self.RESICO_ANNUAL_LIMIT)
            if row:
                return dict(row)
            return None

    async def get_accumulated_amount(self, rfc: str) -> Decimal:
        """
        Obtiene el monto facturado acumulado para un RFC en el año fiscal.
        """
        async with self.db.acquire() as conn:
            query = "SELECT current_resico_amount FROM rfc_emitters WHERE rfc = $1"
            amount = await conn.fetchval(query, rfc)
            return Decimal(amount) if amount is not None else Decimal("0.00")

    async def select_optimal_rfc(self, amount: Decimal) -> Optional[Dict[str, Any]]:
        """
        Selecciona el RFC apropiado para una factura según el monto.
        Busca el RFC con mayor capacidad disponible que pueda alojar 'amount'.
        Retorna el diccionario completo del emisor, incluyendo facturapi_api_key.
        """
        async with self.db.acquire() as conn:
            query = """
                SELECT id, rfc, legal_name, certificate_path, key_path, facturapi_api_key, current_resico_amount
                FROM rfc_emitters
                WHERE is_active = true AND (current_resico_amount + $1) <= $2
                ORDER BY current_resico_amount ASC
                LIMIT 1;
            """
            row = await conn.fetchrow(query, amount, self.RESICO_ANNUAL_LIMIT)
            if row:
                return dict(row)
            return None

    async def list_emitters(self) -> List[Dict[str, Any]]:
        """
        Lista todos los emisores registrados con su estado.
        """
        async with self.db.acquire() as conn:
            query = """
                SELECT id, rfc, legal_name, is_active, current_resico_amount
                FROM rfc_emitters
                ORDER BY rfc;
            """
            rows = await conn.fetch(query)
            return [dict(r) for r in rows]

    async def update_accumulated_amount(self, rfc: str, additional_amount: Decimal) -> bool:
        """
        Incrementa el acumulado RESICO de un RFC tras emitir una factura.
        """
        async with self.db.acquire() as conn:
            query = """
                UPDATE rfc_emitters
                SET current_resico_amount = current_resico_amount + $1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE rfc = $2
                RETURNING id;
            """
            result = await conn.fetchval(query, additional_amount, rfc)
            return result is not None
