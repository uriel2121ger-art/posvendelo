# TODO [REFACTOR]: Este archivo tiene ~3400 lineas. Considerar dividir en:
# - settings_general.py: Configuracion general de la tienda
# - settings_fiscal.py: Configuracion fiscal y facturacion
# - settings_printers.py: Configuracion de impresoras
# - settings_users.py: Gestion de usuarios y permisos
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
import secrets

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger(__name__)

from app.core import DATA_DIR, STATE, POSCore

# Get project root directory dynamically for debug logging
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
_DEBUG_LOG_PATH = _PROJECT_ROOT / '.cursor' / 'debug.log'

def log_debug(location: str, message: str, data: dict = None, hypothesis_id: str = "A") -> None:
    """Log debug information to debug.log file."""
    try:
        _DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        log_entry = {
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000)
        }
        with open(_DEBUG_LOG_PATH, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
            f.flush()
    except Exception:
        pass  # Don't fail if logging fails
from app.utils.network_client import NetworkClient
from app.utils.path_utils import get_debug_log_path_str, get_debug_log_path, agent_log_enabled
from app.utils.theme_manager import theme_manager

# Optional imports - modules may not exist
try:
    from app.dialogs.backup_settings_test_dialog import BackupSettingsTestDialog
except ImportError:
    BackupSettingsTestDialog = None

try:
    from app.dialogs.backup_restore_dialog import BackupRestoreDialog
except ImportError:
    BackupRestoreDialog = None
from app.dialogs.printer_wizard import PrinterWizardDialog
from app.dialogs.ticket_config_dialog import TicketConfigDialog
from app.dialogs.user_dialog import UserDialog
from app.utils import ticket_engine


class LoyaltyRuleDialog(QtWidgets.QDialog):
    """Dialog for creating/editing loyalty rules"""
    
    def __init__(self, parent=None, rule_data=None):
        super().__init__(parent)
        self.rule_data = rule_data
        self.setWindowTitle("Editar Regla" if rule_data else "Nueva Regla de Lealtad")
        self.setMinimumWidth(450)
        self._build_ui()
        
        if rule_data:
            self._load_data(rule_data)
    
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Form
        form = QtWidgets.QFormLayout()
        form.setSpacing(10)
        
        # Rule ID
        self.rule_id = QtWidgets.QLineEdit()
        self.rule_id.setPlaceholderText("ej: BONUS_WEEKENDS")
        if self.rule_data:
            self.rule_id.setEnabled(False)  # Can't edit ID
        form.addRow("ID de Regla:", self.rule_id)
        
        # Display Name
        self.nombre = QtWidgets.QLineEdit()
        self.nombre.setPlaceholderText("ej: 10% Extra en Fines de Semana")
        form.addRow("Nombre:", self.nombre)
        
        # Condition Type
        self.condicion_tipo = QtWidgets.QComboBox()
        self.condicion_tipo.addItems([
            "SIEMPRE",           # Always active
            "DIA_SEMANA",        # Specific day of week
            "HORA_RANGO",        # Time range
            "CLIENTE_NIVEL",     # Customer tier
            "MONTO_MINIMO",      # Minimum amount
            "PRODUCTO_CATEGORIA", # Product category
            "PRIMERA_COMPRA"     # First purchase
        ])
        form.addRow("Tipo de Condición:", self.condicion_tipo)
        
        # Condition Value
        self.condicion_valor = QtWidgets.QLineEdit()
        self.condicion_valor.setPlaceholderText('ej: "5,6" para sábado/domingo')
        form.addRow("Valor Condición:", self.condicion_valor)
        
        # Help text for condition
        help_label = QtWidgets.QLabel(
            "💡 Valores: SIEMPRE=vacío, DIA_SEMANA=0-6 (Lun-Dom), "
            "HORA_RANGO='09:00-18:00', MONTO_MINIMO=500"
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #666; font-size: 10px;")
        form.addRow("", help_label)
        
        # Multiplier (percentage)
        mult_layout = QtWidgets.QHBoxLayout()
        self.multiplicador = QtWidgets.QDoubleSpinBox()
        self.multiplicador.setRange(0.01, 100)
        self.multiplicador.setValue(1.0)
        self.multiplicador.setSuffix(" %")
        self.multiplicador.setDecimals(2)
        mult_layout.addWidget(self.multiplicador)
        mult_layout.addWidget(QtWidgets.QLabel("(% del monto que se convierte en puntos)"))
        mult_layout.addStretch()
        form.addRow("Multiplicador:", mult_layout)
        
        # Priority
        self.prioridad = QtWidgets.QSpinBox()
        self.prioridad.setRange(0, 100)
        self.prioridad.setValue(10)
        form.addRow("Prioridad:", self.prioridad)
        
        layout.addLayout(form)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QtWidgets.QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QtWidgets.QPushButton("💾 Guardar")
        save_btn.setStyleSheet("background: #27ae60; color: white; font-weight: bold; padding: 8px 20px;")
        save_btn.clicked.connect(self._validate_and_accept)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_data(self, data):
        self.rule_id.setText(data.get('regla_id', ''))
        self.nombre.setText(data.get('nombre_display', ''))
        
        idx = self.condicion_tipo.findText(data.get('condicion_tipo', 'SIEMPRE'))
        if idx >= 0:
            self.condicion_tipo.setCurrentIndex(idx)
        
        self.condicion_valor.setText(data.get('condicion_valor', ''))
        self.multiplicador.setValue(float(data.get('multiplicador', 0.01)) * 100)
        self.prioridad.setValue(int(data.get('prioridad', 10)))
    
    def _validate_and_accept(self):
        if not self.rule_id.text().strip():
            QtWidgets.QMessageBox.warning(self, "Campo requerido", "Ingrese un ID de regla")
            return
        if not self.nombre.text().strip():
            QtWidgets.QMessageBox.warning(self, "Campo requerido", "Ingrese un nombre para la regla")
            return
        self.accept()
    
    def get_data(self):
        return {
            'regla_id': self.rule_id.text().strip().upper().replace(' ', '_'),
            'nombre_display': self.nombre.text().strip(),
            'condicion_tipo': self.condicion_tipo.currentText(),
            'condicion_valor': self.condicion_valor.text().strip(),
            'multiplicador': self.multiplicador.value() / 100,  # Convert % to decimal
            'prioridad': self.prioridad.value()
        }

class SettingsTab(QtWidgets.QWidget):
    """
    Modern settings tab with sidebar navigation (TITAN style).
    """

    def __init__(self, core: POSCore, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.core = core
        self.cfg = self.core.get_app_config() or {}
        self.fiscal_cfg = self.core.get_fiscal_config()
        self.load_assets()
        # #region agent log
        if agent_log_enabled():
            try:
                import json
                with open(get_debug_log_path_str(), "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "sessionId": "e2e-test",
                        "runId": "run1",
                        "hypothesisId": "SETTINGS_TAB_INIT",
                        "location": "app/ui/settings_tab.py:__init__",
                        "message": "SettingsTab initialized",
                        "data": {},
                        "timestamp": int(__import__("time").time() * 1000)
                    }) + "\n")
            except Exception as e:
                logger.debug("Writing debug log for settings tab init: %s", e)
        # #endregion
        self._init_ui()

    def load_assets(self):
        self.icons = {}
        try:
            self.icons["general"] = QtGui.QIcon("assets/icon_products.png")
            self.icons["devices"] = QtGui.QIcon("assets/icon_print.png")
            self.icons["fiscal"] = QtGui.QIcon("assets/icon_excel.png")
            self.icons["backup"] = QtGui.QIcon("assets/icon_shifts.png")
            self.icons["network"] = QtGui.QIcon("assets/icon_search.png")
            self.icons["users"] = QtGui.QIcon("assets/icon_clients.png")
        except Exception as e:
            pass  # Icons are optional, fail silently

    def _init_ui(self) -> None:
        self.setObjectName("SettingsTab")
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Sidebar (Left) ---
        self.sidebar = QtWidgets.QListWidget()
        self.sidebar.setFixedWidth(260)
        self.sidebar.currentRowChanged.connect(self._change_page)

        # --- Content Area (Right) ---
        self.pages = QtWidgets.QStackedWidget()

        self._add_category("General", "general", self._create_general_page())
        self._add_category("Usuarios", "users", self._create_users_page())
        self._add_category("Permisos", "users", self._create_permissions_page())  # NEW
        self._add_category("MIDAS Loyalty", "general", self._create_midas_page())  # NEW: Comprehensive loyalty settings
        self._add_category("Dispositivos", "devices", self._create_devices_page())
        self._add_category("Facturación", "fiscal", self._create_fiscal_page())
        self._add_category("Respaldos", "backup", self._create_backups_page())
        self._add_category("Red y API", "network", self._create_network_page())
        self._add_category("Multi-Sucursal", "network", self._create_multibranch_page())  # NEW: Multi-branch config

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.pages)

        # Apply theme
        self.update_theme()

        # Select first item
        self.sidebar.setCurrentRow(0)

    def _add_category(self, name: str, icon_key: str, widget: QtWidgets.QWidget) -> None:
        item = QtWidgets.QListWidgetItem(f" {name}")
        if icon_key in self.icons:
            item.setIcon(self.icons[icon_key])
        
        self.sidebar.addItem(item)
        
        # Wrap widget in a scroll area for safety
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        # Only make the scroll area itself transparent, not all widgets inside
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        
        # Container for centering/margins
        container = QtWidgets.QWidget()
        container.setObjectName("SettingsContainer")
        container_layout = QtWidgets.QVBoxLayout(container)
        container_layout.setContentsMargins(30, 30, 30, 30)
        container_layout.addWidget(widget)
        container_layout.addStretch()
        
        # Ensure container is transparent so it shows the main background
        container.setStyleSheet("QWidget#SettingsContainer { background: transparent; }")
        
        scroll.setWidget(container)
        self.pages.addWidget(scroll)

    def _change_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)

    # ------------------------------------------------------------------
    # Page Builders
    # ------------------------------------------------------------------

    def _create_general_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Get theme colors first - needed by multiple sections
        cfg = self.core.get_app_config() or {}
        theme = cfg.get("theme", "Light")
        c = theme_manager.get_colors(theme)

        layout.addWidget(self._header("Configuración General"))

        # Mode selection (Standalone, Server, Client)
        gb_mode = QtWidgets.QGroupBox("🔧 Modo de Operación")
        form_mode = QtWidgets.QFormLayout(gb_mode)
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["standalone", "server", "client"])
        current_mode = self.cfg.get("mode", "standalone")
        self.mode_combo.setCurrentText(current_mode)
        form_mode.addRow("Modo:", self.mode_combo)

        # Server Connection (only for client mode)
        self.server_ip = QtWidgets.QLineEdit(self.cfg.get("server_ip", ""))
        self.server_ip.setPlaceholderText("192.168.1.100")
        self.server_port = QtWidgets.QSpinBox()
        self.server_port.setRange(1, 65535)
        self.server_port.setValue(int(self.cfg.get("server_port", 8000)))
        self.sync_interval = QtWidgets.QSpinBox()
        self.sync_interval.setRange(10, 300)
        self.sync_interval.setValue(int(self.cfg.get("sync_interval_seconds", 30)))
        self.sync_interval.setSuffix(" seg")

        form_mode.addRow("IP Servidor:", self.server_ip)
        form_mode.addRow("Puerto:", self.server_port)
        form_mode.addRow("Intervalo Sync:", self.sync_interval)

        layout.addWidget(gb_mode)

        # Theme selection
        gb_theme = QtWidgets.QGroupBox("🎨 Tema Visual")
        form_theme = QtWidgets.QFormLayout(gb_theme)
        self.theme_combo = QtWidgets.QComboBox()
        self.theme_combo.addItems(["Dark", "Gray", "AMOLED", "Light"])
        self.theme_combo.setCurrentText(self.cfg.get("theme", "Dark"))
        form_theme.addRow("Tema:", self.theme_combo)

        self.apply_theme_btn = QtWidgets.QPushButton("Aplicar Tema Ahora")
        self.apply_theme_btn.clicked.connect(self._apply_theme)
        form_theme.addRow("", self.apply_theme_btn)
        layout.addWidget(gb_theme)

        # Wallet
        gb_wallet = QtWidgets.QGroupBox("💰 Monedero Electrónico (MIDAS)")
        gb_wallet.setToolTip("Configuración del sistema de lealtad y cashback")
        form_wallet = QtWidgets.QFormLayout(gb_wallet)
        self.cashback_percent = QtWidgets.QDoubleSpinBox()
        self.cashback_percent.setRange(0.0, 100.0)
        self.cashback_percent.setSuffix("%")
        self.cashback_percent.setValue(float(self.cfg.get("cashback_percent", 0.0)))
        self.cashback_percent.setToolTip(
            "Cashback global cuando NO hay reglas activas.\n"
            "Si activas reglas abajo, se usarán esas en vez de este porcentaje."
        )
        form_wallet.addRow("Cashback Global (Fallback):", self.cashback_percent)
        
        # Quick toggles for default rules
        self.rule_base_1pct = QtWidgets.QCheckBox("Regla: 1% en todas las compras")
        self.rule_base_1pct.setToolTip("Acumula 1% de puntos en cada venta, todos los días")
        
        self.rule_weekend_10pct = QtWidgets.QCheckBox("Regla: 10% extra en fines de semana")
        self.rule_weekend_10pct.setToolTip("Acumula 10% de puntos en ventas de sábado y domingo")
        
        # Load current rule states from database
        try:
            if not self.core.db:
                logger.warning("Database not available")
                return
            # Rule 1: 1% base
            result = self.core.db.execute_query(
                "SELECT activo FROM loyalty_rules WHERE nombre_display = '1% Base en Todas las Compras'"
            )
            # CRITICAL FIX: Handle empty results properly
            if result and isinstance(result, (list, tuple)) and len(result) > 0:
                row = result[0]
                if isinstance(row, dict):
                    activo = row.get('activo', 0)
                elif isinstance(row, (list, tuple)) and len(row) > 0:
                    activo = row[0]
                else:
                    activo = 0
                self.rule_base_1pct.setChecked(bool(activo))
            else:
                # Regla no existe, desactivar checkbox
                self.rule_base_1pct.setChecked(False)
            
            # Rule 2: 10% weekend
            result = self.core.db.execute_query(
                "SELECT activo FROM loyalty_rules WHERE nombre_display = '10% Extra en Fines de Semana'"
            )
            # CRITICAL FIX: Handle empty results properly
            if result and isinstance(result, (list, tuple)) and len(result) > 0:
                row = result[0]
                if isinstance(row, dict):
                    activo = row.get('activo', 0)
                elif isinstance(row, (list, tuple)) and len(row) > 0:
                    activo = row[0]
                else:
                    activo = 0
                self.rule_weekend_10pct.setChecked(bool(activo))
            else:
                # Regla no existe, desactivar checkbox
                self.rule_weekend_10pct.setChecked(False)
        except Exception as e:
            logger.warning(f"Error loading loyalty rules: {e}")
            # FIX 2026-02-01: Agregado logging para excepción interna en lugar de silenciarla
            # En caso de error, desactivar ambos checkboxes
            try:
                self.rule_base_1pct.setChecked(False)
                self.rule_weekend_10pct.setChecked(False)
            except Exception as checkbox_error:
                logger.error(f"Error resetting loyalty checkboxes: {checkbox_error}")
        
        form_wallet.addRow("", self.rule_base_1pct)
        form_wallet.addRow("", self.rule_weekend_10pct)
        
        # Info label
        rules_info = QtWidgets.QLabel(
            "💡 Tip: Las reglas tienen prioridad sobre el cashback global.\n"
            "Para gestión avanzada, ve a Configuración → MIDAS Loyalty"
        )
        rules_info.setWordWrap(True)
        rules_info.setStyleSheet(f"color: {c['text_secondary']}; font-size: 11px; padding: 5px;")
        form_wallet.addRow("", rules_info)
        
        layout.addWidget(gb_wallet)

        layout.addStretch()
        layout.addWidget(self._save_btn())
        return page

    def _create_users_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        layout.addWidget(self._header("Gestión de Usuarios"))

        # User Info
        cfg = self.core.get_app_config() or {}
        theme = cfg.get("theme", "Light")
        c = theme_manager.get_colors(theme)
        
        self.user_info_lbl = QtWidgets.QLabel(f"Usuario actual: {STATE.username} (Rol: {STATE.role})")
        self.user_info_lbl.setStyleSheet(f"color: {c['text_secondary']}; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(self.user_info_lbl)

        # Toolbar
        toolbar = QtWidgets.QHBoxLayout()
        self.btn_add_user = QtWidgets.QPushButton("Nuevo Usuario")
        self.btn_add_user.clicked.connect(self._add_user)
        self.btn_edit_user = QtWidgets.QPushButton("Editar")
        self.btn_edit_user.clicked.connect(self._edit_user)
        self.btn_del_user = QtWidgets.QPushButton("Eliminar")
        self.btn_del_user.clicked.connect(self._delete_user)
        
        # Check permissions (visual only - logic is in handlers)
        is_admin = STATE.role in ["admin", "manager", "encargado"]
        
        # We enable buttons so users can click and see why they can't perform the action
        self.btn_add_user.setEnabled(True)
        self.btn_edit_user.setEnabled(True)
        self.btn_del_user.setEnabled(True)
        
        if not is_admin:
            self.btn_add_user.setToolTip("Solo administradores pueden gestionar usuarios")
            self.btn_edit_user.setToolTip("Solo administradores pueden gestionar usuarios")
            self.btn_del_user.setToolTip("Solo administradores pueden gestionar usuarios")

        # Style buttons
        for btn in [self.btn_add_user, self.btn_edit_user]:
            btn.setStyleSheet(f"background-color: {c['btn_primary']}; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold;")
            if not is_admin:
                 # Visual cue that it's restricted, even if clickable
                 btn.setStyleSheet(f"background-color: {c['text_secondary']}; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold;")
                 
        self.btn_del_user.setStyleSheet(f"background-color: {c['btn_danger']}; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold;")
        if not is_admin:
             self.btn_del_user.setStyleSheet(f"background-color: {c['text_secondary']}; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold;")

        toolbar.addWidget(self.btn_add_user)
        toolbar.addWidget(self.btn_edit_user)
        toolbar.addWidget(self.btn_del_user)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Table
        self.users_table = QtWidgets.QTableWidget()
        self.users_table.setColumnCount(5)
        self.users_table.setHorizontalHeaderLabels(["ID", "Usuario", "Nombre", "Rol", "Estado"])
        self.users_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.users_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.users_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.users_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # Style table
        self.users_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {c['bg_card']};
                color: {c['text_primary']};
                gridline-color: {c['border']};
                border: 1px solid {c['border']};
            }}
            QHeaderView::section {{
                background-color: {c['bg_header']};
                color: {c['text_header']};
                padding: 5px;
                border: 1px solid {c['border']};
            }}
            QTableWidget::item {{
                padding: 5px;
            }}
            QTableWidget::item:selected {{
                background-color: {c['btn_primary']};
                color: white;
            }}
        """)
        
        layout.addWidget(self.users_table)
        
        self._load_users()
        
        return page

    def showEvent(self, event):
        """Update user info when tab is shown"""
        super().showEvent(event)
        # Aplicar tema cuando se muestra el tab
        if hasattr(self, 'update_theme'):
            self.update_theme()
        # Only update text, don't recreate widgets
        if hasattr(self, 'user_info_lbl'):
            try:
                self.user_info_lbl.setText(f"Usuario actual: {STATE.username} (Rol: {STATE.role})")
            except (RuntimeError, AttributeError):
                pass  # Widget deleted or doesn't exist

    def _load_users(self):
        self.users_table.setRowCount(0)
        users = self.core.list_users()
        self.users_table.setRowCount(len(users))
        for i, u in enumerate(users):
            self.users_table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(u["id"])))
            self.users_table.setItem(i, 1, QtWidgets.QTableWidgetItem(u["username"]))
            self.users_table.setItem(i, 2, QtWidgets.QTableWidgetItem(u["name"] or ""))
            self.users_table.setItem(i, 3, QtWidgets.QTableWidgetItem(u["role"]))
            status = "Activo" if u["is_active"] else "Inactivo"
            self.users_table.setItem(i, 4, QtWidgets.QTableWidgetItem(status))

    def _check_permission(self):
        if STATE.role not in ["admin", "manager", "encargado"]:
            QtWidgets.QMessageBox.warning(self, "Acceso Denegado", "No tienes permisos para realizar esta acción.\nContacta al administrador.")
            return False
        return True

    def _add_user(self):
        if not self._check_permission():
            return
        logging.getLogger(__name__).info("DEBUG: _add_user clicked")
        try:
            dlg = UserDialog(self.core, parent=self)
            if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                self._load_users()
        except Exception as e:
            logging.getLogger(__name__).error(f"Error opening UserDialog: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al abrir diálogo: {e}")

    def _edit_user(self):
        if not self._check_permission():
            return
        logging.getLogger(__name__).info("DEBUG: _edit_user clicked")
        row = self.users_table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.warning(self, "Selección", "Selecciona un usuario")
            return
        user_id = int(self.users_table.item(row, 0).text())
        try:
            dlg = UserDialog(self.core, user_id=user_id, parent=self)
            if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                self._load_users()
        except Exception as e:
            logging.getLogger(__name__).error(f"Error opening UserDialog: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al abrir diálogo: {e}")

    def _delete_user(self):
        if not self._check_permission():
            return
        logging.getLogger(__name__).info("DEBUG: _delete_user clicked")
        row = self.users_table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.warning(self, "Selección", "Selecciona un usuario")
            return
        user_id = int(self.users_table.item(row, 0).text())
        username = self.users_table.item(row, 1).text()
        
        if username == "admin":
            QtWidgets.QMessageBox.warning(self, "Error", "No se puede eliminar al administrador principal")
            return

        if QtWidgets.QMessageBox.question(self, "Confirmar", f"¿Eliminar usuario {username}?") == QtWidgets.QMessageBox.StandardButton.Yes:
            self.core.delete_user(user_id)
            self._load_users()

    def _create_devices_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        cfg = self.core.get_app_config() or {}
        theme = cfg.get("theme", "Light")
        c = theme_manager.get_colors(theme)

        layout.addWidget(self._header("Dispositivos y Hardware"))

        # Printer
        gb_print = QtWidgets.QGroupBox("🖨️ Impresora de Tickets")
        gb_print.setToolTip("Configuración de la impresora térmica para tickets de venta")
        form_print = QtWidgets.QFormLayout(gb_print)
        self.printer_name = QtWidgets.QComboBox()
        self.printer_name.setEditable(True)  # Allow manual entry if needed
        self.printer_name.setToolTip("Selecciona la impresora o escribe el nombre manualmente")
        self._refresh_printer_list()
        
        # Set saved printer if available
        saved_printer = self.cfg.get("printer_name", "")
        if saved_printer:
            idx = self.printer_name.findText(saved_printer)
            if idx >= 0:
                self.printer_name.setCurrentIndex(idx)
            else:
                self.printer_name.setCurrentText(saved_printer)
        
        # Refresh button
        self.refresh_printers_btn = QtWidgets.QPushButton("🔄")
        self.refresh_printers_btn.setMaximumWidth(40)
        self.refresh_printers_btn.setToolTip("Actualizar lista de impresoras")
        self.refresh_printers_btn.clicked.connect(self._refresh_printer_list)
        self.paper_width = QtWidgets.QComboBox()
        self.paper_width.addItems(["58mm", "80mm"])
        self.paper_width.setCurrentText(self.cfg.get("ticket_paper_width", "80mm"))
        self.paper_width.setToolTip("Ancho del papel térmico (58mm = compacto, 80mm = estándar)")
        self.auto_print = QtWidgets.QCheckBox("Imprimir ticket automáticamente al cobrar")
        self.auto_print.setChecked(bool(self.cfg.get("auto_print_tickets", False)))
        self.auto_print.setToolTip("Si está activado, se imprime automáticamente al completar una venta")
        self.test_print_btn = QtWidgets.QPushButton("Probar Impresión")
        self.test_print_btn.clicked.connect(self._test_print)
        
        self.wizard_btn = QtWidgets.QPushButton("🧙 Asistente de Configuración")
        self.wizard_btn.setIcon(QtGui.QIcon("assets/icon_settings.png")) # Use generic icon if available or just text
        self.wizard_btn.clicked.connect(self._launch_printer_wizard)
        self.wizard_btn.setStyleSheet(f"background-color: {c['btn_success']}; color: white; font-weight: bold; padding: 8px;")
        self.wizard_btn.setToolTip("Abre el asistente paso a paso para configurar la impresora fácilmente")
        
        self.ticket_config_btn = QtWidgets.QPushButton("🎨 Diseñar Ticket")
        self.ticket_config_btn.setIcon(QtGui.QIcon("assets/icon_edit.png"))
        self.ticket_config_btn.clicked.connect(self._launch_ticket_config)
        self.ticket_config_btn.setStyleSheet(f"background-color: {c['btn_primary']}; color: white; font-weight: bold; padding: 8px;")
        self.ticket_config_btn.setToolTip("Personaliza el diseño y contenido de los tickets impresos")

        printer_row = QtWidgets.QHBoxLayout()
        printer_row.addWidget(self.printer_name, 1)
        printer_row.addWidget(self.refresh_printers_btn)
        form_print.addRow("Impresora:", printer_row)
        form_print.addRow("Ancho Papel:", self.paper_width)
        form_print.addRow("", self.auto_print)
        
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self.wizard_btn)
        btn_layout.addWidget(self.ticket_config_btn)
        form_print.addRow("", btn_layout)
        
        form_print.addRow("", self.test_print_btn)
        layout.addWidget(gb_print)

        # Cash Drawer
        gb_drawer = QtWidgets.QGroupBox("💵 Cajón de Dinero")
        gb_drawer.setToolTip("Configuración del cajón de efectivo conectado a la impresora")
        form_drawer = QtWidgets.QFormLayout(gb_drawer)
        self.drawer_enabled = QtWidgets.QCheckBox("Abrir cajón automáticamente al cobrar")
        self.drawer_enabled.setChecked(bool(self.cfg.get("cash_drawer_enabled", False)))
        self.drawer_enabled.setToolTip("Si está activado, el cajón se abre automáticamente al completar una venta")
        
        # Preset selector
        self.drawer_preset = QtWidgets.QComboBox()
        self.drawer_preset.addItem("EPSON/Compatible (Pin 2) - Estándar", "\\x1B\\x70\\x00\\x19\\xFA")
        self.drawer_preset.addItem("EPSON/Compatible (Pin 5)", "\\x1B\\x70\\x01\\x19\\xFA")
        self.drawer_preset.addItem("STAR Micronics (Legacy)", "\\x1B\\x07")
        self.drawer_preset.addItem("Genérico DLE DC4", "\\x10\\x14\\x01\\x00\\x05")
        self.drawer_preset.addItem("Pulso Largo (100ms)", "\\x1B\\x70\\x00\\x32\\xFA")
        self.drawer_preset.addItem("Pulso Corto (30ms)", "\\x1B\\x70\\x00\\x0F\\x50")
        self.drawer_preset.addItem("Personalizado...", "custom")
        self.drawer_preset.setToolTip(
            "Selecciona el tipo de comando según tu impresora/cajón.\n"
            "La mayoría funciona con EPSON/Compatible Pin 2."
        )
        self.drawer_preset.currentIndexChanged.connect(self._on_drawer_preset_changed)
        
        # Sequence text (for custom)
        self.drawer_sequence = QtWidgets.QLineEdit(self.cfg.get("cash_drawer_pulse_bytes", "\\x1B\\x70\\x00\\x19\\xFA"))
        self.drawer_sequence.setToolTip(
            "Secuencia de bytes hexadecimal que se envía a la impresora.\n"
            "Formato: \\x1B\\x70\\x00\\x19\\xFA\n\n"
            "COMANDOS COMUNES:\n"
            "EPSON Pin 2: \\x1B\\x70\\x00\\x19\\xFA\n"
            "EPSON Pin 5: \\x1B\\x70\\x01\\x19\\xFA\n"
            "STAR: \\x1B\\x07\n"
            "Genérico: \\x10\\x14\\x01\\x00\\x05"
        )
        
        # Set current preset based on saved value
        saved_seq = self.cfg.get("cash_drawer_pulse_bytes", "\\x1B\\x70\\x00\\x19\\xFA")
        preset_found = False
        for i in range(self.drawer_preset.count() - 1):  # Exclude "Personalizado"
            if self.drawer_preset.itemData(i) == saved_seq:
                self.drawer_preset.setCurrentIndex(i)
                preset_found = True
                break
        if not preset_found:
            self.drawer_preset.setCurrentIndex(self.drawer_preset.count() - 1)  # Custom
        
        self.test_drawer_btn = QtWidgets.QPushButton("🔓 Probar Apertura")
        self.test_drawer_btn.clicked.connect(self._test_drawer)
        self.test_drawer_btn.setToolTip("Envía el comando para abrir el cajón y probar la conexión")
        
        # Help label
        drawer_help = QtWidgets.QLabel(
            "💡 El cajón se conecta al puerto RJ-11/RJ-12 (DK) de la impresora.\n"
            "Si no funciona, prueba otros presets o contacta al fabricante."
        )
        drawer_help.setWordWrap(True)
        drawer_help.setStyleSheet(f"color: {c['text_secondary']}; font-size: 10px; padding: 5px;")
        
        form_drawer.addRow("", self.drawer_enabled)
        form_drawer.addRow("Tipo de Comando:", self.drawer_preset)
        seq_label = QtWidgets.QLabel("Secuencia (Hex):")
        seq_label.setToolTip("Comando hexadecimal para apertura del cajón")
        form_drawer.addRow(seq_label, self.drawer_sequence)
        form_drawer.addRow("", self.test_drawer_btn)
        form_drawer.addRow("", drawer_help)
        layout.addWidget(gb_drawer)

        # Scanners
        gb_scan = QtWidgets.QGroupBox("📷 Lectores de Código de Barras")
        gb_scan.setToolTip("Configuración de lectores de códigos de barras y QR")
        form_scan = QtWidgets.QFormLayout(gb_scan)
        self.prefix_input = QtWidgets.QLineEdit(self.cfg.get("scanner_prefix", ""))
        self.prefix_input.setPlaceholderText("Ej: >>>")
        self.prefix_input.setToolTip("Caracteres que el escáner envía antes del código (opcional)")
        self.suffix_input = QtWidgets.QLineEdit(self.cfg.get("scanner_suffix", ""))
        self.suffix_input.setPlaceholderText("Ej: ENTER")
        self.suffix_input.setToolTip("Caracteres que el escáner envía después del código (opcional)")
        self.camera_enabled = QtWidgets.QCheckBox("Usar Cámara Web como Escáner")
        self.camera_enabled.setChecked(bool(self.cfg.get("camera_scanner_enabled", False)))
        self.camera_enabled.setToolTip("Permite usar la cámara del equipo para leer códigos QR/barras")
        self.camera_index = QtWidgets.QSpinBox()
        self.camera_index.setRange(0, 10)
        self.camera_index.setValue(int(self.cfg.get("camera_scanner_index", 0)))
        self.camera_index.setToolTip("Índice de la cámara a usar (0 = cámara principal, 1 = secundaria, etc.)")
        
        prefix_label = QtWidgets.QLabel("Prefijo (Opcional):")
        prefix_label.setToolTip("Caracteres iniciales del escáner")
        form_scan.addRow(prefix_label, self.prefix_input)
        suffix_label = QtWidgets.QLabel("Sufijo (Opcional):")
        suffix_label.setToolTip("Caracteres finales del escáner")
        form_scan.addRow(suffix_label, self.suffix_input)
        form_scan.addRow("", self.camera_enabled)
        camera_label = QtWidgets.QLabel("Índice Cámara:")
        camera_label.setToolTip("Número de cámara del sistema")
        form_scan.addRow(camera_label, self.camera_index)
        layout.addWidget(gb_scan)

        layout.addStretch()
        layout.addWidget(self._save_btn())
        return page

    def _create_fiscal_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        layout.addWidget(self._header("📋 Facturación Electrónica (CFDI 4.0)"))

        gb_fiscal = QtWidgets.QGroupBox("🏢 Datos del Emisor")
        gb_fiscal.setToolTip("Información fiscal de tu empresa para generar facturas electrónicas")
        form = QtWidgets.QFormLayout(gb_fiscal)
        
        self.rfc_emisor = QtWidgets.QLineEdit(self.fiscal_cfg.get("rfc_emisor", ""))
        self.rfc_emisor.setPlaceholderText("XAXX010101000")
        self.rfc_emisor.setToolTip("RFC de 12 o 13 caracteres asignado por el SAT")
        self.razon_emisor = QtWidgets.QLineEdit(self.fiscal_cfg.get("razon_social_emisor", ""))
        self.razon_emisor.setToolTip("Razón social registrada ante el SAT")
        self.regimen_emisor = QtWidgets.QLineEdit(self.fiscal_cfg.get("regimen_fiscal", ""))
        self.regimen_emisor.setPlaceholderText("Ej: 601, 612, 625")
        self.regimen_emisor.setToolTip("Clave del régimen fiscal (601=General, 612=Persona Física, 625=Resico, etc.)")
        self.lugar_expedicion = QtWidgets.QLineEdit(self.fiscal_cfg.get("lugar_expedicion", ""))
        self.lugar_expedicion.setPlaceholderText("12345")
        self.lugar_expedicion.setToolTip("Código postal del domicilio fiscal")
        
        form.addRow("RFC:", self.rfc_emisor)
        form.addRow("Razón Social:", self.razon_emisor)
        form.addRow("Régimen Fiscal:", self.regimen_emisor)
        form.addRow("C.P. Expedición:", self.lugar_expedicion)
        layout.addWidget(gb_fiscal)

        gb_csd = QtWidgets.QGroupBox("🔐 Certificados (CSD)")
        gb_csd.setToolTip("Certificados de Sello Digital otorgados por el SAT")
        form_csd = QtWidgets.QFormLayout(gb_csd)
        
        # Certificate file (.cer) with browse button
        self.csd_cert = QtWidgets.QLineEdit(self.fiscal_cfg.get("csd_cert_path", ""))
        self.csd_cert.setPlaceholderText("/ruta/al/certificado.cer")
        self.csd_cert.setToolTip("Ruta completa al archivo .cer del SAT")
        
        cert_layout = QtWidgets.QHBoxLayout()
        cert_layout.addWidget(self.csd_cert)
        btn_browse_cert = QtWidgets.QPushButton("📁 Buscar")
        btn_browse_cert.setMaximumWidth(100)
        btn_browse_cert.clicked.connect(lambda: self._browse_cert_file('cer'))
        btn_browse_cert.setToolTip("Seleccionar archivo .cer del SAT")
        cert_layout.addWidget(btn_browse_cert)
        
        # Private key file (.key) with browse button
        self.csd_key = QtWidgets.QLineEdit(self.fiscal_cfg.get("csd_key_path", ""))
        self.csd_key.setPlaceholderText("/ruta/a/llave.key")
        self.csd_key.setToolTip("Ruta completa al archivo .key del SAT")
        
        key_layout = QtWidgets.QHBoxLayout()
        key_layout.addWidget(self.csd_key)
        btn_browse_key = QtWidgets.QPushButton("📁 Buscar")
        btn_browse_key.setMaximumWidth(100)
        btn_browse_key.clicked.connect(lambda: self._browse_cert_file('key'))
        btn_browse_key.setToolTip("Seleccionar archivo .key del SAT")
        key_layout.addWidget(btn_browse_key)
        
        # Password
        self.csd_pass = QtWidgets.QLineEdit(self.fiscal_cfg.get("csd_key_password", ""))
        self.csd_pass.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.csd_pass.setToolTip("Contraseña privada de la llave .key")
        
        form_csd.addRow("Archivo .cer:", cert_layout)
        form_csd.addRow("Archivo .key:", key_layout)
        form_csd.addRow("Contraseña:", self.csd_pass)
        layout.addWidget(gb_csd)

        gb_pac = QtWidgets.QGroupBox("Proveedor (PAC)")
        form_pac = QtWidgets.QFormLayout(gb_pac)
        self.pac_url = QtWidgets.QLineEdit(self.fiscal_cfg.get("pac_base_url", ""))
        self.pac_user = QtWidgets.QLineEdit(self.fiscal_cfg.get("pac_user", ""))
        self.pac_pass = QtWidgets.QLineEdit(self.fiscal_cfg.get("pac_password", ""))
        self.pac_pass.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.serie_factura = QtWidgets.QLineEdit(self.fiscal_cfg.get("serie_factura", "F"))
        self.folio_actual = QtWidgets.QSpinBox()
        self.folio_actual.setMaximum(9999999)
        self.folio_actual.setValue(int(self.fiscal_cfg.get("folio_actual", 1)))
        
        form_pac.addRow("URL Servicio:", self.pac_url)
        form_pac.addRow("Usuario:", self.pac_user)
        form_pac.addRow("Contraseña:", self.pac_pass)
        form_pac.addRow("Serie Facturas:", self.serie_factura)
        form_pac.addRow("Folio Actual:", self.folio_actual)
        
        self.test_fiscal_btn = QtWidgets.QPushButton("Verificar Configuración Fiscal")
        self.test_fiscal_btn.clicked.connect(self._test_fiscal)
        layout.addWidget(gb_pac)
        layout.addWidget(self.test_fiscal_btn)
        
        # Facturapi Integration
        gb_facturapi = QtWidgets.QGroupBox("🚀 Facturapi (Recomendado)")
        gb_facturapi.setToolTip("API de facturación simplificada - No requiere CSD ni PAC externo")
        form_facturapi = QtWidgets.QFormLayout(gb_facturapi)
        
        self.facturapi_enabled = QtWidgets.QCheckBox("Usar Facturapi para facturación")
        self.facturapi_enabled.setChecked(bool(self.fiscal_cfg.get("facturapi_enabled", True)))
        self.facturapi_enabled.setToolTip("Habilita Facturapi como proveedor de timbrado (más simple que configurar CSD)")
        
        self.facturapi_key = QtWidgets.QLineEdit(self.fiscal_cfg.get("facturapi_api_key", ""))
        self.facturapi_key.setPlaceholderText("sk_test_xxxxxxxxxxxx o sk_live_xxxxxxxxxxxx")
        self.facturapi_key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.facturapi_key.setToolTip(
            "API Key de Facturapi.\n"
            "• sk_test_xxx = Modo pruebas (facturas no válidas ante SAT)\n"
            "• sk_live_xxx = Modo producción (facturas reales)"
        )
        
        # Show/hide password button
        show_key_btn = QtWidgets.QPushButton("👁")
        show_key_btn.setMaximumWidth(40)
        show_key_btn.setCheckable(True)
        show_key_btn.toggled.connect(
            lambda checked: self.facturapi_key.setEchoMode(
                QtWidgets.QLineEdit.EchoMode.Normal if checked else QtWidgets.QLineEdit.EchoMode.Password
            )
        )
        
        key_layout = QtWidgets.QHBoxLayout()
        key_layout.addWidget(self.facturapi_key)
        key_layout.addWidget(show_key_btn)
        
        self.facturapi_mode = QtWidgets.QLabel("")
        self._update_facturapi_mode()
        self.facturapi_key.textChanged.connect(self._update_facturapi_mode)
        
        self.test_facturapi_btn = QtWidgets.QPushButton("🔗 Probar Conexión Facturapi")
        self.test_facturapi_btn.clicked.connect(self._test_facturapi)
        
        info_label = QtWidgets.QLabel(
            "💡 Facturapi simplifica la facturación: no necesitas configurar CSD ni PAC.\n"
            "   Obtén tu API Key en: https://dashboard.facturapi.io"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #7f8c8d; font-size: 10px;")
        
        form_facturapi.addRow("", self.facturapi_enabled)
        form_facturapi.addRow("API Key:", key_layout)
        form_facturapi.addRow("Modo:", self.facturapi_mode)
        form_facturapi.addRow("", self.test_facturapi_btn)
        form_facturapi.addRow("", info_label)
        layout.addWidget(gb_facturapi)
        
        # Store reference for toggling
        self.gb_pac = gb_pac
        self.gb_csd = gb_csd
        self.gb_facturapi = gb_facturapi
        
        # Connect toggle - when Facturapi enabled, dim PAC section
        self.facturapi_enabled.toggled.connect(self._toggle_pac_section)
        self._toggle_pac_section(self.facturapi_enabled.isChecked())
        
        # Global Invoice Dashboard button
        self.global_invoice_btn = QtWidgets.QPushButton("📊 Dashboard Facturación Global")
        self.global_invoice_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.global_invoice_btn.setToolTip("Genera CFDIs globales para ventas en efectivo sin facturar")
        self.global_invoice_btn.clicked.connect(self._open_global_invoice_dashboard)
        layout.addWidget(self.global_invoice_btn)

        layout.addStretch()
        layout.addWidget(self._save_btn())
        return page

    def _create_backups_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        layout.addWidget(self._header("💾 Respaldos y Seguridad"))

        # Local
        gb_local = QtWidgets.QGroupBox("💻 Respaldo Local")
        gb_local.setToolTip("Configuración de respaldos en el disco local")
        form_local = QtWidgets.QFormLayout(gb_local)
        self.backup_auto = QtWidgets.QCheckBox("Crear respaldo automáticamente al cerrar turno")
        self.backup_auto.setChecked(bool(self.cfg.get("backup_auto_on_close", False)))
        self.backup_auto.setToolTip("Genera una copia de seguridad automática cada vez que cierras el turno")
        self.backup_dir = QtWidgets.QLineEdit(self.cfg.get("backup_dir", str(Path(DATA_DIR) / "backups")))
        self.backup_dir.setToolTip("Ruta donde se guardarán los archivos de respaldo")
        
        # Buttons
        self.restore_btn = QtWidgets.QPushButton("📥 Restaurar Respaldo Anterior...")
        self.restore_btn.clicked.connect(self._open_restore)
        self.restore_btn.setToolTip("Abre el asistente para restaurar un respaldo previo")
        
        self.backup_now_btn = QtWidgets.QPushButton("💾 Crear Respaldo Ahora")
        self.backup_now_btn.clicked.connect(self._create_backup_now)
        self.backup_now_btn.setToolTip("Crea un respaldo manual inmediatamente")
        self.backup_now_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 10px;")
        
        self.advanced_tools_btn = QtWidgets.QPushButton("🛡️ Herramientas Avanzadas")
        self.advanced_tools_btn.clicked.connect(self._open_advanced_tools)
        self.advanced_tools_btn.setToolTip("Modo Auditor, Contingencia, Redes...")
        self.advanced_tools_btn.setStyleSheet("background-color: #9b59b6; color: white; font-weight: bold; padding: 10px;")
        
        form_local.addRow("", self.backup_auto)
        backup_dir_label = QtWidgets.QLabel("Carpeta:")
        backup_dir_label.setToolTip("Ubicación de los respaldos locales")
        form_local.addRow(backup_dir_label, self.backup_dir)
        form_local.addRow("", self.backup_now_btn)
        form_local.addRow("", self.restore_btn)
        form_local.addRow("", self.advanced_tools_btn)
        layout.addWidget(gb_local)

        # Encryption
        gb_enc = QtWidgets.QGroupBox("Cifrado")
        form_enc = QtWidgets.QFormLayout(gb_enc)
        self.backup_encrypt = QtWidgets.QCheckBox("Cifrar respaldos (AES-256)")
        self.backup_encrypt.setChecked(bool(self.cfg.get("backup_encrypt", False)))
        self.backup_key = QtWidgets.QLineEdit(self.cfg.get("backup_encrypt_key", ""))
        self.backup_key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.backup_key.setPlaceholderText("Clave secreta para desencriptar")
        
        form_enc.addRow("", self.backup_encrypt)
        form_enc.addRow("Clave:", self.backup_key)
        layout.addWidget(gb_enc)

        # Cloud / NAS
        gb_cloud = QtWidgets.QGroupBox("Nube y NAS")
        form_cloud = QtWidgets.QFormLayout(gb_cloud)
        
        self.backup_nas_enabled = QtWidgets.QCheckBox("Copiar a NAS / Red")
        self.backup_nas_enabled.setChecked(bool(self.cfg.get("backup_nas_enabled", False)))
        self.backup_nas_path = QtWidgets.QLineEdit(self.cfg.get("backup_nas_path", ""))
        self.test_nas_btn = QtWidgets.QPushButton("Probar NAS")
        self.test_nas_btn.clicked.connect(self._test_nas)
        
        # Google Drive
        self.backup_gdrive_enabled = QtWidgets.QCheckBox("Subir a Google Drive (rclone)")
        self.backup_gdrive_enabled.setChecked(bool(self.cfg.get("backup_gdrive_enabled", False)))
        
        # OneDrive
        self.backup_onedrive_enabled = QtWidgets.QCheckBox("Subir a OneDrive (rclone)")
        self.backup_onedrive_enabled.setChecked(bool(self.cfg.get("backup_onedrive_enabled", False)))
        
        # S3
        self.backup_cloud_enabled = QtWidgets.QCheckBox("Subir a S3 (AWS/MinIO)")
        self.backup_cloud_enabled.setChecked(bool(self.cfg.get("backup_cloud_enabled", False)))
        self.s3_endpoint = QtWidgets.QLineEdit(self.cfg.get("backup_s3_endpoint", ""))
        self.s3_bucket = QtWidgets.QLineEdit(self.cfg.get("backup_s3_bucket", ""))
        self.s3_access = QtWidgets.QLineEdit(self.cfg.get("backup_s3_access_key", ""))
        self.s3_secret = QtWidgets.QLineEdit(self.cfg.get("backup_s3_secret_key", ""))
        self.s3_secret.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.s3_prefix = QtWidgets.QLineEdit(self.cfg.get("backup_s3_prefix", ""))
        self.test_s3_btn = QtWidgets.QPushButton("Probar S3")
        self.test_s3_btn.clicked.connect(self._test_s3)

        form_cloud.addRow("", self.backup_nas_enabled)
        form_cloud.addRow("Ruta NAS:", self.backup_nas_path)
        form_cloud.addRow("", self.test_nas_btn)
        
        form_cloud.addRow(QtWidgets.QLabel("--- Google Drive ---"))
        form_cloud.addRow("", self.backup_gdrive_enabled)
        
        form_cloud.addRow(QtWidgets.QLabel("--- OneDrive ---"))
        form_cloud.addRow("", self.backup_onedrive_enabled)
        
        form_cloud.addRow(QtWidgets.QLabel("--- S3 ---"))
        form_cloud.addRow("", self.backup_cloud_enabled)
        form_cloud.addRow("Endpoint:", self.s3_endpoint)
        form_cloud.addRow("Bucket:", self.s3_bucket)
        form_cloud.addRow("Access Key:", self.s3_access)
        form_cloud.addRow("Secret Key:", self.s3_secret)
        form_cloud.addRow("Prefijo:", self.s3_prefix)
        form_cloud.addRow("", self.test_s3_btn)
        
        layout.addWidget(gb_cloud)

        # Retention
        gb_ret = QtWidgets.QGroupBox("Mantenimiento")
        form_ret = QtWidgets.QFormLayout(gb_ret)
        self.retention_enabled = QtWidgets.QCheckBox("Eliminar respaldos antiguos")
        self.retention_enabled.setChecked(bool(self.cfg.get("backup_retention_enabled", False)))
        self.retention_days = QtWidgets.QSpinBox()
        self.retention_days.setRange(1, 3650)
        self.retention_days.setValue(int(self.cfg.get("backup_retention_days", 30)))
        form_ret.addRow("", self.retention_enabled)
        form_ret.addRow("Días a conservar:", self.retention_days)
        layout.addWidget(gb_ret)

        layout.addStretch()
        layout.addWidget(self._save_btn())
        return page

    def _create_network_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        layout.addWidget(self._header("🌐 Red y Conectividad"))

        # MultiCaja
        gb_net = QtWidgets.QGroupBox("🔗 Conexión MultiCaja")
        gb_net.setToolTip("Configuración para múltiples cajas sincronizadas en red")
        form_net = QtWidgets.QFormLayout(gb_net)
        
        self.server_ip = QtWidgets.QLineEdit(self.cfg.get("server_ip", "127.0.0.1"))
        self.server_ip.setPlaceholderText("192.168.1.100")
        self.server_ip.setToolTip("Dirección IP del servidor maestro (solo para modo cliente)")
        
        self.server_port = QtWidgets.QSpinBox()
        self.server_port.setRange(1, 65535)
        self.server_port.setValue(int(self.cfg.get("server_port", 8000)))
        self.server_port.setToolTip("Puerto TCP del servidor (por defecto 8000)")
        
        self.sync_interval = QtWidgets.QSpinBox()
        self.sync_interval.setRange(5, 3600)
        self.sync_interval.setSuffix(" seg")
        self.sync_interval.setValue(int(self.cfg.get("sync_interval_seconds", 10)))
        self.sync_interval.setToolTip("Frecuencia de sincronización automática entre cajas")
        
        # Connection test button
        self.test_conn_btn = QtWidgets.QPushButton("🔌 Probar Conexión con Servidor")
        self.test_conn_btn.clicked.connect(self._test_connection)
        self.test_conn_btn.setToolTip("Verifica la conectividad con el servidor maestro")
        
        # Status label with latency
        self.status_lbl = QtWidgets.QLabel("Estado: Desconocido")
        self.status_lbl.setWordWrap(True)
        
        # Last sync info
        self.last_sync_lbl = QtWidgets.QLabel("Última sincronización: Nunca")
        self.last_sync_lbl.setStyleSheet("color: #95a5a6; font-size: 11px;")
        
        # Manual sync button
        self.manual_sync_btn = QtWidgets.QPushButton("🔄 Sincronizar Ahora")
        self.manual_sync_btn.clicked.connect(self._manual_sync)
        self.manual_sync_btn.setToolTip("Forzar sincronización inmediata con el servidor")
        self.manual_sync_btn.setEnabled(False)  # Enable after successful connection test
        
        form_net.addRow("IP Servidor Maestro:", self.server_ip)
        form_net.addRow("Puerto:", self.server_port)
        sync_label = QtWidgets.QLabel("Intervalo Sinc.:")
        sync_label.setToolTip("Segundos entre sincronizaciones")
        form_net.addRow(sync_label, self.sync_interval)
        form_net.addRow("", self.test_conn_btn)
        form_net.addRow("", self.status_lbl)
        form_net.addRow("", self.last_sync_lbl)
        form_net.addRow("", self.manual_sync_btn)
        layout.addWidget(gb_net)

        # API
        gb_api = QtWidgets.QGroupBox("🔌 API Externa (Dashboard/Web)")
        gb_api.setToolTip("Configuración de API para integración con sistemas externos")
        form_api = QtWidgets.QFormLayout(gb_api)
        
        self.api_enabled = QtWidgets.QCheckBox("Habilitar API REST Externa")
        self.api_enabled.setChecked(bool(self.cfg.get("api_external_enabled", False)))
        self.api_enabled.setToolTip("Permite que aplicaciones externas se conecten al POS via API")
        
        self.api_base_url = QtWidgets.QLineEdit(self.cfg.get("api_external_base_url", ""))
        self.api_base_url.setPlaceholderText("https://mi-tienda.com/api")
        self.api_base_url.setToolTip("URL base del servidor API externo")
        
        self.api_token = QtWidgets.QLineEdit(self.cfg.get("api_dashboard_token", ""))
        self.api_token.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.api_token.setToolTip("Token de autenticación para acceso seguro a la API")
        
        # Token buttons row
        token_buttons = QtWidgets.QHBoxLayout()
        self.gen_token_btn = QtWidgets.QPushButton("🔑 Generar Token")
        self.gen_token_btn.clicked.connect(self._generate_token)
        self.gen_token_btn.setToolTip("Crea un nuevo token seguro de 256 bits")
        
        self.test_api_btn = QtWidgets.QPushButton("✓ Probar API")
        self.test_api_btn.clicked.connect(self._test_api)
        self.test_api_btn.setToolTip("Verifica la conexión con la API externa")
        
        token_buttons.addWidget(self.gen_token_btn)
        token_buttons.addWidget(self.test_api_btn)
        token_buttons_widget = QtWidgets.QWidget()
        token_buttons_widget.setLayout(token_buttons)
        
        # API status
        self.api_status_lbl = QtWidgets.QLabel("")
        self.api_status_lbl.setWordWrap(True)
        
        form_api.addRow("", self.api_enabled)
        form_api.addRow("URL Base:", self.api_base_url)
        form_api.addRow("Token de Acceso:", self.api_token)
        form_api.addRow("", token_buttons_widget)
        form_api.addRow("", self.api_status_lbl)
        layout.addWidget(gb_api)

        layout.addStretch()
        layout.addWidget(self._save_btn())
        return page
    
    def _create_multibranch_page(self) -> QtWidgets.QWidget:
        """Create Multi-Branch configuration page."""
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        cfg = self.core.get_app_config() or {}
        theme = cfg.get("theme", "Light")
        c = theme_manager.get_colors(theme)
        
        layout.addWidget(self._header("🏪 Configuración Multi-Sucursal"))
        
        # === INFORMACIÓN DE ESTA SUCURSAL ===
        gb_branch = QtWidgets.QGroupBox("📍 Esta Sucursal")
        gb_branch.setToolTip("Identifica esta terminal dentro de la red de sucursales")
        form_branch = QtWidgets.QFormLayout(gb_branch)
        
        self.branch_id = QtWidgets.QSpinBox()
        self.branch_id.setRange(1, 999)
        self.branch_id.setValue(int(cfg.get("branch_id", 1)))
        self.branch_id.setToolTip("ID único de esta sucursal (1=Matriz)")
        form_branch.addRow("ID de Sucursal:", self.branch_id)
        
        self.branch_name = QtWidgets.QLineEdit()
        self.branch_name.setText(cfg.get("branch_name", "Sucursal Principal"))
        self.branch_name.setPlaceholderText("ej: Sucursal Centro")
        form_branch.addRow("Nombre:", self.branch_name)
        
        self.terminal_id = QtWidgets.QSpinBox()
        self.terminal_id.setRange(1, 99)
        self.terminal_id.setValue(int(cfg.get("terminal_id", 1)))
        self.terminal_id.setToolTip("Número de caja dentro de la sucursal")
        form_branch.addRow("Terminal/Caja:", self.terminal_id)
        
        layout.addWidget(gb_branch)
        
        # === SERVIDOR CENTRAL ===
        gb_central = QtWidgets.QGroupBox("🖥️ Servidor Central")
        gb_central.setToolTip("Configuración del servidor central para sincronización")
        form_central = QtWidgets.QFormLayout(gb_central)
        
        self.central_enabled = QtWidgets.QCheckBox("Habilitar sincronización con servidor central")
        self.central_enabled.setChecked(bool(cfg.get("central_enabled", False)))
        form_central.addRow("", self.central_enabled)
        
        self.central_url = QtWidgets.QLineEdit()
        self.central_url.setText(cfg.get("central_url", ""))
        self.central_url.setPlaceholderText("http://100.64.0.1:8000 (IP Tailscale)")
        self.central_url.setToolTip("URL del servidor central TITAN Gateway")
        form_central.addRow("URL Servidor:", self.central_url)
        
        self.central_token = QtWidgets.QLineEdit()
        self.central_token.setText(cfg.get("central_token", ""))
        self.central_token.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.central_token.setPlaceholderText("Token de autenticación")
        form_central.addRow("Token:", self.central_token)
        
        # Botones de conexión
        central_btns = QtWidgets.QHBoxLayout()
        
        self.test_central_btn = QtWidgets.QPushButton("🔗 Probar Conexión")
        self.test_central_btn.clicked.connect(self._test_central_connection)
        central_btns.addWidget(self.test_central_btn)
        
        self.sync_now_btn = QtWidgets.QPushButton("🔄 Sincronizar Ahora")
        self.sync_now_btn.clicked.connect(self._sync_with_central)
        central_btns.addWidget(self.sync_now_btn)
        
        central_btns_widget = QtWidgets.QWidget()
        central_btns_widget.setLayout(central_btns)
        form_central.addRow("", central_btns_widget)
        
        self.central_status_lbl = QtWidgets.QLabel("")
        self.central_status_lbl.setWordWrap(True)
        form_central.addRow("Estado:", self.central_status_lbl)
        
        layout.addWidget(gb_central)
        
        # === SINCRONIZACIÓN AUTOMÁTICA ===
        gb_sync = QtWidgets.QGroupBox("⏱️ Sincronización Automática")
        form_sync = QtWidgets.QFormLayout(gb_sync)
        
        self.auto_sync_enabled = QtWidgets.QCheckBox("Sincronizar automáticamente")
        self.auto_sync_enabled.setChecked(bool(cfg.get("auto_sync_enabled", True)))
        form_sync.addRow("", self.auto_sync_enabled)
        
        self.sync_interval = QtWidgets.QSpinBox()
        self.sync_interval.setRange(5, 3600)
        self.sync_interval.setSuffix(" segundos")
        self.sync_interval.setValue(int(cfg.get("sync_interval", 30)))
        self.sync_interval.setToolTip("Intervalo de sincronización automática")
        form_sync.addRow("Intervalo:", self.sync_interval)
        
        # Qué sincronizar
        self.sync_sales = QtWidgets.QCheckBox("Ventas")
        self.sync_sales.setChecked(bool(cfg.get("sync_sales", True)))
        self.sync_inventory = QtWidgets.QCheckBox("Inventario")
        self.sync_inventory.setChecked(bool(cfg.get("sync_inventory", True)))
        self.sync_customers = QtWidgets.QCheckBox("Clientes")
        self.sync_customers.setChecked(bool(cfg.get("sync_customers", True)))
        self.sync_products = QtWidgets.QCheckBox("Productos/Precios")
        self.sync_products.setChecked(bool(cfg.get("sync_products", True)))
        
        sync_options = QtWidgets.QHBoxLayout()
        sync_options.addWidget(self.sync_sales)
        sync_options.addWidget(self.sync_inventory)
        sync_options.addWidget(self.sync_customers)
        sync_options.addWidget(self.sync_products)
        sync_widget = QtWidgets.QWidget()
        sync_widget.setLayout(sync_options)
        form_sync.addRow("Sincronizar:", sync_widget)
        
        # Manual full sync button
        self.btn_sync_all = QtWidgets.QPushButton("🔄 Sincronizar Todo Ahora")
        self.btn_sync_all.setToolTip("Descarga e importa todas las tablas desde el servidor (productos, clientes, etc.)")
        self.btn_sync_all.clicked.connect(self._on_sync_all_tables)
        self.btn_sync_all.setEnabled(cfg.get("mode") == "client")  # Only for clients
        form_sync.addRow("", self.btn_sync_all)
        
        layout.addWidget(gb_sync)
        
        # === TAILSCALE INFO ===
        gb_tailscale = QtWidgets.QGroupBox("🔐 Tailscale VPN")
        form_tailscale = QtWidgets.QFormLayout(gb_tailscale)
        
        # Check Tailscale status
        self.tailscale_status = QtWidgets.QLabel("⏳ Verificando...")
        form_tailscale.addRow("Estado:", self.tailscale_status)
        
        self.tailscale_ip = QtWidgets.QLabel("-")
        form_tailscale.addRow("IP Tailscale:", self.tailscale_ip)
        
        check_ts_btn = QtWidgets.QPushButton("🔄 Verificar Tailscale")
        check_ts_btn.clicked.connect(self._check_tailscale)
        form_tailscale.addRow("", check_ts_btn)
        
        layout.addWidget(gb_tailscale)
        
        # Check Tailscale on load
        self._check_tailscale()
        
        layout.addStretch()
        layout.addWidget(self._save_btn())
        return page
    
    def _test_central_connection(self):
        """Test connection to central server."""
        url = self.central_url.text().strip()
        token = self.central_token.text().strip()
        
        if not url:
            self.central_status_lbl.setText("❌ Ingrese URL del servidor")
            self.central_status_lbl.setStyleSheet("color: #e74c3c;")
            return
        
        self.test_central_btn.setEnabled(False)
        self.central_status_lbl.setText("⏳ Conectando...")
        QtWidgets.QApplication.processEvents()
        
        try:
            import requests
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            response = requests.get(f"{url}/health", headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                self.central_status_lbl.setText(f"✅ Conectado - {data.get('message', 'OK')}")
                self.central_status_lbl.setStyleSheet("color: #27ae60; font-weight: bold;")
            else:
                self.central_status_lbl.setText(f"⚠️ Servidor respondió: {response.status_code}")
                self.central_status_lbl.setStyleSheet("color: #f39c12;")
                
        except requests.exceptions.ConnectionError:
            self.central_status_lbl.setText("❌ No se pudo conectar al servidor")
            self.central_status_lbl.setStyleSheet("color: #e74c3c;")
        except Exception as e:
            self.central_status_lbl.setText(f"❌ Error: {str(e)[:50]}")
            self.central_status_lbl.setStyleSheet("color: #e74c3c;")
        finally:
            self.test_central_btn.setEnabled(True)
    
    def _sync_with_central(self):
        """Manual sync with central server."""
        url = self.central_url.text().strip()
        token = self.central_token.text().strip()
        
        if not url:
            QtWidgets.QMessageBox.warning(self, "Error", "Configure la URL del servidor central primero.")
            return
        
        progress = QtWidgets.QProgressDialog(
            "Sincronizando con servidor central...",
            "Cancelar",
            0, 100,
            self
        )
        progress.setWindowTitle("Sincronización")
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.show()
        progress.setValue(10)
        QtWidgets.QApplication.processEvents()
        
        try:
            from app.services.centralized_backup import CentralizedBackupService
            
            service = CentralizedBackupService(self.core, url)
            
            progress.setValue(30)
            QtWidgets.QApplication.processEvents()
            
            result = service.sync_incremental()
            
            progress.setValue(100)
            progress.close()
            
            if result.get("success"):
                QtWidgets.QMessageBox.information(
                    self,
                    "Sincronización Completa",
                    f"✅ Sincronización exitosa\n\n"
                    f"Ventas enviadas: {result.get('sales_sent', 0)}\n"
                    f"Productos recibidos: {result.get('products_received', 0)}"
                )
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Error de Sincronización",
                    f"⚠️ {result.get('error', 'Error desconocido')}"
                )
                
        except Exception as e:
            progress.close()
            QtWidgets.QMessageBox.critical(self, "Error", f"Error: {e}")
    
    def _on_sync_all_tables(self) -> None:
        """Perform full synchronization of all tables from server."""
        cfg = self.core.read_local_config()
        
        if cfg.get("mode") != "client":
            QtWidgets.QMessageBox.warning(
                self,
                "No disponible",
                "La sincronización manual solo está disponible en modo cliente."
            )
            return
        
        # Get server configuration
        server_ip = cfg.get("server_ip", "127.0.0.1")
        server_port = cfg.get("server_port", 8000)
        token = cfg.get("sync_token") or cfg.get("api_dashboard_token", "")
        
        if not token:
            QtWidgets.QMessageBox.warning(
                self,
                "Configuración incompleta",
                "No se encontró el token de sincronización en la configuración."
            )
            return
        
        server_url = f"http://{server_ip}:{server_port}"
        
        # Show progress dialog
        progress = QtWidgets.QProgressDialog(
            "Sincronizando todas las tablas desde el servidor...",
            "Cancelar",
            0,
            100,
            self
        )
        progress.setWindowTitle("Sincronización Completa")
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)  # No cancel for now
        progress.show()
        progress.setValue(0)
        QtWidgets.QApplication.processEvents()
        
        try:
            from app.utils.network_client import MultiCajaClient
            from app.utils.sync_client import sync_all_tables_pull
            from app.utils.sync_config import PUSH_ONLY_TABLES
            
            progress.setValue(10)
            progress.setLabelText("Conectando con el servidor...")
            QtWidgets.QApplication.processEvents()
            
            # Create sync client
            sync_client = MultiCajaClient(server_url, timeout=30, token=token)
            
            progress.setValue(20)
            progress.setLabelText("Sincronizando tablas bidireccionales...")
            QtWidgets.QApplication.processEvents()
            
            # Perform full pull sync
            results = sync_all_tables_pull(sync_client, self.core)
            
            progress.setValue(90)
            progress.setLabelText("Finalizando...")
            QtWidgets.QApplication.processEvents()
            
            # Count successes
            success_count = sum(1 for r in results.values() if r.get("success"))
            total_count = len(results)
            
            progress.setValue(100)
            progress.close()
            
            # Show results
            if success_count == total_count:
                QtWidgets.QMessageBox.information(
                    self,
                    "Sincronización Completa",
                    f"✅ Se sincronizaron exitosamente {success_count} tablas desde el servidor."
                )
            else:
                failed = [name for name, r in results.items() if not r.get("success")]
                failed_details = []
                for name in failed[:10]:  # Show first 10 with details
                    r = results[name]
                    error_msg = r.get("error") or r.get("message", "Error desconocido")
                    # Show full error message (allow up to 200 chars per table)
                    if len(error_msg) > 200:
                        error_msg = error_msg[:200] + "..."
                    failed_details.append(f"  • {name}: {error_msg}")
                
                error_text = f"Se sincronizaron {success_count} de {total_count} tablas bidireccionales.\n\n"
                error_text += f"Tablas con error ({len(failed)}):\n" + "\n".join(failed_details)
                if len(failed) > 10:
                    error_text += f"\n  ... y {len(failed) - 10} más"
                
                error_text += f"\n\nTotal de tablas configuradas: {total_count} bidireccionales + {len(PUSH_ONLY_TABLES)} push-only = {total_count + len(PUSH_ONLY_TABLES)} total"
                
                QtWidgets.QMessageBox.warning(
                    self,
                    "Sincronización Parcial",
                    error_text
                )
                
        except Exception as e:
            progress.close()
            QtWidgets.QMessageBox.critical(
                self,
                "Error de Sincronización",
                f"Error al sincronizar con el servidor:\n\n{e}"
            )
            import logging
            logging.error(f"Error in _on_sync_all_tables: {e}", exc_info=True)
    
    def _check_tailscale(self):
        """Check Tailscale status and IP."""
        import subprocess
        
        try:
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                
                if data.get("BackendState") == "Running":
                    self.tailscale_status.setText("🟢 Conectado")
                    self.tailscale_status.setStyleSheet("color: #27ae60; font-weight: bold;")
                    
                    # Get own IP
                    own_ip = data.get("Self", {}).get("TailscaleIPs", [])
                    if own_ip:
                        self.tailscale_ip.setText(own_ip[0])
                else:
                    self.tailscale_status.setText("🟡 " + data.get("BackendState", "Desconocido"))
                    self.tailscale_status.setStyleSheet("color: #f39c12;")
                    self.tailscale_ip.setText("-")
            else:
                self.tailscale_status.setText("🔴 No iniciado")
                self.tailscale_status.setStyleSheet("color: #e74c3c;")
                self.tailscale_ip.setText("-")
                
        except FileNotFoundError:
            self.tailscale_status.setText("⚪ Tailscale no instalado")
            self.tailscale_status.setStyleSheet("color: #95a5a6;")
            self.tailscale_ip.setText("-")
        except Exception as e:
            self.tailscale_status.setText(f"❌ Error: {str(e)[:30]}")
            self.tailscale_status.setStyleSheet("color: #e74c3c;")
            self.tailscale_ip.setText("-")
    
    def _create_midas_page(self) -> QtWidgets.QWidget:
        """Create MIDAS Loyalty System configuration page"""
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        cfg = self.core.get_app_config() or {}
        theme = cfg.get("theme", "Light")
        c = theme_manager.get_colors(theme)
        
        layout.addWidget(self._header("💎 Sistema de Lealtad MIDAS"))
        
        # Global Settings
        gb_global = QtWidgets.QGroupBox("⚙️ Configuración Global")
        gb_global.setToolTip("Configuración general del sistema de puntos")
        form_global = QtWidgets.QFormLayout(gb_global)
        
        self.midas_enabled = QtWidgets.QCheckBox("Activar sistema MIDAS de lealtad")
        self.midas_enabled.setChecked(bool(self.cfg.get("midas_enabled", True)))
        self.midas_enabled.setToolTip("Habilita o deshabilita todo el sistema de lealtad")
        
        self.midas_cashback_percent = QtWidgets.QDoubleSpinBox()
        self.midas_cashback_percent.setRange(0.0, 100.0)
        self.midas_cashback_percent.setSuffix("%")
        self.midas_cashback_percent.setValue(float(self.cfg.get("cashback_percent", 0.0)))
        self.midas_cashback_percent.setToolTip(
            "Porcentaje global de cashback cuando no hay reglas específicas.\\n"
            "Este valor se usa como fallback si no aplica ninguna regla."
        )
        
        form_global.addRow("", self.midas_enabled)
        form_global.addRow("Cashback Global (Fallback):", self.midas_cashback_percent)
        layout.addWidget(gb_global)
        
        # Loyalty Rules Management
        gb_rules = QtWidgets.QGroupBox("📊 Reglas de Lealtad")
        gb_rules.setToolTip("Gestiona las reglas de acumulación de puntos")
        rules_layout = QtWidgets.QVBoxLayout(gb_rules)
        
        # Info label
        rules_info = QtWidgets.QLabel(
            "Las reglas definen cómo se acumulan puntos. Puedes crear reglas globales, "
            "por categoría o por producto específico."
        )
        rules_info.setWordWrap(True)
        rules_info.setStyleSheet(f"color: {c['text_secondary']}; padding: 5px;")
        rules_layout.addWidget(rules_info)
        
        # Rules table
        self.rules_table = QtWidgets.QTableWidget()
        self.rules_table.setColumnCount(6)
        self.rules_table.setHorizontalHeaderLabels([
            "ID", "Nombre", "Tipo", "Multiplicador", "Activa", "Prioridad"
        ])
        self.rules_table.horizontalHeader().setStretchLastSection(True)
        self.rules_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.rules_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rules_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
            }}
            QHeaderView::section {{
                background-color: {c['bg_header']};
                color: {c['text_header']};
                padding: 5px;
            }}
        """)
        rules_layout.addWidget(self.rules_table)
        
        # Rules buttons
        rules_btns = QtWidgets.QHBoxLayout()
        self.btn_add_rule = QtWidgets.QPushButton("➕ Nueva Regla")
        self.btn_edit_rule = QtWidgets.QPushButton("✏️ Editar")
        self.btn_del_rule = QtWidgets.QPushButton("🗑️ Eliminar")
        self.btn_refresh_rules = QtWidgets.QPushButton("🔄 Actualizar")
        
        for btn in [self.btn_add_rule, self.btn_edit_rule]:
            btn.setStyleSheet(f"background-color: {c['btn_primary']}; color: white; padding: 6px;")
        self.btn_del_rule.setStyleSheet(f"background-color: {c['btn_danger']}; color: white; padding: 6px;")
        self.btn_refresh_rules.setStyleSheet(f"background-color: {c['btn_success']}; color: white; padding: 6px;")
        
        self.btn_add_rule.clicked.connect(self._add_loyalty_rule)
        self.btn_edit_rule.clicked.connect(self._edit_loyalty_rule)
        self.btn_del_rule.clicked.connect(self._del_loyalty_rule)
        self.btn_refresh_rules.clicked.connect(self._load_loyalty_rules)
        
        rules_btns.addWidget(self.btn_add_rule)
        rules_btns.addWidget(self.btn_edit_rule)
        rules_btns.addWidget(self.btn_del_rule)
        rules_btns.addStretch()
        rules_btns.addWidget(self.btn_refresh_rules)
        rules_layout.addLayout(rules_btns)
        layout.addWidget(gb_rules)
        
        # Tier Thresholds
        gb_tiers = QtWidgets.QGroupBox("🎖️ Niveles de Lealtad")
        gb_tiers.setToolTip("Define los umbrales de puntos para cada nivel")
        form_tiers = QtWidgets.QFormLayout(gb_tiers)
        
        self.tier_plata = QtWidgets.QSpinBox()
        self.tier_plata.setRange(0, 1000000)
        self.tier_plata.setValue(int(self.cfg.get("midas_tier_plata", 1000)))
        self.tier_plata.setPrefix("$ ")
        self.tier_plata.setToolTip("Puntos necesarios para alcanzar nivel PLATA")
        
        self.tier_oro = QtWidgets.QSpinBox()
        self.tier_oro.setRange(0, 1000000)
        self.tier_oro.setValue(int(self.cfg.get("midas_tier_oro", 5000)))
        self.tier_oro.setPrefix("$ ")
        self.tier_oro.setToolTip("Puntos necesarios para alcanzar nivel ORO")
        
        self.tier_platino = QtWidgets.QSpinBox()
        self.tier_platino.setRange(0, 1000000)
        self.tier_platino.setValue(int(self.cfg.get("midas_tier_platino", 20000)))
        self.tier_platino.setPrefix("$ ")
        self.tier_platino.setToolTip("Puntos necesarios para alcanzar nivel PLATINO")
        
        form_tiers.addRow("🥉 BRONCE → PLATA:", self.tier_plata)
        form_tiers.addRow("🥈 PLATA → ORO:", self.tier_oro)
        form_tiers.addRow("🥇 ORO → PLATINO:", self.tier_platino)
        layout.addWidget(gb_tiers)
        
        # Fraud Detection
        gb_fraud = QtWidgets.QGroupBox("🛡️ Prevención de Fraude")
        gb_fraud.setToolTip("Configuración del sistema anti-fraude")
        form_fraud = QtWidgets.QFormLayout(gb_fraud)
        
        self.fraud_velocity_limit = QtWidgets.QSpinBox()
        self.fraud_velocity_limit.setRange(1, 100)
        self.fraud_velocity_limit.setValue(int(self.cfg.get("midas_velocity_limit", 20)))
        self.fraud_velocity_limit.setToolTip(
            "Número máximo de transacciones permitidas en una hora.\\n"
            "Si se excede, se marca como sospechoso."
        )
        
        self.fraud_auto_suspend = QtWidgets.QCheckBox("Suspender automáticamente cuentas con 3+ alertas")
        self.fraud_auto_suspend.setChecked(bool(self.cfg.get("midas_auto_suspend", True)))
        self.fraud_auto_suspend.setToolTip("Bloquea cuentas automáticamente si se detectan múltiples alertas de fraude")
        
        form_fraud.addRow("Límite de Velocidad (tx/hora):", self.fraud_velocity_limit)
        form_fraud.addRow("", self.fraud_auto_suspend)
        layout.addWidget(gb_fraud)
        
        # Statistics Panel
        gb_stats = QtWidgets.QGroupBox("📈 Estadísticas del Sistema")
        gb_stats.setToolTip("Información general del sistema MIDAS")
        stats_layout = QtWidgets.QVBoxLayout(gb_stats)
        
        self.midas_stats_label = QtWidgets.QLabel("Cargando estadísticas...")
        self.midas_stats_label.setWordWrap(True)
        self.midas_stats_label.setStyleSheet(f"color: {c['text_primary']}; padding: 10px;")
        stats_layout.addWidget(self.midas_stats_label)
        
        self.btn_refresh_stats = QtWidgets.QPushButton("🔄 Actualizar Estadísticas")
        self.btn_refresh_stats.clicked.connect(self._load_midas_stats)
        self.btn_refresh_stats.setStyleSheet(f"background-color: {c['btn_primary']}; color: white; padding: 6px;")
        stats_layout.addWidget(self.btn_refresh_stats)
        
        layout.addWidget(gb_stats)
        
        # Load initial data
        self._load_loyalty_rules()
        self._load_midas_stats()
        
        layout.addStretch()
        layout.addWidget(self._save_btn())
        return page
    
    def _create_permissions_page(self) -> QtWidgets.QWidget:
        """Create permissions configuration page"""
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        cfg = self.core.get_app_config() or {}
        theme = cfg.get("theme", "Light")
        c = theme_manager.get_colors(theme)
        
        layout.addWidget(self._header("🔐 Configuración de Permisos por Rol"))
        
        # Role selector
        role_layout = QtWidgets.QHBoxLayout()
        role_label = QtWidgets.QLabel("Rol a configurar:")
        role_label.setStyleSheet(f"font-weight: bold; font-size: 14px; color: {c['text_primary']};")
        self.role_selector = QtWidgets.QComboBox()
        self.role_selector.addItems(["Admin", "Manager", "Encargado", "Cajero"])
        self.role_selector.currentTextChanged.connect(self._load_role_permissions)
        self.role_selector.setFixedWidth(200)
        role_layout.addWidget(role_label)
        role_layout.addWidget(self.role_selector)
        role_layout.addStretch()
        layout.addLayout(role_layout)
        
        # Permissions table
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        
        permissions_widget = QtWidgets.QWidget()
        self.permissions_layout = QtWidgets.QVBoxLayout(permissions_widget)
        self.permissions_layout.setSpacing(10)
        
        # Store checkboxes for later access
        self.permission_checkboxes = {}
        
        # Get all permissions from engine
        from src.core.permission_engine import PERMISSIONS
        
        for category, perms in PERMISSIONS.items():
            # Category header
            category_label = QtWidgets.QLabel(f"📌 {category.upper()}")
            category_label.setStyleSheet(f"""
                font-weight: bold;
                font-size: 13px;
                color: {c['btn_primary']};
                padding: 5px 0;
                border-bottom: 2px solid {c['border']};
                margin-top: 10px;
            """)
            self.permissions_layout.addWidget(category_label)
            
            # Permission checkboxes
            for perm_id, perm_name in perms:
                cb = QtWidgets.QCheckBox(perm_name)
                cb.setStyleSheet(f"""
                    QCheckBox {{
                        color: {c['text_primary']};
                        font-size: 13px;
                        padding: 5px 20px;
                    }}
                    QCheckBox::indicator {{
                        width: 18px;
                        height: 18px;
                    }}
                """)
                self.permission_checkboxes[perm_id] = cb
                self.permissions_layout.addWidget(cb)
        
        self.permissions_layout.addStretch()
        scroll.setWidget(permissions_widget)
        layout.addWidget(scroll)
        
        # Buttons
        buttons_layout = QtWidgets.QHBoxLayout()
        
        self.btn_save_perms = QtWidgets.QPushButton("💾 Guardar Permisos")
        self.btn_save_perms.clicked.connect(self._save_permissions)
        self.btn_save_perms.setFixedHeight(40)
        self.btn_save_perms.setStyleSheet(f"""
            QPushButton {{
                background: {c['btn_success']};
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
                padding: 0 20px;
            }}
            QPushButton:hover {{
                background: #45a049;
            }}
        """)
        
        self.btn_reset_perms = QtWidgets.QPushButton("🔄 Restaurar Predeterminados")
        self.btn_reset_perms.clicked.connect(self._reset_permissions)
        self.btn_reset_perms.setFixedHeight(40)
        self.btn_reset_perms.setStyleSheet(f"""
            QPushButton {{
                background: {c['btn_warning']};
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
                padding: 0 20px;
            }}
            QPushButton:hover {{
                background: #F57C00;
            }}
        """)
        
        buttons_layout.addWidget(self.btn_save_perms)
        buttons_layout.addWidget(self.btn_reset_perms)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
        
        # Load initial permissions
        self._load_role_permissions("Admin")
        
        return page
    
    def _load_role_permissions(self, role_text: str):
        """Load permissions for selected role"""
        role_map = {"Admin": "admin", "Manager": "manager", "Encargado": "encargado", "Cajero": "cashier"}
        role = role_map.get(role_text, "cashier")
        
        if not hasattr(self.core, 'permission_engine'):
            return
        
        permissions = self.core.permission_engine.get_role_permissions(role)
        
        for perm_id, cb in self.permission_checkboxes.items():
            cb.setChecked(permissions.get(perm_id, False))
    
    def _save_permissions(self):
        """Save permissions for current role"""
        role_text = self.role_selector.currentText()
        role_map = {"Admin": "admin", "Manager": "manager", "Encargado": "encargado", "Cajero": "cashier"}
        role = role_map.get(role_text, "cashier")
        
        if not hasattr(self.core, 'permission_engine'):
            QtWidgets.QMessageBox.warning(self, "Error", "Permission engine not available")
            return
        
        for perm_id, cb in self.permission_checkboxes.items():
            self.core.permission_engine.set_permission(role, perm_id, cb.isChecked())
        
        QtWidgets.QMessageBox.information(self, "Guardado", f"Permisos actualizados para {role_text}")
    
    def _reset_permissions(self):
        """Reset permissions to defaults"""
        role_text = self.role_selector.currentText()
        role_map = {"Admin": "admin", "Manager": "manager", "Encargado": "encargado", "Cajero": "cashier"}
        role = role_map.get(role_text, "cashier")
        
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirmar",
            f"¿Restaurar permisos predeterminados para {role_text}?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            if hasattr(self.core, 'permission_engine'):
                self.core.permission_engine.reset_role_to_defaults(role)
                self._load_role_permissions(role_text)
                QtWidgets.QMessageBox.information(self, "Restaurado", f"Permisos restaurados para {role_text}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _header(self, text: str) -> QtWidgets.QLabel:
        lbl = QtWidgets.QLabel(text)
        lbl.setStyleSheet("""
            QLabel {
                font-size: 22px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 15px;
                border-bottom: 2px solid #3498db;
                padding-bottom: 5px;
            }
        """)
        return lbl

    def _save_btn(self) -> QtWidgets.QPushButton:
        btn = QtWidgets.QPushButton("💾 Guardar Cambios")
        btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2980b9, stop:1 #3498db);
                color: white;
                font-weight: bold;
                padding: 12px 24px;
                border-radius: 6px;
                font-size: 14px;
                border: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3498db, stop:1 #5dade2);
            }
        """)
        btn.clicked.connect(self._save)
        return btn

    # ------------------------------------------------------------------
    # Logic Handlers (Same logic, new UI)
    # ------------------------------------------------------------------
    def _test_connection(self) -> None:
        """Test connection to MultiCaja server with detailed feedback."""
        import re

        from PyQt6.QtCore import QThread, pyqtSignal

        # Validate IP address
        ip = self.server_ip.text().strip()
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(ip_pattern, ip):
            self.status_lbl.setText("❌ Error: Dirección IP inválida")
            self.status_lbl.setStyleSheet("color: #e74c3c; font-weight: bold;")
            QtWidgets.QMessageBox.warning(
                self, 
                "IP Inválida",
                f"La dirección IP '{ip}' no es válida.\nFormato esperado: 192.168.1.100"
            )
            return
        
        # Validate each octet
        octets = ip.split('.')
        for octet in octets:
            if int(octet) > 255:
                self.status_lbl.setText("❌ Error: IP fuera de rango")
                self.status_lbl.setStyleSheet("color: #e74c3c; font-weight: bold;")
                QtWidgets.QMessageBox.warning(
                    self,
                    "IP Inválida",
                    f"El octeto {octet} está fuera de rango (0-255)"
                )
                return
        
        port = self.server_port.value()
        url = f"http://{ip}:{port}"
        
        # Show testing status
        self.status_lbl.setText("⏳ Probando conexión...")
        self.status_lbl.setStyleSheet("color: #3498db; font-weight: bold;")
        self.test_conn_btn.setEnabled(False)
        QtWidgets.QApplication.processEvents()
        
        try:
            client = NetworkClient(url, timeout=5)
            
            # Test ping
            ok = client.ping()
            
            if ok:
                # Measure latency
                latency = client.measure_latency()
                latency_str = f" ({latency}ms)" if latency else ""
                
                self.status_lbl.setText(f"✅ Conectado{latency_str}")
                self.status_lbl.setStyleSheet("color: #2ecc71; font-weight: bold;")
                
                # Enable manual sync
                self.manual_sync_btn.setEnabled(True)
                
                # Try to get server info
                info = client.get_server_info()
                if "error" not in info:
                    server_name = info.get("server_name", "Desconocido")
                    QtWidgets.QMessageBox.information(
                        self,
                        "Conexión Exitosa",
                        f"Conectado al servidor: {server_name}\n"
                        f"Latencia: {latency_str}\n"
                        f"URL: {url}"
                    )
            else:
                self.status_lbl.setText("❌ Sin conexión")
                self.status_lbl.setStyleSheet("color: #e74c3c; font-weight: bold;")
                self.manual_sync_btn.setEnabled(False)
                
                # Try to get more details
                info = client.get_server_info()
                error_msg = info.get("error", "No se pudo conectar al servidor")
                
                QtWidgets.QMessageBox.warning(
                    self,
                    "Error de Conexión",
                    f"No se pudo conectar al servidor\n\n"
                    f"URL: {url}\n"
                    f"Error: {error_msg}\n\n"
                    f"Verifique:\n"
                    f"• El servidor está encendido y ejecutando\n"
                    f"• La IP y puerto son correctos\n"
                    f"• El firewall permite conexiones en el puerto {port}"
                )
        
        except Exception as e:
            self.status_lbl.setText(f"❌ Error: {str(e)[:30]}...")
            self.status_lbl.setStyleSheet("color: #e74c3c; font-weight: bold;")
            self.manual_sync_btn.setEnabled(False)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Error al probar conexión:\n{str(e)}"
            )
        
        finally:
            self.test_conn_btn.setEnabled(True)

    def update_theme(self) -> None:
        cfg = self.core.read_local_config()
        theme = cfg.get("theme", "Light")
        c = theme_manager.get_colors(theme)
        
        # Sidebar styles
        self.sidebar.setStyleSheet(f"""
            QListWidget {{
                background: {c['bg_header']};
                border: none;
                font-size: 14px;
                outline: none;
                padding-top: 20px;
            }}
            QListWidget::item {{
                padding: 15px 20px;
                color: {c['text_header']};
                border-left: 4px solid transparent;
                margin-bottom: 5px;
                font-weight: 500;
            }}
            QListWidget::item:selected {{
                background: {c['bg_card']};
                color: {c['btn_primary']};
                border-left: 4px solid {c['btn_primary']};
                font-weight: bold;
            }}
            QListWidget::item:hover:!selected {{
                background: {c['bg_card']};
                color: {c['btn_primary']};
                opacity: 0.8;
            }}
        """)
        
        # Pages background
        self.pages.setStyleSheet(f"QStackedWidget {{ background: {c['bg_main']}; }}")
        
        # Global styles for inputs within SettingsTab
        self.setStyleSheet(f"""
            QWidget#SettingsTab {{ background-color: {c['bg_main']}; }}
            QLabel {{ color: {c['text_primary']}; }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {c['border']};
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                color: {c['text_primary']};
                background-color: {c['bg_card']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                left: 10px;
                color: {c['text_secondary']};
            }}
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
                background-color: {c['input_bg']};
                color: {c['text_primary']};
                border: 1px solid {c['input_border']};
                border-radius: 6px;
                padding: 5px;
                font-size: 13px;
            }}
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
                border: 2px solid {c['input_focus']};
            }}
            QPushButton {{
                background-color: {c['bg_card']};
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {c['border']};
            }}
            QCheckBox {{
                color: {c['text_primary']};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {c['input_border']};
                border-radius: 4px;
                background: {c['input_bg']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {c['btn_primary']};
                border-color: {c['btn_primary']};
                image: url(assets/icon_check_white.png); 
            }}
            QComboBox QAbstractItemView {{
                background-color: {c['input_bg']};
                color: {c['text_primary']};
                selection-background-color: {c['input_focus']};
                selection-color: white;
            }}
        """)

        if hasattr(self, "users_table"):
            self.users_table.setStyleSheet(f"""
                QTableWidget {{
                    background-color: {c['bg_card']};
                    color: {c['text_primary']};
                    gridline-color: {c['border']};
                    border: 1px solid {c['border']};
                }}
                QHeaderView::section {{
                    background-color: {c['bg_header']};
                    color: {c['text_header']};
                    padding: 5px;
                    border: 1px solid {c['border']};
                }}
                QTableWidget::item {{
                    padding: 5px;
                }}
                QTableWidget::item:selected {{
                    background-color: {c['btn_primary']};
                    color: white;
                }}
            """)
        
        # Update permissions page if it exists
        if hasattr(self, 'role_selector'):
            self.role_selector.setStyleSheet(f"""
                QComboBox {{
                    background-color: {c['input_bg']};
                    color: {c['text_primary']};
                    border: 1px solid {c['input_border']};
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 13px;
                }}
                QComboBox::drop-down {{
                    border: none;
                }}
                QComboBox::down-arrow {{
                    image: url(none);
                }}
            """)
        
        if hasattr(self, 'permission_checkboxes'):
            for cb in self.permission_checkboxes.values():
                cb.setStyleSheet(f"""
                    QCheckBox {{
                        color: {c['text_primary']};
                        font-size: 13px;
                        padding: 5px 20px;
                        background: transparent;
                    }}
                    QCheckBox::indicator {{
                        width: 18px;
                        height: 18px;
                        border: 2px solid {c['border']};
                        border-radius: 3px;
                        background: {c['input_bg']};
                    }}
                    QCheckBox::indicator:checked {{
                        background: {c['btn_primary']};
                        border: 2px solid {c['btn_primary']};
                    }}
                """)
        
        if hasattr(self, 'btn_save_perms'):
            self.btn_save_perms.setStyleSheet(f"""
                QPushButton {{
                    background: {c['btn_success']};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 0 20px;
                }}
                QPushButton:hover {{
                    background: #45a049;
                }}
            """)
        
        if hasattr(self, 'btn_reset_perms'):
            self.btn_reset_perms.setStyleSheet(f"""
                QPushButton {{
                    background: {c['btn_warning']};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 0 20px;
                }}
                QPushButton:hover {{
                    background: #F57C00;
                }}
            """)
            
        if hasattr(self, "btn_add_user"):
            for btn in [self.btn_add_user, self.btn_edit_user]:
                btn.setStyleSheet(f"background-color: {c['btn_primary']}; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold;")
            self.btn_del_user.setStyleSheet(f"background-color: {c['btn_danger']}; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold;")

        # Force style update
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _apply_theme(self) -> None:
        app = QtWidgets.QApplication.instance()
        if app is None:
            return
        selected = self.theme_combo.currentText()
        theme_manager.apply_theme(app, selected)  # type: ignore[arg-type]
        cfg = self.core.read_local_config()
        cfg["theme"] = selected
        self.core.write_local_config(cfg)
        
        # Notify main window to reload theme for all tabs
        window = self.window()
        if hasattr(window, "reload_theme"):
            window.reload_theme()

    def _save(self) -> None:
        cfg = self.core.read_local_config()
        
        # Collect MIDAS settings if they exist
        midas_settings = {}
        if hasattr(self, 'midas_enabled'):
            midas_settings = {
                "midas_enabled": self.midas_enabled.isChecked(),
                "midas_tier_plata": self.tier_plata.value(),
                "midas_tier_oro": self.tier_oro.value(),
                "midas_tier_platino": self.tier_platino.value(),
                "midas_velocity_limit": self.fraud_velocity_limit.value(),
                "midas_auto_suspend": self.fraud_auto_suspend.isChecked(),
            }
        
        # Update cfg dictionary (not using upCAST - cfg is a dict)
        cfg.update(
            {
                "mode": self.mode_combo.currentText(),
                "server_ip": self.server_ip.text().strip(),
                "server_port": self.server_port.value(),
                "sync_interval_seconds": self.sync_interval.value(),
                "cashback_percent": self.cashback_percent.value() if hasattr(self, 'cashback_percent') else (self.midas_cashback_percent.value() if hasattr(self, 'midas_cashback_percent') else 0.0),
                "theme": self.theme_combo.currentText(),

                "scanner_prefix": self.prefix_input.text(),
                "scanner_suffix": self.suffix_input.text(),
                "camera_scanner_enabled": self.camera_enabled.isChecked(),
                "camera_scanner_index": self.camera_index.value(),
                "printer_name": self.printer_name.currentText().strip(),
                "ticket_paper_width": self.paper_width.currentText(),
                "auto_print_tickets": self.auto_print.isChecked(),
                "cash_drawer_enabled": self.drawer_enabled.isChecked(),
                "cash_drawer_pulse_bytes": self.drawer_sequence.text().strip() or "\\x1B\\x70\\x00\\x19\\xFA",
                "api_external_enabled": self.api_enabled.isChecked(),
                "api_external_base_url": self.api_base_url.text().strip(),
                "api_dashboard_token": self.api_token.text().strip(),
                "backup_auto_on_close": self.backup_auto.isChecked(),
                "backup_dir": self.backup_dir.text().strip() or str(DATA_DIR / "backups"),
                "backup_encrypt": self.backup_encrypt.isChecked(),
                "backup_encrypt_key": self.backup_key.text().strip(),
                "backup_nas_enabled": self.backup_nas_enabled.isChecked(),
                "backup_nas_path": self.backup_nas_path.text().strip(),
                "backup_gdrive_enabled": self.backup_gdrive_enabled.isChecked(),
                "backup_onedrive_enabled": self.backup_onedrive_enabled.isChecked(),
                "backup_cloud_enabled": self.backup_cloud_enabled.isChecked(),
                "backup_s3_endpoint": self.s3_endpoint.text().strip(),
                "backup_s3_access_key": self.s3_access.text().strip(),
                "backup_s3_secret_key": self.s3_secret.text().strip(),
                "backup_s3_bucket": self.s3_bucket.text().strip(),
                "backup_s3_prefix": self.s3_prefix.text().strip(),
                "backup_retention_enabled": self.retention_enabled.isChecked(),
                "backup_retention_days": self.retention_days.value(),
                # Multi-Branch settings
                "branch_id": self.branch_id.value() if hasattr(self, 'branch_id') else 1,
                "branch_name": self.branch_name.text().strip() if hasattr(self, 'branch_name') else "Sucursal Principal",
                "terminal_id": self.terminal_id.value() if hasattr(self, 'terminal_id') else 1,
                "central_enabled": self.central_enabled.isChecked() if hasattr(self, 'central_enabled') else False,
                "central_url": self.central_url.text().strip() if hasattr(self, 'central_url') else "",
                "central_token": self.central_token.text().strip() if hasattr(self, 'central_token') else "",
                "auto_sync_enabled": self.auto_sync_enabled.isChecked() if hasattr(self, 'auto_sync_enabled') else True,
                "sync_sales": self.sync_sales.isChecked() if hasattr(self, 'sync_sales') else True,
                "sync_inventory": self.sync_inventory.isChecked() if hasattr(self, 'sync_inventory') else True,
                "sync_customers": self.sync_customers.isChecked() if hasattr(self, 'sync_customers') else True,
                "sync_products": self.sync_products.isChecked() if hasattr(self, 'sync_products') else True,
                **midas_settings  # Merge MIDAS settings
            }
        )
        self.core.write_local_config(cfg)
        
        # Save loyalty rules state to database
        if hasattr(self, 'rule_base_1pct') and hasattr(self, 'rule_weekend_10pct'):
            try:
                if not self.core.db:
                    logger.warning("Database not available")
                    return
                operations = []
                
                # Update Rule 1: 1% base
                operations.append((
                    "UPDATE loyalty_rules SET activo = %s WHERE nombre_display = '1% Base en Todas las Compras'",
                    (1 if self.rule_base_1pct.isChecked() else 0,)
                ))
                
                # Update Rule 2: 10% weekend
                operations.append((
                    "UPDATE loyalty_rules SET activo = %s WHERE nombre_display = '10% Extra en Fines de Semana'",
                    (1 if self.rule_weekend_10pct.isChecked() else 0,)
                ))
                
                if operations:
                    # CRITICAL FIX: Use INSERT ... ON CONFLICT to handle missing rules
                    # This ensures rules are created if they don't exist, or updated if they do
                    upsert_operations = []
                    for query, params in operations:
                        # Convert UPDATE to INSERT ... ON CONFLICT ... DO UPDATE
                        if "UPDATE loyalty_rules SET activo" in query:
                            # Extract rule name from WHERE clause
                            if "'1% Base en Todas las Compras'" in query:
                                rule_name = "1% Base en Todas las Compras"
                            elif "'10% Extra en Fines de Semana'" in query:
                                rule_name = "10% Extra en Fines de Semana"
                            else:
                                # Fallback to original UPDATE
                                upsert_operations.append((query, params))
                                continue
                            
                            # Use UPSERT (INSERT ... ON CONFLICT)
                            # Map rule names to regla_id (which has UNIQUE constraint)
                            regla_id_map = {
                                "1% Base en Todas las Compras": "BASE_DEFAULT",
                                "10% Extra en Fines de Semana": "WEEKEND_10PCT"
                            }
                            regla_id = regla_id_map.get(rule_name, rule_name.upper().replace(" ", "_").replace("%", "PCT"))
                            
                            # Determine multiplicador based on rule
                            multiplicador = 0.01 if "1%" in rule_name else 0.10
                            
                            # CRITICAL: All required fields must be provided
                            # regla_id: UNIQUE NOT NULL
                            # nombre_display: NOT NULL
                            # multiplicador: NOT NULL
                            # Other fields have defaults
                            upsert_query = """
                                INSERT INTO loyalty_rules (regla_id, nombre_display, activo, condicion_tipo, multiplicador, prioridad, descripcion)
                                VALUES (%s, %s, %s, 'GLOBAL', %s, 1, %s)
                                ON CONFLICT (regla_id) 
                                DO UPDATE SET 
                                    activo = EXCLUDED.activo, 
                                    nombre_display = EXCLUDED.nombre_display,
                                    multiplicador = EXCLUDED.multiplicador,
                                    updated_at = NOW()
                            """
                            descripcion = f"Regla automática: {rule_name}"
                            upsert_operations.append((upsert_query, (regla_id, rule_name, params[0], multiplicador, descripcion)))
                        else:
                            upsert_operations.append((query, params))
                    
                    # CRITICAL FIX: Handle execute_transaction result properly
                    try:
                        result = self.core.db.execute_transaction(upsert_operations)
                        # execute_transaction returns a dict with 'success' key
                        if isinstance(result, dict):
                            success = result.get('success', False)
                        else:
                            # Fallback for legacy return type (bool)
                            success = bool(result)
                        
                        if not success:
                            raise Exception("Failed to update loyalty rules")
                        logger.info("✅ Loyalty rules updated")
                    except Exception as tx_error:
                        # If transaction fails, try individual updates
                        logger.warning(f"Transaction failed, trying individual updates: {tx_error}")
                        for query, params in upsert_operations:
                            try:
                                self.core.db.execute_write(query, params)
                            except Exception as e:
                                logger.error(f"Failed to update rule: {e}")
                                # Don't raise - continue with other rules
                                pass
                        logger.info("✅ Loyalty rules updated (individual)")
            except Exception as e:
                logger.error(f"Error saving loyalty rules: {e}")
        
        self.core.update_fiscal_config(
            {
                "rfc_emisor": self.rfc_emisor.text().strip(),
                "razon_social_emisor": self.razon_emisor.text().strip(),
                "regimen_fiscal": self.regimen_emisor.text().strip(),
                "codigo_postal": self.lugar_expedicion.text().strip(),
                "lugar_expedicion": self.lugar_expedicion.text().strip(),
                "csd_cert_path": self.csd_cert.text().strip(),
                "csd_key_path": self.csd_key.text().strip(),
                "csd_key_password": self.csd_pass.text().strip(),
                "pac_base_url": self.pac_url.text().strip(),
                "pac_user": self.pac_user.text().strip(),
                "pac_password": self.pac_pass.text().strip(),
                "serie_factura": self.serie_factura.text().strip() or "F",
                "folio_actual": self.folio_actual.value(),
                # Facturapi settings - use correct column names matching DB
                "facturapi_enabled": 1 if (hasattr(self, 'facturapi_enabled') and self.facturapi_enabled.isChecked()) else 0,
                "facturapi_api_key": self.facturapi_key.text().strip() if hasattr(self, 'facturapi_key') else "",
                # Auto-detect sandbox mode from API key (sk_test_ = sandbox, sk_live_ = production)
                "facturapi_sandbox": 1 if 'sk_test' in (self.facturapi_key.text().strip() if hasattr(self, 'facturapi_key') else '') else 0,
            }
        )
        
        # Also update .env if facturapi key provided
        if hasattr(self, 'facturapi_key'):
            facturapi_key = self.facturapi_key.text().strip()
            if facturapi_key:
                import os
                os.environ['FACTURAPI_KEY'] = facturapi_key
        QtWidgets.QMessageBox.information(self, "Configuración", "Guardado exitosamente")

    def save_settings(self):
        """
        FIX B3 2026-01-30: Método legacy que referenciaba widgets inexistentes.
        Los widgets business_name, tax_rate, currency, printer_enabled no existen en SettingsTab.
        Este método nunca es llamado. Se convierte en stub seguro para evitar AttributeError.
        La configuración se guarda desde los diálogos específicos (TicketConfigDialog, etc.)
        """
        logging.getLogger(__name__).warning(
            "save_settings() called but this is legacy code. "
            "Use specific dialogs to save settings instead."
        )
        # No hacer nada - la configuración se maneja en diálogos específicos

    def _refresh_printer_list(self):
        """Detect and populate CUPS printers in the dropdown."""
        import subprocess
        
        current_text = self.printer_name.currentText() if hasattr(self.printer_name, 'currentText') else ""
        self.printer_name.clear()
        
        try:
            result = subprocess.run(
                ["lpstat", "-a"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    # Format: "PRINTER_NAME accepting requests since ..."
                    if line.strip():
                        printer_name = line.split()[0]
                        self.printer_name.addItem(printer_name)
                
                logging.getLogger(__name__).info(f"Detected {self.printer_name.count()} printers")
            else:
                # Add placeholder if no printers found
                self.printer_name.addItem("(Sin impresoras detectadas)")
                
        except subprocess.TimeoutExpired:
            logging.getLogger(__name__).warning("Timeout detecting printers")
            self.printer_name.addItem("(Error de timeout)")
        except FileNotFoundError:
            logging.getLogger(__name__).warning("lpstat not found - CUPS not installed?")
            self.printer_name.addItem("(CUPS no instalado)")
        except Exception as e:
            logging.getLogger(__name__).error(f"Error detecting printers: {e}")
            self.printer_name.addItem("(Error)")
        
        # Restore previous selection if exists
        if current_text:
            idx = self.printer_name.findText(current_text)
            if idx >= 0:
                self.printer_name.setCurrentIndex(idx)
            else:
                self.printer_name.setCurrentText(current_text)

    def _launch_printer_wizard(self):
        try:
            dlg = PrinterWizardDialog(self.core, parent=self)
            if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                # Reload ALL settings into UI after wizard saves
                self.cfg = self.core.get_app_config() or {}
                self._refresh_printer_list()
                self.printer_name.setCurrentText(self.cfg.get("printer_name", ""))
                self.paper_width.setCurrentText(self.cfg.get("ticket_paper_width", "80mm"))
                self.auto_print.setChecked(bool(self.cfg.get("auto_print_tickets", False)))
                self.drawer_enabled.setChecked(bool(self.cfg.get("cash_drawer_enabled", False)))
                self.drawer_sequence.setText(self.cfg.get("cash_drawer_pulse_bytes", "\\x1B\\x70\\x00\\x19\\xFA"))
        except Exception as e:
            logging.getLogger(__name__).error(f"Error launching printer wizard: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo abrir el asistente: {e}")

    def _launch_ticket_config(self):
        try:
            dlg = TicketConfigDialog(self.core, parent=self)
            dlg.exec()
        except Exception as e:
            logging.getLogger(__name__).error(f"Error launching ticket config: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo abrir el diseñador: {e}")

    def _test_print(self) -> None:
        """Test print using CUPS lp command"""
        printer_name = self.printer_name.currentText().strip()
        if not printer_name:
            QtWidgets.QMessageBox.warning(self, "Impresora", "Configura el nombre de la impresora primero")
            return
            
        try:
            from datetime import datetime
            import subprocess

            # Create test ticket content
            test_content = f"""
{"=" * 40}
     TITAN POS - TICKET DE PRUEBA
{"=" * 40}

Impresora: {printer_name}
Fecha: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}

{"*" * 40}
     PRUEBA EXITOSA
{"*" * 40}

Si puedes leer este texto,
la impresora está configurada
correctamente.

"""
            
            # Send to printer using lp command (CUPS)
            # Use latin-1 encoding for thermal printers (ESC/POS compatibility)
            # -o raw prevents CUPS from processing the text
            result = subprocess.run(
                ["lp", "-d", printer_name, "-o", "raw", "-"],
                input=test_content.encode('latin-1', errors='replace'),
                capture_output=True,
                timeout=10
            )
            
            if result.returncode == 0:
                output = result.stdout.decode('utf-8', errors='ignore').strip()
                QtWidgets.QMessageBox.information(
                    self, 
                    "Impresión", 
                    f"✓ Ticket enviado a CUPS\n\n{output}\n\n"
                    "Verifica que la impresora esté encendida y con papel."
                )
            else:
                error_msg = result.stderr.decode('utf-8', errors='ignore')
                QtWidgets.QMessageBox.critical(
                    self, 
                    "Error de Impresión", 
                    f"Error CUPS:\n{error_msg}"
                )
        except subprocess.TimeoutExpired:
            QtWidgets.QMessageBox.critical(self, "Error", "Timeout: La impresora no responde")
        except FileNotFoundError:
            QtWidgets.QMessageBox.critical(self, "Error", "Comando 'lp' no encontrado. ¿CUPS instalado%s")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error de Hardware", str(e))

    def _on_drawer_preset_changed(self, index: int) -> None:
        """Handle drawer preset selection change."""
        preset_data = self.drawer_preset.itemData(index)
        if preset_data and preset_data != "custom":
            self.drawer_sequence.setText(preset_data)
            self.drawer_sequence.setEnabled(False)
        else:
            # Custom - enable manual entry
            self.drawer_sequence.setEnabled(True)

    def _test_drawer(self) -> None:
        printer = self.printer_name.currentText().strip()
        if not printer:
            QtWidgets.QMessageBox.warning(self, "Cajón", "Define una impresora primero")
            return
        pulse_str = self.drawer_sequence.text().strip() or "\\x1B\\x70\\x00\\x19\\xFA"
        try:
            # La función open_cash_drawer ahora acepta strings y los parsea
            ticket_engine.open_cash_drawer(printer, pulse_str)
            QtWidgets.QMessageBox.information(self, "Cajón", "✅ Comando enviado correctamente.\nEl cajón debería haberse abierto.")
        except Exception as e:
            logging.exception("No se pudo probar el cajón")
            QtWidgets.QMessageBox.critical(self, "Cajón", f"❌ Error al enviar pulso:\n{e}")

    def _generate_token(self) -> None:
        new_token = secrets.token_urlsafe(32)
        self.api_token.setText(new_token)
    
    def _test_api(self) -> None:
        """Test external API connection and token validation."""
        base_url = self.api_base_url.text().strip()
        token = self.api_token.text().strip()
        
        # Validate URL
        if not base_url:
            self.api_status_lbl.setText("❌ Ingrese URL base primero")
            self.api_status_lbl.setStyleSheet("color: #e74c3c;")
            QtWidgets.QMessageBox.warning(
                self,
                "URL Requerida",
                "Debe ingresar la URL base de la API externa."
            )
            return
        
        if not token:
            self.api_status_lbl.setText("❌ Ingrese token primero")
            self.api_status_lbl.setStyleSheet("color: #e74c3c;")
            QtWidgets.QMessageBox.warning(
                self,
                "Token Requerido",
                "Debe generar o ingresar un token de acceso."
            )
            return
        
        # Test connection
        self.api_status_lbl.setText("⏳ Probando API...")
        self.api_status_lbl.setStyleSheet("color: #3498db;")
        self.test_api_btn.setEnabled(False)
        QtWidgets.QApplication.processEvents()
        
        try:
            client = NetworkClient(base_url, timeout=10, token=token)
            
            # Test token validation
            valid, message = client.test_api_token()
            
            if valid:
                self.api_status_lbl.setText(f"✅ {message}")
                self.api_status_lbl.setStyleSheet("color: #2ecc71; font-weight: bold;")
                
                QtWidgets.QMessageBox.information(
                    self,
                    "API Conectada",
                    f"Conexión exitosa con la API externa\n\n"
                    f"URL: {base_url}\n"
                    f"Token: {'*' * 20}...{token[-8:]}\n"
                    f"Estado: {message}"
                )
            else:
                self.api_status_lbl.setText(f"❌ {message}")
                self.api_status_lbl.setStyleSheet("color: #e74c3c; font-weight: bold;")
                
                QtWidgets.QMessageBox.warning(
                    self,
                    "Error de Autenticación",
                    f"No se pudo autenticar con la API:\\n\\n{message}\\n\\n"
                    f"Verifique:\\n"
                    f"• El token es correcto\\n"
                    f"• La URL de la API es válida\\n"
                    f"• El servidor API está en línea"
                )
        
        except Exception as e:
            self.api_status_lbl.setText(f"❌ Error: {str(e)[:30]}...")
            self.api_status_lbl.setStyleSheet("color: #e74c3c;")
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Error al probar API:\\n{str(e)}"
            )
        
        finally:
            self.test_api_btn.setEnabled(True)
    
    def _manual_sync(self) -> None:
        """Trigger manual synchronization with server."""
        ip = self.server_ip.text().strip()
        port = self.server_port.value()
        url = f"http://{ip}:{port}"
        token = self.api_token.text().strip()
        
        # Show progress dialog
        progress = QtWidgets.QProgressDialog(
            "Sincronizando con el servidor...",
            "Cancelar",
            0,
            100,
            self
        )
        progress.setWindowTitle("Sincronización")
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.show()
        progress.setValue(10)
        QtWidgets.QApplication.processEvents()
        
        try:
            from datetime import datetime

            from app.utils.network_client import MultiCajaClient

            # Create  sync client
            sync_client = MultiCajaClient(url, timeout=15, token=token)
            
            progress.setValue(20)
            progress.setLabelText("Sincronizando inventario...")
            QtWidgets.QApplication.processEvents()
            
            # For now, just test connectivity
            # In production, you'd fetch actual data from database
            sample_products = []  # Would be: self.core.get_all_products()
            
            success_inv, msg_inv, data_inv = sync_client.sync_inventory(sample_products)
            
            progress.setValue(50)
            progress.setLabelText("Sincronizando ventas...")
            QtWidgets.QApplication.processEvents()
            
            sample_sales = []  # Would be: self.core.get_recent_sales()
            success_sales, msg_sales, data_sales = sync_client.sync_sales(sample_sales)
            
            progress.setValue(80)
            progress.setLabelText("Sincronizando clientes...")
            QtWidgets.QApplication.processEvents()
            
            sample_customers = []  # Would be: self.core.get_all_customers()
            success_cust, msg_cust, data_cust = sync_client.sync_customers(sample_customers)
            
            progress.setValue(100)
            progress.close()
            
            # Update last sync time
            self.last_sync_lbl.setText(f"Última sincronización: {datetime.now().strftime('%H:%M:%S')}")
            self.last_sync_lbl.setStyleSheet("color: #2ecc71; font-size: 11px; font-weight: bold;")
            
            # Show results
            results = f"Inventario: {msg_inv}\\n"
            results += f"Ventas: {msg_sales}\\n"
            results += f"Clientes: {msg_cust}"
            
            if success_inv and success_sales and success_cust:
                QtWidgets.QMessageBox.information(
                    self,
                    "Sincronización Completa",
                    f"✅ Sincronización exitosa\\n\\n{results}"
                )
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Sincronización Parcial",
                    f"⚠️ Se completó con errores:\\n\\n{results}"
                )
        
        except Exception as e:
            progress.close()
            QtWidgets.QMessageBox.critical(
                self,
                "Error de Sincronización",
                f"Error durante la sincronización:\\n\\n{str(e)}"
            )

    def _test_nas(self) -> None:
        if BackupSettingsTestDialog is None:
            QtWidgets.QMessageBox.warning(
                self,
                "No disponible",
                "El módulo de prueba de configuración de backup no está disponible"
            )
            return
        dlg = BackupSettingsTestDialog("nas", {"path": self.backup_nas_path.text().strip()}, self)
        dlg.exec()

    def _test_s3(self) -> None:
        if BackupSettingsTestDialog is None:
            QtWidgets.QMessageBox.warning(
                self,
                "No disponible",
                "El módulo de prueba de configuración de backup no está disponible"
            )
            return
        dlg = BackupSettingsTestDialog(
            "s3",
            {
                "endpoint_url": self.s3_endpoint.text().strip(),
                "access_key": self.s3_access.text().strip(),
                "secret_key": self.s3_secret.text().strip(),
                "bucket": self.s3_bucket.text().strip(),
            },
            self,
        )
        dlg.exec()

    def _browse_cert_file(self, file_type):
        """Open file dialog for certificate files (.cer or .key)."""
        from pathlib import Path
        
        ext = ".cer" if file_type == 'cer' else ".key"
        desc = "Certificado" if file_type == 'cer' else "Llave Privada"
        
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            f"Seleccionar {desc} ({ext.upper()})",
            str(Path.home()),
            f"Archivos {ext.upper()} (*{ext});;Todos los archivos (*.*)"
        )
        
        if file_path:
            if file_type == 'cer':
                self.csd_cert.setText(file_path)
            else:
                self.csd_key.setText(file_path)
    
    def _open_global_invoice_dashboard(self) -> None:
        """Open the Global Invoice Dashboard for generating bulk CFDIs."""
        # CRITICAL DEBUG: Log button click
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                from app.utils.path_utils import get_debug_log_path_str
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"GLOBAL_INVOICE_DASHBOARD","location":"settings_tab.py:_open_global_invoice_dashboard","message":"Button clicked","data":{},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                logger.debug("Writing debug log for global invoice dashboard button: %s", e)
        # #endregion
        try:
            from app.dialogs.global_invoice_dialog import GlobalInvoiceDialog
            # CRITICAL DEBUG: Log before creating dialog
            # #region agent log
            if agent_log_enabled():
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"GLOBAL_INVOICE_DASHBOARD","location":"settings_tab.py:_open_global_invoice_dashboard","message":"Creating dialog","data":{},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                    logger.debug("Writing debug log for creating dialog: %s", e)
            # #endregion
            dialog = GlobalInvoiceDialog(self.core, self)
            # CRITICAL DEBUG: Log before showing dialog
            # #region agent log
            if agent_log_enabled():
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"GLOBAL_INVOICE_DASHBOARD","location":"settings_tab.py:_open_global_invoice_dashboard","message":"Showing dialog","data":{},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                    logger.debug("Writing debug log for showing dialog: %s", e)
            # #endregion
            dialog.exec()
            # CRITICAL DEBUG: Log after dialog closes
            # #region agent log
            if agent_log_enabled():
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"GLOBAL_INVOICE_DASHBOARD","location":"settings_tab.py:_open_global_invoice_dashboard","message":"Dialog closed","data":{},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                    logger.debug("Writing debug log for dialog closed: %s", e)
            # #endregion
        except Exception as e:
            # CRITICAL DEBUG: Log error
            # #region agent log
            if agent_log_enabled():
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"GLOBAL_INVOICE_DASHBOARD","location":"settings_tab.py:_open_global_invoice_dashboard","message":"Error opening dialog","data":{"error":str(e)},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e2:
                    logger.debug("Writing debug log for error: %s", e2)
            # #endregion
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Error al abrir Dashboard de Facturación Global:\n{e}"
            )
    
    def _toggle_pac_section(self, facturapi_enabled: bool):
        """Toggle PAC/CSD section based on Facturapi selection."""
        # When Facturapi is enabled, dim the PAC/CSD section
        if hasattr(self, 'gb_pac') and hasattr(self, 'gb_csd'):
            opacity = 0.5 if facturapi_enabled else 1.0
            style = "color: #888;" if facturapi_enabled else ""
            
            self.gb_pac.setEnabled(not facturapi_enabled)
            self.gb_csd.setEnabled(not facturapi_enabled)
            
            # Update title to indicate status
            if facturapi_enabled:
                self.gb_pac.setTitle("Proveedor (PAC) - No requerido con Facturapi")
                self.gb_csd.setTitle("🔐 Certificados (CSD) - No requerido con Facturapi")
            else:
                self.gb_pac.setTitle("Proveedor (PAC)")
                self.gb_csd.setTitle("🔐 Certificados (CSD)")
    
    def _update_facturapi_mode(self):
        """Update Facturapi mode label based on API key."""
        key = self.facturapi_key.text().strip()
        if not key:
            self.facturapi_mode.setText("⚪ No configurado")
            self.facturapi_mode.setStyleSheet("color: #95a5a6;")
        elif "test" in key.lower():
            self.facturapi_mode.setText("🧪 MODO PRUEBAS (Sandbox)")
            self.facturapi_mode.setStyleSheet("color: #f39c12; font-weight: bold;")
        elif "live" in key.lower():
            self.facturapi_mode.setText("🟢 MODO PRODUCCIÓN (Real)")
            self.facturapi_mode.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.facturapi_mode.setText("⚠️ Formato de key no reconocido")
            self.facturapi_mode.setStyleSheet("color: #e74c3c;")
    
    def _test_facturapi(self):
        """Test Facturapi connection."""
        key = self.facturapi_key.text().strip()
        
        if not key:
            QtWidgets.QMessageBox.warning(
                self,
                "API Key requerida",
                "Ingresa tu API Key de Facturapi.\n\n"
                "Obtén tu key en: https://dashboard.facturapi.io"
            )
            return
        
        try:
            # Temporarily set the key
            import os

            from app.fiscal.facturapi_connector import Facturapi
            old_key = os.environ.get('FACTURAPI_KEY', '')
            os.environ['FACTURAPI_KEY'] = key
            
            try:
                facturapi = Facturapi(key)
                result = facturapi.health_check()
                
                if result.get('success'):
                    mode_text = "🧪 PRUEBAS" if facturapi.mode == 'test' else "🟢 PRODUCCIÓN"
                    QtWidgets.QMessageBox.information(
                        self,
                        "✅ Conexión Exitosa",
                        f"Facturapi conectado correctamente.\n\n"
                        f"Modo: {mode_text}\n\n"
                        "Ya puedes generar facturas desde el historial de ventas."
                    )
                else:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Error de conexión",
                        f"No se pudo conectar a Facturapi:\n\n{result.get('error', 'Error desconocido')}"
                    )
            finally:
                # Restore original key
                if old_key:
                    os.environ['FACTURAPI_KEY'] = old_key
                elif 'FACTURAPI_KEY' in os.environ:
                    del os.environ['FACTURAPI_KEY']
                    
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Error al probar Facturapi:\n\n{str(e)}"
            )
    
    def _test_fiscal(self) -> None:
        """Validate fiscal configuration and certificates."""
        from pathlib import Path
        
        try:
            from app.utils.cert_validator import validate_cert_key_pair
        except ImportError:
            QtWidgets.QMessageBox.warning(
                self, 
                "Módulo no disponible",
                "El módulo de validación de certificados no está instalado.\n"
                "Instale: pip3 install cryptography"
            )
            return
        
        cert_path = self.csd_cert.text().strip()
        key_path = self.csd_key.text().strip()
        password = self.csd_pass.text().strip()
        
        # Validate inputs
        if not cert_path:
            QtWidgets.QMessageBox.warning(
                self, "Campo requerido", "Seleccione el archivo .cer"
            )
            return
        
        if not Path(cert_path).exists():
            QtWidgets.QMessageBox.warning(
                self, "Archivo no encontrado", 
                f"El archivo .cer no existe:\n{cert_path}"
            )
            return
        
        if not key_path:
            QtWidgets.QMessageBox.warning(
                self, "Campo requerido", "Seleccione el archivo .key"
            )
            return
        
        if not Path(key_path).exists():
            QtWidgets.QMessageBox.warning(
                self, "Archivo no encontrado",
                f"El archivo .key no existe:\n{key_path}"
            )
            return
        
        if not password:
            QtWidgets.QMessageBox.warning(
                self, "Campo requerido",
                "Ingrese la contraseña del certificado"
            )
            return
        
        # Validate certificates
        result = validate_cert_key_pair(cert_path, key_path, password)
        
        if result['valid']:
            # Success message
            msg = "✅ Certificados Válidos\n\n"
            msg += f"Serial: {result['cert_serial']}\n"
            msg += f"Válido hasta: {result['cert_expires']}\n"
            
            if result.get('cert_expired'):
                msg += "\n⚠️ ADVERTENCIA: Certificado expirado"
                QtWidgets.QMessageBox.warning(
                    self, "Certificado Expirado", msg
                )
            else:
                days = result.get('days_remaining', 0)
                msg += f"\nDías restantes: {days}"
                
                if days < 30:
                    msg += "\n\n⚠️ El certificado expira pronto"
                    QtWidgets.QMessageBox.warning(
                        self, "Certificado Válido (Próximo a vencer)", msg
                    )
                else:
                    QtWidgets.QMessageBox.information(
                        self, "Certificado Válido", msg
                    )
        else:
            # Error message
            QtWidgets.QMessageBox.critical(
                self,
                "Error de Validación",
                f"No se pudieron validar los certificados:\n\n{result['error']}"
            )

    def _open_restore(self):

        if BackupRestoreDialog is None:
            log_debug("settings_tab.py:_open_restore:no_dialog", "BackupRestoreDialog es None", {}, "H1")
            QtWidgets.QMessageBox.warning(self, "No disponible", "El módulo de backup no está disponible")
            return
        
        try:
            log_debug("settings_tab.py:_open_restore:creating_dialog", "Creando BackupRestoreDialog", {
                "has_core": self.core is not None
            }, "H1")
            dlg = BackupRestoreDialog(self.core, self)
            log_debug("settings_tab.py:_open_restore:dialog_created", "Dialog creado exitosamente", {}, "H1")
            result = dlg.exec()
            log_debug("settings_tab.py:_open_restore:dialog_closed", "Dialog cerrado", {
                "result": str(result)
            }, "H1")
        except Exception as e:
            log_debug("settings_tab.py:_open_restore:error", "Error al crear/ejecutar dialog", {
                "error": str(e),
                "error_type": type(e).__name__
            }, "H1")
            import traceback
            log_debug("settings_tab.py:_open_restore:traceback", "Traceback completo", {
                "traceback": traceback.format_exc()
            }, "H1")
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Error al abrir diálogo de restauración:\n\n{str(e)}"
            )
    
    def _open_advanced_tools(self):
        """Abre el panel de herramientas avanzadas."""
        from app.dialogs.advanced_tools_dialog import AdvancedToolsDialog
        dlg = AdvancedToolsDialog(self.core, self)
        dlg.exec()
    
    def _create_backup_now(self):
        """Create manual backup immediately."""
        # Optional import - module may not exist
        try:
            from app.utils.backup_engine import BackupEngine
        except ImportError:
            QtWidgets.QMessageBox.warning(
                self,
                "No disponible",
                "El módulo de backup no está disponible"
            )
            return
        
        from pathlib import Path

        # Confirm
        reply = QtWidgets.QMessageBox.question(
            self,
            "Crear Respaldo",
            "¿Desea crear un respaldo completo ahora?\n\n" 
            "Esto puede tardar unos minutos dependiendo del tamaño de la base de datos.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        
        # Show progress
        progress = QtWidgets.QProgressDialog(
            "Creando respaldo...\n\nPor favor espere.",
            None,
            0,
            0,
            self
        )
        progress.setWindowTitle("Respaldo en Progreso")
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        
        # Process events
        QtWidgets.QApplication.processEvents()
        
        try:
            # Create backup engine
            backup_dir = self.backup_dir.text().strip()
            engine = BackupEngine(self.core, backup_dir if backup_dir else None)
            
            # Create backup
            result = engine.create_local_backup(
                include_media=True,
                compress=True,
                encrypt=self.backup_encrypt.isChecked(),
                notes="Respaldo manual creado desde Settings"
            )
            
            progress.close()
            
            if result.get('success'):
                size_mb = result['size'] / (1024 * 1024)
                msg = f"✅ Respaldo creado exitosamente\n\n"
                msg += f"Archivo: {Path(result['backup_path']).name}\n"
                msg += f"Tamaño: {size_mb:.2f} MB\n"
                msg += f"Checksum: {result['checksum'][:16]}...\n"
                
                QtWidgets.QMessageBox.information(
                    self,
                    "Respaldo Completado",
                    msg
                )
            else:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"No se pudo crear el respaldo:\n\n{result.get('error', 'Error desconocido')}"
                )
        
        except Exception as e:
            progress.close()
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Error al crear respaldo:\n\n{str(e)}"
            )
    
    # =========================================================================
    # MIDAS Loyalty System Helper Methods
    # =========================================================================
    
    def _load_loyalty_rules(self):
        """Load loyalty rules from database into table"""
        try:
            if not self.core.db:
                logger.warning("Database not available")
                return
            self.rules_table.setRowCount(0)

            # Query loyalty rules directly from database
            rules = self.core.db.execute_query('''
                SELECT regla_id, nombre_display, condicion_tipo, multiplicador, activo, prioridad
                FROM loyalty_rules
                ORDER BY prioridad DESC, regla_id ASC
            ''')
            
            self.rules_table.setRowCount(len(rules))
            
            for i, rule in enumerate(rules):
                if isinstance(rule, dict):
                    regla_id = rule.get('regla_id')
                    nombre_display = rule.get('nombre_display')
                    condicion_tipo = rule.get('condicion_tipo')
                    multiplicador = rule.get('multiplicador')
                    activo = rule.get('activo')
                    prioridad = rule.get('prioridad')
                else:
                    regla_id = rule[0]
                    nombre_display = rule[1]
                    condicion_tipo = rule[2]
                    multiplicador = rule[3]
                    activo = rule[4]
                    prioridad = rule[5]
                
                self.rules_table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(regla_id)))
                self.rules_table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(nombre_display)))
                self.rules_table.setItem(i, 2, QtWidgets.QTableWidgetItem(str(condicion_tipo)))
                self.rules_table.setItem(i, 3, QtWidgets.QTableWidgetItem(f"{float(multiplicador) * 100:.1f}%"))
                self.rules_table.setItem(i, 4, QtWidgets.QTableWidgetItem("✓" if activo else "✗"))
                self.rules_table.setItem(i, 5, QtWidgets.QTableWidgetItem(str(prioridad)))
            
        except Exception as e:
            print(f"Error loading loyalty rules: {e}")
            QtWidgets.QMessageBox.warning(self, "Error", f"No se pudieron cargar las reglas: {e}")
    
    def _load_midas_stats(self):
        """Load and display MIDAS system statistics"""
        try:
            if not self.core.db:
                logger.warning("Database not available")
                return
            # Get accounts count by status
            result = self.core.db.execute_query("SELECT status, COUNT(*) as count FROM loyalty_accounts GROUP BY status")
            status_counts = {}
            for row in result:
                if isinstance(row, dict):
                    status_counts[row.get('status')] = row.get('count', 0)
                else:
                    status_counts[row[0]] = row[1]
            
            # Get tier distribution
            result = self.core.db.execute_query("SELECT nivel_lealtad, COUNT(*) as count FROM loyalty_accounts GROUP BY nivel_lealtad")
            tier_counts = {}
            for row in result:
                if isinstance(row, dict):
                    tier_counts[row.get('nivel_lealtad')] = row.get('count', 0)
                else:
                    tier_counts[row[0]] = row[1]
            
            # Get total points in circulation
            result = self.core.db.execute_query("SELECT COALESCE(SUM(saldo_actual), 0) as total FROM loyalty_accounts")
            if result:
                row = result[0]
                total_points = row.get('total', 0) if isinstance(row, dict) else (row[0] or 0)
            else:
                total_points = 0
            
            # Get total transactions this month
            # Use CAST for PostgreSQL compatibility
            # CURRENT_DATE - INTERVAL '1 month' equivalent: first day of current month
            from datetime import datetime
            first_day = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            result = self.core.db.execute_query("""
                SELECT COUNT(*) as count FROM loyalty_ledger 
                WHERE CAST(fecha_hora AS DATE) >= %s
            """, (first_day,))
            if result:
                row = result[0]
                monthly_txns = row.get('count', 0) if isinstance(row, dict) else row[0]
            else:
                monthly_txns = 0
            
            # Format stats
            stats_html = "<div style='line-height: 1.8;'>"
            stats_html += "<p><b>📊 Estado General:</b></p>"
            stats_html += f"<p>  • Cuentas Activas: {status_counts.get('ACTIVE', 0)}</p>"
            stats_html += f"<p>  • Cuentas Suspendidas: {status_counts.get('SUSPENDED', 0)}</p>"
            stats_html += f"<p>  • Puntos en Circulación: ${total_points:,.2f}</p>"
            stats_html += f"<p>  • Transacciones este Mes: {monthly_txns}</p>"
            stats_html += "<p><b>🎖️ Distribución por Nivel:</b></p>"
            stats_html += f"<p>  • 🥉 BRONCE: {tier_counts.get('BRONCE', 0)}</p>"
            stats_html += f"<p>  • 🥈 PLATA: {tier_counts.get('PLATA', 0)}</p>"
            stats_html += f"<p>  • 🥇 ORO: {tier_counts.get('ORO', 0)}</p>"
            stats_html += f"<p>  • 💎 PLATINO: {tier_counts.get('PLATINO', 0)}</p>"
            stats_html += "</div>"
            
            self.midas_stats_label.setText(stats_html)
            
        except Exception as e:
            print(f"Error loading MIDAS stats: {e}")
            self.midas_stats_label.setText(f"Error al cargar estadísticas: {e}")
    
    def _add_loyalty_rule(self):
        """Add a new loyalty rule"""
        if not self.core.db:
            logger.warning("Database not available")
            QtWidgets.QMessageBox.warning(self, "Error", "Base de datos no disponible")
            return
        dialog = LoyaltyRuleDialog(self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            rule_data = dialog.get_data()
            try:
                self.core.db.execute_write('''
                    INSERT INTO loyalty_rules (regla_id, nombre_display, condicion_tipo, 
                                              condicion_valor, multiplicador, activo, prioridad)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', (
                    rule_data['regla_id'],
                    rule_data['nombre_display'],
                    rule_data['condicion_tipo'],
                    rule_data['condicion_valor'],
                    rule_data['multiplicador'],
                    1,  # activo
                    rule_data['prioridad']
                ))
                
                QtWidgets.QMessageBox.information(self, "Éxito", "Regla creada correctamente")
                self._load_loyalty_rules()
                
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo crear la regla: {e}")
    
    def _edit_loyalty_rule(self):
        """Edit selected loyalty rule"""
        if not self.core.db:
            logger.warning("Database not available")
            QtWidgets.QMessageBox.warning(self, "Error", "Base de datos no disponible")
            return
        row = self.rules_table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.warning(self, "Selección", "Selecciona una regla para editar")
            return

        rule_id = self.rules_table.item(row, 0).text()

        # Get current rule data
        try:
            result = self.core.db.execute_query("SELECT * FROM loyalty_rules WHERE regla_id = %s", (rule_id,))
            if not result:
                QtWidgets.QMessageBox.warning(self, "Error", "Regla no encontrada")
                return
            
            rule_row = result[0]
            if isinstance(rule_row, dict):
                rule = rule_row
            else:
                # Convert tuple to dict
                columns = ['regla_id', 'nombre_display', 'condicion_tipo', 'condicion_valor', 
                          'multiplicador', 'activo', 'prioridad']
                rule = dict(zip(columns, rule_row))
            
            dialog = LoyaltyRuleDialog(self, rule)
            if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                rule_data = dialog.get_data()
                self.core.db.execute_write('''
                    UPDATE loyalty_rules SET 
                        nombre_display = %s, condicion_tipo = %s, condicion_valor = %s,
                        multiplicador = %s, prioridad = %s
                    WHERE regla_id = %s
                ''', (
                    rule_data['nombre_display'],
                    rule_data['condicion_tipo'],
                    rule_data['condicion_valor'],
                    rule_data['multiplicador'],
                    rule_data['prioridad'],
                    rule_id
                ))
                
                QtWidgets.QMessageBox.information(self, "Éxito", "Regla actualizada correctamente")
                self._load_loyalty_rules()
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo editar la regla: {e}")
    
    def _del_loyalty_rule(self):
        """Delete selected loyalty rule"""
        if not self.core.db:
            logger.warning("Database not available")
            QtWidgets.QMessageBox.warning(self, "Error", "Base de datos no disponible")
            return
        row = self.rules_table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.warning(self, "Selección", "Selecciona una regla para eliminar")
            return

        rule_id = self.rules_table.item(row, 0).text()
        rule_name = self.rules_table.item(row, 1).text()
        
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirmar Eliminación",
            f"¿Estás seguro de eliminar la regla '{rule_name}'?\n\n"
            "Esta acción no se puede deshacer.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            try:
                self.core.db.execute_write("DELETE FROM loyalty_rules WHERE regla_id = %s", (rule_id,))
                
                QtWidgets.QMessageBox.information(self, "Éxito", "Regla eliminada correctamente")
                self._load_loyalty_rules()
                
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo eliminar la regla: {e}")
