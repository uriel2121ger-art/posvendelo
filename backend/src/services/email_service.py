"""
Email Service for TITAN POS E-Commerce
Handles transactional emails for orders, recovery, and notifications
"""

from typing import Dict, List
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import smtplib


class EmailService:
    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER', 'your-email@gmail.com')
        self.smtp_password = os.getenv('SMTP_PASSWORD', 'your-app-password')
        self.from_email = os.getenv('FROM_EMAIL', 'noreply@titanstore.com')
        self.from_name = os.getenv('FROM_NAME', 'TITAN Store')

    def send_email(self, to: str, subject: str, html_content: str):
        """Send HTML email."""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to
            
            # Attach HTML content
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            print(f"Email sent to {to}: {subject}")
            return True
        
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False

    def send_order_confirmation(self, order: Dict, customer: Dict, items: List[Dict]):
        """Send order confirmation email."""
        html = self._render_order_confirmation(order, customer, items)
        subject = f"Confirmación de Pedido #{order['order_number']}"
        
        return self.send_email(customer['email'], subject, html)

    def send_cart_recovery(self, cart: Dict, contact: Dict):
        """Send cart abandonment recovery email."""
        html = self._render_cart_recovery(cart, contact)
        subject = "¡No te vayas sin tus productos! 🛒"
        
        return self.send_email(contact['email'], subject, html)

    def send_shipping_notification(self, order: Dict, customer: Dict, tracking: str):
        """Send shipping notification email."""
        html = self._render_shipping_notification(order, customer, tracking)
        subject = f"Tu pedido #{order['order_number']} ha sido enviado 📦"
        
        return self.send_email(customer['email'], subject, html)

    def _render_order_confirmation(self, order: Dict, customer: Dict, items: List[Dict]):
        """Render order confirmation email template."""
        items_html = ''.join([
            f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">
                    {item['product_name']}
                </td>
                <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: center;">
                    {item['quantity']}
                </td>
                <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: right;">
                    ${item['unit_price']:.2f}
                </td>
                <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: bold;">
                    ${item['total']:.2f}
                </td>
            </tr>
            """
            for item in items
        ])

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f7fafc;">
            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f7fafc; padding: 40px 0;">
                <tr>
                    <td align="center">
                        <table width="600" cellpadding="0" cellspacing="0" style="background-color: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                            
                            <!-- Header -->
                            <tr>
                                <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; text-align: center;">
                                    <h1 style="color: white; margin: 0; font-size: 32px;">¡Gracias por tu compra!</h1>
                                </td>
                            </tr>
                            
                            <!-- Content -->
                            <tr>
                                <td style="padding: 40px;">
                                    <p style="font-size: 16px; color: #4a5568; margin-bottom: 20px;">
                                        Hola <strong>{customer['name']}</strong>,
                                    </p>
                                    <p style="font-size: 16px; color: #4a5568; margin-bottom: 30px;">
                                        Hemos recibido tu pedido y lo estamos procesando. 
                                        Te notificaremos cuando sea enviado.
                                    </p>
                                    
                                    <!-- Order Details -->
                                    <div style="background-color: #f7fafc; padding: 20px; border-radius: 8px; margin-bottom: 30px;">
                                        <h2 style="color: #2d3748; font-size: 18px; margin-top: 0;">
                                            Detalles del Pedido
                                        </h2>
                                        <p style="margin: 5px 0;">
                                            <strong>Número de Orden:</strong> {order['order_number']}
                                        </p>
                                        <p style="margin: 5px 0;">
                                            <strong>Fecha:</strong> {datetime.now().strftime('%d/%m/%Y')}
                                        </p>
                                        <p style="margin: 5px 0;">
                                            <strong>Total:</strong> ${order['total']:.2f}
                                        </p>
                                    </div>
                                    
                                    <!-- Items Table -->
                                    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 30px;">
                                        <thead>
                                            <tr style="background-color: #edf2f7;">
                                                <th style="padding: 10px; text-align: left;">Producto</th>
                                                <th style="padding: 10px; text-align: center;">Cant.</th>
                                                <th style="padding: 10px; text-align: right;">Precio</th>
                                                <th style="padding: 10px; text-align: right;">Total</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {items_html}
                                        </tbody>
                                        <tfoot>
                                            <tr>
                                                <td colspan="3" style="padding: 15px; text-align: right; font-weight: bold;">
                                                    Total:
                                                </td>
                                                <td style="padding: 15px; text-align: right; font-weight: bold; font-size: 18px; color: #667eea;">
                                                    ${order['total']:.2f}
                                                </td>
                                            </tr>
                                        </tfoot>
                                    </table>
                                    
                                    <!-- CTA Button -->
                                    <div style="text-align: center; margin: 30px 0;">
                                        <a href="https://titanstore.com/orders/{order['order_number']}" 
                                           style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                                  color: white; padding: 15px 40px; text-decoration: none; border-radius: 8px; 
                                                  font-weight: bold;">
                                            Ver Estado del Pedido
                                        </a>
                                    </div>
                                </td>
                            </tr>
                            
                            <!-- Footer -->
                            <tr>
                                <td style="background-color: #f7fafc; padding: 20px; text-align: center; color: #718096; font-size: 14px;">
                                    <p style="margin: 5px 0;">TITAN Store</p>
                                    <p style="margin: 5px 0;">soporte@titanstore.com | +52 55 1234 5678</p>
                                    <p style="margin: 15px 0 5px 0;">
                                        <a href="#" style="color: #667eea; text-decoration: none; margin: 0 10px;">Facebook</a>
                                        <a href="#" style="color: #667eea; text-decoration: none; margin: 0 10px;">Instagram</a>
                                        <a href="#" style="color: #667eea; text-decoration: none; margin: 0 10px;">Twitter</a>
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

    def _render_cart_recovery(self, cart: Dict, contact: Dict):
        """Render cart recovery email template."""
        items_html = ''.join([
            f"""
            <div style="margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px solid #e2e8f0;">
                <strong style="color: #2d3748;">{item['name']}</strong><br>
                <span style="color: #718096;">Cantidad: {item['quantity']} x ${item['price']:.2f}</span>
            </div>
            """
            for item in cart['cart_items']
        ])

        total = sum(item['price'] * item['quantity'] for item in cart['cart_items'])
        discount = total * 0.10
        final_total = total - discount

        return f"""
        <!DOCTYPE html>
        <html>
        <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f7fafc;">
            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f7fafc; padding: 40px 0;">
                <tr>
                    <td align="center">
                        <table width="600" cellpadding="0" cellspacing="0" style="background-color: white; border-radius: 8px; overflow: hidden;">
                            
                            <tr>
                                <td style="padding: 40px; text-align: center;">
                                    <h1 style="color: #667eea; font-size: 32px; margin: 0 0 10px 0;">¡Espera!</h1>
                                    <p style="font-size: 18px; color: #4a5568;">Olvidaste algo en tu carrito</p>
                                </td>
                            </tr>
                            
                            <tr>
                                <td style="padding: 0 40px 40px 40px;">
                                    <p style="font-size: 16px; color: #4a5568; margin-bottom: 20px;">
                                        Notamos que dejaste estos productos en tu carrito:
                                    </p>
                                    
                                    <div style="background-color: #f7fafc; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                                        {items_html}
                                        <div style="text-align: right; padding-top: 15px; border-top: 2px solid #cbd5e0;">
                                            <p style="margin: 5px 0; font-size: 18px; font-weight: bold; color: #2d3748;">
                                                Total: ${total:.2f}
                                            </p>
                                        </div>
                                    </div>
                                    
                                    <div style="background: linear-gradient(135deg, #fef5e7 0%, #fdebd0 100%); 
                                                padding: 20px; border-radius: 8px; border-left: 4px solid #f39c12; margin-bottom: 30px;">
                                        <h3 style="color: #d68910; margin-top: 0;">🎁 ¡Oferta Especial Solo Por Hoy!</h3>
                                        <p style="color: #7d6608; margin: 10px 0;">
                                            Completa tu compra en las próximas 24 horas y obtén:
                                        </p>
                                        <ul style="color: #7d6608; margin: 10px 0;">
                                            <li><strong>10% de descuento</strong> (ahorras ${discount:.2f})</li>
                                            <li><strong>Envío gratis</strong> en pedidos mayores a $500</li>
                                        </ul>
                                        <p style="color: #2d3748; font-size: 20px; font-weight: bold; margin: 15px 0 0 0;">
                                            Tu nuevo total: <span style="color: #48bb78;">${final_total:.2f}</span>
                                        </p>
                                    </div>
                                    
                                    <div style="text-align: center;">
                                        <a href="https://titanstore.com/checkout.html%srecovery=true" 
                                           style="display: inline-block; background: linear-gradient(135deg, #48bb78 0%, #38a169 100%); 
                                                  color: white; padding: 18px 50px; text-decoration: none; border-radius: 8px; 
                                                  font-weight: bold; font-size: 18px;">
                                            Completar Mi Compra Ahora
                                        </a>
                                    </div>
                                    
                                    <p style="text-align: center; color: #e53e3e; font-weight: bold; margin-top: 20px;">
                                        ⏰ Oferta válida por 24 horas
                                    </p>
                                </td>
                            </tr>
                            
                            <tr>
                                <td style="background-color: #f7fafc; padding: 20px; text-align: center; color: #718096; font-size: 12px;">
                                    <p>¿No quieres recibir estos emails%s <a href="#" style="color: #667eea;">Cancelar suscripción</a></p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

    def _render_shipping_notification(self, order: Dict, customer: Dict, tracking: str):
        """Render shipping notification email template."""
        return f"""
        <!DOCTYPE html>
        <html>
        <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f7fafc;">
            <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f7fafc; padding: 40px 0;">
                <tr>
                    <td align="center">
                        <table width="600" cellpadding="0" cellspacing="0" style="background-color: white; border-radius: 8px;">
                            
                            <tr>
                                <td style="padding: 40px; text-align: center;">
                                    <div style="font-size: 60px; margin-bottom: 20px;">📦</div>
                                    <h1 style="color: #667eea; margin: 0;">¡Tu pedido va en camino!</h1>
                                </td>
                            </tr>
                            
                            <tr>
                                <td style="padding: 0 40px 40px 40px;">
                                    <p style="font-size: 16px; color: #4a5568;">
                                        Hola <strong>{customer['name']}</strong>,
                                    </p>
                                    <p style="font-size: 16px; color: #4a5568; margin-bottom: 30px;">
                                        Tu pedido #{order['order_number']} ha sido enviado y está en camino.
                                    </p>
                                    
                                    <div style="background-color: #f7fafc; padding: 20px; border-radius: 8px; margin-bottom: 30px;">
                                        <p style="margin: 5px 0;">
                                            <strong>Número de Rastreo:</strong> {tracking}
                                        </p>
                                        <p style="margin: 5px 0;">
                                            <strong>Tiempo de entrega estimado:</strong> 3-5 días hábiles
                                        </p>
                                    </div>
                                    
                                    <div style="text-align: center;">
                                        <a href="https://tracking.example.com/{tracking}" 
                                           style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                                  color: white; padding: 15px 40px; text-decoration: none; border-radius: 8px; 
                                                  font-weight: bold;">
                                            Rastrear Mi Pedido
                                        </a>
                                    </div>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

# Global instance
email_service = EmailService()
