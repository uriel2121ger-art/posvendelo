"""
TITAN POS - Terminal Heartbeat Service (REFACTORIZADO)

Usa la clase base BackgroundService para eliminar código duplicado.
"""

from typing import Any, Dict, Optional
from datetime import datetime
import logging

try:
    import requests
except ImportError:
    requests = None

# Importar clase base
try:
    from app.utils.optimization import BackgroundService, with_retry
except ImportError:
    # Fallback si no existe
    BackgroundService = object
    def with_retry(*args, **kwargs):
        def decorator(f):
            return f
        return decorator

logger = logging.getLogger(__name__)

class TerminalHeartbeatService(BackgroundService):
    """
    Servicio de heartbeat refactorizado usando BackgroundService.
    
    Envía actualizaciones periódicas al Gateway central.
    """
    
    def __init__(self, pos_core, config: Dict[str, Any]):
        """
        Initialize heartbeat service.
        
        Args:
            pos_core: POSCore instance for database access
            config: Configuration dictionary with gateway info
        """
        self.core = pos_core
        self.config = config
        
        # Soporta central_url (nuevo) o central_server (legacy)
        self.gateway_url = config.get("central_url", "") or config.get("central_server", "")
        self.terminal_id = config.get("terminal_id", 1)
        self.branch_id = config.get("branch_id", 1)
        self.terminal_name = config.get("terminal_name", "") or config.get("branch_name", f"Terminal {self.terminal_id}")
        self.api_token = config.get("central_token", "") or config.get("api_token", "")
        
        interval = config.get("heartbeat_interval", 60)
        enabled = config.get("heartbeat_enabled", True) and bool(self.gateway_url)
        
        # Inicializar clase base
        super().__init__(
            name="TerminalHeartbeat",
            interval=interval,
            enabled=enabled,
            max_consecutive_errors=10
        )
    
    def _get_payload(self) -> Dict[str, Any]:
        """Gather current terminal status for heartbeat."""
        payload = {
            "terminal_id": self.terminal_id,
            "terminal_name": self.terminal_name,
            "branch_id": self.branch_id,
            "timestamp": datetime.now().isoformat(),
            "status": "online"
        }
        
        try:
            # Today's sales
            result = self.core.db.execute_query("""
                SELECT COUNT(*) as cnt, COALESCE(SUM(total), 0) as tot 
                FROM sales 
                WHERE CAST(created_at AS DATE) = CURRENT_DATE
                AND status = 'completed'
            """)
            if result:
                payload["today_sales"] = result[0]['cnt'] or 0
                payload["today_total"] = round(result[0]['tot'] or 0, 2)
            
            # Active turn
            turn_result = self.core.db.execute_query("""
                SELECT id, user_id, start_timestamp 
                FROM turns 
                WHERE status = 'open' 
                ORDER BY id DESC LIMIT 1
            """)
            if turn_result:
                turn = turn_result[0]
                payload["active_turn"] = {
                    "id": turn['id'],
                    "user_id": turn['user_id'],
                    "started": turn['start_timestamp']
                }
            
            # Pending sync
            sync_result = self.core.db.execute_query("SELECT COUNT(*) as cnt FROM sales WHERE synced = 0 OR synced IS NULL")
            if sync_result:
                payload["pending_sync"] = sync_result[0]['cnt'] or 0
            
            # Product count
            prod_result = self.core.db.execute_query("SELECT COUNT(*) as cnt FROM products WHERE is_active = 1")
            if prod_result:
                payload["product_count"] = prod_result[0]['cnt'] or 0
                
        except Exception as e:
            logger.error(f"Error gathering heartbeat data: {e}")
            payload["error"] = str(e)
            
        return payload
    
    @with_retry(max_retries=2, base_delay=1.0, exceptions=(requests.exceptions.RequestException,) if requests else (Exception,))
    def _send_to_gateway(self, payload: Dict[str, Any]) -> bool:
        """Send heartbeat to gateway with retry."""
        if not requests:
            return False
            
        # gateway_url ya incluye protocolo y puerto (ej: http://100.81.7.8:8888)
        base_url = self.gateway_url.rstrip('/')
        if not base_url.startswith('http'):
            base_url = f"http://{base_url}"
        url = f"{base_url}/api/v1/heartbeat"
        
        headers = {}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code == 200
    
    def _execute(self) -> bool:
        """Execute heartbeat (called by BackgroundService loop)."""
        if not self.gateway_url:
            return False
            
        try:
            payload = self._get_payload()
            success = self._send_to_gateway(payload)
            
            if success:
                logger.debug(f"💓 Heartbeat sent to {self.gateway_url}")
            
            return success
            
        except Exception as e:
            logger.debug(f"Heartbeat failed: {e}")
            return False
    
    def _on_success(self):
        """Called after successful heartbeat."""
        pass
    
    def _on_error(self, error: Exception):
        """Called after heartbeat error."""
        logger.debug(f"Gateway unreachable: {error}")
    
    @property
    def is_gateway_reachable(self) -> bool:
        """Check if gateway has been reachable recently."""
        return self.is_healthy
    
    # Mantener compatibilidad con la API antigua
    def send_heartbeat(self) -> bool:
        """Send a single heartbeat (for manual calls)."""
        return self._execute()

def create_heartbeat_service(pos_core, config: Dict[str, Any]) -> Optional[TerminalHeartbeatService]:
    """
    Factory function to create heartbeat service.
    
    Args:
        pos_core: POSCore instance
        config: Configuration dictionary
        
    Returns:
        TerminalHeartbeatService instance or None if not applicable
    """
    mode = config.get("db_mode", "standalone")
    
    if mode not in ("hybrid", "client"):
        logger.debug(f"Heartbeat disabled for mode: {mode}")
        return None
        
    gateway = config.get("central_url", "") or config.get("central_server", "")
    if not gateway:
        logger.debug("No gateway configured, heartbeat disabled")
        return None
        
    try:
        return TerminalHeartbeatService(pos_core, config)
    except Exception as e:
        logger.error(f"Failed to create heartbeat service: {e}")
        return None

# Alias para compatibilidad hacia atrás
TerminalHeartbeat = TerminalHeartbeatService
