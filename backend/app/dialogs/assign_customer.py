from PyQt6 import QtCore, QtWidgets
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout


class AssignCustomerDialog(QDialog):
    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.setWindowTitle("Asignar Cliente")
        self.resize(600, 400)
        self.selected_customer_id = None
        self.selected_customer_name = None
        
        layout = QVBoxLayout()
        
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Buscar cliente por nombre, RFC o teléfono...")
        self.search_input.textChanged.connect(self.do_search)
        layout.addWidget(self.search_input)
        
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Nombre", "RFC", "Teléfono"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self.select_and_accept)
        layout.addWidget(self.table)
        
        btn_box = QtWidgets.QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_select = QPushButton("Seleccionar")
        btn_select.clicked.connect(self.select_and_accept)
        
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_select)
        layout.addLayout(btn_box)
        
        self.setLayout(layout)
        self.search_input.setFocus()
        self.do_search()

    def do_search(self):
        query = self.search_input.text().strip()
        customers = self.core.search_customers(query)
        
        self.table.setRowCount(0)
        self.table.setRowCount(len(customers))
        
        for row, customer_row in enumerate(customers):
            c = dict(customer_row)  # FIX: Convert Row to dict
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(c.get("id"))))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(c.get("name"))))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(str(c.get("rfc", ""))))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(str(c.get("phone", ""))))
            
            # Store full customer data in first item
            self.table.item(row, 0).setData(QtCore.Qt.ItemDataRole.UserRole, dict(c))

    def select_and_accept(self):
        row = self.table.currentRow()
        if row >= 0:
            data = self.table.item(row, 0).data(QtCore.Qt.ItemDataRole.UserRole)
            self.selected_customer_id = data.get("id")
            self.selected_customer_name = data.get("name")
            self.accept()

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
