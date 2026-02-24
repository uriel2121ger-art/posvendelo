"""
TITAN POS - Machine Identifier Utility
Obtiene un identificador único para la PC/terminal actual.
"""

import os
import socket
import logging
import json
import time
from pathlib import Path
from typing import Optional

# FIX 2026-02-01: Import agent_log_enabled ANTES de usarla
try:
    from app.utils.path_utils import agent_log_enabled
except ImportError:
    def agent_log_enabled(): return False

logger = logging.getLogger(__name__)

# #region agent log
if agent_log_enabled():
    def _log_debug(session_id, run_id, hypothesis_id, location, message, data):
        try:
            from app.utils.path_utils import get_debug_log_path_str  # FIX: agent_log_enabled ya importado arriba
            log_path = get_debug_log_path_str()
            with open(log_path, "a") as f:
                f.write(json.dumps({
                    "sessionId": session_id,
                    "runId": run_id,
                    "hypothesisId": hypothesis_id,
                    "location": location,
                    "message": message,
                    "data": data,
                    "timestamp": int(time.time() * 1000)
                }) + "\n")
        except Exception as e:
            logger.debug("_log_debug write: %s", e)
# #endregion


def get_machine_identifier() -> str:
    """
    Obtiene un identificador único para esta PC/terminal.
    
    Prioridad:
    1. machine_id desde data/.machine_id (TITAN-XXXXX)
    2. hostname + terminal_id desde configuración
    3. hostname solamente
    4. "UNKNOWN-PC" como fallback
    
    Returns:
        str: Identificador único de la PC (ej: "TITAN-A1B2C3D4", "PC1-T1", "hostname-1")
    """
    # #region agent log
    if agent_log_enabled():
        _log_debug("debug-session", "run1", "REV1", "machine_identifier.py:get_machine_identifier", "Function entry", {})
    # #endregion
    
    # Método 1: Intentar leer machine_id persistente
    machine_id_file = Path("data/.machine_id")
    if machine_id_file.exists():
        try:
            with open(machine_id_file, 'r') as f:
                machine_id = f.read().strip()
                if machine_id:
                    # #region agent log
                    if agent_log_enabled():
                        _log_debug("debug-session", "run1", "REV1", "machine_identifier.py:get_machine_identifier", "Using machine_id from file", {"machine_id": machine_id, "method": "file"})
                    # #endregion
                    return machine_id
        except Exception as e:
            logger.debug(f"No se pudo leer machine_id: {e}")
            # #region agent log
            if agent_log_enabled():
                _log_debug("debug-session", "run1", "REV1", "machine_identifier.py:get_machine_identifier", "Error reading machine_id file", {"error": str(e)})
            # #endregion
    
    # Método 2: hostname + terminal_id desde configuración
    try:
        from app.core import get_core_instance, GlobalState
        
        core = get_core_instance()
        if core and core.db:
            cfg = core.get_app_config() or {}
            terminal_id = cfg.get("terminal_id", GlobalState().terminal_id)
            hostname = socket.gethostname()
            result = f"{hostname}-T{terminal_id}"
            # #region agent log
            if agent_log_enabled():
                _log_debug("debug-session", "run1", "REV1", "machine_identifier.py:get_machine_identifier", "Using hostname+terminal_id", {"hostname": hostname, "terminal_id": terminal_id, "result": result, "method": "config"})
            # #endregion
            return result
    except Exception as e:
        # #region agent log
        if agent_log_enabled():
            _log_debug("debug-session", "run1", "REV1", "machine_identifier.py:get_machine_identifier", "Error getting config", {"error": str(e)})
        # #endregion
        pass
    
    # Método 3: Solo hostname
    try:
        hostname = socket.gethostname()
        if hostname:
            # #region agent log
            if agent_log_enabled():
                _log_debug("debug-session", "run1", "REV1", "machine_identifier.py:get_machine_identifier", "Using hostname only", {"hostname": hostname, "method": "hostname"})
            # #endregion
            return hostname
    except Exception as e:
        # #region agent log
        if agent_log_enabled():
            _log_debug("debug-session", "run1", "REV1", "machine_identifier.py:get_machine_identifier", "Error getting hostname", {"error": str(e)})
        # #endregion
        pass
    
    # Fallback
    # #region agent log
    if agent_log_enabled():
        _log_debug("debug-session", "run1", "REV1", "machine_identifier.py:get_machine_identifier", "Using fallback", {"result": "UNKNOWN-PC", "method": "fallback"})
    # #endregion
    return "UNKNOWN-PC"


def get_machine_identifier_safe() -> str:
    """
    Versión segura que nunca falla.
    
    Returns:
        str: Identificador de PC, nunca None
    """
    try:
        return get_machine_identifier()
    except Exception as e:
        logger.warning(f"Error obteniendo machine identifier: {e}")
        return "UNKNOWN-PC"
