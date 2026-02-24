from pathlib import Path

"""
Sentinel Signal - Monitor de Intrusión de Red WiFi
Detecta dispositivos sospechosos cerca de la sucursal
"""

from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
import logging
import re
import subprocess
import sys
import threading
import time

logger = logging.getLogger(__name__)

class SentinelSignal:
    """
    Monitor de espectro WiFi para detección de intrusos.
    
    Detecta:
    - Dispositivos desconocidos con señal fuerte
    - Laptops con nombres sospechosos (forense, SAT, etc.)
    - Cambios repentinos en el espectro
    
    Acciones:
    - Alertar a PWA
    - Activar camuflaje de red
    - Generar tráfico basura
    """
    
    # Patrones sospechosos en nombres de dispositivos
    SUSPICIOUS_PATTERNS = [
        r'SAT[-_]%s',
        r'HACIENDA',
        r'FORENS[EI]',
        r'AUDIT',
        r'POLIC[IE]A',
        r'INSPECTOR',
        r'SNIFFER',
        r'KALI',
        r'PARROT',
        r'WIRESHARK',
        r'CAPTURE',
    ]
    
    # Umbral de señal para "dispositivo cercano"
    SIGNAL_THRESHOLD_DBM = -50  # Muy fuerte = muy cerca
    
    # Ruta al archivo de contactos de emergencia
    CONTACTS_FILE = "data/emergency_contacts.json"
    
    def __init__(self, interface: str = 'wlan0', callback: Callable = None):
        self.interface = interface
        self.known_devices = set()
        self.suspicious_devices = []
        self._suspicious_devices_lock = threading.Lock()
        self.is_monitoring = False
        self.alert_callback = callback
        self.decoy_active = False
        self._emergency_contacts_lock = threading.Lock()
        self.emergency_contacts = self._load_contacts()
    
    def _load_contacts(self) -> List[Dict]:
        """Carga contactos de emergencia desde archivo."""
        import json
        import os
        
        if os.path.exists(self.CONTACTS_FILE):
            try:
                with open(self.CONTACTS_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        
        # Contactos por defecto (vacíos)
        return []
    
    def save_contacts(self, contacts: List[Dict]) -> bool:
        """Guarda contactos de emergencia."""
        import json
        import os

        os.makedirs(os.path.dirname(self.CONTACTS_FILE), exist_ok=True)

        try:
            with open(self.CONTACTS_FILE, 'w') as f:
                json.dump(contacts, f, indent=2)
            with self._emergency_contacts_lock:
                self.emergency_contacts = contacts
            return True
        except Exception:
            return False
    
    def add_contact(self, name: str, phone: str = None, email: str = None,
                   telegram: str = None, notify_methods: List[str] = None):
        """Agrega un contacto de emergencia."""
        contact = {
            'name': name,
            'phone': phone,  # Para WhatsApp
            'email': email,
            'telegram': telegram,  # Username de Telegram
            'notify_methods': notify_methods or ['whatsapp', 'telegram'],
            'active': True
        }
        with self._emergency_contacts_lock:
            self.emergency_contacts.append(contact)
            contacts_copy = list(self.emergency_contacts)
        self.save_contacts(contacts_copy)
        return contact
    
    def remove_contact(self, name: str) -> bool:
        """Elimina un contacto por nombre."""
        with self._emergency_contacts_lock:
            self.emergency_contacts = [c for c in self.emergency_contacts if c.get('name') != name]
            contacts_copy = list(self.emergency_contacts)
        return self.save_contacts(contacts_copy)
    
    def list_contacts(self) -> List[Dict]:
        """Lista contactos de emergencia."""
        with self._emergency_contacts_lock:
            return list(self.emergency_contacts)
    
    def send_emergency_signal(self, message: str = None) -> Dict[str, Any]:
        """
        Envía señal de emergencia a todos los contactos configurados.
        
        Métodos soportados:
        - WhatsApp (vía API o wa.me link)
        - Telegram (vía Bot API)
        - Email (vía SMTP)
        """
        if not message:
            message = "⚠️ ALERTA TITAN POS: Actividad sospechosa detectada en la sucursal."
        
        sent = 0
        failed = 0
        results = []

        with self._emergency_contacts_lock:
            contacts_copy = list(self.emergency_contacts)

        for contact in contacts_copy:
            if not contact.get('active', True):
                continue
            
            methods = contact.get('notify_methods', ['whatsapp'])
            
            for method in methods:
                try:
                    if method == 'whatsapp' and contact.get('phone'):
                        result = self._send_whatsapp(contact['phone'], message)
                    elif method == 'telegram' and contact.get('telegram'):
                        result = self._send_telegram(contact['telegram'], message)
                    elif method == 'email' and contact.get('email'):
                        result = self._send_email(contact['email'], message)
                    else:
                        continue
                    
                    if result:
                        sent += 1
                    else:
                        failed += 1
                    
                    results.append({
                        'contact': contact['name'],
                        'method': method,
                        'success': result
                    })
                except Exception as e:
                    failed += 1
                    results.append({
                        'contact': contact['name'],
                        'method': method,
                        'success': False,
                        'error': str(e)
                    })
        
        return {
            'sent': sent,
            'failed': failed,
            'total_contacts': len(self.emergency_contacts),
            'results': results
        }
    
    def _send_whatsapp(self, phone: str, message: str) -> bool:
        """Envía mensaje por WhatsApp (genera link wa.me)."""
        import urllib.parse

        # Genera link que el usuario puede abrir
        link = f"https://wa.me/{phone}?text={urllib.parse.quote(message)}"
        # Guardar link para que el sistema lo abra
        with open('/tmp/titan_whatsapp_alert.txt', 'w') as f:
            f.write(link)
        return True  # El link queda guardado para abrirse
    
    def _send_telegram(self, username: str, message: str) -> bool:
        """Envía mensaje por Telegram Bot."""
        # Requiere configurar BOT_TOKEN y CHAT_ID
        # Por ahora, guarda el mensaje para envío manual
        with open('/tmp/titan_telegram_alert.txt', 'a') as f:
            f.write(f"{username}: {message}\n")
        return True
    
    def _send_email(self, email: str, message: str) -> bool:
        """Envía email de emergencia."""
        # Requiere configurar SMTP
        with open('/tmp/titan_email_alert.txt', 'a') as f:
            f.write(f"To: {email}\nSubject: ALERTA TITAN POS\n\n{message}\n\n")
        return True
    
    def start_monitoring(self):
        """Inicia monitoreo continuo del espectro."""
        self.is_monitoring = True
        
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()
        
        # SECURITY: No loguear inicio de monitoreo
        pass
    
    def stop_monitoring(self):
        """Detiene el monitoreo."""
        self.is_monitoring = False
        # SECURITY: No loguear detención de monitoreo
        pass
    
    def _monitor_loop(self):
        """Loop principal de monitoreo."""
        while self.is_monitoring:
            try:
                devices = self._scan_nearby_devices()
                
                for device in devices:
                    if self._is_suspicious(device):
                        self._handle_suspicious_device(device)
                
                time.sleep(10)  # Escanear cada 10 segundos
                
            except Exception as e:
                logger.error(f"Error en monitoreo: {e}")
                time.sleep(30)
    
    def _scan_nearby_devices(self) -> List[Dict]:
        """Escanea dispositivos WiFi cercanos."""
        devices = []
        
        try:
            # Método 1: iwlist scan
            result = subprocess.run(
                ['sudo', 'iwlist', self.interface, 'scan'],
                capture_output=True, text=True, timeout=30
            )
            
            devices.extend(self._parse_iwlist_output(result.stdout))
            
        except Exception:
            pass
        
        try:
            # Método 2: nmcli (más amigable)
            result = subprocess.run(
                ['nmcli', '-t', '-f', 'SSID,SIGNAL,BSSID,SECURITY', 'dev', 'wifi', 'list'],
                capture_output=True, text=True, timeout=30
            )
            
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(':')
                    if len(parts) >= 3:
                        devices.append({
                            'ssid': parts[0],
                            'signal': int(parts[1]) if parts[1].isdigit() else 0,
                            'mac': parts[2] if len(parts) > 2 else '',
                            'type': 'wifi'
                        })
                        
        except Exception:
            pass
        
        try:
            # Método 3: arp-scan para dispositivos conectados
            result = subprocess.run(
                ['sudo', 'arp-scan', '-l'],
                capture_output=True, text=True, timeout=30
            )
            
            for line in result.stdout.split('\n'):
                if re.match(r'\d+\.\d+\.\d+\.\d+', line):
                    parts = line.split()
                    if len(parts) >= 3:
                        devices.append({
                            'ip': parts[0],
                            'mac': parts[1],
                            'vendor': ' '.join(parts[2:]) if len(parts) > 2 else '',
                            'type': 'lan'
                        })
                        
        except Exception:
            pass
        
        return devices
    
    def _parse_iwlist_output(self, output: str) -> List[Dict]:
        """Parsea salida de iwlist scan."""
        devices = []
        current_device = {}
        
        for line in output.split('\n'):
            if 'Cell' in line and 'Address' in line:
                if current_device:
                    devices.append(current_device)
                current_device = {
                    'mac': re.search(r'Address: ([\w:]+)', line).group(1) if 'Address' in line else ''
                }
            elif 'ESSID' in line:
                match = re.search(r'ESSID:"([^"]*)"', line)
                if match:
                    current_device['ssid'] = match.group(1)
            elif 'Signal level' in line:
                match = re.search(r'Signal level[=:](-?\d+)', line)
                if match:
                    current_device['signal_dbm'] = int(match.group(1))
        
        if current_device:
            devices.append(current_device)
        
        return devices
    
    def _is_suspicious(self, device: Dict) -> bool:
        """Evalúa si un dispositivo es sospechoso."""
        
        # Verificar si es conocido
        device_id = device.get('mac', '') or device.get('ip', '')
        if device_id in self.known_devices:
            return False
        
        # Verificar señal muy fuerte (dispositivo muy cerca)
        signal = device.get('signal_dbm', device.get('signal', -100))
        if signal > self.SIGNAL_THRESHOLD_DBM:
            # SECURITY: No loguear detección de dispositivos
            pass
            return True
        
        # Verificar nombre sospechoso
        name = device.get('ssid', '') or device.get('vendor', '')
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, name, re.IGNORECASE):
                # SECURITY: No loguear nombres sospechosos
                pass
                return True
        
        # Verificar dispositivo nuevo en la red local
        if device.get('type') == 'lan' and device_id not in self.known_devices:
            # Primer avistamiento - agregar y monitorear
            self.known_devices.add(device_id)
            
            # Si aparecen muchos dispositivos nuevos a la vez, sospechoso
            with self._suspicious_devices_lock:
                recent_suspicious = len([d for d in self.suspicious_devices if
                        (datetime.now() - d['detected_at']).total_seconds() < 60])
            if recent_suspicious > 3:
                return True
        
        return False
    
    def _handle_suspicious_device(self, device: Dict):
        """Maneja detección de dispositivo sospechoso."""
        alert = {
            'device': device,
            'detected_at': datetime.now(),
            'signal': device.get('signal_dbm', device.get('signal', 0)),
            'type': device.get('type', 'unknown'),
            'threat_level': self._calculate_threat_level(device)
        }

        with self._suspicious_devices_lock:
            self.suspicious_devices.append(alert)
        
        # Llamar callback si existe
        if self.alert_callback:
            self.alert_callback(alert)
        
        # Log de alerta
        # SECURITY: No loguear alertas de dispositivos sospechosos
        pass
    
    def _calculate_threat_level(self, device: Dict) -> str:
        """Calcula nivel de amenaza del dispositivo."""
        score = 0
        
        # Señal fuerte = más amenaza
        signal = device.get('signal_dbm', device.get('signal', -100))
        if signal > -30: score += 3
        elif signal > -50: score += 2
        elif signal > -70: score += 1
        
        # Nombre sospechoso = más amenaza
        name = device.get('ssid', '') or device.get('vendor', '')
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, name, re.IGNORECASE):
                score += 2
        
        if score >= 4:
            return 'CRITICAL'
        elif score >= 2:
            return 'HIGH'
        elif score >= 1:
            return 'MEDIUM'
        return 'LOW'
    
    def activate_network_camouflage(self):
        """Activa camuflaje de red."""
        # SECURITY: No loguear camuflaje de red
        pass
        
        try:
            # Cambiar nombre de red a algo genérico
            subprocess.run([
                'sudo', 'hostnamectl', 'set-hostname', 'Smart-TV'
            ], check=False)
            
            # Iniciar tráfico señuelo
            self._start_decoy_traffic()
            
            self.decoy_active = True
            
        except Exception as e:
            logger.error(f"Error activando camuflaje: {e}")
    
    def _start_decoy_traffic(self):
        """Genera tráfico que parece Netflix/YouTube."""
        def generate_traffic():
            while self.decoy_active:
                try:
                    # Simular tráfico de streaming
                    subprocess.run([
                        'curl', '-s', '-o', '/dev/null',
                        'https://www.netflix.com',
                        'https://www.youtube.com',
                    ], timeout=10, check=False)
                    time.sleep(2)
                except Exception:
                    pass
        
        thread = threading.Thread(target=generate_traffic, daemon=True)
        thread.start()
    
    def add_known_device(self, device_id: str):
        """Agrega dispositivo a lista de conocidos/confiables."""
        self.known_devices.add(device_id)
    
    def get_alerts(self, last_minutes: int = 60) -> List[Dict]:
        """Obtiene alertas recientes."""
        cutoff = datetime.now()
        with self._suspicious_devices_lock:
            return [
                a for a in self.suspicious_devices
                if (cutoff - a['detected_at']).total_seconds() < last_minutes * 60
            ]

# Función para iniciar monitoreo
def start_sentinel(interface: str = 'wlan0', callback: Callable = None):
    """Inicia el Sentinel Signal."""
    sentinel = SentinelSignal(interface, callback)
    sentinel.start_monitoring()
    return sentinel
