from __future__ import annotations

from typing import Any

from PyQt6 import QtCore, QtGui, QtWidgets

from app.core import STATE, POSCore
from app.dialogs.layaway_detail_dialog import LayawayDetailDialog
from app.dialogs.layaway_payment_dialog import LayawayPaymentDialog
from app.utils import ticket_engine
from app.utils.export_csv import export_layaways_to_csv
from app.utils.theme_manager import theme_manager


class LayawaysTab(QtWidgets.QWidget):
    def __init__(self, core: POSCore, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.core = core
        self._layaways_cache: list[QtCore.QObject] | list[dict] = []
        self.load_assets()
        self._build_ui()
        self.refresh_layaways()

    def load_assets(self):
        self.icons = {}
        try:
            self.icons["layaway"] = QtGui.QIcon("assets/icon_products.png")
            self.icons["add"] = QtGui.QIcon("assets/icon_add.png")
            self.icons["money"] = QtGui.QIcon("assets/icon_money.png")
            self.icons["cancel"] = QtGui.QIcon("assets/icon_exit.png")
            self.icons["deliver"] = QtGui.QIcon("assets/icon_shifts.png")
        except Exception as e:
            pass  # Icons are optional, fail silently

    def _build_ui(self) -> None:
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === HEADER ===
        self.header = QtWidgets.QFrame()
        self.header.setFixedHeight(70)
        header_layout = QtWidgets.QHBoxLayout(self.header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        
        if "layaway" in self.icons:
            icon_lbl = QtWidgets.QLabel()
            icon_lbl.setPixmap(self.icons["layaway"].pixmap(32, 32))
            header_layout.addWidget(icon_lbl)
            
        self.title_label = QtWidgets.QLabel("GESTIÓN DE APARTADOS")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        
        main_layout.addWidget(self.header)

        # === CONTENEDOR PRINCIPAL ===
        self.content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)

        # === DASHBOARD DE CONTROL ===
        self.dashboard_frame = QtWidgets.QFrame()
        dashboard_layout = QtWidgets.QVBoxLayout(self.dashboard_frame)
        dashboard_layout.setContentsMargins(15, 15, 15, 15)
        dashboard_layout.setSpacing(15)
        
        # --- FILA 1: Filtros y Búsqueda ---
        row1 = QtWidgets.QHBoxLayout()
        row1.setSpacing(15)
        
        # Filtro Estado
        self.lbl_status = QtWidgets.QLabel("Estado:")
        row1.addWidget(self.lbl_status)
        
        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.addItems(["Todos", "Pendiente", "Liquidado", "Cancelado", "Vencido"])
        self.status_filter.currentIndexChanged.connect(self.refresh_layaways)
        self.status_filter.setFixedHeight(40)
        row1.addWidget(self.status_filter)
        
        # Filtro Cliente
        self.customer_search = QtWidgets.QLineEdit()
        self.customer_search.setPlaceholderText("🔍 Filtrar por cliente...")
        self.customer_search.setFixedHeight(40)
        self.customer_search.textChanged.connect(self.refresh_layaways)
        row1.addWidget(self.customer_search, 1)
        
        dashboard_layout.addLayout(row1)
        
        # --- FILA 2: Fechas y Botones ---
        row2 = QtWidgets.QHBoxLayout()
        row2.setSpacing(15)
        
        self.lbl_from = QtWidgets.QLabel("Desde:")
        self.date_from = QtWidgets.QDateEdit(QtCore.QDate.currentDate().addMonths(-1))
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.setCalendarPopup(True)
        self.date_from.setFixedHeight(40)
        self.date_from.dateChanged.connect(self.refresh_layaways)
        
        self.lbl_to = QtWidgets.QLabel("Hasta:")
        self.date_to = QtWidgets.QDateEdit(QtCore.QDate.currentDate())
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setCalendarPopup(True)
        self.date_to.setFixedHeight(40)
        self.date_to.dateChanged.connect(self.refresh_layaways)
        
        row2.addWidget(self.lbl_from)
        row2.addWidget(self.date_from)
        row2.addWidget(self.lbl_to)
        row2.addWidget(self.date_to)
        
        # Botones
        self.action_buttons_data = []
        
        def make_btn(text, icon_key, color_key, callback):
            btn = QtWidgets.QPushButton(f" {text}")
            if icon_key in self.icons:
                btn.setIcon(self.icons[icon_key])
                btn.setIconSize(QtCore.QSize(18, 18))
            btn.clicked.connect(callback)
            btn.setFixedHeight(40)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self.action_buttons_data.append((btn, color_key))
            return btn
            
        self.btn_new = make_btn("Nuevo Apartado", "add", "btn_success", self.new_layaway)
        self.btn_pay = make_btn("Abonar", "money", "btn_primary", self.add_payment)
        self.btn_cancel = make_btn("Cancelar", "cancel", "btn_danger", self.cancel_layaway)
        self.btn_deliver = make_btn("Entregar", "deliver", "#9b59b6", self.deliver_layaway)
        
        row2.addStretch()
        row2.addWidget(self.btn_new)
        row2.addWidget(self.btn_pay)
        row2.addWidget(self.btn_cancel)
        row2.addWidget(self.btn_deliver)
        
        dashboard_layout.addLayout(row2)
        content_layout.addWidget(self.dashboard_frame)
        
        # === CONTENIDO PRINCIPAL (SPLITTER VERTICAL) ===
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.splitter.setHandleWidth(1)
        
        # --- TABLA APARTADOS ---
        self.table_card = QtWidgets.QFrame()
        table_layout = QtWidgets.QVBoxLayout(self.table_card)
        table_layout.setContentsMargins(0, 0, 0, 0)
        
        self.table = QtWidgets.QTableWidget(0, 7)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)  # Read-only
        self.table.setHorizontalHeaderLabels(["ID", "Fecha", "Cliente", "Total", "Pagado", "Saldo", "Estado"])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.refresh_items)
        self.table.doubleClicked.connect(self._open_detail)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        table_layout.addWidget(self.table)
        self.splitter.addWidget(self.table_card)
        
        # --- DETALLE (ITEMS + PAGOS + ACCIONES) ---
        self.detail_widget = QtWidgets.QWidget()
        detail_layout = QtWidgets.QVBoxLayout(self.detail_widget)
        detail_layout.setContentsMargins(0, 10, 0, 0)
        detail_layout.setSpacing(10)
        
        # Tablas de detalle
        tables_layout = QtWidgets.QHBoxLayout()
        
        # Items
        self.items_group = QtWidgets.QGroupBox("📦 Productos Apartados")
        items_layout = QtWidgets.QVBoxLayout(self.items_group)
        self.items_table = QtWidgets.QTableWidget(0, 4)
        self.items_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)  # Read-only
        self.items_table.setHorizontalHeaderLabels(["Producto", "Cantidad", "Precio", "Total"])
        self.items_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.items_table.verticalHeader().setVisible(False)
        items_layout.addWidget(self.items_table)
        tables_layout.addWidget(self.items_group, 3)
        
        # Pagos
        self.payments_group = QtWidgets.QGroupBox("💰 Historial de Pagos")
        payments_layout = QtWidgets.QVBoxLayout(self.payments_group)
        self.payments_table = QtWidgets.QTableWidget(0, 3)
        self.payments_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)  # Read-only
        self.payments_table.setHorizontalHeaderLabels(["Fecha", "Monto", "Notas"])
        self.payments_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.payments_table.verticalHeader().setVisible(False)
        payments_layout.addWidget(self.payments_table)
        tables_layout.addWidget(self.payments_group, 2)
        
        detail_layout.addLayout(tables_layout)
        
        # Botones de Acción (Outline)
        btn_layout = QtWidgets.QHBoxLayout()
        
        self.outline_buttons_data = []
        
        def make_outline_btn(text, icon_key, color, callback):
            btn = QtWidgets.QPushButton(f" {text}")
            if icon_key in self.icons:
                btn.setIcon(self.icons[icon_key])
                btn.setIconSize(QtCore.QSize(18, 18))
            btn.clicked.connect(callback)
            btn.setFixedHeight(40)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self.outline_buttons_data.append((btn, color))
            return btn
            
        self.pay_btn = make_outline_btn("Registrar Abono", "money", "#27ae60", self._register_payment)
        self.liquidate_btn = make_outline_btn("Liquidar Apartado", "add", "#2980b9", self._liquiCAST)
        self.cancel_btn = make_outline_btn("Cancelar Apartado", "cancel", "#c0392b", self._cancel)
        
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.pay_btn)
        btn_layout.addWidget(self.liquidate_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        detail_layout.addLayout(btn_layout)
        
        self.splitter.addWidget(self.detail_widget)
        self.splitter.setStretchFactor(0, 60)
        self.splitter.setStretchFactor(1, 40)
        
        content_layout.addWidget(self.splitter)
        main_layout.addWidget(self.content_widget)

        self.update_theme()

    def _status_code(self) -> str | None:
        try:
            current_text = self.status_filter.currentText()
        except RuntimeError:
            return "pendiente"

        mapping = {
            "Pendiente": "pendiente",
            "Liquidado": "liquidado",
            "Entregado": "entregado",
            "Cancelado": "cancelado",
            "Vencido": "vencido",
            "Todos": "all",
        }
        return mapping.get(current_text, "pendiente")

    def _selected_layaway(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._layaways_cache):
            return None
        return self._layaways_cache[row]

    def refresh_layaways(self) -> None:
        status = self._status_code()
        date_range = None
        if self.date_from.date().isValid() and self.date_to.date().isValid():
            date_range = (
                self.date_from.date().toString("yyyy-MM-dd"),
                self.date_to.date().toString("yyyy-MM-dd"),
            )
        layaways = self.core.list_layaways(
            branch_id=STATE.branch_id,
            status=status,
            date_range=date_range,
        )
        search = self.customer_search.text().strip().lower()
        if search:
            layaways = [l for l in layaways if search in (l.get("customer_name", "").lower())]
        self._layaways_cache = [dict(l) for l in layaways]
        self.table.setRowCount(len(layaways))
        for row_idx, layaway in enumerate(layaways):
            paid = float(layaway.get("paid_total", 0.0))
            balance = float(layaway.get("balance_calc", layaway.get("balance", 0.0)))
            total = layaway.get("total", paid + balance)  # Safe fallback
            values = [
                layaway["id"],
                layaway.get("created_at", ""),
                layaway["customer_name"] or "",
                f"{total:.2f}",
                f"{paid:.2f}",
                f"{balance:.2f}",
                layaway.get("display_status", layaway.get("status", "")),
            ]
            for col, value in enumerate(values):
                cell = QtWidgets.QTableWidgetItem(str(value))
                cell.setFlags(cell.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                if col in (3, 4, 5):
                    cell.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_idx, col, cell)
        self.items_table.setRowCount(0)
        self.payments_table.setRowCount(0)

    def refresh_items(self) -> None:
        layaway = self._selected_layaway()
        if not layaway:
            return
        layaway_id = layaway["id"]
        items = self.core.get_layaway_items(layaway_id)
        self.items_table.setRowCount(len(items))
        for idx, item in enumerate(items):
            values = [item["name"], f"{item['qty']:.2f}", f"{item['price']:.2f}", f"{item['total']:.2f}"]
            for col, value in enumerate(values):
                cell = QtWidgets.QTableWidgetItem(str(value))
                cell.setFlags(cell.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                self.items_table.setItem(idx, col, cell)

        payments = self.core.get_layaway_payments(layaway_id)
        self.payments_table.setRowCount(len(payments))
        for idx, pay in enumerate(payments):
            values = [pay["timestamp"], f"{pay['amount']:.2f}", pay.get("notes", "") or ""]
            for col, value in enumerate(values):
                cell = QtWidgets.QTableWidgetItem(str(value))
                cell.setFlags(cell.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                self.payments_table.setItem(idx, col, cell)

    def _register_payment(self) -> None:
        layaway = self._selected_layaway()
        if not layaway:
            QtWidgets.QMessageBox.warning(self, "Selecciona", "Selecciona un apartado")
            return
        balance = float(layaway.get("balance_calc", layaway.get("balance", 0.0)))
        if balance <= 0:
            QtWidgets.QMessageBox.information(self, "Sin saldo", "Este apartado no tiene saldo pendiente")
            return
        dialog = LayawayPaymentDialog(
            layaway.get("customer_name") or "Cliente",
            layaway["total"],
            layaway.get("paid_total", layaway.get("deposit", 0)),
            balance,
            self,
        )
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted or not dialog.result_data:
            return
        try:
            self.core.add_layaway_payment(
                layaway["id"], dialog.result_data["amount"], notes=dialog.result_data.get("notes"), user_id=STATE.user_id
            )
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo registrar el abono: {exc}")
            return
        try:
            refreshed = self.core.get_layaway(layaway["id"])
            ticket_engine.print_layaway_payment(
                dict(refreshed or {}),
                {"amount": dialog.result_data["amount"], "notes": dialog.result_data.get("notes")},
            )
        except Exception:
            pass
        self.refresh_layaways()
        self.refresh_items()

    def _cancel(self) -> None:
        layaway = self._selected_layaway()
        if not layaway:
            QtWidgets.QMessageBox.warning(self, "Selecciona", "Selecciona un apartado")
            return
        if QtWidgets.QMessageBox.question(self, "Cancelar", "¿Cancelar este apartado?") != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            self.core.cancel_layaway(layaway["id"])
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo cancelar: {exc}")
            return
        self.refresh_layaways()

    def _liquiCAST(self) -> None:
        layaway = self._selected_layaway()
        if not layaway:
            QtWidgets.QMessageBox.warning(self, "Selecciona", "Selecciona un apartado")
            return
        if QtWidgets.QMessageBox.question(self, "Liquidar", "¿Liquidar y consumir el stock reservado?") != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            self.core.liquidate_layaway(layaway["id"], user_id=STATE.user_id)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo liquidar: {exc}")
            return
        try:
            refreshed = self.core.get_layaway(layaway["id"])
            ticket_engine.print_layaway_liquidation(dict(refreshed or {}))
        except Exception:
            pass
        self.refresh_layaways()

    def _open_detail(self, *_: object) -> None:
        layaway = self._selected_layaway()
        if not layaway:
            return
        dlg = LayawayDetailDialog(self.core, layaway["id"], self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted and dlg.result_action:
            self.refresh_layaways()

    def new_layaway(self) -> None:
        QtWidgets.QMessageBox.information(self, "Nuevo Apartado", 
            "Para crear un nuevo apartado, vaya a la pestaña de Ventas (F1), agregue productos y seleccione 'Apartar'.")

    def add_payment(self) -> None:
        self._register_payment()

    def cancel_layaway(self) -> None:
        self._cancel()

    def deliver_layaway(self) -> None:
        self._liquiCAST()
    def update_theme(self) -> None:
        cfg = self.core.read_local_config()
        theme = cfg.get("theme", "Light")
        c = theme_manager.get_colors(theme)
        
        self.setStyleSheet(f"background-color: {c['bg_main']}; color: {c['text_primary']};")
        
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
            
        if hasattr(self, "dashboard_frame"):
            self.dashboard_frame.setStyleSheet(f"""
                QFrame {{
                    background: {c['bg_card']};
                    border: 1px solid {c['border']};
                    border-bottom: 2px solid {c['border']};
                    border-radius: 10px;
                }}
            """)
            
        if hasattr(self, "lbl_status"):
            self.lbl_status.setStyleSheet(f"font-weight:bold; color:{c['text_secondary']}; font-size: 13px;")
            
        if hasattr(self, "status_filter"):
            self.status_filter.setStyleSheet(f"""
                QComboBox {{ border: 1px solid {c['input_border']}; border-radius: 6px; padding: 5px 10px; background: {c['input_bg']}; font-size: 13px; color: {c['text_primary']}; }}
                QComboBox::drop-down {{ border: none; }}
            """)
            
        if hasattr(self, "customer_search"):
            self.customer_search.setStyleSheet(f"""
                QLineEdit {{
                    background: {c['input_bg']}; border: 1px solid {c['input_border']}; border-radius: 6px; padding: 0 10px; font-size: 13px; color: {c['text_primary']};
                }}
                QLineEdit:focus {{ border: 2px solid {c['input_focus']}; background: {c['bg_card']}; }}
            """)
            
        # Labels fechas
        for lbl in [getattr(self, "lbl_from", None), getattr(self, "lbl_to", None)]:
            if lbl:
                lbl.setStyleSheet(f"font-weight:bold; color:{c['text_secondary']}; font-size: 13px;")
                
        # Date edits
        date_style = f"""
            QDateEdit {{
                border: 1px solid {c['input_border']}; border-radius: 6px; padding: 5px 10px; background: {c['input_bg']}; font-size: 13px; color: {c['text_primary']};
            }}
            QDateEdit::drop-down {{ border: none; }}
        """
        for date_edit in [getattr(self, "date_from", None), getattr(self, "date_to", None)]:
            if date_edit:
                date_edit.setStyleSheet(date_style)
                
        if hasattr(self, "action_buttons_data"):
            for btn, color_key in self.action_buttons_data:
                color = c.get(color_key, color_key)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {color}; color: white; border: none;
                        border-radius: 8px; padding: 0 15px; font-weight: bold; font-size: 13px;
                    }}
                    QPushButton:hover {{ opacity: 0.9; }}
                """)
                
        if hasattr(self, "splitter"):
            self.splitter.setStyleSheet("QSplitter::handle { background: transparent; }")
            
        if hasattr(self, "table_card"):
            self.table_card.setStyleSheet(f"""
                QFrame {{
                    background: {c['bg_card']};
                    border: 1px solid {c['border']};
                    border-bottom: 2px solid {c['border']};
                    border-radius: 10px;
                }}
            """)
            
        if hasattr(self, "table"):
            self.table.setStyleSheet(f"""
                QTableWidget {{
                    background: {c['bg_card']}; border: none; border-radius: 10px;
                    gridline-color: transparent; font-size: 13px;
                }}
                QHeaderView::section {{
                    background: {c['table_header_bg']};
                    color: {c['table_header_text']}; padding: 12px; border: none;
                    border-bottom: 1px solid {c['border']};
                    font-weight: bold; font-size: 12px;
                }}
                QTableWidget::item {{ padding: 10px; border-bottom: 1px solid {c['border']}; color: {c['table_text']}; }}
                QTableWidget::item:selected {{ background: {c['table_selected']}; color: {c['bg_header']}; }}
            """)
            
        # Detail groups
        group_style = f"QGroupBox {{ font-weight: bold; color: {c['text_secondary']}; border: 1px solid {c['border']}; border-radius: 8px; margin-top: 20px; background: {c['bg_card']}; }} QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}"
        if hasattr(self, "items_group"):
            self.items_group.setStyleSheet(group_style)
        if hasattr(self, "payments_group"):
            self.payments_group.setStyleSheet(group_style)
            
        # Detail tables
        detail_table_style = f"""
            QTableWidget {{
                background: {c['bg_card']}; border: none;
                gridline-color: transparent; font-size: 12px;
            }}
            QHeaderView::section {{
                background: {c['table_header_bg']}; padding: 8px; border: none;
                border-bottom: 1px solid {c['border']}; font-weight: bold; color: {c['table_header_text']};
            }}
            QTableWidget::item {{ padding: 6px; border-bottom: 1px solid {c['border']}; color: {c['table_text']}; }}
        """
        if hasattr(self, "items_table"):
            self.items_table.setStyleSheet(detail_table_style)
        if hasattr(self, "payments_table"):
            self.payments_table.setStyleSheet(detail_table_style)
            
        if hasattr(self, "outline_buttons_data"):
            for btn, color in self.outline_buttons_data:
                # Outline buttons use fixed colors for now, or could adapt to theme
                # Keeping original colors but ensuring background matches card
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {c['bg_card']}; color: {color}; border: 1px solid {color};
                        border-radius: 8px; padding: 0 20px; font-weight: bold; font-size: 13px;
                    }}
                    QPushButton:hover {{ background: {color}; color: white; }}
                """)

        # Force style update
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def showEvent(self, event):
        """Apply theme when tab is shown."""
        super().showEvent(event)
        self.update_theme()

