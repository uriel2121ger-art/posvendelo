"""
Dialog para registrar pagos/abonos de crédito de clientes
"""
import logging
from datetime import datetime

from PyQt6 import QtCore, QtWidgets

logger = logging.getLogger(__name__)


class CreditPaymentDialog(QtWidgets.QDialog):
    """Diálogo para registrar un abono al crédito de un cliente"""
    
    def __init__(self, customer_id, customer_name, current_balance, core, parent=None):
        super().__init__(parent)
        self.customer_id = customer_id
        self.customer_name = customer_name
        self.current_balance = float(current_balance)
        self.core = core
        self.payment_amount = 0.0
        
        self.setWindowTitle(f"Abono a Crédito - {customer_name}")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        self._build_ui()
        
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Info del cliente
        info_group = QtWidgets.QGroupBox("Información del Cliente")
        info_layout = QtWidgets.QFormLayout(info_group)
        
        self.lbl_customer = QtWidgets.QLabel(self.customer_name)
        self.lbl_customer.setStyleSheet("font-weight: bold; font-size: 14px;")
        info_layout.addRow("Cliente:", self.lbl_customer)
        
        self.lbl_balance = QtWidgets.QLabel(f"${self.current_balance:,.2f}")
        self.lbl_balance.setStyleSheet("color: #d32f2f; font-weight: bold; font-size: 16px;")
        info_layout.addRow("Saldo Actual:", self.lbl_balance)
        
        layout.addWidget(info_group)
        
        # Monto del pago
        payment_group = QtWidgets.QGroupBox("Abono")
        payment_layout = QtWidgets.QFormLayout(payment_group)
        
        self.spin_amount = QtWidgets.QDoubleSpinBox()
        self.spin_amount.setRange(0.01, self.current_balance)
        self.spin_amount.setDecimals(2)
        self.spin_amount.setPrefix("$ ")
        self.spin_amount.setValue(self.current_balance)  # Default: pagar todo
        self.spin_amount.valueChanged.connect(self._update_new_balance)
        self.spin_amount.setStyleSheet("font-size: 14px; padding: 5px;")
        payment_layout.addRow("Monto a Abonar:", self.spin_amount)
        
        self.lbl_new_balance = QtWidgets.QLabel(f"${0.00:,.2f}")
        self.lbl_new_balance.setStyleSheet("color: #388e3c; font-weight: bold; font-size: 14px;")
        payment_layout.addRow("Nuevo Saldo:", self.lbl_new_balance)
        
        layout.addWidget(payment_group)
        
        # Notas opcionales
        notes_group = QtWidgets.QGroupBox("Notas (Opcional)")
        notes_layout = QtWidgets.QVBoxLayout(notes_group)
        
        self.txt_notes = QtWidgets.QTextEdit()
        self.txt_notes.setMaximumHeight(80)
        self.txt_notes.setPlaceholderText("Ej: Pago en efectivo, Transferencia, etc.")
        notes_layout.addWidget(self.txt_notes)
        
        layout.addWidget(notes_group)
        
        # Botones
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        btn_save = QtWidgets.QPushButton("💰 Registrar Abono")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        btn_save.clicked.connect(self._save_payment)
        btn_layout.addWidget(btn_save)
        
        layout.addLayout(btn_layout)
        
        self._update_new_balance()
        
    def _update_new_balance(self):
        """Actualizar el nuevo saldo calculado"""
        amount = self.spin_amount.value()
        new_balance = max(0, self.current_balance - amount)
        self.lbl_new_balance.setText(f"${new_balance:,.2f}")
        
    def _save_payment(self):
        """Guardar el pago en la base de datos"""
        amount = self.spin_amount.value()
        
        if amount <= 0:
            QtWidgets.QMessageBox.warning(self, "Error", "El monto debe ser mayor a 0")
            return
            
        if amount > self.current_balance:
            QtWidgets.QMessageBox.warning(self, "Error", "El monto no puede ser mayor al saldo actual")
            return
        
        try:
            # Obtener balance actual de la BD
            customer_info = list(self.core.db.execute_query(
                "SELECT credit_balance FROM customers WHERE id = %s",
                (self.customer_id,)
            ))
            
            if not customer_info:
                QtWidgets.QMessageBox.critical(self, "Error", "Cliente no encontrado")
                return
                
            balance_before = float(customer_info[0]['credit_balance'] or 0.0)
            # CRÍTICO: balance_after se calcula para mostrar al usuario y para credit_history,
            # pero el UPDATE usa aritmética atómica para evitar race conditions
            balance_after = max(0, balance_before - amount)

            notes = self.txt_notes.toPlainText().strip() or "Abono a crédito"

            # Crear transacción
            ops = []

            # 1. Actualizar saldo del cliente - FIX RACE CONDITION
            # Auditoría 2026-01-30: Usar UPDATE atómico con GREATEST() para evitar:
            # - Race condition si dos pagos ocurren simultáneamente
            # - Saldos negativos si el balance cambió desde que se leyó
            update_sql = "UPDATE customers SET credit_balance = GREATEST(0, credit_balance - %s), synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
            ops.append((update_sql, (amount, self.customer_id)))
            
            # 2. Registrar en credit_history
            # CRITICAL FIX: Verificar si user_id y movement_type existen antes de INSERT
            try:
                table_info = self.core.db.get_table_info("credit_history")
                available_cols = [col.get('name') if isinstance(col, dict) else col[1] for col in table_info]
                has_user_id = "user_id" in available_cols
                has_movement_type = "movement_type" in available_cols
            except Exception as e:
                logger.warning(f"Could not get credit_history table info: {e}")
                has_user_id = False
                has_movement_type = False
            
            # Obtener user_id del estado global si existe
            try:
                from app.utils.state import STATE
                user_id = STATE.user_id if hasattr(STATE, 'user_id') else 1
            except Exception as e:
                logger.debug(f"Could not get user_id from STATE: {e}")
                user_id = 1
            
            if has_user_id:
                if has_movement_type:
                    history_sql = """INSERT INTO credit_history
                        (customer_id, transaction_type, movement_type, amount, balance_before, balance_after, timestamp, notes, user_id, synced)
                        VALUES (%s, 'PAYMENT', 'PAYMENT', %s, %s, %s, NOW(), %s, %s, 0)"""
                    ops.append((history_sql, (self.customer_id, amount, balance_before, balance_after, notes, user_id)))
                else:
                    history_sql = """INSERT INTO credit_history
                        (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes, user_id, synced)
                        VALUES (%s, 'PAYMENT', %s, %s, %s, NOW(), %s, %s, 0)"""
                    ops.append((history_sql, (self.customer_id, amount, balance_before, balance_after, notes, user_id)))
            else:
                # Fallback: INSERT sin user_id
                if has_movement_type:
                    history_sql = """INSERT INTO credit_history
                        (customer_id, transaction_type, movement_type, amount, balance_before, balance_after, timestamp, notes, synced)
                        VALUES (%s, 'PAYMENT', 'PAYMENT', %s, %s, %s, NOW(), %s, 0)"""
                    ops.append((history_sql, (self.customer_id, amount, balance_before, balance_after, notes)))
                else:
                    history_sql = """INSERT INTO credit_history
                        (customer_id, transaction_type, amount, balance_before, balance_after, timestamp, notes, synced)
                        VALUES (%s, 'PAYMENT', %s, %s, %s, NOW(), %s, 0)"""
                    ops.append((history_sql, (self.customer_id, amount, balance_before, balance_after, notes)))
            
            # Ejecutar transacción
            result = self.core.db.execute_transaction(ops)
            success = result.get('success') if isinstance(result, dict) else result
            if success:
                self.payment_amount = amount
                QtWidgets.QMessageBox.information(
                    self,
                    "Éxito",
                    f"Abono de ${amount:,.2f} registrado correctamente\\n\\nNuevo saldo: ${balance_after:,.2f}"
                )
                self.accept()
            else:
                QtWidgets.QMessageBox.critical(self, "Error", "No se pudo registrar el abono")
                
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Error al registrar abono: {str(e)}")
            import traceback
            traceback.print_exc()

    def showEvent(self, event):
        """Apply theme colors when dialog is shown."""
        super().showEvent(event)
        try:
            from app.utils.theme_manager import theme_manager
            c = theme_manager.get_colors()
            for btn in self.findChildren(QtWidgets.QPushButton):
                text = btn.text().lower()
                if any(w in text for w in ['guardar', 'save', 'aceptar', 'ok', 'crear', 'agregar']):
                    btn.setStyleSheet(f"background: {c['btn_success']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
                elif any(w in text for w in ['cancelar', 'cancel', 'cerrar', 'eliminar', 'delete']):
                    btn.setStyleSheet(f"background: {c['btn_danger']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
        except Exception as e:
            logger.debug(f"Could not apply theme colors: {e}")
