from PyQt6 import QtCore, QtWidgets


class UserDialog(QtWidgets.QDialog):
    def __init__(self, core, user_id=None, parent=None):
        super().__init__(parent)
        self.core = core
        self.user_id = user_id
        self.setWindowTitle("Gestión de Usuario")
        self.setFixedSize(400, 300)
        self._build_ui()
        if self.user_id:
            self._load_data()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        form = QtWidgets.QFormLayout()
        
        self.username = QtWidgets.QLineEdit()
        form.addRow("Usuario:", self.username)
        
        self.password = QtWidgets.QLineEdit()
        self.password.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Dejar vacío para no cambiar" if self.user_id else "Contraseña")
        form.addRow("Contraseña:", self.password)
        
        self.full_name = QtWidgets.QLineEdit()
        form.addRow("Nombre Completo:", self.full_name)
        
        self.role = QtWidgets.QComboBox()
        self.role.addItems(["admin", "manager", "cashier", "encargado"])
        form.addRow("Rol:", self.role)
        
        self.is_active = QtWidgets.QCheckBox("Usuario Activo")
        self.is_active.setChecked(True)
        form.addRow("", self.is_active)
        
        layout.addLayout(form)
        
        btn_box = QtWidgets.QHBoxLayout()
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QtWidgets.QPushButton("Guardar")
        btn_save.clicked.connect(self._save)
        
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    def _load_data(self):
        user = self.core.get_user(self.user_id)
        if not user:
            return
        self.username.setText(user.get("username", ""))
        self.full_name.setText(user.get("name", ""))
        self.role.setCurrentText(user.get("role", "cashier"))
        self.is_active.setChecked(bool(user.get("is_active", 1)))
        # Password not loaded for security

    def _save(self):
        username = self.username.text().strip()
        if not username:
            QtWidgets.QMessageBox.warning(self, "Error", "El usuario es obligatorio")
            return
            
        data = {
            "username": username,
            "name": self.full_name.text().strip(),
            "role": self.role.currentText(),
            "is_active": 1 if self.is_active.isChecked() else 0
        }
        
        password = self.password.text().strip()
        if password:
            data["password"] = password
        elif not self.user_id:
            QtWidgets.QMessageBox.warning(self, "Error", "La contraseña es obligatoria para nuevos usuarios")
            return

        try:
            if self.user_id:
                self.core.update_user(self.user_id, data)
            else:
                self.core.create_user(data)
            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"No se pudo guardar: {e}")

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
