from pathlib import Path

"""
Audit-Safe - Hotkey Física de Pánico
F12+Esc para modo phantom instantáneo
"""

from typing import Any, Callable, Dict, Optional
from datetime import datetime
import logging
import os
import secrets
import sys
import threading
import time

logger = logging.getLogger(__name__)


def _get_restore_auth_code() -> str:
    """
    Obtiene el código de autorización para restaurar modo normal.
    FIX 2026-02-04: Eliminado hardcoding de credenciales.

    IMPORTANTE: Configure la variable de entorno TITAN_RESTORE_CODE
    antes de usar esta funcionalidad.
    """
    code = os.environ.get('TITAN_RESTORE_CODE', '')
    if code and len(code) >= 4:
        return code

    config_path = os.path.expanduser('~/.titan/restore.key')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                code = f.read().strip()
                if code and len(code) >= 4:
                    return code
        except Exception as e:
            logger.error(f"Error reading restore key: {e}")

    logger.warning("TITAN_RESTORE_CODE not configured")
    return ""

class AuditSafe:
    """
    Sistema de pánico por hotkey de teclado.
    
    Al presionar F12 + Esc:
    - Cambia a Modo Phantom (Solo Serie A)
    - Borra historial de 4 horas de RAM
    - Muestra mensaje de "error de conexión"
    
    El auditor ve un sistema "fallando" con datos aburridos.
    """
    
    # Combinaciones de pánico
    PANIC_COMBOS = [
        ('F12', 'Escape'),
        ('F11', 'F12'),
        ('Ctrl', 'Alt', 'Delete', 'Escape'),  # Combo extremo
    ]
    
    def __init__(self, core, on_panic: Callable = None):
        self.core = core
        self.on_panic = on_panic
        self.is_monitoring = False
        self.panic_triggered = False
        self.phantom_mode = False
        self.keys_pressed = set()
    
    def start_monitoring(self):
        """Inicia monitoreo de teclas."""
        self.is_monitoring = True
        
        # Intentar usar pynput si está disponible
        try:
            from pynput import keyboard
            
            def on_press(key):
                try:
                    key_name = key.name if hasattr(key, 'name') else str(key)
                    self.keys_pressed.add(key_name.lower())
                    self._check_panic_combo()
                except Exception as e:
                    logger.debug("AuditSafe on_press: %s", e)
            
            def on_release(key):
                try:
                    key_name = key.name if hasattr(key, 'name') else str(key)
                    self.keys_pressed.discard(key_name.lower())
                except Exception as e:
                    logger.debug("AuditSafe on_release: %s", e)
            
            listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            listener.start()
            
            # SECURITY: No loguear activación de hotkeys
            pass
            
        except ImportError:
            # SECURITY: No loguear disponibilidad de pynput
            pass
            self._start_fallback_monitoring()
    
    def _start_fallback_monitoring(self):
        """Monitoreo alternativo sin pynput con manejo robusto de errores."""
        def monitor_loop():
            consecutive_errors = 0
            max_errors = 10  # Máximo de errores consecutivos antes de pausar
            
            while self.is_monitoring:
                try:
                    # Leer /dev/input/event* (Linux)
                    self._read_input_events()
                    consecutive_errors = 0  # Reset contador si éxito
                except Exception as e:
                    consecutive_errors += 1
                    if consecutive_errors >= max_errors:
                        # Demasiados errores, pausar más tiempo
                        logging.warning(f"AuditSafe: {consecutive_errors} errores consecutivos, pausando 5s")
                        time.sleep(5)
                        consecutive_errors = 0
                    else:
                        logging.debug(f"AuditSafe error: {e}")
                
                # Sleep para evitar consumo excesivo de CPU
                time.sleep(0.1)
        
        thread = threading.Thread(target=monitor_loop, daemon=True, name="AuditSafe-Monitor")
        thread.start()
    
    def _read_input_events(self):
        """Lee eventos de teclado de /dev/input con timeout y manejo de errores."""
        import os
        import struct
        import select
        
        # Buscar dispositivos de teclado válidos
        input_devices = []
        try:
            for event_file in os.listdir('/dev/input'):
                if event_file.startswith('event'):
                    path = f'/dev/input/{event_file}'
                    # Verificar que el dispositivo existe y es accesible
                    if os.path.exists(path) and os.access(path, os.R_OK):
                        input_devices.append(path)
        except (OSError, PermissionError) as e:
            # Si no se puede acceder a /dev/input, simplemente retornar
            return
        
        if not input_devices:
            return
        
        # Intentar leer de cada dispositivo con timeout
        for device_path in input_devices:
            try:
                # Usar select para verificar si hay datos disponibles (evita bloqueo)
                with open(device_path, 'rb') as f:
                    # Verificar si hay datos disponibles (timeout 0.1s)
                    ready, _, _ = select.select([f], [], [], 0.1)
                    if not ready:
                        continue  # No hay datos, intentar siguiente dispositivo
                    
                    # Leer evento (formato: time_sec, time_usec, type, code, value)
                    data = f.read(24)
                    if len(data) == 24:
                        _, _, type_, code, value = struct.unpack('llHHI', data)
                        if type_ == 1:  # EV_KEY
                            self._handle_key_event(code, value)
            except (OSError, PermissionError, IOError):
                # Dispositivo no disponible o sin permisos, continuar con siguiente
                continue
            except Exception as e:
                # Otros errores (dispositivo desconectado, etc.)
                logging.debug(f"Error reading from {device_path}: {e}")
                continue
    
    def _handle_key_event(self, code: int, value: int):
        """Maneja evento de tecla."""
        # Códigos de teclas importantes
        KEY_CODES = {
            1: 'escape',
            87: 'f11',
            88: 'f12',
            29: 'ctrl',
            56: 'alt',
            111: 'delete',
        }
        
        key_name = KEY_CODES.get(code)
        if key_name:
            if value == 1:  # Key down
                self.keys_pressed.add(key_name)
                self._check_panic_combo()
            elif value == 0:  # Key up
                self.keys_pressed.discard(key_name)
    
    def _check_panic_combo(self):
        """Verifica si se presionó combo de pánico."""
        for combo in self.PANIC_COMBOS:
            combo_lower = {k.lower() for k in combo}
            if combo_lower.issubset(self.keys_pressed):
                self.trigger_panic()
                break
    
    def trigger_panic(self):
        """Activa modo pánico."""
        if self.panic_triggered:
            return  # Ya se activó
        
        self.panic_triggered = True
        # SECURITY: No loguear activación de pánico
        pass
        
        try:
            # 1. Activar modo Phantom
            self._activate_phantom_mode()
            
            # 2. Borrar historial de RAM
            self._clear_ram_history()
            
            # 3. Mostrar mensaje de error
            self._show_error_screen()
            
            # 4. Callback personalizado
            if self.on_panic:
                self.on_panic()
            
        except Exception as e:
            logger.error(f"Error en pánico: {e}")
    
    def _activate_phantom_mode(self):
        """Activa modo que solo muestra Serie A."""
        self.phantom_mode = True
        
        try:
            # Guardar estado actual en config volátil
            self.core.db.execute_write("""
                INSERT INTO app_config (key, value)
                VALUES ('display_mode', 'phantom')
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """)
            
            # Ocultar datos Serie B de la memoria
            self.core.db.execute_write("""
                UPDATE sales SET visible = 0 
                WHERE serie = 'B' AND CAST(timestamp AS DATE) = CURRENT_DATE
            """)
            
            # SECURITY: No loguear modo phantom
            pass
            
        except Exception as e:
            logger.error(f"Error activando Phantom: {e}")
    
    def _clear_ram_history(self):
        """Borra historial de las últimas 4 horas de RAM."""
        try:
            cutoff = datetime.now().replace(
                hour=max(0, datetime.now().hour - 4),
                minute=0, second=0
            )
            
            # Limpiar tablas de caché/sesión
            self.core.db.execute_write("""
                DELETE FROM session_cache WHERE timestamp > %s
            """, (cutoff.isoformat(),))
            
            # Limpiar logs volátiles
            self.core.db.execute_write("""
                DELETE FROM activity_log WHERE timestamp > %s
            """, (cutoff.isoformat(),))
            
            # Forzar garbage collection
            import gc
            gc.collect()
            
            # SECURITY: No loguear limpieza de RAM
            pass
            
        except Exception as e:
            logger.error(f"Error limpiando RAM: {e}")
    
    def _show_error_screen(self):
        """Muestra pantalla de error falso."""
        self.error_message = (
            "⚠️ ERROR DE CONEXIÓN\n\n"
            "No se puede conectar con el servidor central.\n"
            "Operando en modo contingencia limitado.\n\n"
            "Funciones disponibles:\n"
            "• Consulta de precios\n"
            "• Ventas sin factura (limitado)\n\n"
            "Contacte al soporte técnico."
        )
        
        # Guardar estado de error
        try:
            self.core.db.execute_write("""
                INSERT INTO app_config (key, value)
                VALUES ('error_mode', 'connection_error')
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """)
        except Exception as e:
            logger.debug("AuditSafe error_mode insert: %s", e)
    
    def get_phantom_sales_query(self) -> str:
        """
        Query modificada que solo retorna Serie A.
        Para usar en lugar del query normal cuando Phantom está activo.
        """
        return """
            SELECT * FROM sales 
            WHERE serie = 'A' 
            AND visible = 1
            ORDER BY timestamp DESC
        """
    
    def is_phantom_active(self) -> bool:
        """Verifica si el modo Phantom está activo."""
        return self.phantom_mode
    
    def deactivate_phantom(self, auth_code: str = None):
        """
        Desactiva modo Phantom (requiere autenticación).
        FIX 2026-02-04: Usar comparación segura y código desde variable de entorno.
        """
        # Obtener código esperado desde configuración segura
        expected_code = _get_restore_auth_code()
        if not expected_code:
            return {'success': False, 'error': 'Código de restauración no configurado en servidor'}

        if not auth_code or not secrets.compare_digest(auth_code.encode(), expected_code.encode()):
            return {'success': False, 'error': 'Código incorrecto'}
        
        try:
            self.phantom_mode = False
            self.panic_triggered = False
            
            # Restaurar visibilidad
            self.core.db.execute_write("""
                UPDATE sales SET visible = 1 WHERE visible = 0
            """)
            
            self.core.db.execute_write("""
                DELETE FROM app_config WHERE key IN ('display_mode', 'error_mode')
            """)
            
            # SECURITY: No loguear desactivación de phantom
            pass
            return {'success': True}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

# Función para registrar en PyQt
def register_panic_shortcut(window, core, on_panic=None):
    """Registra shortcut de pánico en ventana PyQt."""
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QKeySequence, QShortcut
        
        audit_safe = AuditSafe(core, on_panic)
        
        # F12
        shortcut = QShortcut(QKeySequence(Qt.Key.Key_F12), window)
        shortcut.activated.connect(lambda: audit_safe._check_panic_combo())
        
        # También iniciar monitoreo de sistema
        audit_safe.start_monitoring()
        
        return audit_safe
        
    except ImportError:
        logger.warning("PyQt6 no disponible para shortcuts")
        return None
