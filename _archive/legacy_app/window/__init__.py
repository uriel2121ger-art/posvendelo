"""
TITAN POS - Window Module

Main application window, navigation, and UI components.
"""

# Import with error handling - modules may not exist in all installations
# CRITICAL: Import server_manager FIRST (it's the most important and has fewer dependencies)
try:
    from .server_manager import EmbeddedServerManager
except (ImportError, AttributeError) as e:
    EmbeddedServerManager = None
    # Log error if logging is available
    try:
        import logging
        _logger = logging.getLogger(__name__)
        _logger.warning(f"Could not import EmbeddedServerManager: {e}")
    except Exception:
        pass

# Try to import POSWindow from app.main (it's actually there, not in app.window.main_window)
try:
    from app.main import POSWindow
except (ImportError, AttributeError):
    POSWindow = None

try:
    from .navigation import NavigationBar, ShortcutManager
except (ImportError, AttributeError):
    NavigationBar = None
    ShortcutManager = None

__all__ = [
    "POSWindow",
    "NavigationBar",
    "ShortcutManager",
    "EmbeddedServerManager",
]
