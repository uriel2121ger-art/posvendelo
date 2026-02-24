from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout


class CustomerProDialog(QDialog):
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent)
        self.setWindowTitle("CustomerProDialog")
        self.setFixedSize(300, 150)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Funcionalidad en reconstrucción."))
        layout.addWidget(QLabel("(Protocolo Omega)"))
        
        btn = QPushButton("Cerrar")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
        
        self.setLayout(layout)

    def showEvent(self, event):
        """Apply theme colors when dialog is shown."""
        super().showEvent(event)
        try:
            from app.utils.theme_manager import theme_manager
            c = theme_manager.get_colors()
            for btn in self.findChildren(QPushButton):
                text = btn.text().lower()
                if any(w in text for w in ['guardar', 'save', 'aceptar', 'ok', 'crear', 'agregar']):
                    btn.setStyleSheet(f"background: {c['btn_success']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
                elif any(w in text for w in ['cancelar', 'cancel', 'cerrar', 'eliminar', 'delete']):
                    btn.setStyleSheet(f"background: {c['btn_danger']}; color: white; font-weight: bold; padding: 8px; border-radius: 5px;")
        except Exception:
            pass
