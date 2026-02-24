"""
CFDI PDF Generator
Generates printable representation of CFDI with QR code
"""

from typing import Any, Dict, Optional
from io import BytesIO
import logging
from pathlib import Path

import qrcode

logger = logging.getLogger(__name__)

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("reportlab not available - PDF generation disabled")

class CFDIPDFGenerator:
    """Generates PDF representation of CFDI."""
    
    def __init__(self):
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab package required for PDF generation")
    
    def generate(
        self,
        cfdi_data: Dict[str, Any],
        fiscal_config: Dict[str, Any],
        output_path: str,
        logo_path: Optional[str] = None
    ) -> str:
        """
        Generate PDF from CFDI data.
        
        Args:
            cfdi_data: CFDI record from database
            fiscal_config: Fiscal configuration
            output_path: Path to save PDF
            logo_path: Optional path to company logo
            
        Returns:
            Path to generated PDF
        """
        # Create PDF
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Container for elements
        elements = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        # Header with logo
        elements.extend(self._build_header(cfdi_data, fiscal_config, logo_path, title_style))
        
        # Emisor/Receptor info
        elements.extend(self._build_parties_info(cfdi_data, fiscal_config, styles))
        
        # Items table
        elements.extend(self._build_items_table(cfdi_data, styles))
        
        # Totals
        elements.extend(self._build_totals(cfdi_data, styles))
        
        # QR Code and digital seal
        elements.extend(self._build_footer(cfdi_data, fiscal_config, styles))
        
        # Build PDF
        doc.build(elements)
        
        logger.info(f"PDF generated: {output_path}")
        return output_path
    
    def _build_header(self, cfdi_data, fiscal_config, logo_path, title_style):
        """Build PDF header with logo and title."""
        elements = []
        
        # Logo and title side by side
        header_data = []
        
        if logo_path and Path(logo_path).exists():
            try:
                logo = Image(logo_path, width=2*inch, height=1*inch)
                header_data.append([logo, Paragraph("FACTURA ELECTRÓNICA", title_style)])
            except Exception:
                header_data.append([Paragraph("FACTURA ELECTRÓNICA", title_style)])
        else:
            elements.append(Paragraph("FACTURA ELECTRÓNICA", title_style))
        
        if header_data:
            header_table = Table(header_data, colWidths=[2.5*inch, 4*inch])
            header_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(header_table)
        
        elements.append(Spacer(1, 0.3*inch))
        
        # Folio fiscal
        folio_style = ParagraphStyle(
            'Folio',
            fontSize=10,
            textColor=colors.HexColor('#7f8c8d'),
            alignment=TA_CENTER
        )
        
        uuid = cfdi_data.get('uuid', 'N/A')
        elements.append(Paragraph(f"<b>UUID (Folio Fiscal):</b> {uuid}", folio_style))
        elements.append(Spacer(1, 0.2*inch))
        
        return elements
    
    def _build_parties_info(self, cfdi_data, fiscal_config, styles):
        """Build emisor and receptor information."""
        elements = []
        
        # Emisor
        emisor_data = [
            ['EMISOR'],
            [f"RFC: {fiscal_config.get('rfc_emisor', 'N/A')}"],
            [f"Nombre: {fiscal_config.get('razon_social_emisor', 'N/A')}"],
            [f"Régimen Fiscal: {fiscal_config.get('regimen_fiscal', 'N/A')}"],
            [f"Lugar de Expedición: {fiscal_config.get('lugar_expedicion', 'N/A')}"],
        ]
        
        # Receptor
        receptor_data = [
            ['RECEPTOR'],
            [f"RFC: {cfdi_data.get('rfc_receptor', 'N/A')}"],
            [f"Nombre: {cfdi_data.get('nombre_receptor', 'N/A')}"],
            [f"Régimen Fiscal: {cfdi_data.get('regimen_receptor', 'N/A')}"],
            [f"Uso CFDI: {cfdi_data.get('uso_cfdi', 'N/A')}"],
        ]
        
        # Side by side
        party_table = Table(
            [[
                Table(emisor_data, colWidths=[3*inch]),
                Table(receptor_data, colWidths=[3*inch])
            ]],
            colWidths=[3.2*inch, 3.2*inch]
        )
        
        party_table.setStyle(TableStyle([
            # Emisor styling
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (0, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (0, 0), 11),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#ecf0f1')),
            ('FONTSIZE', (0, 1), (0, -1), 9),
            ('LEFTPADDING', (0, 0), (0, -1), 10),
            ('RIGHTPADDING', (0, 0), (0, -1), 10),
            ('TOPPADDING', (0, 0), (0, -1), 5),
            ('BOTTOMPADDING', (0, 0), (0, -1), 5),
            
            # Receptor styling  
            ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#2ecc71')),
            ('TEXTCOLOR', (1, 0), (1, 0), colors.whitesmoke),
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (1, 0), (1, 0), 11),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('BACKGROUND', (1, 1), (1, -1), colors.HexColor('#ecf0f1')),
            ('FONTSIZE', (1, 1), (1, -1), 9),
            ('LEFTPADDING', (1, 0), (1, -1), 10),
            ('RIGHTPADDING', (1, 0), (1, -1), 10),
            ('TOPPADDING', (1, 0), (1, -1), 5),
            ('BOTTOMPADDING', (1, 0), (1, -1), 5),
            
            # Border
            ('BOX', (0, 0), (-1, -1), 1, colors.grey),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        elements.append(party_table)
        elements.append(Spacer(1, 0.3*inch))
        
        return elements
    
    def _build_items_table(self, cfdi_data, styles):
        """Build items table."""
        elements = []
        
        # Parse XML to get items (simplified - in production parse xml_timbrado)
        # For now, use dummy data structure
        items_data = [
            ['Cant.', 'Descripción', 'P. Unit.', 'Importe']
        ]
        
        # TODO: Parse XML properly - this is placeholder
        items_data.append(['N/A', 'Ver XML para detalles completos', '-', '-'])
        
        items_table = Table(items_data, colWidths=[0.8*inch, 3.5*inch, 1.2*inch, 1.2*inch])
        items_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            
            # Body
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Cantidad
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),   # Precios
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        elements.append(items_table)
        elements.append(Spacer(1, 0.2*inch))
        
        return elements
    
    def _build_totals(self, cfdi_data, styles):
        """Build totals section."""
        elements = []
        
        subtotal = cfdi_data.get('subtotal', 0)
        impuestos = cfdi_data.get('impuestos', 0)
        total = cfdi_data.get('total', 0)
        
        totals_data = [
            ['Subtotal:', f"${subtotal:,.2f}"],
            ['IVA (16%):', f"${impuestos:,.2f}"],
            ['TOTAL:', f"${total:,.2f}"],
        ]
        
        totals_table = Table(totals_data, colWidths=[4.5*inch, 2*inch])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 12),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#27ae60')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#27ae60')),
        ]))
        
        elements.append(totals_table)
        elements.append(Spacer(1, 0.3*inch))
        
        return elements
    
    def _build_footer(self, cfdi_data, fiscal_config, styles):
        """Build footer with QR code and seal."""
        elements = []
        
        # Generate QR Code
        uuid = cfdi_data.get('uuid', '')
        rfc_emisor = fiscal_config.get('rfc_emisor', '')
        rfc_receptor = cfdi_data.get('rfc_receptor', '')
        total = cfdi_data.get('total', 0)
        
        # QR data format: https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx?...
        qr_data = f"https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx?id={uuid}&re={rfc_emisor}&rr={rfc_receptor}&tt={total:.6f}"
        
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Save QR to BytesIO
        qr_buffer = BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        
        qr_image = Image(qr_buffer, width=1.5*inch, height=1.5*inch)
        
        # Sello digital (abbreviated)
        # FIX 2026-02-01: Safely extract sello with try/except to prevent IndexError
        sello = cfdi_data.get('xml_timbrado', '')
        if sello and 'Sello="' in sello:
            try:
                sello_value = sello.split('Sello="')[1].split('"')[0][:100] + '...'
            except (IndexError, AttributeError):
                sello_value = 'Ver XML'
        else:
            sello_value = 'Ver XML'
        sello = sello_value
        
        footer_data = [[
            qr_image,
            Paragraph(f"<b>Sello Digital:</b><br/>{sello}<br/><br/>"
                     f"<b>Fecha Timbrado:</b> {cfdi_data.get('fecha_timbrado', 'N/A')}<br/>"
                     f"<b>Estado:</b> <font color='green'>{cfdi_data.get('estado', 'vigente').upper()}</font>",
                     styles['Normal'])
        ]]
        
        footer_table = Table(footer_data, colWidths=[2*inch, 4.5*inch])
        footer_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('LEFTPADDING', (1, 0), (1, 0), 20),
        ]))
        
        elements.append(footer_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # SAT legend
        legend = Paragraph(
            "<i>Este documento es una representación impresa de un CFDI</i>",
            ParagraphStyle('Legend', fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
        )
        elements.append(legend)
        
        return elements

def generate_cfdi_pdf(cfdi_id: int, core, logo_path: Optional[str] = None) -> str:
    """
    Convenience function to generate PDF for a CFDI.
    
    Args:
        cfdi_id: CFDI database ID
        core: POSCore instance
        logo_path: Optional path to company logo
        
    Returns:
        Path to generated PDF
    """
    # Get CFDI data
    cfdi = core.db.execute_query("SELECT * FROM cfdis WHERE id = %s", (cfdi_id,))
    if not cfdi:
        raise ValueError(f"CFDI {cfdi_id} not found")
    
    cfdi_data = dict(cfdi[0])
    
    # Get fiscal config
    fiscal_config = core.get_fiscal_config()
    
    # Output path
    from app.core import DATA_DIR
    pdf_dir = Path(DATA_DIR) / "cfdis" / "pdfs"
    pdf_dir.mkdir(exist_ok=True, parents=True)
    
    pdf_path = pdf_dir / f"{cfdi_data['uuid']}.pdf"
    
    # Generate
    generator = CFDIPDFGenerator()
    generator.generate(cfdi_data, fiscal_config, str(pdf_path), logo_path)
    
    # Update database
    core.db.execute_write(
        "UPDATE cfdis SET pdf_path = %s WHERE id = %s",
        (str(pdf_path), cfdi_id)
    )
    
    return str(pdf_path)
