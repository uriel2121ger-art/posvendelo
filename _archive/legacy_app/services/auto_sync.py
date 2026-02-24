"""
Auto Sync Service - Sincronización automática en background
Maneja la sincronización periódica con el servidor central
"""

import logging

logger = logging.getLogger(__name__)


def start_auto_sync(core):
    """
    Inicia el servicio de sincronización automática.
    
    Esta función redirige a la implementación exhaustiva del auto-sync.
    
    Args:
        core: POSCore instance
        
    Returns:
        True si se inició correctamente, False en caso contrario
    """
    try:
        # Intentar usar la implementación exhaustiva
        from app.services.auto_sync_exhaustivo import start_auto_sync as start_auto_sync_exhaustive
        return start_auto_sync_exhaustive(core)
    except ImportError as e:
        logger.warning(f"Could not import exhaustive auto-sync implementation: {e}")
        logger.info("Auto-sync service not available (stub implementation)")
        return False
    except Exception as e:
        logger.error(f"Error starting auto-sync: {e}")
        return False
def stop_auto_sync():
    """
    Detiene el servicio de sincronización automática.
    
    Returns:
        True si se detuvo correctamente, False en caso contrario
    """
    try:
        from app.services.auto_sync_exhaustivo import stop_auto_sync as stop_auto_sync_exhaustive
        return stop_auto_sync_exhaustive()
    except ImportError:
        logger.debug("Auto-sync service not available (stub implementation)")
        return False
    except Exception as e:
        logger.error(f"Error stopping auto-sync: {e}")
        return False