#!/usr/bin/env python3
"""
TITAN POS - Main Window Module

This module contains the POSWindow class, the main application window.
Entry points (main, run_app, run_wizard) are now in app/entry.py.

Modular Architecture:
- app/startup/: Bootstrap, crash handling, single instance
- app/sync/: Synchronization with remote servers
- app/window/: Navigation, shortcuts, server manager
- app/turns/: Turn lifecycle management
- app/exports/: Data export functionality
- app/entry.py: Application entry points
"""

import logging
import os
from pathlib import Path
from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

# --- Startup and Configuration ---
from app.startup import (
    DATA_DIR,
    ICON_DIR,
    install_crash_handler,
)

# Install crash handler early
install_crash_handler()

# --- Core imports ---
from app.core import APP_NAME, POSCore, STATE

# --- Module imports ---
# Import sync modules with error handling (may not exist in all installations)
try:
    from app.sync import SyncManager
except (ImportError, AttributeError):
    SyncManager = None

try:
    from app.sync.connectivity import ConnectionStatusWidget, ConnectivityMonitor
except (ImportError, AttributeError):
    # Fallback classes if connectivity module doesn't exist
    class ConnectionStatusWidget(QtWidgets.QLabel):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.setText("Sin conexión")
        
        def set_server_mode(self, port):
            self.setText(f"🖥️ Servidor: {port}")
            self.setStyleSheet("color: #2ecc71; font-weight: 700;")
        
        def set_online(self, message="Conectado"):
            self.setText(f"📡 {message}")
            self.setStyleSheet("color: #2ecc71; font-weight: 700;")
        
        def set_offline(self, message="Sin conexión"):
            self.setText(f"🔴 {message}")
            self.setStyleSheet("color: #e74c3c; font-weight: 700;")
        
        def set_error(self, message="Error"):
            self.setText(f"❌ {message}")
            self.setStyleSheet("color: #e74c3c; font-weight: 700;")
        
        def set_warning(self, message="Advertencia"):
            self.setText(f"⚠️ {message}")
            self.setStyleSheet("color: #e67e22; font-weight: 700;")
        
        def set_disabled(self, message="Deshabilitado"):
            self.setText(f"⚫ {message}")
            self.setStyleSheet("color: #95a5a6; font-weight: 700;")
    
    ConnectivityMonitor = None

# Import window modules with error handling
try:
    from app.window.navigation import NavigationBar, ShortcutManager
except (ImportError, AttributeError):
    # Fallback classes if navigation module doesn't exist
    class NavigationBar(QtWidgets.QWidget):
        # Signals
        tab_requested = QtCore.pyqtSignal(int)
        exit_requested = QtCore.pyqtSignal()
        
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._buttons = {}
            self._layout = QtWidgets.QHBoxLayout(self)
        
        def add_button(self, name, text, icon_name, index=None, callback=None):
            """Fallback: create a dummy button."""
            btn = QtWidgets.QToolButton()
            btn.setText(text)
            self._layout.addWidget(btn)
            self._buttons[name] = btn
            if index is not None:
                btn.clicked.connect(lambda: self.tab_requested.emit(index))
            if callback:
                btn.clicked.connect(callback)
            return btn
        
        def add_stretch(self):
            """Fallback: add stretch."""
            self._layout.addStretch()
        
        def add_exit_button(self, text="Exit", icon_name="exit.png"):
            """Fallback: create exit button."""
            btn = self.add_button("exit", text, icon_name)
            btn.clicked.connect(self.exit_requested.emit)
            return btn
        
        def hide_button(self, name):
            """Fallback: hide button."""
            if name in self._buttons:
                self._buttons[name].hide()
        
        def refresh_style(self):
            """Fallback: refresh style."""
            pass
    
    class ShortcutManager:
        def __init__(self, *args, **kwargs):
            self._shortcuts = {}
        
        def add_shortcut(self, name, key, callback, context=None):
            """Fallback: store shortcut (no-op)."""
            self._shortcuts[name] = {"key": key, "callback": callback}
            return None
        
        def handle_tab_change(self, widget):
            """Fallback: handle tab change (no-op)."""
            pass

# Try multiple import strategies for EmbeddedServerManager
EmbeddedServerManager = None
_import_error = None

# Strategy 1: Direct import (preferred)
try:
    from app.window.server_manager import EmbeddedServerManager
    # Log successful import
    import logging
    _import_logger = logging.getLogger(__name__)
    _import_logger.error("✅ [DEBUG] EmbeddedServerManager importado correctamente desde app.window.server_manager")
except (ImportError, AttributeError) as e:
    _import_error = e
    # Strategy 2: Try importing the module first, then the class
    try:
        import logging
        _import_logger = logging.getLogger(__name__)
        _import_logger.warning(f"⚠️ [DEBUG] Estrategia 1 falló, intentando estrategia 2...")
        import importlib
        server_manager_module = importlib.import_module('app.window.server_manager')
        EmbeddedServerManager = getattr(server_manager_module, 'EmbeddedServerManager', None)
        if EmbeddedServerManager:
            _import_logger.error("✅ [DEBUG] EmbeddedServerManager importado usando importlib")
    except Exception as e2:
        _import_error = e2
        # Strategy 3: Try importing from __init__.py
        try:
            import logging
            _import_logger = logging.getLogger(__name__)
            _import_logger.warning(f"⚠️ [DEBUG] Estrategia 2 falló, intentando estrategia 3...")
            from app.window import EmbeddedServerManager
            if EmbeddedServerManager:
                _import_logger.error("✅ [DEBUG] EmbeddedServerManager importado desde app.window")
        except Exception as e3:
            _import_error = e3

if EmbeddedServerManager is None:
    # Fallback class if server_manager doesn't exist
    # Log the error for debugging
    import logging
    _import_logger = logging.getLogger(__name__)
    _import_logger.error("=" * 60)
    _import_logger.error("❌ [DEBUG] ===== FALLO AL IMPORTAR EmbeddedServerManager =====")
    if _import_error:
        _import_logger.error(f"❌ [DEBUG] Error: {type(_import_error).__name__}: {_import_error}")
        import traceback
        _import_logger.error(f"❌ [DEBUG] Traceback completo:\n{traceback.format_exc()}")
    _import_logger.error("=" * 60)
    class EmbeddedServerManager:
        def __init__(self, *args, **kwargs):
            # logger not available yet, will log later when used
            pass
        
        def start(self):
            """Fallback: start server (no-op)."""
            # logger will be available when this is called
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error("❌ [DEBUG] EmbeddedServerManager.start() FALLBACK llamado - retornando False")
            return False  # ⚠️ CRÍTICO: Debe retornar False, no None
        
        def stop(self):
            """Fallback: stop server (no-op)."""
            pass

# Import turns module with error handling
try:
    from app.turns import TurnManager
except (ImportError, AttributeError):
    # Fallback class if turns module doesn't exist
    # Must inherit from QObject for signals to work
    class TurnManager(QtCore.QObject):
        # Signals
        turn_opened = QtCore.pyqtSignal(int)
        turn_closed = QtCore.pyqtSignal()
        
        def __init__(self, *args, **kwargs):
            super().__init__()
        
        def close_turn_on_exit(self):
            """Fallback: always allow exit."""
            return True
        
        def ensure_turn(self, sync_callback=None):
            """Fallback: ensure turn (no-op)."""
            pass

# --- UI Tabs ---
# Import UI tabs with error handling (may not exist in all installations)
try:
    from app.ui.customers_tab import CustomersTab
except (ImportError, AttributeError):
    CustomersTab = None

try:
    from app.ui.employees_tab import EmployeesTab
except (ImportError, AttributeError):
    EmployeesTab = None

try:
    from app.ui.history_tab import HistoryTab
except (ImportError, AttributeError):
    HistoryTab = None

try:
    from app.ui.inventory_tab import InventoryTab
except (ImportError, AttributeError):
    InventoryTab = None

try:
    from app.ui.layaways_tab import LayawaysTab
except (ImportError, AttributeError):
    LayawaysTab = None

try:
    from app.ui.products_tab import ProductsTab
except (ImportError, AttributeError):
    ProductsTab = None

try:
    from app.ui.reports_tab import ReportsTab
except (ImportError, AttributeError):
    ReportsTab = None

try:
    from app.ui.sales_tab import SalesTab
except (ImportError, AttributeError):
    SalesTab = None

try:
    from app.ui.settings_tab import SettingsTab
except (ImportError, AttributeError):
    SettingsTab = None

try:
    from app.ui.time_clock_tab import TimeClockTab
except (ImportError, AttributeError):
    TimeClockTab = None

try:
    from app.ui.turn_tab import TurnTab
except (ImportError, AttributeError):
    TurnTab = None

# --- UX Components ---
try:
    from app.ui.components import (
        ShortcutsPanel,
        apply_tooltip_stylesheet,
    )
except (ImportError, AttributeError):
    # Fallback functions/classes if components module doesn't exist
    class ShortcutsPanel(QtWidgets.QWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
    
    def apply_tooltip_stylesheet(*args, **kwargs):
        pass

# --- Services ---
try:
    from app.services.hardware_shield import init_hardware_shield
except (ImportError, AttributeError):
    def init_hardware_shield(*args, **kwargs):
        return None

# --- Utilities ---
try:
    from app.utils import permissions
except (ImportError, AttributeError):
    permissions = None

try:
    from app.utils.network_client import NetworkClient
except (ImportError, AttributeError):
    NetworkClient = None

# Debug logging - disabled in production builds
def agent_log_enabled():
    """Debug logging disabled in production."""
    return False

def get_debug_log_path_str():
    """Debug logging disabled in production."""
    return None

def get_debug_log_path():
    """Debug logging disabled in production."""
    return None

logger = logging.getLogger(__name__)


class POSWindow(QtWidgets.QMainWindow):
    """
    Main POS application window.

    Orchestrates all tabs, navigation, synchronization, and turn management.
    """

    def __init__(
        self,
        core: POSCore,
        *,
        mode: str = "server",
        network_client: Optional[NetworkClient] = None
    ):
        """
        Initialize the main window.

        Args:
            core: POSCore instance
            mode: Operating mode ("server" or "client")
            network_client: Network client for client mode synchronization
        """
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                if get_debug_log_path_str:
                    log_path = get_debug_log_path_str()
                    if log_path:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"main.py:POSWindow.__init__","message":"Starting POSWindow initialization","data":{"mode":mode},"timestamp":int(time.time()*1000)})+"\n")
                            f.flush()
            except Exception as e:
                logger.debug(f"Debug logging failed: {e}")
        # #endregion
        
        super().__init__()
        # #region agent log
        if agent_log_enabled():
            try:
                if get_debug_log_path_str:
                    log_path = get_debug_log_path_str()
                    if log_path:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"main.py:POSWindow.__init__","message":"After super().__init__","data":{},"timestamp":int(time.time()*1000)})+"\n")
                            f.flush()
            except Exception as e:
                logger.debug(f"Debug logging failed: {e}")
        # #endregion
        
        self.core = core
        self.mode = mode
        self.network_client = network_client

        # Window setup
        # #region agent log
        if agent_log_enabled():
            try:
                if get_debug_log_path_str:
                    log_path = get_debug_log_path_str()
                    if log_path:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"main.py:POSWindow.__init__","message":"Before window setup","data":{},"timestamp":int(time.time()*1000)})+"\n")
                            f.flush()
            except Exception as e:
                logger.debug(f"Debug logging failed: {e}")
        # #endregion
        self.setWindowTitle(APP_NAME)
        self._set_window_icon()
        self.setMinimumSize(1200, 720)
        # #region agent log
        if agent_log_enabled():
            try:
                if get_debug_log_path_str:
                    log_path = get_debug_log_path_str()
                    if log_path:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"main.py:POSWindow.__init__","message":"After window setup, before managers","data":{},"timestamp":int(time.time()*1000)})+"\n")
                            f.flush()
            except Exception as e:
                logger.debug(f"Debug logging failed: {e}")
        # #endregion

        # Initialize managers
        self._init_hardware_shield()
        # #region agent log
        if agent_log_enabled():
            try:
                if get_debug_log_path_str:
                    log_path = get_debug_log_path_str()
                    if log_path:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"main.py:POSWindow.__init__","message":"After _init_hardware_shield, before _init_managers","data":{},"timestamp":int(time.time()*1000)})+"\n")
                            f.flush()
            except Exception as e:
                logger.debug(f"Debug logging failed: {e}")
        # #endregion
        self._init_managers()
        # #region agent log
        if agent_log_enabled():
            try:
                if get_debug_log_path_str:
                    log_path = get_debug_log_path_str()
                    if log_path:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"main.py:POSWindow.__init__","message":"After _init_managers, before _build_ui","data":{},"timestamp":int(time.time()*1000)})+"\n")
                            f.flush()
            except Exception as e:
                logger.debug(f"Debug logging failed: {e}")
        # #endregion

        # Build UI
        self._build_ui()
        # #region agent log
        if agent_log_enabled():
            try:
                if get_debug_log_path_str:
                    log_path = get_debug_log_path_str()
                    if log_path:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"main.py:POSWindow.__init__","message":"After _build_ui, before _init_ux_components","data":{},"timestamp":int(time.time()*1000)})+"\n")
                            f.flush()
            except Exception as e:
                logger.debug(f"Debug logging failed: {e}")
        # #endregion
        self._init_ux_components()
        # #region agent log
        if agent_log_enabled():
            try:
                if get_debug_log_path_str:
                    log_path = get_debug_log_path_str()
                    if log_path:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"main.py:POSWindow.__init__","message":"After _init_ux_components, POSWindow init complete","data":{},"timestamp":int(time.time()*1000)})+"\n")
                            f.flush()
            except Exception as e:
                logger.debug(f"Debug logging failed: {e}")
        # #endregion

        # Track turn state
        self._turn_ensured = False

        # Start services after UI is ready
        QtCore.QTimer.singleShot(1000, self._start_services)

    def _set_window_icon(self) -> None:
        """Set the window icon."""
        icon_path = Path(__file__).parent.parent / 'assets' / 'icon.png'
        if icon_path.exists():
            self.setWindowIcon(QtGui.QIcon(str(icon_path)))

    def _init_hardware_shield(self) -> None:
        """Initialize the hardware temperature monitor."""
        def on_warning(temp: float):
            logger.warning(f"CPU temperature high: {temp}C")

        def on_critical(temp: float):
            logger.warning(f"CRITICAL TEMPERATURE: {temp}C - Reducing load")
            try:
                QtWidgets.QMessageBox.warning(
                    self, "High Temperature",
                    f"CPU temperature is {temp}C.\n\n"
                    "Heavy operations will be limited to protect the equipment.\n"
                    "Consider improving ventilation."
                )
            except Exception as e:
                logger.debug("Showing high temperature warning dialog: %s", e)

        def on_emergency(temp: float):
            logger.critical(f"THERMAL EMERGENCY: {temp}C")
            try:
                QtWidgets.QMessageBox.critical(
                    self, "THERMAL EMERGENCY",
                    f"CRITICAL TEMPERATURE: {temp}C!\n\n"
                    "Equipment is at risk of damage.\n"
                    "Heavy operations have been blocked.\n\n"
                    "Please:\n"
                    "1. Check ventilation\n"
                    "2. Close unnecessary programs\n"
                    "3. Consider shutting down temporarily"
                )
            except Exception as e:
                logger.debug("Showing thermal emergency dialog: %s", e)

        try:
            self.hardware_shield = init_hardware_shield(
                on_warning=on_warning,
                on_critical=on_critical,
                on_emergency=on_emergency,
                start_monitoring=True
            )
            logger.info("Hardware Shield started")
        except Exception as e:
            logger.warning(f"Could not start Hardware Shield: {e}")
            self.hardware_shield = None

    def _init_managers(self) -> None:
        """Initialize managers for sync, turns, and server."""
        # Connection status widget
        self.connection_label = ConnectionStatusWidget()

        # Turn manager
        if TurnManager is not None:
            try:
                self.turn_manager = TurnManager(self.core, self)
                self.turn_manager.turn_opened.connect(self._on_turn_opened)
                self.turn_manager.turn_closed.connect(self._on_turn_closed)
            except Exception as e:
                logger.warning(f"Could not initialize TurnManager: {e}")
                self.turn_manager = None
        else:
            self.turn_manager = None

        # Obtenemos la configuración para ver si estamos en Server-Only mode
        app_config = self.core.get_app_config() or {}
        auto_sync_enabled = app_config.get("auto_sync_enabled", True)

        # Sync manager (for client mode)
        # Si auto_sync_enabled es False, estamos en Server-Only mode y no necesitamos sincronizar
        if self.network_client and SyncManager is not None and auto_sync_enabled:
            try:
                self.sync_manager = SyncManager(self.core, self.network_client)
            except Exception as e:
                logger.warning(f"Could not initialize SyncManager: {e}")
                self.sync_manager = None
        else:
            if not auto_sync_enabled:
                logger.info("📡 Modo Server-Only DB detectado. SyncManager deshabilitado.")
            self.sync_manager = None

        # Connectivity monitor (for client mode)
        if self.network_client and ConnectivityMonitor is not None:
            try:
                self.connectivity_monitor = ConnectivityMonitor(self.network_client)
                self.connectivity_monitor.connection_changed.connect(self._on_connection_changed)
                self.connectivity_monitor.sync_requested.connect(self._perform_sync)
            except Exception as e:
                logger.warning(f"Could not initialize ConnectivityMonitor: {e}")
                self.connectivity_monitor = None
        else:
            self.connectivity_monitor = None

        # Server manager (for server mode)
        if EmbeddedServerManager is not None:
            try:
                self.server_manager = EmbeddedServerManager(self.core, self.connection_label)
                logger.info("✅ EmbeddedServerManager inicializado correctamente")
            except Exception as e:
                logger.error(f"❌ [DEBUG] ERROR al inicializar EmbeddedServerManager: {type(e).__name__}: {e}")
                import traceback
                logger.error(f"❌ [DEBUG] Traceback:\n{traceback.format_exc()}")
                logger.warning(f"Could not initialize EmbeddedServerManager: {e}")
                self.server_manager = None
        else:
            logger.error("❌ [DEBUG] EmbeddedServerManager es None - el import falló")
            self.server_manager = None

        # Backup engine (lazy init)
        self.backup_engine = None

    def _build_ui(self) -> None:
        """Build the main UI with tabs and navigation."""
        # Create tab widget
        self.tabs = QtWidgets.QTabWidget()
        self._create_tabs()
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.tabs.tabBar().hide()  # Hide native tabs, use custom nav

        # Create navigation bar
        self._create_navigation()

        # Create shortcuts
        self.shortcut_manager = ShortcutManager(self)
        self._setup_shortcuts()

        # Layout
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.nav_bar)
        main_layout.addWidget(self.tabs)

        central_widget = QtWidgets.QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Status bar
        self.statusBar().showMessage(f"Active branch: {STATE.branch_id}")
        self.statusBar().addPermanentWidget(self.connection_label)

        # Apply permissions
        self._apply_permissions()

    def _create_tabs(self) -> None:
        """Create all application tabs."""
        icon = QtGui.QIcon
        
        # Initialize tab attributes to None
        self.sales_tab = None
        self.products_tab = None
        self.inventory_tab = None
        self.customers_tab = None
        self.history_tab = None
        self.layaways_tab = None
        self.employees_tab = None
        self.time_clock_tab = None
        self.turn_tab = None
        self.reports_tab = None
        self.settings_tab = None
        
        # Track actual tab indices
        self._tab_indices = {}

        # Sales (index 0)
        logger.info(f"🔍 Verificando SalesTab: {SalesTab is not None}")
        if SalesTab is not None:
            try:
                logger.info("🔍 Intentando crear SalesTab...")
                self.sales_tab = SalesTab(self.core, mode=self.mode, network_client=self.network_client)
                idx = self.tabs.addTab(self.sales_tab, icon(str(ICON_DIR / "sales.png")), "Ventas")
                self._tab_indices['sales'] = idx
                logger.info(f"✅ SalesTab creada en índice {idx}")
            except Exception as e:
                import traceback
                logger.error(f"❌ Error al crear SalesTab: {e}")
                logger.error(f"❌ Traceback completo:\n{traceback.format_exc()}")
                self.sales_tab = None
        else:
            logger.error("❌ SalesTab es None - no se pudo importar")

        # Products (index 1)
        if ProductsTab is not None:
            try:
                self.products_tab = ProductsTab(self.core)
                idx = self.tabs.addTab(self.products_tab, icon(str(ICON_DIR / "inventory.png")), "Productos")
                self._tab_indices['products'] = idx
                logger.debug(f"✅ ProductsTab creada en índice {idx}")
            except Exception as e:
                logger.warning(f"Could not create ProductsTab: {e}")
                self.products_tab = None

        # Inventory (index 2)
        if InventoryTab is not None:
            try:
                self.inventory_tab = InventoryTab(self.core)
                idx = self.tabs.addTab(self.inventory_tab, icon(str(ICON_DIR / "inventory.png")), "Inventario")
                self._tab_indices['inventory'] = idx
                logger.debug(f"✅ InventoryTab creada en índice {idx}")
            except Exception as e:
                logger.warning(f"Could not create InventoryTab: {e}")
                self.inventory_tab = None

        # Customers (index 3)
        if CustomersTab is not None:
            try:
                self.customers_tab = CustomersTab(self.core)
                idx = self.tabs.addTab(self.customers_tab, icon(str(ICON_DIR / "customers.png")), "Clientes")
                self._tab_indices['customers'] = idx
                logger.debug(f"✅ CustomersTab creada en índice {idx}")
            except Exception as e:
                logger.warning(f"Could not create CustomersTab: {e}")
                self.customers_tab = None

        # History (index 4)
        if HistoryTab is not None:
            try:
                self.history_tab = HistoryTab(self.core)
                idx = self.tabs.addTab(self.history_tab, icon(str(ICON_DIR / "reports.png")), "Historial")
                self._tab_indices['history'] = idx
                logger.debug(f"✅ HistoryTab creada en índice {idx}")
            except Exception as e:
                logger.warning(f"Could not create HistoryTab: {e}")
                self.history_tab = None

        # Layaways (index 5)
        if LayawaysTab is not None:
            try:
                self.layaways_tab = LayawaysTab(self.core)
                idx = self.tabs.addTab(self.layaways_tab, icon(str(ICON_DIR / "cash.png")), "Apartados")
                self._tab_indices['layaways'] = idx
                logger.debug(f"✅ LayawaysTab creada en índice {idx}")
            except Exception as e:
                logger.warning(f"Could not create LayawaysTab: {e}")
                self.layaways_tab = None

        # Employees (index 6)
        if EmployeesTab is not None:
            try:
                self.employees_tab = EmployeesTab(self.core)
                idx = self.tabs.addTab(self.employees_tab, icon(str(ICON_DIR / "customers.png")), "Empleados")
                self._tab_indices['employees'] = idx
                logger.debug(f"✅ EmployeesTab creada en índice {idx}")
            except Exception as e:
                logger.warning(f"Could not create EmployeesTab: {e}")
                self.employees_tab = None

        # Time Clock (index 7)
        if TimeClockTab is not None:
            try:
                self.time_clock_tab = TimeClockTab(self.core)
                idx = self.tabs.addTab(self.time_clock_tab, icon(str(ICON_DIR / "cash.png")), "Asistencia")
                self._tab_indices['attendance'] = idx
                logger.debug(f"✅ TimeClockTab creada en índice {idx}")
            except Exception as e:
                logger.warning(f"Could not create TimeClockTab: {e}")
                self.time_clock_tab = None

        # Turns (index 8)
        if TurnTab is not None:
            try:
                self.turn_tab = TurnTab(self.core, backup_engine=None)
                idx = self.tabs.addTab(self.turn_tab, icon(str(ICON_DIR / "cash.png")), "Turnos")
                self._tab_indices['turns'] = idx
                logger.debug(f"✅ TurnTab creada en índice {idx}")
            except Exception as e:
                logger.warning(f"Could not create TurnTab: {e}")
                self.turn_tab = None

        # Reports (index 9)
        if ReportsTab is not None:
            try:
                self.reports_tab = ReportsTab(self.core)
                idx = self.tabs.addTab(self.reports_tab, icon(str(ICON_DIR / "reports.png")), "Reportes")
                self._tab_indices['reports'] = idx
                logger.debug(f"✅ ReportsTab creada en índice {idx}")
            except Exception as e:
                logger.warning(f"Could not create ReportsTab: {e}")
                self.reports_tab = None

        # Settings (index 10)
        if SettingsTab is not None:
            try:
                logger.debug("🔍 Intentando crear SettingsTab...")
                self.settings_tab = SettingsTab(self.core)
                idx = self.tabs.addTab(self.settings_tab, icon(str(ICON_DIR / "settings.png")), "Configuración")
                self._tab_indices['settings'] = idx
                logger.info(f"✅ SettingsTab creada en índice {idx}")
            except Exception as e:
                import traceback
                logger.error(f"❌ Error al crear SettingsTab: {e}")
                logger.error(f"❌ Traceback completo:\n{traceback.format_exc()}")
                self.settings_tab = None
        
        # Log final tab mapping
        logger.info(f"📋 Mapeo de tabs: {self._tab_indices}")

        # Connect signals
        if self.sales_tab is not None and self.products_tab is not None:
            try:
                self.sales_tab.sale_completed.connect(
                    lambda _: QtCore.QTimer.singleShot(100, self.products_tab.refresh_table)
                )
            except Exception as e:
                logger.warning(f"Could not connect sales_tab signal: {e}")
        
        if self.employees_tab is not None and self.time_clock_tab is not None:
            try:
                self.employees_tab.employees_updated.connect(self.time_clock_tab.refresh)
            except Exception as e:
                logger.warning(f"Could not connect employees_tab signal: {e}")

    def _create_navigation(self) -> None:
        """Create the navigation bar."""
        if NavigationBar is not None:
            try:
                self.nav_bar = NavigationBar()
                self.nav_bar.tab_requested.connect(self.tabs.setCurrentIndex)
            except Exception as e:
                logger.warning(f"Could not create NavigationBar: {e}")
                self.nav_bar = None
        else:
            self.nav_bar = None
        
        if self.nav_bar is not None:
            try:
                self.nav_bar.exit_requested.connect(self.close)

                # Add navigation buttons using actual tab indices
                # Left side - main functions (orden lógico)
                sales_idx = self._tab_indices.get('sales', 0)
                products_idx = self._tab_indices.get('products', 1)
                inventory_idx = self._tab_indices.get('inventory', 2)
                customers_idx = self._tab_indices.get('customers', 3)
                turns_idx = self._tab_indices.get('turns', 8)
                employees_idx = self._tab_indices.get('employees', 6)
                attendance_idx = self._tab_indices.get('attendance', 7)
                
                self.nav_bar.add_button("sales", "F1 Ventas", "sales.png", sales_idx)
                self.nav_bar.add_button("products", "F3 Productos", "inventory.png", products_idx)
                self.nav_bar.add_button("inventory", "F4 Inventario", "inventory.png", inventory_idx)
                self.nav_bar.add_button("customers", "F2 Clientes", "customers.png", customers_idx)
                self.nav_bar.add_button("turns", "F5 Turnos", "cash.png", turns_idx)
                self.nav_bar.add_button("employees", "F6 Empleados", "customers.png", employees_idx)
                self.nav_bar.add_button("attendance", "F7 Asistencia", "cash.png", attendance_idx)

                self.nav_bar.add_stretch()

                # Right side - secondary functions
                layaways_idx = self._tab_indices.get('layaways', 5)
                history_idx = self._tab_indices.get('history', 4)
                reports_idx = self._tab_indices.get('reports', 9)
                settings_idx = self._tab_indices.get('settings', 10)
                
                self.nav_bar.add_button("layaways", "Apartados", "cash.png", layaways_idx)
                self.nav_bar.add_button("history", "Historial", "reports.png", history_idx)
                self.nav_bar.add_button("reports", "Reportes", "reports.png", reports_idx)
                self.nav_bar.add_button("settings", "Configuración", "settings.png", settings_idx)
                self.nav_bar.add_exit_button("Salir", "exit.png")
            except Exception as e:
                logger.warning(f"Could not configure NavigationBar: {e}")

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts."""
        if self.shortcut_manager is None:
            return
        sm = self.shortcut_manager

        # Function keys using actual tab indices
        sales_idx = self._tab_indices.get('sales', 0)
        products_idx = self._tab_indices.get('products', 1)
        inventory_idx = self._tab_indices.get('inventory', 2)
        customers_idx = self._tab_indices.get('customers', 3)
        turns_idx = self._tab_indices.get('turns', 8)
        employees_idx = self._tab_indices.get('employees', 6)
        attendance_idx = self._tab_indices.get('attendance', 7)
        
        sm.add_shortcut("f1", Qt.Key.Key_F1, lambda: self.tabs.setCurrentIndex(sales_idx))
        sm.add_shortcut("f2", Qt.Key.Key_F2, self._focus_customers_tab)
        sm.add_shortcut("f3", Qt.Key.Key_F3, lambda: self.tabs.setCurrentIndex(products_idx))
        sm.add_shortcut("f4", Qt.Key.Key_F4, lambda: self.tabs.setCurrentIndex(inventory_idx))
        sm.add_shortcut("f5", Qt.Key.Key_F5, lambda: self.tabs.setCurrentIndex(turns_idx))
        sm.add_shortcut("f6", Qt.Key.Key_F6, lambda: self.tabs.setCurrentIndex(employees_idx))

        # Alt+F7 for attendance (F7 conflicts with SalesTab)
        sm.add_shortcut("alt_f7", "Alt+F7", lambda: self.tabs.setCurrentIndex(attendance_idx))

        # Initialize state
        sales_idx = self._tab_indices.get('sales', 0)
        self._on_tab_changed(sales_idx)

    def _init_ux_components(self) -> None:
        """Initialize UX enhancement components."""
        try:
            app = QtWidgets.QApplication.instance()
            if app:
                apply_tooltip_stylesheet(app)

            self.shortcuts_panel = ShortcutsPanel(self)

            # Shift+F1 for shortcuts panel
            self.shift_f1_shortcut = QtGui.QShortcut(
                QtGui.QKeySequence("Shift+F1"),
                self
            )
            self.shift_f1_shortcut.activated.connect(self._toggle_shortcuts_panel)
            self.shift_f1_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)

            logger.info("UX Components initialized (Shift+F1 for shortcuts)")
        except Exception as e:
            logger.warning(f"Could not initialize UX Components: {e}")
            self.shortcuts_panel = None

    def _start_services(self) -> None:
        """Start background services after UI is ready."""
        logger.error("=" * 60)
        logger.debug("🔍 [DEBUG] _start_services() LLAMADO")
        logger.debug(f"🔍 [DEBUG] self.mode = {self.mode}")
        logger.debug(f"🔍 [DEBUG] self.server_manager = {self.server_manager}")
        logger.debug("=" * 60)
        
        # Start server for server mode
        if self.mode == "server":
            logger.debug("🔍 [DEBUG] Modo es 'server', procediendo...")
            if self.server_manager:
                logger.debug("🔍 [DEBUG] server_manager existe, llamando start()...")
                logger.info(f"🖥️  Iniciando servidor HTTP en modo servidor (mode={self.mode})...")
                try:
                    logger.debug(f"🔍 [DEBUG] Llamando self.server_manager.start()...")
                    logger.debug(f"🔍 [DEBUG] Tipo de server_manager: {type(self.server_manager)}")
                    logger.debug(f"🔍 [DEBUG] Módulo de server_manager: {type(self.server_manager).__module__}")
                    success = self.server_manager.start()
                    logger.debug(f"🔍 [DEBUG] server_manager.start() retornó: {success} (type: {type(success)})")
                    if success:
                        logger.info("✅ Servidor HTTP iniciado correctamente")
                    else:
                        cfg = self.core.get_app_config() or {}
                        logger.debug("=" * 60)
                        logger.debug("❌ [DEBUG] SERVIDOR NO INICIÓ - DIAGNÓSTICO:")
                        logger.debug(f"   - mode: {cfg.get('mode')}")
                        logger.debug(f"   - api_dashboard_token: {'✅ configurado' if cfg.get('api_dashboard_token') else '❌ faltante'}")
                        logger.debug(f"   - server_port: {cfg.get('server_port', 8000)}")
                        logger.debug("=" * 60)
                        logger.warning(f"⚠️  Servidor HTTP no se pudo iniciar. Verificar:")
                        logger.warning(f"   - mode: {cfg.get('mode')}")
                        logger.warning(f"   - api_dashboard_token: {'✅ configurado' if cfg.get('api_dashboard_token') else '❌ faltante'}")
                        logger.warning(f"   - server_port: {cfg.get('server_port', 8000)}")
                except Exception as e:
                    logger.error(f"EXCEPCIÓN en server_manager.start(): {type(e).__name__}: {e}")
                    import traceback
                    logger.debug(f"Traceback:\n{traceback.format_exc()}")
            else:
                logger.debug("❌ [DEBUG] server_manager es None o no está disponible")
                logger.warning("⚠️  server_manager no está disponible")

        # Start connectivity monitor for client mode
        if self.mode == "client" and self.connectivity_monitor:
            cfg = self.core.get_app_config() or {}
            sync_interval = cfg.get("sync_interval_seconds", 30) * 1000
            self.connectivity_monitor.sync_interval_ms = sync_interval
            self.connectivity_monitor.start()
            logger.info(f"Auto-sync enabled: every {sync_interval/1000}s")

    # --- Event Handlers ---

    def showEvent(self, event) -> None:
        """Handle window show event - ensure turn is opened."""
        super().showEvent(event)
        if not self._turn_ensured:
            self._turn_ensured = True
            QtCore.QTimer.singleShot(100, self._ensure_turn)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Handle window close with turn closing and backup."""
        logger.info("🔄 Iniciando proceso de cierre de aplicación...")
        
        # Handle turn closing (pregunta si cerrar o dejar pendiente)
        if self.turn_manager is not None:
            try:
                if not self.turn_manager.close_turn_on_exit():
                    logger.info("Usuario canceló el cierre")
                    event.ignore()
                    return
            except Exception as e:
                logger.error(f"Error en close_turn_on_exit: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # Continuar con el cierre aunque haya error

        # Check for pending tickets
        if not self._check_pending_tickets():
            event.ignore()
            return

        # Mandatory backup (siempre se ejecuta al cerrar)
        logger.info("💾 Iniciando backup obligatorio antes de cerrar...")
        try:
            self._perform_backup_on_close()
        except Exception as e:
            logger.error(f"Error durante backup al cerrar: {e}", exc_info=True)
            # Continuar con el cierre aunque haya error en el backup
        
        # Limpiar recursos antes de cerrar
        try:
            self._cleanup_resources()
        except Exception as e:
            logger.error(f"Error durante limpieza de recursos: {e}", exc_info=True)
        
        event.accept()
        logger.info("✅ Aplicación cerrada correctamente")

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change."""
        # #region agent log
        if agent_log_enabled():
            try:
                import json
                with open(get_debug_log_path_str(), "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "e2e-test",
                        "runId": "run1",
                        "hypothesisId": "TAB_CHANGE",
                        "location": "app/main.py:_on_tab_changed",
                        "message": "Tab changed",
                        "data": {"index": index, "tab_name": self.tabs.tabText(index) if index < self.tabs.count() else "unknown"},
                        "timestamp": int(__import__("time").time() * 1000)
                    }) + "\n")
            except Exception as e:
                logger.debug("Writing tab change debug log: %s", e)
        # #endregion
        
        if not self._check_tab_permissions(index):
            return

        widget = self.tabs.widget(index)

        # Aplicar tema al cambiar de tab
        if widget and hasattr(widget, "update_theme"):
            widget.update_theme()

        # Refresh tab data
        if hasattr(widget, "refresh_data"):
            widget.refresh_data()

        # Manage shortcut conflicts
        self.shortcut_manager.handle_tab_change(widget)

    def _on_turn_opened(self, turn_id: int) -> None:
        """Handle turn opened event."""
        if hasattr(self, "turn_tab"):
            self.turn_tab.refresh()
            logger.info("TurnTab UI refreshed after opening turn")

        # Auto-sync for client mode
        if self.mode == "client" and self.sync_manager:
            QtCore.QTimer.singleShot(1000, self._perform_sync)

    def _on_turn_closed(self, turn_id: int) -> None:
        """Handle turn closed event."""
        logger.info(f"Turn closed event received: ID={turn_id}, triggering backup...")
        # Trigger backup automáticamente después de cerrar turno
        self._init_backup_engine()
        if self.backup_engine:
            try:
                self.backup_engine.auto_backup_flow(force=True)
                logger.info("✅ Backup automático completado después de cerrar turno")
            except Exception as e:
                logger.error(f"Error en backup automático después de cerrar turno: {e}")

    def _on_connection_changed(self, connected: bool) -> None:
        """Handle connection state change."""
        if connected:
            self.connection_label.set_online()
        else:
            self.connection_label.set_offline()

        # Update sales tab offline state
        if hasattr(self, "sales_tab"):
            self.sales_tab._set_offline(not connected)

    # --- Helper Methods ---

    def _ensure_turn(self) -> None:
        """Ensure a turn is open."""
        if self.turn_manager is not None:
            try:
                logger.info("🔍 Verificando estado de turnos al iniciar aplicación...")
                sync_callback = self._perform_sync if self.mode == "client" and self.sync_manager else None
                self.turn_manager.ensure_turn(sync_callback)
                logger.info("✅ Verificación de turnos completada")
            except Exception as e:
                logger.error(f"❌ Error ensuring turn: {e}")
                import traceback
                logger.error(traceback.format_exc())
        else:
            logger.warning("⚠️  turn_manager no está disponible, no se puede verificar turnos")

    def _perform_sync(self) -> None:
        """Perform synchronization."""
        if self.sync_manager:
            # Sync offline sales first
            if hasattr(self, "sales_tab"):
                self.sales_tab.sync_offline_sales()
            self.sync_manager.sync()

    def _focus_customers_tab(self) -> None:
        """Focus the customers tab and search input."""
        customers_idx = self._tab_indices.get('customers', 3)
        self.tabs.setCurrentIndex(customers_idx)
        if hasattr(self.customers_tab, "search_input"):
            self.customers_tab.search_input.setFocus()

    def _toggle_shortcuts_panel(self) -> None:
        """Toggle shortcuts panel visibility."""
        if self.shortcuts_panel:
            self.shortcuts_panel.toggle()

    def _apply_permissions(self) -> None:
        """Apply UI restrictions based on user role."""
        if STATE.role == "admin":
            return

        # Hide restricted buttons and tabs for non-admins
        restricted = ["history", "employees", "reports", "settings"]
        restricted_indices = [4, 6, 9, 10]

        for name in restricted:
            self.nav_bar.hide_button(name)

        for idx in restricted_indices:
            self.tabs.setTabEnabled(idx, False)

    def _check_tab_permissions(self, index: int) -> bool:
        """Check if user can access a tab."""
        if STATE.role == "admin":
            return True

        restricted_indices = [4, 6, 9, 10]

        if index in restricted_indices:
            QtWidgets.QMessageBox.warning(
                self,
                "Acceso Restringido",
                "No tienes permisos para acceder a esta sección."
            )
            QtCore.QTimer.singleShot(0, lambda: self.tabs.setCurrentIndex(0))
            return False

        return True

    def _check_pending_tickets(self) -> bool:
        """Check for pending tickets in cart."""
        if not hasattr(self, 'sales_tab') or self.sales_tab is None:
            return True

        has_items = bool(self.sales_tab.cart) if hasattr(self.sales_tab, 'cart') else False
        if not has_items and hasattr(self.sales_tab, 'sessions'):
            for session in self.sales_tab.sessions:
                if session.get("cart"):
                    has_items = True
                    break

        if has_items:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Tickets pendientes",
                "Tienes tickets abiertos o productos en el carrito.\n"
                "¿Deseas conservarlos para la próxima vez?",
                QtWidgets.QMessageBox.StandardButton.Yes |
                QtWidgets.QMessageBox.StandardButton.No |
                QtWidgets.QMessageBox.StandardButton.Cancel
            )

            if reply == QtWidgets.QMessageBox.StandardButton.Cancel:
                return False

            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                self.sales_tab.save_state()
            else:
                path = Path(DATA_DIR) / "data/temp/cart_state.json"
                if path.exists():
                    path.unlink()

        return True

    def _init_backup_engine(self) -> None:
        """Initialize backup engine if needed."""
        if self.backup_engine is None:
            try:
                from app.utils.backup_engine import BackupEngine
                self.backup_engine = BackupEngine(self.core)
                logger.info("BackupEngine initialized")
            except ImportError as e:
                logger.debug("Importing BackupEngine module: %s", e)
            except Exception as e:
                logger.error(f"Failed to initialize BackupEngine: {e}")

    def _perform_backup_on_close(self) -> None:
        """Perform mandatory backup on application close."""
        try:
            self._init_backup_engine()

            if not self.backup_engine:
                logger.warning("BackupEngine not available, skipping backup")
                return

            import time

            progress = QtWidgets.QProgressDialog(
                "Creando respaldo de seguridad...",
                None, 0, 0, self
            )
            progress.setWindowTitle("Respaldo Automatico")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setCancelButton(None)
            progress.show()
            QtWidgets.QApplication.processEvents()

            start_time = time.time()
            MIN_DISPLAY_TIME = 1.5

            try:
                logger.info("Starting mandatory backup on application close")
                self.backup_engine.auto_backup_flow(force=True)

                elapsed = time.time() - start_time
                if elapsed < MIN_DISPLAY_TIME:
                    QtCore.QThread.msleep(int((MIN_DISPLAY_TIME - elapsed) * 1000))
                    QtWidgets.QApplication.processEvents()

                # Cerrar progress dialog de forma segura
                try:
                    progress.close()
                    progress.deleteLater()
                except Exception as e:
                    logger.debug("Closing progress dialog after backup success: %s", e)

                logger.info("Backup completed successfully before closing")
            except Exception as exc:
                logger.error(f"Backup failed on close: {exc}", exc_info=True)
                # Cerrar progress dialog de forma segura
                try:
                    progress.close()
                    progress.deleteLater()
                except Exception as e:
                    logger.debug("Closing progress dialog after backup failure: %s", e)
                # No mostrar diálogo al cerrar - puede causar segfault
                # Solo loguear el error
        except Exception as e:
            logger.error(f"Error in _perform_backup_on_close: {e}", exc_info=True)
            # Continuar con el cierre aunque haya error

    def _cleanup_resources(self) -> None:
        """Clean up resources before application close."""
        try:
            # Cerrar conexiones de base de datos de forma segura
            if hasattr(self, 'core') and self.core and hasattr(self.core, 'db') and self.core.db:
                try:
                    # Cerrar pool de conexiones si existe
                    if hasattr(self.core.db, 'backend') and hasattr(self.core.db.backend, 'connection_pool'):
                        if self.core.db.backend.connection_pool:
                            try:
                                self.core.db.backend.connection_pool.closeall()
                                logger.info("Database connection pool closed")
                            except Exception as e:
                                logger.debug("Closing database connection pool: %s", e)
                except Exception as e:
                    logger.debug(f"Error closing database connections: {e}")
            
            # Limpiar backup engine
            if hasattr(self, 'backup_engine') and self.backup_engine:
                try:
                    self.backup_engine = None
                except Exception as e:
                    logger.debug("Clearing backup engine reference: %s", e)
            
            # Limpiar otros recursos
            if hasattr(self, 'sync_manager') and self.sync_manager:
                try:
                    # Detener sincronización si está corriendo
                    if hasattr(self.sync_manager, 'stop'):
                        self.sync_manager.stop()
                except Exception as e:
                    logger.debug("Stopping sync manager: %s", e)
            
            logger.debug("Resources cleaned up successfully")
        except Exception as e:
            logger.debug(f"Error during resource cleanup: {e}")
    
    def reload_theme(self) -> None:
        """Reload theme for all tabs."""
        tabs_with_theme = [
            "sales_tab", "products_tab", "inventory_tab", "customers_tab",
            "history_tab", "layaways_tab", "turn_tab", "reports_tab",
            "settings_tab", "employees_tab", "time_clock_tab"
        ]

        for tab_name in tabs_with_theme:
            tab = getattr(self, tab_name, None)
            if tab and hasattr(tab, "update_theme"):
                tab.update_theme()

        # Refresh navigation bar
        self.nav_bar.refresh_style()

        # Refresh main window
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


# --- Entry Points (for backward compatibility) ---
# These are now in app/entry.py but kept here for imports

def run_app(*args, **kwargs):
    """Run the application. See app.entry.run_app for details."""
    from app.entry import run_app as _run_app
    return _run_app(*args, **kwargs)


def run_wizard(*args, **kwargs):
    """Run the setup wizard. See app.entry.run_wizard for details."""
    from app.entry import run_wizard as _run_wizard
    return _run_wizard(*args, **kwargs)


def main():
    """Main entry point. See app.entry.main for details."""
    from app.entry import main as _main
    return _main()


if __name__ == "__main__":
    main()
