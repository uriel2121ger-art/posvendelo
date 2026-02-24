"""
TITAN POS - Sistema de Caché Optimizado
Reduce consumo de recursos mediante caché inteligente de consultas frecuentes
"""
from typing import Any, Callable, Optional
from functools import lru_cache, wraps
import hashlib
import json
import time


class QueryCache:
    """Cache inteligente para consultas de base de datos"""
    
    def __init__(self, max_size=100, ttl=300):
        """
        Args:
            max_size: Máximo de entradas en caché
            ttl: Tiempo de vida en segundos (default: 5 minutos)
        """
        self.cache = {}
        self.max_size = max_size
        self.ttl = ttl
        self.hits = 0
        self.misses = 0
        
    def _make_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Genera clave única para la consulta"""
        try:
            key_data = {
                'func': func_name,
                'args': args,
                'kwargs': kwargs
            }
            key_str = json.dumps(key_data, sort_keys=True, default=str)
            # SECURITY: Use SHA-256 instead of MD5 (MD5 is cryptographically broken)
            return hashlib.sha256(key_str.encode()).hexdigest()
        except Exception:
            # Fallback si JSON no puede serializar
            return f"{func_name}_{hash((args, tuple(sorted(kwargs.items()))))}"
    
    def get(self, key: str) -> Optional[Any]:
        """Obtiene valor de caché si es válido"""
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry['timestamp'] < self.ttl:
                self.hits += 1
                return entry['value']
            else:
                # Expiró, eliminar
                del self.cache[key]
        
        self.misses += 1
        return None
    
    def set(self, key: str, value: Any):
        """Guarda valor en caché"""
        # Limpiar cache si está lleno
        if len(self.cache) >= self.max_size:
            # Eliminar entrada más antigua
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]['timestamp'])
            del self.cache[oldest_key]
        
        self.cache[key] = {
            'value': value,
            'timestamp': time.time()
        }
    
    def clear(self):
        """Limpia toda la caché"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
    
    def invalidate_pattern(self, pattern: str):
        """Invalida entradas que contengan el patrón"""
        keys_to_delete = [k for k in self.cache.keys() if pattern in k]
        for key in keys_to_delete:
            del self.cache[key]
    
    def stats(self) -> dict:
        """Retorna estadísticas de caché"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate:.2f}%",
            'size': len(self.cache),
            'max_size': self.max_size
        }

# Instancia global de caché
query_cache = QueryCache(max_size=200, ttl=300)  # 5 minutos

def cached_query(ttl: int = 300, invalidate_on: list = None):
    """
    Decorador para cachear resultados de consultas
    
    Args:
        ttl: Tiempo de vida en segundos
        invalidate_on: Lista de funciones que invalidan este cache
    
    Usage:
        @cached_query(ttl=600, invalidate_on=['create_product', 'update_product'])
        def get_products(self, limit=50):
            return self.db.execute_query("SELECT * FROM products LIMIT %s", (limit,))
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generar clave de caché
            cache_key = query_cache._make_key(func.__name__, args[1:], kwargs)  # args[0] es self
            
            # Intentar obtener de caché
            cached_result = query_cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Ejecutar consulta
            result = func(*args, **kwargs)
            
            # Guardar en caché
            query_cache.set(cache_key, result)
            
            return result
        
        # Registrar función para invalidación
        if invalidate_on:
            wrapper._invalidate_on = invalidate_on
        
        return wrapper
    return decorator

class ResourceMonitor:
    """Monitor de recursos del sistema"""
    
    def __init__(self):
        self.query_count = 0
        self.query_time = 0.0
        self.start_time = time.time()
    
    def log_query(self, duration: float):
        """Registra tiempo de consulta"""
        self.query_count += 1
        self.query_time += duration
    
    def stats(self) -> dict:
        """Retorna estadísticas de recursos"""
        uptime = time.time() - self.start_time
        avg_query = self.query_time / self.query_count if self.query_count > 0 else 0
        
        return {
            'uptime_seconds': uptime,
            'total_queries': self.query_count,
            'avg_query_time_ms': f"{avg_query * 1000:.2f}",
            'queries_per_second': f"{self.query_count / uptime:.2f}" if uptime > 0 else "0"
        }

resource_monitor = ResourceMonitor()

def timed_query(func: Callable) -> Callable:
    """Decorador para medir tiempo de consultas"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        resource_monitor.log_query(duration)
        
        # Log si es muy lenta (>100ms)
        if duration > 0.1:
            import logging
            logging.warning(f"Slow query detected: {func.__name__} took {duration*1000:.2f}ms")
        
        return result
    return wrapper
