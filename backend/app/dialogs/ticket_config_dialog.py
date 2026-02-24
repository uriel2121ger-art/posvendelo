from __future__ import annotations

import json
import logging
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from app.core import DATA_DIR, POSCore
from app.utils.path_utils import get_debug_log_path_str, agent_log_enabled

logger = logging.getLogger(__name__)

class TicketConfigDialog(QtWidgets.QDialog):
    """
    Visual ticket designer with live preview.
    Allows customization of ticket header, footer, and layout.
    """

    def __init__(self, core: POSCore, parent=None):
        super().__init__(parent)
        self.core = core
        self.cfg = self.core.get_app_config() or {}
        
        # Load current ticket config or defaults
        # #region agent log
        if agent_log_enabled():
            import time
            try:
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_INIT","location":"ticket_config_dialog.py:__init__","message":"Initializing dialog","data":{},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                logger.debug("Writing debug log for dialog init: %s", e)
        # #endregion
        
        self.ticket_config = self._load_ticket_config()
        
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                from app.utils.path_utils import get_debug_log_path_str
                config_keys = list(self.ticket_config.keys()) if self.ticket_config else []
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_INIT","location":"ticket_config_dialog.py:__init__","message":"Ticket config loaded","data":{"config_keys":config_keys,"has_config":bool(self.ticket_config)},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                logger.debug("Writing debug log for config loaded: %s", e)
        # #endregion
        
        self.setWindowTitle("Diseñador de Tickets")
        self.setMinimumSize(900, 600)
        self.setModal(True)
        
        self._init_ui()
        self._update_preview()
        
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                from app.utils.path_utils import get_debug_log_path_str
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_INIT","location":"ticket_config_dialog.py:__init__","message":"Dialog initialized and UI created","data":{},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                logger.debug("Writing debug log for UI created: %s", e)
        # #endregion

    def _init_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        
        # Left panel: Configuration
        left_panel = self._create_config_panel()
        layout.addWidget(left_panel, 2)
        
        # Right panel: Preview
        right_panel = self._create_preview_panel()
        layout.addWidget(right_panel, 3)

    def _create_config_panel(self):
        """Create configuration panel with tabs"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        title = QtWidgets.QLabel("⚙️ Configuración del Ticket")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Tabs for different sections
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self._create_header_tab(), "Encabezado")
        tabs.addTab(self._create_body_tab(), "Cuerpo")
        tabs.addTab(self._create_footer_tab(), "Pie")
        tabs.addTab(self._create_advanced_tab(), "Avanzado")
        tabs.currentChanged.connect(lambda: self._update_preview())
        layout.addWidget(tabs)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        btn_reset = QtWidgets.QPushButton("Restaurar")
        btn_reset.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(btn_reset)
        
        btn_save = QtWidgets.QPushButton("💾 Guardar")
        btn_save.setStyleSheet("")  # Styled in showEvent
        btn_save.clicked.connect(self._save_config)
        btn_layout.addWidget(btn_save)
        
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        
        return widget

    def _create_header_tab(self):
        """Header configuration with enhanced address fields"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        
        # Business name
        self.header_business_name = QtWidgets.QLineEdit(self.ticket_config.get("business_name", "MI NEGOCIO"))
        self.header_business_name.textChanged.connect(self._update_preview)
        layout.addRow("Nombre del Negocio:", self.header_business_name)
        
        # Razón Social (for fiscal purposes)
        self.header_razon_social = QtWidgets.QLineEdit(self.ticket_config.get("razon_social", ""))
        self.header_razon_social.setPlaceholderText("Razón Social Fiscal (si es diferente al nombre)")
        self.header_razon_social.textChanged.connect(self._update_preview)
        layout.addRow("Razón Social:", self.header_razon_social)
        
        # Street address
        self.header_street = QtWidgets.QLineEdit(self.ticket_config.get("street", ""))
        self.header_street.setPlaceholderText("Calle y Número (ej: Av. Principal #123)")
        self.header_street.textChanged.connect(self._update_preview)
        layout.addRow("Calle:", self.header_street)
        
        # Cross streets
        self.header_cross_streets = QtWidgets.QLineEdit(self.ticket_config.get("cross_streets", ""))
        self.header_cross_streets.setPlaceholderText("Entre calles (opcional)")
        self.header_cross_streets.textChanged.connect(self._update_preview)
        layout.addRow("Cruzamientos:", self.header_cross_streets)
        
        # Neighborhood
        self.header_neighborhood = QtWidgets.QLineEdit(self.ticket_config.get("neighborhood", ""))
        self.header_neighborhood.setPlaceholderText("Colonia o Barrio")
        self.header_neighborhood.textChanged.connect(self._update_preview)
        layout.addRow("Colonia:", self.header_neighborhood)
        
        # City and State in same row
        city_state_layout = QtWidgets.QHBoxLayout()
        self.header_city = QtWidgets.QLineEdit(self.ticket_config.get("city", ""))
        self.header_city.setPlaceholderText("Ciudad")
        self.header_city.textChanged.connect(self._update_preview)
        city_state_layout.addWidget(self.header_city)
        
        self.header_state = QtWidgets.QLineEdit(self.ticket_config.get("state", ""))
        self.header_state.setPlaceholderText("Estado")
        self.header_state.textChanged.connect(self._update_preview)
        city_state_layout.addWidget(self.header_state)
        
        layout.addRow("Ciudad / Estado:", city_state_layout)
        
        # Postal Code
        self.header_postal_code = QtWidgets.QLineEdit(self.ticket_config.get("postal_code", ""))
        self.header_postal_code.setPlaceholderText("Código Postal (ej: 12345)")
        self.header_postal_code.setMaxLength(5)
        self.header_postal_code.textChanged.connect(self._update_preview)
        layout.addRow("CP:", self.header_postal_code)
        
        # Phone
        self.header_phone = QtWidgets.QLineEdit(self.ticket_config.get("phone", ""))
        self.header_phone.setPlaceholderText("(555) 123-4567")
        self.header_phone.textChanged.connect(self._update_preview)
        layout.addRow("Teléfono:", self.header_phone)
        
        # RFC
        self.header_rfc = QtWidgets.QLineEdit(self.ticket_config.get("rfc", ""))
        self.header_rfc.setPlaceholderText("RFC o Tax ID (opcional)")
        self.header_rfc.textChanged.connect(self._update_preview)
        layout.addRow("RFC:", self.header_rfc)
        
        # Fiscal Regime (NEW - below RFC)
        self.header_regime = QtWidgets.QLineEdit(self.ticket_config.get("regime", ""))
        self.header_regime.setPlaceholderText("Régimen Fiscal (ej: General de Ley)")
        self.header_regime.textChanged.connect(self._update_preview)
        layout.addRow("Régimen Fiscal:", self.header_regime)

        return widget

    def _create_body_tab(self):
        """Body/items configuration"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        
        # Column widths
        self.body_show_code = QtWidgets.QCheckBox("Mostrar código de producto")
        self.body_show_code.setChecked(self.ticket_config.get("show_product_code", True))
        self.body_show_code.toggled.connect(self._update_preview)
        layout.addRow("", self.body_show_code)
        
        self.body_show_unit = QtWidgets.QCheckBox("Mostrar unidad de medida")
        self.body_show_unit.setChecked(self.ticket_config.get("show_unit", False))
        self.body_show_unit.toggled.connect(self._update_preview)
        layout.addRow("", self.body_show_unit)
        
        # Number format
        self.body_decimal_places = QtWidgets.QSpinBox()
        self.body_decimal_places.setRange(0, 4)
        self.body_decimal_places.setValue(self.ticket_config.get("decimal_places", 2))
        self.body_decimal_places.valueChanged.connect(self._update_preview)
        layout.addRow("Decimales:", self.body_decimal_places)
        
        # Currency symbol
        self.body_currency = QtWidgets.QLineEdit(self.ticket_config.get("currency_symbol", "$"))
        self.body_currency.setMaxLength(3)
        self.body_currency.textChanged.connect(self._update_preview)
        layout.addRow("Símbolo Moneda:", self.body_currency)
        
        # Separator lines
        self.body_separator = QtWidgets.QCheckBox("Líneas separadoras entre secciones")
        self.body_separator.setChecked(self.ticket_config.get("show_separators", True))
        self.body_separator.toggled.connect(self._update_preview)
        layout.addRow("", self.body_separator)
        
        return widget

    def _create_footer_tab(self):
        """Footer configuration"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        
        # Thank you message
        self.footer_thanks = QtWidgets.QTextEdit()
        self.footer_thanks.setPlainText(self.ticket_config.get("thank_you_message", "¡Gracias por su compra!"))
        self.footer_thanks.setMaximumHeight(60)
        self.footer_thanks.textChanged.connect(self._update_preview)
        layout.addRow("Mensaje de Agradecimiento:", self.footer_thanks)
        
        # Legal text
        self.footer_legal = QtWidgets.QTextEdit()
        self.footer_legal.setPlainText(self.ticket_config.get("legal_text", ""))
        self.footer_legal.setPlaceholderText("Texto legal (opcional)")
        self.footer_legal.setMaximumHeight(60)
        self.footer_legal.textChanged.connect(self._update_preview)
        layout.addRow("Texto Legal:", self.footer_legal)
        
        # QR Code
        self.footer_qr_enabled = QtWidgets.QCheckBox("Mostrar código QR")
        self.footer_qr_enabled.setChecked(self.ticket_config.get("show_qr", False))
        self.footer_qr_enabled.toggled.connect(self._update_preview)
        layout.addRow("", self.footer_qr_enabled)
        
        self.footer_qr_content = QtWidgets.QComboBox()
        self.footer_qr_content.addItems([
            "URL del negocio",
            "Número de ticket",
            "Datos de contacto"
        ])
        current_qr = self.ticket_config.get("qr_content", "URL del negocio")
        self.footer_qr_content.setCurrentText(current_qr)
        self.footer_qr_content.currentTextChanged.connect(self._update_preview)
        layout.addRow("Contenido QR:", self.footer_qr_content)
        
        # Website/social
        self.footer_website = QtWidgets.QLineEdit(self.ticket_config.get("website", ""))
        self.footer_website.setPlaceholderText("www.minegocio.com")
        self.footer_website.textChanged.connect(self._update_preview)
        layout.addRow("Sitio Web:", self.footer_website)
        
        return widget

    def _create_advanced_tab(self):
        """Advanced settings"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)
        
        # Font size
        self.adv_font_size = QtWidgets.QSpinBox()
        self.adv_font_size.setRange(8, 24)
        self.adv_font_size.setValue(self.ticket_config.get("font_size", 10))
        self.adv_font_size.valueChanged.connect(self._update_preview)
        layout.addRow("Tamaño de Fuente:", self.adv_font_size)
        
        # Line spacing
        self.adv_line_spacing = QtWidgets.QDoubleSpinBox()
        self.adv_line_spacing.setRange(0.5, 3.0)
        self.adv_line_spacing.setSingleStep(0.1)
        self.adv_line_spacing.setValue(self.ticket_config.get("line_spacing", 1.0))
        self.adv_line_spacing.valueChanged.connect(self._update_preview)
        layout.addRow("Espaciado de Línea:", self.adv_line_spacing)
        
        # Margins
        self.adv_margin = QtWidgets.QSpinBox()
        self.adv_margin.setRange(0, 20)
        self.adv_margin.setValue(self.ticket_config.get("margin_chars", 2))
        self.adv_margin.valueChanged.connect(self._update_preview)
        layout.addRow("Margen (caracteres):", self.adv_margin)
        
        # Cut lines
        self.adv_cut_lines = QtWidgets.QSpinBox()
        self.adv_cut_lines.setRange(0, 10)
        self.adv_cut_lines.setValue(self.ticket_config.get("cut_lines", 3))
        self.adv_cut_lines.valueChanged.connect(self._update_preview)
        layout.addRow("Líneas antes de corte:", self.adv_cut_lines)
        
        # Bold headers
        self.adv_bold_headers = QtWidgets.QCheckBox("Negrita en encabezados")
        self.adv_bold_headers.setChecked(self.ticket_config.get("bold_headers", True))
        self.adv_bold_headers.toggled.connect(self._update_preview)
        layout.addRow("", self.adv_bold_headers)
        
        # Top margin
        self.adv_margin_top = QtWidgets.QSpinBox()
        self.adv_margin_top.setRange(0, 10)
        self.adv_margin_top.setValue(self.ticket_config.get("margin_top", 0))
        self.adv_margin_top.valueChanged.connect(self._update_preview)
        self.adv_margin_top.setToolTip("Espacios en blanco al inicio del ticket")
        layout.addRow("Margen Superior:", self.adv_margin_top)
        
        # Bottom margin
        self.adv_margin_bottom = QtWidgets.QSpinBox()
        self.adv_margin_bottom.setRange(0, 10)
        self.adv_margin_bottom.setValue(self.ticket_config.get("margin_bottom", 0))
        self.adv_margin_bottom.valueChanged.connect(self._update_preview)
        self.adv_margin_bottom.setToolTip("Espacios en blanco al final del ticket (además de las líneas de corte)")
        layout.addRow("Margen Inferior:", self.adv_margin_bottom)
        
        return widget

    def _create_preview_panel(self):
        """Create preview panel"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        title = QtWidgets.QLabel("👁️ Vista Previa")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        info = QtWidgets.QLabel("Esta es una simulación de cómo se verá tu ticket impreso:")
        info.setWordWrap(True)
        info.setStyleSheet("color: #7f8c8d; margin-bottom: 5px;")
        layout.addWidget(info)
        
        # Preview area with scroll
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 2px solid #bdc3c7; background: white; }")
        
        self.preview_text = QtWidgets.QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setStyleSheet("""
            QTextEdit {
                background: white;
                color: black;
                font-family: 'Courier New', monospace;
                padding: 20px;
            }
        """)
        
        scroll.setWidget(self.preview_text)
        layout.addWidget(scroll)
        
        return widget

    def _update_preview(self):
        """Update the ticket preview"""
        # Get paper width from config
        paper_width = self.cfg.get("ticket_paper_width", "80mm")
        width_chars = 48 if paper_width == "80mm" else 32
        
        # Build preview
        lines = []
        
        business = self.header_business_name.text() or "MI NEGOCIO"
        if self.adv_bold_headers.isChecked():
            business = f"**{business}**"
        lines.append(business.center(width_chars))
        
        # Razón Social (si es diferente al nombre)
        razon_social = self.header_razon_social.text()
        if razon_social and razon_social.strip().upper() != (self.header_business_name.text() or "").strip().upper():
            lines.append(razon_social.center(width_chars))
        
        address_lines = f"{self.header_street.text()}, {self.header_neighborhood.text()}".split("\n")
        for addr in address_lines:
            lines.append(addr.center(width_chars))
        
        if self.header_phone.text():
            lines.append(self.header_phone.text().center(width_chars))
        
        if self.header_rfc.text():
            lines.append(f"RFC: {self.header_rfc.text()}".center(width_chars))
        
        if self.body_separator.isChecked():
            lines.append("=" * width_chars)
        
        # Ticket info
        lines.append("")
        lines.append(f"Ticket #: 12345".ljust(width_chars // 2) + f"Fecha: 09/12/2024")
        lines.append(f"Cajero: Demo".ljust(width_chars // 2) + f"Hora: 11:30")
        
        if self.body_separator.isChecked():
            lines.append("-" * width_chars)
        
        # Items header
        lines.append("")
        if self.body_show_code.isChecked():
            header = "Cod  Descripcion            Cant  P.Unit   Total"
        else:
            header = "Descripcion              Cant  P.Unit   Total"
        lines.append(header)
        
        if self.body_separator.isChecked():
            lines.append("-" * width_chars)
        
        # Sample items
        currency = self.body_currency.text() or "$"
        decimals = self.body_decimal_places.value()
        
        items = [
            ("001", "Producto Demo 1", 2, 50.00),
            ("002", "Producto Demo 2", 1, 125.50),
            ("003", "Producto Demo 3", 3, 35.25),
        ]
        
        for code, name, qty, price in items:
            total = qty * price
            if self.body_show_code.isChecked():
                line = f"{code} {name[:20]:<20} {qty:>4} {currency}{price:>6.{decimals}f} {currency}{total:>7.{decimals}f}"
            else:
                line = f"{name[:24]:<24} {qty:>4} {currency}{price:>6.{decimals}f} {currency}{total:>7.{decimals}f}"
            lines.append(line)
        
        if self.body_separator.isChecked():
            lines.append("=" * width_chars)
        
        # Totals
        lines.append("")
        subtotal = 335.75
        tax = 53.72
        total = 389.47
        
        lines.append(f"{'Subtotal:':<{width_chars-12}}{currency}{subtotal:>10.{decimals}f}")
        lines.append(f"{'IVA (16%):':<{width_chars-12}}{currency}{tax:>10.{decimals}f}")
        lines.append(f"{'TOTAL:':<{width_chars-12}}{currency}{total:>10.{decimals}f}")
        
        if self.body_separator.isChecked():
            lines.append("=" * width_chars)
        
        # Payment
        lines.append("")
        lines.append(f"Efectivo: {currency}400.00")
        lines.append(f"Cambio:   {currency}10.53")
        
        # Footer
        lines.append("")
        if self.body_separator.isChecked():
            lines.append("-" * width_chars)
        
        thanks = self.footer_thanks.toPlainText() or "¡Gracias por su compra!"
        for line in thanks.split("\n"):
            lines.append(line.center(width_chars))
        
        if self.footer_website.text():
            lines.append("")
            lines.append(self.footer_website.text().center(width_chars))
        
        if self.footer_legal.toPlainText():
            lines.append("")
            legal_lines = self.footer_legal.toPlainText().split("\n")
            for legal in legal_lines:
                lines.append(legal.center(width_chars))
        
        if self.footer_qr_enabled.isChecked():
            lines.append("")
            lines.append("[CÓDIGO QR]".center(width_chars))
            lines.append(f"({self.footer_qr_content.currentText()})".center(width_chars))
        
        # Cut lines
        for _ in range(self.adv_cut_lines.value()):
            lines.append("")
        
        # Apply formatting
        text = "\n".join(lines)
        
        # Apply font size
        font_size = self.adv_font_size.value()
        self.preview_text.setStyleSheet(f"""
            QTextEdit {{
                background: white;
                color: black;
                font-family: 'Courier New', monospace;
                font-size: {font_size}px;
                padding: 20px;
                line-height: {self.adv_line_spacing.value()};
            }}
        """)
        
        self.preview_text.setPlainText(text)

    def _load_ticket_config(self):
        """Load ticket configuration from database"""
        from app.core import STATE

        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                from app.utils.path_utils import get_debug_log_path_str
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_LOAD","location":"ticket_config_dialog.py:_load_ticket_config","message":"Loading ticket config","data":{"branch_id":STATE.branch_id},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                logger.debug("Writing debug log for loading config: %s", e)
        # #endregion

        # Get config from database
        config = self.core.get_ticket_config(STATE.branch_id)
        
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                from app.utils.path_utils import get_debug_log_path_str
                config_summary = {k: (str(v)[:50] if isinstance(v, str) and len(str(v)) > 50 else v) for k, v in (config.items() if config else {})}
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_LOAD","location":"ticket_config_dialog.py:_load_ticket_config","message":"Config loaded from DB","data":{"has_config":bool(config),"config_keys":list(config.keys()) if config else [],"config_summary":config_summary},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                logger.debug("Writing debug log for config from DB: %s", e)
        # #endregion
        
        if not config:
            # Return defaults if database returns empty
            return {
                "business_name": self.cfg.get("store_name", "MI NEGOCIO"),
                "business_address": self.cfg.get("store_address", "Calle Ejemplo #123\nCiudad, Estado, CP"),
                "business_phone": self.cfg.get("store_phone", "Tel: (555) 123-4567"),
                "business_rfc": self.cfg.get("store_rfc", ""),
                "website_url": "",
                "show_phone": True,
                "show_rfc": True,
                "logo_path": "",
                "show_logo": False,
                "show_product_code": True,
                "show_unit": False,
                "price_decimals": 2,
                "currency_symbol": "$",
                "show_separators": True,
                "thank_you_message": "¡Gracias por su compra!",
                "legal_text": "",
                "qr_enabled": False,
                "qr_content_type": "url",
                "font_size": 10,
                "line_spacing": 1.0,
                "margin_chars": 2,
                "cut_lines": 3,
                "bold_headers": True,
            }
        
        # Map database fields to dialog fields
        return {
            "business_name": config.get("business_name", "MI NEGOCIO"),
            "street": config.get("business_street", ""),
            "cross_streets": config.get("business_cross_streets", ""),
            "neighborhood": config.get("business_neighborhood", ""),
            "city": config.get("business_city", ""),
            "state": config.get("business_state", ""),
            "postal_code": config.get("business_postal_code", ""),
            "phone": config.get("business_phone", ""),
            "rfc": config.get("business_rfc", ""),
            "razon_social": config.get("business_razon_social", ""),
            "regime": config.get("business_regime", ""),

            "show_product_code": config.get("show_product_code", True),
            "show_unit": config.get("show_unit", False),
            "decimal_places": config.get("price_decimals", 2),
            "currency_symbol": config.get("currency_symbol", "$"),
            "show_separators": config.get("show_separators", True),
            "thank_you_message": config.get("thank_you_message", "¡Gracias por su compra!"),
            "legal_text": config.get("legal_text", ""),
            "show_qr": config.get("qr_enabled", False),
            "qr_content": config.get("qr_content_type", "url"),
            "website": config.get("website_url", ""),
            "font_size": 10,
            "line_spacing": config.get("line_spacing", 1.0),
            "margin_chars": config.get("margin_chars", 2),
            "cut_lines": config.get("cut_lines", 3),
            "bold_headers": config.get("bold_headers", True),
            "margin_top": config.get("margin_top", 0),
            "margin_bottom": config.get("margin_bottom", 0),
        }

    def _save_config(self):
        """Save ticket configuration to database"""
        from app.core import STATE
        
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                from app.utils.path_utils import get_debug_log_path_str
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_SAVE","location":"ticket_config_dialog.py:_save_config","message":"Starting save config","data":{"branch_id":STATE.branch_id},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                logger.debug("Writing debug log for starting save: %s", e)
        # #endregion
        
        config = {
            "business_name": self.header_business_name.text(),
            "business_address": self.header_street.text(),  # Using street as main address
            "business_phone": self.header_phone.text(),
            "business_rfc": self.header_rfc.text(),
            "business_razon_social": self.header_razon_social.text(),
            "business_regime": self.header_regime.text(),
            "business_street": self.header_street.text(),
            "business_cross_streets": self.header_cross_streets.text(),
            "business_neighborhood": self.header_neighborhood.text(),
            "business_city": self.header_city.text(),
            "business_state": self.header_state.text(),
            "business_postal_code": self.header_postal_code.text(),
            "website_url": self.footer_website.text(),
            "show_phone": True,
            "show_rfc": True,
            "show_product_code": self.body_show_code.isChecked(),
            "show_unit": self.body_show_unit.isChecked(),
            "price_decimals": self.body_decimal_places.value(),
            "currency_symbol": self.body_currency.text(),
            "show_separators": self.body_separator.isChecked(),
            "thank_you_message": self.footer_thanks.toPlainText(),
            "legal_text": self.footer_legal.toPlainText(),
            "qr_enabled": self.footer_qr_enabled.isChecked(),
            "qr_content_type": self.footer_qr_content.currentText(),
            "line_spacing": self.adv_line_spacing.value(),
            "margin_chars": self.adv_margin.value(),
            "cut_lines": self.adv_cut_lines.value(),
            "bold_headers": self.adv_bold_headers.isChecked(),
            "margin_top": self.adv_margin_top.value(),
            "margin_bottom": self.adv_margin_bottom.value(),
        }
        
        # #region agent log
        if agent_log_enabled():
            import json, time
            try:
                from app.utils.path_utils import get_debug_log_path_str
                config_summary = {k: (str(v)[:50] if isinstance(v, str) and len(str(v)) > 50 else v) for k, v in config.items()}
                with open(get_debug_log_path_str(), "a") as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_SAVE","location":"ticket_config_dialog.py:_save_config","message":"Config prepared","data":{"config_keys":list(config.keys()),"config_summary":config_summary},"timestamp":int(time.time()*1000)})+"\n")
            except Exception as e:
                logger.debug("Writing debug log for config prepared: %s", e)
        # #endregion
        
        try:
            # Debug: Log what we're about to save
            logger.info(f"SAVING CONFIG TO DB:")
            for key, value in config.items():
                if value and str(value).strip():
                    logger.info(f"  {key} = {repr(value)}")
            
            # Save to database
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_SAVE","location":"ticket_config_dialog.py:_save_config","message":"Calling save_ticket_config","data":{"branch_id":STATE.branch_id},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                    logger.debug("Writing debug log for calling save: %s", e)
            # #endregion
            
            success = self.core.save_ticket_config(STATE.branch_id, config)
            
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_SAVE","location":"ticket_config_dialog.py:_save_config","message":"save_ticket_config returned","data":{"success":success},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e:
                    logger.debug("Writing debug log for save returned: %s", e)
            # #endregion
            
            logger.info(f"Save result: {success}")
            
            if success:
                # #region agent log
                if agent_log_enabled():
                    import json, time
                    try:
                        from app.utils.path_utils import get_debug_log_path_str
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_SAVE","location":"ticket_config_dialog.py:_save_config","message":"Save successful, showing message","data":{},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                        logger.debug("Writing debug log for save success: %s", e)
                # #endregion
                
                QtWidgets.QMessageBox.information(
                    self,
                    "Configuración Guardada",
                    "✓ El diseño del ticket se guardó correctamente en la base de datos.\n\n"
                    "Los cambios se aplicarán en la próxima impresión."
                )
                
                # #region agent log
                if agent_log_enabled():
                    import json, time
                    try:
                        from app.utils.path_utils import get_debug_log_path_str
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_SAVE","location":"ticket_config_dialog.py:_save_config","message":"Message shown, accepting dialog","data":{},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                        logger.debug("Writing debug log for accepting dialog: %s", e)
                # #endregion
                
                self.accept()
            else:
                # #region agent log
                if agent_log_enabled():
                    import json, time
                    try:
                        from app.utils.path_utils import get_debug_log_path_str
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_SAVE","location":"ticket_config_dialog.py:_save_config","message":"Save failed, showing error","data":{},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e:
                        logger.debug("Writing debug log for save failed: %s", e)
                # #endregion
                
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    "No se pudo guardar la configuración en la base de datos."
                )
        except Exception as e:
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"TICKET_CONFIG_SAVE","location":"ticket_config_dialog.py:_save_config","message":"Exception during save","data":{"error":str(e)},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as log_err:
                    logger.debug("Writing debug log for save exception: %s", log_err)
            # #endregion
            
            logger.error(f"Error saving ticket config: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"No se pudo guardar la configuración:\n{str(e)}"
            )

    def _reset_defaults(self):
        """Reset to default configuration"""
        reply = QtWidgets.QMessageBox.question(
            self,
            "Restaurar Valores",
            "¿Deseas restaurar la configuración a los valores por defecto?\n"
            "Se perderán los cambios actuales no guardados.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self.ticket_config = self._load_ticket_config()
            # Reload all fields
            self.header_business_name.setText(self.ticket_config.get("business_name", "MI NEGOCIO"))
            self.header_razon_social.setText(self.ticket_config.get("razon_social", ""))
            self.header_street.setText(self.ticket_config.get("street", ""))
            self.header_cross_streets.setText(self.ticket_config.get("cross_streets", ""))
            self.header_neighborhood.setText(self.ticket_config.get("neighborhood", ""))
            self.header_city.setText(self.ticket_config.get("city", ""))
            self.header_state.setText(self.ticket_config.get("state", ""))
            self.header_postal_code.setText(self.ticket_config.get("postal_code", ""))
            self.header_regime.setText(self.ticket_config.get("regime", ""))
            self.header_phone.setText(self.ticket_config.get("phone", ""))
            self.header_rfc.setText(self.ticket_config.get("rfc", ""))
            self.body_show_code.setChecked(self.ticket_config.get("show_product_code", True))
            self.body_show_unit.setChecked(self.ticket_config.get("show_unit", False))
            self.body_decimal_places.setValue(self.ticket_config.get("decimal_places", 2))
            self.body_currency.setText(self.ticket_config.get("currency_symbol", "$"))
            self.body_separator.setChecked(self.ticket_config.get("show_separators", True))
            self.footer_thanks.setPlainText(self.ticket_config.get("thank_you_message", ""))
            self.footer_legal.setPlainText(self.ticket_config.get("legal_text", ""))
            self.footer_qr_enabled.setChecked(self.ticket_config.get("show_qr", False))
            self.footer_qr_content.setCurrentText(self.ticket_config.get("qr_content", "URL del negocio"))
            self.footer_website.setText(self.ticket_config.get("website", ""))
            self.adv_font_size.setValue(self.ticket_config.get("font_size", 10))
            self.adv_line_spacing.setValue(self.ticket_config.get("line_spacing", 1.0))
            self.adv_margin.setValue(self.ticket_config.get("margin_chars", 2))
            self.adv_cut_lines.setValue(self.ticket_config.get("cut_lines", 3))
            self.adv_bold_headers.setChecked(self.ticket_config.get("bold_headers", True))
            self.adv_margin_top.setValue(self.ticket_config.get("margin_top", 0))
            self.adv_margin_bottom.setValue(self.ticket_config.get("margin_bottom", 0))
            self._update_preview()

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
            logger.debug("Applying theme colors in showEvent: %s", e)

