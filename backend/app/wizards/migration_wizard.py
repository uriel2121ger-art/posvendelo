"""
Wizard GUI para migración de datos del cliente
Permite migrar productos, ventas y monedero anónimo desde base de datos vieja
"""

from PyQt6 import QtWidgets, QtCore
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)

try:
    from scripts.migrate_client_data import ClientDataMigrator
    HAS_MIGRATOR = True
except ImportError:
    HAS_MIGRATOR = False
    logger.warning("Script de migración no disponible")


class MigrationWizard(QtWidgets.QWizard):
    """Wizard para migración de datos del cliente"""
    
    def __init__(self, parent=None, core=None):
        super().__init__(parent)
        self.core = core
        self.setWindowTitle("Migración de Datos del Cliente")
        self.setWizardStyle(QtWidgets.QWizard.WizardStyle.ModernStyle)
        
        # Agregar páginas
        self.addPage(IntroPage())
        self.addPage(SourcePage())
        self.addPage(TargetPage(core=core))
        self.addPage(OptionsPage())
        self.addPage(MigrationPage(core=core))
        
        self.resize(700, 500)
        self._apply_theme()
    
    def _apply_theme(self):
        """Aplicar tema"""
        try:
            from app.utils.theme_manager import theme_manager
            c = theme_manager.get_colors()
            self.setStyleSheet(f"""
                QWizard {{ background: {c['bg_secondary']}; }}
                QWizardPage {{ background: {c['bg_primary']}; }}
                QLabel {{ color: {c['text_primary']}; }}
                QLineEdit, QTextEdit, QComboBox {{
                    background: {c['bg_secondary']}; color: {c['text_primary']};
                    border: 1px solid {c['border']}; padding: 8px; border-radius: 4px;
                }}
                QPushButton {{
                    background: {c['btn_primary']}; color: white;
                    padding: 8px 16px; border-radius: 4px; font-weight: bold;
                }}
                QPushButton:hover {{ background: {c['btn_success']}; }}
            """)
        except Exception:
            pass

    def closeEvent(self, event):
        """Cleanup threads on close."""
        for page_id in range(self.pageIds()[-1] + 1 if self.pageIds() else 0):
            page = self.page(page_id)
            if hasattr(page, 'migration_thread') and page.migration_thread:
                if page.migration_thread.isRunning():
                    page.migration_thread.quit()
                    page.migration_thread.wait(3000)
        super().closeEvent(event)


class IntroPage(QtWidgets.QWizardPage):
    """Página de introducción"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Migración de Datos")
        self.setSubTitle("Importa productos, ventas y monedero anónimo desde versión anterior")
        
        layout = QtWidgets.QVBoxLayout(self)
        
        info = QtWidgets.QLabel(
            "Este asistente te ayudará a migrar datos desde tu versión anterior:\n\n"
            "• 📦 Productos (catálogo completo)\n"
            "• 💰 Ventas (historial de ventas)\n"
            "• 💳 Monedero Anónimo (puntos y transacciones)\n\n"
            "La migración preservará todas las relaciones y datos importantes."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        layout.addStretch()


class SourcePage(QtWidgets.QWizardPage):
    """Página de selección de base de datos origen"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Base de Datos Origen")
        self.setSubTitle("Selecciona la base de datos vieja (SQLite o PostgreSQL)")
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Tipo de base de datos
        type_group = QtWidgets.QGroupBox("Tipo de Base de Datos")
        type_layout = QtWidgets.QVBoxLayout()
        
        self.rb_sqlite = QtWidgets.QRadioButton("SQLite (.db)")
        self.rb_sqlite.setChecked(True)
        self.rb_postgresql = QtWidgets.QRadioButton("PostgreSQL")
        
        type_layout.addWidget(self.rb_sqlite)
        type_layout.addWidget(self.rb_postgresql)
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)
        
        # Ruta/Connection string
        path_group = QtWidgets.QGroupBox("Ubicación")
        path_layout = QtWidgets.QVBoxLayout()
        
        self.path_input = QtWidgets.QLineEdit()
        self.path_input.setPlaceholderText("Ruta al archivo .db o connection string PostgreSQL")
        
        btn_browse = QtWidgets.QPushButton("Examinar...")
        btn_browse.clicked.connect(self.browse_file)
        
        path_layout.addWidget(QtWidgets.QLabel("Ruta o Connection String:"))
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(btn_browse)
        path_group.setLayout(path_layout)
        layout.addWidget(path_group)
        
        layout.addStretch()
        
        self.registerField("source_type", self.rb_sqlite, "checked")
        self.registerField("source_path", self.path_input)
    
    def browse_file(self):
        """Abrir diálogo para seleccionar archivo"""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Seleccionar Base de Datos SQLite",
            "",
            "SQLite Database (*.db);;All Files (*)"
        )
        if file_path:
            self.path_input.setText(file_path)


class TargetPage(QtWidgets.QWizardPage):
    """Página de configuración de base de datos destino"""
    
    def __init__(self, core=None):
        super().__init__()
        self.core = core
        self.setTitle("Base de Datos Destino")
        self.setSubTitle("Configuración de PostgreSQL nueva")
        
        layout = QtWidgets.QVBoxLayout(self)
        
        info = QtWidgets.QLabel(
            "La migración se realizará a la base de datos PostgreSQL configurada actualmente.\n"
            "Verifica que la configuración sea correcta."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Mostrar configuración actual
        config_group = QtWidgets.QGroupBox("Configuración Actual")
        config_layout = QtWidgets.QFormLayout()
        
        self.config_label = QtWidgets.QLabel()
        self.config_label.setWordWrap(True)
        self.config_label.setStyleSheet("padding: 10px; background: #f0f0f0; border-radius: 4px;")
        
        config_layout.addRow(self.config_label)
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        layout.addStretch()
    
    def initializePage(self):
        """Cargar configuración actual"""
        try:
            if self.core and self.core.db:
                # Obtener configuración de base de datos
                config_path = Path("data/config/database.json")
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                    
                    pg_config = config.get("postgresql", {})
                    config_text = (
                        f"Host: {pg_config.get('host', 'localhost')}\n"
                        f"Puerto: {pg_config.get('port', 5432)}\n"
                        f"Base de datos: {pg_config.get('database', 'titan_pos')}\n"
                        f"Usuario: {pg_config.get('user', 'titan_user')}"
                    )
                    self.config_label.setText(config_text)
                else:
                    self.config_label.setText("⚠️ No se encontró archivo de configuración")
            else:
                self.config_label.setText("⚠️ Core no disponible")
        except Exception as e:
            self.config_label.setText(f"❌ Error: {e}")


class OptionsPage(QtWidgets.QWizardPage):
    """Página de opciones de migración"""
    
    def __init__(self):
        super().__init__()
        self.setTitle("Opciones de Migración")
        self.setSubTitle("Selecciona qué datos migrar")
        
        layout = QtWidgets.QVBoxLayout(self)
        
        options_group = QtWidgets.QGroupBox("Datos a Migrar")
        options_layout = QtWidgets.QVBoxLayout()
        
        self.cb_products = QtWidgets.QCheckBox("📦 Productos (catálogo completo)")
        self.cb_products.setChecked(True)
        
        self.cb_sales = QtWidgets.QCheckBox("💰 Ventas (historial completo)")
        self.cb_sales.setChecked(True)
        
        self.cb_wallet = QtWidgets.QCheckBox("💳 Monedero Anónimo (puntos y transacciones)")
        self.cb_wallet.setChecked(True)
        
        options_layout.addWidget(self.cb_products)
        options_layout.addWidget(self.cb_sales)
        options_layout.addWidget(self.cb_wallet)
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Notas
        notes = QtWidgets.QLabel(
            "⚠️ IMPORTANTE:\n"
            "• Los productos duplicados (mismo SKU) se saltarán\n"
            "• Las ventas se importarán con sus items asociados\n"
            "• El monedero anónimo incluirá todas las transacciones\n"
            "• Se recomienda hacer backup antes de migrar"
        )
        notes.setWordWrap(True)
        notes.setStyleSheet("color: #d9534f; padding: 10px; background: #fff3cd; border-radius: 4px;")
        layout.addWidget(notes)
        
        layout.addStretch()
        
        self.registerField("migrate_products", self.cb_products)
        self.registerField("migrate_sales", self.cb_sales)
        self.registerField("migrate_wallet", self.cb_wallet)


class MigrationPage(QtWidgets.QWizardPage):
    """Página de ejecución de migración"""
    
    def __init__(self, core=None):
        super().__init__()
        self.core = core
        self.setTitle("Migrando Datos...")
        self.setSubTitle("Procesando migración")
        
        layout = QtWidgets.QVBoxLayout(self)
        
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)  # Indeterminado
        layout.addWidget(self.progress)
        
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QtWidgets.QFont("Courier", 9))
        layout.addWidget(self.log_text)
        
        self.setCommitPage(True)
        self.setButtonText(QtWidgets.QWizard.WizardButton.CommitButton, "Iniciar Migración")
    
    def initializePage(self):
        """Iniciar migración cuando se muestra la página"""
        if not HAS_MIGRATOR:
            self.log_text.append("❌ Error: Script de migración no disponible")
            return
        
        # Obtener valores de campos
        source_path = self.field("source_path")
        migrate_products = self.field("migrate_products")
        migrate_sales = self.field("migrate_sales")
        migrate_wallet = self.field("migrate_wallet")
        
        if not source_path:
            self.log_text.append("❌ Error: No se especificó ruta de base de datos origen")
            return
        
        # Cargar configuración de nueva base de datos
        config_path = Path("data/config/database.json")
        if not config_path.exists():
            self.log_text.append("❌ Error: No se encontró archivo de configuración")
            return
        
        try:
            with open(config_path, 'r') as f:
                new_db_config = json.load(f)
            
            # Ejecutar migración en hilo separado
            self.migration_thread = MigrationThread(
                source_path,
                new_db_config,
                migrate_products,
                migrate_sales,
                migrate_wallet
            )
            self.migration_thread.log_signal.connect(self.log_text.append)
            self.migration_thread.finished.connect(self.on_migration_finished)
            self.migration_thread.start()
            
        except Exception as e:
            self.log_text.append(f"❌ Error: {e}")
    
    def on_migration_finished(self, success: bool):
        """Callback cuando termina la migración"""
        if success:
            self.log_text.append("\n✅ Migración completada exitosamente!")
        else:
            self.log_text.append("\n❌ Migración completada con errores. Revisa los logs.")


class MigrationThread(QtCore.QThread):
    """Hilo para ejecutar migración sin bloquear UI"""
    
    log_signal = QtCore.pyqtSignal(str)
    
    def __init__(self, source_path, new_db_config, migrate_products, migrate_sales, migrate_wallet):
        super().__init__()
        self.source_path = source_path
        self.new_db_config = new_db_config
        self.migrate_products = migrate_products
        self.migrate_sales = migrate_sales
        self.migrate_wallet = migrate_wallet
    
    def run(self):
        """Ejecutar migración"""
        try:
            migrator = ClientDataMigrator(self.source_path, self.new_db_config)
            
            # Redirigir logs a la UI
            import logging
            handler = LogHandler(self.log_signal)
            handler.setLevel(logging.INFO)
            logger = logging.getLogger("MIGRATE_CLIENT_DATA")
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            
            success = migrator.migrate_all(
                migrate_products=self.migrate_products,
                migrate_sales=self.migrate_sales,
                migrate_wallet=self.migrate_wallet
            )
            
            self.finished.emit(success)
            
        except Exception as e:
            self.log_signal.emit(f"❌ Error crítico: {e}")
            self.finished.emit(False)


class LogHandler(logging.Handler):
    """Handler de logging que emite señales para UI"""
    
    def __init__(self, signal):
        super().__init__()
        self.signal = signal
    
    def emit(self, record):
        """Emitir log a la UI"""
        try:
            msg = self.format(record)
            self.signal.emit(msg)
        except Exception:
            pass
