from pathlib import Path

"""
Hardware Tripwire - Sensor de Intrusión Física
Detecta si la Mini-PC fue desconectada o manipulada
"""

from typing import Any, Callable, Dict, Optional
from datetime import datetime
import logging
import os
import subprocess
import sys
import threading
import time

logger = logging.getLogger(__name__)

class HardwareTripwire:
    """
    Sistema de detección de intrusión física.
    
    Monitorea:
    - Desconexión de periféricos críticos
    - Cambios de voltaje/temperatura
    - Ausencia de YubiKey en reinicio (SOLO SI ESTÁ HABILITADO)
    
    ADVERTENCIA: La protección de YubiKey está DESHABILITADA por defecto.
    Si la habilitas y hay un corte de luz sin YubiKey, el disco se destruye.
    
    Si detecta manipulación (con yubikey_required=True):
    - Ejecuta shred preventivo
    - Corrompe tabla de particiones
    - El disco queda como "RAW"
    """
    
    # Archivos críticos de hardware
    TEMP_SENSORS = [
        '/sys/class/thermal/thermal_zone0/temp',
        '/sys/class/hwmon/hwmon0/temp1_input',
    ]
    
    VOLTAGE_FILES = [
        '/sys/class/power_supply/AC/online',
        '/sys/bus/acpi/drivers/battery/',
    ]
    
    def __init__(self, 
                 yubikey_required: bool = False,  # CAMBIADO: Seguro por defecto
                 on_intrusion: Callable = None):
        self.yubikey_required = yubikey_required
        self.on_intrusion = on_intrusion
        self.is_monitoring = False
        self.baseline = {}
        self.intrusion_detected = False
    
    def initialize(self):
        """Establece línea base de hardware."""
        # SECURITY: No loguear inicialización de tripwire
        pass
        
        self.baseline = {
            'usb_devices': self._get_usb_devices(),
            'network_interfaces': self._get_network_interfaces(),
            'mounted_drives': self._get_mounted_drives(),
            'temperature': self._get_temperature(),
            'boot_time': self._get_boot_time(),
            'yubikey_present': self._check_yubikey(),
        }
        
        # SECURITY: No loguear línea base
        pass
    
    def start_monitoring(self):
        """Inicia monitoreo continuo."""
        self.is_monitoring = True
        self.initialize()
        
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()
        
        # SECURITY: No loguear activación de monitoreo
        pass
    
    def stop_monitoring(self):
        """Detiene monitoreo."""
        self.is_monitoring = False
    
    def _monitor_loop(self):
        """Loop principal de monitoreo."""
        while self.is_monitoring:
            try:
                self._check_for_intrusion()
                time.sleep(5)  # Verificar cada 5 segundos
            except Exception as e:
                logger.error(f"Error en monitoreo: {e}")
                time.sleep(10)
    
    def _check_for_intrusion(self):
        """Verifica señales de intrusión."""
        intrusions = []
        
        # 1. USB críticos desconectados
        current_usb = self._get_usb_devices()
        critical_lost = self._find_lost_critical_devices(current_usb)
        if critical_lost:
            intrusions.append({
                'type': 'usb_disconnect',
                'details': critical_lost
            })
        
        # 2. Cambio brusco de temperatura (indicativo de chasis abierto)
        current_temp = self._get_temperature()
        if self.baseline.get('temperature') and current_temp:
            temp_diff = abs(current_temp - self.baseline['temperature'])
            if temp_diff > 15:  # Más de 15°C de diferencia
                intrusions.append({
                    'type': 'temperature_anomaly',
                    'details': f"Δ{temp_diff}°C"
                })
        
        # 3. Desconexión de red repentina
        current_net = self._get_network_interfaces()
        if len(current_net) < len(self.baseline.get('network_interfaces', [])):
            intrusions.append({
                'type': 'network_disconnect',
                'details': 'Interfaz de red perdida'
            })
        
        if intrusions:
            self._handle_intrusion(intrusions)
    
    def _find_lost_critical_devices(self, current_devices: list) -> list:
        """Encuentra dispositivos críticos que fueron desconectados."""
        critical_patterns = ['yubikey', 'keyboard', 'printer', 'barcode']
        baseline_devices = self.baseline.get('usb_devices', [])
        
        lost = []
        for device in baseline_devices:
            device_lower = device.lower()
            for pattern in critical_patterns:
                if pattern in device_lower:
                    if device not in current_devices:
                        lost.append(device)
        
        return lost
    
    def _handle_intrusion(self, intrusions: list):
        """Maneja detección de intrusión."""
        if self.intrusion_detected:
            return
        
        self.intrusion_detected = True
        
        # SECURITY: No loguear intrusión detectada
        pass
        
        # Callback si existe
        if self.on_intrusion:
            self.on_intrusion(intrusions)
    
    def check_safe_boot(self) -> Dict[str, Any]:
        """
        Verificación a ejecutar en cada arranque.
        Si no hay YubiKey, ejecutar auto-protección.
        """
        # SECURITY: No loguear verificación de arranque
        pass
        
        yubikey_present = self._check_yubikey()
        
        if self.yubikey_required and not yubikey_present:
            # SECURITY: No loguear falta de YubiKey
            pass
            
            # Verificar si es arranque forzado (después de desconexión)
            if self._was_unexpected_shutdown():
                # SECURITY: No loguear detección de intrusión
                pass
                return self._execute_boot_protection()
            
            return {
                'safe': False,
                'reason': 'YubiKey no presente',
                'action': 'waiting_for_key'
            }
        
        return {
            'safe': True,
            'yubikey': yubikey_present
        }
    
    def _was_unexpected_shutdown(self) -> bool:
        """Detecta si el último shutdown fue inesperado."""
        try:
            # Verificar si el flag de shutdown limpio existe
            clean_shutdown_flag = '/var/run/antigravity_clean_shutdown'
            
            if os.path.exists(clean_shutdown_flag):
                os.remove(clean_shutdown_flag)
                return False  # Shutdown fue limpio
            
            return True  # No hubo flag = shutdown inesperado
            
        except Exception:
            return True  # Por seguridad, asumir inesperado
    
    def _execute_boot_protection(self) -> Dict[str, Any]:
        """
        Ejecuta protección de arranque cuando hay intrusion.
        Hace el disco inutilizable.
        """
        # SECURITY: No loguear protección de arranque
        pass
        
        try:
            # 1. Shred sobre sectores críticos
            self._shred_partition_table()
            
            # 2. El sistema no podrá continuar
            return {
                'safe': False,
                'action': 'protection_executed',
                'result': 'disk_corrupted'
            }
            
        except Exception as e:
            logger.error(f"Error en protección: {e}")
            return {
                'safe': False,
                'error': str(e)
            }
    
    def _shred_partition_table(self):
        """Destruye tabla de particiones."""
        try:
            # Encontrar disco principal
            root_device = subprocess.check_output(
                ['findmnt', '-n', '-o', 'SOURCE', '/'],
                text=True
            ).strip()
            
            # Obtener dispositivo base (sin número de partición)
            base_device = ''.join(c for c in root_device if not c.isdigit())
            
            # Shred primeros 1MB
            subprocess.run([
                'dd', 'if=/dev/urandom', f'of={base_device}',
                'bs=1M', 'count=1', 'conv=notrunc'
            ], check=False, timeout=30)
            
            # SECURITY: No loguear destrucción de tabla de particiones
            pass
            
        except Exception as e:
            logger.error(f"Error en shred: {e}")
    
    def _get_usb_devices(self) -> list:
        """Obtiene lista de dispositivos USB."""
        try:
            result = subprocess.run(
                ['lsusb'], capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip().split('\n')
        except Exception:
            return []
    
    def _get_network_interfaces(self) -> list:
        """Obtiene interfaces de red activas."""
        try:
            result = subprocess.run(
                ['ip', 'link', 'show', 'up'],
                capture_output=True, text=True, timeout=10
            )
            interfaces = []
            for line in result.stdout.split('\n'):
                if ':' in line and 'state UP' in line:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        interfaces.append(parts[1].strip())
            return interfaces
        except Exception:
            return []
    
    def _get_mounted_drives(self) -> list:
        """Obtiene drives montados."""
        try:
            result = subprocess.run(
                ['mount'], capture_output=True, text=True, timeout=10
            )
            drives = []
            for line in result.stdout.split('\n'):
                if line.startswith('/dev'):
                    drives.append(line.split()[0])
            return drives
        except Exception:
            return []
    
    def _get_temperature(self) -> Optional[float]:
        """Obtiene temperatura del CPU."""
        for sensor in self.TEMP_SENSORS:
            try:
                with open(sensor, 'r') as f:
                    temp = int(f.read().strip()) / 1000  # millicelsius to celsius
                    return temp
            except Exception:
                continue
        return None
    
    def _get_boot_time(self) -> Optional[float]:
        """Obtiene timestamp del último boot."""
        try:
            with open('/proc/uptime', 'r') as f:
                uptime = float(f.read().split()[0])
                return time.time() - uptime
        except Exception:
            return None
    
    def _check_yubikey(self) -> bool:
        """Verifica si hay YubiKey conectada."""
        try:
            result = subprocess.run(
                ['lsusb'], capture_output=True, text=True, timeout=10
            )
            return 'yubico' in result.stdout.lower()
        except Exception:
            return False
    
    def set_clean_shutdown_flag(self):
        """Marca que el shutdown fue limpio (llamar antes de apagar)."""
        try:
            with open('/var/run/antigravity_clean_shutdown', 'w') as f:
                f.write('1')
        except Exception:
            pass

# Función para systemd service
def create_boot_check_service():
    """Genera archivo de servicio para verificación de arranque."""
    service_content = """
[Unit]
Description=Antigravity Hardware Tripwire Boot Check
DefaultDependencies=no
Before=systemd-user-sessions.service

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 {INSTALL_DIR}/app/services/hardware_tripwire.py --boot-check
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""
    
    try:
        with open('/etc/systemd/system/antigravity-tripwire.service', 'w') as f:
            f.write(service_content)
        
        subprocess.run(['systemctl', 'daemon-reload'], check=False)
        subprocess.run(['systemctl', 'enable', 'antigravity-tripwire'], check=False)
        
        return True
    except Exception:
        return False

# Entry point para boot check
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--boot-check', action='store_true')
    args = parser.parse_args()
    
    if args.boot_check:
        tripwire = HardwareTripwire()
        result = tripwire.check_safe_boot()
        print(f"Boot check result: {result}")
