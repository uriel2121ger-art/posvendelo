"""
Network Lockdown - Kill switch de red para inspecciones
Cierra Tailscale y bloquea puertos sensibles
"""

from typing import Any, Dict, List
from datetime import datetime
import logging
import os
import secrets
from pathlib import Path
import signal
import subprocess

logger = logging.getLogger(__name__)


def _get_lockdown_auth_code() -> str:
    """
    Obtiene el código de autorización para lockdown.
    FIX 2026-02-01: Eliminado hardcoding de credenciales.
    """
    code = os.environ.get('TITAN_LOCKDOWN_CODE')
    if code and len(code) >= 8:
        return code

    config_path = os.path.expanduser('~/.titan/lockdown.key')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                code = f.read().strip()
                if code and len(code) >= 8:
                    return code
        except Exception as e:
            logger.error(f"Error reading lockdown key: {e}")

    logger.warning("TITAN_LOCKDOWN_CODE not configured")
    return ""

class NetworkLockdown:
    """
    Kill switch de red para situaciones de inspección.
    Cierra túneles VPN y bloquea acceso a datos sensibles.
    """
    
    LOCKDOWN_FILE = Path('/tmp/.antigravity_lockdown')
    
    def __init__(self):
        self.lockdown_active = self.LOCKDOWN_FILE.exists()
    
    def activate_lockdown(self, reason: str = None) -> Dict[str, Any]:
        """
        Activa el modo lockdown de red.
        
        Efectos:
        - Detiene Tailscale
        - Bloquea puertos de BD
        - Crea archivo de lockdown
        """
        results = {
            'timestamp': datetime.now().isoformat(),
            'reason': reason,
            'actions': []
        }
        
        # 1. Detener Tailscale
        tailscale_result = self._stop_tailscale()
        results['actions'].append({
            'action': 'stop_tailscale',
            'success': tailscale_result['success']
        })
        
        # 2. Bloquear puerto de base de datos (si API activa)
        firewall_result = self._block_db_ports()
        results['actions'].append({
            'action': 'block_ports',
            'success': firewall_result['success']
        })
        
        # 3. Limpiar conexiones activas
        conn_result = self._kill_remote_sessions()
        results['actions'].append({
            'action': 'kill_sessions',
            'success': conn_result['success']
        })
        
        # 4. Crear archivo de lockdown
        self.LOCKDOWN_FILE.write_text(
            f"LOCKDOWN ACTIVE\n"
            f"Timestamp: {datetime.now().isoformat()}\n"
            f"Reason: {reason or 'Manual activation'}\n"
        )
        
        self.lockdown_active = True
        
        # SECURITY: No loguear activación de lockdown
        pass
        
        results['success'] = True
        return results
    
    def deactivate_lockdown(self, auth_code: str = None) -> Dict[str, Any]:
        """
        Desactiva el modo lockdown (requiere autenticación).
        """
        # FIX 2026-02-01: Usar comparación segura y código desde config
        expected_code = _get_lockdown_auth_code()
        if not expected_code:
            return {
                'success': False,
                'error': 'Código de autorización no configurado en servidor'
            }

        if not auth_code or not secrets.compare_digest(auth_code.encode(), expected_code.encode()):
            return {
                'success': False,
                'error': 'Código de autorización inválido'
            }
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'actions': []
        }
        
        # 1. Reiniciar Tailscale
        tailscale_result = self._start_tailscale()
        results['actions'].append({
            'action': 'start_tailscale',
            'success': tailscale_result['success']
        })
        
        # 2. Desbloquear puertos
        firewall_result = self._unblock_db_ports()
        results['actions'].append({
            'action': 'unblock_ports',
            'success': firewall_result['success']
        })
        
        # 3. Eliminar archivo de lockdown
        if self.LOCKDOWN_FILE.exists():
            self.LOCKDOWN_FILE.unlink()
        
        self.lockdown_active = False
        
        # SECURITY: No loguear desactivación de lockdown
        pass
        
        results['success'] = True
        return results
    
    def _stop_tailscale(self) -> Dict[str, Any]:
        """Detiene el servicio Tailscale."""
        try:
            # Intentar detener con tailscale down
            subprocess.run(
                ['sudo', 'tailscale', 'down'],
                capture_output=True,
                timeout=10
            )
            
            # También detener el servicio
            subprocess.run(
                ['sudo', 'systemctl', 'stop', 'tailscaled'],
                capture_output=True,
                timeout=10
            )
            
            return {'success': True}
        except Exception as e:
            logger.error(f"Error stopping Tailscale: {e}")
            return {'success': False, 'error': str(e)}
    
    def _start_tailscale(self) -> Dict[str, Any]:
        """Inicia el servicio Tailscale."""
        try:
            subprocess.run(
                ['sudo', 'systemctl', 'start', 'tailscaled'],
                capture_output=True,
                timeout=10
            )
            
            subprocess.run(
                ['sudo', 'tailscale', 'up'],
                capture_output=True,
                timeout=30
            )
            
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _block_db_ports(self) -> Dict[str, Any]:
        """
        Bloquea puertos de base de datos con iptables.
        IMPORTANTE: Preserva red LAN local (192.168.x.x y 10.x.x.x) 
        para que multi-caja siga funcionando.
        """
        ports_to_block = [5432, 3306, 27017, 8000, 8080]  # DB ports + API
        
        # Redes LAN a preservar
        local_networks = ['192.168.0.0/16', '10.0.0.0/8', '172.16.0.0/12', '127.0.0.0/8']
        
        try:
            for port in ports_to_block:
                # Primero: PERMITIR tráfico LAN local
                for network in local_networks:
                    subprocess.run(
                        ['sudo', 'iptables', '-A', 'INPUT', '-p', 'tcp',
                         '-s', network, '--dport', str(port), '-j', 'ACCEPT'],
                        capture_output=True,
                        timeout=5
                    )
                
                # Luego: BLOQUEAR todo lo demás (internet/Tailscale)
                subprocess.run(
                    ['sudo', 'iptables', '-A', 'INPUT', '-p', 'tcp', 
                     '--dport', str(port), '-j', 'DROP'],
                    capture_output=True,
                    timeout=5
                )
            
            return {
                'success': True, 
                'ports_blocked': ports_to_block,
                'lan_preserved': True,
                'note': 'Comunicación multi-caja LAN sigue funcionando'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _unblock_db_ports(self) -> Dict[str, Any]:
        """Desbloquea puertos con iptables."""
        try:
            # Flush de reglas de INPUT
            subprocess.run(
                ['sudo', 'iptables', '-F', 'INPUT'],
                capture_output=True,
                timeout=5
            )
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _kill_remote_sessions(self) -> Dict[str, Any]:
        """Termina sesiones remotas activas."""
        killed = 0
        
        try:
            # Buscar procesos SSH remotos
            result = subprocess.run(
                ['pgrep', '-f', 'sshd.*pts'],
                capture_output=True,
                text=True
            )
            
            if result.stdout:
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        killed += 1
                    except Exception:
                        pass
            
            return {'success': True, 'sessions_killed': killed}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """Estado actual del lockdown."""
        # Verificar si Tailscale está corriendo
        tailscale_running = False
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'tailscaled'],
                capture_output=True,
                text=True
            )
            tailscale_running = result.stdout.strip() == 'active'
        except Exception:
            pass
        
        return {
            'lockdown_active': self.lockdown_active,
            'tailscale_running': tailscale_running,
            'lockdown_file_exists': self.LOCKDOWN_FILE.exists(),
            'timestamp': datetime.now().isoformat()
        }
    
    def quick_lockdown(self) -> Dict[str, Any]:
        """Lockdown rápido con un solo comando (para botón de pánico)."""
        return self.activate_lockdown(reason="PANIC_BUTTON")
