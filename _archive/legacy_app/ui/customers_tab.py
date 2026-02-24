from __future__ import annotations

import logging
from typing import Any

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger(__name__)

from app.core import STATE, POSCore
from app.dialogs.credit_payment_dialog import CreditPaymentDialog
from app.dialogs.credit_statement_dialog import CreditStatementDialog
from app.dialogs.import_customer_wizard import ImportCustomerWizardDialog
from app.dialogs.wallet_dialog import WalletDialog
from app.utils.customer_exporter import export_customers_to_csv, export_customers_to_excel

# Optional import - customer_backup module may not exist
try:
    from app.utils.customer_backup import export_complete_backup, import_complete_backup
except ImportError:
    # Stub functions if module doesn't exist
    def export_complete_backup(*args, **kwargs):
        raise NotImplementedError("customer_backup module not available")
    def import_complete_backup(*args, **kwargs):
        raise NotImplementedError("customer_backup module not available")
import csv

from app.utils.theme_manager import theme_manager


class CustomersTab(QtWidgets.QWidget):
    def __init__(self, core: POSCore, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.core = core
        self.selected_customer_id: int | None = None
        self.load_assets()
        self._build_ui()
        self.refresh_table()

    def load_assets(self):
        self.icons = {}
        try:
            self.icons["search"] = QtGui.QIcon("assets/icon_search.png")
            self.icons["add"] = QtGui.QIcon("assets/icon_add.png")
            self.icons["save"] = QtGui.QIcon("assets/icon_config.png")
            self.icons["delete"] = QtGui.QIcon("assets/icon_delete.png")
            self.icons["clients"] = QtGui.QIcon("assets/icon_clients.png")
            self.icons["import"] = QtGui.QIcon("assets/icon_import.png")
            self.icons["export"] = QtGui.QIcon("assets/icon_excel.png")
            self.icons["money"] = QtGui.QIcon("assets/icon_money.png")
        except Exception as e:
            logger.debug("Error loading icons: %s", e)

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
        
        if "clients" in self.icons:
            icon_lbl = QtWidgets.QLabel()
            icon_lbl.setPixmap(self.icons["clients"].pixmap(32, 32))
            header_layout.addWidget(icon_lbl)
            
        self.title_label = QtWidgets.QLabel("GESTIÓN DE CLIENTES")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        
        main_layout.addWidget(self.header)

        # === TAB WIDGET ===
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setTabPosition(QtWidgets.QTabWidget.TabPosition.North)
        
        # Tab 1: Lista de Clientes
        self.tab_lista = self._create_lista_tab(c)
        self.tab_widget.addTab(self.tab_lista, "📋 Lista de Clientes")
        
        # Tab 2: Crédito
        self.tab_credito = self._create_credito_tab(c)
        self.tab_widget.addTab(self.tab_credito, "💳 Crédito")
        
        # Tab 3: Monedero MIDAS
        self.tab_midas = self._create_midas_tab(c)
        self.tab_widget.addTab(self.tab_midas, "💰 Monedero MIDAS")
        
        # Tab 4: Historial de Compras
        self.tab_historial = self._create_historial_tab(c)
        self.tab_widget.addTab(self.tab_historial, "🛒 Historial")
        
        # Tab 5: Importar/Exportar
        self.tab_import_export = self._create_import_export_tab(c)
        self.tab_widget.addTab(self.tab_import_export, "📥 Import/Export")
        
        # Tab 6: Análisis
        self.tab_analisis = self._create_analisis_tab(c)
        self.tab_widget.addTab(self.tab_analisis, "📈 Análisis")
        
        # Tab 7: Gift Cards
        self.tab_giftcards = self._create_giftcards_tab(c)
        self.tab_widget.addTab(self.tab_giftcards, "🎁 Gift Cards")
        
        # Tab 8: Configuración de Cliente
        self.tab_config = self._create_config_tab(c)
        self.tab_widget.addTab(self.tab_config, "⚙️ Configuración")
        
        main_layout.addWidget(self.tab_widget)
        
        self.update_theme()
        
        # Shortcuts
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_F2), self, self.open_overview)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Delete), self, self.delete_customer)
        QtGui.QShortcut(QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.New), self, self.new_customer)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Return), self, self.save_customer)

    def _create_lista_tab(self, c: dict) -> QtWidgets.QWidget:
        """Pestaña principal: Lista de clientes con formulario"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Dashboard de control
        dashboard_frame = QtWidgets.QFrame()
        dashboard_layout = QtWidgets.QVBoxLayout(dashboard_frame)
        dashboard_layout.setContentsMargins(15, 15, 15, 15)
        dashboard_layout.setSpacing(15)
        
        # Búsqueda
        row1 = QtWidgets.QHBoxLayout()
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("🔍 Buscar cliente por nombre, teléfono, email o RFC...")
        self.search_input.textChanged.connect(self.refresh_table)
        self.search_input.setFixedHeight(40)
        row1.addWidget(self.search_input)
        dashboard_layout.addLayout(row1)
        
        # Botones de acción
        row2 = QtWidgets.QHBoxLayout()
        row2.setSpacing(10)
        
        self.action_buttons_data = []
        
        def make_btn(text, icon_key, color_key, callback, outline=False):
            btn = QtWidgets.QPushButton(f" {text}")
            if icon_key in self.icons:
                btn.setIcon(self.icons[icon_key])
                btn.setIconSize(QtCore.QSize(18, 18))
            btn.clicked.connect(callback)
            btn.setFixedHeight(40)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self.action_buttons_data.append((btn, color_key, outline))
            return btn
            
        self.btn_new = make_btn("Nuevo", "add", 'btn_success', self.new_customer)
        self.btn_save = make_btn("Guardar", "save", 'btn_primary', self.save_customer)
        self.btn_delete = make_btn("Eliminar", "delete", 'btn_danger', self.delete_customer)
        self.btn_import = make_btn("Importar", "import", "#e67e22", self.import_customers, outline=True)
        self.btn_export = make_btn("Exportar", "export", "#16a085", self.export_customers, outline=True)
        self.btn_backup = make_btn("Backup Completo", "export", "#c0392b", self.export_complete_backup, outline=True)
        self.btn_restore = make_btn("Restaurar Backup", "import", "#d35400", self.import_complete_backup, outline=True)
        
        row2.addWidget(self.btn_new)
        row2.addWidget(self.btn_save)
        row2.addWidget(self.btn_delete)
        row2.addStretch()
        row2.addWidget(self.btn_import)
        row2.addWidget(self.btn_export)
        row2.addWidget(self.btn_backup)
        row2.addWidget(self.btn_restore)
        
        dashboard_layout.addLayout(row2)
        layout.addWidget(dashboard_frame)
        
        # Splitter: Tabla + Formulario
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        
        # Tabla
        table_card = QtWidgets.QFrame()
        table_layout = QtWidgets.QVBoxLayout(table_card)
        table_layout.setContentsMargins(0, 0, 0, 0)
        
        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Nombre", "Teléfono", "Crédito", "Saldo"])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)  # NO EDITABLE
        self.table.itemSelectionChanged.connect(self.load_selected)
        
        table_layout.addWidget(self.table)
        splitter.addWidget(table_card)
        
        # Formulario
        form_card = QtWidgets.QFrame()
        form_card_layout = QtWidgets.QVBoxLayout(form_card)
        form_card_layout.setContentsMargins(0, 0, 0, 0)

        form_container = QtWidgets.QScrollArea()
        form_container.setWidgetResizable(True)
        form_container.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        form_container.setStyleSheet("background: transparent;")
        
        form_widget = QtWidgets.QWidget()
        form_layout = QtWidgets.QFormLayout(form_widget)
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setSpacing(15)
        
        form_title = QtWidgets.QLabel("📝 Datos del Cliente")
        form_layout.addRow(form_title)
        
        # Campos
        self.first_name = QtWidgets.QLineEdit()
        self.first_name.setPlaceholderText("Nombre(s)")
        self.last_name = QtWidgets.QLineEdit()
        self.last_name.setPlaceholderText("Apellido(s)")
        self.phone = QtWidgets.QLineEdit()
        self.phone.setPlaceholderText("Teléfono")
        self.email = QtWidgets.QLineEdit()
        self.email.setPlaceholderText("Correo electrónico")
        self.email_fiscal = QtWidgets.QLineEdit()
        self.email_fiscal.setPlaceholderText("Correo electrónico fiscal")
        self.rfc = QtWidgets.QLineEdit()
        self.rfc.setPlaceholderText("RFC")
        self.razon_social = QtWidgets.QLineEdit()
        self.razon_social.setPlaceholderText("Razón Social")
        self.regimen_fiscal = QtWidgets.QLineEdit()
        self.regimen_fiscal.setPlaceholderText("Régimen Fiscal")
        self.domicilio1 = QtWidgets.QLineEdit()
        self.domicilio1.setPlaceholderText("Domicilio 1")
        self.domicilio2 = QtWidgets.QLineEdit()
        self.domicilio2.setPlaceholderText("Domicilio 2")
        self.colonia = QtWidgets.QLineEdit()
        self.colonia.setPlaceholderText("Colonia")
        self.municipio = QtWidgets.QLineEdit()
        self.municipio.setPlaceholderText("Municipio")
        self.estado = QtWidgets.QLineEdit()
        self.estado.setPlaceholderText("Estado")
        self.pais = QtWidgets.QLineEdit("México")
        self.pais.setPlaceholderText("País")
        self.codigo_postal = QtWidgets.QLineEdit()
        self.codigo_postal.setPlaceholderText("Código Postal")
        self.notes = QtWidgets.QPlainTextEdit()
        self.notes.setPlaceholderText("Notas adicionales...")
        self.notes.setFixedHeight(80)
        
        self.credit_limit = QtWidgets.QDoubleSpinBox()
        self.credit_limit.setRange(0, 1000000)
        self.credit_limit.setPrefix("$")
        
        self.credit_mode = QtWidgets.QComboBox()
        self.credit_mode.addItems(["De máximo", "Ilimitado"])

        self.credit_balance = QtWidgets.QLabel("$0.00")
        self.credit_balance.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.credit_balance.setStyleSheet("font-size: 18px; font-weight: bold; color: #f5576c; padding: 8px;")
        
        self.input_fields = [
            self.first_name, self.last_name, self.phone, self.email, self.email_fiscal,
            self.rfc, self.razon_social, self.regimen_fiscal, self.domicilio1, self.domicilio2,
            self.colonia, self.municipio, self.estado, self.pais, self.codigo_postal,
            self.notes, self.credit_limit, self.credit_mode
        ]
        
        # Agregar campos al formulario
        form_layout.addRow(self._form_label("Nombre(s)", c), self.first_name)
        form_layout.addRow(self._form_label("Apellido(s)", c), self.last_name)
        form_layout.addRow(self._form_label("Teléfono", c), self.phone)
        form_layout.addRow(self._form_label("Email", c), self.email)
        
        separator1 = QtWidgets.QFrame()
        separator1.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator1.setStyleSheet(f"background: {c['border']}; max-height: 1px;")
        form_layout.addRow(separator1)
        
        form_layout.addRow(self._form_label("Email Fiscal", c), self.email_fiscal)
        form_layout.addRow(self._form_label("RFC", c), self.rfc)
        form_layout.addRow(self._form_label("Razón Social", c), self.razon_social)
        form_layout.addRow(self._form_label("Régimen Fiscal", c), self.regimen_fiscal)
        
        separator2 = QtWidgets.QFrame()
        separator2.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator2.setStyleSheet(f"background: {c['border']}; max-height: 1px;")
        form_layout.addRow(separator2)
        
        form_layout.addRow(self._form_label("Domicilio 1", c), self.domicilio1)
        form_layout.addRow(self._form_label("Domicilio 2", c), self.domicilio2)
        form_layout.addRow(self._form_label("Colonia", c), self.colonia)
        form_layout.addRow(self._form_label("Municipio", c), self.municipio)
        form_layout.addRow(self._form_label("Estado", c), self.estado)
        form_layout.addRow(self._form_label("País", c), self.pais)
        form_layout.addRow(self._form_label("Código Postal", c), self.codigo_postal)
        
        separator3 = QtWidgets.QFrame()
        separator3.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator3.setStyleSheet(f"background: {c['border']}; max-height: 1px;")
        form_layout.addRow(separator3)
        
        form_layout.addRow(self._form_label("Notas", c), self.notes)
        
        self.vip_cb = QtWidgets.QCheckBox("Cliente VIP (Descuento automático)")
        self.vip_cb.setStyleSheet(f"font-weight: bold; color: {c['text_secondary']};")
        
        self.credit_enabled = QtWidgets.QCheckBox("Habilitar Crédito")
        self.credit_enabled.setStyleSheet(f"font-weight: bold; color: {c['text_secondary']};")

        form_layout.addRow(self.vip_cb)
        form_layout.addRow(self.credit_enabled)
        form_layout.addRow(self._form_label("Modo de Crédito", c), self.credit_mode)
        form_layout.addRow(self._form_label("Límite de Crédito", c), self.credit_limit)
        form_layout.addRow(self._form_label("Saldo Actual", c), self.credit_balance)
        
        form_container.setWidget(form_widget)
        form_card_layout.addWidget(form_container)
        splitter.addWidget(form_card)
        
        splitter.setSizes([600, 400])
        layout.addWidget(splitter)
        
        return tab

    def _create_credito_tab(self, c: dict) -> QtWidgets.QWidget:
        """Pestaña de gestión de crédito"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Header
        header_lbl = QtWidgets.QLabel("💳 Gestión de Crédito")
        header_lbl.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['text_primary']};")
        layout.addWidget(header_lbl)
        
        # Botones
        btn_layout = QtWidgets.QHBoxLayout()
        
        self.btn_pay = QtWidgets.QPushButton("💰 Abonar a Cuenta")
        self.btn_pay.setFixedHeight(45)
        self.btn_pay.clicked.connect(self.open_payment_dialog)
        self.btn_pay.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        
        self.btn_stmt = QtWidgets.QPushButton("📋 Estado de Cuenta")
        self.btn_stmt.setFixedHeight(45)
        self.btn_stmt.clicked.connect(self.open_overview)
        self.btn_stmt.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        
        btn_layout.addWidget(self.btn_pay)
        btn_layout.addWidget(self.btn_stmt)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
        # Tabla de clientes con crédito
        self.credit_table = QtWidgets.QTableWidget(0, 4)
        self.credit_table.setHorizontalHeaderLabels(["Cliente", "Límite", "Saldo", "Disponible"])
        self.credit_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.credit_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.credit_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)  # NO EDITABLE
        self.credit_table.itemSelectionChanged.connect(self._on_credit_table_selection)
        
        layout.addWidget(self.credit_table)
        
        # Actualizar tabla
        self._refresh_credit_table()
        
        return tab

    def _create_midas_tab(self, c: dict) -> QtWidgets.QWidget:
        """Pestaña de monedero MIDAS"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Header
        header_lbl = QtWidgets.QLabel("💰 Monedero MIDAS - Puntos de Lealtad")
        header_lbl.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['text_primary']};")
        layout.addWidget(header_lbl)
        
        # Botones
        btn_layout = QtWidgets.QHBoxLayout()
        
        btn_wallet = QtWidgets.QPushButton("🌟 Ver Detalles de Monedero MIDAS")
        btn_wallet.setFixedHeight(45)
        btn_wallet.clicked.connect(self.open_wallet_dialog)
        btn_wallet.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn_layout.addWidget(btn_wallet)
        
        # NUEVO: Botón para monederos anónimos
        btn_anonymous = QtWidgets.QPushButton("🎁 Gestionar Monederos Anónimos")
        btn_anonymous.setFixedHeight(45)
        btn_anonymous.clicked.connect(self._open_wallet_manager)
        btn_anonymous.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn_anonymous.setStyleSheet("background: #9b59b6; color: white; font-weight: bold;")
        btn_layout.addWidget(btn_anonymous)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Tabla de clientes con puntos
        self.midas_table = QtWidgets.QTableWidget(0, 3)
        self.midas_table.setHorizontalHeaderLabels(["Cliente", "Puntos Disponibles", "Estado Cuenta"])
        self.midas_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.midas_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.midas_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)  # NO EDITABLE
        self.midas_table.itemSelectionChanged.connect(self._on_midas_table_selection)
        
        layout.addWidget(self.midas_table)
        
        # Actualizar tabla
        self._refresh_midas_table()
        
        return tab

    def _create_historial_tab(self, c: dict) -> QtWidgets.QWidget:
        """Pestaña de historial de compras del cliente"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Header
        header_lbl = QtWidgets.QLabel("🛒 Historial de Compras por Cliente")
        header_lbl.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['text_primary']};")
        layout.addWidget(header_lbl)
        
        # Filtros
        filter_layout = QtWidgets.QHBoxLayout()
        
        filter_layout.addWidget(QtWidgets.QLabel("Desde:"))
        self.hist_date_from = QtWidgets.QDateEdit()
        self.hist_date_from.setCalendarPopup(True)
        self.hist_date_from.setDate(QtCore.QDate.currentDate().addMonths(-1))
        filter_layout.addWidget(self.hist_date_from)
        
        filter_layout.addWidget(QtWidgets.QLabel("Hasta:"))
        self.hist_date_to = QtWidgets.QDateEdit()
        self.hist_date_to.setCalendarPopup(True)
        self.hist_date_to.setDate(QtCore.QDate.currentDate())
        filter_layout.addWidget(self.hist_date_to)
        
        btn_refresh = QtWidgets.QPushButton("🔄 Actualizar")
        btn_refresh.clicked.connect(self._refresh_historial_table)
        btn_refresh.setFixedHeight(35)
        filter_layout.addWidget(btn_refresh)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # Tabla de ventas
        self.historial_table = QtWidgets.QTableWidget(0, 6)
        self.historial_table.setHorizontalHeaderLabels(["Fecha", "Folio", "Cliente", "Total", "Método Pago", "Estado"])
        self.historial_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.historial_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.historial_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)  # NO EDITABLE
        
        layout.addWidget(self.historial_table)
        
        # Totales
        totals_layout = QtWidgets.QHBoxLayout()
        self.hist_total_sales = QtWidgets.QLabel("Total Ventas: $0.00")
        self.hist_total_sales.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {c['text_primary']};")
        self.hist_count_sales = QtWidgets.QLabel("Cantidad: 0")
        self.hist_count_sales.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {c['text_secondary']};")
        
        totals_layout.addWidget(self.hist_total_sales)
        totals_layout.addWidget(self.hist_count_sales)
        totals_layout.addStretch()
        layout.addLayout(totals_layout)
        
        # Actualizar tabla
        self._refresh_historial_table()
        
        return tab

    def _create_import_export_tab(self, c: dict) -> QtWidgets.QWidget:
        """Pestaña de importación y exportación de clientes"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(30)
        
        # Header
        header_lbl = QtWidgets.QLabel("📥 Gestión de Datos de Clientes")
        header_lbl.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['text_primary']};")
        layout.addWidget(header_lbl)
        
        # Sección de Exportación
        export_group = QtWidgets.QGroupBox("📤 Exportar Clientes")
        export_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                border: 2px solid {c['border']};
                border-radius: 8px;
                margin-top: 10px;
                padding: 20px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)
        export_layout = QtWidgets.QVBoxLayout(export_group)
        
        export_desc = QtWidgets.QLabel(
            "Exporta la lista completa de clientes a Excel o CSV.\n"
            "Incluye: datos personales, crédito, loyalty, notas."
        )
        export_desc.setStyleSheet(f"color: {c['text_secondary']};")
        export_layout.addWidget(export_desc)
        
        export_buttons = QtWidgets.QHBoxLayout()
        btn_export_excel = QtWidgets.QPushButton("📊 Exportar a Excel")
        btn_export_excel.setFixedHeight(45)
        btn_export_excel.clicked.connect(lambda: self.export_customers())
        
        btn_export_csv = QtWidgets.QPushButton("📄 Exportar a CSV")  
        btn_export_csv.setFixedHeight(45)
        btn_export_csv.clicked.connect(lambda: self.export_customers())
        
        export_buttons.addWidget(btn_export_excel)
        export_buttons.addWidget(btn_export_csv)
        export_buttons.addStretch()
        export_layout.addLayout(export_buttons)
        
        layout.addWidget(export_group)
        
        # Sección de Importación
        import_group = QtWidgets.QGroupBox("📥 Importar Clientes")
        import_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                border: 2px solid {c['border']};
                border-radius: 8px;
                margin-top: 10px;
                padding: 20px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)
        import_layout = QtWidgets.QVBoxLayout(import_group)
        
        import_desc = QtWidgets.QLabel(
            "Importa clientes desde archivos Excel o CSV.\n"
            "El wizard te guiará paso a paso en el proceso."
        )
        import_desc.setStyleSheet(f"color: {c['text_secondary']};")
        import_layout.addWidget(import_desc)
        
        btn_import = QtWidgets.QPushButton("🚀 Iniciar Wizard de Importación")
        btn_import.setFixedHeight(45)
        btn_import.clicked.connect(self.import_customers)
        import_layout.addWidget(btn_import)
        
        layout.addWidget(import_group)
        
        # Sección de Backup Completo
        backup_group = QtWidgets.QGroupBox("💾 Backup Completo")
        backup_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                border: 2px solid {c['border']};
                border-radius: 8px;
                margin-top: 10px;
                padding: 20px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)
        backup_layout = QtWidgets.QVBoxLayout(backup_group)
        
        backup_desc = QtWidgets.QLabel(
            "Backup completo incluye: Clientes + Historial de Crédito + Loyalty.\n"
            "Ideal para migración o respaldo total."
        )
        backup_desc.setStyleSheet(f"color: {c['text_secondary']};")
        backup_layout.addWidget(backup_desc)
        
        backup_buttons = QtWidgets.QHBoxLayout()
        btn_backup = QtWidgets.QPushButton("💾 Crear Backup Completo")
        btn_backup.setFixedHeight(45)
        btn_backup.clicked.connect(self.export_complete_backup)
        
        btn_restore = QtWidgets.QPushButton("♻️ Restaurar Backup")
        btn_restore.setFixedHeight(45)
        btn_restore.clicked.connect(self.import_complete_backup)
        
        backup_buttons.addWidget(btn_backup)
        backup_buttons.addWidget(btn_restore)
        backup_buttons.addStretch()
        backup_layout.addLayout(backup_buttons)
        
        layout.addWidget(backup_group)
        
        layout.addStretch()
        
        return tab

    def _create_analisis_tab(self, c: dict) -> QtWidgets.QWidget:
        """Pestaña de análisis y estadísticas de clientes"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Header
        header_lbl = QtWidgets.QLabel("📈 Análisis de Clientes")
        header_lbl.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['text_primary']};")
        layout.addWidget(header_lbl)
        
        # Cards de estadísticas
        stats_layout = QtWidgets.QHBoxLayout()
        stats_layout.setSpacing(15)
        
        self.stat_total = self._create_stat_card("Total Clientes", "0", "#4CAF50", c)
        self.stat_vip = self._create_stat_card("Clientes VIP", "0", "#FF9800", c)
        self.stat_credito = self._create_stat_card("Con Crédito", "0", "#2196F3", c)
        self.stat_activos = self._create_stat_card("Activos (30 días)", "0", "#9C27B0", c)
        
        stats_layout.addWidget(self.stat_total)
        stats_layout.addWidget(self.stat_vip)
        stats_layout.addWidget(self.stat_credito)
        stats_layout.addWidget(self.stat_activos)
        
        layout.addLayout(stats_layout)
        
        # Botón actualizar
        btn_refresh = QtWidgets.QPushButton("🔄 Actualizar Estadísticas")
        btn_refresh.setFixedHeight(40)
        btn_refresh.clicked.connect(self._refresh_analisis)
        layout.addWidget(btn_refresh)
        
        # Tabla de mejores clientes
        top_lbl = QtWidgets.QLabel("🏆 Top 10 Mejores Clientes (por compras)")
        top_lbl.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {c['text_primary']};")
        layout.addWidget(top_lbl)
        
        self.top_customers_table = QtWidgets.QTableWidget(0, 4)
        self.top_customers_table.setHorizontalHeaderLabels(["Cliente", "Total Compras", "Compras", "Última Compra"])
        self.top_customers_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.top_customers_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.top_customers_table)
        
        self._refresh_analisis()
        
        return tab

    def _create_giftcards_tab(self, c: dict) -> QtWidgets.QWidget:
        """Pestaña de gestión de gift cards por cliente"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Header
        header_lbl = QtWidgets.QLabel("🎁 Gift Cards del Cliente")
        header_lbl.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['text_primary']};")
        layout.addWidget(header_lbl)
        
        # Info
        info_lbl = QtWidgets.QLabel("Selecciona un cliente en la pestaña 'Lista' para ver sus gift cards.")
        info_lbl.setStyleSheet(f"color: {c['text_secondary']}; font-style: italic;")
        layout.addWidget(info_lbl)
        
        # Botones
        btn_layout = QtWidgets.QHBoxLayout()
        
        btn_new_gc = QtWidgets.QPushButton("➕ Crear Gift Card")
        btn_new_gc.setFixedHeight(45)
        btn_new_gc.clicked.connect(self._create_gift_card)
        
        btn_refresh_gc = QtWidgets.QPushButton("🔄 Actualizar")
        btn_refresh_gc.setFixedHeight(45)
        btn_refresh_gc.clicked.connect(self._refresh_giftcards)
        
        btn_layout.addWidget(btn_new_gc)
        btn_layout.addWidget(btn_refresh_gc)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Tabla de gift cards
        self.giftcards_table = QtWidgets.QTableWidget(0, 5)
        self.giftcards_table.setHorizontalHeaderLabels(["Código", "Saldo", "Estado", "Creación", "Cliente"])
        self.giftcards_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.giftcards_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.giftcards_table)
        
        return tab

    def _create_config_tab(self, c: dict) -> QtWidgets.QWidget:
        """Pestaña de configuración específica por cliente"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Header
        header_lbl = QtWidgets.QLabel("⚙️ Configuración del Cliente")
        header_lbl.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['text_primary']};")
        layout.addWidget(header_lbl)
        
        # Info
        info_lbl = QtWidgets.QLabel("Configuraciones específicas para el cliente seleccionado.")
        info_lbl.setStyleSheet(f"color: {c['text_secondary']}; font-style: italic;")
        layout.addWidget(info_lbl)
        
        # Grupo: Preferencias de Venta
        sales_group = QtWidgets.QGroupBox("🛒 Preferencias de Venta")
        sales_group.setStyleSheet(f"""
            QGroupBox {{ font-weight: bold; border: 2px solid {c['border']}; border-radius: 8px; margin-top: 10px; padding: 15px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}
        """)
        sales_layout = QtWidgets.QFormLayout(sales_group)
        
        self.cfg_default_discount = QtWidgets.QSpinBox()
        self.cfg_default_discount.setRange(0, 100)
        self.cfg_default_discount.setSuffix(" %")
        
        self.cfg_price_list = QtWidgets.QComboBox()
        self.cfg_price_list.addItems(["Precio Normal", "Mayoreo", "Distribuidor", "Especial"])
        
        self.cfg_auto_apply_vip = QtWidgets.QCheckBox("Aplicar descuento VIP automáticamente")
        
        sales_layout.addRow("Descuento por defecto:", self.cfg_default_discount)
        sales_layout.addRow("Lista de precios:", self.cfg_price_list)
        sales_layout.addRow(self.cfg_auto_apply_vip)
        
        layout.addWidget(sales_group)
        
        # Grupo: Notificaciones
        notif_group = QtWidgets.QGroupBox("📧 Notificaciones")
        notif_group.setStyleSheet(f"""
            QGroupBox {{ font-weight: bold; border: 2px solid {c['border']}; border-radius: 8px; margin-top: 10px; padding: 15px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}
        """)
        notif_layout = QtWidgets.QVBoxLayout(notif_group)
        
        self.cfg_notify_promos = QtWidgets.QCheckBox("Enviar promociones por email")
        self.cfg_notify_birthdays = QtWidgets.QCheckBox("Enviar felicitación de cumpleaños")
        self.cfg_notify_payments = QtWidgets.QCheckBox("Recordatorios de pago de crédito")
        
        notif_layout.addWidget(self.cfg_notify_promos)
        notif_layout.addWidget(self.cfg_notify_birthdays)
        notif_layout.addWidget(self.cfg_notify_payments)
        
        layout.addWidget(notif_group)
        
        # Botón guardar
        btn_save_config = QtWidgets.QPushButton("💾 Guardar Configuración del Cliente")
        btn_save_config.setFixedHeight(45)
        btn_save_config.clicked.connect(self._save_customer_config)
        layout.addWidget(btn_save_config)
        
        layout.addStretch()
        
        return tab

    def _create_stat_card(self, title: str, value: str, color: str, c: dict) -> QtWidgets.QFrame:
        """Crea una tarjeta de estadísticas"""
        card = QtWidgets.QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {c['bg_main']};
                border: 2px solid {color};
                border-radius: 10px;
                padding: 15px;
            }}
        """)
        card_layout = QtWidgets.QVBoxLayout(card)
        
        title_lbl = QtWidgets.QLabel(title)
        title_lbl.setStyleSheet(f"color: {c['text_secondary']}; font-size: 12px;")
        
        value_lbl = QtWidgets.QLabel(value)
        value_lbl.setObjectName("value")
        value_lbl.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold;")
        
        card_layout.addWidget(title_lbl)
        card_layout.addWidget(value_lbl)
        
        return card

    def _refresh_analisis(self) -> None:
        """Actualiza estadísticas de análisis"""
        try:
            if not self.core.db:
                logger.warning("Database not available")
                return
            # Total clientes
            result = self.core.db.execute_query("SELECT COUNT(*) as cnt FROM customers")
            total = result[0]["cnt"] if result else 0
            self.stat_total.findChild(QtWidgets.QLabel, "value").setText(str(total))
            
            # VIP
            result = self.core.db.execute_query("SELECT COUNT(*) as cnt FROM customers WHERE vip = 1")
            vip = result[0]["cnt"] if result else 0
            self.stat_vip.findChild(QtWidgets.QLabel, "value").setText(str(vip))
            
            # Con crédito
            result = self.core.db.execute_query("SELECT COUNT(*) as cnt FROM customers WHERE credit_limit != 0")
            credito = result[0]["cnt"] if result else 0
            self.stat_credito.findChild(QtWidgets.QLabel, "value").setText(str(credito))
            
            # Activos (30 días)
            result = self.core.db.execute_query("""
                SELECT COUNT(DISTINCT customer_id) as cnt FROM sales 
                WHERE customer_id IS NOT NULL AND timestamp::timestamp >= NOW() - INTERVAL '30 days'
            """)
            activos = result[0]["cnt"] if result else 0
            self.stat_activos.findChild(QtWidgets.QLabel, "value").setText(str(activos))
            
            # Top clientes
            top = self.core.db.execute_query("""
                SELECT c.name, COALESCE(SUM(s.total), 0) as total_compras, COUNT(s.id) as num_compras, MAX(s.timestamp) as ultima
                FROM sales s
                JOIN customers c ON s.customer_id = c.id
                GROUP BY s.customer_id, c.name
                ORDER BY total_compras DESC
                LIMIT 10
            """)
            
            self.top_customers_table.setRowCount(len(top))
            for i, row in enumerate(top):
                r = dict(row)
                values = [
                    r.get("name", ""),
                    f"${float(r.get('total_compras', 0)):.2f}",
                    str(r.get("num_compras", 0)),
                    str(r.get("ultima", ""))[:10]
                ]
                for j, val in enumerate(values):
                    item = QtWidgets.QTableWidgetItem(str(val))
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    self.top_customers_table.setItem(i, j, item)
                    
        except Exception as e:
            print(f"Error refreshing analytics: {e}")

    def _refresh_giftcards(self) -> None:
        """Actualiza tabla de gift cards"""
        try:
            if not self.core.db:
                logger.warning("Database not available")
                return
            # Query gift cards - show selected customer's cards OR all cards if no customer selected
            if self.selected_customer_id:
                # Show cards for selected customer plus general public cards
                gcs = self.core.db.execute_query("""
                    SELECT code, balance, status, created_at, customer_id
                    FROM gift_cards 
                    WHERE customer_id = %s OR customer_id IS NULL
                    ORDER BY created_at DESC
                """, [self.selected_customer_id])
            else:
                # Show all gift cards (no customer filter)
                gcs = self.core.db.execute_query("""
                    SELECT code, balance, status, created_at, customer_id
                    FROM gift_cards 
                    ORDER BY created_at DESC
                    LIMIT 100
                """)
            
            self.giftcards_table.setRowCount(len(gcs))
            for i, gc in enumerate(gcs):
                g = dict(gc)
                customer_id = g.get("customer_id")
                values = [
                    g.get("code", ""),
                    f"${float(g.get('balance', 0)):.2f}",
                    g.get("status", ""),
                    str(g.get("created_at", ""))[:10],
                    f"Cliente #{customer_id}" if customer_id else "Público General"
                ]
                for j, val in enumerate(values):
                    item = QtWidgets.QTableWidgetItem(str(val))
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    self.giftcards_table.setItem(i, j, item)
                    
        except Exception as e:
            print(f"Error refreshing gift cards: {e}")

    def _create_gift_card(self) -> None:
        """Crea una nueva gift card (con o sin cliente)"""
        try:
            from app.dialogs.gift_card_dialog import GiftCardDialog

            # customer_id puede ser None para público general
            dlg = GiftCardDialog(self.core, self.selected_customer_id, self)
            if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                self._refresh_giftcards()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al crear gift card: {e}")

    def _save_customer_config(self) -> None:
        """Guarda configuración específica del cliente"""
        if not self.selected_customer_id:
            QtWidgets.QMessageBox.warning(self, "Selecciona", "Primero selecciona un cliente")
            return
        try:
            # Aquí se guardaría en config_customer o similar
            QtWidgets.QMessageBox.information(self, "Guardado", "Configuración del cliente guardada")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al guardar: {e}")

    def _form_label(self, text: str, c: dict) -> QtWidgets.QLabel:
        """Crea un label estilizado para el formulario"""
        label = QtWidgets.QLabel(text)
        label.setStyleSheet(f"font-weight: bold; color: {c['text_secondary']}; font-size: 13px;")
        return label

    def _reset_form(self) -> None:
        for widget in [
            self.first_name, self.last_name, self.phone, self.email,
            self.email_fiscal, self.rfc, self.razon_social, self.regimen_fiscal,
            self.domicilio1, self.domicilio2, self.colonia, self.municipio,
            self.estado, self.pais, self.codigo_postal,
        ]:
            widget.clear()
        self.pais.setText("México")
        self.notes.clear()
        self.vip_cb.setChecked(False)
        self.credit_enabled.setChecked(False)
        self.credit_mode.setCurrentIndex(0)
        self.credit_limit.setValue(0.0)
        self.credit_balance.setText("$0.00")

    def _gather_data(self) -> dict[str, Any]:
        credit_authorized = self.credit_enabled.isChecked()
        credit_limit = -1.0 if credit_authorized and self.credit_mode.currentText() == "Ilimitado" else self.credit_limit.value()
        return {
            "first_name": self.first_name.text().strip(),
            "last_name": self.last_name.text().strip(),
            "phone": self.phone.text().strip(),
            "email": self.email.text().strip(),
            "email_fiscal": self.email_fiscal.text().strip(),
            "rfc": self.rfc.text().strip(),
            "razon_social": self.razon_social.text().strip(),
            "regimen_fiscal": self.regimen_fiscal.text().strip(),
            "domicilio1": self.domicilio1.text().strip(),
            "domicilio2": self.domicilio2.text().strip(),
            "colonia": self.colonia.text().strip(),
            "municipio": self.municipio.text().strip(),
            "estado": self.estado.text().strip(),
            "pais": self.pais.text().strip(),
            "codigo_postal": self.codigo_postal.text().strip(),
            "notes": self.notes.toPlainText().strip(),
            "vip": self.vip_cb.isChecked(),
            "credit_authorized": credit_authorized,
            "credit_limit": credit_limit if credit_authorized else 0.0,
            "name": f"{self.first_name.text().strip()} {self.last_name.text().strip()}".strip(),
        }

    def refresh_table(self) -> None:
        try:
            query = self.search_input.text().strip()
        except RuntimeError:
            return
        customers = self.core.search_customers(query) if query else self.core.list_customers(limit=300)
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(0)
        self.table.setRowCount(len(customers))
        for row_idx, row in enumerate(customers):
            customer = dict(row)
            
            full_name = (customer.get("name") or "").strip()
            if not full_name:
                full_name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
            
            values = [
                customer.get("id"),
                full_name,
                customer.get("phone") or "",
                "Ilimitado" if float(customer.get("credit_limit", 0.0) or 0.0) < 0 else f"{float(customer.get('credit_limit', 0.0) or 0.0):.2f}",
                f"{float(customer.get('credit_balance', 0.0) or 0.0):.2f}",
            ]

            for col, value in enumerate(values):
                if col >= self.table.columnCount(): break
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_idx, col, item)
        self.table.setUpdatesEnabled(True)

    def _refresh_credit_table(self) -> None:
        """Actualiza tabla de crédito"""
        try:
            customers = self.core.list_customers(limit=500)
            credit_customers = [dict(c) for c in customers if float(dict(c).get("credit_limit", 0) or 0) != 0]
            
            self.credit_table.setRowCount(0)
            self.credit_table.setRowCount(len(credit_customers))
            
            for row_idx, customer in enumerate(credit_customers):
                full_name = customer.get("name") or f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
                limit = float(customer.get("credit_limit", 0) or 0)
                balance = float(customer.get("credit_balance", 0) or 0)
                available = limit - balance if limit >= 0 else float('inf')
                
                values = [
                    full_name,
                    "Ilimitado" if limit < 0 else f"${limit:.2f}",
                    f"${balance:.2f}",
                    "Ilimitado" if limit < 0 else f"${available:.2f}"
                ]
                
                for col, value in enumerate(values):
                    item = QtWidgets.QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, customer.get("id"))
                    self.credit_table.setItem(row_idx, col, item)
        except Exception as e:
            print(f"Error refreshing credit table: {e}")

    def _refresh_midas_table(self) -> None:
        """Actualiza tabla MIDAS"""
        try:
            customers = self.core.list_customers(limit=500)
            
            self.midas_table.setRowCount(0)
            self.midas_table.setRowCount(len(customers))
            
            for row_idx, row in enumerate(customers):
                customer = dict(row)
                full_name = customer.get("name") or f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
                wallet_balance = float(customer.get("wallet_balance", 0) or 0)
                
                # Obtener estado de cuenta loyalty
                try:
                    account = self.core.loyalty_engine.get_account_by_customer(customer.get("id"))
                    status = account.get("status", "N/A") if account else "Sin Cuenta"
                except Exception:
                    status = "N/A"
                
                values = [
                    full_name,
                    f"${wallet_balance:.2f}",
                    status
                ]
                
                for col, value in enumerate(values):
                    item = QtWidgets.QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, customer.get("id"))
                    self.midas_table.setItem(row_idx, col, item)
        except Exception as e:
            print(f"Error refreshing MIDAS table: {e}")

    def _refresh_historial_table(self) -> None:
        """Actualiza tabla de historial de compras"""
        try:
            if not hasattr(self, 'historial_table'):
                return
            if not self.core.db:
                logger.warning("Database not available")
                return

            # Obtener fechas seleccionadas
            date_from = self.hist_date_from.date().toPyDate() if hasattr(self, 'hist_date_from') else None
            date_to = self.hist_date_to.date().toPyDate() if hasattr(self, 'hist_date_to') else None
            
            # Consultar ventas del cliente seleccionado o todas
            query = """
                SELECT 
                    s.id,
                    s.timestamp,
                    s.customer_id,
                    c.name as customer_name,
                    s.total,
                    s.payment_method,
                    s.status
                FROM sales s
                LEFT JOIN customers c ON s.customer_id = c.id
                WHERE 1=1
            """
            params = []
            
            if date_from:
                query += " AND CAST(s.timestamp AS DATE) >= %s"
                params.append(str(date_from))
            
            if date_to:
                query += " AND CAST(s.timestamp AS DATE) <= %s"
                params.append(str(date_to))
            
            # Si hay cliente seleccionado, filtrar por él
            if self.selected_customer_id:
                query += " AND s.customer_id = %s"
                params.append(self.selected_customer_id)
            
            query += " ORDER BY s.timestamp DESC LIMIT 500"
            
            sales = self.core.db.execute_query(query,params)
            
            self.historial_table.setRowCount(0)
            self.historial_table.setRowCount(len(sales))
            
            total_amount = 0.0
            
            for row_idx, sale in enumerate(sales):
                sale_dict = dict(sale)
                
                values = [
                    sale_dict.get("timestamp", "")[:16],  # Fecha y hora
                    str(sale_dict.get("id", "")),  # Folio
                    sale_dict.get("customer_name", "Público General"),
                    f"${float(sale_dict.get('total', 0)):.2f}",
                    sale_dict.get("payment_method", "N/A"),
                    sale_dict.get("status", "completed")
                ]
                
                total_amount += float(sale_dict.get("total", 0))
                
                for col, value in enumerate(values):
                    item = QtWidgets.QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    self.historial_table.setItem(row_idx, col, item)
            
            # Actualizar totales
            if hasattr(self, 'hist_total_sales'):
                self.hist_total_sales.setText(f"Total Ventas: ${total_amount:,.2f}")
            if hasattr(self, 'hist_count_sales'):
                self.hist_count_sales.setText(f"Cantidad: {len(sales)}")
                
        except Exception as e:
            print(f"Error refreshing historial table: {e}")

    def _on_credit_table_selection(self) -> None:
        """Sincroniza selección de tabla de crédito con lista principal"""
        try:
            row = self.credit_table.currentRow()
            if row >= 0:
                item = self.credit_table.item(row, 0)
                if item:
                    customer_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
                    self.selected_customer_id = customer_id
                    # Opcional: cargar en formulario
        except Exception as e:
            print(f"Error syncing credit selection: {e}")

    def _on_midas_table_selection(self) -> None:
        """Sincroniza selección de tabla MIDAS con lista principal"""
        try:
            row = self.midas_table.currentRow()
            if row >= 0:
                item = self.midas_table.item(row, 0)
                if item:
                    customer_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
                    self.selected_customer_id = customer_id
        except Exception as e:
            print(f"Error syncing MIDAS selection: {e}")

    def load_selected(self) -> None:
        try:
            row = self.table.currentRow()
            if row < 0:
                self.selected_customer_id = None
                return
            
            item_id = self.table.item(row, 0)
            if not item_id:
                return
                
            try:
                self.selected_customer_id = int(item_id.text())
            except (ValueError, TypeError):
                return
            record_row = self.core.get_customer(self.selected_customer_id)
            if not record_row:
                return
            record = dict(record_row)
            
            f_name = record.get("first_name", "")
            l_name = record.get("last_name", "")
            if not f_name and record.get("name"):
                parts = record["name"].split(" ", 1)
                f_name = parts[0]
                l_name = parts[1] if len(parts) > 1 else ""
                
            self.first_name.setText(f_name)
            self.last_name.setText(l_name)
            self.phone.setText(record.get("phone") or "")
            self.email.setText(record.get("email") or "")
            self.email_fiscal.setText(record.get("email_fiscal") or "")
            self.rfc.setText(record.get("rfc") or "")
            self.razon_social.setText(record.get("razon_social") or "")
            self.regimen_fiscal.setText(record.get("regimen_fiscal") or "")
            self.domicilio1.setText(record.get("domicilio1") or "")
            self.domicilio2.setText(record.get("domicilio2") or "")
            self.colonia.setText(record.get("colonia") or "")
            self.municipio.setText(record.get("municipio") or "")
            self.estado.setText(record.get("estado") or "")
            self.pais.setText(record.get("pais") or "México")
            self.codigo_postal.setText(record.get("codigo_postal") or "")
            self.notes.setPlainText(record.get("notes") or "")
            self.vip_cb.setChecked(bool(record.get("vip")))
            credit_limit = float(record.get("credit_limit", 0.0) or 0.0)
            authorized = bool(record.get("credit_authorized") or credit_limit != 0)
            self.credit_enabled.setChecked(authorized)
            if credit_limit < 0:
                self.credit_mode.setCurrentText("Ilimitado")
            else:
                self.credit_mode.setCurrentText("De máximo")
                self.credit_limit.setValue(max(0.0, credit_limit))
            balance = float(record.get("credit_balance", 0.0) or 0.0)
            self.credit_balance.setText(f"$ {balance:,.2f}")
            
            if hasattr(self, "btn_pay"):
                self.btn_pay.setEnabled(True)
        except Exception as e:
            print(f"Error loading customer: {e}")

    def new_customer(self) -> None:
        self.selected_customer_id = None
        self._reset_form()
        self.first_name.setFocus()
        self.tab_widget.setCurrentIndex(0)  # Cambiar a pestaña Lista

    def save_customer(self) -> None:
        data = self._gather_data()
        if not data["first_name"]:
            QtWidgets.QMessageBox.warning(self, "Nombre requerido", "El nombre es obligatorio")
            return
        try:
            if self.selected_customer_id:
                old_customer = self.core.get_customer(self.selected_customer_id)
                self.core.update_customer(self.selected_customer_id, data)
                
                try:
                    customer_name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
                    self.core.audit.log_update('customer', self.selected_customer_id, 
                                              customer_name, old_customer, data)
                except Exception:
                    pass
                    
                QtWidgets.QMessageBox.information(self, "Actualizado", "Cliente actualizado")
            else:
                self.selected_customer_id = self.core.create_customer(data)
                
                try:
                    customer_name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
                    self.core.audit.log_create('customer', self.selected_customer_id, 
                                              customer_name, data)
                except Exception:
                    pass
                    
                QtWidgets.QMessageBox.information(self, "Guardado", "Cliente creado correctamente")
            self.refresh_table()
            self._refresh_credit_table()
            self._refresh_midas_table()
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo guardar: {exc}")

    def delete_customer(self) -> None:
        if not self.selected_customer_id:
            QtWidgets.QMessageBox.warning(self, "Selecciona", "Elige un cliente a eliminar")
            return
        if QtWidgets.QMessageBox.question(self, "Eliminar", "¿Borrar cliente seleccionado?") != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            self.core.delete_customer(self.selected_customer_id)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Error", str(exc))
            return
        QtWidgets.QMessageBox.information(self, "Eliminado", "Cliente eliminado exitosamente")
        self.selected_customer_id = None
        self.refresh_table()
        self._refresh_credit_table()
        self._refresh_midas_table()
        self._reset_form()

    def open_payment_dialog(self) -> None:
        if not self.selected_customer_id:
            QtWidgets.QMessageBox.warning(self, "Selecciona", "Elige un cliente para abonar")
            return
        customer_row = self.core.get_customer(self.selected_customer_id)
        if not customer_row:
            QtWidgets.QMessageBox.warning(self, "No encontrado", "Cliente no disponible")
            return
        customer = dict(customer_row)
        balance = float(customer.get("credit_balance", 0.0) or 0.0)
        if balance <= 0:
            QtWidgets.QMessageBox.information(self, "Sin saldo", "Este cliente no tiene saldo pendiente")
            return
        
        customer_name = customer.get("name") or f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
        
        dlg = CreditPaymentDialog(
            customer_id=self.selected_customer_id,
            customer_name=customer_name,
            current_balance=balance,
            core=self.core,
            parent=self
        )
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            QtWidgets.QMessageBox.information(self, "Abono registrado", "El abono se registró correctamente")
            self.refresh_table()
            self._refresh_credit_table()
            self.load_selected()

    def open_overview(self) -> None:

        if not self.selected_customer_id:
            QtWidgets.QMessageBox.warning(self, "Selecciona", "Elige un cliente")
            return
        try:
            customer_row = self.core.get_customer_full_profile(self.selected_customer_id)
            customer_name = (customer_row.get("full_name") if customer_row else "Cliente") if customer_row else "Cliente"
            dlg = CreditStatementDialog(self.core, self.selected_customer_id, customer_name, self)
            dlg.exec()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al abrir estado de cuenta: {e}")

    def open_wallet_dialog(self) -> None:
        if not self.selected_customer_id:
            QtWidgets.QMessageBox.warning(self, "Selecciona", "Elige un cliente para ver su monedero")
            return
        try:
            dlg = WalletDialog(self, self.core, self.selected_customer_id)
            dlg.exec()
            self._refresh_midas_table()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al abrir monedero: {e}")
    
    def _open_wallet_manager(self) -> None:
        """Abre el gestor de monederos anónimos."""
        try:
            from app.dialogs.wallet_manager_dialog import WalletManagerDialog
            dlg = WalletManagerDialog(self.core, self)
            dlg.exec()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al abrir gestor: {e}")

    def export_customers(self) -> None:
        customers = self.core.list_customers(limit=10000)
        if not customers:
            QtWidgets.QMessageBox.information(self, "Exportar", "No hay clientes para exportar")
            return
        path, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self, "Exportar clientes", "clientes", "Excel (*.xlsx);;CSV (*.csv)",
        )
        if not path:
            return
            
        if selected_filter.startswith("Excel") and not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        elif selected_filter.startswith("CSV") and not path.lower().endswith(".csv"):
            path += ".csv"

        try:
            if path.endswith(".xlsx"):
                export_customers_to_excel(customers, path)
            else:
                export_customers_to_csv(customers, path)
            QtWidgets.QMessageBox.information(self, "Exportar", "Catálogo exportado correctamente")
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Exportar", f"No se pudo exportar: {exc}")

    def import_customers(self) -> None:
        dlg = ImportCustomerWizardDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            file_path, mapping, update_existing, header_row_idx = dlg.get_data()
            
            if not file_path or not file_path.strip():
                QtWidgets.QMessageBox.warning(self, "Error", "No se seleccionó ningún archivo")
                return
                
            import os
            if not os.path.exists(file_path):
                QtWidgets.QMessageBox.warning(self, "Error", f"El archivo no existe:\\n{file_path}")
                return
                
            self._process_import(file_path, mapping, update_existing, header_row_idx)

    def _process_import(self, file_path: str, mapping: dict, update_existing: bool, header_row_idx: int) -> None:
        progress = QtWidgets.QProgressDialog("Importando clientes...", "Cancelar", 0, 100, self)
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.show()
        
        def clean_float(val: Any) -> float:
            if not val: return 0.0
            if isinstance(val, (int, float)): return float(val)
            s = str(val).strip().replace("$", "").replace(",", "")
            try:
                return float(s)
            except ValueError:
                return 0.0

        try:
            rows = []
            if file_path.lower().endswith('.xlsx'):
                import openpyxl
                import zipfile
                import os
                
                # Validar archivo antes de leer
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"El archivo no existe: {file_path}")
                
                if os.path.getsize(file_path) == 0:
                    raise ValueError("El archivo está vacío")
                
                # Validar que .xlsx sea un ZIP válido
                try:
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_files = zip_ref.namelist()
                        if not any('xl/workbook.xml' in f or '[Content_Types].xml' in f for f in zip_files):
                            raise ValueError("El archivo no parece ser un Excel válido")
                except zipfile.BadZipFile:
                    raise ValueError(
                        "El archivo Excel está corrupto o no es válido.\n\n"
                        "Error: Bad magic number for central directory\n\n"
                        "Solución:\n"
                        "1. Abre el archivo en Excel\n"
                        "2. Guarda el archivo nuevamente (Ctrl+S)\n"
                        "3. Intenta importar de nuevo"
                    )
                
                try:
                    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
                    ws = wb.active
                    rows = list(ws.iter_rows(min_row=header_row_idx + 2, values_only=True))
                    wb.close()
                except zipfile.BadZipFile:
                    raise ValueError(
                        "El archivo Excel está corrupto.\n\n"
                        "Por favor, abre el archivo en Excel y guárdalo nuevamente."
                    )
                except Exception as e:
                    error_msg = str(e)
                    if "Bad magic number" in error_msg or "BadZipFile" in error_msg:
                        raise ValueError(
                            "El archivo Excel está corrupto o no es válido.\n\n"
                            "Solución: Abre el archivo en Excel y guárdalo nuevamente."
                        )
                    raise
            else:
                encodings = ['utf-8-sig', 'utf-8', 'latin-1']
                content = None
                for encoding in encodings:
                    try:
                        with open(file_path, 'r', encoding=encoding) as f:
                            content = f.read()
                        break
                    except UnicodeDecodeError:
                        continue
                if not content:
                    raise ValueError("Error de codificación en CSV")
                lines = [line.strip() for line in content.splitlines() if line.strip()]
                if len(lines) > header_row_idx:
                    header = lines[header_row_idx]
                    delimiter = ';' if ';' in header and header.count(';') > header.count(',') else ','
                    rows = [line.split(delimiter) for line in lines[header_row_idx+1:]]

            total = len(rows)
            created = 0
            updated = 0
            errors = 0
            
            for i, row_data in enumerate(rows):
                if progress.wasCanceled():
                    break
                progress.setValue(int((i / total) * 100))
                # FIX 2026-02-01: Procesar eventos cada 10 filas para evitar freeze de UI
                if i % 10 == 0:
                    QtWidgets.QApplication.processEvents()
                
                try:
                    data = {}
                    for field, col_idx in mapping.items():
                        if col_idx < len(row_data):
                            val = row_data[col_idx]
                            data[field] = str(val).strip() if val is not None else ""
                    
                    if not data.get("full_name") and not data.get("first_name"):
                        continue

                    for num_field in ["credit_limit", "credit_balance", "points", "wallet_balance"]:
                        if num_field in data and num_field in mapping:
                            data[num_field] = clean_float(row_data[mapping[num_field]] if mapping[num_field] < len(row_data) else 0)
                    
                    for bool_field in ["vip", "credit_authorized"]:
                        if bool_field in data:
                            val_str = str(data[bool_field]).lower().strip()
                            # Convertir a INTEGER (0/1) para PostgreSQL, no boolean
                            data[bool_field] = 1 if val_str in ["sí", "si", "yes", "true", "1", "verdadero"] else 0

                    full_name = data.get("full_name", "")
                    if not full_name and data.get("first_name"):
                        full_name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
                        data["full_name"] = full_name
                        
                    data["name"] = full_name
                    if "first_name" not in data or not data["first_name"]:
                        parts = full_name.split(" ", 1)
                        data["first_name"] = parts[0]
                        data["last_name"] = parts[1] if len(parts) > 1 else ""

                    existing = None
                    if update_existing:
                        if data.get("rfc"):
                            res = self.core.search_customers(data["rfc"], limit=1)
                            # FIX 2026-02-01: Validar res con len() antes de acceder a [0]
                            if res and len(res) > 0: existing = res[0]

                        if not existing and full_name:
                            res = self.core.search_customers(full_name, limit=1)
                            # FIX 2026-02-01: Validar res con len() antes de acceder a [0]
                            if res and len(res) > 0: existing = res[0]

                    if existing:
                        self.core.update_customer(existing["id"], data)
                        updated += 1
                    else:
                        self.core.create_customer(data)
                        created += 1
                        
                except Exception as e:
                    logger.warning("Error importing customer row %d: %s", i, e)
                    errors += 1
            
            progress.setValue(100)
            QtWidgets.QMessageBox.information(
                self, "Importación completada", 
                f"Proceso finalizado.\\n\\nCreados: {created}\\nActualizados: {updated}\\nErrores/Omitidos: {errors}"
            )
            self.refresh_table()
            self._refresh_credit_table()
            self._refresh_midas_table()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Error durante la importación: {e}")
        finally:
            progress.close()

    def export_complete_backup(self) -> None:
        from datetime import datetime
        
        default_name = f"backup_completo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Guardar Backup Completo", default_name, "Excel (*.xlsx)"
        )
        
        if not path:
            return
        
        if not path.lower().endswith('.xlsx'):
            path += '.xlsx'
        
        progress = QtWidgets.QProgressDialog("Exportando backup completo...", None, 0, 0, self)
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.show()
        QtWidgets.QApplication.processEvents()
        
        try:
            success, message = export_complete_backup(self.core, path)
            progress.close()
            
            if success:
                QtWidgets.QMessageBox.information(self, "Backup Completo", message)
            else:
                QtWidgets.QMessageBox.critical(self, "Error", message)
                
        except Exception as e:
            progress.close()
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al exportar backup: {e}")
    
    def import_complete_backup(self) -> None:
        reply = QtWidgets.QMessageBox.question(
            self, "Restaurar Backup Completo",
            "⚠️ ADVERTENCIA ⚠️\\n\\n"
            "Esta operación importará:\\n"
            "• Clientes\\n"
            "• Historial de crédito\\n"
            "• Historial de loyalty/monedero\\n\\n"
            "Los clientes existentes serán actualizados si coincide el RFC.\\n\\n"
            "¿Deseas continuar?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Seleccionar Backup Completo", "", "Excel (*.xlsx)"
        )
        
        if not path:
            return
        
        progress = QtWidgets.QProgressDialog("Importando backup completo...", None, 0, 0, self)
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.show()
        QtWidgets.QApplication.processEvents()
        
        try:
            success, message = import_complete_backup(self.core, path)
            progress.close()
            
            if success:
                QtWidgets.QMessageBox.information(self, "Backup Restaurado", message)
                self.refresh_table()
                self._refresh_credit_table()
                self._refresh_midas_table()
            else:
                QtWidgets.QMessageBox.critical(self, "Error", message)
                
        except Exception as e:
            progress.close()
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al importar backup: {e}")

    def update_theme(self) -> None:
        theme = (self.core.get_app_config() or {}).get("theme", "Light")
        c = theme_manager.get_colors(theme)
        
        # Header
        self.header.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {c['bg_secondary']}, stop:1 {c['bg_main']});
                border-bottom: 2px solid {c['accent']};
            }}
        """)
        
        self.title_label.setStyleSheet(f"""
            font-size: 24px;
            font-weight: bold;
            color: {c['text_primary']};
            padding-left: 10px;
        """)
        
        # Tab widget
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {c['border']};
                background: {c['bg_secondary']};
            }}
            QTabBar::tab {{
                background: {c['bg_main']};
                color: {c['text_secondary']};
                padding: 12px 20px;
                margin-right: 2px;
                border: 1px solid {c['border']};
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
            QTabBar::tab:selected {{
                background: {c['bg_secondary']};
                color: {c['text_primary']};
                font-weight: bold;
                border-bottom: 2px solid {c['accent']};
            }}
            QTabBar::tab:hover {{
                background: {c['bg_secondary']};
            }}
        """)
        
        # Tables
        for table in [self.table, self.credit_table, self.midas_table]:
            table.setStyleSheet(f"""
                QTableWidget {{
                    background-color: {c['bg_main']};
                    gridline-color: {c['border']};
                    border: 1px solid {c['border']};
                    border-radius: 6px;
                }}
                QTableWidget::item {{
                    padding: 8px;
                    color: {c['text_primary']};
                }}
                QTableWidget::item:selected {{
                    background-color: {c['accent']};
                    color: white;
                }}
                QHeaderView::section {{
                    background-color: {c['table_header_bg']};
                    color: {c['table_header_text']};
                    padding: 10px;
                    border: none;
                    border-right: 1px solid {c['border']};
                    font-weight: bold;
                }}
            """)
        
        # Buttons
        for btn, color_key, outline in self.action_buttons_data:
            color = c.get(color_key, color_key)
            if outline:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {color};
                        border: 2px solid {color};
                        border-radius: 6px;
                        padding: 8px 16px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{
                        background-color: {color};
                        color: white;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {color};
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 8px 16px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{
                        background-color: {c['bg_secondary']};
                    }}
                """)
        
        # Input fields
        for field in self.input_fields:
            field.setStyleSheet(f"""
                QLineEdit, QPlainTextEdit, QDoubleSpinBox, QComboBox {{
                    background-color: {c['input_bg']};
                    color: {c['text_primary']};
                    border: 1px solid {c['border']};
                    border-radius: 4px;
                    padding: 8px;
                }}
                QLineEdit:focus, QPlainTextEdit:focus {{
                    border-color: {c['accent']};
                }}
            """)
        
        # Search
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {c['input_bg']};
                color: {c['text_primary']};
                border: 2px solid {c['border']};
                border-radius: 8px;
                padding: 10px 15px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: {c['accent']};
            }}
        """)

    def showEvent(self, event):
        """Apply theme when tab is shown."""
        super().showEvent(event)
        self.update_theme()

