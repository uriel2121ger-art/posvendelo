"""
Permission Engine - Configurable Role-Based Access Control
Manages granular permissions stored in database
"""

import logging
from typing import Dict, List

# FIX 2026-02-01: Agregar logger que se usaba sin estar definido
logger = logging.getLogger(__name__)

# Permission definitions
PERMISSIONS = {
    'turnos': [
        ('open_turn', 'Abrir Turno'),
        ('close_turn', 'Cerrar Turno'),
        ('partial_cut', 'Corte Parcial'),
    ],
    'ventas': [
        ('create_sale', 'Realizar Venta'),
        ('cancel_sale', 'Cancelar Venta'),
        ('apply_discount', 'Aplicar Descuentos'),
        ('apply_large_discount', 'Descuentos >20%'),
    ],
    'productos': [
        ('view_products', 'Ver Productos'),
        ('create_product', 'Crear Producto'),
        ('edit_product', 'Editar Producto'),
        ('delete_product', 'Eliminar Producto'),
        ('edit_prices', 'Modificar Precios'),
    ],
    'inventario': [
        ('view_stock', 'Ver Stock'),
        ('modify_stock', 'Modificar Stock'),
    ],
    'empleados': [
        ('view_employees', 'Ver Empleados'),
        ('manage_employees', 'Gestionar Empleados'),
    ],
    'prestamos': [
        ('view_loans', 'Ver Préstamos'),
        ('approve_loans', 'Aprobar Préstamos'),
    ],
    'clientes': [
        ('view_customers', 'Ver Clientes'),
        ('edit_customers', 'Editar Clientes'),
        ('view_unmasked_data', 'Ver Datos Sin Máscara'),
    ],
    'usuarios': [
        ('manage_users', 'Gestionar Usuarios'),
    ],
    'configuracion': [
        ('configure_printer', 'Configurar Impresora'),
        ('configure_fiscal', 'Configurar Fiscal'),
        ('configure_network', 'Configurar Red'),
    ],
}

# Default permissions for each role
DEFAULT_PERMISSIONS = {
    'admin': [  # Admin has ALL permissions
        'open_turn', 'close_turn', 'partial_cut',
        'create_sale', 'cancel_sale', 'apply_discount', 'apply_large_discount',
        'view_products', 'create_product', 'edit_product', 'delete_product', 'edit_prices',
        'view_stock', 'modify_stock',
        'view_employees', 'manage_employees',
        'view_loans', 'approve_loans',
        'view_customers', 'edit_customers', 'view_unmasked_data',
        'manage_users',
        'configure_printer', 'configure_fiscal', 'configure_network',
    ],
    'manager': [  # Manager has all except view_unmasked_data
        'open_turn', 'close_turn', 'partial_cut',
        'create_sale', 'cancel_sale', 'apply_discount', 'apply_large_discount',
        'view_products', 'create_product', 'edit_product', 'delete_product', 'edit_prices',
        'view_stock', 'modify_stock',
        'view_employees', 'manage_employees',
        'view_loans', 'approve_loans',
        'view_customers', 'edit_customers',
        'manage_users',
        'configure_printer', 'configure_fiscal', 'configure_network',
    ],
    'encargado': [  # Encargado has most operational permissions
        'open_turn', 'close_turn', 'partial_cut',
        'create_sale', 'cancel_sale', 'apply_discount',
        'view_products', 'create_product', 'edit_product', 'delete_product',
        'view_stock', 'modify_stock',
        'view_employees', 'manage_employees',
        'view_loans', 'approve_loans',
        'view_customers', 'edit_customers',
        'manage_users',
        'configure_printer',
    ],
    'cashier': [  # Cashier has basic operational permissions
        'open_turn', 'close_turn', 'partial_cut',
        'create_sale', 'cancel_sale', 'apply_discount',
        'view_products', 'create_product', 'edit_product', 'delete_product',
        'view_stock', 'modify_stock',
        'view_employees', 'manage_employees',
        'view_loans',
        'view_customers', 'edit_customers',
        'configure_printer',
    ],
}

class PermissionEngine:
    """Manages configurable role-based permissions"""
    
    def __init__(self, db):
        self.db = db
        self._ensure_table()
    
    def _ensure_table(self):
        """Create permissions table if it doesn't exist"""
        self.db.execute_write("""
            CREATE TABLE IF NOT EXISTS role_permissions (
                role TEXT NOT NULL,
                permission TEXT NOT NULL,
                allowed INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (role, permission)
            )
        """)
    
    def initialize_defaults(self, force=False):
        """Initialize default permissions for all roles"""
        if not force:
            # Check if already initialized
            existing = self.db.execute_query("SELECT COUNT(*) as count FROM role_permissions")
            if existing and len(existing) > 0 and existing[0] and existing[0].get('count', 0) > 0:
                return  # Already initialized
        
        # Insert defaults for each role
        for role, permissions in DEFAULT_PERMISSIONS.items():
            for perm in permissions:
                # PostgreSQL: usar ON CONFLICT DO NOTHING en lugar de INSERT OR IGNORE
                self.db.execute_write("""
                    INSERT INTO role_permissions (role, permission, allowed)
                    VALUES (%s, %s, 1)
                    ON CONFLICT (role, permission) DO NOTHING
                """, (role, perm))
            
            # Also insert denied permissions (those not in the list)
            all_perms = []
            for category in PERMISSIONS.values():
                all_perms.extend([p[0] for p in category])
            
            for perm in all_perms:
                if perm not in permissions:
                    # PostgreSQL: usar ON CONFLICT DO NOTHING
                    self.db.execute_write("""
                        INSERT INTO role_permissions (role, permission, allowed)
                        VALUES (%s, %s, 0)
                        ON CONFLICT (role, permission) DO NOTHING
                    """, (role, perm))
    
    def has_permission(self, role: str, permission: str) -> bool:
        """Check if role has specific permission"""
        result = self.db.execute_query("""
            SELECT allowed FROM role_permissions
            WHERE role = %s AND permission = %s
        """, (role, permission))
        
        if result and len(result) > 0 and result[0]:
            return bool(result[0].get('allowed', False))
        
        # Default to False if not found
        return False
    
    def set_permission(self, role: str, permission: str, allowed: bool):
        """Set permission for a role"""
        # PostgreSQL: usar ON CONFLICT DO UPDATE en lugar de INSERT OR REPLACE
        self.db.execute_write("""
            INSERT INTO role_permissions (role, permission, allowed, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (role, permission) DO UPDATE SET allowed = EXCLUDED.allowed, updated_at = CURRENT_TIMESTAMP
        """, (role, permission, 1 if allowed else 0))
    
    def get_role_permissions(self, role: str) -> Dict[str, bool]:
        """Get all permissions for a role"""
        results = self.db.execute_query("""
            SELECT permission, allowed FROM role_permissions
            WHERE role = %s
        """, (role,))
        
        return {r['permission']: bool(r['allowed']) for r in results} if results else {}
    
    def check_permission(self, role: str, permission: str) -> bool:
        """
        Check if a role has a specific permission.

        Args:
            role: Role name (e.g., 'admin', 'manager', 'cajero')
            permission: Permission name (e.g., 'view_sales', 'edit_products')

        Returns:
            bool: True if role has permission, False otherwise

        Raises:
            ValueError: Si role o permission son invalidos
            RuntimeError: Si hay error de base de datos
        """
        # Validacion de parametros
        if not role or not isinstance(role, str):
            raise ValueError("role es requerido y debe ser string")
        if not permission or not isinstance(permission, str):
            raise ValueError("permission es requerido y debe ser string")

        try:
            permissions = self.get_role_permissions(role)
            return permissions.get(permission, False)
        except ValueError:
            # Re-raise validation errors
            raise
        except ConnectionError as e:
            # Error de conexion - propagar con contexto
            logger.error(f"Error de conexion al verificar permiso {permission} para rol {role}: {e}")
            raise RuntimeError(f"Error de conexion a base de datos: {e}") from e
        except Exception as e:
            # Otros errores - log detallado y propagar
            logger.error(f"Error inesperado al verificar permiso {permission} para rol {role}: {type(e).__name__}: {e}")
            raise RuntimeError(f"Error al verificar permiso: {type(e).__name__}: {e}") from e
    
    def reset_role_to_defaults(self, role: str):
        """Reset a role's permissions to defaults"""
        # Delete existing
        self.db.execute_write("DELETE FROM role_permissions WHERE role = %s", (role,))
        
        # Re-insert defaults
        if role in DEFAULT_PERMISSIONS:
            for perm in DEFAULT_PERMISSIONS[role]:
                self.set_permission(role, perm, True)
            
            # Insert denied permissions
            all_perms = []
            for category in PERMISSIONS.values():
                all_perms.extend([p[0] for p in category])
            
            for perm in all_perms:
                if perm not in DEFAULT_PERMISSIONS[role]:
                    self.set_permission(role, perm, False)
    
    @staticmethod
    def get_all_permissions() -> Dict[str, List]:
        """Get all available permissions organized by category"""
        return PERMISSIONS
    
    @staticmethod
    def get_roles() -> List[str]:
        """Get all available roles"""
        return ['admin', 'manager', 'encargado', 'cashier']
