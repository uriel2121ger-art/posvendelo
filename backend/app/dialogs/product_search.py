from PyQt6 import QtCore, QtWidgets
from PyQt6.QtWidgets import QDialog, QHeaderView, QLabel, QPushButton, QVBoxLayout


class ProductSearchDialog(QDialog):
    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.setWindowTitle("Buscar Producto")
        self.setMinimumSize(900, 650)  # Más grande
        self.resize(1000, 700)
        self.selected_product = None
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # === SEARCH INPUT ===
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("🔍 Buscar por nombre, código o categoría...")
        self.search_input.setMinimumHeight(50)
        self.search_input.textChanged.connect(self.do_search)
        layout.addWidget(self.search_input)
        
        # === TABLE ===
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["CÓDIGO", "NOMBRE", "PRECIO", "STOCK"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self.select_and_accept)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        
        # Configurar columnas para aprovechar el espacio
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Código - auto
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Nombre - STRETCH para llenar
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Precio - auto
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Stock - auto
        
        # Altura de filas
        self.table.verticalHeader().setDefaultSectionSize(40)
        
        layout.addWidget(self.table, 1)  # stretch=1 para expandirse
        
        # === BUTTONS ===
        btn_box = QtWidgets.QHBoxLayout()
        btn_box.setSpacing(15)
        
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setMinimumHeight(45)
        btn_cancel.clicked.connect(self.reject)
        
        btn_select = QPushButton("Seleccionar")
        btn_select.setMinimumHeight(45)
        btn_select.clicked.connect(self.select_and_accept)
        
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_select)
        layout.addLayout(btn_box)
        
        self.setLayout(layout)
        self.search_input.setFocus()
        self.do_search()

    def do_search(self):
        query = self.search_input.text().strip()
        products = self.core.get_products_for_search(query, limit=100)
        
        self.table.setRowCount(0)
        self.table.setRowCount(len(products))
        
        for row, p in enumerate(products):
            # Código
            sku_item = QtWidgets.QTableWidgetItem(str(p.get("sku", "")))
            self.table.setItem(row, 0, sku_item)
            
            # Nombre - mostrar completo
            name = str(p.get("name", ""))
            name_item = QtWidgets.QTableWidgetItem(name)
            self.table.setItem(row, 1, name_item)
            
            # Precio
            price_item = QtWidgets.QTableWidgetItem(f"${float(p.get('price', 0)):,.2f}")
            price_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 2, price_item)
            
            # Stock
            stock = float(p.get("stock", 0))
            stock_item = QtWidgets.QTableWidgetItem(f"{stock:g}")
            stock_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, stock_item)
            
            # Store full product data in first item
            self.table.item(row, 0).setData(QtCore.Qt.ItemDataRole.UserRole, dict(p))

    def select_and_accept(self):
        row = self.table.currentRow()
        if row >= 0:
            self.selected_product = self.table.item(row, 0).data(QtCore.Qt.ItemDataRole.UserRole)
            self.accept()

    def showEvent(self, event):
        """Apply theme colors when dialog is shown."""
        super().showEvent(event)
        try:
            from app.utils.theme_manager import theme_manager
            c = theme_manager.get_colors()
            
            # Style buttons
            for btn in self.findChildren(QtWidgets.QPushButton):
                text = btn.text().lower()
                if any(w in text for w in ['seleccionar', 'guardar', 'save', 'aceptar', 'ok', 'crear', 'agregar']):
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #00C896, stop:1 #00a07a);
                            color: white;
                            font-weight: bold;
                            font-size: 14px;
                            padding: 12px 30px;
                            border-radius: 10px;
                            border: none;
                        }}
                        QPushButton:hover {{
                            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #00E0A8, stop:1 #00C896);
                        }}
                    """)
                elif any(w in text for w in ['cancelar', 'cancel', 'cerrar', 'eliminar', 'delete']):
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #FF4757, stop:1 #c92a38);
                            color: white;
                            font-weight: bold;
                            font-size: 14px;
                            padding: 12px 30px;
                            border-radius: 10px;
                            border: none;
                        }}
                        QPushButton:hover {{
                            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #FF6B7A, stop:1 #FF4757);
                        }}
                    """)
        except Exception:
            pass

