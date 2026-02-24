"""
🔴 SENTRY - Error Tracking en Producción
Captura errores automáticamente y envía alertas

Setup:
1. Crear cuenta en sentry.io
2. Obtener DSN del proyecto
3. Configurar SENTRY_DSN en .env

Uso:
    from app.utils.sentry_integration import init_sentry, capture_error, set_user_context
    
    init_sentry()  # Llamar al inicio de la app
    
    try:
        risky_operation()
    except Exception as e:
        capture_error(e, context={"operation": "risky"})
"""
from typing import Any, Dict, Optional
import logging
import os

logger = logging.getLogger("SENTRY")

# Estado global
_initialized = False

def init_sentry(
    dsn: str = None,
    environment: str = None,
    release: str = None,
    sample_rate: float = 1.0
):
    """
    Inicializa Sentry para tracking de errores.
    
    Args:
        dsn: Data Source Name de Sentry (o variable SENTRY_DSN)
        environment: Ambiente (production, development, staging)
        release: Versión de la app (ej: "titan-pos@6.5.0")
        sample_rate: Porcentaje de errores a capturar (0.0 - 1.0)
    """
    global _initialized
    
    dsn = dsn or os.getenv("SENTRY_DSN")
    
    if not dsn:
        logger.debug("Sentry DSN no configurado, tracking deshabilitado")
        return False
    
    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.threading import ThreadingIntegration

        # Determinar ambiente
        if environment is None:
            environment = os.getenv("ENVIRONMENT", "production")
        
        # Determinar release
        if release is None:
            release = os.getenv("APP_VERSION", "titan-pos@6.5.0")
        
        # Configurar integración con logging
        logging_integration = LoggingIntegration(
            level=logging.INFO,        # Capturar logs INFO+
            event_level=logging.ERROR  # Enviar solo errores a Sentry
        )
        
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            traces_sample_rate=sample_rate,
            profiles_sample_rate=sample_rate,
            integrations=[
                logging_integration,
                ThreadingIntegration(propagate_hub=True),
            ],
            # No capturar información sensible
            send_default_pii=False,
            # Antes de enviar, limpiar datos
            before_send=_before_send,
        )
        
        _initialized = True
        logger.info(f"✅ Sentry inicializado ({environment})")
        return True
        
    except ImportError:
        logger.warning("sentry-sdk no instalado. Ejecutar: pip install sentry-sdk")
        return False
    except Exception as e:
        logger.error(f"Error inicializando Sentry: {e}")
        return False

def _before_send(event, hint):
    """
    Callback antes de enviar evento a Sentry.
    Limpia información sensible.
    """
    # Remover contraseñas o tokens
    if 'exception' in event:
        for exception in event['exception'].get('values', []):
            if 'stacktrace' in exception:
                for frame in exception['stacktrace'].get('frames', []):
                    # Limpiar variables locales sensibles
                    if 'vars' in frame:
                        for key in list(frame['vars'].keys()):
                            if any(s in key.lower() for s in ['password', 'token', 'secret', 'key']):
                                frame['vars'][key] = '[REDACTED]'
    
    return event

def capture_error(
    error: Exception,
    context: Dict[str, Any] = None,
    user: Dict[str, Any] = None,
    level: str = "error"
):
    """
    Captura y envía un error a Sentry.
    
    Args:
        error: Excepción a capturar
        context: Contexto adicional
        user: Información del usuario
        level: Nivel (error, warning, info)
    """
    if not _initialized:
        logger.error(f"[LOCAL] {type(error).__name__}: {error}")
        return
    
    try:
        import sentry_sdk
        
        with sentry_sdk.push_scope() as scope:
            if context:
                for key, value in context.items():
                    scope.set_extra(key, value)
            
            if user:
                scope.set_user(user)
            
            scope.set_level(level)
            sentry_sdk.capture_exception(error)
            
    except Exception as e:
        logger.error(f"Error enviando a Sentry: {e}")

def capture_message(
    message: str,
    level: str = "info",
    context: Dict[str, Any] = None
):
    """
    Envía un mensaje a Sentry (no un error).
    
    Útil para eventos importantes como:
    - Usuario completó una compra grande
    - Sistema entró en modo contingencia
    - Alerta de stock bajo
    """
    if not _initialized:
        logger.info(f"[LOCAL] {message}")
        return
    
    try:
        import sentry_sdk
        
        with sentry_sdk.push_scope() as scope:
            if context:
                for key, value in context.items():
                    scope.set_extra(key, value)
            
            scope.set_level(level)
            sentry_sdk.capture_message(message)
            
    except Exception as e:
        logger.error(f"Error enviando mensaje a Sentry: {e}")

def set_user_context(
    user_id: int = None,
    username: str = None,
    email: str = None,
    role: str = None,
    branch: str = None
):
    """
    Establece contexto del usuario actual.
    
    Útil para saber quién experimentó el error.
    """
    if not _initialized:
        return
    
    try:
        import sentry_sdk
        
        sentry_sdk.set_user({
            "id": str(user_id) if user_id else None,
            "username": username,
            "email": email,
        })
        
        sentry_sdk.set_context("pos", {
            "role": role,
            "branch": branch,
            "terminal_id": os.getenv("TERMINAL_ID"),
        })
        
    except Exception as e:
        logger.debug(f"Error setting user context: {e}")

def set_tag(key: str, value: str):
    """
    Establece un tag para filtrar errores.
    
    Ejemplos:
        set_tag("payment_method", "card")
        set_tag("feature", "checkout")
    """
    if not _initialized:
        return
    
    try:
        import sentry_sdk
        sentry_sdk.set_tag(key, value)
    # FIX 2026-02-01: Agregar logging mínimo en lugar de excepción silenciada
    except Exception as e:
        logger.debug(f"Error setting tag: {e}")

def add_breadcrumb(
    message: str,
    category: str = "custom",
    level: str = "info",
    data: Dict[str, Any] = None
):
    """
    Agrega una "migaja de pan" para trazar acciones del usuario.
    
    Ejemplos:
        add_breadcrumb("Usuario buscó producto", category="search", data={"query": "coca"})
        add_breadcrumb("Agregó al carrito", category="cart", data={"product_id": 123})
    """
    if not _initialized:
        return
    
    try:
        import sentry_sdk
        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data
        )
    # FIX 2026-02-01: Agregar logging mínimo en lugar de excepción silenciada
    except Exception as e:
        logger.debug(f"Error adding breadcrumb: {e}")

# Context manager para operaciones
class track_operation:
    """
    Context manager para trackear operaciones.
    
    Uso:
        with track_operation("procesar_venta", sale_id=123):
            process_sale()
    """
    
    def __init__(self, operation_name: str, **context):
        self.operation_name = operation_name
        self.context = context
    
    def __enter__(self):
        add_breadcrumb(
            f"Iniciando: {self.operation_name}",
            category="operation",
            data=self.context
        )
        set_tag("current_operation", self.operation_name)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            capture_error(exc_val, context={
                "operation": self.operation_name,
                **self.context
            })
            return False  # Re-raise exception
        
        add_breadcrumb(
            f"Completado: {self.operation_name}",
            category="operation",
            level="info"
        )
        return False

if __name__ == "__main__":
    # Test
    print("🔴 Sentry Integration Test")
    
    # Simular inicialización (sin DSN real)
    os.environ["SENTRY_DSN"] = ""  # Dejar vacío para test local
    
    result = init_sentry()
    print(f"Inicializado: {result}")
    
    # Simular error
    try:
        raise ValueError("Test error")
    except Exception as e:
        capture_error(e, context={"test": True})
    
    print("✅ Test completado (errores se muestran solo en consola sin DSN)")
