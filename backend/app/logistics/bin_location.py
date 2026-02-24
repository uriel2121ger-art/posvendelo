from pathlib import Path

"""
Virtual Bin-Location - El GPS del Estante
Sistema de ubicación física en bodega con QR

Funciones:
- Mapeo lógico de coordenadas: Pasillo, Estante, Nivel
- Escaneo QR para asignación de ubicación
- Búsqueda de productos con ubicación exacta
- Generación de rutas de picking optimizadas
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import hashlib
import logging
import sys

logger = logging.getLogger(__name__)

class BinLocationManager:
    """
    GPS del Estante - Sistema de ubicación en bodega.
    
    El Problema: Con 14,000 productos, un empleado nuevo pierde
    20 minutos buscando un producto específico.
    
    La Solución:
    - Cada estante tiene un QR pequeño
    - Al recibir mercancía, se escanea producto + QR del estante
    - En búsquedas: "Pasillo 3, Estante B, Nivel 2"
    
    Impacto: Reduce tiempo de surtido en 50%
    """
    
    def __init__(self, core):
        self.core = core
        self._ensure_schema()
    
    def _ensure_schema(self):
        """Crea tabla de ubicaciones si no existe."""
        try:
            self.core.db.execute_write("""
                CREATE TABLE IF NOT EXISTS bin_locations (
                    id BIGSERIAL PRIMARY KEY,
                    product_id INTEGER NOT NULL,
                    branch_id INTEGER DEFAULT 1,
                    aisle TEXT NOT NULL,
                    shelf TEXT NOT NULL,
                    level INTEGER DEFAULT 1,
                    section TEXT,
                    location_qr TEXT,
                    notes TEXT,
                    last_verified_at TEXT,
                    last_placed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    placed_by TEXT,
                    FOREIGN KEY(product_id) REFERENCES products(id),
                    UNIQUE(product_id, branch_id)
                )
            """)
            
            # Índice para búsquedas rápidas
            self.core.db.execute_write("""
                CREATE INDEX IF NOT EXISTS idx_bin_loc_product 
                ON bin_locations(product_id)
            """)
            
            self.core.db.execute_write("""
                CREATE INDEX IF NOT EXISTS idx_bin_loc_location 
                ON bin_locations(aisle, shelf, level)
            """)
            
        except Exception as e:
            logger.error(f"Error creating bin_locations table: {e}")
    
    def assign_location(self, product_id: int, 
                        aisle: str, 
                        shelf: str, 
                        level: int = 1,
                        section: str = None,
                        branch_id: int = 1,
                        placed_by: str = None) -> Dict[str, Any]:
        """
        Asigna ubicación a un producto.
        
        Args:
            product_id: ID del producto
            aisle: Pasillo ("3", "A", "COSMETICOS")
            shelf: Estante ("B", "2", "ARRIBA")
            level: Nivel (1, 2, 3)
            section: Sección opcional
            branch_id: ID de sucursal
            placed_by: Usuario que coloca
            
        Returns:
            Dict con ubicación asignada
        """
        # Generar QR único para esta ubicación
        location_qr = self._generate_location_qr(aisle, shelf, level, branch_id)
        
        try:
            # Upsert: actualiza si existe, inserta si no
            self.core.db.execute_write("""
                INSERT INTO bin_locations 
                (product_id, branch_id, aisle, shelf, level, section, 
                 location_qr, placed_by, last_placed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT(product_id, branch_id) DO UPDATE SET
                    aisle = excluded.aisle,
                    shelf = excluded.shelf,
                    level = excluded.level,
                    section = excluded.section,
                    location_qr = excluded.location_qr,
                    placed_by = excluded.placed_by,
                    last_placed_at = NOW()
            """, (product_id, branch_id, aisle, shelf, level, section, 
                  location_qr, placed_by))
            
            # Obtener nombre del producto
            product = list(self.core.db.execute_query(
                "SELECT name, sku FROM products WHERE id = %s", (product_id,)
            ))
            product_name = product[0]['name'] if product else 'Desconocido'
            product_sku = product[0]['sku'] if product else ''
            
            location_str = self._format_location(aisle, shelf, level, section)
            
            logger.info(f"📍 Ubicación asignada: {product_name} → {location_str}")
            
            return {
                'success': True,
                'product_id': product_id,
                'product_name': product_name,
                'product_sku': product_sku,
                'location': {
                    'aisle': aisle,
                    'shelf': shelf,
                    'level': level,
                    'section': section,
                    'formatted': location_str
                },
                'location_qr': location_qr,
                'message': f"✅ {product_name} ubicado en {location_str}"
            }
            
        except Exception as e:
            logger.error(f"Error assigning location: {e}")
            return {'success': False, 'error': str(e)}
    
    def _generate_location_qr(self, aisle: str, shelf: str, 
                               level: int, branch_id: int) -> str:
        """Genera código QR único para ubicación."""
        location_string = f"{branch_id}-{aisle}-{shelf}-{level}"
        return f"BIN-{hashlib.sha256(location_string.encode()).hexdigest()[:8].upper()}"
    
    def _format_location(self, aisle: str, shelf: str, 
                          level: int, section: str = None) -> str:
        """Formatea ubicación legible."""
        loc = f"Pasillo {aisle}, Estante {shelf}, Nivel {level}"
        if section:
            loc += f" ({section})"
        return loc
    
    def get_product_location(self, product_id: int, 
                              branch_id: int = None) -> Optional[Dict[str, Any]]:
        """
        Obtiene la ubicación de un producto.
        
        Returns:
            Dict con ubicación o None si no tiene asignada
        """
        params = [product_id]
        branch_filter = ""
        if branch_id:
            branch_filter = "AND bl.branch_id = %s"
            params.append(branch_id)

        # nosec B608 - branch_filter is hardcoded "AND bl.branch_id = %s" string, not user input
        result = list(self.core.db.execute_query(f"""
            SELECT bl.*, p.name, p.sku, p.stock
            FROM bin_locations bl
            JOIN products p ON bl.product_id = p.id
            WHERE bl.product_id = %s {branch_filter}
        """, tuple(params)))
        
        if not result:
            return None
        
        loc = dict(result[0])
        
        return {
            'product_id': loc['product_id'],
            'product_name': loc['name'],
            'product_sku': loc['sku'],
            'stock': loc['stock'],
            'location': {
                'aisle': loc['aisle'],
                'shelf': loc['shelf'],
                'level': loc['level'],
                'section': loc.get('section'),
                'formatted': self._format_location(
                    loc['aisle'], loc['shelf'], loc['level'], loc.get('section')
                )
            },
            'location_qr': loc['location_qr'],
            'last_placed_at': loc['last_placed_at'],
            'placed_by': loc['placed_by']
        }
    
    def scan_placement(self, product_barcode: str, 
                       location_qr: str,
                       placed_by: str = None) -> Dict[str, Any]:
        """
        Procesa escaneo de colocación: producto + ubicación QR.
        
        Flujo:
        1. Empleado escanea el producto
        2. Empleado escanea el QR del estante
        3. Sistema registra la ubicación
        
        Args:
            product_barcode: Código de barras del producto
            location_qr: QR del estante escaneado
            placed_by: Usuario que coloca
        """
        # Buscar producto por barcode/sku
        product = list(self.core.db.execute_query("""
            SELECT id, name, sku FROM products 
            WHERE barcode = %s OR sku = %s
        """, (product_barcode, product_barcode)))
        
        if not product:
            return {
                'success': False,
                'error': f'Producto no encontrado: {product_barcode}'
            }
        
        product = dict(product[0])
        
        # Buscar ubicación existente con ese QR
        existing = list(self.core.db.execute_query("""
            SELECT aisle, shelf, level, section, branch_id 
            FROM bin_locations 
            WHERE location_qr = %s
            LIMIT 1
        """, (location_qr,)))
        
        if existing:
            # Usar ubicación existente
            loc = dict(existing[0])
            return self.assign_location(
                product_id=product['id'],
                aisle=loc['aisle'],
                shelf=loc['shelf'],
                level=loc['level'],
                section=loc.get('section'),
                branch_id=loc['branch_id'],
                placed_by=placed_by
            )
        else:
            # QR nuevo - necesita parsear o pedir datos
            return {
                'success': False,
                'error': 'QR de ubicación no registrado. Registre primero la ubicación.',
                'product': product,
                'scanned_qr': location_qr,
                'action_needed': 'register_location'
            }
    
    def register_shelf_qr(self, location_qr: str, aisle: str, 
                          shelf: str, level: int = 1,
                          section: str = None,
                          branch_id: int = 1) -> Dict[str, Any]:
        """
        Registra un nuevo QR de estante en el sistema.
        Se usa al configurar inicialmente la bodega.
        """
        # Crear entrada temporal para registrar el QR
        try:
            self.core.db.execute_write("""
                INSERT INTO bin_locations 
                (product_id, branch_id, aisle, shelf, level, section, location_qr)
                VALUES (0, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (branch_id, aisle, shelf, level, section, location_qr))
            
            location_str = self._format_location(aisle, shelf, level, section)
            
            return {
                'success': True,
                'location_qr': location_qr,
                'location': location_str,
                'message': f"✅ QR registrado: {location_qr} → {location_str}"
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def search_with_location(self, query: str, 
                              branch_id: int = None) -> List[Dict[str, Any]]:
        """
        Búsqueda de productos incluyendo ubicación.
        
        Mejora la búsqueda estándar añadiendo:
        "Pasillo 3, Estante B, Nivel 2"
        """
        params = [f"%{query}%", f"%{query}%", f"%{query}%"]
        branch_filter = ""
        if branch_id:
            branch_filter = "AND (bl.branch_id = %s OR bl.branch_id IS NULL)"
            params.append(branch_id)

        # nosec B608 - branch_filter is hardcoded SQL fragment, not user input
        results = list(self.core.db.execute_query(f"""
            SELECT p.id, p.sku, p.name, p.price, p.stock, p.barcode,
                   bl.aisle, bl.shelf, bl.level, bl.section, bl.location_qr
            FROM products p
            LEFT JOIN bin_locations bl ON p.id = bl.product_id
            WHERE p.is_active = 1
              AND (p.name LIKE %s OR p.sku LIKE %s OR p.barcode LIKE %s)
              {branch_filter}
            ORDER BY p.name
            LIMIT 50
        """, tuple(params)))
        
        products = []
        for r in results:
            product = dict(r)
            
            # Añadir ubicación formateada
            if product.get('aisle'):
                product['location'] = {
                    'aisle': product['aisle'],
                    'shelf': product['shelf'],
                    'level': product['level'],
                    'section': product.get('section'),
                    'formatted': self._format_location(
                        product['aisle'], 
                        product['shelf'], 
                        product['level'],
                        product.get('section')
                    ),
                    'qr': product.get('location_qr')
                }
            else:
                product['location'] = None
            
            products.append(product)
        
        return products
    
    def generate_picking_route(self, product_ids: List[int],
                                branch_id: int = None) -> Dict[str, Any]:
        """
        Genera ruta de picking optimizada.
        
        Dado una lista de productos a recoger, ordena la ruta
        para minimizar tiempo de recorrido.
        
        Algoritmo simple: ordenar por pasillo → estante → nivel
        """
        if not product_ids:
            return {'success': True, 'route': [], 'message': 'Lista vacía'}
        
        placeholders = ','.join(['%s'] * len(product_ids))
        params = list(product_ids)
        
        if branch_id:
            params.append(branch_id)
        
        branch_filter = "AND bl.branch_id = %s" if branch_id else ""

        # nosec B608 - placeholders are %s literals, branch_filter is hardcoded SQL fragment
        results = list(self.core.db.execute_query(f"""
            SELECT p.id, p.sku, p.name, p.stock,
                   bl.aisle, bl.shelf, bl.level, bl.section
            FROM products p
            LEFT JOIN bin_locations bl ON p.id = bl.product_id
            WHERE p.id IN ({placeholders}) {branch_filter}
            ORDER BY bl.aisle, bl.shelf, bl.level
        """, tuple(params)))
        
        route = []
        no_location = []
        
        for idx, r in enumerate(results):
            item = dict(r)
            
            if item.get('aisle'):
                route.append({
                    'step': len(route) + 1,
                    'product_id': item['id'],
                    'product_name': item['name'],
                    'sku': item['sku'],
                    'stock': item['stock'],
                    'location': self._format_location(
                        item['aisle'], item['shelf'], item['level'], item.get('section')
                    ),
                    'aisle': item['aisle'],
                    'shelf': item['shelf'],
                    'level': item['level']
                })
            else:
                no_location.append({
                    'product_id': item['id'],
                    'product_name': item['name'],
                    'warning': 'Sin ubicación asignada'
                })
        
        return {
            'success': True,
            'route': route,
            'total_stops': len(route),
            'no_location': no_location,
            'no_location_count': len(no_location),
            'estimated_time_minutes': len(route) * 0.5,  # 30 seg por producto
            'instructions': self._build_picking_instructions(route)
        }
    
    def _build_picking_instructions(self, route: List[Dict]) -> str:
        """Genera instrucciones de picking legibles."""
        if not route:
            return "No hay productos con ubicación asignada."
        
        lines = ["📋 RUTA DE PICKING:", ""]
        
        current_aisle = None
        for item in route:
            if item['aisle'] != current_aisle:
                current_aisle = item['aisle']
                lines.append(f"📍 PASILLO {current_aisle}")
            
            lines.append(f"   {item['step']}. {item['product_name']}")
            lines.append(f"      → Estante {item['shelf']}, Nivel {item['level']}")
            lines.append("")
        
        lines.append(f"⏱️ Tiempo estimado: {len(route) * 0.5:.0f} minutos")
        
        return "\n".join(lines)
    
    def get_location_stats(self, branch_id: int = None) -> Dict[str, Any]:
        """
        Estadísticas del sistema de ubicaciones.
        """
        branch_filter = "WHERE branch_id = %s" if branch_id else ""
        params = (branch_id,) if branch_id else ()

        # Total productos con ubicación
        # nosec B608 - branch_filter is hardcoded "WHERE branch_id = %s" or empty string
        with_location = list(self.core.db.execute_query(f"""
            SELECT COUNT(DISTINCT product_id) as count
            FROM bin_locations
            {branch_filter}
        """, params))
        
        # Total productos activos
        total_products = list(self.core.db.execute_query(
            "SELECT COUNT(*) as count FROM products WHERE is_active = 1"
        ))
        
        # Distribución por pasillo
        # nosec B608 - branch_filter is hardcoded "WHERE branch_id = %s" or empty string
        by_aisle = list(self.core.db.execute_query(f"""
            SELECT aisle, COUNT(*) as count
            FROM bin_locations
            {branch_filter}
            GROUP BY aisle
            ORDER BY count DESC
        """, params))
        
        total = total_products[0]['count'] if total_products else 0
        mapped = with_location[0]['count'] if with_location else 0
        coverage = (mapped / total * 100) if total > 0 else 0
        
        return {
            'total_products': total,
            'products_with_location': mapped,
            'products_without_location': total - mapped,
            'coverage_pct': round(coverage, 1),
            'by_aisle': [dict(r) for r in by_aisle],
            'status': '✅ Buen mapeo' if coverage > 80 else '⚠️ Faltan ubicaciones'
        }

# Funciones de conveniencia
def assign_location(core, product_id, aisle, shelf, level=1):
    """Asigna ubicación rápida."""
    return BinLocationManager(core).assign_location(product_id, aisle, shelf, level)

def get_location(core, product_id):
    """Obtiene ubicación de producto."""
    return BinLocationManager(core).get_product_location(product_id)

def search_products(core, query):
    """Búsqueda con ubicaciones."""
    return BinLocationManager(core).search_with_location(query)

def generate_route(core, product_ids):
    """Genera ruta de picking."""
    return BinLocationManager(core).generate_picking_route(product_ids)
