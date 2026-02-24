import json
import logging
import secrets  # SECURITY: For constant-time comparison
import time

logger = logging.getLogger(__name__)

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
import bcrypt

from app.core import APP_NAME, STATE
from app.utils.path_utils import get_debug_log_path_str, agent_log_enabled
from app.utils.theme_manager import theme_manager


class LoginDialog(QDialog):
    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.setWindowTitle(f"Iniciar Sesión - {APP_NAME}")
        self.setFixedSize(400, 300)
        
        # Get theme colors
        colors = theme_manager.get_colors()
        background_color = colors.get("background", "white")
        accent_color = colors.get("accent", "#3498db")
        btn_primary = colors.get("btn_primary", "#2980b9")
        
        self.setStyleSheet(f"""
            QDialog {{ background-color: {background_color}; }}
            QLabel {{ color: #2c3e50; }}
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Título
        lbl_title = QLabel("Bienvenido")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(lbl_title)
        
        layout.addSpacing(10)
        
        # Usuario Dropdown
        layout.addWidget(QLabel("Usuario:"))
        self.user_combo = QComboBox()
        self.user_combo.setEditable(True) # Permitir escribir para admin oculto
        self.user_combo.setPlaceholderText("Seleccione o escriba usuario")
        self.user_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: white;
                color: #2c3e50;
                padding: 8px;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                font-size: 14px;
                min-height: 20px;
            }}
            QComboBox:focus {{
                border-color: {accent_color};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
            }}
            QComboBox QAbstractItemView {{
                background-color: white;
                color: #2c3e50;
                selection-background-color: {accent_color};
                selection-color: white;
            }}
        """)
        self._populate_users()
        layout.addWidget(self.user_combo)
        
        # Password
        layout.addWidget(QLabel("Contraseña:"))
        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Contraseña")
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: white;
                color: #2c3e50;
                padding: 8px;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                font-size: 14px;
                min-height: 20px;
            }}
            QLineEdit:focus {{ 
                border-color: {accent_color}; 
            }}
            QLineEdit::placeholder {{
                color: #95a5a6;
                font-style: italic;
            }}
        """)
        self.pass_input.returnPressed.connect(self.do_login)
        layout.addWidget(self.pass_input)
        
        layout.addSpacing(10)
        
        # Botón Entrar
        btn_login = QPushButton("Iniciar Sesión")
        btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_login.setStyleSheet(f"""
            QPushButton {{
                background-color: #3498db;
                color: white;
                padding: 12px;
                border: none;
                border-radius: 5px;
                font-size: 16px;
                font-weight: bold;
                min-height: 20px;
            }}
            QPushButton:hover {{
                background-color: #2980b9;
            }}
            QPushButton:pressed {{
                background-color: #1f6ca1;
            }}
        """)
        btn_login.clicked.connect(self.do_login)
        layout.addWidget(btn_login)
        
        layout.addStretch()
        self.setLayout(layout)
        
        # Focus logic
        if self.user_combo.count() > 0:
            self.pass_input.setFocus()
        else:
            self.user_combo.setFocus()

    def _populate_users(self):
        try:
            users = self.core.list_users()
            self.user_combo.clear()
            # Agregar usuarios NO admin primero
            for u in users:
                if u.get("role") != "admin":
                    self.user_combo.addItem(u.get("username"), u)
            
            # Admin no se agrega a la lista visible, el usuario debe escribirlo
            # si desea loguearse como tal, dado que el combo es editable.
        except Exception as e:
            print(f"Error loading users: {e}")

    def do_login(self):
        username = self.user_combo.currentText().strip()
        password = self.pass_input.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "Datos incompletos", "Ingrese usuario y contraseña")
            return
            
        # 1. Verificar credenciales de config (generadas durante instalación)
        cfg = self.core.read_local_config()
        admin_user = cfg.get("admin_user", "admin")
        admin_pass_hash = cfg.get("admin_pass_hash")  # Hash SHA256 - NO texto plano
        
        # Validar contra DB
        user_found = None
        try:
            users = self.core.list_users()
            # #region agent log
            if agent_log_enabled():
                try:
                    log_path = get_debug_log_path_str()
                    if log_path:
                        try:
                            with open(log_path, "a", encoding="utf-8") as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"LOGIN_B","location":"login_dialog.py:do_login","message":"Users retrieved from DB","data":{"username":username,"users_count":len(users) if users else 0,"usernames":[u.get("username") for u in users] if users else []},"timestamp":int(time.time()*1000)})+"\n")
                                f.flush()
                        except Exception as log_e:
                            logging.debug(f"Could not write debug log: {log_e}")
                except Exception as e:
                    logging.debug(f"Debug logging setup failed: {e}")
            # #endregion
            for u in users:
                if u.get("username") == username:
                    user_found = u
                    break
        except Exception as list_e:
            # #region agent log
            if agent_log_enabled():
                try:
                    log_path = get_debug_log_path_str()
                    if log_path:
                        try:
                            with open(log_path, "a", encoding="utf-8") as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"LOGIN_B","location":"login_dialog.py:do_login","message":"Exception listing users","data":{"username":username,"error":str(list_e),"error_type":type(list_e).__name__},"timestamp":int(time.time()*1000)})+"\n")
                                f.flush()
                        except Exception as log_e:
                            logging.debug(f"Could not write debug log: {log_e}")
                except Exception as e:
                    logging.debug(f"Debug logging setup failed: {e}")
            # #endregion
            pass  # No hay usuarios en DB
        
        # Lógica de autenticación
        auth_success = False
        is_admin = False
        user_id = 0
        role = "cashier"
        
        if user_found:
            # Autenticación: soporta bcrypt, SHA256, o texto plano (legacy)
            stored_pass = user_found.get("password_hash")
            
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    log_path = get_debug_log_path_str()
                    if log_path:
                        try:
                            # SECURITY: Do NOT log password hashes or previews - removed stored_pass_preview
                            with open(log_path, "a", encoding="utf-8") as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"LOGIN_B","location":"login_dialog.py:do_login","message":"User found, checking password","data":{"username":username,"stored_pass_type":"bcrypt" if stored_pass and stored_pass.startswith("$2b$") else "SHA256" if stored_pass and len(stored_pass) == 64 else "plain" if stored_pass else "None"},"timestamp":int(time.time()*1000)})+"\n")
                                f.flush()
                        except Exception as log_e:
                            logging.debug(f"Could not write debug log: {log_e}")
                except Exception as e:
                    logging.debug(f"Debug logging setup failed: {e}")
            # #endregion
            
            # Check if stored_pass is a bcrypt hash
            try:
                import hashlib
                if stored_pass and stored_pass.startswith("$2b$"):
                    # Bcrypt hash
                    # #region agent log
                    if agent_log_enabled():
                        try:
                            from app.utils.path_utils import get_debug_log_path_str
                            log_path = get_debug_log_path_str()
                            if log_path:
                                with open(log_path, "a", encoding="utf-8") as f:
                                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"LOGIN_B","location":"login_dialog.py:do_login","message":"Trying bcrypt verification","data":{"username":username},"timestamp":int(time.time()*1000)})+"\n")
                                    f.flush()
                        except Exception as log_e:
                            logging.debug(f"Could not write debug log: {log_e}")
                    # #endregion
                    if bcrypt.checkpw(password.encode('utf-8'), stored_pass.encode('utf-8')):
                        auth_success = True
                elif stored_pass and len(stored_pass) == 64:
                    # SHA256 hash (64 hex characters) - used by Wizard
                    password_sha256 = hashlib.sha256(password.encode()).hexdigest()
                    # #region agent log
                    if agent_log_enabled():
                        try:
                            from app.utils.path_utils import get_debug_log_path_str
                            log_path = get_debug_log_path_str()
                            if log_path:
                                # SECURITY: Do NOT log password hashes - removed stored_hash and computed_hash
                                with open(log_path, "a", encoding="utf-8") as f:
                                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"LOGIN_B","location":"login_dialog.py:do_login","message":"Trying SHA256 verification","data":{"username":username},"timestamp":int(time.time()*1000)})+"\n")
                                    f.flush()
                        except Exception as log_e:
                            logging.debug(f"Could not write debug log: {log_e}")
                    # #endregion
                    # SECURITY: Use constant-time comparison to prevent timing attacks
                    if secrets.compare_digest(stored_pass, password_sha256):
                        auth_success = True
            except Exception as e:
                logging.error(f"Auth Error: {e}")
                # #region agent log
                if agent_log_enabled():
                    try:
                        from app.utils.path_utils import get_debug_log_path_str
                        log_path = get_debug_log_path_str()
                        if log_path:
                            with open(log_path, "a", encoding="utf-8") as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"LOGIN_B","location":"login_dialog.py:do_login","message":"Auth exception occurred","data":{"username":username,"error":str(e),"error_type":type(e).__name__},"timestamp":int(time.time()*1000)})+"\n")
                                f.flush()
                    except Exception as log_e:
                        logging.debug(f"Could not write debug log: {log_e}")
                # #endregion
            
            # #region agent log
            if agent_log_enabled():
                try:
                    log_path = get_debug_log_path_str()
                    if log_path:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"LOGIN_B","location":"login_dialog.py:do_login","message":"Auth result","data":{"username":username,"auth_success":auth_success},"timestamp":int(time.time()*1000)})+"\n")
                            f.flush()
                except Exception as e:
                    logging.debug(f"Debug logging setup failed: {e}")
            # #endregion

            if auth_success:
                user_id = user_found.get("id")
                role = user_found.get("role")
                is_admin = (role == "admin")
                
                # AUDIT LOG - Successful login
                try:
                    self.core.audit.log_login(username, success=True, user_id=user_id)
                except Exception as e:
                    logger.debug("Logging successful user login to audit: %s", e)
        else:
            # Fallback: admin de config.json (instalación limpia sin usuarios)
            if username == admin_user and admin_pass_hash:
                # Verificar contra hash de config
                import hashlib
                input_hash = hashlib.sha256(password.encode()).hexdigest()
                # FIX 2026-02-01: Use constant-time comparison to prevent timing attacks
                if secrets.compare_digest(input_hash, admin_pass_hash):
                    auth_success = True
                    is_admin = True
                    role = "admin"
                    
                    # Crear el usuario admin en la DB si no existe
                    try:
                        created_id = self.core.create_user(username, password, "admin")
                        user_id = created_id if created_id else 1
                        logging.info(f"Admin user created/found with ID: {user_id}")
                    except Exception as e:
                        # Si falla la creación (ej: ya existe), buscar el ID
                        logging.warning(f"Could not create admin user: {e}")
                        try:
                            users = self.core.list_users()
                            for u in users:
                                if u.get("username") == username:
                                    user_id = u.get("id", 1)
                                    break
                            else:
                                user_id = 1  # Fallback mínimo
                        except Exception as e:
                            logger.debug("Fetching user ID after admin creation failed: %s", e)
                            user_id = 1
                    
                    # AUDIT LOG - Admin login
                    try:
                        self.core.audit.log_login(username, success=True, user_id=user_id)
                    except Exception as e:
                        logger.debug("Logging admin login to audit: %s", e)
        
        if auth_success:
            STATE.user_id = user_id
            STATE.username = username
            STATE.is_admin = is_admin
            STATE.role = role
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Credenciales incorrectas")

