"""
Payment Receipt Complement (Complemento de Recepcion de Pagos)
For generating CFDIs when receiving payment for invoices

Refactored: receives `db` (DB wrapper) instead of `core`.
Uses :name params and db.fetch/db.fetchrow/db.execute.
Added missing awaits, XML escaping for string interpolation.
"""

from typing import Any, Dict, List
from datetime import datetime
from decimal import Decimal
from xml.sax.saxutils import escape as xml_escape
import logging
import aiofiles

from modules.fiscal.constants import IVA_RATE
from modules.shared.constants import money

logger = logging.getLogger(__name__)


class PaymentReceiptService:
    """Service for generating payment receipt CFDIs."""

    def __init__(self, db):
        self.db = db

    async def _get_fiscal_config(self) -> dict:
        """Fetch fiscal config directly from DB."""
        row = await self.db.fetchrow(
            "SELECT * FROM fiscal_config WHERE branch_id = :bid LIMIT 1",
            {"bid": 1},
        )
        return row or {}

    async def generate_payment_receipt(
        self,
        related_cfdis: List[str],
        payment_data: Dict[str, Any],
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
                - payer_rfc: Payer RFC
                - payer_name: Payer name
        Returns:
            Result dictionary with UUID and details
        """
        try:
            # Validate related CFDIs exist
            for uuid in related_cfdis:
                cfdi = await self.db.fetchrow(
                    "SELECT id FROM cfdis WHERE uuid = :uuid",
                    {"uuid": uuid},
                )
                if not cfdi:
                    return {
                        'success': False,
                        'error': f'CFDI relacionado no encontrado: {uuid}',
                    }

            # Get fiscal config (was missing await before)
            fiscal_config = await self._get_fiscal_config()

            # Build payment complement XML
            payment_xml = await self._build_payment_complement(
                related_cfdis, payment_data, fiscal_config
            )

            # Generate CFDI with payment complement
            from modules.fiscal.cfdi_builder import CFDIBuilder
            from modules.fiscal.signature import sign_cfdi_xml

            builder = CFDIBuilder(fiscal_config)

            # Build base CFDI (tipo "P" - Pago)
            base_xml = self._build_payment_cfdi_base(payment_data, fiscal_config)

            # Add payment complement
            full_xml = self._inject_payment_complement(base_xml, payment_xml)

            # Sign
            signed_xml = sign_cfdi_xml(full_xml, fiscal_config)

            # Send to PAC (was missing await before)
            from modules.fiscal.pac_connector import create_pac_connector
            pac = create_pac_connector(fiscal_config)
            result = await pac.timbrar_cfdi(signed_xml)

            if not result.get('success'):
                return result

            # Save to database
            cfdi_id = await self._save_payment_receipt(
                result, payment_data, related_cfdis
            )

            result['cfdi_id'] = cfdi_id
            result['type'] = 'payment_receipt'

            return result

        except Exception as e:
            logger.error(f"Error generating payment receipt: {e}")
            return {'success': False, 'error': str(e)}

    async def _build_payment_complement(
        self,
        related_cfdis: List[str],
        payment_data: Dict[str, Any],
        fiscal_config: Dict[str, Any],
    ) -> str:
        """Build payment complement XML following SAT Pagos 2.0 specification."""
        pago_ns = "http://www.sat.gob.mx/Pagos20"

        total_amount = money(payment_data.get("amount", 0))
        currency = xml_escape(payment_data.get("currency", "MXN"))

        xml = f'<pago20:Pagos xmlns:pago20="{pago_ns}" Version="2.0">\n'
        xml += f'  <pago20:Totales MontoTotalPagos="{total_amount:.2f}"/>\n'

        payment_date = xml_escape(
            payment_data.get("payment_date", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
        )
        payment_method = xml_escape(payment_data.get("payment_method", "03"))
        operation_number = xml_escape(payment_data.get("operation_number", ""))

        xml += f'  <pago20:Pago FechaPago="{payment_date}" FormaDePagoP="{payment_method}" '
        xml += f'MonedaP="{currency}" Monto="{total_amount:.2f}"'

        if operation_number:
            xml += f' NumOperacion="{operation_number}"'

        xml += '>\n'

        # Related documents (DoctoRelacionado)
        for uuid in related_cfdis:
            cfdi_row = await self.db.fetchrow(
                "SELECT * FROM cfdis WHERE uuid = :uuid",
                {"uuid": uuid},
            )
            if cfdi_row:
                cfdi_total = money(cfdi_row.get("total", 0))
                paid_amount = min(total_amount, cfdi_total)
                remaining = max(0, cfdi_total - paid_amount)

                xml += f'    <pago20:DoctoRelacionado IdDocumento="{xml_escape(uuid)}" '
                xml += f'MonedaDR="{currency}" '
                xml += f'MetodoDePagoDR="PPD" '
                xml += f'NumParcialidad="1" '
                xml += f'ImpSaldoAnt="{cfdi_total:.2f}" '
                xml += f'ImpPagado="{paid_amount:.2f}" '
                xml += f'ImpSaldoInsoluto="{remaining:.2f}" '
                xml += f'ObjetoImpDR="01"/>\n'

        xml += '  </pago20:Pago>\n'
        xml += '</pago20:Pagos>\n'

        return xml

    def _build_payment_cfdi_base(
        self,
        payment_data: Dict[str, Any],
        fiscal_config: Dict[str, Any],
    ) -> str:
        """Build base CFDI for payment type (sync, no I/O operations)."""
        fecha = xml_escape(
            payment_data.get("payment_date", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
        )
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml += '<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" '
        xml += 'Version="4.0" '
        xml += f'Fecha="{fecha}" '
        xml += 'SubTotal="0" '
        xml += 'Total="0" '
        xml += 'Moneda="XXX" '
        xml += 'TipoDeComprobante="P" '
        xml += 'Exportacion="01" '
        xml += 'LugarExpedicion="' + xml_escape(fiscal_config.get('lugar_expedicion', '00000')) + '">\n'

        xml += '  <cfdi:Emisor '
        xml += 'Rfc="' + xml_escape(fiscal_config.get('rfc_emisor', '')) + '" '
        xml += 'Nombre="' + xml_escape(fiscal_config.get('razon_social_emisor', '')) + '" '
        xml += 'RegimenFiscal="' + xml_escape(fiscal_config.get('regimen_fiscal', '601')) + '"/>\n'

        xml += '  <cfdi:Receptor '
        xml += 'Rfc="' + xml_escape(payment_data.get('payer_rfc', 'XAXX010101000')) + '" '
        xml += 'Nombre="' + xml_escape(payment_data.get('payer_name', 'Cliente')) + '" '
        xml += 'UsoCFDI="CP01"/>\n'

        xml += '  <cfdi:Conceptos>\n'
        xml += '    <cfdi:Concepto ClaveProdServ="84111506" Cantidad="1" '
        xml += 'ClaveUnidad="ACT" Descripcion="Pago" ValorUnitario="0" Importe="0" '
        xml += 'ObjetoImp="01"/>\n'
        xml += '  </cfdi:Conceptos>\n'

        xml += '</cfdi:Comprobante>\n'

        return xml

    def _inject_payment_complement(self, base_xml: str, complement_xml: str) -> str:
        """Inject payment complement into base CFDI (sync, no I/O operations)."""
        insert_point = base_xml.rfind('</cfdi:Comprobante>')

        full_xml = base_xml[:insert_point]
        full_xml += '  <cfdi:Complemento>\n'
        full_xml += '    ' + complement_xml
        full_xml += '  </cfdi:Complemento>\n'
        full_xml += base_xml[insert_point:]

        return full_xml

    async def _save_payment_receipt(
        self,
        pac_result: Dict[str, Any],
        payment_data: Dict[str, Any],
        related_cfdis: List[str],
    ) -> int:
        """Save payment receipt to database."""
        from pathlib import Path
        from modules.fiscal.utils import DATA_DIR

        uuid = pac_result['uuid']
        xml_dir = Path(DATA_DIR) / "cfdis"
        xml_dir.mkdir(exist_ok=True)

        xml_path = xml_dir / f"{uuid}.xml"
        async with aiofiles.open(xml_path, 'w', encoding='utf-8') as f:
            await f.write(pac_result['xml_timbrado'])

        row = await self.db.fetchrow(
            """INSERT INTO cfdis
               (uuid, folio, serie, rfc_receptor, nombre_receptor,
                xml_timbrado, fecha_timbrado, total, estado)
               VALUES (:uuid, 0, 'P', :rfc, :nombre,
                :xml, :fecha, 0, 'vigente')
               RETURNING id""",
            {
                "uuid": uuid,
                "rfc": payment_data.get('payer_rfc', 'XAXX010101000'),
                "nombre": payment_data.get('payer_name', 'Cliente'),
                "xml": pac_result['xml_timbrado'],
                "fecha": pac_result.get('fecha_timbrado'),
            },
        )
        cfdi_id = row['id'] if row else 0

        # Link to related CFDIs
        for related_uuid in related_cfdis:
            await self.db.execute(
                "INSERT INTO cfdi_relations (parent_uuid, related_uuid, relation_type) "
                "VALUES (:parent, :related, 'payment')",
                {"parent": uuid, "related": related_uuid},
            )

        return cfdi_id
