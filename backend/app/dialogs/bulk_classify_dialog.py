"""
Herramienta de Reclasificación Masiva de Productos

Permite clasificar múltiples productos a la vez con:
- Filtros avanzados
- Vista previa de cambios
- Procesamiento en background
- Exportación de productos sin clasificar
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging
from datetime import datetime

from PyQt6 import QtCore, QtGui, QtWidgets

from app.services.product_classifier import ProductClassifier, ClassificationResult
from app.utils.theme_manager import theme_manager
from app.utils.sql_validators import validate_product_column, PRODUCT_UPDATE_COLUMNS

logger = logging.getLogger(__name__)


class BulkClassifyWorker(QtCore.QThread):
    """Worker thread para procesar clasificación en background."""
    
    progress_updated = QtCore.pyqtSignal(int, int)  # current, total
    product_classified = QtCore.pyqtSignal(dict)  # product data with classification
    finished = QtCore.pyqtSignal(dict)  # results: {classified, unclassified, errors}
    
    def __init__(self, core, products: List[Dict[str, Any]], 
                 force_reclassify: bool = False,
                 min_confidence: float = 0.0):
        super().__init__()
        self.core = core
        self.products = products
        self.force_reclassify = force_reclassify
        self.min_confidence = min_confidence
        self.classifier = ProductClassifier()
        self._should_stop = False
    
    def request_stop(self):
        """Solicita detener el procesamiento."""
        self._should_stop = True
    
    def run(self):
        """Procesa productos en background."""
        total = len(self.products)
        classified = 0
        unclassified = 0
        errors = 0
        
        results = {
            "classified": [],
            "unclassified": [],
            "errors": []
        }
        
        for idx, product in enumerate(self.products):
            if self._should_stop:
                break
            
            try:
                product_id = product.get("id")
                product_name = product.get("name", "")
                current_dept = product.get("department", "")
                current_sat_code = product.get("sat_clave_prod_serv", "")
                
                # Determinar si necesita clasificación
                needs_dept = not current_dept or current_dept.strip() == ""
                needs_sat = not current_sat_code or current_sat_code.strip() == ""
                needs_classification = needs_dept or needs_sat
                
                if not needs_classification and not self.force_reclassify:
                    # Ya tiene clasificación, saltar
                    continue
                
                # Clasificar
                result: ClassificationResult = self.classifier.classify(
                    product_name,
                    existing_department=current_dept if not self.force_reclassify else None
                )
                
                # Verificar confianza mínima
                if result.confidence < self.min_confidence:
                    results["unclassified"].append({
                        "id": product_id,
                        "name": product_name,
                        "reason": f"Confianza baja ({result.confidence:.2f})"
                    })
                    unclassified += 1
                    continue
                
                # Preparar actualización
                updates = {}
                if needs_dept or self.force_reclassify:
                    updates["department"] = result.department
                if needs_sat or self.force_reclassify:
                    updates["sat_clave_prod_serv"] = result.sat_clave_prod_serv
                    updates["sat_clave_unidad"] = result.sat_clave_unidad
                
                # Aplicar actualización
                if updates:
                    # SECURITY: Validate all column names against whitelist
                    for col in updates.keys():
                        validate_product_column(col)

                    set_clause = ", ".join([f"{k} = %s" for k in updates.keys()])
                    values = list(updates.values())
                    values.append(product_id)

                    self.core.db.execute_write(
                        f"UPDATE products SET {set_clause}, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                        tuple(values)
                    )
                    
                    results["classified"].append({
                        "id": product_id,
                        "name": product_name,
                        "department": result.department,
                        "sat_code": result.sat_clave_prod_serv,
                        "confidence": result.confidence
                    })
                    classified += 1
                    
                    # Emitir señal para actualizar UI
                    self.product_classified.emit({
                        "id": product_id,
                        "name": product_name,
                        "classification": result
                    })
                
            except Exception as e:
                logger.error(f"Error clasificando producto {product.get('id')}: {e}")
                results["errors"].append({
                    "id": product.get("id"),
                    "name": product.get("name", ""),
                    "error": str(e)
                })
                errors += 1
            
            # Actualizar progreso
            self.progress_updated.emit(idx + 1, total)
        
        # Emitir resultados finales
        results["summary"] = {
            "total": total,
            "classified": classified,
            "unclassified": unclassified,
            "errors": errors
        }
        self.finished.emit(results)


class BulkClassifyDialog(QtWidgets.QDialog):
    """Diálogo para reclasificación masiva de productos."""
    
    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.products = []
        self.filtered_products = []
        self.worker = None
        
        self.setWindowTitle("Reclasificación Masiva de Productos")
        self.setMinimumSize(900, 600)
        self.resize(1000, 700)
        
        self._build_ui()
        self._load_products()
        self.update_theme()
    
    def _build_ui(self):
        """Construye la interfaz de usuario."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # ─────────────────────────────────────────────────────────────
        # Filtros
        # ─────────────────────────────────────────────────────────────
        filter_group = QtWidgets.QGroupBox("Filtros")
        filter_layout = QtWidgets.QHBoxLayout(filter_group)
        
        # Filtro de tipo
        filter_layout.addWidget(QtWidgets.QLabel("Mostrar:"))
        self.filter_combo = QtWidgets.QComboBox()
        self.filter_combo.addItems([
            "Todos los productos",
            "Sin departamento",
            "Sin código SAT",
            "Sin departamento ni código SAT",
            "Por departamento..."
        ])
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.filter_combo)
        
        # Filtro de departamento (solo visible si "Por departamento..." está seleccionado)
        self.dept_filter_combo = QtWidgets.QComboBox()
        self.dept_filter_combo.setVisible(False)
        self.dept_filter_combo.currentTextChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.dept_filter_combo)
        
        filter_layout.addStretch()
        
        # Botón refrescar
        btn_refresh = QtWidgets.QPushButton("🔄 Refrescar")
        btn_refresh.clicked.connect(self._load_products)
        filter_layout.addWidget(btn_refresh)
        
        layout.addWidget(filter_group)
        
        # ─────────────────────────────────────────────────────────────
        # Tabla de productos
        # ─────────────────────────────────────────────────────────────
        table_group = QtWidgets.QGroupBox("Productos a Clasificar")
        table_layout = QtWidgets.QVBoxLayout(table_group)
        
        # Tabla
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "✓", "SKU", "Nombre", "Dept. Actual", "Dept. Sugerido", 
            "Confianza", "Código SAT Sugerido"
        ])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        
        # Checkbox en primera columna
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        
        table_layout.addWidget(self.table)
        
        # Info label
        self.info_label = QtWidgets.QLabel("Cargando productos...")
        self.info_label.setStyleSheet("color: #666; font-size: 11px;")
        table_layout.addWidget(self.info_label)
        
        layout.addWidget(table_group)
        
        # ─────────────────────────────────────────────────────────────
        # Opciones de clasificación
        # ─────────────────────────────────────────────────────────────
        options_group = QtWidgets.QGroupBox("Opciones")
        options_layout = QtWidgets.QHBoxLayout(options_group)
        
        self.force_check = QtWidgets.QCheckBox("Forzar reclasificación (sobrescribir datos existentes)")
        self.force_check.setToolTip("Si está activado, sobrescribirá departamento y código SAT incluso si ya existen")
        options_layout.addWidget(self.force_check)
        
        options_layout.addWidget(QtWidgets.QLabel("Confianza mínima:"))
        self.confidence_spin = QtWidgets.QDoubleSpinBox()
        self.confidence_spin.setRange(0.0, 1.0)
        self.confidence_spin.setSingleStep(0.1)
        self.confidence_spin.setValue(0.0)
        self.confidence_spin.setDecimals(2)
        self.confidence_spin.setToolTip("Solo clasificará productos con confianza >= este valor")
        options_layout.addWidget(self.confidence_spin)
        
        options_layout.addStretch()
        
        layout.addWidget(options_group)
        
        # ─────────────────────────────────────────────────────────────
        # Botones de acción
        # ─────────────────────────────────────────────────────────────
        btn_layout = QtWidgets.QHBoxLayout()
        
        btn_export = QtWidgets.QPushButton("📥 Exportar Sin Clasificar")
        btn_export.setToolTip("Exporta productos sin clasificar a Excel para revisión manual")
        btn_export.clicked.connect(self._export_unclassified)
        btn_layout.addWidget(btn_export)
        
        btn_layout.addStretch()
        
        btn_classify_selected = QtWidgets.QPushButton("✓ Clasificar Seleccionados")
        btn_classify_selected.clicked.connect(self._classify_selected)
        btn_layout.addWidget(btn_classify_selected)
        
        btn_classify_all = QtWidgets.QPushButton("✓✓ Clasificar Todos")
        btn_classify_all.setDefault(True)
        btn_classify_all.clicked.connect(self._classify_all)
        btn_layout.addWidget(btn_classify_all)
        
        btn_cancel = QtWidgets.QPushButton("Cerrar")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        
        # ─────────────────────────────────────────────────────────────
        # Progress dialog (se crea cuando se necesita)
        # ─────────────────────────────────────────────────────────────
        self.progress_dialog = None
    
    def _load_products(self):
        """Carga productos desde la base de datos."""
        try:
            query = """
                SELECT id, sku, name, department, sat_clave_prod_serv, sat_clave_unidad
                FROM products
                WHERE is_active = 1
                ORDER BY name
            """
            results = self.core.db.execute_query(query)
            
            self.products = []
            for row in results:
                if isinstance(row, dict):
                    self.products.append(row)
                else:
                    # Convertir tupla a dict
                    self.products.append({
                        "id": row[0],
                        "sku": row[1],
                        "name": row[2],
                        "department": row[3] or "",
                        "sat_clave_prod_serv": row[4] or "",
                        "sat_clave_unidad": row[5] or ""
                    })
            
            self._apply_filter()
            self._update_table()
            
        except Exception as e:
            logger.error(f"Error cargando productos: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"No se pudieron cargar los productos:\n{e}"
            )
    
    def _on_filter_changed(self):
        """Se ejecuta cuando cambia el filtro."""
        # Actualizar visibilidad del combo de departamento
        is_dept_filter = self.filter_combo.currentText() == "Por departamento..."
        self.dept_filter_combo.setVisible(is_dept_filter)
        
        if is_dept_filter and self.dept_filter_combo.count() == 0:
            # Cargar departamentos únicos
            try:
                depts = self.core.db.execute_query(
                    "SELECT DISTINCT department FROM products WHERE department IS NOT NULL AND department != '' ORDER BY department"
                )
                self.dept_filter_combo.clear()
                self.dept_filter_combo.addItem("(Todos)")
                for dept in depts:
                    dept_name = dept.get("department", "") if isinstance(dept, dict) else dept[0]
                    if dept_name:
                        self.dept_filter_combo.addItem(dept_name)
            except Exception as e:
                logger.error(f"Error cargando departamentos: {e}")
        
        self._apply_filter()
        self._update_table()
    
    def _apply_filter(self):
        """Aplica el filtro seleccionado."""
        filter_text = self.filter_combo.currentText()
        
        if filter_text == "Todos los productos":
            self.filtered_products = self.products.copy()
        
        elif filter_text == "Sin departamento":
            self.filtered_products = [
                p for p in self.products
                if not p.get("department") or p.get("department", "").strip() == ""
            ]
        
        elif filter_text == "Sin código SAT":
            self.filtered_products = [
                p for p in self.products
                if not p.get("sat_clave_prod_serv") or p.get("sat_clave_prod_serv", "").strip() == ""
            ]
        
        elif filter_text == "Sin departamento ni código SAT":
            self.filtered_products = [
                p for p in self.products
                if (not p.get("department") or p.get("department", "").strip() == "") and
                   (not p.get("sat_clave_prod_serv") or p.get("sat_clave_prod_serv", "").strip() == "")
            ]
        
        elif filter_text == "Por departamento...":
            selected_dept = self.dept_filter_combo.currentText()
            if selected_dept == "(Todos)":
                self.filtered_products = self.products.copy()
            else:
                self.filtered_products = [
                    p for p in self.products
                    if p.get("department", "") == selected_dept
                ]
        
        # Generar sugerencias para productos filtrados
        self._generate_suggestions()
    
    def _generate_suggestions(self):
        """Genera sugerencias de clasificación para productos filtrados."""
        classifier = ProductClassifier()
        
        for product in self.filtered_products:
            if "suggestion" not in product:
                try:
                    result = classifier.classify(
                        product.get("name", ""),
                        existing_department=product.get("department") if not self.force_check.isChecked() else None
                    )
                    product["suggestion"] = result
                except Exception as e:
                    logger.error(f"Error generando sugerencia para {product.get('id')}: {e}")
                    product["suggestion"] = None
    
    def _update_table(self):
        """Actualiza la tabla con productos filtrados."""
        self.table.setRowCount(len(self.filtered_products))
        
        for row, product in enumerate(self.filtered_products):
            # Checkbox
            checkbox = QtWidgets.QCheckBox()
            checkbox.setChecked(True)
            self.table.setCellWidget(row, 0, checkbox)
            
            # SKU
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(product.get("sku", ""))))
            
            # Nombre
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(product.get("name", "")))
            
            # Departamento actual
            dept_item = QtWidgets.QTableWidgetItem(product.get("department", "") or "(Sin departamento)")
            if not product.get("department"):
                dept_item.setForeground(QtGui.QColor("#999"))
            self.table.setItem(row, 3, dept_item)
            
            # Departamento sugerido
            suggestion = product.get("suggestion")
            if suggestion:
                dept_suggested = QtWidgets.QTableWidgetItem(suggestion.department)
                self.table.setItem(row, 4, dept_suggested)
                
                # Confianza
                confidence_item = QtWidgets.QTableWidgetItem(f"{suggestion.confidence:.2f}")
                if suggestion.confidence >= 0.8:
                    confidence_item.setForeground(QtGui.QColor("#27ae60"))
                elif suggestion.confidence >= 0.5:
                    confidence_item.setForeground(QtGui.QColor("#f39c12"))
                else:
                    confidence_item.setForeground(QtGui.QColor("#e74c3c"))
                self.table.setItem(row, 5, confidence_item)
                
                # Código SAT sugerido
                sat_item = QtWidgets.QTableWidgetItem(f"{suggestion.sat_clave_prod_serv} ({suggestion.sat_clave_unidad})")
                self.table.setItem(row, 6, sat_item)
            else:
                self.table.setItem(row, 4, QtWidgets.QTableWidgetItem("(Error)"))
                self.table.setItem(row, 5, QtWidgets.QTableWidgetItem("0.00"))
                self.table.setItem(row, 6, QtWidgets.QTableWidgetItem(""))
        
        # Actualizar info label
        total = len(self.filtered_products)
        self.info_label.setText(f"{total} producto(s) encontrado(s)")
    
    def _classify_selected(self):
        """Clasifica solo los productos seleccionados."""
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            QtWidgets.QMessageBox.warning(
                self,
                "Sin selección",
                "Por favor selecciona al menos un producto de la tabla."
            )
            return
        
        # Obtener productos seleccionados
        products_to_classify = [self.filtered_products[row] for row in selected_rows]
        self._start_classification(products_to_classify)
    
    def _classify_all(self):
        """Clasifica todos los productos filtrados."""
        if not self.filtered_products:
            QtWidgets.QMessageBox.warning(
                self,
                "Sin productos",
                "No hay productos para clasificar."
            )
            return
        
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirmar",
            f"¿Clasificar {len(self.filtered_products)} producto(s)?\n\n"
            f"Esto puede tomar varios minutos.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self._start_classification(self.filtered_products)
    
    def _start_classification(self, products: List[Dict[str, Any]]):
        """Inicia el proceso de clasificación en background."""
        if self.worker and self.worker.isRunning():
            QtWidgets.QMessageBox.warning(
                self,
                "Proceso en curso",
                "Ya hay un proceso de clasificación en curso. Por favor espera a que termine."
            )
            return
        
        # Crear progress dialog
        self.progress_dialog = QtWidgets.QProgressDialog(
            "Clasificando productos...",
            "Cancelar",
            0,
            len(products),
            self
        )
        self.progress_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        
        # Crear worker
        self.worker = BulkClassifyWorker(
            self.core,
            products,
            force_reclassify=self.force_check.isChecked(),
            min_confidence=self.confidence_spin.value()
        )
        
        # Conectar señales
        self.worker.progress_updated.connect(self._on_progress_updated)
        self.worker.product_classified.connect(self._on_product_classified)
        self.worker.finished.connect(self._on_classification_finished)
        self.progress_dialog.canceled.connect(self.worker.request_stop)
        
        # Iniciar
        self.worker.start()
    
    def _on_progress_updated(self, current: int, total: int):
        """Actualiza el progreso."""
        if self.progress_dialog:
            self.progress_dialog.setMaximum(total)
            self.progress_dialog.setValue(current)
    
    def _on_product_classified(self, product_data: Dict[str, Any]):
        """Se ejecuta cuando un producto es clasificado."""
        # Actualizar tabla en tiempo real (opcional)
        pass
    
    def _on_classification_finished(self, results: Dict[str, Any]):
        """Se ejecuta cuando termina la clasificación."""
        if self.progress_dialog:
            self.progress_dialog.close()
        
        summary = results.get("summary", {})
        
        msg = (
            f"Clasificación completada:\n\n"
            f"✓ Clasificados: {summary.get('classified', 0)}\n"
            f"⚠ Sin clasificar: {summary.get('unclassified', 0)}\n"
            f"✗ Errores: {summary.get('errors', 0)}\n"
            f"Total: {summary.get('total', 0)}"
        )
        
        QtWidgets.QMessageBox.information(self, "Clasificación Completada", msg)
        
        # Refrescar tabla
        self._load_products()
    
    def _export_unclassified(self):
        """Exporta productos sin clasificar a Excel."""
        unclassified = [
            p for p in self.filtered_products
            if not p.get("suggestion") or p.get("suggestion").confidence < self.confidence_spin.value()
        ]
        
        if not unclassified:
            QtWidgets.QMessageBox.information(
                self,
                "Sin productos sin clasificar",
                "Todos los productos filtrados tienen clasificación válida."
            )
            return
        
        # Pedir ubicación de archivo
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Exportar Productos Sin Clasificar",
            f"productos_sin_clasificar_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "Excel Files (*.xlsx);;CSV Files (*.csv)"
        )
        
        if not filename:
            return
        
        try:
            import openpyxl
            from openpyxl import Workbook
            
            wb = Workbook()
            ws = wb.active
            ws.title = "Productos Sin Clasificar"
            
            # Headers
            headers = ["ID", "SKU", "Nombre", "Departamento Actual", "Código SAT Actual"]
            ws.append(headers)
            
            # Data
            for product in unclassified:
                ws.append([
                    product.get("id"),
                    product.get("sku", ""),
                    product.get("name", ""),
                    product.get("department", ""),
                    product.get("sat_clave_prod_serv", "")
                ])
            
            wb.save(filename)
            
            QtWidgets.QMessageBox.information(
                self,
                "Exportación Exitosa",
                f"Se exportaron {len(unclassified)} productos a:\n{filename}"
            )
            
        except ImportError:
            QtWidgets.QMessageBox.warning(
                self,
                "Error",
                "openpyxl no está instalado. Instala con: pip install openpyxl"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"No se pudo exportar:\n{e}"
            )
    
    def closeEvent(self, event):
        """Cleanup worker thread on close."""
        if self.worker and self.worker.isRunning():
            self.worker.request_stop()
            self.worker.quit()
            if not self.worker.wait(3000):
                logger.warning("BulkClassifyWorker did not stop gracefully")
            self.worker = None
        super().closeEvent(event)

    def update_theme(self):
        """Actualiza el tema del diálogo."""
        theme_manager.apply_theme_to_widget(self)
