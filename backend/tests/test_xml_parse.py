"""
Test Parsear XML (CFDI 4.0) - Verifica que el ingestor extrae datos correctamente.

Requisito: defusedxml instalado (pip install -r requirements.txt).
Si falta, el test se omite.
"""
import os
import tempfile
import pytest

try:
    import defusedxml.ElementTree  # noqa: F401
    DEFUSEDXML_AVAILABLE = True
except ImportError:
    DEFUSEDXML_AVAILABLE = False

# XML mínimo CFDI 4.0 (namespace oficial SAT) para pruebas
SAMPLE_CFDI_XML = """<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
  xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
  Fecha="2025-01-15T12:00:00" TipoDeComprobante="I" SubTotal="100.00" Total="116.00" Moneda="MXN">
  <cfdi:Emisor Rfc="PRO010101XXX" Nombre="PROVEEDOR SA" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="NOV800101XXX" Nombre="NOVEDADES LUPITA" UsoCFDI="G03"/>
  <cfdi:Conceptos>
    <cfdi:Concepto ClaveProdServ="50171600" ClaveUnidad="H87" Cantidad="2" ValorUnitario="50.00" Importe="100.00" Descripcion="Producto prueba"/>
  </cfdi:Conceptos>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital UUID="a1b2c3d4-e5f6-7890-abcd-ef1234567890"/>
  </cfdi:Complemento>
</cfdi:Comprobante>
"""


@pytest.mark.skipif(not DEFUSEDXML_AVAILABLE, reason="defusedxml no instalado; ejecuta: pip install -r requirements.txt")
def test_xml_ingestor_parse_cfdi():
    """Parsear XML CFDI 4.0 extrae comprobante, emisor, receptor y conceptos."""
    from modules.fiscal.xml_ingestor import XMLIngestor

    ingestor = XMLIngestor(db=None)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_CFDI_XML)
        path = f.name
    try:
        data = ingestor.parse_cfdi(path)
        assert data.get("success") is True
        comp = data.get("comprobante", {})
        assert comp.get("fecha") == "2025-01-15T12:00:00"
        assert float(comp.get("total", 0)) == 116.00
        assert comp.get("uuid") == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        emisor = data.get("emisor", {})
        assert emisor.get("rfc") == "PRO010101XXX"
        receptor = data.get("receptor", {})
        assert receptor.get("nombre") == "NOVEDADES LUPITA"
        conceptos = data.get("conceptos", [])
        assert len(conceptos) == 1
        assert conceptos[0]["descripcion"] == "Producto prueba"
        assert int(conceptos[0]["cantidad"]) == 2
        assert float(conceptos[0]["valor_unitario"]) == 50.00
    finally:
        os.unlink(path)


@pytest.mark.skipif(not DEFUSEDXML_AVAILABLE, reason="defusedxml no instalado; ejecuta: pip install -r requirements.txt")
def test_xml_ingestor_invalid_xml_returns_error():
    """XML inválido o vacío devuelve success=False y mensaje de error."""
    from modules.fiscal.xml_ingestor import XMLIngestor

    ingestor = XMLIngestor(db=None)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as f:
        f.write("<root><broken")
        path = f.name
    try:
        data = ingestor.parse_cfdi(path)
        assert data.get("success") is False
        assert "error" in data
        assert len(data.get("error", "")) > 0
    finally:
        os.unlink(path)


# ─── Integración: POST /api/v1/fiscal/xml/parse ───────────────────────────────

from conftest import auth_header


@pytest.mark.asyncio
async def test_fiscal_xml_parse_403_cashier(client, cashier_token):
    """Cajero sin permisos recibe 403."""
    r = await client.post(
        "/api/v1/fiscal/xml/parse",
        headers=auth_header(cashier_token),
        files={"file": ("dummy.xml", b"<x/>", "application/xml")},
    )
    assert r.status_code == 403
    assert "permisos" in (r.json().get("detail") or "").lower()


@pytest.mark.asyncio
async def test_fiscal_xml_parse_400_wrong_extension(client, admin_token):
    """Archivo sin extensión .xml recibe 400."""
    r = await client.post(
        "/api/v1/fiscal/xml/parse",
        headers=auth_header(admin_token),
        files={"file": ("factura.pdf", b"not xml", "application/pdf")},
    )
    assert r.status_code == 400
    assert "xml" in (r.json().get("detail") or "").lower()


@pytest.mark.skipif(not DEFUSEDXML_AVAILABLE, reason="defusedxml no instalado; ejecuta: pip install -r requirements.txt")
@pytest.mark.asyncio
async def test_fiscal_xml_parse_200_ok(client, admin_token):
    """Admin con archivo CFDI 4.0 válido recibe 200 y datos parseados."""
    r = await client.post(
        "/api/v1/fiscal/xml/parse",
        headers=auth_header(admin_token),
        files={"file": ("cfdi.xml", SAMPLE_CFDI_XML.encode("utf-8"), "application/xml")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    data = body.get("data", {})
    assert "comprobante" in data
    assert data.get("comprobante", {}).get("uuid") == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    assert "conceptos" in data
    assert len(data.get("conceptos", [])) == 1
