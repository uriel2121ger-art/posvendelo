"""
TITAN POS - Comprehensive Activity Logger
Logs ALL user interactions and app events for detailed monitoring
"""
from typing import Any, Callable
from datetime import datetime
from functools import wraps
from pathlib import Path
import logging
import os

# Configure activity logger
activity_logger = logging.getLogger('activity_monitor')
activity_logger.setLevel(logging.INFO)

# Create handler if not exists
if not activity_logger.handlers:
    # Crear directorio logs si no existe
    log_dir = Path(__file__).parent.parent.parent / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'activity_monitor.log'

    handler = logging.FileHandler(str(log_file))
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    activity_logger.addHandler(handler)

def log_activity(category: str, action: str, details: dict = None):
    """
    Log user activity with detailed context
    
    Args:
        category: Category of action (UI, CART, PAYMENT, NAVIGATION, etc.)
        action: Specific action taken
        details: Additional context/data
    """
    details_str = f" | {details}" if details else ""
    activity_logger.info(f"[{category}] {action}{details_str}")

def track_method(category: str):
    """
    Decorator to automatically track method calls
    
    Usage:
        @track_method("CART")
        def add_to_cart(self, item):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Log method call
            method_name = func.__name__
            log_activity(category, f"METHOD_CALL: {method_name}", {
                'args_count': len(args) - 1,  # -1 for self
                'kwargs': list(kwargs.keys())
            })
            
            # Execute method
            try:
                result = func(*args, **kwargs)
                log_activity(category, f"METHOD_SUCCESS: {method_name}")
                return result
            except Exception as e:
                log_activity(category, f"METHOD_ERROR: {method_name}", {
                    'error': str(e)
                })
                raise
        
        return wrapper
    return decorator

# Specific logging functions for common actions

def log_ui_click(widget_name: str, button_text: str = None):
    """Log UI button/widget click"""
    details = {'widget': widget_name}
    if button_text:
        details['button'] = button_text
    log_activity("UI_CLICK", f"User clicked: {widget_name}", details)

def log_navigation(from_tab: str, to_tab: str):
    """Log tab/page navigation"""
    log_activity("NAVIGATION", f"Changed tab: {from_tab} → {to_tab}")

def log_cart_operation(operation: str, product_name: str = None, quantity: float = None):
    """Log cart operations"""
    details = {}
    if product_name:
        details['product'] = product_name
    if quantity:
        details['quantity'] = quantity
    log_activity("CART", f"{operation}", details)

def log_payment(method: str, amount: float, customer: str = None):
    """Log payment transactions"""
    details = {
        'method': method,
        'amount': amount
    }
    if customer:
        details['customer'] = customer
    log_activity("PAYMENT", f"Payment processed", details)

def log_customer_action(action: str, customer_name: str = None, customer_id: int = None):
    """Log customer-related actions"""
    details = {}
    if customer_name:
        details['name'] = customer_name
    if customer_id:
        details['id'] = customer_id
    log_activity("CUSTOMER", action, details)

def log_product_action(action: str, product_name: str = None, sku: str = None):
    """Log product-related actions"""
    details = {}
    if product_name:
        details['name'] = product_name
    if sku:
        details['sku'] = sku
    log_activity("PRODUCT", action, details)

def log_discount(discount_type: str, amount: float, target: str = None):
    """Log discount applications"""
    details = {
        'type': discount_type,
        'amount': amount
    }
    if target:
        details['target'] = target
    log_activity("DISCOUNT", f"Discount applied", details)

def log_search(search_type: str, query: str, results_count: int = None):
    """Log search operations"""
    details = {
        'type': search_type,
        'query': query
    }
    if results_count is not None:
        details['results'] = results_count
    log_activity("SEARCH", f"Search performed", details)

def log_dialog(dialog_name: str, action: str, result: str = None):
    """Log dialog interactions"""
    details = {
        'dialog': dialog_name,
        'action': action
    }
    if result:
        details['result'] = result
    log_activity("DIALOG", f"Dialog interaction", details)

def log_keyboard(key: str, modifier: str = None):
    """Log keyboard shortcuts"""
    details = {'key': key}
    if modifier:
        details['modifier'] = modifier
    log_activity("KEYBOARD", f"Shortcut used", details)

def log_session(action: str, session_id: int = None):
    """Log session/ticket operations"""
    details = {}
    if session_id is not None:
        details['session'] = session_id
    log_activity("SESSION", action, details)

def log_turn(action: str, turn_id: int = None, amount: float = None):
    """Log turn/shift operations"""
    details = {}
    if turn_id:
        details['turn_id'] = turn_id
    if amount:
        details['amount'] = amount
    log_activity("TURN", action, details)

def log_inventory(action: str, product: str = None, quantity: float = None):
    """Log inventory operations"""
    details = {}
    if product:
        details['product'] = product
    if quantity:
        details['quantity'] = quantity
    log_activity("INVENTORY", action, details)

def log_report(report_type: str, filters: dict = None):
    """Log report generation"""
    details = {'type': report_type}
    if filters:
        details['filters'] = filters
    log_activity("REPORT", f"Report generated", details)

def log_export(export_type: str, format: str, record_count: int = None):
    """Log data exports"""
    details = {
        'type': export_type,
        'format': format
    }
    if record_count:
        details['records'] = record_count
    log_activity("EXPORT", f"Data exported", details)

def log_import(import_type: str, source: str, record_count: int = None):
    """Log data imports"""
    details = {
        'type': import_type,
        'source': source
    }
    if record_count:
        details['records'] = record_count
    log_activity("IMPORT", f"Data imported", details)

def log_settings(setting_name: str, old_value: Any = None, new_value: Any = None):
    """Log settings changes"""
    details = {'setting': setting_name}
    if old_value is not None:
        details['old'] = str(old_value)
    if new_value is not None:
        details['new'] = str(new_value)
    log_activity("SETTINGS", f"Setting changed", details)

def log_error(error_type: str, message: str, context: dict = None):
    """Log errors and exceptions"""
    details = {
        'type': error_type,
        'message': message
    }
    if context:
        details.update(context)
    activity_logger.error(f"[ERROR] {error_type} | {details}")

def log_startup():
    """Log application startup"""
    activity_logger.info("=" * 80)
    activity_logger.info(f"[SYSTEM] Application started at {datetime.now()}")
    activity_logger.info("=" * 80)

def log_shutdown():
    """Log application shutdown"""
    activity_logger.info("=" * 80)
    activity_logger.info(f"[SYSTEM] Application shutdown at {datetime.now()}")
    activity_logger.info("=" * 80)
