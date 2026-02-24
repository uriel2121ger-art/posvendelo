from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette


class ThemeManager:
    def __init__(self):
        self.current_theme = "Light"
        
    def get_colors(self, theme_name=None):
        theme = theme_name or self.current_theme
        
        # Definición de paletas completas para satisfacer todas las dependencias de la UI
        if theme == "Dark":
            # === PALETA PREMIUM UNIFICADA ===
            # Inspirada en los tooltips con colores más ricos y consistentes
            return {
                # Fondos - Gradiente oscuro profesional
                "bg_main": "#1a1d23",       # Fondo principal (más oscuro)
                "bg_primary": "#1a1d23",    # Alias
                "bg_secondary": "#1e2128",  # Fondo secundario
                "bg_card": "#2a2f38",       # Tarjetas y paneles
                "bg_header": "#12151a",     # Header (el más oscuro)
                "bg_input": "#2a2d35",      # Fondos de inputs
                
                # Texto - Alta legibilidad
                "text_primary": "#e8eaed",  # Texto principal (casi blanco)
                "text_secondary": "#a0a4ab", # Texto secundario
                "text_header": "#ffffff",   # Texto de cabeceras
                "text_muted": "#6c7280",    # Texto deshabilitado
                
                # Colores de acento - Verde TITAN
                "accent": "#00C896",        # Verde principal (de los tooltips)
                "accent_hover": "#00E0A8",  # Verde hover
                "accent_dark": "#00a07a",   # Verde oscuro
                
                # Bordes
                "border": "#3a3f48",        # Borde principal
                "border_light": "#4a4f58",  # Borde más claro
                
                # Inputs
                "input_bg": "#2a2d35",
                "input_border": "#3a3f48",
                "input_focus": "#00C896",   # Verde al enfocar
                
                # Botones
                "btn_primary": "#00C896",   # Verde principal
                "btn_primary_hover": "#00E0A8",
                "btn_success": "#00C896",   # Verde éxito
                "btn_danger": "#FF4757",    # Rojo error
                "btn_warning": "#FFA502",   # Naranja advertencia
                "btn_info": "#3498db",      # Azul info
                "btn_disabled": "#4a4f58",
                
                "text_disabled": "#6c7280",
                
                # Tablas
                "table_header_bg": "#12151a",
                "table_header_text": "#00C896",
                "table_selected": "rgba(0, 200, 150, 0.2)",
                "table_text": "#e8eaed",
                "table_alternate": "#1e2128",
                
                # Estados
                "success": "#00C896",
                "warning": "#FFA502",
                "danger": "#FF4757",
                "info": "#3498db",
            }
        elif theme == "AMOLED":
            return {
                "bg_main": "#000000",
                "bg_primary": "#000000",
                "bg_secondary": "#121212",
                "bg_card": "#1e1e1e",
                "bg_header": "#121212",
                
                "text_primary": "#ffffff",
                "text_secondary": "#b0b0b0",
                "text_header": "#ffffff",
                
                "accent": "#ffffff",
                "border": "#333333",
                
                "input_bg": "#1e1e1e",
                "input_border": "#333333",
                "input_focus": "#ffffff",
                
                "btn_primary": "#333333",
                "btn_success": "#00ff00",
                "btn_danger": "#ff0000",
                "btn_warning": "#ffff00",
                "btn_disabled": "#444444",
                
                "text_disabled": "#666666",
                
                "table_header_bg": "#121212",
                "table_header_text": "#ffffff",
                "table_selected": "rgba(255, 255, 255, 0.2)",
                "table_text": "#ffffff",
                
                "success": "#00ff00",
                "warning": "#ffff00",
                "danger": "#ff0000"
            }
        elif theme == "Cyber Night":
            # === TEMA CYBER NIGHT ===
            # Tema oscuro futurista con acentos neón
            from app.ui.themes.colors import CyberNight
            return {
                "bg_main": CyberNight.BG_PRIMARY,
                "bg_primary": CyberNight.BG_PRIMARY,
                "bg_secondary": CyberNight.BG_SECONDARY,
                "bg_card": CyberNight.BG_CARD,
                "bg_header": CyberNight.BG_SECONDARY,
                "bg_input": CyberNight.BG_TERTIARY,
                
                "text_primary": CyberNight.TEXT_PRIMARY,
                "text_secondary": CyberNight.TEXT_SECONDARY,
                "text_header": CyberNight.TEXT_PRIMARY,
                "text_muted": CyberNight.TEXT_TERTIARY,
                
                "accent": CyberNight.ACCENT_PRIMARY,
                "accent_hover": CyberNight.ACCENT_PRIMARY_HOVER,
                "accent_dark": CyberNight.ACCENT_PRIMARY_DARK,
                
                "border": CyberNight.BORDER_DEFAULT,
                "border_light": CyberNight.BORDER_HOVER,
                
                "input_bg": CyberNight.BG_TERTIARY,
                "input_border": CyberNight.BORDER_DEFAULT,
                "input_focus": CyberNight.BORDER_FOCUS,
                
                "btn_primary": CyberNight.ACCENT_PRIMARY,
                "btn_primary_hover": CyberNight.ACCENT_PRIMARY_HOVER,
                "btn_success": CyberNight.ACCENT_SUCCESS,
                "btn_danger": CyberNight.ACCENT_DANGER,
                "btn_warning": CyberNight.ACCENT_WARNING,
                "btn_info": CyberNight.ACCENT_INFO,
                "btn_disabled": CyberNight.BG_SECONDARY,
                
                "text_disabled": CyberNight.TEXT_DISABLED,
                
                "table_header_bg": CyberNight.BG_SECONDARY,
                "table_header_text": CyberNight.ACCENT_PRIMARY,
                "table_selected": "rgba(0, 242, 255, 0.2)",
                "table_text": CyberNight.TEXT_PRIMARY,
                "table_alternate": CyberNight.BG_TERTIARY,
                
                "success": CyberNight.ACCENT_SUCCESS,
                "warning": CyberNight.ACCENT_WARNING,
                "danger": CyberNight.ACCENT_DANGER,
                "info": CyberNight.ACCENT_INFO,
            }
        elif theme == "Gray":
            # === TEMA GRIS INTERMEDIO ===
            # Balance entre oscuro y claro, ideal para iluminación moderada
            return {
                # Fondos - Escala de grises neutros
                "bg_main": "#3d4048",       # Gris oscuro base
                "bg_primary": "#3d4048",    # Alias
                "bg_secondary": "#4a4e57",  # Gris medio
                "bg_card": "#52565f",       # Tarjetas (más claro)
                "bg_header": "#32353c",     # Header (más oscuro)
                "bg_input": "#4a4e57",      # Fondos de inputs
                
                # Texto - Claro sobre gris
                "text_primary": "#f0f1f3",  # Texto principal
                "text_secondary": "#b8bcc4", # Texto secundario
                "text_header": "#ffffff",   # Texto de cabeceras
                "text_muted": "#8a8f9a",    # Texto deshabilitado
                
                # Colores de acento - Verde TITAN
                "accent": "#00C896",        # Verde principal
                "accent_hover": "#00E0A8",  # Verde hover
                "accent_dark": "#00a07a",   # Verde oscuro
                
                # Bordes
                "border": "#5a5e67",        # Borde principal
                "border_light": "#6a6e77",  # Borde más claro
                
                # Inputs
                "input_bg": "#4a4e57",
                "input_border": "#5a5e67",
                "input_focus": "#00C896",   # Verde al enfocar
                
                # Botones
                "btn_primary": "#00C896",   # Verde principal
                "btn_primary_hover": "#00E0A8",
                "btn_success": "#00C896",   # Verde éxito
                "btn_danger": "#FF4757",    # Rojo error
                "btn_warning": "#FFA502",   # Naranja advertencia
                "btn_info": "#3498db",      # Azul info
                "btn_disabled": "#6a6e77",
                
                "text_disabled": "#8a8f9a",
                
                # Tablas
                "table_header_bg": "#32353c",
                "table_header_text": "#00C896",
                "table_selected": "rgba(0, 200, 150, 0.25)",
                "table_text": "#f0f1f3",
                "table_alternate": "#454950",
                
                # Estados
                "success": "#00C896",
                "warning": "#FFA502",
                "danger": "#FF4757",
                "info": "#3498db",
            }
        else: # Light
            return {
                "bg_main": "#f5f5f5",
                "bg_primary": "#f5f5f5",
                "bg_secondary": "#ffffff",
                "bg_card": "#ffffff",
                "bg_header": "#ffffff",
                
                "text_primary": "#333333",
                "text_secondary": "#666666",
                "text_header": "#333333",
                
                "accent": "#3498db",
                "border": "#e0e0e0",
                
                "input_bg": "#ffffff",
                "input_border": "#cccccc",
                "input_focus": "#3498db",
                
                "btn_primary": "#3498db",
                "btn_success": "#27ae60",
                "btn_danger": "#c0392b",
                "btn_warning": "#f39c12",
                "btn_disabled": "#95a5a6",
                
                "text_disabled": "#7f8c8d",
                
                "table_header_bg": "#f0f0f0",
                "table_header_text": "#333333",
                "table_selected": "rgba(52, 152, 219, 0.2)",
                "table_text": "#333333",
                
                "success": "#27ae60",
                "warning": "#f39c12",
                "danger": "#c0392b"
            }
    
    def get_theme(self, theme_name=None):
        """Alias for get_colors for compatibility."""
        return self.get_colors(theme_name)
        
    def apply_theme(self, app, theme_name):
        self.current_theme = theme_name
        palette = QPalette()
        
        colors = self.get_colors(theme_name)
        
        if theme_name in ["Dark", "AMOLED", "Gray", "Cyber Night"]:
            palette.setColor(QPalette.ColorRole.Window, QColor(colors["bg_primary"]))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["text_primary"]))
            palette.setColor(QPalette.ColorRole.Base, QColor(colors["bg_secondary"]))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["bg_card"]))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#1e2128"))
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#e8eaed"))
            palette.setColor(QPalette.ColorRole.Text, QColor(colors["text_primary"]))
            palette.setColor(QPalette.ColorRole.Button, QColor(colors["bg_card"]))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text_primary"]))
            palette.setColor(QPalette.ColorRole.BrightText, QColor("#FF4757"))
            palette.setColor(QPalette.ColorRole.Link, QColor(colors["accent"]))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["accent"]))
            palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
            
            # === STYLESHEET GLOBAL PREMIUM ===
            global_stylesheet = f"""
                /* ===== TIPOGRAFÍA GLOBAL ===== */
                * {{
                    font-family: 'Segoe UI', 'SF Pro Display', 'Roboto', -apple-system, sans-serif;
                }}
                
                /* ===== SCROLLBARS MODERNAS ===== */
                QScrollBar:vertical {{
                    background: rgba(255, 255, 255, 0.03);
                    width: 10px;
                    border-radius: 5px;
                    margin: 0;
                }}
                QScrollBar::handle:vertical {{
                    background: rgba(0, 200, 150, 0.4);
                    border-radius: 5px;
                    min-height: 30px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background: rgba(0, 200, 150, 0.6);
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
                QScrollBar:horizontal {{
                    background: rgba(255, 255, 255, 0.03);
                    height: 10px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:horizontal {{
                    background: rgba(0, 200, 150, 0.4);
                    border-radius: 5px;
                    min-width: 30px;
                }}
                
                /* ===== TOOLTIPS PREMIUM ===== */
                QToolTip {{
                    background-color: #1e2128;
                    color: #e8eaed;
                    border: 1px solid #00C896;
                    border-radius: 8px;
                    padding: 8px 12px;
                    font-size: 12px;
                }}
                
                /* ===== MENÚS ===== */
                QMenu {{
                    background-color: {colors['bg_card']};
                    border: 1px solid {colors['border']};
                    border-radius: 8px;
                    padding: 8px 0;
                }}
                QMenu::item {{
                    padding: 8px 30px;
                    color: {colors['text_primary']};
                }}
                QMenu::item:selected {{
                    background-color: rgba(0, 200, 150, 0.2);
                    color: #00C896;
                }}
                QMenu::separator {{
                    height: 1px;
                    background: {colors['border']};
                    margin: 5px 15px;
                }}
                
                /* ===== COMBOBOX ===== */
                QComboBox {{
                    background: {colors['input_bg']};
                    border: 1px solid {colors['border']};
                    border-radius: 6px;
                    padding: 8px 12px;
                    color: {colors['text_primary']};
                    min-height: 20px;
                }}
                QComboBox:focus {{
                    border: 2px solid #00C896;
                }}
                QComboBox::drop-down {{
                    border: none;
                    width: 30px;
                }}
                QComboBox QAbstractItemView {{
                    background: {colors['bg_card']};
                    border: 1px solid {colors['border']};
                    selection-background-color: rgba(0, 200, 150, 0.2);
                }}
                
                /* ===== SPINBOX ===== */
                QSpinBox, QDoubleSpinBox {{
                    background: {colors['input_bg']};
                    border: 1px solid {colors['border']};
                    border-radius: 6px;
                    padding: 6px 10px;
                    color: {colors['text_primary']};
                }}
                QSpinBox:focus, QDoubleSpinBox:focus {{
                    border: 2px solid #00C896;
                }}
                
                /* ===== CHECKBOX & RADIO ===== */
                QCheckBox, QRadioButton {{
                    color: {colors['text_primary']};
                    spacing: 8px;
                }}
                QCheckBox::indicator, QRadioButton::indicator {{
                    width: 18px;
                    height: 18px;
                    border: 2px solid {colors['border']};
                    border-radius: 4px;
                    background: {colors['input_bg']};
                }}
                QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
                    background: #00C896;
                    border-color: #00C896;
                }}
                QRadioButton::indicator {{
                    border-radius: 9px;
                }}
                
                /* ===== GROUPBOX ===== */
                QGroupBox {{
                    color: {colors['text_primary']};
                    border: 1px solid {colors['border']};
                    border-radius: 8px;
                    margin-top: 12px;
                    padding-top: 10px;
                    font-weight: bold;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 15px;
                    padding: 0 8px;
                    color: #00C896;
                }}
                
                /* ===== TABWIDGET ===== */
                QTabWidget::pane {{
                    border: 1px solid {colors['border']};
                    background: {colors['bg_card']};
                    border-radius: 8px;
                }}
                QTabBar::tab {{
                    background: {colors['bg_secondary']};
                    color: {colors['text_secondary']};
                    padding: 10px 20px;
                    margin-right: 2px;
                    border-top-left-radius: 6px;
                    border-top-right-radius: 6px;
                }}
                QTabBar::tab:selected {{
                    background: #00C896;
                    color: white;
                }}
                QTabBar::tab:hover:!selected {{
                    background: {colors['border']};
                }}
                
                /* ===== PROGRESSBAR ===== */
                QProgressBar {{
                    background: {colors['input_bg']};
                    border: none;
                    border-radius: 4px;
                    height: 8px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #00C896, stop:1 #00E0A8);
                    border-radius: 4px;
                }}
                
                /* ===== SLIDER ===== */
                QSlider::groove:horizontal {{
                    height: 6px;
                    background: {colors['input_bg']};
                    border-radius: 3px;
                }}
                QSlider::handle:horizontal {{
                    background: #00C896;
                    width: 18px;
                    height: 18px;
                    margin: -6px 0;
                    border-radius: 9px;
                }}
                QSlider::handle:horizontal:hover {{
                    background: #00E0A8;
                }}
                
                /* ===== DIALOGS PREMIUM ===== */
                QDialog {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #2a2f38, stop:1 #1a1d23);
                    border: 1px solid #00C896;
                    border-radius: 16px;
                }}
                
                /* ===== MESSAGEBOX PREMIUM ===== */
                QMessageBox {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #2a2f38, stop:1 #1a1d23);
                    border: 2px solid #00C896;
                    border-radius: 16px;
                }}
                QMessageBox QLabel {{
                    color: #e8eaed;
                    font-size: 14px;
                    background: transparent;
                }}
                QMessageBox QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #00C896, stop:1 #00a07a);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 25px;
                    font-weight: bold;
                    font-size: 13px;
                    min-width: 80px;
                }}
                QMessageBox QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #00E0A8, stop:1 #00C896);
                }}
                QMessageBox QPushButton:pressed {{
                    background: #00a07a;
                }}
                
                /* ===== INPUTDIALOG PREMIUM ===== */
                QInputDialog {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #2a2f38, stop:1 #1a1d23);
                    border: 2px solid #00C896;
                    border-radius: 16px;
                }}
                
                /* ===== FRAMES / CARDS PREMIUM ===== */
                QFrame {{
                    background: transparent;
                }}
                QFrame[frameShape="4"], QFrame[frameShape="5"] {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #2a2f38, stop:1 #1e2128);
                    border: 1px solid {colors['border']};
                    border-radius: 12px;
                }}
                
                /* ===== LINEEDIT PREMIUM ===== */
                QLineEdit {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #2a2d35, stop:1 #22252b);
                    border: 1px solid {colors['border']};
                    border-radius: 10px;
                    padding: 10px 15px;
                    color: {colors['text_primary']};
                    font-size: 14px;
                    selection-background-color: rgba(0, 200, 150, 0.3);
                }}
                QLineEdit:focus {{
                    border: 2px solid #00C896;
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #2e3138, stop:1 #26292f);
                }}
                QLineEdit:disabled {{
                    background: {colors['bg_secondary']};
                    color: {colors['text_disabled']};
                }}
                
                /* ===== TEXTEDIT PREMIUM ===== */
                QTextEdit, QPlainTextEdit {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #2a2d35, stop:1 #1e2128);
                    border: 1px solid {colors['border']};
                    border-radius: 10px;
                    padding: 10px;
                    color: {colors['text_primary']};
                    selection-background-color: rgba(0, 200, 150, 0.3);
                }}
                QTextEdit:focus, QPlainTextEdit:focus {{
                    border: 2px solid #00C896;
                }}
                
                /* ===== PUSHBUTTON PREMIUM ===== */
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #3a3f48, stop:1 #2a2f38);
                    color: {colors['text_primary']};
                    border: 1px solid {colors['border']};
                    border-radius: 10px;
                    padding: 10px 20px;
                    font-weight: 600;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #4a4f58, stop:1 #3a3f48);
                    border-color: #00C896;
                }}
                QPushButton:pressed {{
                    background: #2a2f38;
                }}
                QPushButton:disabled {{
                    background: {colors['btn_disabled']};
                    color: {colors['text_disabled']};
                    border-color: {colors['border']};
                }}
                
                /* ===== TABLEWIDGET PREMIUM ===== */
                QTableWidget, QTableView {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1e2128, stop:1 #1a1d23);
                    alternate-background-color: #22252b;
                    border: 1px solid {colors['border']};
                    border-radius: 10px;
                    gridline-color: {colors['border']};
                    color: {colors['text_primary']};
                    selection-background-color: rgba(0, 200, 150, 0.25);
                    selection-color: white;
                }}
                QTableWidget::item, QTableView::item {{
                    padding: 8px 12px;
                    border-bottom: 1px solid rgba(58, 63, 72, 0.5);
                }}
                QTableWidget::item:selected, QTableView::item:selected {{
                    background: rgba(0, 200, 150, 0.25);
                    color: white;
                }}
                QTableWidget::item:hover, QTableView::item:hover {{
                    background: rgba(0, 200, 150, 0.1);
                }}
                QHeaderView::section {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #2a2f38, stop:1 #1e2128);
                    color: #00C896;
                    padding: 12px 15px;
                    border: none;
                    border-bottom: 2px solid #00C896;
                    font-weight: bold;
                    font-size: 12px;
                    text-transform: uppercase;
                }}
                QHeaderView::section:hover {{
                    background: #3a3f48;
                }}
                
                /* ===== LISTWIDGET PREMIUM ===== */
                QListWidget, QListView {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1e2128, stop:1 #1a1d23);
                    border: 1px solid {colors['border']};
                    border-radius: 10px;
                    padding: 5px;
                    color: {colors['text_primary']};
                }}
                QListWidget::item, QListView::item {{
                    padding: 10px 15px;
                    border-radius: 6px;
                    margin: 2px 0;
                }}
                QListWidget::item:selected, QListView::item:selected {{
                    background: rgba(0, 200, 150, 0.25);
                    color: white;
                }}
                QListWidget::item:hover, QListView::item:hover {{
                    background: rgba(0, 200, 150, 0.1);
                }}
                
                /* ===== TREEVIEW PREMIUM ===== */
                QTreeWidget, QTreeView {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1e2128, stop:1 #1a1d23);
                    border: 1px solid {colors['border']};
                    border-radius: 10px;
                    color: {colors['text_primary']};
                }}
                QTreeWidget::item, QTreeView::item {{
                    padding: 6px;
                }}
                QTreeWidget::item:selected, QTreeView::item:selected {{
                    background: rgba(0, 200, 150, 0.25);
                }}
                
                /* ===== LABELS PREMIUM ===== */
                QLabel {{
                    color: {colors['text_primary']};
                    background: transparent;
                }}
                
                /* ===== SPLITTER ===== */
                QSplitter::handle {{
                    background: {colors['border']};
                }}
                QSplitter::handle:hover {{
                    background: #00C896;
                }}
                
                /* ===== STATUSBAR ===== */
                QStatusBar {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1a1d23, stop:1 #12151a);
                    border-top: 1px solid {colors['border']};
                    color: {colors['text_secondary']};
                }}
                
                /* ===== TOOLBAR ===== */
                QToolBar {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #2a2f38, stop:1 #1e2128);
                    border: none;
                    spacing: 10px;
                    padding: 5px;
                }}
                QToolButton {{
                    background: transparent;
                    border: none;
                    border-radius: 6px;
                    padding: 8px;
                    color: {colors['text_primary']};
                }}
                QToolButton:hover {{
                    background: rgba(0, 200, 150, 0.2);
                }}
                QToolButton:pressed {{
                    background: rgba(0, 200, 150, 0.3);
                }}

                /* ===== DOCKWIDGET ===== */
                QDockWidget {{
                    color: {colors['text_primary']};
                    titlebar-close-icon: none;
                }}
                QDockWidget::title {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #2a2f38, stop:1 #1e2128);
                    padding: 10px;
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                }}
                
                /* ══════════════════════════════════════════════════════════
                   CALENDAR WIDGET - DISEÑO ULTRA PREMIUM
                   ══════════════════════════════════════════════════════════ */
                   
                QCalendarWidget {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #2a2f38, stop:1 #1a1d23);
                    border: 2px solid rgba(0, 200, 150, 0.6);
                    border-radius: 16px;
                    min-width: 320px;
                }}
                
                /* Contenedor general */
                QCalendarWidget QWidget {{
                    alternate-background-color: transparent;
                    background: transparent;
                }}
                
                /* ═══ BARRA DE NAVEGACIÓN DEL MES ═══ */
                QCalendarWidget QWidget#qt_calendar_navigationbar {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #12151a, stop:1 #1a1d23);
                    border-bottom: 1px solid rgba(0, 200, 150, 0.3);
                    padding: 10px 15px;
                    min-height: 50px;
                }}
                
                /* Botones de navegación (< >) */
                QCalendarWidget QToolButton {{
                    color: #e8eaed;
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #3a3f48, stop:1 #2a2f38);
                    border: 1px solid #4a4f58;
                    border-radius: 8px;
                    padding: 10px 16px;
                    font-weight: bold;
                    font-size: 14px;
                    margin: 3px;
                }}
                QCalendarWidget QToolButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #00C896, stop:1 #00a07a);
                    border-color: #00E0A8;
                    color: white;
                }}
                QCalendarWidget QToolButton:pressed {{
                    background: #00a07a;
                }}
                QCalendarWidget QToolButton#qt_calendar_prevmonth,
                QCalendarWidget QToolButton#qt_calendar_nextmonth {{
                    min-width: 40px;
                    qproperty-icon: none;
                }}
                QCalendarWidget QToolButton#qt_calendar_prevmonth {{
                    qproperty-text: "◀";
                }}
                QCalendarWidget QToolButton#qt_calendar_nextmonth {{
                    qproperty-text: "▶";
                }}
                QCalendarWidget QToolButton::menu-indicator {{
                    image: none;
                    width: 0;
                }}
                
                /* SpinBox del año */
                QCalendarWidget QSpinBox {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #2a2f38, stop:1 #22252b);
                    border: 1px solid #3a3f48;
                    border-radius: 8px;
                    color: #e8eaed;
                    padding: 8px 12px;
                    font-size: 14px;
                    font-weight: bold;
                    min-width: 80px;
                }}
                QCalendarWidget QSpinBox:focus {{
                    border: 2px solid #00C896;
                }}
                QCalendarWidget QSpinBox::up-button {{
                    background: transparent;
                    border: none;
                    width: 20px;
                }}
                QCalendarWidget QSpinBox::down-button {{
                    background: transparent;
                    border: none;
                    width: 20px;
                }}
                
                /* ═══ TABLA DE DÍAS ═══ */
                QCalendarWidget QTableView {{
                    background: transparent;
                    alternate-background-color: transparent;
                    selection-background-color: transparent;
                    outline: none;
                    border: none;
                    margin: 8px;
                    font-size: 13px;
                }}
                
                /* Headers de días (Lu, Ma, Mi...) */
                QCalendarWidget QTableView QHeaderView {{
                    background: transparent;
                }}
                QCalendarWidget QTableView QHeaderView::section {{
                    background: transparent;
                    color: #00C896;
                    font-weight: bold;
                    font-size: 11px;
                    text-transform: uppercase;
                    border: none;
                    padding: 8px 0;
                }}
                QCalendarWidget QTableView QHeaderView::section:vertical {{
                    background: transparent;
                    color: #5a5f68;
                    font-size: 10px;
                }}
                
                /* ═══ CELDAS DE DÍAS ═══ */
                QCalendarWidget QAbstractItemView:enabled {{
                    color: #e8eaed;
                    background: transparent;
                    font-size: 13px;
                    selection-background-color: #00C896;
                    selection-color: white;
                }}
                QCalendarWidget QAbstractItemView:disabled {{
                    color: #4a4f58;
                }}
                
                /* ═══ DATEEDIT / TIMEEDIT ═══ */
                QDateEdit, QTimeEdit, QDateTimeEdit {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #2a2d35, stop:1 #22252b);
                    border: 1px solid {colors['border']};
                    border-radius: 10px;
                    padding: 10px 15px;
                    color: {colors['text_primary']};
                    font-size: 14px;
                    min-height: 20px;
                }}
                QDateEdit:focus, QTimeEdit:focus, QDateTimeEdit:focus {{
                    border: 2px solid #00C896;
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #2e3138, stop:1 #26292f);
                }}
                QDateEdit::drop-down, QTimeEdit::drop-down, QDateTimeEdit::drop-down {{
                    border: none;
                    background: transparent;
                    width: 30px;
                    subcontrol-origin: padding;
                    subcontrol-position: center right;
                }}
                QDateEdit::down-arrow, QTimeEdit::down-arrow, QDateTimeEdit::down-arrow {{
                    width: 12px;
                    height: 12px;
                }}
            """
            app.setStyleSheet(global_stylesheet)
            
        else:  # Light theme
            palette.setColor(QPalette.ColorRole.Window, QColor(colors["bg_primary"]))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["text_primary"]))
            palette.setColor(QPalette.ColorRole.Base, QColor(colors["bg_secondary"]))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["bg_card"]))
            palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.black)
            palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorRole.Text, QColor(colors["text_primary"]))
            palette.setColor(QPalette.ColorRole.Button, QColor(colors["bg_secondary"]))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text_primary"]))
            palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
            palette.setColor(QPalette.ColorRole.Link, QColor(colors["accent"]))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["accent"]))
            palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
            
        app.setPalette(palette)

theme_manager = ThemeManager()
