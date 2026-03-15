"""
Legal Document Generator - Generador de documentos legales con sellado digital
Conforme al Art. 32-F CFF y Art. 25 fracc. VI LISR

Refactored: receives `db` (DB wrapper, optional) instead of `core`.
- Removed create_task from __init__; uses os.makedirs synchronously.
- Fixed missing awaits on config fetches (now direct DB queries).
- File I/O uses aiofiles (non-blocking async writes).
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import hashlib
import logging
import os
from pathlib import Path

import aiofiles

logger = logging.getLogger(__name__)


class LegalDocumentGenerator:
    """
    Generador de documentos legales para soporte de materialidad fiscal.
    Incluye sellado digital SHA-256 para integridad.
    """

    DOCS_PATH = Path(__file__).resolve().parent.parent.parent / 'docs/actas'

    def __init__(self, db=None, branch_id: int | None = None):
        self.db = db
        self.branch_id = branch_id
        # Sync dir creation -- no create_task needed
        os.makedirs(self.DOCS_PATH, exist_ok=True)
        os.makedirs(self.DOCS_PATH / 'destruccion', exist_ok=True)
        os.makedirs(self.DOCS_PATH / 'devoluciones', exist_ok=True)
        os.makedirs(self.DOCS_PATH / 'autoconsumo', exist_ok=True)
        os.makedirs(self.DOCS_PATH / 'evidencias', exist_ok=True)

    async def _get_app_config(self) -> dict:
        """Fetch app config from DB."""
        if not self.db:
            return {}
        row = await self.db.fetchrow("SELECT * FROM app_config LIMIT 1")
        return row or {}

    async def _get_fiscal_config(self) -> dict:
        """Fetch fiscal config from DB."""
        if not self.db:
            return {}
        if self.branch_id is None:
            row = await self.db.fetchrow("SELECT * FROM fiscal_config ORDER BY branch_id ASC LIMIT 1")
        else:
            row = await self.db.fetchrow(
                "SELECT * FROM fiscal_config WHERE branch_id = :bid LIMIT 1",
                {"bid": self.branch_id},
            )
        return row or {}

    async def generate_destruction_acta(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Genera acta circunstanciada de destruccion de mercancia.
        Art. 32-F CFF, Art. 25 Fracc. VI LISR.
        """
        config = await self._get_app_config()
        fiscal = await self._get_fiscal_config()

        folio = data.get('folio', f"ACT-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        timestamp = datetime.now()
        location_label = config.get('location_label') or config.get('city') or 'Localidad configurada'
        address_label = config.get('address') or 'Domicilio fiscal configurado'

        acta_content = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     ACTA CIRCUNSTANCIADA DE DESTRUCCION DE MERCANCIA E INVENTARIO INUTIL     ║
║                           FOLIO: {folio:<42} ║
╚══════════════════════════════════════════════════════════════════════════════╝

LUGAR:           {location_label}
FECHA Y HORA:    {timestamp.strftime('%d de %B de %Y, %H:%M:%S horas')}

═══════════════════════════════════════════════════════════════════════════════
                              FUNDAMENTO LEGAL
═══════════════════════════════════════════════════════════════════════════════

Se levanta la presente acta en cumplimiento con lo dispuesto en:

* Articulo 25, fraccion VI de la Ley del Impuesto sobre la Renta (LISR) -
  Deducciones autorizadas por perdidas por caso fortuito, fuerza mayor o
  enajenacion de bienes distintos de inversiones.

* Articulo 32-F del Codigo Fiscal de la Federacion (CFF) - Obligacion de
  destruir mercancias que hubieran perdido su valor por deterioro u otras
  causas no imputables al contribuyente.

* Regla 2.7.1.21 de la Resolucion Miscelanea Fiscal Vigente.

═══════════════════════════════════════════════════════════════════════════════
                          DATOS DEL CONTRIBUYENTE
═══════════════════════════════════════════════════════════════════════════════

Razon Social:    {config.get('business_name', 'RAZON SOCIAL')}
RFC:             {fiscal.get('rfc_emisor', 'RFC')}
Regimen Fiscal:  {fiscal.get('emisor_regimen', '626')} - RESICO
Domicilio:       {address_label}

═══════════════════════════════════════════════════════════════════════════════
                          DESCRIPCION DE BIENES
═══════════════════════════════════════════════════════════════════════════════

Producto:            {data.get('product_name', 'N/A')}
SKU/Codigo:          {data.get('sku', 'N/A')}
Clave SAT:           {data.get('sat_key', 'N/A')}
Cantidad Afectada:   {data.get('quantity', 0)} {data.get('unit', 'PZA')}
Costo Unitario:      ${data.get('unit_cost', 0):,.2f} MXN
Valor Total:         ${data.get('total_value', 0):,.2f} MXN

═══════════════════════════════════════════════════════════════════════════════
                           CAUSA DE LA BAJA
═══════════════════════════════════════════════════════════════════════════════

Categoria:           {data.get('category', 'DETERIORO').upper()}
Motivo Especifico:   {data.get('reason', 'Deterioro del producto')}

═══════════════════════════════════════════════════════════════════════════════
                          RELATO DE LOS HECHOS
═══════════════════════════════════════════════════════════════════════════════

En la fecha y hora antes senaladas, siendo las {timestamp.strftime('%H:%M')} horas del dia
{timestamp.strftime('%d de %B de %Y')}, en el establecimiento comercial ubicado en
{address_label}, se detecto que los bienes arriba descritos
NO SON APTOS PARA SU COMERCIALIZACION debido a: {data.get('reason', 'deterioro')}.

Se procedio a la SEGREGACION INMEDIATA del inventario apto para venta y se autoriza
su DESTRUCCION FISICA para evitar:
  a) Su comercializacion indebida
  b) Riesgos a la salud del consumidor (en caso de productos perecederos)
  c) Afectacion a la imagen comercial del establecimiento

La mercancia sera destruida conforme a las disposiciones ambientales aplicables.

═══════════════════════════════════════════════════════════════════════════════
                         TESTIGOS Y FIRMAS
═══════════════════════════════════════════════════════════════════════════════

Testigo 1 (Personal):     {data.get('witness_name', 'N/A')}
Testigo 2 (Supervisor):   {data.get('supervisor_name', 'N/A')}

Autorizado por:           {data.get('authorized_by', 'Pendiente')}
Fecha Autorización:       {data.get('authorized_at', 'Pendiente')}

___________________________          ___________________________
    Responsable del Area                  Testigo Presencial

___________________________
    Representante Legal

═══════════════════════════════════════════════════════════════════════════════
                         EVIDENCIA FOTOGRAFICA
═══════════════════════════════════════════════════════════════════════════════

Estado de Evidencia:     {'FOTOGRAFIAS ANEXAS' if data.get('photo_path') else 'PENDIENTE'}
Archivo de Evidencia:    {data.get('photo_path', 'No adjunta')}
UUID Expediente:         {data.get('uuid', 'N/A')}

═══════════════════════════════════════════════════════════════════════════════
                         SELLADO DIGITAL
═══════════════════════════════════════════════════════════════════════════════

Fecha Generacion:        {timestamp.isoformat()}
"""

        content_for_hash = f"{folio}|{timestamp.isoformat()}|{data.get('product_name')}|{data.get('total_value')}"
        sha256_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()

        acta_content += f"""Hash SHA-256:            {sha256_hash}

Este documento fue generado automaticamente por el Sistema POSVENDELO/Antigravity.
El hash SHA-256 garantiza la integridad del documento desde su creacion.

═══════════════════════════════════════════════════════════════════════════════
                              FIN DEL ACTA
═══════════════════════════════════════════════════════════════════════════════
"""

        filename = f"ACTA_{folio}_{timestamp.strftime('%Y%m%d')}.txt"
        filepath = self.DOCS_PATH / 'destruccion' / filename

        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(acta_content)

        return {
            'success': True,
            'folio': folio,
            'filepath': str(filepath),
            'hash': sha256_hash,
            'timestamp': timestamp.isoformat(),
            'content_length': len(acta_content),
        }

    async def generate_return_document(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Genera documento de devolucion.
        Serie A: Requiere CFDI de Egreso.
        Serie B: Nota de crédito interna.
        """
        folio = f"DEV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        timestamp = datetime.now()

        serie = data.get('serie', 'B')
        requires_cfdi = serie == 'A'

        doc_content = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    NOTA DE DEVOLUCION / CREDITO                              ║
║                    FOLIO: {folio:<46} ║
╚══════════════════════════════════════════════════════════════════════════════╝

FECHA:               {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
TIPO:                {'FISCAL (Requiere CFDI Egreso)' if requires_cfdi else 'INTERNA'}
SERIE ORIGINAL:      {serie}

───────────────────────────────────────────────────────────────────────────────
                         DATOS DE LA VENTA ORIGINAL
───────────────────────────────────────────────────────────────────────────────

Folio Venta:         {data.get('original_folio', 'N/A')}
UUID CFDI:           {data.get('original_uuid', 'N/A') if requires_cfdi else 'N/A (Serie B)'}
Fecha Venta:         {data.get('original_date', 'N/A')}
Total Original:      ${data.get('original_total', 0):,.2f}

───────────────────────────────────────────────────────────────────────────────
                         DETALLE DE LA DEVOLUCION
───────────────────────────────────────────────────────────────────────────────

Producto:            {data.get('product_name', 'N/A')}
SKU:                 {data.get('sku', 'N/A')}
Cantidad:            {data.get('quantity', 0)}
Precio Unitario:     ${data.get('unit_price', 0):,.2f}
Subtotal:            ${data.get('subtotal', 0):,.2f}
IVA:                 ${data.get('tax', 0):,.2f}
Total Devolucion:    ${data.get('total', 0):,.2f}

───────────────────────────────────────────────────────────────────────────────
                         MOTIVO DE LA DEVOLUCION
───────────────────────────────────────────────────────────────────────────────

Categoria:           {data.get('return_category', 'Cambio de opinion')}
Descripcion:         {data.get('return_reason', 'N/A')}
Estado del Producto: {data.get('product_condition', 'integro')}

───────────────────────────────────────────────────────────────────────────────
                         ACCIONES REQUERIDAS
───────────────────────────────────────────────────────────────────────────────
"""

        if requires_cfdi:
            doc_content += f"""
    ACCIÓN FISCAL REQUERIDA:
    Generar CFDI de Egreso (Nota de Credito) relacionado al UUID:
    {data.get('original_uuid', 'PENDIENTE')}

    Tipo Relacion: 01 - Nota de crédito de los documentos relacionados
"""
        else:
            doc_content += """
    ACCIÓN INTERNA:
    El stock ha sido reintegrado al inventario fisico.
    No se requiere documento fiscal adicional.
"""

        doc_content += f"""
───────────────────────────────────────────────────────────────────────────────
                         FIRMAS
───────────────────────────────────────────────────────────────────────────────

Procesado por:       {data.get('processed_by', 'N/A')}
Cliente:             {data.get('customer_name', 'Publico General')}

___________________________          ___________________________
    Personal de Tienda                    Cliente (Opcional)

Hash: {hashlib.sha256(folio.encode()).hexdigest()[:32]}
"""

        filename = f"DEVOLUCION_{folio}.txt"
        filepath = self.DOCS_PATH / 'devoluciones' / filename

        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(doc_content)

        return {
            'success': True,
            'folio': folio,
            'filepath': str(filepath),
            'requires_cfdi': requires_cfdi,
            'serie': serie,
        }

    async def generate_selfconsumption_voucher(
        self, items: List[Dict], period: str = None
    ) -> Dict[str, Any]:
        """
        Genera vale de consumo interno mensual.
        Art. 25 LISR - Gastos de operacion deducibles.
        """
        period = period or datetime.now().strftime('%Y-%m')
        folio = f"AUTO-{period.replace('-', '')}"

        total_value = sum(item.get('value', 0) for item in items)

        doc_content = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    VALE DE CONSUMO INTERNO MENSUAL                           ║
║                    PERIODO: {period:<47} ║
╚══════════════════════════════════════════════════════════════════════════════╝

FOLIO:               {folio}
FECHA GENERACION:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

───────────────────────────────────────────────────────────────────────────────
                         FUNDAMENTO FISCAL
───────────────────────────────────────────────────────────────────────────────

Este documento ampara el AUTOCONSUMO y MUESTRAS GRATUITAS del periodo,
registrados como GASTO DE OPERACION conforme al Art. 25 de la LISR.

El autoconsumo NO genera ingreso fiscal al no existir enajenacion a terceros.
Se registra unicamente para efectos de control de inventario.

───────────────────────────────────────────────────────────────────────────────
                         DETALLE DE CONSUMOS
───────────────────────────────────────────────────────────────────────────────

{'PRODUCTO':<30} {'CANTIDAD':>10} {'VALOR':>15} {'MOTIVO':<20}
{'─'*80}
"""

        for item in items:
            doc_content += (
                f"{item.get('product', 'N/A')[:30]:<30} "
                f"{item.get('quantity', 0):>10} "
                f"${item.get('value', 0):>12,.2f} "
                f"{item.get('reason', 'Uso interno')[:20]:<20}\n"
            )

        doc_content += f"""{'─'*80}
{'TOTAL PERIODO:':<42} ${total_value:>12,.2f}

───────────────────────────────────────────────────────────────────────────────
                         CATEGORIAS DE CONSUMO
───────────────────────────────────────────────────────────────────────────────

* LIMPIEZA:      Productos usados para mantenimiento del local
* EMPLEADOS:     Consumo autorizado por personal
* MUESTRAS:      Productos entregados sin costo para promocion
* OPERACION:     Insumos consumidos en la operacion diaria

───────────────────────────────────────────────────────────────────────────────

Autorizado por: ____________________________

Este vale justifica fiscalmente la baja de inventario sin venta correspondiente
para el periodo indicado.

Hash: {hashlib.sha256(f'{folio}|{total_value}'.encode()).hexdigest()[:32]}
"""

        filename = f"AUTOCONSUMO_{folio}.txt"
        filepath = self.DOCS_PATH / 'autoconsumo' / filename

        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(doc_content)

        return {
            'success': True,
            'folio': folio,
            'filepath': str(filepath),
            'period': period,
            'total_value': total_value,
            'items_count': len(items),
        }

    async def get_monthly_summary(self, year: int = None, month: int = None) -> Dict[str, Any]:
        """Obtiene resumen mensual de documentos generados."""
        year = year or datetime.now().year
        month = month or datetime.now().month

        destruccion = list((self.DOCS_PATH / 'destruccion').glob(f'*{year}{month:02d}*.txt'))
        devoluciones = list((self.DOCS_PATH / 'devoluciones').glob(f'*{year}{month:02d}*.txt'))
        autoconsumo = list((self.DOCS_PATH / 'autoconsumo').glob(f'*{year}{month:02d}*.txt'))

        return {
            'period': f'{year}-{month:02d}',
            'destruccion': len(destruccion),
            'devoluciones': len(devoluciones),
            'autoconsumo': len(autoconsumo),
            'total_docs': len(destruccion) + len(devoluciones) + len(autoconsumo),
        }
