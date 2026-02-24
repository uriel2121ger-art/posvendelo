# TODO [REFACTOR]: Este archivo tiene ~4400 lineas. Considerar dividir en:
# - sales_tab_cart.py: Logica del carrito y tabla de productos
# - sales_tab_shortcuts.py: Atajos de teclado y handlers
# - sales_tab_dialogs.py: Integracion con dialogos (pagos, descuentos, etc)
# - sales_tab_ui.py: Construccion de UI y estilos
from __future__ import annotations

from typing import Any, Optional
from datetime import datetime
from decimal import Decimal
import json
import logging
from pathlib import Path
import threading

from PyQt6 import QtCore, QtGui, QtWidgets

from app.core import APP_NAME, DATA_DIR, STATE, POSCore
from app.dialogs.assign_customer import AssignCustomerDialog
from app.dialogs.cash_movement_dialog import CashMovementDialog
from app.dialogs.discount_dialog import DiscountDialog
from app.dialogs.layaway_create_dialog import LayawayCreateDialog
from app.dialogs.loyalty_widgets import LoyaltyWidget
from app.dialogs.payment_dialog import PaymentDialog
from app.dialogs.price_checker import PriceCheckerDialog
from app.dialogs.product_common import CommonProductDialog
from app.dialogs.product_search import ProductSearchDialog
# === NEW UX COMPONENTS ===
from app.ui.components import (
    CartAnimations,
    RichTooltips,
    SaleCompletedOverlay,
    ToastManager,
    apply_rich_tooltips,
)
from app.ui.customers.layaways_tab import ApartadosTab  # Import ApartadosTab
# ChangeDialog removed - now using Toast for all sale confirmations
from app.utils import permissions, ticket_engine
from app.utils.path_utils import get_debug_log_path_str, get_debug_log_path, agent_log_enabled
from app.utils.activity_logger import (
    log_activity,
    log_cart_operation,
    log_customer_action,
    log_dialog,
    log_discount,
    log_keyboard,
    log_navigation,
    log_payment,
    log_product_action,
    log_search,
    log_session,
    log_startup,
    log_ui_click,
)
from app.utils.animations import fade_in
from app.utils.network_client import NetworkClient
from app.utils.scanner_camera import CameraScannerThread
from app.utils.theme_manager import theme_manager

logger = logging.getLogger(__name__)

OFFLINE_QUEUE_FILE = Path(DATA_DIR) / "data/temp/offline_sales_queue.json"

class SalesTab(QtWidgets.QWidget):
    # Signal emitted when a sale is completed successfully
    sale_completed = QtCore.pyqtSignal(int)  # Emits sale_id
    
    def __init__(
        self,
        core: POSCore,
        parent: QtWidgets.QWidget | None = None,
        *,
        mode: str = "server",
        network_client: NetworkClient | None = None,
    ):
        super().__init__(parent)
        self.core = core
        self.mode = mode
        self.network_client = network_client
        self.cart: list[dict[str, Any]] = []
        # NOTE: Lock para carrito. No todas las operaciones lo usan porque la mayoría
        # ocurren en el UI thread principal. Solo es crítico para el thread de cámara.
        # Auditoría 2026-01-30: Riesgo bajo, se omite corrección por complejidad vs beneficio.
        self._cart_lock = threading.RLock()  # Lock reentrant para carrito
        self.totals: dict[str, float] = {"subtotal": 0.0, "tax": 0.0, "total": 0.0}
        # FIX 2026-02-01: Eliminado código muerto que obtenía tax_rate de BD.
        # El tax_rate se fija en 0.16 por diseño (ver línea 122), haciendo ese código redundante.

        # Sistema POS Optimizado (locks y cola de impresión)
        from app.pos_core.pos_integration import create_print_callback, create_drawer_callback
        cfg = self.core.get_app_config() or {}
        print_callback = create_print_callback(self.core, cfg)
        drawer_callback = create_drawer_callback(cfg)
        
        from app.pos_core.pos_optimized import OptimizedPOSSystem
        self.pos_system = OptimizedPOSSystem(print_callback, drawer_callback)
        
        # Get app config with fallback to empty dict
        self.app_config = self.core.get_app_config() or {}
        self.scanner_prefix = self.app_config.get("scanner_prefix", "")
        self.scanner_suffix = self.app_config.get("scanner_suffix", "")
        self.camera_enabled = bool(self.app_config.get("camera_scanner_enabled", False))
        self.camera_index = int(self.app_config.get("camera_scanner_index", 0))
        self.global_discount: dict[str, Any] | None = None
        self.loyalty_widget: LoyaltyWidget | None = None
        self._last_total_before_global = 0.0
        self._last_subtotal_before_global = 0.0  # CRITICAL: Guardar subtotal sin IVA para descuento global
        self.current_customer_id: int | None = None
        self.current_customer_name: str | None = None
        self.current_ticket_note: str | None = None  # F4 ticket notes
        self.offline_queue_file = OFFLINE_QUEUE_FILE
        self.camera_thread: CameraScannerThread | None = None
        self.sessions: list[dict[str, Any]] = []
        self.last_sale_data = None  # Store last sale for reprint (sale_id, cart, payment_data)
        self.current_session_index: int = 0
        self._is_switching_session = False
        # FIX 2026-02-01: IVA fijo 16% por diseño. Código legacy eliminado arriba.
        self.tax_rate = 0.16
        
        # Track last cart state for incremental updates
        self._last_cart_size = 0
        self._last_cart_hash = None
        self._refresh_timer = None  # For debounced refresh
        
        self.load_assets()
        self._build_ui()
        
        # #region agent log
        if agent_log_enabled():
            try:
                import json
                with open(get_debug_log_path_str(), "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "e2e-test",
                        "runId": "run1",
                        "hypothesisId": "SALES_TAB_INIT",
                        "location": "app/ui/sales_tab.py:__init__",
                        "message": "SalesTab initialized",
                        "data": {"mode": self.mode, "has_network_client": self.network_client is not None},
                        "timestamp": int(__import__("time").time() * 1000)
                    }) + "\n")
            except Exception as e:
                 logger.debug("Writing debug log: %s", e)
        # #endregion
        
        # Initialize with one empty session if none restored
        if not self.sessions:
            self.new_session()

        # Shortcuts
        self.shortcuts = []
        def add_shortcut(key, callback):
            sc = QtGui.QShortcut(QtGui.QKeySequence(key), self)
            sc.activated.connect(callback)
            sc.setContext(QtCore.Qt.ShortcutContext.WindowShortcut)
            self.shortcuts.append(sc)
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"SHORTCUT_REGISTER","location":"sales_tab.py:add_shortcut","message":"Shortcut registered","data":{"key":str(key),"callback":callback.__name__ if hasattr(callback, '__name__') else str(callback),"context":"WindowShortcut","enabled":sc.isEnabled()},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            return sc

        add_shortcut(QtCore.Qt.Key.Key_F12, self._handle_charge)
        add_shortcut("Ctrl+P", self.add_common_product)
        add_shortcut("Ctrl+D", self.apply_line_discount)
        add_shortcut("Ctrl+Shift+D", self.apply_global_discount)
        add_shortcut(QtCore.Qt.Key.Key_F11, self.apply_mayoreo)
        add_shortcut(QtCore.Qt.Key.Key_F9, self.open_price_checker)
        add_shortcut(QtCore.Qt.Key.Key_F10, self._open_product_search)  # Product search
        # F6 is global shortcut for Employees tab - don't override here
        add_shortcut(QtCore.Qt.Key.Key_Equal, self.open_assign_customer)  # = to assign customer
        # Removed: add_shortcut(QtCore.Qt.Key.Key_Minus, self.clear_customer)  # CONFLICT with decrease quantity
        add_shortcut(QtCore.Qt.Key.Key_Escape, self.clear_customer)  # ESC to clear customer instead
        add_shortcut(QtCore.Qt.Key.Key_F7, self._cash_in)
        add_shortcut(QtCore.Qt.Key.Key_F8, self._cash_out)
        add_shortcut(QtCore.Qt.Key.Key_Insert, self._open_multiple_products_dialog)
        add_shortcut("Ctrl+T", self.new_session)
        add_shortcut("Ctrl+W", self.close_current_session)
        add_shortcut("Tab", self._cycle_next_ticket)  # Cycle through tickets with Tab
        add_shortcut("Shift+Tab", self._cycle_prev_ticket)  # Cycle backwards
        # Removed duplicate F10 - quick turn close removed to avoid conflict
        add_shortcut(QtCore.Qt.Key.Key_F4, self._add_ticket_note)  # Add note to ticket
        add_shortcut(QtCore.Qt.Key.Key_PageDown, self._reprint_last_ticket)  # Reprint last ticket
        # CRITICAL FIX: Use ApplicationShortcut context for Ctrl+O to ensure it works even when focus is in input fields
        ctrl_o_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+O"), self)
        ctrl_o_shortcut.activated.connect(self.open_cash_drawer_manual)
        ctrl_o_shortcut.setContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)  # Changed from WindowShortcut
        self.shortcuts.append(ctrl_o_shortcut)
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"SHORTCUT_REGISTER","location":"sales_tab.py:add_shortcut","message":"Ctrl+O shortcut registered with ApplicationShortcut context","data":{"key":"Ctrl+O","callback":"open_cash_drawer_manual","context":"ApplicationShortcut","enabled":ctrl_o_shortcut.isEnabled()},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                 logger.debug("Writing debug log: %s", e)
        # #endregion
        add_shortcut("Ctrl+X", self._cancel_last_sale)  # Cancel last sale (requires auth)
        add_shortcut("Ctrl+H", self._show_turn_sales)  # View turn sales and cancel any (requires auth)
        
        # Quantity shortcuts
        QtGui.QShortcut(QtGui.QKeySequence("+"), self, self._increase_quantity)
        QtGui.QShortcut(QtGui.QKeySequence("-"), self, self._decrease_quantity)  # Same as +
        QtGui.QShortcut(QtGui.QKeySequence("="), self, self._increase_quantity)
        
        # Delete item shortcuts
        QtGui.QShortcut(QtGui.QKeySequence("Del"), self, self._delete_selected_item)
        QtGui.QShortcut(QtGui.QKeySequence("Backspace"), self, self._delete_selected_item)

        # Restore previous session state
        self.restore_state()
        
        # Scanner Buffer
        self.scan_buffer = ""
        self.scan_timer = QtCore.QTimer(self)
        self.scan_timer.setSingleShot(True)
        self.scan_timer.timeout.connect(self._process_scan_buffer)
        self.SCAN_TIMEOUT = 50 # ms
        
        # Debounce protection for double-scan issue
        self._last_add_time = 0
        self._last_add_identifier = ""
        self.ADD_DEBOUNCE_MS = 300  # Prevent same product within 300ms
        
        # Flag para prevenir procesamiento mientras se muestra error
        self._processing_error = False

        # === UX IMPROVEMENTS INITIALIZATION ===
        self._init_ux_components()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """Captura entrada rápida del escáner (Keyboard Wedge)."""
        # CRITICAL: Allow shortcuts to work - don't intercept Ctrl+O, Ctrl+X, Ctrl+H, etc.
        # Check if Ctrl is pressed with a key that has a shortcut
        if event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            # Let shortcuts handle Ctrl+key combinations
            super().keyPressEvent(event)
            return
        
        # Si el foco está en un input editable, no interferir (salvo que sea el sku_input y queramos override)
        # Pero el escáner suele mandar caracteres muy rápido.
        # Si el usuario está escribiendo manual, el delay entre teclas es > 50ms.
        
        # Ignorar teclas modificadoras
        if event.key() in (QtCore.Qt.Key.Key_Control, QtCore.Qt.Key.Key_Shift, QtCore.Qt.Key.Key_Alt):
            super().keyPressEvent(event)
            return

        # Si es Enter, procesar buffer si existe
        if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            if self.scan_buffer:
                self._process_scan_buffer()
                event.accept()
                return
            else:
                super().keyPressEvent(event)
                return
        
        # Si es caracter imprimible
        text = event.text()
        if text and text.isprintable():
            # HIPÓTESIS B: Logging de caracteres especiales (solo en debug)
            if logger.isEnabledFor(logging.DEBUG):
                # Verificar si hay caracteres de control mezclados
                if any(ord(c) < 32 or ord(c) > 126 for c in text):
                    logger.debug(f"[SCAN] Special character detected: {repr(text)} (key={event.key()})")
            
            self.scan_buffer += text
            self.scan_timer.start(self.SCAN_TIMEOUT)
            # Opcional: Si el foco NO está en un input de texto, aceptar el evento para que no haga nada más
            if not isinstance(self.focusWidget(), QtWidgets.QLineEdit) and not isinstance(self.focusWidget(), QtWidgets.QSpinBox):
                event.accept()
            else:
                super().keyPressEvent(event)
        else:
            # HIPÓTESIS B: Logging de caracteres no imprimibles
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"[SCAN] Non-printable character: key={event.key()}, text={repr(text)}")
            super().keyPressEvent(event)

    def _process_scan_buffer(self) -> None:
        """Procesa el buffer de escaneo."""
        # CRITICAL: No procesar si hay un error en curso (evita bloqueos)
        if self._processing_error:
            logging.debug("[SCAN] Ignorando escaneo - error en proceso")
            self.scan_buffer = ""  # Limpiar buffer para evitar acumulación
            self.scan_timer.stop()  # Detener timer
            # CRITICAL: Restaurar foco al campo de escaneo para recibir nuevos escaneos
            # Esto previene que el teclado parezca "bloqueado" si el foco se perdió
            QtCore.QTimer.singleShot(100, self._focus_sku_input)
            return
        
        if not self.scan_buffer:
            return
        
        code = self.scan_buffer
        self.scan_buffer = ""
        self.scan_timer.stop()  # Detener timer explícitamente
        
        # Normalizar y buscar
        normalized = self._normalize_scan(code)
        if normalized:
            # HIPÓTESIS B: Logging de caracteres especiales del escáner
            # Verificar si hay caracteres no imprimibles o especiales
            if code != normalized:
                logger.debug(f"[SCAN] Raw code: {repr(code)}, Normalized: {repr(normalized)}")
            
            # Si el foco está en sku_input, limpiar para evitar duplicados visuales
            if self.sku_input.hasFocus():
                self.sku_input.clear()
            
            self.sku_input.setText(normalized)
            # CRITICAL: Asegurar que sku_input tenga foco antes de procesar
            # Esto previene que el escáner no funcione si el foco se perdió
            if not self.sku_input.hasFocus():
                self.sku_input.setFocus()
            self.add_item()

    def save_state(self) -> None:
        """Saves all open sessions to disk."""
        self._save_current_session_to_memory()
        state = {
            "sessions": self.sessions,
            "current_index": self.session_tabs.currentIndex()
        }
        try:
            path = Path(DATA_DIR) / "data/temp/cart_state.json"
            path.write_text(json.dumps(state, default=str), encoding="utf-8")
        except Exception as e:
            print(f"Error saving cart state: {e}")

    def restore_state(self) -> None:
        """Restores sessions from disk."""
        path = Path(DATA_DIR) / "data/temp/cart_state.json"
        if not path.exists():
            return
        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)
            saved_sessions = data.get("sessions", [])
            saved_index = data.get("current_index", 0)
            
            if saved_sessions:
                self.sessions = saved_sessions
                self.session_tabs.blockSignals(True)
                self.session_tabs.clear()
                for i, session in enumerate(self.sessions):
                    self.session_tabs.addTab(QtWidgets.QWidget(), f"Ticket {i+1}")
                
                target_index = saved_index if 0 <= saved_index < len(self.sessions) else 0
                self.session_tabs.setCurrentIndex(target_index)
                self._load_session_from_memory(target_index)
                self.current_session_index = target_index
                self.session_tabs.blockSignals(False)
        except Exception as e:
            print(f"Error restoring cart state: {e}")
            if not self.sessions:
                self.new_session()

    def new_session(self) -> None:
        """Creates a new empty sales session."""
        self._save_current_session_to_memory()
        new_session = {
            "cart": [],
            "global_discount": None,
            "customer_id": None,
            "customer_name": None,
            "totals": {"subtotal": 0.0, "tax": 0.0, "total": 0.0},
            "loyalty_widget": None,
        }
        self.sessions.append(new_session)
        index = self.session_tabs.addTab(QtWidgets.QWidget(), f"Venta {len(self.sessions)}")
        
        # Apply custom close button with visible ✕ character (more visible style)
        close_btn = QtWidgets.QPushButton("✕")
        close_btn.setFlat(False)  # Show button border for better visibility
        close_btn.setFixedSize(24, 24)  # Larger size for better visibility
        close_btn.clicked.connect(lambda checked, idx=index: self.close_session(idx))
        close_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 68, 68, 0.15);
                color: #FF4444;
                font-weight: bold;
                border: 1px solid rgba(255, 68, 68, 0.3);
                border-radius: 4px;
                font-size: 18px;
                padding: 0px;
            }
            QPushButton:hover { 
                color: #FFFFFF;
                background: #FF4444;
                border: 1px solid #FF2222;
            }
            QPushButton:pressed {
                background: #DD2222;
            }
        """)
        self.session_tabs.tabBar().setTabButton(index, QtWidgets.QTabBar.ButtonPosition.RightSide, close_btn)
        
        self.session_tabs.setCurrentIndex(index)
        self._update_active_ticket_indicator()  # Update visual indicator

    def close_current_session(self) -> None:
        """Closes the current tab."""
        self.close_session(self.session_tabs.currentIndex())

    def close_session(self, index: int) -> None:
        """Closes the session at index."""
        if len(self.sessions) <= 1:
            self.cart: list[dict] = []
            self.global_discount: dict | None = None
            self.loyalty_widget: LoyaltyWidget | None = None
            self.current_customer_id = None
            self.current_customer_name = None
            self._refresh_table()
            self._update_customer_badge()
            self._save_current_session_to_memory()
            return

        session = self.sessions[index]
        if index == self.session_tabs.currentIndex():
             has_items = bool(self.cart)
        else:
             has_items = bool(session.get("cart"))

        if has_items:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Cerrar venta",
                "Esta venta tiene productos. ¿Estás seguro de cerrarla?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            if reply == QtWidgets.QMessageBox.StandardButton.No:
                return

        self.session_tabs.removeTab(index)
        self.sessions.pop(index)
        for i in range(self.session_tabs.count()):
            self.session_tabs.setTabText(i, f"Venta {i+1}")

    def switch_session(self, index: int) -> None:
        """Switches UI to display session at index."""
        if index < 0 or index >= len(self.sessions):
            return
        if self._is_switching_session:
            return

        self._is_switching_session = True
        if hasattr(self, 'current_session_index') and self.current_session_index < len(self.sessions):
             self.sessions[self.current_session_index] = {
                "cart": self.cart,
                "global_discount": self.global_discount,
                "customer_id": self.current_customer_id,
                "customer_name": self.current_customer_name,
                "totals": self.totals,
                "loyalty_widget": self.loyalty_widget.to_dict() if self.loyalty_widget else None,
             }
        
        self._load_session_from_memory(index)
        self.current_session_index = index
        self._update_active_ticket_indicator()  # Update visual indicator
        self._is_switching_session = False

    def _save_current_session_to_memory(self) -> None:
        """Helper to dump UI state to the current session dict."""
        index = self.session_tabs.currentIndex()
        if 0 <= index < len(self.sessions):
            # CRITICAL FIX: Deep copy cart to prevent session mirroring
            import copy
            self.sessions[index]["cart"] = copy.deepcopy(self.cart)
            self.sessions[index]["global_discount"] = self.global_discount
            self.sessions[index]["customer_id"] = self.current_customer_id
            self.sessions[index]["customer_name"] = self.current_customer_name
            self.sessions[index]["totals"] = dict(self.totals)
            self.sessions[index]["loyalty_widget"] = self.loyalty_widget.to_dict() if self.loyalty_widget else None

    def _load_session_from_memory(self, index: int) -> None:
        """Helper to load session dict into UI."""
        if 0 <= index < len(self.sessions):
            session = self.sessions[index]
            # CRITICAL FIX: Deep copy cart to prevent session mirroring
            import copy
            self.cart = copy.deepcopy(session.get("cart", []))
            
            # CRITICAL FIX: Sanitize cart items - ensure no negative discounts
            # Negative discounts can occur when price is increased (new_price > base_price)
            # but we should never allow negative discounts in calculations
            for item in self.cart:
                if isinstance(item, dict):
                    discount = float(item.get("discount", 0.0))
                    # Normalize -0.0 to 0.0 and clamp negative discounts to 0
                    if discount < 0:
                        # #region agent log
                        if agent_log_enabled():
                            import json, time
                            try:
                                with open(get_debug_log_path_str(), "a") as f:
                                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"NEGATIVE_DISCOUNT_LOAD","location":"sales_tab.py:_load_session_from_memory","message":"Negative discount detected and fixed when loading session","data":{"product_id":item.get("product_id"),"item_name":item.get("name"),"discount_before":discount,"base_price":item.get("base_price"),"price":item.get("price")},"timestamp":int(time.time()*1000)})+"\n")
                            except Exception as e:
                                 logger.debug("Writing debug log: %s", e)
                        # #endregion
                        item["discount"] = 0.0
                    # Normalize -0.0 to 0.0 (use tolerance check for floating point)
                    elif abs(discount) < 1e-9:
                        item["discount"] = 0.0  # Normalize -0.0 to 0.0
            
            self.global_discount = session.get("global_discount")
            self.current_customer_id = session.get("customer_id")
            self.current_customer_name = session.get("customer_name")
            self.totals = session.get("totals", {"subtotal": 0.0, "tax": 0.0, "total": 0.0})
            
            loyalty_data = session.get("loyalty_widget")
            if loyalty_data and self.loyalty_widget:
                try:
                    self.loyalty_widget.from_dict(loyalty_data)
                except Exception as e:
                    logger.warning(f"Error restoring cart state: {e}")
            
            self._refresh_table()
            self._update_customer_badge()

    def load_assets(self):
        self.icons = {}
        try:
            self.icons["search"] = QtGui.QIcon("assets/icon_search.png")
            self.icons["add"] = QtGui.QIcon("assets/icon_add.png")
            self.icons["sales"] = QtGui.QIcon("assets/icon_sales.png")
            self.icons["clients"] = QtGui.QIcon("assets/icon_clients.png")
            self.icons["products"] = QtGui.QIcon("assets/icon_products.png")
            self.icons["inventory"] = QtGui.QIcon("assets/icon_inventory.png")
            self.icons["shifts"] = QtGui.QIcon("assets/icon_shifts.png")
            self.icons["config"] = QtGui.QIcon("assets/icon_config.png")
            self.icons["exit"] = QtGui.QIcon("assets/icon_exit.png")
            self.icons["money"] = QtGui.QIcon("assets/icon_money.png")
            self.icons["filter"] = QtGui.QIcon("assets/icon_filter.png")
            self.icons["logo"] = QtGui.QIcon("assets/logo_pos.png")
        except Exception as e:
            print(f"Error loading icons: {e}")

    def _init_ux_components(self) -> None:
        """
        Inicializa los componentes de mejora de UX.
        
        Incluye:
        - Overlay de venta completada
        - Animaciones del carrito
        - Tooltips enriquecidos
        - Atajos visibles en botones
        """
        try:
            print(">>> [UX] Inicializando componentes UX...")
            
            # Sale completed overlay - Se creará lazy cuando se necesite
            # para evitar problemas de visualización al inicio
            self._sale_overlay = None
            print(">>> [UX] SaleCompletedOverlay configurado (lazy)")
            
            # Cart animations helper
            self._cart_anim = CartAnimations()
            print(">>> [UX] CartAnimations creado")
            
            # Aplicar tooltips ricos a botones principales
            self._apply_rich_tooltips()
            print(">>> [UX] Rich tooltips aplicados")
            
            # Agregar atajos visibles a botones (si no los tienen ya)
            self._add_visible_shortcuts()
            print(">>> [UX] Atajos visibles agregados")
            
            print(">>> [UX] ✅ UX Components inicializados correctamente")
            logger.info("✅ UX Components inicializados")
        except Exception as e:
            print(f">>> [UX] ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            logger.warning(f"Error inicializando UX components: {e}")
    
    def _apply_rich_tooltips(self) -> None:
        """Aplica tooltips enriquecidos a los botones principales."""
        tooltips_map = {
            'charge_btn': 'charge_btn',
            'add_btn': 'add_btn',
            'discount_btn': 'discount_btn',
            'layaway_btn': 'layaway_btn',
            'cash_in_btn': 'cash_in_btn',
            'cash_out_btn': 'cash_out_btn',
            'pending_btn': 'pending_btn',
        }
        
        for attr_name, tooltip_key in tooltips_map.items():
            widget = getattr(self, attr_name, None)
            if widget:
                RichTooltips.apply(widget, tooltip_key)
    
    def _add_visible_shortcuts(self) -> None:
        """Agrega atajos de teclado visibles a los botones."""
        # Solo actualizar si el texto no tiene ya el atajo
        shortcuts_to_add = [
            ('discount_btn', 'Ctrl+D', '🏷'),
            ('cash_in_btn', 'F7', '💵'),
            ('cash_out_btn', 'F8', '💸'),
        ]
        
        for attr_name, shortcut, icon in shortcuts_to_add:
            btn = getattr(self, attr_name, None)
            if btn and isinstance(btn, QtWidgets.QPushButton):
                current_text = btn.text()
                if shortcut not in current_text and '[' not in current_text:
                    # Agregar el atajo al texto del botón
                    btn.setText(f"{current_text} [{shortcut}]")
    
    def _show_sale_completed_animation(
        self,
        amount: float,
        change: float = 0,
        ticket_id: int = None
    ) -> None:
        """
        Muestra la animación de venta completada.

        Args:
            amount: Monto total de la venta
            change: Cambio entregado
            ticket_id: ID del ticket (opcional)
        """
        try:
            # FIX: Verificar si el overlay existe Y si el objeto C++ aún es válido
            # Un objeto Qt destruido no es None pero su objeto C++ ya no existe
            need_new_overlay = False

            if not hasattr(self, '_sale_overlay') or self._sale_overlay is None:
                need_new_overlay = True
            else:
                # Verificar si el objeto C++ fue destruido
                try:
                    # Intentar acceder a un método del widget
                    # Si el objeto C++ fue destruido, esto lanzará RuntimeError
                    _ = self._sale_overlay.isVisible()
                except RuntimeError:
                    # "wrapped C/C++ object has been deleted"
                    need_new_overlay = True
                    self._sale_overlay = None

            if need_new_overlay:
                self._sale_overlay = SaleCompletedOverlay(self.window())

            self._sale_overlay.play(amount, change, ticket_id, duration=2000)
        except RuntimeError as e:
            # Objeto C++ destruido durante la animación
            logger.warning(f"Overlay destruido, recreando: {e}")
            self._sale_overlay = None
        except Exception as e:
            logger.warning(f"Error mostrando animación de venta: {e}")

    def _add_ticket_note(self) -> None:
        """Add a note to the current ticket (F4)."""
        current_note = self.current_ticket_note or ""
        note, ok = QtWidgets.QInputDialog.getMultiLineText(
            self,
            "Nota de Ticket (F4)",
            "Agrega una nota o instrucción especial para este ticket:",
            current_note
        )
        if ok:
            self.current_ticket_note = note.strip() if note.strip() else None
            # Visual feedback
            if self.current_ticket_note:
                QtWidgets.QMessageBox.information(
                    self,
                    "Nota Agregada",
                    f"✓ Nota guardada: {self.current_ticket_note[:50]}{'...' if len(self.current_ticket_note) > 50 else ''}"
                )
            else:
                QtWidgets.QMessageBox.information(self, "Nota Borrada", "La nota del ticket fue eliminada")

    def _build_ui(self) -> None:
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === HEADER ===
        self.header = QtWidgets.QFrame()
        self.header.setFixedHeight(70)
        
        header_layout = QtWidgets.QHBoxLayout(self.header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        
        # Logo y Título
        logo_lbl = QtWidgets.QLabel()
        if "logo" in self.icons:
            logo_lbl.setPixmap(self.icons["logo"].pixmap(32, 32))
        header_layout.addWidget(logo_lbl)
        
        self.title_label = QtWidgets.QLabel("PUNTO DE VENTA")
        header_layout.addWidget(self.title_label)
        
        # Menú de Navegación eliminado por duplicidad
        header_layout.addStretch()
        
        main_layout.addWidget(self.header)

        # === ÁREA DE CONTENIDO ===
        self.content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)

        # --- TARJETA SUPERIOR ---
        self.top_card = QtWidgets.QFrame()
        top_layout = QtWidgets.QVBoxLayout(self.top_card)
        top_layout.setContentsMargins(15, 15, 15, 15)
        top_layout.setSpacing(15)

        # Fila 1: Búsqueda y Botones
        row1 = QtWidgets.QHBoxLayout()
        row1.setSpacing(15)
        
        # Input Búsqueda
        self.sku_input = QtWidgets.QLineEdit()
        self.sku_input.setPlaceholderText("🔍 Buscar producto (Escanea o escribe)...")
        self.sku_input.setMinimumWidth(350)
        self.sku_input.setFixedHeight(45)

        # Input Cantidad
        self.qty_input = QtWidgets.QSpinBox()
        self.qty_input.setRange(1, 10000)
        self.qty_input.setFixedWidth(70)
        self.qty_input.setFixedHeight(45)

        # Botón Agregar
        self.add_btn = QtWidgets.QPushButton(" AGREGAR")
        self.add_btn.setFixedHeight(45)
        if "add" in self.icons:
            self.add_btn.setIcon(self.icons["add"])
            self.add_btn.setText("+ AGREGAR")
        self.add_btn.clicked.connect(self.add_item)
        self.add_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.add_btn.setToolTip("🅰 Agregar producto al carrito\n\nAtajo: Enter en el campo de búsqueda\nPuedes escanear códigos de barras directamente")

        row1.addWidget(self.sku_input)
        row1.addWidget(QtWidgets.QLabel("Cant:", styleSheet="font-weight:bold; border:none;"))
        row1.addWidget(self.qty_input)
        row1.addWidget(self.add_btn)
        
        # Separador
        self.line_separator = QtWidgets.QFrame()
        self.line_separator.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        row1.addWidget(self.line_separator)

        # Botones de Acción Rápidos
        self.action_buttons = []
        def make_action_btn(text, callback, tooltip, color_key, icon_key):
            btn = QtWidgets.QPushButton(text)
            if icon_key in self.icons:
                btn.setIcon(self.icons[icon_key])
                btn.setIconSize(QtCore.QSize(18, 18))
            btn.setToolTip(tooltip)
            btn.clicked.connect(callback)
            btn.setFixedHeight(45)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self.action_buttons.append((btn, color_key))
            return btn

        row1.addWidget(make_action_btn(" Buscar (F10)", self._open_product_search, "🔍 Búsqueda avanzada de productos\n\nAtajo: F10\nFiltra por nombre, categoría, precio, stock", 'btn_primary', "search"))
        row1.addWidget(make_action_btn(" Varios (Ctrl+P)", self.add_common_product, "📦 Producto común (venta rápida)\n\nAtajo: Ctrl+P\nVende productos sin registro en catálogo", 'btn_primary', "products"))
        row1.addWidget(make_action_btn(" Mayoreo (F11)", self.apply_mayoreo, "💰 Activar precio de mayoreo\n\nAtajo: F11\nAplica precio especial al producto seleccionado", '#ff9800', "filter"))
        row1.addWidget(make_action_btn(" Precio (F9)", self.open_price_checker, "💵 Verificador de precios\n\nAtajo: F9\nConsulta precios sin agregar al ticket", 'btn_primary', "money"))
        
        top_layout.addLayout(row1)

        # Fila 2: Tickets y Cliente
        row2 = QtWidgets.QHBoxLayout()
        
        # Tabs
        self.session_tabs = QtWidgets.QTabWidget()
        self.session_tabs.setTabsClosable(True)
        self.session_tabs.setMovable(True)
        self.session_tabs.tabCloseRequested.connect(self.close_session)
        self.session_tabs.currentChanged.connect(self.switch_session)
        self.session_tabs.setFixedHeight(50)
        
        # Create custom close icon with visible X
        from PyQt6.QtCore import QSize
        from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
        pixmap = QPixmap(16, 16)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QtGui.QPen(QColor(255, 255, 255), 2))
        painter.drawLine(4, 4, 12, 12)
        painter.drawLine(12, 4, 4, 12)
        painter.end()
        close_icon = QIcon(pixmap)
        
        # Set the custom icon for all tab close buttons
        tab_bar = self.session_tabs.tabBar()
        tab_bar.setIconSize(QSize(16, 16))
        # Store icon to apply to tabs
        self._close_icon = close_icon
        
        self.new_ticket_btn = QtWidgets.QPushButton("+")
        self.new_ticket_btn.clicked.connect(self.new_session)
        self.new_ticket_btn.setFixedSize(30, 30)
        self.new_ticket_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        
        row2.addWidget(self.session_tabs)
        row2.addWidget(self.new_ticket_btn)
        row2.addStretch()
        
        # Cliente
        self.client_box = QtWidgets.QFrame()
        client_layout = QtWidgets.QHBoxLayout(self.client_box)
        client_layout.setContentsMargins(10, 2, 10, 2)
        
        self.customer_label = QtWidgets.QLabel("Público General")
        
        self.change_client_btn = QtWidgets.QPushButton("Cambiar")
        self.change_client_btn.clicked.connect(self._customer_button_clicked)
        self.change_client_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.change_client_btn.setToolTip("Asignar cliente a la venta (F6)")
        
        self.clear_customer_btn = QtWidgets.QPushButton("✕")
        self.clear_customer_btn.clicked.connect(self.clear_customer)
        
        self.customer_avatar = QtWidgets.QLabel("👤")
        self.customer_avatar.setFixedSize(40, 40)
        self.customer_avatar.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.customer_avatar.setStyleSheet("font-size: 18px; border: none;")
        client_layout.addWidget(self.customer_avatar)
        client_layout.addWidget(self.customer_label)
        client_layout.addWidget(self.change_client_btn)
        client_layout.addWidget(self.clear_customer_btn)

        # MIDAS Loyalty Widget
        self.loyalty_widget = LoyaltyWidget(self)
        self.loyalty_widget.setVisible(False) # Initially hidden
        client_layout.addWidget(self.loyalty_widget)
        
        row2.addWidget(self.client_box)
        top_layout.addLayout(row2)
        
        content_layout.addWidget(self.top_card)

        # --- TABLA DE PRODUCTOS ---
        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["SKU", "Producto", "Precio", "Cant.", "Subtotal"])
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # Set focus policy so keyboard events work - ONLY CHANGE
        self.table.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        # When selection changes, set focus to this widget so keyPressEvent works
        self.table.itemSelectionChanged.connect(lambda: self.setFocus())
        
        # Double-click to change price (TITAN style)
        self.table.doubleClicked.connect(self._on_item_double_clicked)
        
        content_layout.addWidget(self.table)

        # --- FOOTER ---
        self.footer = QtWidgets.QFrame()
        footer_layout = QtWidgets.QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(20, 15, 20, 15)
        
        # Botones Izquierda
        left_layout = QtWidgets.QHBoxLayout()
        left_layout.setSpacing(10)
        
        self.pending_btn = QtWidgets.QPushButton("💾 Guardar / Tickets Pendientes")
        self.pending_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.pending_btn.clicked.connect(self._manage_pending_tickets)
        self.pending_btn.setToolTip("Guardar ticket actual o cargar tickets pendientes (F6)")
        
        self.discount_btn = QtWidgets.QPushButton("🏷 Descuento")
        self.discount_btn.clicked.connect(self.apply_line_discount)
        self.discount_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.discount_btn.setToolTip("Aplicar descuento a línea seleccionada (Ctrl+D)")
        
        self.layaway_btn = QtWidgets.QPushButton("💳 Apartar")
        self.layaway_btn.clicked.connect(self.create_layaway)
        self.layaway_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.layaway_btn.setToolTip("Crear apartado del carrito actual")
        
        self.manage_layaways_btn = QtWidgets.QPushButton("📋 Ver Apartados")
        self.manage_layaways_btn.clicked.connect(self._open_layaways_manager)
        self.manage_layaways_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.manage_layaways_btn.setToolTip("Ver y gestionar apartados existentes")
        
        self.cash_in_btn = QtWidgets.QPushButton("Entrada")
        self.cash_in_btn.clicked.connect(self._cash_in)
        self.cash_in_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        
        self.cash_out_btn = QtWidgets.QPushButton("Salida")
        self.cash_out_btn.clicked.connect(self._cash_out)
        self.cash_out_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        
        # Botón de monedero removido - ahora se pregunta automáticamente al cobrar (estilo OXXO)
        # self.wallet_btn = QtWidgets.QPushButton("🎁 Monedero")
        # self.wallet_btn.clicked.connect(self._open_anonymous_wallet)
        
        left_layout.addWidget(self.pending_btn)
        left_layout.addWidget(self.discount_btn)
        left_layout.addWidget(self.layaway_btn)
        left_layout.addWidget(self.manage_layaways_btn)
        left_layout.addWidget(self.cash_in_btn)
        left_layout.addWidget(self.cash_out_btn)
        # left_layout.addWidget(self.wallet_btn)  # Removido - estilo OXXO
        
        footer_layout.addLayout(left_layout)
        footer_layout.addStretch()
        
        # Totales y Botón Cobrar
        right_layout = QtWidgets.QVBoxLayout()
        right_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        
        self.subtotal_lbl = QtWidgets.QLabel("Subtotal: 0.00")
        self.global_discount_lbl = QtWidgets.QLabel("Descuento: -0.00")
        self.tax_lbl = QtWidgets.QLabel("IVA: 0.00")
        
        for lbl in (self.subtotal_lbl, self.global_discount_lbl, self.tax_lbl):
            lbl.setStyleSheet("color: #909497; font-size: 12px; font-weight: 600;")
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
            right_layout.addWidget(lbl)
            
        self.total_lbl = QtWidgets.QLabel("0.00")
        self.total_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.total_lbl.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.total_lbl.setToolTip("💰 DESCUENTO GLOBAL\n\nClick aquí o presiona Ctrl+Shift+D para aplicar\nun descuento (% o $) a TODA la venta.\n\nPerfecto para aplicar 10% a todos los productos de una vez.")
        self.total_lbl.mousePressEvent = lambda event: self.apply_global_discount()
        right_layout.addWidget(self.total_lbl)
        
        footer_layout.addLayout(right_layout)
        
        self.charge_btn = QtWidgets.QPushButton(" COBRAR (F12)")
        if "money" in self.icons:
            self.charge_btn.setIcon(self.icons["money"])
            self.charge_btn.setIconSize(QtCore.QSize(24, 24))
        self.charge_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.charge_btn.clicked.connect(self._handle_charge)
        
        footer_layout.addSpacing(20)
        footer_layout.addWidget(self.charge_btn)
        
        content_layout.addWidget(self.footer)
        main_layout.addWidget(self.content_widget)
        
        self.update_theme()

        # Focus
        self.sku_input.setFocus()
        self.sku_input.installEventFilter(self)
        self.sku_input.returnPressed.connect(self.add_item)

    # ------------------------------------------------------------------
    def add_item(self) -> None:
        identifier = self._normalize_scan(self.sku_input.text())
        qty = self.qty_input.value()
        
        # COMPREHENSIVE LOGGING FOR MONITORING
        import time
        current_time = time.time() * 1000  # Convert to milliseconds
        logger.info(f"[ADD_ITEM] Called with identifier='{identifier}', qty={qty}")
        
        # DEBOUNCE PROTECTION: Prevent double-scan from scanner sending double Enter
        time_since_last = current_time - self._last_add_time
        
        logger.info(f"[DEBOUNCE] Current time: {current_time:.2f}ms")
        logger.info(f"[DEBOUNCE] Last add time: {self._last_add_time:.2f}ms")
        logger.info(f"[DEBOUNCE] Time since last: {time_since_last:.2f}ms")
        logger.info(f"[DEBOUNCE] Last identifier: '{self._last_add_identifier}'")
        logger.info(f"[DEBOUNCE] Current identifier: '{identifier}'")
        logger.info(f"[DEBOUNCE] Threshold: {self.ADD_DEBOUNCE_MS}ms")
        
        if (identifier == self._last_add_identifier and 
            time_since_last < self.ADD_DEBOUNCE_MS):
            # Same product scanned within debounce window - ignore
            logger.warning(f"[DEBOUNCE] BLOCKED duplicate scan! Same product '{identifier}' within {time_since_last:.2f}ms (threshold: {self.ADD_DEBOUNCE_MS}ms)")
            self.sku_input.clear()
            return
        
        logger.info(f"[DEBOUNCE] PASSED - Proceeding with add_item")
        
        # Update debounce tracking
        self._last_add_time = current_time
        self._last_add_identifier = identifier
        
        # Parse asterisk syntax: 5*codigo = 5 units of codigo
        if '*' in identifier:
            parts = identifier.split('*', 1)
            if len(parts) == 2 and parts[0].strip().replace('.', '', 1).isdigit():
                try:
                    qty = float(parts[0].strip())
                    identifier = parts[1].strip()
                    self.qty_input.setValue(int(qty) if qty == int(qty) else qty)
                    logger.info(f"[PARSE] Asterisk syntax detected: qty={qty}, identifier='{identifier}'")
                except ValueError:
                    logger.warning(f"[PARSE] Invalid asterisk syntax, treating as normal identifier")
                    pass  # Invalid syntax, treat as normal identifier
        
        if not identifier:
            logger.info(f"[VALIDATION] Empty identifier - ignoring silently (likely scanner double-enter)")
            # Silently ignore empty scans (scanner sends extra Enter)
            self.sku_input.clear()
            return

        logger.info(f"[FETCH] Searching for product with identifier='{identifier}'")
        product = self._fetch_product(identifier)
        
        if not product:
            logger.error(f"[FETCH] Product NOT FOUND for identifier='{identifier}'")
            
            # CRITICAL FIX: Usar notificación no modal en lugar de QMessageBox modal
            # QMessageBox.warning() es BLOQUEANTE y causa que el teclado se trabe
            # si el usuario escanea otro producto mientras está abierto
            
            # Limpiar buffer y detener timer para evitar procesamiento duplicado
            self.scan_buffer = ""
            self.scan_timer.stop()
            
            # Marcar que estamos procesando un error (previene nuevos escaneos)
            self._processing_error = True
            
            # Mostrar notificación no bloqueante usando Toast
            # NOTA: ToastManager ya está importado globalmente al inicio del archivo
            ToastManager.warning(
                "Producto no encontrado",
                f"No se encontró el producto: {identifier}",
                parent=self
            )
            
            # Limpiar input
            self.sku_input.clear()
            
            # Feedback visual y sonoro
            self._play_error_sound()
            self._flash_error()
            
            # CRITICAL: Restaurar foco al campo de escaneo después del error
            # Esto previene que el teclado parezca "bloqueado" si el foco se perdió
            # El delay de 200ms asegura que cualquier diálogo/notificación ya se haya mostrado
            QtCore.QTimer.singleShot(200, self._focus_sku_input)

            # Resetear flag después de un delay (permite nuevos escaneos)
            # Delay más corto para permitir escaneos rápidos
            QtCore.QTimer.singleShot(500, self._reset_processing_error)
            
            return
        
        logger.info(f"[FETCH] Product FOUND: ID={product.get('id')}, SKU={product.get('sku')}, Name={product.get('name')}")

        sale_type = (product.get("sale_type") or "unit").lower()
        logger.info(f"[PRODUCT] Sale type: {sale_type}")
        
        if sale_type in {"weight", "granel"}:
            logger.info(f"[PRODUCT] Weight/bulk product - opening dialog")
            from app.dialogs.bulk_sale_dialog import BulkSaleDialog
            dialog = BulkSaleDialog(product, self)
            if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                qty = dialog.result_qty
                logger.info(f"[DIALOG] Bulk dialog accepted with qty={qty}")
            else:
                logger.info(f"[DIALOG] Bulk dialog cancelled")
                return
                
        kit_items = []
        if sale_type == "kit":
            logger.info(f"[PRODUCT] Kit product - checking components")
            kit_items = self.core.get_kit_items(product["id"]) if hasattr(self.core, "get_kit_items") else []
            for comp in kit_items:
                # Fixed: get_stock_info only takes product_id
                comp_stock = self.core.get_stock_info(comp.get("product_id")) if hasattr(self.core, "get_stock_info") else {"stock": 0}
                if float(comp_stock.get("stock", 0.0) or 0.0) < qty * float(comp.get("qty", 1)):
                    logger.warning(f"[STOCK] Kit component insufficient stock")
                    QtWidgets.QMessageBox.warning(self, "Stock insuficiente", "Un componente del kit no tiene inventario")
                    self._play_error_sound()  # Sound feedback
                    return

        # Fixed: get_stock_info only takes product_id
        stock_row = self.core.get_stock_info(product["id"]) if hasattr(self.core, "get_stock_info") else {"stock": 999999}
        available = float(stock_row.get("stock", 999999)) if stock_row else 999999
        
        logger.info(f"[STOCK] Available stock: {available}, Requested qty: {qty}")
        
        if available < qty:
            logger.warning(f"[STOCK] Insufficient stock! Available={available}, Requested={qty}")
            ToastManager.warning(
                "⚠️ STOCK INSUFICIENTE",
                f"Solo hay {int(available)} unidades disponibles.\nSolicitaste {int(qty)} unidades.",
                [("ok", "Entendido")],
                parent=self.window()
            )
            self._play_error_sound()  # Sound feedback
            return

        # Check if product already exists in cart (thread-safe)
        existing_item = None
        with self._cart_lock:
            for item in self.cart:
                if item.get("product_id") == product["id"] and item.get("sale_type") == sale_type:
                    existing_item = item
                    break
        
        if existing_item:
            # Product already in cart - increment quantity
            with self._cart_lock:  # Thread-safe
                old_qty = existing_item.get("qty", 1)
                new_qty = float(old_qty) + qty
                existing_item["qty"] = new_qty
            logger.info(f"[CART] Product already in cart - incrementing qty from {old_qty} to {new_qty}")
        else:
            # New product - add to cart
            # CRITICAL DEBUG: Log price when adding normal product to cart
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"NORMAL_PRODUCT_CART","location":"sales_tab.py:add_item","message":"Adding normal product to cart","data":{"price":float(product["price"]),"base_price":float(product["price"]),"price_includes_tax":True,"product_id":product["id"],"name":product["name"],"sku":product["sku"]},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            line = {
                "product_id": product["id"],
                "sku": product["sku"],
                "name": product["name"],
                "price": float(product["price"]),
                "base_price": float(product["price"]),
                "price_normal": float(product["price"]),
                "price_wholesale": float(product.get("price_wholesale", 0.0) or 0.0),
                "is_wholesale": False,
                "qty": qty,
                "price_includes_tax": True,
                "discount": 0.0,
                "sale_type": sale_type,
                "kit_items": kit_items,
            }
            self.cart.append(line)
            logger.info(f"[CART] New product added to cart: {product['name']} x{qty}")
        
        cart_size = len(self.cart)
        logger.info(f"[CART] Total items in cart: {cart_size}")
        
        # Safety: Limit cart size to prevent crashes
        # Configurable limit - can be increased for large orders
        MAX_CART_SIZE = 4000  # Increased from 2000 to support very large orders (2000+ items)
        if cart_size > MAX_CART_SIZE:
            logger.warning(f"[CART] Cart size ({cart_size}) exceeds maximum ({MAX_CART_SIZE}), truncating...")
            with self._cart_lock:  # Thread-safe
                self.cart = self.cart[:MAX_CART_SIZE]
                cart_size = len(self.cart)
            ToastManager.warning(
                "⚠️ Límite de productos",
                f"El carrito tiene un límite de {MAX_CART_SIZE} productos.\nSe mantendrán los primeros {MAX_CART_SIZE}.",
                [("ok", "Entendido")],
                parent=self.window()
            )
        
        # #region agent log
        if agent_log_enabled():
            try:
                with open(Path(DATA_DIR) / "logs" / "crash_debug.log", 'a', encoding='utf-8') as f:
                    import json, time
                    f.write(json.dumps({
                        "sessionId": "crash-debug",
                        "runId": "run1",
                        "location": "sales_tab.py:add_item",
                        "message": "add_item completed, about to refresh",
                        "data": {"cart_size": cart_size},
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
            except Exception as e:
                 logger.debug("Writing debug log: %s", e)
        # #endregion
        
        # #endregion
        
        # WARNING: Large cart may cause performance issues
        if cart_size > 100:
            logger.warning(f"[CART] Large cart detected: {cart_size} items. Performance may degrade.")
        
        # Auto-save cart state to prevent data loss
        # More frequent saves for very large carts
        try:
            self._save_current_session_to_memory()
            # Adaptive save frequency based on cart size
            if cart_size > 500:
                save_frequency = 10  # Every 10 items for very large carts
            elif cart_size > 100:
                save_frequency = 5   # Every 5 items for large carts
            else:
                save_frequency = 5   # Every 5 items for normal carts
            
            # Save to disk periodically or if cart is large
            if cart_size % save_frequency == 0 or cart_size > 20:
                self.save_state()
                logger.debug(f"[AUTO_SAVE] Cart state saved ({cart_size} items, frequency={save_frequency})")
        except Exception as save_err:
            logger.warning(f"[AUTO_SAVE] Failed to save cart state: {save_err}")
        
        # Debounced refresh: delay refresh for rapid additions
        if self._refresh_timer:
            self._refresh_timer.stop()
        
        # For large carts, use debounced refresh to avoid lag
        # Adaptive delay: more items = longer delay
        if cart_size > 15:
            from PyQt6.QtCore import QTimer
            if not hasattr(self, '_refresh_timer') or self._refresh_timer is None:
                self._refresh_timer = QTimer(self)
                self._refresh_timer.setSingleShot(True)
                self._refresh_timer.timeout.connect(self._refresh_table)
            self._refresh_timer.stop()  # Stop any pending refresh
            
            # Adaptive delay based on cart size
            if cart_size > 500:
                delay = 200  # 200ms for very large carts (500+)
            elif cart_size > 100:
                delay = 100  # 100ms for large carts (100+)
            else:
                delay = 50   # 50ms for medium carts (15-100)
            
            self._refresh_timer.start(delay)
            logger.debug(f"[REFRESH] Debounced refresh scheduled (cart_size={cart_size}, delay={delay}ms)")
        else:
            # Small carts: refresh immediately
            try:
                self._refresh_table()
            except Exception as e:
                logger.error(f"[CART] Error refreshing table: {e}")
                import traceback
                logger.error(traceback.format_exc())
                try:
                    with open(Path(DATA_DIR) / "logs" / "crash_debug.log", 'a') as f:
                        f.write(json.dumps({"sessionId":"crash-debug","runId":"run1","hypothesisId":"D","location":"sales_tab.py:add_item","message":"Exception in _refresh_table after add_item","data":{"cart_size":cart_size,"error":str(e),"error_type":type(e).__name__},"timestamp":int(time.time()*1000)})+"\n")
                except Exception:
                    pass
                ToastManager.error(
                    "⚠️ Error actualizando tabla",
                    f"El carrito tiene {cart_size} productos.\nPuede haber un problema de rendimiento.",
                    [("ok", "Continuar")],
                    parent=self.window()
                )
        
        self._play_add_sound()  # Sound feedback for successful add
        self.sku_input.clear()
        self.qty_input.setValue(1)
        logger.info(f"[ADD_ITEM] Completed successfully")

    def add_common_product(self) -> None:
        """Agregar producto común (Ctrl+P) - venta sin registro en catálogo"""
        dialog = CommonProductDialog(self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted and dialog.result_data:
            result = dialog.result_data
            
            # CRITICAL: Create product in database immediately to prevent FOREIGN KEY errors
            # and protect against power outages
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            # Generate unique SKU: COM-YYYYMMDDHHMMSS-XXX
            import random
            random_suffix = str(random.randint(100, 999))
            unique_sku = f"COM-{timestamp}-{random_suffix}"
            
            # Create product in database
            try:
                # CRITICAL DEBUG: Log price when creating common product
                # #region agent log
                if agent_log_enabled():
                    import json, time
                    try:
                        from app.utils.path_utils import get_debug_log_path_str
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"COMMON_PRODUCT","location":"sales_tab.py:add_common_product","message":"Creating common product","data":{"price":float(result["price"]),"name":result["name"],"sku":unique_sku},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                # #endregion
                product_data = {
                    "sku": unique_sku,
                    "name": result["name"],
                    "price": float(result["price"]),
                    "cost": 0.0,
                    "stock": 999999,  # High stock so +/- buttons work (but visible=0 hides from catalog)
                    "min_stock": 0,
                    "department": "COMUN",
                    "sale_type": "unit",
                    "visible": 0,  # Hidden from catalog - only for this sale
                    "sat_clave_prod_serv": result.get("sat_clave_prod_serv", "01010101"),
                    "sat_clave_unidad": "H87",  # Default: Pieza
                }
                product_id = self.core.create_product(product_data)
                
                if not product_id:
                    raise RuntimeError("Failed to create common product in database")
                    
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"No se pudo crear el producto común: {e}"
                )
                return
            
            # Now add to cart with the real product_id
            # CRITICAL DEBUG: Log price when adding common product to cart
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"COMMON_PRODUCT_CART","location":"sales_tab.py:add_common_product","message":"Adding common product to cart","data":{"price":float(result["price"]),"base_price":float(result["price"]),"price_includes_tax":True,"product_id":product_id,"name":result["name"]},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            line = {
                "product_id": product_id,  # Real ID from database
                "sku": unique_sku,
                "name": result["name"],
                "description": result.get("description", result["name"]),
                "price": float(result["price"]),
                "base_price": float(result["price"]),
                "price_normal": float(result["price"]),
                "price_wholesale": 0.0,
                "is_wholesale": False,
                "qty": float(result["qty"]),
                "price_includes_tax": True,  # Common products always include tax
                "discount": 0.0,
                "is_common": True,  # Flag for identification
                "sale_type": "unit",
                "iva": result.get("iva", True),  # For invoicing
                "ieps": result.get("ieps", False),  # For invoicing
                "sat_clave_prod_serv": result.get("sat_clave_prod_serv", "01010101"),
            }
            self.cart.append(line)
            self._refresh_table()
            self._save_current_session_to_memory()

    def _open_multiple_products_dialog(self) -> None:
        """INS - Dialog para agregar varios productos rápidamente"""
        from app.dialogs.multiple_products_dialog import MultipleProductsDialog
        
        dialog = MultipleProductsDialog(self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted and dialog.result_data:
            code = dialog.result_data["code"]
            qty = dialog.result_data["qty"]
            
            # Try to find product
            product = self.core.get_product_by_sku_or_barcode(code)
            if not product:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Producto no encontrado",
                    f"No se encontró ningún producto con el código: {code}"
                )
                return
            
            # Add to cart with specified quantity
            self._add_product_to_cart(product, qty)

    def open_price_checker(self, preset_query: str | None = None) -> None:
        dialog = PriceCheckerDialog(
            self.core, branch_id=STATE.branch_id, on_add=self.add_product_from_checker, parent=self
        )
        if preset_query:
            dialog.search_line.setText(preset_query)
            dialog.do_search()
        dialog.exec()

    def _open_price_checker_from_field(self) -> None:
        preset = self._normalize_scan(self.sku_input.text())
        self.open_price_checker(preset if preset else None)

    def _open_product_search(self) -> None:
        dialog = ProductSearchDialog(core=self.core, parent=self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted and dialog.selected_product:
            self.add_product_from_search(dialog.selected_product)

    def add_product_from_checker(self, product: dict[str, Any]) -> None:
        qty = self.qty_input.value()
        stock_available = int(product.get("stock", 0) or 0)
        if stock_available and stock_available < qty:
            QtWidgets.QMessageBox.warning(self, "Sin stock", "No hay suficiente inventario")
            return
        line = {
            "product_id": product.get("product_id") or product.get("id"),
            "sku": product.get("sku"),
            "name": product.get("name"),
            "price": float(product.get("price", 0.0)),
            "base_price": float(product.get("price", 0.0)),
            "price_normal": float(product.get("price", 0.0)),
            "price_wholesale": float(product.get("price_wholesale", 0.0) or 0.0),
            "is_wholesale": False,
            "qty": qty,
            "price_includes_tax": True, # Fix: Default to True to avoid adding tax on top
            "discount": 0.0,
        }
        self.cart.append(line)
        self._refresh_table()

    def add_product_from_search(self, product: dict[str, Any]) -> None:
        sale_type = (product.get("sale_type") or product.get("unit_type") or "unit").lower()
        qty = float(self.qty_input.value())
        if sale_type in {"weight", "granel"}:
            from app.dialogs.bulk_sale_dialog import BulkSaleDialog
            dialog = BulkSaleDialog(product, self)
            if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                qty = dialog.result_qty
            else:
                return
        product_id = product.get("product_id") or product.get("id")
        stock_available = float(product.get("stock", 0.0) or 0.0)
        kit_items = []
        if sale_type == "kit":
            kit_items = self.core.get_kit_items(product_id)
            for comp in kit_items:
                comp_stock = self.core.get_stock_info(comp.get("product_id"), STATE.branch_id) or {}
                if float(comp_stock.get("stock", 0.0) or 0.0) < qty * float(comp.get("qty", 1)):
                    QtWidgets.QMessageBox.warning(self, "Sin stock", "Componente de kit sin inventario")
                    return
        if stock_available and stock_available < qty and sale_type != "kit":
            QtWidgets.QMessageBox.warning(self, "Sin stock", "No hay suficiente inventario")
            return
        line = {
            "product_id": product_id,
            "sku": product.get("sku"),
            "name": product.get("name"),
            "price": float(product.get("price", 0.0)),
            "base_price": float(product.get("price", 0.0)),
            "price_normal": float(product.get("price", 0.0)),
            "price_wholesale": float(product.get("price_wholesale", 0.0) or 0.0),
            "is_wholesale": False,
            "qty": qty,
            "price_includes_tax": True,
            "discount": 0.0,
            "sale_type": sale_type,
            "kit_items": kit_items,
        }
        self.cart.append(line)
        self._refresh_table()

    def _normalize_scan(self, text: str) -> str:
        value = (text or "").strip()
        if self.scanner_prefix and value.startswith(self.scanner_prefix):
            value = value[len(self.scanner_prefix) :]
        if self.scanner_suffix and value.endswith(self.scanner_suffix):
            value = value[: -len(self.scanner_suffix)]
        return value.strip()

    def _focus_sku_input(self) -> None:
        """Focus SKU input field if it exists. Safe to call from QTimer."""
        if hasattr(self, 'sku_input') and self.sku_input:
            self.sku_input.setFocus()

    def _reset_processing_error(self) -> None:
        """Reset the processing error flag. Safe to call from QTimer."""
        self._processing_error = False

    def _fetch_product(self, identifier: str) -> Any:
        if self.mode == "client" and self.network_client:
            try:
                data = self.network_client.fetch_product(identifier)
                if data:
                    return {
                        "id": data.get("id"),
                        "sku": data.get("sku"),
                        "barcode": data.get("barcode"),
                        "name": data.get("name"),
                        "price": data.get("price"),
                        "price_wholesale": data.get("price_wholesale", 0.0),
                    }
            except Exception:
                self._set_offline(True)
        return self.core.get_product_by_sku_or_barcode(identifier)

    def _customer_button_clicked(self) -> None:
        if self.current_customer_id:
            self.clear_customer()
        else:
            self.open_assign_customer()

    def _avatar_color(self, seed: str) -> str:
        h = hash(seed) & 0xFFFFFF
        r = (((h >> 16) & 0xFF) + 255) // 2
        g = (((h >> 8) & 0xFF) + 255) // 2
        b = ((h & 0xFF) + 255) // 2
        return f"rgb({r},{g},{b})"

    def _update_customer_badge(self) -> None:
        if self.current_customer_id and self.current_customer_name:
            initial = self.current_customer_name[0].upper()
            bg_color = self._avatar_color(self.current_customer_name)
            self.customer_avatar.setText(f"{initial}")
            self.customer_avatar.setStyleSheet(f"""
                QLabel {{
                    background: {bg_color};
                    color: white;
                    border-radius: 20px;
                    font-weight: bold;
                    font-size: 16px;
                }}
            """)
            self.customer_avatar.setToolTip(self.current_customer_name)
            self.customer_label.setText(self.current_customer_name)
            if hasattr(self, 'clear_customer_btn'):
                self.clear_customer_btn.setVisible(True)
            if self.loyalty_widget:
                # Get loyalty balance for customer
                saldo = self.core.get_loyalty_balance(self.current_customer_id)
                from decimal import Decimal
                self.loyalty_widget.set_customer(
                    self.current_customer_id, 
                    self.current_customer_name,
                    Decimal(str(saldo))
                )
        else:
            self.customer_avatar.setText("👤")
            self.customer_avatar.setStyleSheet("font-size: 18px; border: none;")
            self.customer_label.setText("Público General")
            if hasattr(self, 'clear_customer_btn'):
                self.clear_customer_btn.setVisible(False)
            # Hide loyalty widget when no customer is assigned
            if self.loyalty_widget:
                self.loyalty_widget.setVisible(False)

    def _set_offline(self, offline: bool) -> None:
        if hasattr(self, 'offline_banner') and self.offline_banner:
            self.offline_banner.setVisible(offline)

    def _scan_with_camera(self) -> None:
        if not self.camera_enabled:
            QtWidgets.QMessageBox.information(self, "Escáner", "Habilita el lector por cámara en Configuración")
            return
        if self.camera_thread and self.camera_thread.isRunning():
            return
        try:
            self.camera_thread = CameraScannerThread(self.camera_index, self)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Cámara", f"No se pudo iniciar la cámara: {exc}")
            return
        self.camera_thread.code_detected.connect(self._on_camera_code)
        self.camera_thread.start()

    def _on_camera_code(self, code: str) -> None:
        """
        Callback cuando cámara detecta código.
        IMPORTANTE: Este código corre en thread de cámara.
        Usar QtCore.QTimer para ejecutar en UI thread (thread-safe).
        """
        normalized = self._normalize_scan(code)

        # CRITICAL: Ejecutar en UI thread para evitar race conditions
        # No modificar carrito directamente desde thread de cámara
        # Store normalized code temporarily for thread-safe processing
        self._pending_camera_code = normalized
        QtCore.QTimer.singleShot(0, self._process_pending_camera_code)

        if self.camera_thread:
            self.camera_thread.stop()

    def _process_pending_camera_code(self) -> None:
        """Process pending camera code in UI thread. Safe to call from QTimer."""
        if hasattr(self, '_pending_camera_code') and self._pending_camera_code:
            code = self._pending_camera_code
            self._pending_camera_code = None
            self._add_item_from_camera(code)
    
    def _add_item_from_camera(self, code: str) -> None:
        """
        Agregar item desde cámara (ejecuta en UI thread - seguro).
        """
        self.sku_input.setText(code)
        self.add_item()  # Ahora es seguro porque corre en UI thread

    def open_assign_customer(self) -> None:
        dialog = AssignCustomerDialog(self.core, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted and dialog.selected_customer_id:
            self.current_customer_id = dialog.selected_customer_id
            self.current_customer_name = dialog.selected_customer_name
            self._update_customer_badge()

    def clear_customer(self) -> None:
        self.current_customer_id = None
        self.current_customer_name = None
        self._update_customer_badge()

    def _refresh_table(self) -> None:
        """Refresh cart table with robust error handling and logging."""
        import traceback
        needs_full_refresh = True  # This method does a full table refresh
        import sys
        from pathlib import Path
        
        # Log file for crash debugging
        try:
            crash_log_file = Path(DATA_DIR) / "logs" / "crash_debug.log"
            crash_log_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as path_err:
            # Fallback if DATA_DIR is not available
            crash_log_file = Path.home() / ".titan_pos_crash.log"
            crash_log_file.parent.mkdir(parents=True, exist_ok=True)
        
        cart_size = len(self.cart)
        
        # Calculate cart hash for incremental updates
        try:
            import hashlib
            cart_hash = hashlib.sha256(json.dumps(self.cart, sort_keys=True, default=str).encode()).hexdigest()
        except Exception:
            cart_hash = None
        
        # Log entry
        try:
            with open(crash_log_file, 'a', encoding='utf-8') as f:
                import json, time
                f.write(json.dumps({
                    "sessionId": "crash-debug",
                    "runId": "run1",
                    "location": "sales_tab.py:_refresh_table",
                    "message": "_refresh_table started",
                    "data": {
                        "cart_size": cart_size,
                        "has_table": bool(self.table),
                        "table_type": str(type(self.table)) if hasattr(self, 'table') else "None"
                    },
                    "timestamp": int(time.time() * 1000)
                }) + "\n")
        except Exception as log_err:
            # If logging fails, at least print to stderr
            print(f"[CRASH_DEBUG] Failed to write log: {log_err}", file=sys.stderr)
        
        # Safety check: ensure table exists
        if not hasattr(self, 'table') or self.table is None:
            logger.error("[CRASH_DEBUG] Table widget is None or missing!")
            try:
                with open(crash_log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[ERROR] Table widget is None at {cart_size} items\n")
            except Exception as e:
                 logger.debug("Writing debug log: %s", e)
            return
        
        try:
            # OPTIMIZATION: Disable updates while refreshing to prevent UI lag
            self.table.setUpdatesEnabled(False)
            
            # OPTIMIZATION: For large carts, use block signals
            # Adaptive threshold: block signals earlier for very large carts
            if cart_size > 500:
                block_threshold = 5   # Block signals with 5+ items for very large carts
            elif cart_size > 100:
                block_threshold = 8   # Block signals with 8+ items for large carts
            else:
                block_threshold = 10  # Block signals with 10+ items for normal carts
            
            if cart_size > block_threshold:
                self.table.blockSignals(True)
            
            # Store threshold for later use
            self._block_threshold = block_threshold
            
            # Safety: Validate cart_size before setRowCount
            if cart_size < 0:
                logger.error(f"[CRASH_DEBUG] Invalid cart_size: {cart_size}")
                cart_size = 0
            
            # CRITICAL FIX: Clean up old widgets BEFORE setRowCount to prevent memory leak
            # setRowCount() does NOT automatically delete old QTableWidgetItem widgets
            # Without cleanup, each refresh creates new widgets but old ones remain in memory
            # With 30 products × 5 columns = 150 widgets per refresh
            # After 10 refreshes = 1500 widgets in memory → CRASH
            try:
                # Method 1: Clear all items (fastest, recommended)
                self.table.clearContents()
                # Note: clearContents() removes items but keeps row count, so we still need setRowCount
            except Exception as clear_err:
                logger.warning(f"[MEMORY_FIX] clearContents() failed, using manual cleanup: {clear_err}")
                # Method 2: Manual cleanup (fallback if clearContents fails)
                try:
                    current_rows = self.table.rowCount()
                    for row in range(current_rows):
                        for col in range(self.table.columnCount()):
                            item = self.table.takeItem(row, col)
                            if item:
                                # Explicitly delete the item to free memory
                                del item
                except Exception as manual_err:
                    logger.error(f"[MEMORY_FIX] Manual cleanup also failed: {manual_err}")
            
            # Log before setRowCount (critical operation)
            try:
                with open(crash_log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[CRASH_DEBUG] Cleaned old widgets, about to setRowCount({cart_size})\n")
            except Exception as e:
                 logger.debug("Writing debug log: %s", e)
            
            # Now safe to set new row count (old widgets are cleaned)
            self.table.setRowCount(cart_size)
            subtotal = 0.0
            tax_total = 0.0
            total_before_global = 0.0
            total_line_discounts = 0.0  # NEW: Track line-level discounts
            
            wholesale_color = QtGui.QColor(254, 215, 102)
            discount_color = QtGui.QColor(142, 228, 145)
            weight_color = QtGui.QColor(174, 214, 241)
            kit_color = QtGui.QColor(230, 176, 170)
            
            # #region agent log
            if agent_log_enabled():
                with open(Path(DATA_DIR) / "logs" / "crash_debug.log", 'a') as f:
                    f.write(json.dumps({"sessionId":"crash-debug","runId":"run1","hypothesisId":"C","location":"sales_tab.py:1256","message":"Starting cart iteration","data":{"cart_size":cart_size},"timestamp":int(time.time()*1000)})+"\n")
            # #endregion
            
            with self._cart_lock:  # Thread-safe
                cart_copy = list(self.cart)  # Copia segura para iterar
            for row_idx, item in enumerate(cart_copy):
                try:
                    # Safety: Validate item
                    if not isinstance(item, dict):
                        logger.error(f"[CRASH_DEBUG] Invalid item at row {row_idx}: {type(item)}")
                        continue
                    
                    qty = float(item.get("qty", 1))
                    base_price = float(item.get("base_price", item.get("price", 0)))
                    
                    includes_tax = bool(item.get("price_includes_tax", True))
                    is_wholesale = bool(item.get("is_wholesale", False))
                    
                    # FIXED: Use wholesale price when is_wholesale is True
                    if is_wholesale and item.get("price_wholesale"):
                        effective_price = float(item.get("price_wholesale", 0))
                    else:
                        effective_price = base_price
                    
                    # CRITICAL FIX: Ensure discount is never negative
                    # Negative discounts can occur when price is increased (new_price > base_price)
                    # but we should never allow negative discounts in calculations
                    
                    # #region agent log
                    if agent_log_enabled():
                        # Instrumentación ANTES de leer el descuento para rastrear el origen
                        import json, time
                        try:
                            item_discount_raw = item.get("discount", 0.0)
                            with open(get_debug_log_path_str(), "a") as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"NEGATIVE_DISCOUNT_TRACE","location":"sales_tab.py:_refresh_table:before_read","message":"Reading discount from item","data":{"row_idx":row_idx,"product_id":item.get("product_id"),"item_discount_raw":item_discount_raw,"item_discount_type":type(item_discount_raw).__name__,"is_wholesale":is_wholesale},"timestamp":int(time.time()*1000)})+"\n")
                        except Exception as e:
                             logger.debug("Writing debug log: %s", e)
                    # #endregion
                    
                    raw_discount = 0.0 if is_wholesale else float(item.get("discount", 0.0))
                    
                    # CRITICAL: Normalize -0.0 to 0.0 (Python distinguishes them, but they're mathematically equal)
                    # This prevents issues with comparisons and JSON serialization
                    # Use tolerance check for floating point comparison
                    if abs(raw_discount) < 1e-9:
                        raw_discount = 0.0  # Normalize -0.0 and near-zero to 0.0
                        # CRITICAL: Also fix the item directly to prevent -0.0 from persisting
                        item_discount_value = float(item.get("discount", 0.0))
                        if abs(item_discount_value) < 1e-9:
                            item["discount"] = 0.0  # Normalize in item
                    
                    # #region agent log
                    if agent_log_enabled():
                        # Instrumentación para detectar descuentos negativos
                        if raw_discount < 0:
                            try:
                                with open(get_debug_log_path_str(), "a") as f:
                                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"NEGATIVE_DISCOUNT","location":"sales_tab.py:_refresh_table","message":"Negative discount detected and clamped","data":{"row_idx":row_idx,"product_id":item.get("product_id"),"raw_discount":raw_discount,"item_discount_before":item.get("discount"),"base_price":base_price,"effective_price":effective_price,"qty":qty,"is_wholesale":is_wholesale},"timestamp":int(time.time()*1000)})+"\n")
                            except Exception as e:
                                 logger.debug("Writing debug log: %s", e)
                            # CRITICAL: Fix the item's discount directly to prevent it from persisting
                            item["discount"] = 0.0
                            raw_discount = 0.0  # Update raw_discount after fixing
                    # #endregion
                    
                    line_discount = max(0.0, raw_discount)  # Clamp to 0 if negative
                    total_line_discounts += line_discount  # NEW: Accumulate line discounts
                    
                    line_base = effective_price * qty
                    
                    if includes_tax:
                        gross = max(line_base - line_discount, 0)
                        base_without_tax = gross / (1 + self.tax_rate)
                        line_tax = gross - base_without_tax
                        line_total = gross
                    else:
                        base_without_tax = max(line_base - line_discount, 0)
                        line_tax = base_without_tax * self.tax_rate
                        line_total = base_without_tax + line_tax
                
                    base_without_tax = round(base_without_tax, 2)
                    line_tax = round(line_tax, 2)
                    line_total = round(line_total, 2)
                
                    subtotal += base_without_tax
                    tax_total += line_tax
                    total_before_global += line_total
                    
                    # FIXED: Mostrar el precio actual (ya refleja cambios manuales)
                    # Cuando el precio se modifica manualmente, base_price = new_price y discount = 0
                    # Por lo tanto, el precio a mostrar es simplemente effective_price
                    # CRITICAL: Si discount = 0, el precio ya es el final, no calcular con descuento
                    if line_discount > 0 and qty > 0:
                        # Si hay descuento, calcular precio unitario con descuento
                        display_price = (line_base - line_discount) / qty
                    else:
                        # Usar effective_price directamente (ya refleja cambios manuales o wholesale)
                        # NO calcular (line_base - line_discount) / qty cuando discount = 0
                        # porque eso daría el mismo resultado pero es más claro usar effective_price
                        display_price = effective_price
                    
                    # #region agent log
                    if agent_log_enabled():
                        # Instrumentación mejorada para rastrear precio mostrado
                        try:
                            with open(get_debug_log_path_str(), "a") as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"sales_tab.py:_refresh_table","message":"Calculating display price","data":{"row_idx":row_idx,"base_price":base_price,"effective_price":effective_price,"qty":qty,"line_discount":line_discount,"line_base":line_base,"display_price":display_price,"item_price":item.get("price"),"item_base_price":item.get("base_price"),"item_discount":item.get("discount"),"is_wholesale":is_wholesale,"line_total":line_total},"timestamp":int(time.time()*1000)})+"\n")
                        except Exception as e:
                             logger.debug("Writing debug log: %s", e)
                    # #endregion
                    
                    # OPTIMIZATION: Create cells in batch
                    values = [
                        str(item.get("sku", "")),
                        str(item.get("name", "")),
                        f"{display_price:.2f}", # Precio Unitario Base
                        f"{qty:.3g}",
                        f"{line_total:.2f}",    # Total de línea (con descuento aplicado)
                    ]
                    
                    bg_color: QtGui.QColor | None = None
                    if is_wholesale:
                        bg_color = wholesale_color
                    elif line_discount > 0:
                        bg_color = discount_color
                    sale_type = (item.get("sale_type") or "unit").lower()
                    if sale_type == "weight":
                        bg_color = weight_color
                    elif sale_type == "kit":
                        bg_color = kit_color
                    
                    # OPTIMIZATION: Set items and colors in one pass
                    # Safety: Validate row_idx before setItem
                    if row_idx >= cart_size:
                        logger.error(f"[CRASH_DEBUG] row_idx {row_idx} >= cart_size {cart_size}")
                        break
                    
                    for col, value in enumerate(values):
                        try:
                            # CRITICAL FIX: Check if item already exists and reuse/delete it
                            # This prevents creating duplicate widgets if refresh is called multiple times
                            existing_item = self.table.item(row_idx, col)
                            if existing_item:
                                # Reuse existing item (update text instead of creating new)
                                existing_item.setText(str(value))
                                if bg_color:
                                    existing_item.setBackground(bg_color)
                                # Item already has correct flags from previous creation
                            else:
                                # Create new item only if it doesn't exist
                                cell = QtWidgets.QTableWidgetItem(str(value))
                                cell.setFlags(cell.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                                if bg_color:
                                    cell.setBackground(bg_color)
                                self.table.setItem(row_idx, col, cell)
                        except Exception as cell_err:
                            logger.error(f"[CRASH_DEBUG] Error setting cell at row {row_idx}, col {col}: {cell_err}")
                            try:
                                with open(crash_log_file, 'a', encoding='utf-8') as f:
                                    f.write(f"[CRASH_DEBUG] Cell error at row {row_idx}, col {col}: {cell_err}\n")
                                    f.write(traceback.format_exc() + "\n")
                            except Exception as e:
                                 logger.debug("Writing debug log: %s", e)
                            # Continue with next cell
                    
                    # Log progress every 10 items (more frequent for debugging)
                    if (row_idx + 1) % 10 == 0:
                        try:
                            with open(crash_log_file, 'a', encoding='utf-8') as f:
                                f.write(f"[CRASH_DEBUG] Progress: {row_idx + 1}/{cart_size} items processed\n")
                        except Exception as e:
                             logger.debug("Writing debug log: %s", e)
                        
                except Exception as item_err:
                    logger.error(f"[CRASH_DEBUG] Error processing item at row {row_idx}: {item_err}")
                    try:
                        with open(crash_log_file, 'a', encoding='utf-8') as f:
                            f.write(f"[CRASH_DEBUG] Item error at row {row_idx}: {item_err}\n")
                            f.write(traceback.format_exc() + "\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                    # Continue with next item
                    continue
            
            discount_amount = 0.0
            if self.global_discount:
                # CRITICAL FIX: Calcular descuento global sobre subtotal (SIN IVA) para consistencia con BD
                # En create_sale_transaction(), el descuento se aplica sobre subtotal (sin IVA)
                # Por lo tanto, aquí también debe calcularse sobre subtotal (sin IVA)
                if self.global_discount["type"] == "percent":
                    discount_amount = subtotal * (float(self.global_discount["value"]) / 100.0)
                else:
                    discount_amount = float(self.global_discount["value"])
                # Limitar descuento al subtotal (no puede ser mayor que el subtotal)
                discount_amount = min(discount_amount, subtotal)
            
            # Calcular total: subtotal - descuento global, luego agregar IVA
            subtotal_after_discount = max(subtotal - discount_amount, 0)
            # Recalcular IVA proporcionalmente sobre el subtotal después del descuento
            # Si el subtotal cambió por el descuento, el IVA debe ajustarse proporcionalmente
            if subtotal > 0:
                tax_ratio = tax_total / subtotal
                tax_total_adjusted = subtotal_after_discount * tax_ratio
            else:
                tax_total_adjusted = 0.0
            total = subtotal_after_discount + tax_total_adjusted
            self._last_total_before_global = total_before_global
            self._last_subtotal_before_global = subtotal  # CRITICAL: Guardar subtotal sin IVA para descuento global
            
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    # Calcular subtotal ANTES de descuentos individuales para verificación
                    subtotal_before_line_discounts = sum((float(item.get("base_price", item.get("price", 0))) * float(item.get("qty", 1))) for item in self.cart)
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"COMBINED","location":"sales_tab.py:_refresh_table","message":"Combined discounts calculation","data":{"subtotal_before_line_discounts":subtotal_before_line_discounts,"total_line_discounts":total_line_discounts,"subtotal_after_line_discounts":subtotal,"global_discount":self.global_discount,"global_discount_amount":discount_amount,"subtotal_after_global_discount":subtotal_after_discount,"tax_total_original":tax_total,"tax_total_adjusted":tax_total_adjusted,"total":total,"has_line_discounts":total_line_discounts>0,"has_global_discount":bool(self.global_discount)},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            
            # Calculate points (Rule: 5% of total purchase)
            points_earned = total * 0.05
            
            # NEW: Show total discounts (line + global)
            total_discounts = total_line_discounts + discount_amount
            
            self.subtotal_lbl.setText(f"Subtotal: ${subtotal:.2f}")
            self.global_discount_lbl.setText(f"Descuento: -${total_discounts:.2f}")
            self.tax_lbl.setText(f"IVA: ${tax_total_adjusted:.2f}")
            self.total_lbl.setText(f"TOTAL: ${total:.2f}")
            self.totals = {
                "subtotal": subtotal_after_discount,  # Subtotal después del descuento global
                "tax": tax_total_adjusted,  # IVA ajustado proporcionalmente
                "total": total, 
                "global_discount": discount_amount,
                "points_earned": points_earned
            }
            
            # Update loyalty widget
            self._update_loyalty_potential()
            
            # Update tracking state
            self._last_cart_size = cart_size
            self._last_cart_hash = cart_hash
            
            # OPTIMIZATION: Re-enable updates after refresh
            # Use same adaptive threshold as above
            block_threshold = getattr(self, '_block_threshold', 10)
            if cart_size > block_threshold:
                self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            
            # Log successful completion
            try:
                with open(crash_log_file, 'a', encoding='utf-8') as f:
                    import json, time
                    f.write(json.dumps({
                        "sessionId": "crash-debug",
                        "runId": "run1",
                        "location": "sales_tab.py:_refresh_table",
                        "message": "_refresh_table completed successfully",
                        "data": {
                            "cart_size": cart_size,
                            "total": total,
                            "refresh_mode": "FULL" if needs_full_refresh else "INCREMENTAL"
                        },
                        "timestamp": int(time.time() * 1000)
                    }) + "\n")
            except Exception as e:
                 logger.debug("Writing debug log: %s", e)
            
        except Exception as e:
            # Critical error - log everything
            error_msg = f"[CRASH_DEBUG] CRITICAL ERROR in _refresh_table with {cart_size} items: {e}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            
            # Write to crash log file
            try:
                with open(crash_log_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n{'='*80}\n")
                    f.write(f"[CRITICAL ERROR] {error_msg}\n")
                    f.write(f"Cart size: {cart_size}\n")
                    f.write(f"Error type: {type(e).__name__}\n")
                    f.write(f"Error message: {str(e)}\n")
                    f.write(f"\nTraceback:\n{traceback.format_exc()}\n")
                    f.write(f"{'='*80}\n\n")
                    f.flush()  # Force write
            except Exception as log_err:
                # If file logging fails, at least print to stderr
                print(f"[CRASH_DEBUG] Failed to write crash log: {log_err}", file=sys.stderr)
                print(f"[CRASH_DEBUG] Original error: {e}", file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
            
            # Re-enable updates even on error (critical for recovery)
            try:
                if hasattr(self, 'table') and self.table is not None:
                    self.table.setUpdatesEnabled(True)
                    if cart_size > 10:
                        self.table.blockSignals(False)
            except Exception as recovery_err:
                logger.error(f"[CRASH_DEBUG] Failed to recover table state: {recovery_err}")
                try:
                    with open(crash_log_file, 'a', encoding='utf-8') as f:
                        f.write(f"[CRASH_DEBUG] Recovery failed: {recovery_err}\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            
            # Try to show partial table or empty table
            try:
                if hasattr(self, 'table') and self.table is not None:
                    # Set a safe row count
                    safe_count = min(cart_size, 100)  # Limit to 100 rows max
                    self.table.setRowCount(safe_count)
                    # Show error message in first row
                    error_cell = QtWidgets.QTableWidgetItem(f"Error al mostrar carrito: {str(e)[:50]}")
                    error_cell.setBackground(QtGui.QColor(255, 200, 200))
                    self.table.setItem(0, 0, error_cell)
            except Exception as ui_err:
                logger.error(f"[CRASH_DEBUG] Failed to show error UI: {ui_err}")
            
            # Don't re-raise - let the app continue
            # But log the error for debugging
    
    def _update_loyalty_potential(self) -> None:
        """Update potential loyalty points in widget."""
        if self.loyalty_widget and self.current_customer_id and self.cart:
            try:
                cashback = self.core.calcular_cashback(self.cart, self.current_customer_id)
                if cashback:
                    self.loyalty_widget.update_puntos_potenciales(cashback.total_puntos)
            except Exception as e:
                print(f"Error calculating cashback: {e}")
    def _verify_server_stock(self) -> bool:
        """
        Check real-time stock availability with server.
        
        Returns:
            True if stock is available or check skipped/offline (with confirm).
            False if stock is definitely insufficient.
        """
        if not self.network_client:
            return True
            
        # Check if enabled in config
        cfg = self.core.get_app_config() or {}
        if not cfg.get("enable_strict_stock", True): # Default True
             return True
             
        # Show checking dialog
        progress = QtWidgets.QProgressDialog("Verificando existencias en servidor...", None, 0, 0, self)
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        progress.show()
        QtWidgets.QApplication.processEvents()
        
        try:
            from app.utils.network_client import MultiCajaClient

            # Get API token
            cfg = self.core.get_app_config() or {}
            token = cfg.get("api_dashboard_token", "")
            
            if not token:
                progress.close()
                return True
            
            # Use short timeout key for responsiveness
            client = MultiCajaClient(
                self.network_client.base_url,
                timeout=5,
                token=token
            )
            
            # Prepare items
            items_to_check = []
            for item in self.cart:
                # Use SKU if available, otherwise just skip (can't check non-inventory items)
                sku = item.get('sku')
                product_id = item.get('product_id')
                if not sku and product_id:
                     # Try to find SKU in core if missing (though usually cart has it)
                     # For now, rely on SKU in cart
                     pass
                     
                if sku:
                    items_to_check.append({
                        "sku": sku,
                        "qty": float(item.get('qty', 0))
                    })
            
            if not items_to_check:
                progress.close()
                return True
                
            # Perform check
            result = client.check_realtime_stock(items_to_check)
            progress.close()

            # Validar que result es un diccionario válido
            if not result or not isinstance(result, dict):
                logger.warning("Stock check returned invalid response")
                return True  # Fail open - permitir venta si respuesta inválida

            # Handle offline/error
            if result.get("offline") or result.get("error"):
                logger.warning(f"Stock check offline/error: {result.get('error')}")
                reply = QtWidgets.QMessageBox.warning(
                    self,
                    "⚠️ Servidor No Disponible",
                    "No se pudo verificar el stock con el servidor central.\n\n"
                    "¿Deseas continuar con la venta bajo tu riesgo%s\n"
                    "(Podría haber sobreventa de productos)",
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
                )
                return reply == QtWidgets.QMessageBox.StandardButton.Yes
            
            # Handle allowed/denied
            if not result.get("allowed", True):
                bad_items = result.get("insufficient_items", [])
                msg = "🚫 <b>STOCK INSUFICIENTE EN SERVIDOR</b><br><br>"
                msg += "Los siguientes productos no tienen existencia suficiente:<br><ul>"
                for i in bad_items:
                    name = i.get('name', 'Producto')
                    req = i.get('requested', 0)
                    avail = i.get('available', 0)
                    msg += f"<li><b>{name}</b> (Pides: {req}, Hay: {avail})</li>"
                msg += "</ul>"
                
                QtWidgets.QMessageBox.warning(self, "Stock Insuficiente", msg)
                return False
                
            return True
            
        except Exception as e:
            progress.close()
            logger.error(f"Stock check critical error: {e}")
            return True # Fail open on critical app error to not block operations

    def _handle_charge(self) -> None:
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E2E1","location":"sales_tab.py:_handle_charge","message":"E2E Flow: Function entry","data":{"cart_size":len(self.cart) if self.cart else 0,"total":self.totals.get("total", 0.0) if hasattr(self, 'totals') else 0.0},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as log_e:
                import traceback
                print(f"DEBUG LOG ERROR (entry): {log_e}\n{traceback.format_exc()}")
        # #endregion
        
        try:
            # CRITICAL VALIDATION: Prevent sales with zero or negative totals
            if not self.cart:
                # #region agent log
                if agent_log_enabled():
                    try:
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E2E1","location":"sales_tab.py:_handle_charge","message":"E2E Flow: Cart empty, returning","data":{},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                # #endregion
                QtWidgets.QMessageBox.warning(self, "Carrito vacío", "Agrega productos antes de cobrar")
                return
                
            current_total = self.totals.get("total", 0.0)
            if current_total <= 0:
                QtWidgets.QMessageBox.critical(
                    self,
                    "❌ Venta Inválida",
                    f"No se puede procesar una venta con total de ${current_total:.2f}\n\n"
                    "Posibles causas:\n"
                    "• Descuento excesivo aplicado\n"
                    "• Precios editados por debajo del costo\n"
                    "• Error en el cálculo del total\n\n"
                    "Ajusta los descuentos o precios antes de continuar."
                )
                return
            
            # CRITICAL: Validate turn is open before allowing sale
            if not STATE.current_turn_id:
                logger.warning("⚠️ Attempted sale without open turn")
                reply = QtWidgets.QMessageBox.critical(
                    self,
                    "⚠️ Turno No Abierto",
                    "No hay un turno abierto actualmente.\n\n"
                    "Debes abrir un turno antes de realizar ventas para:\n"
                    "• Registrar correctamente el ingreso de efectivo\n"
                    "• Llevar control de caja\n"
                    "• Generar reportes precisos\n\n"
                    "¿Deseas abrir un turno ahora%s",
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.Yes
                )
                
                if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                    # Open turn dialog from sales tab
                    from app.dialogs.turn_open_dialog import TurnOpenDialog
                    dlg = TurnOpenDialog(STATE.username or "Usuario", self.core, self)
                    if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted and dlg.result_data:
                        try:
                            turn_id = self.core.open_turn(
                                STATE.branch_id, STATE.user_id,
                                dlg.result_data["opening_amount"],
                                dlg.result_data.get("notes")
                            )
                            STATE.current_turn_id = turn_id
                            self.core.engine.current_turn_id = turn_id
                            logger.info(f"✅ Turn opened from sales tab: ID={turn_id}")
                            
                            # Abrir cajón después de abrir turno
                            try:
                                from app.utils.ticket_engine import open_cash_drawer_safe
                                open_cash_drawer_safe(core=self.core)
                            except Exception as e:
                                logger.warning(f"No se pudo abrir cajón: {e}")
                            
                            QtWidgets.QMessageBox.information(
                                self, 
                                "✅ Turno Abierto", 
                                "Turno abierto correctamente. Ahora puedes realizar la venta."
                            )
                            # Don't return - continue with sale
                        except Exception as e:
                            logger.error(f"Error opening turn from sales tab: {e}")
                            QtWidgets.QMessageBox.critical(
                                self, 
                                "Error", 
                                f"No se pudo abrir el turno:\n{e}"
                            )
                            return
                    else:
                        logger.info("User cancelled turn opening from sales tab")
                        return  # User cancelled - don't allow sale
                else:
                    logger.info("User declined to open turn from sales tab")
                    return  # User said no - don't allow sale
            
            if not self.cart:
                QtWidgets.QMessageBox.information(self, "Sin productos", "Agrega productos antes de cobrar")
                return
            
            # MULTICAJA REAL-TIME STOCK CHECK
            if self.mode == "client":
                if not self._verify_server_stock():
                    return
            
            credit_available = 0.0
            allow_credit = False
            if self.current_customer_id:
                info = self.core.get_customer_credit_info(self.current_customer_id)
                credit_limit = float(info.get("credit_limit", 0.0) or 0.0)
                credit_balance = float(info.get("credit_balance", 0.0) or 0.0)
                authorized = bool(info.get("credit_authorized") or credit_limit != 0)
                allow_credit = authorized
                if credit_limit < 0:
                    credit_available = float("inf")
                else:
                    credit_available = max(credit_limit - credit_balance, 0.0)
            
            wallet_balance = 0.0
            if self.current_customer_id:
                wallet_balance = self.core.get_loyalty_balance(self.current_customer_id)  # Use MIDAS balance

            # --- GIFT CARD ACTIVATION ---
            # Check if cart contains any gift card products
            gift_card_items = []
            for idx, item in enumerate(self.cart):
                product_name = (item.get("name") or "").lower()
                sku = (item.get("sku") or "").lower()
                
                # Detect gift card products by name or SKU
                if any(keyword in product_name for keyword in ["gift card", "tarjeta de regalo", "tarjeta regalo", "giftcard"]) or \
                   any(keyword in sku for keyword in ["giftcard", "gift-card", "gc"]):
                    gift_card_items.append((idx, item))
            
            # DISEÑO: Activar tarjetas de regalo ANTES del pago es intencional.
            # Permite generar el código para imprimirlo en el ticket.
            # Si el usuario cancela, se aborta la venta completa (no se activa la tarjeta).
            # Auditoría 2026-01-30: Confirmado como flujo correcto por diseño.
            if gift_card_items:
                from app.dialogs.gift_card_dialogs import GiftCardActivationDialog
                
                for idx, item in gift_card_items:
                    amount = float(item.get("price", 0)) * float(item.get("qty", 1))
                    
                    activation_dialog = GiftCardActivationDialog(
                        amount=amount,
                        gift_engine=self.core.gift_card_engine,
                        parent=self
                    )
                    
                    if activation_dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                        # Store the generated code in the cart item for printing
                        self.cart[idx]["gift_card_code"] = activation_dialog.card_code
                        self.cart[idx]["is_gift_card"] = True
                    else:
                        # User cancelled gift card activation - abort sale
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Activación Cancelada",
                            "Debe activar la tarjeta de regalo para completar la venta."
                        )
                        return

            cfg = self.core.get_app_config() or {}
            payment_dialog = PaymentDialog(
                self.totals["total"],
                self.core,
                self,
                allow_credit=bool(self.current_customer_id and allow_credit),
                customer_name=self.current_customer_name or "",
                customer_id=self.current_customer_id,
                credit_available=credit_available,
                card_fee_percent=float(cfg.get("card_fee_percent", 0.0) or 0.0),
                default_exchange=float(cfg.get("usd_exchange_rate", 17.0) or 17.0),
                wallet_balance=wallet_balance,
                gift_engine=self.core.gift_card_engine,  # Pass Gift Card Engine
            )

            cart_snapshot = [dict(item) for item in self.cart]
            
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E2E1","location":"sales_tab.py:_handle_charge","message":"E2E Flow: Payment dialog about to open","data":{"cart_size":len(self.cart),"total":self.totals.get("total", 0.0)},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as log_e:
                    import traceback
                    print(f"DEBUG LOG ERROR (payment dialog): {log_e}\n{traceback.format_exc()}")
            # #endregion
            
            if payment_dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted and payment_dialog.result_data:
                # #region agent log
                if agent_log_enabled():
                    try:
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E2E1","location":"sales_tab.py:_handle_charge","message":"E2E Flow: Payment dialog accepted","data":{"payment_method":payment_dialog.result_data.get("method") if payment_dialog.result_data else None},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                # #endregion
                
                method = payment_dialog.result_data.get("method")
                if method == "credit" and not self.current_customer_id:
                    QtWidgets.QMessageBox.warning(self, "Crédito no disponible", "Asigna un cliente antes de vender a crédito")
                    return
                payload = {
                    "items": self.cart,
                    "payment": payment_dialog.result_data,
                    "branch_id": STATE.branch_id,
                    "discount": self.totals.get("global_discount", 0.0),
                    "customer_id": self.current_customer_id,
                    "user_id": STATE.user_id,
                }
                
                # #region agent log
                if agent_log_enabled():
                    import json, time
                    try:
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"L","location":"sales_tab.py:_handle_charge","message":"About to create sale","data":{"cart_size":len(self.cart),"global_discount_from_totals":self.totals.get("global_discount", 0.0),"totals":self.totals,"cart_items":[{k:v for k,v in item.items() if k in ["product_id","qty","price","base_price","discount","is_wholesale"]} for item in self.cart[:5]]},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                # #endregion
                
                try:
                    # CRITICAL FIX: Always save sale locally FIRST, then sync to server
                    # This ensures sales are never lost even if server is offline
                    # #region agent log
                    if agent_log_enabled():
                        import json, time
                        try:
                            with open(get_debug_log_path_str(), "a") as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E2E1","location":"sales_tab.py:_handle_charge","message":"E2E Flow: Calling create_sale","data":{"cart_size":len(self.cart),"payment_method":payment_dialog.result_data.get("method") if payment_dialog.result_data else None,"branch_id":STATE.branch_id,"discount":self.totals.get("global_discount", 0.0),"customer_id":self.current_customer_id},"timestamp":int(time.time()*1000)})+"\n")
                        except Exception as log_e:
                            import traceback
                            print(f"DEBUG LOG ERROR: {log_e}\n{traceback.format_exc()}")
                    # #endregion
                    
                    sale_id = self.core.create_sale(
                        self.cart,
                        payment_dialog.result_data,
                        branch_id=STATE.branch_id,
                        discount=self.totals.get("global_discount", 0.0),
                        customer_id=self.current_customer_id,
                    )

                    # CRITICAL: Validar que la venta se creó correctamente
                    if not sale_id:
                        logger.error("create_sale returned None - sale was not created")
                        QtWidgets.QMessageBox.critical(
                            self,
                            "Error Crítico",
                            "No se pudo crear la venta en la base de datos.\n\n"
                            "Por favor intente nuevamente. Si el problema persiste, contacte soporte."
                        )
                        return

                    # GIFT CARD REDEMPTION - Auditoría 2026-01-30
                    # Redimir DESPUÉS de confirmar que la venta se creó exitosamente
                    # Esto evita deducir balance si la venta falla
                    #
                    # FIX 2026-02-04: Rollback garantizado con transacción explícita
                    gift_card_info = payment_dialog.result_data.get("gift_card_info", {})
                    if gift_card_info.get("pending_redemption"):
                        from decimal import Decimal, InvalidOperation
                        gc_code = gift_card_info.get("code")
                        gc_amount = gift_card_info.get("amount_to_redeem", 0)
                        rollback_info = gift_card_info.get("rollback_info", {})

                        if gc_code and gc_amount > 0 and self.core.gift_card_engine:
                            redemption_success = False
                            try:
                                # Validar monto antes de redimir
                                try:
                                    amount_decimal = Decimal(str(gc_amount))
                                    if not amount_decimal.is_finite():
                                        raise ValueError("Invalid amount: NaN or Infinity")
                                except (InvalidOperation, ValueError) as ve:
                                    raise ValueError(f"Invalid redemption amount: {ve}")

                                # Redimir con transacción (el gift_card_engine debe manejar atomicidad)
                                new_balance = self.core.gift_card_engine.redeem(
                                    code=gc_code,
                                    amount=amount_decimal,
                                    sale_id=sale_id,
                                    user_id=STATE.user_id
                                )
                                redemption_success = True
                                logger.info(f"Gift card {gc_code} redeemed ${gc_amount:.2f} for sale #{sale_id}, new balance: ${float(new_balance):.2f}")
                            except Exception as gc_err:
                                # Venta ya creada pero redención falló
                                # Intentar rollback si tenemos la información
                                logger.error(f"Failed to redeem gift card after sale #{sale_id}: {gc_err}")

                                rollback_attempted = False
                                if rollback_info.get("can_rollback") and rollback_info.get("original_balance") is not None:
                                    try:
                                        # Restaurar balance original usando transacción
                                        original_balance = Decimal(str(rollback_info["original_balance"]))
                                        if hasattr(self.core.gift_card_engine, 'restore_balance'):
                                            self.core.gift_card_engine.restore_balance(
                                                code=gc_code,
                                                balance=original_balance,
                                                reason=f"Rollback: sale #{sale_id} redemption failed"
                                            )
                                            rollback_attempted = True
                                            logger.info(f"Gift card {gc_code} balance restored to ${float(original_balance):.2f}")
                                    except Exception as rb_err:
                                        logger.error(f"Failed to rollback gift card balance: {rb_err}")

                                error_msg = (
                                    f"La venta #{sale_id} se registró pero hubo un error\n"
                                    f"al redimir la tarjeta de regalo:\n{gc_err}\n\n"
                                )
                                if rollback_attempted:
                                    error_msg += "Se intentó restaurar el saldo de la tarjeta."
                                else:
                                    error_msg += "Por favor ajuste el saldo de la tarjeta manualmente."

                                QtWidgets.QMessageBox.warning(
                                    self,
                                    "Advertencia",
                                    error_msg
                                )

                    # #region agent log
                    if agent_log_enabled():
                        try:
                            with open(get_debug_log_path_str(), "a") as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E2E1","location":"sales_tab.py:_handle_charge","message":"E2E Flow: create_sale returned","data":{"sale_id":sale_id,"mode":self.mode,"has_network_client":bool(self.network_client)},"timestamp":int(time.time()*1000)})+"\n")
                        except Exception as e:
                             logger.debug("Writing debug log: %s", e)
                    # #endregion

                    # After saving locally, try to sync to server (non-blocking)
                    if self.mode == "client" and self.network_client:
                        try:
                            # Build sale with items: get_table_data only returns sales columns, not sale_items.
                            # Server expects sale with 'items' or 'sale_items' for INSERT sale_items.
                            current_sale = self.core.get_sale(sale_id)
                            if current_sale:
                                items = self.core.get_sale_items(sale_id) or []
                                # Server accepts 'items' or 'sale_items'; items have product_id, qty/quantity, price/unit_price, subtotal, name
                                current_sale["items"] = items
                                current_sale["sale_items"] = items
                                # #region agent log
                                if agent_log_enabled():
                                    try:
                                        with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                                            f.write(json.dumps({"sessionId": "debug-session", "runId": "post-fix", "hypothesisId": "L", "location": "sales_tab.py:sync_sale", "message": "About to sync sale", "data": {"sale_id": sale_id, "sale_keys": list(current_sale.keys()), "items_count": len(items)}, "timestamp": int(time.time() * 1000)}) + "\n")
                                    except Exception as e:
                                         logger.debug("Writing debug log: %s", e)
                                # #endregion
                                success, msg, _ = self.network_client.sync_sales([current_sale])
                                if success:
                                    self._set_offline(False)
                                    try:
                                        with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                                            f.write(json.dumps({"sessionId": "debug-session", "runId": "post-fix", "hypothesisId": "L", "location": "sales_tab.py:sync_sale", "message": "Sale synced to server", "data": {"sale_id": sale_id}, "timestamp": int(time.time() * 1000)}) + "\n")
                                    except Exception as e:
                                         logger.debug("Writing debug log: %s", e)
                                else:
                                    try:
                                        with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                                            f.write(json.dumps({"sessionId": "debug-session", "runId": "post-fix", "hypothesisId": "L", "location": "sales_tab.py:sync_sale", "message": "Sale sync failed", "data": {"sale_id": sale_id, "error": msg}, "timestamp": int(time.time() * 1000)}) + "\n")
                                    except Exception as e:
                                         logger.debug("Writing debug log: %s", e)
                                    self._set_offline(True)
                                    logger.warning(f"Failed to sync sale {sale_id} to server: {msg}")
                            else:
                                logger.warning(f"Sale {sale_id} not found for sync (get_sale returned None)")
                        except Exception as sync_error:
                            # #region agent log
                            if agent_log_enabled():
                                try:
                                    with open(Path(DATA_DIR) / "logs" / "crash_debug.log", "a") as f:
                                        f.write(json.dumps({"sessionId": "debug-session", "runId": "post-fix", "hypothesisId": "L", "location": "sales_tab.py:1681", "message": "Sale sync exception", "data": {"sale_id": sale_id, "error": str(sync_error), "error_type": type(sync_error).__name__}, "timestamp": int(time.time() * 1000)}) + "\n")
                                except Exception as e:
                                     logger.debug("Writing debug log: %s", e)
                            # #endregion
                            logger.error(f"Error syncing sale to server: {sync_error}")
                            self._set_offline(True)
                            # Sale is already saved locally, so we continue normally

                    # --- LOYALTY POINTS ACCUMULATION ---
                    # This must run ALWAYS, not just in client mode
                    if self.current_customer_id:
                            # Calculate amount eligible for points (total - wallet payment)
                            wallet_paid = 0.0
                            if method == "wallet":
                                wallet_paid = float(payment_dialog.result_data.get("amount", 0))
                            elif method == "mixed":
                                mixed_breakdown = payment_dialog.result_data.get("mixed_breakdown", {})
                                wallet_paid = float(mixed_breakdown.get("wallet", 0.0))
                            
                            # Only accumulate points on non-wallet portion
                            amount_for_points = self.totals["total"] - wallet_paid
                            
                            if amount_for_points > 0:
                                try:
                                    from decimal import Decimal

                                    # Get cashback percent from config
                                    cashback_percent = Decimal(str((self.core.get_app_config() or {}).get("cashback_percent", 1)))  # Default 1%
                                    
                                    # Format cart items for loyalty engine
                                    formatted_cart = []
                                    for item in self.cart:
                                        formatted_cart.append({
                                            'product_id': item.get('product_id'),
                                            'qty': item.get('qty', 1),
                                            'price': item.get('price', item.get('base_price', 0)),
                                            'category_id': item.get('category_id')
                                        })
                                    
                                    # CRITICAL FIX: Acumulación de puntos con retry logic (similar a audit log)
                                    # Esto previene que el cliente no reciba puntos si hay un error transitorio
                                    # DISEÑO: El retry es seguro porque:
                                    #   1. loyalty_engine usa execute_transaction() (atómico)
                                    #   2. ticket_id previene duplicados si la BD lo verifica
                                    #   3. Break inmediato en éxito
                                    # Auditoría 2026-01-30: Confirmado como diseño seguro.
                                    max_retries = 3
                                    success = False
                                    for attempt in range(max_retries):
                                        try:
                                            success = self.core.loyalty_engine.acumular_puntos(
                                                customer_id=self.current_customer_id,
                                                monto=Decimal(str(amount_for_points)),
                                                ticket_id=sale_id,
                                                turn_id=STATE.current_turn_id,
                                                user_id=STATE.user_id,
                                                carrito=formatted_cart,  # Pass formatted cart
                                                global_cashback_percent=cashback_percent  # Pass global % as fallback
                                            )
                                            if success:
                                                break  # Éxito, salir del loop de retry
                                        except Exception as e:
                                            if attempt < max_retries - 1:
                                                import time
                                                time.sleep(0.5 * (attempt + 1))  # Backoff exponencial
                                                logger.warning(f"MIDAS accumulation failed (attempt {attempt + 1}/{max_retries}), retrying: {e}")
                                            else:
                                                logger.error(f"MIDAS accumulation failed after {max_retries} attempts: {e}")
                                                # No lanzar excepción, solo registrar error (venta ya está creada)
                                    
                                    # Get actual balance after accumulation
                                    if success:
                                        new_balance = self.core.loyalty_engine.get_balance(self.current_customer_id)
                                        print(f">>> MIDAS: Accumulated points on ${amount_for_points:.2f}. New balance: ${new_balance}")
                                    else:
                                        print(f">>> MIDAS: Failed to accumulate points after {max_retries} attempts - check logs above for reason")
                                        logger.error(f"MIDAS: Failed to accumulate points for sale {sale_id}, customer {self.current_customer_id}, amount ${amount_for_points:.2f}")
                                except Exception as e:
                                    print(f">>> MIDAS ERROR: {e}")
                                    logger.error(f"MIDAS accumulation critical error: {e}")
                                    import traceback
                                    traceback.print_exc()
                            
                            # --- REDIMIR PUNTOS SI PAGÓ CON WALLET ---
                            # CRITICAL FIX: Redención de puntos con retry logic (CRÍTICO - puede causar pérdidas)
                            # Esto previene que el cliente pague con puntos pero no se descuenten
                            if wallet_paid > 0:
                                try:
                                    max_retries = 3
                                    redeem_success = False
                                    for attempt in range(max_retries):
                                        try:
                                            redeem_success = self.core.loyalty_engine.redimir_puntos(
                                                customer_id=self.current_customer_id,
                                                monto=Decimal(str(wallet_paid)),
                                                ticket_id=sale_id,
                                                turn_id=STATE.current_turn_id,
                                                user_id=STATE.user_id,
                                                descripcion=f"Pago venta #{sale_id}"
                                            )
                                            if redeem_success:
                                                break  # Éxito, salir del loop de retry
                                        except Exception as e:
                                            if attempt < max_retries - 1:
                                                import time
                                                time.sleep(0.5 * (attempt + 1))  # Backoff exponencial
                                                logger.warning(f"MIDAS redemption failed (attempt {attempt + 1}/{max_retries}), retrying: {e}")
                                            else:
                                                logger.error(f"MIDAS redemption failed after {max_retries} attempts: {e}")
                                                # CRITICAL: Mostrar advertencia al usuario si falla
                                                QtWidgets.QMessageBox.warning(
                                                    self,
                                                    "⚠️ Advertencia - Redención de Puntos",
                                                    f"La venta se completó exitosamente (#{sale_id}), pero hubo un problema al descontar los puntos del monedero.\n\n"
                                                    f"Monto pagado con puntos: ${wallet_paid:.2f}\n\n"
                                                    "Por favor, verifica manualmente el saldo del cliente y contacta a soporte si es necesario."
                                                )
                                    
                                    if redeem_success:
                                        final_balance = self.core.loyalty_engine.get_balance(self.current_customer_id)
                                        print(f">>> MIDAS: Redeemed ${wallet_paid:.2f} points. Final balance: ${final_balance}")
                                    else:
                                        print(f">>> MIDAS: Failed to redeem points after {max_retries} attempts!")
                                        logger.error(f"MIDAS: CRITICAL - Failed to redeem points for sale {sale_id}, customer {self.current_customer_id}, amount ${wallet_paid:.2f}")
                                except Exception as e:
                                    print(f">>> MIDAS REDEEM ERROR: {e}")
                                    logger.error(f"MIDAS redemption critical error: {e}")
                                    import traceback
                                    traceback.print_exc()
                    
                    # ═══════════════════════════════════════════════════════════════
                    # MONEDERO OXXO: Procesar puntos de cliente SIN asignar
                    # ═══════════════════════════════════════════════════════════════
                    monedero_data = payment_dialog.result_data.get('monedero')
                    if monedero_data and not self.current_customer_id:
                            try:
                                source = monedero_data.get('source')
                                discount = monedero_data.get('discount', 0)
                                accumulate = monedero_data.get('accumulate', False)
                                
                                print(f">>> MONEDERO OXXO: source={source}, discount={discount}, accumulate={accumulate}")
                                
                                # --- REDIMIR puntos si hay descuento ---
                                # CRITICAL FIX: Redención con retry logic
                                if discount > 0:
                                    if source == 'midas':
                                        # Redimir de cliente registrado
                                        cust_id = monedero_data.get('customer_id')
                                        if cust_id:
                                            max_retries = 3
                                            redeem_success = False
                                            for attempt in range(max_retries):
                                                try:
                                                    redeem_success = self.core.loyalty_engine.redimir_puntos(
                                                        customer_id=cust_id,
                                                        monto=Decimal(str(discount)),
                                                        ticket_id=sale_id,
                                                        turn_id=STATE.current_turn_id,
                                                        user_id=STATE.user_id,
                                                        descripcion=f"Pago venta #{sale_id} (OXXO flow)"
                                                    )
                                                    if redeem_success:
                                                        break
                                                except Exception as e:
                                                    if attempt < max_retries - 1:
                                                        import time
                                                        time.sleep(0.5 * (attempt + 1))
                                                        logger.warning(f"OXXO MIDAS redemption failed (attempt {attempt + 1}/{max_retries}), retrying: {e}")
                                                    else:
                                                        logger.error(f"OXXO MIDAS redemption failed after {max_retries} attempts: {e}")
                                            
                                            if redeem_success:
                                                print(f">>> MONEDERO OXXO: Redeemed ${discount} from MIDAS customer {cust_id}")
                                            else:
                                                logger.error(f"OXXO: Failed to redeem ${discount} from MIDAS customer {cust_id} for sale {sale_id}")
                                    elif source == 'anonymous':
                                        # Redimir de monedero anónimo
                                        wallet_id = monedero_data.get('wallet_id')
                                        if wallet_id:
                                            from app.services.anonymous_loyalty import (
                                                AnonymousLoyalty,
                                            )
                                            anon_loyalty = AnonymousLoyalty(self.core)
                                            # Convertir monto a puntos (10 puntos = $1)
                                            points_to_redeem = int(discount / anon_loyalty.PESO_PER_POINT)
                                            
                                            # CRITICAL FIX: Retry logic para redención anónima
                                            max_retries = 3
                                            redeem_success = False
                                            for attempt in range(max_retries):
                                                try:
                                                    anon_loyalty.redeem_points(wallet_id, points_to_redeem)
                                                    redeem_success = True
                                                    break
                                                except Exception as e:
                                                    if attempt < max_retries - 1:
                                                        import time
                                                        time.sleep(0.5 * (attempt + 1))
                                                        logger.warning(f"OXXO anonymous redemption failed (attempt {attempt + 1}/{max_retries}), retrying: {e}")
                                                    else:
                                                        logger.error(f"OXXO anonymous redemption failed after {max_retries} attempts: {e}")
                                            
                                            if redeem_success:
                                                print(f">>> MONEDERO OXXO: Redeemed {points_to_redeem} pts from anonymous wallet {wallet_id}")
                                            else:
                                                logger.error(f"OXXO: Failed to redeem {points_to_redeem} pts from anonymous wallet {wallet_id} for sale {sale_id}")
                                
                                # --- ACUMULAR puntos si corresponde ---
                                if accumulate:
                                    # Monto elegible = total - descuento (no acumular sobre lo pagado con puntos)
                                    amount_for_points = self.totals["total"] - discount
                                    
                                    if amount_for_points > 0:
                                        # Import Decimal locally to avoid UnboundLocalError
                                        from decimal import Decimal
                                        
                                        if source in ['midas']:
                                            # Acumular en cliente registrado
                                            cust_id = monedero_data.get('customer_id')
                                            if cust_id:
                                                cashback_percent = Decimal(str((self.core.get_app_config() or {}).get("cashback_percent", 1)))  # Default 1%
                                                
                                                # CRITICAL FIX: Retry logic para acumulación MIDAS OXXO
                                                max_retries = 3
                                                earn_success = False
                                                for attempt in range(max_retries):
                                                    try:
                                                        earn_success = self.core.loyalty_engine.acumular_puntos(
                                                            customer_id=cust_id,
                                                            monto=Decimal(str(amount_for_points)),
                                                            ticket_id=sale_id,
                                                            turn_id=STATE.current_turn_id,
                                                            user_id=STATE.user_id,
                                                            global_cashback_percent=cashback_percent
                                                        )
                                                        if earn_success:
                                                            break
                                                    except Exception as e:
                                                        if attempt < max_retries - 1:
                                                            import time
                                                            time.sleep(0.5 * (attempt + 1))
                                                            logger.warning(f"OXXO MIDAS accumulation failed (attempt {attempt + 1}/{max_retries}), retrying: {e}")
                                                        else:
                                                            logger.error(f"OXXO MIDAS accumulation failed after {max_retries} attempts: {e}")
                                                
                                                if earn_success:
                                                    print(f">>> MONEDERO OXXO: Accumulated points on ${amount_for_points} for MIDAS customer {cust_id}")
                                                else:
                                                    logger.error(f"OXXO: Failed to accumulate points on ${amount_for_points} for MIDAS customer {cust_id} for sale {sale_id}")
                                        elif source in ['anonymous', 'anonymous_new']:
                                            # Acumular en monedero anónimo
                                            wallet_id = monedero_data.get('wallet_id')
                                            if wallet_id:
                                                from app.services.anonymous_loyalty import (
                                                    AnonymousLoyalty,
                                                )
                                                anon_loyalty = AnonymousLoyalty(self.core)
                                                
                                                # CRITICAL FIX: Retry logic para acumulación anónima
                                                max_retries = 3
                                                earn_success = False
                                                for attempt in range(max_retries):
                                                    try:
                                                        anon_loyalty.earn_points(wallet_id, Decimal(str(amount_for_points)), sale_id)
                                                        earn_success = True
                                                        break
                                                    except Exception as e:
                                                        if attempt < max_retries - 1:
                                                            import time
                                                            time.sleep(0.5 * (attempt + 1))
                                                            logger.warning(f"OXXO anonymous accumulation failed (attempt {attempt + 1}/{max_retries}), retrying: {e}")
                                                        else:
                                                            logger.error(f"OXXO anonymous accumulation failed after {max_retries} attempts: {e}")
                                                
                                                if earn_success:
                                                    print(f">>> MONEDERO OXXO: Accumulated points on ${amount_for_points} for anonymous wallet {wallet_id}")
                                                else:
                                                    logger.error(f"OXXO: Failed to accumulate points on ${amount_for_points} for anonymous wallet {wallet_id} for sale {sale_id}")
                            except Exception as e:
                                print(f">>> MONEDERO OXXO ERROR: {e}")
                                import traceback
                                traceback.print_exc()
                    
                    # Sync inventory changes to server (if in client mode)
                    if self.mode == "client" and self.network_client:
                        try:
                            self.network_client.post(
                                "/api/inventory/apply_sale",
                                {"items": cart_snapshot, "branch_id": STATE.branch_id},
                            )
                        except Exception:
                            if hasattr(self.network_client, "inventory_queue"):
                                self.network_client.inventory_queue.append(
                                    {"items": cart_snapshot, "branch_id": STATE.branch_id}
                                )
                except Exception as exc:
                    error_msg = str(exc).lower()
                    # FIX 2026-01-31: Solo encolar offline si es error de RED, no de validación
                    is_network_error = any(x in error_msg for x in [
                        'connection', 'timeout', 'network', 'socket', 'refused',
                        'unreachable', 'errno', 'connectionerror', 'urlerror'
                    ])
                    is_validation_error = any(x in error_msg for x in [
                        'stock insuficiente', 'insufficient stock', 'no hay suficiente',
                        'cantidad disponible', 'disponible:', 'solicitado:'
                    ])

                    if is_validation_error:
                        # Error de validación - mostrar al usuario, NO encolar
                        QtWidgets.QMessageBox.critical(
                            self,
                            "Error de Stock",
                            f"No se pudo completar la venta:\n\n{exc}\n\nVerifica las cantidades en el carrito."
                        )
                        return

                    if self.mode == "client" and self.network_client and is_network_error:
                        self._enqueue_offline_sale(payload)
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Modo offline",
                            "Venta guardada en cola offline. Se enviará al reconectar.",
                        )
                        self._clear_after_sale()
                        return

                    QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo registrar la venta: {exc}")
                    return
                
                # Debug: Check if print_ticket will be called
                print_ticket_flag = payment_dialog.result_data.get("print_ticket", True)
                logging.info(f"DEBUG: payment_dialog.result_data = {payment_dialog.result_data}")
                logging.info(f"DEBUG: print_ticket flag = {print_ticket_flag}")
                
                # OPTIMIZADO: Solo almacenar sale_id para reimpresión
                # Los datos completos se consultan desde BD cuando se necesitan
                self.last_sale_data = {
                    'sale_id': sale_id
                }
                logging.info(f"Stored sale_id for reprint: #{sale_id}")
                
                # CRITICAL: Print ticket and open drawer in a separate thread to avoid blocking
                # This prevents the UI from freezing if printer is slow or unresponsive
                if print_ticket_flag:
                    import threading
                    def print_with_error_handling():
                        """Wrapper para manejar excepciones en thread de impresión."""
                        try:
                            self._print_sale_ticket(sale_id, cart_snapshot, payment_dialog.result_data)
                        except Exception as e:
                            logging.exception(f"Error en thread de impresión: {e}")
                            # No crashear el proceso si hay error en impresión
                    
                    print_thread = threading.Thread(
                        target=print_with_error_handling,
                        daemon=True,
                        name="Print-Ticket"
                    )
                    print_thread.start()
                else:
                    logging.warning("Print ticket skipped - flag is False")
                
                # NOTE: Loyalty points are already accumulated above (lines 1535-1553)
                # No need to accumulate again here to avoid double points
                
                # CRITICAL FIX: Save values BEFORE clearing cart
                sale_total = self.totals["total"]
                customer_name = self.current_customer_name or "Público General"
                
                self._clear_after_sale()
                
                # Emit signal to refresh other tabs (e.g., inventory)
                logger.info(f">>> Emitting sale_completed signal for sale_id={sale_id}")
                self.sale_completed.emit(sale_id)
                
                # Mostrar Cambio Grande
                change = float(payment_dialog.result_data.get('change', 0.0))
                received = float(payment_dialog.result_data.get('amount', 0.0))
                
                # UNIFIED: Use Toast for ALL payment methods
                self._play_success_sound()
                
                # Build message based on payment method
                if method == "cash" and change > 0:
                    toast_message = f"Venta #{sale_id} - Total: ${sale_total:,.2f}\n💵 Cambio: ${change:,.2f}"
                else:
                    toast_message = f"Venta #{sale_id} cobrada con {method}.\nTotal: ${sale_total:,.2f}"
                
                ToastManager.success(
                    "✅ VENTA COMPLETADA",
                    toast_message,
                    parent=self.window(),
                    duration=5000  # 5 segundos
                )
                
                # Show sale completed animation
                self._show_sale_completed_animation(sale_total, change, sale_id)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error Crítico", f"Error al procesar cobro: {str(e)}")

    def _clear_after_sale(self) -> None:
        self.cart.clear()
        self.global_discount = None
        self.clear_customer()
        self._refresh_table()
        self.sku_input.clear()
        self.sku_input.setFocus()
        # REMOVED: installEventFilter y connect duplicados
        # Estas conexiones ya se establecen en __init__ y agregar más
        # causa que add_item se llame múltiples veces por cada Enter
        # self.sku_input.installEventFilter(self)
        # self.sku_input.returnPressed.connect(self.add_item)
        self._save_current_session_to_memory()
        
        # RESET DEBOUNCE: Allow fresh start for next sale
        self._last_add_time = 0
        self._last_add_identifier = ""
        logger.info("[DEBOUNCE] Reset after sale completion - ready for new sale")

    def _delete_item(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.remove_item(row)
        else:
            if self.cart:
                self.remove_item(len(self.cart) - 1)

    def remove_item(self, index: int) -> None:
        if 0 <= index < len(self.cart):
            with self._cart_lock:  # Thread-safe
                del self.cart[index]
            self._refresh_table()
            self._save_current_session_to_memory()

    def _increase_quantity(self) -> None:
        row = self.table.currentRow()
        if row < 0 and len(self.cart) > 0:
            row = 0
            self.table.selectRow(row)
        
        if row >= 0 and row < len(self.cart):
            item = self.cart[row]
            current_qty = float(item.get("qty", 1))
            item["qty"] = current_qty + 1
            self._refresh_table()
            self.table.selectRow(row)

    def _decrease_quantity(self) -> None:
        row = self.table.currentRow()
        if row < 0 and len(self.cart) > 0:
            row = 0
            self.table.selectRow(row)
        
        if row >= 0 and row < len(self.cart):
            item = self.cart[row]
            current_qty = float(item.get("qty", 1))
            if current_qty > 1:
                item["qty"] = current_qty - 1
                self._refresh_table()
                self.table.selectRow(row)
            elif current_qty == 1:
                product_name = item.get("name", "este producto")
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Eliminar producto",
                    f"¿Quitar '{product_name}' del ticket?",
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.Yes  # Changed from No to Yes
                )
                if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                    self.remove_item(row)

    def _delete_selected_item(self) -> None:
        row = self.table.currentRow()
        if row >= 0 and row < len(self.cart):
            item = self.cart[row]
            product_name = item.get("name", "este producto")
            reply = QtWidgets.QMessageBox.question(
                self,
                "Eliminar producto",
                f"¿Quitar '{product_name}' del ticket?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.Yes  # Changed from No to Yes
            )
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                self.remove_item(row)

    def _reprint_last_ticket(self) -> None:
        """Reprint the last completed sale ticket (Page Down)"""
        # OPTIMIZADO: Solo necesitamos sale_id, consultar todo desde BD
        if not self.last_sale_data:
            QtWidgets.QMessageBox.information(
                self,
                "Reimpresión",
                "No hay ningún ticket para reimprimir.\n\n"
                "Complete una venta primero."
            )
            return
        
        sale_id = self.last_sale_data.get('sale_id')
        if not sale_id:
            QtWidgets.QMessageBox.warning(self, "Error", "No se encontró el ID de la venta.")
            return
        
        # Verificar que la venta existe en BD antes de reimprimir
        sale = self.core.get_sale(sale_id)
        if not sale:
            QtWidgets.QMessageBox.warning(
                self,
                "Venta no encontrada",
                f"La venta #{sale_id} no existe en la base de datos.\n\n"
                "Puede haber sido eliminada o cancelada."
            )
            return
        
        # Ask for confirmation
        reply = QtWidgets.QMessageBox.question(
            self,
            "Reimprimir Ticket",
            f"¿Reimprimir el ticket de la venta #{sale_id}?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            # OPTIMIZADO: Consultar siempre desde BD (ignora parámetros cart/payment_data)
            self._print_sale_ticket(sale_id)
            logging.info(f"Reprinted ticket for sale #{sale_id} (queried from DB)")

    def _cancel_last_sale(self) -> None:
        """Cancel the last completed sale - requires supervisor authorization"""
        if not self.last_sale_data:
            QtWidgets.QMessageBox.information(
                self,
                "Sin venta",
                "No hay ninguna venta para cancelar.\n\n"
                "Complete una venta primero."
            )
            return
        
        sale_id = self.last_sale_data['sale_id']
        
        # Get sale info
        sale = self.core.get_sale(sale_id)
        if not sale:
            QtWidgets.QMessageBox.warning(self, "Error", "No se encontró la venta.")
            return
        
        if sale.get("status") == "cancelled":
            QtWidgets.QMessageBox.warning(self, "Aviso", "Esta venta ya está cancelada.")
            return
        
        total = float(sale.get('total', 0))
        folio = sale.get('folio_visible', f"#{sale_id}")
        
        # Requiere autorización de supervisor
        from app.dialogs.supervisor_override_dialog import require_supervisor_override
        
        authorized, supervisor = require_supervisor_override(
            core=self.core,
            action_description=f"Cancelar Última Venta\nFolio: {folio}\nTotal: ${total:,.2f}",
            required_permission="cancel_sale",
            min_role="encargado",
            parent=self
        )
        
        if not authorized:
            return
        
        # Diálogo de cancelación
        from app.dialogs.cancel_sale_dialog import CancelSaleDialog
        dlg = CancelSaleDialog(self.core, sale_id, parent=self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # Abrir cajón después de cancelar venta
            self._open_drawer_silent()
            self.last_sale_data = None  # Clear after cancel
            QtWidgets.QMessageBox.information(
                self, 
                "Venta Cancelada", 
                f"La venta {folio} ha sido cancelada.\n\n"
                f"Autorizado por: {supervisor.get('full_name', supervisor.get('username'))}"
            )

    def _show_turn_sales(self) -> None:
        """Mostrar ventas del turno actual para poder cancelar cualquiera"""
        from app.dialogs.turn_sales_dialog import TurnSalesDialog
        dlg = TurnSalesDialog(self.core, parent=self)
        dlg.exec()

    def _print_sale_ticket(self, sale_id: Any, cart: list[dict[str, Any]] = None, payment_data: dict[str, Any] = None) -> None:
        """
        Print sale ticket using the centralized build_custom_ticket function.
        
        OPTIMIZADO: Parámetros cart y payment_data son opcionales y se ignoran.
        Siempre consulta datos actualizados desde BD para garantizar precisión.
        
        Args:
            sale_id: ID de la venta (requerido)
            cart: Ignorado - se consulta desde BD (mantenido por compatibilidad)
            payment_data: Ignorado - se consulta desde BD (mantenido por compatibilidad)
        """
        import subprocess

        from app.core import STATE
        from app.utils import ticket_engine
        
        cfg = self.core.get_app_config() or {}
        
        # OPTIMIZADO: Agregar logging y feedback cuando se omite la impresión
        if not cfg.get("auto_print_tickets"):
            logging.info(f"Ticket printing skipped for sale #{sale_id}: auto_print_tickets is disabled")
            return
        
        printer_name = cfg.get("printer_name", "")
        if not printer_name:
            logging.warning(f"Ticket printing skipped for sale #{sale_id}: No printer configured")
            return
        
        try:
            # OPTIMIZADO: Siempre consultar desde BD (ignora cart/payment_data pasados)
            # Esto garantiza que los datos estén actualizados y sean precisos
            sale_data = self.core.get_sale_details(sale_id)
            
            if not sale_data:
                logging.error(f"Could not get sale details for sale_id={sale_id}")
                return
            
            # Build ticket using centralized function (includes all fiscal features)
            ticket_content = ticket_engine.build_custom_ticket(cfg, sale_data, self.core)
            
            # ESC/POS Initialization: Reset printer to ensure clean state
            # ESC @ (0x1B 0x40) = Initialize printer
            init_sequence = b'\x1B\x40'
            # Encoding para impresora termica ESC/POS (requiere latin-1/CP437)
            full_content = init_sequence + ticket_content.encode('latin-1', errors='replace')
            
            # Print using CUPS with timeout to prevent hanging
            # Timeout de 20 segundos para impresoras lentas o ocupadas
            # Esto previene timeouts prematuros que causan retrasos
            result = subprocess.run(
                ["lp", "-d", printer_name, "-o", "raw", "-"],
                input=full_content,
                capture_output=True,
                timeout=20  # Timeout de 20 segundos
            )
            
            if result.returncode == 0:
                output = result.stdout.decode('utf-8', errors='ignore').strip()
                logging.info(f"Ticket printed successfully: {output}")
            else:
                error = result.stderr.decode('utf-8', errors='ignore')
                logging.error(f"Print error: {error}")
                
        except subprocess.TimeoutExpired:
            logging.error(f"Print timeout: Printer '{printer_name}' did not respond within 5 seconds")
        except Exception as e:
            logging.exception(f"Failed to print ticket: {e}")
        
        # Open cash drawer if enabled (después de cobrar)
        # CRITICAL: Mover a thread separado para no bloquear si la impresora está ocupada
        if cfg.get("cash_drawer_enabled"):
            pulse_str = cfg.get("cash_drawer_pulse_bytes", "\\x1B\\x70\\x00\\x19\\xFA")
            def open_drawer_async():
                try:
                    ticket_engine.open_cash_drawer(printer_name, pulse_str)
                    logging.info("💵 Cajón de dinero abierto después de cobrar")
                except Exception as e:
                    logging.exception(f"Could not open cash drawer: {e}")
            
            # Abrir cajón en thread separado para no bloquear
            drawer_thread = threading.Thread(target=open_drawer_async, daemon=True, name="CashDrawer-Open")
            drawer_thread.start()

    def _enqueue_offline_sale(self, payload: dict[str, Any]) -> None:
        if hasattr(self.network_client, "sales_queue"):
            self.network_client.sales_queue.append(payload)
        else:
            queue: list[dict[str, Any]] = []
            if self.offline_queue_file.exists():
                try:
                    queue = json.loads(self.offline_queue_file.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    queue = []
            queue.append(payload)
            self.offline_queue_file.parent.mkdir(parents=True, exist_ok=True)
            self.offline_queue_file.write_text(json.dumps(queue, indent=2), encoding="utf-8")
        self._set_offline(True)

    def sync_offline_sales(self) -> None:
        if self.mode != "client" or not self.network_client:
            return
        if hasattr(self.network_client, "flush_queue_when_online"):
            try:
                self.network_client.flush_queue_when_online()
                self._set_offline(getattr(self.network_client, "offline_mode", False))
            except Exception as e:
                logging.debug(f"Sync offline queue skipped: {e}")

    def _create_layaway_from_cart(self) -> None:
        if not self.cart:
            QtWidgets.QMessageBox.warning(self, "Sin productos", "Agrega productos antes de generar un apartado")
            return
        missing_products = [item for item in self.cart if not item.get("product_id")]
        if missing_products:
            QtWidgets.QMessageBox.warning(
                self,
                "Producto común no permitido",
                "No se pueden generar apartados con productos sin identificar (COMMON).",
            )
            return
        dialog = LayawayCreateDialog(self.cart, self.totals.get("total", 0.0), self)
        dialog.set_customer(self.current_customer_id, self.current_customer_name)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted or not dialog.result_data:
            return
        data = dialog.result_data
        deposit = float(data.get("deposit") or 0.0)
        total = float(self.totals.get("total", 0.0))
        if deposit > total:
            deposit = total
        try:
            layaway_id = self.core.create_layaway(
                self.cart,
                deposit=deposit,
                due_date=data.get("due_date"),
                customer_id=data.get("customer_id"),
                branch_id=STATE.branch_id,
                notes=data.get("notes"),
                user_id=STATE.user_id,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo crear el apartado: {exc}")
            return
        self.cart.clear()
        self.global_discount = None
        self.clear_customer()
        self._refresh_table()
        try:
            layaway = self.core.get_layaway(layaway_id)
            items = self.core.get_layaway_items(layaway_id)
            ticket_engine.print_layaway_create(dict(layaway or {}), [dict(i) for i in items])
        except Exception as e:
            logging.warning(f"No se pudo imprimir ticket de apartado: {e}")
        QtWidgets.QMessageBox.information(
            self,
            "Apartado creado",
            f"Apartado #{layaway_id} registrado correctamente. Depósito: ${deposit:,.2f}",
        )

    def _cash_in(self) -> None:
        # #region agent log
        if agent_log_enabled():
            import json, time, traceback
            try:
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CASH_IN_ENTRY","location":"sales_tab.py:_cash_in","message":"Cash in dialog opened","data":{"branch_id":STATE.branch_id,"user_id":STATE.user_id},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                 logger.debug("Writing debug log: %s", e)
        # #endregion
        
        dialog = CashMovementDialog("in", self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted and dialog.result_data:
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CASH_IN_DATA","location":"sales_tab.py:_cash_in","message":"Dialog accepted with data","data":{"result_data":dialog.result_data,"amount":dialog.result_data.get("amount"),"reason":dialog.result_data.get("reason")},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            
            try:
                # #region agent log
                if agent_log_enabled():
                    try:
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CASH_IN_BEFORE_REGISTER","location":"sales_tab.py:_cash_in","message":"Before register_cash_movement call","data":{"turn_id":None,"type":"in","amount":dialog.result_data["amount"],"reason":dialog.result_data.get("reason"),"branch_id":STATE.branch_id,"user_id":STATE.user_id},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                # #endregion
                
                self.core.register_cash_movement(
                    None,
                    "in",
                    dialog.result_data["amount"],
                    reason=dialog.result_data.get("reason"),
                    branch_id=STATE.branch_id,
                    user_id=STATE.user_id,
                )
                
                # #region agent log
                if agent_log_enabled():
                    try:
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CASH_IN_SUCCESS","location":"sales_tab.py:_cash_in","message":"Cash movement registered successfully","data":{},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                # #endregion
                
                # Abrir cajón para depositar efectivo
                self._open_drawer_silent()
                QtWidgets.QMessageBox.information(self, "Entrada registrada", "Movimiento guardado")
            except Exception as exc:
                # #region agent log
                if agent_log_enabled():
                    try:
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CASH_IN_ERROR","location":"sales_tab.py:_cash_in","message":"Error registering cash movement","data":{"error":str(exc),"error_type":type(exc).__name__,"traceback":traceback.format_exc()},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                # #endregion
                QtWidgets.QMessageBox.critical(self, "Error", str(exc))

    def _cash_out(self) -> None:
        # #region agent log
        if agent_log_enabled():
            import json, time, traceback
            try:
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CASH_OUT_ENTRY","location":"sales_tab.py:_cash_out","message":"Cash out dialog opened","data":{"branch_id":STATE.branch_id,"user_id":STATE.user_id},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                 logger.debug("Writing debug log: %s", e)
        # #endregion
        
        dialog = CashMovementDialog("out", self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted and dialog.result_data:
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CASH_OUT_DATA","location":"sales_tab.py:_cash_out","message":"Dialog accepted with data","data":{"result_data":dialog.result_data,"amount":dialog.result_data.get("amount"),"reason":dialog.result_data.get("reason")},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            
            try:
                # #region agent log
                if agent_log_enabled():
                    try:
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CASH_OUT_BEFORE_REGISTER","location":"sales_tab.py:_cash_out","message":"Before register_cash_movement call","data":{"turn_id":None,"type":"out","amount":dialog.result_data["amount"],"reason":dialog.result_data.get("reason"),"branch_id":STATE.branch_id,"user_id":STATE.user_id},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                # #endregion
                
                self.core.register_cash_movement(
                    None,
                    "out",
                    dialog.result_data["amount"],
                    reason=dialog.result_data.get("reason"),
                    branch_id=STATE.branch_id,
                    user_id=STATE.user_id,
                )
                
                # #region agent log
                if agent_log_enabled():
                    try:
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CASH_OUT_SUCCESS","location":"sales_tab.py:_cash_out","message":"Cash movement registered successfully","data":{},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                # #endregion
                
                # Abrir cajón para retirar efectivo
                self._open_drawer_silent()
                QtWidgets.QMessageBox.information(self, "Salida registrada", "Movimiento guardado")
            except Exception as exc:
                # #region agent log
                if agent_log_enabled():
                    try:
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CASH_OUT_ERROR","location":"sales_tab.py:_cash_out","message":"Error registering cash movement","data":{"error":str(exc),"error_type":type(exc).__name__,"traceback":traceback.format_exc()},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                # #endregion
                QtWidgets.QMessageBox.critical(self, "Error", str(exc))

    def _open_drawer_silent(self) -> None:
        """Abre cajón sin mostrar mensajes (uso interno)."""
        try:
            cfg = self.core.get_app_config() or {}
            if not cfg.get("cash_drawer_enabled"):
                return
            printer = cfg.get("printer_name", "")
            if not printer:
                return
            pulse = cfg.get("cash_drawer_pulse_bytes", "\\x1B\\x70\\x00\\x19\\xFA")
            ticket_engine.open_cash_drawer(printer, pulse)
        except Exception:
            pass  # Silencioso

    def _open_anonymous_wallet(self) -> None:
        """Abre el diálogo para canjear puntos del monedero anónimo."""
        try:
            from app.dialogs.anonymous_loyalty_dialog import RedeemPointsDialog
            dlg = RedeemPointsDialog(self.core, self)
            if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                # Aplicar descuento al carrito
                discount = dlg.discount_value
                if discount > 0 and self.cart:
                    # Aplicar como descuento global
                    current_discount = self.global_discount or 0
                    self.global_discount = current_discount + discount
                    self._update_totals()
                    QtWidgets.QMessageBox.information(
                        self, "Descuento Aplicado",
                        f"Se aplicó un descuento de ${discount:.2f} al carrito"
                    )
        except Exception as e:
            logger.error(f"Error en monedero anónimo: {e}")
            QtWidgets.QMessageBox.warning(self, "Error", f"Error: {e}")

    def open_cash_drawer_manual(self) -> None:
        """Abrir cajón de dinero sin hacer venta - requiere autorización"""
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CASH_DRAWER_SHORTCUT","location":"sales_tab.py:open_cash_drawer_manual","message":"Ctrl+O shortcut activated - open_cash_drawer_manual called","data":{"focus_widget":str(self.focusWidget()) if self.focusWidget() else None},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                 logger.debug("Writing debug log: %s", e)
        # #endregion
        
        # Verificar autorización si es cajero
        current_role = getattr(STATE, 'role', 'cashier').lower()
        
        if current_role == 'cashier':
            from app.dialogs.supervisor_override_dialog import require_supervisor_override
            
            authorized, supervisor = require_supervisor_override(
                core=self.core,
                action_description="Abrir cajón de dinero sin venta",
                required_permission="open_cash_drawer",
                min_role="encargado",
                parent=self
            )
            
            if not authorized:
                return
        
        # Abrir cajón
        try:
            cfg = self.core.get_ticket_config(STATE.branch_id) or {}
            printer_name = cfg.get("printer_name") or (self.core.get_app_config() or {}).get("printer_name", "")
            
            if not printer_name:
                QtWidgets.QMessageBox.warning(self, "Sin impresora", "Configure una impresora primero.")
                return
            
            if cfg.get("cash_drawer_enabled"):
                pulse_str = cfg.get("cash_drawer_pulse_bytes", "\\x1B\\x70\\x00\\x19\\xFA")
                
                from app.utils import ticket_engine

                # La función open_cash_drawer ahora acepta strings directamente
                ticket_engine.open_cash_drawer(printer_name, pulse_str)
                
                # Log de auditoría
                if hasattr(self.core, 'audit'):
                    self.core.audit.log(
                        action='MANUAL_DRAWER_OPEN',
                        entity_type='cash_drawer',
                        entity_id=0,
                        details={'user_id': STATE.user_id, 'branch_id': STATE.branch_id}
                    )
                
                QtWidgets.QMessageBox.information(self, "Cajón Abierto", "✅ El cajón de dinero se ha abierto.")
            else:
                QtWidgets.QMessageBox.warning(self, "Deshabilitado", "El cajón de dinero no está habilitado en la configuración.")
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo abrir el cajón: {e}")

    def create_layaway(self) -> None:
        """Crea un apartado desde el carrito actual"""
        if not self.cart:
            QtWidgets.QMessageBox.warning(self, "Carrito vacío", "Agrega productos antes de apartar")
            return
        
        if not self.current_customer_id:
            QtWidgets.QMessageBox.warning(self, "Cliente requerido", "Debes asignar un cliente para crear un apartado")
            return
        
        # Open Dialog
        from app.dialogs.layaway_dialog import LayawayCreateDialog
        total = self.totals.get("total", 0.0)
        dialog = LayawayCreateDialog(total, self)
        
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            data = dialog.result_data
            try:
                layaway_id = self.core.create_layaway(
                    self.current_customer_id,
                    self.cart,
                    data["initial_payment"],
                    data["due_date"],
                    data["notes"]
                )
                
                QtWidgets.QMessageBox.information(self, "Éxito", f"Apartado #{layaway_id} creado correctamente.")
                self._clear_after_sale()
                
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Error al crear apartado: {e}")

    def _open_layaways_manager(self):
        """Abre el gestor de apartados en un diálogo"""
        try:
            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle("Gestión de Apartados")
            dlg.setMinimumSize(900, 600)
            
            layout = QtWidgets.QVBoxLayout(dlg)
            
            # Instanciar ApartadosTab
            # ApartadosTab requiere core y parent_tab (opcional)
            tab = ApartadosTab(self.core, parent_tab=None)
            
            # Forzar refresh inicial
            tab.refresh_data()
            
            layout.addWidget(tab)
            
            btn_close = QtWidgets.QPushButton("Cerrar")
            btn_close.clicked.connect(dlg.accept)
            layout.addWidget(btn_close)
            
            dlg.exec()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo abrir el gestor de apartados: {e}")
            import traceback
            traceback.print_exc()

    def apply_mayoreo(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.warning(self, "Selecciona", "Selecciona una línea para alternar mayoreo")
            return
        item = self.cart[row]
        if not item.get("product_id"):
            QtWidgets.QMessageBox.warning(self, "No aplica", "El producto común no soporta precio de mayoreo")
            return
        sku = item.get("sku")
        product = self.core.get_product_by_sku_or_barcode(sku) if sku else None
        if not product:
            QtWidgets.QMessageBox.warning(self, "Producto no encontrado", "No se pudo cargar el producto seleccionado")
            return
        price_wholesale = float(product.get("price_wholesale", 0.0) or 0.0)
        if price_wholesale <= 0:
            QtWidgets.QMessageBox.information(
                self, "Sin mayoreo", "Este producto no tiene precio de mayoreo configurado."
            )
            return

        if item.get("discount", 0.0) > 0 and not item.get("is_wholesale"):
            confirm = QtWidgets.QMessageBox.question(
                self,
                "Reemplazar Descuento",
                "El producto tiene un descuento manual. ¿Desea cambiarlo por precio de mayoreo?",
            )
            if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            item["discount"] = 0.0

        item.setdefault("price_normal", float(product.get("price", 0.0)))
        
        if not item.get("is_wholesale"):
            item["is_wholesale"] = True
            item["price"] = price_wholesale
            item["base_price"] = price_wholesale
            item["discount"] = 0.0
        else:
            normal_price = float(item.get("price_normal", product.get("price", 0.0)))
            item["is_wholesale"] = False
            item["price"] = normal_price
            item["base_price"] = normal_price
            item["discount"] = 0.0
            
        self._refresh_table()

    def apply_line_discount(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.warning(self, "Selecciona", "Selecciona una línea para aplicar descuento")
            return
        item = self.cart[row]
        
        if item.get("is_wholesale"):
            confirm = QtWidgets.QMessageBox.question(
                self,
                "Reemplazar Mayoreo",
                "El producto tiene precio de mayoreo. ¿Desea quitarlo y aplicar un descuento manual?",
            )
            if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            sku = item.get("sku")
            normal_price = float(item.get("price_normal", item.get("base_price", 0.0)))
            if normal_price == 0 and sku:
                 product = self.core.get_product_by_sku_or_barcode(sku)
                 if product:
                     normal_price = float(product.get("price", 0.0))
            
            item["is_wholesale"] = False
            item["price"] = normal_price
            item["base_price"] = normal_price
            item["discount"] = 0.0

        base_price = float(item.get("base_price", item.get("price", 0.0)))
        qty = float(item.get("qty", 1))
        
        if item.get("discount", 0.0) > 0:
            confirm = QtWidgets.QMessageBox.question(
                self,
                "Reemplazar descuento",
                "Este producto ya tiene un descuento aplicado. ¿Reemplazar descuento?",
            )
            if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
                return
                
        current_unit_price = base_price
        if item.get("discount", 0.0) > 0:
            current_unit_price = max(base_price - (item.get("discount", 0.0) / max(qty, 1)), 0)
            
        dialog = DiscountDialog(base_price, current_price=current_unit_price, parent=self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted and dialog.result_data:
            result = dialog.result_data
            discount_amount_unit = float(result["discount_amount"])  # Discount per unit
            
            # Calculate total discount for the line (discount_per_unit * qty)
            # This is correct for percentage discounts (20% of $1.00 = $0.20/unit * 33 = $6.60)
            discount_total = discount_amount_unit * qty
            
            # CRITICAL: Limit discount to maximum of base_price * qty (cannot exceed line total)
            # This prevents negative prices when discount > base_price
            max_discount = base_price * qty
            if discount_total > max_discount:
                discount_total = max_discount
                # Show warning if discount was capped
                QtWidgets.QMessageBox.warning(
                    self,
                    "Descuento Limitado",
                    f"El descuento se limitó a ${max_discount:.2f} (precio base de la línea).\n"
                    f"No se puede aplicar un descuento mayor al precio total."
                )
            
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"sales_tab.py:apply_line_discount","message":"Line discount applied","data":{"product_id":item.get("product_id"),"base_price":base_price,"qty":qty,"discount_amount_unit":discount_amount_unit,"discount_total":discount_total,"max_discount":max_discount,"discount_type":result.get("type"),"discount_value":result.get("value"),"item_before":dict(item)},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            
            # Store the TOTAL discount for this line
            # CRITICAL: Normalize -0.0 to 0.0 and clamp negative discounts to 0
            # Use tolerance check for floating point comparison
            if abs(discount_total) < 1e-9:
                item["discount"] = 0.0  # Normalize -0.0 and near-zero to 0.0
            else:
                item["discount"] = max(0.0, discount_total)  # Clamp negative discounts to 0
            
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"sales_tab.py:apply_line_discount","message":"Item after discount applied","data":{"item_after":dict(item),"expected_price_after_discount":base_price - (discount_total / qty) if qty > 0 else base_price},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            
            # Refresh table to show new price
            self._refresh_table()

    def _on_item_double_clicked(self, index) -> None:
        """Handle double-click on cart item to change price directly (TITAN style)"""
        row = index.row()
        if row < 0 or row >= len(self.cart):
            return
            
        item = self.cart[row]
        
        # Get product details
        product_name = item.get("name", "Producto")
        base_price = float(item.get("base_price", item.get("price", 0.0)))
        qty = float(item.get("qty", 1))
        
        # Calculate current price (considering existing discount)
        discount = float(item.get("discount", 0.0))
        current_unit_price = base_price - (discount / max(qty, 1))
        
        # Check if wholesale - warn user
        if item.get("is_wholesale"):
            confirm = QtWidgets.QMessageBox.question(
                self,
                "Precio de Mayoreo Activo",
                "Este producto tiene precio de mayoreo. Al cambiar el precio manualmente, "
                "se desactivará el mayoreo. ¿Continuar?",
            )
            if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            # Reset wholesale
            item["is_wholesale"] = False
            # Restore normal price as base
            if item.get("price_normal"):
                base_price = float(item["price_normal"])
                item["base_price"] = base_price
                item["price"] = base_price
        
        # Open price change dialog
        from app.dialogs.price_change_dialog import PriceChangeDialog
        dialog = PriceChangeDialog(product_name, current_unit_price, base_price, qty, self)
        
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted and dialog.result_data:
            result = dialog.result_data
            new_price = float(result["new_price"])
            discount_total = float(result["discount_total"])
            
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"sales_tab.py:_on_item_double_clicked","message":"Price change dialog accepted","data":{"base_price":base_price,"new_price":new_price,"qty":qty,"discount_total":discount_total,"item_price_before":item.get("price"),"item_base_price_before":item.get("base_price"),"item_discount_before":item.get("discount")},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            
            # Calcular porcentaje de descuento
            discount_percent = ((base_price - new_price) / base_price * 100) if base_price > 0 else 0
            
            # Si el descuento es mayor al 20%, requiere autorización
            if discount_percent > 20:
                from app.core import STATE
                current_role = getattr(STATE, 'role', 'cashier').lower()
                
                if current_role == 'cashier':
                    from app.dialogs.supervisor_override_dialog import require_supervisor_override
                    
                    authorized, supervisor = require_supervisor_override(
                        core=self.core,
                        action_description=f"Aplicar descuento de {discount_percent:.1f}%\nProducto: {product_name}\nPrecio original: ${base_price:,.2f} → ${new_price:,.2f}",
                        required_permission="apply_large_discount",
                        min_role="encargado",
                        parent=self
                    )
                    
                    if not authorized:
                        return  # No autorizado
            
            # FIXED: Cuando se cambia el precio manualmente, el nuevo precio se convierte en el precio base
            # El descuento se establece en 0 porque el precio ya refleja el cambio
            # Esto evita doble descuento y asegura consistencia en tabla, BD y ticket
            # CRITICAL FIX: Always ensure discount is 0.0 when price is manually changed
            # (discount_total can be negative when new_price > base_price, but we don't store negative discounts)
            item["base_price"] = new_price  # Nuevo precio como base
            item["price"] = new_price  # Actualizar precio actual
            item["discount"] = 0.0  # Siempre 0 cuando se cambia el precio manualmente
            item["is_wholesale"] = False
            
            # #region agent log
            if agent_log_enabled():
                # Instrumentación para detectar cuando se corrige un descuento negativo
                if discount_total < 0:
                    import json, time
                    try:
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"NEGATIVE_DISCOUNT_FIX","location":"sales_tab.py:_on_item_double_clicked","message":"Negative discount_total corrected","data":{"base_price":base_price,"new_price":new_price,"discount_total":discount_total,"item_discount_after":item.get("discount"),"qty":qty},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
            # #endregion
            
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"sales_tab.py:_on_item_double_clicked","message":"Item updated after price change","data":{"item_price_after":item.get("price"),"item_base_price_after":item.get("base_price"),"item_discount_after":item.get("discount"),"expected_display_price":(base_price * qty - discount_total) / qty if qty > 0 else 0},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            
            # Refresh table to show new price and recalculated total
            self._refresh_table()
            self._save_current_session_to_memory()

    def request_close_turn(self) -> None:
        """Delegates close turn request to the main window."""
        win = self.window()
        if hasattr(win, "_close_turn"):
            win._close_turn()
        else:
            QtWidgets.QMessageBox.warning(self, "Error", "Función de cierre de turno no disponible desde aquí.")

    def apply_global_discount(self) -> None:
        if not self.cart:
            QtWidgets.QMessageBox.warning(self, "Sin productos", "Agrega productos antes de aplicar descuento")
            return
        if self.global_discount:
            confirm = QtWidgets.QMessageBox.question(
                self,
                "Reemplazar descuento",
                "Ya existe un descuento global aplicado. ¿Reemplazarlo?",
            )
            if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        # CRITICAL FIX: Usar subtotal sin IVA para calcular descuento global
        # El descuento global se calcula sobre subtotal (sin IVA) para consistencia con BD
        base_total = self._last_subtotal_before_global or self.totals.get("subtotal", 0.0)
        # Si no hay subtotal guardado, calcularlo desde totals (use tolerance for float comparison)
        if abs(base_total) < 1e-9 and self.totals.get("total", 0.0) > 1e-9:
            # Calcular subtotal aproximado desde total (total / (1 + tax_rate))
            divisor = 1 + self.tax_rate
            base_total = self.totals.get("total", 0.0) / divisor if abs(divisor) > 1e-9 else self.totals.get("total", 0.0)
        dialog = DiscountDialog(base_total, parent=self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted and dialog.result_data:
            result = dialog.result_data
            discount_value = float(result["value"])
            
            # Si el descuento es porcentaje mayor a 20% o monto mayor al 20% del total
            needs_auth = False
            if result["type"] == "percent" and discount_value > 20:
                needs_auth = True
            elif result["type"] == "amount" and base_total > 0 and (discount_value / base_total * 100) > 20:
                needs_auth = True
            
            if needs_auth:
                from app.core import STATE
                current_role = getattr(STATE, 'role', 'cashier').lower()
                
                if current_role == 'cashier':
                    from app.dialogs.supervisor_override_dialog import require_supervisor_override
                    
                    desc = f"Descuento Global de {discount_value}{'%' if result['type'] == 'percent' else '$'}\nTotal de venta: ${base_total:,.2f}"
                    
                    authorized, supervisor = require_supervisor_override(
                        core=self.core,
                        action_description=desc,
                        required_permission="apply_large_discount",
                        min_role="encargado",
                        parent=self
                    )
                    
                    if not authorized:
                        return
            
            self.global_discount = {"type": result["type"], "value": discount_value}
            
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"G","location":"sales_tab.py:apply_global_discount","message":"Global discount applied","data":{"base_total":base_total,"discount_type":result["type"],"discount_value":discount_value,"discount_amount":result.get("discount_amount"),"last_total_before_global":self._last_total_before_global,"current_totals":self.totals},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            
            self._refresh_table()
            
            # #region agent log
            if agent_log_enabled():
                try:
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"G","location":"sales_tab.py:apply_global_discount","message":"Totals after refresh","data":{"totals_after_refresh":self.totals,"global_discount":self.global_discount},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if obj is self.sku_input and event.type() == QtCore.QEvent.Type.FocusIn:
            QtCore.QTimer.singleShot(0, self.sku_input.selectAll)
        return super().eventFilter(obj, event)

    def update_theme(self) -> None:
        theme = (self.core.get_app_config() or {}).get("theme", "Light")
        c = theme_manager.get_colors(theme)
        
        # Main background
        self.setStyleSheet(f"background-color: {c['bg_main']}; color: {c['text_primary']};")
        
        # Header
        if hasattr(self, "header"):
            self.header.setStyleSheet(f"""
                QFrame {{
                    background: {c['bg_header']};
                    border-bottom: 1px solid {c['border']};
                }}
            """)
        
        if hasattr(self, "title_label"):
            self.title_label.setStyleSheet(f"color: {c['text_header']}; font-size: 20px; font-weight: 800; letter-spacing: 1px; background: transparent;")

        if hasattr(self, "content_widget"):
            self.content_widget.setStyleSheet(f"background-color: {c['bg_main']};")

        if hasattr(self, "top_card"):
            self.top_card.setStyleSheet(f"""
                QFrame {{
                    background: {c['bg_card']};
                    border: 1px solid {c['border']};
                    border-bottom: 2px solid {c['border']};
                    border-radius: 10px;
                }}
            """)

        if hasattr(self, "sku_input"):
            self.sku_input.setStyleSheet(f"""
                QLineEdit {{
                    background: {c['input_bg']};
                    border: 1px solid {c['input_border']};
                    border-radius: 8px;
                    padding: 0 15px;
                    font-size: 15px;
                    color: {c['text_primary']};
                }}
                QLineEdit:focus {{
                    background: {c['bg_card']};
                    border: 2px solid {c['input_focus']};
                }}
            """)

        if hasattr(self, "qty_input"):
            self.qty_input.setStyleSheet(f"""
                QSpinBox {{
                    background: {c['input_bg']}; border: 1px solid {c['input_border']}; border-radius: 8px;
                    font-size: 15px; padding: 0 5px; color: {c['text_primary']}; font-weight: bold;
                }}
                QSpinBox:focus {{ border: 2px solid {c['input_focus']}; background: {c['bg_card']}; }}
                QSpinBox::up-button, QSpinBox::down-button {{ width: 0px; }}
            """)

        if hasattr(self, "add_btn"):
            self.add_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {c['btn_primary']}; color: white; border: none; border-radius: 8px;
                    padding: 0 20px; font-weight: bold; font-size: 13px;
                }}
                QPushButton:hover {{ opacity: 0.9; }}
            """)

        if hasattr(self, "line_separator"):
             self.line_separator.setStyleSheet(f"color: {c['border']}; margin: 0 10px;")

        if hasattr(self, "action_buttons"):
            for btn, color in self.action_buttons:
                # Use the color key to get the actual color from the theme dict if possible, 
                # otherwise treat 'color' as a direct color string or key.
                # In _build_ui, we passed keys like 'btn_primary' or hex codes.
                # We need to resolve it.
                btn_color = c.get(color, color)
                
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {btn_color}; 
                        color: white; 
                        border: none; 
                        border-radius: 8px;
                        font-weight: bold; 
                        font-size: 13px; 
                        padding: 0 15px;
                        text-align: center;
                    }}
                    QPushButton:hover {{ 
                        opacity: 0.9; 
                    }}

                """)

        if hasattr(self, "session_tabs"):
            self.session_tabs.setStyleSheet(f"""
                QTabWidget::pane {{
                    border: 1px solid {c['border']};
                    background: {c['bg_card']};
                }}
                QTabBar::tab {{
                    background: {c['bg_card']};
                    color: {c['text_secondary']};
                    padding: 8px 16px;
                    margin-right: 2px;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    border: 1px solid {c['border']};
                }}
                QTabBar::tab:selected {{
                    background: {c['btn_primary']};
                    color: white;
                    border: none;
                }}
                QTabBar::tab:hover {{
                    background: {c.get('btn_primary_hover', c['btn_primary'])};
                }}
                QTabBar::close-button {{
                    width: 16px;
                    height: 16px;
                    margin: 2px;
                    border: none;
                    background: rgba(255, 255, 255, 0.2);
                    border-radius: 3px;
                }}
                QTabBar::close-button:hover {{
                    background: rgba(255, 100, 100, 0.8);
                }}
            """)

        if hasattr(self, "new_ticket_btn"):
            self.new_ticket_btn.setStyleSheet(f"""
                QPushButton {{ 
                    background: {c['btn_success']}; 
                    color: white; 
                    border-radius: 8px; 
                    font-weight: bold; 
                    border: none; 
                    font-size: 16px;
                }}
                QPushButton:hover {{ opacity: 0.9; }}
            """)

        if hasattr(self, "client_box"):
            self.client_box.setStyleSheet("background: transparent; border: none;")

        if hasattr(self, "customer_label"):
            self.customer_label.setStyleSheet(f"font-weight: bold; color: {c['text_primary']}; border: none; font-size: 14px;")

        if hasattr(self, "change_client_btn"):
            self.change_client_btn.setStyleSheet(f"""
                QPushButton {{ 
                    background: {c['bg_card']}; 
                    color: {c['btn_primary']}; 
                    border: 1px solid {c['btn_primary']}; 
                    border-radius: 6px; 
                    padding: 5px 12px; 
                    font-weight: bold; 
                    font-size: 12px; 
                }}
                QPushButton:hover {{ background: {c['btn_primary']}; color: white; }}
            """)

        if hasattr(self, "clear_customer_btn"):
            self.clear_customer_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; 
                    color: {c['btn_danger']}; 
                    font-weight: bold; 
                    border: none;
                    font-size: 14px;
                }}
                QPushButton:hover {{ color: #ff5252; }}
            """)

        if hasattr(self, "table"):
            self.table.setStyleSheet(f"""
                QTableWidget {{
                    background: {c['bg_card']}; 
                    border: 1px solid {c['border']}; 
                    border-radius: 8px;
                    gridline-color: {c['border']};
                    font-size: 14px; 
                    selection-background-color: {c['table_selected']}; 
                    selection-color: {c['text_primary']};
                }}
                QHeaderView::section {{
                    background: {c['table_header_bg']}; 
                    color: {c['table_header_text']};
                    padding: 12px; 
                    border: none; 
                    font-weight: bold; 
                    font-size: 13px;
                    border-bottom: 2px solid {c['border']};
                }}
                QTableWidget::item {{ padding: 12px; border-bottom: 1px solid {c['border']}; }}
            """)
            # Refresh table to update row colors if needed
            self._refresh_table()

        if hasattr(self, "footer"):
            self.footer.setStyleSheet(f"""
                QFrame {{
                    background: {c['bg_card']}; 
                    border-top: 2px solid {c['border']};
                    border-bottom-left-radius: 10px; 
                    border-bottom-right-radius: 10px;
                }}
            """)

        if hasattr(self, "total_lbl"):
            self.total_lbl.setStyleSheet(f"font-size: 42px; font-weight: 900; color: {c['text_primary']}; border: none;")

        if hasattr(self, "charge_btn"):
            self.charge_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {c['btn_success']}; 
                    color: white; 
                    border: none; 
                    border-radius: 10px;
                    font-size: 20px; 
                    font-weight: 800; 
                    padding: 0 40px;
                }}
                QPushButton:hover {{ opacity: 0.9; }}
            """)

        if hasattr(self, "pending_btn"):
             self.pending_btn.setStyleSheet(f"""
                QPushButton {{ 
                    background: {c['input_bg']}; 
                    color: {c['text_primary']}; 
                    border: 1px solid {c['border']}; 
                    border-radius: 8px; 
                    padding: 10px 15px; 
                    font-weight: 600; 
                }}
                QPushButton:hover {{ background: {c['border']}; }}
            """)
             # Agregar atajo visible si no lo tiene
             if "F6" not in self.pending_btn.text():
                 self.pending_btn.setText("💾 Pendientes [F6]")
        
        if hasattr(self, "discount_btn"):
             self.discount_btn.setStyleSheet(f"""
                QPushButton {{ 
                    background: {c['input_bg']}; 
                    color: #FFA502; 
                    border: 1px solid {c['border']}; 
                    border-radius: 8px; 
                    padding: 10px 15px; 
                    font-weight: 600; 
                }}
                QPushButton:hover {{ background: {c['border']}; color: #FFB732; }}
            """)
             if "Ctrl+D" not in self.discount_btn.text():
                 self.discount_btn.setText("🏷 Descuento [Ctrl+D]")
        
        # === LAYAWAY BUTTON - Mismo estilo que los demás ===
        if hasattr(self, "layaway_btn"):
             self.layaway_btn.setStyleSheet(f"""
                QPushButton {{ 
                    background: {c['input_bg']}; 
                    color: #9b59b6; 
                    border: 1px solid {c['border']}; 
                    border-radius: 8px; 
                    padding: 10px 15px; 
                    font-weight: 600; 
                }}
                QPushButton:hover {{ background: {c['border']}; color: #a569bd; }}
            """)
             # Remover el setFixedSize para que sea consistente
             self.layaway_btn.setMinimumHeight(40)
             self.layaway_btn.setMaximumHeight(50)
        
        if hasattr(self, "manage_layaways_btn"):
             self.manage_layaways_btn.setStyleSheet(f"""
                QPushButton {{ 
                    background: {c['input_bg']}; 
                    color: {c['text_secondary']}; 
                    border: 1px solid {c['border']}; 
                    border-radius: 8px; 
                    padding: 10px 15px; 
                    font-weight: 600; 
                }}
                QPushButton:hover {{ background: {c['border']}; }}
            """)
        
        if hasattr(self, "cash_in_btn"):
             self.cash_in_btn.setStyleSheet(f"""
                QPushButton {{ 
                    background: {c['input_bg']}; 
                    color: {c['btn_success']}; 
                    border: 1px solid {c['border']}; 
                    border-radius: 8px; 
                    padding: 10px 15px; 
                    font-weight: 600; 
                }}
                QPushButton:hover {{ background: {c['border']}; }}
            """)
             if "F7" not in self.cash_in_btn.text():
                 self.cash_in_btn.setText("💵 Entrada [F7]")
        
        if hasattr(self, "cash_out_btn"):
             self.cash_out_btn.setStyleSheet(f"""
                QPushButton {{ 
                    background: {c['input_bg']}; 
                    color: {c['btn_danger']}; 
                    border: 1px solid {c['border']}; 
                    border-radius: 8px; 
                    padding: 10px 15px; 
                    font-weight: 600; 
                }}
                QPushButton:hover {{ background: {c['border']}; }}
            """)
             if "F8" not in self.cash_out_btn.text():
                 self.cash_out_btn.setText("💸 Salida [F8]")

    def _manage_pending_tickets(self) -> None:
        """Open pending tickets dialog to save current ticket or load a saved one."""
        from app.dialogs.pending_tickets_dialog import PendingTicketsDialog, save_pending_ticket

        # If current cart has items, ask if user wants to save it first
        if self.cart:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Guardar Ticket Actual",
                f"¿Guardar el ticket actual antes de abrir tickets pendientes?\n\n"
                f"Items: {len(self.cart)}\n"
                f"Total: ${self.totals.get('total', 0.0):.2f}",
                QtWidgets.QMessageBox.StandardButton.Yes | 
                QtWidgets.QMessageBox.StandardButton.No |
                QtWidgets.QMessageBox.StandardButton.Cancel
            )
            
            if reply == QtWidgets.QMessageBox.StandardButton.Cancel:
                return
            elif reply == QtWidgets.QMessageBox.StandardButton.Yes:
                # Save current ticket
                ticket_id = save_pending_ticket(
                    self.cart,
                    self.current_customer_id,
                    self.current_customer_name,
                    self.global_discount,
                    self.totals
                )
                if ticket_id:
                    QtWidgets.QMessageBox.information(
                        self,
                        "Ticket Guardado",
                        f"Ticket guardado correctamente.\n\nID: {ticket_id[:8]}..."
                    )
                    self._clear_cart()
                else:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Error",
                        "No se pudo guardar el ticket."
                    )
                    return
        
        # Open pending tickets dialog
        dialog = PendingTicketsDialog(self)
        dialog.ticket_loaded.connect(self._load_pending_ticket)
        dialog.exec()
    
    def _load_pending_ticket(self, ticket_data: dict) -> None:
        """Load a pending ticket into the current cart."""
        # Clear current cart first
        if self.cart:
            self._clear_cart()
        
        # Load ticket data
        self.cart = ticket_data.get('cart', [])
        self.current_customer_id = ticket_data.get('customer_id')
        self.current_customer_name = ticket_data.get('customer_name')
        self.global_discount = ticket_data.get('global_discount')
        
        # Refresh UI
        self._refresh_table()
        self._update_customer_badge()
        
        QtWidgets.QMessageBox.information(
            self,
            "Ticket Cargado",
            f"Ticket cargado correctamente.\n\n"
            f"Cliente: {self.current_customer_name or 'Público General'}\n"
            f"Items: {len(self.cart)}"
        )

        # Force style update
        self.style().unpolish(self)
        self.style().polish(self)
    
    def cancel_current_operation(self) -> None:
        """Cancel current operation and clear inputs (ESC key handler)."""
        # Clear SKU input
        if self.sku_input.hasFocus() or self.sku_input.text():
            self.sku_input.clear()
            self.sku_input.setFocus()
            return
        
        # Clear quantity input and reset to 1
        if self.qty_input.value() != 1:
            self.qty_input.setValue(1)
            return
        
        # If cart has items, ask to clear cart
        if self.cart:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Cancelar Venta",
                "¿Deseas cancelar la venta actual y limpiar el carrito?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                self._clear_cart()
                QtWidgets.QMessageBox.information(
                    self,
                    "Venta Cancelada",
                    "El carrito se ha limpiado correctamente."
                )

        self.update()

    # ------------------------------------------------------------------
    # TIER B: Tab Navigation & Visual Indicators
    # ------------------------------------------------------------------
    
    def _cycle_next_ticket(self) -> None:
        """Cycle to next ticket with Tab key."""
        if self.session_tabs.count() <= 1:
            return
        current = self.session_tabs.currentIndex()
        next_idx = (current + 1) % self.session_tabs.count()
        self.session_tabs.setCurrentIndex(next_idx)
        self._update_active_ticket_indicator()
    
    def _cycle_prev_ticket(self) -> None:
        """Cycle to previous ticket with Shift+Tab."""
        if self.session_tabs.count() <= 1:
            return
        current = self.session_tabs.currentIndex()
        prev_idx = (current - 1) % self.session_tabs.count()
        self.session_tabs.setCurrentIndex(prev_idx)
        self._update_active_ticket_indicator()
    
    def _update_active_ticket_indicator(self) -> None:
        """Update visual indicator for active ticket."""
        theme = theme_manager.get_theme()
        active_color = theme.get('accent', '#3498db')
        inactive_color = theme.get('btn_secondary', '#95a5a6')
        
        for i in range(self.session_tabs.count()):
            if i == self.session_tabs.currentIndex():
                # Active ticket - bold text with badge
                badge = "●"
                self.session_tabs.setTabText(i, f"{badge} Venta {i+1}")
                # Apply style to tab bar (limited styling available)
                tab_bar = self.session_tabs.tabBar()
                if tab_bar:
                    tab_bar.setTabTextColor(i, QtGui.QColor(active_color))
            else:
                # Inactive ticket
                self.session_tabs.setTabText(i, f"  Venta {i+1}")
                tab_bar = self.session_tabs.tabBar()
                if tab_bar:
                    tab_bar.setTabTextColor(i, QtGui.QColor(inactive_color))
    
    def _quick_turn_close(self) -> None:
        """F10: Quick turn close with minimal dialog."""
        from app.dialogs.quick_turn_close import QuickTurnCloseDialog
        
        if not hasattr(self, 'core') or not self.core:
            QtWidgets.QMessageBox.warning(self, "Error", "No hay conexión con el sistema")
            return
            
        dialog = QuickTurnCloseDialog(self.core, parent=self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # Turn closed successfully
            try:
                from app.utils.sound_manager import sound_manager
                if sound_manager:
                    sound_manager.play_success()
            except Exception:
                pass  # Sonido es opcional, no crítico
            QtWidgets.QMessageBox.information(
                self,
                "Turno Cerrado",
                "El turno se cerró exitosamente"
            )

    # ------------------------------------------------------------------
    # TIER C: Sound Integration
    # ------------------------------------------------------------------
    
    def _play_add_sound(self) -> None:
        """Play sound when item added to cart."""
        try:
            from app.utils.sound_manager import sound_manager
            if sound_manager:
                sound_manager.play_beep()
        except Exception:
            pass  # Sonido opcional
    
    def _play_success_sound(self) -> None:
        """Play sound when sale completed."""
        try:
            from app.utils.sound_manager import sound_manager
            if sound_manager:
                sound_manager.play_success()
        except Exception:
            pass  # Sound is optional
    
    def _play_error_sound(self) -> None:
        """Play sound on error."""
        try:
            from app.utils.sound_manager import sound_manager
            if sound_manager:
                sound_manager.play_error()
        except Exception:
            pass  # Sonido opcional
    
    def _flash_error(self) -> None:
        """Flash screen effect when error occurs (product not found)."""
        # Get theme colors
        theme = (self.core.get_app_config() or {}).get("theme", "Light")
        c = theme_manager.get_colors(theme)
        
        # Flash the SKU input field with red background
        original_style = self.sku_input.styleSheet()
        flash_count = 0
        max_flashes = 6  # 3 complete cycles
        
        def toggle_flash():
            nonlocal flash_count
            if flash_count >= max_flashes:
                self.sku_input.setStyleSheet(original_style)
                return
            
            # Alternate between red and normal
            if flash_count % 2 == 0:
                # Use btn_danger color from theme, fallback to red if not available
                danger_color = c.get('btn_danger', '#e74c3c')
                self.sku_input.setStyleSheet(f"background-color: {danger_color}; color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
            else:
                self.sku_input.setStyleSheet(original_style)
            
            flash_count += 1
            QtCore.QTimer.singleShot(150, toggle_flash)  # Flash every 150ms
        
        toggle_flash()
    
    def closeEvent(self, event):
        """Stop timers before widget destruction to prevent crashes."""
        if hasattr(self, 'scan_timer') and self.scan_timer:
            self.scan_timer.stop()
        if hasattr(self, '_refresh_timer') and self._refresh_timer:
            self._refresh_timer.stop()
        super().closeEvent(event)

    def showEvent(self, event):
        """Aplicar tema cuando se muestra el tab."""
        super().showEvent(event)
        if hasattr(self, 'update_theme'):
            self.update_theme()