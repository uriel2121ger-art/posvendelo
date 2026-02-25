"""
CFDI Email Service
Sends CFDI XML and PDF to customers via email
"""

from typing import Any, Dict, List, Optional
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from pathlib import Path
import smtplib

logger = logging.getLogger(__name__)

class CFDIEmailService:
    """Service for sending CFDIs via email."""
    
    def __init__(self, smtp_config: Dict[str, Any]):
        """
        Initialize email service.
        
        Args:
            smtp_config: Dictionary with SMTP configuration:
                - smtp_server: SMTP server address
                - smtp_port: SMTP port (usually 587 for TLS)
                - smtp_user: Email username
                - smtp_password: Email password
                - from_email: Sender email address
                - from_name: Sender name
        """
        self.smtp_server = smtp_config.get('smtp_server', 'smtp.gmail.com')
        self.smtp_port = smtp_config.get('smtp_port', 587)
        self.smtp_user = smtp_config.get('smtp_user', '')
        self.smtp_password = smtp_config.get('smtp_password', '')
        self.from_email = smtp_config.get('from_email', self.smtp_user)
        self.from_name = smtp_config.get('from_name', 'Mi Empresa')
    
    async def send_cfdi(
        self,
        to_email: str,
        cfdi_data: Dict[str, Any],
        xml_path: str,
        pdf_path: Optional[str] = None,
        custom_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send CFDI to customer email.
        
        Args:
            to_email: Recipient email address
            cfdi_data: CFDI record from database
            xml_path: Path to XML file
            pdf_path: Optional path to PDF file
            custom_message: Optional custom message for email body
            
        Returns:
            Result dictionary with success status
        """
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = f"Factura Electrónica - {cfdi_data.get('uuid', '')[:8]}"
            
            # Email body
            body = await self._build_email_body(cfdi_data, custom_message)
            msg.attach(MIMEText(body, 'html'))
            
            # Attach XML
            if Path(xml_path).exists():
                with open(xml_path, 'rb') as f:
                    xml_attachment = MIMEApplication(f.read(), _subtype='xml')
                    xml_attachment.add_header(
                        'Content-Disposition',
                        f'attachment; filename="{Path(xml_path).name}"'
                    )
                    msg.attach(xml_attachment)
            
            # Attach PDF if available
            if pdf_path and Path(pdf_path).exists():
                with open(pdf_path, 'rb') as f:
                    pdf_attachment = MIMEApplication(f.read(), _subtype='pdf')
                    pdf_attachment.add_header(
                        'Content-Disposition',
                        f'attachment; filename="{Path(pdf_path).name}"'
                    )
                    msg.attach(pdf_attachment)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"CFDI sent to {to_email}")
            
            return {
                'success': True,
                'message': f'Factura enviada a {to_email}'
            }
            
        except Exception as e:
            logger.error(f"Error sending CFDI email: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _build_email_body(self, cfdi_data: Dict[str, Any], custom_message: Optional[str] = None) -> str:
        """Build HTML email body."""
        uuid = cfdi_data.get('uuid', 'N/A')
        total = cfdi_data.get('total', 0)
        fecha = cfdi_data.get('fecha_emision', 'N/A')
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: #3498db; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .info-box {{ background-color: #ecf0f1; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .footer {{ color: #7f8c8d; font-size: 12px; text-align: center; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>📄 Factura Electrónica (CFDI)</h2>
            </div>
            <div class="content">
                <p>Estimado cliente,</p>
                
                {f'<p>{custom_message}</p>' if custom_message else '<p>Adjunto encontrará su factura electrónica.</p>'}
                
                <div class="info-box">
                    <strong>UUID (Folio Fiscal):</strong> {uuid}<br>
                    <strong>Fecha:</strong> {fecha}<br>
                    <strong>Total:</strong> ${total:,.2f} MXN
                </div>
                
                <p><strong>Archivos adjuntos:</strong></p>
                <ul>
                    <li>XML - Comprobante fiscal digital</li>
                    <li>PDF - Representación impresa (si disponible)</li>
                </ul>
                
                <p>Para verificar la validez de esta factura ante el SAT, visite:</p>
                <p><a href="https://verificacfdi.facturaelectronica.sat.gob.mx/">https://verificacfdi.facturaelectronica.sat.gob.mx/</a></p>
                
                <p style="margin-top: 30px;">Gracias por su preferencia.</p>
            </div>
            <div class="footer">
                <p>Este es un correo automático, por favor no responder.</p>
                <p><i>Factura electrónica generada conforme a disposiciones fiscales vigentes.</i></p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test SMTP connection."""
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
            
            return {
                'success': True,
                'message': 'Conexión SMTP exitosa'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

async def send_cfdi_email(cfdi_id: int, to_email: str, core) -> Dict[str, Any]:
    """
    Convenience function to send CFDI email.
    
    Args:
        cfdi_id: CFDI database ID
        to_email: Recipient email
        core: POSCore instance
        
    Returns:
        Result dictionary
    """
    # Get CFDI
    cfdi = core.db.execute_query("SELECT * FROM cfdis WHERE id = %s", (cfdi_id,))
    if not cfdi:
        return {'success': False, 'error': f'CFDI {cfdi_id} not found'}
    
    cfdi_data = dict(cfdi[0])
    
    # Get email config (from settings or fiscal_config)
    email_config = (core.get_fiscal_config() or {}).get('email_config', {})
    
    if not email_config or not email_config.get('smtp_user'):
        return {
            'success': False,
            'error': 'Configuración de email no encontrada. Configure en Settings.'
        }
    
    # Get file paths
    xml_path = cfdi_data.get('xml_path', '')
    if not xml_path:
        # Reconstruct path
        from app.core import DATA_DIR
        xml_path = str(Path(DATA_DIR) / "cfdis" / f"{cfdi_data['uuid']}.xml")
    
    pdf_path = cfdi_data.get('pdf_path')
    
    # Send
    service = CFDIEmailService(email_config)
    return await service.send_cfdi(to_email, cfdi_data, xml_path, pdf_path)
