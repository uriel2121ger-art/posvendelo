"""
TITAN POS - Configuración de Logging con Rotación
==================================================
Configura logging con rotación automática de archivos.
"""

from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import os

# Directorio de logs
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')

# Asegurar que existe
os.makedirs(LOGS_DIR, exist_ok=True)

# Formato de logs
LOG_FORMAT = '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

def setup_rotating_logger(
    name: str,
    filename: str = None,
    level: int = logging.INFO,
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB por archivo
    backup_count: int = 5  # Mantener 5 archivos de backup
) -> logging.Logger:
    """
    Configura un logger con rotación por tamaño.
    
    Args:
        name: Nombre del logger
        filename: Nombre del archivo de log
        level: Nivel de logging
        max_bytes: Tamaño máximo antes de rotar (default 5MB)
        backup_count: Número de archivos de backup a mantener
    
    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Evitar duplicados
    if logger.handlers:
        return logger
    
    # Archivo de log
    if filename is None:
        filename = f"{name.lower().replace(' ', '_')}.log"
    
    log_path = os.path.join(LOGS_DIR, filename)
    
    # Handler con rotación por tamaño
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    file_handler.setLevel(level)
    
    # Handler de consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    console_handler.setLevel(logging.WARNING)  # Solo warnings+ a consola
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def setup_daily_logger(
    name: str,
    filename: str = None,
    level: int = logging.INFO,
    backup_count: int = 30  # Mantener 30 días
) -> logging.Logger:
    """
    Configura un logger con rotación diaria.
    
    Args:
        name: Nombre del logger
        filename: Nombre del archivo de log
        level: Nivel de logging
        backup_count: Número de días a mantener
    
    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if logger.handlers:
        return logger
    
    if filename is None:
        filename = f"{name.lower().replace(' ', '_')}.log"
    
    log_path = os.path.join(LOGS_DIR, filename)
    
    # Handler con rotación diaria a medianoche
    file_handler = TimedRotatingFileHandler(
        log_path,
        when='midnight',
        interval=1,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    file_handler.setLevel(level)
    
    logger.addHandler(file_handler)
    
    return logger

# Loggers pre-configurados para módulos principales
def get_pos_logger():
    """Logger para operaciones POS."""
    return setup_rotating_logger('POS', 'pos_operations.log')

def get_sales_logger():
    """Logger para ventas."""
    return setup_rotating_logger('SALES', 'sales.log')

def get_security_logger():
    """Logger para eventos de seguridad."""
    return setup_rotating_logger('SECURITY', 'security.log', level=logging.WARNING)

def get_error_logger():
    """Logger para errores del sistema."""
    return setup_rotating_logger('ERRORS', 'errors.log', level=logging.ERROR)

def get_audit_logger():
    """Logger para auditoría."""
    return setup_daily_logger('AUDIT', 'audit.log')

# Inicialización al importar
_initialized = False

def init_logging():
    """Inicializa el sistema de logging."""
    global _initialized
    if _initialized:
        return
    
    # Configurar logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Crear archivo principal
    main_log = os.path.join(LOGS_DIR, 'titan_pos.log')
    main_handler = RotatingFileHandler(
        main_log,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10,
        encoding='utf-8'
    )
    main_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root_logger.addHandler(main_handler)
    
    _initialized = True
    logging.info("Sistema de logging inicializado con rotación")

# Auto-inicializar
init_logging()
