"""
TITAN POS - Turn Repository (DEPRECATED)

Legacy re-export. Turn logic now lives in modules/turns/routes.py
using asyncpg direct queries. This file is kept for backward compatibility.
"""

try:
    from app.repositories.turn_repository import TurnRepository
except ImportError:
    TurnRepository = None  # type: ignore

__all__ = ["TurnRepository"]
