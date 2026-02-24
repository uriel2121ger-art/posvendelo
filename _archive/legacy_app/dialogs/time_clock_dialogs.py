"""
TIME CLOCK DIALOGS
Dialogs for manual entry and reporting in Time Clock module
"""

import csv
from datetime import date, datetime

from PyQt6 import QtCore, QtGui, QtWidgets


class TimeClockManualEntryDialog(QtWidgets.QDialog):
    """Dialog for manual check-in/out entry."""
    
    def __init__(self, time_clock_engine, employee_id=None, parent=None):
        super().__init__(parent)
        self.engine = time_clock_engine
        self.employee_id = employee_id
        
        self.setWindowTitle("Entrada Manual de Asistencia")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        self._build_ui()
        
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        form = QtWidgets.QFormLayout()
        
        # Employee (if not provided)
        # For simplicity, we assume employee is pre-selected or passed. 
        # But if needed we could add a combo here. 
        # Let's assume passed for now, or just show ID if passed.
        
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems(["Entrada (Check-In)", "Salida (Check-Out)"])
        form.addRow("Tipo:", self.type_combo)
        
        self.date_edit = QtWidgets.QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(date.today())
        form.addRow("Fecha:", self.date_edit)
        
        self.time_edit = QtWidgets.QTimeEdit()
        self.time_edit.setTime(datetime.now().time())
        form.addRow("Hora:", self.time_edit)
        
        self.notes_input = QtWidgets.QLineEdit()
        self.notes_input.setPlaceholderText("Razón del registro manual...")
        form.addRow("Notas:", self.notes_input)
        
        layout.addLayout(form)
        
        # Buttons
        buttons = QtWidgets.QHBoxLayout()
        saved_btn = QtWidgets.QPushButton("Guardar")
        saved_btn.setStyleSheet("")  # Styled in showEvent
        saved_btn.clicked.connect(self._save)
        
        cancel_btn = QtWidgets.QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addWidget(cancel_btn)
        buttons.addWidget(saved_btn)
        layout.addLayout(buttons)
        
    def _save(self):
        try:
            from app.core import STATE
            entry_type = "check_in" if self.type_combo.currentIndex() == 0 else "check_out"
            
            entry_dt = datetime.combine(
                self.date_edit.date().toPyDate(),
                self.time_edit.time().toPyTime()
            )
            timestamp = entry_dt.isoformat()
            
            if entry_type == "check_in":
                self.engine.check_in(
                    employee_id=self.employee_id,
                    user_id=STATE.user_id,
                    notes=self.notes_input.text(),
                    timestamp=timestamp
                )
            else:
                self.engine.check_out(
                    employee_id=self.employee_id,
                    user_id=STATE.user_id,
                    notes=self.notes_input.text(),
                    timestamp=timestamp
                )
                
            QtWidgets.QMessageBox.information(self, "Éxito", "Registro manual guardado.")
            self.accept()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

class TimeClockReportsDialog(QtWidgets.QDialog):
    """Dialog for attendance reports."""
    
    def __init__(self, time_clock_engine, parent=None):
        super().__init__(parent)
        self.engine = time_clock_engine
        self.setWindowTitle("Reportes de Asistencia")
        self.resize(800, 600)
        self._build_ui()
        
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Filters
        filter_layout = QtWidgets.QHBoxLayout()
        
        self.start_date = QtWidgets.QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(date.today().replace(day=1)) # First of month
        
        self.end_date = QtWidgets.QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(date.today())
        
        filter_layout.addWidget(QtWidgets.QLabel("Desde:"))
        filter_layout.addWidget(self.start_date)
        filter_layout.addWidget(QtWidgets.QLabel("Hasta:"))
        filter_layout.addWidget(self.end_date)
        
        btn_refresh = QtWidgets.QPushButton("Generar Reporte")
        btn_refresh.clicked.connect(self._generate_report)
        filter_layout.addWidget(btn_refresh)
        
        btn_export = QtWidgets.QPushButton("Exportar CSV")
        btn_export.clicked.connect(self._export_csv)
        filter_layout.addWidget(btn_export)
        
        layout.addLayout(filter_layout)
        
        # Table
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Fecha", "Empleado", "Entrada", "Salida", "Horas", "Estado"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        # Initial Load
        self._generate_report()
        
    def _generate_report(self):
        start_date = self.start_date.date().toString("yyyy-MM-dd")
        end_date = self.end_date.date().toString("yyyy-MM-dd")
        
        try:
            records = self.engine.get_attendance_range(start_date, end_date)
            self.table.setRowCount(0)
            
            for row, record in enumerate(records):
                self.table.insertRow(row)
                
                # Format check-in/out
                check_in = record.get('check_in_time', '--:--')
                check_out = record.get('check_out_time', '--:--')
                
                self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(record.get('date', '')))
                self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(record.get('employee_name', '')))
                self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(check_in))
                self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(check_out))
                
                hours = float(record.get('total_hours', 0))
                self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(f"{hours:.2f}"))
                
                status = "Presente"
                if record.get('was_late'):
                    status = "Tardanza"
                
                self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(status))
        
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Error generando reporte: {e}")
        
    def _export_csv(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Guardar Reporte", "asistencia.csv", "CSV Files (*.csv)"
        )
        if filename:
            try:
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Fecha", "Empleado", "Entrada", "Salida", "Horas", "Estado"])
                    for row in range(self.table.rowCount()):
                        writer.writerow([
                            self.table.item(row, 0).text(),
                            self.table.item(row, 1).text(),
                            self.table.item(row, 2).text(),
                            self.table.item(row, 3).text(),
                            self.table.item(row, 4).text(),
                            self.table.item(row, 5).text(),
                        ])
                QtWidgets.QMessageBox.information(self, "Éxito", "Reporte exportado.")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Error al exportar: {e}")

    def showEvent(self, event):
        """Apply theme colors"""
        super().showEvent(event)
        try:
            from app.utils.theme_manager import theme_manager
            c = theme_manager.get_colors()
            # Apply theme to buttons
            for btn in self.findChildren(QtWidgets.QPushButton):
                text = btn.text().lower()
                if any(word in text for word in ['guardar', 'save', 'crear', 'create']):
                    btn.setStyleSheet(f"background: {c['btn_success']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
                elif any(word in text for word in ['eliminar', 'delete', 'cancelar', 'cancel', 'confirmar']):
                    btn.setStyleSheet(f"background: {c['btn_danger']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
                elif any(word in text for word in ['restaurar', 'restore']):
                    btn.setStyleSheet(f"background: {c['btn_success']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
                elif any(word in text for word in ['agregar', 'add']):
                    btn.setStyleSheet(f"background: {c['btn_primary']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
        except Exception as e:
            pass  # Silently fail if theme_manager not available

