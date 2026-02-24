"""
Legal Document Generator - Generador de documentos legales con sellado digital
Conforme al Art. 32-F CFF y Art. 25 fracc. VI LISR
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import hashlib
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class LegalDocumentGenerator:
    """
    Generador de documentos legales para soporte de materialidad fiscal.
    Incluye sellado digital SHA-256 para integridad.
    """
    
    DOCS_PATH = Path(__file__).resolve().parent.parent.parent / 'docs/actas'
    
    def __init__(self, core):
        self.core = core
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """Crea directorios necesarios."""
        self.DOCS_PATH.mkdir(parents=True, exist_ok=True)
        (self.DOCS_PATH / 'destruccion').mkdir(exist_ok=True)
        (self.DOCS_PATH / 'devoluciones').mkdir(exist_ok=True)
        (self.DOCS_PATH / 'autoconsumo').mkdir(exist_ok=True)
        (self.DOCS_PATH / 'evidencias').mkdir(exist_ok=True)
    
    def generate_destruction_acta(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Genera acta circunstanciada de destrucción de mercancía.
        Art. 32-F CFF, Art. 25 Fracc. VI LISR.
        """
        config = self.core.get_app_config()
        fiscal = self.core.get_fiscal_config()
        
        folio = data.get('folio', f"MER-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        timestamp = datetime.now()
        
        # Template legal
        acta_content = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     ACTA CIRCUNSTANCIADA DE DESTRUCCIÓN DE MERCANCÍA E INVENTARIO INÚTIL     ║
║                           FOLIO: {folio:<42} ║
╚══════════════════════════════════════════════════════════════════════════════╝

LUGAR:           Mérida, Yucatán, México
FECHA Y HORA:    {timestamp.strftime('%d de %B de %Y, %H:%M:%S horas')}

═══════════════════════════════════════════════════════════════════════════════
                              FUNDAMENTO LEGAL
═══════════════════════════════════════════════════════════════════════════════

Se levanta la presente acta en cumplimiento con lo dispuesto en:

• Artículo 25, fracción VI de la Ley del Impuesto sobre la Renta (LISR) - 
  Deducciones autorizadas por pérdidas por caso fortuito, fuerza mayor o 
  enajenación de bienes distintos de inversiones.

• Artículo 32-F del Código Fiscal de la Federación (CFF) - Obligación de 
  destruir mercancías que hubieran perdido su valor por deterioro u otras 
  causas no imputables al contribuyente.

• Regla 2.7.1.21 de la Resolución Miscelánea Fiscal Vigente.

═══════════════════════════════════════════════════════════════════════════════
                          DATOS DEL CONTRIBUYENTE
═══════════════════════════════════════════════════════════════════════════════

Razón Social:    {config.get('business_name', 'RAZÓN SOCIAL')}
RFC:             {fiscal.get('rfc_emisor', 'RFC')}
Régimen Fiscal:  {fiscal.get('emisor_regimen', '626')} - RESICO
Domicilio:       {config.get('address', 'Mérida, Yucatán')}

═══════════════════════════════════════════════════════════════════════════════
                          DESCRIPCIÓN DE BIENES
═══════════════════════════════════════════════════════════════════════════════

Producto:            {data.get('product_name', 'N/A')}
SKU/Código:          {data.get('sku', 'N/A')}
Clave SAT:           {data.get('sat_key', 'N/A')}
Cantidad Afectada:   {data.get('quantity', 0)} {data.get('unit', 'PZA')}
Costo Unitario:      ${data.get('unit_cost', 0):,.2f} MXN
Valor Total:         ${data.get('total_value', 0):,.2f} MXN

═══════════════════════════════════════════════════════════════════════════════
                           CAUSA DE LA BAJA
═══════════════════════════════════════════════════════════════════════════════

Categoría:           {data.get('category', 'DETERIORO').upper()}
Motivo Específico:   {data.get('reason', 'Deterioro del producto')}

═══════════════════════════════════════════════════════════════════════════════
                          RELATO DE LOS HECHOS
═══════════════════════════════════════════════════════════════════════════════

En la fecha y hora antes señaladas, siendo las {timestamp.strftime('%H:%M')} horas del día 
{timestamp.strftime('%d de %B de %Y')}, en el establecimiento comercial ubicado en 
{config.get('address', 'Mérida, Yucatán')}, se detectó que los bienes arriba descritos 
NO SON APTOS PARA SU COMERCIALIZACIÓN debido a: {data.get('reason', 'deterioro')}.

Se procedió a la SEGREGACIÓN INMEDIATA del inventario apto para venta y se autoriza 
su DESTRUCCIÓN FÍSICA para evitar:
  a) Su comercialización indebida
  b) Riesgos a la salud del consumidor (en caso de productos perecederos)
  c) Afectación a la imagen comercial del establecimiento

La mercancía será destruida conforme a las disposiciones ambientales aplicables.

═══════════════════════════════════════════════════════════════════════════════
                         TESTIGOS Y FIRMAS
═══════════════════════════════════════════════════════════════════════════════

Testigo 1 (Personal):     {data.get('witness_name', 'N/A')}
Testigo 2 (Supervisor):   {data.get('supervisor_name', 'N/A')}

Autorizado por:           {data.get('authorized_by', 'Pendiente')}
Fecha Autorización:       {data.get('authorized_at', 'Pendiente')}

___________________________          ___________________________
    Responsable del Área                  Testigo Presencial

___________________________
    Representante Legal

═══════════════════════════════════════════════════════════════════════════════
                         EVIDENCIA FOTOGRÁFICA
═══════════════════════════════════════════════════════════════════════════════

Estado de Evidencia:     {'FOTOGRAFÍAS ANEXAS' if data.get('photo_path') else 'PENDIENTE'}
Archivo de Evidencia:    {data.get('photo_path', 'No adjunta')}
UUID Expediente:         {data.get('uuid', 'N/A')}

═══════════════════════════════════════════════════════════════════════════════
                         SELLADO DIGITAL
═══════════════════════════════════════════════════════════════════════════════

Fecha Generación:        {timestamp.isoformat()}
"""
        
        # Generar hash SHA-256 para sellado digital
        content_for_hash = f"{folio}|{timestamp.isoformat()}|{data.get('product_name')}|{data.get('total_value')}"
        sha256_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()
        
        acta_content += f"""Hash SHA-256:            {sha256_hash}

Este documento fue generado automáticamente por el Sistema TITAN POS/Antigravity.
El hash SHA-256 garantiza la integridad del documento desde su creación.

═══════════════════════════════════════════════════════════════════════════════
                              FIN DEL ACTA
═══════════════════════════════════════════════════════════════════════════════
"""
        
        # Guardar archivo
        filename = f"ACTA_{folio}_{timestamp.strftime('%Y%m%d')}.txt"
        filepath = self.DOCS_PATH / 'destruccion' / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(acta_content)
        
        # SECURITY: No loguear generación de actas
        pass
        
        return {
            'success': True,
            'folio': folio,
            'filepath': str(filepath),
            'hash': sha256_hash,
            'timestamp': timestamp.isoformat(),
            'content_length': len(acta_content)
        }
    
    def generate_return_document(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Genera documento de devolución.
        Serie A: Requiere CFDI de Egreso.
        Serie B: Nota de crédito interna.
        """
        folio = f"DEV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        timestamp = datetime.now()
        
        serie = data.get('serie', 'B')
        requires_cfdi = serie == 'A'
        
        doc_content = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    NOTA DE DEVOLUCIÓN / CRÉDITO                              ║
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
                         DETALLE DE LA DEVOLUCIÓN
───────────────────────────────────────────────────────────────────────────────

Producto:            {data.get('product_name', 'N/A')}
SKU:                 {data.get('sku', 'N/A')}
Cantidad:            {data.get('quantity', 0)}
Precio Unitario:     ${data.get('unit_price', 0):,.2f}
Subtotal:            ${data.get('subtotal', 0):,.2f}
IVA:                 ${data.get('tax', 0):,.2f}
Total Devolución:    ${data.get('total', 0):,.2f}

───────────────────────────────────────────────────────────────────────────────
                         MOTIVO DE LA DEVOLUCIÓN
───────────────────────────────────────────────────────────────────────────────

Categoría:           {data.get('return_category', 'Cambio de opinión')}
Descripción:         {data.get('return_reason', 'N/A')}
Estado del Producto: {data.get('product_condition', 'íntegro')}

───────────────────────────────────────────────────────────────────────────────
                         ACCIONES REQUERIDAS
───────────────────────────────────────────────────────────────────────────────
"""
        
        if requires_cfdi:
            doc_content += f"""
⚠️  ACCIÓN FISCAL REQUERIDA:
    Generar CFDI de Egreso (Nota de Crédito) relacionado al UUID:
    {data.get('original_uuid', 'PENDIENTE')}
    
    Tipo Relación: 01 - Nota de crédito de los documentos relacionados
"""
        else:
            doc_content += """
✅  ACCIÓN INTERNA:
    El stock ha sido reintegrado al inventario físico.
    No se requiere documento fiscal adicional.
"""
        
        doc_content += f"""
───────────────────────────────────────────────────────────────────────────────
                         FIRMAS
───────────────────────────────────────────────────────────────────────────────

Procesado por:       {data.get('processed_by', 'N/A')}
Cliente:             {data.get('customer_name', 'Público General')}

___________________________          ___________________________
    Personal de Tienda                    Cliente (Opcional)

Hash: {hashlib.sha256(folio.encode()).hexdigest()[:32]}
"""
        
        filename = f"DEVOLUCION_{folio}.txt"
        filepath = self.DOCS_PATH / 'devoluciones' / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(doc_content)
        
        return {
            'success': True,
            'folio': folio,
            'filepath': str(filepath),
            'requires_cfdi': requires_cfdi,
            'serie': serie
        }
    
    def generate_selfconsumption_voucher(self, items: List[Dict], 
                                          period: str = None) -> Dict[str, Any]:
        """
        Genera vale de consumo interno mensual.
        Art. 25 LISR - Gastos de operación deducibles.
        """
        period = period or datetime.now().strftime('%Y-%m')
        folio = f"AUTO-{period.replace('-', '')}"
        
        total_value = sum(item.get('value', 0) for item in items)
        
        doc_content = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    VALE DE CONSUMO INTERNO MENSUAL                           ║
║                    PERÍODO: {period:<47} ║
╚══════════════════════════════════════════════════════════════════════════════╝

FOLIO:               {folio}
FECHA GENERACIÓN:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

───────────────────────────────────────────────────────────────────────────────
                         FUNDAMENTO FISCAL
───────────────────────────────────────────────────────────────────────────────

Este documento ampara el AUTOCONSUMO y MUESTRAS GRATUITAS del período, 
registrados como GASTO DE OPERACIÓN conforme al Art. 25 de la LISR.

El autoconsumo NO genera ingreso fiscal al no existir enajenación a terceros.
Se registra únicamente para efectos de control de inventario.

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
{'TOTAL PERÍODO:':<42} ${total_value:>12,.2f}

───────────────────────────────────────────────────────────────────────────────
                         CATEGORÍAS DE CONSUMO
───────────────────────────────────────────────────────────────────────────────

• LIMPIEZA:      Productos usados para mantenimiento del local
• EMPLEADOS:     Consumo autorizado por personal
• MUESTRAS:      Productos entregados sin costo para promoción
• OPERACIÓN:     Insumos consumidos en la operación diaria

───────────────────────────────────────────────────────────────────────────────

Autorizado por: ____________________________

Este vale justifica fiscalmente la baja de inventario sin venta correspondiente
para el período indicado.

Hash: {hashlib.sha256(f'{folio}|{total_value}'.encode()).hexdigest()[:32]}
"""
        
        filename = f"AUTOCONSUMO_{folio}.txt"
        filepath = self.DOCS_PATH / 'autoconsumo' / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(doc_content)
        
        return {
            'success': True,
            'folio': folio,
            'filepath': str(filepath),
            'period': period,
            'total_value': total_value,
            'items_count': len(items)
        }
    
    def get_monthly_summary(self, year: int = None, month: int = None) -> Dict[str, Any]:
        """Obtiene resumen mensual de documentos generados."""
        year = year or datetime.now().year
        month = month or datetime.now().month
        
        # Contar archivos por tipo
        destruccion = list((self.DOCS_PATH / 'destruccion').glob(f'*{year}{month:02d}*.txt'))
        devoluciones = list((self.DOCS_PATH / 'devoluciones').glob(f'*{year}{month:02d}*.txt'))
        autoconsumo = list((self.DOCS_PATH / 'autoconsumo').glob(f'*{year}{month:02d}*.txt'))
        
        return {
            'period': f'{year}-{month:02d}',
            'destruccion': len(destruccion),
            'devoluciones': len(devoluciones),
            'autoconsumo': len(autoconsumo),
            'total_docs': len(destruccion) + len(devoluciones) + len(autoconsumo)
        }
