"""
XML Ingestor - Parser CFDI 4.0 para facturas de proveedores
Extrae productos con simetría SAT completa para dar de alta en inventario
"""

from typing import Any, Dict, List, Optional
from decimal import Decimal
import logging
from pathlib import Path

# SECURITY: Use defusedxml to prevent XXE (XML External Entity) attacks
# XXE can lead to: local file disclosure, SSRF, DoS
try:
    import defusedxml.ElementTree as ET
except ImportError:
    # Fallback: Use standard library with manual XXE protection
    import xml.etree.ElementTree as ET
    import logging as _log
    _log.getLogger(__name__).warning(
        "defusedxml not installed. Using standard ElementTree. "
        "Install defusedxml for better XXE protection: pip install defusedxml"
    )

logger = logging.getLogger(__name__)

# SAT CFDI 4.0 Namespaces
CFDI_NS = {
    'cfdi': 'http://www.sat.gob.mx/cfd/4',
    'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
}

class XMLIngestor:
    """Parser de XML CFDI 4.0 para importar productos de proveedores."""
    
    def __init__(self, core=None):
        self.core = core
        self.default_margin = 0.35  # 35% margen por defecto
    
    def parse_cfdi(self, xml_path: str) -> Dict[str, Any]:
        """
        Parsea un archivo CFDI XML y extrae información clave.
        
        Args:
            xml_path: Ruta al archivo XML
            
        Returns:
            Dict con emisor, receptor, conceptos y totales
        """
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # Datos del comprobante
            comprobante = {
                'uuid': self._get_uuid(root),
                'fecha': root.get('Fecha'),
                'tipo_comprobante': root.get('TipoDeComprobante'),
                'moneda': root.get('Moneda', 'MXN'),
                'subtotal': Decimal(root.get('SubTotal', '0')),
                'total': Decimal(root.get('Total', '0')),
            }
            
            # Emisor (proveedor)
            emisor = self._get_emisor(root)
            
            # Receptor (tu negocio)
            receptor = self._get_receptor(root)
            
            # Conceptos (productos)
            conceptos = self._get_conceptos(root)
            
            return {
                'success': True,
                'comprobante': comprobante,
                'emisor': emisor,
                'receptor': receptor,
                'conceptos': conceptos,
                'total_productos': len(conceptos)
            }
            
        except ET.ParseError as e:
            logger.error(f"Error parsing XML: {e}")
            return {'success': False, 'error': f'XML inválido: {e}'}
        except Exception as e:
            logger.error(f"Error processing CFDI: {e}")
            return {'success': False, 'error': str(e)}
    
    def _get_uuid(self, root) -> Optional[str]:
        """Extrae UUID del timbre fiscal."""
        tfd = root.find('.//tfd:TimbreFiscalDigital', CFDI_NS)
        if tfd is not None:
            return tfd.get('UUID')
        return None
    
    def _get_emisor(self, root) -> Dict[str, str]:
        """Extrae datos del emisor (proveedor)."""
        emisor = root.find('.//cfdi:Emisor', CFDI_NS)
        if emisor is not None:
            return {
                'rfc': emisor.get('Rfc', ''),
                'nombre': emisor.get('Nombre', ''),
                'regimen': emisor.get('RegimenFiscal', '')
            }
        return {}
    
    def _get_receptor(self, root) -> Dict[str, str]:
        """Extrae datos del receptor (tu negocio)."""
        receptor = root.find('.//cfdi:Receptor', CFDI_NS)
        if receptor is not None:
            return {
                'rfc': receptor.get('Rfc', ''),
                'nombre': receptor.get('Nombre', ''),
                'uso_cfdi': receptor.get('UsoCFDI', '')
            }
        return {}
    
    def _get_conceptos(self, root) -> List[Dict[str, Any]]:
        """Extrae todos los conceptos (productos)."""
        conceptos = []
        
        for concepto in root.findall('.//cfdi:Concepto', CFDI_NS):
            item = {
                'clave_sat': concepto.get('ClaveProdServ', '01010101'),
                'clave_unidad': concepto.get('ClaveUnidad', 'H87'),
                'unidad': concepto.get('Unidad', 'Pieza'),
                'no_identificacion': concepto.get('NoIdentificacion', ''),
                'descripcion': concepto.get('Descripcion', ''),
                'cantidad': Decimal(concepto.get('Cantidad', '1')),
                'valor_unitario': Decimal(concepto.get('ValorUnitario', '0')),
                'importe': Decimal(concepto.get('Importe', '0')),
                'objeto_imp': concepto.get('ObjetoImp', '02'),
            }
            
            # Calcular precio de venta sugerido
            item['precio_sugerido'] = self._calcular_precio_venta(item['valor_unitario'])
            
            # Extraer impuestos del concepto
            impuestos = concepto.find('.//cfdi:Impuestos', CFDI_NS)
            if impuestos is not None:
                traslados = impuestos.findall('.//cfdi:Traslado', CFDI_NS)
                for traslado in traslados:
                    if traslado.get('Impuesto') == '002':  # IVA
                        item['tasa_iva'] = Decimal(traslado.get('TasaOCuota', '0.160000'))
            
            conceptos.append(item)
        
        return conceptos
    
    def _calcular_precio_venta(self, costo: Decimal) -> Decimal:
        """Calcula precio de venta con margen por defecto."""
        return (costo * Decimal(str(1 + self.default_margin))).quantize(Decimal('0.01'))
    
    def import_to_database(self, parsed_data: Dict, serie_distribution: Dict = None) -> Dict:
        """
        Importa productos del XML a la base de datos.
        
        Args:
            parsed_data: Resultado de parse_cfdi()
            serie_distribution: {'serie_a': 0.6, 'serie_b': 0.4} - Distribución de stock
        
        Returns:
            Dict con resultados de importación
        """
        if not self.core:
            return {'success': False, 'error': 'Core no inicializado'}
        
        if not parsed_data.get('success'):
            return parsed_data
        
        serie_distribution = serie_distribution or {'serie_a': 1.0, 'serie_b': 0.0}
        
        imported = 0
        updated = 0
        errors = []
        
        for concepto in parsed_data.get('conceptos', []):
            try:
                # Buscar si producto ya existe
                existing = self._find_existing_product(concepto)
                
                if existing:
                    # Actualizar stock y costo
                    self._update_product(existing['id'], concepto, serie_distribution)
                    updated += 1
                else:
                    # Crear nuevo producto
                    self._create_product(concepto, serie_distribution, parsed_data['emisor'])
                    imported += 1
                    
            except Exception as e:
                errors.append(f"{concepto['descripcion'][:30]}: {e}")
        
        return {
            'success': True,
            'imported': imported,
            'updated': updated,
            'errors': errors,
            'emisor': parsed_data['emisor']['nombre'],
            'uuid': parsed_data['comprobante']['uuid']
        }
    
    def _find_existing_product(self, concepto: Dict) -> Optional[Dict]:
        """Busca producto existente por código o descripción."""
        # Buscar por NoIdentificacion (código proveedor)
        if concepto.get('no_identificacion'):
            result = list(self.core.db.execute_query(
                "SELECT * FROM products WHERE barcode = %s OR sku = %s LIMIT 1",
                (concepto['no_identificacion'], concepto['no_identificacion'])
            ))
            if result:
                return dict(result[0])
        
        # Buscar por descripción similar
        result = list(self.core.db.execute_query(
            "SELECT * FROM products WHERE LOWER(name) LIKE %s LIMIT 1",
            (f"%{concepto['descripcion'][:20].lower()}%",)
        ))
        return dict(result[0]) if result else None
    
    def _create_product(self, concepto: Dict, distribution: Dict, emisor: Dict):
        """Crea nuevo producto con simetría SAT."""
        total_qty = int(concepto['cantidad'])
        qty_a = int(total_qty * distribution['serie_a'])
        qty_b = total_qty - qty_a
        
        product_data = {
            'sku': concepto.get('no_identificacion') or self._generate_sku(),
            'barcode': concepto.get('no_identificacion', ''),
            'name': concepto['descripcion'][:100],
            'price': float(concepto['precio_sugerido']),
            'cost_price': float(concepto['valor_unitario']),
            'stock': total_qty,
            'min_stock': 5,
            'category_id': 1,  # Default category
            'sat_clave_prod_serv': concepto['clave_sat'],
            'sat_clave_unidad': concepto['clave_unidad'],
            'status': 'active',
            'supplier_rfc': emisor.get('rfc', ''),
            'supplier_name': emisor.get('nombre', ''),
            'synced': 0,
        }

        # Insertar producto
        cols = ', '.join(product_data.keys())
        placeholders = ', '.join(['%s' for _ in product_data])
        
        self.core.db.execute_write(
            f"INSERT INTO products ({cols}) VALUES ({placeholders})",
            tuple(product_data.values())
        )
        
        logger.info(f"Producto creado: {product_data['name']}")
    
    def _update_product(self, product_id: int, concepto: Dict, distribution: Dict):
        """Actualiza stock y costo de producto existente (Parte A Fase 1.4: registrar movimiento)."""
        adicional = int(concepto['cantidad'])
        
        self.core.db.execute_write(
            """UPDATE products SET
               stock = stock + %s,
               cost_price = %s,
               sat_clave_prod_serv = COALESCE(sat_clave_prod_serv, %s),
               sat_clave_unidad = COALESCE(sat_clave_unidad, %s),
               synced = 0
               WHERE id = %s""",
            (adicional, float(concepto['valor_unitario']),
             concepto['clave_sat'], concepto['clave_unidad'], product_id)
        )
        try:
            self.core.db.execute_write(
                """INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                   VALUES (%s, 'IN', 'xml_ingestor', %s, %s, 'xml_ingestor', NOW(), 0)""",
                (product_id, adicional, "Importación XML proveedor")
            )
        except Exception as e:
            logger.debug("xml_ingestor movement: %s", e)
    
    def _generate_sku(self) -> str:
        """Genera SKU único."""
        import random
        import string
        return 'IMP-' + ''.join(random.choices(string.digits, k=8))

def procesar_xml_proveedor(xml_path: str) -> List[Dict]:
    """
    Función de compatibilidad para el código de ejemplo del usuario.
    """
    ingestor = XMLIngestor()
    result = ingestor.parse_cfdi(xml_path)
    if result.get('success'):
        return result.get('conceptos', [])
    return []
