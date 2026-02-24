#!/usr/bin/env python3
"""
Welcome Wizard - Initial setup wizard for TITAN POS.

Extracted from app/main.py for better code organization.
"""
import logging
import re
import secrets
import shlex

from PyQt6 import QtWidgets

from app.core import POSCore
from app.utils.path_utils import agent_log_enabled
from app.utils.theme_manager import theme_manager

logger = logging.getLogger(__name__)


def _escape_pg_identifier(identifier: str) -> str:
    """Escape a PostgreSQL identifier to prevent SQL injection.

    Args:
        identifier: The PostgreSQL identifier (username, database name, etc.)

    Returns:
        The escaped identifier safe for use in SQL statements.

    Raises:
        ValueError: If the identifier contains invalid characters.
    """
    # Only allow alphanumeric characters and underscores
    # Must start with a letter or underscore
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier):
        raise ValueError(f"Invalid PostgreSQL identifier: {identifier}")
    # Remove any existing quotes and escape internal quotes (defensive)
    clean = identifier.replace('"', '""')
    return clean

class WelcomeWizard(QtWidgets.QWizard):
    """Complete setup wizard with MultiCaja configuration."""

    def __init__(self, core: POSCore):
        super().__init__()
        self.core = core
        self.setWindowTitle("🚀 Configuración Inicial - TITAN POS")
        self.setMinimumSize(700, 500)
        
        # Add pages in order
        self.addPage(self._intro_page())
        self.addPage(self._database_page())  # PostgreSQL configuration FIRST
        self.addPage(self._business_page())
        self.addPage(self._multicaja_page())
        self.addPage(self._printer_page())
        self.addPage(self._user_page())
        self.addPage(self._finish_page())
        
        self.setWizardStyle(QtWidgets.QWizard.WizardStyle.ModernStyle)
        self.setOption(QtWidgets.QWizard.WizardOption.HaveHelpButton, False)
        self._apply_theme()
    
    def showEvent(self, event):
        """Apply theme when shown."""
        super().showEvent(event)
        self._apply_theme()
    
    def _apply_theme(self):
        """Apply current theme colors."""
        try:
            c = theme_manager.get_colors()
            self.setStyleSheet(f"""
                QWizard {{
                    background: {c['bg_secondary']};
                }}
                QWizardPage {{
                    background: {c['bg_primary']};
                }}
                QLabel {{
                    color: {c['text_primary']};
                }}
                QLineEdit, QTextEdit, QComboBox, QSpinBox {{
                    background: {c['bg_secondary']};
                    color: {c['text_primary']};
                    border: 1px solid {c['border']};
                    padding: 8px;
                    border-radius: 4px;
                }}
                QPushButton {{
                    background: {c['btn_primary']};
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 5px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {c['btn_success']};
                }}
                QCheckBox, QRadioButton {{
                    color: {c['text_primary']};
                }}
                QGroupBox {{
                    color: {c['text_primary']};
                    border: 1px solid {c['border']};
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 10px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }}
            """)
            
            # Update summary label if it exists
            if hasattr(self, 'summary_label'):
                self.summary_label.setStyleSheet(f"""
                    padding: 20px;
                    background: {c['bg_card']};
                    color: {c['text_primary']};
                    border-radius: 5px;
                    border: 1px solid {c['border']};
                """)
        except Exception:
            pass

    def _intro_page(self) -> QtWidgets.QWizardPage:
        """Welcome page."""
        page = QtWidgets.QWizardPage()
        page.setTitle("¡Bienvenido a TITAN POS!")
        page.setSubTitle("Este asistente te ayudará a configurar el sistema en minutos.")
        
        layout = QtWidgets.QVBoxLayout(page)
        layout.addSpacing(20)
        
        label = QtWidgets.QLabel(
            "TITAN POS es un sistema completo de punto de venta con:\n\n"
            "✅ Gestión de inventario\n"
            "✅ Control de turnos y caja\n"
            "✅ Sincronización MultiCaja (múltiples terminales)\n"
            "✅ Facturación electrónica\n"
            "✅ Reportes y análisis\n\n"
            "Presiona 'Siguiente' para comenzar la configuración."
        )
        label.setStyleSheet("font-size: 13px; padding: 20px;")
        layout.addWidget(label)
        layout.addStretch()
        
        return page

    def _database_page(self) -> QtWidgets.QWizardPage:
        """PostgreSQL database configuration page."""
        page = QtWidgets.QWizardPage()
        page.setTitle("🗄️ Configuración de Base de Datos")
        page.setSubTitle("TITAN POS requiere PostgreSQL para funcionar")
        
        layout = QtWidgets.QVBoxLayout(page)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Info label
        info_label = QtWidgets.QLabel(
            "⚠️ PostgreSQL es REQUERIDO.\n\n"
            "Si no lo tienes instalado:\n"
            "   sudo apt install postgresql postgresql-contrib\n"
            "   sudo systemctl start postgresql\n\n"
            "✨ AUTOMÁTICO: El sistema creará el usuario y base de datos\n"
            "   automáticamente cuando hagas clic en 'Probar Conexión' o 'Finalizar'.\n\n"
            "Solo ingresa los datos que deseas usar:\n"
            "   • Usuario: nombre del usuario (ej: titan_user)\n"
            "   • Contraseña: contraseña para el usuario\n"
            "   • Base de datos: nombre de la BD (ej: titan_pos)\n\n"
            "💡 Nota: Se te pedirá la contraseña de sudo para crear el usuario.\n\n"
            "🔧 Si ya tienes database.json pero la contraseña no coincide:\n"
            "   Ejecuta en terminal: bash scripts/sync_postgresql_password.sh"
        )
        info_label.setStyleSheet("color: #7f8c8d; font-size: 11px; padding: 10px; background: #f8f9fa; border-radius: 5px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Botón para ejecutar script de sincronización (solo si existe database.json)
        existing_config = self._load_existing_database_config()
        if existing_config:
            sync_btn = QtWidgets.QPushButton("🔐 Sincronizar Contraseña de PostgreSQL")
            sync_btn.setToolTip("Ejecuta el script para sincronizar la contraseña de database.json con PostgreSQL")
            sync_btn.clicked.connect(self._run_sync_password_script)
            sync_btn.setStyleSheet("padding: 8px; background: #17a2b8; color: white; border-radius: 4px;")
            layout.addWidget(sync_btn)
        
        # Form layout
        form = QtWidgets.QFormLayout()
        form.setSpacing(12)
        
        # CRITICAL: Cargar valores existentes de database.json si existe
        # (Se carga antes para el botón de sincronización)
        
        self.db_host = QtWidgets.QLineEdit()
        self.db_host.setText(existing_config.get("host", "localhost"))
        self.db_host.setPlaceholderText("localhost")
        form.addRow("Host:", self.db_host)
        
        self.db_port = QtWidgets.QSpinBox()
        self.db_port.setRange(1, 65535)
        self.db_port.setValue(existing_config.get("port", 5432))
        form.addRow("Puerto:", self.db_port)
        
        self.db_name = QtWidgets.QLineEdit()
        self.db_name.setText(existing_config.get("database", "titan_pos"))
        self.db_name.setPlaceholderText("titan_pos")
        form.addRow("Base de Datos:", self.db_name)
        
        self.db_user = QtWidgets.QLineEdit()
        self.db_user.setText(existing_config.get("user", "titan_user"))
        self.db_user.setPlaceholderText("titan_user")
        form.addRow("Usuario:", self.db_user)
        
        self.db_password = QtWidgets.QLineEdit()
        self.db_password.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.db_password.setPlaceholderText("Ingresa la contraseña")
        # NO cargar password existente por seguridad
        form.addRow("Contraseña:", self.db_password)
        
        layout.addLayout(form)
        
        # Test connection button
        test_btn = QtWidgets.QPushButton("🔍 Probar Conexión")
        test_btn.clicked.connect(self._test_database_connection)
        layout.addWidget(test_btn)
        
        # Status label
        self.db_status_label = QtWidgets.QLabel("")
        self.db_status_label.setStyleSheet("padding: 10px; border-radius: 5px;")
        layout.addWidget(self.db_status_label)
        
        layout.addStretch()
        
        return page

    def _run_sync_password_script(self) -> None:
        """Ejecuta el script de sincronización de contraseña."""
        import subprocess
        import os
        from pathlib import Path
        from app.utils.path_utils import get_workspace_root, agent_log_enabled
        
        workspace_root = get_workspace_root()
        script_path = workspace_root / "scripts" / "sync_postgresql_password.sh"
        
        if not script_path.exists():
            QtWidgets.QMessageBox.warning(
                self,
                "Script no encontrado",
                f"El script no se encontró en:\n{script_path}\n\n"
                "Ejecuta manualmente en la terminal:\n"
                "bash scripts/sync_postgresql_password.sh"
            )
            return
        
        # Verificar que sea ejecutable
        if not os.access(script_path, os.X_OK):
            os.chmod(script_path, 0o755)
        
        # Mostrar diálogo informativo
        reply = QtWidgets.QMessageBox.question(
            self,
            "Sincronizar Contraseña",
            "Este script sincronizará la contraseña de PostgreSQL con la de database.json.\n\n"
            "Se abrirá una terminal donde deberás ingresar tu contraseña de sudo.\n\n"
            "¿Deseas continuar?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            try:
                # Intentar ejecutar en terminal
                # En Linux, intentar usar diferentes terminales
                terminals = ['gnome-terminal', 'xterm', 'konsole', 'terminator']
                terminal_found = False
                
                for term in terminals:
                    try:
                        result = subprocess.run(['which', term], capture_output=True, timeout=2)
                        if result.returncode == 0:
                            # SECURITY: Use shlex.quote() to properly escape the path
                            # Prevents command injection if workspace_root contains special chars
                            safe_script_path = shlex.quote(str(script_path))
                            subprocess.Popen([term, '-e', f'bash {safe_script_path}'], cwd=str(workspace_root))
                            terminal_found = True
                            break
                    except Exception:
                        continue
                
                if not terminal_found:
                    # Si no hay terminal gráfica, mostrar instrucciones
                    QtWidgets.QMessageBox.information(
                        self,
                        "Ejecutar en Terminal",
                        f"Abre una terminal y ejecuta:\n\n"
                        f"cd {workspace_root}\n"
                        f"bash scripts/sync_postgresql_password.sh\n\n"
                        f"Luego vuelve aquí y haz clic en 'Probar Conexión'."
                    )
                else:
                    QtWidgets.QMessageBox.information(
                        self,
                        "Script Ejecutándose",
                        "El script se está ejecutando en una terminal.\n\n"
                        "Después de que termine, haz clic en 'Probar Conexión' aquí."
                    )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Error",
                    f"No se pudo abrir la terminal:\n{e}\n\n"
                    "Ejecuta manualmente:\n"
                    f"bash {script_path}"
                )

    def _load_existing_database_config(self) -> dict:
        """Carga configuración existente de database.json si existe."""
        import json
        from pathlib import Path
        from app.utils.path_utils import get_workspace_root
        
        try:
            workspace_root = get_workspace_root()
            config_path = workspace_root / "data" / "config" / "database.json"
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Extraer valores de postgresql si existe
                    if "postgresql" in config:
                        return config["postgresql"]
                    # Si no hay postgresql, retornar valores por defecto
        except Exception as e:
            logger.debug(f"Could not load existing database config: {e}")
        
        return {}

    def _create_postgresql_user_and_database(self, user: str, password: str, database: str) -> tuple[bool, str]:
        """
        Intenta crear automáticamente el usuario y base de datos de PostgreSQL.
        
        Returns:
            (success: bool, message: str)
        """
        import subprocess
        import json
        import time
        
        # #region agent log
        if agent_log_enabled():
            try:
                from app.utils.path_utils import get_debug_log_path_str
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CREATE_USER_START","location":"welcome_wizard.py:_create_postgresql_user_and_database","message":"Starting user/database creation","data":{"user":user,"database":database,"password_length":len(password)},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                 logger.debug("Writing debug log: %s", e)
        # #endregion
        
        try:
            # CRITICAL: Escapar comillas simples en la contraseña para SQL
            password_escaped = password.replace("'", "''")
            
            # #region agent log
            if agent_log_enabled():
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"PASSWORD_ESCAPE","location":"welcome_wizard.py:_create_postgresql_user_and_database","message":"Password escaped","data":{"original_length":len(password),"escaped_length":len(password_escaped),"has_single_quote":"'" in password},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            
            # Intentar crear usuario (ignorar si ya existe)
            # CRITICAL: Usar -v ON_ERROR_STOP=1 para detectar errores correctamente
            # Escape user and database identifiers to prevent SQL injection
            # FIX 2026-02-02: Definir ambas variables al inicio para evitar UnboundLocalError en timeout
            safe_user = _escape_pg_identifier(user)
            safe_database = _escape_pg_identifier(database)
            create_user_cmd = [
                "sudo", "-u", "postgres", "psql",
                "-v", "ON_ERROR_STOP=1",
                "-c", f'CREATE USER "{safe_user}" WITH PASSWORD \'{password_escaped}\';'
            ]
            
            # #region agent log
            if agent_log_enabled():
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CREATE_USER_CMD","location":"welcome_wizard.py:_create_postgresql_user_and_database","message":"Executing CREATE USER command","data":{"cmd":"CREATE USER","user":user},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            
            result = subprocess.run(
                create_user_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # #region agent log
            if agent_log_enabled():
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CREATE_USER_RESULT","location":"welcome_wizard.py:_create_postgresql_user_and_database","message":"CREATE USER result","data":{"returncode":result.returncode,"stdout":result.stdout[:200],"stderr":result.stderr[:200],"already_exists":"already exists" in result.stderr.lower()},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            
            # Si el usuario ya existe, actualizar su contraseña
            if result.returncode != 0 and "already exists" in result.stderr.lower():
                logger.info(f"User {user} already exists, updating password...")
                
                # #region agent log
                if agent_log_enabled():
                    try:
                        from app.utils.path_utils import get_debug_log_path_str
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"ALTER_USER_PASSWORD","location":"welcome_wizard.py:_create_postgresql_user_and_database","message":"User exists, updating password","data":{"user":user},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                # #endregion
                
                alter_user_cmd = [
                    "sudo", "-u", "postgres", "psql",
                    "-v", "ON_ERROR_STOP=1",
                    "-c", f'ALTER USER "{safe_user}" WITH PASSWORD \'{password_escaped}\';'
                ]
                result = subprocess.run(
                    alter_user_cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                # #region agent log
                if agent_log_enabled():
                    try:
                        from app.utils.path_utils import get_debug_log_path_str
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"ALTER_USER_RESULT","location":"welcome_wizard.py:_create_postgresql_user_and_database","message":"ALTER USER result","data":{"returncode":result.returncode,"stdout":result.stdout[:200],"stderr":result.stderr[:200]},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                # #endregion
                
                if result.returncode != 0:
                    logger.warning(f"Could not update password for existing user: {result.stderr}")
            elif result.returncode != 0:
                logger.warning(f"Could not create user: {result.stderr}")
            
            # Intentar crear base de datos (ignorar si ya existe)
            # Escape database identifier to prevent SQL injection
            safe_database = _escape_pg_identifier(database)
            create_db_cmd = [
                "sudo", "-u", "postgres", "psql",
                "-c", f'CREATE DATABASE "{safe_database}" OWNER "{safe_user}";'
            ]
            result = subprocess.run(
                create_db_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            # Si la BD ya existe, asegurar que el usuario sea el propietario
            if result.returncode != 0 and "already exists" in result.stderr.lower():
                logger.info(f"Database {database} already exists, ensuring ownership...")
                alter_db_cmd = [
                    "sudo", "-u", "postgres", "psql",
                    "-c", f'ALTER DATABASE "{safe_database}" OWNER TO "{safe_user}";'
                ]
                result = subprocess.run(
                    alter_db_cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode != 0:
                    logger.warning(f"Could not update database owner: {result.stderr}")
            elif result.returncode != 0:
                logger.warning(f"Could not create database: {result.stderr}")
            
            # Otorgar permisos en la base de datos
            grant_db_cmd = [
                "sudo", "-u", "postgres", "psql",
                "-c", f'GRANT ALL PRIVILEGES ON DATABASE "{safe_database}" TO "{safe_user}";'
            ]
            result = subprocess.run(
                grant_db_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # CRITICAL: Otorgar permisos en el schema public (requerido para crear tablas)
            # Esto debe ejecutarse conectándose a la base de datos específica
            grant_schema_cmd = [
                "sudo", "-u", "postgres", "psql",
                "-d", safe_database,  # Conectarse a la base de datos específica
                "-c", f'GRANT CREATE ON SCHEMA public TO "{safe_user}";'
            ]
            result = subprocess.run(
                grant_schema_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Otorgar permisos por defecto en el schema public
            grant_default_cmd = [
                "sudo", "-u", "postgres", "psql",
                "-d", safe_database,
                "-c", f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO "{safe_user}";'
            ]
            result = subprocess.run(
                grant_default_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Otorgar permisos por defecto para secuencias
            grant_seq_cmd = [
                "sudo", "-u", "postgres", "psql",
                "-d", safe_database,
                "-c", f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO "{safe_user}";'
            ]
            result = subprocess.run(
                grant_seq_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Si la base de datos ya existía, asegurar que el usuario sea propietario del schema public
            alter_schema_cmd = [
                "sudo", "-u", "postgres", "psql",
                "-d", safe_database,
                "-c", f'ALTER SCHEMA public OWNER TO "{safe_user}";'
            ]
            result = subprocess.run(
                alter_schema_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # CRITICAL: Cambiar propietario de todas las tablas existentes al usuario
            # Esto es necesario si las tablas fueron creadas por otro usuario (ej: postgres)
            change_tables_owner_cmd = [
                "sudo", "-u", "postgres", "psql",
                "-d", safe_database,
                "-c", f"""
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
        EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) || ' OWNER TO "{safe_user}"';
    END LOOP;
END $$;
"""
            ]
            result = subprocess.run(
                change_tables_owner_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # CRITICAL: Cambiar propietario de todas las secuencias existentes al usuario
            change_sequences_owner_cmd = [
                "sudo", "-u", "postgres", "psql",
                "-d", safe_database,
                "-c", f"""
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public') LOOP
        EXECUTE 'ALTER SEQUENCE public.' || quote_ident(r.sequence_name) || ' OWNER TO "{safe_user}"';
    END LOOP;
END $$;
"""
            ]
            result = subprocess.run(
                change_sequences_owner_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Otorgar permisos en tablas existentes
            grant_existing_tables_cmd = [
                "sudo", "-u", "postgres", "psql",
                "-d", safe_database,
                "-c", f'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "{safe_user}";'
            ]
            result = subprocess.run(
                grant_existing_tables_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Otorgar permisos en secuencias existentes
            grant_existing_sequences_cmd = [
                "sudo", "-u", "postgres", "psql",
                "-d", safe_database,
                "-c", f'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "{safe_user}";'
            ]
            result = subprocess.run(
                grant_existing_sequences_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # #region agent log
            if agent_log_enabled():
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"PERMISSIONS_COMPLETE","location":"welcome_wizard.py:_create_postgresql_user_and_database","message":"All permissions granted","data":{"final_returncode":result.returncode},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            
            # CRITICAL: Esperar un momento para que PostgreSQL propague los cambios de contraseña
            # Esto es necesario porque PostgreSQL puede cachear credenciales
            # También forzar cierre de conexiones existentes del usuario
            import time
            time.sleep(1.0)  # 1 segundo para asegurar propagación
            
            # CRITICAL: Forzar cierre de conexiones existentes del usuario para que use la nueva contraseña
            try:
                # SECURITY: Use -v parameter to pass user safely and quote_literal() for SQL value
                terminate_conns_cmd = [
                    "sudo", "-u", "postgres", "psql",
                    "-d", "postgres",  # Conectarse a la BD por defecto
                    "-v", f"target_user={safe_user}",
                    "-c", "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = :'target_user' AND pid <> pg_backend_pid();"
                ]
                subprocess.run(
                    terminate_conns_cmd,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                # #region agent log
                if agent_log_enabled():
                    try:
                        from app.utils.path_utils import get_debug_log_path_str
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TERMINATE_CONNECTIONS","location":"welcome_wizard.py:_create_postgresql_user_and_database","message":"Terminated existing connections for user","data":{"user":user},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                # #endregion
            except Exception as e:
                # No es crítico si falla, solo loguear
                logger.debug(f"Could not terminate existing connections: {e}")
            
            # #region agent log
            if agent_log_enabled():
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"PASSWORD_PROPAGATION","location":"welcome_wizard.py:_create_postgresql_user_and_database","message":"Waiting for password propagation","data":{},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            
            if result.returncode == 0:
                return True, "Usuario y base de datos creados automáticamente con permisos completos"
            else:
                # Intentar continuar de todas formas (puede que ya existan)
                return True, "Configuración verificada (usuario/BD pueden ya existir)"
                
        except subprocess.TimeoutExpired:
            # #region agent log
            if agent_log_enabled():
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TIMEOUT_ERROR","location":"welcome_wizard.py:_create_postgresql_user_and_database","message":"Timeout creating user/database","data":{},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            return False, f"Timeout: sudo requiere contraseña interactiva. Ejecuta manualmente:\n\nbash scripts/setup_postgresql_user.sh\n\nO ejecuta estos comandos:\nsudo -u postgres psql -c \"CREATE USER \\\"{safe_user}\\\" WITH PASSWORD '{password}';\"\nsudo -u postgres psql -c \"CREATE DATABASE \\\"{safe_database}\\\" OWNER \\\"{safe_user}\\\";\"\nsudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE \\\"{safe_database}\\\" TO \\\"{safe_user}\\\";\""
        except FileNotFoundError:
            # #region agent log
            if agent_log_enabled():
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"FILE_NOT_FOUND","location":"welcome_wizard.py:_create_postgresql_user_and_database","message":"PostgreSQL or sudo not found","data":{},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            return False, "PostgreSQL no está instalado o 'sudo' no está disponible"
        except Exception as e:
            # #region agent log
            if agent_log_enabled():
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"EXCEPTION_ERROR","location":"welcome_wizard.py:_create_postgresql_user_and_database","message":"Exception creating user/database","data":{"error":str(e)},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            logger.error(f"Error creating PostgreSQL user/database: {e}")
            return False, f"Error: {str(e)}"

    def _test_database_connection(self) -> None:
        """Test PostgreSQL connection and create database.json if successful."""
        import json
        from pathlib import Path
        from app.utils.path_utils import get_workspace_root
        
        host = self.db_host.text().strip() or "localhost"
        port = self.db_port.value()
        database = self.db_name.text().strip() or "titan_pos"
        user = self.db_user.text().strip() or "titan_user"
        password = self.db_password.text()

        if not password:
            self.db_status_label.setText("⚠️ Por favor ingresa la contraseña")
            self.db_status_label.setStyleSheet("padding: 10px; border-radius: 5px; background: #fff3cd; color: #856404;")
            return

        # Validate identifiers to prevent SQL injection
        try:
            safe_user = _escape_pg_identifier(user)
            safe_database = _escape_pg_identifier(database)
        except ValueError as e:
            self.db_status_label.setText(f"⚠️ Nombre de usuario o base de datos inválido: {e}")
            self.db_status_label.setStyleSheet("padding: 10px; border-radius: 5px; background: #f8d7da; color: #721c24;")
            return
        
        # CRITICAL: Intentar crear automáticamente usuario y base de datos
        self.db_status_label.setText("🔄 Creando usuario y base de datos automáticamente...")
        self.db_status_label.setStyleSheet("padding: 10px; border-radius: 5px; background: #d1ecf1; color: #0c5460;")
        QtWidgets.QApplication.processEvents()  # Actualizar UI
        
        success, message = self._create_postgresql_user_and_database(user, password, database)
        if not success:
            # Si falla la creación automática, mostrar instrucciones claras
            if "Timeout" in message or "sudo requiere contraseña" in message:
                # Mostrar diálogo con instrucciones
                help_dialog = QtWidgets.QMessageBox(self)
                help_dialog.setIcon(QtWidgets.QMessageBox.Icon.Warning)
                help_dialog.setWindowTitle("⚠️ Configuración Manual Requerida")
                help_dialog.setText(
                    f"<b>La creación automática falló porque sudo requiere contraseña.</b><br><br>"
                    f"<b>Ejecuta uno de estos métodos:</b><br><br>"
                    f"<b>Opción 1 - Script Automático (Recomendada):</b><br>"
                    f"Abre una terminal y ejecuta:<br>"
                    f"<code>cd [directorio donde extrajiste TITAN POS]</code><br>"
                    f"<code>bash scripts/setup_postgresql_user.sh</code><br><br>"
                    f"<b>Opción 2 - Comandos Manuales:</b><br>"
                    f"<code>sudo -u postgres psql -c \"CREATE USER \\\"{safe_user}\\\" WITH PASSWORD '{password}';\"</code><br>"
                    f"<code>sudo -u postgres psql -c \"CREATE DATABASE \\\"{safe_database}\\\" OWNER \\\"{safe_user}\\\";\"</code><br>"
                    f"<code>sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE \\\"{safe_database}\\\" TO \\\"{safe_user}\\\";\"</code><br><br>"
                    f"Luego haz clic en 'Probar Conexión' nuevamente."
                )
                help_dialog.setDetailedText(message)
                # Aplicar tema al QMessageBox
                try:
                    from app.utils.theme_helpers import ThemeHelper
                    from app.core import STATE
                    core = getattr(STATE, 'core', None)
                    ThemeHelper.apply_dialog_theme(help_dialog, core)
                except Exception:
                    pass
                help_dialog.exec()
            # Si falla la creación automática, mostrar instrucciones
            logger.warning(f"Auto-creation failed: {message}")
            # Actualizar UI con instrucciones
            if "Timeout" in message or "sudo" in message.lower():
                self.db_status_label.setText(
                    f"⚠️ Creación automática falló (sudo requiere contraseña).\n\n"
                    f"Ejecuta en la terminal:\n"
                    f"bash scripts/setup_postgresql_user.sh\n\n"
                    f"O ejecuta estos comandos:\n"
                    f"sudo -u postgres psql -c \"CREATE USER \\\"{safe_user}\\\" WITH PASSWORD '{password}';\"\n"
                    f"sudo -u postgres psql -c \"CREATE DATABASE \\\"{safe_database}\\\" OWNER \\\"{safe_user}\\\";\"\n"
                    f"sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE \\\"{safe_database}\\\" TO \\\"{safe_user}\\\";\"\n\n"
                    f"Luego haz clic en 'Probar Conexión' nuevamente."
                )
                self.db_status_label.setStyleSheet("padding: 10px; border-radius: 5px; background: #fff3cd; color: #856404; font-family: monospace; font-size: 10px;")
                QtWidgets.QApplication.processEvents()
                return  # No continuar con la prueba de conexión si falló la creación
        
        # CRITICAL: Verificar conexión después de crear/actualizar usuario
        # Esto asegura que la contraseña guardada funcione
        # Usar retry con backoff para manejar propagación de contraseñas
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                from app.utils.path_utils import get_debug_log_path_str
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CONNECTION_TEST_START","location":"welcome_wizard.py:_test_database_connection","message":"Starting connection test","data":{"host":host,"port":port,"database":database,"user":user,"password_length":len(password)},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                 logger.debug("Writing debug log: %s", e)
        # #endregion
        
        import psycopg2
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                test_conn = psycopg2.connect(
                    host=host,
                    port=port,
                    database=database,
                    user=user,
                    password=password,
                    connect_timeout=5
                )
                test_conn.close()
                
                # #region agent log
                if agent_log_enabled():
                    try:
                        from app.utils.path_utils import get_debug_log_path_str
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CONNECTION_SUCCESS","location":"welcome_wizard.py:_test_database_connection","message":"Connection test successful","data":{"attempt":attempt+1},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                # #endregion
                
                self.db_status_label.setText("✅ Conexión exitosa y usuario configurado correctamente")
                self.db_status_label.setStyleSheet("padding: 10px; border-radius: 5px; background: #d4edda; color: #155724;")
                break
            except Exception as e:
                # #region agent log
                if agent_log_enabled():
                    try:
                        from app.utils.path_utils import get_debug_log_path_str
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CONNECTION_RETRY","location":"welcome_wizard.py:_test_database_connection","message":"Connection test failed, retrying","data":{"attempt":attempt+1,"max_retries":max_retries,"error":str(e),"error_type":type(e).__name__},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                # #endregion
                
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))  # Backoff exponencial
                    continue
                else:
                    # #region agent log
                    if agent_log_enabled():
                        try:
                            from app.utils.path_utils import get_debug_log_path_str
                            with open(get_debug_log_path_str(), "a") as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"CONNECTION_FAILED","location":"welcome_wizard.py:_test_database_connection","message":"Connection test failed after all retries","data":{"error":str(e),"error_type":type(e).__name__},"timestamp":int(time.time()*1000)})+"\n")
                        except Exception as e:
                             logger.debug("Writing debug log: %s", e)
                    # #endregion
                    logger.warning(f"Connection test failed after {max_retries} attempts: {e}")
                    
                    # Mostrar diálogo con instrucciones si es error de autenticación
                    if "password authentication failed" in str(e).lower():
                        error_dialog = QtWidgets.QMessageBox(self)
                        error_dialog.setIcon(QtWidgets.QMessageBox.Icon.Critical)
                        error_dialog.setWindowTitle("❌ Error de Autenticación")
                        error_dialog.setText(
                            f"<b>No se pudo conectar a PostgreSQL.</b><br><br>"
                            f"<b>El usuario '{safe_user}' existe pero la contraseña no coincide.</b><br><br>"
                            f"<b>Soluciones:</b><br><br>"
                            f"<b>Opción 1 - Sincronizar Contraseña (Recomendada):</b><br>"
                            f"Haz clic en el botón '🔐 Sincronizar Contraseña' arriba,<br>"
                            f"o ejecuta en la terminal:<br>"
                            f"<code>bash scripts/sync_postgresql_password.sh</code><br><br>"
                            f"<b>Opción 2 - Crear Usuario Nuevo:</b><br>"
                            f"Ejecuta en la terminal:<br>"
                            f"<code>bash scripts/setup_postgresql_user.sh</code><br><br>"
                            f"<b>Opción 3 - Cambiar Contraseña Manualmente:</b><br>"
                            f"<code>sudo -u postgres psql -c \"ALTER USER \\\"{safe_user}\\\" WITH PASSWORD 'TU_PASSWORD';\"</code><br><br>"
                            f"Luego vuelve aquí y haz clic en 'Probar Conexión' nuevamente."
                        )
                        error_dialog.setDetailedText(f"Error: {e}")
                        # Aplicar tema al QMessageBox
                        try:
                            from app.utils.theme_helpers import ThemeHelper
                            from app.core import STATE
                            core = getattr(STATE, 'core', None)
                            ThemeHelper.apply_dialog_theme(error_dialog, core)
                        except Exception:
                            pass
                        error_dialog.exec()
                    self.db_status_label.setText(f"⚠️ Usuario/BD creados pero conexión falló. Verifica la contraseña.\nError: {str(e)[:100]}")
                    self.db_status_label.setStyleSheet("padding: 10px; border-radius: 5px; background: #fff3cd; color: #856404;")
        
        # Create database.json
        config = {
            "backend": "postgresql",
            "postgresql": {
                "host": host,
                "port": port,
                "database": database,
                "user": user,
                "password": password,
                "pool_size": 5
            }
        }
        
        # Ensure directory exists (using dynamic workspace root)
        workspace_root = get_workspace_root()
        config_dir = workspace_root / "data" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        config_path = config_dir / "database.json"
        
        try:
            # Save configuration
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            # Test connection
            try:
                from src.infra.database import initialize_db
                test_db = initialize_db(str(config_path))
                
                if test_db:
                    # Test query
                    test_db.execute_query("SELECT 1")
                    self.db_status_label.setText("✅ Conexión exitosa! Base de datos configurada correctamente.")
                    self.db_status_label.setStyleSheet("padding: 10px; border-radius: 5px; background: #d4edda; color: #155724;")
                    
                    # Try to reinitialize core database
                    try:
                        if self.core.initialize_database(str(config_path)):
                            logger.info("Database initialized successfully from wizard")
                    except Exception as e:
                        logger.warning(f"Could not reinitialize core database: {e}")
                    
                    return
                else:
                    raise Exception("initialize_db returned None")
            except Exception as e:
                self.db_status_label.setText(f"❌ Error de conexión: {str(e)}\n\nVerifica que PostgreSQL esté instalado y corriendo.")
                self.db_status_label.setStyleSheet("padding: 10px; border-radius: 5px; background: #f8d7da; color: #721c24;")
        except Exception as e:
            self.db_status_label.setText(f"❌ Error guardando configuración: {str(e)}")
            self.db_status_label.setStyleSheet("padding: 10px; border-radius: 5px; background: #f8d7da; color: #721c24;")

    def _business_page(self) -> QtWidgets.QWizardPage:
        """Business information page."""
        page = QtWidgets.QWizardPage()
        page.setTitle("Información del Negocio")
        page.setSubTitle("Datos que aparecerán en tickets y facturas")
        
        layout = QtWidgets.QFormLayout(page)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.business_name = QtWidgets.QLineEdit()
        self.business_name.setPlaceholderText("Ej: Mi Tienda")
        
        self.business_type = QtWidgets.QComboBox()
        self.business_type.addItems([
            "Tienda", "Restaurante", "Cafetería", "Farmacia", 
            "Ferretería", "Supermercado", "Otro"
        ])
        
        self.business_rfc = QtWidgets.QLineEdit()
        self.business_rfc.setPlaceholderText("XAXX010101000")
        self.business_rfc.setMaxLength(13)
        
        self.business_address = QtWidgets.QLineEdit()
        self.business_address.setPlaceholderText("Calle, Colonia, CP, Ciudad")
        
        self.business_phone = QtWidgets.QLineEdit()
        self.business_phone.setPlaceholderText("555-1234567")
        
        self.branch_name = QtWidgets.QLineEdit()
        self.branch_name.setPlaceholderText("Ej: Sucursal Centro")
        
        layout.addRow("Nombre del Negocio:*", self.business_name)
        layout.addRow("Tipo de Negocio:", self.business_type)
        layout.addRow("RFC:", self.business_rfc)
        layout.addRow("Dirección:", self.business_address)
        layout.addRow("Teléfono:", self.business_phone)
        layout.addRow("Nombre de Sucursal:", self.branch_name)
        
        # Mark required
        page.registerField("business_name*", self.business_name)
        
        return page

    def _multicaja_page(self) -> QtWidgets.QWizardPage:
        """MultiCaja configuration page."""
        page = QtWidgets.QWizardPage()
        page.setTitle("⚙️ Configuración MultiCaja")
        page.setSubTitle("¿Cómo funcionará este terminal en tu red de cajas?")
        
        layout = QtWidgets.QVBoxLayout(page)
        layout.setSpacing(15)
        
        # Mode selection
        mode_group = QtWidgets.QGroupBox("Modo de Operación")
        mode_layout = QtWidgets.QVBoxLayout()
        
        self.mode_standalone = QtWidgets.QRadioButton("🖥️ Terminal Independiente (sin sincronización)")
        self.mode_standalone.setToolTip("Este terminal trabajará solo, sin conectarse a otros")
        
        self.mode_server = QtWidgets.QRadioButton("🏢 Terminal Maestro (Servidor)")
        self.mode_server.setToolTip("Este será el terminal principal que recibirá datos de otros terminales")
        
        self.mode_client = QtWidgets.QRadioButton("📡 Terminal Secundario (Cliente)")
        self.mode_client.setToolTip("Este terminal enviará datos a un terminal maestro")
        
        self.mode_standalone.setChecked(True)  # Default
        
        mode_layout.addWidget(self.mode_standalone)
        mode_layout.addWidget(self.mode_server)
        mode_layout.addWidget(self.mode_client)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # Client configuration (only visible when client mode selected)
        self.client_config_group = QtWidgets.QGroupBox("Configuración de Cliente")
        client_layout = QtWidgets.QFormLayout()
        
        self.server_ip = QtWidgets.QLineEdit()
        self.server_ip.setPlaceholderText("192.168.1.100")
        self.server_ip.setToolTip("IP del terminal maestro")
        
        self.server_port = QtWidgets.QSpinBox()
        self.server_port.setRange(1, 65535)
        self.server_port.setValue(8000)
        
        self.sync_interval = QtWidgets.QSpinBox()
        self.sync_interval.setRange(10, 300)
        self.sync_interval.setValue(30)
        self.sync_interval.setSuffix(" segundos")

        # Configuración de Stock en Tiempo Real
        self.enable_strict_stock = QtWidgets.QCheckBox("Activación de Stock Estricto (Real-Time)")
        self.enable_strict_stock.setToolTip(
            "Si se activa, el sistema verificará el stock en el servidor en tiempo real antes de cada venta.\n"
            "Evita vender productos agotados por otras cajas, pero requiere conexión estable."
        )
        self.enable_strict_stock.setChecked(True)
        
        client_layout.addRow("IP Servidor Maestro:*", self.server_ip)
        client_layout.addRow("Puerto:", self.server_port)
        client_layout.addRow("Intervalo de Sincronización:", self.sync_interval)
        client_layout.addRow("", self.enable_strict_stock)
        
        self.client_config_group.setLayout(client_layout)
        self.client_config_group.setVisible(False)
        layout.addWidget(self.client_config_group)
        
        # Connect mode changes
        self.mode_client.toggled.connect(
            lambda checked: self.client_config_group.setVisible(checked)
        )
        
        # Token generation/input (behavior changes based on mode)
        self.token_group = QtWidgets.QGroupBox("Token de Autenticación")
        token_layout = QtWidgets.QVBoxLayout()
        
        self.token_info = QtWidgets.QLabel(
            "Se generará automáticamente un token seguro para autenticación.\n"
            "Guarda este token y úsalo en los terminales clientes."
        )
        self.token_info.setWordWrap(True)
        self.token_info.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        
        self.token_display = QtWidgets.QLineEdit()
        self.token_display.setText(secrets.token_urlsafe(32))
        
        # Update token field behavior based on mode
        def update_token_field():
            if self.mode_server.isChecked():
                # Server mode: generate token automatically, read-only
                self.token_display.setReadOnly(True)
                self.token_info.setText(
                    "Se generó automáticamente un token seguro para autenticación.\n"
                    "⚠️ GUARDA ESTE TOKEN - Lo necesitarás en los terminales clientes."
                )
                # Generate new token if empty
                if not self.token_display.text():
                    self.token_display.setText(secrets.token_urlsafe(32))
            elif self.mode_client.isChecked():
                # Client mode: user must enter server token, editable
                self.token_display.setReadOnly(False)
                self.token_display.clear()
                self.token_info.setText(
                    "Ingresa el token del terminal maestro (servidor).\n"
                    "Este token fue generado durante la configuración del servidor."
                )
            else:
                # Standalone mode: token not needed
                self.token_display.setReadOnly(True)
                self.token_info.setText("Token no requerido en modo independiente.")
        
        # Connect mode changes to update token field
        self.mode_server.toggled.connect(lambda: update_token_field())
        self.mode_client.toggled.connect(lambda: update_token_field())
        self.mode_standalone.toggled.connect(lambda: update_token_field())
        
        # Set initial state
        update_token_field()
        
        token_layout.addWidget(self.token_info)
        token_layout.addWidget(self.token_display)
        self.token_group.setLayout(token_layout)
        layout.addWidget(self.token_group)
        
        layout.addStretch()
        
        return page

    def _printer_page(self) -> QtWidgets.QWizardPage:
        """Printer configuration page."""
        page = QtWidgets.QWizardPage()
        page.setTitle("🖨️ Configuración de Impresora")
        page.setSubTitle("Configura tu impresora de tickets")
        
        layout = QtWidgets.QVBoxLayout(page)
        form = QtWidgets.QFormLayout()
        form.setSpacing(12)
        
        # Printer combo with CUPS detection
        printer_row = QtWidgets.QHBoxLayout()
        self.printer_combo = QtWidgets.QComboBox()
        self.printer_combo.setMinimumWidth(250)
        self.printer_combo.setEditable(True)  # Allow manual entry
        printer_row.addWidget(self.printer_combo, 1)
        
        refresh_btn = QtWidgets.QPushButton("🔄")
        refresh_btn.setMaximumWidth(40)
        refresh_btn.setToolTip("Detectar impresoras CUPS")
        refresh_btn.clicked.connect(self._detect_printers)
        printer_row.addWidget(refresh_btn)
        
        form.addRow("Impresora:", printer_row)
        
        self.paper_width = QtWidgets.QComboBox()
        self.paper_width.addItems(["58mm", "80mm"])
        self.paper_width.setCurrentIndex(1)  # 80mm default
        form.addRow("Ancho de Papel:", self.paper_width)
        
        self.auto_print = QtWidgets.QCheckBox("Imprimir tickets automáticamente")
        self.auto_print.setChecked(True)
        form.addRow("", self.auto_print)
        
        self.open_drawer = QtWidgets.QCheckBox("Abrir cajón al cobrar")
        self.open_drawer.setChecked(True)
        form.addRow("", self.open_drawer)
        
        layout.addLayout(form)
        
        # Test print button
        test_btn = QtWidgets.QPushButton("🖨️ Imprimir Prueba")
        test_btn.clicked.connect(self._print_test)
        layout.addWidget(test_btn)
        
        info_label = QtWidgets.QLabel(
            "💡 Puedes configurar esto después en Configuración → Dispositivos"
        )
        info_label.setStyleSheet("color: #7f8c8d; font-size: 11px; margin-top: 10px;")
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        # Detect printers on page creation
        self._detect_printers()
        
        return page

    def _user_page(self) -> QtWidgets.QWizardPage:
        """Admin user creation page."""
        page = QtWidgets.QWizardPage()
        page.setTitle("👤 Usuario Administrador")
        page.setSubTitle("Crea tu usuario administrador para el sistema")
        
        layout = QtWidgets.QFormLayout(page)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.admin_username = QtWidgets.QLineEdit()
        self.admin_username.setPlaceholderText("admin")
        
        self.admin_password = QtWidgets.QLineEdit()
        self.admin_password.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.admin_password.setPlaceholderText("Mínimo 4 caracteres")
        
        self.admin_password_confirm = QtWidgets.QLineEdit()
        self.admin_password_confirm.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.admin_password_confirm.setPlaceholderText("Repetir contraseña")
        
        self.admin_name = QtWidgets.QLineEdit()
        self.admin_name.setPlaceholderText("Nombre del administrador")
        
        layout.addRow("Usuario:*", self.admin_username)
        layout.addRow("Contraseña:*", self.admin_password)
        layout.addRow("Confirmar:*", self.admin_password_confirm)
        layout.addRow("Nombre:", self.admin_name)
        
        info_label = QtWidgets.QLabel(
            "⚠️ Guarda estas credenciales en un lugar seguro"
        )
        info_label.setStyleSheet("color: #e67e22; font-size: 11px; margin-top: 10px;")
        layout.addRow(info_label)
        
        page.registerField("admin_username*", self.admin_username)
        page.registerField("admin_password*", self.admin_password)
        
        return page

    def _detect_printers(self) -> None:
        """Detect installed CUPS printers."""
        import platform
        import subprocess
        
        current = self.printer_combo.currentText()
        self.printer_combo.clear()
        printers = []
        
        try:
            if platform.system() == "Linux":
                result = subprocess.run(
                    ["lpstat", "-a"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            parts = line.split()
                            if parts:
                                printers.append(parts[0])
        except Exception:
            pass
        
        if printers:
            self.printer_combo.addItems(printers)
        else:
            self.printer_combo.addItem("(No se detectaron impresoras)")
        
        # Restore previous selection if valid
        if current:
            idx = self.printer_combo.findText(current)
            if idx >= 0:
                self.printer_combo.setCurrentIndex(idx)
            else:
                self.printer_combo.setCurrentText(current)

    def _print_test(self) -> None:
        """Print a test ticket."""
        from app.utils import ticket_engine
        
        printer = self.printer_combo.currentText()
        if not printer or printer.startswith("("):
            QtWidgets.QMessageBox.warning(
                self, "Impresora",
                "Selecciona una impresora válida para hacer la prueba."
            )
            return
        
        try:
            ticket_engine.print_test_ticket(printer)
            QtWidgets.QMessageBox.information(
                self, "Prueba",
                f"Ticket de prueba enviado a '{printer}'.\n"
                "Verifica que la impresora lo haya recibido."
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Error al imprimir: {e}"
            )

    def _finish_page(self) -> QtWidgets.QWizardPage:
        """Final page with summary."""
        page = QtWidgets.QWizardPage()
        page.setTitle("✅ Configuración Completa")
        page.setSubTitle("Revisa los datos y presiona 'Finalizar' para comenzar")
        
        layout = QtWidgets.QVBoxLayout(page)
        
        self.summary_label = QtWidgets.QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("padding: 20px; background: #ecf0f1; border-radius: 5px;")
        layout.addWidget(self.summary_label)
        
        layout.addStretch()
        
        # Update summary when page is shown
        page.initializePage = self._update_summary
        
        return page

    def _update_summary(self):
        """Update summary on finish page."""
        mode_text = "Independiente"
        if self.mode_server.isChecked():
            mode_text = "Servidor Maestro"
        elif self.mode_client.isChecked():
            mode_text = "Cliente"
        
        printer_name = self.printer_combo.currentText()
        if printer_name.startswith("("):
            printer_name = "No configurada"
        
        summary = f"""
<h3>Resumen de Configuración:</h3>

<p><b>Negocio:</b> {self.business_name.text() or 'Sin nombre'}<br>
<b>RFC:</b> {self.business_rfc.text() or 'No especificado'}<br>
<b>Tipo:</b> {self.business_type.currentText()}<br>
<b>Sucursal:</b> {self.branch_name.text() or 'Principal'}</p>

<p><b>Modo MultiCaja:</b> {mode_text}<br>
"""
        
        if self.mode_client.isChecked():
            summary += f"<b>Servidor:</b> {self.server_ip.text()}:{self.server_port.value()}<br>"
        
        if self.mode_server.isChecked() or self.mode_client.isChecked():
            summary += f"<b>Token:</b> {self.token_display.text()[:20]}...</p>"
        
        summary += f"""
<p><b>Impresora:</b> {printer_name}<br>
<b>Papel:</b> {self.paper_width.currentText()}<br>
<b>Abrir cajón:</b> {'Sí' if self.open_drawer.isChecked() else 'No'}</p>

<p><b>Usuario Admin:</b> {self.admin_username.text() or 'admin'}</p>

<p style='font-weight: bold;'>
🎉 ¡Todo listo! El sistema está configurado y listo para usar.
</p>
"""
        
        self.summary_label.setText(summary)
        # Apply theme to ensure proper colors
        self._apply_theme()

    def accept(self) -> None:  # type: ignore[override]
        """Save configuration and complete setup."""
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                from app.utils.path_utils import get_debug_log_path_str
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"welcome_wizard.py:accept","message":"Function entry","data":{"core_db_is_none":self.core.db is None},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                 logger.debug("Writing debug log: %s", e)
        # #endregion
        
        # Validate passwords match
        if self.admin_password.text() != self.admin_password_confirm.text():
            QtWidgets.QMessageBox.warning(
                self, "Error", "Las contraseñas no coinciden"
            )
            return
        if len(self.admin_password.text()) < 4:
            QtWidgets.QMessageBox.warning(
                self, "Error", "La contraseña debe tener al menos 4 caracteres"
            )
            return
        
        admin_username = self.admin_username.text().strip() or "admin"
        admin_password = self.admin_password.text()
        
        # ═══════════════════════════════════════════════════════════════════════
        # PASO 0: Crear/Actualizar database.json desde la página de configuración
        # ═══════════════════════════════════════════════════════════════════════
        import json
        from pathlib import Path
        from app.utils.path_utils import get_workspace_root
        
        # Siempre crear/actualizar database.json desde los campos del wizard
        workspace_root = get_workspace_root()
        config_dir = workspace_root / "data" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "database.json"
        
        # Obtener valores del wizard (si la página existe)
        if hasattr(self, 'db_host'):
            host = self.db_host.text().strip() or "localhost"
            port = self.db_port.value()
            database = self.db_name.text().strip() or "titan_pos"
            user = self.db_user.text().strip() or "titan_user"
            password = self.db_password.text()
        else:
            # Si no existe la página (wizard antiguo), usar valores por defecto
            host = "localhost"
            port = 5432
            database = "titan_pos"
            user = "titan_user"
            password = ""
        
        if not password:
            QtWidgets.QMessageBox.warning(
                self, "Configuración Incompleta",
                "Por favor ingresa la contraseña de PostgreSQL en la página de configuración de base de datos."
            )
            return

        # Validate identifiers to prevent SQL injection
        try:
            safe_user = _escape_pg_identifier(user)
            safe_database = _escape_pg_identifier(database)
        except ValueError as e:
            QtWidgets.QMessageBox.warning(
                self, "Configuración Inválida",
                f"Nombre de usuario o base de datos inválido: {e}"
            )
            return

        # CRITICAL: Intentar crear automáticamente usuario y base de datos antes de guardar config
        # Esto asegura que la contraseña en database.json coincida con la del usuario en PostgreSQL
        try:
            success, message = self._create_postgresql_user_and_database(user, password, database)
            if success:
                logger.info(f"Auto-creation successful: {message}")
            else:
                # Si falla, mostrar advertencia pero continuar (puede que ya existan)
                logger.warning(f"Auto-creation failed, continuing anyway: {message}")
                # Si es timeout, mostrar diálogo con instrucciones
                if "Timeout" in message or "sudo requiere contraseña" in message:
                    help_dialog = QtWidgets.QMessageBox(self)
                    help_dialog.setIcon(QtWidgets.QMessageBox.Icon.Warning)
                    help_dialog.setWindowTitle("⚠️ Configuración Manual Requerida")
                    help_dialog.setText(
                        f"<b>La creación automática falló porque sudo requiere contraseña.</b><br><br>"
                        f"<b>Ejecuta uno de estos métodos:</b><br><br>"
                        f"<b>Opción 1 - Script Automático (Recomendada):</b><br>"
                        f"Abre una terminal y ejecuta:<br>"
                        f"<code>bash scripts/setup_postgresql_user.sh</code><br><br>"
                        f"<b>Opción 2 - Comandos Manuales:</b><br>"
                        f"<code>sudo -u postgres psql -c \"CREATE USER \\\"{safe_user}\\\" WITH PASSWORD '{password}';\"</code><br>"
                        f"<code>sudo -u postgres psql -c \"CREATE DATABASE \\\"{safe_database}\\\" OWNER \\\"{safe_user}\\\";\"</code><br>"
                        f"<code>sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE \\\"{safe_database}\\\" TO \\\"{safe_user}\\\";\"</code><br><br>"
                        f"Luego haz clic en 'Finalizar' nuevamente."
                    )
                    help_dialog.setDetailedText(message)
                    # Aplicar tema al QMessageBox
                    try:
                        from app.utils.theme_helpers import ThemeHelper
                        from app.core import STATE
                        core = getattr(STATE, 'core', None)
                        ThemeHelper.apply_dialog_theme(help_dialog, core)
                    except Exception:
                        pass
                    help_dialog.exec()
        except Exception as e:
            logger.warning(f"Error in auto-creation, continuing: {e}")
        
        # CRITICAL: Verificar conexión después de crear/actualizar usuario
        # Esto asegura que la contraseña guardada funcione antes de continuar
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                from app.utils.path_utils import get_debug_log_path_str
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"ACCEPT_CONNECTION_TEST_START","location":"welcome_wizard.py:accept","message":"Starting connection test in accept()","data":{"host":host,"port":port,"database":database,"user":user,"password_length":len(password)},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                 logger.debug("Writing debug log: %s", e)
        # #endregion
        
        try:
            import psycopg2
            test_conn = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password
            )
            test_conn.close()
            
            # #region agent log
            if agent_log_enabled():
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"ACCEPT_CONNECTION_SUCCESS","location":"welcome_wizard.py:accept","message":"Connection test successful in accept()","data":{},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            
            logger.info("✅ Connection test successful after user creation")
        except Exception as e:
            # #region agent log
            if agent_log_enabled():
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"ACCEPT_CONNECTION_FAILED","location":"welcome_wizard.py:accept","message":"Connection test failed in accept()","data":{"error":str(e),"error_type":type(e).__name__},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            error_msg = str(e)
            logger.warning(f"⚠️ Connection test failed after user creation: {e}")
            
            if "password authentication failed" in error_msg.lower():
                error_dialog = QtWidgets.QMessageBox(self)
                error_dialog.setIcon(QtWidgets.QMessageBox.Icon.Critical)
                error_dialog.setWindowTitle("❌ Error de Autenticación PostgreSQL")
                error_dialog.setText(
                    f"<b>La contraseña no coincide con el usuario '{safe_user}' en PostgreSQL.</b><br><br>"
                    f"<b>Soluciones:</b><br><br>"
                    f"<b>Opción 1 - Script Automático (Recomendada):</b><br>"
                    f"Ejecuta en la terminal:<br>"
                    f"<code>bash scripts/setup_postgresql_user.sh</code><br><br>"
                    f"<b>Opción 2 - Manual:</b><br>"
                    f"Ejecuta estos comandos (reemplaza 'tu_password' con la contraseña que quieras):<br>"
                    f"<code>sudo -u postgres psql -c \"CREATE USER \\\"{safe_user}\\\" WITH PASSWORD 'tu_password';\"</code><br>"
                    f"<code>sudo -u postgres psql -c \"CREATE DATABASE \\\"{safe_database}\\\" OWNER \\\"{safe_user}\\\";\"</code><br>"
                    f"<code>sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE \\\"{safe_database}\\\" TO \\\"{safe_user}\\\";\"</code><br><br>"
                    f"<b>Opción 3 - Si el usuario ya existe:</b><br>"
                    f"<code>sudo -u postgres psql -c \"ALTER USER \\\"{safe_user}\\\" WITH PASSWORD 'tu_password';\"</code><br><br>"
                    f"Luego vuelve a este wizard y usa la misma contraseña."
                )
                error_dialog.setDetailedText(
                    f"Error completo: {error_msg}\n\n"
                    f"Usuario: {safe_user}\n"
                    f"Base de datos: {safe_database}\n"
                    f"Host: {host}\n"
                    f"Puerto: {port}"
                )
                # Aplicar tema al QMessageBox
                try:
                    from app.utils.theme_helpers import ThemeHelper
                    from app.core import STATE
                    core = getattr(STATE, 'core', None)
                    ThemeHelper.apply_dialog_theme(error_dialog, core)
                except Exception:
                    pass
                error_dialog.exec()
                logger.error("❌ CRITICAL: La contraseña en database.json NO coincide con la del usuario en PostgreSQL")
                logger.error(f"   Usuario: {safe_user}")
                logger.error("   Solución: Ejecuta scripts/setup_postgresql_user.sh o los comandos manuales mostrados en el diálogo")
            else:
                logger.warning("The password in database.json may not match the PostgreSQL user password.")
                logger.warning("You may need to run: bash scripts/setup_postgresql_user.sh")
            
            # No bloquear el flujo, pero advertir al usuario
        
        config = {
            "backend": "postgresql",
            "postgresql": {
                "host": host,
                "port": port,
                "database": database,
                "user": user,
                "password": password,
                "pool_size": 5
            }
        }
        
        # #region agent log
        if agent_log_enabled():
            try:
                from app.utils.path_utils import get_debug_log_path_str
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"SAVE_CONFIG_START","location":"welcome_wizard.py:accept","message":"Saving database.json","data":{"config_path":str(config_path),"host":host,"port":port,"database":database,"user":user,"password_length":len(password)},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                 logger.debug("Writing debug log: %s", e)
        # #endregion
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            # #region agent log
            if agent_log_enabled():
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"SAVE_CONFIG_SUCCESS","location":"welcome_wizard.py:accept","message":"database.json saved successfully","data":{},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            
            logger.info(f"Created/Updated database.json at {config_path}")
            
            # CRITICAL: Verificar que el archivo se guardó correctamente leyéndolo de vuelta
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    verify_config = json.load(f)
                verify_pg = verify_config.get('postgresql', {})
                verify_password = verify_pg.get('password', '')
                
                # #region agent log
                if agent_log_enabled():
                    try:
                        from app.utils.path_utils import get_debug_log_path_str
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"VERIFY_CONFIG_SAVED","location":"welcome_wizard.py:accept","message":"Verifying saved config","data":{"password_matches":verify_password == password,"verify_password_length":len(verify_password),"original_password_length":len(password)},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                # #endregion
                
                if verify_password != password:
                    logger.error(f"⚠️ CRITICAL: Password mismatch! Saved: {len(verify_password)} chars, Original: {len(password)} chars")
            except Exception as e:
                logger.warning(f"Could not verify saved config: {e}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"No se pudo crear el archivo de configuración:\n{str(e)}"
            )
            return
        
        # ═══════════════════════════════════════════════════════════════════════
        # PASO 1: Verificar e inicializar base de datos
        # ═══════════════════════════════════════════════════════════════════════
        if self.core.db is None:
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"welcome_wizard.py:accept","message":"DB is None, attempting to initialize","data":{},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            
            # Intentar inicializar la base de datos usando el método de POSCore
            config_path_str = str(config_path) if config_path.exists() else None
            if not self.core.initialize_database(config_path_str):
                # #region agent log
                if agent_log_enabled():
                    import json, time
                    try:
                        from app.utils.path_utils import get_debug_log_path_str
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"welcome_wizard.py:accept","message":"Failed to initialize DB","data":{},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                # #endregion
                
                # CRITICAL: No cerrar el wizard si la conexión falla
                # Regresar a la página de configuración de base de datos
                reply = QtWidgets.QMessageBox.critical(
                    self, "Error de Conexión",
                    "No se pudo conectar a PostgreSQL.\n\n"
                    "Verifica que:\n"
                    "1. PostgreSQL esté instalado y corriendo\n"
                    "2. La base de datos y usuario existan\n"
                    "3. Las credenciales sean correctas\n\n"
                    "Serás redirigido a la página de configuración de base de datos para corregir las credenciales.",
                    QtWidgets.QMessageBox.StandardButton.Ok
                )
                
                # Regresar a la página de configuración de base de datos (índice 1)
                self.setCurrentId(1)
                return  # NO cerrar el wizard
        
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                from app.utils.path_utils import get_debug_log_path_str
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"welcome_wizard.py:accept","message":"DB initialized, proceeding with branch creation","data":{},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                 logger.debug("Writing debug log: %s", e)
        # #endregion
        
        # Verificación adicional: asegurar que la DB sigue disponible después de inicializarse
        if self.core.db is None:
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"welcome_wizard.py:accept","message":"DB became None after initialization","data":{},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            QtWidgets.QMessageBox.critical(
                self, "Error de Base de Datos",
                "La base de datos no está disponible después de la inicialización.\n\n"
                "Por favor, verifica la conexión a PostgreSQL e intenta de nuevo."
            )
            return
        
        # ═══════════════════════════════════════════════════════════════════════
        # PASO 1: Crear/actualizar sucursal PRIMERO (necesaria para FOREIGN KEY)
        # ═══════════════════════════════════════════════════════════════════════
        branch_name = self.branch_name.text().strip() or "Sucursal Principal"
        try:
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"welcome_wizard.py:accept","message":"Attempting to create/update branch","data":{"branch_name":branch_name},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            
            # Verificar si existe la sucursal principal
            existing_branch = self.core.db.execute_query(
                "SELECT id FROM branches WHERE id = 1"
            )
            if not existing_branch:
                # Crear sucursal principal
                self.core.db.execute_write(
                    """INSERT INTO branches (id, name, code, is_default, is_active, created_at)
                       VALUES (1, %s, 'MAIN', 1, 1, NOW())""",
                    (branch_name,)
                )
                logger.info(f"Branch '{branch_name}' created with ID 1")
            else:
                # Actualizar nombre si ya existe
                self.core.db.execute_write(
                    "UPDATE branches SET name = %s WHERE id = 1",
                    (branch_name,)
                )
                logger.info(f"Branch '{branch_name}' updated")
        except Exception as e:
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"welcome_wizard.py:accept","message":"Error creating branch","data":{"error":str(e)},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            logger.error(f"Error creating branch: {e}")
            # Verificar si es un error crítico de conexión
            error_str = str(e).lower()
            if 'connection' in error_str or 'connect' in error_str or 'database' in error_str:
                QtWidgets.QMessageBox.critical(
                    self, "Error de Conexión",
                    f"Error de conexión a la base de datos:\n{e}\n\n"
                    "Por favor, verifica que PostgreSQL esté corriendo e intenta de nuevo."
                )
                return
            # No es crítico para otros errores, continuar
        
        # ═══════════════════════════════════════════════════════════════════════
        # PASO 2: Crear usuario admin (crítico)
        # ═══════════════════════════════════════════════════════════════════════
        user_created = False
        try:
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"welcome_wizard.py:accept","message":"Checking if user exists","data":{"admin_username":admin_username},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            
            # Check if user already exists
            existing = self.core.db.execute_query(
                "SELECT id FROM users WHERE username = %s",
                (admin_username,)
            )
            
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"welcome_wizard.py:accept","message":"User check result","data":{"existing":bool(existing)},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            if not existing:
                # #region agent log
                if agent_log_enabled():
                    import json, time
                    try:
                        from app.utils.path_utils import get_debug_log_path_str
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"welcome_wizard.py:accept","message":"Creating admin user","data":{"admin_username":admin_username},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                # #endregion
                
                # Verificar que la DB sigue disponible antes de crear usuario
                if self.core.db is None:
                    # #region agent log
                    if agent_log_enabled():
                        import json, time
                        try:
                            from app.utils.path_utils import get_debug_log_path_str
                            with open(get_debug_log_path_str(), "a") as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"welcome_wizard.py:accept","message":"DB became None before user creation","data":{},"timestamp":int(time.time()*1000)})+"\n")
                        except Exception as e:
                             logger.debug("Writing debug log: %s", e)
                    # #endregion
                    QtWidgets.QMessageBox.critical(
                        self, "Error de Base de Datos",
                        "La base de datos no está disponible.\n\n"
                        "Por favor, verifica la conexión a PostgreSQL e intenta de nuevo."
                    )
                    return
                
                self.core.create_user({
                    'username': admin_username,
                    'password': admin_password,
                    'role': 'admin',
                    'name': self.admin_name.text() or 'Administrador',
                    'is_active': 1,
                    'branch_id': 1  # Asignar a sucursal principal
                })
                logger.info(f"Admin user '{admin_username}' created")
                user_created = True
                
                # #region agent log
                if agent_log_enabled():
                    import json, time
                    try:
                        from app.utils.path_utils import get_debug_log_path_str
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"welcome_wizard.py:accept","message":"Admin user created successfully","data":{"admin_username":admin_username},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                         logger.debug("Writing debug log: %s", e)
                # #endregion
            else:
                logger.info(f"Admin user '{admin_username}' already exists")
                user_created = True  # Ya existe, está bien
        except Exception as e:
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"welcome_wizard.py:accept","message":"Error creating admin user","data":{"error":str(e),"error_type":type(e).__name__},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                     logger.debug("Writing debug log: %s", e)
            # #endregion
            logger.error(f"Error creating admin user: {e}")
            
            # Verificar tipo de error para mensaje más específico
            error_str = str(e).lower()
            error_msg = f"No se pudo crear el usuario administrador:\n{e}\n\n"
            
            if 'connection' in error_str or 'connect' in error_str:
                error_msg += "Error de conexión a la base de datos.\nVerifica que PostgreSQL esté corriendo."
            elif 'foreign key' in error_str or 'constraint' in error_str:
                error_msg += "Error de integridad referencial.\nVerifica que la sucursal principal exista."
            elif 'duplicate' in error_str or 'unique' in error_str:
                error_msg += "El usuario ya existe.\nIntenta con otro nombre de usuario."
            else:
                error_msg += "Por favor intenta de nuevo."
            
            QtWidgets.QMessageBox.critical(
                self, "Error Crítico",
                error_msg
            )
            return  # NO continuar si falla la creación del usuario
        
        # ═══════════════════════════════════════════════════════════════════════
        # PASO 2: Guardar configuración
        # ═══════════════════════════════════════════════════════════════════════
        cfg = self.core.read_config()
        
        # Business info
        cfg["business_name"] = self.business_name.text()
        cfg["business_type"] = self.business_type.currentText()
        cfg["business_rfc"] = self.business_rfc.text()
        cfg["business_address"] = self.business_address.text()
        cfg["business_phone"] = self.business_phone.text()
        
        # Store info for tickets (also save with 'store_' prefix for compatibility)
        cfg["store_name"] = self.business_name.text()
        cfg["store_rfc"] = self.business_rfc.text()
        cfg["store_address"] = self.business_address.text()
        cfg["store_phone"] = self.business_phone.text()
        
        # Branch info
        if not cfg.get("branch"):
            cfg["branch"] = {}
        cfg["branch"]["name"] = self.branch_name.text() or "Principal"
        
        # MultiCaja configuration
        if self.mode_standalone.isChecked():
            cfg["mode"] = "standalone"
        elif self.mode_server.isChecked():
            cfg["mode"] = "server"
            cfg["api_dashboard_token"] = self.token_display.text()
            cfg["server_port"] = self.server_port.value()
        elif self.mode_client.isChecked():
            cfg["mode"] = "client"
            cfg["server_ip"] = self.server_ip.text()
            cfg["server_port"] = self.server_port.value()
            cfg["sync_interval_seconds"] = self.sync_interval.value()
            cfg["api_dashboard_token"] = self.token_display.text()
            cfg["enable_strict_stock"] = self.enable_strict_stock.isChecked()

        # Printer configuration
        printer = self.printer_combo.currentText()
        if not printer.startswith("("):
            cfg["printer_name"] = printer
        cfg["ticket_paper_width"] = self.paper_width.currentText()
        cfg["auto_print_tickets"] = self.auto_print.isChecked()
        cfg["open_drawer"] = self.open_drawer.isChecked()
        
        # ═══════════════════════════════════════════════════════════════════════
        # PASO 3: Guardar credenciales de fallback admin en config
        # (en caso de que algo falle con la DB, el login puede usar esto)
        # ═══════════════════════════════════════════════════════════════════════
        cfg["admin_user"] = admin_username
        # SECURITY: Store password HASH, never plaintext
        # This matches the verification in supervisor_override_dialog.py
        import hashlib
        cfg["admin_pass_hash"] = hashlib.sha256(admin_password.encode()).hexdigest()
        # Remove any legacy plaintext password if it exists
        cfg.pop("admin_pass", None)
        
        # Mark setup as completed SOLO si el usuario fue creado
        if user_created:
            cfg["setup_completed"] = True
            cfg["setup_complete"] = True  # Ambos por compatibilidad
        
        # Save config
        self.core.write_local_config(cfg)
        
        # ═══════════════════════════════════════════════════════════════════════
        # PASO 4: Guardar configuración de tickets (opcional)
        # ═══════════════════════════════════════════════════════════════════════
        try:
            ticket_config = {
                "business_name": self.business_name.text(),
                "business_address": self.business_address.text(),
                "business_phone": self.business_phone.text(),
                "business_rfc": self.business_rfc.text(),
                "business_street": self.business_address.text(),
                "business_city": "",
                "business_state": "",
                "business_postal_code": "",
                "thank_you_message": "¡Gracias por su compra!",
                "show_phone": 1,
                "show_rfc": 1 if self.business_rfc.text() else 0,
                "show_product_code": 1,
                "currency_symbol": "$",
                "show_separators": 1,
            }
            self.core.save_ticket_config(1, ticket_config)
            logger.info("Ticket config saved to database")
        except Exception as e:
            logger.error(f"Error saving ticket config: {e}")
        
        logger.info(f"Setup completed: mode={cfg.get('mode')}, business={cfg.get('business_name')}, admin={admin_username}")
        
        super().accept()

