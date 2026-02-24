from datetime import datetime

from PyQt6 import QtCore, QtGui, QtWidgets


class CreditStatementDialog(QtWidgets.QDialog):
    def __init__(self, core, customer_id, customer_name, parent=None):
        super().__init__(parent)
        self.core = core
        self.customer_id = customer_id
        self.customer_name = customer_name
        self.setWindowTitle(f"Estado de Cuenta - {customer_name}")
        self.resize(800, 600)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Header
        header = QtWidgets.QLabel(f"Movimientos de Crédito: {self.customer_name}")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(header)
        
        # Table
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Fecha", "Tipo", "Descripción", "Cargo (+)", "Abono (-)"])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        # Footer totals
        footer_layout = QtWidgets.QHBoxLayout()
        self.lbl_balance = QtWidgets.QLabel("Saldo Actual: $0.00")
        self.lbl_balance.setStyleSheet("font-size: 16px; font-weight: bold;")
        footer_layout.addStretch()
        footer_layout.addWidget(self.lbl_balance)
        layout.addLayout(footer_layout)
        
        # Buttons
        btn_box = QtWidgets.QHBoxLayout()
        btn_print = QtWidgets.QPushButton("Imprimir")
        btn_print.clicked.connect(self._print_statement)
        btn_close = QtWidgets.QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        
        btn_box.addWidget(btn_print)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)

    def _load_data(self):
        movements = []
        
        # 1. Get all movements from credit_history (includes both CHARGE and payment)
        credit_history = self.core.db.execute_query(
            """SELECT timestamp, transaction_type, amount, notes, balance_before, balance_after 
               FROM credit_history 
               WHERE customer_id = %s 
               ORDER BY timestamp""",
            (self.customer_id,)
        )
        
        for row in credit_history:
            ch = dict(row)  # Convert sqlite3.Row to dict
            txn_type = (ch.get("transaction_type") or "").upper()
            is_charge = txn_type == "CHARGE"
            movements.append({
                "date": ch.get("timestamp") or "",
                "type": "Cargo" if is_charge else "Abono",
                "desc": ch.get("notes") or ("Venta a crédito" if is_charge else "Pago de crédito"),
                "amount": float(ch.get("amount") or 0),
                "is_charge": is_charge
            })
        
        # 2. Fallback: If no credit_history, try legacy sales and cash_movements
        if not movements:
            # Get Sales on Credit
            sales = self.core.db.execute_query(
                "SELECT id, timestamp, total FROM sales WHERE customer_id = %s AND payment_method = 'credit'", 
                (self.customer_id,)
            )
            
            for s in sales:
                movements.append({
                    "date": s["timestamp"],
                    "type": "Cargo",
                    "desc": f"Venta #{s['id']}",
                    "amount": float(s["total"]),
                    "is_charge": True
                })
            
            # Get Payments from cash_movements (legacy)
            payments = self.core.db.execute_query(
                "SELECT timestamp, amount, reason FROM cash_movements WHERE reason LIKE %s AND type = 'in'",
                (f"Abono Crédito Cliente #{self.customer_id}%",)
            )
            
            for p in payments:
                movements.append({
                    "date": p["timestamp"],
                    "type": "Abono",
                    "desc": p["reason"],
                    "amount": float(p["amount"]),
                    "is_charge": False
                })
            
            # Sort by date
            movements.sort(key=lambda x: x["date"])
        
        self.table.setRowCount(len(movements))
        balance = 0.0
        
        for i, mov in enumerate(movements):
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(mov["date"])))
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(mov["type"]))
            self.table.setItem(i, 2, QtWidgets.QTableWidgetItem(mov["desc"]))
            
            if mov["is_charge"]:
                self.table.setItem(i, 3, QtWidgets.QTableWidgetItem(f"${mov['amount']:.2f}"))
                self.table.setItem(i, 4, QtWidgets.QTableWidgetItem(""))
                balance += mov["amount"]
            else:
                self.table.setItem(i, 3, QtWidgets.QTableWidgetItem(""))
                self.table.setItem(i, 4, QtWidgets.QTableWidgetItem(f"${mov['amount']:.2f}"))
                balance -= mov["amount"]
                
        self.lbl_balance.setText(f"Saldo Calculado: ${balance:.2f}")

    def _print_statement(self):
        """Imprime el estado de cuenta a impresora térmica via CUPS."""
        import subprocess
        
        cfg = self.core.get_app_config() or {}
        printer_name = cfg.get("printer_name", "")
        
        if not printer_name:
            QtWidgets.QMessageBox.warning(
                self, "Sin Impresora", 
                "No hay impresora configurada.\nVaya a Configuración para configurar una."
            )
            return
        
        # Build statement content
        paper_width = cfg.get("ticket_paper_width", "80mm")
        line_width = 48 if paper_width == "80mm" else 32
        
        lines = []
        lines.append("=" * line_width)
        lines.append("ESTADO DE CUENTA".center(line_width))
        lines.append("=" * line_width)
        lines.append("")
        lines.append(f"Cliente: {self.customer_name}")
        lines.append(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        lines.append("-" * line_width)
        lines.append("")
        
        # Get movements from table
        total_charges = 0.0
        total_payments = 0.0
        
        for row in range(self.table.rowCount()):
            date_item = self.table.item(row, 0)
            type_item = self.table.item(row, 1)
            desc_item = self.table.item(row, 2)
            charge_item = self.table.item(row, 3)
            payment_item = self.table.item(row, 4)
            
            date_str = date_item.text()[:10] if date_item else ""
            mov_type = type_item.text() if type_item else ""
            desc = (desc_item.text()[:20] if desc_item else "")
            
            if charge_item and charge_item.text():
                amount_str = charge_item.text()
                try:
                    total_charges += float(amount_str.replace("$", "").replace(",", ""))
                except Exception:
                    pass
                lines.append(f"{date_str} {desc}")
                lines.append(f"  Cargo: {amount_str}")
            elif payment_item and payment_item.text():
                amount_str = payment_item.text()
                try:
                    total_payments += float(amount_str.replace("$", "").replace(",", ""))
                except Exception:
                    pass
                lines.append(f"{date_str} {desc}")
                lines.append(f"  Abono: {amount_str}")
        
        lines.append("")
        lines.append("-" * line_width)
        lines.append(f"Total Cargos:  ${total_charges:,.2f}")
        lines.append(f"Total Abonos: -${total_payments:,.2f}")
        lines.append("=" * line_width)
        
        balance = total_charges - total_payments
        lines.append(f"SALDO ACTUAL: ${balance:,.2f}".center(line_width))
        lines.append("=" * line_width)
        lines.append("")
        lines.append("")
        lines.append("")
        
        content = "\n".join(lines)
        
        try:
            result = subprocess.run(
                ["lp", "-d", printer_name, "-o", "raw", "-"],
                input=content.encode('latin-1', errors='replace'),
                capture_output=True,
                timeout=10
            )
            
            if result.returncode == 0:
                QtWidgets.QMessageBox.information(
                    self, "Impresión", 
                    "Estado de cuenta enviado a impresora."
                )
            else:
                error_msg = result.stderr.decode('utf-8', errors='ignore')
                QtWidgets.QMessageBox.critical(
                    self, "Error de Impresión", 
                    f"Error: {error_msg}"
                )
        except subprocess.TimeoutExpired:
            QtWidgets.QMessageBox.critical(
                self, "Timeout", 
                "La impresora no responde."
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error", 
                f"Error al imprimir: {e}"
            )

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
        except Exception:
            pass
