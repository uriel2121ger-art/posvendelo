"""
TITAN POS - Connectivity Monitor

Monitors network connectivity and manages connection state.
"""

from typing import Callable, Optional
import logging

from PyQt6 import QtCore, QtWidgets

from app.startup.bootstrap import log_debug

logger = logging.getLogger(__name__)


class ConnectivityMonitor(QtCore.QObject):
    """
    Monitors network connectivity to the server.

    Provides periodic connectivity checks and automatic reconnection.
    Emits signals when connection state changes.
    """

    # Signals
    connection_changed = QtCore.pyqtSignal(bool)  # True = connected, False = disconnected
    sync_requested = QtCore.pyqtSignal()  # Request sync when connection restored

    def __init__(
        self,
        network_client,
        sync_interval_ms: int = 30000,
        parent: Optional[QtCore.QObject] = None
    ):
        """
        Initialize the connectivity monitor.

        Args:
            network_client: NetworkClient instance for connectivity checks
            sync_interval_ms: Interval between connectivity checks in milliseconds
            parent: Parent QObject
        """
        super().__init__(parent)
        self.network_client = network_client
        self.sync_interval_ms = sync_interval_ms
        self._is_connected = False
        self._timer: Optional[QtCore.QTimer] = None

    @property
    def is_connected(self) -> bool:
        """Return current connection state."""
        return self._is_connected

    def start(self) -> None:
        """Start the connectivity monitor."""
        if self._timer is not None:
            return  # Already running

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._check_connectivity)
        self._timer.start(self.sync_interval_ms)

        logger.info(f"Connectivity monitor started: checking every {self.sync_interval_ms/1000}s")

        # Initial check
        QtCore.QTimer.singleShot(100, self._check_connectivity)

    def stop(self) -> None:
        """Stop the connectivity monitor."""
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
            logger.info("Connectivity monitor stopped")

    def check_now(self) -> bool:
        """
        Perform an immediate connectivity check.

        Returns:
            True if connected, False otherwise
        """
        return self._check_connectivity()

    def _check_connectivity(self) -> bool:
        """
        Check connectivity to server.

        Returns:
            True if connected, False otherwise
        """
        if not self.network_client:
            log_debug("connectivity:check", "No network client", {}, "A")
            return False

        try:
            ok = self.network_client.ping()
            log_debug("connectivity:check", "Ping result", {"success": ok}, "A")

            # Detect state change
            if ok != self._is_connected:
                self._is_connected = ok
                self.connection_changed.emit(ok)

                if ok:
                    logger.info("Connection restored")
                    self.sync_requested.emit()
                else:
                    logger.warning("Connection lost")

            return ok

        except Exception as e:
            logger.error(f"Connectivity check failed: {e}")
            if self._is_connected:
                self._is_connected = False
                self.connection_changed.emit(False)
            return False


class ConnectionStatusWidget(QtWidgets.QLabel):
    """
    Widget that displays connection status.

    Shows different colors and icons based on connection state.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize the status widget."""
        super().__init__(parent)
        self.set_offline()

    def set_online(self, message: str = "Connected") -> None:
        """Set the widget to show online status."""
        self.setText(f"📡 {message}")
        self.setStyleSheet("color: #2ecc71; font-weight: 700;")

    def set_offline(self, message: str = "Offline") -> None:
        """Set the widget to show offline status."""
        self.setText(f"🔴 {message}")
        self.setStyleSheet("color: #e74c3c; font-weight: 700;")

    def set_server_mode(self, port: int) -> None:
        """Set the widget to show server mode status."""
        self.setText(f"🖥️ Server: :{port}")
        self.setStyleSheet("color: #2ecc71; font-weight: 700;")

    def set_disabled(self, message: str = "Server disabled") -> None:
        """Set the widget to show disabled status."""
        self.setText(message)
        self.setStyleSheet("color: #95a5a6; font-weight: 700;")

    def set_error(self, message: str = "Error") -> None:
        """Set the widget to show error status."""
        self.setText(message)
        self.setStyleSheet("color: #e74c3c; font-weight: 700;")

    def set_warning(self, message: str = "Warning") -> None:
        """Set the widget to show warning status."""
        self.setText(message)
        self.setStyleSheet("color: #e67e22; font-weight: 700;")
