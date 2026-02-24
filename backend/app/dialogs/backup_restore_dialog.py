"""
Backup Restore Dialog - Complete UI for disaster recovery
"""

import logging
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger(__name__)

class BackupRestoreDialog(QtWidgets.QDialog):
    """Dialog for restoring from backup."""
    
    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.selected_backup = None
        
        self.setWindowTitle("🔄 Restaurar Respaldo")
        self.setMinimumSize(800, 600)
        
        self._setup_ui()
        self._load_backups()
    
    def _setup_ui(self):
        """Setup UI components."""
        layout = QtWidgets.QVBoxLayout(self)
        
        # Title
        title = QtWidgets.QLabel("🔄 Restaurar Sistema desde Respaldo")
        title_font = title.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Warning
        warning = QtWidgets.QLabel(
            "⚠️ ADVERTENCIA: La restauración reemplazará TODOS los datos actuales.\n"
            "   Se creará un respaldo de seguridad antes de restaurar."
        )
        warning.setStyleSheet("color: #e74c3c; background-color: #fef5e7; padding: 10px; border-radius: 5px;")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        
        # Backups table
        layout.addWidget(QtWidgets.QLabel("\n📦 Respaldos Disponibles:"))
        
        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Fecha", "Tamaño", "Comprimido", "Cifrado", "Notas"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)
        
        # Info panel
        self.info_panel = QtWidgets.QTextEdit()
        self.info_panel.setReadOnly(True)
        self.info_panel.setMaximumHeight(150)
        self.info_panel.setPlaceholderText("Seleccione un respaldo para ver detalles...")
        layout.addWidget(self.info_panel)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        self.refresh_btn = QtWidgets.QPushButton("🔄 Actualizar Lista")
        self.refresh_btn.clicked.connect(self._load_backups)
        button_layout.addWidget(self.refresh_btn)
        
        button_layout.addStretch()
        
        self.cancel_btn = QtWidgets.QPushButton("❌ Cancelar")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.restore_btn = QtWidgets.QPushButton("✅ RESTAURAR SELECCIONADO")
        self.restore_btn.clicked.connect(self._restore_backup)
        self.restore_btn.setEnabled(False)
        self.restore_btn.setStyleSheet("")  # Styled in showEvent
        button_layout.addWidget(self.restore_btn)
        
        layout.addLayout(button_layout)
    
    def _load_backups(self):
        """Load available backups."""
        try:
            from app.utils.backup_engine import BackupEngine
            
            engine = BackupEngine(self.core)
            backups = engine.list_backups(limit=100)
            
            self.table.setRowCount(0)
            self.backups_data = {}
            
            for backup in backups:
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                # Store backup data
                backup_id = backup['id']
                self.backups_data[row] = backup
                
                # ID
                self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(backup_id)))
                
                # Date
                created = backup.get('created_at', 'N/A')
                # Handle datetime objects or strings
                if isinstance(created, str):
                    if isinstance(created, str) and 'T' in created:
                        created = created.split('.')[0].replace('T', ' ')
                elif hasattr(created, 'strftime'):
                    # It's a datetime object
                    created = created.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    created = str(created)
                self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(created))
                
                # Size
                size_mb = backup.get('size', 0) / (1024 * 1024)
                self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{size_mb:.2f} MB"))
                
                # Compressed
                compressed = "Sí" if backup.get('compressed') else "No"
                self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(compressed))
                
                # Encrypted
                encrypted = "Sí" if backup.get('encrypted') else "No"
                self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(encrypted))
                
                # Notes
                notes = backup.get('notes', '')
                self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(notes))
            
            if backups:
                self.info_panel.setPlainText(f"✅ {len(backups)} respaldos encontrados")
            else:
                self.info_panel.setPlainText("⚠️ No hay respaldos disponibles")
                
        except Exception as e:
            logger.error(f"Error loading backups: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"No se pudieron cargar los respaldos:\n\n{str(e)}"
            )
    
    def _on_selection_changed(self):
        """Handle backup selection."""
        selected_rows = self.table.selectionModel().selectedRows()
        
        if selected_rows:
            row = selected_rows[0].row()
            backup = self.backups_data.get(row)
            
            if backup:
                self.selected_backup = backup
                self.restore_btn.setEnabled(True)
                
                # Show backup details
                size_mb = backup.get('size', 0) / (1024 * 1024)
                
                info = f"📦 Detalles del Respaldo:\n\n"
                info += f"ID: {backup['id']}\n"
                info += f"Archivo: {backup['filename']}\n"
                info += f"Fecha: {backup.get('created_at', 'N/A')}\n"
                info += f"Tamaño: {size_mb:.2f} MB\n"
                info += f"Comprimido: {'Sí' if backup.get('compressed') else 'No'}\n"
                info += f"Cifrado: {'Sí' if backup.get('encrypted') else 'No'}\n"
                info += f"Checksum: {(backup.get('checksum') or 'N/A')[:32]}...\n"
                info += f"Notas: {backup.get('notes', 'N/A')}\n"
                
                self.info_panel.setPlainText(info)
        else:
            self.selected_backup = None
            self.restore_btn.setEnabled(False)
            self.info_panel.setPlainText("Seleccione un respaldo para ver detalles...")
    
    def _restore_backup(self):
        """Restore selected backup."""
        if not self.selected_backup:
            return
        
        backup = self.selected_backup
        
        # Triple confirmation
        reply = QtWidgets.QMessageBox.question(
            self,
            "⚠️ CONFIRMACIÓN REQUERIDA",
            f"¿Está COMPLETAMENTE SEGURO que desea restaurar este respaldo?\n\n"
            f"Fecha: {backup.get('created_at', 'N/A')}\n"
            f"Tamaño: {backup.get('size', 0) / (1024*1024):.2f} MB\n\n"
            f"⚠️ ESTO REEMPLAZARÁ:\n"
            f"   • Toda la base de datos (clientes, productos, ventas, etc.)\n"
            f"   • Toda la configuración\n"
            f"   • Todas las imágenes y archivos\n\n"
            f"Se guardará un respaldo de seguridad antes de restaurar.\n\n"
            f"¿PROCEDER CON LA RESTAURACIÓN?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        
        # Second confirmation
        password, ok = QtWidgets.QInputDialog.getText(
            self,
            "Verificación de Seguridad",
            "Para confirmar, escriba 'RESTAURAR' (en mayúsculas):",
            QtWidgets.QLineEdit.EchoMode.Normal
        )
        
        if not ok or password != "RESTAURAR":
            QtWidgets.QMessageBox.information(
                self,
                "Cancelado",
                "Restauración cancelada por el usuario."
            )
            return
        
        # Show progress
        progress = QtWidgets.QProgressDialog(
            "Restaurando respaldo...\n\nPor favor NO cierre esta ventana.\nEsto puede tardar varios minutos.",
            None,
            0,
            0,
            self
        )
        progress.setWindowTitle("Restauración en Progreso")
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        
        QtWidgets.QApplication.processEvents()
        
        try:
            from app.utils.backup_engine import BackupEngine
            
            engine = BackupEngine(self.core)
            
            # Perform restore - use path if id is None (physical file) or id if available (database record)
            if backup.get('id') and backup.get('id') is not None:
                result = engine.restore_backup(backup_id=backup['id'], confirm=True)
            elif backup.get('path'):
                result = engine.restore_backup(backup_path=backup['path'], confirm=True)
            else:
                result = {'success': False, 'error': 'Backup information incomplete: missing id and path'}
            
            progress.close()
            
            if result.get('success'):
                QtWidgets.QMessageBox.information(
                    self,
                    "✅ Restauración Completada",
                    f"El respaldo ha sido restaurado exitosamente.\n\n"
                    f"Timestamp del backup: {result.get('backup_timestamp')}\n\n"
                    f"⚠️ IMPORTANTE: Debe REINICIAR la aplicación ahora para que los cambios surtan efecto.\n\n"
                    f"La aplicación se cerrará al hacer click en OK."
                )
                
                # Close application
                import sys
                sys.exit(0)
            else:
                QtWidgets.QMessageBox.critical(
                    self,
                    "❌ Error en Restauración",
                    f"No se pudo restaurar el respaldo:\n\n{result.get('error', 'Error desconocido')}\n\n"
                    f"Los datos actuales NO han sido modificados."
                )
        
        except Exception as e:
            progress.close()
            logger.error(f"Restore error: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "❌ Error Crítico",
                f"Error durante la restauración:\n\n{str(e)}\n\n"
                f"Los datos pueden estar en estado inconsistente.\n"
                f"Se recomienda verificar manualmente."
            )

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

