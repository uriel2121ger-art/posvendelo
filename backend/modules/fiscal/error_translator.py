"""
Traductor de Errores SAT
Convierte errores crípticos del SAT a mensajes amigables para usuarios.

Uso:
    from modules.fiscal.error_translator import translate_sat_error, get_solution
    
    # Error del PAC
    error_code = "301"
    error_message = "La estructura del atributo 'Importe' es incorrecta"
    
    # Traducir
    friendly = translate_sat_error(error_code, error_message)
    print(friendly['user_message'])  # "El precio de un producto tiene formato incorrecto..."
    print(friendly['solution'])       # "Verifica que los precios sean números positivos..."
"""
from typing import Any, Dict, Optional
import logging
import re

logger = logging.getLogger("SAT_ERRORS")

# =============================================================================
# DICCIONARIO DE ERRORES SAT → MENSAJES AMIGABLES
# =============================================================================

SAT_ERROR_TRANSLATIONS = {
    # Errores de Estructura (300s)
    "301": {
        "category": "Estructura XML",
        "user_message": "El precio de un producto tiene formato incorrecto",
        "solution": "Verifica que los precios sean números positivos con máximo 2 decimales",
        "technical": "Atributo 'Importe' con estructura incorrecta (ej: número negativo o demasiados decimales)"
    },
    "302": {
        "category": "Estructura XML",
        "user_message": "El RFC del emisor o receptor es inválido",
        "solution": "Verifica que el RFC tenga 12 caracteres (empresa) o 13 caracteres (persona) y sea correcto",
        "technical": "RFC no cumple con el patrón regex del SAT"
    },
    "303": {
        "category": "Estructura XML",
        "user_message": "Falta información obligatoria en la factura",
        "solution": "Revisa que todos los campos requeridos estén llenos (RFC, nombre, uso CFDI, etc.)",
        "technical": "Atributo requerido no presente en el XML"
    },
    "304": {
        "category": "Estructura XML",
        "user_message": "El código postal del emisor no es válido",
        "solution": "Verifica que el código postal tenga 5 dígitos y corresponda a tu ubicación",
        "technical": "Atributo 'LugarExpedicion' no corresponde al catálogo c_CodigoPostal"
    },
    "305": {
        "category": "Estructura XML",
        "user_message": "El código del producto SAT no es válido",
        "solution": "El código 'ClaveProdServ' no existe en el catálogo del SAT. Usa uno válido como '01010101'",
        "technical": "ClaveProdServ no encontrado en catálogo c_ClaveProdServ"
    },
    
    # Errores de Validación Fiscal (400s)
    "401": {
        "category": "Fecha y Hora",
        "user_message": "La fecha de la factura está fuera del rango permitido",
        "solution": "Solo puedes facturar hasta 72 horas atrás. Verifica la fecha y hora de tu computadora",
        "technical": "Fecha del comprobante fuera del rango de tolerancia (72 horas)"
    },
    "402": {
        "category": "Certificado",
        "user_message": "Tu certificado de sello digital (CSD) ha expirado",
        "solution": "Necesitas renovar tu CSD en el portal del SAT. Agenda cita para tramitarlo",
        "technical": "CSD con fecha de vigencia vencida"
    },
    "403": {
        "category": "Certificado",
        "user_message": "El certificado no corresponde al RFC del emisor",
        "solution": "El archivo .cer que estás usando es de otro RFC. Verifica que sea el correcto",
        "technical": "RFC del CSD no coincide con RFC del emisor en el XML"
    },
    "404": {
        "category": "Sello Digital",
        "user_message": "Error al firmar la factura",
        "solution": "La contraseña del archivo .key es incorrecta o el archivo está dañado",
        "technical": "No se pudo generar el sello digital - llave privada inválida"
    },
    "405": {
        "category": "Régimen Fiscal",
        "user_message": "El régimen fiscal no es válido para este tipo de operación",
        "solution": "Verifica que el régimen fiscal del emisor sea correcto (ej: 601, 612, 621)",
        "technical": "RegimenFiscal no válido según catálogo c_RegimenFiscal"
    },
    
    # Errores de Receptor (500s)
    "501": {
        "category": "Datos del Cliente",
        "user_message": "El nombre del cliente no coincide con los registros del SAT",
        "solution": "El nombre DEBE coincidir EXACTAMENTE con la Constancia de Situación Fiscal del cliente (incluyendo acentos y mayúsculas)",
        "technical": "Nombre del receptor no coincide con registro en SAT"
    },
    "502": {
        "category": "Datos del Cliente", 
        "user_message": "El código postal del cliente no es válido",
        "solution": "Pide al cliente su Constancia de Situación Fiscal y usa el código postal que aparece ahí",
        "technical": "DomicilioFiscalReceptor no válido"
    },
    "503": {
        "category": "Datos del Cliente",
        "user_message": "El régimen fiscal del cliente no es correcto",
        "solution": "Verifica el régimen fiscal en la Constancia de Situación Fiscal del cliente",
        "technical": "RegimenFiscalReceptor no válido para el RFC"
    },
    "504": {
        "category": "Uso CFDI",
        "user_message": "El uso del CFDI seleccionado no es válido para este cliente",
        "solution": "Cambia el 'Uso CFDI' a uno compatible con el régimen del cliente (G03 funciona para la mayoría)",
        "technical": "UsoCFDI no permitido para el RegimenFiscalReceptor"
    },
    
    # Errores de Cálculo (600s)
    "601": {
        "category": "Cálculo",
        "user_message": "La suma de los productos no coincide con el total",
        "solution": "Error de redondeo en los cálculos. Contacta soporte técnico",
        "technical": "Suma de Importe de conceptos no coincide con SubTotal"
    },
    "602": {
        "category": "Cálculo",
        "user_message": "El cálculo del IVA es incorrecto",
        "solution": "El impuesto calculado no coincide con el esperado. Verifica los porcentajes de IVA",
        "technical": "TotalImpuestosTrasladados no coincide con suma de traslados"
    },
    "603": {
        "category": "Cálculo",
        "user_message": "El total de la factura es incorrecto",
        "solution": "Total ≠ Subtotal - Descuento + Impuestos. Verifica los cálculos",
        "technical": "Atributo Total no coincide con cálculo: SubTotal - Descuento + Impuestos"
    },
    
    # Errores de Método de Pago (700s)
    "701": {
        "category": "Método de Pago",
        "user_message": "Combinación inválida de método y forma de pago",
        "solution": "Si es PPD (crédito), la forma de pago DEBE ser '99'. Si es PUE (contado), NO puede ser '99'",
        "technical": "MetodoPago=PPD requiere FormaPago=99 / MetodoPago=PUE no permite FormaPago=99"
    },
    "702": {
        "category": "Complemento de Pago",
        "user_message": "Falta el complemento de pago",
        "solution": "Las facturas PPD requieren un Recibo Electrónico de Pago (REP) cuando se cobra",
        "technical": "CFDI con MetodoPago=PPD sin complemento de pago asociado"
    },
    
    # Errores de Lista Negra (LCO/EFOS)
    "LCO": {
        "category": "Lista Negra",
        "user_message": "El RFC esta en la Lista Negra del SAT (Articulo 69-B)",
        "solution": "NO DEBES facturar a este RFC. Podría ser una empresa fantasma. Consulta con tu contador",
        "technical": "RFC en Lista de Contribuyentes con Operaciones Inexistentes (EFOS)"
    },
    "EFOS": {
        "category": "Lista Negra",
        "user_message": "RFC bloqueado por el SAT - Empresa Facturadora de Operaciones Simuladas",
        "solution": "Este RFC está inhabilitado. No lo uses para facturar",
        "technical": "RFC publicado en lista 69-B como EFOS definitivo"
    },
    
    # Errores de Cancelación (800s)
    "801": {
        "category": "Cancelación",
        "user_message": "No se puede cancelar: el cliente rechazó la solicitud",
        "solution": "Contacta al cliente para que acepte la cancelación en su buzón tributario",
        "technical": "Solicitud de cancelación rechazada por el receptor"
    },
    "802": {
        "category": "Cancelación",
        "user_message": "La factura ya fue cancelada previamente",
        "solution": "Esta factura ya tiene estatus 'Cancelado'. No es necesario cancelarla de nuevo",
        "technical": "Intento de cancelar UUID con estatus Cancelado"
    },
    "803": {
        "category": "Cancelación",
        "user_message": "Cancelación con motivo '01' requiere factura sustituta",
        "solution": "Primero genera la factura correcta y usa su UUID como 'folio fiscal que sustituye'",
        "technical": "Motivo 01 (sustitución) sin FolioSustitucion"
    },
    
    # Errores de Conexión
    "TIMEOUT": {
        "category": "Conexión",
        "user_message": "El servidor del SAT no responde",
        "solution": "El SAT está saturado (común días 15 y 30). Intenta de nuevo en unos minutos",
        "technical": "Timeout en conexión al PAC/SAT"
    },
    "CONNECTION_ERROR": {
        "category": "Conexión",
        "user_message": "No hay conexión a internet",
        "solution": "Verifica tu conexión a internet e intenta de nuevo",
        "technical": "Error de conexión TCP/HTTPS"
    },
    "PAC_ERROR": {
        "category": "Proveedor",
        "user_message": "Error en el servicio de facturación",
        "solution": "El PAC está teniendo problemas. Intenta de nuevo en unos minutos",
        "technical": "Error 500 del PAC"
    },
}

# Patrones para detectar errores en mensajes
ERROR_PATTERNS = [
    (r"importe.*incorrecto|incorrect.*amount", "301"),
    (r"rfc.*inv[aá]lid|invalid.*rfc", "302"),
    (r"atributo.*requerido|required.*attribute", "303"),
    (r"c[oó]digo postal|postal code|lugar.*expedici[oó]n", "304"),
    (r"claveprodserv|clave.*producto", "305"),
    (r"fecha.*rango|date.*range|72.*horas", "401"),
    (r"certificado.*vencid|expired.*certificate|csd.*expirado", "402"),
    (r"certificado.*no.*corresponde|certificate.*mismatch", "403"),
    (r"sello.*inv[aá]lid|invalid.*seal|firma.*error", "404"),
    (r"r[eé]gimen.*fiscal|fiscal.*regime", "405"),
    (r"nombre.*no.*coincide|name.*mismatch|receptor.*nombre", "501"),
    (r"domicilio.*fiscal.*receptor|receptor.*cp", "502"),
    (r"regimen.*fiscal.*receptor", "503"),
    (r"uso.*cfdi|usocfdi", "504"),
    (r"suma.*concepto|subtotal.*no.*coincide", "601"),
    (r"impuesto.*trasladad|iva.*incorrecto", "602"),
    (r"total.*no.*coincide|total.*incorrect", "603"),
    (r"metodopago.*formapago|pue.*ppd|99.*por.*definir", "701"),
    (r"complemento.*pago|rep.*falta", "702"),
    (r"lista.*negra|69-b|efos|lco", "LCO"),
    (r"cancelaci[oó]n.*rechaz", "801"),
    (r"ya.*cancelad", "802"),
    (r"motivo.*01.*sustitu", "803"),
    (r"timeout|tiempo.*agotado", "TIMEOUT"),
    (r"conexi[oó]n|connection|network", "CONNECTION_ERROR"),
]

def translate_sat_error(error_code: str = None,
                        error_message: str = None) -> Dict[str, Any]:
    """
    Traduce un error del SAT a un mensaje amigable.
    
    Args:
        error_code: Código de error (ej: "301", "401", "LCO")
        error_message: Mensaje de error del PAC/SAT
        
    Returns:
        {
            'code': str,
            'category': str,
            'user_message': str,
            'solution': str,
            'technical': str,
            'original_message': str
        }
    """
    result = {
        'code': error_code or 'UNKNOWN',
        'category': 'General',
        'user_message': 'Error al procesar la factura',
        'solution': 'Contacta a soporte técnico con el código de error',
        'technical': error_message or 'Error desconocido',
        'original_message': error_message
    }
    
    # Intentar buscar por código
    if error_code and error_code in SAT_ERROR_TRANSLATIONS:
        translation = SAT_ERROR_TRANSLATIONS[error_code]
        result.update({
            'category': translation['category'],
            'user_message': translation['user_message'],
            'solution': translation['solution'],
            'technical': translation['technical']
        })
        return result
    
    # Intentar detectar por patrones en el mensaje
    if error_message:
        message_lower = error_message.lower()
        
        for pattern, code in ERROR_PATTERNS:
            if re.search(pattern, message_lower):
                if code in SAT_ERROR_TRANSLATIONS:
                    translation = SAT_ERROR_TRANSLATIONS[code]
                    result.update({
                        'code': code,
                        'category': translation['category'],
                        'user_message': translation['user_message'],
                        'solution': translation['solution'],
                        'technical': translation['technical']
                    })
                    return result
    
    # Error no identificado
    logger.warning(f"Error SAT no traducido: {error_code} - {error_message}")
    return result

def get_solution(error_code: str) -> str:
    """
    Obtiene la solución sugerida para un código de error.
    """
    if error_code in SAT_ERROR_TRANSLATIONS:
        return SAT_ERROR_TRANSLATIONS[error_code]['solution']
    return "Contacta a soporte técnico con el código de error"

def get_user_message(error_code: str) -> str:
    """
    Obtiene el mensaje amigable para un código de error.
    """
    if error_code in SAT_ERROR_TRANSLATIONS:
        return SAT_ERROR_TRANSLATIONS[error_code]['user_message']
    return "Error al procesar la factura"

def format_error_for_ui(error_code: str = None,
                        error_message: str = None) -> str:
    """
    Formatea el error para mostrar en la UI.
    
    Returns:
        String formateado con emoji y mensaje
    """
    translation = translate_sat_error(error_code, error_message)

    return f"""**{translation['user_message']}**

**Codigo:** {translation['code']}
**Categoria:** {translation['category']}

**Solucion:**
{translation['solution']}

---
_Error tecnico: {translation['technical']}_
""".strip()

if __name__ == "__main__":
    def main():
        print("SAT Error Translator Test\n")

        # Test con codigos conocidos
        test_cases = [
            ("301", "La estructura del atributo 'Importe' es incorrecta"),
            ("401", "Fecha fuera de rango"),
            ("501", "El nombre del receptor no coincide"),
            ("LCO", "RFC en lista negra"),
            (None, "El timeout de conexion fue excedido"),
            (None, "Error desconocido XYZ"),
        ]

        for code, message in test_cases:
            result = translate_sat_error(code, message)
            print(f"Codigo: {result['code']}")
            print(f"  {result['user_message']}")
            print(f"  {result['solution']}")
            print()

    main()
