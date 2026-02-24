"""
EMPLOYEE & LOAN DIALOGS
UI dialogs for employee management and loan processing
"""

from datetime import datetime, timedelta
from decimal import Decimal

from PyQt6 import QtCore, QtGui, QtWidgets


class EmployeeDialog(QtWidgets.QDialog):
    """Dialog for creating/editing employees."""
    
    def __init__(self, loan_engine, employee_id=None, parent=None):
        super().__init__(parent)
        self.loan_engine = loan_engine
        self.employee_id = employee_id
        self.result_data = None
        
        self.setWindowTitle("Nuevo Empleado" if not employee_id else "Editar Empleado")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self._build_ui()
        
        if employee_id:
            self._load_employee()
    
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Form
        form = QtWidgets.QFormLayout()
        
        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText("Nombre completo")
        form.addRow("Nombre:*", self.name_input)
        
        self.position_input = QtWidgets.QLineEdit()
        self.position_input.setPlaceholderText("Cajero, Vendedor, Gerente...")
        form.addRow("Puesto:", self.position_input)
        
        self.phone_input = QtWidgets.QLineEdit()
        self.phone_input.setPlaceholderText("(555) 123-4567")
        form.addRow("Teléfono:", self.phone_input)
        
        self.email_input = QtWidgets.QLineEdit()
        self.email_input.setPlaceholderText("empleado@ejemplo.com")
        form.addRow("Email:", self.email_input)
        
        self.salary_input = QtWidgets.QDoubleSpinBox()
        self.salary_input.setRange(0, 999999)
        self.salary_input.setPrefix("$")
        self.salary_input.setValue(0)
        form.addRow("Salario Base:", self.salary_input)
        
        self.commission_input = QtWidgets.QDoubleSpinBox()
        self.commission_input.setRange(0, 100)
        self.commission_input.setSuffix("%")
        self.commission_input.setValue(0)
        form.addRow("Comisión Ventas:", self.commission_input)
        
        self.loan_limit_input = QtWidgets.QDoubleSpinBox()
        self.loan_limit_input.setRange(0, 999999)
        self.loan_limit_input.setPrefix("$")
        self.loan_limit_input.setValue(5000)
        form.addRow("Límite Préstamo:", self.loan_limit_input)
        
        self.hire_date = QtWidgets.QDateEdit()
        self.hire_date.setCalendarPopup(True)
        self.hire_date.setDate(QtCore.QDate.currentDate())
        form.addRow("Fecha Contratación:", self.hire_date)
        
        self.notes_input = QtWidgets.QTextEdit()
        self.notes_input.setMaximumHeight(80)
        form.addRow("Notas:", self.notes_input)
        
        layout.addLayout(form)
        
        # Buttons
        buttons = QtWidgets.QHBoxLayout()
        
        cancel_btn = QtWidgets.QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QtWidgets.QPushButton("Guardar")
        save_btn.clicked.connect(self._save)
        # Style applied via showEvent
        
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)
        
        layout.addLayout(buttons)
    
    def _load_employee(self):
        """Load existing employee data."""
        employee = self.loan_engine.get_employee(self.employee_id)
        if not employee:
            return
        
        self.name_input.setText(employee.get('name', ''))
        self.position_input.setText(employee.get('position', ''))
        self.phone_input.setText(employee.get('phone', ''))
        self.email_input.setText(employee.get('email', ''))
        self.salary_input.setValue(float(employee.get('base_salary', 0)))
        self.commission_input.setValue(float(employee.get('commission_rate', 0)))
        self.loan_limit_input.setValue(float(employee.get('loan_limit', 0)))
        self.notes_input.setPlainText(employee.get('notes', ''))
        
        if employee.get('hire_date'):
            date = QtCore.QDate.fromString(employee['hire_date'], "yyyy-MM-dd")
            self.hire_date.setDate(date)
    
    def _save(self):
        """Save employee."""
        name = self.name_input.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Error", "El nombre es requerido")
            return
        
        data = {
            'name': name,
            'position': self.position_input.text().strip(),
            'phone': self.phone_input.text().strip(),
            'email': self.email_input.text().strip(),
            'base_salary': self.salary_input.value(),
            'commission_rate': self.commission_input.value(),
            'loan_limit': self.loan_limit_input.value(),
            'hire_date': self.hire_date.date().toString("yyyy-MM-dd"),
            'notes': self.notes_input.toPlainText().strip()
        }
        
        try:
            if self.employee_id:
                # Update
                self.loan_engine.update_employee(self.employee_id, **data)
            else:
                # Create
                self.employee_id = self.loan_engine.create_employee(**data)
            
            self.result_data = data
            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al guardar: {str(e)}")
    
    def showEvent(self, event):
        """Apply theme colors"""
        super().showEvent(event)
        try:
            from app.utils.theme_manager import theme_manager
            c = theme_manager.get_colors()
            for btn in self.findChildren(QtWidgets.QPushButton):
                if "Guardar" in btn.text():
                    btn.setStyleSheet(f"background-color: {c['btn_success']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
        except Exception:
            pass

class LoanCreateDialog(QtWidgets.QDialog):
    """Dialog for creating a new loan/advance."""
    
    def __init__(self, loan_engine, employee_id=None, parent=None):
        super().__init__(parent)
        self.loan_engine = loan_engine
        self.employee_id = employee_id
        self.result_data = None
        
        self.setWindowTitle("Nuevo Préstamo/Anticipo")
        self.setModal(True)
        self.setMinimumWidth(550)
        
        self._build_ui()
    
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Employee Selection
        emp_layout = QtWidgets.QHBoxLayout()
        emp_layout.addWidget(QtWidgets.QLabel("Empleado:*"))
        
        self.employee_combo = QtWidgets.QComboBox()
        self.employee_combo.currentIndexChanged.connect(self._update_employee_info)
        emp_layout.addWidget(self.employee_combo, 1)
        
        layout.addLayout(emp_layout)
        
        # Employee Info
        self.employee_info = QtWidgets.QLabel()
        self.employee_info.setStyleSheet("background: #ecf0f1; padding: 10px; border-radius: 5px;")
        layout.addWidget(self.employee_info)
        
        # Loan Details
        form = QtWidgets.QFormLayout()
        
        self.loan_type = QtWidgets.QComboBox()
        self.loan_type.addItems(["Anticipo (sin interés)", "Préstamo (con interés)"])
        self.loan_type.currentIndexChanged.connect(self._toggle_interest)
        form.addRow("Tipo:*", self.loan_type)
        
        self.amount_input = QtWidgets.QDoubleSpinBox()
        self.amount_input.setRange(1, 999999)
        self.amount_input.setPrefix("$")
        self.amount_input.setValue(500)
        self.amount_input.valueChanged.connect(self._calculate_installment)
        form.addRow("Monto:*", self.amount_input)
        
        self.installments_input = QtWidgets.QSpinBox()
        self.installments_input.setRange(1, 24)
        self.installments_input.setValue(1)
        self.installments_input.valueChanged.connect(self._calculate_installment)
        form.addRow("Número de Pagos:", self.installments_input)
        
        self.interest_input = QtWidgets.QDoubleSpinBox()
        self.interest_input.setRange(0, 100)
        self.interest_input.setSuffix("% anual")
        self.interest_input.setValue(0)
        self.interest_input.setEnabled(False)
        self.interest_input.valueChanged.connect(self._calculate_installment)
        form.addRow("Tasa de Interés:", self.interest_input)
        
        self.installment_label = QtWidgets.QLabel("$0.00 / pago")
        self.installment_label.setStyleSheet("font-weight: bold; color: #27ae60; font-size: 14px;")
        form.addRow("Monto por Pago:", self.installment_label)
        
        self.due_date = QtWidgets.QDateEdit()
        self.due_date.setCalendarPopup(True)
        self.due_date.setDate(QtCore.QDate.currentDate().addMonths(1))
        form.addRow("Fecha Límite:", self.due_date)
        
        self.notes_input = QtWidgets.QTextEdit()
        self.notes_input.setMaximumHeight(60)
        self.notes_input.setPlaceholderText("Razón del préstamo, términos especiales, etc.")
        form.addRow("Notas:", self.notes_input)
        
        layout.addLayout(form)
        
        # Buttons
        buttons = QtWidgets.QHBoxLayout()
        
        cancel_btn = QtWidgets.QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        
        create_btn = QtWidgets.QPushButton("✓ Crear Préstamo")
        create_btn.clicked.connect(self._create_loan)
        # Style applied via showEvent
        
        buttons.addWidget(cancel_btn)
        buttons.addWidget(create_btn)
        
        layout.addLayout(buttons)
        
        # Initial calculation
        self._calculate_installment()
        
        # Load employees LAST (after all widgets created)
        self._load_employees()
    
    def _load_employees(self):
        """Load active employees into combo."""
        employees = self.loan_engine.list_employees(status='active')
        
        for emp in employees:
            self.employee_combo.addItem(
                f"{emp['employee_code']} - {emp['name']}",
                emp['id']
            )
        
        # Select pre-selected employee if provided
        if self.employee_id:
            for i in range(self.employee_combo.count()):
                if self.employee_combo.itemData(i) == self.employee_id:
                    self.employee_combo.setCurrentIndex(i)
                    break
    
    def _update_employee_info(self):
        """Update employee info display."""
        emp_id = self.employee_combo.currentData()
        if not emp_id:
            return
        
        summary = self.loan_engine.get_employee_loan_summary(emp_id)
        
        info = f"""
        <b>Límite:</b> ${summary['loan_limit']:.2f} | 
        <b>Balance Actual:</b> ${summary['current_balance']:.2f} | 
        <b>Disponible:</b> ${summary['loan_limit'] - summary['current_balance']:.2f}
        """
        
        self.employee_info.setText(info)
    
    def _toggle_interest(self):
        """Enable/disable interest based on loan type."""
        is_loan = self.loan_type.currentIndex() == 1
        self.interest_input.setEnabled(is_loan)
        if is_loan:
            self.interest_input.setValue(10.0)
        else:
            self.interest_input.setValue(0.0)
        self._calculate_installment()
    
    def _calculate_installment(self):
        """Calculate and display installment amount."""
        amount = Decimal(str(self.amount_input.value()))
        installments = self.installments_input.value()
        interest = self.interest_input.value()
        
        try:
            installment = self.loan_engine.calculate_installment(amount, installments, interest)
            self.installment_label.setText(f"${installment:.2f} / pago")
        except Exception as e:
            self.installment_label.setText(f"Error: {str(e)}")
    
    def _create_loan(self):
        """Create the loan."""
        emp_id = self.employee_combo.currentData()
        if not emp_id:
            QtWidgets.QMessageBox.warning(self, "Error", "Selecciona un empleado")
            return
        
        amount = self.amount_input.value()
        if amount <= 0:
            QtWidgets.QMessageBox.warning(self, "Error", "El monto debe ser mayor a cero")
            return
        
        try:
            from app.core import STATE
            
            loan_id = self.loan_engine.create_loan(
                employee_id=emp_id,
                amount=amount,
                loan_type='advance' if self.loan_type.currentIndex() == 0 else 'loan',
                installments=self.installments_input.value(),
                interest_rate=self.interest_input.value(),
                approved_by=STATE.user_id,
                due_date=self.due_date.date().toString("yyyy-MM-dd"),
                notes=self.notes_input.toPlainText().strip()
            )
            
            self.result_data = {'loan_id': loan_id}
            
            QtWidgets.QMessageBox.information(
                self,
                "Préstamo Creado",
                f"Préstamo #{loan_id} creado exitosamente.\n"
                f"Monto: ${amount:.2f}\n"
                f"Pagos: {self.installments_input.value()}"
            )
            
            self.accept()
        except ValueError as e:
            QtWidgets.QMessageBox.warning(self, "Error de Validación", str(e))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al crear préstamo: {str(e)}")
    
    def showEvent(self, event):
        """Apply theme colors"""
        super().showEvent(event)
        try:
            from app.utils.theme_manager import theme_manager
            c = theme_manager.get_colors()
            for btn in self.findChildren(QtWidgets.QPushButton):
                if "Crear" in btn.text():
                    btn.setStyleSheet(f"background-color: {c['btn_success']}; color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
        except Exception:
            pass

class LoanPaymentDialog(QtWidgets.QDialog):
    """Dialog for recording a loan payment."""
    
    def __init__(self, loan_engine, loan_id=None, parent=None):
        super().__init__(parent)
        self.loan_engine = loan_engine
        self.loan_id = loan_id
        self.loan = None
        self.result_data = None
        
        self.setWindowTitle("Registrar Pago de Préstamo")
        self.setModal(True)
        self.setMinimumWidth(450)
        
        self._build_ui()
        
        if loan_id:
            self._load_loan()
    
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Loan Info
        self.loan_info = QtWidgets.QLabel()
        self.loan_info.setStyleSheet("background: #3498db; color: white; padding: 15px; border-radius: 5px; font-size: 14px;")
        layout.addWidget(self.loan_info)
        
        # Payment Amount
        form = QtWidgets.QFormLayout()
        
        self.amount_input = QtWidgets.QDoubleSpinBox()
        self.amount_input.setRange(0.01, 999999)
        self.amount_input.setPrefix("$")
        self.amount_input.setValue(0)
        self.amount_input.valueChanged.connect(self._update_remaining)
        form.addRow("Monto a Pagar:*", self.amount_input)
        
        self.remaining_label = QtWidgets.QLabel("$0.00")
        self.remaining_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        form.addRow("Saldo Restante:", self.remaining_label)
        
        self.notes_input = QtWidgets.QLineEdit()
        self.notes_input.setPlaceholderText("Notas opcionales...")
        form.addRow("Notas:", self.notes_input)
        
        layout.addLayout(form)
        
        # Quick Amount Buttons
        quick_layout = QtWidgets.QHBoxLayout()
        quick_layout.addWidget(QtWidgets.QLabel("Rápido:"))
        
        self.btn_installment = QtWidgets.QPushButton("1 Cuota")
        self.btn_installment.clicked.connect(lambda: self._quick_amount('installment'))
        
        self.btn_half = QtWidgets.QPushButton("50%")
        self.btn_half.clicked.connect(lambda: self._quick_amount('half'))
        
        self.btn_full = QtWidgets.QPushButton("Total")
        self.btn_full.clicked.connect(lambda: self._quick_amount('full'))
        
        quick_layout.addWidget(self.btn_installment)
        quick_layout.addWidget(self.btn_half)
        quick_layout.addWidget(self.btn_full)
        quick_layout.addStretch()
        
        layout.addLayout(quick_layout)
        
        layout.addSpacing(10)
        
        # Buttons
        buttons = QtWidgets.QHBoxLayout()
        
        cancel_btn = QtWidgets.QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        
        pay_btn = QtWidgets.QPushButton("✓ Registrar Pago")
        pay_btn.clicked.connect(self._record_payment)
        # Style applied via showEvent
        
        buttons.addWidget(cancel_btn)
        buttons.addWidget(pay_btn)
        
        layout.addLayout(buttons)
    
    def _load_loan(self):
        """Load loan details."""
        self.loan = self.loan_engine.get_loan(self.loan_id)
        if not self.loan:
            QtWidgets.QMessageBox.critical(self, "Error", "Préstamo no encontrado")
            self.reject()
            return
        
        employee = self.loan_engine.get_employee(self.loan['employee_id'])
        
        info = f"""
        <b>Empleado:</b> {employee['name']} ({employee['employee_code']})<br>
        <b>Préstamo:</b> #{self.loan_id} | {self.loan['loan_type'].title()}<br>
        <b>Monto Original:</b> ${self.loan['amount']:.2f} | 
        <b>Balance:</b> ${self.loan['balance']:.2f}
        """
        
        self.loan_info.setText(info)
        
        # Set initial amount to installment
        if self.loan['installment_amount']:
            self.amount_input.setValue(min(
                float(self.loan['installment_amount']),
                float(self.loan['balance'])
            ))
        else:
            self.amount_input.setValue(float(self.loan['balance']))
        
        self._update_remaining()
    
    def _update_remaining(self):
        """Update remaining balance display."""
        if not self.loan:
            return
        
        payment = self.amount_input.value()
        remaining = float(self.loan['balance']) - payment
        
        self.remaining_label.setText(f"${max(0, remaining):.2f}")
        
        if remaining < 0.01:
            self.remaining_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #27ae60;")
        else:
            self.remaining_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #e74c3c;")
    
    def _quick_amount(self, type):
        """Set quick amount."""
        if not self.loan:
            return
        
        balance = float(self.loan['balance'])
        
        if type == 'installment':
            amount = min(float(self.loan['installment_amount'] or balance), balance)
        elif type == 'half':
            amount = balance / 2
        else:  # full
            amount = balance
        
        self.amount_input.setValue(amount)
    
    def _record_payment(self):
        """Record the payment."""
        if not self.loan:
            return
        
        amount = self.amount_input.value()
        if amount <= 0:
            QtWidgets.QMessageBox.warning(self, "Error", "El monto debe ser mayor a cero")
            return
        
        if amount > float(self.loan['balance']):
            QtWidgets.QMessageBox.warning(
                self,
                "Error",
                f"El monto excede el balance (${self.loan['balance']:.2f})"
            )
            return
        
        try:
            from app.core import STATE
            
            payment_id = self.loan_engine.record_payment(
                loan_id=self.loan_id,
                amount=amount,
                payment_type='manual',
                user_id=STATE.user_id,
                notes=self.notes_input.text().strip()
            )
            
            self.result_data = {'payment_id': payment_id, 'amount': amount}
            
            remaining = float(self.loan['balance']) - amount
            
            if remaining < 0.01:
                QtWidgets.QMessageBox.information(
                    self,
                    "¡Préstamo Liquidado!",
                    f"Pago de ${amount:.2f} registrado.\n"
                    f"El préstamo ha sido completamente pagado."
                )
            else:
                QtWidgets.QMessageBox.information(
                    self,
                    "Pago Registrado",
                    f"Pago de ${amount:.2f} registrado exitosamente.\n"
                    f"Balance restante: ${remaining:.2f}"
                )
            
            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al registrar pago: {str(e)}")
