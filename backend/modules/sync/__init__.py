"""
TITAN POS - Sync Module

Bounded context for data synchronization:
- HTTP sync endpoints (routes.py) — used by frontend posApi.ts
- Multi-branch sync engine (service.py) — DEPRECATED legacy
- Auto-sync scheduling (auto_sync.py) — DEPRECATED legacy
"""

# Legacy re-exports with safe fallback
try:
    from modules.sync.service import SyncEngine
except Exception:
    SyncEngine = None  # type: ignore[assignment,misc]

try:
    from modules.sync.auto_sync import AutoSync
except Exception:
    AutoSync = None  # type: ignore[assignment,misc]

__all__ = [
    "SyncEngine",
    "AutoSync",
]
