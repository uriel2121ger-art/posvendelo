"""
CFDI Utilities
Shared helper functions for CFDI module
"""

from typing import Any, Dict, Optional
from datetime import datetime, timezone
import logging
from pathlib import Path
import re

from modules.fiscal.constants import (
    EMAIL_PATTERN,
    ERROR_MESSAGES,
    RFC_PATTERN_FISICA,
    RFC_PATTERN_MORAL,
)

logger = logging.getLogger(__name__)

# Local constant for data directory (backend/data/)
DATA_DIR = Path(__file__).parent.parent.parent / "data"

def validate_fiscal_config(fiscal_config: Dict[str, Any]) -> None:
    """
    Validate that fiscal configuration is complete and valid.
    
    Args:
        fiscal_config: Fiscal configuration dictionary
        
    Raises:
        ValueError: If configuration is invalid or incomplete
    """
    if not fiscal_config:
        raise ValueError(ERROR_MESSAGES['NO_FISCAL_CONFIG'])
    
    required_fields = [
        'rfc_emisor',
        'razon_social_emisor',
        'regimen_fiscal',
        'lugar_expedicion'
    ]
    
    for field in required_fields:
        if not fiscal_config.get(field):
            raise ValueError(f"Missing required fiscal config field: {field}")
    
    # Validate RFC format
    rfc = fiscal_config['rfc_emisor']
    if not validate_rfc(rfc):
        raise ValueError(f"Invalid RFC format: {rfc}")
    
    # Validate certificates exist
    cert_path = fiscal_config.get('csd_cert_path', '')
    key_path = fiscal_config.get('csd_key_path', '')
    
    if cert_path and not Path(cert_path).exists():
        raise FileNotFoundError(ERROR_MESSAGES['CERT_NOT_FOUND'])
    
    if key_path and not Path(key_path).exists():
        raise FileNotFoundError(ERROR_MESSAGES['KEY_NOT_FOUND'])

def validate_rfc(rfc: str) -> bool:
    """
    Validate RFC format.
    
    Args:
        rfc: RFC string to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not rfc:
        return False
    
    rfc = rfc.upper().strip()
    
    # Check for moral (12 chars) or física (13 chars)
    return (
        bool(re.match(RFC_PATTERN_MORAL, rfc)) or
        bool(re.match(RFC_PATTERN_FISICA, rfc))
    )

def validate_email(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email: Email string to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not email:
        return False
    
    return bool(re.match(EMAIL_PATTERN, email.strip()))

def save_xml_file(uuid: str, xml_content: str, subdirectory: Optional[str] = None) -> str:
    """
    Save XML to standard CFDI directory.
    
    Args:
        uuid: UUID for filename
        xml_content: XML content to save
        subdirectory: Optional subdirectory within cfdis/
        
    Returns:
        Full path to saved file
    """
    base_dir = DATA_DIR / "cfdis"

    if subdirectory:
        base_dir = base_dir / subdirectory

    base_dir.mkdir(exist_ok=True, parents=True)

    xml_path = base_dir / f"{uuid}.xml"
    with open(xml_path, 'w', encoding='utf-8') as f:
        f.write(xml_content)
    
    logger.info(f"XML saved: {xml_path}")
    return str(xml_path)

def format_datetime_cfdi(dt: Optional[datetime] = None) -> str:
    """
    Format datetime for CFDI (ISO 8601 without microseconds).
    
    Args:
        dt: Datetime object (defaults to now)
        
    Returns:
        Formatted datetime string
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    
    return dt.strftime('%Y-%m-%dT%H:%M:%S')

def format_currency(amount: float, decimals: int = 2) -> str:
    """
    Format amount for CFDI (always 2 decimals).
    
    Args:
        amount: Amount to format
        decimals: Number of decimal places
        
    Returns:
        Formatted string
    """
    return f"{amount:.{decimals}f}"

def parse_xml_safe(xml_string: str):
    """
    Safely parse XML string.
    
    Args:
        xml_string: XML string to parse
        
    Returns:
        Parsed XML element or None
    """
    try:
        from lxml import etree
        # SECURITY: Use secure parser to prevent XXE attacks
        parser = etree.XMLParser(
            resolve_entities=False,  # Disable entity resolution
            no_network=True,         # Disable network access
            dtd_validation=False,    # Don't validate DTD
            load_dtd=False,          # Don't load external DTD
        )
        return etree.fromstring(xml_string.encode('utf-8'), parser=parser)
    except Exception as e:
        logger.error(f"Error parsing XML: {e}")
        return None

def extract_uuid_from_xml(xml_string: str) -> Optional[str]:
    """
    Extract UUID from timbrado XML.
    
    Args:
        xml_string: Timbrado XML content
        
    Returns:
        UUID string or None
    """
    root = parse_xml_safe(xml_string)
    if root is None:
        return None
    
    # Look for TimbreFiscalDigital complement
    tfd_ns = "http://www.sat.gob.mx/TimbreFiscalDigital"
    tfd = root.find(f".//{{{tfd_ns}}}TimbreFiscalDigital")
    
    if tfd is not None:
        return tfd.get('UUID')
    
    return None

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to remove invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove invalid chars for filenames (including ? for Windows compatibility)
    invalid_chars = '<>:"/\\|%*?'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    return filename

def calculate_iva(subtotal: float, rate: float = 0.16) -> float:
    """
    Calculate IVA amount using Decimal for precision.

    Args:
        subtotal: Subtotal amount
        rate: IVA rate (default 16%)

    Returns:
        IVA amount
    """
    from decimal import Decimal, ROUND_HALF_UP
    result = (Decimal(str(subtotal)) * Decimal(str(rate))).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    return float(result)

def truncate_string(text: str, max_length: int, suffix: str = '...') -> str:
    """
    Truncate string to max length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def get_cfdi_directory(subdirectory: Optional[str] = None) -> Path:
    """
    Get CFDI storage directory, creating if needed.
    
    Args:
        subdirectory: Optional subdirectory name
        
    Returns:
        Path object
    """
    base_dir = DATA_DIR / "cfdis"

    if subdirectory:
        base_dir = base_dir / subdirectory

    base_dir.mkdir(exist_ok=True, parents=True)
    return base_dir

def log_cfdi_event(event_type: str, uuid: str, details: str = ""):
    """
    Log CFDI-related event.
    
    Args:
        event_type: Type of event (generated, cancelled, etc)
        uuid: CFDI UUID
        details: Additional details
    """
    logger.info(f"CFDI {event_type}: {uuid} {details}")
