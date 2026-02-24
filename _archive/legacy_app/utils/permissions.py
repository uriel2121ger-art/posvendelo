"""
Permission System - Configurable Role-based Access Control
Now reads from database via permission_engine
"""

from app.core import STATE


def _check_permission(permission: str) -> bool:
    """Internal helper to check permission from database"""
    try:
        from app.core import POSCore
        core = POSCore.get_instance()
        if core and hasattr(core, 'permission_engine'):
            return core.permission_engine.has_permission(STATE.role, permission)
    except Exception as e:
        # SECURITY: Log permission check failures for investigation
        import logging
        logging.getLogger(__name__).warning(
            f"Permission check failed for '{permission}': {e}. "
            "Denying access by default (fail-secure)."
        )
    # SECURITY: Fail-secure - deny access if permission check fails
    # This prevents privilege escalation if the permission system breaks
    return False

def can_open_turn() -> bool:
    """Check if user can open a turn."""
    return _check_permission('open_turn')

def can_close_turn() -> bool:
    """Check if user can close a turn."""
    return _check_permission('close_turn')

def can_delete_product() -> bool:
    """Check if user can delete products."""
    return _check_permission('delete_product')

def can_modify_stock() -> bool:
    """Check if user can modify stock levels."""
    return _check_permission('modify_stock')

def can_cancel_sale() -> bool:
    """Check if user can cancel sales."""
    return _check_permission('cancel_sale')

def can_approve_loan() -> bool:
    """Check if user can approve/manage employee loans."""
    return _check_permission('approve_loans')

def can_edit_prices() -> bool:
    """Check if user can edit product prices."""
    return _check_permission('edit_prices')

def can_manage_users() -> bool:
    """Check if user can create/edit/delete users."""
    return _check_permission('manage_users')

def can_configure_system() -> bool:
    """Check if user can access system configuration."""
    # Any of the config permissions
    return (_check_permission('configure_printer') or 
            _check_permission('configure_fiscal') or 
            _check_permission('configure_network'))

def can_view_unmasked_data() -> bool:
    """Check if user can view unmasked financial data."""
    return _check_permission('view_unmasked_data')

def is_admin() -> bool:
    """Check if user is admin."""
    return STATE.role == "admin"

def is_supervisor() -> bool:
    """Check if user has supervisory permissions (admin/manager/encargado)."""
    return STATE.role in ["admin", "manager", "encargado"]

def get_permission_denied_message() -> str:
    """Get standard permission denied message."""
    return "No tienes permisos para realizar esta acción.\\nContacta al administrador."
