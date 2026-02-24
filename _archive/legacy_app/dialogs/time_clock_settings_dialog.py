"""
Time Clock Settings Dialog
"""

from PyQt6 import QtCore, QtWidgets

from src.core.time_clock_engine import TimeClockEngine


class TimeClockSettingsDialog(QtWidgets.QDialog):
    """Dialog to configure time clock rules."""
    
    def __init__(self, time_clock_engine: TimeClockEngine, parent=None):
        super().__init__(parent)
        self.engine = time_clock_engine
        self.setWindowTitle("Configuración de Asistencia")
        self.setMinimumWidth(400)
        self._build_ui()
        self._load_values()
        
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        form_group = QtWidgets.QGroupBox("Reglas Generales")
        form = QtWidgets.QFormLayout(form_group)
        
        self.start_time = QtWidgets.QTimeEdit()
        self.start_time.setDisplayFormat("HH:mm")
        form.addRow("Hora Entrada Estándar:", self.start_time)
        
        self.end_time = QtWidgets.QTimeEdit()
        self.end_time.setDisplayFormat("HH:mm")
        form.addRow("Hora Salida Estándar:", self.end_time)
        
        self.grace_period = QtWidgets.QSpinBox()
        self.grace_period.setRange(0, 120)
        self.grace_period.setSuffix(" min")
        form.addRow("Tolerancia Retardo:", self.grace_period)
        
        self.max_break = QtWidgets.QSpinBox()
        self.max_break.setRange(0, 240)
        self.max_break.setSuffix(" min")
        form.addRow("Duración Max. Break:", self.max_break)
        
        layout.addWidget(form_group)
        
        # Buttons
        buttons = QtWidgets.QHBoxLayout()
        save_btn = QtWidgets.QPushButton("Guardar")
        save_btn.setStyleSheet("")  # Styled in showEvent
        save_btn.clicked.connect(self._save)
        
        cancel_btn = QtWidgets.QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)
        layout.addLayout(buttons)
        
    def _load_values(self):
        rules = self.engine.rules
        
        start = rules.get('standard_start_time', '08:00')
        self.start_time.setTime(QtCore.QTime.fromString(start, "HH:mm"))
        
        end = rules.get('standard_end_time', '17:00')
        self.end_time.setTime(QtCore.QTime.fromString(end, "HH:mm"))
        
        self.grace_period.setValue(int(rules.get('grace_period_minutes', 15)))
        self.max_break.setValue(int(rules.get('max_break_duration_minutes', 60)))
        
    def _save(self):
        new_rules = {
            'standard_start_time': self.start_time.time().toString("HH:mm"),
            'standard_end_time': self.end_time.time().toString("HH:mm"),
            'grace_period_minutes': self.grace_period.value(),
            'max_break_duration_minutes': self.max_break.value()
        }
        
        if self.engine.save_rules(new_rules):
            QtWidgets.QMessageBox.information(self, "Éxito", "Configuración guardada correctamente.")
            self.accept()
        else:
            QtWidgets.QMessageBox.critical(self, "Error", "Error al guardar configuración.")

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

