"""
Network Configuration - Auto-detección de configuración de red
Centraliza la configuración de IPs y puertos para TITAN POS
"""

from typing import Any, Dict, Optional
import json
import logging
import os
from pathlib import Path
import socket

logger = logging.getLogger(__name__)

class NetworkConfig:
    """
    Configuración centralizada de red.
    Detecta automáticamente IPs y puertos, o los lee de config.json
    """
    
    _instance = None
    _config: Dict[str, Any] = {}
    
    # Puertos por defecto
    DEFAULT_API_PORT = 8080
    DEFAULT_WS_PORT = 8082
    DEFAULT_PWA_PORT = 8081
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """Carga la configuración desde config.json o usa defaults."""
        config_paths = [
            Path(__file__).resolve().parent.parent.parent / 'data/config/config.json',
            Path(__file__).resolve().parent.parent.parent / 'config.json',
            Path.home() / '.titan_pos/config.json'
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        self._config = json.load(f)
                    logger.info(f"📡 Network config loaded from {config_path}")
                    return
                # FIX 2026-02-01: Agregar logging mínimo en lugar de excepción silenciada
                except Exception as e:
                    logger.debug(f"Error loading config from {config_path}: {e}")

        # Usar configuración por defecto
        self._config = {}
        logger.info("📡 Using default network configuration")
    
    def get_local_ip(self) -> str:
        """Detecta la IP local de la máquina."""
        # 1. Intentar desde config
        configured_ip = self._config.get('network', {}).get('local_ip')
        if configured_ip:
            return configured_ip
        
        # 2. Intentar obtener IP de Tailscale
        tailscale_ip = self._get_tailscale_ip()
        if tailscale_ip:
            return tailscale_ip
        
        # 3. Detectar IP de red local
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        # FIX 2026-02-01: Agregar logging mínimo en lugar de excepción silenciada
        except Exception as e:
            logger.debug(f"Error detecting local IP: {e}")

        # 4. Fallback
        return "127.0.0.1"
    
    def _get_tailscale_ip(self) -> Optional[str]:
        """Obtiene la IP de Tailscale si está disponible."""
        try:
            import subprocess
            result = subprocess.run(
                ['tailscale', 'ip', '-4'],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                ip = result.stdout.strip().split('\n')[0]
                if ip.startswith('100.'):
                    logger.info(f"🔗 Tailscale IP detected: {ip}")
                    return ip
        # FIX 2026-02-01: Agregar logging mínimo en lugar de excepción silenciada
        except Exception as e:
            logger.debug(f"Error getting Tailscale IP: {e}")
        return None
    
    def get_server_ip(self) -> str:
        """Obtiene la IP del servidor central (para clientes)."""
        # Primero intentar desde config
        server_ip = self._config.get('sync', {}).get('server_ip')
        if server_ip:
            return server_ip
        
        # Si es el servidor, usar IP local
        return self.get_local_ip()
    
    def get_api_port(self) -> int:
        """Obtiene el puerto de la API REST."""
        return self._config.get('network', {}).get('api_port', self.DEFAULT_API_PORT)
    
    def get_ws_port(self) -> int:
        """Obtiene el puerto del WebSocket."""
        return self._config.get('network', {}).get('ws_port', self.DEFAULT_WS_PORT)
    
    def get_api_url(self, use_local: bool = True) -> str:
        """Obtiene la URL completa de la API."""
        ip = "localhost" if use_local else self.get_server_ip()
        port = self.get_api_port()
        return f"http://{ip}:{port}"
    
    def get_ws_url(self, use_local: bool = True) -> str:
        """Obtiene la URL completa del WebSocket."""
        ip = "localhost" if use_local else self.get_server_ip()
        port = self.get_ws_port()
        return f"http://{ip}:{port}"
    
    def get_central_url(self) -> Optional[str]:
        """Obtiene la URL del servidor central para sincronización."""
        return self._config.get('sync', {}).get('central_url')
    
    def is_server(self) -> bool:
        """Determina si esta instancia es el servidor central."""
        return self._config.get('sync', {}).get('is_server', True)
    
    def update_config(self, key: str, value: Any):
        """Actualiza un valor en la configuración."""
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
    
    def save_config(self, config_path: Path = None):
        """Guarda la configuración actual."""
        if config_path is None:
            config_path = Path(__file__).resolve().parent.parent.parent / 'data/config/config.json'
        
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)
        logger.info(f"📡 Config saved to {config_path}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Retorna la configuración actual como diccionario."""
        return {
            'local_ip': self.get_local_ip(),
            'server_ip': self.get_server_ip(),
            'api_port': self.get_api_port(),
            'ws_port': self.get_ws_port(),
            'api_url': self.get_api_url(),
            'ws_url': self.get_ws_url(),
            'is_server': self.is_server()
        }

# Singleton global
_network_config: Optional[NetworkConfig] = None

def get_network_config() -> NetworkConfig:
    """Obtiene la instancia global de configuración de red."""
    global _network_config
    if _network_config is None:
        _network_config = NetworkConfig()
    return _network_config

# Funciones de conveniencia
def get_api_url(use_local: bool = True) -> str:
    """Obtiene la URL de la API."""
    return get_network_config().get_api_url(use_local)

def get_ws_url(use_local: bool = True) -> str:
    """Obtiene la URL del WebSocket."""
    return get_network_config().get_ws_url(use_local)

def get_local_ip() -> str:
    """Obtiene la IP local."""
    return get_network_config().get_local_ip()

def get_server_ip() -> str:
    """Obtiene la IP del servidor."""
    return get_network_config().get_server_ip()
