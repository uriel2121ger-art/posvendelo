"""
TITAN POS - Fiscal Module

Bounded context for CFDI 4.0 / SAT compliance:
- CFDI building and signing
- PAC connector (Facturapi)
- Invoice generation (global, individual)
- Credit notes
- Payment complements
- RFC validation
- SAT catalogs

Public API:
    - CfdiBuilder: CFDI XML construction
    - CfdiService: CFDI orchestration
    - FacurapiConnector: PAC integration
    - RfcValidator: RFC validation
"""

from modules.fiscal.cfdi_builder import CfdiBuilder
from modules.fiscal.cfdi_service import CfdiService
from modules.fiscal.facturapi_connector import FacturapiConnector
from modules.fiscal.rfc_validator import RfcValidator

__all__ = [
    "CfdiBuilder",
    "CfdiService",
    "FacturapiConnector",
    "RfcValidator",
]
