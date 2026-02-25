"""
TITAN POS - SAT Catalog Module Routes

Queries sat_clave_prod_serv table in PostgreSQL via asyncpg.
Falls back to embedded _COMMON_CODES if table is unavailable.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from db.connection import get_db
from modules.shared.auth import verify_token

logger = logging.getLogger(__name__)
router = APIRouter()

# Fallback codes for when sat_clave_prod_serv table is unavailable
_COMMON_CODES = [
    ("01010101", "No existe en el catalogo"),
    ("53131500", "Productos para el cuidado de la piel"),
    ("53131600", "Productos para el cabello"),
    ("53131700", "Perfumes y fragancias"),
    ("53131900", "Productos de maquillaje"),
    ("53132000", "Productos de higiene personal"),
    ("50181900", "Dulces y chocolates"),
    ("50192100", "Bebidas"),
]


@router.get("/search")
async def search_sat_codes(
    q: str = Query(..., min_length=2),
    limit: int = Query(20, ge=1, le=100),
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Search SAT catalog by code or description."""
    try:
        from modules.sat.sat_catalog import search_sat_codes as _search

        rows = await _search(db, q, limit=limit)
        return {
            "success": True,
            "data": {
                "results": [
                    {"code": r["clave"], "description": r["descripcion"]}
                    for r in rows
                ],
                "total": len(rows),
            },
        }
    except Exception as e:
        logger.warning("SAT catalog search fallback: %s", e)
        q_lower = q.lower()
        filtered = [
            {"code": code, "description": desc}
            for code, desc in _COMMON_CODES
            if q_lower in code.lower() or q_lower in desc.lower()
        ][:limit]
        return {
            "success": True,
            "data": {"results": filtered, "total": len(filtered), "fallback": True},
        }


@router.get("/{code}")
async def get_sat_code_info(
    code: str,
    auth: dict = Depends(verify_token),
    db=Depends(get_db),
):
    """Get SAT code description by key."""
    try:
        from modules.sat.sat_catalog import get_sat_description

        description = await get_sat_description(db, code)
        if description:
            return {"success": True, "data": {"code": code, "description": description}}
        raise HTTPException(status_code=404, detail="Codigo SAT no encontrado")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("SAT catalog lookup fallback: %s", e)
        raise HTTPException(status_code=404, detail="Codigo SAT no encontrado")
