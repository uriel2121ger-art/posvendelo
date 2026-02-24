"""
TITAN POS - Embedded Server Manager

Manages the embedded HTTP server for MultiCaja synchronization.
"""

from typing import Optional
import logging
import time

from PyQt6 import QtWidgets

# Import log_debug with error handling (may not exist in some installations)
try:
    from app.startup.bootstrap import log_debug
except (ImportError, AttributeError):
    # Fallback if log_debug doesn't exist
    def log_debug(*args, **kwargs):
        pass  # No-op if log_debug is not available

# Import ConnectionStatusWidget with error handling (may not exist)
try:
    from app.sync.connectivity import ConnectionStatusWidget
except (ImportError, AttributeError):
    # Fallback if connectivity module doesn't exist
    from PyQt6 import QtWidgets
    class ConnectionStatusWidget(QtWidgets.QLabel):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.setText("Sin conexión")
        
        def set_server_mode(self, port):
            self.setText(f"Servidor: {port}")
        
        def set_disabled(self, msg):
            self.setText(f"Deshabilitado: {msg}")
        
        def set_error(self, msg):
            self.setText(f"Error: {msg}")
        
        def set_warning(self, msg):
            self.setText(f"Advertencia: {msg}")

logger = logging.getLogger(__name__)


class EmbeddedServerManager:
    """
    Manages the embedded HTTP server for MultiCaja synchronization.

    Handles server startup, status tracking, and error handling.
    """

    def __init__(self, core, status_widget: Optional[ConnectionStatusWidget] = None):
        """
        Initialize the server manager.

        Args:
            core: POSCore instance
            status_widget: Optional widget to update with server status
        """
        self.core = core
        self.status_widget = status_widget
        self.http_server = None
        self._server_thread = None

    def start(self) -> bool:
        """
        Start the embedded HTTP server.

        Returns:
            True if server started successfully, False otherwise
        """
        logger.error("=" * 60)
        logger.debug("🔍 [DEBUG] ===== server_manager.start() INICIADO =====")
        logger.debug("=" * 60)
        try:
            logger.debug("🔍 [DEBUG] server_manager.start() - Iniciando...")
            from app.services.http_server import create_pos_server
            logger.warning("✅ [DEBUG] create_pos_server importado correctamente")

            cfg = self.core.get_app_config() or {}
            logger.warning(f"🔍 [DEBUG] Config obtenida: {list(cfg.keys())}")
            logger.warning(f"🔍 [DEBUG] mode={cfg.get('mode')}, has_token={bool(cfg.get('api_dashboard_token'))}, port={cfg.get('server_port', 8000)}")

            log_debug("server_manager:start", "Creating server", {
                "mode": cfg.get("mode"),
                "has_token": bool(cfg.get("api_dashboard_token")),
                "port": cfg.get("server_port", 8000)
            }, "H")

            logger.warning("🔍 [DEBUG] Llamando create_pos_server()...")
            server = create_pos_server(self.core, cfg)
            logger.warning(f"🔍 [DEBUG] create_pos_server() retornó: {server} (type: {type(server)})")

            if server:
                logger.warning("✅ [DEBUG] Server creado, procediendo a iniciar...")
                logger.warning(f"🔍 [DEBUG] server.host={server.host}, server.port={server.port}")
                self.http_server = server

                log_debug("server_manager:start", "Starting server in background", {
                    "port": cfg.get("server_port", 8000),
                    "host": server.host
                }, "H")

                try:
                    logger.warning("🔍 [DEBUG] Llamando server.start_background()...")
                    self._server_thread = self.http_server.start_background()
                    logger.warning(f"✅ [DEBUG] Thread de servidor creado: {self._server_thread}")
                    logger.warning(f"🔍 [DEBUG] Thread is_alive: {self._server_thread.is_alive() if self._server_thread else 'None'}")

                    # Wait and verify thread is alive
                    time.sleep(0.5)

                    if self._server_thread and self._server_thread.is_alive():
                        port = cfg.get("server_port", 8000)

                        if self.status_widget:
                            # Use safe method calls - widget may not have all methods
                            try:
                                if hasattr(self.status_widget, 'set_server_mode'):
                                    self.status_widget.set_server_mode(port)
                                    logger.info(f"✅ Widget actualizado: Servidor en puerto {port}")
                                elif hasattr(self.status_widget, 'setText'):
                                    self.status_widget.setText(f"🖥️ Servidor: {port}")
                                    logger.info(f"✅ Widget actualizado (fallback): Servidor en puerto {port}")
                                else:
                                    logger.warning(f"⚠️ Widget no tiene métodos para actualizar estado")
                            except Exception as e:
                                logger.error(f"❌ Error al actualizar widget: {e}")

                        logger.info(f"MultiCaja HTTP server started on port {port}")

                        log_debug("server_manager:start", "Server started successfully", {
                            "port": port,
                            "thread_alive": self._server_thread.is_alive()
                        }, "H")

                        return True
                    else:
                        raise RuntimeError("Server thread failed to start")

                except OSError as e:
                    if "already in use" in str(e).lower() or "Address already in use" in str(e):
                        error_msg = f"Port {cfg.get('server_port', 8000)} already in use"
                        logger.error(f"❌ {error_msg}")

                        if self.status_widget:
                            # Use safe method calls
                            if hasattr(self.status_widget, 'set_error'):
                                self.status_widget.set_error("Port occupied")
                            elif hasattr(self.status_widget, 'setText'):
                                self.status_widget.setText("Error: Puerto ocupado")

                        log_debug("server_manager:start", "Port conflict", {
                            "port": cfg.get("server_port", 8000),
                            "error": str(e)
                        }, "H")
                    else:
                        raise

            else:
                logger.debug("=" * 60)
                logger.debug("❌ [DEBUG] ===== create_pos_server() RETORNÓ None =====")
                logger.debug(f"❌ [DEBUG] Config recibida: mode={cfg.get('mode')}, has_token={bool(cfg.get('api_dashboard_token'))}, port={cfg.get('server_port', 8000)}")
                logger.debug("=" * 60)
                logger.warning("HTTP server not started (check mode and token configuration)")
                logger.warning(f"   create_pos_server() returned None")
                logger.warning(f"   Config: mode={cfg.get('mode')}, has_token={bool(cfg.get('api_dashboard_token'))}, port={cfg.get('server_port', 8000)}")

                if self.status_widget:
                    # Use safe method calls
                    if hasattr(self.status_widget, 'set_disabled'):
                        self.status_widget.set_disabled("Server disabled")
                    elif hasattr(self.status_widget, 'setText'):
                        self.status_widget.setText("Servidor deshabilitado")

                log_debug("server_manager:start", "Server not created", {
                    "mode": cfg.get("mode"),
                    "has_token": bool(cfg.get("api_dashboard_token")),
                    "port": cfg.get("server_port", 8000)
                }, "H")

            return False

        except ImportError as e:
            logger.warning(f"FastAPI not available, HTTP server disabled: {e}")

            if self.status_widget:
                # Use safe method calls
                if hasattr(self.status_widget, 'set_warning'):
                    self.status_widget.set_warning("No FastAPI")
                elif hasattr(self.status_widget, 'setText'):
                    self.status_widget.setText("Advertencia: No FastAPI")

            log_debug("server_manager:start", "Import error", {"error": str(e)}, "H")
            return False

        except Exception as e:
            logger.error(f"Error starting HTTP server: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

            if self.status_widget:
                # Use safe method calls
                if hasattr(self.status_widget, 'set_error'):
                    self.status_widget.set_error("Server error")
                elif hasattr(self.status_widget, 'setText'):
                    self.status_widget.setText(f"Error: {str(e)[:50]}")

            log_debug("server_manager:start", "Exception starting server", {
                "error": str(e),
                "error_type": type(e).__name__
            }, "H")

            return False

    def stop(self) -> None:
        """Stop the embedded HTTP server."""
        if self.http_server:
            try:
                if hasattr(self.http_server, 'stop'):
                    self.http_server.stop()
                logger.info("HTTP server stopped")
            except Exception as e:
                logger.error(f"Error stopping HTTP server: {e}")

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._server_thread is not None and self._server_thread.is_alive()

    @property
    def port(self) -> Optional[int]:
        """Get the server port."""
        if self.http_server:
            cfg = self.core.get_app_config() or {}
            return cfg.get("server_port", 8000)
        return None
