"""
TITAN POS - Navigation Module

Navigation bar and keyboard shortcuts management.
"""

from typing import Callable, List, Optional, Tuple
import logging

from PyQt6 import QtCore, QtGui, QtWidgets

from app.startup.bootstrap import ICON_DIR

logger = logging.getLogger(__name__)


class NavigationBar(QtWidgets.QWidget):
    """
    Custom navigation bar for the POS application.

    Provides styled navigation buttons and integrates with tab navigation.
    """

    # Signal emitted when a nav button is clicked (index)
    tab_requested = QtCore.pyqtSignal(int)
    # Signal emitted when exit is requested
    exit_requested = QtCore.pyqtSignal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize the navigation bar."""
        super().__init__(parent)
        self.setObjectName("NavBar")
        self._buttons: dict[str, QtWidgets.QToolButton] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the navigation bar UI."""
        self.setStyleSheet("""
            QWidget#NavBar {
                background: palette(window);
                border-bottom: 1px solid palette(mid);
            }
            QToolButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
                color: palette(window-text);
                font-size: 12px;
            }
            QToolButton:hover {
                background: palette(midlight);
                border: 1px solid palette(mid);
            }
            QToolButton:pressed {
                background: palette(dark);
                border: 1px solid palette(shadow);
                padding-top: 9px;
                padding-left: 9px;
            }
        """)

        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(5, 5, 5, 5)
        self._layout.setSpacing(5)

    def add_button(
        self,
        name: str,
        text: str,
        icon_name: str,
        index: Optional[int] = None,
        callback: Optional[Callable] = None
    ) -> QtWidgets.QToolButton:
        """
        Add a navigation button.

        Args:
            name: Internal name for the button
            text: Display text
            icon_name: Icon filename in ICON_DIR
            index: Tab index to navigate to when clicked
            callback: Optional callback function

        Returns:
            The created QToolButton
        """
        btn = QtWidgets.QToolButton()
        btn.setText(text)
        btn.setIcon(QtGui.QIcon(str(ICON_DIR / icon_name)))
        btn.setIconSize(QtCore.QSize(32, 32))
        btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        if index is not None:
            btn.clicked.connect(lambda: self.tab_requested.emit(index))
        if callback:
            btn.clicked.connect(callback)

        self._layout.addWidget(btn)
        self._buttons[name] = btn
        return btn

    def add_stretch(self) -> None:
        """Add a stretch spacer."""
        self._layout.addStretch()

    def add_exit_button(self, text: str = "Exit", icon_name: str = "exit.png") -> QtWidgets.QToolButton:
        """Add exit button at the end."""
        btn = self.add_button("exit", text, icon_name)
        btn.clicked.connect(self.exit_requested.emit)
        return btn

    def get_button(self, name: str) -> Optional[QtWidgets.QToolButton]:
        """Get a button by name."""
        return self._buttons.get(name)

    def hide_button(self, name: str) -> None:
        """Hide a button by name."""
        if name in self._buttons:
            self._buttons[name].hide()

    def show_button(self, name: str) -> None:
        """Show a button by name."""
        if name in self._buttons:
            self._buttons[name].show()

    def refresh_style(self) -> None:
        """Refresh button styles after theme change."""
        self.style().unpolish(self)
        self.style().polish(self)


class ShortcutManager:
    """
    Manages global keyboard shortcuts for the application.

    Centralizes shortcut creation and provides methods to enable/disable
    shortcuts based on context.
    """

    def __init__(self, parent: QtWidgets.QWidget):
        """
        Initialize the shortcut manager.

        Args:
            parent: Parent widget for shortcuts
        """
        self.parent = parent
        self._shortcuts: dict[str, QtGui.QShortcut] = {}

    def add_shortcut(
        self,
        name: str,
        key: str | QtCore.Qt.Key,
        callback: Callable,
        context: QtCore.Qt.ShortcutContext = QtCore.Qt.ShortcutContext.WindowShortcut
    ) -> QtGui.QShortcut:
        """
        Add a keyboard shortcut.

        Args:
            name: Internal name for the shortcut
            key: Key sequence (e.g., "F1", "Ctrl+N", or Qt.Key.Key_F1)
            callback: Function to call when shortcut is activated
            context: Shortcut context

        Returns:
            The created QShortcut
        """
        if isinstance(key, str):
            sequence = QtGui.QKeySequence(key)
        else:
            sequence = QtGui.QKeySequence(key)

        shortcut = QtGui.QShortcut(sequence, self.parent)
        shortcut.activated.connect(callback)
        shortcut.setContext(context)

        self._shortcuts[name] = shortcut
        return shortcut

    def get_shortcut(self, name: str) -> Optional[QtGui.QShortcut]:
        """Get a shortcut by name."""
        return self._shortcuts.get(name)

    def enable(self, name: str) -> None:
        """Enable a shortcut."""
        if name in self._shortcuts:
            self._shortcuts[name].setEnabled(True)

    def disable(self, name: str) -> None:
        """Disable a shortcut."""
        if name in self._shortcuts:
            self._shortcuts[name].setEnabled(False)

    def enable_all(self) -> None:
        """Enable all shortcuts."""
        for shortcut in self._shortcuts.values():
            shortcut.setEnabled(True)

    def disable_all(self) -> None:
        """Disable all shortcuts."""
        for shortcut in self._shortcuts.values():
            shortcut.setEnabled(False)

    def setup_function_keys(self, tab_widget: QtWidgets.QTabWidget) -> None:
        """
        Set up standard function key shortcuts.

        Args:
            tab_widget: QTabWidget to control
        """
        # F1: Sales
        self.add_shortcut("f1", QtCore.Qt.Key.Key_F1, lambda: tab_widget.setCurrentIndex(0))

        # F3: Products
        self.add_shortcut("f3", QtCore.Qt.Key.Key_F3, lambda: tab_widget.setCurrentIndex(1))

        # F4: Inventory
        self.add_shortcut("f4", QtCore.Qt.Key.Key_F4, lambda: tab_widget.setCurrentIndex(2))

        # F5: Turns
        self.add_shortcut("f5", QtCore.Qt.Key.Key_F5, lambda: tab_widget.setCurrentIndex(8))

        # F6: Employees
        self.add_shortcut("f6", QtCore.Qt.Key.Key_F6, lambda: tab_widget.setCurrentIndex(6))

    def handle_tab_change(self, tab_widget: QtWidgets.QWidget) -> None:
        """
        Adjust shortcuts based on active tab.

        Some shortcuts conflict with tab-specific functionality.

        Args:
            tab_widget: The currently active tab widget
        """
        # Disable F2 and F3 global shortcuts when in Products tab
        products_tab_class = "ProductsTab"
        is_products_tab = type(tab_widget).__name__ == products_tab_class

        if "f2" in self._shortcuts:
            self._shortcuts["f2"].setEnabled(not is_products_tab)

        if "f3" in self._shortcuts:
            self._shortcuts["f3"].setEnabled(not is_products_tab)
