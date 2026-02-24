"""
EMPLOYEES TAB - Employee & Loan Management
Complete UI with tab-based organization
"""
from datetime import datetime

from PyQt6 import QtCore, QtGui, QtWidgets

from app.dialogs.loan_dialogs import EmployeeDialog, LoanCreateDialog, LoanPaymentDialog
from app.utils import permissions
from app.utils.theme_manager import theme_manager


class EmployeesTab(QtWidgets.QWidget):
    """Tab for employee and loan management - reorganized with tabs."""
    
    employees_updated = QtCore.pyqtSignal()
    
    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.current_employee = None
        self._build_ui()
        self._load_employees()
    
    def _build_ui(self):
        """Build the UI with tabs."""
        theme = (self.core.get_app_config() or {}).get("theme", "Light")
        c = theme_manager.get_colors(theme)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        self.header = QtWidgets.QFrame()
        self.header.setFixedHeight(70)
        header_layout = QtWidgets.QHBoxLayout(self.header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        
        self.header_label = QtWidgets.QLabel("👥 GESTIÓN DE RECURSOS HUMANOS")
        self.header_label.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['text_primary']};")
        header_layout.addWidget(self.header_label)
        header_layout.addStretch()
        
        layout.addWidget(self.header)
        
        # Tab Widget
        self.tab_widget = QtWidgets.QTabWidget()
        
        # Tab 1: Personal
        self.tab_personal = self._create_personal_tab(c)
        self.tab_widget.addTab(self.tab_personal, "👥 Personal")
        
        # Tab 2: Préstamos
        self.tab_prestamos = self._create_prestamos_tab(c)
        self.tab_widget.addTab(self.tab_prestamos, "💰 Préstamos")
        
        # Tab 3: Asistencia
        self.tab_asistencia = self._create_asistencia_tab(c)
        self.tab_widget.addTab(self.tab_asistencia, "⏰ Asistencia")
        
        # Tab 4: Nómina
        self.tab_nomina = self._create_nomina_tab(c)
        self.tab_widget.addTab(self.tab_nomina, "📊 Nómina")
        
        # Tab 5: Reportes
        self.tab_reportes = self._create_reportes_tab(c)
        self.tab_widget.addTab(self.tab_reportes, "📈 Reportes")
        
        layout.addWidget(self.tab_widget)
        
        self.update_theme()

    # =========================================================================
    # TAB CREATION
    # =========================================================================
    
    def _create_personal_tab(self, c: dict) -> QtWidgets.QWidget:
        """Pestaña de gestión de personal"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Search & Actions Bar
        search_layout = QtWidgets.QHBoxLayout()
        
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("🔍 Buscar empleado por nombre o código...")
        self.search_input.textChanged.connect(self._filter_employees)
        self.search_input.setFixedHeight(40)
        search_layout.addWidget(self.search_input, 3)
        
        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.addItems(["Activos", "Inactivos", "Terminados", "Todos"])
        self.status_filter.setFixedHeight(40)
        self.status_filter.currentTextChanged.connect(self._load_employees)
        search_layout.addWidget(self.status_filter, 1)
        
        self.btn_new_employee = QtWidgets.QPushButton("➕ Nuevo Empleado")
        self.btn_new_employee.setFixedHeight(40)
        self.btn_new_employee.clicked.connect(self._create_employee)
        search_layout.addWidget(self.btn_new_employee)
        
        btn_refresh = QtWidgets.QPushButton("🔄")
        btn_refresh.setFixedWidth(50)
        btn_refresh.setFixedHeight(40)
        btn_refresh.clicked.connect(self._load_employees)
        search_layout.addWidget(btn_refresh)
        
        layout.addLayout(search_layout)
        
        # Splitter
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        
        # Left: Employee List
        left_panel = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        list_label = QtWidgets.QLabel("📋 Lista de Empleados")
        list_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {c['text_primary']};")
        left_layout.addWidget(list_label)
        
        self.employee_table = QtWidgets.QTableWidget()
        self.employee_table.setColumnCount(6)
        self.employee_table.setHorizontalHeaderLabels([
            "Código", "Nombre", "Puesto", "Comisión %", "Préstamos", "Estado"
        ])
        self.employee_table.horizontalHeader().setStretchLastSection(False)
        self.employee_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.employee_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.employee_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.employee_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.employee_table.itemSelectionChanged.connect(self._on_employee_selected)
        self.employee_table.doubleClicked.connect(self._edit_employee)
        left_layout.addWidget(self.employee_table)
        
        splitter.addWidget(left_panel)
        
        # Right: Employee Details
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Employee Info Card
        self.info_card = QtWidgets.QGroupBox("📊 Información del Empleado")
        info_layout = QtWidgets.QVBoxLayout()
        
        self.info_label = QtWidgets.QLabel("Selecciona un empleado para ver detalles")
        self.info_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(self.info_label)
        
        # Action Buttons
        actions_layout = QtWidgets.QHBoxLayout()
        
        self.btn_edit = QtWidgets.QPushButton("✏️ Editar")
        self.btn_edit.setEnabled(False)
        self.btn_edit.clicked.connect(self._edit_employee)
        
        self.btn_new_loan = QtWidgets.QPushButton("💰 Nuevo Préstamo")
        self.btn_new_loan.setEnabled(False)
        self.btn_new_loan.clicked.connect(self._create_loan)
        
        self.btn_deactivate = QtWidgets.QPushButton("🚫 Desactivar")
        self.btn_deactivate.setEnabled(False)
        self.btn_deactivate.clicked.connect(self._toggle_employee_status)
        
        self.btn_delete = QtWidgets.QPushButton("🗑️ Eliminar")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._delete_employee)
        
        for btn in [self.btn_edit, self.btn_new_loan, self.btn_deactivate, self.btn_delete]:
            btn.setFixedHeight(35)
            actions_layout.addWidget(btn)
        
        info_layout.addLayout(actions_layout)
        self.info_card.setLayout(info_layout)
        right_layout.addWidget(self.info_card)
        
        # Loans Quick View
        loans_label = QtWidgets.QLabel("💳 Préstamos del Empleado")
        loans_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {c['text_primary']};")
        right_layout.addWidget(loans_label)
        
        self.loans_table = QtWidgets.QTableWidget()
        self.loans_table.setColumnCount(6)
        self.loans_table.setHorizontalHeaderLabels([
            "ID", "Tipo", "Monto", "Balance", "Cuota", "Estado"
        ])
        self.loans_table.horizontalHeader().setStretchLastSection(True)
        self.loans_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.loans_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.loans_table.doubleClicked.connect(self._pay_loan)
        self.loans_table.itemSelectionChanged.connect(self._on_loan_selected)
        right_layout.addWidget(self.loans_table)
        
        # Loan Actions
        loan_actions = QtWidgets.QHBoxLayout()
        
        self.btn_pay_loan = QtWidgets.QPushButton("💵 Registrar Pago")
        self.btn_pay_loan.setEnabled(False)
        self.btn_pay_loan.clicked.connect(self._pay_loan)
        
        self.btn_loan_history = QtWidgets.QPushButton("📜 Historial")
        self.btn_loan_history.setEnabled(False)
        self.btn_loan_history.clicked.connect(self._show_loan_history)
        
        self.btn_cancel_loan = QtWidgets.QPushButton("❌ Cancelar")
        self.btn_cancel_loan.setEnabled(False)
        self.btn_cancel_loan.clicked.connect(self._cancel_loan)
        
        for btn in [self.btn_pay_loan, self.btn_loan_history, self.btn_cancel_loan]:
            btn.setFixedHeight(35)
            loan_actions.addWidget(btn)
        loan_actions.addStretch()
        
        right_layout.addLayout(loan_actions)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 600])
        
        layout.addWidget(splitter, 1)
        
        # Summary Bar
        self.summary_bar = QtWidgets.QLabel()
        self.summary_bar.setFixedHeight(40)
        layout.addWidget(self.summary_bar)
        
        self._update_summary()
        
        return tab

    def _create_prestamos_tab(self, c: dict) -> QtWidgets.QWidget:
        """Pestaña de gestión de préstamos"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Header
        header_lbl = QtWidgets.QLabel("💰 Gestión de Préstamos y Anticipos")
        header_lbl.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['text_primary']};")
        layout.addWidget(header_lbl)
        
        # Stats cards
        stats_layout = QtWidgets.QHBoxLayout()
        
        self.loan_stat_total = self._create_stat_card("Total Préstamos", "0", "#2196F3", c)
        self.loan_stat_activos = self._create_stat_card("Activos", "0", "#FF9800", c)
        self.loan_stat_balance = self._create_stat_card("Balance Total", "$0", "#F44336", c)
        
        stats_layout.addWidget(self.loan_stat_total)
        stats_layout.addWidget(self.loan_stat_activos)
        stats_layout.addWidget(self.loan_stat_balance)
        layout.addLayout(stats_layout)
        
        # Tabla de todos los préstamos
        self.all_loans_table = QtWidgets.QTableWidget(0, 7)
        self.all_loans_table.setHorizontalHeaderLabels([
            "ID", "Empleado", "Tipo", "Monto", "Balance", "Cuota", "Estado"
        ])
        self.all_loans_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.all_loans_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.all_loans_table)
        
        # Botón refresh
        btn_refresh = QtWidgets.QPushButton("🔄 Actualizar")
        btn_refresh.setFixedHeight(40)
        btn_refresh.clicked.connect(self._refresh_all_loans)
        layout.addWidget(btn_refresh)
        
        self._refresh_all_loans()
        
        return tab

    def _create_asistencia_tab(self, c: dict) -> QtWidgets.QWidget:
        """Pestaña de control de asistencia"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Header
        header_lbl = QtWidgets.QLabel("⏰ Control de Asistencia")
        header_lbl.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['text_primary']};")
        layout.addWidget(header_lbl)
        
        # Info
        info_lbl = QtWidgets.QLabel("Ver el módulo de Reloj Checador para control de asistencia detallado.")
        info_lbl.setStyleSheet(f"color: {c['text_secondary']}; font-style: italic;")
        layout.addWidget(info_lbl)
        
        # Resumen de asistencia
        self.attendance_table = QtWidgets.QTableWidget(0, 5)
        self.attendance_table.setHorizontalHeaderLabels(["Empleado", "Días Trabajados", "Retardos", "Faltas", "Horas Extra"])
        self.attendance_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.attendance_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.attendance_table)
        
        layout.addStretch()
        
        return tab

    def _create_nomina_tab(self, c: dict) -> QtWidgets.QWidget:
        """Pestaña de nómina"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Header
        header_lbl = QtWidgets.QLabel("📊 Información de Nómina")
        header_lbl.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['text_primary']};")
        layout.addWidget(header_lbl)
        
        # Tabla de nómina
        self.nomina_table = QtWidgets.QTableWidget(0, 6)
        self.nomina_table.setHorizontalHeaderLabels([
            "Empleado", "Salario Base", "Comisiones", "Deducciones", "Préstamos", "Neto"
        ])
        self.nomina_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.nomina_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.nomina_table)
        
        # Botones
        btn_layout = QtWidgets.QHBoxLayout()
        btn_calc = QtWidgets.QPushButton("🧮 Calcular Nómina")
        btn_calc.setFixedHeight(45)
        btn_calc.clicked.connect(self._calculate_payroll)
        btn_export = QtWidgets.QPushButton("📤 Exportar")
        btn_export.setFixedHeight(45)
        btn_export.clicked.connect(self._export_payroll)
        btn_layout.addWidget(btn_calc)
        btn_layout.addWidget(btn_export)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        layout.addStretch()
        
        return tab

    def _create_reportes_tab(self, c: dict) -> QtWidgets.QWidget:
        """Pestaña de reportes de empleados"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Header
        header_lbl = QtWidgets.QLabel("📈 Reportes de Recursos Humanos")
        header_lbl.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['text_primary']};")
        layout.addWidget(header_lbl)
        
        # Botones de reportes
        reports = [
            ("📋 Reporte de Empleados", "Lista completa con datos de contacto", "employees"),
            ("💰 Reporte de Préstamos", "Estado de todos los préstamos", "loans"),
            ("⏰ Reporte de Asistencia", "Resumen mensual de asistencia", "attendance"),
            ("📊 Reporte de Comisiones", "Comisiones del período", "commissions"),
        ]
        
        for title, desc, report_type in reports:
            group = QtWidgets.QGroupBox(title)
            group.setStyleSheet(f"""
                QGroupBox {{ font-weight: bold; border: 2px solid {c['border']}; border-radius: 8px; margin-top: 10px; padding: 15px; }}
                QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}
            """)
            g_layout = QtWidgets.QHBoxLayout(group)
            g_layout.addWidget(QtWidgets.QLabel(desc))
            g_layout.addStretch()
            btn = QtWidgets.QPushButton("Generar")
            btn.setFixedHeight(35)
            btn.clicked.connect(lambda checked, rt=report_type: self._generate_report(rt))
            g_layout.addWidget(btn)
            layout.addWidget(group)
        
        layout.addStretch()
        
        return tab

    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _create_stat_card(self, title: str, value: str, color: str, c: dict) -> QtWidgets.QFrame:
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

    # =========================================================================
    # DATA METHODS
    # =========================================================================
    
    def _load_employees(self):
        """Load employees from database."""
        status_map = {
            "Activos": "active",
            "Inactivos": "inactive",
            "Terminados": "terminated",
            "Todos": "all"
        }
        status = status_map.get(self.status_filter.currentText(), "active")
        
        employees = self.core.loan_engine.list_employees(status=status)
        
        self.employee_table.setRowCount(0)
        
        for emp in employees:
            row = self.employee_table.rowCount()
            self.employee_table.insertRow(row)
            
            self.employee_table.setItem(row, 0, QtWidgets.QTableWidgetItem(emp['employee_code']))
            self.employee_table.setItem(row, 1, QtWidgets.QTableWidgetItem(emp['name']))
            self.employee_table.setItem(row, 2, QtWidgets.QTableWidgetItem(emp.get('position', '')))
            
            commission = f"{float(emp.get('commission_rate', 0)):.1f}%"
            self.employee_table.setItem(row, 3, QtWidgets.QTableWidgetItem(commission))
            
            balance = f"${float(emp.get('current_loan_balance', 0)):,.2f}"
            balance_item = QtWidgets.QTableWidgetItem(balance)
            if float(emp.get('current_loan_balance', 0)) > 0:
                balance_item.setForeground(QtGui.QColor("#e74c3c"))
                balance_item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Weight.Bold))
            self.employee_table.setItem(row, 4, balance_item)
            
            status_text = emp.get('status', 'active').capitalize()
            status_item = QtWidgets.QTableWidgetItem(status_text)
            if status_text == 'Active':
                status_item.setForeground(QtGui.QColor("#27ae60"))
            else:
                status_item.setForeground(QtGui.QColor("#95a5a6"))
            self.employee_table.setItem(row, 5, status_item)
            
            self.employee_table.item(row, 0).setData(QtCore.Qt.ItemDataRole.UserRole, emp)
        
        self._update_summary()
    
    def _filter_employees(self):
        """Filter employees by search text."""
        search_text = self.search_input.text().lower()
        
        for row in range(self.employee_table.rowCount()):
            code = self.employee_table.item(row, 0).text().lower()
            name = self.employee_table.item(row, 1).text().lower()
            
            should_show = search_text in code or search_text in name
            self.employee_table.setRowHidden(row, not should_show)
    
    def _on_employee_selected(self):
        """Handle employee selection."""
        selected = self.employee_table.selectedItems()
        if not selected:
            self.current_employee = None
            self.info_label.setText("Selecciona un empleado para ver detalles")
            self.btn_edit.setEnabled(False)
            self.btn_new_loan.setEnabled(False)
            self.btn_deactivate.setEnabled(False)
            self.btn_delete.setEnabled(False)
            self.loans_table.setRowCount(0)
            self.btn_pay_loan.setEnabled(False)
            self.btn_loan_history.setEnabled(False)
            self.btn_cancel_loan.setEnabled(False)
            return
        
        if not selected or len(selected) == 0:
            return
        row = selected[0].row()
        item = self.employee_table.item(row, 0)
        if not item:
            return
        emp = item.data(QtCore.Qt.ItemDataRole.UserRole)
        self.current_employee = emp
        
        summary = self.core.loan_engine.get_employee_loan_summary(emp['id'])
        
        info_html = f"""
        <div style='padding: 10px;'>
            <h3 style='margin: 0;'>{emp['name']}</h3>
            <p style='margin: 5px 0;'><b>Código:</b> {emp['employee_code']} | <b>Puesto:</b> {emp.get('position', 'N/A')}</p>
            <hr>
            <table style='width: 100%; font-size: 13px;'>
                <tr><td><b>Salario Base:</b></td><td style='text-align: right;'>${float(emp.get('base_salary', 0)):,.2f}</td></tr>
                <tr><td><b>Comisión:</b></td><td style='text-align: right;'>{float(emp.get('commission_rate', 0)):.1f}%</td></tr>
                <tr><td><b>Límite Préstamo:</b></td><td style='text-align: right;'>${summary['loan_limit']:,.2f}</td></tr>
                <tr><td><b>Balance Actual:</b></td><td style='text-align: right; color: #e74c3c;'>${summary['current_balance']:,.2f}</td></tr>
                <tr><td><b>Disponible:</b></td><td style='text-align: right; color: #27ae60;'>${summary['loan_limit'] - summary['current_balance']:,.2f}</td></tr>
            </table>
        </div>
        """
        
        self.info_label.setText(info_html)
        
        self.btn_edit.setEnabled(True)
        self.btn_new_loan.setEnabled(emp['status'] == 'active')
        self.btn_deactivate.setEnabled(True)
        self.btn_deactivate.setText("✅ Activar" if emp['status'] != 'active' else "🚫 Desactivar")
        self.btn_delete.setEnabled(True)
        
        self._load_loans(emp['id'])
    
    def _load_loans(self, employee_id):
        """Load loans for employee."""
        loans = self.core.loan_engine.list_loans(employee_id=employee_id, status='all')
        
        self.loans_table.setRowCount(0)
        
        for loan in loans:
            row = self.loans_table.rowCount()
            self.loans_table.insertRow(row)
            
            self.loans_table.setItem(row, 0, QtWidgets.QTableWidgetItem(f"#{loan['id']}"))
            
            loan_type = "Anticipo" if loan['loan_type'] == 'advance' else "Préstamo"
            self.loans_table.setItem(row, 1, QtWidgets.QTableWidgetItem(loan_type))
            
            self.loans_table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"${float(loan['amount']):,.2f}"))
            
            balance = float(loan['balance'])
            balance_item = QtWidgets.QTableWidgetItem(f"${balance:,.2f}")
            if balance > 0:
                balance_item.setForeground(QtGui.QColor("#e74c3c"))
            else:
                balance_item.setForeground(QtGui.QColor("#27ae60"))
            self.loans_table.setItem(row, 3, balance_item)
            
            self.loans_table.setItem(row, 4, QtWidgets.QTableWidgetItem(f"${float(loan.get('installment_amount', 0)):,.2f}"))
            
            status = loan['status'].capitalize()
            status_item = QtWidgets.QTableWidgetItem(status)
            if status == 'Active':
                status_item.setForeground(QtGui.QColor("#3498db"))
            elif status == 'Paid':
                status_item.setForeground(QtGui.QColor("#27ae60"))
            else:
                status_item.setForeground(QtGui.QColor("#95a5a6"))
            self.loans_table.setItem(row, 5, status_item)
            
            self.loans_table.item(row, 0).setData(QtCore.Qt.ItemDataRole.UserRole, loan)
    
    def _refresh_all_loans(self):
        """Refresh all loans table in Préstamos tab."""
        try:
            loans = self.core.loan_engine.list_loans(status='all')
            
            total = len(loans)
            activos = len([l for l in loans if l['status'] == 'active'])
            balance = sum(float(l.get('balance', 0)) for l in loans)
            
            self.loan_stat_total.findChild(QtWidgets.QLabel, "value").setText(str(total))
            self.loan_stat_activos.findChild(QtWidgets.QLabel, "value").setText(str(activos))
            self.loan_stat_balance.findChild(QtWidgets.QLabel, "value").setText(f"${balance:,.0f}")
            
            self.all_loans_table.setRowCount(len(loans))
            for i, loan in enumerate(loans):
                emp = self.core.loan_engine.get_employee(loan.get('employee_id'))
                emp_name = emp['name'] if emp else "N/A"
                
                values = [
                    f"#{loan['id']}",
                    emp_name,
                    "Anticipo" if loan['loan_type'] == 'advance' else "Préstamo",
                    f"${float(loan['amount']):,.2f}",
                    f"${float(loan['balance']):,.2f}",
                    f"${float(loan.get('installment_amount', 0)):,.2f}",
                    loan['status'].capitalize()
                ]
                for j, val in enumerate(values):
                    item = QtWidgets.QTableWidgetItem(str(val))
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    self.all_loans_table.setItem(i, j, item)
        except Exception as e:
            print(f"Error refreshing loans: {e}")

    # =========================================================================
    # ACTION METHODS
    # =========================================================================
    
    def _create_employee(self):
        dialog = EmployeeDialog(self.core.loan_engine, parent=self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            QtWidgets.QMessageBox.information(self, "Éxito", "Empleado creado exitosamente")
            self._load_employees()
            self.employees_updated.emit()
    
    def _edit_employee(self):
        if not self.current_employee:
            return
        
        dialog = EmployeeDialog(self.core.loan_engine, employee_id=self.current_employee['id'], parent=self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            QtWidgets.QMessageBox.information(self, "Éxito", "Empleado actualizado")
            self._load_employees()
            self.employees_updated.emit()
    
    def _create_loan(self):
        if not self.current_employee:
            return
        
        dialog = LoanCreateDialog(self.core.loan_engine, employee_id=self.current_employee['id'], parent=self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._load_employees()
            self._on_employee_selected()
    
    def _pay_loan(self):
        selected = self.loans_table.selectedItems()
        if not selected:
            return
        
        row = selected[0].row()
        item = self.loans_table.item(row, 0)
        
        if not item:
            return
            
        loan = item.data(QtCore.Qt.ItemDataRole.UserRole)
        
        if not loan or loan['status'] != 'active':
            QtWidgets.QMessageBox.warning(self, "Error", "Solo se pueden pagar préstamos activos")
            return
        
        dialog = LoanPaymentDialog(self.core.loan_engine, loan_id=loan['id'], parent=self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self._load_employees()
            self._on_employee_selected()
    
    def _show_loan_history(self):
        selected = self.loans_table.selectedItems()
        if not selected or len(selected) == 0:
            return

        row = selected[0].row()
        item = self.loans_table.item(row, 0)
        if not item:
            return
        loan = item.data(QtCore.Qt.ItemDataRole.UserRole)
        
        history = self.core.loan_engine.get_payment_history(loan['id'])
        
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(f"Historial - Préstamo #{loan['id']}")
        dialog.setMinimumSize(600, 400)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        table = QtWidgets.QTableWidget()
        table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Fecha", "Monto", "Tipo", "Balance", "Notas"])
        table.horizontalHeader().setStretchLastSection(True)
        
        for payment in history:
            row_idx = table.rowCount()
            table.insertRow(row_idx)
            
            try:
                date = datetime.fromisoformat(str(payment['payment_date'])).strftime("%d/%m/%Y %H:%M")
            except (ValueError, TypeError):
                date = str(payment.get('payment_date', 'N/A'))
            table.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(date))
            table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(f"${float(payment['amount']):,.2f}"))
            table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(payment['payment_type']))
            table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(f"${float(payment['balance_after']):,.2f}"))
            table.setItem(row_idx, 4, QtWidgets.QTableWidgetItem(payment.get('notes', '')))
        
        layout.addWidget(table)
        
        close_btn = QtWidgets.QPushButton("Cerrar")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()
    
    def _cancel_loan(self):
        selected = self.loans_table.selectedItems()
        if not selected or len(selected) == 0:
            return

        row = selected[0].row()
        item = self.loans_table.item(row, 0)
        if not item:
            return
        loan = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if not loan:
            return

        if loan.get('status') != 'active':
            QtWidgets.QMessageBox.warning(self, "Error", "Solo se pueden cancelar préstamos activos")
            return
        
        reason, ok = QtWidgets.QInputDialog.getText(
            self, "Cancelar Préstamo", f"¿Razón para cancelar préstamo #{loan['id']}?"
        )
        
        if ok and reason:
            try:
                from app.core import STATE
                self.core.loan_engine.cancel_loan(loan['id'], STATE.user_id, reason)
                QtWidgets.QMessageBox.information(self, "Éxito", "Préstamo cancelado")
                self._load_employees()
                self._on_employee_selected()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))
    
    def _toggle_employee_status(self):
        if not self.current_employee:
            return
        
        current_status = self.current_employee['status']
        new_status = 'active' if current_status != 'active' else 'inactive'
        
        try:
            self.core.loan_engine.update_employee(self.current_employee['id'], status=new_status)
            QtWidgets.QMessageBox.information(
                self, "Éxito", f"Empleado {'activado' if new_status == 'active' else 'desactivado'}"
            )
            self._load_employees()
            self.employees_updated.emit()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
    
    def _delete_employee(self):
        if not self.current_employee:
            return
            
        confirm = QtWidgets.QMessageBox.question(
            self, "Confirmar",
            f"¿Eliminar a {self.current_employee['name']}?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if confirm == QtWidgets.QMessageBox.StandardButton.Yes:
            try:
                self.core.loan_engine.delete_employee(self.current_employee['id'])
                QtWidgets.QMessageBox.information(self, "Éxito", "Empleado eliminado")
                self.current_employee = None
                self._load_employees()
                self.employees_updated.emit()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def _on_loan_selected(self):
        selected = bool(self.loans_table.selectedItems())
        self.btn_pay_loan.setEnabled(selected)
        self.btn_loan_history.setEnabled(selected)
        self.btn_cancel_loan.setEnabled(selected)
    
    def _update_summary(self):
        try:
            all_employees = self.core.loan_engine.list_employees(status='all')
            active = len([e for e in all_employees if e['status'] == 'active'])
            total_balance = sum(float(e.get('current_loan_balance', 0)) for e in all_employees)
            outstanding_loans = self.core.loan_engine.get_outstanding_loans()
            
            self.summary_bar.setText(
                f"📊 <b>Total:</b> {len(all_employees)} | "
                f"<b>Activos:</b> {active} | "
                f"<b>Préstamos:</b> {len(outstanding_loans)} | "
                f"<b>Balance:</b> <span style='color: #e74c3c;'>${total_balance:,.2f}</span>"
            )
        except Exception:
            self.summary_bar.setText("📊 Cargando...")
    
    def _calculate_payroll(self):
        """Calculate payroll for all active employees"""
        try:
            employees = self.core.loan_engine.list_employees(status='active')

            self.nomina_table.setRowCount(len(employees))

            # FIX 2026-01-30: Calcular comisiones de ventas reales del mes actual
            from datetime import datetime, timedelta
            today = datetime.now()
            first_day = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            date_from = first_day.strftime("%Y-%m-%d")
            date_to = today.strftime("%Y-%m-%d")

            for i, emp in enumerate(employees):
                base_salary = float(emp.get('base_salary', 0))
                commission_rate = float(emp.get('commission_rate', 0)) / 100.0  # Convert % to decimal
                loan_balance = float(emp.get('current_loan_balance', 0))
                employee_id = emp.get('id')

                # FIX: Calcular comisiones de ventas reales del empleado en el período
                commissions = 0.0
                try:
                    sales_sql = """
                        SELECT COALESCE(SUM(total), 0) as total_sales
                        FROM sales
                        WHERE user_id = %s
                        AND timestamp BETWEEN %s AND %s
                        AND status != 'cancelled'
                    """
                    sales_result = self.core.db.execute_query(
                        sales_sql,
                        (employee_id, f"{date_from} 00:00:00", f"{date_to} 23:59:59")
                    )
                    # FIX 2026-02-01: Validar sales_result con len() antes de acceder a [0]
                    if sales_result and len(sales_result) > 0 and sales_result[0]:
                        total_sales = float(sales_result[0].get('total_sales', 0) or 0)
                        commissions = total_sales * commission_rate
                except Exception:
                    commissions = 0.0

                # Calculate deductions
                deductions = min(loan_balance, base_salary * 0.3)  # Max 30% deduction

                # Net salary
                net_salary = base_salary + commissions - deductions

                values = [
                    emp.get('name', ''),
                    f"${base_salary:,.2f}",
                    f"${commissions:,.2f}",
                    f"${0:,.2f}",  # Other deductions
                    f"${deductions:,.2f}",
                    f"${net_salary:,.2f}"
                ]

                for j, val in enumerate(values):
                    item = QtWidgets.QTableWidgetItem(str(val))
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    self.nomina_table.setItem(i, j, item)

            QtWidgets.QMessageBox.information(self, "Nómina", f"Nómina calculada para {len(employees)} empleados\nPeríodo: {date_from} a {date_to}")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al calcular nómina: {e}")
    
    def _export_payroll(self):
        """Export payroll to CSV"""
        try:
            import csv

            from PyQt6.QtWidgets import QFileDialog
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Exportar Nómina", "", "CSV Files (*.csv)"
            )
            
            if not file_path:
                return
            
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Header
                headers = [self.nomina_table.horizontalHeaderItem(i).text() 
                          for i in range(self.nomina_table.columnCount())]
                writer.writerow(headers)
                
                # Data
                for row in range(self.nomina_table.rowCount()):
                    row_data = []
                    for col in range(self.nomina_table.columnCount()):
                        item = self.nomina_table.item(row, col)
                        row_data.append(item.text() if item else '')
                    writer.writerow(row_data)
            
            QtWidgets.QMessageBox.information(self, "Exportar", f"Nómina exportada a:\n{file_path}")
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al exportar: {e}")
    
    def _generate_report(self, report_type: str):
        """Generate and export a report based on type"""
        try:
            import csv

            from PyQt6.QtWidgets import QFileDialog
            
            report_names = {
                'employees': 'Reporte_Empleados',
                'loans': 'Reporte_Prestamos',
                'attendance': 'Reporte_Asistencia',
                'commissions': 'Reporte_Comisiones'
            }
            
            file_name = report_names.get(report_type, 'Reporte')
            file_path, _ = QFileDialog.getSaveFileName(
                self, f"Exportar {file_name}", f"{file_name}.csv", "CSV Files (*.csv)"
            )
            
            if not file_path:
                return
            
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                if report_type == 'employees':
                    employees = self.core.loan_engine.list_employees(status='all')
                    writer.writerow(['Código', 'Nombre', 'Puesto', 'Teléfono', 'Email', 'Estado'])
                    for emp in employees:
                        writer.writerow([
                            emp.get('employee_code', ''),
                            emp.get('name', ''),
                            emp.get('position', ''),
                            emp.get('phone', ''),
                            emp.get('email', ''),
                            emp.get('status', '')
                        ])
                        
                elif report_type == 'loans':
                    loans = self.core.loan_engine.list_loans(status='all')
                    writer.writerow(['ID', 'Empleado', 'Tipo', 'Monto', 'Balance', 'Cuota', 'Estado'])
                    for loan in loans:
                        emp = self.core.loan_engine.get_employee(loan.get('employee_id'))
                        emp_name = emp['name'] if emp else 'N/A'
                        writer.writerow([
                            loan.get('id', ''),
                            emp_name,
                            loan.get('loan_type', ''),
                            f"${float(loan.get('amount', 0)):,.2f}",
                            f"${float(loan.get('balance', 0)):,.2f}",
                            f"${float(loan.get('installment_amount', 0)):,.2f}",
                            loan.get('status', '')
                        ])
                        
                elif report_type == 'attendance':
                    writer.writerow(['Empleado', 'Días Trabajados', 'Retardos', 'Faltas', 'Horas Extra'])
                    employees = self.core.loan_engine.list_employees(status='active')
                    for emp in employees:
                        writer.writerow([emp.get('name', ''), '0', '0', '0', '0'])
                    
                elif report_type == 'commissions':
                    writer.writerow(['Empleado', 'Ventas', 'Tasa Comisión', 'Comisión Generada'])
                    employees = self.core.loan_engine.list_employees(status='active')
                    for emp in employees:
                        rate = float(emp.get('commission_rate', 0))
                        writer.writerow([emp.get('name', ''), '$0.00', f'{rate:.1f}%', '$0.00'])
            
            QtWidgets.QMessageBox.information(self, "Reporte", f"Reporte generado:\n{file_path}")
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al generar reporte: {e}")
    
    def refresh(self):
        self._load_employees()
        if self.current_employee:
            self._on_employee_selected()
    
    # =========================================================================
    # THEME
    # =========================================================================
    
    def update_theme(self):
        theme = (self.core.get_app_config() or {}).get("theme", "Light")
        c = theme_manager.get_colors(theme)
        
        self.setStyleSheet(f"background-color: {c['bg_main']}; color: {c['text_primary']};")
        
        if hasattr(self, 'header'):
            self.header.setStyleSheet(f"""
                QFrame {{
                    background: {c['bg_secondary']};
                    border-bottom: 2px solid {c['accent']};
                }}
            """)
            
        if hasattr(self, 'header_label'):
            self.header_label.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['text_primary']}; background: transparent;")
        
        if hasattr(self, 'tab_widget'):
            self.tab_widget.setStyleSheet(f"""
                QTabWidget::pane {{ border: 1px solid {c['border']}; background: {c['bg_secondary']}; }}
                QTabBar::tab {{
                    background: {c['bg_main']}; color: {c['text_secondary']};
                    padding: 12px 20px; margin-right: 2px;
                    border: 1px solid {c['border']}; border-bottom: none;
                    border-top-left-radius: 4px; border-top-right-radius: 4px;
                }}
                QTabBar::tab:selected {{
                    background: {c['bg_secondary']}; color: {c['text_primary']};
                    font-weight: bold; border-bottom: 2px solid {c['accent']};
                }}
            """)

        if hasattr(self, 'employee_table'):
            self.employee_table.setStyleSheet(f"""
                QTableWidget {{
                    background-color: {c['bg_main']}; color: {c['text_primary']};
                    border: 1px solid {c['border']}; border-radius: 5px;
                }}
                QHeaderView::section {{
                    background-color: {c['table_header_bg']}; color: {c['table_header_text']};
                    padding: 10px; font-weight: bold; border: none;
                }}
                QTableWidget::item:selected {{
                    background-color: {c['table_selected']}; color: {c['text_primary']};
                }}
            """)
            
        if hasattr(self, 'loans_table'):
            self.loans_table.setStyleSheet(self.employee_table.styleSheet())
            
        if hasattr(self, 'summary_bar'):
            self.summary_bar.setStyleSheet(f"""
                background-color: {c['bg_secondary']}; color: {c['text_primary']};
                padding: 10px; border-radius: 5px; border: 1px solid {c['border']};
            """)
            
        if hasattr(self, 'info_card'):
            self.info_card.setStyleSheet(f"""
                QGroupBox {{
                    font-weight: bold; border: 2px solid {c['accent']}; border-radius: 8px;
                    margin-top: 10px; padding: 15px; background-color: {c['bg_secondary']};
                    color: {c['text_primary']};
                }}
            """)

        if hasattr(self, 'search_input'):
            self.search_input.setStyleSheet(f"""
                padding: 10px; font-size: 14px; 
                border: 1px solid {c['border']}; border-radius: 5px;
                background-color: {c['input_bg']}; color: {c['text_primary']};
            """)

        if hasattr(self, 'btn_new_employee'):
            self.btn_new_employee.setStyleSheet(f"""
                background-color: {c['btn_success']}; color: white;
                font-weight: bold; padding: 10px; border-radius: 5px;
            """)

        self.style().unpolish(self)
        self.style().polish(self)

    def showEvent(self, event):
        """Apply theme when tab is shown."""
        super().showEvent(event)
        self.update_theme()

