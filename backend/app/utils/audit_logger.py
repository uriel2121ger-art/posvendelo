"""
Comprehensive Audit Logging System for TITAN POS

This module provides complete audit trail functionality to track all critical
operations in the system including sales, products, customers, turns, and system changes.

Author: Antigravity
Date: 2025-12-14
"""

from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
from functools import wraps
import json
import logging

logger = logging.getLogger(__name__)

class AuditLogger:
    """Comprehensive audit logging system for tracking all critical operations"""
    
    def __init__(self, db_connection):
        """
        Initialize audit logger with database connection
        
        Args:
            db_connection: Database connection object with execute_write method
        """
        self.db = db_connection
        self._enabled = True
    
    def log(self, 
            action: str,
            entity_type: str,
            entity_id: Optional[int] = None,
            entity_name: Optional[str] = None,
            old_value: Optional[Dict] = None,
            new_value: Optional[Dict] = None,
            success: bool = True,
            error_message: Optional[str] = None,
            details: Optional[Dict] = None,
            user_id: Optional[int] = None,
            username: Optional[str] = None,
            turn_id: Optional[int] = None,
            branch_id: Optional[int] = None) -> None:
        """
        Log an audit event to the database
        
        Args:
            action: Action performed (e.g., CREATE, UPDATE, DELETE, LOGIN)
            entity_type: Type of entity (sale, product, customer, turn, user, system)
            entity_id: ID of the affected entity
            entity_name: Name/description of the entity
            old_value: Previous value (for updates)
            new_value: New value (for creates/updates)
            success: Whether the operation succeeded
            error_message: Error message if failed
            details: Additional details as dictionary
            user_id: Override user_id (auto-detected from STATE if not provided)
            username: Override username
            turn_id: Override turn_id
            branch_id: Override branch_id
        """
        if not self._enabled:
            return
        
        try:
            # Import STATE here to avoid circular imports
            from app.core import STATE

            # Auto-detect values from STATE if not provided
            if user_id is None:
                user_id = getattr(STATE, 'user_id', None)
            if username is None:
                username = getattr(STATE, 'username', None)
            if turn_id is None:
                turn_id = getattr(STATE, 'current_turn_id', None)
            if branch_id is None:
                branch_id = getattr(STATE, 'branch_id', None)
            
            # CRITICAL FIX: Verificar qué columnas existen antes de INSERT
            # Construir SQL dinámicamente basado en columnas disponibles
            try:
                table_info = self.db.get_table_info("audit_log")
                available_cols = [col.get('name') if isinstance(col, dict) else col[1] for col in table_info]
            except Exception:
                # Si no podemos obtener info, usar columnas básicas
                available_cols = ['timestamp', 'action', 'entity_type']
            
            # Columnas requeridas (siempre presentes)
            columns = ['timestamp', 'action', 'entity_type']
            values = [datetime.now().isoformat(), action, entity_type]
            
            # Columnas opcionales (solo si existen en la tabla)
            optional_fields = [
                ('user_id', user_id),
                ('username', username),
                ('entity_id', entity_id),
                ('entity_name', entity_name),
                ('old_value', json.dumps(old_value, default=str) if old_value else None),
                ('new_value', json.dumps(new_value, default=str) if new_value else None),
                ('turn_id', turn_id),
                ('branch_id', branch_id),
                ('success', 1 if success else 0),
                ('error_message', error_message),
                ('details', json.dumps(details, default=str) if details else None)
            ]
            
            for col_name, col_value in optional_fields:
                if col_name in available_cols:
                    columns.append(col_name)
                    values.append(col_value)
            
            # Construir SQL dinámicamente
            placeholders = ', '.join(['%s'] * len(columns))
            columns_str = ', '.join(columns)
            sql = f"INSERT INTO audit_log ({columns_str}) VALUES ({placeholders})"
            
            self.db.execute_write(sql, tuple(values))
            
        except Exception as e:
            # Don't let audit failures break the application
            logger.error(f"Failed to write audit log: {e}")
    
    # ==================== CONVENIENCE METHODS ====================
    
    def log_create(self, entity_type: str, entity_id: int, entity_name: str, data: Dict):
        """Log entity creation"""
        self.log('CREATE', entity_type, entity_id, entity_name, new_value=data)
    
    def log_update(self, entity_type: str, entity_id: int, entity_name: str, old: Dict, new: Dict):
        """Log entity update"""
        self.log('UPDATE', entity_type, entity_id, entity_name, old_value=old, new_value=new)
    
    def log_delete(self, entity_type: str, entity_id: int, entity_name: str, data: Dict):
        """Log entity deletion"""
        self.log('DELETE', entity_type, entity_id, entity_name, old_value=data)
    
    # ==================== USER & AUTH ====================
    
    def log_login(self, username: str, success: bool, error: Optional[str] = None, user_id: Optional[int] = None):
        """Log login attempt"""
        self.log('LOGIN', 'user', user_id, username, success=success, 
                error_message=error, username=username, user_id=user_id)
    
    def log_logout(self, username: str, user_id: Optional[int] = None):
        """Log logout"""
        self.log('LOGOUT', 'user', user_id, username, username=username, user_id=user_id)
    
    def log_password_change(self, user_id: int, username: str, success: bool):
        """Log password change"""
        self.log('PASSWORD_CHANGE', 'user', user_id, username, success=success)
    
    # ==================== SALES ====================
    
    def log_sale(self, sale_id: int, total: float, details: Dict):
        """Log sale creation - ONLY Serie A (fiscal) sales are logged."""
        # SECURITY: Do not log Serie B (shadow) sales to audit trail
        serie = details.get('serie', 'A') if details else 'A'
        if serie == 'B':
            return  # Serie B stays invisible
        
        self.log('SALE_CREATE', 'sale', sale_id, f"Sale ${total:.2f}", 
                new_value={'total': total}, details=details)
    
    def log_sale_cancel(self, sale_id: int, reason: str, old_data: Dict):
        """Log sale cancellation"""
        self.log('SALE_CANCEL', 'sale', sale_id, old_value=old_data, 
                details={'reason': reason})
    
    def log_refund(self, sale_id: int, amount: float, reason: str):
        """Log refund"""
        self.log('SALE_REFUND', 'sale', sale_id, 
                details={'amount': amount, 'reason': reason})
    
    # ==================== PRODUCTS ====================
    
    def log_price_change(self, product_id: int, sku: str, old_price: float, new_price: float):
        """Log product price change"""
        self.log('PRICE_CHANGE', 'product', product_id, sku,
                old_value={'price': old_price},
                new_value={'price': new_price})
    
    def log_inventory_adjustment(self, product_id: int, sku: str, old_stock: float, 
                                 new_stock: float, reason: str):
        """Log inventory adjustment"""
        self.log('INVENTORY_ADJUST', 'product', product_id, sku,
                old_value={'stock': old_stock},
                new_value={'stock': new_stock},
                details={'reason': reason, 'difference': new_stock - old_stock})
    
    # ==================== CUSTOMERS ====================
    
    def log_credit_grant(self, customer_id: int, customer_name: str, amount: float, limit: float):
        """Log credit granted to customer"""
        self.log('CREDIT_GRANT', 'customer', customer_id, customer_name,
                details={'amount': amount, 'limit': limit})
    
    def log_credit_payment(self, customer_id: int, customer_name: str, amount: float):
        """Log customer credit payment"""
        self.log('CREDIT_PAYMENT', 'customer', customer_id, customer_name,
                details={'amount': amount})
    
    def log_loyalty_points(self, customer_id: int, customer_name: str, points: float, 
                          action: str = 'ADD'):
        """Log loyalty points transaction"""
        self.log(f'LOYALTY_{action}', 'customer', customer_id, customer_name,
                details={'points': points})
    
    # ==================== TURNS ====================
    
    def log_turn_open(self, turn_id: int, opening_amount: float, user_id: Optional[int] = None):
        """Log turn opening"""
        self.log('TURN_OPEN', 'turn', turn_id, 
                details={'opening_amount': opening_amount}, user_id=user_id)
    
    def log_turn_close(self, turn_id: int, closing_amount: float, expected: float, 
                      difference: float):
        """Log turn closing"""
        self.log('TURN_CLOSE', 'turn', turn_id, details={
            'closing_amount': closing_amount,
            'expected_cash': expected,
            'difference': difference
        })
    
    def log_cash_movement(self, turn_id: int, movement_type: str, amount: float, reason: str):
        """Log cash in/out during turn"""
        self.log(f'CASH_{movement_type.upper()}', 'turn', turn_id,
                details={'amount': amount, 'reason': reason})
    
    # ==================== SYSTEM ====================
    
    def log_config_change(self, setting: str, old_value: Any, new_value: Any):
        """Log system configuration change"""
        self.log('CONFIG_CHANGE', 'system', entity_name=setting,
                old_value={'value': old_value},
                new_value={'value': new_value})
    
    def log_backup(self, backup_file: str, success: bool, error: Optional[str] = None):
        """Log backup operation"""
        self.log('BACKUP', 'system', entity_name=backup_file, 
                success=success, error_message=error)
    
    def log_restore(self, backup_file: str, success: bool, error: Optional[str] = None):
        """Log restore operation"""
        self.log('RESTORE', 'system', entity_name=backup_file,
                success=success, error_message=error)
    
    def log_migration(self, version: str, success: bool, error: Optional[str] = None):
        """Log database migration"""
        self.log('DB_MIGRATION', 'system', entity_name=f"Migration {version}",
                success=success, error_message=error)
    
    # ==================== QUERY METHODS ====================
    
    def get_logs(self, filters: Optional[Dict] = None, limit: int = 100) -> List[Dict]:
        """
        Query audit logs with optional filters.
        
        Args:
            filters: Dict with filter criteria (action, user_id, entity_type, etc.)
            limit: Max number of records
        """
        # Fix: Handle case where filters is not a dict
        if filters is not None and not isinstance(filters, dict):
            filters = {}
        
        # SECURITY: Especificar columnas en lugar de SELECT *
        sql = "SELECT id, action, entity_type, entity_id, entity_name, user_id, username, timestamp, success, error_message, details FROM audit_log WHERE 1=1"
        params = []

        if filters:
            if 'user_id' in filters:
                sql += " AND user_id = %s"
                params.append(filters['user_id'])
            if 'action' in filters:
                sql += " AND action = %s"
                params.append(filters['action'])
            if 'entity_type' in filters:
                sql += " AND entity_type = %s"
                params.append(filters['entity_type'])
            if 'date_from' in filters:
                sql += " AND timestamp >= %s"
                params.append(filters['date_from'])
            if 'date_to' in filters:
                sql += " AND timestamp <= %s"
                params.append(filters['date_to'])
            if 'success' in filters:
                sql += " AND success = %s"
                params.append(1 if filters['success'] else 0)

        # SECURITY: Parameterize LIMIT con cap máximo obligatorio
        limit = max(1, min(int(limit), 10000))
        sql += " ORDER BY timestamp DESC LIMIT %s"
        params.append(limit)

        return self.db.execute_query(sql, tuple(params))
    
    def get_entity_history(self, entity_type: str, entity_id: int, limit: int = 1000) -> list:
        """Get complete history for a specific entity"""
        # SECURITY: Especificar columnas y agregar LIMIT
        limit = max(1, min(int(limit), 10000))
        return self.db.execute_query("""
            SELECT id, action, entity_type, entity_id, entity_name, user_id, username, timestamp, success, details
            FROM audit_log
            WHERE entity_type = %s AND entity_id = %s
            ORDER BY timestamp DESC
            LIMIT %s
        """, (entity_type, entity_id, limit))
    
    def get_user_activity(self, user_id: int, days: int = 30, limit: int = 1000) -> list:
        """Get recent activity for a specific user"""
        from datetime import timedelta

        # SECURITY: Especificar columnas y agregar LIMIT
        limit = max(1, min(int(limit), 10000))
        date_from = (datetime.now() - timedelta(days=days)).isoformat()
        return self.db.execute_query("""
            SELECT id, action, entity_type, entity_id, entity_name, user_id, username, timestamp, success, details
            FROM audit_log
            WHERE user_id = %s AND timestamp >= %s
            ORDER BY timestamp DESC
            LIMIT %s
        """, (user_id, date_from, limit))
    
    # ==================== UTILITY ====================
    
    def enable(self):
        """Enable audit logging"""
        self._enabled = True
    
    def disable(self):
        """Disable audit logging (use carefully!)"""
        self._enabled = False
    
    @property
    def is_enabled(self) -> bool:
        """Check if audit logging is enabled"""
        return self._enabled

# ==================== DECORATOR ====================

def audit_action(action: str, entity_type: str, capture_result: bool = False):
    """
    Decorator to automatically audit function calls
    
    Usage:
        @audit_action('PRODUCT_CREATE', 'product', capture_result=True)
        def create_product(self, data):
            # ... implementation
            return product_id
    
    Args:
        action: Audit action name
        entity_type: Entity type being operated on
        capture_result: If True, logs the function result as entity_id
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                result = func(self, *args, **kwargs)
                
                # Log success
                if hasattr(self, 'audit'):
                    entity_id = result if capture_result and isinstance(result, int) else None
                    self.audit.log(
                        action, 
                        entity_type,
                        entity_id=entity_id,
                        details={'args': str(args)[:200]},
                        success=True
                    )
                return result
                
            except Exception as e:
                # Log failure
                if hasattr(self, 'audit'):
                    self.audit.log(
                        action,
                        entity_type,
                        success=False,
                        error_message=str(e)[:500],
                        details={'args': str(args)[:200]}
                    )
                raise
        return wrapper
    return decorator

# Global audit logger instance (initialized by POSCore)
_audit_instance: Optional[AuditLogger] = None

def get_audit_logger() -> Optional[AuditLogger]:
    """Get global audit logger instance"""
    return _audit_instance

def set_audit_logger(logger: AuditLogger):
    """Set global audit logger instance"""
    global _audit_instance
    _audit_instance = logger
