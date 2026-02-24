"""
TITAN POS - Auto Discovery Service
Sistema de auto-detección de servidor central y registro automático de terminales.

Flujo:
1. Al iniciar, busca servidor central en la red
2. Si encuentra, se registra automáticamente como terminal
3. Si no encuentra, trabaja en modo local
4. Periódicamente intenta reconectar
"""
from typing import Any, Dict, Optional
import json
import logging
import os
from pathlib import Path
import socket
import threading
import time
import uuid

logger = logging.getLogger("AUTO_DISCOVERY")

# Puerto para discovery (broadcast UDP)
DISCOVERY_PORT = 54321
# Puerto del servidor central
CENTRAL_PORT = 8000
# Intervalo de búsqueda (segundos)
DISCOVERY_INTERVAL = 30

class AutoDiscoveryService:
    """Servicio de auto-descubrimiento de servidor central y terminales."""
    
    def __init__(self, config_path: str = "data/local_config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        
        # Identificador único de esta terminal
        self.machine_id = self._get_machine_id()
        
        # Estado
        self.central_found = False
        self.central_url = None
        self.terminal_id = self.config.get('terminal_id', 1)
        self.branch_id = self.config.get('branch_id', 1)
        
        # Threading
        self._running = False
        self._discovery_thread = None
    
    def _load_config(self) -> Dict[str, Any]:
        """Carga configuración existente."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    def _save_config(self):
        """Guarda configuración."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def _get_machine_id(self) -> str:
        """Obtiene un ID único para esta máquina."""
        # Intentar leer ID existente
        id_file = "data/.machine_id"
        if os.path.exists(id_file):
            try:
                with open(id_file, 'r') as f:
                    return f.read().strip()
            except Exception:
                pass
        
        # Generar nuevo ID
        machine_id = f"TITAN-{uuid.uuid4().hex[:8].upper()}"
        os.makedirs("data", exist_ok=True)
        with open(id_file, 'w') as f:
            f.write(machine_id)
        
        return machine_id
    
    def discover_central_server(self) -> Optional[str]:
        """
        Busca servidor central en la red.
        
        Métodos de búsqueda (en orden):
        1. Configuración existente (central_url)
        2. Broadcast UDP en red local
        3. IPs conocidas de Tailscale (100.64.x.x)
        """
        # Método 1: Configuración existente
        existing_url = self.config.get('central_url')
        if existing_url:
            if self._check_server(existing_url):
                return existing_url
        
        # Método 2: Broadcast UDP (red local)
        central = self._udp_discovery()
        if central:
            return central
        
        # Método 3: Escaneo de red Tailscale
        central = self._scan_tailscale_network()
        if central:
            return central
        
        return None
    
    def _check_server(self, url: str) -> bool:
        """Verifica si un servidor está disponible."""
        try:
            import urllib.request
            clean_url = url.rstrip('/')
            req = urllib.request.Request(f"{clean_url}/api/health", method='GET')
            req.add_header('User-Agent', 'TITAN-POS')
            
            with urllib.request.urlopen(req, timeout=3) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    if data.get('service') == 'titan-gateway':
                        return True
        except Exception as e:
            logger.debug(f"Servidor no disponible en {url}: {e}")
        return False
    
    def _udp_discovery(self) -> Optional[str]:
        """Busca servidor por broadcast UDP."""
        try:
            # Crear socket UDP
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(2)
            
            # Enviar mensaje de discovery
            message = json.dumps({
                'type': 'TITAN_DISCOVERY',
                'machine_id': self.machine_id
            }).encode()
            
            sock.sendto(message, ('<broadcast>', DISCOVERY_PORT))
            
            # Esperar respuesta
            try:
                data, addr = sock.recvfrom(1024)
                response = json.loads(data.decode())
                if response.get('type') == 'TITAN_CENTRAL':
                    url = f"http://{addr[0]}:{response.get('port', CENTRAL_PORT)}"
                    logger.info(f"✅ Servidor central encontrado: {url}")
                    return url
            except socket.timeout:
                pass
            
            sock.close()
        except Exception as e:
            logger.debug(f"UDP discovery error: {e}")
        
        return None
    
    def _scan_tailscale_network(self) -> Optional[str]:
        """Escanea red Tailscale buscando servidor."""
        # IPs típicas de Tailscale
        base_ips = ['100.64.0.1', '100.64.0.2', '100.64.0.3', '100.64.0.4', '100.64.0.5']
        
        for ip in base_ips:
            url = f"http://{ip}:{CENTRAL_PORT}"
            if self._check_server(url):
                logger.info(f"✅ Servidor Tailscale encontrado: {url}")
                return url
        
        return None
    
    def register_terminal(self, central_url: str) -> Dict[str, Any]:
        """Registra esta terminal en el servidor central."""
        try:
            import urllib.request
            
            registration_data = {
                'machine_id': self.machine_id,
                'hostname': socket.gethostname(),
                'branch_id': self.branch_id,
                'requested_terminal_id': self.terminal_id
            }
            
            data = json.dumps(registration_data).encode()
            req = urllib.request.Request(
                f"{central_url.rstrip('/')}/api/register-terminal",
                data=data,
                method='POST'
            )
            req.add_header('Content-Type', 'application/json')
            req.add_header('User-Agent', 'TITAN-POS')
            
            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode())
                
                if result.get('success'):
                    # Actualizar configuración con datos del servidor
                    self.terminal_id = result.get('terminal_id', self.terminal_id)
                    self.branch_id = result.get('branch_id', self.branch_id)
                    
                    self.config['terminal_id'] = self.terminal_id
                    self.config['branch_id'] = self.branch_id
                    self.config['central_url'] = central_url
                    self.config['db_mode'] = 'central'
                    
                    # Configuración PostgreSQL del servidor
                    if result.get('postgresql'):
                        self.config['postgresql'] = result['postgresql']
                    
                    self._save_config()
                    logger.info(f"✅ Terminal registrada: branch={self.branch_id}, terminal={self.terminal_id}")
                    
                return result
                
        except Exception as e:
            logger.error(f"Error registrando terminal: {e}")
            return {'success': False, 'error': str(e)}
    
    def auto_configure(self) -> Dict[str, Any]:
        """
        Proceso completo de auto-configuración.
        
        Returns:
            Dict con el resultado de la configuración:
            - mode: 'central' o 'local'
            - terminal_id: ID asignado
            - branch_id: ID de sucursal
            - central_url: URL del servidor (si aplica)
        """
        logger.info("🔍 Iniciando auto-discovery...")
        
        # Buscar servidor central
        central_url = self.discover_central_server()
        
        if central_url:
            # Encontrado! Registrar terminal
            result = self.register_terminal(central_url)
            
            if result.get('success'):
                self.central_found = True
                self.central_url = central_url
                
                return {
                    'mode': 'central',
                    'terminal_id': self.terminal_id,
                    'branch_id': self.branch_id,
                    'central_url': central_url,
                    'postgresql': self.config.get('postgresql')
                }
        
        # No encontrado, modo local
        logger.info("📁 Modo LOCAL: No se encontró servidor central")
        self.config['db_mode'] = 'local'
        self._save_config()
        
        return {
            'mode': 'local',
            'terminal_id': self.terminal_id,
            'branch_id': self.branch_id
        }
    
    def start_background_discovery(self):
        """Inicia búsqueda periódica en background."""
        if self._running:
            return
        
        self._running = True
        self._discovery_thread = threading.Thread(target=self._discovery_loop, daemon=True)
        self._discovery_thread.start()
    
    def stop(self):
        """Detiene el servicio."""
        self._running = False
    
    def _discovery_loop(self):
        """Loop de búsqueda en background."""
        while self._running:
            if not self.central_found:
                result = self.auto_configure()
                if result['mode'] == 'central':
                    logger.info("✅ Conectado a servidor central")
            else:
                # Verificar que sigue conectado
                if self.central_url and not self._check_server(self.central_url):
                    logger.warning("⚠️ Perdida conexión con servidor central")
                    self.central_found = False
            
            time.sleep(DISCOVERY_INTERVAL)
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna estado actual."""
        return {
            'machine_id': self.machine_id,
            'terminal_id': self.terminal_id,
            'branch_id': self.branch_id,
            'mode': 'central' if self.central_found else 'local',
            'central_url': self.central_url,
            'central_connected': self.central_found
        }

# Singleton
_discovery_service = None

def get_discovery_service() -> AutoDiscoveryService:
    """Obtiene o crea el servicio de auto-discovery."""
    global _discovery_service
    if _discovery_service is None:
        _discovery_service = AutoDiscoveryService()
    return _discovery_service

def auto_configure_terminal() -> Dict[str, Any]:
    """
    Función conveniente para auto-configurar la terminal.
    Llamar al inicio de la aplicación.
    """
    service = get_discovery_service()
    return service.auto_configure()

def get_terminal_info() -> Dict[str, Any]:
    """Retorna información de esta terminal."""
    service = get_discovery_service()
    return service.get_status()

# Para testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("🔍 TITAN POS - Auto Discovery Test")
    print("=" * 60)
    
    result = auto_configure_terminal()
    print(f"\nResultado: {json.dumps(result, indent=2)}")
    
    info = get_terminal_info()
    print(f"\nInfo: {json.dumps(info, indent=2)}")
