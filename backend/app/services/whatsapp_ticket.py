from pathlib import Path

"""
WhatsApp Ticket - Envío de tickets digitales por WhatsApp
Sin papel, sin rastro físico, 100% digital
"""

from typing import Any, Dict, Optional
from datetime import datetime
from decimal import Decimal
import json
import logging
import sys
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

class WhatsAppTicket:
    """
    Envía tickets de venta por WhatsApp usando la API de WhatsApp Business.
    Serie A = Ticket Fiscal | Serie B = Nota de Remisión
    """
    
    def __init__(self, core, api_token: str = None, phone_number_id: str = None):
        self.core = core
        self.api_token = api_token or self._get_config('whatsapp_token')
        self.phone_number_id = phone_number_id or self._get_config('whatsapp_phone_id')
        self.api_url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"
    
    def _get_config(self, key: str) -> Optional[str]:
        """Obtiene configuración de BD."""
        try:
            result = list(self.core.db.execute_query(
                "SELECT value FROM config WHERE key = %s", (key,)
            ))
            return result[0]['value'] if result else None
        except Exception:
            return None
    
    def configure(self, api_token: str, phone_number_id: str):
        """Configura las credenciales de WhatsApp Business API."""
        self.api_token = api_token
        self.phone_number_id = phone_number_id
        self.api_url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
        
        # Guardar en config
        self.core.db.execute_write(
            "INSERT INTO config (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            ('whatsapp_token', api_token)
        )
        self.core.db.execute_write(
            "INSERT INTO config (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            ('whatsapp_phone_id', phone_number_id)
        )
        
        logger.info("✅ WhatsApp Business API configurado")
    
    def send_ticket(self, sale_id: int, customer_phone: str) -> Dict[str, Any]:
        """Envía ticket de venta al cliente por WhatsApp."""
        # Obtener datos de la venta
        sale = self._get_sale_data(sale_id)
        if not sale:
            return {'success': False, 'error': 'Venta no encontrada'}
        
        # Formatear mensaje según serie
        if sale['serie'] == 'A':
            message = self._format_fiscal_ticket(sale)
        else:
            message = self._format_remision(sale)
        
        # Enviar
        return self._send_message(customer_phone, message)
    
    def _get_sale_data(self, sale_id: int) -> Optional[Dict]:
        """Obtiene datos completos de la venta."""
        sale = list(self.core.db.execute_query("""
            SELECT s.*, c.name as customer_name, c.phone as customer_phone
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            WHERE s.id = %s
        """, (sale_id,)))
        
        if not sale:
            return None
        
        sale = dict(sale[0])
        
        # Obtener items
        items = list(self.core.db.execute_query("""
            SELECT si.*, p.name as product_name
            FROM sale_items si
            JOIN products p ON si.product_id = p.id
            WHERE si.sale_id = %s
        """, (sale_id,)))
        
        sale['items'] = items
        return sale
    
    def _format_fiscal_ticket(self, sale: Dict) -> str:
        """Formatea ticket fiscal (Serie A)."""
        # Obtener datos del negocio
        try:
            config = dict(list(self.core.db.execute_query(
                "SELECT key, value FROM config WHERE key IN ('business_name', 'rfc', 'address')"
            )))
        except Exception:
            config = {}
        
        business = config.get('business_name', 'TITAN POS')
        rfc = config.get('rfc', 'XAXX010101000')
        
        lines = [
            f"🧾 *{business}*",
            f"RFC: {rfc}",
            "─" * 25,
            f"📅 {sale['timestamp'][:16]}",
            f"🔢 Ticket: {sale['serie']}-{sale['folio_visible']}",
            "─" * 25,
        ]
        
        for item in sale['items']:
            qty = float(item['quantity'])
            price = float(item['price'])
            name = item['product_name'][:20]
            lines.append(f"{qty:.0f}x {name}")
            lines.append(f"    ${price:.2f} = ${qty * price:.2f}")
        
        lines.extend([
            "─" * 25,
            f"*TOTAL: ${float(sale['total']):,.2f}*",
            "",
            f"Método: {sale.get('payment_method', 'Efectivo')}",
            "",
            "✅ *Este ticket es comprobante fiscal*",
            "Conserve para cualquier aclaración"
        ])
        
        return "\n".join(lines)
    
    def _format_remision(self, sale: Dict) -> str:
        """
        Formatea nota de remisión (Serie B).
        Sin elementos fiscales.
        """
        lines = [
            "📝 *Nota de Remisión*",
            "─" * 25,
            f"📅 {sale['timestamp'][:16]}",
            f"🔢 Folio: {sale['folio_visible']}",
            "─" * 25,
        ]
        
        for item in sale['items']:
            qty = float(item['quantity'])
            price = float(item['price'])
            name = item['product_name'][:20]
            lines.append(f"• {qty:.0f}x {name} - ${qty * price:.2f}")
        
        lines.extend([
            "─" * 25,
            f"*Total: ${float(sale['total']):,.2f}*",
            "",
            "Gracias por su preferencia 🙏",
            "",
            "_Documento interno - No válido para efectos fiscales_"
        ])
        
        return "\n".join(lines)
    
    def _send_message(self, phone: str, message: str) -> Dict[str, Any]:
        """Envía mensaje por WhatsApp Business API."""
        if not self.api_token or not self.phone_number_id:
            # Fallback: simular envío (para desarrollo)
            logger.info(f"📱 [SIMULADO] WhatsApp a {phone}: {message[:50]}...")
            return {
                'success': True,
                'simulated': True,
                'message': 'API no configurada - mensaje simulado'
            }
        
        # Formatear número
        phone = phone.replace(' ', '').replace('-', '')
        if not phone.startswith('52'):
            phone = '52' + phone
        
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": message}
        }
        
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(self.api_url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    logger.info(f"✅ Ticket enviado a {phone}")
                    return {'success': True, 'phone': phone}
                else:
                    return {'success': False, 'error': f'HTTP {response.status}'}
                
        except Exception as e:
            logger.error(f"Error enviando WhatsApp: {e}")
            return {'success': False, 'error': str(e)}
    
    def send_promo(self, phones: list, promo_text: str) -> Dict[str, Any]:
        """Envía promoción a múltiples clientes."""
        success = 0
        failed = 0
        
        for phone in phones:
            result = self._send_message(phone, promo_text)
            if result['success']:
                success += 1
            else:
                failed += 1
        
        return {
            'total': len(phones),
            'success': success,
            'failed': failed
        }
    
    def send_low_points_reminder(self, wallet_id: str, points: int, 
                                 phone: str) -> Dict[str, Any]:
        """Recuerda al cliente sus puntos de lealtad."""
        message = f"""
🎁 *¡Tienes {points} puntos!*

Equivalen a *${points * 0.10:.2f}* de descuento.

Ven a canjearlos en tu próxima compra.

_Solo válido en compras sin factura_
"""
        return self._send_message(phone, message.strip())

# Función para integrar con el flujo de venta
def send_ticket_after_sale(core, sale_id: int, customer_phone: str) -> Dict:
    """Helper para enviar ticket después de la venta."""
    wa = WhatsAppTicket(core)
    return wa.send_ticket(sale_id, customer_phone)
