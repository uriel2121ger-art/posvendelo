"""
Network client for POS multi-terminal synchronization and external API integration.

This module provides HTTP-based communication for:
- Multi-terminal (MultiCaja) synchronization
- External API integration
- Server health checks and monitoring
"""

import logging
import uuid
import time
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import socket

logger = logging.getLogger(__name__)


def _serialize_for_json(obj: Any) -> Any:
    """
    Recursively convert an object to JSON-serializable format.

    Handles datetime, date, Decimal, and nested dict/list structures.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_serialize_for_json(item) for item in obj]
    return obj


class NetworkClient:
    """
    Base HTTP client for network communication.
    
    Provides reliable HTTP requests with automatic retries,
    timeout handling, and connection pooling.
    """
    
    def __init__(self, base_url: str, timeout: int = 5, token: Optional[str] = None, terminal_id: Optional[int] = None):
        """
        Initialize network client.
        
        Args:
            base_url: Base URL of the server (e.g., "http://192.168.1.100:8000")
            timeout: Request timeout in seconds (default: 5)
            token: Optional authentication token
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.token = token
        self.terminal_id = terminal_id or 1
        self._cached_branch_id: Optional[int] = None
        self.session = None
        self._init_session()
    
    def _init_session(self) -> None:
        """Initialize requests session with retry strategy."""
        self.session = requests.Session()
        
        # Retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers
        if self.token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            })
        self.session.headers.update({
            "X-Terminal-Id": str(self.terminal_id),
        })

    def _ensure_connected_for_write(self) -> Tuple[bool, str]:
        """
        Server-only DB policy: if unreachable, client must stay read-only.
        """
        is_up = self.ping()
        # #region agent log
        try:
            import json
            with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "sessionId": "5e74cc",
                    "runId": "pre-fix",
                    "hypothesisId": "H4_connectivity_gate",
                    "location": "app/utils/network_client.py:_ensure_connected_for_write",
                    "message": "Connectivity gate evaluated for write",
                    "data": {"base_url": self.base_url, "ping_ok": is_up, "terminal_id": self.terminal_id},
                    "timestamp": int(time.time() * 1000),
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass
        # #endregion
        if not is_up:
            return False, "Sin conexión al servidor. Cliente en modo solo lectura."
        return True, "ok"

    @staticmethod
    def _new_request_id(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex}"

    def _resolve_branch_id(self) -> Optional[int]:
        """Resolve authenticated branch_id from /api/auth/test when available."""
        if self._cached_branch_id is not None:
            return self._cached_branch_id
        try:
            resp = self.session.get(f"{self.base_url}/api/auth/test", timeout=self.timeout)
            if resp.status_code == 200:
                payload = resp.json()
                branch_id = payload.get("branch_id")
                if branch_id is not None:
                    self._cached_branch_id = int(branch_id)
                    return self._cached_branch_id
        except Exception:
            pass
        return None
    
    def ping(self) -> bool:
        """
        Check server connectivity with health endpoint.
        
        Returns:
            True if server is reachable, False otherwise
        """
        try:
            url = f"{self.base_url}/api/health"
            response = self.session.get(url, timeout=self.timeout)
            # #region agent log
            try:
                import json
                with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "5e74cc",
                        "runId": "pre-fix",
                        "hypothesisId": "H6_ping_route_mismatch",
                        "location": "app/utils/network_client.py:ping",
                        "message": "Ping request completed",
                        "data": {"url": url, "status_code": response.status_code, "ok": response.status_code == 200},
                        "timestamp": int(time.time() * 1000),
                    }, ensure_ascii=False) + "\n")
            except Exception:
                pass
            # #endregion
            if response.status_code == 200:
                return True
            if response.status_code == 404:
                fallback_url = f"{self.base_url}/health"
                fallback_response = self.session.get(fallback_url, timeout=self.timeout)
                # #region agent log
                try:
                    import json
                    with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "sessionId": "5e74cc",
                            "runId": "post-fix",
                            "hypothesisId": "H6_ping_route_mismatch",
                            "location": "app/utils/network_client.py:ping",
                            "message": "Ping fallback request completed",
                            "data": {"url": fallback_url, "status_code": fallback_response.status_code, "ok": fallback_response.status_code == 200},
                            "timestamp": int(time.time() * 1000),
                        }, ensure_ascii=False) + "\n")
                except Exception:
                    pass
                # #endregion
                return fallback_response.status_code == 200
            return False
        except Exception as e:
            # #region agent log
            try:
                import json
                with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "5e74cc",
                        "runId": "pre-fix",
                        "hypothesisId": "H6_ping_route_mismatch",
                        "location": "app/utils/network_client.py:ping",
                        "message": "Ping request failed",
                        "data": {"url": f"{self.base_url}/api/health", "error": str(e)},
                        "timestamp": int(time.time() * 1000),
                    }, ensure_ascii=False) + "\n")
            except Exception:
                pass
            # #endregion
            logger.debug(f"Ping failed: {e}")
            return False
    
    def get_server_info(self) -> Dict[str, Any]:
        """
        Get server information and status.
        
        Returns:
            Dictionary with server info or error details
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/info",
                timeout=self.timeout
            )
            # #region agent log
            try:
                import json
                with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "5e74cc",
                        "runId": "pre-fix",
                        "hypothesisId": "H24_get_server_info_status_missing",
                        "location": "app/utils/network_client.py:get_server_info",
                        "message": "get_server_info primary response",
                        "data": {"status_code": response.status_code, "url": f"{self.base_url}/api/info"},
                        "timestamp": int(time.time() * 1000),
                    }, ensure_ascii=False) + "\n")
            except Exception:
                pass
            # #endregion
            if response.status_code == 200:
                return response.json()
            if response.status_code in (404, 405):
                fallback = self.session.get(
                    f"{self.base_url}/api/status",
                    timeout=self.timeout
                )
                # #region agent log
                try:
                    import json
                    with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "sessionId": "5e74cc",
                            "runId": "post-fix",
                            "hypothesisId": "H24_get_server_info_status_missing",
                            "location": "app/utils/network_client.py:get_server_info",
                            "message": "get_server_info fallback response",
                            "data": {"status_code": fallback.status_code, "url": f"{self.base_url}/api/status"},
                            "timestamp": int(time.time() * 1000),
                        }, ensure_ascii=False) + "\n")
                except Exception:
                    pass
                # #endregion
                if fallback.status_code == 200:
                    return fallback.json()
                return {"error": f"HTTP {fallback.status_code}"}
            else:
                return {"error": f"HTTP {response.status_code}"}
        except requests.exceptions.ConnectionError as e:
            # Connection refused - server not running or not accessible
            logger.warning(f"Servidor HTTP no accesible en {self.base_url}: {e}")
            return {
                "error": "connection_refused",
                "message": f"No se pudo conectar al servidor en {self.base_url}",
                "details": str(e)
            }
        except requests.exceptions.Timeout as e:
            logger.warning(f"Timeout al conectar con {self.base_url}: {e}")
            return {
                "error": "timeout",
                "message": f"Timeout al conectar con {self.base_url}",
                "details": str(e)
            }
        except Exception as e:
            logger.error(f"Failed to get server info: {e}")
            return {"error": str(e)}
    
    def test_api_token(self) -> Tuple[bool, str]:
        """
        Validate API token authentication.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/auth/test",
                timeout=self.timeout
            )
            # #region agent log
            try:
                import json
                with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "5e74cc",
                        "runId": "pre-fix",
                        "hypothesisId": "H21_auth_test_route_missing",
                        "location": "app/utils/network_client.py:test_api_token",
                        "message": "test_api_token response",
                        "data": {"status_code": response.status_code, "url": f"{self.base_url}/api/auth/test"},
                        "timestamp": int(time.time() * 1000),
                    }, ensure_ascii=False) + "\n")
            except Exception:
                pass
            # #endregion
            if response.status_code == 200:
                return True, "Token válido"
            if response.status_code in (404, 405):
                fallback = self.session.get(
                    f"{self.base_url}/api/status",
                    timeout=self.timeout
                )
                # #region agent log
                try:
                    import json
                    with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "sessionId": "5e74cc",
                            "runId": "post-fix",
                            "hypothesisId": "H21_auth_test_route_missing",
                            "location": "app/utils/network_client.py:test_api_token",
                            "message": "test_api_token fallback response",
                            "data": {"status_code": fallback.status_code, "url": f"{self.base_url}/api/status"},
                            "timestamp": int(time.time() * 1000),
                        }, ensure_ascii=False) + "\n")
                except Exception:
                    pass
                # #endregion
                if fallback.status_code == 200:
                    return True, "Token válido"
                if fallback.status_code == 401:
                    return False, "Token inválido o expirado"
                return False, f"Error HTTP {fallback.status_code}"
            elif response.status_code == 401:
                return False, "Token inválido o expirado"
            else:
                return False, f"Error HTTP {response.status_code}"
        except Exception as e:
            return False, f"Error de conexión: {e}"
    
    def measure_latency(self) -> Optional[float]:
        """
        Measure network latency to server.
        
        Returns:
            Latency in milliseconds, or None if failed
        """
        try:
            start = time.time()
            response = self.session.get(
                f"{self.base_url}/api/health",
                timeout=self.timeout
            )
            elapsed = (time.time() - start) * 1000  # Convert to ms
            # #region agent log
            try:
                import json
                with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "5e74cc",
                        "runId": "pre-fix",
                        "hypothesisId": "H11_measure_latency_route_mismatch",
                        "location": "app/utils/network_client.py:measure_latency",
                        "message": "measure_latency primary request",
                        "data": {"url": f"{self.base_url}/api/health", "status_code": response.status_code, "elapsed_ms": round(elapsed, 2)},
                        "timestamp": int(time.time() * 1000),
                    }, ensure_ascii=False) + "\n")
            except Exception:
                pass
            # #endregion
            
            if response.status_code == 200:
                return round(elapsed, 2)
            if response.status_code == 404:
                fallback_start = time.time()
                fallback_response = self.session.get(
                    f"{self.base_url}/health",
                    timeout=self.timeout
                )
                fallback_elapsed = (time.time() - fallback_start) * 1000
                # #region agent log
                try:
                    import json
                    with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "sessionId": "5e74cc",
                            "runId": "post-fix",
                            "hypothesisId": "H11_measure_latency_route_mismatch",
                            "location": "app/utils/network_client.py:measure_latency",
                            "message": "measure_latency fallback request",
                            "data": {"url": f"{self.base_url}/health", "status_code": fallback_response.status_code, "elapsed_ms": round(fallback_elapsed, 2)},
                            "timestamp": int(time.time() * 1000),
                        }, ensure_ascii=False) + "\n")
                except Exception:
                    pass
                # #endregion
                if fallback_response.status_code == 200:
                    return round(fallback_elapsed, 2)
            return None
        except Exception:
            return None


class MultiCajaClient(NetworkClient):
    """
    MultiCaja synchronization client.
    
    Extends NetworkClient with MultiCaja-specific sync methods.
    """
    
    def __init__(self, base_url: str, timeout: int = 10, token: Optional[str] = None, terminal_id: Optional[int] = None):
        """
        Initialize MultiCaja client.
        
        Args:
            base_url: Base URL of master server
            timeout: Request timeout (default: 10s for sync operations)
            token: Authentication token
        """
        super().__init__(base_url, timeout, token, terminal_id=terminal_id)
    
    def sync_inventory(self, products: list) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Synchronize inventory data with server.
        
        Args:
            products: List of product dictionaries to sync
            
        Returns:
            Tuple of (success: bool, message: str, response_data: dict)
        """
        ok, msg = self._ensure_connected_for_write()
        if not ok:
            return False, msg, {}
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/sync/inventory",
                json={
                    "data": products,
                    "timestamp": datetime.now().isoformat(),
                    "terminal_id": self.terminal_id,
                    "request_id": self._new_request_id("sync_inventory"),
                },
                timeout=self.timeout
            )
            # #region agent log
            try:
                import json
                with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "5e74cc",
                        "runId": "pre-fix",
                        "hypothesisId": "H8_inventory_sync_route_mismatch",
                        "location": "app/utils/network_client.py:sync_inventory",
                        "message": "sync_inventory response received",
                        "data": {
                            "url": f"{self.base_url}/api/v1/sync/inventory",
                            "status_code": response.status_code,
                        },
                        "timestamp": int(time.time() * 1000),
                    }, ensure_ascii=False) + "\n")
            except Exception:
                pass
            # #endregion
            if response.status_code == 200:
                data = response.json()
                return True, "Inventario sincronizado", data
            elif response.status_code == 401:
                error_detail = response.json().get("detail", "Token inválido o faltante") if response.content else "Token inválido o faltante"
                logger.error(f"Error 401 en sync_inventory: {error_detail}. Verifica que el token 'api_dashboard_token' sea correcto")
                return False, f"Error HTTP 401: {error_detail}", {}
            else:
                error_msg = f"Error HTTP {response.status_code}"
                try:
                    error_detail = response.json().get("detail", "")
                    if error_detail:
                        error_msg += f" - {error_detail}"
                except Exception as e:
                    logger.debug("response.json(): %s", e)
                return False, error_msg, {}
        except Exception as e:
            return False, f"Error de conexión: {e}", {}
    
    def sync_sales(self, sales: list) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Synchronize sales data with server.

        Args:
            sales: List of sale dictionaries to sync

        Returns:
            Tuple of (success: bool, message: str, response_data: dict)
        """
        ok, msg = self._ensure_connected_for_write()
        if not ok:
            return False, msg, {}
        try:
            # FIX: Convert datetime/Decimal to JSON-serializable format
            serializable_sales = _serialize_for_json(sales)
            response = self.session.post(
                f"{self.base_url}/api/v1/sync/sales",
                json={
                    "data": serializable_sales,
                    "timestamp": datetime.now().isoformat(),
                    "terminal_id": self.terminal_id,
                    "request_id": self._new_request_id("sync_sales"),
                },
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                return True, "Ventas sincronizadas", data
            elif response.status_code == 401:
                error_detail = response.json().get("detail", "Token inválido o faltante") if response.content else "Token inválido o faltante"
                logger.error(f"Error 401 en sync_sales: {error_detail}. Verifica que el token 'api_dashboard_token' sea correcto")
                return False, f"Error HTTP 401: {error_detail}", {}
            else:
                error_msg = f"Error HTTP {response.status_code}"
                try:
                    error_detail = response.json().get("detail", "")
                    if error_detail:
                        error_msg += f" - {error_detail}"
                except Exception as e:
                    logger.debug("response.json(): %s", e)
                return False, error_msg, {}
        except Exception as e:
            return False, f"Error de conexión: {e}", {}
    
    def sync_customers(self, customers: list) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Synchronize customer data with server.
        
        Args:
            customers: List of customer dictionaries to sync
            
        Returns:
            Tuple of (success: bool, message: str, response_data: dict)
        """
        ok, msg = self._ensure_connected_for_write()
        if not ok:
            return False, msg, {}
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/sync/customers",
                json={
                    "data": customers,
                    "timestamp": datetime.now().isoformat(),
                    "terminal_id": self.terminal_id,
                    "request_id": self._new_request_id("sync_customers"),
                },
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                return True, "Clientes sincronizados", data
            elif response.status_code == 401:
                error_detail = response.json().get("detail", "Token inválido o faltante") if response.content else "Token inválido o faltante"
                logger.error(f"Error 401 en sync_customers: {error_detail}. Verifica que el token 'api_dashboard_token' sea correcto")
                return False, f"Error HTTP 401: {error_detail}", {}
            else:
                error_msg = f"Error HTTP {response.status_code}"
                try:
                    error_detail = response.json().get("detail", "")
                    if error_detail:
                        error_msg += f" - {error_detail}"
                except Exception as e:
                    logger.debug("response.json(): %s", e)
                return False, error_msg, {}
        except Exception as e:
            return False, f"Error de conexión: {e}", {}
    
    def sync_inventory_movements(self, movements: list, terminal_id: Optional[str] = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Push inventory movements to server (Parte A Fase 2 - delta sync).
        terminal_id: para idempotencia en servidor (applied_inventory_movements).
        Returns (success, message, response_data with accepted_ids).
        """
        ok, msg = self._ensure_connected_for_write()
        if not ok:
            return False, msg, {}
        payload_terminal_id = self.terminal_id
        if terminal_id is not None:
            try:
                payload_terminal_id = int(terminal_id)
            except Exception:
                payload_terminal_id = self.terminal_id
        payload = {
            "data": movements,
            "timestamp": datetime.now().isoformat(),
            "terminal_id": payload_terminal_id,
            "request_id": self._new_request_id("sync_inventory_movements"),
        }
        # #region agent log
        try:
            import json
            with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "sessionId": "5e74cc",
                    "runId": "pre-fix",
                    "hypothesisId": "H16_movements_missing_connectivity_gate",
                    "location": "app/utils/network_client.py:sync_inventory_movements",
                    "message": "sync_inventory_movements called",
                    "data": {"base_url": self.base_url, "terminal_id": payload_terminal_id},
                    "timestamp": int(time.time() * 1000),
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass
        # #endregion
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/sync/inventory-movements",
                json=payload,
                timeout=self.timeout
            )
            # #region agent log
            try:
                import json
                with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "5e74cc",
                        "runId": "pre-fix",
                        "hypothesisId": "H13_inventory_movements_contract",
                        "location": "app/utils/network_client.py:sync_inventory_movements",
                        "message": "sync_inventory_movements response",
                        "data": {"status_code": response.status_code, "url": f"{self.base_url}/api/v1/sync/inventory-movements"},
                        "timestamp": int(time.time() * 1000),
                    }, ensure_ascii=False) + "\n")
            except Exception:
                pass
            # #endregion
            if response.status_code == 200:
                data = response.json()
                return True, "Movimientos sincronizados", data
            elif response.status_code == 401:
                error_detail = response.json().get("detail", "Token inválido") if response.content else "Token inválido"
                return False, f"Error HTTP 401: {error_detail}", {}
            else:
                error_msg = f"Error HTTP {response.status_code}"
                try:
                    error_msg += f" - {response.json().get('detail', '')}"
                except Exception:
                    pass
                return False, error_msg, {}
        except Exception as e:
            return False, f"Error de conexión: {e}", {}

    def get_last_sync_status(self) -> Dict[str, Any]:
        """Get last synchronization status from server."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/sync/status",
                timeout=self.timeout
            )
            # #region agent log
            try:
                import json
                with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "5e74cc",
                        "runId": "pre-fix",
                        "hypothesisId": "H14_sync_status_route_missing",
                        "location": "app/utils/network_client.py:get_last_sync_status",
                        "message": "get_last_sync_status response",
                        "data": {"status_code": response.status_code, "url": f"{self.base_url}/api/v1/sync/status"},
                        "timestamp": int(time.time() * 1000),
                    }, ensure_ascii=False) + "\n")
            except Exception:
                pass
            # #endregion
            if response.status_code == 200:
                return response.json()
            if response.status_code in (404, 405):
                fallback = self.session.get(
                    f"{self.base_url}/api/status",
                    timeout=self.timeout
                )
                # #region agent log
                try:
                    import json
                    with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "sessionId": "5e74cc",
                            "runId": "post-fix",
                            "hypothesisId": "H14_sync_status_route_missing",
                            "location": "app/utils/network_client.py:get_last_sync_status",
                            "message": "get_last_sync_status fallback response",
                            "data": {"status_code": fallback.status_code, "url": f"{self.base_url}/api/status"},
                            "timestamp": int(time.time() * 1000),
                        }, ensure_ascii=False) + "\n")
                except Exception:
                    pass
                # #endregion
                if fallback.status_code == 200:
                    return fallback.json()
                return {"error": f"HTTP {fallback.status_code}"}
            return {"error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}
    
    def pull_table(self, table_name: str) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        Generic method to pull any table from server.
        
        Args:
            table_name: Name of table to pull
            
        Returns:
            Tuple of (success: bool, message: str, data_list: list)
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/sync/{table_name}",
                timeout=self.timeout
            )
            # #region agent log
            try:
                import json
                with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "5e74cc",
                        "runId": "pre-fix",
                        "hypothesisId": "H15_pull_table_get_not_supported",
                        "location": "app/utils/network_client.py:pull_table",
                        "message": "pull_table response",
                        "data": {"table_name": table_name, "status_code": response.status_code, "url": f"{self.base_url}/api/v1/sync/{table_name}"},
                        "timestamp": int(time.time() * 1000),
                    }, ensure_ascii=False) + "\n")
            except Exception:
                pass
            # #endregion
            if response.status_code == 200:
                result = response.json()
                data = result.get("data", [])
                return True, f"Pulled {len(data)} {table_name} records", data
            if response.status_code in (404, 405):
                fallback_url = None
                if table_name == "products":
                    fallback_url = f"{self.base_url}/api/sync/products"
                elif table_name == "customers":
                    fallback_url = f"{self.base_url}/api/customers"
                elif table_name == "sales":
                    fallback_url = f"{self.base_url}/api/reports/sales"

                if fallback_url:
                    fallback = self.session.get(fallback_url, timeout=self.timeout)
                    # #region agent log
                    try:
                        import json
                        with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                            f.write(json.dumps({
                                "sessionId": "5e74cc",
                                "runId": "post-fix",
                                "hypothesisId": "H29_pull_table_classic_fallbacks",
                                "location": "app/utils/network_client.py:pull_table",
                                "message": "pull_table fallback response",
                                "data": {"table_name": table_name, "status_code": fallback.status_code, "url": fallback_url},
                                "timestamp": int(time.time() * 1000),
                            }, ensure_ascii=False) + "\n")
                    except Exception:
                        pass
                    # #endregion
                    if fallback.status_code == 200:
                        result = fallback.json()
                        if table_name == "products":
                            data = result.get("products", result.get("data", []))
                        elif table_name == "customers":
                            data = result.get("customers", result.get("data", []))
                        else:
                            data = result.get("sales", result.get("data", []))
                            branch_id = self._resolve_branch_id()
                            if branch_id is not None:
                                data = [
                                    s for s in data
                                    if not isinstance(s, dict) or s.get("_branch_id") in (None, branch_id)
                                ]
                                # #region agent log
                                try:
                                    import json
                                    with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                                        f.write(json.dumps({
                                            "sessionId": "5e74cc",
                                            "runId": "post-fix",
                                            "hypothesisId": "H31_sales_branch_scope_enforced",
                                            "location": "app/utils/network_client.py:pull_table",
                                            "message": "pull_table(sales) fallback enforced branch scope",
                                            "data": {"branch_id": branch_id, "records_after_branch_filter": len(data)},
                                            "timestamp": int(time.time() * 1000),
                                        }, ensure_ascii=False) + "\n")
                                except Exception:
                                    pass
                                # #endregion
                        return True, f"Pulled {len(data)} {table_name} records", data
                    if fallback.status_code == 401:
                        return False, "Error HTTP 401: Token inválido o faltante", []
                    return False, f"Error HTTP {fallback.status_code}", []
            elif response.status_code == 401:
                error_detail = response.json().get("detail", "Token inválido o faltante") if response.content else "Token inválido o faltante"
                logger.error(f"Error 401 en pull_table({table_name}): {error_detail}. Verifica que el token 'api_dashboard_token' sea correcto")
                return False, f"Error HTTP 401: {error_detail}", []
            else:
                error_msg = f"Error HTTP {response.status_code}"
                try:
                    error_detail = response.json().get("detail", "")
                    if error_detail:
                        error_msg += f" - {error_detail}"
                except Exception as e:
                    logger.debug("response.json(): %s", e)
                return False, error_msg, []
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error pulling {table_name}: {e}")
            return False, f"Error de conexión: {e}", []
        except requests.exceptions.Timeout as e:
            logger.warning(f"Timeout pulling {table_name}: {e}")
            return False, f"Timeout: {e}", []
        except Exception as e:
            logger.error(f"Error pulling {table_name}: {e}")
            return False, f"Error: {str(e)}", []
    
    def pull_inventory(self) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        Pull inventory data from server.
        
        Returns:
            Tuple of (success: bool, message: str, products: list)
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/sync/inventory",
                timeout=self.timeout
            )
            # #region agent log
            try:
                import json
                with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "5e74cc",
                        "runId": "pre-fix",
                        "hypothesisId": "H19_pull_inventory_contract",
                        "location": "app/utils/network_client.py:pull_inventory",
                        "message": "pull_inventory response",
                        "data": {"status_code": response.status_code, "url": f"{self.base_url}/api/v1/sync/inventory"},
                        "timestamp": int(time.time() * 1000),
                    }, ensure_ascii=False) + "\n")
            except Exception:
                pass
            # #endregion
            if response.status_code == 200:
                result = response.json()
                products = result.get("products", result.get("data", []))
                return True, f"Pulled {len(products)} products", products
            if response.status_code in (404, 405):
                fallback = self.session.get(
                    f"{self.base_url}/api/sync/products",
                    timeout=self.timeout
                )
                # #region agent log
                try:
                    import json
                    with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "sessionId": "5e74cc",
                            "runId": "post-fix",
                            "hypothesisId": "H19_pull_inventory_contract",
                            "location": "app/utils/network_client.py:pull_inventory",
                            "message": "pull_inventory fallback response",
                            "data": {"status_code": fallback.status_code, "url": f"{self.base_url}/api/sync/products"},
                            "timestamp": int(time.time() * 1000),
                        }, ensure_ascii=False) + "\n")
                except Exception:
                    pass
                # #endregion
                if fallback.status_code == 200:
                    result = fallback.json()
                    products = result.get("products", result.get("data", []))
                    return True, f"Pulled {len(products)} products", products
                if fallback.status_code == 401:
                    return False, "Error HTTP 401: Token inválido o faltante", []
                return False, f"Error HTTP {fallback.status_code}", []
            elif response.status_code == 401:
                error_detail = response.json().get("detail", "Token inválido o faltante") if response.content else "Token inválido o faltante"
                logger.error(f"Error 401 en pull_inventory: {error_detail}. Verifica que el token 'api_dashboard_token' sea correcto")
                return False, f"Error HTTP 401: {error_detail}", []
            else:
                error_msg = f"Error HTTP {response.status_code}"
                try:
                    error_detail = response.json().get("detail", "")
                    if error_detail:
                        error_msg += f" - {error_detail}"
                except Exception as e:
                    logger.debug("response.json(): %s", e)
                return False, error_msg, []
        except Exception as e:
            logger.error(f"Error pulling inventory: {e}")
            return False, f"Error: {str(e)}", []
    
    def pull_sales(self, limit: int = 500, since: Optional[str] = None) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        Pull sales data from server.
        
        Args:
            limit: Maximum number of sales to pull
            since: Optional timestamp to pull sales since
            
        Returns:
            Tuple of (success: bool, message: str, sales: list)
        """
        try:
            params = {"limit": limit}
            if since:
                params["since"] = since
            
            response = self.session.get(
                f"{self.base_url}/api/v1/sync/sales",
                params=params,
                timeout=self.timeout
            )
            # #region agent log
            try:
                import json
                with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "5e74cc",
                        "runId": "pre-fix",
                        "hypothesisId": "H20_pull_sales_contract",
                        "location": "app/utils/network_client.py:pull_sales",
                        "message": "pull_sales response",
                        "data": {"status_code": response.status_code, "url": f"{self.base_url}/api/v1/sync/sales"},
                        "timestamp": int(time.time() * 1000),
                    }, ensure_ascii=False) + "\n")
            except Exception:
                pass
            # #endregion
            if response.status_code == 200:
                result = response.json()
                sales = result.get("sales", result.get("data", []))
                return True, f"Pulled {len(sales)} sales", sales
            if response.status_code in (404, 405):
                fallback = self.session.get(
                    f"{self.base_url}/api/reports/sales",
                    timeout=self.timeout
                )
                # #region agent log
                try:
                    import json
                    with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "sessionId": "5e74cc",
                            "runId": "post-fix",
                            "hypothesisId": "H20_pull_sales_contract",
                            "location": "app/utils/network_client.py:pull_sales",
                            "message": "pull_sales fallback response",
                            "data": {"status_code": fallback.status_code, "url": f"{self.base_url}/api/reports/sales"},
                            "timestamp": int(time.time() * 1000),
                        }, ensure_ascii=False) + "\n")
                except Exception:
                    pass
                # #endregion
                if fallback.status_code == 200:
                    result = fallback.json()
                    sales = result.get("sales", result.get("data", []))
                    branch_id = self._resolve_branch_id()
                    if branch_id is not None:
                        sales = [
                            s for s in sales
                            if not isinstance(s, dict) or s.get("_branch_id") in (None, branch_id)
                        ]
                        # #region agent log
                        try:
                            import json
                            with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                                f.write(json.dumps({
                                    "sessionId": "5e74cc",
                                    "runId": "post-fix",
                                    "hypothesisId": "H31_sales_branch_scope_enforced",
                                    "location": "app/utils/network_client.py:pull_sales",
                                    "message": "pull_sales fallback enforced branch scope",
                                    "data": {"branch_id": branch_id, "records_after_branch_filter": len(sales)},
                                    "timestamp": int(time.time() * 1000),
                                }, ensure_ascii=False) + "\n")
                        except Exception:
                            pass
                        # #endregion
                    if since:
                        filtered_sales = []
                        for sale in sales:
                            sale_ts = str(
                                sale.get("timestamp")
                                or sale.get("_received_at")
                                or sale.get("created_at")
                                or ""
                            )
                            if sale_ts and sale_ts >= since:
                                filtered_sales.append(sale)
                        sales = filtered_sales
                    # #region agent log
                    try:
                        import json
                        with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                            f.write(json.dumps({
                                "sessionId": "5e74cc",
                                "runId": "post-fix",
                                "hypothesisId": "H28_pull_sales_since_filter",
                                "location": "app/utils/network_client.py:pull_sales",
                                "message": "pull_sales fallback applied client-side since filter",
                                "data": {"since": since, "records_after_filter": len(sales)},
                                "timestamp": int(time.time() * 1000),
                            }, ensure_ascii=False) + "\n")
                    except Exception:
                        pass
                    # #endregion
                    sales = sales[-max(1, limit):]
                    return True, f"Pulled {len(sales)} sales", sales
                if fallback.status_code == 401:
                    return False, "Error HTTP 401: Token inválido o faltante", []
                return False, f"Error HTTP {fallback.status_code}", []
            elif response.status_code == 401:
                error_detail = response.json().get("detail", "Token inválido o faltante") if response.content else "Token inválido o faltante"
                logger.error(f"Error 401 en pull_sales: {error_detail}. Verifica que el token 'api_dashboard_token' sea correcto")
                return False, f"Error HTTP 401: {error_detail}", []
            else:
                error_msg = f"Error HTTP {response.status_code}"
                try:
                    error_detail = response.json().get("detail", "")
                    if error_detail:
                        error_msg += f" - {error_detail}"
                except Exception as e:
                    logger.debug("response.json(): %s", e)
                return False, error_msg, []
        except Exception as e:
            logger.error(f"Error pulling sales: {e}")
            return False, f"Error: {str(e)}", []
    
    def pull_customers(self) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        Pull customer data from server.
        
        Returns:
            Tuple of (success: bool, message: str, customers: list)
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/sync/customers",
                timeout=self.timeout
            )
            if response.status_code == 200:
                result = response.json()
                customers = result.get("customers", result.get("data", []))
                return True, f"Pulled {len(customers)} customers", customers
            if response.status_code in (404, 405):
                fallback = self.session.get(
                    f"{self.base_url}/api/customers",
                    timeout=self.timeout
                )
                # #region agent log
                try:
                    import json
                    with open("/home/uriel/Documentos/PUNTO DE VENTA/.cursor/debug-5e74cc.log", "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "sessionId": "5e74cc",
                            "runId": "post-fix",
                            "hypothesisId": "H27_pull_customers_contract",
                            "location": "app/utils/network_client.py:pull_customers",
                            "message": "pull_customers fallback response",
                            "data": {"status_code": fallback.status_code, "url": f"{self.base_url}/api/customers"},
                            "timestamp": int(time.time() * 1000),
                        }, ensure_ascii=False) + "\n")
                except Exception:
                    pass
                # #endregion
                if fallback.status_code == 200:
                    result = fallback.json()
                    customers = result.get("customers", result.get("data", []))
                    return True, f"Pulled {len(customers)} customers", customers
                if fallback.status_code == 401:
                    return False, "Error HTTP 401: Token inválido o faltante", []
                return False, f"Error HTTP {fallback.status_code}", []
            elif response.status_code == 401:
                error_detail = response.json().get("detail", "Token inválido o faltante") if response.content else "Token inválido o faltante"
                logger.error(f"Error 401 en pull_customers: {error_detail}. Verifica que el token 'api_dashboard_token' sea correcto")
                return False, f"Error HTTP 401: {error_detail}", []
            else:
                error_msg = f"Error HTTP {response.status_code}"
                try:
                    error_detail = response.json().get("detail", "")
                    if error_detail:
                        error_msg += f" - {error_detail}"
                except Exception as e:
                    logger.debug("response.json(): %s", e)
                return False, error_msg, []
        except Exception as e:
            logger.error(f"Error pulling customers: {e}")
            return False, f"Error: {str(e)}", []
    
    def sync_table(self, table_name: str, data: list) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Generic method to sync any table to server.
        
        Args:
            table_name: Name of table to sync
            data: List of records to sync
            
        Returns:
            Tuple of (success: bool, message: str, response_data: dict)
        """
        ok, msg = self._ensure_connected_for_write()
        if not ok:
            return False, msg, {}
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/sync/{table_name}",
                json={
                    "data": data,
                    "timestamp": datetime.now().isoformat(),
                    "terminal_id": self.terminal_id,
                    "request_id": self._new_request_id(f"sync_{table_name}"),
                },
                timeout=self.timeout
            )
            if response.status_code == 200:
                result = response.json()
                return True, f"Synced {len(data)} {table_name} records", result
            elif response.status_code == 401:
                error_detail = response.json().get("detail", "Token inválido o faltante") if response.content else "Token inválido o faltante"
                logger.error(f"Error 401 en sync_table({table_name}): {error_detail}. Verifica que el token 'api_dashboard_token' sea correcto")
                return False, f"Error HTTP 401: {error_detail}", {}
            else:
                error_msg = f"Error HTTP {response.status_code}"
                try:
                    error_detail = response.json().get("detail", "")
                    if error_detail:
                        error_msg += f" - {error_detail}"
                except Exception as e:
                    logger.debug("response.json(): %s", e)
                return False, error_msg, {}
        except Exception as e:
            logger.error(f"Error syncing {table_name}: {e}")
            return False, f"Error: {str(e)}", {}