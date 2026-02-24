"""
Keyboard Shortcuts and Handlers
Centralized keyboard shortcut definitions for sales operations
"""

from typing import Callable, Dict, Optional
import logging

from PyQt6 import QtCore, QtGui

logger = logging.getLogger(__name__)

# Default keyboard shortcuts for sales operations
DEFAULT_SHORTCUTS = {
    # Function keys
    'F1': 'show_help',
    'F2': 'search_product',
    'F3': 'apply_discount',
    'F4': 'add_note',
    'F5': 'select_customer',
    'F6': 'open_price_checker',
    'F7': 'open_calculator',
    'F8': 'print_last_ticket',
    'F9': 'pause_sale',
    'F10': 'void_item',
    'F11': 'void_transaction',
    'F12': 'toggle_fullscreen',
    
    # Navigation
    'Up': 'select_previous_item',
    'Down': 'select_next_item',
    'Home': 'select_first_item',
    'End': 'select_last_item',
    
    # Actions
    'Enter': 'confirm_action',
    'Escape': 'cancel_action',
    'Delete': 'delete_selected_item',
    '+': 'increase_quantity',
    '-': 'decrease_quantity',
    '*': 'multiply_quantity',
    '=': 'assign_customer',
    
    # Control combinations
    'Ctrl+N': 'new_session',
    'Ctrl+W': 'close_session',
    'Ctrl+Tab': 'next_session',
    'Ctrl+Shift+Tab': 'previous_session',
    'Ctrl+P': 'add_generic_product',
    'Ctrl+S': 'save_session',
}

def parse_key_sequence(key_string: str) -> Optional[QtGui.QKeySequence]:
    """
    Parse a key string into a QKeySequence.
    
    Args:
        key_string: String like 'Ctrl+P' or 'F1'
    
    Returns:
        QKeySequence or None if invalid
    """
    try:
        return QtGui.QKeySequence(key_string)
    except Exception as e:
        logger.warning(f"Invalid key sequence: {key_string} - {e}")
        return None

def create_shortcut(parent, key: str, callback: Callable) -> Optional[QtGui.QShortcut]:
    """
    Create a keyboard shortcut.
    
    Args:
        parent: Parent widget
        key: Key string (e.g., 'Ctrl+P', 'F1')
        callback: Function to call when triggered
    
    Returns:
        QShortcut object or None
    """
    try:
        seq = parse_key_sequence(key)
        if seq:
            shortcut = QtGui.QShortcut(seq, parent)
            shortcut.activated.connect(callback)
            return shortcut
    except Exception as e:
        logger.error(f"Error creating shortcut {key}: {e}")
    return None

def get_key_name(event: QtGui.QKeyEvent) -> str:
    """
    Get human-readable key name from event.
    
    Args:
        event: QKeyEvent
    
    Returns:
        Key name string
    """
    key = event.key()
    modifiers = event.modifiers()
    
    parts = []
    
    if modifiers & QtCore.Qt.KeyboardModifier.ControlModifier:
        parts.append('Ctrl')
    if modifiers & QtCore.Qt.KeyboardModifier.AltModifier:
        parts.append('Alt')
    if modifiers & QtCore.Qt.KeyboardModifier.ShiftModifier:
        parts.append('Shift')
    
    key_map = {
        QtCore.Qt.Key.Key_F1: 'F1',
        QtCore.Qt.Key.Key_F2: 'F2',
        QtCore.Qt.Key.Key_F3: 'F3',
        QtCore.Qt.Key.Key_F4: 'F4',
        QtCore.Qt.Key.Key_F5: 'F5',
        QtCore.Qt.Key.Key_F6: 'F6',
        QtCore.Qt.Key.Key_F7: 'F7',
        QtCore.Qt.Key.Key_F8: 'F8',
        QtCore.Qt.Key.Key_F9: 'F9',
        QtCore.Qt.Key.Key_F10: 'F10',
        QtCore.Qt.Key.Key_F11: 'F11',
        QtCore.Qt.Key.Key_F12: 'F12',
        QtCore.Qt.Key.Key_Escape: 'Escape',
        QtCore.Qt.Key.Key_Return: 'Enter',
        QtCore.Qt.Key.Key_Enter: 'Enter',
        QtCore.Qt.Key.Key_Delete: 'Delete',
        QtCore.Qt.Key.Key_Plus: '+',
        QtCore.Qt.Key.Key_Minus: '-',
        QtCore.Qt.Key.Key_Asterisk: '*',
        QtCore.Qt.Key.Key_Equal: '=',
    }
    
    if key in key_map:
        parts.append(key_map[key])
    else:
        text = event.text()
        if text:
            parts.append(text.upper())
    
    return '+'.join(parts) if parts else ''

def is_printable_key(event: QtGui.QKeyEvent) -> bool:
    """Check if key event is a printable character."""
    text = event.text()
    return bool(text) and text.isprintable()

def is_barcode_scan(buffer: str) -> bool:
    """
    Detect if input looks like a barcode scan.
    Barcodes are typically numeric or alphanumeric with no spaces.
    
    Args:
        buffer: Input text
    
    Returns:
        True if looks like barcode
    """
    if not buffer or len(buffer) < 3:
        return False
    
    # Barcodes are typically alphanumeric
    clean = buffer.strip()
    if not clean:
        return False
    
    # Check if mostly digits or valid barcode chars
    valid_chars = sum(1 for c in clean if c.isalnum() or c in '-_.')
    return valid_chars / len(clean) > 0.9
