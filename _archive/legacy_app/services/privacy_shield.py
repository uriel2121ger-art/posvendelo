"""
Privacy Shield - Módulo de protección de datos y modo privacidad
Para cumplimiento de protección de datos personales (LFPDPPP)
"""

from typing import Any, Dict, Optional
from datetime import datetime
import logging
import os
import signal
import secrets

logger = logging.getLogger(__name__)


def _get_master_key() -> str:
    """
    Obtiene el master key de forma segura.
    FIX 2026-02-01: Eliminado hardcoding de credenciales.

    Prioridad:
    1. Variable de entorno TITAN_MASTER_KEY
    2. Archivo de configuración seguro
    3. Falla si no está configurado (NO hay valor por defecto)
    """
    # Intentar variable de entorno primero
    key = os.environ.get('TITAN_MASTER_KEY')
    if key and len(key) >= 16:
        return key

    # Intentar archivo de configuración seguro
    config_path = os.path.expanduser('~/.titan/master.key')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                key = f.read().strip()
                if key and len(key) >= 16:
                    return key
        except Exception as e:
            logger.error(f"Error reading master key file: {e}")

    # Sin master key configurado - funcionalidad de bypass deshabilitada
    logger.warning("TITAN_MASTER_KEY not configured. Remote bypass disabled.")
    return ""


class PrivacyShield:
    """
    Sistema de protección de privacidad y modo seguro.
    Gestiona el acceso a información sensible del sistema.

    IMPORTANTE: El modo privacidad NUNCA bloquea el acceso con master_key.
    Esto permite desactivarlo remotamente si es necesario.
    """
    
    def __init__(self, core):
        self.core = core
        self._privacy_mode = False
        self._session_tokens = set()
        self._privacy_activated_at = None
        self._auto_expire_hours = 24  # Auto-desactivar después de 24 horas
    
    def remote_bypass(self, master_key: str) -> Dict[str, Any]:
        """
        Bypass remoto de emergencia. Desactiva modo privacidad
        sin importar el estado actual.

        SIEMPRE funciona, incluso si el acceso remoto está 'bloqueado'.
        """
        # FIX 2026-02-01: Usar comparación segura contra timing attacks
        expected_key = _get_master_key()
        if not expected_key:
            return {'success': False, 'error': 'Master key no configurado en servidor'}

        if not secrets.compare_digest(master_key.encode(), expected_key.encode()):
            return {'success': False, 'error': 'Master key inválida'}
        
        self._privacy_mode = False
        self._privacy_activated_at = None
        
        return {
            'success': True,
            'mode': 'NORMAL',
            'message': 'Privacy Shield desactivado por master key',
            'remote_access': True,
            'api_access': True
        }
    
    def _check_auto_expire(self) -> bool:
        """Verifica si el modo privacidad expiró automáticamente."""
        if not self._privacy_mode or not self._privacy_activated_at:
            return False
        
        from datetime import timedelta
        expire_time = self._privacy_activated_at + timedelta(hours=self._auto_expire_hours)
        
        if datetime.now() > expire_time:
            self._privacy_mode = False
            self._privacy_activated_at = None
            return True
        return False
    
    def activate_privacy_mode(self, admin_pin: str) -> Dict[str, Any]:
        """
        Activa el modo privacidad.
        - Cierra sesiones remotas
        - Oculta dashboard de análisis
        - Muestra interfaz básica
        """
        if not self._verify_admin(admin_pin):
            return {'success': False, 'error': 'PIN incorrecto'}
        
        self._privacy_mode = True
        self._privacy_activated_at = datetime.now()
        
        # Limpiar sesiones activas
        self._clear_sessions()
        
        # Registrar activación
        self._log_privacy_event('PRIVACY_MODE_ON')
        
        # SECURITY: No loguear activación de modo privacidad
        pass
        
        return {
            'success': True,
            'mode': 'PRIVACY',
            'message': 'Modo privacidad activado',
            'features_disabled': [
                'Dashboard fiscal detallado',
                'Reportes de análisis',
                'Acceso remoto API',
                'Historial de sesiones'
            ]
        }
    
    def deactivate_privacy_mode(self, admin_pin: str) -> Dict[str, Any]:
        """Desactiva el modo privacidad."""
        if not self._verify_admin(admin_pin):
            return {'success': False, 'error': 'PIN incorrecto'}
        
        self._privacy_mode = False
        self._log_privacy_event('PRIVACY_MODE_OFF')
        
        # SECURITY: No loguear desactivación de modo privacidad
        pass
        
        return {
            'success': True,
            'mode': 'NORMAL',
            'message': 'Modo normal restaurado'
        }
    
    def is_privacy_mode(self) -> bool:
        """Verifica si el modo privacidad está activo."""
        return self._privacy_mode
    
    def _verify_admin(self, pin: str) -> bool:
        """Verifica PIN de administrador."""
        config = self.core.get_app_config()
        admin_pin = config.get('admin_pin')
        if not admin_pin:
            # No hay PIN configurado - rechazar
            return False
        return pin == admin_pin
    
    def _clear_sessions(self):
        """Limpia sesiones remotas activas."""
        try:
            # Limpiar tokens
            self._session_tokens.clear()
            
            # Registrar limpieza
            self.core.db.execute_write(
                """UPDATE audit_log SET details = details || ' [CLEARED]'
                   WHERE action = 'API_ACCESS' 
                   AND timestamp::date = CURRENT_DATE"""
            )
            
            # SECURITY: No loguear limpieza de sesiones
            pass
        except Exception as e:
            logger.error(f"Error clearing sessions: {e}")
    
    def _log_privacy_event(self, event: str):
        """Registra evento de privacidad."""
        try:
            self.core.db.execute_write(
                """INSERT INTO audit_log (timestamp, user_id, action, entity_type, details)
                   VALUES (%s, 0, %s, 'system', 'Privacy Shield activated')""",
                (datetime.now().isoformat(), event)
            )
        except Exception as e:
            logger.error(f"Error logging privacy event: {e}")
    
    def get_safe_dashboard(self) -> Dict[str, Any]:
        """
        Retorna datos del dashboard seguros para modo privacidad.
        Solo información básica sin análisis detallado.
        """
        if not self._privacy_mode:
            return {'mode': 'NORMAL', 'full_access': True}
        
        # Solo datos básicos
        today = datetime.now().strftime('%Y-%m-%d')
        
        sales_today = list(self.core.db.execute_query(
            """SELECT COUNT(*) as c, COALESCE(SUM(total), 0) as t 
               FROM sales WHERE timestamp::date = %s""",
            (today,)
        ))
        
        return {
            'mode': 'PRIVACY',
            'date': today,
            'sales_count': sales_today[0]['c'] if sales_today else 0,
            'total': float(sales_today[0]['t'] or 0) if sales_today else 0,
            'message': 'Información limitada en modo privacidad',
            'details_hidden': True
        }
    
    def check_data_access(self, resource: str, accessor: str = 'local') -> Dict[str, Any]:
        """
        Verifica si el acceso a un recurso está permitido.
        """
        # Recursos restringidos en modo privacidad
        restricted = [
            'fiscal_dashboard',
            'serie_b_report',
            'analysis',
            'audit_log',
            'api_full'
        ]
        
        if self._privacy_mode and resource in restricted:
            return {
                'allowed': False,
                'resource': resource,
                'reason': 'Recurso restringido en modo privacidad'
            }
        
        return {
            'allowed': True,
            'resource': resource
        }
    
    def emergency_lockdown(self, trigger: str = 'manual') -> Dict[str, Any]:
        """
        Bloqueo de emergencia del sistema.
        Cierra todo acceso externo y muestra solo interfaz básica.
        """
        self._privacy_mode = True
        
        # Limpiar todo
        self._clear_sessions()
        
        # Log con trigger
        self.core.db.execute_write(
            """INSERT INTO audit_log (timestamp, user_id, action, entity_type, details)
               VALUES (%s, 0, 'EMERGENCY_LOCKDOWN', 'system', %s)""",
            (datetime.now().isoformat(), f'Trigger: {trigger}')
        )
        
        # SECURITY: No loguear emergency lockdown
        pass
        
        return {
            'success': True,
            'mode': 'LOCKDOWN',
            'message': 'Sistema en modo de emergencia',
            'remote_access': False,
            'api_access': False,
            'basic_sales': True
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna estado del shield."""
        return {
            'privacy_mode': self._privacy_mode,
            'active_sessions': len(self._session_tokens),
            'lockdown': False,
            'timestamp': datetime.now().isoformat()
        }
