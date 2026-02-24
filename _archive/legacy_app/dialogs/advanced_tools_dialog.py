"""
Diálogo de Herramientas Avanzadas - Acceso a servicios especiales del POS
"""

from datetime import datetime, timedelta

from PyQt6 import QtCore, QtGui, QtWidgets

from app.utils.theme_manager import theme_manager


class AdvancedToolsDialog(QtWidgets.QDialog):
    """Panel de herramientas avanzadas del sistema."""
    
    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        
        self.setWindowTitle("🛡️ Herramientas Avanzadas")
        self.setMinimumSize(700, 500)
        self._build_ui()
    
    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(20)
        
        # Tema
        theme = (self.core.get_app_config() or {}).get("theme", "Light")
        c = theme_manager.get_colors(theme)
        
        self.setStyleSheet(f"""
            QDialog {{
                background: {c['bg_main']};
                color: {c['text_primary']};
            }}
            QGroupBox {{
                background: {c['bg_card']};
                border: 1px solid {c['border']};
                border-radius: 8px;
                padding: 15px;
                margin-top: 10px;
            }}
            QGroupBox::title {{
                color: {c['accent']};
                font-weight: bold;
            }}
            QPushButton {{
                padding: 12px 20px;
                border-radius: 6px;
                font-weight: bold;
            }}
        """)
        
        # Header
        header = QtWidgets.QLabel("🛡️ Panel de Herramientas Avanzadas")
        header.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(header)
        
        # Tabs de herramientas
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self._build_audit_tab(c), "📊 Modo Auditor")
        tabs.addTab(self._build_contingency_tab(c), "🚨 Contingencia")
        tabs.addTab(self._build_network_tab(c), "🌐 Red")
        tabs.addTab(self._build_security_tab(c), "🔐 Seguridad")
        tabs.addTab(self._build_antiforensic_tab(c), "🛡️ Anti-Forense")
        
        layout.addWidget(tabs)
        
        # Botón cerrar
        close_btn = QtWidgets.QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
    
    def _build_audit_tab(self, c) -> QtWidgets.QWidget:
        """Tab de modo auditor."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # Status
        group = QtWidgets.QGroupBox("Modo Auditor - Reportes Fiscales")
        group_layout = QtWidgets.QVBoxLayout(group)
        
        info = QtWidgets.QLabel(
            "El Modo Auditor genera reportes que SOLO muestran ventas Serie A.\n"
            "Los totales coincidirán exactamente con los CFDIs timbrados.\n\n"
            "PIN de activación: Tu PIN normal invertido (ej: 1234 → 4321)"
        )
        info.setWordWrap(True)
        group_layout.addWidget(info)
        
        # Status actual
        self.audit_status = QtWidgets.QLabel("Estado: Desactivado")
        self.audit_status.setStyleSheet("font-weight: bold; padding: 10px;")
        group_layout.addWidget(self.audit_status)
        
        # Botones
        btn_layout = QtWidgets.QHBoxLayout()
        
        activate_btn = QtWidgets.QPushButton("🔓 Activar Modo Auditor")
        activate_btn.clicked.connect(self._activate_audit_mode)
        activate_btn.setStyleSheet(f"background: {c['btn_primary']}; color: white;")
        btn_layout.addWidget(activate_btn)
        
        deactivate_btn = QtWidgets.QPushButton("🔒 Desactivar")
        deactivate_btn.clicked.connect(self._deactivate_audit_mode)
        btn_layout.addWidget(deactivate_btn)
        
        group_layout.addLayout(btn_layout)
        
        # Generar reporte
        report_btn = QtWidgets.QPushButton("📊 Generar Reporte Fiscal")
        report_btn.clicked.connect(self._generate_fiscal_report)
        report_btn.setStyleSheet(f"background: {c['btn_success']}; color: white;")
        group_layout.addWidget(report_btn)
        
        layout.addWidget(group)
        layout.addStretch()
        
        return widget
    
    def _build_contingency_tab(self, c) -> QtWidgets.QWidget:
        """Tab de modo contingencia."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # Venta genérica
        group1 = QtWidgets.QGroupBox("Venta Genérica Auditada")
        g1_layout = QtWidgets.QVBoxLayout(group1)
        
        g1_layout.addWidget(QtWidgets.QLabel(
            "Permite vender productos sin código.\n"
            "El uso queda registrado en auditoría."
        ))
        
        generic_btn = QtWidgets.QPushButton("🛒 Habilitar Venta Genérica")
        generic_btn.clicked.connect(self._enable_generic_sale)
        g1_layout.addWidget(generic_btn)
        
        layout.addWidget(group1)
        
        # Cierre ciego
        group2 = QtWidgets.QGroupBox("Cierre Ciego")
        g2_layout = QtWidgets.QVBoxLayout(group2)
        
        g2_layout.addWidget(QtWidgets.QLabel(
            "La cajera NO ve el monto esperado.\n"
            "Solo ingresa lo que contó físicamente."
        ))
        
        blind_btn = QtWidgets.QPushButton("👁️ Activar Cierre Ciego")
        blind_btn.clicked.connect(self._enable_blind_close)
        g2_layout.addWidget(blind_btn)
        
        layout.addWidget(group2)
        layout.addStretch()
        
        return widget
    
    def _build_network_tab(self, c) -> QtWidgets.QWidget:
        """Tab de estado de red."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        group = QtWidgets.QGroupBox("Estado de Red y Sincronización")
        g_layout = QtWidgets.QVBoxLayout(group)
        
        # Status de conexión
        self.network_status = QtWidgets.QLabel("Verificando conexión...")
        self.network_status.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        g_layout.addWidget(self.network_status)
        
        # Colas de sync
        self.queue_status = QtWidgets.QLabel("Colas: --")
        g_layout.addWidget(self.queue_status)
        
        # Facturas pendientes
        self.invoice_status = QtWidgets.QLabel("Facturas pendientes: --")
        g_layout.addWidget(self.invoice_status)
        
        # Botones
        btn_layout = QtWidgets.QHBoxLayout()
        
        check_btn = QtWidgets.QPushButton("🔄 Verificar Conexión")
        check_btn.clicked.connect(self._check_network)
        btn_layout.addWidget(check_btn)
        
        sync_btn = QtWidgets.QPushButton("📤 Forzar Sincronización")
        sync_btn.clicked.connect(self._force_sync)
        sync_btn.setStyleSheet(f"background: {c['btn_primary']}; color: white;")
        btn_layout.addWidget(sync_btn)
        
        g_layout.addLayout(btn_layout)
        
        layout.addWidget(group)
        layout.addStretch()
        
        # Verificar al abrir
        QtCore.QTimer.singleShot(500, self._check_network)
        
        return widget
    
    def _build_security_tab(self, c) -> QtWidgets.QWidget:
        """Tab de seguridad."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # Hardware Shield
        group = QtWidgets.QGroupBox("Hardware Shield")
        g_layout = QtWidgets.QVBoxLayout(group)
        
        self.hw_status = QtWidgets.QLabel("Hardware Shield: Verificando...")
        g_layout.addWidget(self.hw_status)
        
        check_hw_btn = QtWidgets.QPushButton("🌡️ Verificar Temperatura")
        check_hw_btn.clicked.connect(self._check_hardware)
        g_layout.addWidget(check_hw_btn)
        
        layout.addWidget(group)
        
        # Privacy Shield
        group2 = QtWidgets.QGroupBox("Privacy Shield")
        g2_layout = QtWidgets.QVBoxLayout(group2)
        
        self.privacy_status = QtWidgets.QLabel("Modo privacidad: Desactivado")
        g2_layout.addWidget(self.privacy_status)
        
        privacy_btn = QtWidgets.QPushButton("🔒 Activar Modo Privacidad")
        privacy_btn.clicked.connect(self._toggle_privacy)
        g2_layout.addWidget(privacy_btn)
        
        emergency_btn = QtWidgets.QPushButton("🚨 Bloqueo de Emergencia")
        emergency_btn.clicked.connect(self._emergency_lockdown)
        emergency_btn.setStyleSheet(f"background: {c['btn_danger']}; color: white;")
        g2_layout.addWidget(emergency_btn)
        
        layout.addWidget(group2)
        layout.addStretch()
        
        QtCore.QTimer.singleShot(500, self._check_hardware)
        QtCore.QTimer.singleShot(600, self._check_privacy)
        
        return widget
    
    def _build_antiforensic_tab(self, c) -> QtWidgets.QWidget:
        """Tab de herramientas anti-forense."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # Warning
        warning = QtWidgets.QLabel(
            "⚠️ ZONA CRÍTICA - Solo para emergencias extremas\n"
            "Estas herramientas son irreversibles."
        )
        warning.setStyleSheet("background: #e74c3c; color: white; padding: 10px; border-radius: 5px;")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        
        # Sentinel Signal
        group1 = QtWidgets.QGroupBox("📡 Sentinel Signal")
        g1_layout = QtWidgets.QVBoxLayout(group1)
        g1_layout.addWidget(QtWidgets.QLabel("Envía alerta de emergencia a contactos predefinidos."))
        
        sentinel_btn = QtWidgets.QPushButton("📡 Enviar Señal de Emergencia")
        sentinel_btn.clicked.connect(self._send_sentinel)
        sentinel_btn.setStyleSheet(f"background: {c['btn_warning']}; color: white;")
        g1_layout.addWidget(sentinel_btn)
        layout.addWidget(group1)
        
        # Network Lockdown
        group2 = QtWidgets.QGroupBox("🔒 Network Lockdown")
        g2_layout = QtWidgets.QVBoxLayout(group2)
        g2_layout.addWidget(QtWidgets.QLabel("Bloquea toda conexión de red entrante/saliente."))
        
        lockdown_btn = QtWidgets.QPushButton("🔒 Activar Lockdown de Red")
        lockdown_btn.clicked.connect(self._network_lockdown)
        g2_layout.addWidget(lockdown_btn)
        layout.addWidget(group2)
        
        # Fake Maintenance
        group3 = QtWidgets.QGroupBox("🖥️ Pantalla de Distracción")
        g3_layout = QtWidgets.QVBoxLayout(group3)
        g3_layout.addWidget(QtWidgets.QLabel("Muestra pantalla de 'Windows Update' o 'Error de BIOS'."))
        
        fake_btn = QtWidgets.QPushButton("🖥️ Mostrar Pantalla Falsa")
        fake_btn.clicked.connect(self._show_fake_screen)
        g3_layout.addWidget(fake_btn)
        layout.addWidget(group3)
        
        # Hardware Tripwire Status
        group4 = QtWidgets.QGroupBox("🔌 Hardware Tripwire")
        g4_layout = QtWidgets.QVBoxLayout(group4)
        
        self.tripwire_status = QtWidgets.QLabel("Estado: Verificando...")
        g4_layout.addWidget(self.tripwire_status)
        
        tripwire_btn = QtWidgets.QPushButton("🔍 Verificar Dispositivos")
        tripwire_btn.clicked.connect(self._check_tripwire)
        g4_layout.addWidget(tripwire_btn)
        layout.addWidget(group4)
        
        # Fila de botones extremos
        extreme_layout = QtWidgets.QHBoxLayout()
        
        # Panic Wipe
        panic_btn = QtWidgets.QPushButton("🔥 Panic Wipe")
        panic_btn.setToolTip("Borrado seguro de datos sensibles")
        panic_btn.clicked.connect(self._panic_wipe)
        panic_btn.setStyleSheet("background: #c0392b; color: white; font-weight: bold;")
        extreme_layout.addWidget(panic_btn)
        
        # Biometric Kill
        bio_btn = QtWidgets.QPushButton("🖐️ Biometric Kill")
        bio_btn.setToolTip("Kill switch con huella dactilar")
        bio_btn.clicked.connect(self._biometric_kill)
        bio_btn.setStyleSheet("background: #8e44ad; color: white; font-weight: bold;")
        extreme_layout.addWidget(bio_btn)
        
        layout.addLayout(extreme_layout)
        
        layout.addStretch()
        
        QtCore.QTimer.singleShot(700, self._check_tripwire)
        
        return widget
    
    # === Callbacks ===
    
    def _activate_audit_mode(self):
        pin, ok = QtWidgets.QInputDialog.getText(
            self, "Modo Auditor", "Ingresa tu PIN invertido:",
            QtWidgets.QLineEdit.EchoMode.Password
        )
        if ok and pin:
            from app.services.audit_mode import AuditMode
            audit = AuditMode(self.core)
            result = audit.activate_audit_mode(pin)
            
            if result.get('success'):
                self.audit_status.setText("✅ Estado: MODO AUDITOR ACTIVO")
                self.audit_status.setStyleSheet("font-weight: bold; padding: 10px; color: #e74c3c;")
                QtWidgets.QMessageBox.information(self, "Modo Auditor", result['message'])
            else:
                QtWidgets.QMessageBox.warning(self, "Error", result['message'])
    
    def _deactivate_audit_mode(self):
        pin, ok = QtWidgets.QInputDialog.getText(
            self, "Desactivar", "Ingresa tu PIN:",
            QtWidgets.QLineEdit.EchoMode.Password
        )
        if ok and pin:
            from app.services.audit_mode import AuditMode
            audit = AuditMode(self.core)
            result = audit.deactivate_audit_mode(pin)
            
            if result.get('success'):
                self.audit_status.setText("Estado: Desactivado")
                self.audit_status.setStyleSheet("font-weight: bold; padding: 10px;")
    
    def _generate_fiscal_report(self):
        from app.services.audit_mode import AuditMode
        
        audit = AuditMode(self.core)
        audit._audit_mode_active = True  # Forzar modo auditor
        
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        report = audit.get_printable_report(start_date, end_date)
        
        # Mostrar en diálogo
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Reporte Fiscal")
        dlg.setMinimumSize(600, 400)
        
        layout = QtWidgets.QVBoxLayout(dlg)
        text = QtWidgets.QTextEdit()
        text.setReadOnly(True)
        text.setFont(QtGui.QFont("Courier New", 10))
        text.setText(report)
        layout.addWidget(text)
        
        dlg.exec()
    
    def _enable_generic_sale(self):
        QtWidgets.QMessageBox.information(
            self, "Venta Genérica",
            "La venta genérica está disponible desde el teclado:\n\n"
            "1. Presiona F9 o escribe 'GENERICO' en el SKU\n"
            "2. Ingresa descripción y precio\n"
            "3. El uso queda registrado en auditoría"
        )
    
    def _enable_blind_close(self):
        QtWidgets.QMessageBox.information(
            self, "Cierre Ciego",
            "Para habilitar el cierre ciego:\n\n"
            "1. Ve a Configuración → Turnos\n"
            "2. Activa 'Cierre ciego para cajeros'\n\n"
            "Los cajeros no verán el monto esperado al cerrar turno."
        )
    
    def _check_network(self):
        from app.services.network_failover import NetworkFailover
        
        failover = NetworkFailover()
        quality = failover.check_connection()
        status = failover.get_status()
        
        icons = {
            'excellent': '🟢',
            'good': '🟡',
            'degraded': '🟠',
            'poor': '🔴',
            'offline': '⚫'
        }
        
        self.network_status.setText(
            f"{icons.get(quality.value, '❓')} Conexión: {quality.value.upper()}"
        )
        
        self.queue_status.setText(
            f"Colas pendientes - Críticos: {status['queues']['critical']} | "
            f"Normal: {status['queues']['normal']} | "
            f"Diferidos: {status['queues']['deferred']}"
        )
        
        # Verificar facturas pendientes
        try:
            from app.services.offline_worker import OfflineWorker
            worker = OfflineWorker(self.core)
            pending = worker.get_pending_count()
            self.invoice_status.setText(f"📄 Facturas pendientes de timbrar: {pending}")
        except Exception as e:
            self.invoice_status.setText(f"Facturas: Error ({e})")
    
    def _force_sync(self):
        from app.services.network_failover import NetworkFailover
        
        failover = NetworkFailover()
        result = failover.force_sync_all()
        
        QtWidgets.QMessageBox.information(
            self, "Sincronización",
            f"Sincronización completada.\n\n"
            f"Restantes:\n"
            f"- Críticos: {result['critical_remaining']}\n"
            f"- Normal: {result['normal_remaining']}\n"
            f"- Diferidos: {result['deferred_remaining']}"
        )
        
        self._check_network()
    
    def _check_hardware(self):
        try:
            from app.services.hardware_shield import HardwareShield
            shield = HardwareShield()
            stats = shield.get_system_stats()
            
            temp = stats.get('temperature_c', 0)
            status = stats.get('status', 'UNKNOWN')
            
            icons = {'🟢 OK': '🟢', '🟡 WARNING': '🟡', '🔴 CRITICAL': '🔴'}
            icon = icons.get(status, '❓')
            
            self.hw_status.setText(
                f"{icon} Hardware Shield\n"
                f"   Temperatura: {temp}°C\n"
                f"   CPU: {stats.get('cpu_percent', 0):.1f}%\n"
                f"   RAM: {stats.get('ram_percent', 0):.1f}%\n"
                f"   Disco: {stats.get('disk_percent', 0):.1f}%"
            )
        except Exception as e:
            self.hw_status.setText(f"❌ Error: {e}")
    
    def _check_privacy(self):
        try:
            from app.services.privacy_shield import PrivacyShield
            shield = PrivacyShield(self.core)
            status = shield.get_status()
            
            if status['privacy_mode']:
                self.privacy_status.setText("🔒 Modo privacidad: ACTIVADO")
                self.privacy_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
            else:
                self.privacy_status.setText("🔓 Modo privacidad: Desactivado")
                self.privacy_status.setStyleSheet("")
        except Exception as e:
            self.privacy_status.setText(f"Error: {e}")
    
    def _toggle_privacy(self):
        pin, ok = QtWidgets.QInputDialog.getText(
            self, "Privacy Shield", "Ingresa tu PIN:",
            QtWidgets.QLineEdit.EchoMode.Password
        )
        if ok and pin:
            from app.services.privacy_shield import PrivacyShield
            shield = PrivacyShield(self.core)
            
            if shield.is_privacy_mode():
                result = shield.deactivate_privacy_mode(pin)
            else:
                result = shield.activate_privacy_mode(pin)
            
            if result.get('success'):
                self._check_privacy()
                QtWidgets.QMessageBox.information(self, "Privacy Shield", result['message'])
            else:
                QtWidgets.QMessageBox.warning(self, "Error", result.get('error', 'Error'))
    
    def _emergency_lockdown(self):
        reply = QtWidgets.QMessageBox.warning(
            self, "⚠️ Bloqueo de Emergencia",
            "¿Estás seguro de activar el bloqueo de emergencia?\n\n"
            "Esto cerrará todas las sesiones remotas y activará el modo privacidad.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            from app.services.privacy_shield import PrivacyShield
            shield = PrivacyShield(self.core)
            result = shield.emergency_lockdown(trigger='ui_button')
            
            self._check_privacy()
            QtWidgets.QMessageBox.information(
                self, "Bloqueo Activado",
                f"🔒 {result['message']}\n\n"
                f"Acceso remoto: {'❌' if not result.get('remote_access') else '✅'}\n"
                f"API: {'❌' if not result.get('api_access') else '✅'}"
            )
    
    # === Anti-Forense Callbacks ===
    
    def _send_sentinel(self):
        """Envía señal de emergencia."""
        from app.services.sentinel_signal import SentinelSignal
        sentinel = SentinelSignal()
        
        contacts = sentinel.list_contacts()
        
        # Si no hay contactos, ofrecer agregar
        if not contacts:
            reply = QtWidgets.QMessageBox.question(
                self, "Sin Contactos",
                "No hay contactos de emergencia configurados.\n\n"
                "¿Desea agregar uno ahora?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                self._manage_emergency_contacts()
            return
        
        # Mostrar contactos y confirmar envío
        contact_list = "\n".join([f"  • {c['name']} ({c.get('phone', c.get('telegram', c.get('email', 'N/A')))})" 
                                  for c in contacts])
        
        reply = QtWidgets.QMessageBox.warning(
            self, "⚠️ Señal de Emergencia",
            f"¿Enviar alerta de emergencia a estos contactos?\n\n"
            f"{contact_list}\n\n"
            "Esta acción notificará a todos los contactos configurados.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            try:
                result = sentinel.send_emergency_signal()
                QtWidgets.QMessageBox.information(
                    self, "Señal Enviada",
                    f"📡 Señal de emergencia enviada.\n"
                    f"Contactos notificados: {result.get('sent', 0)}\n"
                    f"Fallidos: {result.get('failed', 0)}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Error", f"Error: {e}")
    
    def _manage_emergency_contacts(self):
        """Gestiona contactos de emergencia."""
        from app.services.sentinel_signal import SentinelSignal
        sentinel = SentinelSignal()
        
        while True:
            contacts = sentinel.list_contacts()
            
            if contacts:
                items = [f"{c['name']} - {c.get('phone', '')} {c.get('telegram', '')} {c.get('email', '')}"
                         for c in contacts]
                items.append("➕ Agregar nuevo contacto")
                items.append("🚪 Salir")
            else:
                items = ["➕ Agregar nuevo contacto", "🚪 Salir"]
            
            item, ok = QtWidgets.QInputDialog.getItem(
                self, "📞 Contactos de Emergencia",
                "Seleccione un contacto para eliminar o agregar uno nuevo:",
                items, 0, False
            )
            
            if not ok or item == "🚪 Salir":
                break
            
            if item == "➕ Agregar nuevo contacto":
                # Pedir nombre
                name, ok = QtWidgets.QInputDialog.getText(
                    self, "Nombre", "Nombre del contacto:")
                if not ok or not name:
                    continue
                
                # Pedir teléfono (WhatsApp)
                phone, _ = QtWidgets.QInputDialog.getText(
                    self, "WhatsApp", 
                    "Teléfono con código de país (ej: 529991234567):\n(Dejar vacío para omitir)")
                
                # Pedir Telegram
                telegram, _ = QtWidgets.QInputDialog.getText(
                    self, "Telegram",
                    "Usuario de Telegram (sin @):\n(Dejar vacío para omitir)")
                
                # Pedir email
                email, _ = QtWidgets.QInputDialog.getText(
                    self, "Email",
                    "Correo electrónico:\n(Dejar vacío para omitir)")
                
                if phone or telegram or email:
                    methods = []
                    if phone: methods.append('whatsapp')
                    if telegram: methods.append('telegram')
                    if email: methods.append('email')
                    
                    sentinel.add_contact(name, phone, email, telegram, methods)
                    QtWidgets.QMessageBox.information(
                        self, "✅ Agregado",
                        f"Contacto '{name}' agregado exitosamente."
                    )
                else:
                    QtWidgets.QMessageBox.warning(
                        self, "Error",
                        "Debe proporcionar al menos un método de contacto."
                    )
            else:
                # Eliminar contacto seleccionado
                contact_name = item.split(" - ")[0]
                reply = QtWidgets.QMessageBox.question(
                    self, "Confirmar",
                    f"¿Eliminar contacto '{contact_name}'?",
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
                )
                
                if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                    sentinel.remove_contact(contact_name)
                    QtWidgets.QMessageBox.information(
                        self, "✅ Eliminado",
                        f"Contacto '{contact_name}' eliminado."
                    )
    
    def _network_lockdown(self):
        """Activa lockdown de red."""
        reply = QtWidgets.QMessageBox.warning(
            self, "⚠️ Network Lockdown",
            "¿Bloquear TODAS las conexiones de red?\n\n"
            "El sistema quedará completamente aislado.\n"
            "Solo podrá liberarse con reinicio del sistema.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            try:
                from app.services.network_lockdown import NetworkLockdown
                lockdown = NetworkLockdown()
                result = lockdown.quick_lockdown() if hasattr(lockdown, 'quick_lockdown') else lockdown.activate()
                QtWidgets.QMessageBox.information(
                    self, "Lockdown Activo",
                    "🔒 Red bloqueada completamente.\n\n"
                    "El sistema está aislado."
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Error", f"Error: {e}")
    
    def _show_fake_screen(self):
        """Muestra pantalla de distracción."""
        items = ["Windows Update", "Error de BIOS", "Verificación de Disco"]
        item, ok = QtWidgets.QInputDialog.getItem(
            self, "Pantalla de Distracción",
            "Selecciona el tipo de pantalla:\n\n"
            "⚠️ ADVERTENCIA: La pantalla cubrirá TODO y solo se cierra\n"
            "escribiendo: exit",
            items, 0, False
        )
        
        if ok:
            reply = QtWidgets.QMessageBox.warning(
                self, "⚠️ Confirmar",
                f"¿Activar pantalla '{item}'?\n\n"
                "Para salir escribe: exit\n\n"
                "¿Continuar?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
            )
            
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                # Ejecutar pantalla falsa en proceso SEPARADO
                import os
                import subprocess
                
                script_path = os.path.join(os.path.dirname(__file__), '..', 'services', 'fake_screen_runner.py')
                script_path = os.path.abspath(script_path)
                
                screen_map = {
                    "Windows Update": "windows_update",
                    "Error de BIOS": "bios_error",
                    "Disk Check": "disk_check"
                }
                screen_type = screen_map.get(item, "windows_update")
                
                try:
                    # Ejecutar en proceso completamente separado
                    subprocess.Popen(
                        ['python3', script_path, screen_type],
                        env={**os.environ, 'PYTHONPATH': os.path.dirname(os.path.dirname(os.path.dirname(script_path)))},
                        start_new_session=True
                    )
                except Exception as e:
                    print(f"Error lanzando pantalla falsa: {e}")
                
                # Cerrar este diálogo
                self.close()
    
    def _check_tripwire(self):
        """Verifica estado del tripwire de hardware."""
        try:
            from app.services.hardware_tripwire import HardwareTripwire
            tripwire = HardwareTripwire()
            
            # Verificar dispositivos
            if hasattr(tripwire, 'check_devices'):
                status = tripwire.check_devices()
            elif hasattr(tripwire, 'get_status'):
                status = tripwire.get_status()
            else:
                status = {'status': 'OK', 'devices': []}
            
            if status.get('status') == 'OK' or not status.get('alerts', []):
                self.tripwire_status.setText("🟢 Sin dispositivos sospechosos detectados")
                self.tripwire_status.setStyleSheet("color: #27ae60;")
            else:
                alert_count = len(status.get('alerts', []))
                self.tripwire_status.setText(f"🔴 {alert_count} dispositivos sospechosos detectados")
                self.tripwire_status.setStyleSheet("color: #e74c3c;")
        except Exception as e:
            self.tripwire_status.setText(f"⚠️ Error: {e}")
    
    def _panic_wipe(self):
        """Ejecuta borrado de pánico."""
        # Confirmación doble
        reply = QtWidgets.QMessageBox.critical(
            self, "🔥 PANIC WIPE - IRREVERSIBLE",
            "⚠️ ATENCIÓN: Esta acción BORRARÁ permanentemente:\n\n"
            "• Logs de auditoría\n"
            "• Datos de ventas Serie B\n"
            "• Cache y archivos temporales\n"
            "• Historial de sesiones\n\n"
            "¡ESTA ACCIÓN ES IRREVERSIBLE!\n\n"
            "¿Deseas continuar?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            # Segunda confirmación con código
            code, ok = QtWidgets.QInputDialog.getText(
                self, "Confirmar Panic Wipe",
                "Escribe 'CONFIRMAR BORRADO' para continuar:",
                QtWidgets.QLineEdit.EchoMode.Normal
            )
            
            if ok and code == "CONFIRMAR BORRADO":
                try:
                    from app.services.panic_wipe import PanicWipe
                    wipe = PanicWipe()
                    result = wipe.execute() if hasattr(wipe, 'execute') else wipe.wipe_all()
                    QtWidgets.QMessageBox.information(
                        self, "Wipe Completado",
                        f"🔥 Borrado completado.\n\n"
                        f"Archivos eliminados: {result.get('files_deleted', 0)}"
                    )
                except Exception as e:
                    QtWidgets.QMessageBox.warning(self, "Error", f"Error: {e}")
    
    def _biometric_kill(self):
        """Configura kill switch biométrico."""
        QtWidgets.QMessageBox.information(
            self, "🖐️ Biometric Kill Switch",
            "El kill switch biométrico permite:\n\n"
            "• Desactivar el sistema con huella específica\n"
            "• Activar panic wipe con combinación de dedos\n"
            "• Bloqueo inmediato al detectar huella de emergencia\n\n"
            "Configuración:\n"
            "1. Conecta lector de huellas\n"
            "2. Registra huella de 'pánico' (ej: meñique)\n"
            "3. El sistema se desactivará al detectarla\n\n"
            "Requiere: Lector de huellas USB compatible"
        )

