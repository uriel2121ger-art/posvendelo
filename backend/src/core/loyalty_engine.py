"""
PROTOCOLO MIDAS - LOYALTY ENGINE
Motor de Lealtad, Cashback Dinámico y Prevención de Fraude

Este módulo es el cerebro del sistema de monedero electrónico.
$1 Punto = $1 Peso (configurable)
"""

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime, timedelta
import decimal  # FIX 2026-02-01: Import módulo completo para decimal.InvalidOperation
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
import hashlib
import logging

if TYPE_CHECKING:
    from src.infra.database import DatabaseManager

logger = logging.getLogger("MIDAS_ENGINE")

class TransactionType(Enum):
    """Tipos de transacciones en el ledger"""
    EARN = "EARN"  # Acumulación de puntos
    REDEEM = "REDEEM"  # Redención de puntos
    EXPIRE = "EXPIRE"  # Expiración
    ADJUST = "ADJUST"  # Ajuste manual
    REFUND = "REFUND"  # Devolución
    BONUS = "BONUS"  # Bonificación especial

class LoyaltyTier(Enum):
    """Niveles de lealtad"""
    BRONCE = "BRONCE"
    PLATA = "PLATA"
    ORO = "ORO"
    PLATINO = "PLATINO"

class FraudAlertType(Enum):
    """Tipos de alertas de fraude"""
    VELOCITY = "VELOCITY"  # Demasiadas transacciones en poco tiempo
    ANOMALY = "ANOMALY"  # Comportamiento anómalo
    MANUAL = "MANUAL"  # Marcado manualmente

@dataclass
class CashbackResult:
    """Resultado del cálculo de cashback"""
    total_puntos: Decimal
    desglose: List[Dict[str, Any]]  # Detalle por producto
    reglas_aplicadas: List[str]
    advertencias: List[str]

@dataclass
class LoyaltyAccount:
    """Cuenta de lealtad de un cliente"""
    id: int
    customer_id: int
    saldo_actual: Decimal
    nivel_lealtad: str
    status: str
    flags_fraude: int

class LoyaltyEngine:
    """
    Motor de Lealtad y Cashback Dinámico
    
    Este es el corazón del sistema MIDAS. Maneja:
    - Cálculo de cashback basado en reglas complejas
    - Acumulación y redención de puntos
    - Prevención de fraude
    - Auditoría completa
    """
    
    def __init__(self, db_manager: "DatabaseManager"):
        """
        Inicializa el motor de lealtad.
        
        Args:
            db_manager: DatabaseManager instance (supports SQLite and PostgreSQL)
        """
        self.db = db_manager
        self._ensure_schema()
    
    def _ensure_schema(self):
        """Aplica el esquema de lealtad si no existe (solo estructura, no datos)"""
        try:
            from pathlib import Path

            # Check if schema already applied (loyalty_accounts table exists)
            tables = self.db.list_tables()
            tables_exist = 'loyalty_accounts' in tables
            
            # If tables exist, don't re-apply schema (preserves user rules)
            if tables_exist:
                # Just verify the rules table exists
                rules = self.db.execute_query("SELECT COUNT(*) as count FROM loyalty_rules")
                rule_count = rules[0].get('count', 0) if rules and len(rules) > 0 and rules[0] else 0
                logger.info(f"✅ MIDAS Schema already exists ({rule_count} rules configured)")
                return
            
            # First time setup - apply full schema
            current_file = Path(__file__).resolve()
            schema_path = current_file.parent.parent / "infra" / "loyalty_schema.sql"
            
            if not schema_path.exists():
                root_dir = current_file.parent
                while not (root_dir / "pos_app.py").exists() and root_dir.parent != root_dir:
                    root_dir = root_dir.parent
                schema_path = root_dir / "src" / "infra" / "loyalty_schema.sql"
            
            if schema_path.exists():
                with open(schema_path, "r", encoding="utf-8") as f:
                    schema_sql = f.read()
                # Execute schema script (may contain multiple statements)
                # DatabaseManager handles this via execute_transaction or individual statements
                # Split by semicolon and execute each statement
                statements = [s.strip() for s in schema_sql.split(';') if s.strip()]
                operations = [(stmt, ()) for stmt in statements if stmt]
                if operations:
                    self.db.execute_transaction(operations)
                logger.info(f"✅ MIDAS Schema Applied Successfully from {schema_path}")
            else:
                logger.warning(f"⚠️ Loyalty schema not found. Searched: {schema_path}")
        except Exception as e:
            logger.error(f"❌ Failed to apply loyalty schema: {e}")
    
    # =========================================================================
    # GESTIÓN DE CUENTAS
    # =========================================================================
    
    def get_or_create_account(self, customer_id: int) -> Optional[LoyaltyAccount]:
        """
        Obtiene o crea una cuenta de lealtad para un cliente.
        
        Args:
            customer_id: ID del cliente
            
        Returns:
            LoyaltyAccount o None si hay error
        """
        try:
            rows = self.db.execute_query(
                "SELECT * FROM loyalty_accounts WHERE customer_id = %s",
                (customer_id,)
            )
            
            if rows and len(rows) > 0 and rows[0]:
                row = dict(rows[0])
                return LoyaltyAccount(
                    id=row.get('id'),
                    customer_id=row.get('customer_id'),
                    saldo_actual=Decimal(str(row.get('saldo_actual', 0))),
                    nivel_lealtad=row.get('nivel_lealtad', 'BRONCE'),
                    status=row.get('status', 'ACTIVE'),
                    flags_fraude=row.get('flags_fraude', 0)
                )
            else:
                # Crear nueva cuenta
                self.db.execute_write("""
                    INSERT INTO loyalty_accounts (customer_id, saldo_actual, nivel_lealtad, status, synced)
                    VALUES (%s, 0.00, 'BRONCE', 'ACTIVE', 0)
                """, (customer_id,))
                
                logger.info(f"🎉 Nueva cuenta de lealtad creada para cliente {customer_id}")
                print(f">>> MIDAS DEBUG: Nueva cuenta creada para cliente {customer_id} con status ACTIVE")
                
                # Obtener la cuenta recién creada
                return self.get_or_create_account(customer_id)
                
        except Exception as e:
            logger.error(f"Error al obtener/crear cuenta de lealtad: {e}")
            return None
    
    def get_balance(self, customer_id: int) -> Decimal:
        """
        Obtiene el saldo actual de puntos de un cliente.
        
        Args:
            customer_id: ID del cliente
            
        Returns:
            Saldo en puntos (Decimal)
        """
        account = self.get_or_create_account(customer_id)
        return account.saldo_actual if account else Decimal('0.00')
    
    # =========================================================================
    # MOTOR DE REGLAS Y CÁLCULO DE CASHBACK
    # =========================================================================
    
    def get_active_rules(self, fecha_hora: Optional[datetime] = None) -> List[Dict]:
        """
        Obtiene todas las reglas activas para una fecha/hora específica.
        
        Args:
            fecha_hora: Fecha y hora para verificar vigencia (default: ahora)
            
        Returns:
            Lista de reglas activas ordenadas por prioridad
        """
        if fecha_hora is None:
            fecha_hora = datetime.now()
        
        fecha_str = fecha_hora.strftime("%Y-%m-%d %H:%M:%S")
        dia_semana = fecha_hora.weekday()  # 0=Lunes, 6=Domingo
        
        # Mapeo de día de semana a columna
        dias_cols = [
            'aplica_lunes', 'aplica_martes', 'aplica_miercoles',
            'aplica_jueves', 'aplica_viernes', 'aplica_sabado', 'aplica_domingo'
        ]
        dia_col = dias_cols[dia_semana]
        
        try:
            query = f"""
                SELECT * FROM loyalty_rules
                WHERE activo = 1
                AND {dia_col} = 1
                AND (vigencia_inicio IS NULL OR vigencia_inicio <= %s)
                AND (vigencia_fin IS NULL OR vigencia_fin >= %s)
                ORDER BY prioridad DESC, multiplicador DESC
            """
            
            rows = self.db.execute_query(query, (fecha_str, fecha_str))
            rules = [dict(row) for row in rows]
            
            logger.debug(f"📋 {len(rules)} reglas activas para {fecha_str}")
            return rules
            
        except Exception as e:
            logger.error(f"Error al obtener reglas activas: {e}")
            return []
    
    def calcular_cashback_potencial(
        self, 
        carrito: List[Dict[str, Any]], 
        customer_id: Optional[int] = None
    ) -> CashbackResult:
        """
        Calcula cuántos puntos generará una compra ANTES de cobrarla.
        
        Esta es la función clave para mostrar al cliente cuánto ganará.
        
        Args:
            carrito: Lista de productos [{'product_id', 'qty', 'price', 'category_id'}]
            customer_id: ID del cliente (para verificar nivel de lealtad)
            
        Returns:
            CashbackResult con el desglose completo
        """
        total_puntos = Decimal('0.00')
        desglose = []
        reglas_aplicadas = set()
        advertencias = []
        
        # Obtener nivel de lealtad del cliente
        nivel_lealtad = "BRONCE"
        if customer_id:
            account = self.get_or_create_account(customer_id)
            if account:
                nivel_lealtad = account.nivel_lealtad
        
        # Obtener reglas activas
        reglas = self.get_active_rules()
        
        # Procesar cada producto del carrito
        for item in carrito:
            product_id = item.get('product_id')
            qty = Decimal(str(item.get('qty', 1)))
            price = Decimal(str(item.get('price', 0)))
            category_id = item.get('category_id')
            
            subtotal = qty * price
            mejor_regla = None
            mejor_cashback = Decimal('0.00')
            
            # Buscar la MEJOR regla aplicable para este producto
            for regla in reglas:
                # Verificar si la regla aplica a este producto
                if not self._regla_aplica(regla, product_id, category_id, nivel_lealtad):
                    continue
                
                # Verificar monto mínimo
                monto_minimo = Decimal(str(regla.get('monto_minimo', 0)))
                if subtotal < monto_minimo:
                    continue
                
                # Calcular cashback con esta regla
                multiplicador = Decimal(str(regla['multiplicador']))
                cashback = (subtotal * multiplicador).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
                
                # Verificar límite máximo de puntos
                monto_maximo = regla.get('monto_maximo_puntos')
                if monto_maximo:
                    monto_maximo = Decimal(str(monto_maximo))
                    if cashback > monto_maximo:
                        cashback = monto_maximo
                        advertencias.append(
                            f"Cashback limitado a ${monto_maximo} por regla '{regla['nombre_display']}'"
                        )
                
                # ¿Es la mejor regla hasta ahora?
                if cashback > mejor_cashback:
                    mejor_cashback = cashback
                    mejor_regla = regla
            
            # Aplicar la mejor regla encontrada
            if mejor_regla:
                total_puntos += mejor_cashback
                reglas_aplicadas.add(mejor_regla['regla_id'])
                
                desglose.append({
                    'product_id': product_id,
                    'subtotal': float(subtotal),
                    'cashback': float(mejor_cashback),
                    'porcentaje': float(mejor_regla['multiplicador'] * 100),
                    'regla': mejor_regla['nombre_display']
                })
            else:
                # Sin regla aplicable
                desglose.append({
                    'product_id': product_id,
                    'subtotal': float(subtotal),
                    'cashback': 0.00,
                    'porcentaje': 0.00,
                    'regla': 'Sin cashback'
                })
        
        # Verificar anomalías
        if carrito:
            total_venta = sum(Decimal(str(item.get('qty', 1))) * Decimal(str(item.get('price', 0))) 
                            for item in carrito)
            if total_venta > 0:
                porcentaje_total = (total_puntos / total_venta) * 100
                
                # Alerta si el cashback excede el 20% (posible error de configuración)
                if porcentaje_total > 20:
                    advertencias.append(
                        f"⚠️ ALERTA: Cashback de {porcentaje_total:.1f}% es inusualmente alto. "
                        "Verificar configuración de reglas."
                    )
        
        return CashbackResult(
            total_puntos=total_puntos,
            desglose=desglose,
            reglas_aplicadas=list(reglas_aplicadas),
            advertencias=advertencias
        )
    
    def _regla_aplica(
        self, 
        regla: Dict, 
        product_id: Optional[int], 
        category_id: Optional[int],
        nivel_lealtad: str
    ) -> bool:
        """
        Determina si una regla aplica a un producto específico.
        
        Args:
            regla: Diccionario con la regla
            product_id: ID del producto
            category_id: ID de la categoría del producto
            nivel_lealtad: Nivel del cliente
            
        Returns:
            True si la regla aplica
        """
        condicion_tipo = regla.get('condicion_tipo', 'GLOBAL')
        condicion_valor = regla.get('condicion_valor')
        
        # Verificar nivel de lealtad
        niveles_aplicables = regla.get('aplica_niveles', 'BRONCE,PLATA,ORO,PLATINO')
        if nivel_lealtad not in niveles_aplicables:
            return False
        
        # Regla global: aplica a todo
        if condicion_tipo == 'GLOBAL':
            return True
        
        # Regla por categoría
        if condicion_tipo == 'CATEGORIA' and category_id:
            try:
                categoria_objetivo = int(condicion_valor)
                return category_id == categoria_objetivo
            except (ValueError, TypeError):
                return False
        
        # Regla por producto específico
        if condicion_tipo == 'PRODUCTO' and product_id:
            try:
                producto_objetivo = int(condicion_valor)
                return product_id == producto_objetivo
            except (ValueError, TypeError):
                return False
        
        return False
    
    # =========================================================================
    # ACUMULACIÓN DE PUNTOS
    # =========================================================================
    
    def acumular_puntos(
        self,
        customer_id: int,
        monto: Decimal,
        ticket_id: Optional[int] = None,
        turn_id: Optional[int] = None,
        user_id: Optional[int] = None,
        carrito: Optional[List[Dict]] = None,
        descripcion: str = "Compra",
        global_cashback_percent: Optional[Decimal] = None
    ) -> bool:
        """
        Acumula puntos en la cuenta de un cliente.
        
        Args:
            customer_id: ID del cliente
            monto: Monto en puntos a acumular
            ticket_id: ID del ticket de venta
            turn_id: ID del turno
            user_id: ID del usuario que procesó
            carrito: Carrito para calcular reglas (opcional)
            descripcion: Descripción de la transacción
            global_cashback_percent: Porcentaje global de cashback (fallback si no hay reglas)
            
        Returns:
            True si se acumuló correctamente
        """
        import math

        # ===== VALIDACIONES WTF =====
        if customer_id is None:
            raise ValueError("customer_id es requerido")
        if isinstance(customer_id, (list, dict, tuple)):
            raise ValueError(f"customer_id inválido: {type(customer_id).__name__}")
        try:
            customer_id = int(customer_id)
            if customer_id <= 0:
                raise ValueError(f"customer_id debe ser mayor a 0: {customer_id}")
        except (TypeError, ValueError) as e:
            raise ValueError(f"customer_id inválido: {e}")
        
        # Validar monto si no hay carrito
        if carrito is None:
            if monto is None:
                raise ValueError("monto es requerido cuando no hay carrito")
            if isinstance(monto, (list, dict, tuple)):
                raise ValueError(f"monto inválido: {type(monto).__name__}")
            try:
                monto = Decimal(str(monto))
                if math.isnan(float(monto)) or math.isinf(float(monto)):
                    raise ValueError("monto no puede ser NaN o Infinito")
            except (ValueError, TypeError, decimal.InvalidOperation):
                raise ValueError(f"monto inválido: {monto}")
        
        try:
            # Obtener o crear cuenta
            account = self.get_or_create_account(customer_id)
            if not account:
                print(f">>> MIDAS DEBUG: No se pudo obtener cuenta para cliente {customer_id}")
                logger.error(f"No se pudo obtener cuenta para cliente {customer_id}")
                return False
            
            # Verificar si la cuenta está bloqueada
            if account.status != 'ACTIVE':
                print(f">>> MIDAS DEBUG: Cuenta {account.id} bloqueada: {account.status}")
                logger.warning(f"Cuenta {account.id} está bloqueada ({account.status})")
                return False
            
            # Calcular el cashback si tenemos el carrito
            if carrito:
                resultado = self.calcular_cashback_potencial(carrito, customer_id)
                
                # Si no hay reglas configuradas, usar porcentaje global como fallback
                if resultado.total_puntos == Decimal('0.00') and global_cashback_percent:
                    # Calcular total del carrito
                    total_carrito = sum(
                        Decimal(str(item.get('qty', 1))) * Decimal(str(item.get('price', 0)))
                        for item in carrito
                    )
                    monto = (total_carrito * global_cashback_percent / 100).quantize(
                        Decimal('0.01'), rounding=ROUND_HALF_UP
                    )
                    regla_aplicada = f'Global {float(global_cashback_percent)}%'
                    print(f">>> MIDAS DEBUG: Using global {global_cashback_percent}% = ${monto} on total ${total_carrito}")
                    logger.info(f"💡 Using global cashback: {global_cashback_percent}% = ${monto}")
                else:
                    monto = resultado.total_puntos
                    regla_aplicada = ', '.join(resultado.reglas_aplicadas) if resultado.reglas_aplicadas else 'Ninguna'
            else:
                regla_aplicada = 'Manual'
            
            # Redondear a 2 decimales
            monto = monto.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            if monto <= 0:
                print(f">>> MIDAS DEBUG: monto <= 0, monto={monto}")
                logger.warning(f"⚠️ No hay puntos para acumular para cliente {customer_id}: monto={monto}")
                return True  # No es error, simplemente no hay puntos
            
            # FRAUD CHECK: Velocity Check
            if not self._velocity_check(customer_id):
                logger.warning(f"🚨 VELOCITY CHECK FAILED para cliente {customer_id}")
                self._flag_fraud(
                    account.id, 
                    customer_id, 
                    FraudAlertType.VELOCITY,
                    f"Demasiadas acumulaciones en corto tiempo",
                    monto
                )
                return False
            
            # Calcular nuevo saldo
            saldo_anterior = account.saldo_actual
            saldo_nuevo = saldo_anterior + monto
            
            # Generar hash de seguridad
            hash_data = f"{customer_id}:{monto}:{saldo_nuevo}:{datetime.now().isoformat()}"
            hash_seguridad = hashlib.sha256(hash_data.encode()).hexdigest()
            
            # Registrar en el ledger y actualizar cuenta atómicamente
            operations = [
                (
                    """
                    INSERT INTO loyalty_ledger (
                        account_id, customer_id, fecha_hora, tipo, monto, saldo_anterior, saldo_nuevo,
                        ticket_referencia_id, turn_id, user_id, descripcion, regla_aplicada,
                        hash_seguridad
                    ) VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        account.id, customer_id, TransactionType.EARN.value, float(monto),
                        float(saldo_anterior), float(saldo_nuevo), ticket_id, turn_id, user_id,
                        descripcion, regla_aplicada, hash_seguridad
                    )
                ),
                (
                    """
                    UPDATE loyalty_accounts
                    SET saldo_actual = %s, fecha_ultima_actividad = NOW(), synced = 0
                    WHERE id = %s
                    """,
                    (float(saldo_nuevo), account.id)
                )
            ]

            # SYNC: Actualizar también customers.wallet_balance para mantener coherencia
            try:
                operations.append((
                    "UPDATE customers SET wallet_balance = %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (float(saldo_nuevo), customer_id)
                ))
            except Exception as sync_err:
                logger.warning(f"No se pudo sincronizar wallet_balance: {sync_err}")

            # Ejecutar todas las operaciones atómicamente
            # CRÍTICO: Auditoría 2026-01-30 - Verificar resultado de transacción
            result = self.db.execute_transaction(operations)
            success = result.get('success') if isinstance(result, dict) else result
            if not success:
                logger.error(f"Transaction failed for acumular_puntos: cliente {customer_id}, monto {monto}")
                return False

            # Verificar si subió de nivel (después de la transacción)
            self._check_tier_upgrade(customer_id, saldo_nuevo)

            logger.info(
                f"💰 Puntos acumulados: Cliente {customer_id} ganó ${monto} puntos. "
                f"Nuevo saldo: ${saldo_nuevo}"
            )

            return True

        except Exception as e:
            logger.error(f"Error al acumular puntos: {e}")
            return False
    
    # =========================================================================
    # REDENCIÓN DE PUNTOS
    # =========================================================================
    
    def redimir_puntos(
        self,
        customer_id: int,
        monto: Decimal,
        ticket_id: Optional[int] = None,
        turn_id: Optional[int] = None,
        user_id: Optional[int] = None,
        require_otp: bool = False,
        descripcion: str = "Pago con puntos"
    ) -> Tuple[bool, str]:
        """
        Redime (usa) puntos de la cuenta de un cliente.
        
        Args:
            customer_id: ID del cliente
            monto: Monto en puntos a redimir
            ticket_id: ID del ticket de venta
            turn_id: ID del turno
            user_id: ID del usuario que procesó
            require_otp: Si se requiere OTP para montos grandes
            descripcion: Descripción de la transacción
            
        Returns:
            (éxito, mensaje)
        """
        import math

        # ===== VALIDACIONES WTF =====
        if customer_id is None:
            raise ValueError("customer_id es requerido")
        if isinstance(customer_id, (list, dict, tuple)):
            raise ValueError(f"customer_id inválido: {type(customer_id).__name__}")
        try:
            customer_id = int(customer_id)
            if customer_id <= 0:
                raise ValueError(f"customer_id debe ser mayor a 0: {customer_id}")
        except (TypeError, ValueError) as e:
            raise ValueError(f"customer_id inválido: {e}")
        
        if monto is None:
            raise ValueError("monto es requerido")
        if isinstance(monto, (list, dict, tuple)):
            raise ValueError(f"monto inválido: {type(monto).__name__}")
        try:
            monto = Decimal(str(monto))
            if math.isnan(float(monto)) or math.isinf(float(monto)):
                raise ValueError("monto no puede ser NaN o Infinito")
            if monto <= 0:
                raise ValueError(f"monto debe ser mayor a 0: {monto}")
        except Exception:
            raise ValueError(f"monto inválido: {monto}")
        
        try:
            # Obtener cuenta
            account = self.get_or_create_account(customer_id)
            if not account:
                return False, "No se pudo obtener la cuenta del cliente"
            
            # Verificar estado de la cuenta
            if account.status != 'ACTIVE':
                return False, f"La cuenta está {account.status}. No se pueden redimir puntos."
            
            # Redondear a 2 decimales
            monto = monto.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Validar saldo suficiente
            if monto > account.saldo_actual:
                return False, f"Saldo insuficiente. Disponible: ${account.saldo_actual}, Solicitado: ${monto}"
            
            # OTP Simulado para montos grandes (preparación para SMS)
            if require_otp and monto > Decimal('500.00'):
                # TODO [CRITICAL]: Implementar OTP real antes de producción
                # Requiere: integración con Twilio/SMS Gateway, tabla otp_codes,
                # validación de códigos con expiración de 5 min
                logger.info(f"OTP simulado - Redencion de ${monto} requeriria OTP en produccion")
            
            # Calcular nuevo saldo
            saldo_anterior = account.saldo_actual
            saldo_nuevo = saldo_anterior - monto
            
            # Generar hash de seguridad
            hash_data = f"{customer_id}:-{monto}:{saldo_nuevo}:{datetime.now().isoformat()}"
            hash_seguridad = hashlib.sha256(hash_data.encode()).hexdigest()
            
            # Registrar en el ledger y actualizar cuenta atómicamente
            operations = [
                (
                    """
                    INSERT INTO loyalty_ledger (
                        account_id, customer_id, fecha_hora, tipo, monto, saldo_anterior, saldo_nuevo,
                        ticket_referencia_id, turn_id, user_id, descripcion, hash_seguridad
                    ) VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        account.id, customer_id, TransactionType.REDEEM.value, float(-monto),
                        float(saldo_anterior), float(saldo_nuevo), ticket_id, turn_id, user_id,
                        descripcion, hash_seguridad
                    )
                ),
                (
                    """
                    UPDATE loyalty_accounts
                    SET saldo_actual = %s, fecha_ultima_actividad = NOW(), synced = 0
                    WHERE id = %s AND saldo_actual >= %s
                    """,
                    (float(saldo_nuevo), account.id, float(monto))
                )
            ]

            # SYNC: Actualizar también customers.wallet_balance
            try:
                operations.append((
                    "UPDATE customers SET wallet_balance = %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (float(saldo_nuevo), customer_id)
                ))
            except Exception as sync_err:
                logger.warning(f"No se pudo sincronizar wallet_balance: {sync_err}")

            # Ejecutar todas las operaciones atómicamente
            # CRÍTICO: Auditoría 2026-01-30 - Verificar resultado de transacción
            result = self.db.execute_transaction(operations)
            success = result.get('success') if isinstance(result, dict) else result
            if not success:
                logger.error(f"Transaction failed for redimir_puntos: cliente {customer_id}, monto {monto}")
                return False, "Error al guardar la redención en la base de datos"

            logger.info(
                f"💳 Puntos redimidos: Cliente {customer_id} usó ${monto} puntos. "
                f"Nuevo saldo: ${saldo_nuevo}"
            )

            return True, f"Redención exitosa. Nuevo saldo: ${saldo_nuevo}"

        except Exception as e:
            logger.error(f"Error al redimir puntos: {e}")
            return False, f"Error al procesar redención: {str(e)}"
    
    # =========================================================================
    # PREVENCIÓN DE FRAUDE (THE SHIELD)
    # =========================================================================
    
    def _velocity_check(self, customer_id: int, ventana_segundos: int = 3600) -> bool:
        """
        Verifica si el cliente está acumulando puntos demasiado rápido.
        
        Args:
            customer_id: ID del cliente
            ventana_segundos: Ventana de tiempo en segundos (default: 1 hora)
            
        Returns:
            True si pasa la verificación, False si es sospechoso
        """
        try:
            ventana_inicio = (datetime.now() - timedelta(seconds=ventana_segundos)).strftime("%Y-%m-%d %H:%M:%S")
            
            rows = self.db.execute_query(
                """
                SELECT COUNT(*) as cuenta
                FROM loyalty_ledger
                WHERE customer_id = %s
                AND tipo = %s
                AND fecha_hora >= %s
                """,
                (customer_id, TransactionType.EARN.value, ventana_inicio)
            )
            
            cuenta = rows[0].get('cuenta', 0) if rows and len(rows) > 0 and rows[0] else 0
            
            # Si tiene 20 o más transacciones en 1 hora, es sospechoso
            # Esto permite compras múltiples normales pero detecta fraude
            if cuenta >= 20:
                logger.warning(f"🚨 Velocity check: Cliente {customer_id} tiene {cuenta} acumulaciones en {ventana_segundos}s")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error en velocity check: {e}")
            return True  # En caso de error, permitir la operación
    
    def _flag_fraud(
        self, 
        account_id: int, 
        customer_id: int, 
        tipo: FraudAlertType,
        descripcion: str,
        monto: Decimal
    ):
        """
        Registra una alerta de fraude y bloquea la cuenta si es necesario.
        
        Args:
            account_id: ID de la cuenta
            customer_id: ID del cliente
            tipo: Tipo de alerta
            descripcion: Descripción del incidente
            monto: Monto involucrado
        """
        try:
            # Registrar en el log de fraude y actualizar cuenta atómicamente
            operations = [
                (
                    """
                    INSERT INTO loyalty_fraud_log (
                        account_id, customer_id, tipo_alerta, descripcion, severidad,
                        monto_involucrado, accion
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (account_id, customer_id, tipo.value, descripcion, 'HIGH', float(monto), 'FLAGGED')
                ),
                (
                    """
                    UPDATE loyalty_accounts
                    SET flags_fraude = flags_fraude + 1,
                        ultima_alerta = NOW()
                    WHERE id = %s
                    """,
                    (account_id,)
                )
            ]
            
            # Ejecutar operaciones
            self.db.execute_transaction(operations)
            
            # Verificar si tiene 3 o más flags y bloquear
            # CRITICAL FIX: Leer flags_fraude después de la transacción para verificar bloqueo
            accounts = self.db.execute_query(
                "SELECT flags_fraude FROM loyalty_accounts WHERE id = %s",
                (account_id,)
            )
            
            if accounts and len(accounts) > 0 and accounts[0] and accounts[0].get('flags_fraude', 0) >= 3:
                # CRITICAL FIX: El bloqueo se hace en una transacción separada
                # porque necesitamos leer el valor actualizado después del INSERT
                # Esto es aceptable porque el bloqueo es una acción post-fraude
                # y no afecta la integridad de los datos de fraude registrados
                self.db.execute_write(
                    "UPDATE loyalty_accounts SET status = 'SUSPENDED', updated_at = CURRENT_TIMESTAMP, synced = 0 WHERE id = %s",
                    (account_id,)
                )
                logger.critical(f"🔒 Cuenta {account_id} BLOQUEADA por múltiples alertas de fraude")
            
        except Exception as e:
            logger.error(f"Error al registrar fraude: {e}")
    
    # =========================================================================
    # GAMIFICACIÓN Y NIVELES
    # =========================================================================
    
    def _check_tier_upgrade(self, customer_id: int, saldo_actual: Decimal):
        """
        Verifica si el cliente debe subir de nivel.
        
        Lógica simple:
        - BRONCE: 0 - 999 puntos
        - PLATA: 1,000 - 4,999 puntos
        - ORO: 5,000 - 19,999 puntos
        - PLATINO: 20,000+ puntos
        """
        try:
            # Determinar nuevo nivel
            if saldo_actual >= Decimal('20000'):
                nuevo_nivel = LoyaltyTier.PLATINO.value
            elif saldo_actual >= Decimal('5000'):
                nuevo_nivel = LoyaltyTier.ORO.value
            elif saldo_actual >= Decimal('1000'):
                nuevo_nivel = LoyaltyTier.PLATA.value
            else:
                nuevo_nivel = LoyaltyTier.BRONCE.value
            
            # Obtener nivel actual
            accounts = self.db.execute_query(
                "SELECT nivel_lealtad FROM loyalty_accounts WHERE customer_id = %s",
                (customer_id,)
            )
            nivel_actual = accounts[0].get('nivel_lealtad', 'BRONCE') if accounts and len(accounts) > 0 and accounts[0] else 'BRONCE'
            
            # Si cambió el nivel, actualizarlo
            if nuevo_nivel != nivel_actual:
                operations = [
                    (
                        "UPDATE loyalty_accounts SET nivel_lealtad = %s, updated_at = CURRENT_TIMESTAMP, synced = 0 WHERE customer_id = %s",
                        (nuevo_nivel, customer_id)
                    ),
                    (
                        """
                        INSERT INTO loyalty_tier_history (customer_id, nivel_anterior, nivel_nuevo, razon)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (customer_id, nivel_actual, nuevo_nivel, f"Alcanzó ${saldo_actual} en puntos")
                    )
                ]
                
                self.db.execute_transaction(operations)
                
                logger.info(f"🎖️ Cliente {customer_id} subió de {nivel_actual} a {nuevo_nivel}!")
                
        except Exception as e:
            logger.error(f"Error al verificar tier upgrade: {e}")
    
    # =========================================================================
    # HISTORIAL Y REPORTES
    # =========================================================================
    
    def get_transaction_history(
        self, 
        customer_id: int, 
        limit: int = 50
    ) -> List[Dict]:
        """
        Obtiene el historial de transacciones de un cliente.
        
        Args:
            customer_id: ID del cliente
            limit: Número máximo de registros
            
        Returns:
            Lista de transacciones
        """
        try:
            rows = self.db.execute_query(
                """
                SELECT * FROM loyalty_ledger
                WHERE customer_id = %s
                ORDER BY fecha_hora DESC
                LIMIT %s
                """,
                (customer_id, limit)
            )
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error al obtener historial: {e}")
            return []
    
    # =========================================================================
    # API READINESS (Preparación para App Móvil)
    # =========================================================================
    
    def exportar_movimientos_cliente(self, customer_id: int) -> Dict[str, Any]:
        """
        Exporta los movimientos de un cliente en formato JSON listo para API.
        
        Este JSON puede ser consumido directamente por Firebase o una API REST.
        
        Args:
            customer_id: ID del cliente
            
        Returns:
            Diccionario con la estructura lista para API
        """
        try:
            account = self.get_or_create_account(customer_id)
            transactions = self.get_transaction_history(customer_id, limit=50)
            
            # Obtener datos del cliente
            customers = self.db.execute_query(
                "SELECT name, email, phone FROM customers WHERE id = %s",
                (customer_id,)
            )
            customer_row = dict(customers[0]) if customers and len(customers) > 0 and customers[0] else None
            
            # FIX 2026-01-30: Obtener nombre de sucursal de configuración
            store_name = "Sucursal Principal"
            try:
                config_result = self.db.execute_query(
                    "SELECT value FROM app_config WHERE key = 'branch_name' LIMIT 1"
                )
                if config_result and len(config_result) > 0 and config_result[0]:
                    store_name = config_result[0].get('value', store_name) or store_name
            except Exception:
                pass  # Usar valor por defecto si no existe

            # Formatear transacciones
            formatted_transactions = []
            for tx in transactions:
                formatted_transactions.append({
                    "date": tx['fecha_hora'],
                    "type": "BUY" if tx['tipo'] == 'EARN' else "USE" if tx['tipo'] == 'REDEEM' else tx['tipo'],
                    "amount": float(tx['monto']),
                    "balance_after": float(tx['saldo_nuevo']),
                    "description": tx['descripcion'],
                    "store": store_name
                })
            
            return {
                "user_id": customer_id,
                "name": customer_row['name'] if customer_row else "Cliente",
                "email": customer_row['email'] if customer_row else None,
                "phone": customer_row['phone'] if customer_row else None,
                "balance": float(account.saldo_actual) if account else 0.00,
                "tier": account.nivel_lealtad if account else "BRONCE",
                "last_transactions": formatted_transactions,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error al exportar movimientos: {e}")
            return {
                "user_id": customer_id,
                "error": str(e),
                "balance": 0.00,
                "last_transactions": []
            }
    
    def __del__(self):
        """Cleanup (DatabaseManager maneja las conexiones automáticamente)"""
        pass
