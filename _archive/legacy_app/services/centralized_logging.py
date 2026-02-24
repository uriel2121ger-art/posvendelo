"""
TITAN POS - Centralized Logging Service (REFACTORIZADO)

Usa BackgroundService para el loop de envío en batch.
"""

from typing import Any, Dict, List, Optional
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
import logging
import queue

try:
    import requests
except ImportError:
    requests = None

try:
    from app.utils.optimization import BackgroundService, with_retry
except ImportError:
    BackgroundService = object
    def with_retry(*args, **kwargs):
        def decorator(f): return f
        return decorator

logger = logging.getLogger(__name__)

class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class LogEntry:
    """Entrada de log para enviar al gateway."""
    level: str
    message: str
    module: str
    timestamp: str
    terminal_id: int
    branch_id: int
    extra: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class CentralizedLoggingService(BackgroundService):
    """
    Servicio de logs centralizados refactorizado.
    """
    
    def __init__(self, pos_core, config: Dict[str, Any]):
        self.core = pos_core
        self.config = config
        
        # Soporta central_url (nuevo) o central_server (legacy)
        self.gateway_url = config.get("central_url", "") or config.get("central_server", "")
        self.terminal_id = config.get("terminal_id", 1)
        self.branch_id = config.get("branch_id", 1)
        self.api_token = config.get("central_token", "") or config.get("api_token", "")
        
        self.min_level = config.get("log_min_level", "warning")
        self.batch_size = config.get("log_batch_size", 10)
        
        self._queue: queue.Queue = queue.Queue(maxsize=1000)
        self._level_priority = {"debug": 0, "info": 1, "warning": 2, "error": 3, "critical": 4}
        
        interval = config.get("log_flush_interval", 30)
        enabled = config.get("centralized_logging", True) and bool(self.gateway_url)
        
        super().__init__(
            name="CentralizedLogging",
            interval=interval,
            enabled=enabled,
            max_consecutive_errors=10
        )
    
    def _should_send(self, level: str) -> bool:
        """Verificar si el nivel cumple el umbral."""
        return self._level_priority.get(level.lower(), 0) >= self._level_priority.get(self.min_level, 2)
    
    def log(self, level: str, message: str, module: str = "unknown", extra: Dict = None):
        """Agregar log a la cola."""
        if not self._enabled or not self._should_send(level):
            return
        
        entry = LogEntry(
            level=level.lower(),
            message=message[:500],
            module=module,
            timestamp=datetime.now().isoformat(),
            terminal_id=self.terminal_id,
            branch_id=self.branch_id,
            extra=extra
        )
        
        try:
            self._queue.put_nowait(entry)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(entry)
            except queue.Empty:
                pass
    
    @with_retry(max_retries=2, base_delay=1.0, exceptions=(Exception,))
    def _send_batch(self, entries: List[LogEntry]) -> bool:
        """Enviar batch de logs al gateway con retry."""
        if not requests or not self.gateway_url or not entries:
            return False
        
        # gateway_url ya incluye protocolo y puerto
        base_url = self.gateway_url.rstrip('/')
        if not base_url.startswith('http'):
            base_url = f"http://{base_url}"
        url = f"{base_url}/api/v1/logs"
        
        payload = {
            "terminal_id": self.terminal_id,
            "branch_id": self.branch_id,
            "timestamp": datetime.now().isoformat(),
            "entries": [e.to_dict() for e in entries]
        }
        
        headers = {"Authorization": f"Bearer {self.api_token}"} if self.api_token else {}
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code == 200
    
    def _execute(self) -> bool:
        """Ejecutar flush de logs (llamado por BackgroundService)."""
        batch = []
        
        # Recolectar hasta batch_size logs
        while len(batch) < self.batch_size and not self._queue.empty():
            try:
                entry = self._queue.get_nowait()
                batch.append(entry)
            except queue.Empty:
                break
        
        if not batch:
            return True
        
        try:
            success = self._send_batch(batch)
            if not success:
                # Re-encolar primeros 5 en caso de fallo
                for entry in batch[:5]:
                    try:
                        self._queue.put_nowait(entry)
                    except queue.Full:
                        break  # Queue full, stop re-queuing
            return success
        except Exception as e:
            logger.debug(f"Error sending logs: {e}")
            return False
    
    def flush(self):
        """Forzar flush de todos los logs pendientes."""
        batch = []
        while not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break

        if batch:
            try:
                self._send_batch(batch)
            except Exception:
                pass  # Best effort flush

class CentralizedLogHandler(logging.Handler):
    """
    Handler de Python logging que envía logs al servicio centralizado.
    """
    
    def __init__(self, central_logger: CentralizedLoggingService):
        super().__init__()
        self.central_logger = central_logger
        
    def emit(self, record: logging.LogRecord):
        try:
            self.central_logger.log(
                level=record.levelname.lower(),
                message=self.format(record),
                module=record.module,
                extra={"lineno": record.lineno, "funcName": record.funcName}
            )
        except Exception:
            pass  # Logging handler should never raise

def create_centralized_logger(pos_core, config: Dict[str, Any]) -> Optional[CentralizedLoggingService]:
    """Factory function."""
    mode = config.get("db_mode", "standalone")
    
    if mode not in ("hybrid", "client"):
        return None
    
    gateway = config.get("central_url", "") or config.get("central_server", "")
    if not gateway:
        return None
    
    try:
        return CentralizedLoggingService(pos_core, config)
    except Exception as e:
        logger.error(f"Failed to create centralized logger: {e}")
        return None

# Alias para compatibilidad
CentralizedLogger = CentralizedLoggingService
