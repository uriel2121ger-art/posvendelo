from __future__ import annotations

from typing import Any
import logging

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger(__name__)

from app.core import STATE, POSCore
from app.dialogs.import_wizard import ImportWizardDialog
from app.dialogs.product_delete import ProductDeleteDialog
from app.dialogs.product_editor import ProductEditorDialog
from app.dialogs.product_search import ProductSearchDialog
from app.utils.export_csv import export_inventory_to_csv, export_product_catalog_to_csv
from app.utils.path_utils import get_debug_log_path_str, get_debug_log_path, agent_log_enabled
from app.utils.export_excel import export_inventory_to_excel, export_product_catalog_to_excel
from app.utils.theme_manager import theme_manager

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

class ProductImportWorker(QtCore.QThread):
    progress_updated = QtCore.pyqtSignal(int, int)
    finished = QtCore.pyqtSignal(int, int)
    error_occurred = QtCore.pyqtSignal(str)

    def __init__(self, core, path, mapping, update_existing, header_row_idx):
        super().__init__()
        self.core = core
        self.path = path
        self.mapping = mapping
        self.update_existing = update_existing
        self.header_row_idx = header_row_idx

    def run(self):
        import csv
        try:
            rows = []
            if self.path.endswith('.csv'):
                with open(self.path, mode='r', encoding='utf-8-sig', errors='replace') as f:
                    reader = csv.reader(f)
                    rows = list(reader)
            elif self.path.endswith(('.xlsx', '.xls')):
                if not HAS_OPENPYXL:
                    raise ImportError("Se requiere openpyxl para importar Excel.")
                
                # Validar archivo antes de leer
                import zipfile
                import os
                
                if not os.path.exists(self.path):
                    raise FileNotFoundError(f"El archivo no existe: {self.path}")
                
                if os.path.getsize(self.path) == 0:
                    raise ValueError("El archivo está vacío")
                
                # Validar que .xlsx sea un ZIP válido
                if self.path.endswith('.xlsx'):
                    try:
                        with zipfile.ZipFile(self.path, 'r') as zip_ref:
                            zip_files = zip_ref.namelist()
                            if not any('xl/workbook.xml' in f or '[Content_Types].xml' in f for f in zip_files):
                                raise ValueError("El archivo no parece ser un Excel válido")
                    except zipfile.BadZipFile:
                        raise ValueError(
                            "El archivo Excel está corrupto o no es válido.\n"
                            "Abre el archivo en Excel y guárdalo nuevamente."
                        )
                
                try:
                    wb = openpyxl.load_workbook(self.path, read_only=True, data_only=True)
                    ws = wb.active
                    for row in ws.iter_rows(values_only=True):
                        rows.append([str(cell) if cell is not None else "" for cell in row])
                    wb.close()
                except zipfile.BadZipFile:
                    raise ValueError(
                        "El archivo Excel está corrupto.\n"
                        "Por favor, abre el archivo en Excel y guárdalo nuevamente."
                    )
                except Exception as e:
                    error_msg = str(e)
                    if "Bad magic number" in error_msg or "BadZipFile" in error_msg:
                        raise ValueError(
                            "El archivo Excel está corrupto.\n\n"
                            "Solución: Abre el archivo en Excel y guárdalo nuevamente."
                        )
                    raise
            
            if self.header_row_idx >= len(rows):
                raise ValueError("La fila de encabezados está fuera de rango.")

            total_rows = len(rows) - (self.header_row_idx + 1)
            imported_count = 0
            updated_count = 0
            
            for i in range(self.header_row_idx + 1, len(rows)):
                if self.isInterruptionRequested():
                    break
                    
                row = rows[i]
                if not row: continue
                
                def get_val(key):
                    col_idx = self.mapping.get(key)
                    if col_idx is not None and 0 <= col_idx < len(row):
                        return str(row[col_idx]).strip()
                    return ""
                
                sku = get_val("sku")
                if not sku: continue
                
                name = get_val("name")
                
                def parse_float(val):
                    if not val: return 0.0
                    clean = val.replace("$", "").replace(",", "")
                    try:
                        return float(clean)
                    except ValueError:
                        return 0.0
                
                product_data = {
                    "sku": sku,
                    "name": name,
                    "price": parse_float(get_val("price")),
                    "price_wholesale": parse_float(get_val("price_wholesale")),
                    "cost": parse_float(get_val("cost")),
                    "stock": parse_float(get_val("stock")),
                    "min_stock": parse_float(get_val("min_stock")),
                    "department": get_val("department"),
                    "provider": get_val("provider"),
                    "tax_rate": parse_float(get_val("tax_rate")),
                    "sale_type": get_val("sale_type") or "unit",
                    "barcode": get_val("barcode"),
                    # SAT Catalog fields for CFDI 4.0
                    "sat_clave_prod_serv": get_val("sat_clave_prod_serv") or "01010101",
                    "sat_clave_unidad": get_val("sat_clave_unidad") or "H87"
                }
                
                existing = self.core.get_product_by_sku_or_barcode(sku)
                if existing:
                    if self.update_existing:
                        self.core.update_product(existing["id"], product_data)
                        updated_count += 1
                else:
                    self.core.create_product(product_data)
                    imported_count += 1
                
                self.progress_updated.emit(i - self.header_row_idx, total_rows)
                
            self.finished.emit(imported_count, updated_count)
            
        except Exception as e:
            self.error_occurred.emit(str(e))

class ProductsTab(QtWidgets.QWidget):
    """Módulo de Productos reorganizado con pestañas"""
    
    def __init__(self, core: POSCore, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.core = core
        self.current_page = 0
        self.page_size = 100
        self.selected_product_id = None
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
                        "hypothesisId": "PRODUCTS_TAB_INIT",
                        "location": "app/ui/products_tab.py:__init__",
                        "message": "ProductsTab initialized",
                        "data": {},
                        "timestamp": int(__import__("time").time() * 1000)
                    }) + "\n")
            except Exception as e:
                logger.debug("Writing debug log for products tab init: %s", e)
        # #endregion
        QtCore.QTimer.singleShot(0, self.refresh_table)
    
    def showEvent(self, event):
        super().showEvent(event)
        # Aplicar tema cuando se muestra el tab
        if hasattr(self, 'update_theme'):
            self.update_theme()
        self.refresh_table()

    def load_assets(self):
        self.icons = {}
        try:
            self.icons["search"] = QtGui.QIcon("assets/icon_search.png")
            self.icons["add"] = QtGui.QIcon("assets/icon_add.png")
            self.icons["edit"] = QtGui.QIcon("assets/icon_edit.png")
            self.icons["delete"] = QtGui.QIcon("assets/icon_delete.png")
            self.icons["excel"] = QtGui.QIcon("assets/icon_excel.png")
            self.icons["import"] = QtGui.QIcon("assets/icon_import.png")
            self.icons["products"] = QtGui.QIcon("assets/icon_products.png")
        except Exception as e:
            # FIX 2026-02-01: Usar logger
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
        
        if "products" in self.icons:
            icon_lbl = QtWidgets.QLabel()
            icon_lbl.setPixmap(self.icons["products"].pixmap(32, 32))
            header_layout.addWidget(icon_lbl)
            
        self.title_label = QtWidgets.QLabel("📦 GESTIÓN DE PRODUCTOS")
        self.title_label.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['text_primary']};")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        
        main_layout.addWidget(self.header)

        # === TAB WIDGET ===
        self.tab_widget = QtWidgets.QTabWidget()
        
        # Tab 1: Catálogo
        self.tab_catalogo = self._create_catalogo_tab(c)
        self.tab_widget.addTab(self.tab_catalogo, "📦 Catálogo")
        
        # Tab 2: Categorías (Inventario movido al módulo dedicado)
        self.tab_categorias = self._create_categorias_tab(c)
        self.tab_widget.addTab(self.tab_categorias, "🏷️ Categorías")
        
        # Tab 3: Import/Export
        self.tab_import_export = self._create_import_export_tab(c)
        self.tab_widget.addTab(self.tab_import_export, "📥 Import/Export")
        
        # Tab 4: Análisis
        self.tab_analisis = self._create_analisis_tab(c)
        self.tab_widget.addTab(self.tab_analisis, "📈 Análisis")
        
        main_layout.addWidget(self.tab_widget)
        
        self.update_theme()
        
        # Shortcuts
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+N"), self, self._new_product)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_F3), self, self._edit_selected)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Delete), self, self._delete_selected)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+E"), self, self._export_catalog)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+I"), self, self._import_catalog)
        QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_F10), self, self._open_search_dialog)

    # =========================================================================
    # TAB CREATION METHODS
    # =========================================================================
    
    def _create_catalogo_tab(self, c: dict) -> QtWidgets.QWidget:
        """Pestaña principal de catálogo de productos"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Cards de resumen
        cards_layout = QtWidgets.QHBoxLayout()
        cards_layout.setSpacing(15)

        self.card_total = self._create_card("Total Productos", "0", "#4CAF50", c)
        self.card_value = self._create_card("Valor Inventario", "$0.00", "#2196F3", c)
        self.card_low = self._create_card("Bajo Stock", "0", "#FF9800", c)
        
        self.summary_cards = [
            (self.card_total, "#4CAF50"),
            (self.card_value, "#2196F3"),
            (self.card_low, "#FF9800")
        ]

        cards_layout.addWidget(self.card_total)
        cards_layout.addWidget(self.card_value)
        cards_layout.addWidget(self.card_low)
        
        layout.addLayout(cards_layout)

        # Barra de acciones
        actions_frame = QtWidgets.QFrame()
        actions_layout = QtWidgets.QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(15, 15, 15, 15)
        actions_layout.setSpacing(15)

        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("🔍 Buscar por código, nombre o categoría...")
        self.search_input.setFixedHeight(40)
        self.search_input.textChanged.connect(self.refresh_table)
        actions_layout.addWidget(self.search_input, 1)

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

        self.btn_new = make_btn("Nuevo", "add", 'btn_success', self._new_product)
        self.btn_edit = make_btn("Editar", "edit", 'btn_primary', self._edit_selected)
        self.btn_delete = make_btn("Eliminar", "delete", 'btn_danger', self._delete_selected)

        actions_layout.addWidget(self.btn_new)
        actions_layout.addWidget(self.btn_edit)
        actions_layout.addWidget(self.btn_delete)

        layout.addWidget(actions_frame)

        # Tabla
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "ID", "Código", "Descripción", "Tipo", 
            "Precio", "Mayoreo", "Depto", "Proveedor", 
            "Existencia", "Min", "Max"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)  # NO EDITABLE
        self.table.itemDoubleClicked.connect(lambda *_: self._edit_selected())
        
        layout.addWidget(self.table)
        
        # Paginación
        pagination_layout = QtWidgets.QHBoxLayout()
        
        self.page_label = QtWidgets.QLabel("Página 1")
        self.prev_btn = QtWidgets.QPushButton("◀ Anterior")
        self.prev_btn.clicked.connect(self._prev_page)
        self.next_btn = QtWidgets.QPushButton("Siguiente ▶")
        self.next_btn.clicked.connect(self._next_page)
        
        self.pagination_buttons = [self.prev_btn, self.next_btn]
        
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.prev_btn)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.next_btn)
        
        layout.addLayout(pagination_layout)

        return tab

    def _create_categorias_tab(self, c: dict) -> QtWidgets.QWidget:
        """Pestaña de gestión de categorías"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Header
        header_lbl = QtWidgets.QLabel("🏷️ Categorías y Departamentos")
        header_lbl.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['text_primary']};")
        layout.addWidget(header_lbl)
        
        # Botones
        btn_layout = QtWidgets.QHBoxLayout()
        
        btn_new_cat = QtWidgets.QPushButton("➕ Nueva Categoría")
        btn_new_cat.setFixedHeight(45)
        btn_new_cat.clicked.connect(self._new_category)
        
        btn_edit_cat = QtWidgets.QPushButton("✏️ Editar")
        btn_edit_cat.setFixedHeight(45)
        btn_edit_cat.clicked.connect(self._edit_category)
        
        btn_delete_cat = QtWidgets.QPushButton("🗑️ Eliminar")
        btn_delete_cat.setFixedHeight(45)
        btn_delete_cat.clicked.connect(self._delete_category)
        
        btn_layout.addWidget(btn_new_cat)
        btn_layout.addWidget(btn_edit_cat)
        btn_layout.addWidget(btn_delete_cat)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Tabla de categorías
        self.categories_table = QtWidgets.QTableWidget(0, 3)
        self.categories_table.setHorizontalHeaderLabels(["Categoría", "Productos", "Descripción"])
        self.categories_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.categories_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.categories_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.categories_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.categories_table.itemDoubleClicked.connect(lambda: self._edit_category())
        layout.addWidget(self.categories_table)
        
        self._refresh_categories()
        
        return tab

    def _create_import_export_tab(self, c: dict) -> QtWidgets.QWidget:
        """Pestaña de importación y exportación"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(30)
        
        # Header
        header_lbl = QtWidgets.QLabel("📥 Importar y Exportar Productos")
        header_lbl.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['text_primary']};")
        layout.addWidget(header_lbl)
        
        # Exportar
        export_group = QtWidgets.QGroupBox("📤 Exportar")
        export_group.setStyleSheet(f"""
            QGroupBox {{ font-weight: bold; border: 2px solid {c['border']}; border-radius: 8px; margin-top: 10px; padding: 20px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}
        """)
        export_layout = QtWidgets.QVBoxLayout(export_group)
        
        export_desc = QtWidgets.QLabel("Exporta el catálogo completo o solo inventario a Excel/CSV.")
        export_desc.setStyleSheet(f"color: {c['text_secondary']};")
        export_layout.addWidget(export_desc)
        
        export_btns = QtWidgets.QHBoxLayout()
        btn_export_catalog = QtWidgets.QPushButton("📊 Exportar Catálogo")
        btn_export_catalog.setFixedHeight(45)
        btn_export_catalog.clicked.connect(self._export_catalog)
        
        btn_export_inv = QtWidgets.QPushButton("📦 Exportar Inventario")
        btn_export_inv.setFixedHeight(45)
        btn_export_inv.clicked.connect(lambda: self._export_catalog(inventory_only=True))
        
        export_btns.addWidget(btn_export_catalog)
        export_btns.addWidget(btn_export_inv)
        export_btns.addStretch()
        export_layout.addLayout(export_btns)
        
        layout.addWidget(export_group)
        
        # Importar
        import_group = QtWidgets.QGroupBox("📥 Importar")
        import_group.setStyleSheet(f"""
            QGroupBox {{ font-weight: bold; border: 2px solid {c['border']}; border-radius: 8px; margin-top: 10px; padding: 20px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}
        """)
        import_layout = QtWidgets.QVBoxLayout(import_group)
        
        import_desc = QtWidgets.QLabel("Importa productos desde Excel o CSV usando el wizard interactivo.")
        import_desc.setStyleSheet(f"color: {c['text_secondary']};")
        import_layout.addWidget(import_desc)
        
        btn_import = QtWidgets.QPushButton("🚀 Iniciar Wizard de Importación")
        btn_import.setFixedHeight(45)
        btn_import.clicked.connect(self._import_catalog)
        import_layout.addWidget(btn_import)
        
        # Botón de reclasificación masiva
        btn_bulk_classify = QtWidgets.QPushButton("🎯 Reclasificación Masiva")
        btn_bulk_classify.setFixedHeight(45)
        btn_bulk_classify.setToolTip("Clasificar múltiples productos automáticamente por departamento y código SAT")
        btn_bulk_classify.clicked.connect(self._open_bulk_classify)
        import_layout.addWidget(btn_bulk_classify)
        
        layout.addWidget(import_group)
        layout.addStretch()
        
        return tab

    def _create_analisis_tab(self, c: dict) -> QtWidgets.QWidget:
        """Pestaña de análisis de productos"""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Header
        header_lbl = QtWidgets.QLabel("📈 Análisis de Productos")
        header_lbl.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['text_primary']};")
        layout.addWidget(header_lbl)
        
        # Stats cards
        stats_layout = QtWidgets.QHBoxLayout()
        stats_layout.setSpacing(15)
        
        self.stat_total_prods = self._create_stat_card("Total Productos", "0", "#4CAF50", c)
        self.stat_valor_inv = self._create_stat_card("Valor Inventario", "$0", "#2196F3", c)
        self.stat_bajo_stock = self._create_stat_card("Bajo Stock", "0", "#FF9800", c)
        self.stat_sin_stock = self._create_stat_card("Sin Stock", "0", "#F44336", c)
        
        stats_layout.addWidget(self.stat_total_prods)
        stats_layout.addWidget(self.stat_valor_inv)
        stats_layout.addWidget(self.stat_bajo_stock)
        stats_layout.addWidget(self.stat_sin_stock)
        layout.addLayout(stats_layout)
        
        # Refresh button
        btn_refresh = QtWidgets.QPushButton("🔄 Actualizar Estadísticas")
        btn_refresh.setFixedHeight(40)
        btn_refresh.clicked.connect(self._refresh_product_stats)
        layout.addWidget(btn_refresh)
        
        # Top products table
        top_lbl = QtWidgets.QLabel("🏆 Top 10 Productos Más Vendidos")
        top_lbl.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {c['text_primary']};")
        layout.addWidget(top_lbl)
        
        self.top_products_table = QtWidgets.QTableWidget(0, 4)
        self.top_products_table.setHorizontalHeaderLabels(["Producto", "Unidades Vendidas", "Ingresos", "Stock"])
        self.top_products_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.top_products_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.top_products_table)
        
        self._refresh_product_stats()
        
        return tab

    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _create_card(self, title: str, value: str, color: str, c: dict) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {c['bg_secondary']};
                border: 1px solid {c['border']};
                border-radius: 10px;
                border-left: 5px solid {color};
            }}
        """)
        
        layout = QtWidgets.QVBoxLayout(card)
        layout.setSpacing(5)
        
        title_label = QtWidgets.QLabel(title)
        title_label.setStyleSheet(f"color: {c['text_secondary']}; font-size: 13px; font-weight: 600; border: none;")
        
        value_label = QtWidgets.QLabel(value)
        value_label.setObjectName("value_label")
        value_label.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold; border: none;")
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        
        return card

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

    def _update_cards(self, total: int, products: list[dict]) -> None:
        def set_card_value(card, text):
            lbl = card.findChild(QtWidgets.QLabel, "value_label")
            if lbl:
                lbl.setText(text)

        set_card_value(self.card_total, str(total))
        
        val = sum(float(p.get("price", 0) or 0) * float(p.get("stock", 0) or 0) for p in products)
        if STATE.role == "admin":
            set_card_value(self.card_value, f"${val:,.2f}")
        else:
            set_card_value(self.card_value, "$***")
        
        low = sum(1 for p in products if float(p.get("stock", 0) or 0) <= float(p.get("min_stock", 0) or 0))
        set_card_value(self.card_low, str(low))

    # =========================================================================
    # ACTION METHODS
    # =========================================================================
    
    def _selected_product_id_from_table(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.text()) if item else None

    def _open_search_dialog(self) -> None:
        dialog = ProductSearchDialog(core=self.core, parent=self)
        dialog.search_input.setText(self.search_input.text())
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted and dialog.selected_product:
            product = dialog.selected_product
            self._open_editor(product.get("id"))
        self.refresh_table()

    def _new_product(self) -> None:
        self._open_editor(None)

    def _edit_selected(self) -> None:
        product_id = self._selected_product_id_from_table()
        if not product_id:
            QtWidgets.QMessageBox.warning(self, "Productos", "Selecciona un producto")
            return
        self._open_editor(product_id)

    def _delete_selected(self) -> None:
        product_id = self._selected_product_id_from_table()
        if not product_id:
            QtWidgets.QMessageBox.warning(self, "Productos", "Selecciona un producto")
            return
        dialog = ProductDeleteDialog(core=self.core, product_id=product_id, parent=self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            try:
                old_data = self.core.get_product_by_id(product_id)
            except Exception:
                old_data = {}
            
            result = self.core.engine.delete_product(product_id)
            
            try:
                product_name = old_data.get('name', '') if old_data else ''
                sku = old_data.get('sku', '') if old_data else ''
                self.core.audit.log_delete('product', product_id, sku or product_name, old_data)
            except Exception:
                pass
            
            if result:
                QtWidgets.QMessageBox.information(self, "Éxito", "Producto eliminado")
            else:
                QtWidgets.QMessageBox.warning(self, "Error", "No se pudo eliminar el producto.")
                return
            self.refresh_table()

    def _open_editor(self, product_id: int | None) -> None:
        product_data = None
        if product_id:
            row = self.core.get_product_by_id(product_id)
            if row:
                product_data = dict(row)
            else:
                QtWidgets.QMessageBox.warning(self, "Error", "No se pudo cargar el producto.")
                return

        dialog = ProductEditorDialog(core=self.core, product=product_data, parent=self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            QtWidgets.QMessageBox.information(self, "Productos", "Producto guardado correctamente")
            self.refresh_table()

    def _export_catalog(self, inventory_only: bool = False) -> None:
        products = self.core.list_products_for_export()
        if inventory_only:
            products = [p for p in products if p.get("uses_inventory", True)]
        path, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self, "Exportar productos", "productos", "Excel (*.xlsx);;CSV (*.csv)"
        )
        if not path:
            return
        if selected_filter.startswith("Excel") and not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        elif selected_filter.startswith("CSV") and not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            if selected_filter.startswith("Excel") or path.lower().endswith(".xlsx"):
                if inventory_only:
                    export_inventory_to_excel(products, path)
                else:
                    export_product_catalog_to_excel(products, path)
            else:
                if inventory_only:
                    export_inventory_to_csv(products, path)
                else:
                    export_product_catalog_to_csv(products, path)
            QtWidgets.QMessageBox.information(self, "Exportar", "Exportación completada")
        except Exception as exc:
            logging.exception("export products failed")
            QtWidgets.QMessageBox.critical(self, "Exportar", f"No se pudo exportar: {exc}")

    def _import_catalog(self) -> None:
        dialog = ImportWizardDialog(self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # get_data() retorna 4 valores: path, mapping, update_existing, header_row_idx
            path, mapping, update_existing, header_row_idx = dialog.get_data()
            self._process_import(path, mapping, update_existing, header_row_idx)
    
    def _open_bulk_classify(self) -> None:
        """Abre el diálogo de reclasificación masiva."""
        from app.dialogs.bulk_classify_dialog import BulkClassifyDialog
        dialog = BulkClassifyDialog(core=self.core, parent=self)
        dialog.exec()
        # Refrescar tabla después de clasificar
        self.refresh_table()

    def _process_import(self, path: str, mapping: dict, update_existing: bool, header_row_idx: int) -> None:
        self.progress_dialog = QtWidgets.QProgressDialog("Importando productos...", "Cancelar", 0, 100, self)
        self.progress_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        
        self.worker = ProductImportWorker(
            self.core, path, mapping, update_existing, header_row_idx
        )
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.finished.connect(self.import_finished)
        self.worker.error_occurred.connect(self.import_error)
        self.progress_dialog.canceled.connect(self.worker.requestInterruption)
        self.worker.start()
        
    def update_progress(self, current, total):
        self.progress_dialog.setMaximum(total)
        self.progress_dialog.setValue(current)
        
    def import_finished(self, imported, updated):
        self.progress_dialog.close()
        QtWidgets.QMessageBox.information(
            self, 
            "Importación Exitosa", 
            f"Se importaron {imported} productos nuevos.\nSe actualizaron {updated} productos existentes."
        )
        self.refresh_table()
        
    def import_error(self, error_msg):
        self.progress_dialog.close()
        QtWidgets.QMessageBox.critical(self, "Error de Importación", f"Ocurrió un error: {error_msg}")

    # =========================================================================
    # INVENTORY TAB METHODS
    # =========================================================================
    
    def _open_inventory_adjustment(self) -> None:
        QtWidgets.QMessageBox.information(self, "Ajuste", "Función de ajuste de inventario")

    def _show_movements(self) -> None:
        QtWidgets.QMessageBox.information(self, "Movimientos", "Función de movimientos de inventario")

    def _show_low_stock(self) -> None:
        QtWidgets.QMessageBox.information(self, "Bajo Stock", "Función de productos bajo stock")

    # =========================================================================
    # CATEGORIES TAB METHODS
    # =========================================================================
    
    def _refresh_categories(self) -> None:
        try:
            if not self.core.db:
                logger.warning("Database not available")
                return
            # FIX 2026-02-04: Optimized - single query with GROUP BY instead of N+1 queries
            cats = self.core.db.execute_query("""
                SELECT department, COUNT(*) as cnt
                FROM products
                WHERE department IS NOT NULL AND department != ''
                GROUP BY department
                ORDER BY department
            """)
            self.categories_table.setRowCount(len(cats))
            for i, cat in enumerate(cats):
                cat_dict = dict(cat)
                dept = cat_dict.get("department", "")
                count = cat_dict.get("cnt", 0)
                self.categories_table.setItem(i, 0, QtWidgets.QTableWidgetItem(dept))
                self.categories_table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(count)))
                self.categories_table.setItem(i, 2, QtWidgets.QTableWidgetItem(""))
        except Exception as e:
            # FIX 2026-02-01: Usar logger
            logger.debug("Error refreshing categories: %s", e)

    def _new_category(self) -> None:
        if not self.core.db:
            logger.warning("Database not available")
            QtWidgets.QMessageBox.warning(self, "Error", "Base de datos no disponible")
            return
        text, ok = QtWidgets.QInputDialog.getText(self, "Nueva Categoría", "Nombre de la categoría:")
        if ok and text.strip():
            category_name = text.strip()
            # Check if category already exists
            existing = self.core.db.execute_query(
                "SELECT COUNT(*) as cnt FROM products WHERE department = %s", 
                [category_name]
            )
            if existing and len(existing) > 0 and existing[0] and existing[0].get("cnt", 0) > 0:
                QtWidgets.QMessageBox.warning(
                    self, "Categoría Existente", 
                    f"La categoría '{category_name}' ya existe."
                )
                return
            
            # Create category by adding a placeholder product or just notify success
            # Categories are derived from products, so we just inform the user
            QtWidgets.QMessageBox.information(
                self, "Nueva Categoría", 
                f"Categoría '{category_name}' registrada.\n\n"
                f"Asigna esta categoría a productos para que aparezca en la lista."
            )
            self._refresh_categories()

    def _edit_category(self) -> None:
        if not self.core.db:
            logger.warning("Database not available")
            QtWidgets.QMessageBox.warning(self, "Error", "Base de datos no disponible")
            return
        # Get selected category from table
        row = self.categories_table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.warning(
                self, "Editar Categoría",
                "Selecciona una categoría de la tabla para editar."
            )
            return

        item = self.categories_table.item(row, 0)
        if not item:
            return

        old_name = item.text()
        
        new_name, ok = QtWidgets.QInputDialog.getText(
            self, "Editar Categoría", 
            f"Nuevo nombre para '{old_name}':",
            text=old_name
        )
        
        if ok and new_name.strip() and new_name.strip() != old_name:
            new_name = new_name.strip()
            
            # Confirm the change
            confirm = QtWidgets.QMessageBox.question(
                self, "Confirmar Cambio",
                f"¿Renombrar '{old_name}' a '{new_name}'?\n\n"
                f"Todos los productos con esta categoría serán actualizados.",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            
            if confirm == QtWidgets.QMessageBox.StandardButton.Yes:
                try:
                    self.core.db.execute_write(
                        "UPDATE products SET department = %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE department = %s",
                        (new_name, old_name)
                    )
                    QtWidgets.QMessageBox.information(
                        self, "Éxito", 
                        f"Categoría renombrada de '{old_name}' a '{new_name}'."
                    )
                    self._refresh_categories()
                except Exception as e:
                    QtWidgets.QMessageBox.critical(
                        self, "Error", 
                        f"No se pudo renombrar la categoría: {e}"
                    )

    def _delete_category(self) -> None:
        if not self.core.db:
            logger.warning("Database not available")
            QtWidgets.QMessageBox.warning(self, "Error", "Base de datos no disponible")
            return
        # Get selected category from table
        row = self.categories_table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.warning(
                self, "Eliminar Categoría",
                "Selecciona una categoría de la tabla para eliminar."
            )
            return

        item = self.categories_table.item(row, 0)
        if not item:
            return

        category_name = item.text()

        # Get count of products in this category
        count_result = self.core.db.execute_query(
            "SELECT COUNT(*) as cnt FROM products WHERE department = %s",
            [category_name]
        )
        product_count = count_result[0]["cnt"] if count_result else 0
        
        # Confirm deletion
        confirm = QtWidgets.QMessageBox.question(
            self, "Confirmar Eliminación",
            f"¿Eliminar la categoría '{category_name}'?\n\n"
            f"Esta categoría tiene {product_count} producto(s).\n"
            f"Los productos NO serán eliminados, solo se les quitará la categoría.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if confirm == QtWidgets.QMessageBox.StandardButton.Yes:
            try:
                # Remove category from products (set to empty)
                self.core.db.execute_write(
                    "UPDATE products SET department = '', synced = 0, updated_at = CURRENT_TIMESTAMP WHERE department = %s",
                    (category_name,)
                )
                QtWidgets.QMessageBox.information(
                    self, "Éxito", 
                    f"Categoría '{category_name}' eliminada.\n"
                    f"{product_count} producto(s) ahora sin categoría."
                )
                self._refresh_categories()
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Error", 
                    f"No se pudo eliminar la categoría: {e}"
                )

    # =========================================================================
    # ANALYSIS TAB METHODS
    # =========================================================================
    
    def _refresh_product_stats(self) -> None:
        try:
            if not self.core.db:
                logger.warning("Database not available")
                return
            # Total productos
            result = self.core.db.execute_query("SELECT COUNT(*) as cnt FROM products")
            total = result[0]["cnt"] if result else 0
            self.stat_total_prods.findChild(QtWidgets.QLabel, "value").setText(str(total))
            
            # Valor inventario
            val_result = self.core.db.execute_query("SELECT COALESCE(SUM(price * stock), 0) as val FROM products")
            val = float(val_result[0]["val"] or 0) if val_result else 0
            self.stat_valor_inv.findChild(QtWidgets.QLabel, "value").setText(f"${val:,.0f}")
            
            # Bajo stock
            result = self.core.db.execute_query("SELECT COUNT(*) as cnt FROM products WHERE stock <= min_stock AND min_stock > 0")
            bajo = result[0]["cnt"] if result else 0
            self.stat_bajo_stock.findChild(QtWidgets.QLabel, "value").setText(str(bajo))
            
            # Sin stock
            result = self.core.db.execute_query("SELECT COUNT(*) as cnt FROM products WHERE stock <= 0")
            sin = result[0]["cnt"] if result else 0
            self.stat_sin_stock.findChild(QtWidgets.QLabel, "value").setText(str(sin))
            
            # Top productos (basado en sale_items)
            top = self.core.db.execute_query("""
                SELECT p.name, COALESCE(SUM(si.qty), 0) as units, COALESCE(SUM(si.subtotal), 0) as revenue, p.stock
                FROM sale_items si
                JOIN products p ON si.product_id = p.id
                GROUP BY si.product_id, p.name, p.stock
                ORDER BY units DESC
                LIMIT 10
            """)
            
            self.top_products_table.setRowCount(len(top))
            for i, row in enumerate(top):
                r = dict(row)
                values = [
                    r.get("name", ""),
                    str(int(r.get("units", 0))),
                    f"${float(r.get('revenue', 0)):.2f}",
                    str(int(r.get("stock", 0)))
                ]
                for j, val in enumerate(values):
                    item = QtWidgets.QTableWidgetItem(str(val))
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    self.top_products_table.setItem(i, j, item)
                    
        except Exception as e:
            # FIX 2026-02-01: Usar logger
            logger.debug("Error refreshing product stats: %s", e)

    # =========================================================================
    # TABLE REFRESH
    # =========================================================================
    
    def refresh_table(self) -> None:
        try:
            query = self.search_input.text().strip()
            total_count = self.core.get_products_count(query)
            max_pages = max(1, (total_count + self.page_size - 1) // self.page_size)
            
            if self.current_page >= max_pages: self.current_page = max_pages - 1
            if self.current_page < 0: self.current_page = 0
                
            offset = self.current_page * self.page_size
            products = self.core.get_products_for_search(query, limit=self.page_size, offset=offset)
            
            self.table.setUpdatesEnabled(False)
            self.table.setRowCount(0)
            self.table.setRowCount(len(products))
            
            self.page_label.setText(f"Página {self.current_page + 1} de {max_pages} | Total: {total_count}")
            if hasattr(self, 'prev_btn'): self.prev_btn.setEnabled(self.current_page > 0)
            if hasattr(self, 'next_btn'): self.next_btn.setEnabled(self.current_page < max_pages - 1)

            self._update_cards(total_count, products)

            for row_idx, row in enumerate(products):
                st = (row.get("sale_type") or "unit").lower()
                sale_type_map = {"unit": "Unidad", "weight": "Granel", "kit": "Kit"}
                display_type = sale_type_map.get(st, st.capitalize())

                stock = float(row.get('stock', 0.0) or 0.0)
                min_stock = float(row.get('min_stock', 0.0) or 0.0)
                max_stock = float(row.get('max_stock', 0.0) or 0.0)
                
                self.table.setItem(row_idx, 0, QtWidgets.QTableWidgetItem(str(row['id'])))
                self.table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(str(row.get('sku', ''))))
                self.table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(str(row.get('name', ''))))
                self.table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(display_type))
                self.table.setItem(row_idx, 4, QtWidgets.QTableWidgetItem(f"${float(row.get('price', 0.0)):.2f}"))
                self.table.setItem(row_idx, 5, QtWidgets.QTableWidgetItem(f"${float(row.get('price_wholesale', 0.0)):.2f}"))
                self.table.setItem(row_idx, 6, QtWidgets.QTableWidgetItem(str(row.get('department', '') or row.get('category', ''))))
                self.table.setItem(row_idx, 7, QtWidgets.QTableWidgetItem(str(row.get('provider', ''))))
                self.table.setItem(row_idx, 8, QtWidgets.QTableWidgetItem(f"{stock:.2f}"))
                self.table.setItem(row_idx, 9, QtWidgets.QTableWidgetItem(f"{min_stock:.2f}"))
                self.table.setItem(row_idx, 10, QtWidgets.QTableWidgetItem(f"{max_stock:.2f}"))

                # Colorize stock column
                for col in range(11):
                    item = self.table.item(row_idx, col)
                    if not item: continue
                    item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    
                    if col == 8:
                        item.setFont(QtGui.QFont("Arial", weight=QtGui.QFont.Weight.Bold))
                        cfg = self.core.get_app_config() or {}
                        theme = cfg.get("theme", "Light")
                        c_temp = theme_manager.get_colors(theme)
                        if stock <= min_stock:
                            item.setForeground(QtGui.QColor(c_temp['danger']))
                        else:
                            item.setForeground(QtGui.QColor(c_temp['success']))
            
            self.table.setUpdatesEnabled(True)
            self.table.update()
        except RuntimeError:
            pass

    def _prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.refresh_table()

    def _next_page(self):
        self.current_page += 1
        self.refresh_table()

    # =========================================================================
    # THEME
    # =========================================================================
    
    def update_theme(self) -> None:
        theme = (self.core.get_app_config() or {}).get("theme", "Light")
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
            self.title_label.setStyleSheet(f"color: {c['text_primary']}; font-size: 20px; font-weight: bold; background: transparent;")
        
        # Tab widget
        if hasattr(self, "tab_widget"):
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

        # Summary Cards
        if hasattr(self, "summary_cards"):
            for card, color in self.summary_cards:
                card.setStyleSheet(f"""
                    QFrame {{
                        background-color: {c['bg_secondary']};
                        border: 1px solid {c['border']};
                        border-left: 5px solid {color};
                        border-radius: 8px;
                    }}
                """)
                for child in card.findChildren(QtWidgets.QLabel):
                    child.setStyleSheet(f"color: {c['text_primary']}; border: none; background: transparent;")

        # Action Buttons
        if hasattr(self, "action_buttons_data"):
            for btn, color_key in self.action_buttons_data:
                color = c.get(color_key, color_key)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {color}; color: white; border: none; border-radius: 6px;
                        padding: 10px 15px; font-weight: bold; font-size: 13px;
                    }}
                    QPushButton:hover {{ background-color: {c['bg_secondary']}; }}
                """)

        # Table
        if hasattr(self, "table"):
            self.table.setStyleSheet(f"""
                QTableWidget {{
                    background-color: {c['bg_main']}; border: 1px solid {c['border']}; border-radius: 8px;
                    gridline-color: {c['border']}; font-size: 13px;
                }}
                QHeaderView::section {{
                    background-color: {c['table_header_bg']}; color: {c['table_header_text']};
                    padding: 10px; border: none; font-weight: bold;
                }}
                QTableWidget::item {{ padding: 8px; border-bottom: 1px solid {c['border']}; }}
                QTableWidget::item:selected {{ background-color: {c['table_selected']}; color: {c['text_primary']}; }}
            """)
            
        # Search input
        if hasattr(self, "search_input"):
            self.search_input.setStyleSheet(f"""
                QLineEdit {{
                    background: {c['input_bg']};
                    border: 1px solid {c['border']};
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 14px;
                    color: {c['text_primary']};
                }}
                QLineEdit:focus {{
                    border: 2px solid {c['accent']};
                }}
            """)
            
        # Pagination
        if hasattr(self, "page_label"):
            self.page_label.setStyleSheet(f"color: {c['text_secondary']}; font-weight: bold;")
            
        for btn in getattr(self, "pagination_buttons", []):
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {c['bg_secondary']}; border: 1px solid {c['border']}; border-radius: 4px;
                    padding: 5px 10px; color: {c['text_primary']};
                }}
                QPushButton:hover {{ background: {c['bg_main']}; }}
            """)

    def closeEvent(self, event):
        """Cleanup timers and threads on close."""
        for attr in ['timer', 'refresh_timer', 'auto_save_timer', 'worker']:
            obj = getattr(self, attr, None)
            if obj:
                if hasattr(obj, 'stop'):
                    obj.stop()
                elif hasattr(obj, 'quit'):
                    obj.quit()
                    obj.wait(3000)
        super().closeEvent(event)
