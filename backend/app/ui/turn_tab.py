from __future__ import annotations

import logging

from PyQt6 import QtCore, QtGui, QtWidgets

from app.core import STATE, POSCore
from app.utils import permissions

# Optional import - module may not exist
try:
    from app.utils.backup_engine import BackupEngine
except ImportError:
    BackupEngine = None

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

from app.dialogs.turn_close_dialog import TurnCloseDialog
from app.dialogs.turn_open_dialog import TurnOpenDialog
from app.dialogs.turn_partial_dialog import TurnPartialDialog
from app.services.cash_expenses import CashExpenses
from app.utils import ticket_engine
from app.utils.export_csv import export_turn_to_csv
from app.utils.theme_manager import theme_manager

logger = logging.getLogger(__name__)


class TurnTab(QtWidgets.QWidget):
    def __init__(self, core: POSCore, parent: QtWidgets.QWidget | None = None, *, backup_engine: BackupEngine | None = None):
        super().__init__(parent)
        self.core = core
        self.backup_engine = backup_engine
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
                        "hypothesisId": "TURN_TAB_INIT",
                        "location": "app/ui/turn_tab.py:__init__",
                        "message": "TurnTab initialized",
                        "data": {},
                        "timestamp": int(__import__("time").time() * 1000)
                    }) + "\n")
            except Exception as e:
                logger.debug("Writing debug log for turn tab init: %s", e)
        # #endregion
        self.refresh()

    def load_assets(self):
        self.icons = {}
        try:
            self.icons["shifts"] = QtGui.QIcon("assets/icon_shifts.png")
            self.icons["add"] = QtGui.QIcon("assets/icon_add.png")
            self.icons["money"] = QtGui.QIcon("assets/icon_money.png")
            self.icons["exit"] = QtGui.QIcon("assets/icon_exit.png")
        except Exception as e:
            pass  # Icons are optional, fail silently

    def _build_ui(self) -> None:
        theme = (self.core.get_app_config() or {}).get("theme", "Light")
        c = theme_manager.get_colors(theme)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # === HEADER ===
        self.header = QtWidgets.QFrame()
        self.header.setFixedHeight(70)
        
        header_layout = QtWidgets.QHBoxLayout(self.header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        
        if "shifts" in self.icons:
            icon_lbl = QtWidgets.QLabel()
            icon_lbl.setPixmap(self.icons["shifts"].pixmap(32, 32))
            header_layout.addWidget(icon_lbl)
            
        self.title_label = QtWidgets.QLabel("GESTIÓN DE TURNOS")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        
        main_layout.addWidget(self.header)
        
        # === CONTENEDOR PRINCIPAL ===
        self.content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)
        
        # === BARRA DE ACCIONES ===
        self.actions_card = QtWidgets.QFrame()
        actions_layout = QtWidgets.QHBoxLayout(self.actions_card)
        actions_layout.setContentsMargins(15, 15, 15, 15)
        actions_layout.setSpacing(15)
        
        self.action_buttons_data = []
        
        def make_btn(text, icon_key, color_key, callback):
            btn = QtWidgets.QPushButton(f" {text}")
            if icon_key in self.icons:
                btn.setIcon(self.icons[icon_key])
                btn.setIconSize(QtCore.QSize(20, 20))
            btn.clicked.connect(callback)
            btn.setFixedHeight(45)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self.action_buttons_data.append((btn, color_key))
            return btn
            
        self.open_btn = make_btn("Abrir Turno", "add", 'btn_success', self._open_turn)
        self.partial_btn = make_btn("Corte Parcial", "money", 'btn_primary', self._partial)
        self.close_btn = make_btn("Cerrar Turno", "exit", 'btn_danger', self._close_turn)
        self.expense_btn = make_btn("Registrar Gasto", "money", 'btn_warning', self._register_expense)
        
        actions_layout.addWidget(self.open_btn)
        actions_layout.addWidget(self.partial_btn)
        actions_layout.addWidget(self.close_btn)
        actions_layout.addWidget(self.expense_btn)
        actions_layout.addStretch()
        
        content_layout.addWidget(self.actions_card)
        
        # === RESUMEN DEL TURNO ===
        self.summary_card = QtWidgets.QFrame()
        summary_layout = QtWidgets.QVBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(20, 20, 20, 20)
        
        self.summary_lbl = QtWidgets.QLabel("💼 Sin turno activo")
        summary_layout.addWidget(self.summary_lbl)
        
        content_layout.addWidget(self.summary_card)
        
        # === TABLA DE MOVIMIENTOS ===
        self.table_card = QtWidgets.QFrame()
        table_layout = QtWidgets.QVBoxLayout(self.table_card)
        table_layout.setContentsMargins(0, 0, 0, 0)
        
        # Título de tabla
        self.table_title = QtWidgets.QLabel("📋 Movimientos de Efectivo")
        table_layout.addWidget(self.table_title)

        self.movements = QtWidgets.QTableWidget(0, 4)
        self.movements.setHorizontalHeaderLabels(["Fecha", "Tipo", "Monto", "Motivo"])
        self.movements.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.movements.setAlternatingRowColors(False)
        self.movements.verticalHeader().setVisible(False)
        self.movements.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.movements.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        
        table_layout.addWidget(self.movements)
        
        content_layout.addWidget(self.table_card, 1)
        main_layout.addWidget(self.content_widget)
        
        self.update_theme()

    def refresh(self) -> None:
        turn = self.core.get_current_turn(STATE.branch_id, STATE.user_id)
        if not turn:
            self.summary_lbl.setText("💼 Sin turno activo")
            self.movements.setRowCount(0)
            self.open_btn.setEnabled(True)
            self.partial_btn.setEnabled(False)
            self.close_btn.setEnabled(False)
            return
            
        self.open_btn.setEnabled(False)
        self.partial_btn.setEnabled(True)
        self.close_btn.setEnabled(True)

        summary = self.core.get_turn_summary(turn["id"])
        
        # Extract all financial details
        initial_cash = summary.get('initial_cash', 0)
        cash_sales = summary.get('cash_sales', 0)
        total_in = summary.get('total_in', 0)
        total_out = summary.get('total_out', 0)
        total_expenses = summary.get('total_expenses', 0)
        expenses_count = summary.get('expenses_count', 0)
        expected_cash = summary.get('expected_cash', 0)
        
        summary_text = f"""
        🔑 Turno #{turn['id']} - ACTIVO
        
        💰 Fondo Inicial: ${initial_cash:,.2f}
        💵 Ventas Efectivo: ${cash_sales:,.2f}
        📥 Entradas: ${total_in:,.2f}
        📤 Salidas: ${total_out:,.2f}
        💸 Gastos Efectivo: ${total_expenses:,.2f} ({expenses_count} ops)
        ━━━━━━━━━━━━━━━━━━━━━━
        ✅ Efectivo Esperado: ${expected_cash:,.2f}
        """
        
        self.summary_lbl.setText(summary_text.strip())
        
        moves = self.core.get_turn_movements(turn["id"])
        self.movements.setRowCount(0)
        for mov in moves:
            row = self.movements.rowCount()
            self.movements.insertRow(row)
            
            # Style each row based on movement type
            movement_type = mov["movement_type"]
            type_text = "💸 Entrada" if movement_type == "in" else "💳 Salida"
            amount = float(mov['amount'] or 0)
            
            self.movements.setItem(row, 0, QtWidgets.QTableWidgetItem(str(mov["created_at"] if "created_at" in mov.keys() else "")))
            
            # Get theme colors for movement types
            cfg = self.core.read_local_config()
            theme = cfg.get("theme", "Light")
            c = theme_manager.get_colors(theme)
            
            type_item = QtWidgets.QTableWidgetItem(type_text)
            if movement_type == "in":
                type_item.setForeground(QtGui.QColor(c['success']))
            else:
                type_item.setForeground(QtGui.QColor(c['danger']))
            self.movements.setItem(row, 1, type_item)
            
            amount_item = QtWidgets.QTableWidgetItem(f"$ {amount:.2f}")
            amount_font = amount_item.font()
            amount_font.setBold(True)
            amount_item.setFont(amount_font)
            self.movements.setItem(row, 2, amount_item)
            
            self.movements.setItem(row, 3, QtWidgets.QTableWidgetItem(mov["reason"] or ""))

    def _open_turn(self) -> None:
        dlg = TurnOpenDialog(STATE.username or "Usuario", self.core, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted and dlg.result_data:
            try:
                turn_id = self.core.open_turn(STATE.branch_id, STATE.user_id, dlg.result_data["opening_amount"], dlg.result_data.get("notes"))
                ticket_engine.print_turn_open({
                    "id": turn_id,
                    "user": STATE.username or "",
                    "branch": STATE.branch_id,
                    "opening_amount": dlg.result_data["opening_amount"],
                    "notes": dlg.result_data.get("notes"),
                    "opened_at": "",
                })
                # Abrir cajón automáticamente para contar fondo de caja (después de imprimir)
                self._open_drawer()
                QtWidgets.QMessageBox.information(self, "Turno", "Turno abierto")
                self.refresh()
            except Exception as exc:  # noqa: BLE001
                QtWidgets.QMessageBox.critical(self, "Error", str(exc))

    def _partial(self) -> None:
        turn = self.core.get_current_turn(STATE.branch_id, STATE.user_id)
        if not turn:
            QtWidgets.QMessageBox.warning(self, "Turno", "No hay turno abierto")
            return
        summary = self.core.get_turn_summary(turn["id"])
        dlg = TurnPartialDialog(self, summary, self.core)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # Abrir cajón después de corte parcial
            self._open_drawer()
            self.refresh()

    def _open_drawer(self) -> None:
        """Abrir cajón de dinero - se conecta vía impresora de tickets."""
        cfg = self.core.get_app_config() or {}
        if not cfg.get("cash_drawer_enabled"):
            QtWidgets.QMessageBox.information(self, "Cajón", "Habilita el cajón en Configuración → Dispositivos")
            return
        printer = cfg.get("printer_name") or ""
        if not printer:
            QtWidgets.QMessageBox.warning(self, "Cajón", "Configura una impresora primero.\nEl cajón se conecta a la impresora de tickets.")
            return
        pulse_str = cfg.get("cash_drawer_pulse_bytes", "\\x1B\\x70\\x00\\x19\\xFA")
        try:
            # La función open_cash_drawer ahora acepta strings directamente
            ticket_engine.open_cash_drawer(printer, pulse_str)
            logging.info("💵 Cajón abierto desde TurnTab")
        except Exception as e:
            logging.exception("No se pudo abrir el cajón")
            QtWidgets.QMessageBox.critical(self, "Cajón", f"No se pudo abrir el cajón:\n{e}")

    def _close_turn(self) -> None:
        turn = self.core.get_current_turn(STATE.branch_id, STATE.user_id)
        if not turn:
            QtWidgets.QMessageBox.information(self, "Turno", "No hay turno abierto")
            return
        summary = self.core.get_turn_summary(turn["id"])
        dlg = TurnCloseDialog(summary, self.core, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted and dlg.result_data:
            try:
                self.core.close_turn(turn["id"], dlg.result_data["closing_amount"], dlg.result_data.get("notes"))
                # Abrir cajón para contar efectivo al cerrar
                self._open_drawer()
                # Optionally create backup after close
                if self.backup_engine:
                    self.backup_engine.auto_backup_flow()
                QtWidgets.QMessageBox.information(self, "Turno", "Turno cerrado")
                self.refresh()
            except Exception as exc:
                logging.exception("Error closing turn")
                QtWidgets.QMessageBox.critical(self, "Error", str(exc))

    def _register_expense(self) -> None:
        """Abre diálogo para registrar gasto en efectivo."""
        # Crear diálogo simple
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("💸 Registrar Gasto en Efectivo")
        dlg.setMinimumWidth(400)
        
        layout = QtWidgets.QVBoxLayout(dlg)
        
        # Categoría
        cat_layout = QtWidgets.QHBoxLayout()
        cat_layout.addWidget(QtWidgets.QLabel("Categoría:"))
        cat_combo = QtWidgets.QComboBox()
        cat_combo.addItems([
            "mercancia - Productos para venta",
            "insumos - Materiales de operación",
            "servicios - Plomero, electricista, etc.",
            "transporte - Fletes, gasolina",
            "comida - Comidas del personal",
            "propinas - Propinas, favores",
            "mantenimiento - Reparaciones",
            "otros - Misceláneos"
        ])
        cat_layout.addWidget(cat_combo)
        layout.addLayout(cat_layout)
        
        # Monto
        amount_layout = QtWidgets.QHBoxLayout()
        amount_layout.addWidget(QtWidgets.QLabel("Monto: $"))
        amount_input = QtWidgets.QDoubleSpinBox()
        amount_input.setRange(0.01, 999999.99)
        amount_input.setDecimals(2)
        amount_input.setValue(100.00)
        amount_layout.addWidget(amount_input)
        layout.addLayout(amount_layout)
        
        # Descripción
        desc_layout = QtWidgets.QHBoxLayout()
        desc_layout.addWidget(QtWidgets.QLabel("Descripción:"))
        desc_input = QtWidgets.QLineEdit()
        desc_input.setPlaceholderText("Ej: Frutas del mercado, plomero, etc.")
        desc_layout.addWidget(desc_input)
        layout.addLayout(desc_layout)
        
        # Proveedor (opcional)
        vendor_layout = QtWidgets.QHBoxLayout()
        vendor_layout.addWidget(QtWidgets.QLabel("Proveedor:"))
        vendor_input = QtWidgets.QLineEdit()
        vendor_input.setPlaceholderText("(Opcional) Nombre del proveedor")
        vendor_layout.addWidget(vendor_input)
        layout.addLayout(vendor_layout)
        
        # Botones
        btn_layout = QtWidgets.QHBoxLayout()
        cancel_btn = QtWidgets.QPushButton("Cancelar")
        cancel_btn.clicked.connect(dlg.reject)
        save_btn = QtWidgets.QPushButton("💾 Guardar Gasto")
        save_btn.setStyleSheet("background: #e74c3c; color: white; font-weight: bold; padding: 10px;")
        save_btn.clicked.connect(dlg.accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)
        
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            try:
                expenses = CashExpenses(self.core)
                category = cat_combo.currentText().split(" - ")[0]
                result = expenses.register_expense(
                    category=category,
                    amount=amount_input.value(),
                    description=desc_input.text(),
                    vendor_name=vendor_input.text() if vendor_input.text() else None,
                    user_id=STATE.user_id
                )
                
                if result.get('success'):
                    # Abrir cajón después de registrar gasto
                    self._open_drawer()
                    QtWidgets.QMessageBox.information(
                        self, "Gasto Registrado",
                        f"✅ Gasto de ${amount_input.value():.2f} registrado\n"
                        f"Categoría: {category}"
                    )
                else:
                    QtWidgets.QMessageBox.warning(self, "Error", result.get('error', 'Error desconocido'))
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Error al registrar: {e}")

    def update_theme(self) -> None:
        cfg = self.core.read_local_config()
        theme = cfg.get("theme", "Light")
        c = theme_manager.get_colors(theme)
        
        self.setStyleSheet(f"background-color: {c['bg_main']}; color: {c['text_primary']};")
        
        if hasattr(self, "header"):
            self.header.setStyleSheet(f"""
                QFrame {{
                    background: {c['bg_secondary']};
                    border-bottom: 2px solid {c['accent']};
                }}
            """)
            
        if hasattr(self, "title_label"):
            self.title_label.setStyleSheet(f"color: {c['text_primary']}; font-size: 20px; font-weight: 800; letter-spacing: 1px; background: transparent;")
            
        if hasattr(self, "content_widget"):
            self.content_widget.setStyleSheet(f"background-color: {c['bg_main']};")
            
        if hasattr(self, "actions_card"):
            self.actions_card.setStyleSheet(f"""
                QFrame {{
                    background: {c['bg_secondary']};
                    border: 1px solid {c['border']};
                    border-bottom: 2px solid {c['accent']};
                    border-radius: 10px;
                }}
            """)
            
        if hasattr(self, "action_buttons_data"):
            for btn, color_key in self.action_buttons_data:
                color = c.get(color_key, color_key)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {color}; color: white; border: none;
                        border-radius: 8px; padding: 0 20px; font-weight: bold; font-size: 14px;
                    }}
                    QPushButton:hover {{ opacity: 0.9; }}
                """)
                
        if hasattr(self, "summary_card"):
            self.summary_card.setStyleSheet(f"""
                QFrame {{
                    background: {c['bg_secondary']};
                    border: 1px solid {c['border']};
                    border-left: 5px solid {c['accent']};
                    border-radius: 10px;
                }}
            """)
            
        if hasattr(self, "summary_lbl"):
            self.summary_lbl.setStyleSheet(f"font-size: 16px; color: {c['text_primary']}; font-weight: 500;")
            
        if hasattr(self, "table_card"):
            self.table_card.setStyleSheet(f"""
                QFrame {{
                    background: {c['bg_secondary']};
                    border: 1px solid {c['border']};
                    border-bottom: 2px solid {c['accent']};
                    border-radius: 10px;
                }}
            """)
            
        if hasattr(self, "table_title"):
            self.table_title.setStyleSheet(f"font-weight: bold; color: {c['text_secondary']}; font-size: 14px; padding: 15px;")
            
        if hasattr(self, "movements"):
            self.movements.setStyleSheet(f"""
                QTableWidget {{
                    background: {c['bg_main']}; border: none;
                    gridline-color: transparent; font-size: 13px; color: {c['text_primary']};
                }}
                QHeaderView::section {{
                    background: {c['table_header_bg']};
                    color: {c['table_header_text']}; padding: 12px; border: none;
                    border-bottom: 1px solid {c['border']};
                    font-weight: bold; font-size: 12px;
                }}
                QTableWidget::item {{ padding: 10px; border-bottom: 1px solid {c['border']}; color: {c['text_primary']}; }}
            """)

        # Force style update
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
    
    def showEvent(self, event):
        """Aplicar tema cuando se muestra el tab."""
        super().showEvent(event)
        if hasattr(self, 'update_theme'):
            self.update_theme()