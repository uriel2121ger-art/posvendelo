"""
CFDI Sync Service - Descarga y sincroniza CFDIs al servidor central

Descarga PDFs, XMLs y genera reportes CSV de todas las facturas
para respaldo centralizado en el servidor.

Refactored: receives `db` (DB wrapper) instead of `core`.
Uses :name params and db.fetch/db.fetchrow/db.execute.
"""

from typing import Any, Dict, List, Optional
import asyncio
import csv
from datetime import datetime, timedelta
import logging
from pathlib import Path
import aiofiles

logger = logging.getLogger(__name__)


class CFDISyncService:
    def __init__(self, db):
        self.db = db
        self._facturapi = None

    async def _init_config(self):
        cfg = await self.db.fetchrow(
            "SELECT * FROM app_config LIMIT 1"
        )
        cfg = cfg or {}
        self.sync_base_path = Path(cfg.get('cfdi_sync_path', '/var/posvendelo/cfdis'))
        self.nas_path = cfg.get('backup_nas_path', '')

    async def _get_facturapi(self):
        if self._facturapi is None:
            try:
                from modules.fiscal.cfdi_service import CFDIService
                service = CFDIService(self.db)
                self._facturapi = await service._get_facturapi()
            except Exception as e:
                logger.warning(f"Facturapi no disponible: {e}")
        return self._facturapi

    async def sync_cfdi(self, cfdi_id: int, facturapi_id: str) -> Dict[str, Any]:
        await self._init_config()
        facturapi = await self._get_facturapi()
        if not facturapi:
            return {'success': False, 'error': 'Facturapi no configurado'}

        try:
            cfdi = await self.db.fetchrow(
                "SELECT * FROM cfdis WHERE id = :cid", {"cid": cfdi_id}
            )
            if not cfdi:
                return {'success': False, 'error': f'CFDI {cfdi_id} no encontrado'}

            uuid = cfdi.get('uuid', 'unknown')
            fecha = cfdi.get('fecha_emision', datetime.now().isoformat())[:10]

            year, month = fecha[:4], fecha[5:7]
            cfdi_dir = self.sync_base_path / year / month
            await asyncio.to_thread(cfdi_dir.mkdir, parents=True, exist_ok=True)

            result = {'success': True, 'cfdi_id': cfdi_id, 'uuid': uuid, 'files': {}}

            try:
                pdf_content = await facturapi.invoices.download_pdf(facturapi_id)
                if pdf_content and isinstance(pdf_content, bytes):
                    pdf_path = cfdi_dir / f"{uuid}.pdf"
                    async with aiofiles.open(pdf_path, 'wb') as f:
                        await f.write(pdf_content)
                    result['files']['pdf'] = str(pdf_path)
                    logger.info(f"PDF guardado: {pdf_path}")
            except Exception as e:
                logger.warning(f"Error descargando PDF: {e}")
                result['files']['pdf_error'] = str(e)

            try:
                xml_content = await facturapi.invoices.download_xml(facturapi_id)
                if xml_content and isinstance(xml_content, str):
                    xml_path = cfdi_dir / f"{uuid}.xml"
                    async with aiofiles.open(xml_path, 'w', encoding='utf-8') as f:
                        await f.write(xml_content)
                    result['files']['xml'] = str(xml_path)
                    logger.info(f"XML guardado: {xml_path}")
            except Exception as e:
                logger.warning(f"Error descargando XML: {e}")
                result['files']['xml_error'] = str(e)

            await self.db.execute(
                """UPDATE cfdis
                   SET sync_status = 'synced', sync_date = :sdate,
                       pdf_path = :pdf, xml_path = :xml
                   WHERE id = :cid""",
                {
                    "sdate": datetime.now().isoformat(),
                    "pdf": result['files'].get('pdf', ''),
                    "xml": result['files'].get('xml', ''),
                    "cid": cfdi_id,
                },
            )

            if self.nas_path:
                await self._copy_to_nas(cfdi_dir, year, month)

            return result
        except Exception as e:
            logger.error(f"Error sincronizando CFDI {cfdi_id}: {e}")
            return {'success': False, 'error': str(e)}

    async def sync_pending_cfdis(self) -> Dict[str, Any]:
        pending = await self.db.fetch(
            """SELECT id, facturapi_id
               FROM cfdis
               WHERE facturapi_id IS NOT NULL AND facturapi_id != ''
                 AND (sync_status IS NULL OR sync_status != 'synced')
               ORDER BY id DESC LIMIT 100"""
        )

        results = {'total': len(pending), 'synced': 0, 'errors': 0, 'details': []}

        for cfdi in pending:
            result = await self.sync_cfdi(cfdi['id'], cfdi['facturapi_id'])
            if result.get('success'):
                results['synced'] += 1
            else:
                results['errors'] += 1
            results['details'].append(result)

        logger.info(f"Sincronizacion completa: {results['synced']}/{results['total']} CFDIs")
        return results

    async def generate_csv_report(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> str:
        await self._init_config()
        if not date_to:
            date_to = datetime.now().strftime('%Y-%m-%d')
        if not date_from:
            date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        cfdis = await self.db.fetch(
            """SELECT * FROM cfdis
               WHERE fecha_emision::date BETWEEN :d1::date AND :d2::date
               ORDER BY id
               LIMIT 10000""",
            {"d1": date_from, "d2": date_to},
        )

        if not output_path:
            reports_dir = self.sync_base_path / 'reportes'
            await asyncio.to_thread(reports_dir.mkdir, parents=True, exist_ok=True)
            output_path = reports_dir / f"cfdis_{date_from}_{date_to}.csv"
        else:
            output_path = Path(output_path)

        async with aiofiles.open(output_path, 'w', newline='', encoding='utf-8') as f:
            header = (
                'ID,UUID,Serie,Folio,Fecha Emision,RFC Receptor,Nombre Receptor,'
                'Uso CFDI,Subtotal,IVA,Total,Estado,Venta ID,Facturapi ID,PDF Path,XML Path\n'
            )
            await f.write(header)

            def escape(val):
                import re as _re
                s = str(val)
                # Strip non-printable control chars
                s = _re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', s)
                # Prefix formula-triggering chars to prevent injection in Excel/Calc
                if s and s[0] in ('=', '+', '-', '@', '\t', '\r', '\n'):
                    s = f'\t{s}'
                # RFC 4180 quoting
                s = s.replace('"', '""')
                if ',' in s or '"' in s or '\n' in s or '\t' in s:
                    return f'"{s}"'
                return s

            for c in cfdis:
                row = [
                    c.get('id', ''), c.get('uuid', ''), c.get('serie', ''),
                    c.get('folio', ''), c.get('fecha_emision', ''),
                    c.get('rfc_receptor', ''), c.get('nombre_receptor', ''),
                    c.get('uso_cfdi', ''), c.get('subtotal', 0),
                    c.get('impuestos', 0), c.get('total', 0),
                    c.get('estado', ''), c.get('sale_id', ''),
                    c.get('facturapi_id', ''), c.get('pdf_path', ''),
                    c.get('xml_path', ''),
                ]
                await f.write(','.join(map(escape, row)) + '\n')

        logger.info(f"CSV generado: {output_path} ({len(cfdis)} registros)")
        return str(output_path)

    async def _copy_to_nas(self, source_dir: Path, year: str, month: str):
        try:
            import shutil
            import asyncio
            nas_target = Path(self.nas_path) / 'cfdis' / year / month
            await asyncio.to_thread(nas_target.mkdir, parents=True, exist_ok=True)

            def do_copy():
                for file in source_dir.iterdir():
                    if file.suffix in ['.pdf', '.xml']:
                        shutil.copy2(file, nas_target / file.name)

            await asyncio.to_thread(do_copy)
            logger.info(f"Copiado a NAS: {nas_target}")
        except Exception as e:
            logger.warning(f"Error copiando a NAS: {e}")

    async def get_sync_stats(self) -> Dict[str, Any]:
        await self._init_config()
        row = await self.db.fetchrow(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN sync_status = 'synced' THEN 1 ELSE 0 END) as synced,
                SUM(CASE WHEN facturapi_id IS NOT NULL AND sync_status IS NULL THEN 1 ELSE 0 END) as pending
               FROM cfdis"""
        )
        if row:
            return {
                'total_cfdis': row.get('total', 0),
                'synced': row.get('synced', 0),
                'pending': row.get('pending', 0),
                'sync_path': str(self.sync_base_path),
                'nas_enabled': bool(self.nas_path),
            }
        return {}
