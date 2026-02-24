"""
Database Configuration Loader
Carga configuración de base de datos desde archivo JSON
"""

import json
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("DB_CONFIG")

def load_database_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Carga configuración de base de datos desde archivo JSON.
    
    Args:
        config_path: Ruta al archivo de configuración. Si es None, busca en ubicaciones estándar.
        
    Returns:
        Diccionario con configuración de base de datos
    """
    # Ubicaciones estándar para buscar configuración
    default_paths = [
        "data/config/database.json",
        "data/local_config.json",
        "config/database.json",
    ]
    
    if config_path:
        paths_to_try = [config_path] + default_paths
    else:
        paths_to_try = default_paths
    
    for path in paths_to_try:
        config_file = Path(path)
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info(f"✅ Configuración cargada desde: {path}")
                return config
            except Exception as e:
                logger.warning(f"⚠️ Error leyendo {path}: {e}")
                continue
    
    # No hay configuración por defecto - PostgreSQL es requerido
    logger.error("❌ No se encontró configuración PostgreSQL")
    raise ValueError(
        "Configuración PostgreSQL no encontrada.\n"
        "PostgreSQL es requerido. Crea data/config/database.json con credenciales PostgreSQL.\n"
        "Ver docs/INSTALACION_POSTGRESQL.md para más información."
    )

def create_database_manager_from_config(
    config_path: Optional[str] = None
) -> Any:
    """
    Crea DatabaseManager PostgreSQL según configuración.
    
    Args:
        config_path: Ruta al archivo de configuración con credenciales PostgreSQL
        
    Returns:
        DatabaseManager instance con backend PostgreSQL
        
    Raises:
        ValueError: Si la configuración no está completa
        ConnectionError: Si no se puede conectar a PostgreSQL
    """
    # #region agent log
    import json, time
    try:
        from app.utils.path_utils import get_debug_log_path_str
        with open(get_debug_log_path_str(), "a") as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CREATE_DB_MANAGER_START","location":"database_config.py:create_database_manager_from_config","message":"Starting DatabaseManager creation","data":{"config_path":config_path},"timestamp":int(time.time()*1000)})+"\n")
    except Exception as e:
        logger.debug("Debug logging for DatabaseManager creation start failed: %s", e)
    # #endregion
    
    from src.infra.database_central import (
        PostgreSQLBackend,
        create_database_backend
    )
    from src.infra.database import DatabaseManager
    
    # Usar create_database_backend que ahora solo crea PostgreSQL
    try:
        backend = create_database_backend(config_path or "data/local_config.json")
        
        # #region agent log
        try:
            from app.utils.path_utils import get_debug_log_path_str
            with open(get_debug_log_path_str(), "a") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"BACKEND_CREATED_FOR_MANAGER","location":"database_config.py:create_database_manager_from_config","message":"Backend created, creating DatabaseManager","data":{},"timestamp":int(time.time()*1000)})+"\n")
        except Exception as e:
            logger.debug("Debug logging for backend created for manager failed: %s", e)
        # #endregion

        db_manager = DatabaseManager(backend=backend)
        
        # #region agent log
        try:
            from app.utils.path_utils import get_debug_log_path_str
            with open(get_debug_log_path_str(), "a") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"DB_MANAGER_CREATED","location":"database_config.py:create_database_manager_from_config","message":"DatabaseManager created successfully","data":{},"timestamp":int(time.time()*1000)})+"\n")
        except Exception as e:
            logger.debug("Debug logging for DatabaseManager creation success failed: %s", e)
        # #endregion

        return db_manager
    except Exception as e:
        # #region agent log
        try:
            from app.utils.path_utils import get_debug_log_path_str
            with open(get_debug_log_path_str(), "a") as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"DB_MANAGER_CREATE_FAILED","location":"database_config.py:create_database_manager_from_config","message":"DatabaseManager creation failed","data":{"error":str(e),"error_type":type(e).__name__},"timestamp":int(time.time()*1000)})+"\n")
        except Exception as log_e:
            logger.debug("Debug logging for DatabaseManager creation failure failed: %s", log_e)
        # #endregion
        logger.error(f"❌ Error creando DatabaseManager: {e}")
        raise
