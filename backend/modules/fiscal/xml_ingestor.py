"""
XML Ingestor - Parser CFDI 4.0 para facturas de proveedores
Extrae productos con simetria SAT completa para dar de alta en inventario

Refactored: receives `db` (DB wrapper, optional) instead of `core`.
Parsing functions are sync (no await needed). DB functions use :name params.
"""

from typing import Any, Dict, List, Optional
from decimal import Decimal
import logging
from pathlib import Path
from modules.fiscal.constants import IVA_RATE

# SECURITY: Use defusedxml to prevent XXE (XML External Entity) attacks
try:
    import defusedxml.ElementTree as ET
except ImportError:
    raise ImportError(
        "defusedxml is REQUIRED for secure XML parsing. "
        "Install it: pip install defusedxml"
    )

logger = logging.getLogger(__name__)

# SAT CFDI 4.0 Namespaces
CFDI_NS = {
    'cfdi': 'http://www.sat.gob.mx/cfd/4',
    'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
}


class XMLIngestor:
    """Parser de XML CFDI 4.0 para importar productos de proveedores."""

    def __init__(self, db=None):
        self.db = db
        self.default_margin = 0.35  # 35% margen por defecto

    def parse_cfdi(self, xml_path: str) -> Dict[str, Any]:
        """
        Parsea un archivo CFDI XML y extrae informacion clave.
        This is a sync function -- no DB access needed.

        Args:
            xml_path: Ruta al archivo XML

        Returns:
            Dict con emisor, receptor, conceptos y totales
        """
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            comprobante = {
                'uuid': self._get_uuid(root),
                'fecha': root.get('Fecha'),
                'tipo_comprobante': root.get('TipoDeComprobante'),
                'moneda': root.get('Moneda', 'MXN'),
                'subtotal': Decimal(root.get('SubTotal', '0')),
                'total': Decimal(root.get('Total', '0')),
            }

            emisor = self._get_emisor(root)
            receptor = self._get_receptor(root)
            conceptos = self._get_conceptos(root)

            return {
                'success': True,
                'comprobante': comprobante,
                'emisor': emisor,
                'receptor': receptor,
                'conceptos': conceptos,
                'total_productos': len(conceptos),
            }

        except ET.ParseError as e:
            logger.error(f"Error parsing XML: {e}")
            return {'success': False, 'error': f'XML invalido: {e}'}
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
                'regimen': emisor.get('RegimenFiscal', ''),
            }
        return {}

    def _get_receptor(self, root) -> Dict[str, str]:
        """Extrae datos del receptor (tu negocio)."""
        receptor = root.find('.//cfdi:Receptor', CFDI_NS)
        if receptor is not None:
            return {
                'rfc': receptor.get('Rfc', ''),
                'nombre': receptor.get('Nombre', ''),
                'uso_cfdi': receptor.get('UsoCFDI', ''),
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
                        item['tasa_iva'] = Decimal(traslado.get('TasaOCuota', str(IVA_RATE)))

            conceptos.append(item)

        return conceptos

    def _calcular_precio_venta(self, costo: Decimal) -> Decimal:
        """Calcula precio de venta con margen por defecto."""
        return (costo * Decimal(str(1 + self.default_margin))).quantize(Decimal('0.01'))

    async def import_to_database(self, parsed_data: Dict, serie_distribution: Dict = None) -> Dict:
        """
        Importa productos del XML a la base de datos.

        Args:
            parsed_data: Resultado de parse_cfdi()
            serie_distribution: {'serie_a': 0.6, 'serie_b': 0.4}

        Returns:
            Dict con resultados de importacion
        """
        if not self.db:
            return {'success': False, 'error': 'DB no inicializado'}

        if not parsed_data.get('success'):
            return parsed_data

        serie_distribution = serie_distribution or {'serie_a': 1.0, 'serie_b': 0.0}

        imported = 0
        updated = 0
        errors = []

        for concepto in parsed_data.get('conceptos', []):
            try:
                existing = await self._find_existing_product(concepto)

                if existing:
                    await self._update_product(existing['id'], concepto, serie_distribution)
                    updated += 1
                else:
                    await self._create_product(concepto, serie_distribution, parsed_data['emisor'])
                    imported += 1

            except Exception as e:
                errors.append(f"{concepto['descripcion'][:30]}: {e}")

        return {
            'success': True,
            'imported': imported,
            'updated': updated,
            'errors': errors,
            'emisor': parsed_data['emisor']['nombre'],
            'uuid': parsed_data['comprobante']['uuid'],
        }

    async def _find_existing_product(self, concepto: Dict) -> Optional[Dict]:
        """Busca producto existente por codigo o descripcion."""
        if concepto.get('no_identificacion'):
            result = await self.db.fetchrow(
                "SELECT * FROM products WHERE barcode = :code OR sku = :code LIMIT 1",
                {"code": concepto['no_identificacion']},
            )
            if result:
                return result

        desc_pattern = f"%{concepto['descripcion'][:20].lower()}%"
        result = await self.db.fetchrow(
            "SELECT * FROM products WHERE LOWER(name) LIKE :pattern LIMIT 1",
            {"pattern": desc_pattern},
        )
        return result

    async def _create_product(self, concepto: Dict, distribution: Dict, emisor: Dict):
        """Crea nuevo producto con simetria SAT."""
        total_qty = int(concepto['cantidad'])

        sku = concepto.get('no_identificacion') or self._generate_sku()

        await self.db.execute(
            """INSERT INTO products
               (sku, barcode, name, price, cost_price, stock, min_stock, category_id,
                sat_clave_prod_serv, sat_clave_unidad, status, supplier_rfc, supplier_name, synced)
               VALUES (:sku, :barcode, :name, :price, :cost_price, :stock, :min_stock, :cat,
                :sat_prod, :sat_unit, :status, :sup_rfc, :sup_name, :synced)""",
            {
                "sku": sku,
                "barcode": concepto.get('no_identificacion', ''),
                "name": concepto['descripcion'][:100],
                "price": float(concepto['precio_sugerido']),
                "cost_price": float(concepto['valor_unitario']),
                "stock": total_qty,
                "min_stock": 5,
                "cat": 1,
                "sat_prod": concepto['clave_sat'],
                "sat_unit": concepto['clave_unidad'],
                "status": "active",
                "sup_rfc": emisor.get('rfc', ''),
                "sup_name": emisor.get('nombre', ''),
                "synced": 0,
            },
        )
        logger.info(f"Producto creado: {concepto['descripcion'][:100]}")

    async def _update_product(self, product_id: int, concepto: Dict, distribution: Dict):
        """Actualiza stock y costo de producto existente."""
        adicional = int(concepto['cantidad'])

        await self.db.execute(
            """UPDATE products SET
               stock = stock + :qty,
               cost_price = :cost,
               sat_clave_prod_serv = COALESCE(sat_clave_prod_serv, :sat_prod),
               sat_clave_unidad = COALESCE(sat_clave_unidad, :sat_unit),
               synced = 0
               WHERE id = :pid""",
            {
                "qty": adicional,
                "cost": float(concepto['valor_unitario']),
                "sat_prod": concepto['clave_sat'],
                "sat_unit": concepto['clave_unidad'],
                "pid": product_id,
            },
        )
        try:
            await self.db.execute(
                """INSERT INTO inventory_movements
                   (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                   VALUES (:pid, 'IN', 'xml_ingestor', :qty, :reason, 'xml_ingestor', NOW(), 0)""",
                {"pid": product_id, "qty": adicional, "reason": "Importacion XML proveedor"},
            )
        except Exception as e:
            logger.debug("xml_ingestor movement: %s", e)

    def _generate_sku(self) -> str:
        """Genera SKU unico."""
        import random
        import string
        return 'IMP-' + ''.join(random.choices(string.digits, k=8))
