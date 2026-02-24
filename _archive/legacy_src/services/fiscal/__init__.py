"""
Fiscal Service Module
Migrated from app/fiscal/ to src/services/fiscal/
"""

# Importar submódulos para compatibilidad
from . import constants
from . import utils
from . import error_translator
from . import timezone_handler
from . import crypto_bridge
from . import rfc_validator
from . import sat_catalog
from . import sat_catalog_full
from . import xml_ingestor
from . import csd_vault
from . import pdf_generator
from . import email_service
from . import facturapi_connector
from . import signature
from . import pac_connector

# Re-exportar clases principales
from .cerebro_contable import CerebroContable
from .cfdi_builder import CFDIBuilder
from .cfdi_service import CFDIService
from .cfdi_sync_service import CFDISyncService
from .fiscal_dashboard import FiscalDashboard
from .global_invoicing import GlobalInvoicingService
from .legal_documents import LegalDocumentGenerator
from .materiality_engine import MaterialityEngine
from .resico_monitor import RESICOMonitor
from .returns_engine import ReturnsEngine
from .self_consumption import SelfConsumptionEngine
from .shadow_inventory import ShadowInventory
from .smart_variance import SmartVarianceEngine
from .wealth_dashboard import WealthDashboard
from .xml_ingestor import XMLIngestor
from .facturapi_connector import Facturapi

__all__ = [
    # Clases principales
    'CFDIBuilder',
    'CFDIService',
    'CFDISyncService',
    'GlobalInvoicingService',
    'XMLIngestor',
    'FiscalDashboard',
    'CerebroContable',
    'SmartVarianceEngine',
    'RESICOMonitor',
    'MaterialityEngine',
    'LegalDocumentGenerator',
    'ReturnsEngine',
    'SelfConsumptionEngine',
    'ShadowInventory',
    'WealthDashboard',
    'Facturapi',  # Clase principal de facturapi_connector
    # Submódulos para acceso directo
    'constants',
    'utils',
    'error_translator',
    'timezone_handler',
    'crypto_bridge',
    'rfc_validator',
    'sat_catalog',
    'sat_catalog_full',
    'xml_ingestor',
    'csd_vault',
    'pdf_generator',
    'email_service',
    'facturapi_connector',
    'signature',
    'pac_connector',
]
