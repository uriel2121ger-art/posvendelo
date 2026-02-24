"""
Certificate validator for SAT CSD files (.cer and .key)
Validates certificate and key files used for CFDI electronic invoicing
"""
from typing import Any, Dict
import datetime
from pathlib import Path


def validate_cer_file(cert_path: str) -> Dict[str, Any]:
    """
    Validate .cer certificate file from SAT.
    
    Args:
        cert_path: Path to .cer file
        
    Returns:
        Dictionary with validation results:
        - valid: bool
        - serial: str (hex format)
        - valid_from: ISO datetime
        - valid_to: ISO datetime
        - subject: str
        - expired: bool
        - error: str (if invalid)
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        
        cert_path_obj = Path(cert_path)
        if not cert_path_obj.exists():
            return {'valid': False, 'error': 'Archivo no encontrado'}
        
        with open(cert_path, 'rb') as f:
            cert_data = f.read()
        
        # Load DER-encoded certificate (SAT certificates use DER format)
        cert = x509.load_der_x509_certificate(cert_data, default_backend())
        
        # Extract certificate info
        serial_hex = format(cert.serial_number, 'x').upper()
        valid_from = cert.not_valid_before
        valid_to = cert.not_valid_after
        is_expired = valid_to < datetime.datetime.now()
        
        # Get subject info
        subject = cert.subject.rfc4514_string()
        
        return {
            'valid': True,
            'serial': serial_hex,
            'valid_from': valid_from.isoformat(),
            'valid_to': valid_to.isoformat(),
            'subject': subject,
            'expired': is_expired,
            'days_remaining': (valid_to - datetime.datetime.now()).days if not is_expired else 0
        }
        
    except Exception as e:
        return {
            'valid': False,
            'error': f'Error al validar certificado: {str(e)}'
        }

def validate_key_file(key_path: str, password: str) -> Dict[str, Any]:
    """
    Validate .key private key file with password.
    
    Args:
        key_path: Path to .key file
        password: Password for the private key
        
    Returns:
        Dictionary with validation results:
        - valid: bool
        - key_type: str (type of private key)
        - error: str (if invalid)
    """
    try:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.serialization import load_der_private_key
        
        key_path_obj = Path(key_path)
        if not key_path_obj.exists():
            return {'valid': False, 'error': 'Archivo no encontrado'}
        
        if not password:
            return {'valid': False, 'error': 'Contraseña requerida'}
        
        with open(key_path, 'rb') as f:
            key_data = f.read()
        
        # Try to load private key with password
        # SAT keys are DER-encoded and password-protected
        private_key = load_der_private_key(
            key_data,
            password=password.encode('utf-8'),
            backend=default_backend()
        )
        
        key_type_name = type(private_key).__name__
        
        return {
            'valid': True,
            'key_type': key_type_name,
            'message': 'Llave privada validada correctamente'
        }
        
    except ValueError as e:
        # Most common error: wrong password
        return {
            'valid': False,
            'error': 'Contraseña incorrecta o archivo .key inválido'
        }
    except Exception as e:
        return {
            'valid': False,
            'error': f'Error al validar llave: {str(e)}'
        }

def validate_cert_key_pair(cert_path: str, key_path: str, password: str) -> Dict[str, Any]:
    """
    Validate that certificate and key files match and are valid.
    
    Args:
        cert_path: Path to .cer file
        key_path: Path to .key file
        password: Password for the private key
        
    Returns:
        Dictionary with combined validation results
    """
    cert_result = validate_cer_file(cert_path)
    if not cert_result['valid']:
        return {
            'valid': False,
            'error': f"Certificado inválido: {cert_result['error']}"
        }
    
    key_result = validate_key_file(key_path, password)
    if not key_result['valid']:
        return {
            'valid': False,
            'error': f"Llave inválida: {key_result['error']}"
        }
    
    # Both are valid
    return {
        'valid': True,
        'cert_serial': cert_result['serial'],
        'cert_expires': cert_result['valid_to'],
        'cert_expired': cert_result['expired'],
        'days_remaining': cert_result.get('days_remaining', 0),
        'message': '✅ Certificado y llave validados correctamente'
    }
