"""
Sync Configuration - Configuración de sincronización optimizada para escala

Optimizado para manejar 20k+ productos con:
- Sync incremental
- Paginación
- Compresión
- Índices optimizados
- Caché local
"""

# =============================================================================
# CONFIGURACIÓN DE SYNC
# =============================================================================

SYNC_CONFIG = {
    # Tamaño de lote para paginación
    "batch_size": 500,  # Productos por lote (ajustar según ancho de banda)
    
    # Compresión
    "use_compression": True,  # gzip para payloads grandes
    "compression_threshold": 10240,  # 10KB - comprimir si es mayor
    
    # Sync incremental
    "incremental_only": True,  # Solo sincronizar cambios desde última sync
    "max_sync_age_hours": 24,  # Re-sincronizar completa cada 24h (fallback)
    
    # Timeouts
    "timeout_seconds": 30,  # Timeout por lote
    "connection_timeout": 10,  # Timeout de conexión
    
    # Caché local
    "cache_enabled": True,
    "cache_ttl_seconds": 300,  # 5 minutos
    
    # Límites (B.3: unificado con http_server/sync_endpoints 50000)
    "max_records_per_sync": 50000,
    "max_batch_retries": 3,  # Reintentos por lote fallido
    
    # Backoff exponencial para reintentos
    "backoff_base": 2,  # 2, 4, 8 segundos
    "max_backoff_seconds": 60,
}

# =============================================================================
# CONFIGURACIÓN POR TABLA
# =============================================================================

TABLE_SYNC_CONFIG = {
    "products": {
        "batch_size": 500,
        "priority": 1,
        "max_records": 50000,
    },
    "customers": {
        "batch_size": 1000,
        "priority": 2,
        "max_records": 50000,
    },
    "sales": {
        "batch_size": 200,
        "priority": 1,
        "max_records": 50000,
    },
    "employees": {
        "batch_size": 1000,
        "priority": 3,
        "max_records": 1000,
    },
}

# =============================================================================
# FUNCIONES HELPER
# =============================================================================

def get_batch_size(table_name: str) -> int:
    """Retorna el tamaño de lote para una tabla."""
    return TABLE_SYNC_CONFIG.get(table_name, {}).get("batch_size", SYNC_CONFIG["batch_size"])


def should_compress(payload_size: int) -> bool:
    """Determina si un payload debe comprimirse."""
    return (
        SYNC_CONFIG["use_compression"] and
        payload_size > SYNC_CONFIG["compression_threshold"]
    )


def get_timeout(table_name: str) -> int:
    """Retorna el timeout para una tabla."""
    return SYNC_CONFIG["timeout_seconds"]


def get_max_records(table_name: str) -> int:
    """Retorna el máximo de registros para una tabla."""
    return TABLE_SYNC_CONFIG.get(table_name, {}).get("max_records", SYNC_CONFIG["max_records_per_sync"])
