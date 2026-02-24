"""
TITAN POS - Utilidades Comunes de Optimización

Este módulo contiene clases y funciones base reutilizables para
eliminar duplicación de código en los servicios.
"""

from typing import Any, Callable, Dict, Optional
from abc import ABC, abstractmethod
from datetime import datetime
import functools
import logging
import threading
import time

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CLASE BASE PARA SERVICIOS EN SEGUNDO PLANO
# ═══════════════════════════════════════════════════════════════════════════════

class BackgroundService(ABC):
    """
    Clase base abstracta para servicios que corren en segundo plano.
    
    Elimina la duplicación de código en:
    - TerminalHeartbeat
    - StockAlertService
    - CentralizedLogger
    
    Características:
    - Start/Stop con thread daemon
    - Loop con intervalo configurable
    - Conteo de errores consecutivos
    - Última ejecución exitosa
    """
    
    def __init__(self, 
                 name: str,
                 interval: int = 60,
                 enabled: bool = True,
                 max_consecutive_errors: int = 10):
        """
        Initialize background service.
        
        Args:
            name: Nombre del servicio para logging
            interval: Segundos entre ejecuciones
            enabled: Si el servicio está habilitado
            max_consecutive_errors: Máximo de errores antes de pausar
        """
        self._name = name
        self._interval = interval
        self._enabled = enabled
        self._max_errors = max_consecutive_errors

        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_success: Optional[datetime] = None
        self._consecutive_errors = 0
        self._total_runs = 0
        self._total_errors = 0
        
    @abstractmethod
    def _execute(self) -> bool:
        """
        Ejecutar la tarea principal del servicio.
        
        Returns:
            True si fue exitoso, False si hubo error
        """
        pass
    
    def _on_success(self):
        """Hook llamado después de una ejecución exitosa."""
        pass
    
    def _on_error(self, error: Exception):
        """Hook llamado después de un error."""
        pass
    
    def _loop(self):
        """Loop principal del servicio."""
        logger.info(f"🚀 {self._name} iniciado (intervalo: {self._interval}s)")

        while True:
            with self._lock:
                if not self._running:
                    break
                self._total_runs += 1

            try:
                success = self._execute()

                with self._lock:
                    if success:
                        self._last_success = datetime.now()
                        self._consecutive_errors = 0
                        self._on_success()
                    else:
                        self._consecutive_errors += 1
                        self._total_errors += 1

            except Exception as e:
                with self._lock:
                    self._consecutive_errors += 1
                    self._total_errors += 1
                logger.error(f"{self._name} error: {e}")
                self._on_error(e)

            # Pausar si hay demasiados errores
            with self._lock:
                consecutive_errors = self._consecutive_errors
                max_errors = self._max_errors

            if consecutive_errors >= max_errors:
                pause_time = min(self._interval * 5, 300)
                logger.warning(f"{self._name}: {consecutive_errors} errores, pausando {pause_time}s")
                time.sleep(pause_time)
                with self._lock:
                    self._consecutive_errors = 0
            else:
                time.sleep(self._interval)

        logger.info(f"🛑 {self._name} detenido")
    
    def start(self):
        """Iniciar el servicio en segundo plano."""
        if not self._enabled:
            logger.info(f"{self._name} deshabilitado")
            return

        with self._lock:
            if self._running:
                logger.warning(f"{self._name} ya está corriendo")
                return
            self._running = True

        self._thread = threading.Thread(
            target=self._loop,
            name=f"Thread-{self._name}",
            daemon=True
        )
        self._thread.start()

    def stop(self):
        """Detener el servicio."""
        with self._lock:
            self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del servicio."""
        return {
            "name": self._name,
            "running": self._running,
            "enabled": self._enabled,
            "interval": self._interval,
            "total_runs": self._total_runs,
            "total_errors": self._total_errors,
            "consecutive_errors": self._consecutive_errors,
            "last_success": self._last_success.isoformat() if self._last_success else None,
            "error_rate": round(self._total_errors / self._total_runs, 3) if self._total_runs > 0 else 0
        }
    
    @property
    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        if not self._running:
            return False
        if not self._last_success:
            return self._consecutive_errors < 3
        elapsed = (datetime.now() - self._last_success).total_seconds()
        return elapsed < (self._interval * 5)

# ═══════════════════════════════════════════════════════════════════════════════
# DECORADOR DE RETRY CON BACKOFF EXPONENCIAL
# ═══════════════════════════════════════════════════════════════════════════════

def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    Decorador para reintentar funciones con backoff exponencial.
    
    Args:
        max_retries: Número máximo de reintentos
        base_delay: Delay inicial en segundos
        max_delay: Delay máximo en segundos
        exponential_base: Base para el cálculo exponencial
        exceptions: Tupla de excepciones a capturar
        on_retry: Callback opcional llamado en cada retry
        
    Usage:
        @with_retry(max_retries=3, base_delay=1.0)
        def send_data():
            response = requests.post(url, data=data)
            response.raise_for_status()
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        delay = min(base_delay * (exponential_base ** attempt), max_delay)
                        
                        if on_retry:
                            on_retry(e, attempt + 1)
                        else:
                            logger.debug(f"{func.__name__} retry {attempt + 1}/{max_retries} in {delay:.1f}s: {e}")
                        
                        time.sleep(delay)
                    else:
                        raise
            
            raise last_exception
        
        return wrapper
    return decorator

def with_retry_async(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Versión async del decorador de retry."""
    import asyncio
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        delay = min(base_delay * (exponential_base ** attempt), max_delay)
                        logger.debug(f"{func.__name__} retry {attempt + 1}/{max_retries}")
                        await asyncio.sleep(delay)
                    else:
                        raise
            
            raise last_exception
        
        return wrapper
    return decorator

# ═══════════════════════════════════════════════════════════════════════════════
# CACHE CON EXPIRACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

class TTLCache:
    """
    Cache simple con Time-To-Live (TTL).
    
    Thread-safe y con limpieza automática de entradas expiradas.
    """
    
    def __init__(self, default_ttl: int = 60, max_size: int = 1000):
        """
        Initialize cache.
        
        Args:
            default_ttl: TTL por defecto en segundos
            max_size: Tamaño máximo del cache
        """
        self._cache: Dict[str, tuple] = {}  # key -> (value, expiry_time)
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if time.time() < expiry:
                    self._hits += 1
                    return value
                else:
                    del self._cache[key]
            
            self._misses += 1
            return default
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache."""
        with self._lock:
            # Cleanup if too large
            if len(self._cache) >= self._max_size:
                self._cleanup()
            
            expiry = time.time() + (ttl or self._default_ttl)
            self._cache[key] = (value, expiry)
    
    def delete(self, key: str):
        """Delete key from cache."""
        with self._lock:
            self._cache.pop(key, None)
    
    def clear(self):
        """Clear all cache."""
        with self._lock:
            self._cache.clear()
    
    def _cleanup(self):
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, (_, exp) in self._cache.items() if exp <= now]
        for k in expired:
            del self._cache[k]
        
        # If still too large, remove oldest
        if len(self._cache) >= self._max_size:
            sorted_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k][1])
            for k in sorted_keys[:len(self._cache) // 4]:
                del self._cache[k]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 3) if total > 0 else 0
        }

# ═══════════════════════════════════════════════════════════════════════════════
# CIRCUIT BREAKER PATTERN
# ═══════════════════════════════════════════════════════════════════════════════

class CircuitBreaker:
    """
    Implementación del patrón Circuit Breaker para evitar
    llamadas repetidas a servicios caídos.
    
    Estados:
    - CLOSED: Normal operation
    - OPEN: Failing, reject calls immediately
    - HALF_OPEN: Testing if service recovered
    """
    
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
    
    def __init__(self,
                 name: str,
                 failure_threshold: int = 5,
                 recovery_timeout: int = 30,
                 half_open_max_calls: int = 3):
        """
        Initialize circuit breaker.
        
        Args:
            name: Name for logging
            failure_threshold: Failures before opening
            recovery_timeout: Seconds before trying half-open
            half_open_max_calls: Calls allowed in half-open state
        """
        self._name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls
        
        self._state = self.CLOSED
        self._failures = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = threading.Lock()
    
    def can_execute(self) -> bool:
        """Check if call is allowed."""
        with self._lock:
            if self._state == self.CLOSED:
                return True
            
            if self._state == self.OPEN:
                if self._last_failure_time and \
                   (time.time() - self._last_failure_time) > self._recovery_timeout:
                    self._state = self.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info(f"CircuitBreaker {self._name}: OPEN -> HALF_OPEN")
                    return True
                return False
            
            if self._state == self.HALF_OPEN:
                return self._half_open_calls < self._half_open_max_calls
            
            return False
    
    def record_success(self):
        """Record a successful call."""
        with self._lock:
            if self._state == self.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self._half_open_max_calls:
                    self._state = self.CLOSED
                    self._failures = 0
                    logger.info(f"CircuitBreaker {self._name}: HALF_OPEN -> CLOSED")
            else:
                self._failures = 0
    
    def record_failure(self):
        """Record a failed call."""
        with self._lock:
            self._failures += 1
            self._last_failure_time = time.time()
            
            if self._state == self.HALF_OPEN:
                self._state = self.OPEN
                logger.warning(f"CircuitBreaker {self._name}: HALF_OPEN -> OPEN")
            elif self._failures >= self._failure_threshold:
                self._state = self.OPEN
                logger.warning(f"CircuitBreaker {self._name}: CLOSED -> OPEN")
    
    @property
    def state(self) -> str:
        return self._state
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "name": self._name,
            "state": self._state,
            "failures": self._failures,
            "failure_threshold": self._failure_threshold
        }

# ═══════════════════════════════════════════════════════════════════════════════
# RATE LIMITER SIMPLE
# ═══════════════════════════════════════════════════════════════════════════════

class SimpleRateLimiter:
    """
    Rate limiter simple usando token bucket algorithm.
    """
    
    def __init__(self, rate: float, capacity: int):
        """
        Initialize rate limiter.
        
        Args:
            rate: Tokens per second
            capacity: Maximum tokens (burst)
        """
        self._rate = rate
        self._capacity = capacity
        self._tokens = capacity
        self._last_update = time.time()
        self._lock = threading.Lock()
    
    def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens.
        
        Returns:
            True if acquired, False if rate limited
        """
        with self._lock:
            now = time.time()
            elapsed = now - self._last_update
            self._last_update = now
            
            # Add tokens based on elapsed time
            self._tokens = min(
                self._capacity,
                self._tokens + (elapsed * self._rate)
            )
            
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            
            return False
    
    def wait_for_token(self, tokens: int = 1, timeout: float = 10.0) -> bool:
        """Wait until tokens are available."""
        deadline = time.time() + timeout
        
        while time.time() < deadline:
            if self.acquire(tokens):
                return True
            time.sleep(0.1)
        
        return False
