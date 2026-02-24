"""
Debug Logger Utility
Función centralizada para logging de debug que usa rutas dinámicas.
"""
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("DEBUG_LOGGER")

# Calcular ruta del proyecto dinámicamente
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
_DEBUG_LOG_PATH = _PROJECT_ROOT / '.cursor' / 'debug.log'

def get_debug_log_path() -> Path:
    """
    Obtiene la ruta del archivo de debug log.
    
    Usa ruta relativa al proyecto para evitar rutas hardcodeadas.
    
    Returns:
        Path al archivo de debug log
    """
    return _DEBUG_LOG_PATH

def log_debug(
    location: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    hypothesis_id: str = "A"
) -> None:
    """
    Log debug information to debug.log file.
    
    Args:
        location: Ubicación en el código (ej: "app/core.py:123")
        message: Mensaje descriptivo
        data: Datos adicionales (dict)
        hypothesis_id: ID de hipótesis para debugging
    """
    try:
        debug_path = get_debug_log_path()
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        
        log_entry = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000)
        }
        
        with open(debug_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            f.flush()
    except Exception as e:
        # No fallar si el logging falla
        logger.debug(f"Error writing debug log: {e}")
