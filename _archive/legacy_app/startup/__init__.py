"""
TITAN POS - Startup Module

Handles application initialization, crash handling, and single instance control.
"""

# Import essential items from bootstrap (always required)
from .bootstrap import (
    ASSETS_DIR,
    CONFIG_PATH,
    DATA_DIR,
    DB_PATH,
    ICON_DIR,
    OFFLINE_INVENTORY_QUEUE_FILE,
    OFFLINE_QUEUE_FILE,
    init_logging,
    log_debug,
)

# Import optional modules (may not exist in all installations)
try:
    from .crash_handler import install_crash_handler, log_crash
except ImportError:
    # Fallback if crash_handler doesn't exist
    def install_crash_handler():
        pass
    
    def log_crash(exc_type, exc_value, exc_traceback):
        pass

try:
    from .single_instance import SingleInstanceGuard
except ImportError:
    # Fallback if single_instance doesn't exist
    class SingleInstanceGuard:
        def __init__(self, *args, **kwargs):
            pass
        
        @classmethod
        def create(cls, *args, **kwargs):
            return cls()
        
        @staticmethod
        def check_or_exit(*args, **kwargs):
            """Fallback: always allow instance (no single instance enforcement)."""
            return SingleInstanceGuard()

__all__ = [
    "DATA_DIR",
    "DB_PATH",
    "CONFIG_PATH",
    "ASSETS_DIR",
    "ICON_DIR",
    "OFFLINE_QUEUE_FILE",
    "OFFLINE_INVENTORY_QUEUE_FILE",
    "init_logging",
    "log_debug",
    "install_crash_handler",
    "log_crash",
    "SingleInstanceGuard",
]
