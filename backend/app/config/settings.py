"""
TITAN POS - Configuración Centralizada

Todas las constantes y configuraciones en un solo lugar.
"""

from typing import Any, Dict, Optional
from dataclasses import dataclass, field
import os
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# RUTAS DEL SISTEMA
# ═══════════════════════════════════════════════════════════════════════════════

# Detectar directorio base
if os.environ.get("TITAN_BASE_DIR"):
    BASE_DIR = Path(os.environ["TITAN_BASE_DIR"])
else:
    BASE_DIR = Path(__file__).parent.parent.parent

DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
BACKUPS_DIR = BASE_DIR / "backups"
TEMP_DIR = BASE_DIR / "temp"

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DEL GATEWAY
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class GatewaySettings:
    """Configuración del Gateway central."""
    
    # Servidor
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    log_level: str = "info"
    
    # Autenticación
    admin_token: str = ""  # MUST be configured, empty = disabled
    token_expiry_days: int = 365
    
    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_rpm: int = 60  # Requests per minute
    rate_limit_burst: int = 20
    
    # Almacenamiento
    max_heartbeats: int = 1000
    max_alerts: int = 5000
    max_logs: int = 10000
    heartbeat_timeout: int = 180  # Seconds before terminal is "offline"
    
    # Cache
    cache_enabled: bool = True
    cache_ttl: int = 60  # Seconds
    
    # Persistencia
    persist_data: bool = True
    db_path: str = "gateway_data/gateway.db"
    min_client_version: str = "1.0.0"
    reject_incompatible_clients: bool = True

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE TERMINALES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TerminalSettings:
    """Configuración de una terminal POS."""
    
    # Identificación
    terminal_id: int = 1
    terminal_name: str = "Terminal 1"
    branch_id: int = 1
    branch_name: str = "Sucursal Principal"
    
    # Gateway
    gateway_url: str = ""
    gateway_port: int = 8000
    api_token: str = ""
    
    # Modo de operación
    db_mode: str = "client"  # standalone, hybrid, client
    enforce_server_only_db: bool = True
    
    # Heartbeat
    heartbeat_enabled: bool = True
    heartbeat_interval: int = 60  # Seconds
    
    # Stock alerts
    stock_alerts_enabled: bool = True
    stock_alert_interval: int = 300  # Seconds
    critical_stock_threshold: float = 0.25  # 25% of min
    
    # Centralized logging
    centralized_logging: bool = True
    log_min_level: str = "warning"
    log_batch_size: int = 10
    log_flush_interval: int = 30  # Seconds
    
    # HTTP Server
    http_server_enabled: bool = True
    http_server_port: int = 5555

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE SINCRONIZACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass  
class SyncSettings:
    """Configuración de sincronización."""
    
    # Intervalos
    sync_interval: int = 300  # Seconds
    full_sync_interval: int = 3600  # Hourly full sync
    
    # Compresión
    compression_enabled: bool = True
    compression_min_size: int = 1024  # Bytes
    compression_level: int = 6
    
    # Retry
    max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0
    
    # Batch
    batch_size: int = 100

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE BACKUP
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BackupSettings:
    """Configuración de backups."""
    
    # Auto backup
    auto_backup_enabled: bool = True
    auto_backup_hour: int = 3  # 3 AM
    retention_days: int = 30
    
    # Destinos
    local_backup_dir: str = "backups"
    remote_backup_enabled: bool = False
    remote_backup_path: str = ""
    
    # Contenido
    include_database: bool = True
    include_config: bool = True
    include_logs: bool = False
    compress: bool = True

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE SEGURIDAD
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SecuritySettings:
    """Configuración de seguridad."""
    
    # Sesiones
    session_timeout: int = 28800  # 8 hours
    max_login_attempts: int = 5
    lockout_duration: int = 900  # 15 minutes
    
    # Passwords
    min_password_length: int = 6
    require_password_change: int = 0  # Days, 0 = disabled
    
    # API
    api_rate_limit: int = 100  # Requests per minute
    # SECURITY: HTTPS should be enabled in production
    # Set TITAN_REQUIRE_HTTPS=true in environment for production
    require_https: bool = os.getenv("TITAN_REQUIRE_HTTPS", "false").lower() == "true"

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN MAESTRA
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Settings:
    """Configuración maestra que agrupa todas las configuraciones."""
    
    gateway: GatewaySettings = field(default_factory=GatewaySettings)
    terminal: TerminalSettings = field(default_factory=TerminalSettings)
    sync: SyncSettings = field(default_factory=SyncSettings)
    backup: BackupSettings = field(default_factory=BackupSettings)
    security: SecuritySettings = field(default_factory=SecuritySettings)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        from dataclasses import asdict
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Settings':
        """Create from dictionary."""
        return cls(
            gateway=GatewaySettings(**data.get("gateway", {})),
            terminal=TerminalSettings(**data.get("terminal", {})),
            sync=SyncSettings(**data.get("sync", {})),
            backup=BackupSettings(**data.get("backup", {})),
            security=SecuritySettings(**data.get("security", {}))
        )

# ═══════════════════════════════════════════════════════════════════════════════
# INSTANCIA GLOBAL
# ═══════════════════════════════════════════════════════════════════════════════

_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """Get global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

def configure(config: Dict[str, Any]):
    """Update settings from config dictionary."""
    global _settings
    _settings = Settings.from_dict(config)

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES DE LA APLICACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

# Versión
APP_VERSION = "6.3.5"
APP_NAME = "TITAN POS"
APP_AUTHOR = "TITAN Systems"

# Database
DEFAULT_DB_NAME = "titan_pos.db"
SCHEMA_VERSION = 35

# UI
DEFAULT_THEME = "dark"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800

# Tickets
DEFAULT_TICKET_WIDTH = 80
DEFAULT_FONT_SIZE = 12

# Inventario
LOW_STOCK_THRESHOLD = 0.25
OUT_OF_STOCK_THRESHOLD = 0

# Moneda
CURRENCY_SYMBOL = "$"
CURRENCY_CODE = "MXN"
TAX_RATE = 0.16

# Formatos
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
TIME_FORMAT = "%H:%M:%S"
