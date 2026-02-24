"""
Network Defaults - Centralized network configuration for TITAN POS
All network-related defaults are defined here to avoid hardcoding in multiple files.
"""

from typing import Any, Dict, List
import json
import os
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT VALUES
# These can be overridden by config files or environment variables
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULTS = {
    # Gateway (Multi-terminal server)
    'gateway_host': '127.0.0.1',
    'gateway_port': 8000,
    
    # WebSocket server
    'websocket_host': '127.0.0.1',
    'websocket_port': 8082,
    
    # API server
    'api_host': '127.0.0.1',
    'api_port': 8080,
    
    # CORS origins for development
    'cors_origins_dev': [
        'http://localhost:3000',
        'http://localhost:8080',
        'http://localhost:5173',  # Vite default
    ],
    
    # Tor proxy (standard port)
    'tor_host': '127.0.0.1',
    'tor_port': 9050,
}

def _get_project_root() -> Path:
    """Get project root directory."""
    # This file is at app/utils/network_defaults.py
    return Path(__file__).parent.parent.parent

def _load_network_config() -> Dict[str, Any]:
    """Load network configuration from file if exists."""
    config_path = _get_project_root() / 'data' / 'config' / 'network.json'
    
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    
    return {}

def get_network_config() -> Dict[str, Any]:
    """
    Get merged network configuration.
    
    Priority:
    1. Environment variables
    2. network.json config file  
    3. Defaults
    
    Returns:
        Dictionary with all network settings
    """
    config = DEFAULTS.copy()
    
    # Override with file config
    file_config = _load_network_config()
    config.update(file_config)
    
    # Override with environment variables
    if os.getenv('GATEWAY_HOST'):
        config['gateway_host'] = os.getenv('GATEWAY_HOST')
    if os.getenv('GATEWAY_PORT'):
        config['gateway_port'] = int(os.getenv('GATEWAY_PORT'))
    if os.getenv('WEBSOCKET_PORT'):
        config['websocket_port'] = int(os.getenv('WEBSOCKET_PORT'))
    if os.getenv('API_PORT'):
        config['api_port'] = int(os.getenv('API_PORT'))
    
    return config

# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_gateway_url(use_local: bool = True) -> str:
    """Get gateway URL."""
    cfg = get_network_config()
    host = 'localhost' if use_local else cfg['gateway_host']
    return f"http://{host}:{cfg['gateway_port']}"

def get_websocket_url(use_local: bool = True) -> str:
    """Get WebSocket server URL."""
    cfg = get_network_config()
    host = 'localhost' if use_local else cfg['websocket_host']
    return f"http://{host}:{cfg['websocket_port']}"

def get_api_url(use_local: bool = True) -> str:
    """Get API server URL."""
    cfg = get_network_config()
    host = 'localhost' if use_local else cfg['api_host']
    return f"http://{host}:{cfg['api_port']}"

def get_cors_origins() -> List[str]:
    """Get CORS origins for development."""
    cfg = get_network_config()
    return cfg.get('cors_origins_dev', DEFAULTS['cors_origins_dev'])

def get_tor_proxy() -> str:
    """Get Tor SOCKS5 proxy address."""
    cfg = get_network_config()
    return f"socks5://{cfg['tor_host']}:{cfg['tor_port']}"

def save_network_config(config: Dict[str, Any]) -> bool:
    """
    Save network configuration to file.
    
    Args:
        config: Configuration dictionary to save
    
    Returns:
        True if saved successfully
    """
    config_path = _get_project_root() / 'data' / 'config' / 'network.json'
    
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving network config: {e}")
        return False
