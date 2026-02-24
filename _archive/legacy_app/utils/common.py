"""
TITAN POS - Utilidades Comunes
Centraliza funciones y decoradores reutilizables
"""

from typing import Any, Callable, Optional
from datetime import datetime
import functools
import logging
import time

# Cache simple para consultas frecuentes
# FIX 2026-02-01: WARNING: Not thread-safe - usar solo en contextos single-threaded
_cache = {}
_cache_ttl = {}

def cached(ttl_seconds: int = 60):
    """
    Decorador para cachear resultados de funciones.
    
    Uso:
        @cached(ttl_seconds=300)
        def get_products():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Crear key único
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Verificar cache
            now = time.time()
            if key in _cache and key in _cache_ttl:
                if now - _cache_ttl[key] < ttl_seconds:
                    return _cache[key]
            
            # Ejecutar y cachear
            result = func(*args, **kwargs)
            _cache[key] = result
            _cache_ttl[key] = now
            return result
        return wrapper
    return decorator

def clear_cache():
    """Limpia todo el cache."""
    global _cache, _cache_ttl
    _cache = {}
    _cache_ttl = {}

def logged(logger_name: str = "TITAN"):
    """
    Decorador para logging automático de funciones.
    
    Uso:
        @logged("SALES")
        def process_sale(amount):
            ...
    """
    def decorator(func: Callable) -> Callable:
        logger = logging.getLogger(logger_name)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            func_name = func.__name__
            
            try:
                result = func(*args, **kwargs)
                elapsed = (time.time() - start) * 1000
                logger.debug(f"{func_name} completed in {elapsed:.1f}ms")
                return result
            except Exception as e:
                elapsed = (time.time() - start) * 1000
                logger.error(f"{func_name} failed after {elapsed:.1f}ms: {e}")
                raise
        return wrapper
    return decorator

def timed(func: Callable) -> Callable:
    """
    Decorador simple para medir tiempo de ejecución.
    
    Uso:
        @timed
        def slow_function():
            ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = (time.time() - start) * 1000
        print(f"⏱️ {func.__name__}: {elapsed:.1f}ms")
        return result
    return wrapper

def retry(max_attempts: int = 3, delay: float = 1.0):
    """
    Decorador para reintentar funciones que pueden fallar.
    
    Uso:
        @retry(max_attempts=3, delay=2.0)
        def unstable_api_call():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator

def deprecated(message: str = ""):
    """
    Decorador para marcar funciones deprecadas.
    
    Uso:
        @deprecated("Use new_function() instead")
        def old_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import warnings
            msg = f"{func.__name__} is deprecated. {message}"
            warnings.warn(msg, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)
        return wrapper
    return decorator

class Timer:
    """
    Context manager para medir tiempo.
    
    Uso:
        with Timer("Operación pesada"):
            do_heavy_work()
    """
    def __init__(self, name: str = "Operation"):
        self.name = name
        self.start = None
        self.elapsed = None
    
    def __enter__(self):
        self.start = time.time()
        return self
    
    def __exit__(self, *args):
        self.elapsed = (time.time() - self.start) * 1000
        print(f"⏱️ {self.name}: {self.elapsed:.1f}ms")

def safe_execute(func: Callable, default: Any = None, log_errors: bool = True) -> Any:
    """
    Ejecuta una función de forma segura, capturando excepciones.
    
    Uso:
        result = safe_execute(risky_function, default=[])
    """
    try:
        return func()
    except Exception as e:
        if log_errors:
            logging.error(f"safe_execute failed: {e}")
        return default

def format_currency(amount: float, symbol: str = "$") -> str:
    """Formatea un número como moneda."""
    return f"{symbol}{amount:,.2f}"

def format_date(dt: datetime, fmt: str = "%Y-%m-%d %H:%M") -> str:  # FIX 2026-02-01: Corregido typo format_CAST -> format_date
    """Formatea una fecha."""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            return dt  # Return original string if can't parse
    return dt.strftime(fmt) if dt else ""

def truncate(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """Trunca texto largo."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

# Singleton pattern helper
def singleton(cls):
    """
    Decorador para convertir una clase en singleton.
    
    Uso:
        @singleton
        class MyService:
            ...
    """
    instances = {}
    
    @functools.wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    return get_instance
