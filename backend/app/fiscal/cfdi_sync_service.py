"""
CFDI Sync Service - Descarga y sincroniza CFDIs al servidor central

Descarga PDFs, XMLs y genera reportes CSV de todas las facturas
para respaldo centralizado en el servidor.

Usage Example::

    from app.fiscal.cfdi_sync_service import CFDISyncService

    sync = CFDISyncService(core)

    # Sincronizar un CFDI especifico
    result = sync.sync_cfdi(cfdi_id=123, facturapi_id='abc123')

    # Sincronizar todos los pendientes
    results = sync.sync_pending_cfdis()

    # Generar CSV para contabilidad
    csv_path = sync.generate_csv_report('2024-01-01', '2024-01-31')
"""

from typing import Any, Dict, List, Optional
import csv
from datetime import datetime, timedelta
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class CFDISyncService:
    """
    Servicio para sincronizar CFDIs de Facturapi al servidor central.
    
    Funciones:
    - Descargar PDFs y XMLs de facturas emitidas
    - Guardarlos en carpeta del servidor (NAS/central)
    - Generar CSV de resumen para contabilidad
    """
    
    def __init__(self, core):
        """
        Initialize sync service.
        
        Args:
            core: POSCore instance
        """
        self.core = core
        self._facturapi = None
        
        # Configurar rutas (leer de config o usar defaults)
        cfg = core.get_app_config() or {}
        self.sync_base_path = Path(cfg.get('cfdi_sync_path', '/var/titan/cfdis'))
        self.nas_path = cfg.get('backup_nas_path', '')
    
    def _get_facturapi(self):
        """Get Facturapi client."""
        if self._facturapi is None:
            try:
                from app.fiscal.cfdi_service import CFDIService
                service = CFDIService(self.core)
                self._facturapi = service._get_facturapi()
            except Exception as e:
                logger.warning(f"Facturapi no disponible: {e}")
        return self._facturapi
    
    def sync_cfdi(self, cfdi_id: int, facturapi_id: str) -> Dict[str, Any]:
        """
        Sincroniza un CFDI específico: descarga PDF y XML.
        
        Args:
            cfdi_id: ID local del CFDI
            facturapi_id: ID de Facturapi
            
        Returns:
            Dict con rutas de archivos guardados
        """
        facturapi = self._get_facturapi()
        if not facturapi:
            return {'success': False, 'error': 'Facturapi no configurado'}
        
        try:
            # Obtener datos del CFDI local
            cfdi = self.core.db.execute_query(
                "SELECT * FROM cfdis WHERE id = %s",
                (cfdi_id,)
            )
            
            if not cfdi:
                return {'success': False, 'error': f'CFDI {cfdi_id} no encontrado'}
            
            cfdi = dict(cfdi[0])
            uuid = cfdi.get('uuid', 'unknown')
            fecha = cfdi.get('fecha_emision', datetime.now().isoformat())[:10]
            
            # Crear estructura de carpetas: /año/mes/
            year = fecha[:4]
            month = fecha[5:7]
            
            cfdi_dir = self.sync_base_path / year / month
            cfdi_dir.mkdir(parents=True, exist_ok=True)
            
            result = {
                'success': True,
                'cfdi_id': cfdi_id,
                'uuid': uuid,
                'files': {}
            }
            
            # Descargar PDF
            try:
                pdf_result = facturapi.invoices.download_pdf(facturapi_id)
                if pdf_result.get('success'):
                    pdf_path = cfdi_dir / f"{uuid}.pdf"
                    with open(pdf_path, 'wb') as f:
                        f.write(pdf_result['content'])
                    result['files']['pdf'] = str(pdf_path)
                    logger.info(f"PDF guardado: {pdf_path}")
            except Exception as e:
                logger.warning(f"Error descargando PDF: {e}")
                result['files']['pdf_error'] = str(e)
            
            # Descargar XML
            try:
                xml_result = facturapi.invoices.download_xml(facturapi_id)
                if xml_result.get('success'):
                    xml_path = cfdi_dir / f"{uuid}.xml"
                    with open(xml_path, 'wb') as f:
                        f.write(xml_result['content'])
                    result['files']['xml'] = str(xml_path)
                    logger.info(f"XML guardado: {xml_path}")
            except Exception as e:
                logger.warning(f"Error descargando XML: {e}")
                result['files']['xml_error'] = str(e)
            
            # Marcar como sincronizado en BD
            self.core.db.execute_write(
                """UPDATE cfdis 
                   SET sync_status = 'synced', 
                       sync_date = %s,
                       pdf_path = %s,
                       xml_path = %s
                   WHERE id = %s""",
                (datetime.now().isoformat(),
                 result['files'].get('pdf', ''),
                 result['files'].get('xml', ''),
                 cfdi_id)
            )
            
            # Copiar a NAS si está configurado
            if self.nas_path:
                self._copy_to_nas(cfdi_dir, year, month)
            
            return result
            
        except Exception as e:
            logger.error(f"Error sincronizando CFDI {cfdi_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def sync_pending_cfdis(self) -> Dict[str, Any]:
        """
        Sincroniza todos los CFDIs pendientes de sincronización.
        
        Returns:
            Resumen de sincronización
        """
        # Obtener CFDIs con facturapi_id pero sin sync
        pending = self.core.db.execute_query(
            """SELECT id, facturapi_id 
               FROM cfdis 
               WHERE facturapi_id IS NOT NULL 
                 AND facturapi_id != ''
                 AND (sync_status IS NULL OR sync_status != 'synced')
               ORDER BY id DESC
               LIMIT 100"""
        )
        
        results = {
            'total': len(pending),
            'synced': 0,
            'errors': 0,
            'details': []
        }
        
        for cfdi in pending:
            cfdi = dict(cfdi)
            result = self.sync_cfdi(cfdi['id'], cfdi['facturapi_id'])
            
            if result.get('success'):
                results['synced'] += 1
            else:
                results['errors'] += 1
                
            results['details'].append(result)
        
        logger.info(f"Sincronización completa: {results['synced']}/{results['total']} CFDIs")
        return results
    
    def generate_csv_report(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> str:
        """
        Genera un CSV con todos los CFDIs del período para contabilidad.
        
        Args:
            date_from: Fecha inicial (YYYY-MM-DD)
            date_to: Fecha final (YYYY-MM-DD)
            output_path: Ruta de salida (opcional)
            
        Returns:
            Ruta del archivo CSV generado
        """
        # Defaults
        if not date_to:
            date_to = datetime.now().strftime('%Y-%m-%d')
        if not date_from:
            date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        # Query
        cfdis = self.core.list_cfdi(date_from=date_from, date_to=date_to)
        
        # Prepare output path
        if not output_path:
            reports_dir = self.sync_base_path / 'reportes'
            reports_dir.mkdir(parents=True, exist_ok=True)
            output_path = reports_dir / f"cfdis_{date_from}_{date_to}.csv"
        else:
            output_path = Path(output_path)
        
        # Write CSV
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'ID', 'UUID', 'Serie', 'Folio', 'Fecha Emisión',
                'RFC Receptor', 'Nombre Receptor', 'Uso CFDI',
                'Subtotal', 'IVA', 'Total', 'Estado',
                'Venta ID', 'Facturapi ID', 'PDF Path', 'XML Path'
            ])
            
            # Data
            for c in cfdis:
                c = dict(c)
                writer.writerow([
                    c.get('id', ''),
                    c.get('uuid', ''),
                    c.get('serie', ''),
                    c.get('folio', ''),
                    c.get('fecha_emision', ''),
                    c.get('rfc_receptor', ''),
                    c.get('nombre_receptor', ''),
                    c.get('uso_cfdi', ''),
                    c.get('subtotal', 0),
                    c.get('impuestos', 0),
                    c.get('total', 0),
                    c.get('estado', ''),
                    c.get('sale_id', ''),
                    c.get('facturapi_id', ''),
                    c.get('pdf_path', ''),
                    c.get('xml_path', ''),
                ])
        
        logger.info(f"CSV generado: {output_path} ({len(cfdis)} registros)")
        return str(output_path)
    
    def _copy_to_nas(self, source_dir: Path, year: str, month: str):
        """Copia archivos al NAS si está configurado."""
        try:
            import shutil
            nas_target = Path(self.nas_path) / 'cfdis' / year / month
            nas_target.mkdir(parents=True, exist_ok=True)
            
            for file in source_dir.iterdir():
                if file.suffix in ['.pdf', '.xml']:
                    shutil.copy2(file, nas_target / file.name)
                    
            logger.info(f"Copiado a NAS: {nas_target}")
        except Exception as e:
            logger.warning(f"Error copiando a NAS: {e}")
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de sincronización."""
        stats = self.core.db.execute_query(
            """SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN sync_status = 'synced' THEN 1 ELSE 0 END) as synced,
                SUM(CASE WHEN facturapi_id IS NOT NULL AND sync_status IS NULL THEN 1 ELSE 0 END) as pending
               FROM cfdis"""
        )
        
        if stats:
            s = dict(stats[0])
            return {
                'total_cfdis': s.get('total', 0),
                'synced': s.get('synced', 0),
                'pending': s.get('pending', 0),
                'sync_path': str(self.sync_base_path),
                'nas_enabled': bool(self.nas_path)
            }
        return {}
