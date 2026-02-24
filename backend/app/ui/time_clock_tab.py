"""
Time Clock Tab - Employee Attendance Management UI
Real-time dashboard and attendance tracking
"""

import logging
from typing import Optional
from datetime import date, datetime
from decimal import Decimal

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger(__name__)

from app.dialogs.time_clock_dialogs import TimeClockManualEntryDialog, TimeClockReportsDialog
from app.dialogs.time_clock_settings_dialog import TimeClockSettingsDialog
from app.utils.theme_manager import theme_manager
from src.core.time_clock_engine import TimeClockEngine


class TimeClockTab(QtWidgets.QWidget):
    """Tab for time clock management."""
    
    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.time_clock_engine = TimeClockEngine(self.core.db)
        self._build_ui()
        self._refresh_all()
        
        # Auto-refresh timer
        self.refresh_timer = QtCore.QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_all)
        self.refresh_timer.start(30000)  # Refresh every 30 seconds
    
    def _build_ui(self):
        """Build the UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header = QtWidgets.QLabel("⏰ CONTROL DE ASISTENCIA")
        header.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            padding: 10px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #3498db, stop:1 #2980b9);
            color: white;
            border-radius: 8px;
        """)
        header.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Top section - Quick actions and stats
        top_layout = QtWidgets.QHBoxLayout()
        
        # Quick Check-In Panel
        checkin_group = QtWidgets.QGroupBox("🚪 CHECK-IN RÁPIDO")
        checkin_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #27ae60;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title { color: #27ae60; }
        """)
        checkin_layout = QtWidgets.QVBoxLayout()
        
        self.employee_combo = QtWidgets.QComboBox()
        self.employee_combo.setPlaceholderText("Seleccionar empleado...")
        self.employee_combo.setStyleSheet("padding: 8px; font-size: 14px;")
        self.employee_combo.currentIndexChanged.connect(self._update_button_states)
        checkin_layout.addWidget(self.employee_combo)
        
        btn_layout = QtWidgets.QHBoxLayout()
        
        self.btn_check_in = QtWidgets.QPushButton("✅ CHECK IN")
        # Style applied dynamically in _update_button_states
        self.btn_check_in.clicked.connect(self._quick_check_in)
        
        self.btn_check_out = QtWidgets.QPushButton("🔴 CHECK OUT")
        # Style applied dynamically in _update_button_states
        self.btn_check_out.clicked.connect(self._quick_check_out)
        
        btn_layout.addWidget(self.btn_check_in)
        btn_layout.addWidget(self.btn_check_out)
        checkin_layout.addLayout(btn_layout)
        
        self.btn_break = QtWidgets.QPushButton("☕ Iniciar Break")
        self.btn_break.setStyleSheet("padding: 8px; font-size: 13px;")
        self.btn_break.clicked.connect(self._toggle_break)
        checkin_layout.addWidget(self.btn_break)
        
        checkin_group.setLayout(checkin_layout)
        top_layout.addWidget(checkin_group)
        
        # Stats Panel
        stats_group = QtWidgets.QGroupBox("📊 ESTADO EN TIEMPO REAL")
        stats_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3498db;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title { color: #2c3e50; }
        """)
        stats_layout = QtWidgets.QVBoxLayout()
        
        self.stats_label = QtWidgets.QLabel()
        self.stats_label.setStyleSheet("font-size: 13px; padding: 10px;")
        self.stats_label.setWordWrap(True)
        stats_layout.addWidget(self.stats_label)
        
        stats_group.setLayout(stats_layout)
        top_layout.addWidget(stats_group)
        
        layout.addLayout(top_layout)
        
        # Attendance Table
        table_label = QtWidgets.QLabel(f"📋 ASISTENCIA HOY - {date.today().strftime('%Y-%m-%d')}")
        table_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px; margin-top: 10px;")
        layout.addWidget(table_label)
        
        self.attendance_table = QtWidgets.QTableWidget()
        self.attendance_table.setColumnCount(7)
        self.attendance_table.setHorizontalHeaderLabels([
            "Código", "Empleado", "Entrada", "Salida", "Horas", "Break", "Estado"
        ])
        self.attendance_table.horizontalHeader().setStretchLastSection(True)
        self.attendance_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.attendance_table.setAlternatingRowColors(True)
        self.attendance_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)  # Read-only
        self.attendance_table.setStyleSheet("""
            QTableWidget {
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                font-size: 13px;
            }
            QTableWidget::item { padding: 8px; }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                padding: 10px;
                font-weight: bold;
                border: none;
            }
        """)
        layout.addWidget(self.attendance_table)
        
        # Action buttons
        action_layout = QtWidgets.QHBoxLayout()
        
        btn_manual = QtWidgets.QPushButton("➕ Entrada Manual")
        btn_manual.setStyleSheet("padding: 8px;")
        btn_manual.clicked.connect(self._manual_entry)
        
        btn_reports = QtWidgets.QPushButton("📊 Reportes")
        btn_reports.setStyleSheet("padding: 8px;")
        btn_reports.clicked.connect(self._open_reports)
        
        btn_refresh = QtWidgets.QPushButton("🔄 Actualizar")
        btn_refresh.setStyleSheet("padding: 8px;")
        btn_refresh.clicked.connect(self._refresh_all)
        
        action_layout.addWidget(btn_manual)
        action_layout.addWidget(btn_reports)
        
        btn_settings = QtWidgets.QPushButton("⚙️ Configurar")
        btn_settings.setStyleSheet("padding: 8px;")
        btn_settings.clicked.connect(self._open_settings)
        action_layout.addWidget(btn_settings)
        
        action_layout.addStretch()
        action_layout.addWidget(btn_refresh)
        
        layout.addLayout(action_layout)
    
    def _load_employees(self):
        """Load employees into combo box."""
        self.employee_combo.clear()
        
        try:
            employees = self.core.loan_engine.list_employees(status='active')
            for emp in employees:
                self.employee_combo.addItem(
                    f"{emp['employee_code']} - {emp['name']}",
                    emp['id']
                )
        except Exception as e:
            # FIX 2026-02-01: Usar logger
            logger.debug("Error loading employees: %s", e)
        
        self._update_button_states()
    
    def _get_theme_colors(self):
        """Get current theme colors."""
        theme = (self.core.get_app_config() or {}).get("theme", "Light")
        return theme_manager.get_colors(theme)

    def _update_button_states(self):
        """Update buttons based on selected employee status."""
        emp_id = self.employee_combo.currentData()
        
        if not emp_id:
            self.btn_check_in.setEnabled(False)
            self.btn_check_out.setEnabled(False)
            self.btn_break.setEnabled(False)
            self.btn_break.setText("☕ Break")
            return
            
        try:
            status = self.time_clock_engine.get_current_status(emp_id)
            c = self._get_theme_colors()
            
            is_checked_in = status['is_checked_in']
            on_break = status.get('on_break', False)
            
            # Check In button
            self.btn_check_in.setEnabled(not is_checked_in)
            if is_checked_in:
                self.btn_check_in.setStyleSheet(f"background-color: {c['btn_disabled']}; color: {c['text_disabled']}; padding: 12px; border-radius: 5px;")
            else:
                self.btn_check_in.setStyleSheet(f"background-color: {c['btn_success']}; color: white; font-weight: bold; font-size: 14px; padding: 12px; border-radius: 5px;")
                
            # Check Out button
            self.btn_check_out.setEnabled(is_checked_in)
            if not is_checked_in:
                self.btn_check_out.setStyleSheet(f"background-color: {c['btn_disabled']}; color: {c['text_disabled']}; padding: 12px; border-radius: 5px;")
            else:
                self.btn_check_out.setStyleSheet(f"background-color: {c['btn_danger']}; color: white; font-weight: bold; font-size: 14px; padding: 12px; border-radius: 5px;")
                
            # Break button
            self.btn_break.setEnabled(is_checked_in)
            if on_break:
                self.btn_break.setText("▶️ Terminar Break")
                self.btn_break.setStyleSheet(f"background-color: {c['btn_warning']}; color: white; font-weight: bold; padding: 8px; font-size: 13px; border-radius: 5px;")
            else:
                self.btn_break.setText("☕ Iniciar Break")
                if is_checked_in:
                    self.btn_break.setStyleSheet(f"background-color: {c['btn_primary']}; color: white; padding: 8px; font-size: 13px; border-radius: 5px;")
                else:
                    self.btn_break.setStyleSheet(f"background-color: {c['btn_disabled']}; color: {c['text_disabled']}; padding: 8px; border-radius: 5px;")
                    
        except Exception as e:
            # FIX 2026-02-01: Usar logger
            logger.debug("Error updating buttons: %s", e)
    
    def _refresh_all(self):
        """Refresh all data."""
        self._load_employees()
        self._update_stats()
        self._load_attendance_table()
        # Keep selection if possible
        self._update_button_states()
    
    def _update_stats(self):
        """Update real-time stats."""
        try:
            today = date.today().isoformat()
            daily_attendance = self.time_clock_engine.get_daily_attendance(today)
            
            active_count = sum(1 for a in daily_attendance if a.get('is_checked_in'))
            on_break_count = sum(1 for a in daily_attendance if a.get('on_break'))
            late_count = sum(1 for a in daily_attendance if a.get('was_late'))
            total_hours = sum(Decimal(str(a.get('hours_worked', 0))) for a in daily_attendance)
            
            stats_html = f"""
            <div style='line-height: 1.8;'>
                <p><b>👤 Empleados Activos:</b> <span style='color: #27ae60; font-size: 16px;'>{active_count}</span></p>
                <p><b>⏰ Total Horas Hoy:</b> <span style='color: #3498db; font-size: 16px;'>{float(total_hours):.1f}h</span></p>
                <p><b>☕ En Break:</b> <span style='color: #f39c12; font-size: 16px;'>{on_break_count}</span></p>
                <p><b>⚠️ Tardanzas:</b> <span style='color: #e74c3c; font-size: 16px;'>{late_count}</span></p>
            </div>
            """
            self.stats_label.setText(stats_html)
            
        except Exception as e:
            self.stats_label.setText(f"Error: {e}")
    
    def _load_attendance_table(self):
        """Load today's attendance into table."""
        self.attendance_table.setRowCount(0)
        
        try:
            today = date.today().isoformat()
            attendance = self.time_clock_engine.get_daily_attendance(today)
            
            for att in attendance:
                row = self.attendance_table.rowCount()
                self.attendance_table.insertRow(row)
                
                # Employee code
                self.attendance_table.setItem(row, 0, QtWidgets.QTableWidgetItem(att['employee_code']))
                
                # Employee name
                self.attendance_table.setItem(row, 1, QtWidgets.QTableWidgetItem(att['employee_name']))
                
                # Check-in time
                check_in = att.get('check_in_time', '--:--')
                if check_in and check_in != '--:--':
                    check_in = datetime.fromisoformat(check_in).strftime('%H:%M')
                self.attendance_table.setItem(row, 2, QtWidgets.QTableWidgetItem(check_in))
                
                # Check-out time
                check_out = att.get('check_out_time', '--:--')
                if check_out and check_out != '--:--':
                    check_out = datetime.fromisoformat(check_out).strftime('%H:%M')
                self.attendance_table.setItem(row, 3, QtWidgets.QTableWidgetItem(check_out))
                
                # Hours worked
                hours = float(att.get('hours_worked', 0))
                hours_item = QtWidgets.QTableWidgetItem(f"{hours:.1f}h")
                if att.get('is_checked_in'):
                    hours_item.setForeground(QtGui.QColor("#27ae60"))
                self.attendance_table.setItem(row, 4, hours_item)
                
                # Break time
                break_mins = att.get('break_minutes', 0)
                break_text = f"{break_mins}min" if break_mins > 0 else "--"
                self.attendance_table.setItem(row, 5, QtWidgets.QTableWidgetItem(break_text))
                
                # Status
                status = "🟢 Activo" if att.get('is_checked_in') else "✅ Completo"
                if att.get('on_break'):
                    status = "☕ Break"
                elif att.get('was_late'):
                    status += " ⚠️"
                    
                status_item = QtWidgets.QTableWidgetItem(status)
                self.attendance_table.setItem(row, 6, status_item)
                
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Error al cargar asistencia: {e}")
    
    def _quick_check_in(self):
        """Quick check-in for selected employee."""
        employee_id = self.employee_combo.currentData()
        if not employee_id:
            QtWidgets.QMessageBox.warning(self, "Error", "Seleccione un empleado")
            return
        
        try:
            from app.core import STATE
            result = self.time_clock_engine.check_in(
                employee_id=employee_id,
                user_id=STATE.user_id,
                location="POS Terminal"
            )
            
            msg = f"✅ Check-in exitoso\n\n"
            msg += f"Empleado: {result['employee_name']}\n"
            msg += f"Hora: {datetime.fromisoformat(result['check_in_time']).strftime('%H:%M')}\n"
            
            if result['is_late']:
                msg += f"\n⚠️ Tardanza: {result['late_minutes']} minutos"
            
            QtWidgets.QMessageBox.information(self, "Check-In", msg)
            self._refresh_all()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
    
    def _quick_check_out(self):
        """Quick check-out for selected employee."""
        employee_id = self.employee_combo.currentData()
        if not employee_id:
            QtWidgets.QMessageBox.warning(self, "Error", "Seleccione un empleado")
            return
        
        try:
            from app.core import STATE
            result = self.time_clock_engine.check_out(
                employee_id=employee_id,
                user_id=STATE.user_id
            )
            
            msg = f"🔴 Check-out exitoso\n\n"
            msg += f"Empleado: {result['employee_name']}\n"
            msg += f"Entrada: {datetime.fromisoformat(result['check_in_time']).strftime('%H:%M')}\n"
            msg += f"Salida: {datetime.fromisoformat(result['check_out_time']).strftime('%H:%M')}\n"
            msg += f"\nHoras Trabajadas: {float(result['total_hours']):.2f}h\n"
            msg += f"  • Regular: {float(result['regular_hours']):.2f}h\n"
            msg += f"  • Extra: {float(result['overtime_hours']):.2f}h\n"
            
            if result['break_minutes'] > 0:
                msg += f"\nBreaks: {result['break_minutes']} minutos"
            
            QtWidgets.QMessageBox.information(self, "Check-Out", msg)
            self._refresh_all()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
    
    def _toggle_break(self):
        """Toggle break for selected employee."""
        employee_id = self.employee_combo.currentData()
        if not employee_id:
            QtWidgets.QMessageBox.warning(self, "Error", "Seleccione un empleado")
            return
        
        try:
            # Check current status
            status = self.time_clock_engine.get_current_status(employee_id)
            
            if not status['is_checked_in']:
                QtWidgets.QMessageBox.warning(self, "Error", "Empleado no ha hecho check-in")
                return
            
            if status['on_break']:
                # End break
                result = self.time_clock_engine.end_break(employee_id)
                QtWidgets.QMessageBox.information(
                    self,
                    "Break Terminado",
                    f"Break terminado\nDuración: {result['duration_minutes']} minutos"
                )
            else:
                # Start break
                break_id = self.time_clock_engine.start_break(employee_id)
                QtWidgets.QMessageBox.information(self, "Break Iniciado", "Break iniciado correctamente")
            
            self._refresh_all()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
    
    def _manual_entry(self):
        """Open manual entry dialog."""
        # Restrict to Admin/Manager if needed. For now let's assume STATE verifies user.
        # Ideally check STATE.current_user_role
        
        emp_id = self.employee_combo.currentData()
        
        dialog = TimeClockManualEntryDialog(
            time_clock_engine=self.time_clock_engine,
            employee_id=emp_id, # Optional pre-selection
            parent=self
        )
        if dialog.exec():
            self._refresh_all()
    
    def _open_reports(self):
        """Open reports dialog."""
        dialog = TimeClockReportsDialog(
            time_clock_engine=self.time_clock_engine,
            parent=self
        )
        dialog.exec()
        
    def _open_settings(self):
        """Open settings dialog."""
        dialog = TimeClockSettingsDialog(
            time_clock_engine=self.time_clock_engine,
            parent=self
        )
        dialog.exec()
    
    def refresh(self):
        """Public refresh method."""
        self._refresh_all()
        
    def update_theme(self):
        """Update theme."""
        theme = (self.core.get_app_config() or {}).get("theme", "Light")
        c = theme_manager.get_colors(theme)
        
        # Header (keeps gradient in this implementation but could be changed)
        # For now let's just make sure other elements assume theme colors
        
        # Stats Label
        if hasattr(self, 'stats_label'):
             # We reconstruct HTML in _update_stats, so we just need to ensure background is correct
             pass
        
        # Table
        if hasattr(self, 'attendance_table'):
             self.attendance_table.setStyleSheet(f"""
                QTableWidget {{
                    background-color: {c['bg_card']};
                    color: {c['text_primary']};
                    border: 1px solid {c['border']};
                    border-radius: 5px;
                    font-size: 13px;
                }}
                QTableWidget::item {{
                    padding: 8px;
                    color: {c['text_primary']};
                }}
                QHeaderView::section {{
                    background-color: {c['bg_header']};
                    color: {c['text_header']};
                    padding: 10px;
                    font-weight: bold;
                    border: none;
                }}
            """)
        
        # Repaint
    
    def showEvent(self, event):
        """Aplicar tema cuando se muestra el tab."""
        super().showEvent(event)
        if hasattr(self, 'update_theme'):
            self.update_theme()
        self.style().unpolish(self)
        self.style().polish(self)

    def closeEvent(self, event):
        """Cleanup timers on close."""
        if hasattr(self, 'refresh_timer') and self.refresh_timer:
            self.refresh_timer.stop()
        super().closeEvent(event)
