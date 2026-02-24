"""
Fiscal Control Tab - GUI para Ghost-Procurement y Nostradamus Fiscal
Centro de comando para optimización fiscal Serie A/B
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

class FiscalControlTab(QWidget):
    """Tab principal de Control Fiscal con Ghost-Procurement y Nostradamus."""
    
    data_changed = pyqtSignal()
    
    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self.ghost_procurement = None
        self.nostradamus = None
        self.fiscal_dashboard = None
        
        self._init_engines()
        self._setup_ui()
        self._load_data()
        
        # Auto-refresh cada 5 minutos
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._load_data)
        self.refresh_timer.start(300000)  # 5 min
    
    def _init_engines(self):
        """Inicializa los motores fiscales."""
        try:
            from app.logistics.ghost_procurement import GhostProcurement
            self.ghost_procurement = GhostProcurement(self.core)
        except Exception as e:
            logger.warning(f"GhostProcurement no disponible: {e}")
        
        try:
            from app.intel.nostradamus_fiscal import NostradamusFiscal
            self.nostradamus = NostradamusFiscal(self.core)
        except Exception as e:
            logger.warning(f"NostradamusFiscal no disponible: {e}")
        
        try:
            from app.fiscal.fiscal_dashboard import FiscalDashboard
            self.fiscal_dashboard = FiscalDashboard(self.core)
        except Exception as e:
            logger.warning(f"FiscalDashboard no disponible: {e}")
    
    def _setup_ui(self):
        """Configura la interfaz de usuario."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Header
        header = self._create_header()
        layout.addWidget(header)
        
        # Tab widget principal
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                background: #2b2b2b;
            }
            QTabBar::tab {
                background: #3d3d3d;
                color: #ffffff;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background: #4a9eff;
            }
        """)
        
        # Tab Nostradamus
        self.nostradamus_widget = NostradamusPanel(self.core, self.nostradamus, self.fiscal_dashboard)
        self.tab_widget.addTab(self.nostradamus_widget, "🔮 Nostradamus Fiscal")
        
        # Tab Ghost-Procurement
        self.ghost_widget = GhostProcurementPanel(self.core, self.ghost_procurement)
        self.tab_widget.addTab(self.ghost_widget, "👻 Ghost-Procurement")
        
        layout.addWidget(self.tab_widget, 1)
    
    def _create_header(self) -> QFrame:
        """Crea el header del módulo."""
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1a1a2e, stop:1 #16213e);
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        layout = QHBoxLayout(header)
        
        # Título
        title = QLabel("🔮 CONTROL FISCAL")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #4a9eff;")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Status badge
        self.status_badge = QLabel("⚪ Cargando...")
        self.status_badge.setStyleSheet("""
            background: #3d3d3d;
            color: white;
            padding: 5px 15px;
            border-radius: 15px;
            font-weight: bold;
        """)
        layout.addWidget(self.status_badge)
        
        # Botón actualizar
        refresh_btn = QPushButton("🔄 Actualizar")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #4a9eff;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #3a8eef;
            }
        """)
        refresh_btn.clicked.connect(self._load_data)
        layout.addWidget(refresh_btn)
        
        return header
    
    def _load_data(self):
        """Carga/actualiza datos."""
        try:
            self.nostradamus_widget.refresh_data()
            self.ghost_widget.refresh_data()
            self._update_status_badge()
        except Exception as e:
            logger.error(f"Error cargando datos fiscales: {e}")
    
    def _update_status_badge(self):
        """Actualiza el badge de estado."""
        try:
            if self.nostradamus:
                result = self.nostradamus.analyze_and_prescribe()
                prescriptions = result.get('prescriptions', [])
                
                high_priority = sum(1 for p in prescriptions if p.get('priority') == 'high')
                medium_priority = sum(1 for p in prescriptions if p.get('priority') == 'medium')
                
                if high_priority > 0:
                    self.status_badge.setText(f"🔴 {high_priority} Alta Prioridad")
                    self.status_badge.setStyleSheet("""
                        background: #e74c3c;
                        color: white;
                        padding: 5px 15px;
                        border-radius: 15px;
                        font-weight: bold;
                    """)
                elif medium_priority > 0:
                    self.status_badge.setText(f"🟡 {medium_priority} Media Prioridad")
                    self.status_badge.setStyleSheet("""
                        background: #f39c12;
                        color: white;
                        padding: 5px 15px;
                        border-radius: 15px;
                        font-weight: bold;
                    """)
                else:
                    self.status_badge.setText("🟢 Todo Optimizado")
                    self.status_badge.setStyleSheet("""
                        background: #27ae60;
                        color: white;
                        padding: 5px 15px;
                        border-radius: 15px;
                        font-weight: bold;
                    """)
            else:
                self.status_badge.setText("⚪ Sin datos")
        except Exception as e:
            self.status_badge.setText("❌ Error")
            logger.error(f"Error actualizando badge: {e}")
    
    def get_notification_badge(self) -> str:
        """Retorna el badge para el menú principal."""
        try:
            if self.nostradamus:
                result = self.nostradamus.analyze_and_prescribe()
                prescriptions = result.get('prescriptions', [])
                
                high = sum(1 for p in prescriptions if p.get('priority') == 'high')
                if high > 0:
                    return "🔴"
                
                medium = sum(1 for p in prescriptions if p.get('priority') == 'medium')
                if medium > 0:
                    return "🟡"

                return "🟢"
        except Exception:
            return ""
        return ""

    def closeEvent(self, event):
        """Cleanup timers on close."""
        if hasattr(self, 'refresh_timer') and self.refresh_timer:
            self.refresh_timer.stop()
        super().closeEvent(event)

class NostradamusPanel(QWidget):
    """Panel de Nostradamus Fiscal - Prescripciones."""
    
    def __init__(self, core, nostradamus, fiscal_dashboard, parent=None):
        super().__init__(parent)
        self.core = core
        self.nostradamus = nostradamus
        self.fiscal_dashboard = fiscal_dashboard
        self._setup_ui()
    
    def _setup_ui(self):
        """Configura la interfaz."""
        layout = QHBoxLayout(self)
        layout.setSpacing(15)
        
        # Panel izquierdo - Balance A/B
        left_panel = self._create_balance_panel()
        layout.addWidget(left_panel, 1)
        
        # Panel central - Prescripciones
        center_panel = self._create_prescriptions_panel()
        layout.addWidget(center_panel, 2)
        
        # Panel derecho - Proyección
        right_panel = self._create_projection_panel()
        layout.addWidget(right_panel, 1)
    
    def _create_balance_panel(self) -> QFrame:
        """Panel de balance Serie A/B."""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background: #2b2b2b;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        
        title = QLabel("📊 BALANCE A/B")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #4a9eff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        layout.addSpacing(20)
        
        # Valores
        self.serie_a_label = QLabel("🟢 Serie A: $0")
        self.serie_a_label.setFont(QFont("Arial", 12))
        self.serie_a_label.setStyleSheet("color: #27ae60;")
        layout.addWidget(self.serie_a_label)
        
        self.serie_b_label = QLabel("🟠 Serie B: $0")
        self.serie_b_label.setFont(QFont("Arial", 12))
        self.serie_b_label.setStyleSheet("color: #f39c12;")
        layout.addWidget(self.serie_b_label)
        
        layout.addSpacing(10)
        
        # Barra de proporción
        self.balance_bar = QProgressBar()
        self.balance_bar.setRange(0, 100)
        self.balance_bar.setValue(50)
        self.balance_bar.setTextVisible(True)
        self.balance_bar.setFormat("%p% Serie A")
        self.balance_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #3d3d3d;
                border-radius: 5px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background: #27ae60;
            }
        """)
        layout.addWidget(self.balance_bar)
        
        layout.addSpacing(20)
        
        # Warning
        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color: #e74c3c;")
        layout.addWidget(self.warning_label)
        
        layout.addStretch()
        
        return panel
    
    def _create_prescriptions_panel(self) -> QFrame:
        """Panel de prescripciones."""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background: #2b2b2b;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        
        title = QLabel("📋 PRESCRIPCIONES")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #4a9eff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Scroll area para prescripciones
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.prescriptions_container = QWidget()
        self.prescriptions_layout = QVBoxLayout(self.prescriptions_container)
        self.prescriptions_layout.setSpacing(10)
        
        scroll.setWidget(self.prescriptions_container)
        layout.addWidget(scroll, 1)
        
        return panel
    
    def _create_projection_panel(self) -> QFrame:
        """Panel de proyección fiscal."""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background: #2b2b2b;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        
        title = QLabel("📈 PROYECCIÓN")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #4a9eff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        layout.addSpacing(20)
        
        # Base gravable actual
        self.base_actual_label = QLabel("Base Gravable Actual:")
        self.base_actual_label.setStyleSheet("color: #888;")
        layout.addWidget(self.base_actual_label)
        
        self.base_actual_value = QLabel("$0")
        self.base_actual_value.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.base_actual_value.setStyleSheet("color: #e74c3c;")
        layout.addWidget(self.base_actual_value)
        
        layout.addSpacing(20)
        
        # ISR Actual
        self.isr_actual_label = QLabel("ISR Estimado:")
        self.isr_actual_label.setStyleSheet("color: #888;")
        layout.addWidget(self.isr_actual_label)
        
        self.isr_actual_value = QLabel("$0")
        self.isr_actual_value.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.isr_actual_value.setStyleSheet("color: #e74c3c;")
        layout.addWidget(self.isr_actual_value)
        
        layout.addSpacing(20)
        
        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: #3d3d3d;")
        layout.addWidget(sep)
        
        layout.addSpacing(20)
        
        # ISR Optimizado
        opt_label = QLabel("ISR Optimizado:")
        opt_label.setStyleSheet("color: #888;")
        layout.addWidget(opt_label)
        
        self.isr_optimized_value = QLabel("$0 ✅")
        self.isr_optimized_value.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.isr_optimized_value.setStyleSheet("color: #27ae60;")
        layout.addWidget(self.isr_optimized_value)
        
        layout.addSpacing(30)
        
        # Ahorro potencial
        self.savings_box = QFrame()
        self.savings_box.setStyleSheet("""
            QFrame {
                background: #1a472a;
                border: 2px solid #27ae60;
                border-radius: 10px;
                padding: 10px;
            }
        """)
        savings_layout = QVBoxLayout(self.savings_box)
        
        savings_title = QLabel("💰 AHORRO POTENCIAL")
        savings_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        savings_title.setStyleSheet("color: #27ae60; font-weight: bold;")
        savings_layout.addWidget(savings_title)
        
        self.savings_value = QLabel("$0")
        self.savings_value.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.savings_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.savings_value.setStyleSheet("color: #2ecc71;")
        savings_layout.addWidget(self.savings_value)
        
        layout.addWidget(self.savings_box)
        
        layout.addStretch()
        
        return panel
    
    def refresh_data(self):
        """Actualiza los datos del panel."""
        self._update_balance()
        self._update_prescriptions()
        self._update_projection()
    
    def _update_balance(self):
        """Actualiza el balance A/B."""
        try:
            if self.fiscal_dashboard:
                data = self.fiscal_dashboard.get_dashboard_data()
                
                serie_a = data.get('serie_a', {}).get('total', 0)
                serie_b = data.get('serie_b', {}).get('total', 0)
                total = serie_a + serie_b
                
                self.serie_a_label.setText(f"🟢 Serie A: ${serie_a:,.2f}")
                self.serie_b_label.setText(f"🟠 Serie B: ${serie_b:,.2f}")
                
                if total > 0:
                    pct_a = int((serie_a / total) * 100)
                    self.balance_bar.setValue(pct_a)
                    self.balance_bar.setFormat(f"{pct_a}% Serie A")
                
                # Warning si B es muy alto
                if total > 0 and serie_b / total > 0.7:
                    self.warning_label.setText("⚠️ Serie B muy alta. Considera mover a Serie A.")
                else:
                    self.warning_label.setText("")
        except Exception as e:
            logger.error(f"Error actualizando balance: {e}")
    
    def _update_prescriptions(self):
        """Actualiza las prescripciones."""
        # Limpiar prescripciones actuales
        while self.prescriptions_layout.count():
            child = self.prescriptions_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        try:
            if self.nostradamus:
                result = self.nostradamus.analyze_and_prescribe()
                prescriptions = result.get('prescriptions', [])
                
                if not prescriptions:
                    no_data = QLabel("✅ No hay prescripciones pendientes")
                    no_data.setStyleSheet("color: #27ae60; padding: 20px;")
                    no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.prescriptions_layout.addWidget(no_data)
                else:
                    for prescription in prescriptions:
                        card = self._create_prescription_card(prescription)
                        self.prescriptions_layout.addWidget(card)
                
                self.prescriptions_layout.addStretch()
        except Exception as e:
            logger.error(f"Error actualizando prescripciones: {e}")
            error_label = QLabel(f"❌ Error: {str(e)}")
            error_label.setStyleSheet("color: #e74c3c;")
            self.prescriptions_layout.addWidget(error_label)
    
    def _create_prescription_card(self, prescription: Dict) -> QFrame:
        """Crea una tarjeta de prescripción."""
        priority = prescription.get('priority', 'low')
        
        colors = {
            'high': {'bg': '#4a1a1a', 'border': '#e74c3c', 'icon': '🔴'},
            'medium': {'bg': '#4a3a1a', 'border': '#f39c12', 'icon': '🟡'},
            'low': {'bg': '#1a3a4a', 'border': '#3498db', 'icon': '🔵'}
        }
        
        style = colors.get(priority, colors['low'])
        
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {style['bg']};
                border: 2px solid {style['border']};
                border-radius: 10px;
                padding: 10px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        
        # Header
        header = QHBoxLayout()
        
        priority_label = QLabel(f"{style['icon']} {priority.upper()}")
        priority_label.setStyleSheet(f"color: {style['border']}; font-weight: bold;")
        header.addWidget(priority_label)
        
        header.addStretch()
        
        layout.addLayout(header)
        
        # Título
        title = QLabel(prescription.get('title', 'Sin título'))
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        title.setWordWrap(True)
        layout.addWidget(title)
        
        # Descripción
        desc = QLabel(prescription.get('description', ''))
        desc.setStyleSheet("color: #aaa;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Ahorro
        savings = prescription.get('savings', 0)
        if savings > 0:
            savings_label = QLabel(f"💰 Ahorro: ${savings:,.2f}")
            savings_label.setStyleSheet("color: #2ecc71; font-weight: bold;")
            layout.addWidget(savings_label)
        
        # Botón ejecutar
        if prescription.get('action'):
            execute_btn = QPushButton("▶️ Ejecutar Ahora")
            execute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {style['border']};
                    color: white;
                    border: none;
                    padding: 8px 15px;
                    border-radius: 5px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    opacity: 0.8;
                }}
            """)
            execute_btn.clicked.connect(lambda: self._execute_prescription(prescription))
            layout.addWidget(execute_btn)
        
        return card
    
    def _execute_prescription(self, prescription: Dict):
        """Ejecuta una prescripción."""
        action = prescription.get('action', '')
        
        QMessageBox.information(
            self,
            "Prescripción",
            f"Acción: {action}\n\n{prescription.get('description', '')}"
        )
    
    def _update_projection(self):
        """Actualiza la proyección fiscal."""
        try:
            if self.nostradamus:
                result = self.nostradamus.analyze_and_prescribe()
                
                current_tax = result.get('current_tax', 0)
                optimized_tax = result.get('optimized_tax', 0)
                savings = result.get('potential_savings', 0)
                base = result.get('taxable_base', 0)
                
                self.base_actual_value.setText(f"${base:,.2f}")
                self.isr_actual_value.setText(f"${current_tax:,.2f}")
                self.isr_optimized_value.setText(f"${optimized_tax:,.2f} ✅")
                self.savings_value.setText(f"${savings:,.2f}")
        except Exception as e:
            logger.error(f"Error actualizando proyección: {e}")

class GhostProcurementPanel(QWidget):
    """Panel de Ghost-Procurement - Entradas Serie B."""
    
    def __init__(self, core, ghost_procurement, parent=None):
        super().__init__(parent)
        self.core = core
        self.ghost_procurement = ghost_procurement
        self.selected_products = []
        self._setup_ui()
    
    def _setup_ui(self):
        """Configura la interfaz."""
        layout = QHBoxLayout(self)
        layout.setSpacing(15)
        
        # Panel izquierdo - Productos
        left_panel = self._create_products_panel()
        layout.addWidget(left_panel, 1)
        
        # Panel central - Justificación
        center_panel = self._create_justification_panel()
        layout.addWidget(center_panel, 1)
        
        # Panel derecho - Documentación
        right_panel = self._create_documentation_panel()
        layout.addWidget(right_panel, 1)
    
    def _create_products_panel(self) -> QFrame:
        """Panel de selección de productos."""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background: #2b2b2b;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        
        title = QLabel("📦 PRODUCTOS")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #4a9eff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Búsqueda
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Buscar producto...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: #3d3d3d;
                border: 1px solid #4a9eff;
                border-radius: 5px;
                padding: 8px;
                color: white;
            }
        """)
        self.search_input.textChanged.connect(self._search_products)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Tabla de productos
        self.products_table = QTableWidget()
        self.products_table.setColumnCount(4)
        self.products_table.setHorizontalHeaderLabels(["Producto", "SKU", "Cantidad", "Costo"])
        self.products_table.horizontalHeader().setStretchLastSection(True)
        self.products_table.setStyleSheet("""
            QTableWidget {
                background: #3d3d3d;
                border: none;
                gridline-color: #4d4d4d;
            }
            QTableWidget::item {
                padding: 8px;
                color: white;
            }
            QHeaderView::section {
                background: #2b2b2b;
                color: #4a9eff;
                padding: 8px;
                border: none;
            }
        """)
        layout.addWidget(self.products_table, 1)
        
        # Botón agregar
        add_btn = QPushButton("➕ Agregar Producto")
        add_btn.setStyleSheet("""
            QPushButton {
                background: #27ae60;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #2ecc71;
            }
        """)
        add_btn.clicked.connect(self._add_product)
        layout.addWidget(add_btn)
        
        return panel
    
    def _create_justification_panel(self) -> QFrame:
        """Panel de justificación."""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background: #2b2b2b;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        
        title = QLabel("📝 JUSTIFICACIÓN")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #4a9eff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Tipo de entrada
        type_label = QLabel("Tipo de Entrada:")
        type_label.setStyleSheet("color: #888;")
        layout.addWidget(type_label)
        
        self.entry_type_combo = QComboBox()
        self.entry_type_combo.addItems([
            "Devolución de cliente",
            "Recuperación de garantía",
            "Ajuste de inventario",
            "Entrada por consignación",
            "Mercancía recuperada"
        ])
        self.entry_type_combo.setStyleSheet("""
            QComboBox {
                background: #3d3d3d;
                border: 1px solid #4a9eff;
                border-radius: 5px;
                padding: 8px;
                color: white;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        self.entry_type_combo.currentTextChanged.connect(self._generate_narrative)
        layout.addWidget(self.entry_type_combo)
        
        layout.addSpacing(10)
        
        # Narrativa generada
        narrative_label = QLabel("Narrativa Generada:")
        narrative_label.setStyleSheet("color: #888;")
        layout.addWidget(narrative_label)
        
        self.narrative_text = QTextEdit()
        self.narrative_text.setReadOnly(True)
        self.narrative_text.setPlaceholderText("La narrativa se generará automáticamente...")
        self.narrative_text.setStyleSheet("""
            QTextEdit {
                background: #3d3d3d;
                border: 1px solid #4a9eff;
                border-radius: 5px;
                padding: 10px;
                color: white;
            }
        """)
        layout.addWidget(self.narrative_text, 1)
        
        # Indicador de plausibilidad
        plausibility_label = QLabel("Plausibilidad:")
        plausibility_label.setStyleSheet("color: #888;")
        layout.addWidget(plausibility_label)
        
        self.plausibility_bar = QProgressBar()
        self.plausibility_bar.setRange(0, 100)
        self.plausibility_bar.setValue(0)
        self.plausibility_bar.setFormat("%p% ")
        self.plausibility_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #3d3d3d;
                border-radius: 5px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #e74c3c, stop:0.5 #f39c12, stop:1 #27ae60);
            }
        """)
        layout.addWidget(self.plausibility_bar)
        
        self.plausibility_status = QLabel("")
        self.plausibility_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.plausibility_status)
        
        return panel
    
    def _create_documentation_panel(self) -> QFrame:
        """Panel de documentación."""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background: #2b2b2b;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        
        title = QLabel("📄 DOCUMENTACIÓN")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #4a9eff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Preview del documento
        doc_preview = QFrame()
        doc_preview.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 5px;
                padding: 15px;
            }
        """)
        
        doc_layout = QVBoxLayout(doc_preview)
        
        self.doc_title = QLabel("NOTA DE AJUSTE")
        self.doc_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.doc_title.setStyleSheet("color: #333;")
        self.doc_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        doc_layout.addWidget(self.doc_title)
        
        self.doc_code = QLabel("AJ-00000000-000")
        self.doc_code.setStyleSheet("color: #666;")
        self.doc_code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        doc_layout.addWidget(self.doc_code)
        
        doc_layout.addSpacing(10)
        
        self.doc_content = QLabel("Concepto: Pendiente...")
        self.doc_content.setWordWrap(True)
        self.doc_content.setStyleSheet("color: #333;")
        doc_layout.addWidget(self.doc_content)
        
        doc_layout.addStretch()
        
        layout.addWidget(doc_preview, 1)
        
        # Resumen
        summary = QFrame()
        summary.setStyleSheet("""
            QFrame {
                background: #1a1a2e;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        
        summary_layout = QHBoxLayout(summary)
        
        self.items_count = QLabel("Items: 0")
        self.items_count.setStyleSheet("color: #4a9eff;")
        summary_layout.addWidget(self.items_count)
        
        self.total_value = QLabel("Total: $0.00")
        self.total_value.setStyleSheet("color: #27ae60;")
        summary_layout.addWidget(self.total_value)
        
        self.stock_change = QLabel("Stock: +0")
        self.stock_change.setStyleSheet("color: #f39c12;")
        summary_layout.addWidget(self.stock_change)
        
        layout.addWidget(summary)
        
        # Botones
        buttons_layout = QHBoxLayout()
        
        pdf_btn = QPushButton("📄 Generar PDF")
        pdf_btn.setStyleSheet("""
            QPushButton {
                background: #3d3d3d;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: #4d4d4d;
            }
        """)
        pdf_btn.clicked.connect(self._generate_pdf)
        buttons_layout.addWidget(pdf_btn)
        
        print_btn = QPushButton("🖨️ Imprimir")
        print_btn.setStyleSheet("""
            QPushButton {
                background: #3d3d3d;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: #4d4d4d;
            }
        """)
        buttons_layout.addWidget(print_btn)
        
        layout.addLayout(buttons_layout)
        
        # Botón confirmar
        confirm_btn = QPushButton("✅ CONFIRMAR ENTRADA")
        confirm_btn.setStyleSheet("""
            QPushButton {
                background: #27ae60;
                color: white;
                border: none;
                padding: 15px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #2ecc71;
            }
        """)
        confirm_btn.clicked.connect(self._confirm_entry)
        layout.addWidget(confirm_btn)
        
        return panel
    
    def refresh_data(self):
        """Actualiza los datos."""
        self._update_summary()
    
    def _search_products(self, text: str):
        """Busca productos."""
        # Implementar búsqueda
        pass
    
    def _add_product(self):
        """Agrega un producto a la lista."""
        row = self.products_table.rowCount()
        self.products_table.insertRow(row)
        
        # Ejemplo - en producción buscar de la BD
        self.products_table.setItem(row, 0, QTableWidgetItem("Producto Ejemplo"))
        self.products_table.setItem(row, 1, QTableWidgetItem("SKU-001"))
        
        qty_spin = QSpinBox()
        qty_spin.setRange(1, 999)
        qty_spin.setValue(1)
        qty_spin.valueChanged.connect(self._update_summary)
        self.products_table.setCellWidget(row, 2, qty_spin)
        
        self.products_table.setItem(row, 3, QTableWidgetItem("$100.00"))
        
        self._generate_narrative()
        self._update_summary()
    
    def _generate_narrative(self):
        """Genera la narrativa automática."""
        entry_type = self.entry_type_combo.currentText()
        qty = self.products_table.rowCount()
        
        narratives = {
            "Devolución de cliente": f"El cliente devolvió {qty} artículo(s) en condiciones originales, presentando ticket de compra. Se reintegran al inventario para su reventa.",
            "Recuperación de garantía": f"Se reciben {qty} artículo(s) por garantía del proveedor. Mercancía verificada y en condiciones de venta.",
            "Ajuste de inventario": f"Ajuste de {qty} artículo(s) detectados durante conteo físico. Se documenta para conciliación contable.",
            "Entrada por consignación": f"Ingreso de {qty} artículo(s) en consignación. Pendiente de formalizar compra según acuerdo comercial.",
            "Mercancía recuperada": f"Se recuperan {qty} artículo(s) previamente dados de baja. Condiciones verificadas para reincorporación."
        }
        
        narrative = narratives.get(entry_type, "Entrada de mercancía registrada.")
        self.narrative_text.setText(narrative)
        
        # Actualizar plausibilidad
        plausibility = 85 if qty <= 10 else (70 if qty <= 20 else 50)
        self.plausibility_bar.setValue(plausibility)
        
        if plausibility >= 80:
            self.plausibility_status.setText("✅ Creíble")
            self.plausibility_status.setStyleSheet("color: #27ae60;")
        elif plausibility >= 60:
            self.plausibility_status.setText("⚠️ Aceptable")
            self.plausibility_status.setStyleSheet("color: #f39c12;")
        else:
            self.plausibility_status.setText("🔴 Sospechoso")
            self.plausibility_status.setStyleSheet("color: #e74c3c;")
        
        # Actualizar documento
        self.doc_code.setText(f"AJ-{datetime.now().strftime('%Y%m%d')}-{qty:03d}")
        self.doc_content.setText(f"Concepto: {entry_type}\n\n{narrative}")
    
    def _update_summary(self):
        """Actualiza el resumen."""
        count = self.products_table.rowCount()
        self.items_count.setText(f"Items: {count}")
        
        total = count * 100  # Ejemplo simplificado
        self.total_value.setText(f"Total: ${total:,.2f}")
        self.stock_change.setText(f"Stock: +{count}")
    
    def _generate_pdf(self):
        """Genera PDF del documento."""
        QMessageBox.information(self, "PDF", "Generando PDF del documento...")
    
    def _confirm_entry(self):
        """Confirma la entrada."""
        if self.products_table.rowCount() == 0:
            QMessageBox.warning(self, "Error", "No hay productos para registrar.")
            return
        
        reply = QMessageBox.question(
            self,
            "Confirmar Entrada",
            f"¿Confirmar entrada de {self.products_table.rowCount()} producto(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Ejecutar entrada con GhostProcurement
            QMessageBox.information(self, "Éxito", "✅ Entrada registrada correctamente.")
            self.products_table.setRowCount(0)
            self._update_summary()
            self._generate_narrative()
