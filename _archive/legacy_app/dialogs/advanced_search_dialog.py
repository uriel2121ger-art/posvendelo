"""
Advanced product search dialog with filters.
Supports filtering by category, price range, stock status, and more.
"""
from __future__ import annotations

from typing import Any

from PyQt6 import QtCore, QtWidgets

from app.utils.theme_manager import theme_manager


class AdvancedSearchDialog(QtWidgets.QDialog):
    """Advanced product search with multiple filters.
    
    Features:
    - Category filter
    - Price range filter
    - Stock status filter
    - Active/Inactive products toggle
    - Supplier filter
    - Combined search with all criteria
    """
    
    def __init__(self, core, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.core = core
        self.selected_product = None
        
        self.setWindowTitle("Búsqueda Avanzada de Productos")
        self.setModal(True)
        self.setMinimumSize(900, 600)
        
        self._build_ui()
        self._load_filters()
        self.update_theme()
    
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        
        # Title
        title = QtWidgets.QLabel("🔍 Búsqueda Avanzada")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        # Filters Section
        filters_group = QtWidgets.QGroupBox("Filtros")
        filters_layout = QtWidgets.QGridLayout(filters_group)
        
        # Text search
        filters_layout.addWidget(QtWidgets.QLabel("Buscar:"), 0, 0)
        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Nombre, SKU, código de barras...")
        self.search_input.textChanged.connect(self._do_search)
        filters_layout.addWidget(self.search_input, 0, 1, 1, 3)
        
        # Category filter
        filters_layout.addWidget(QtWidgets.QLabel("Categoría:"), 1, 0)
        self.category_combo = QtWidgets.QComboBox()
        self.category_combo.addItem("Todas", None)
        self.category_combo.currentIndexChanged.connect(self._do_search)
        filters_layout.addWidget(self.category_combo, 1, 1)
        
        # Price range
        filters_layout.addWidget(QtWidgets.QLabel("Precio desde:"), 1, 2)
        self.price_min = QtWidgets.QDoubleSpinBox()
        self.price_min.setRange(0, 999999)
        self.price_min.setPrefix("$ ")
        self.price_min.valueChanged.connect(self._do_search)
        filters_layout.addWidget(self.price_min, 1, 3)
        
        filters_layout.addWidget(QtWidgets.QLabel("Precio hasta:"), 2, 2)
        self.price_max = QtWidgets.QDoubleSpinBox()
        self.price_max.setRange(0, 999999)
        self.price_max.setValue(999999)
        self.price_max.setPrefix("$ ")
        self.price_max.valueChanged.connect(self._do_search)
        filters_layout.addWidget(self.price_max, 2, 3)
        
        # Stock status
        filters_layout.addWidget(QtWidgets.QLabel("Stock:"), 2, 0)
        self.stock_combo = QtWidgets.QComboBox()
        self.stock_combo.addItem("Todos", "all")
        self.stock_combo.addItem("Con stock", "in_stock")
        self.stock_combo.addItem("Sin stock", "out_of_stock")
        self.stock_combo.addItem("Stock bajo", "low_stock")
        self.stock_combo.currentIndexChanged.connect(self._do_search)
        filters_layout.addWidget(self.stock_combo, 2, 1)
        
        # Active/Inactive
        self.active_check = QtWidgets.QCheckBox("Solo productos activos")
        self.active_check.setChecked(True)
        self.active_check.stateChanged.connect(self._do_search)
        filters_layout.addWidget(self.active_check, 3, 0, 1, 2)
        
        # Search button
        self.search_btn = QtWidgets.QPushButton("🔍 Buscar")
        self.search_btn.clicked.connect(self._do_search)
        filters_layout.addWidget(self.search_btn, 3, 2, 1, 2)
        
        layout.addWidget(filters_group)
        
        # Results table
        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["SKU", "Nombre", "Categoría", "Precio", "Stock", "Estado"])
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._select_product)
        layout.addWidget(self.table)
        
        # Results count
        self.results_label = QtWidgets.QLabel("0 productos encontrados")
        self.results_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.results_label)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        
        self.select_btn = QtWidgets.QPushButton("Seleccionar")
        self.select_btn.clicked.connect(self._select_product)
        self.select_btn.setEnabled(False)
        
        self.cancel_btn = QtWidgets.QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.select_btn)
        
        layout.addLayout(btn_layout)
        
        # Enable select button when row selected
        self.table.itemSelectionChanged.connect(
            lambda: self.select_btn.setEnabled(bool(self.table.selectedItems()))
        )
    
    def _load_filters(self) -> None:
        """Load filter options from database."""
        try:
            # Load categories
            categories = self.core.get_all_categories() if hasattr(self.core, 'get_all_categories') else []
            for cat in categories:
                self.category_combo.addItem(cat.get('name', ''), cat.get('id'))
        except Exception as e:
            print(f"Error loading filters: {e}")
    
    def _do_search(self) -> None:
        """Execute search with current filters."""
        try:
            # Build filter criteria
            filters = {
                'search': self.search_input.text().strip(),
                'category_id': self.category_combo.currentData(),
                'price_min': self.price_min.value(),
                'price_max': self.price_max.value(),
                'stock_status': self.stock_combo.currentData(),
                'active_only': self.active_check.isChecked()
            }
            
            # Get products from database
            products = self._get_filtered_products(filters)
            
            # Update table
            self.table.setRowCount(len(products))
            for row, product in enumerate(products):
                items = [
                    product.get('sku', ''),
                    product.get('name', ''),
                    product.get('category_name', ''),
                    f"${float(product.get('price', 0)):.2f}",
                    str(int(product.get('stock', 0))),
                    "Activo" if product.get('active', True) else "Inactivo"
                ]
                for col, text in enumerate(items):
                    item = QtWidgets.QTableWidgetItem(text)
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, product)
                    self.table.setItem(row, col, item)
            
            self.results_label.setText(f"{len(products)} productos encontrados")
            
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Error en búsqueda: {str(e)}")
    
    def _get_filtered_products(self, filters: dict) -> list[dict[str, Any]]:
        """Get products matching filters from database."""
        try:
            # Use core method if available
            if hasattr(self.core, 'search_products_advanced'):
                return self.core.search_products_advanced(filters)
            
            # Fallback to basic search
            all_products = self.core.get_all_products() if hasattr(self.core, 'get_all_products') else []
            
            # Apply filters manually
            results = []
            for p in all_products:
                # Text search
                if filters['search']:
                    search_lower = filters['search'].lower()
                    if not any([
                        search_lower in str(p.get('sku', '')).lower(),
                        search_lower in str(p.get('name', '')).lower(),
                        search_lower in str(p.get('barcode', '')).lower()
                    ]):
                        continue
                
                # Category filter
                if filters['category_id'] and p.get('category_id') != filters['category_id']:
                    continue
                
                # Price range
                price = float(p.get('price', 0))
                if price < filters['price_min'] or price > filters['price_max']:
                    continue
                
                # Stock status
                stock = int(p.get('stock', 0))
                stock_status = filters['stock_status']
                if stock_status == 'in_stock' and stock <= 0:
                    continue
                elif stock_status == 'out_of_stock' and stock > 0:
                    continue
                elif stock_status == 'low_stock':
                    min_stock = int(p.get('min_stock', 0))
                    if stock > min_stock:
                        continue
                
                # Active status
                if filters['active_only'] and not p.get('active', True):
                    continue
                
                results.append(p)
            
            return results
            
        except Exception as e:
            print(f"Error filtering products: {e}")
            return []
    
    def _select_product(self) -> None:
        """Select current product and close dialog."""
        selected = self.table.selectedItems()
        if selected:
            self.selected_product = selected[0].data(QtCore.Qt.ItemDataRole.UserRole)
            self.accept()
    
    def update_theme(self) -> None:
        """Apply theme colors."""
        theme = theme_manager.get_theme()
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.get('bg_primary', '#ffffff')};
                color: {theme.get('text_primary', '#2c3e50')};
            }}
            QGroupBox {{
                font-weight: bold;
                border: 2px solid {theme.get('border', '#bdc3c7')};
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            QPushButton {{
                background-color: {theme.get('btn_primary', '#3498db')};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme.get('btn_primary_hover', '#2980b9')};
            }}
            QPushButton:disabled {{
                background-color: {theme.get('btn_disabled', '#95a5a6')};
            }}
        """)
