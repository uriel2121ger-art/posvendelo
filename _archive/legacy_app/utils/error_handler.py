"""
TITAN POS - Error Handler

Centralized error handling with consistent logging and user notifications.
"""

from typing import Optional
import logging
import traceback

from PyQt6.QtWidgets import QMessageBox, QWidget

# Configure logger
logger = logging.getLogger("TITAN_POS")

# ============================================================================
# ERROR HANDLER FUNCTIONS
# ============================================================================

def handle_db_error(error: Exception, context: str = "Database operation", 
                   parent: Optional[QWidget] = None, show_dialog: bool = True) -> None:
    """
    Handle database errors with logging and optional user notification.
    
    Args:
        error: The exception that occurred
        context: Description of what operation was being performed
        parent: Parent widget for dialog
        show_dialog: Whether to show error dialog to user
    """
    error_msg = f"{context}: {str(error)}"
    logger.error(error_msg, exc_info=True)
    
    if show_dialog and parent:
        QMessageBox.critical(
            parent,
            "Error de Base de Datos",
            f"Error al realizar operación de base de datos:\n\n{str(error)}\n\n"
            f"Por favor contacte al administrador si el problema persiste."
        )

def handle_ui_error(error: Exception, context: str = "UI operation",
                   parent: Optional[QWidget] = None, show_dialog: bool = True) -> None:
    """
    Handle UI errors with logging and optional user notification.
    
    Args:
        error: The exception that occurred
        context: Description of what operation was being performed
        parent: Parent widget for dialog
        show_dialog: Whether to show error dialog to user
    """
    error_msg = f"{context}: {str(error)}"
    logger.error(error_msg, exc_info=True)
    
    if show_dialog and parent:
        QMessageBox.warning(
            parent,
            "Error",
            f"Error en la interfaz:\n\n{str(error)}"
        )

def handle_validation_error(message: str, parent: Optional[QWidget] = None) -> None:
    """
    Handle validation errors with user notification.
    
    Args:
        message: Validation error message
        parent: Parent widget for dialog
    """
    logger.warning(f"Validation error: {message}")
    
    if parent:
        QMessageBox.warning(
            parent,
            "Validación",
            message
        )

def handle_business_error(message: str, parent: Optional[QWidget] = None) -> None:
    """
    Handle business logic errors with user notification.
    
    Args:
        message: Business error message
        parent: Parent widget for dialog
    """
    logger.warning(f"Business logic error: {message}")
    
    if parent:
        QMessageBox.information(
            parent,
            "Información",
            message
        )

def handle_critical_error(error: Exception, context: str = "Critical operation",
                         parent: Optional[QWidget] = None) -> None:
    """
    Handle critical errors that may require application restart.
    
    Args:
        error: The exception that occurred
        context: Description of what operation was being performed
        parent: Parent widget for dialog
    """
    error_msg = f"CRITICAL ERROR - {context}: {str(error)}"
    logger.critical(error_msg, exc_info=True)
    
    # Log full traceback
    logger.critical(traceback.format_exc())
    
    if parent:
        QMessageBox.critical(
            parent,
            "Error Crítico",
            f"Ha ocurrido un error crítico:\n\n{str(error)}\n\n"
            f"La aplicación puede necesitar reiniciarse.\n"
            f"Por favor contacte al administrador."
        )

def log_info(message: str) -> None:
    """Log informational message."""
    logger.info(message)

def log_warning(message: str) -> None:
    """Log warning message."""
    logger.warning(message)

def log_debug(message: str) -> None:
    """Log debug message."""
    logger.debug(message)

# ============================================================================
# SUCCESS NOTIFICATIONS
# ============================================================================

def show_success(message: str, parent: Optional[QWidget] = None, 
                title: str = "Éxito") -> None:
    """
    Show success message to user.
    
    Args:
        message: Success message
        parent: Parent widget for dialog
        title: Dialog title
    """
    logger.info(f"Success: {message}")
    
    if parent:
        QMessageBox.information(parent, title, message)

def show_info(message: str, parent: Optional[QWidget] = None,
             title: str = "Información") -> None:
    """
    Show informational message to user.
    
    Args:
        message: Info message
        parent: Parent widget for dialog
        title: Dialog title
    """
    logger.info(f"Info: {message}")
    
    if parent:
        QMessageBox.information(parent, title, message)

# ============================================================================
# CONFIRMATION DIALOGS
# ============================================================================

def confirm_action(message: str, parent: Optional[QWidget] = None,
                  title: str = "Confirmar") -> bool:
    """
    Ask user to confirm an action.
    
    Args:
        message: Confirmation message
        parent: Parent widget for dialog
        title: Dialog title
        
    Returns:
        True if user confirmed, False otherwise
    """
    if not parent:
        return True
    
    reply = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No
    )
    
    return reply == QMessageBox.StandardButton.Yes

def confirm_delete(item_name: str, parent: Optional[QWidget] = None) -> bool:
    """
    Ask user to confirm deletion.
    
    Args:
        item_name: Name of item to delete
        parent: Parent widget for dialog
        
    Returns:
        True if user confirmed, False otherwise
    """
    return confirm_action(
        f"¿Está seguro que desea eliminar '{item_name}'?\n\n"
        f"Esta acción no se puede deshacer.",
        parent,
        "Confirmar Eliminación"
    )

# ============================================================================
# EXCEPTION CONTEXT MANAGER
# ============================================================================

class ErrorContext:
    """
    Context manager for handling errors in a block of code.
    
    Example:
        with ErrorContext("Loading customers", parent=self):
            customers = load_customers()
    """
    
    def __init__(self, context: str, parent: Optional[QWidget] = None,
                 show_dialog: bool = True, critical: bool = False):
        self.context = context
        self.parent = parent
        self.show_dialog = show_dialog
        self.critical = critical
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            if self.critical:
                handle_critical_error(exc_val, self.context, self.parent)
            else:
                handle_db_error(exc_val, self.context, self.parent, self.show_dialog)
            return True  # Suppress exception
        return False
