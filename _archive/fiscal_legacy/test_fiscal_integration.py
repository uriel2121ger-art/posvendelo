import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_fiscal_imports():
    """Verify that all fiscal files can be imported without NameErrors or ImportErrors"""
    from modules.fiscal.cfdi_builder import CFDIBuilder
    from modules.fiscal.facturapi_connector import Facturapi
    from modules.fiscal.pac_connector import PACConnector
    from modules.fiscal.cfdi_service import CFDIService
    from modules.fiscal.global_invoicing import GlobalInvoicingService
    from modules.fiscal.crypto_bridge import CryptoBridge
    from modules.fiscal.fiscal_dashboard import FiscalDashboard
    from modules.fiscal.sat_catalog_full import SATCatalogManager
    from modules.fiscal.cfdi_sync_service import CFDISyncService
    from modules.fiscal.rfc_validator import RFCValidator
    from modules.fiscal.signature import sign_cfdi_xml
    
    assert True

@pytest.mark.asyncio
async def test_facturapi_instantiation():
    """Verify that FacturAPI connector can be instantiated"""
    from modules.fiscal.facturapi_connector import Facturapi
    
    client = Facturapi("sk_test_fake1234")
    assert client.mode == "test"
    
@pytest.mark.asyncio
async def test_cfdi_builder_instantiation():
    """Verify that CFDIBuilder can be instantiated"""
    from modules.fiscal.cfdi_builder import CFDIBuilder
    
    config = {
        'rfc_emisor': 'XAXX010101000',
        'nombre_emisor': 'EMPRESA DE PRUEBA',
        'regimen_fiscal': '601',
        'codigo_postal': '01000'
    }
    builder = CFDIBuilder(config)
    assert builder.config['rfc_emisor'] == 'XAXX010101000'
