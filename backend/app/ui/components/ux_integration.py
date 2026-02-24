"""
UX Integration Module - TITAN POS
Módulo de integración para aplicar todas las mejoras UX a la interfaz existente.

Este módulo proporciona funciones de alto nivel para:
1. Integrar el sistema de toasts
2. Configurar tooltips ricos
3. Agregar atajos visibles a botones
4. Integrar el panel de atajos (F1)
5. Agregar la barra de estado
6. Activar animaciones

USO:
    from app.ui.components.ux_integration import UXIntegrator
    
    # En el __init__ del MainWindow:
    self.ux = UXIntegrator(self, self.core)
    self.ux.integrate_all()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional
import logging

from PyQt6 import QtCore, QtGui, QtWidgets

from .animations import CartAnimations, SaleCompletedOverlay
from .rich_tooltips import RichTooltips, apply_rich_tooltips, apply_tooltip_stylesheet
from .shortcut_button import update_button_with_shortcut
from .shortcuts_panel import ShortcutsPanel
from .status_bar import StatusBar
from .toast import ToastManager

if TYPE_CHECKING:
    from app.core import POSCore

logger = logging.getLogger(__name__)

class UXIntegrator:
    """
    Integrador de mejoras UX para la aplicación.
    
    Centraliza la configuración y aplicación de todas las mejoras
    de experiencia de usuario.
    """
    
    # Mapeo de botones a sus atajos para mostrar visiblemente
    BUTTON_SHORTCUTS = {
        "charge_btn": "F12",
        "search_btn": "F10",
        "price_checker_btn": "F9",
        "mayoreo_btn": "F11",
        "common_product_btn": "Ctrl+P",
        "discount_btn": "Ctrl+D",
        "cash_in_btn": "F7",
        "cash_out_btn": "F8",
        "pending_btn": "F6",
        "note_btn": "F4",
    }
    
    def __init__(
        self,
        main_window: QtWidgets.QMainWindow,
        core: Optional['POSCore'] = None,
    ):
        """
        Inicializa el integrador.
        
        Args:
            main_window: Ventana principal de la aplicación
            core: Instancia de POSCore para acceder al estado
        """
        self.main_window = main_window
        self.core = core
        
        # Componentes UX
        self.shortcuts_panel: Optional[ShortcutsPanel] = None
        self.status_bar: Optional[StatusBar] = None
        self.sale_overlay: Optional[SaleCompletedOverlay] = None
        
        # Estado
        self._integrated = False
    
    def integrate_all(self):
        """
        Aplica todas las mejoras UX de una vez.
        
        Incluye:
        - Tooltips ricos globales
        - Panel de atajos (F1)
        - Barra de estado
        - Atajos visibles en botones
        """
        if self._integrated:
            logger.warning("UX ya integrado, saltando...")
            return
        
        try:
            self.setup_tooltip_style()
            self.setup_shortcuts_panel()
            self.setup_status_bar()
            self._integrated = True
            logger.info("✅ Mejoras UX integradas exitosamente")
        except Exception as e:
            logger.error(f"❌ Error integrando UX: {e}")
    
    def setup_tooltip_style(self):
        """Aplica el estilo oscuro global para tooltips."""
        app = QtWidgets.QApplication.instance()
        if app:
            apply_tooltip_stylesheet(app)
            logger.debug("Estilo de tooltips aplicado")
    
    def setup_shortcuts_panel(self):
        """Configura el panel de atajos (F1)."""
        # Crear panel
        self.shortcuts_panel = ShortcutsPanel(self.main_window)
        
        # Atajo F1 para toggle
        f1_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_F1),
            self.main_window
        )
        f1_shortcut.activated.connect(self.toggle_shortcuts_panel)
        f1_shortcut.setContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
        
        # Guardar referencia
        self.main_window._f1_shortcut = f1_shortcut
        
        logger.debug("Panel de atajos configurado (F1)")
    
    def toggle_shortcuts_panel(self):
        """Alterna visibilidad del panel de atajos."""
        if self.shortcuts_panel:
            self.shortcuts_panel.toggle()
    
    def setup_status_bar(self):
        """Configura la barra de estado."""
        self.status_bar = StatusBar(self.main_window)
        
        # Conectar señales
        self.status_bar.clicked_connection.connect(self._on_connection_clicked)
        self.status_bar.clicked_user.connect(self._on_user_clicked)
        self.status_bar.clicked_branch.connect(self._on_branch_clicked)
        self.status_bar.clicked_turn.connect(self._on_turn_clicked)
        self.status_bar.clicked_sales.connect(self._on_sales_clicked)
        
        # Agregar al layout principal si es QMainWindow
        if hasattr(self.main_window, 'statusBar'):
            # Reemplazar status bar nativo
            old_status = self.main_window.statusBar()
            if old_status:
                old_status.hide()
        
        # Buscar layout principal y agregar al final
        central = self.main_window.centralWidget()
        if central and central.layout():
            central.layout().addWidget(self.status_bar)
        
        # Actualizar con estado inicial
        self.refresh_status_bar()
        
        logger.debug("Barra de estado configurada")
    
    def refresh_status_bar(self):
        """Actualiza la barra de estado con el estado actual."""
        if not self.status_bar or not self.core:
            return
        
        try:
            from app.core import STATE

            # Usuario
            if STATE.user_id:
                user = self.core.get_user_by_id(STATE.user_id) if hasattr(self.core, 'get_user_by_id') else None
                if user:
                    self.status_bar.update_user(
                        user.get('name', 'Usuario'),
                        user.get('role', 'Cajero')
                    )
            
            # Sucursal
            if STATE.branch_id:
                branch = self.core.get_branch(STATE.branch_id) if hasattr(self.core, 'get_branch') else None
                if branch:
                    self.status_bar.update_branch(
                        branch.get('name', 'Sucursal'),
                        STATE.branch_id
                    )
            
            # Turno
            if STATE.turn_id:
                self.status_bar.update_turn(STATE.turn_id, True)
                
                # Ventas del turno
                if hasattr(self.core, 'get_turn_summary'):
                    summary = self.core.get_turn_summary(STATE.turn_id)
                    if summary:
                        self.status_bar.update_sales(
                            summary.get('total_sales', 0),
                            summary.get('transactions', 0)
                        )
            else:
                self.status_bar.update_turn(None, False)
            
            # Conexión (asume online por defecto)
            self.status_bar.update_connection('online')
            
        except Exception as e:
            logger.warning(f"Error actualizando status bar: {e}")
    
    def _on_connection_clicked(self):
        """Handler para click en indicador de conexión.

        TODO [LOW]: Mostrar diálogo de estado de conexión con detalles
        de latencia, servidor conectado, y opciones de reconexión.
        """
        logger.warning("_on_connection_clicked no implementado - funcionalidad pendiente")
    
    def _on_user_clicked(self):
        """Handler para click en indicador de usuario."""
        # Emitir señal para cambiar usuario si existe
        if hasattr(self.main_window, 'request_user_change'):
            self.main_window.request_user_change.emit()
    
    def _on_branch_clicked(self):
        """Handler para click en indicador de sucursal.

        TODO [LOW]: Mostrar diálogo con información detallada de la sucursal
        incluyendo dirección, teléfono, horarios y configuración fiscal.
        """
        logger.warning("_on_branch_clicked no implementado - funcionalidad pendiente")
    
    def _on_turn_clicked(self):
        """Handler para click en indicador de turno."""
        # Cambiar a tab de turnos si existe
        if hasattr(self.main_window, 'show_turn_tab'):
            self.main_window.show_turn_tab()
    
    def _on_sales_clicked(self):
        """Handler para click en indicador de ventas."""
        # Mostrar resumen rápido del turno
        if hasattr(self.main_window, 'show_turn_summary'):
            self.main_window.show_turn_summary()
    
    # === Métodos de utilidad para uso en otros módulos ===
    
    def apply_tooltips_to_widget(self, widget: QtWidgets.QWidget, tooltips_map: Dict[str, str]):
        """
        Aplica tooltips ricos a los widgets de un contenedor.
        
        Args:
            widget: Widget contenedor
            tooltips_map: Dict de {nombre_atributo: tooltip_key}
        """
        for attr_name, tooltip_key in tooltips_map.items():
            target = getattr(widget, attr_name, None)
            if target:
                RichTooltips.apply(target, tooltip_key)
    
    def add_shortcuts_to_buttons(self, widget: QtWidgets.QWidget):
        """
        Agrega atajos visibles a los botones de un widget.
        
        Busca botones que tengan nombres en BUTTON_SHORTCUTS y
        les agrega el texto del atajo.
        """
        for attr_name, shortcut in self.BUTTON_SHORTCUTS.items():
            btn = getattr(widget, attr_name, None)
            if btn and isinstance(btn, QtWidgets.QPushButton):
                update_button_with_shortcut(btn, shortcut)
    
    def show_sale_completed(
        self,
        amount: float,
        change: Optional[float] = None,
        ticket_id: Optional[int] = None,
    ):
        """
        Muestra la animación de venta completada.
        
        Args:
            amount: Monto total
            change: Cambio (opcional)
            ticket_id: ID del ticket (opcional)
        """
        if self.sale_overlay is None:
            self.sale_overlay = SaleCompletedOverlay(self.main_window)
        
        self.sale_overlay.play(amount, change, ticket_id)
        
        # Actualizar status bar después de la animación
        if self.status_bar:
            QtCore.QTimer.singleShot(2500, self.refresh_status_bar)
    
    # === Métodos estáticos para uso directo ===
    
    @staticmethod
    def show_success(title: str, message: str, parent: Optional[QtWidgets.QWidget] = None):
        """Muestra toast de éxito."""
        return ToastManager.success(title, message, parent)
    
    @staticmethod
    def show_error(title: str, message: str, parent: Optional[QtWidgets.QWidget] = None):
        """Muestra toast de error."""
        return ToastManager.error(title, message, parent=parent)
    
    @staticmethod
    def show_warning(title: str, message: str, parent: Optional[QtWidgets.QWidget] = None):
        """Muestra toast de advertencia."""
        return ToastManager.warning(title, message, parent=parent)
    
    @staticmethod
    def show_info(title: str, message: str, parent: Optional[QtWidgets.QWidget] = None):
        """Muestra toast informativo."""
        return ToastManager.info(title, message, parent)

def integrate_ux_to_sales_tab(sales_tab):
    """
    Función de conveniencia para integrar mejoras UX al SalesTab existente.
    
    Uso:
        from app.ui.components.ux_integration import integrate_ux_to_sales_tab
        integrate_ux_to_sales_tab(self)  # En __init__ de SalesTab
    """
    try:
        # 1. Aplicar tooltips ricos
        tooltips_map = {
            'charge_btn': 'charge_btn',
            'add_btn': 'add_btn',
            'discount_btn': 'discount_btn',
            'layaway_btn': 'layaway_btn',
            'cash_in_btn': 'cash_in_btn',
            'cash_out_btn': 'cash_out_btn',
            'pending_btn': 'pending_btn',
        }
        
        for attr, key in tooltips_map.items():
            widget = getattr(sales_tab, attr, None)
            if widget:
                RichTooltips.apply(widget, key)
        
        # 2. Agregar atajos visibles a botones principales
        button_shortcuts = {
            'charge_btn': 'F12',
            'discount_btn': 'Ctrl+D',
            'cash_in_btn': 'F7',
            'cash_out_btn': 'F8',
        }
        
        for attr, shortcut in button_shortcuts.items():
            btn = getattr(sales_tab, attr, None)
            if btn and isinstance(btn, QtWidgets.QPushButton):
                current = btn.text()
                if shortcut not in current:
                    btn.setText(f"{current} [{shortcut}]")
        
        # 3. Configurar animaciones del carrito
        if hasattr(sales_tab, 'table'):
            sales_tab._cart_animations = CartAnimations()
        
        logger.info("✅ UX integrado a SalesTab")
        
    except Exception as e:
        logger.warning(f"Error integrando UX a SalesTab: {e}")
