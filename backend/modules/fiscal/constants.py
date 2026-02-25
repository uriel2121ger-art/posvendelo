"""
CFDI Constants
Central location for all CFDI-related constants
"""

# CFDI Version
CFDI_VERSION = "4.0"

# Namespaces
CFDI_NS = "http://www.sat.gob.mx/cfd/4"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
PAGOS_NS = "http://www.sat.gob.mx/Pagos20"

# Schema locations
CFDI_SCHEMA_LOCATION = "http://www.sat.gob.mx/cfd/4 http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd"

# Default values
DEFAULT_CURRENCY = "MXN"
DEFAULT_EXPORTACION = "01"  # No aplica
DEFAULT_USO_CFDI = "G03"  # Gastos en general
DEFAULT_REGIMEN_RECEPTOR = "616"  # Sin obligaciones fiscales

# Payment methods (Forma de Pago)
PAYMENT_METHODS = {
    'cash': '01',  # Efectivo
    'check': '02',  # Cheque nominativo
    'transfer': '03',  # Transferencia electrónica
    'card': '04',  # Tarjeta de crédito
    'wallet': '05',  # Monedero electrónico
    'money_order': '06',  # Dinero electrónico
    'voucher': '08',  # Vales de despensa
    'credit': '12',  # Dación en pago
    'payment_subrogation': '13',  # Pago por subrogación
    'payment_consignment': '14',  # Pago por consignación
    'condonation': '15',  # Condonación
    'compensation': '17',  # Compensación
    'novation': '23',  # Novación
    'confusion': '24',  # Confusión
    'debt_remission': '25',  # Remisión de deuda
    'prescription': '26',  # Prescripción o caducidad
    'creditor_satisfaction': '27',  # A satisfacción del acreedor
    'debit_card': '28',  # Tarjeta de débito
    'service_card': '29',  # Tarjeta de servicios
    'third_party_app': '30',  # Aplicación de anticipos
    'intermediary': '31',  # Intermediario pagos
    'to_define': '99',  # Por definir
}

# Payment method codes (Método de Pago)
PAYMENT_METHOD_CODES = {
    'PUE': 'Pago en una sola exhibición',
    'PPD': 'Pago en parcialidades o diferido'
}

# Invoice types (Tipo de Comprobante)
INVOICE_TYPES = {
    'I': 'Ingreso',
    'E': 'Egreso',
    'T': 'Traslado',
    'N': 'Nómina',
    'P': 'Pago'
}

# Cancellation reasons (Motivo de Cancelación)
CANCELLATION_REASONS = {
    '01': 'Comprobante emitido con errores con relación',
    '02': 'Comprobante emitido con errores sin relación',
    '03': 'No se llevó a cabo la operación',
    '04': 'Operación nominativa relacionada en una factura global'
}

# Tax types
TAX_TYPES = {
    '001': 'ISR',
    '002': 'IVA',
    '003': 'IEPS'
}

# Tax rates
IVA_RATE = 0.16
IVA_TASA_STR = "0.160000"  # 6 decimal places per SAT spec
IVA_TASA_CUOTA = '0.160000'  # Legacy alias

# Product/Service keys (default)
DEFAULT_PROD_SERV_KEY = '01010101'  # Genérico - No existe en catálogo del contribuyente
DEFAULT_UNIT_KEY = 'H87'  # Pieza
DEFAULT_UNIT_NAME = 'Pieza'

# Objeto de impuesto
TAX_OBJECT = {
    '01': 'No objeto de impuesto',
    '02': 'Sí objeto de impuesto',
    '03': 'Sí objeto del impuesto y no obligado al desglose',
    '04': 'Sí objeto del impuesto y no causa impuesto'
}

# CFDI Use (Uso CFDI) - Common ones
CFDI_USE = {
    'G01': 'Adquisición de mercancías',
    'G02': 'Devoluciones, descuentos o bonificaciones',
    'G03': 'Gastos en general',
    'I01': 'Construcciones',
    'I02': 'Mobilario y equipo de oficina por inversiones',
    'I03': 'Equipo de transporte',
    'I04': 'Equipo de computo y accesorios',
    'I05': 'Dados, troqueles, moldes, matrices y herramental',
    'I06': 'Comunicaciones telefónicas',
    'I07': 'Comunicaciones satelitales',
    'I08': 'Otra maquinaria y equipo',
    'D01': 'Honorarios médicos, dentales y gastos hospitalarios',
    'D02': 'Gastos médicos por incapacidad o discapacidad',
    'D03': 'Gastos funerales',
    'D04': 'Donativos',
    'D05': 'Intereses reales efectivamente pagados por créditos hipotecarios',
    'D06': 'Aportaciones voluntarias al SAR',
    'D07': 'Primas por seguros de gastos médicos',
    'D08': 'Gastos de transportación escolar obligatoria',
    'D09': 'Depósitos en cuentas para el ahorro',
    'D10': 'Pagos por servicios educativos',
    'S01': 'Sin efectos fiscales',
    'CP01': 'Pagos',
    'CN01': 'Nómina'
}

# Fiscal regimes (most common)
FISCAL_REGIMES = {
    '601': 'General de Ley Personas Morales',
    '603': 'Personas Morales con Fines no Lucrativos',
    '605': 'Sueldos y Salarios e Ingresos Asimilados a Salarios',
    '606': 'Arrendamiento',
    '607': 'Régimen de Enajenación o Adquisición de Bienes',
    '608': 'Demás ingresos',
    '610': 'Residentes en el Extranjero sin Establecimiento Permanente en México',
    '611': 'Ingresos por Dividendos (socios y accionistas)',
    '612': 'Personas Físicas con Actividades Empresariales y Profesionales',
    '614': 'Ingresos por intereses',
    '615': 'Régimen de los ingresos por obtención de premios',
    '616': 'Sin obligaciones fiscales',
    '620': 'Sociedades Cooperativas de Producción que optan por diferir sus ingresos',
    '621': 'Incorporación Fiscal',
    '622': 'Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras',
    '623': 'Opcional para Grupos de Sociedades',
    '624': 'Coordinados',
    '625': 'Régimen de las Actividades Empresariales con ingresos a través de Plataformas Tecnológicas',
    '626': 'Régimen Simplificado de Confianza - RESICO'
}

# RFC for generic public
RFC_GENERIC_PUBLIC = 'XAXX010101000'
NOMBRE_GENERIC_PUBLIC = 'PUBLICO EN GENERAL'

# Validation regex
RFC_PATTERN_MORAL = r'^[A-Z&Ñ]{3}\d{6}[A-Z0-9]{3}$'  # 12 characters
RFC_PATTERN_FISICA = r'^[A-Z&Ñ]{4}\d{6}[A-Z0-9]{3}$'  # 13 characters
EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

# Timeouts
SMTP_TIMEOUT = 30
PAC_REQUEST_TIMEOUT = 30

# Error messages
ERROR_MESSAGES = {
    'NO_FISCAL_CONFIG': 'Configuración fiscal no encontrada. Configure en Settings → Facturación',
    'NO_SALE': 'Venta no encontrada',
    'SALE_CANCELLED': 'No se puede facturar una venta cancelada',
    'ALREADY_INVOICED': 'Esta venta ya tiene CFDI',
    'INVALID_RFC': 'RFC inválido',
    'INVALID_EMAIL': 'Email inválido',
    'NO_ITEMS': 'La venta debe tener al menos un producto',
    'CERT_NOT_FOUND': 'Archivo de certificado no encontrado',
    'KEY_NOT_FOUND': 'Archivo de llave privada no encontrado',
    'INVALID_PASSWORD': 'Contraseña del certificado incorrecta',
    'PAC_ERROR': 'Error en el servicio de timbrado',
}
