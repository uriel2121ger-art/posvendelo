"""
Supervisor Override Dialog - Autorización Elevada
Permite a un usuario de mayor jerarquía autorizar acciones restringidas
sin cambiar la sesión del cajero actual.
"""

import hashlib
import secrets  # FIX 2026-02-01: Import for constant-time comparison

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

from app.utils.theme_manager import theme_manager


class SupervisorOverrideDialog(QtWidgets.QDialog):
    """
    Diálogo de autorización que solicita credenciales de un supervisor
    para ejecutar acciones restringidas.
    
    Uso:
        dialog = SupervisorOverrideDialog(
            core=self.core,
            action_description="Cancelar Venta #123",
            required_permission="cancel_sale",
            min_role="encargado",  # encargado, manager, admin
            parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Acción autorizada, obtener el supervisor que autorizó
            supervisor = dialog.authorizing_user
            # Ejecutar la acción...
    """
    
    # Jerarquía de roles (menor a mayor)
    # Incluye ambos nombres (español e inglés) para compatibilidad
    ROLE_HIERARCHY = {
        'cashier': 1,
        'cajero': 1,
        'encargado': 2,
        'manager': 3,
        'admin': 4
    }
    
    def __init__(
        self, 
        core, 
        action_description: str,
        required_permission: str = None,
        min_role: str = "encargado",
        parent=None
    ):
        super().__init__(parent)
        self.core = core
        self.action_description = action_description
        self.required_permission = required_permission
        self.min_role = min_role.lower()
        self.authorizing_user = None
        
        self.setWindowTitle("🔐 Autorización Requerida")
        self.setMinimumWidth(400)
        self.setModal(True)
        
        self._build_ui()
        self._apply_theme()
        
        # Focus en el campo de usuario
        self.username_input.setFocus()
    
    def _apply_theme(self):
        """Aplicar colores del tema actual"""
        c = theme_manager.get_colors()
        
        self.setStyleSheet(f"background-color: {c['bg_main']}; color: {c['text_primary']};")
        self.title_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {c['btn_danger']};")
        self.subtitle_label.setStyleSheet(f"color: {c['text_secondary']}; font-size: 11px;")
        self.req_label.setStyleSheet(f"color: {c['btn_danger']}; font-weight: bold;")
        self.error_label.setStyleSheet(f"color: {c['btn_danger']}; font-weight: bold;")
        
        # Action frame con colores de warning
        self.action_frame.setStyleSheet(f"""
            QFrame {{
                background: {c.get('bg_warning', '#fff3cd')};
                border: 1px solid {c.get('border_warning', '#ffc107')};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        
        # Form frame
        self.form_frame.setStyleSheet(f"""
            QFrame {{
                background: {c['bg_card']};
                border: 1px solid {c['border']};
                border-radius: 8px;
                padding: 15px;
            }}
        """)
        
        # Inputs
        input_style = f"padding: 8px; font-size: 14px; background: {c['input_bg']}; color: {c['text_primary']}; border: 1px solid {c['border']};"
        self.username_input.setStyleSheet(input_style)
        self.password_input.setStyleSheet(input_style)
        
        self.authorize_btn.setStyleSheet(f"""
            QPushButton {{
                background: {c['btn_success']};
                color: white;
                font-weight: bold;
                padding: 10px 25px;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background: #219a52;
            }}
        """)
    
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # Icono de advertencia y título
        header = QtWidgets.QHBoxLayout()
        
        icon_label = QtWidgets.QLabel("🔒")
        icon_label.setStyleSheet("font-size: 48px;")
        header.addWidget(icon_label)
        
        title_layout = QtWidgets.QVBoxLayout()
        self.title_label = QtWidgets.QLabel("Autorización de Supervisor")
        title_layout.addWidget(self.title_label)
        
        self.subtitle_label = QtWidgets.QLabel("Esta acción requiere aprobación de un usuario autorizado")
        title_layout.addWidget(self.subtitle_label)
        
        header.addLayout(title_layout)
        header.addStretch()
        layout.addLayout(header)
        
        # Descripción de la acción
        self.action_frame = QtWidgets.QFrame()
        action_layout = QtWidgets.QVBoxLayout(self.action_frame)
        
        action_title = QtWidgets.QLabel("📋 Acción solicitada:")
        action_title.setStyleSheet("font-weight: bold;")
        action_layout.addWidget(action_title)
        
        action_desc = QtWidgets.QLabel(self.action_description)
        action_desc.setStyleSheet("font-size: 14px;")
        action_desc.setWordWrap(True)
        action_layout.addWidget(action_desc)
        
        layout.addWidget(self.action_frame)
        
        # Requisito de rol mínimo
        role_names = {
            'cashier': 'Cajero',
            'cajero': 'Cajero',
            'encargado': 'Encargado',
            'manager': 'Gerente',
            'admin': 'Administrador'
        }
        min_role_name = role_names.get(self.min_role, self.min_role.title())
        
        self.req_label = QtWidgets.QLabel(f"⚠️ Requiere nivel: {min_role_name} o superior")
        layout.addWidget(self.req_label)
        
        # Formulario de credenciales
        self.form_frame = QtWidgets.QFrame()
        form_layout = QtWidgets.QFormLayout(self.form_frame)
        form_layout.setSpacing(12)
        
        # Usuario
        self.username_input = QtWidgets.QLineEdit()
        self.username_input.setPlaceholderText("Usuario del supervisor")
        form_layout.addRow("👤 Usuario:", self.username_input)
        
        # Contraseña
        self.password_input = QtWidgets.QLineEdit()
        self.password_input.setPlaceholderText("Contraseña")
        self.password_input.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self._validate_and_accept)
        form_layout.addRow("🔑 Contraseña:", self.password_input)
        
        layout.addWidget(self.form_frame)
        
        # Mensaje de error (oculto inicialmente)
        self.error_label = QtWidgets.QLabel("")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        
        # Botones
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QtWidgets.QPushButton("❌ Cancelar")
        cancel_btn.setStyleSheet("padding: 10px 20px;")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        self.authorize_btn = QtWidgets.QPushButton("✅ Autorizar")
        self.authorize_btn.clicked.connect(self._validate_and_accept)
        btn_layout.addWidget(self.authorize_btn)
        
        layout.addLayout(btn_layout)
    
    def _validate_and_accept(self):
        """Valida las credenciales y el nivel del usuario."""
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not username or not password:
            self._show_error("Ingrese usuario y contraseña")
            return
        
        # Buscar usuario en la base de datos
        user = self._authenticate_user(username, password)
        
        if not user:
            self._show_error("Usuario o contraseña incorrectos")
            self.password_input.clear()
            self.password_input.setFocus()
            return
        
        # Verificar nivel de jerarquía
        user_role = user.get('role', 'cashier').lower()
        user_level = self.ROLE_HIERARCHY.get(user_role, 0)
        required_level = self.ROLE_HIERARCHY.get(self.min_role, 2)
        
        if user_level < required_level:
            role_names = {
                'cashier': 'Cajero',
                'cajero': 'Cajero',
                'encargado': 'Encargado',
                'manager': 'Gerente',
                'admin': 'Administrador'
            }
            self._show_error(
                f"Nivel insuficiente. Usuario '{username}' es {role_names.get(user_role, user_role)}.\n"
                f"Se requiere {role_names.get(self.min_role, self.min_role)} o superior."
            )
            return
        
        # Verificar permiso específico si se requiere
        if self.required_permission:
            has_permission = self._check_permission(user, self.required_permission)
            if not has_permission:
                self._show_error(f"El usuario no tiene el permiso: {self.required_permission}")
                return
        
        # ¡Autorización exitosa!
        self.authorizing_user = user
        
        # Registrar en auditoría
        self._log_authorization(user)
        
        self.accept()
    
    def _authenticate_user(self, username: str, password: str) -> dict:
        """Autentica al usuario contra la base de datos."""
        try:
            import bcrypt

            # Buscar usuario en tabla users
            result = self.core.db.execute_query("""
                SELECT id, username, password_hash, role
                FROM users 
                WHERE username = %s
            """, (username,))
            
            if not result or len(result) == 0:
                # SECURITY: Check local admin config (NO hardcoded defaults)
                # If admin credentials not explicitly configured, authentication MUST fail
                cfg = self.core.read_local_config()
                admin_user = cfg.get("admin_user")
                admin_pass_hash = cfg.get("admin_pass_hash")  # Must be hashed, not plaintext

                # SECURITY: Require BOTH username AND hashed password to be configured
                if not admin_user or not admin_pass_hash:
                    import logging
                    logging.getLogger(__name__).warning(
                        "Local admin not configured. Set admin_user and admin_pass_hash in config."
                    )
                    return None

                # Verify password against stored hash
                import hashlib
                password_hash = hashlib.sha256(password.encode()).hexdigest()

                # FIX 2026-02-01: Use constant-time comparison to prevent timing attacks
                if username == admin_user and secrets.compare_digest(password_hash, admin_pass_hash):
                    return {
                        'id': 0,
                        'username': username,
                        'role': 'admin',
                        'first_name': 'Admin',
                        'last_name': 'Sistema',
                        'full_name': 'Admin Sistema'
                    }
                return None
            
            row = result[0]
            stored_hash = row['password_hash']
            
            # Verificar contraseña (bcrypt o SHA256)
            auth_success = False
            
            if stored_hash:
                # Check bcrypt
                if stored_hash.startswith("$2b$"):
                    try:
                        if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
                            auth_success = True
                    except Exception:
                        pass
                
                # FIX 2026-02-01: Use constant-time comparison for SHA256 hash check
                if not auth_success:
                    import hashlib
                    sha_hash = hashlib.sha256(password.encode()).hexdigest()
                    if secrets.compare_digest(stored_hash, sha_hash):
                        auth_success = True

                # FIX 2026-02-01: REMOVED plaintext password fallback - security vulnerability
            
            if auth_success:
                return {
                    'id': row['id'],
                    'username': row['username'],
                    'role': row['role'],
                    'first_name': row['username'],  # Users table may not have first_name
                    'last_name': '',
                    'full_name': row['username']
                }
            
            return None
            
        except Exception as e:
            print(f"Error authenticating supervisor: {e}")
            return None
    
    def _check_permission(self, user: dict, permission: str) -> bool:
        """Verifica si el usuario tiene un permiso específico."""
        try:
            # Admins tienen todos los permisos
            if user.get('role', '').lower() == 'admin':
                return True
            
            # Verificar en el sistema de permisos
            if hasattr(self.core, 'permission_engine'):
                return self.core.permission_engine.has_permission(
                    user['id'], 
                    permission
                )
            
            # Si no hay sistema de permisos, verificar por rol
            # Managers y Encargados tienen permisos elevados
            role = user.get('role', '').lower()
            return role in ['admin', 'manager', 'encargado']
            
        except Exception:
            return False
    
    def _log_authorization(self, user: dict):
        """Registra la autorización en el log de auditoría."""
        try:
            if hasattr(self.core, 'audit'):
                from app.core import STATE
                self.core.audit.log(
                    action='SUPERVISOR_OVERRIDE',
                    entity_type='authorization',
                    entity_id=0,
                    details={
                        'action_authorized': self.action_description,
                        'authorizing_user_id': user['id'],
                        'authorizing_user': user['username'],
                        'authorizing_role': user['role'],
                        'required_permission': self.required_permission,
                        'min_role_required': self.min_role,
                        'current_session_user_id': STATE.user_id if hasattr(STATE, 'user_id') else None
                    }
                )
        except Exception as e:
            print(f"Error logging authorization: {e}")
    
    def _show_error(self, message: str):
        """Muestra un mensaje de error."""
        self.error_label.setText(f"❌ {message}")
        self.error_label.show()

def require_supervisor_override(
    core,
    action_description: str,
    required_permission: str = None,
    min_role: str = "encargado",
    parent=None
) -> tuple:
    """
    Función helper para solicitar autorización de supervisor.
    
    Returns:
        (authorized: bool, authorizing_user: dict or None)
    
    Uso:
        authorized, supervisor = require_supervisor_override(
            core=self.core,
            action_description="Cancelar Venta #123 ($500.00)",
            min_role="encargado",
            parent=self
        )
        if authorized:
            # Ejecutar la acción
            self._do_cancel_sale(sale_id)
            print(f"Autorizado por: {supervisor['full_name']}")
    """
    dialog = SupervisorOverrideDialog(
        core=core,
        action_description=action_description,
        required_permission=required_permission,
        min_role=min_role,
        parent=parent
    )
    
    if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
        return True, dialog.authorizing_user
    
    return False, None
