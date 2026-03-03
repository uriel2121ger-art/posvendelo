"""
Multi-Emitter Module - Arquitectura Multi-RFC para RESICO
"""

from typing import Any, Dict, List, Optional
from decimal import Decimal
import logging

from ..shared.constants import RESICO_ANNUAL_LIMIT

logger = logging.getLogger(__name__)


class MultiEmitterManager:
    RESICO_ANNUAL_LIMIT = RESICO_ANNUAL_LIMIT

    def __init__(self, db):
        self.db = db

    async def register_emitter(self, rfc: str, legal_name: str, certificate_path: str = "",
                                key_path: str = "", csd_password_encrypted: str = "",
                                facturapi_api_key: str = "") -> Dict[str, Any]:
        await self.db.execute("""
            INSERT INTO rfc_emitters (rfc, legal_name, certificate_path, key_path, csd_password_encrypted, facturapi_api_key, is_active, current_resico_amount)
            VALUES (:rfc, :name, :cert, :key, :csd, :fapi, true, 0)
            ON CONFLICT (rfc) DO UPDATE
            SET legal_name = EXCLUDED.legal_name, certificate_path = EXCLUDED.certificate_path,
                key_path = EXCLUDED.key_path, csd_password_encrypted = EXCLUDED.csd_password_encrypted,
                facturapi_api_key = EXCLUDED.facturapi_api_key, is_active = true
        """, rfc=rfc, name=legal_name, cert=certificate_path, key=key_path, csd=csd_password_encrypted, fapi=facturapi_api_key)
        return {"success": True, "rfc": rfc}

    async def get_active_emitter(self) -> Optional[Dict[str, Any]]:
        row = await self.db.fetchrow("""
            SELECT id, rfc, legal_name, certificate_path, key_path, facturapi_api_key, current_resico_amount
            FROM rfc_emitters WHERE is_active = true AND current_resico_amount < :limit
            ORDER BY current_resico_amount ASC LIMIT 1
        """, limit=self.RESICO_ANNUAL_LIMIT)
        return dict(row) if row else None

    async def get_accumulated_amount(self, rfc: str) -> Decimal:
        row = await self.db.fetchrow("SELECT current_resico_amount FROM rfc_emitters WHERE rfc = :rfc", rfc=rfc)
        return Decimal(row['current_resico_amount']) if row and row['current_resico_amount'] is not None else Decimal("0.00")

    async def select_optimal_rfc(self, amount: Decimal) -> Optional[Dict[str, Any]]:
        row = await self.db.fetchrow("""
            SELECT id, rfc, legal_name, certificate_path, key_path, facturapi_api_key, current_resico_amount
            FROM rfc_emitters WHERE is_active = true AND (current_resico_amount + :amt) <= :limit
            ORDER BY current_resico_amount ASC LIMIT 1
        """, amt=amount, limit=self.RESICO_ANNUAL_LIMIT)
        return dict(row) if row else None

    async def list_emitters(self) -> List[Dict[str, Any]]:
        rows = await self.db.fetch("SELECT id, rfc, legal_name, is_active, current_resico_amount FROM rfc_emitters ORDER BY rfc")
        return [dict(r) for r in rows]

    async def update_accumulated_amount(self, rfc: str, additional_amount: Decimal) -> bool:
        await self.db.execute("""
            UPDATE rfc_emitters SET current_resico_amount = current_resico_amount + :amt, updated_at = CURRENT_TIMESTAMP WHERE rfc = :rfc
        """, amt=additional_amount, rfc=rfc)
        return True
