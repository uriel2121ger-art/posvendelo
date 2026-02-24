"""
TITAN POS - SAT Catalog Module Routes

Wraps sat_catalog_full.py (SQLite-based) with asyncio.to_thread.
No asyncpg needed — the SAT catalog lives in its own SQLite DB.
"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)
router = APIRouter()


# Common SAT codes fallback for when the catalog is unavailable
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
):
    """Search SAT catalog by code or description. No auth required."""
    try:
        def _search():
            from modules.sat.sat_catalog import search_sat_catalog
            return search_sat_catalog(q, limit=limit)

        results = await asyncio.to_thread(_search)

        return {
            "success": True,
            "data": {
                "results": [{"code": code, "description": desc} for code, desc in results],
                "total": len(results),
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
async def get_sat_code_info(code: str):
    """Get SAT code description. No auth required."""
    try:
        def _get():
            from modules.sat.sat_catalog import get_sat_description
            return get_sat_description(code)

        description = await asyncio.to_thread(_get)

        if description:
            return {"success": True, "data": {"code": code, "description": description}}
        return {"success": False, "data": {"code": code, "description": "No existe en el catalogo"}}
    except Exception as e:
        logger.warning("SAT catalog lookup fallback: %s", e)
        return {"success": False, "data": {"code": code, "description": "No existe en el catalogo"}}
