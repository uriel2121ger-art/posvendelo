from pathlib import Path

"""
Biometric Kill - Sistema de Protección con PIN de Coacción
Interfaz espejo con datos falsos bajo amenaza
"""

from typing import Any, Callable, Dict, Optional
from datetime import datetime
import hashlib
import json
import logging
import sys

logger = logging.getLogger(__name__)

class BiometricKill:
    """
    Sistema de protección bajo coacción.
    
    Características:
    - PIN normal: Acceso completo
    - PIN de coacción: Interfaz espejo con datos falsos
    - Detección de estrés (patrones de escritura)
    - Alerta silenciosa a otras sucursales
    - Auto-lockdown de red
    """
    
    # Configuración de PINs
    NORMAL_PIN = None       # Se configura
    DURESS_PIN = None       # PIN de coacción
    WIPE_PIN = None         # PIN de borrado total
    
    # Datos falsos para modo espejo
    FAKE_SALES = 15000      # Ventas bajas
    FAKE_SERIE_B = 0        # Cero Serie B
    FAKE_WEALTH = 5000      # Riqueza mínima
    
    def __init__(self, core=None):
        self.core = core
        self.duress_mode = False
        self.alert_callback: Optional[Callable] = None
        self._load_pins()
    
    def _load_pins(self):
        """Carga PINs de configuracion."""
        if not self.core or not self.core.db:
            return

        try:
            pins = list(self.core.db.execute_query("""
                SELECT key, value FROM config 
                WHERE key IN ('normal_pin_hash', 'duress_pin_hash', 'wipe_pin_hash')
            """))
            
            for p in pins:
                if p['key'] == 'normal_pin_hash':
                    self.NORMAL_PIN = p['value']
                elif p['key'] == 'duress_pin_hash':
                    self.DURESS_PIN = p['value']
                elif p['key'] == 'wipe_pin_hash':
                    self.WIPE_PIN = p['value']
        except Exception:
            pass
    
    def configure_pins(self, normal_pin: str, duress_pin: str, 
                      wipe_pin: str = None) -> Dict[str, Any]:
        """
        Configura los PINs del sistema.
        
        normal_pin: PIN de acceso normal
        duress_pin: PIN de coacción (activa modo espejo)
        wipe_pin: PIN de borrado de emergencia (opcional)
        """
        if normal_pin == duress_pin:
            return {'success': False, 'error': 'PINs no pueden ser iguales'}
        
        self.NORMAL_PIN = self._hash_pin(normal_pin)
        self.DURESS_PIN = self._hash_pin(duress_pin)
        
        if wipe_pin:
            self.WIPE_PIN = self._hash_pin(wipe_pin)
        
        # Guardar en config
        if self.core and self.core.db:
            self.core.db.execute_write(
                "INSERT INTO config (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                ('normal_pin_hash', self.NORMAL_PIN)
            )
            self.core.db.execute_write(
                "INSERT INTO config (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                ('duress_pin_hash', self.DURESS_PIN)
            )
            if wipe_pin:
                self.core.db.execute_write(
                    "INSERT INTO config (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                    ('wipe_pin_hash', self.WIPE_PIN)
                )
        
        # SECURITY: No loguear configuración de PINs
        pass
        
        return {'success': True, 'message': 'PINs configurados correctamente'}
    
    def _hash_pin(self, pin: str) -> str:
        """Hashea un PIN."""
        return hashlib.sha256(f"biometric_kill_{pin}".encode()).hexdigest()
    
    def verify_pin(self, pin: str) -> Dict[str, Any]:
        """
        Verifica PIN y determina modo de acceso.
        
        Retorna:
        - mode: 'normal', 'duress', 'wipe', 'denied'
        """
        pin_hash = self._hash_pin(pin)
        
        if pin_hash == self.NORMAL_PIN:
            self.duress_mode = False
            return {
                'authenticated': True,
                'mode': 'normal',
                'message': 'Acceso normal concedido'
            }
        
        elif pin_hash == self.DURESS_PIN:
            self.duress_mode = True
            self._trigger_silent_alert()
            return {
                'authenticated': True,
                'mode': 'duress',
                'message': 'Modo espejo activado',
                'note': 'Datos falsos mostrados - alerta enviada'
            }
        
        elif self.WIPE_PIN and pin_hash == self.WIPE_PIN:
            self._emergency_wipe()
            return {
                'authenticated': False,
                'mode': 'wipe',
                'message': 'Protocolo de emergencia activado'
            }
        
        else:
            return {
                'authenticated': False,
                'mode': 'denied',
                'message': 'PIN incorrecto'
            }
    
    def _trigger_silent_alert(self):
        """Envía alerta silenciosa de coacción."""
        alert_data = {
            'type': 'DURESS',
            'timestamp': datetime.now().isoformat(),
            'message': 'PIN de coacción activado - posible amenaza'
        }
        
        # Callback para notificación externa
        if self.alert_callback:
            try:
                self.alert_callback(alert_data)
            except Exception:
                pass
        
        # Registrar en log oculto
        if self.core and self.core.db:
            self.core.db.execute_write("""
                INSERT INTO config (key, value)
                VALUES (%s, %s)
            """, (f'duress_alert_{datetime.now().timestamp()}',
                  json.dumps(alert_data)))
        
        # Intentar enviar por Telegram si está configurado
        self._send_telegram_alert(alert_data)
        
        # SECURITY: No loguear alertas de coacción
        pass
    
    def _send_telegram_alert(self, alert_data: Dict):
        """Envia alerta a Telegram si esta configurado."""
        if not self.core or not self.core.db:
            return

        try:
            import urllib.request

            # Buscar config de Telegram
            config = list(self.core.db.execute_query(
                "SELECT value FROM config WHERE key = 'telegram_bot_token'"
            ))
            if not config:
                return

            token = config[0]['value']

            chat = list(self.core.db.execute_query(
                "SELECT value FROM config WHERE key = 'telegram_chat_id'"
            ))
            if not chat:
                return
            
            chat_id = chat[0]['value']
            
            message = f"🚨 ALERTA CRÍTICA\n\n{alert_data['message']}\n{alert_data['timestamp']}"
            
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = json.dumps({'chat_id': chat_id, 'text': message}).encode()
            
            req = urllib.request.Request(url, data=data,
                                         headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=5) as response:
                _ = response.read()  # Consume response to release connection

        except Exception:
            pass  # Fallo silencioso
    
    def _emergency_wipe(self):
        """Ejecuta borrado de emergencia."""
        if not self.core or not self.core.db:
            return

        # Importar lockdown
        try:
            from app.services.network_lockdown import NetworkLockdown
            lockdown = NetworkLockdown()
            lockdown.activate_audit_mode('WIPE_PIN')
        except Exception:
            pass
        
        # Borrar datos sensibles
        # nosec B608 - table names are hardcoded whitelist, not user input
        sensitive_tables = [
            'crypto_conversions',
            'cold_wallets',
            'cash_extractions',
            'related_persons'
        ]

        for table in sensitive_tables:
            try:
                self.core.db.execute_write(f"DELETE FROM {table}")  # nosec B608
            except Exception:
                pass
        
        # SECURITY: No loguear borrado de emergencia
        pass
    
    def get_fake_dashboard(self) -> Dict[str, Any]:
        """Retorna datos falsos para modo espejo."""
        return {
            'ventas_hoy': self.FAKE_SALES,
            'serie_a': self.FAKE_SALES * 0.9,
            'serie_b': self.FAKE_SERIE_B,
            'utilidad': self.FAKE_WEALTH,
            'disponible_retiro': 0,
            'mermas': 0,
            'resico_percentage': 5,
            'mode': 'espejo'
        }
    
    def get_real_or_fake_data(self, real_data: Dict) -> Dict:
        """
        Retorna datos reales o falsos según modo actual.
        Usar como wrapper en todos los dashboards.
        """
        if self.duress_mode:
            return self.get_fake_dashboard()
        return real_data
    
    def is_duress_mode(self) -> bool:
        """Verifica si está en modo coacción."""
        return self.duress_mode
    
    def set_alert_callback(self, callback: Callable):
        """Configura callback para alertas."""
        self.alert_callback = callback

class StressDetector:
    """
    Detector de estrés basado en patrones de entrada.
    Analiza velocidad de escritura y patrones de presión.
    """
    
    def __init__(self):
        self.keystroke_times = []
        self.baseline_speed = None
        self.threshold_multiplier = 2.0  # 2x más lento = estrés
    
    def record_keystroke(self, timestamp: float):
        """Registra tiempo de pulsación."""
        self.keystroke_times.append(timestamp)
        
        # Mantener solo últimas 20 pulsaciones
        if len(self.keystroke_times) > 20:
            self.keystroke_times.pop(0)
    
    def calculate_typing_speed(self) -> float:
        """Calcula velocidad de escritura actual."""
        if len(self.keystroke_times) < 3:
            return 0
        
        intervals = []
        for i in range(1, len(self.keystroke_times)):
            intervals.append(self.keystroke_times[i] - self.keystroke_times[i-1])
        
        return sum(intervals) / len(intervals)
    
    def set_baseline(self):
        """Establece velocidad base del usuario."""
        speed = self.calculate_typing_speed()
        if speed > 0:
            self.baseline_speed = speed
    
    def detect_stress(self) -> Dict[str, Any]:
        """Detecta si el patrón indica estrés."""
        if not self.baseline_speed:
            return {'detected': False, 'reason': 'No baseline set'}
        
        current_speed = self.calculate_typing_speed()
        
        if current_speed <= 0:
            return {'detected': False, 'reason': 'Not enough data'}
        
        ratio = current_speed / self.baseline_speed
        
        # Escritura mucho más lenta = posible estrés
        if ratio > self.threshold_multiplier:
            return {
                'detected': True,
                'ratio': ratio,
                'reason': 'Typing significantly slower than baseline'
            }
        
        # Escritura muy errática
        if self._check_erratic_pattern():
            return {
                'detected': True,
                'reason': 'Erratic typing pattern detected'
            }
        
        return {'detected': False}
    
    def _check_erratic_pattern(self) -> bool:
        """Verifica patrones erráticos de escritura."""
        if len(self.keystroke_times) < 5:
            return False
        
        intervals = []
        for i in range(1, len(self.keystroke_times)):
            intervals.append(self.keystroke_times[i] - self.keystroke_times[i-1])
        
        # Alta varianza = patrón errático
        import statistics
        if len(intervals) >= 3:
            std = statistics.stdev(intervals)
            mean = statistics.mean(intervals)
            cv = std / mean if mean > 0 else 0
            
            return cv > 1.0  # Coeficiente de variación > 1
        
        return False

# Middleware de protección para PWA
def pwa_security_middleware(core, pin: str) -> Dict:
    """
    Middleware de seguridad para login de PWA.
    Verifica PIN y activa modo apropiado.
    """
    biometric = BiometricKill(core)
    return biometric.verify_pin(pin)

class DeadMansSwitch:
    """
    Dead Man's Switch - Auto-purga si no hay check-in.
    
    Si el operador no hace check-in en 48 horas:
    - Entra en Modo Purga Total de Serie B
    - Borra datos sensibles en todos los nodos
    - Envía alerta de emergencia
    """
    
    DEFAULT_TIMEOUT_HOURS = 48
    
    def __init__(self, core):
        self.core = core
        self._ensure_table()

    def _ensure_table(self):
        """Crea tabla de check-ins."""
        if not self.core.db:
            logger.warning("Database not available for DeadMansSwitch table creation")
            return

        self.core.db.execute_write("""
            CREATE TABLE IF NOT EXISTS dead_mans_switch (
                id INTEGER PRIMARY KEY,
                last_checkin TEXT NOT NULL,
                timeout_hours INTEGER DEFAULT 48,
                enabled INTEGER DEFAULT 0,
                emergency_contact TEXT,
                purge_on_trigger INTEGER DEFAULT 1
            )
        """)
        
        # Insertar config inicial si no existe
        existing = list(self.core.db.execute_query(
            "SELECT id FROM dead_mans_switch LIMIT 1"
        ))
        if not existing:
            self.core.db.execute_write("""
                INSERT INTO dead_mans_switch (id, last_checkin, enabled)
                VALUES (1, %s, 0)
            """, (datetime.now().isoformat(),))
    
    def enable(self, timeout_hours: int = 48,
               emergency_contact: str = None) -> Dict:
        """Activa el Dead Man's Switch."""
        if not self.core.db:
            logger.warning("Database not available for enable DeadMansSwitch")
            return {'enabled': False, 'error': 'Database not available'}

        self.core.db.execute_write("""
            UPDATE dead_mans_switch 
            SET enabled = 1, 
                timeout_hours = %s,
                emergency_contact = %s,
                last_checkin = %s
            WHERE id = 1
        """, (timeout_hours, emergency_contact, datetime.now().isoformat()))
        
        # SECURITY: No loguear Dead Man's Switch
        pass
        
        return {
            'enabled': True,
            'timeout_hours': timeout_hours,
            'next_checkin_required': datetime.now().isoformat()
        }
    
    def disable(self) -> Dict:
        """Desactiva el Dead Man's Switch."""
        if not self.core.db:
            logger.warning("Database not available for disable DeadMansSwitch")
            return {'enabled': False, 'error': 'Database not available'}

        self.core.db.execute_write("""
            UPDATE dead_mans_switch SET enabled = 0 WHERE id = 1
        """)
        
        # SECURITY: No loguear desactivación
        pass
        
        return {'enabled': False}
    
    def checkin(self) -> Dict:
        """
        Registra un check-in del operador.
        Debe llamarse regularmente para evitar la purga.
        """
        if not self.core.db:
            logger.warning("Database not available for checkin")
            return {'error': 'Database not available'}

        self.core.db.execute_write("""
            UPDATE dead_mans_switch
            SET last_checkin = %s
            WHERE id = 1
        """, (datetime.now().isoformat(),))
        
        config = self._get_config()
        
        from datetime import timedelta
        next_deadline = datetime.now() + timedelta(hours=config['timeout_hours'])
        
        # SECURITY: No loguear check-ins
        pass
        
        return {
            'checkin_time': datetime.now().isoformat(),
            'next_deadline': next_deadline.isoformat(),
            'hours_remaining': config['timeout_hours']
        }
    
    def check_status(self) -> Dict:
        """Verifica si el switch debe activarse."""
        config = self._get_config()
        
        if not config['enabled']:
            return {'triggered': False, 'reason': 'Switch desactivado'}
        
        last_checkin = datetime.fromisoformat(config['last_checkin'])
        
        from datetime import timedelta
        deadline = last_checkin + timedelta(hours=config['timeout_hours'])
        now = datetime.now()
        
        if now > deadline:
            # ¡TRIGGER!
            return {
                'triggered': True,
                'reason': 'Tiempo límite excedido',
                'last_checkin': config['last_checkin'],
                'deadline_passed': deadline.isoformat(),
                'hours_overdue': (now - deadline).total_seconds() / 3600
            }
        
        hours_remaining = (deadline - now).total_seconds() / 3600
        
        return {
            'triggered': False,
            'hours_remaining': round(hours_remaining, 1),
            'deadline': deadline.isoformat()
        }
    
    def _get_config(self) -> Dict:
        """Obtiene configuracion del switch."""
        if not self.core.db:
            logger.warning("Database not available for get config")
            return {
                'enabled': False,
                'timeout_hours': 48,
                'last_checkin': datetime.now().isoformat()
            }

        config = list(self.core.db.execute_query(
            "SELECT * FROM dead_mans_switch WHERE id = 1"
        ))
        
        if config:
            return dict(config[0])
        
        return {
            'enabled': False,
            'timeout_hours': 48,
            'last_checkin': datetime.now().isoformat()
        }
    
    def trigger_purge(self) -> Dict:
        """
        Ejecuta la purga de emergencia.
        Llamado automáticamente si el check-in expira.
        """
        # SECURITY: No loguear activación de purga
        pass
        
        # Enviar alerta
        config = self._get_config()
        if config.get('emergency_contact'):
            self._send_emergency_alert(config['emergency_contact'])
        
        # Ejecutar purga
        biometric = BiometricKill(self.core)
        biometric._emergency_wipe()
        
        # Marcar como ejecutado
        if self.core.db:
            self.core.db.execute_write("""
                UPDATE dead_mans_switch
                SET enabled = 0
                WHERE id = 1
            """)
        
        return {
            'purged': True,
            'timestamp': datetime.now().isoformat(),
            'message': 'Dead Man\'s Switch ejecutado - datos sensibles purgados'
        }
    
    def _send_emergency_alert(self, contact: str):
        """Envia alerta de emergencia."""
        if not self.core.db:
            logger.warning("Database not available for emergency alert")
            return

        # Usar el sistema de Telegram existente
        try:
            import urllib.request

            token = list(self.core.db.execute_query(
                "SELECT value FROM config WHERE key = 'telegram_bot_token'"
            ))
            
            if token:
                url = f"https://api.telegram.org/bot{token[0]['value']}/sendMessage"
                message = "💀 DEAD MAN'S SWITCH ACTIVADO - Sin check-in por 48h"
                data = json.dumps({'chat_id': contact, 'text': message}).encode()
                
                req = urllib.request.Request(url, data=data,
                                             headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    _ = response.read()  # Consume response to release connection
        except Exception:
            pass

# Cron job para verificar Dead Man's Switch
def check_dead_mans_switch(core) -> Dict:
    """
    Verificar y ejecutar Dead Man's Switch si es necesario.
    Ejecutar desde cron cada hora.
    """
    switch = DeadMansSwitch(core)
    status = switch.check_status()
    
    if status.get('triggered'):
        return switch.trigger_purge()
    
    return status

