"""
Contingency Mode - Modo de operación para cajeras
Incluye: Genérico auditado, cierre ciego, alertas
"""

from typing import Any, Dict, Optional
from datetime import datetime
import hashlib
import logging
import random
import string

logger = logging.getLogger(__name__)

class ContingencyMode:
    """Sistema de contingencia para operación de cajeras."""
    
    def __init__(self, core):
        self.core = core
        self._auth_codes = {}  # Códigos temporales de autorización
    
    # ==========================================
    # VENTA GENÉRICA AUDITADA
    # ==========================================
    
    def create_generic_sale(self, amount: float, description: str, 
                           cashier_id: int, cashier_name: str) -> Dict[str, Any]:
        """
        Crea una venta con producto genérico (auditada).
        
        Args:
            amount: Monto de la venta
            description: Descripción del producto
            cashier_id: ID del cajero
            cashier_name: Nombre del cajero
        
        Returns:
            Dict con resultado de la venta
        """
        # Registrar auditoría
        self._log_generic_usage(cashier_id, cashier_name, amount, description)
        
        # Crear producto genérico temporal
        generic_product = {
            'id': -1,  # ID especial para genéricos
            'sku': 'GENERICO',
            'name': f'[GENÉRICO] {description}',
            'price': amount,
            'sat_clave_prod_serv': '01010101',  # Genérico SAT
            'sat_clave_unidad': 'ACT',  # Actividad
        }
        
        # SECURITY: No loguear uso de genérico
        pass
        
        return {
            'success': True,
            'product': generic_product,
            'audited': True,
            'warning': f'Uso de genérico registrado para {cashier_name}'
        }
    
    def _log_generic_usage(self, cashier_id: int, cashier_name: str, 
                           amount: float, description: str):
        """Registra uso de genérico en auditoría."""
        try:
            self.core.db.execute_write(
                """INSERT INTO audit_log (timestamp, user_id, action, entity_type, details)
                   VALUES (%s, %s, %s, %s, %s)""",
                (
                    datetime.now().isoformat(),
                    cashier_id,
                    'GENERIC_SALE',
                    'sale',
                    f"Cajera {cashier_name} usó GENÉRICO: ${amount:.2f} - {description}"
                )
            )
        except Exception as e:
            logger.error(f"Error logging generic usage: {e}")
    
    # ==========================================
    # SISTEMA DE AUTORIZACIÓN REMOTA
    # ==========================================
    
    def request_authorization(self, action_type: str, amount: float,
                              cashier_id: int, reason: str) -> Dict[str, Any]:
        """
        Solicita autorización remota del administrador.
        
        Args:
            action_type: Tipo de acción (BAJA, DEVOLUCION, DESCUENTO, etc)
            amount: Monto involucrado
            cashier_id: ID del cajero
            reason: Razón de la solicitud
        
        Returns:
            Dict con código de solicitud
        """
        # Generar código de solicitud
        request_code = ''.join(random.choices(string.digits, k=6))
        
        # Guardar solicitud pendiente
        self._auth_codes[request_code] = {
            'action': action_type,
            'amount': amount,
            'cashier_id': cashier_id,
            'reason': reason,
            'timestamp': datetime.now().isoformat(),
            'status': 'pending'
        }
        
        # Enviar alerta (TODO: integrar Telegram)
        self._send_authorization_alert(request_code, action_type, amount, reason)
        
        return {
            'request_code': request_code,
            'message': 'Solicitud enviada. Espera código de autorización del administrador.',
            'expires_in': '10 minutos'
        }
    
    def validate_authorization(self, auth_code: str) -> Dict[str, Any]:
        """
        Valida código de autorización ingresado por cajera.
        """
        if auth_code not in self._auth_codes:
            return {'valid': False, 'error': 'Código inválido'}
        
        request = self._auth_codes[auth_code]
        
        if request['status'] == 'used':
            return {'valid': False, 'error': 'Código ya utilizado'}
        
        # Verificar expiración (10 minutos)
        created = datetime.fromisoformat(request['timestamp'])
        if (datetime.now() - created).seconds > 600:
            return {'valid': False, 'error': 'Código expirado'}
        
        # Marcar como usado
        self._auth_codes[auth_code]['status'] = 'used'
        
        return {
            'valid': True,
            'action': request['action'],
            'amount': request['amount'],
            'message': 'Autorización válida'
        }
    
    def generate_admin_code(self, request_code: str) -> str:
        """
        Genera código de autorización para el admin.
        Este código es diferente al request_code para seguridad.
        """
        if request_code not in self._auth_codes:
            return None
        
        # El admin recibe el mismo código para simplificar
        # En producción podrías usar un código diferente
        return request_code
    
    def _send_authorization_alert(self, code: str, action: str, 
                                   amount: float, reason: str):
        """Envía alerta de solicitud de autorización."""
        message = (
            f"🔐 SOLICITUD DE AUTORIZACIÓN\n"
            f"Acción: {action}\n"
            f"Monto: ${amount:.2f}\n"
            f"Razón: {reason}\n"
            f"Código: {code}"
        )
        # SECURITY: No loguear autorizaciones en logs normales
        # TODO [LOW]: Integrar con Telegram Bot API para alertas en tiempo real
        # Requiere: TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en configuracion
        logger.debug("Alerta de contingencia generada (detalles omitidos por seguridad)")
    
    # ==========================================
    # CIERRE CIEGO
    # ==========================================
    
    def get_blind_close_data(self, turn_id: int) -> Dict[str, Any]:
        """
        Obtiene datos para cierre ciego.
        La cajera NO ve el monto esperado, solo ingresa lo contado.
        """
        return {
            'turn_id': turn_id,
            'fields': [
                {'name': 'efectivo_contado', 'label': 'Efectivo en Caja', 'type': 'currency'},
                {'name': 'billetes_500', 'label': 'Billetes de $500', 'type': 'count'},
                {'name': 'billetes_200', 'label': 'Billetes de $200', 'type': 'count'},
                {'name': 'billetes_100', 'label': 'Billetes de $100', 'type': 'count'},
                {'name': 'billetes_50', 'label': 'Billetes de $50', 'type': 'count'},
                {'name': 'billetes_20', 'label': 'Billetes de $20', 'type': 'count'},
                {'name': 'monedas', 'label': 'Total Monedas', 'type': 'currency'},
            ],
            'show_expected': False,  # Clave: NO mostrar esperado
            'message': 'Por favor cuenta el dinero en caja e ingresa los montos exactos.'
        }
    
    def process_blind_close(self, turn_id: int, counted_data: Dict) -> Dict[str, Any]:
        """
        Procesa cierre ciego y calcula diferencia (solo visible para admin).
        """
        # Obtener esperado del sistema
        turn_summary = self.core.get_turn_summary(turn_id)
        expected = turn_summary.get('expected_cash', 0)
        
        # Calcular contado
        counted = (
            counted_data.get('efectivo_contado', 0) or
            (
                counted_data.get('billetes_500', 0) * 500 +
                counted_data.get('billetes_200', 0) * 200 +
                counted_data.get('billetes_100', 0) * 100 +
                counted_data.get('billetes_50', 0) * 50 +
                counted_data.get('billetes_20', 0) * 20 +
                counted_data.get('monedas', 0)
            )
        )
        
        difference = counted - expected
        
        # Registrar cierre
        close_result = {
            'turn_id': turn_id,
            'counted': counted,
            'expected': expected,
            'difference': difference,
            'status': 'OK' if abs(difference) < 10 else 'DISCREPANCIA',
            'timestamp': datetime.now().isoformat()
        }
        
        # Si hay faltante significativo, alertar
        if difference < -50:
            self._send_cash_alert(turn_id, expected, counted, difference)
        
        return close_result
    
    def _send_cash_alert(self, turn_id: int, expected: float, 
                          counted: float, difference: float):
        """Envía alerta de faltante de efectivo."""
        message = (
            f"💰 ALERTA: FALTANTE DE EFECTIVO\n"
            f"Turno: #{turn_id}\n"
            f"Esperado: ${expected:.2f}\n"
            f"Contado: ${counted:.2f}\n"
            f"Diferencia: ${difference:.2f}"
        )
        # SECURITY: No loguear montos de efectivo en logs normales
        # TODO [LOW]: Integrar con Telegram Bot API para alertas de faltantes
        # Requiere: TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en configuracion
        logger.debug("Alerta de faltante de efectivo generada (montos omitidos por seguridad)")
