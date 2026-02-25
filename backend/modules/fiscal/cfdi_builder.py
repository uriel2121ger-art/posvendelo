"""
CFDI 4.0 XML Builder
Generates SAT-compliant CFDI XML for electronic invoicing in Mexico

Includes SAT validation rules for MetodoPago (PUE/PPD) and FormaPago
"""

from typing import Any, Dict, List
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
import logging

from lxml import etree
from modules.fiscal.constants import IVA_RATE, IVA_TASA_STR

logger = logging.getLogger(__name__)

# CFDI 4.0 Namespace
CFDI_NS = "http://www.sat.gob.mx/cfd/4"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOCATION = "http://www.sat.gob.mx/cfd/4 http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd"

# Namespace map
NSMAP = {
    'cfdi': CFDI_NS,
    'xsi': XSI_NS
}

# ==============================================================================
# CATÁLOGO SAT: FORMAS DE PAGO (c_FormaPago)
# ==============================================================================
FORMAS_PAGO_SAT = {
    '01': 'Efectivo',
    '02': 'Cheque nominativo',
    '03': 'Transferencia electrónica de fondos',
    '04': 'Tarjeta de crédito',
    '05': 'Monedero electrónico',
    '06': 'Dinero electrónico',
    '08': 'Vales de despensa',
    '12': 'Dación en pago',
    '13': 'Pago por subrogación',
    '14': 'Pago por consignación',
    '15': 'Condonación',
    '17': 'Compensación',
    '23': 'Novación',
    '24': 'Confusión',
    '25': 'Remisión de deuda',
    '26': 'Prescripción o caducidad',
    '27': 'A satisfacción del acreedor',
    '28': 'Tarjeta de débito',
    '29': 'Tarjeta de servicios',
    '30': 'Aplicación de anticipos',
    '99': 'Por definir'
}

# ==============================================================================
# CATÁLOGO SAT: MÉTODOS DE PAGO
# ==============================================================================
METODOS_PAGO_SAT = {
    'PUE': 'Pago en Una Exhibición',  # El dinero ya entró o entrará este mes
    'PPD': 'Pago en Parcialidades o Diferido'  # Venta a crédito
}

def validate_payment_logic(metodo_pago: str, forma_pago: str) -> bool:
    """
    Valida que la combinación MetodoPago + FormaPago sea válida según SAT.
    
    REGLA DE ORO DEL SAT:
    - PUE: Cualquier forma de pago EXCEPTO "99"
    - PPD: OBLIGATORIAMENTE "99" (Por definir)
    
    Args:
        metodo_pago: 'PUE' o 'PPD'
        forma_pago: Clave de forma de pago ('01', '04', '99', etc.)
        
    Returns:
        True si es válida
        
    Raises:
        ValueError: Si la combinación es inválida
    """
    if metodo_pago == 'PPD' and forma_pago != '99':
        raise ValueError(
            f"Error SAT: PPD requiere Forma de Pago 99 (Por definir). "
            f"Recibido: {forma_pago} ({FORMAS_PAGO_SAT.get(forma_pago, 'Desconocido')})"
        )
    
    if metodo_pago == 'PUE' and forma_pago == '99':
        raise ValueError(
            "Error SAT: PUE no puede usar Forma de Pago 99 (Por definir). "
            "El pago debe estar definido al momento de la facturación."
        )
    
    return True

def determine_metodo_pago(payment_method: str, is_credit_sale: bool = False) -> str:
    """
    Determina automáticamente el MetodoPago según las reglas del SAT.
    
    Args:
        payment_method: Método de pago interno ('cash', 'card', 'credit', etc.)
        is_credit_sale: True si es venta a crédito
        
    Returns:
        'PUE' o 'PPD'
    """
    # REGLA 1: Si es crédito → SIEMPRE PPD
    if is_credit_sale or payment_method == 'credit':
        return 'PPD'
    
    # REGLA 2: Métodos con pago inmediato → PUE
    metodos_pue = ['cash', 'card', 'transfer', 'check', 'usd', 'wallet', 'gift_card']
    if payment_method in metodos_pue:
        return 'PUE'
    
    # Default: PUE si recibimos el pago el mismo mes
    return 'PUE'

class CFDIBuilder:
    """Builds CFDI 4.0 XML documents."""
    
    def __init__(self, fiscal_config: Dict[str, Any]):
        """
        Initialize CFDI builder with fiscal configuration.
        
        Args:
            fiscal_config: Dictionary from core.get_fiscal_config()
        """
        self.config = fiscal_config
    
    def build(self, sale_data: Dict[str, Any], customer_data: Dict[str, Any]) -> str:
        """
        Build complete CFDI XML from sale and customer data.
        
        Args:
            sale_data: Sale information from database
            customer_data: Customer RFC, name, regime
            
        Returns:
            XML string (not yet signed)
        """
        # Create root Comprobante element
        comprobante = self._build_comprobante(sale_data)
        
        # Add Emisor
        emisor = self._build_emisor()
        comprobante.append(emisor)
        
        # Add Receptor
        receptor = self._build_receptor(customer_data)
        comprobante.append(receptor)
        
        # Add Conceptos (line items)
        conceptos = self._build_conceptos(sale_data['items'])
        comprobante.append(conceptos)
        
        # Add Impuestos (taxes)
        impuestos = self._build_impuestos(sale_data)
        comprobante.append(impuestos)
        
        # Convert to string
        xml_bytes = etree.tostring(
            comprobante,
            pretty_print=True,
            xml_declaration=True,
            encoding='UTF-8'
        )
        
        return xml_bytes.decode('utf-8')
    
    def _build_comprobante(self, sale_data: Dict[str, Any]) -> etree.Element:
        """Build root Comprobante element with SAT validation."""
        payment_method = sale_data.get('payment_method', 'cash')
        is_credit = payment_method == 'credit'
        
        # Determine MetodoPago and FormaPago according to SAT rules
        metodo_pago = determine_metodo_pago(payment_method, is_credit)
        forma_pago = self._map_payment_method(payment_method)
        
        # VALIDACIÓN SAT CRÍTICA: PPD requiere 99, PUE no puede ser 99
        validate_payment_logic(metodo_pago, forma_pago)
        
        attrs = {
            'Version': '4.0',
            'Serie': self.config.get('serie_factura', 'F'),
            'Folio': str(self.config.get('folio_actual', 1)),
            'Fecha': self._format_timestamp(sale_data.get('timestamp')),
            'FormaPago': forma_pago,
            'MetodoPago': metodo_pago,
            'TipoDeComprobante': 'I',  # Ingreso
            'LugarExpedicion': self.config.get('lugar_expedicion', '00000'),
            'SubTotal': f"{sale_data.get('subtotal', 0):.2f}",
            'Total': f"{sale_data.get('total', 0):.2f}",
            'Moneda': 'MXN',
            'Exportacion': '01',  # No aplica
            '{' + XSI_NS + '}schemaLocation': SCHEMA_LOCATION
        }
        
        # Add Descuento if applicable
        if sale_data.get('discount', 0) > 0:
            attrs['Descuento'] = f"{sale_data['discount']:.2f}"
        
        return etree.Element('{' + CFDI_NS + '}Comprobante', nsmap=NSMAP, **attrs)
    
    def _build_emisor(self) -> etree.Element:
        """Build Emisor (issuer) element."""
        attrs = {
            'Rfc': self.config.get('rfc_emisor', ''),
            'Nombre': self.config.get('razon_social_emisor', ''),
            'RegimenFiscal': self.config.get('regimen_fiscal', '601')
        }
        
        return etree.Element('{' + CFDI_NS + '}Emisor', **attrs)
    
    def _build_receptor(self, customer_data: Dict[str, Any]) -> etree.Element:
        """Build Receptor (customer) element."""
        attrs = {
            'Rfc': customer_data.get('rfc', 'XAXX010101000'),
            'Nombre': customer_data.get('nombre', 'PUBLICO EN GENERAL'),
            'DomicilioFiscalReceptor': customer_data.get('codigo_postal', '00000'),
            'RegimenFiscalReceptor': customer_data.get('regimen_fiscal', '616'),
            'UsoCFDI': customer_data.get('uso_cfdi', 'G03')  # Gastos en general
        }
        
        return etree.Element('{' + CFDI_NS + '}Receptor', **attrs)
    
    def _build_conceptos(self, items: List[Dict[str, Any]]) -> etree.Element:
        """Build Conceptos (line items) element."""
        conceptos = etree.Element('{' + CFDI_NS + '}Conceptos')
        
        for item in items:
            # Get SAT codes from product or use defaults
            clave_prod_serv = item.get('sat_clave_prod_serv', '01010101')
            clave_unidad = item.get('sat_clave_unidad', 'H87')
            
            # Map common clave_unidad to description
            unidad_desc = {
                'H87': 'Pieza',
                'KGM': 'Kilogramo',
                'LTR': 'Litro',
                'MTR': 'Metro',
                'XBX': 'Caja',
                'ACT': 'Actividad',
                'E48': 'Servicio',
            }.get(clave_unidad, 'Pieza')
            
            concepto_attrs = {
                'ClaveProdServ': clave_prod_serv,
                'Cantidad': f"{item.get('qty', 1):.2f}",
                'ClaveUnidad': clave_unidad,
                'Unidad': unidad_desc,
                'Descripcion': item.get('product_name', 'Producto'),
                'ValorUnitario': f"{item.get('price', 0):.2f}",
                'Importe': f"{item.get('subtotal', 0):.2f}",
                'ObjetoImp': '02'  # Sí objeto de impuesto
            }
            
            concepto = etree.Element('{' + CFDI_NS + '}Concepto', **concepto_attrs)
            
            # Add taxes for this item
            impuestos_concepto = self._build_impuestos_concepto(item)
            if impuestos_concepto is not None:
                concepto.append(impuestos_concepto)
            
            conceptos.append(concepto)
        
        return conceptos
    
    def _build_impuestos_concepto(self, item: Dict[str, Any]) -> etree.Element:
        """Build taxes for a single line item."""
        impuestos = etree.Element('{' + CFDI_NS + '}Impuestos')

        # Traslados (transferred taxes like IVA)
        traslados = etree.Element('{' + CFDI_NS + '}Traslados')

        # IVA 16%
        item_subtotal = Decimal(str(item.get('subtotal', 0)))
        iva_amount = (item_subtotal * Decimal(str(IVA_RATE))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        traslado_attrs = {
            'Base': f"{item_subtotal:.2f}",
            'Impuesto': '002',  # IVA
            'TipoFactor': 'Tasa',
            'TasaOCuota': IVA_TASA_STR,
            'Importe': f"{iva_amount:.2f}"
        }

        traslado = etree.Element('{' + CFDI_NS + '}Traslado', **traslado_attrs)
        traslados.append(traslado)
        impuestos.append(traslados)

        return impuestos
    
    def _build_impuestos(self, sale_data: Dict[str, Any]) -> etree.Element:
        """Build Impuestos (taxes summary) element."""
        impuestos = etree.Element('{' + CFDI_NS + '}Impuestos')

        total_impuestos = sale_data.get('tax', 0)
        if total_impuestos > 0:
            impuestos.set('TotalImpuestosTrasladados', f"{total_impuestos:.2f}")

        # Traslados
        traslados = etree.Element('{' + CFDI_NS + '}Traslados')

        subtotal = sale_data.get('subtotal', 0)
        traslado_attrs = {
            'Base': f"{subtotal:.2f}",
            'Impuesto': '002',  # IVA
            'TipoFactor': 'Tasa',
            'TasaOCuota': IVA_TASA_STR,
            'Importe': f"{total_impuestos:.2f}"
        }

        traslado = etree.Element('{' + CFDI_NS + '}Traslado', **traslado_attrs)
        traslados.append(traslado)
        impuestos.append(traslados)

        return impuestos
    
    def _format_timestamp(self, timestamp_str: str) -> str:
        """Format datetime to CFDI format: YYYY-MM-DDTHH:MM:SS"""
        try:
            if not timestamp_str:
                timestamp_str = datetime.now().isoformat()
            
            # Parse and format
            dt = datetime.fromisoformat(timestamp_str.replace(' ', 'T'))
            return dt.strftime('%Y-%m-%dT%H:%M:%S')
        except Exception:
            return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    
    def _map_payment_method(self, payment_method: str) -> str:
        """
        Map internal payment method to SAT catalog (c_FormaPago).
        
        SAT Catalog:
            01: Efectivo
            02: Cheque nominativo
            03: Transferencia electrónica de fondos
            04: Tarjeta de crédito
            05: Monedero electrónico
            08: Vales de despensa
            28: Tarjeta de débito
            99: Por definir (SOLO para PPD/crédito)
        """
        mapping = {
            'cash': '01',          # Efectivo
            'card': '04',          # Tarjeta de crédito (default)
            'credit_card': '04',   # Tarjeta de crédito
            'debit_card': '28',    # Tarjeta de débito
            'transfer': '03',      # Transferencia electrónica
            'check': '02',         # Cheque nominativo
            'cheque': '02',        # Cheque nominativo (alias)
            'usd': '01',           # Dólares = Efectivo
            'vales': '08',         # Vales de despensa
            'voucher': '08',       # Vales (alias)
            'wallet': '05',        # Monedero electrónico (puntos MIDAS)
            'gift_card': '05',     # Tarjeta regalo = Monedero electrónico
            'credit': '99',        # Crédito = Por definir (PPD)
            'mixed': '99',         # Mixto = Por definir
        }
        return mapping.get(payment_method, '01')  # Default: Efectivo
    
    def build_credit_note(self, credit_data: Dict[str, Any], customer_data: Dict[str, Any]) -> str:
        """
        Build CFDI XML for a credit note (Nota de Crédito - Tipo E).
        
        Args:
            credit_data: Dictionary with:
                - tipo_comprobante: 'E' (Egreso)
                - subtotal, tax, total
                - items: list of products
                - cfdi_relacionado: UUID of original CFDI
                - tipo_relacion: '01' for credit note
            customer_data: Customer RFC, name, regime
            
        Returns:
            XML string (not yet signed)
        """
        # Create root Comprobante element for Egreso (Credit Note)
        comprobante = self._build_comprobante_egreso(credit_data)
        
        # Add CfdiRelacionados (related CFDI - required for credit notes)
        if credit_data.get('cfdi_relacionado'):
            relacionados = self._build_cfdi_relacionados(
                credit_data.get('cfdi_relacionado'),
                credit_data.get('tipo_relacion', '01')
            )
            comprobante.append(relacionados)
        
        # Add Emisor
        emisor = self._build_emisor()
        comprobante.append(emisor)
        
        # Add Receptor
        receptor = self._build_receptor(customer_data)
        comprobante.append(receptor)
        
        # Add Conceptos
        conceptos = self._build_conceptos_credit_note(
            credit_data.get('items', []),
            credit_data.get('descripcion_nota', 'Nota de crédito')
        )
        comprobante.append(conceptos)
        
        # Add Impuestos
        impuestos = self._build_impuestos(credit_data)
        comprobante.append(impuestos)
        
        # Convert to string
        xml_bytes = etree.tostring(
            comprobante,
            pretty_print=True,
            xml_declaration=True,
            encoding='UTF-8'
        )
        
        return xml_bytes.decode('utf-8')
    
    def _build_comprobante_egreso(self, credit_data: Dict[str, Any]) -> etree.Element:
        """Build root Comprobante element for Egreso (Credit Note)."""
        attrs = {
            'Version': '4.0',
            'Serie': self.config.get('serie_nota_credito', 'NC'),
            'Folio': str(self.config.get('folio_actual', 1)),
            'Fecha': self._format_timestamp(credit_data.get('timestamp')),
            'FormaPago': '99',  # Por definir (refund method varies)
            'MetodoPago': 'PUE',  # Pago en una sola exhibición
            'TipoDeComprobante': 'E',  # Egreso (Credit Note)
            'LugarExpedicion': self.config.get('lugar_expedicion', '00000'),
            'SubTotal': f"{credit_data.get('subtotal', 0):.2f}",
            'Total': f"{credit_data.get('total', 0):.2f}",
            'Moneda': 'MXN',
            'Exportacion': '01',  # No aplica
            '{' + XSI_NS + '}schemaLocation': SCHEMA_LOCATION
        }
        
        return etree.Element('{' + CFDI_NS + '}Comprobante', nsmap=NSMAP, **attrs)
    
    def _build_cfdi_relacionados(self, uuid_relacionado: str, tipo_relacion: str = '01') -> etree.Element:
        """
        Build CfdiRelacionados element for related CFDIs.
        
        Args:
            uuid_relacionado: UUID of the related CFDI
            tipo_relacion: Type of relation (01=Nota de crédito, 04=Sustitución, etc)
        """
        relacionados = etree.Element(
            '{' + CFDI_NS + '}CfdiRelacionados',
            TipoRelacion=tipo_relacion
        )
        
        cfdi_relacionado = etree.Element(
            '{' + CFDI_NS + '}CfdiRelacionado',
            UUID=uuid_relacionado.upper()
        )
        
        relacionados.append(cfdi_relacionado)
        return relacionados
    
    def _build_conceptos_credit_note(self, items: List[Dict[str, Any]], descripcion: str = 'Nota de crédito') -> etree.Element:
        """Build Conceptos for credit note."""
        conceptos = etree.Element('{' + CFDI_NS + '}Conceptos')
        
        for item in items:
            concepto_attrs = {
                'ClaveProdServ': '84111506',  # Servicios de facturación
                'Cantidad': f"{item.get('qty', 1):.2f}",
                'ClaveUnidad': 'ACT',  # Actividad
                'Unidad': 'Actividad',
                'Descripcion': f"{descripcion}: {item.get('product_name', 'Producto')}",
                'ValorUnitario': f"{item.get('price', 0):.2f}",
                'Importe': f"{item.get('subtotal', item.get('total', 0)):.2f}",
                'ObjetoImp': '02'  # Sí objeto de impuesto
            }
            
            concepto = etree.Element('{' + CFDI_NS + '}Concepto', **concepto_attrs)
            
            # Add taxes
            impuestos_concepto = self._build_impuestos_concepto(item)
            if impuestos_concepto is not None:
                concepto.append(impuestos_concepto)
            
            conceptos.append(concepto)
        
        return conceptos
