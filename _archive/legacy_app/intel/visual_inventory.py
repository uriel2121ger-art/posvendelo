from pathlib import Path

"""
Visual Inventory Intelligence - Módulos de IA Visual
Incluye: Snapshot Stock-Check, Visual Triage (OCR), Inventory Tinder

Funciones:
- Comparación visual de estantes (foto referencia vs actual)
- OCR de facturas de proveedor para carga automática
- Swipe-to-Action para inventario lento
"""

from typing import Any, Dict, List, Optional
import base64
from datetime import datetime, timedelta
import hashlib
import logging
import re
import sys

logger = logging.getLogger(__name__)

class SnapshotStockCheck:
    """
    Inventario por Foto-Referencia.
    
    El Problema: Contar 14,000 piezas una por una es imposible.
    
    La Solución:
    1. Cada Bin-Location tiene una "Foto de Referencia" de cómo se ve lleno
    2. Tomas foto rápida con cel
    3. IA compara y te dice: "Estante al 30%, deberías tener 10 cajas pero veo 5"
    
    Impacto: Detectas robos/errores en 5 segundos sin tocar cajas.
    """
    
    def __init__(self, core):
        self.core = core
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Crea tablas para fotos de referencia."""
        try:
            self.core.db.execute_write("""
                CREATE TABLE IF NOT EXISTS shelf_reference_photos (
                    id BIGSERIAL PRIMARY KEY,
                    location_qr TEXT UNIQUE NOT NULL,
                    aisle TEXT NOT NULL,
                    shelf TEXT NOT NULL,
                    level INTEGER DEFAULT 1,
                    branch_id INTEGER DEFAULT 1,
                    reference_photo_path TEXT,
                    expected_units INTEGER DEFAULT 0,
                    products_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT,
                    created_by TEXT
                )
            """)
            
            self.core.db.execute_write("""
                CREATE TABLE IF NOT EXISTS shelf_audits (
                    id BIGSERIAL PRIMARY KEY,
                    location_qr TEXT NOT NULL,
                    audit_photo_path TEXT,
                    fill_level_pct INTEGER,
                    expected_units INTEGER,
                    estimated_units INTEGER,
                    discrepancy INTEGER,
                    alert_type TEXT,
                    notes TEXT,
                    audited_by TEXT,
                    audited_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
        except Exception as e:
            logger.error(f"Error creating snapshot tables: {e}")
    
    def set_reference_photo(self, location_qr: str, 
                            photo_path: str,
                            expected_units: int,
                            products: List[Dict] = None,
                            created_by: str = None) -> Dict[str, Any]:
        """
        Establece foto de referencia para una ubicación.
        
        Args:
            location_qr: QR del estante
            photo_path: Ruta a la foto de referencia
            expected_units: Unidades cuando está lleno
            products: Lista de productos en ese estante
            created_by: Usuario que toma la referencia
        """
        # Obtener datos de ubicación
        location = list(self.core.db.execute_query("""
            SELECT aisle, shelf, level, branch_id 
            FROM bin_locations 
            WHERE location_qr = %s
            LIMIT 1
        """, (location_qr,)))
        
        if not location:
            return {'success': False, 'error': 'Ubicación no encontrada'}
        
        loc = dict(location[0])
        
        import json
        products_json = json.dumps(products) if products else None
        
        try:
            self.core.db.execute_write("""
                INSERT INTO shelf_reference_photos 
                (location_qr, aisle, shelf, level, branch_id,
                 reference_photo_path, expected_units, products_json, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(location_qr) DO UPDATE SET
                    reference_photo_path = excluded.reference_photo_path,
                    expected_units = excluded.expected_units,
                    products_json = excluded.products_json,
                    updated_at = NOW()
            """, (location_qr, loc['aisle'], loc['shelf'], loc['level'],
                  loc['branch_id'], photo_path, expected_units, products_json, created_by))
            
            return {
                'success': True,
                'location_qr': location_qr,
                'location': f"Pasillo {loc['aisle']}, Estante {loc['shelf']}, Nivel {loc['level']}",
                'expected_units': expected_units,
                'message': '✅ Foto de referencia establecida'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def audit_shelf(self, location_qr: str, 
                    current_photo_path: str = None,
                    visual_fill_pct: int = None,
                    audited_by: str = None) -> Dict[str, Any]:
        """
        Realiza auditoría visual de estante.
        
        Args:
            location_qr: QR del estante
            current_photo_path: Foto actual (para comparar)
            visual_fill_pct: Porcentaje estimado de llenado (0-100)
            audited_by: Usuario que audita
            
        Returns:
            Análisis con discrepancias detectadas
        """
        # Obtener referencia
        ref = list(self.core.db.execute_query("""
            SELECT * FROM shelf_reference_photos
            WHERE location_qr = %s
        """, (location_qr,)))
        
        if not ref:
            return {
                'success': False, 
                'error': 'No hay foto de referencia para esta ubicación',
                'action_needed': 'set_reference_photo'
            }
        
        ref = dict(ref[0])
        expected = ref['expected_units']
        
        # Calcular estimado basado en % visual
        if visual_fill_pct is not None:
            estimated = int(expected * visual_fill_pct / 100)
        else:
            # Si no hay %, usar ventas para estimar
            estimated = self._estimate_from_sales(location_qr, expected)
        
        discrepancy = expected - estimated
        discrepancy_pct = (discrepancy / expected * 100) if expected > 0 else 0
        
        # Determinar tipo de alerta
        alert_type = None
        if discrepancy_pct > 50:
            alert_type = 'CRITICAL'
        elif discrepancy_pct > 25:
            alert_type = 'WARNING'
        elif discrepancy_pct > 10:
            alert_type = 'INFO'
        
        # Guardar auditoría
        self.core.db.execute_write("""
            INSERT INTO shelf_audits 
            (location_qr, audit_photo_path, fill_level_pct, 
             expected_units, estimated_units, discrepancy, 
             alert_type, audited_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (location_qr, current_photo_path, visual_fill_pct,
              expected, estimated, discrepancy, alert_type, audited_by))
        
        # Construir narrativa
        narrative = self._build_audit_narrative(
            ref['aisle'], ref['shelf'], ref['level'],
            visual_fill_pct, expected, estimated, discrepancy
        )
        
        return {
            'success': True,
            'location': f"Pasillo {ref['aisle']}, Estante {ref['shelf']}, Nivel {ref['level']}",
            'fill_level_pct': visual_fill_pct,
            'expected_units': expected,
            'estimated_units': estimated,
            'discrepancy': discrepancy,
            'discrepancy_pct': round(discrepancy_pct, 1),
            'alert_type': alert_type,
            'narrative': narrative,
            'reference_photo': ref['reference_photo_path'],
            'current_photo': current_photo_path
        }
    
    def _estimate_from_sales(self, location_qr: str, expected: int) -> int:
        """Estima unidades restantes basado en ventas recientes."""
        # Obtener productos en esa ubicación
        products = list(self.core.db.execute_query("""
            SELECT bl.product_id, p.stock
            FROM bin_locations bl
            JOIN products p ON bl.product_id = p.id
            WHERE bl.location_qr = %s
        """, (location_qr,)))
        
        if products:
            current_stock = sum(p['stock'] or 0 for p in products)
            return min(current_stock, expected)
        
        return expected  # Si no hay datos, asumir lleno
    
    def _build_audit_narrative(self, aisle, shelf, level, 
                                fill_pct, expected, estimated, discrepancy) -> str:
        """Construye narrativa de auditoría al estilo 'Mano'."""
        location = f"Pasillo {aisle}, Estante {shelf}, Nivel {level}"
        
        if fill_pct is not None:
            lines = [f"Mano, ese estante ({location}) se ve al {fill_pct}%."]
        else:
            lines = [f"Mano, revisé el estante {location}."]
        
        lines.append(f"Según ventas deberías tener {expected} unidades,")
        lines.append(f"pero visualmente parece que hay {estimated}.")
        
        if discrepancy > expected * 0.25:
            lines.append(f"⚠️ Hay una fuga de {discrepancy} unidades. Revisa físicamente.")
        elif discrepancy > 0:
            lines.append(f"ℹ️ Diferencia menor de {discrepancy} unidades.")
        else:
            lines.append("✅ El stock parece cuadrar.")
        
        return " ".join(lines)
    
    def get_shelves_needing_audit(self, days_since: int = 7) -> List[Dict]:
        """Obtiene estantes que necesitan auditoría."""
        cutoff = (datetime.now() - timedelta(days=days_since)).isoformat()
        
        result = list(self.core.db.execute_query("""
            SELECT srp.*, 
                   MAX(sa.audited_at) as last_audit,
                   sa.fill_level_pct as last_fill_pct
            FROM shelf_reference_photos srp
            LEFT JOIN shelf_audits sa ON srp.location_qr = sa.location_qr
            GROUP BY srp.location_qr
            HAVING last_audit IS NULL OR last_audit < %s
            ORDER BY last_audit ASC
            LIMIT 20
        """, (cutoff,)))
        
        return [dict(r) for r in result]

class VisualTriage:
    """
    OCR de Facturas de Proveedor.
    
    El Problema: Capturar factura de 100 productos a mano genera errores.
    
    La Solución:
    1. Tomar foto de la factura del proveedor
    2. IA lee los productos con OCR
    3. Busca SKUs en los 14,000 registros
    4. Carga stock automáticamente
    
    Impacto: De 20 minutos de captura a 30 segundos de validación.
    """
    
    def __init__(self, core):
        self.core = core
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Crea tabla para historial de OCR."""
        try:
            self.core.db.execute_write("""
                CREATE TABLE IF NOT EXISTS invoice_ocr_history (
                    id BIGSERIAL PRIMARY KEY,
                    invoice_photo_path TEXT,
                    supplier_name TEXT,
                    invoice_number TEXT,
                    raw_ocr_text TEXT,
                    items_detected INTEGER DEFAULT 0,
                    items_matched INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    processed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    processed_by TEXT,
                    purchase_id INTEGER
                )
            """)
        except Exception as e:
            logger.error(f"Error creating OCR table: {e}")
    
    def process_invoice_text(self, ocr_text: str,
                              supplier_name: str = None,
                              invoice_number: str = None,
                              processed_by: str = None) -> Dict[str, Any]:
        """
        Procesa texto de factura (después del OCR).
        
        En producción, el OCR se haría con Tesseract o servicio de cloud.
        Aquí procesamos el texto ya extraído.
        
        Args:
            ocr_text: Texto extraído por OCR
            supplier_name: Nombre del proveedor
            invoice_number: Número de factura
            
        Returns:
            Lista de productos detectados y su match con inventario
        """
        # Parsear líneas buscando patrones de productos
        lines = ocr_text.strip().split('\n')
        items_detected = []
        
        for line in lines:
            item = self._parse_invoice_line(line)
            if item:
                items_detected.append(item)
        
        # Buscar matches en inventario
        matched_items = []
        unmatched_items = []
        
        for item in items_detected:
            match = self._find_product_match(item)
            if match:
                matched_items.append({
                    **item,
                    'product_id': match['id'],
                    'product_name': match['name'],
                    'current_stock': match['stock'],
                    'matched_by': match.get('matched_by', 'name')
                })
            else:
                unmatched_items.append(item)
        
        # Guardar historial
        try:
            self.core.db.execute_write("""
                INSERT INTO invoice_ocr_history
                (raw_ocr_text, supplier_name, invoice_number,
                 items_detected, items_matched, processed_by)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (ocr_text, supplier_name, invoice_number,
                  len(items_detected), len(matched_items), processed_by))
        # FIX 2026-02-01: Agregar logging mínimo en lugar de excepción silenciada
        except Exception as e:
            logger.debug(f"Error saving OCR history: {e}")
        
        return {
            'success': True,
            'supplier': supplier_name,
            'invoice_number': invoice_number,
            'items_detected': len(items_detected),
            'items_matched': len(matched_items),
            'items_unmatched': len(unmatched_items),
            'matched': matched_items,
            'unmatched': unmatched_items,
            'confirmation_needed': matched_items,  # Items para confirmar
            'narrative': self._build_ocr_narrative(
                len(items_detected), len(matched_items), matched_items
            )
        }
    
    def _parse_invoice_line(self, line: str) -> Optional[Dict]:
        """
        Parsea una línea de factura buscando producto y cantidad.
        
        Patrones comunes:
        - "100 BLOQUEADOR SOLAR SPF50 $45.00"
        - "BLOQUEADOR SOLAR SPF50    100    $4,500.00"
        - "SKU-12345 Producto Nombre x 100"
        """
        line = line.strip()
        if not line or len(line) < 5:
            return None
        
        # Patrón 1: Cantidad al inicio
        match = re.match(r'^(\d+)\s+(.+%s)\s+\$%s([\d,]+\.%s\d*)$', line)
        if match:
            return {
                'quantity': int(match.group(1)),
                'description': match.group(2).strip(),
                'price': float(match.group(3).replace(',', ''))
            }
        
        # Patrón 2: SKU al inicio
        match = re.match(r'^(SKU[-.]\d+|[A-Z]{2,4}-?\d+)\s+(.+?)\s+[xX]?\s*(\d+)', line, re.IGNORECASE)
        if match:
            return {
                'sku': match.group(1),
                'description': match.group(2).strip(),
                'quantity': int(match.group(3))
            }
        
        # Patrón 3: Descripción con cantidad al final
        match = re.match(r'^(.+%s)\s+(\d+)\s+\$%s([\d,]+\.%s\d*)$', line)
        if match:
            return {
                'description': match.group(1).strip(),
                'quantity': int(match.group(2)),
                'price': float(match.group(3).replace(',', ''))
            }
        
        return None
    
    def _find_product_match(self, item: Dict) -> Optional[Dict]:
        """Busca producto en inventario que coincida."""
        # Buscar por SKU si existe
        if item.get('sku'):
            result = list(self.core.db.execute_query(
                "SELECT id, name, stock FROM products WHERE sku = %s OR barcode = %s",
                (item['sku'], item['sku'])
            ))
            if result:
                return {**dict(result[0]), 'matched_by': 'sku'}
        
        # Buscar por nombre (fuzzy)
        desc = item.get('description', '')
        if desc:
            # Búsqueda exacta primero
            result = list(self.core.db.execute_query(
                "SELECT id, name, stock FROM products WHERE name = %s",
                (desc,)
            ))
            if result:
                return {**dict(result[0]), 'matched_by': 'exact_name'}
            
            # Búsqueda parcial
            words = desc.split()[:3]  # Primeras 3 palabras
            if words:
                search = '%' + '%'.join(words) + '%'
                result = list(self.core.db.execute_query(
                    "SELECT id, name, stock FROM products WHERE name LIKE %s LIMIT 1",
                    (search,)
                ))
                if result:
                    return {**dict(result[0]), 'matched_by': 'partial_name'}
        
        return None
    
    def confirm_and_load(self, items: List[Dict], 
                          serie: str = 'A',
                          processed_by: str = None) -> Dict[str, Any]:
        """
        Confirma y carga el stock de los items validados.
        
        Args:
            items: Lista de items con product_id y quantity
            serie: Serie de compra (A=fiscal, B=efectivo)
        """
        loaded = 0
        errors = []
        
        for item in items:
            try:
                product_id = item.get('product_id')
                quantity = item.get('quantity', 0)
                
                if not product_id or quantity <= 0:
                    continue
                
                # Actualizar stock (Parte A Fase 1.4: registrar movimiento para delta sync)
                self.core.db.execute_write("""
                    UPDATE products 
                    SET stock = stock + %s, synced = 0
                    WHERE id = %s
                """, (quantity, product_id))
                try:
                    self.core.db.execute_write(
                        """INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                           VALUES (%s, 'IN', 'visual_inventory', %s, %s, 'visual_inventory', NOW(), 0)""",
                        (product_id, quantity, "Carga desde visual_inventory")
                    )
                except Exception as e:
                    logger.debug("visual_inventory movement: %s", e)
                
                loaded += 1
                
            except Exception as e:
                errors.append({'item': item, 'error': str(e)})
        
        return {
            'success': True,
            'items_loaded': loaded,
            'errors': errors,
            'serie': serie,
            'message': f"✅ Cargados {loaded} productos al inventario (Serie {serie})"
        }
    
    def _build_ocr_narrative(self, detected: int, matched: int, 
                              items: List[Dict]) -> str:
        """Construye narrativa de OCR."""
        lines = [
            f"Mano, detecté {detected} productos en la factura.",
            f"Encontré {matched} en tu inventario."
        ]
        
        if matched > 0 and items:
            top = items[0]
            lines.append(f"Por ejemplo: {top.get('description', '')} x {top.get('quantity', 0)}")
        
        if detected > matched:
            lines.append(f"⚠️ {detected - matched} productos no los tengo registrados.")
        
        lines.append("¿Confirmo la carga? Tap para validar.")
        
        return " ".join(lines)

class InventoryTinder:
    """
    Swipe-to-Action para Inventario Lento.
    
    Cada domingo muestra los 20 productos que menos se movieron.
    
    Swipe →: Descuento Flash 20% en Serie B
    Swipe ←: Mover stock a sucursal que sí vende
    Swipe ↑: Marcar para devolución a proveedor
    """
    
    def __init__(self, core):
        self.core = core
    
    def get_slow_movers(self, top_n: int = 20, 
                         days: int = 7,
                         branch: str = None) -> List[Dict[str, Any]]:
        """
        Obtiene productos de menor movimiento en la semana.
        
        Returns:
            Lista de productos para "swipe" con métricas
        """
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        params = [cutoff, top_n]
        branch_filter = ""
        if branch:
            branch_filter = "AND s.branch = %s"
            params.insert(1, branch)

        # nosec B608 - branch_filter is hardcoded string "AND s.branch = %s", not user input
        result = list(self.core.db.execute_query(f"""
            SELECT p.id, p.sku, p.name, p.stock, p.cost, p.price,
                   p.department, p.category,
                   COALESCE(SUM(si.qty), 0) as weekly_sales,
                   COUNT(DISTINCT s.id) as transaction_count
            FROM products p
            LEFT JOIN sale_items si ON p.id = si.product_id
            LEFT JOIN sales s ON si.sale_id = s.id
                AND s.status = 'completed'
                AND s.timestamp::date >= %s
                {branch_filter}
            WHERE p.is_active = 1 AND p.stock > 5
            GROUP BY p.id
            ORDER BY weekly_sales ASC, p.stock DESC
            LIMIT %s
        """, tuple(params)))
        
        products = []
        for idx, r in enumerate(result):
            p = dict(r)
            stock_value = float(p['stock'] or 0) * float(p['cost'] or 0)
            
            # Calcular días en inventario estimado
            daily_sales = float(p['weekly_sales'] or 0) / 7
            days_inventory = int(p['stock'] / daily_sales) if daily_sales > 0 else 999
            
            products.append({
                'rank': idx + 1,
                'product_id': p['id'],
                'sku': p['sku'],
                'name': p['name'],
                'stock': p['stock'],
                'stock_value': round(stock_value, 2),
                'price': float(p['price'] or 0),
                'weekly_sales': float(p['weekly_sales']),
                'days_inventory': days_inventory,
                'category': p['category'] or p['department'],
                'actions': {
                    'swipe_right': f"Aplicar 20% descuento Serie B",
                    'swipe_left': f"Mover a otra sucursal",
                    'swipe_up': f"Marcar para devolución"
                }
            })
        
        return products
    
    def apply_flash_discount(self, product_id: int, 
                              discount_pct: float = 20,
                              duration_days: int = 7) -> Dict[str, Any]:
        """Aplica descuento flash (swipe derecha)."""
        try:
            product = list(self.core.db.execute_query(
                "SELECT id, name, price FROM products WHERE id = %s",
                (product_id,)
            ))
            
            if not product:
                return {'success': False, 'error': 'Producto no encontrado'}
            
            p = dict(product[0])
            original_price = float(p['price'] or 0)
            new_price = original_price * (1 - discount_pct / 100)
            
            # Guardar precio original y aplicar descuento
            # En producción, esto iría a una tabla de promociones
            self.core.db.execute_write("""
                UPDATE products 
                SET price = %s,
                    notes = COALESCE(notes, '') || ' [FLASH DISCOUNT ' || 
                            CAST(NOW() AS TEXT) || ' orig:' || %s || ']'
                WHERE id = %s
            """, (new_price, original_price, product_id))
            
            return {
                'success': True,
                'action': 'flash_discount',
                'product': p['name'],
                'original_price': original_price,
                'new_price': round(new_price, 2),
                'discount_pct': discount_pct,
                'expires': (datetime.now() + timedelta(days=duration_days)).isoformat(),
                'message': f"🔥 {p['name']} ahora a ${new_price:.2f} ({discount_pct}% off)"
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def mark_for_transfer(self, product_id: int, 
                           from_branch: str = None) -> Dict[str, Any]:
        """Marca para transferir a otra sucursal (swipe izquierda)."""
        # Usar DeadStockLiquidator para sugerencia
        from app.intel.dead_stock_liquidator import DeadStockLiquidator
        
        dsl = DeadStockLiquidator(self.core)
        return dsl.suggest_transfers(product_id)
    
    def mark_for_return(self, product_id: int,
                         reason: str = "Baja rotación") -> Dict[str, Any]:
        """Marca para devolución a proveedor (swipe arriba)."""
        try:
            product = list(self.core.db.execute_query(
                "SELECT id, name, stock, cost FROM products WHERE id = %s",
                (product_id,)
            ))
            
            if not product:
                return {'success': False, 'error': 'Producto no encontrado'}
            
            p = dict(product[0])
            
            # Marcar en notas  
            self.core.db.execute_write("""
                UPDATE products 
                SET notes = COALESCE(notes, '') || ' [RETURN REQUEST ' || 
                            CAST(NOW() AS TEXT) || ': ' || %s || ']'
                WHERE id = %s
            """, (reason, product_id))
            
            return {
                'success': True,
                'action': 'return_marked',
                'product': p['name'],
                'stock': p['stock'],
                'estimated_value': float(p['stock'] or 0) * float(p['cost'] or 0),
                'reason': reason,
                'message': f"📦 {p['name']} marcado para devolución ({p['stock']} unidades)"
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

# Funciones de conveniencia
def audit_shelf(core, location_qr, fill_pct=None):
    """Auditoría visual de estante."""
    return SnapshotStockCheck(core).audit_shelf(location_qr, visual_fill_pct=fill_pct)

def process_invoice(core, ocr_text, supplier=None):
    """Procesa factura OCR."""
    return VisualTriage(core).process_invoice_text(ocr_text, supplier)

def get_tinder_products(core, limit=20):
    """Obtiene productos para swipe."""
    return InventoryTinder(core).get_slow_movers(limit)

def swipe_action(core, product_id, direction):
    """Procesa swipe action."""
    tinder = InventoryTinder(core)
    if direction == 'right':
        return tinder.apply_flash_discount(product_id)
    elif direction == 'left':
        return tinder.mark_for_transfer(product_id)
    elif direction == 'up':
        return tinder.mark_for_return(product_id)
    return {'error': 'Dirección no válida (right/left/up)'}
