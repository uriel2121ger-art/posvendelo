from pathlib import Path

"""
Anonymous Loyalty - Monedero Anónimo para Serie B
Fidelización sin rastro fiscal usando celular o QR
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import logging
import secrets
import sys

logger = logging.getLogger(__name__)

class AnonymousLoyalty:
    """
    Sistema de lealtad anónimo exclusivo para Serie B.
    Sin RFC, sin correo, solo celular o ID único.
    
    UNIFICADO con MIDAS: $1 punto = $1 peso
    """
    
    # Configuración de puntos (UNIFICADO CON MIDAS)
    POINTS_PER_PESO = 1       # 1 punto por cada peso gastado
    PESO_PER_POINT = 1.0      # $1 punto = $1 peso al redimir (antes 0.10)
    MIN_REDEEM = 10           # Mínimo 10 puntos para redimir (antes 100)
    POINTS_EXPIRY_DAYS = 365  # Puntos expiran en 1 año
    
    def __init__(self, core):
        self.core = core
        self._ensure_table()

    def _ensure_table(self):
        """Crea tabla si no existe."""
        if not self.core.db:
            logger.warning("Database not available for anonymous_wallet table creation")
            return

        self.core.db.execute_write("""
            CREATE TABLE IF NOT EXISTS anonymous_wallet (
                id BIGSERIAL PRIMARY KEY,
                wallet_id TEXT UNIQUE NOT NULL,
                phone TEXT,
                nickname TEXT,
                points_balance INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                total_redeemed INTEGER DEFAULT 0,
                last_visit TEXT,
                visit_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        """)
        
        self.core.db.execute_write("""
            CREATE TABLE IF NOT EXISTS wallet_transactions (
                id BIGSERIAL PRIMARY KEY,
                wallet_id TEXT NOT NULL,
                type TEXT NOT NULL,
                points INTEGER NOT NULL,
                sale_id INTEGER,
                description TEXT,
                expires_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Índices
        self.core.db.execute_write(
            "CREATE INDEX IF NOT EXISTS idx_wallet_phone ON anonymous_wallet(phone)"
        )
    
    def create_wallet(self, phone: str = None, nickname: str = None) -> Dict[str, Any]:
        """Crea un nuevo monedero anonimo o devuelve el existente si ya hay uno con ese telefono."""
        if not self.core.db:
            logger.warning("Database not available for create wallet")
            return {'error': 'Database not available'}

        # Check if wallet already exists for this phone
        if phone:
            existing = self.find_wallet(phone)
            if existing:
                return {
                    'wallet_id': existing['wallet_id'],
                    'phone': existing['phone'],
                    'nickname': existing.get('nickname'),
                    'qr_content': f"TITAN:{existing['wallet_id']}",
                    'existing': True
                }
        
        wallet_id = self._generate_wallet_id()
        
        self.core.db.execute_write("""
            INSERT INTO anonymous_wallet (wallet_id, phone, nickname, created_at, synced)
            VALUES (%s, %s, %s, %s, 0)
        """, (wallet_id, phone, nickname, datetime.now().isoformat()))
        
        return {
            'wallet_id': wallet_id,
            'phone': phone,
            'nickname': nickname,
            'qr_content': f"TITAN:{wallet_id}",
            'existing': False
        }
    
    def _generate_wallet_id(self) -> str:
        """Genera ID único para monedero."""
        return hashlib.sha256(
            f"{secrets.token_hex(16)}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16].upper()
    
    def find_wallet(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Busca monedero por phone o wallet_id."""
        if not self.core.db:
            logger.warning("Database not available for find wallet")
            return None

        # Buscar por wallet_id
        result = list(self.core.db.execute_query(
            "SELECT * FROM anonymous_wallet WHERE wallet_id = %s AND status = 'active'",
            (identifier,)
        ))
        
        if result:
            return dict(result[0])
        
        # Buscar por teléfono
        result = list(self.core.db.execute_query(
            "SELECT * FROM anonymous_wallet WHERE phone = %s AND status = 'active'",
            (identifier,)
        ))
        
        return dict(result[0]) if result else None
    
    def earn_points(self, wallet_id: str, sale_total: Decimal,
                    sale_id: int = None, serie: str = 'B') -> Dict[str, Any]:
        """
        Acumula puntos por compra.
        SOLO acumula en Serie B (sin factura).
        Usa las reglas de MIDAS para calcular el cashback.
        """
        if not self.core.db:
            logger.warning("Database not available for earn points")
            return {'success': False, 'reason': 'Database not available'}

        # Verificar que sea Serie B
        if serie != 'B':
            return {
                'success': False,
                'reason': 'Solo se acumulan puntos en compras sin factura (Serie B)'
            }
        
        wallet = self.find_wallet(wallet_id)
        if not wallet:
            return {'success': False, 'reason': 'Monedero no encontrado'}
        
        # Get cashback percentage from app config or MIDAS rules
        try:
            cfg = self.core.get_app_config() or {}
            cashback_percent = float(cfg.get("cashback_percent", 1.0))  # Default 1%
            
            # Try to get from MIDAS rules if available
            result = self.core.db.execute_query("""
                SELECT multiplicador FROM loyalty_rules 
                WHERE activo = 1 AND condicion_tipo = 'GLOBAL'
                ORDER BY prioridad DESC LIMIT 1
            """)
            if result:
                row = result[0]
                multiplicador = row.get('multiplicador') if isinstance(row, dict) else row[0]
                if multiplicador:
                    cashback_percent = float(multiplicador) * 100  # Convert 0.01 to 1%
        except Exception:
            cashback_percent = 1.0  # Fallback to 1%
        
        # Calculate points based on cashback percentage (use round() to avoid truncation)
        points = round(float(sale_total) * (cashback_percent / 100))
        
        if points <= 0:
            return {
                'success': True,
                'points_earned': 0,
                'new_balance': wallet['points_balance'],
                'reason': 'Cashback es 0% o monto muy bajo'
            }
        
        expiry = (datetime.now() + timedelta(days=self.POINTS_EXPIRY_DAYS)).isoformat()
        
        # CRITICAL FIX: Registrar transacción y actualizar balance en una sola transacción atómica
        # Esto previene race conditions y asegura consistencia de datos
        ops = []
        
        # 1. Registrar transacción (con synced = 0 para sincronización)
        ops.append(("""
            INSERT INTO wallet_transactions (wallet_id, type, points, sale_id, description, expires_at, synced)
            VALUES (%s, 'EARN', %s, %s, %s, %s, 0)
        """, (wallet_id, points, sale_id, f'Compra ${sale_total} ({cashback_percent}%)', expiry)))

        # 2. Actualizar balance (con synced = 0 para sincronización)
        ops.append(("""
            UPDATE anonymous_wallet
            SET points_balance = points_balance + %s,
                total_earned = total_earned + %s,
                visit_count = visit_count + 1,
                last_visit = %s,
                synced = 0
            WHERE wallet_id = %s
        """, (points, points, datetime.now().isoformat(), wallet_id)))
        
        # Ejecutar en transacción atómica
        result = self.core.db.execute_transaction(ops, timeout=5)
        if not result.get('success'):
            raise RuntimeError("Error al acumular puntos: transacción falló")
        
        new_balance = wallet['points_balance'] + points
        
        # SECURITY: No loguear acumulación de puntos (Serie B)
        pass
        
        return {
            'success': True,
            'points_earned': points,
            'new_balance': new_balance,
            'can_redeem': new_balance >= self.MIN_REDEEM,
            'redeem_value': new_balance * self.PESO_PER_POINT,
            'cashback_percent': cashback_percent
        }
    
    def redeem_points(self, wallet_id: str, points: int = None) -> Dict[str, Any]:
        """
        Redime puntos por descuento.
        Retorna el valor en pesos del descuento.
        """
        if not self.core.db:
            logger.warning("Database not available for redeem points")
            return {'success': False, 'reason': 'Database not available'}

        wallet = self.find_wallet(wallet_id)
        if not wallet:
            return {'success': False, 'reason': 'Monedero no encontrado'}
        
        # Si no se especifica, redimir todo
        if points is None:
            points = wallet['points_balance']
        
        # Validaciones
        if points < self.MIN_REDEEM:
            return {
                'success': False,
                'reason': f'Mínimo {self.MIN_REDEEM} puntos para redimir'
            }
        
        if points > wallet['points_balance']:
            return {
                'success': False,
                'reason': f'Saldo insuficiente. Tienes {wallet["points_balance"]} puntos'
            }
        
        # Calcular valor
        discount = points * self.PESO_PER_POINT
        
        # CRITICAL FIX: Registrar transacción y actualizar balance en una sola transacción atómica
        # Esto previene race conditions y asegura consistencia de datos
        ops = []
        
        # 1. Registrar transacción (con synced = 0 para sincronización)
        ops.append(("""
            INSERT INTO wallet_transactions (wallet_id, type, points, description, synced)
            VALUES (%s, 'REDEEM', %s, %s, 0)
        """, (wallet_id, -points, f'Canje ${discount:.2f}')))

        # 2. Actualizar balance (con synced = 0 para sincronización)
        ops.append(("""
            UPDATE anonymous_wallet
            SET points_balance = points_balance - %s,
                total_redeemed = total_redeemed + %s,
                synced = 0
            WHERE wallet_id = %s
        """, (points, points, wallet_id)))
        
        # Ejecutar en transacción atómica
        result = self.core.db.execute_transaction(ops, timeout=5)
        if not result.get('success'):
            raise RuntimeError("Error al redimir puntos: transacción falló")
        
        # SECURITY: No loguear canjes de puntos
        pass
        
        return {
            'success': True,
            'points_redeemed': points,
            'discount_value': discount,
            'remaining_balance': wallet['points_balance'] - points
        }
    
    def get_wallet_status(self, wallet_id: str) -> Dict[str, Any]:
        """Obtiene estado completo del monedero."""
        if not self.core.db:
            logger.warning("Database not available for wallet status")
            return {'found': False, 'error': 'Database not available'}

        wallet = self.find_wallet(wallet_id)
        if not wallet:
            return {'found': False}

        # Historial reciente
        history = list(self.core.db.execute_query("""
            SELECT type, points, description, created_at
            FROM wallet_transactions
            WHERE wallet_id = %s
            ORDER BY created_at DESC
            LIMIT 10
        """, (wallet_id,)))
        
        return {
            'found': True,
            'wallet_id': wallet_id[:8] + '***',
            'nickname': wallet.get('nickname', 'Cliente'),
            'points_balance': wallet['points_balance'],
            'redeem_value': wallet['points_balance'] * self.PESO_PER_POINT,
            'can_redeem': wallet['points_balance'] >= self.MIN_REDEEM,
            'visit_count': wallet['visit_count'],
            'member_since': wallet['created_at'][:10],
            'history': history
        }
    
    def cleanup_expired(self) -> int:
        """Limpia puntos expirados."""
        if not self.core.db:
            logger.warning("Database not available for cleanup expired")
            return 0

        now = datetime.now().isoformat()

        # Encontrar transacciones expiradas
        expired = list(self.core.db.execute_query("""
            SELECT wallet_id, COALESCE(SUM(points), 0) as total
            FROM wallet_transactions
            WHERE type = 'EARN' AND expires_at < %s 
              AND points > 0
            GROUP BY wallet_id
        """, (now,)))
        
        for e in expired:
            self.core.db.execute_write("""
                UPDATE anonymous_wallet 
                SET points_balance = points_balance - %s
                WHERE wallet_id = %s
            """, (e['total'], e['wallet_id']))
        
        # Marcar como expiradas
        self.core.db.execute_write("""
            UPDATE wallet_transactions
            SET type = 'EXPIRED'
            WHERE type = 'EARN' AND expires_at < %s AND points > 0
        """, (now,))
        
        return len(expired)
    
    def get_top_customers(self, limit: int = 10) -> List[Dict]:
        """Top clientes por puntos acumulados."""
        if not self.core.db:
            logger.warning("Database not available for top customers")
            return []

        # Validar limite para evitar DoS
        limit = max(1, min(int(limit), 100))
        return list(self.core.db.execute_query("""
            SELECT wallet_id, nickname, phone, total_earned, 
                   points_balance, visit_count, last_visit
            FROM anonymous_wallet
            WHERE status = 'active'
            ORDER BY total_earned DESC
            LIMIT %s
        """, (limit,)))
    
    def migrate_to_midas(self, wallet_id: str, customer_id: int) -> Dict[str, Any]:
        """
        Migra un monedero anonimo a cuenta MIDAS completa.
        El cliente conserva todos sus puntos acumulados.

        Args:
            wallet_id: ID del monedero anonimo
            customer_id: ID del cliente recien registrado

        Returns:
            Dict con resultado de la migracion
        """
        if not self.core.db:
            logger.warning("Database not available for migrate to midas")
            return {'success': False, 'reason': 'Database not available'}

        wallet = self.find_wallet(wallet_id)
        if not wallet:
            return {'success': False, 'reason': 'Monedero no encontrado'}
        
        if wallet['points_balance'] <= 0:
            return {'success': False, 'reason': 'No hay puntos para migrar'}
        
        try:
            from src.core.loyalty_engine import LoyaltyEngine

            # Crear cuenta MIDAS usando DatabaseManager
            midas = LoyaltyEngine(self.core.db)
            account = midas.get_or_create_account(customer_id)
            
            if not account:
                return {'success': False, 'reason': 'No se pudo crear cuenta MIDAS'}
            
            # Transferir puntos
            points_to_transfer = Decimal(str(wallet['points_balance']))
            
            success = midas.acumular_puntos(
                customer_id=customer_id,
                monto=points_to_transfer,
                descripcion=f"Migración desde monedero anónimo {wallet_id[:8]}***"
            )
            
            if success:
                # Marcar monedero anónimo como migrado
                self.core.db.execute_write("""
                    UPDATE anonymous_wallet 
                    SET status = 'migrated', 
                        points_balance = 0,
                        nickname = %s
                    WHERE wallet_id = %s
                """, (f"Migrado a cliente #{customer_id}", wallet_id))
                
                logger.info(f"✅ Migración exitosa: {points_to_transfer} puntos de {wallet_id} a cliente {customer_id}")
                
                return {
                    'success': True,
                    'points_migrated': float(points_to_transfer),
                    'new_midas_balance': float(midas.get_balance(customer_id)),
                    'message': f'¡Migración exitosa! Tus {int(points_to_transfer)} puntos ahora están en tu cuenta MIDAS.'
                }
            else:
                return {'success': False, 'reason': 'Error al acumular puntos en MIDAS'}
                
        except Exception as e:
            logger.error(f"Error en migración: {e}")
            return {'success': False, 'reason': str(e)}
    
    @classmethod
    def get_config(cls, core) -> Dict[str, Any]:
        """
        Obtiene configuracion dinamica de puntos desde la DB.
        Permite cambiar ratios sin tocar codigo.
        """
        if not core.db:
            logger.warning("Database not available for get config")
            return {
                'points_per_peso': cls.POINTS_PER_PESO,
                'peso_per_point': cls.PESO_PER_POINT,
                'min_redeem': cls.MIN_REDEEM,
                'expiry_days': cls.POINTS_EXPIRY_DAYS,
            }

        try:
            # FIX B1 2026-01-30: Esquema app_config usa 'key'/'value', no 'config_key'/'config_value'
            result = list(core.db.execute_query("""
                SELECT key, value FROM app_config
                WHERE key IN ('anon_points_per_peso', 'anon_peso_per_point',
                              'anon_min_redeem', 'anon_expiry_days')
            """))

            config = {}
            for row in result:
                config[row['key']] = row['value']
            
            return {
                'points_per_peso': float(config.get('anon_points_per_peso', cls.POINTS_PER_PESO)),
                'peso_per_point': float(config.get('anon_peso_per_point', cls.PESO_PER_POINT)),
                'min_redeem': int(config.get('anon_min_redeem', cls.MIN_REDEEM)),
                'expiry_days': int(config.get('anon_expiry_days', cls.POINTS_EXPIRY_DAYS)),
            }
        except Exception:
            # Fallback a valores por defecto
            return {
                'points_per_peso': cls.POINTS_PER_PESO,
                'peso_per_point': cls.PESO_PER_POINT,
                'min_redeem': cls.MIN_REDEEM,
                'expiry_days': cls.POINTS_EXPIRY_DAYS,
            }

# Función de integración con ventas
def integrate_loyalty_with_sale(core, wallet_identifier: str, 
                                sale_total: Decimal, sale_id: int, 
                                serie: str) -> Dict:
    """
    Función helper para integrar con el flujo de venta.
    Llamar después de completar la venta Serie B.
    """
    loyalty = AnonymousLoyalty(core)
    
    # Buscar o crear monedero
    wallet = loyalty.find_wallet(wallet_identifier)
    
    if not wallet:
        # Si es teléfono, crear nuevo
        if wallet_identifier.isdigit() and len(wallet_identifier) >= 10:
            result = loyalty.create_wallet(phone=wallet_identifier)
            wallet_id = result['wallet_id']
        else:
            return {'success': False, 'reason': 'Cliente no encontrado'}
    else:
        wallet_id = wallet['wallet_id']
    
    # Acumular puntos
    return loyalty.earn_points(wallet_id, sale_total, sale_id, serie)

def migrate_anonymous_to_customer(core, phone: str, customer_data: Dict) -> Dict:
    """
    Flujo completo: Crear cliente + migrar puntos de monedero anónimo.
    
    Args:
        core: POSCore instance
        phone: Teléfono del monedero anónimo
        customer_data: Datos del nuevo cliente (name, rfc, email, etc.)
        
    Returns:
        Dict con resultado
    """
    loyalty = AnonymousLoyalty(core)
    
    # 1. Buscar monedero por teléfono
    wallet = loyalty.find_wallet(phone)
    if not wallet:
        return {'success': False, 'reason': 'No existe monedero con ese teléfono'}
    
    # 2. Crear cliente (con el mismo teléfono)
    customer_data['phone'] = phone
    try:
        customer_id = core.create_customer(customer_data)
    except Exception as e:
        return {'success': False, 'reason': f'Error al crear cliente: {e}'}
    
    # 3. Migrar puntos
    migration_result = loyalty.migrate_to_midas(wallet['wallet_id'], customer_id)
    
    if migration_result['success']:
        return {
            'success': True,
            'customer_id': customer_id,
            'points_migrated': migration_result['points_migrated'],
            'message': f"Cliente creado y {migration_result['points_migrated']} puntos migrados a MIDAS"
        }
    else:
        return {
            'success': True,  # Cliente sí se creó
            'customer_id': customer_id,
            'points_migrated': 0,
            'warning': f"Cliente creado pero migración falló: {migration_result['reason']}"
        }

