"""
Digital Signature Module for CFDI
Signs XML documents using CSD certificates from SAT
"""

from typing import Any, Dict, Optional
import base64
import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class CFDISignature:
    """Handles digital signature of CFDI XML documents."""
    
    def __init__(self, cert_path: str, key_path: str, key_password: str):
        """
        Initialize signature handler with CSD certificates.
        
        Args:
            cert_path: Path to .cer file
            key_path: Path to .key file
            key_password: Password for private key
        """
        self.cert_path = Path(cert_path)
        self.key_path = Path(key_path)
        self.key_password = key_password
        self._certificate = None
        self._private_key = None
    
    def load_certificates(self):
        """Load and validate CSD certificates."""
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.serialization import load_der_private_key

        # Load certificate
        with open(self.cert_path, 'rb') as f:
            cert_data = f.read()
        self._certificate = x509.load_der_x509_certificate(cert_data, default_backend())
        
        # Load private key
        with open(self.key_path, 'rb') as f:
            key_data = f.read()
        self._private_key = load_der_private_key(
            key_data,
            password=self.key_password.encode('utf-8'),
            backend=default_backend()
        )
        
        logger.info("CSD certificates loaded successfully")
    
    def get_certificate_number(self) -> str:
        """Get certificate serial number (No. Certificado)."""
        if not self._certificate:
            self.load_certificates()
        
        # Convert to hex string without leading zeros
        serial_hex = format(self._certificate.serial_number, 'x')
        # Remove leading zeros and return as even-length string
        serial_hex = serial_hex.lstrip('0') or '0'
        if len(serial_hex) % 2:
            serial_hex = '0' + serial_hex
        return serial_hex
    
    def get_certificate_der_base64(self) -> str:
        """Get base64-encoded certificate in DER format."""
        if not self._certificate:
            self.load_certificates()
        
        from cryptography.hazmat.primitives import serialization
        cert_der = self._certificate.public_bytes(serialization.Encoding.DER)
        return base64.b64encode(cert_der).decode('ascii')
    
    def sign_xml(self, xml_string: str) -> Dict[str, str]:
        """
        Sign XML document and return signature components.
        
        Args:
            xml_string: XML string to sign
            
        Returns:
            Dictionary with:
            - sello: Digital signature (base64)
            - noCertificado: Certificate number
            - certificado: Certificate in base64
        """
        if not self._private_key:
            self.load_certificates()
        
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from lxml import etree

        # FIX 2026-02-01: Use secure XML parser to prevent XXE attacks
        parser = etree.XMLParser(
            resolve_entities=False,  # Disable entity resolution
            no_network=True,         # Disable network access
            dtd_validation=False,    # Disable DTD validation
            load_dtd=False           # Do not load DTD
        )
        xml_tree = etree.fromstring(xml_string.encode('utf-8'), parser=parser)
        
        # Generate "cadena original" (original string)
        cadena_original = self._generate_cadena_original(xml_tree)
        
        # Sign cadena original with private key
        signature_bytes = self._private_key.sign(
            cadena_original.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        
        # Encode signature
        sello = base64.b64encode(signature_bytes).decode('ascii')
        
        return {
            'sello': sello,
            'noCertificado': self.get_certificate_number(),
            'certificado': self.get_certificate_der_base64()
        }
    
    def add_signature_to_xml(self, xml_string: str) -> str:
        """
        Add signature elements to XML.
        
        Args:
            xml_string: Unsigned XML
            
        Returns:
            Signed XML string
        """
        from lxml import etree

        # Get signature components
        signature_data = self.sign_xml(xml_string)

        # FIX 2026-02-01: Use secure XML parser to prevent XXE attacks
        parser = etree.XMLParser(
            resolve_entities=False,
            no_network=True,
            dtd_validation=False,
            load_dtd=False
        )
        xml_tree = etree.fromstring(xml_string.encode('utf-8'), parser=parser)
        
        # Add signature attributes to Comprobante
        xml_tree.set('NoCertificado', signature_data['noCertificado'])
        xml_tree.set('Certificado', signature_data['certificado'])
        xml_tree.set('Sello', signature_data['sello'])
        
        # Convert back to string
        signed_xml = etree.tostring(
            xml_tree,
            pretty_print=True,
            xml_declaration=True,
            encoding='UTF-8'
        )
        
        return signed_xml.decode('utf-8')
    
    def _generate_cadena_original(self, xml_tree) -> str:
        """
        Generate 'cadena original' from XML using XSLT transformation.
        
        For now, using simplified version. In production, should use
        official SAT XSLT: cadenaoriginal_4_0.xslt
        """
        from lxml import etree

        # Simplified cadena original (concatenate key elements)
        # In production, use proper XSLT transformation
        
        def get_attr(elem, attr, default=''):
            return elem.get(attr, default)
        
        parts = []
        
        # Comprobante attributes
        parts.append(f"||")
        parts.append(f"{get_attr(xml_tree, 'Version')}|")
        parts.append(f"{get_attr(xml_tree, 'Serie')}|")
        parts.append(f"{get_attr(xml_tree, 'Folio')}|")
        parts.append(f"{get_attr(xml_tree, 'Fecha')}|")
        parts.append(f"{get_attr(xml_tree, 'FormaPago')}|")
        parts.append(f"{get_attr(xml_tree, 'SubTotal')}|")
        parts.append(f"{get_attr(xml_tree, 'Total')}|")
        
        # This is a  simplified version. Production should use:
        # XSLT from: http://www.sat.gob.mx/sitio_internet/cfd/4/cadenaoriginal_4_0.xslt
        
        cadena = ''.join(parts)
        logger.debug(f"Cadena original (simplified): {cadena}")
        
        return cadena

def sign_cfdi_xml(xml_string: str, fiscal_config: Dict[str, Any]) -> str:
    """
    Convenience function to sign CFDI XML.
    
    Args:
        xml_string: Unsigned XML
        fiscal_config: Configuration with cert paths and password
        
    Returns:
        Signed XML string
    """
    signer = CFDISignature(
        cert_path=fiscal_config['csd_cert_path'],
        key_path=fiscal_config['csd_key_path'],
        key_password=fiscal_config['csd_key_password']
    )
    
    return signer.add_signature_to_xml(xml_string)
