from pathlib import Path

"""
Panic Wipe - Botón de Autodestrucción de Emergencia
Atajo global para limpieza instantánea bajo inspección física
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

class PanicWipe:
    """
    Sistema de Panic Wipe para inspecciones físicas.
    
    Acciones:
    1. Desmonta RAMFS (borra logs volátiles)
    2. Cierra Tailscale
    3. Borra archivos sensibles de RAM
    4. Apaga la PC
    
    Todo en menos de 3 segundos.
    """
    
    # Rutas críticas a limpiar
    VOLATILE_PATHS = [
        '/mnt/volatile_logs',
        '/tmp/antigravity_*',
        '/run/user/*/antigravity_*',
    ]
    
    # Servicios a detener
    SERVICES_TO_KILL = [
        'tailscaled',
    ]
    
    def __init__(self, core=None):
        self.core = core
        self.armed = False
        self._trigger_callback: Optional[Callable] = None
    
    def arm(self):
        """Arma el sistema de pánico."""
        self.armed = True
        # SECURITY: No loguear armado de panic
        # FIX 2026-02-01: Stub documentado - pass intencional por seguridad
        pass  # Intencional: No hay acción adicional por seguridad
    
    def disarm(self):
        """Desarma el sistema."""
        self.armed = False
        # SECURITY: No loguear desarmado de panic
        # FIX 2026-02-01: Stub documentado - pass intencional por seguridad
        pass  # Intencional: No hay acción adicional por seguridad
    
    def trigger(self, immediate: bool = True) -> Dict[str, Any]:
        """
        Activa el Panic Wipe.
        
        immediate: Si True, apaga la PC al final
        """
        if not self.armed:
            return {'triggered': False, 'reason': 'System not armed'}
        
        start_time = time.time()
        results = {
            'triggered': True,
            'timestamp': datetime.now().isoformat(),
            'actions': []
        }
        
        # SECURITY: No loguear panic wipe
        # FIX 2026-02-01: Stub documentado - pass intencional por seguridad
        pass  # Intencional: No hay logging por seguridad

        # 1. Callback personalizado primero
        if self._trigger_callback:
            try:
                self._trigger_callback()
                results['actions'].append('custom_callback')
            except Exception:
                pass  # Emergency wipe - must continue regardless of errors
        
        # 2. Desmontar RAMFS
        try:
            self._unmount_volatile()
            results['actions'].append('unmount_ramfs')
        except Exception as e:
            results['actions'].append(f'unmount_failed: {e}')
        
        # 3. Matar servicios de red
        try:
            self._kill_network_services()
            results['actions'].append('kill_network')
        except Exception as e:
            results['actions'].append(f'network_failed: {e}')
        
        # 4. Limpiar archivos temporales
        try:
            self._wipe_temp_files()
            results['actions'].append('wipe_temp')
        except Exception as e:
            results['actions'].append(f'wipe_failed: {e}')
        
        # 5. Sync filesystem
        try:
            os.sync()
            results['actions'].append('sync')
        # FIX 2026-02-01: Stub documentado - pass intencional en emergencia
        except Exception:
            pass  # Intencional: Debe continuar independientemente de errores
        
        elapsed = time.time() - start_time
        results['elapsed_seconds'] = elapsed
        
        # SECURITY: No loguear completación de wipe
        # FIX 2026-02-01: Stub documentado - pass intencional por seguridad
        pass  # Intencional: No hay logging por seguridad

        # 6. Apagar si es inmediato
        if immediate:
            results['actions'].append('poweroff')
            self._emergency_poweroff()
        
        return results
    
    def _unmount_volatile(self):
        """Desmonta RAMFS con logs volátiles."""
        mount_points = ['/mnt/volatile_logs', '/mnt/ramfs']
        
        for mp in mount_points:
            try:
                subprocess.run(['umount', '-f', mp], 
                             capture_output=True, timeout=2)
            except Exception:
                pass  # Emergency wipe - must continue regardless of errors
    
    def _kill_network_services(self):
        """Mata servicios de red para aislar el nodo."""
        for service in self.SERVICES_TO_KILL:
            try:
                subprocess.run(['pkill', '-9', service], 
                             capture_output=True, timeout=1)
            except Exception:
                pass  # Emergency wipe - must continue regardless of errors
        
        # Detener Tailscale específicamente
        try:
            subprocess.run(['tailscale', 'down'], 
                         capture_output=True, timeout=2)
        except Exception:
            pass
    
    def _wipe_temp_files(self):
        """Borra archivos temporales sensibles."""
        import glob
        
        patterns = [
            '/tmp/antigravity*',
            '/tmp/.pos_*',
            '/run/user/*/antigravity*',
        ]
        
        for pattern in patterns:
            for path in glob.glob(pattern):
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                    elif os.path.isdir(path):
                        import shutil
                        shutil.rmtree(path)
                except Exception:
                    pass
    
    def _emergency_poweroff(self):
        """Apagado de emergencia inmediato."""
        try:
            # Intenta apagado limpio primero
            subprocess.Popen(['poweroff'], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        except Exception:
            try:
                # Si falla, fuerza apagado
                subprocess.Popen(['poweroff', '-f'], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            except Exception:
                # Último recurso: SysRq
                try:
                    with open('/proc/sysrq-trigger', 'w') as f:
                        f.write('o')  # Power off
                except Exception:
                    pass
    
    def set_trigger_callback(self, callback: Callable):
        """Configura callback personalizado al activar pánico."""
        self._trigger_callback = callback

class GlobalHotkey:
    """
    Atajo de teclado global para Panic Wipe.
    
    Uso: Ctrl+Alt+Shift+K
    """
    
    HOTKEY = 'ctrl+alt+shift+k'
    
    def __init__(self, panic_wipe: PanicWipe):
        self.panic = panic_wipe
        self._running = False
    
    def start_listener(self):
        """Inicia el listener de teclas (requiere pynput)."""
        try:
            from pynput import keyboard
            
            def on_activate():
                if self.panic.armed:
                    self.panic.trigger(immediate=True)
            
            # Definir la combinación
            hotkey = keyboard.HotKey(
                keyboard.HotKey.parse('<ctrl>+<alt>+<shift>+k'),
                on_activate
            )
            
            def for_canonical(f):
                return lambda k: f(listener.canonical(k))
            
            listener = keyboard.Listener(
                on_press=for_canonical(hotkey.press),
                on_release=for_canonical(hotkey.release)
            )
            
            listener.start()
            self._running = True
            
            # SECURITY: No loguear hotkey activo
            pass
            
            return {'active': True, 'hotkey': self.HOTKEY}
            
        except ImportError:
            # SECURITY: No loguear falta de pynput
            pass
            return {'active': False, 'reason': 'pynput not installed'}
    
    def stop_listener(self):
        """Detiene el listener."""
        self._running = False

# Script de instalación del servicio systemd
PANIC_SERVICE = """[Unit]
Description=Antigravity Panic Wipe Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 {INSTALL_DIR}/app/services/panic_wipe.py --daemon
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""

def install_panic_service():
    """Instala el servicio systemd para panic wipe."""
    service_path = '/etc/systemd/system/antigravity-panic.service'
    
    try:
        with open(service_path, 'w') as f:
            f.write(PANIC_SERVICE)
        
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        subprocess.run(['systemctl', 'enable', 'antigravity-panic'], check=True)
        subprocess.run(['systemctl', 'start', 'antigravity-panic'], check=True)
        
        return {'installed': True, 'service': 'antigravity-panic'}
    except Exception as e:
        return {'installed': False, 'error': str(e)}

# Modo daemon
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--daemon', action='store_true')
    parser.add_argument('--trigger', action='store_true')
    args = parser.parse_args()
    
    if args.trigger:
        # Trigger manual
        panic = PanicWipe()
        panic.arm()
        panic.trigger(immediate=False)  # No apagar para testing
        
    elif args.daemon:
        # Modo daemon con hotkey
        logging.basicConfig(level=logging.INFO)
        
        panic = PanicWipe()
        panic.arm()
        
        hotkey = GlobalHotkey(panic)
        result = hotkey.start_listener()
        
        if result.get('active'):
            print(f"Panic Wipe daemon activo. Hotkey: {hotkey.HOTKEY}")
            # Mantener vivo
            while True:
                time.sleep(60)
