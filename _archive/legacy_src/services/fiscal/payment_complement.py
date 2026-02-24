"""
Payment Receipt Complement (Complemento de Recepción de Pagos)
For generating CFDIs when receiving payment for invoices
"""

from typing import Any, Dict, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class PaymentReceiptService:
    """Service for generating payment receipt CFDIs."""
    
    def __init__(self, core):
        self.core = core
    
    def generate_payment_receipt(
        self,
        related_cfdis: List[str],  # UUIDs of invoices being paid
        payment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate payment receipt CFDI.
        
        Args:
            related_cfdis: List of UUIDs of invoices being paid
            payment_data: Payment information:
                - payment_date: Date of payment
                - payment_method: Payment method code
                - amount: Amount paid
                - currency: Currency code (MXN)
                - exchange_rate: Exchange rate if applicable
                - operation_number: Bank operation number
                - payer_rfc: Payer RFC (if different from invoice receptors
                - payer_name: Payer nameReturns:
            Result dictionary with UUID and details
        """
        try:
            # Validate related CFDIs exist
            for uuid in related_cfdis:
                cfdi = self.core.db.execute_query(
                    "SELECT * FROM cfdis WHERE uuid = %s",
                    (uuid,)
                )
                if not cfdi:
                    return {
                        'success': False,
                        'error': f'CFDI relacionado no encontrado: {uuid}'
                    }
            
            # Get fiscal config
            fiscal_config = self.core.get_fiscal_config()
            
            # Build payment complement XML
            payment_xml = self._build_payment_complement(
                related_cfdis,
                payment_data,
                fiscal_config
            )
            
            # Generate CFDI with payment complement
            from src.services.fiscal.cfdi_builder import CFDIBuilder
            from src.services.fiscal.signature import sign_cfdi_xml
            
            builder = CFDIBuilder(fiscal_config)
            
            # Build base CFDI (tipo "P" - Pago)
            base_xml = self._build_payment_cfdi_base(
                payment_data,
                fiscal_config
            )
            
            # Add payment complement
            full_xml = self._inject_payment_complement(base_xml, payment_xml)
            
            # Sign
            signed_xml = sign_cfdi_xml(full_xml, fiscal_config)
            
            # Send to PAC
            from src.services.fiscal.pac_connector import create_pac_connector
            pac = create_pac_connector(fiscal_config)
            
            result = pac.timbrar_cfdi(signed_xml)
            
            if not result.get('success'):
                return result
            
            # Save to database
            cfdi_id = self._save_payment_receipt(
                result, payment_data, related_cfdis
            )
            
            result['cfdi_id'] = cfdi_id
            result['type'] = 'payment_receipt'
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating payment receipt: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _build_payment_complement(
        self,
        related_cfdis: List[str],
        payment_data: Dict[str, Any],
        fiscal_config: Dict[str, Any]
    ) -> str:
        """Build payment complement XML."""
        # Namespace for payment complement
        pago_ns = "http://www.sat.gob.mx/Pagos20"
        
        xml = f'<pago20:Pagos xmlns:pago20="{pago_ns}" Version="2.0">\n'
        xml += '  <pago20:Totales/>\n'  # Required but empty for single payment
        xml += '  <pago20:Pago>\n'
        
        # Payment details
        xml += f'    FechaPago="{payment_data.get("payment_date", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))}"\n'
        xml += f'    FormaDePagoP="{payment_data.get("payment_method", "03")}"\n'  # 03 = Transferencia
        xml += f'    MonedaP="{payment_data.get("currency", "MXN")}"\n'
        xml += f'    Monto="{payment_data.get("amount", 0):.2f}"\n'
        
        if payment_data.get('operation_number'):
            xml += f'    NumOperacion="{payment_data["operation_number"]}"\n'
        
        # Related documents
        for uuid in related_cfdis:
            # Get invoice data
            cfdi = self.core.db.execute_query(
                "SELECT * FROM cfdis WHERE uuid = %s",
                (uuid,)
            )
            if cfdi:
                cfdi_data = dict(cfdi[0])
                xml += '    <pago20:DoctoRelacionado\n'
                xml += f'      IdDocumento="{uuid}"\n'
                xml += f'      MonedaDR="{payment_data.get("currency", "MXN")}"\n'
                xml += f'      MetodoDePagoDR="PPD"\n'  # Pago en parcialidades o diferido
                xml += f'      NumParcialidad="1"\n'
                saldo_anterior = float(cfdi_data.get("total", 0))
                imp_pagado = float(payment_data.get("amount", 0))
                saldo_insoluto = max(0, saldo_anterior - imp_pagado)
                xml += f'      ImpSaldoAnt="{saldo_anterior:.2f}"\n'
                xml += f'      ImpPagado="{imp_pagado:.2f}"\n'
                xml += f'      ImpSaldoInsoluto="{saldo_insoluto:.2f}"/>\n'
        
        xml += '  </pago20:Pago>\n'
        xml += '</pago20:Pagos>\n'
        
        return xml
    
    def _build_payment_cfdi_base(
        self,
        payment_data: Dict[str, Any],
        fiscal_config: Dict[str, Any]
    ) -> str:
        """Build base CFDI for payment type."""
        # This would be a CFDI with TipoDeComprobante="P" (Pago)
        # Simplified version - real implementation needs full CFDI structure
        
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml += '<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" '
        xml += 'Version="4.0" '
        xml += 'TipoDeComprobante="P" '  # P = Pago
        xml += 'Exportacion="01" '
        xml += 'LugarExpedicion="' + fiscal_config.get('lugar_expedicion', '00000') + '">\n'
        
        # Emisor
        xml += '  <cfdi:Emisor '
        xml += 'Rfc="' + fiscal_config.get('rfc_emisor', '') + '" '
        xml += 'Nombre="' + fiscal_config.get('razon_social_emisor', '') + '" '
        xml += 'RegimenFiscal="' + fiscal_config.get('regimen_fiscal', '601') + '"/>\n'
        
        # Receptor (payer)
        xml += '  <cfdi:Receptor '
        xml += 'Rfc="' + payment_data.get('payer_rfc', 'XAXX010101000') + '" '
        xml += 'Nombre="' + payment_data.get('payer_name', 'Cliente') + '" '
        xml += 'UsoCFDI="CP01"/>\n'  # CP01 = Pagos
        
        # Conceptos (required but minimal for payment)
        xml += '  <cfdi:Conceptos>\n'
        xml += '    <cfdi:Concepto ClaveProdServ="84111506" Cantidad="1" '
        xml += 'ClaveUnidad="ACT" Descripcion="Pago" ValorUnitario="0" Importe="0" '
        xml += 'ObjetoImp="01"/>\n'  # 01 = No objeto de impuesto
        xml += '  </cfdi:Conceptos>\n'
        
        # Complemento will be injected here
        
        xml += '</cfdi:Comprobante>\n'
        
        return xml
    
    def _inject_payment_complement(self, base_xml: str, complement_xml: str) -> str:
        """Inject payment complement into base CFDI."""
        # Insert complement before closing Comprobante tag
        insert_point = base_xml.rfind('</cfdi:Comprobante>')
        
        full_xml = base_xml[:insert_point]
        full_xml += '  <cfdi:Complemento>\n'
        full_xml += '    ' + complement_xml
        full_xml += '  </cfdi:Complemento>\n'
        full_xml += base_xml[insert_point:]
        
        return full_xml
    
    def _save_payment_receipt(
        self,
        pac_result: Dict[str, Any],
        payment_data: Dict[str, Any],
        related_cfdis: List[str]
    ) -> int:
        """Save payment receipt to database."""
        from pathlib import Path

        from app.core import DATA_DIR

        # Save XML
        uuid = pac_result['uuid']
        xml_dir = Path(DATA_DIR) / "cfdis"
        xml_dir.mkdir(exist_ok=True)
        
        xml_path = xml_dir / f"{uuid}.xml"
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(pac_result['xml_timbrado'])
        
        # Insert into database
        cfdi_data = {
            'uuid': uuid,
            'folio': 0,  # Payment receipts don't use folio
            'serie': 'P',  # P for payment
            'rfc_receptor': payment_data.get('payer_rfc', 'XAXX010101000'),
            'nombre_receptor': payment_data.get('payer_name', 'Cliente'),
            'xml_timbrado': pac_result['xml_timbrado'],
            'fecha_timbrado': pac_result.get('fecha_timbrado'),
            'total': 0,  # Payment receipts have $0 total
            'estado': 'vigente'
        }
        
        columns = ', '.join(cfdi_data.keys())
        # FIX 2026-02-01: PostgreSQL usa %s en lugar de ?
        placeholders = ', '.join(['%s' for _ in cfdi_data])

        sql = f"INSERT INTO cfdis ({columns}) VALUES ({placeholders})"
        cfdi_id = self.core.db.execute_write(sql, tuple(cfdi_data.values()))
        
        # Link to related CFDIs
        for related_uuid in related_cfdis:
            self.core.db.execute_write(
                "INSERT INTO cfdi_relations (parent_uuid, related_uuid, relation_type) VALUES (%s, %s, 'payment')",
                (uuid, related_uuid)
            )
        
        return cfdi_id
