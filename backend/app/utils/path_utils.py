"""
Utility functions for path management.
Provides dynamic path resolution to avoid hardcoded paths.
"""
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Cache for workspace root
_workspace_root = None
_debug_log_path = None

def get_workspace_root() -> Path:
    """
    Get the workspace root directory dynamically.
    
    This function determines the workspace root by:
    1. Checking CURSOR_WORKSPACE_ROOT environment variable
    2. Looking for .cursor directory (Cursor workspace marker)
    3. Using __file__ to find project root (fallback)
    
    Returns:
        Path: Absolute path to workspace root
    """
    global _workspace_root
    
    if _workspace_root is not None:
        return _workspace_root
    
    # Method 1: Environment variable (set by Cursor)
    env_root = os.environ.get('CURSOR_WORKSPACE_ROOT')
    if env_root:
        _workspace_root = Path(env_root).resolve()
        logger.debug(f"Workspace root from env: {_workspace_root}")
        return _workspace_root
    
    # Method 2: Find .cursor directory (Cursor workspace marker)
    # Start from current file and walk up the directory tree
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / '.cursor').exists():
            _workspace_root = parent
            logger.debug(f"Workspace root from .cursor: {_workspace_root}")
            return _workspace_root
    
    # Method 3: Fallback to parent of app/utils (project root)
    # This assumes app/utils/path_utils.py is in the project
    # app/utils/path_utils.py -> app/utils -> app -> project root
    _workspace_root = Path(__file__).resolve().parent.parent.parent
    logger.debug(f"Workspace root from __file__: {_workspace_root}")
    return _workspace_root

def get_debug_log_path() -> Path:
    """
    Get the path to the debug log file.
    
    Returns:
        Path: Absolute path to .cursor/debug.log
    """
    global _debug_log_path
    
    if _debug_log_path is not None:
        return _debug_log_path
    
    workspace_root = get_workspace_root()
    debug_dir = workspace_root / '.cursor'
    # Crear directorio si no existe
    try:
        debug_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning(f"Could not create .cursor directory: {e}")
    
    _debug_log_path = debug_dir / 'debug.log'
    return _debug_log_path

def get_debug_log_path_str() -> str:
    """
    Get the path to the debug log file as a string.
    
    Returns:
        str: Absolute path to .cursor/debug.log as string
    """
    return str(get_debug_log_path())


def agent_log_enabled() -> bool:
    """
    Issue 10: Instrumentación #region agent log.
    Devuelve True solo si se quiere escribir logs de depuración (hypothesisId, etc.).
    Por defecto False: no se escribe a disco, evitando I/O y ruido.
    Para activar en depuración: AGENT_DEBUG=1 o AGENT_DEBUG=true.
    """
    return os.environ.get("AGENT_DEBUG", "").strip().lower() in ("1", "true", "yes")
