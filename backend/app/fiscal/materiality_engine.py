"""
Materiality Engine - Generador de documentación de respaldo para mermas
Conforme al Art. 32-F del Código Fiscal de la Federación
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class MaterialityEngine:
    """
    Motor de generación de actas circunstanciadas para destrucción de mercancía.
    Proporciona materialidad jurídica conforme al CFF Art. 32-F.
    """
    
    def __init__(self, core):
        self.core = core
        self._setup_table()
    
    def _setup_table(self):
        """Crea tabla de registros de merma si no existe."""
        try:
            self.core.db.execute_write("""
                CREATE TABLE IF NOT EXISTS loss_records (
                    id BIGSERIAL PRIMARY KEY,
                    product_id INTEGER NOT NULL,
                    product_name TEXT,
                    product_sku TEXT,
                    quantity REAL NOT NULL,
                    unit_cost REAL,
                    total_value REAL,
                    reason TEXT NOT NULL,
                    category TEXT DEFAULT 'deterioro',
                    photo_path TEXT,
                    witness_name TEXT,
                    witness_id TEXT,
                    acta_number TEXT UNIQUE,
                    status TEXT DEFAULT 'pending',
                    authorized_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    authorized_at TEXT
                )
            """)
        except Exception as e:
            logger.error(f"Error creating loss_records table: {e}")
    
    def register_loss(self, product_id: int, quantity: float, 
                      reason: str, category: str = 'deterioro',
                      witness_name: str = None) -> Dict[str, Any]:
        """
        Registra una merma/pérdida de inventario.
        
        Args:
            product_id: ID del producto
            quantity: Cantidad perdida
            reason: Razón de la pérdida
            category: deterioro, rotura, caducidad, robo, otro
            witness_name: Nombre del testigo (cajera/encargado)
        
        Returns:
            Dict con número de acta y datos del registro
        """
        # Obtener datos del producto
        product = list(self.core.db.execute_query(
            "SELECT name, sku, price FROM products WHERE id = %s",
            (product_id,)
        ))
        
        if not product:
            return {'success': False, 'error': 'Producto no encontrado'}
        
        p = product[0]
        unit_cost = float(p['price'] or 0) * 0.7  # Estimar costo como 70% del precio
        total_value = unit_cost * quantity
        
        # Generar número de acta
        acta_number = self._generate_acta_number()
        
        # Insertar registro
        try:
            self.core.db.execute_write(
                """INSERT INTO loss_records 
                   (product_id, product_name, product_sku, quantity, 
                    unit_cost, total_value, reason, category, 
                    witness_name, acta_number, status, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)""",
                (product_id, p['name'], p['sku'], quantity,
                 unit_cost, total_value, reason, category,
                 witness_name, acta_number, datetime.now().isoformat())
            )
            
            # Actualizar stock (Parte A Fase 1.4: registrar movimiento para delta sync)
            self.core.db.execute_write(
                "UPDATE products SET stock = stock - %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (quantity, product_id)
            )
            try:
                self.core.db.execute_write(
                    """INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                       VALUES (%s, 'OUT', 'loss', %s, %s, 'loss_record', NOW(), 0)""",
                    (product_id, quantity, reason or "Merma")
                )
            except Exception as e:
                logger.debug("materiality_engine movement: %s", e)
            
            # SECURITY: No loguear registros de mermas
            pass
            
            return {
                'success': True,
                'acta_number': acta_number,
                'product': p['name'],
                'quantity': quantity,
                'total_value': total_value,
                'status': 'pending',
                'message': 'Merma registrada. Pendiente de autorización.'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _generate_acta_number(self) -> str:
        """Genera número único de acta."""
        now = datetime.now()
        count = list(self.core.db.execute_query(
            "SELECT COUNT(*) as c FROM loss_records WHERE EXTRACT(YEAR FROM created_at::timestamp) = %s",
            (str(now.year),)
        ))
        # FIX 2026-01-30: Validar que count no esté vacío antes de acceder a [0]
        seq = (count[0]['c'] or 0) + 1 if count else 1
        return f"MERMA-{now.year}-{seq:05d}"
    
    def authorize_loss(self, acta_number: str, authorized_by: str) -> Dict[str, Any]:
        """Autoriza una merma pendiente."""
        try:
            self.core.db.execute_write(
                """UPDATE loss_records 
                   SET status = 'authorized', authorized_by = %s, authorized_at = %s
                   WHERE acta_number = %s""",
                (authorized_by, datetime.now().isoformat(), acta_number)
            )
            return {'success': True, 'message': f'Acta {acta_number} autorizada'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def generate_acta_text(self, acta_number: str) -> str:
        """
        Genera el texto del acta circunstanciada conforme al CFF.
        """
        record = list(self.core.db.execute_query(
            "SELECT * FROM loss_records WHERE acta_number = %s",
            (acta_number,)
        ))
        
        if not record:
            return "Acta no encontrada"
        
        r = record[0]
        
        # Obtener datos del negocio
        config = self.core.get_app_config()
        fiscal_config = self.core.get_fiscal_config()
        
        business_name = config.get('business_name', 'COMERCIALIZADORA')
        rfc = fiscal_config.get('rfc_emisor', 'XAXX010101000')
        address = config.get('address', 'Mérida, Yucatán')
        
        fecha = datetime.fromisoformat(r['created_at']).strftime('%d de %B de %Y')
        hora = datetime.fromisoformat(r['created_at']).strftime('%H:%M')
        
        acta_text = f"""
╔══════════════════════════════════════════════════════════════════════╗
║           ACTA CIRCUNSTANCIADA DE DESTRUCCIÓN DE MERCANCÍA           ║
║                    Artículo 32-F del CFF                             ║
╠══════════════════════════════════════════════════════════════════════╣
║  Acta No.: {r['acta_number']:<56} ║
╚══════════════════════════════════════════════════════════════════════╝

DATOS DEL CONTRIBUYENTE
───────────────────────────────────────────────────────────────────────
Razón Social:    {business_name}
RFC:             {rfc}
Domicilio:       {address}

CIRCUNSTANCIAS DEL HECHO
───────────────────────────────────────────────────────────────────────
Fecha:           {fecha}
Hora:            {hora}
Ubicación:       Establecimiento comercial

MERCANCÍA AFECTADA
───────────────────────────────────────────────────────────────────────
Producto:        {r['product_name']}
SKU:             {r['product_sku']}
Cantidad:        {r['quantity']} unidades
Costo unitario:  ${r['unit_cost']:,.2f}
Valor total:     ${r['total_value']:,.2f}

CAUSA DE LA BAJA
───────────────────────────────────────────────────────────────────────
Categoría:       {r['category'].upper()}
Descripción:     {r['reason']}

DECLARACIÓN
───────────────────────────────────────────────────────────────────────
Siendo las {hora} horas del día {fecha}, se hace constar que 
el producto arriba descrito sufrió un deterioro/siniestro que impide 
su comercialización. Se procede a la baja del inventario físico para 
efectos de simetría contable y fiscal, de conformidad con lo establecido 
en el Artículo 32-F del Código Fiscal de la Federación.

La presente acta se levanta para los efectos legales a que haya lugar.

TESTIGOS Y FIRMAS
───────────────────────────────────────────────────────────────────────
Testigo:         {r.get('witness_name') or 'N/A'}

Autorizado por:  {r.get('authorized_by') or 'Pendiente'}
Estado:          {r['status'].upper()}

_______________________          _______________________
    Responsable                       Testigo

Documento generado automáticamente por el Sistema TITAN POS
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return acta_text
    
    def get_pending_losses(self) -> List[Dict]:
        """Obtiene mermas pendientes de autorización."""
        result = list(self.core.db.execute_query(
            """SELECT * FROM loss_records 
               WHERE status = 'pending' 
               ORDER BY created_at DESC"""
        ))
        return [dict(r) for r in result]
    
    def get_loss_summary(self, year: int = None) -> Dict[str, Any]:
        """Resumen de mermas del año."""
        year = year or datetime.now().year
        
        sql = """
            SELECT 
                category,
                COUNT(*) as registros,
                COALESCE(SUM(quantity), 0) as unidades,
                COALESCE(SUM(total_value), 0) as valor
            FROM loss_records
            WHERE EXTRACT(YEAR FROM created_at::timestamp) = %s
            GROUP BY category
        """
        result = list(self.core.db.execute_query(sql, (str(year),)))
        
        by_category = {r['category']: dict(r) for r in result}
        total_valor = sum(float(r['valor'] or 0) for r in result)
        
        return {
            'year': year,
            'by_category': by_category,
            'total_value': total_valor,
            'total_records': sum(r['registros'] for r in result)
        }
