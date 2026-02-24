"""
Configuration dialog for POS settings.
Allows setting exchange rates, payment method fees, and other system configs.
"""
from __future__ import annotations
from PyQt6 import QtCore, QtWidgets

from app.utils.theme_manager import theme_manager


class POSConfigDialog(QtWidgets.QDialog):
    """
    Dialog for POS configuration settings.
    
    Features:
    - Exchange rate for USD payments
    - Card commission percentage
    - Enable/disable payment methods
    - Tax rate configuration
    """
    
    def __init__(self, core, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.core = core
        self.config = core.get_app_config() or {}
        
        self.setWindowTitle("Configuración del POS")
        self.setModal(True)
        self.setMinimumSize(600, 500)
        
        self._build_ui()
        self._load_config()
        self.update_theme()
        
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # Header
        header = QtWidgets.QLabel("⚙️ Configuración General")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)
        
        # Tabs for different config categories
        tabs = QtWidgets.QTabWidget()
        
        # Tab 1: Payment Methods
        payment_tab = QtWidgets.QWidget()
        payment_layout = QtWidgets.QVBoxLayout(payment_tab)
        payment_layout.setContentsMargins(15, 15, 15, 15)
        payment_layout.setSpacing(15)
        
        # USD Exchange Rate
        usd_group = QtWidgets.QGroupBox("💵 Tipo de Cambio USD → MXN")
        usd_layout = QtWidgets.QFormLayout(usd_group)
        
        self.exchange_rate_input = QtWidgets.QDoubleSpinBox()
        self.exchange_rate_input.setRange(1.0, 100.0)
        self.exchange_rate_input.setDecimals(2)
        self.exchange_rate_input.setValue(17.00)
        self.exchange_rate_input.setSuffix(" MXN")
        self.exchange_rate_input.setFixedHeight(35)
        
        usd_layout.addRow("1 USD =", self.exchange_rate_input)
        payment_layout.addWidget(usd_group)
        
        # Card Commission
        card_group = QtWidgets.QGroupBox("💳 Comisión de Tarjeta")
        card_layout = QtWidgets.QFormLayout(card_group)
        
        self.card_fee_input = QtWidgets.QDoubleSpinBox()
        self.card_fee_input.setRange(0.0, 20.0)
        self.card_fee_input.setDecimals(2)
        self.card_fee_input.setValue(3.0)
        self.card_fee_input.setSuffix(" %")
        self.card_fee_input.setFixedHeight(35)
        
        card_layout.addRow("Comisión (%)", self.card_fee_input)
        
        self.card_fee_note = QtWidgets.QLabel(
            "ℹ️ Esta comisión se suma al total cuando se paga con tarjeta"
        )
        self.card_fee_note.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        self.card_fee_note.setWordWrap(True)
        card_layout.addRow("", self.card_fee_note)
        
        payment_layout.addWidget(card_group)
        
        # Enabled Payment Methods
        methods_group = QtWidgets.QGroupBox("✅ Métodos de Pago Habilitados")
        methods_layout = QtWidgets.QVBoxLayout(methods_group)
        
        self.method_checkboxes = {}
        methods = [
            ("cash", "Efectivo"),
            ("card", "Tarjeta"),
            ("transfer", "Transferencia"),
            ("usd", "Dólares (USD)"),
            ("voucher", "Vales de Despensa"),
            ("cheque", "Cheque"),
            ("credit", "Crédito"),
            ("wallet", "Monedero"),
        ]
        
        for method_id, method_name in methods:
            checkbox = QtWidgets.QCheckBox(method_name)
            checkbox.setChecked(True)  # All enabled by default
            self.method_checkboxes[method_id] = checkbox
            methods_layout.addWidget(checkbox)
            
        payment_layout.addWidget(methods_group)
        payment_layout.addStretch()
        
        tabs.addTab(payment_tab, "Formas de Pago")
        
        # Tab 2: Taxes & Business
        tax_tab = QtWidgets.QWidget()
        tax_layout = QtWidgets.QVBoxLayout(tax_tab)
        tax_layout.setContentsMargins(15, 15, 15, 15)
        tax_layout.setSpacing(15)
        
        # Tax Rate
        tax_group = QtWidgets.QGroupBox("📊 Impuestos")
        tax_form = QtWidgets.QFormLayout(tax_group)
        
        self.tax_rate_input = QtWidgets.QDoubleSpinBox()
        self.tax_rate_input.setRange(0.0, 50.0)
        self.tax_rate_input.setDecimals(2)
        self.tax_rate_input.setValue(16.0)
        self.tax_rate_input.setSuffix(" %")
        self.tax_rate_input.setFixedHeight(35)
        
        tax_form.addRow("IVA (%)", self.tax_rate_input)
        tax_layout.addWidget(tax_group)
        
        # Business Info
        business_group = QtWidgets.QGroupBox("🏢 Información del Negocio")
        business_form = QtWidgets.QFormLayout(business_group)
        
        self.business_name_input = QtWidgets.QLineEdit()
        self.business_name_input.setPlaceholderText("Nombre del Negocio")
        self.business_name_input.setFixedHeight(35)
        
        self.business_rfc_input = QtWidgets.QLineEdit()
        self.business_rfc_input.setPlaceholderText("RFC")
        self.business_rfc_input.setFixedHeight(35)
        
        business_form.addRow("Nombre:", self.business_name_input)
        business_form.addRow("RFC:", self.business_rfc_input)
        tax_layout.addWidget(business_group)
        
        tax_layout.addStretch()
        tabs.addTab(tax_tab, "Impuestos y Negocio")
        
        layout.addWidget(tabs)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QtWidgets.QPushButton("Cancelar")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setFixedWidth(120)
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QtWidgets.QPushButton("Guardar")
        save_btn.setFixedHeight(40)
        save_btn.setFixedWidth(120)
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save_config)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)
        
    def _load_config(self) -> None:
        """Load current configuration values."""
        self.exchange_rate_input.setValue(float(self.config.get('usd_exchange_rate', 17.0)))
        self.card_fee_input.setValue(float(self.config.get('card_fee_percent', 3.0)))
        self.tax_rate_input.setValue(float(self.config.get('tax_rate', 0.16)) * 100)
        
        self.business_name_input.setText(self.config.get('business_name', ''))
        self.business_rfc_input.setText(self.config.get('business_rfc', ''))
        
        # Load enabled payment methods
        enabled_methods = self.config.get('enabled_payment_methods', list(self.method_checkboxes.keys()))
        for method_id, checkbox in self.method_checkboxes.items():
            checkbox.setChecked(method_id in enabled_methods)
            
    def _save_config(self) -> None:
        """Save configuration to file."""
        new_config = self.config.copy()
        
        # Payment settings
        new_config['usd_exchange_rate'] = self.exchange_rate_input.value()
        new_config['card_fee_percent'] = self.card_fee_input.value()
        new_config['tax_rate'] = self.tax_rate_input.value() / 100.0
        
        # Business info
        new_config['business_name'] = self.business_name_input.text()
        new_config['business_rfc'] = self.business_rfc_input.text()
        
        # Enabled payment methods
        enabled_methods = [
            method_id for method_id, checkbox in self.method_checkboxes.items()
            if checkbox.isChecked()
        ]
        new_config['enabled_payment_methods'] = enabled_methods
        
        # Save
        if self.core.write_local_config(new_config):
            QtWidgets.QMessageBox.information(
                self,
                "Configuración Guardada",
                "La configuración se guardó correctamente."
            )
            self.accept()
        else:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                "No se pudo guardar la configuración."
            )
            
    def update_theme(self) -> None:
        """Apply theme colors to the dialog."""
        cfg = self.config or {}
        theme_name = cfg.get("theme", "Light")
        c = theme_manager.get_colors(theme_name)
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c['bg_main']};
                color: {c['text_primary']};
            }}
            QGroupBox {{
                border: 1px solid {c['border']};
                border-radius: 8px;
                margin-top: 10px;
                padding: 15px;
                font-weight: bold;
                color: {c['text_primary']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            QLineEdit, QDoubleSpinBox {{
                background-color: {c['input_bg']};
                color: {c['text_primary']};
                border: 1px solid {c['input_border']};
                border-radius: 4px;
                padding: 8px;
            }}
            QLineEdit:focus, QDoubleSpinBox:focus {{
                border: 2px solid {c['input_focus']};
            }}
            QCheckBox {{
                padding: 5px;
                color: {c['text_primary']};
            }}
            QPushButton {{
                background-color: {c['btn_primary']};
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
            QLabel {{
                border: none;
                background: transparent;
                color: {c['text_primary']};
            }}
            QTabWidget::pane {{
                border: 1px solid {c['border']};
                background-color: {c['bg_card']};
                border-radius: 4px;
            }}
            QTabBar::tab {{
                background-color: {c['bg_main']};
                color: {c['text_primary']};
                padding: 10px 20px;
                border: 1px solid {c['border']};
                border-bottom: none;
            }}
            QTabBar::tab:selected {{
                background-color: {c['bg_card']};
                border-bottom: 2px solid {c['btn_primary']};
            }}
        """)
