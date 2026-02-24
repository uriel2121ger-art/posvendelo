"""
⚠️ DEPRECATED MODULE ⚠️

This module has been migrated to 'src.services.fiscal'.
This shim provides backward compatibility.

Migration guide:
    OLD: from app.fiscal import CFDIService
    NEW: from src.services.fiscal import CFDIService

This compatibility layer will be removed in v3.0.
"""

import warnings

# Emitir warning en primera importación
warnings.warn(
    "app.fiscal is deprecated. Use src.services.fiscal instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-exportar desde nueva ubicación
from src.services.fiscal import (
    CFDIService,
    CFDIBuilder,
    CFDISyncService,
    FiscalDashboard,
    GlobalInvoicingService,
    XMLIngestor,
    CerebroContable,
    SmartVarianceEngine,
    RESICOMonitor,
    MaterialityEngine,
    LegalDocumentGenerator,
    ReturnsEngine,
    SelfConsumptionEngine,
    ShadowInventory,
    WealthDashboard,
)

# Re-exportar Facturapi desde facturapi_connector
from src.services.fiscal.facturapi_connector import Facturapi

# Re-exportar submódulos para acceso directo
from src.services.fiscal import (
    constants,
    utils,
    error_translator,
    timezone_handler,
    crypto_bridge,
    rfc_validator,
    sat_catalog,
    sat_catalog_full,
    xml_ingestor,
    csd_vault,
    pdf_generator,
    email_service,
    facturapi_connector,
    signature,
    pac_connector,
)

# Mantener __all__ para compatibilidad
__all__ = [
    'CFDIService',
    'CFDIBuilder',
    'CFDISyncService',
    'FiscalDashboard',
    'GlobalInvoicingService',
    'XMLIngestor',
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
    # Submódulos
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
