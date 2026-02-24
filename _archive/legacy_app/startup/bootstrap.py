"""
TITAN POS - Bootstrap Module

Application initialization: paths, logging, and environment setup.
"""

import logging
import os
from pathlib import Path
import sys
import traceback

# Get project root directory dynamically
_SCRIPT_DIR = Path(__file__).resolve().parent.parent  # app/
try:
    _PROJECT_ROOT = _SCRIPT_DIR.parent  # project root
except Exception:
    _PROJECT_ROOT = Path.cwd()  # Fallback to current directory

try:
    _DEBUG_LOG_PATH = _PROJECT_ROOT / '.cursor' / 'debug.log'
except Exception:
    _DEBUG_LOG_PATH = Path.home() / '.titan_pos_debug.log'

# Ensure src is in path (src is at project root, not in app/)
_logger = logging.getLogger(__name__)
try:
    if (_PROJECT_ROOT / 'src').exists():
        sys.path.insert(0, str(_PROJECT_ROOT / 'src'))
    # Also try app/src in case of different structure
    elif (_SCRIPT_DIR / 'src').exists():
        sys.path.insert(0, str(_SCRIPT_DIR / 'src'))
except Exception as e:
    _logger.debug("Path detection: %s", e)

# --- Path Utilities ---
def get_data_dir():
    """
    Get the data directory for TITAN POS.
    
    Tries multiple methods to find the data directory:
    1. From src.utils.paths if available
    2. From environment variable TITAN_DATA_DIR
    3. Relative to project root (where data/ folder should be)
    4. Current working directory as fallback
    """
    # Try importing from src.utils.paths first
    try:
        from src.utils.paths import get_data_dir as _get_data_dir
        return _get_data_dir()
    except (ImportError, AttributeError, ModuleNotFoundError):
        pass
    
    # Try environment variable
    env_data_dir = os.environ.get("TITAN_DATA_DIR")
    if env_data_dir:
        return env_data_dir
    
    # Try relative to project root (where data/ folder should be)
    try:
        # _PROJECT_ROOT is already calculated above
        # Calculate it again here in case it wasn't available at module level
        if '_PROJECT_ROOT' in globals() and _PROJECT_ROOT:
            data_dir = _PROJECT_ROOT / "data"
            if data_dir.exists():
                return str(_PROJECT_ROOT)
        else:
            # Recalculate if not available
            script_dir = Path(__file__).resolve().parent.parent.parent
            data_dir = script_dir / "data"
            if data_dir.exists():
                return str(script_dir)
    except (AttributeError, Exception):
        pass
    
    # Fallback to current working directory
    return os.getcwd()

def resource_path(p):
    """Get absolute path for a resource."""
    return os.path.abspath(p)

# --- Core Paths ---
# CRITICAL: Always assign DATA_DIR, even if get_data_dir() fails
# This prevents ImportError when importing from app.startup
try:
    DATA_DIR = get_data_dir()
except Exception as e:
    # Log the error for debugging
    try:
        error_log = Path.home() / 'titan_pos_bootstrap_error.log'
        with open(error_log, 'a') as f:
            f.write(f"Error in get_data_dir() at {__file__}:\n")
            f.write(f"Exception: {type(e).__name__}: {e}\n")
            f.write(f"Traceback:\n{traceback.format_exc()}\n")
            f.write(f"Working directory: {os.getcwd()}\n")
            f.write(f"_PROJECT_ROOT: {_PROJECT_ROOT}\n")
            f.write(f"_SCRIPT_DIR: {_SCRIPT_DIR}\n")
            f.write("-" * 60 + "\n")
    except Exception as log_e:
        _logger.debug("Bootstrap error log write: %s", log_e)
    
    # Ultimate fallback: use current working directory
    # This ensures DATA_DIR is ALWAYS defined, preventing ImportError
    DATA_DIR = os.getcwd()

# Now that DATA_DIR is guaranteed to exist, define dependent paths
try:
    DB_PATH = os.path.join(DATA_DIR, "data/databases/pos.db")
    CONFIG_PATH = os.path.join(DATA_DIR, "data/config/config.json")
except Exception as e:
    _logger.debug("DB_PATH/CONFIG_PATH setup: %s", e)
    DB_PATH = os.path.join(DATA_DIR, "pos.db")
    CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

ASSETS_DIR = _SCRIPT_DIR / "assets"
ICON_DIR = ASSETS_DIR / "icons"

# --- Offline Queue Paths ---
OFFLINE_QUEUE_FILE = Path(DATA_DIR) / "data/temp/offline_sales_queue.json"
OFFLINE_INVENTORY_QUEUE_FILE = Path(DATA_DIR) / "data/temp/offline_inventory_queue.json"


def init_logging() -> logging.Logger:
    """
    Initialize application logging with rotation.

    Returns:
        Logger instance for the application.
    """
    try:
        from app.utils.logging_config import init_logging as _init_logging
        from app.utils.logging_config import setup_rotating_logger
        _init_logging()
    except ImportError:
        # Fallback to basic config
        log_dir = os.path.join(DATA_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)
        logging.basicConfig(
            filename=os.path.join(log_dir, "titan_pos.log"),
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    return logging.getLogger(__name__)


def log_debug(
    location: str,
    message: str,
    data: dict = None,
    hypothesis_id: str = "A"
) -> None:
    """
    Log debug information to debug.log file.

    Used for development instrumentation and debugging.

    Args:
        location: Code location identifier (e.g., "module:function:line")
        message: Debug message
        data: Optional dictionary with additional data
        hypothesis_id: Debug session identifier
    """
    try:
        _DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        import json
        import time

        log_entry = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000)
        }

        with open(_DEBUG_LOG_PATH, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
            f.flush()
    except Exception as e:
        _logger.debug("log_write failed: %s", e)


def check_optional_imports() -> dict:
    """
    Check availability of optional dependencies.

    Returns:
        Dictionary with import availability flags.
    """
    result = {
        "has_charts": False,
        "has_backup_engine": False,
    }

    try:
        from PyQt6 import QtCharts
        result["has_charts"] = True
    except ImportError:
        print("Warning: QtCharts not found. Charts will be disabled.")

    try:
        from app.utils.backup_engine import BackupEngine
        result["has_backup_engine"] = True
    except ImportError:
        pass

    return result
