from pathlib import Path

"""
Federation Dashboard - Vista consolidada de todas las sucursales
El "Pentágono" que controla el imperio desde la PWA
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import os
import secrets
import sys

logger = logging.getLogger(__name__)


def _get_federation_auth_code() -> str:
    """
    Obtiene el código de autorización para operaciones federadas.
    FIX 2026-02-01: Eliminado hardcoding de credenciales.
    """
    code = os.environ.get('TITAN_FEDERATION_CODE')
    if code and len(code) >= 8:
        return code

    config_path = os.path.expanduser('~/.titan/federation.key')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                code = f.read().strip()
                if code and len(code) >= 8:
                    return code
        except Exception as e:
            logger.error(f"Error reading federation key: {e}")

    logger.warning("TITAN_FEDERATION_CODE not configured")
    return ""

class FederationDashboard:
    """
    Dashboard federado para múltiples sucursales y RFCs.
    Proporciona la "Vista de Dios" sobre todo el imperio.
    """

    RESICO_LIMIT = Decimal('3500000')
    TAX_RATE = Decimal('0.16')       # 16% IVA México
    TAX_FACTOR = Decimal('1.16')     # 1 + TAX_RATE for dividing out IVA
    ISR_RESICO_RATE = Decimal('0.0125')  # ISR RESICO 1.25%
    
    def __init__(self, core):
        self.core = core
    
    # ==========================================================================
    # DASHBOARD OPERATIVO (Real-Time)
    # ==========================================================================
    
    def get_operational_dashboard(self) -> Dict[str, Any]:
        """Dashboard operativo en tiempo real de todas las sucursales."""
        if not self.core.db:
            logger.warning("Database not available for operational dashboard")
            return {'timestamp': datetime.now().isoformat(), 'branches': [], 'totals': {}}

        today = datetime.now().strftime('%Y-%m-%d')

        # Obtener todas las sucursales (usar default si no hay columna is_active)
        try:
            branches = list(self.core.db.execute_query(
                "SELECT id, name, address FROM branches"
            ))
        except Exception:
            branches = [{'id': 1, 'name': 'Principal', 'address': ''}]
        
        branch_data = []
        total_sales = 0
        total_cash = 0
        
        for branch in branches:
            b_id = branch['id']
            
            # Ventas de hoy
            try:
                sales = list(self.core.db.execute_query(
                    """SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total
                       FROM sales WHERE timestamp::date = %s
                       AND status = 'completed'""",
                    (today,)
                ))
            except Exception:
                sales = [{'count': 0, 'total': 0}]
            
            # Cajas abiertas
            try:
                open_registers = list(self.core.db.execute_query(
                    """SELECT id as pos_id, initial_cash as fondo_inicial
                       FROM turns WHERE status = 'open'"""
                ))
            except Exception:
                open_registers = []
            
            # Stock crítico
            try:
                low_stock = list(self.core.db.execute_query(
                    """SELECT COUNT(*) as count FROM products 
                       WHERE stock <= min_stock AND is_active = 1"""
                ))
            except Exception:
                low_stock = [{'count': 0}]
            
            branch_total = float(sales[0].get('total') or 0) if sales and len(sales) > 0 and sales[0] else 0
            total_sales += branch_total

            branch_data.append({
                'id': b_id,
                'name': branch['name'],
                'sales_count': sales[0].get('count', 0) if sales and len(sales) > 0 and sales[0] else 0,
                'sales_total': branch_total,
                'open_registers': len(open_registers),
                'registers': [{
                    'pos_id': r['pos_id'],
                    'cash': float(r.get('fondo_inicial') or 0)
                } for r in open_registers],
                'low_stock_count': low_stock[0].get('count', 0) if low_stock and len(low_stock) > 0 and low_stock[0] else 0,
                'status': 'active' if open_registers else 'closed'
            })
            
            for reg in open_registers:
                total_cash += float(reg.get('fondo_inicial') or 0)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'branches': branch_data,
            'totals': {
                'branches_active': len([b for b in branch_data if b['status'] == 'active']),
                'total_sales': total_sales,
                'total_cash_in_registers': total_cash,
                'low_stock_alerts': sum(b['low_stock_count'] for b in branch_data)
            }
        }
    
    def get_inventory_alerts(self) -> List[Dict]:
        """Alertas de inventario critico."""
        if not self.core.db:
            logger.warning("Database not available for inventory alerts")
            return []

        sql = """
            SELECT p.sku, p.name, p.stock, p.min_stock
            FROM products p
            WHERE p.stock <= p.min_stock AND p.is_active = 1
            ORDER BY (p.stock - p.min_stock) ASC
            LIMIT 50
        """
        try:
            return list(self.core.db.execute_query(sql))
        except Exception:
            return []
    
    def get_transfer_opportunities(self) -> List[Dict]:
        """Detecta oportunidades de traspaso entre sucursales."""
        if not self.core.db:
            logger.warning("Database not available for transfer opportunities")
            return []

        # Productos con exceso en una sucursal y falta en otra
        sql = """
            SELECT p1.sku, p1.name,
                   p1.branch_id as from_branch, b1.name as from_name,
                   p1.stock as from_stock,
                   p2.branch_id as to_branch, b2.name as to_name,
                   p2.stock as to_stock, p2.min_stock
            FROM products p1
            JOIN products p2 ON p1.sku = p2.sku AND p1.branch_id != p2.branch_id
            JOIN branches b1 ON p1.branch_id = b1.id
            JOIN branches b2 ON p2.branch_id = b2.id
            WHERE p1.stock > p1.min_stock * 3
              AND p2.stock <= p2.min_stock
            LIMIT 20
        """
        opportunities = list(self.core.db.execute_query(sql))
        
        return [{
            'sku': o['sku'],
            'product': o['name'],
            'from': {'branch_id': o['from_branch'], 'name': o['from_name'], 'stock': o['from_stock']},
            'to': {'branch_id': o['to_branch'], 'name': o['to_name'], 'stock': o['to_stock']},
            'suggested_quantity': min(
                o['from_stock'] - o['min_stock'],  # No dejar en cero el origen
                o['min_stock'] * 2 - o['to_stock']  # Llevar a 2x mínimo el destino
            )
        } for o in opportunities]
    
    # ==========================================================================
    # DASHBOARD DE INTELIGENCIA FISCAL (RESICO Global)
    # ==========================================================================
    
    def get_fiscal_intelligence(self) -> Dict[str, Any]:
        """Dashboard de inteligencia fiscal consolidado."""
        if not self.core.db:
            logger.warning("Database not available for fiscal intelligence")
            return {'year': datetime.now().year, 'rfcs': [], 'totals': {}, 'recommendation': {}}

        year = datetime.now().year

        # Obtener todos los RFCs/emisores
        emitters = list(self.core.db.execute_query(
            "SELECT id, rfc, razon_social, is_active FROM emitters WHERE is_active = 1"
        ))
        
        rfc_data = []
        total_facturado = Decimal('0')
        
        for emitter in emitters:
            # Facturado por este RFC (Serie A)
            sql = """
                SELECT COALESCE(SUM(s.total), 0) as total
                FROM sales s
                JOIN cfdis c ON s.id = c.sale_id
                WHERE c.emitter_rfc = %s 
                AND EXTRACT(YEAR FROM s.timestamp::timestamp) = %s
                AND s.status = 'completed'
            """
            result = list(self.core.db.execute_query(sql, (emitter['rfc'], str(year))))
            facturado = Decimal(str(result[0]['total'] or 0)) if result else Decimal('0')
            
            # También contar Serie A directa (sin CFDI generado aún)
            sql_direct = """
                SELECT COALESCE(SUM(total), 0) as total
                FROM sales
                WHERE serie = 'A' AND rfc_emisor = %s
                AND EXTRACT(YEAR FROM timestamp::timestamp) = %s
                AND status = 'completed'
            """
            try:
                result_direct = list(self.core.db.execute_query(sql_direct, (emitter['rfc'], str(year))))
                if result_direct:
                    facturado += Decimal(str(result_direct[0]['total'] or 0))
            except Exception:
                pass
            
            restante = self.RESICO_LIMIT - facturado
            porcentaje = (facturado / self.RESICO_LIMIT) * 100
            
            status = 'GREEN'
            if porcentaje >= 90:
                status = 'RED'
            elif porcentaje >= 70:
                status = 'YELLOW'
            
            rfc_data.append({
                'rfc': emitter['rfc'],
                'razon_social': emitter['razon_social'],
                'facturado': float(facturado),
                'limite': float(self.RESICO_LIMIT),
                'restante': float(restante),
                'porcentaje': round(float(porcentaje), 2),
                'status': status
            })
            
            total_facturado += facturado
        
        # Ordenar por porcentaje usado
        rfc_data.sort(key=lambda x: x['porcentaje'], reverse=True)
        
        # Generar recomendación
        recommendation = self._generate_fiscal_recommendation(rfc_data)
        
        return {
            'year': year,
            'rfcs': rfc_data,
            'totals': {
                'total_facturado': float(total_facturado),
                'capacidad_total': float(self.RESICO_LIMIT * len(emitters)),
                'capacidad_usada': round(
                    float(total_facturado / (self.RESICO_LIMIT * len(emitters))) * 100, 2
                ) if emitters else 0
            },
            'recommendation': recommendation
        }
    
    def _generate_fiscal_recommendation(self, rfc_data: List[Dict]) -> Dict:
        """Genera recomendación de flujo fiscal."""
        if not rfc_data:
            return {'action': 'none', 'message': 'No hay RFCs configurados'}
        
        # Encontrar RFC más cargado y menos cargado
        most_loaded = max(rfc_data, key=lambda x: x['porcentaje'])
        least_loaded = min(rfc_data, key=lambda x: x['porcentaje'])
        
        if most_loaded['status'] == 'RED':
            return {
                'action': 'urgent_redirect',
                'from_rfc': most_loaded['rfc'][:4] + '***',
                'to_rfc': least_loaded['rfc'][:4] + '***',
                'message': f"URGENTE: Desviar toda la facturación al RFC {least_loaded['rfc'][:4]}*** inmediatamente"
            }
        
        if most_loaded['status'] == 'YELLOW':
            diff = most_loaded['porcentaje'] - least_loaded['porcentaje']
            if diff > 20:
                return {
                    'action': 'balance',
                    'from_rfc': most_loaded['rfc'][:4] + '***',
                    'to_rfc': least_loaded['rfc'][:4] + '***',
                    'message': f"Recomendado: Balancear facturación hacia RFC {least_loaded['rfc'][:4]}*** (diferencia de {diff:.0f}%)"
                }
        
        return {
            'action': 'maintain',
            'message': 'Distribución de RFCs equilibrada. Mantener operación actual.'
        }
    
    # ==========================================================================
    # DASHBOARD DE RIQUEZA REAL (Serie B + Utilidad)
    # ==========================================================================
    
    def get_wealth_dashboard(self) -> Dict[str, Any]:
        """Dashboard de riqueza real - La verdad absoluta."""
        if not self.core.db:
            logger.warning("Database not available for wealth dashboard")
            return {'timestamp': datetime.now().isoformat(), 'ingresos': {}, 'utilidad': {}, 'extracciones': {}, 'extraction_calculator': {}}

        year = datetime.now().year

        # Total Serie B
        sql_b = """
            SELECT COALESCE(SUM(total), 0) as total
            FROM sales
            WHERE serie = 'B' AND EXTRACT(YEAR FROM timestamp::timestamp) = %s
            AND status = 'completed'
        """
        try:
            result_b = list(self.core.db.execute_query(sql_b, (str(year),)))
            total_serie_b = float(result_b[0]['total'] or 0)
        except Exception:
            total_serie_b = 0
        
        # Total Serie A
        sql_a = """
            SELECT COALESCE(SUM(total), 0) as total
            FROM sales
            WHERE serie = 'A' AND EXTRACT(YEAR FROM timestamp::timestamp) = %s
            AND status = 'completed'
        """
        result_a = list(self.core.db.execute_query(sql_a, (year,)))
        total_serie_a = float(result_a[0]['total'] or 0) if result_a else 0
        
        # Extracciones realizadas
        sql_ext = """
            SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count
            FROM cash_extractions
            WHERE EXTRACT(YEAR FROM extraction_date::date) = %s
        """
        extractions = list(self.core.db.execute_query(sql_ext, (year,)))
        total_extracted = float(extractions[0]['total'] or 0) if extractions else 0
        
        # Cálculos
        ingresos_total = total_serie_a + total_serie_b
        margen_estimado = 0.20  # 20% margen promedio
        utilidad_bruta = ingresos_total * margen_estimado
        
        # Impuestos estimados (solo sobre Serie A) - using Decimal for precision
        total_serie_a_dec = Decimal(str(total_serie_a))
        isr_estimado = float((total_serie_a_dec * self.ISR_RESICO_RATE).quantize(Decimal('0.01')))
        subtotal_a = total_serie_a_dec / self.TAX_FACTOR
        iva_estimado = float((subtotal_a * self.TAX_RATE).quantize(Decimal('0.01')))
        
        utilidad_neta = utilidad_bruta - isr_estimado
        disponible = utilidad_neta - total_extracted
        
        # Calcular extracción segura recomendada
        extraction_calc = self._calculate_safe_extraction(disponible, total_extracted)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'ingresos': {
                'serie_a': total_serie_a,
                'serie_b': total_serie_b,
                'total': ingresos_total
            },
            'utilidad': {
                'bruta': utilidad_bruta,
                'isr_estimado': isr_estimado,
                'neta': utilidad_neta
            },
            'extracciones': {
                'total_extraido': total_extracted,
                'operaciones': extractions[0]['count'] if extractions else 0,
                'disponible': disponible
            },
            'extraction_calculator': extraction_calc
        }
    
    def _calculate_safe_extraction(self, disponible: float, ya_extraido: float) -> Dict:
        """Calcula extracción segura con contratos de donación."""
        # Límite mensual recomendado
        monthly_limit = 50000  # $50k MXN por persona por mes
        
        # Personas relacionadas disponibles
        try:
            personas = list(self.core.db.execute_query(
                "SELECT id, name, relationship FROM related_persons WHERE is_active = 1"
            ))
        except Exception:
            personas = []
        
        personas_count = len(personas) or 1
        capacidad_mensual = monthly_limit * personas_count
        
        # Extracción recomendada hoy
        if disponible <= 0:
            return {
                'recommended_today': 0,
                'message': 'No hay fondos disponibles para extracción',
                'contracts_needed': 0
            }
        
        extraction_today = min(disponible, capacidad_mensual / 4)  # Semanal
        
        # Distribuir entre personas
        contracts = []
        remaining = extraction_today
        for p in personas:
            amount = min(remaining, monthly_limit / 4)
            if amount > 0:
                contracts.append({
                    'person': p['name'],
                    'amount': round(amount, 2),
                    'relationship': p['relationship']
                })
                remaining -= amount
        
        return {
            'recommended_today': round(extraction_today, 2),
            'contracts_needed': len(contracts),
            'contracts': contracts,
            'personas_available': personas_count,
            'monthly_capacity': capacidad_mensual,
            'message': f"Puedes extraer ${extraction_today:,.2f} con {len(contracts)} contratos de donación"
        }
    
    # ==========================================================================
    # GESTIÓN DE TRASPASOS
    # ==========================================================================
    
    def create_transfer(self, from_branch: int, to_branch: int,
                       items: List[Dict]) -> Dict[str, Any]:
        """Crea un traspaso entre sucursales."""
        if not self.core.db:
            logger.warning("Database not available for create transfer")
            return {'success': False, 'error': 'Database not available'}

        transfer_id = datetime.now().strftime('%Y%m%d%H%M%S')

        # Validar stock en origen
        for item in items:
            stock = list(self.core.db.execute_query(
                "SELECT stock FROM products WHERE sku = %s AND branch_id = %s",
                (item['sku'], from_branch)
            ))
            if not stock or stock[0]['stock'] < item['quantity']:
                return {
                    'success': False,
                    'error': f"Stock insuficiente de {item['sku']} en sucursal origen"
                }
        
        # Ejecutar traspaso (Parte A Fase 1.4: registrar movimientos para delta sync)
        for item in items:
            qty, sku = item['quantity'], item['sku']
            # Reducir origen
            self.core.db.execute_write(
                "UPDATE products SET stock = stock - %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE sku = %s AND branch_id = %s",
                (qty, sku, from_branch)
            )
            try:
                self.core.db.execute_write(
                    """INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                       VALUES ((SELECT id FROM products WHERE sku = %s AND branch_id = %s LIMIT 1), 'OUT', 'federation_transfer', %s, %s, 'federation_transfer', NOW(), 0)""",
                    (sku, from_branch, -qty, f"Traspaso a sucursal {to_branch}")
                )
            except Exception as e:
                logger.debug("federation_dashboard movement OUT: %s", e)

            # Aumentar destino
            self.core.db.execute_write(
                "UPDATE products SET stock = stock + %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE sku = %s AND branch_id = %s",
                (qty, sku, to_branch)
            )
            try:
                self.core.db.execute_write(
                    """INSERT INTO inventory_movements (product_id, movement_type, type, quantity, reason, reference_type, timestamp, synced)
                       VALUES ((SELECT id FROM products WHERE sku = %s AND branch_id = %s LIMIT 1), 'IN', 'federation_transfer', %s, %s, 'federation_transfer', NOW(), 0)""",
                    (sku, to_branch, qty, f"Traspaso desde sucursal {from_branch}")
                )
            except Exception as e:
                logger.debug("federation_dashboard movement IN: %s", e)
        
        # Registrar traspaso
        self.core.db.execute_write(
            """INSERT INTO inventory_transfers 
               (transfer_id, from_branch, to_branch, items_count, status, created_at)
               VALUES (%s, %s, %s, %s, 'completed', %s)""",
            (transfer_id, from_branch, to_branch, len(items), datetime.now().isoformat())
        )
        
        return {
            'success': True,
            'transfer_id': transfer_id,
            'from_branch': from_branch,
            'to_branch': to_branch,
            'items_transferred': len(items)
        }
    
    # ==========================================================================
    # LOCKDOWN REMOTO POR SUCURSAL
    # ==========================================================================
    
    def remote_lockdown(self, branch_id: int) -> Dict[str, Any]:
        """Ordena lockdown remoto de una sucursal especifica."""
        if not self.core.db:
            logger.warning("Database not available for remote lockdown")
            return {'success': False, 'error': 'Database not available'}

        # Marcar sucursal en lockdown
        self.core.db.execute_write(
            "UPDATE branches SET lockdown_active = 1, lockdown_at = %s WHERE id = %s",
            (datetime.now().isoformat(), branch_id)
        )
        
        # Crear notificación para el nodo
        self.core.db.execute_write(
            """INSERT INTO sync_commands 
               (branch_id, command, payload, status, created_at)
               VALUES (%s, 'LOCKDOWN', '{}', 'pending', %s)""",
            (branch_id, datetime.now().isoformat())
        )
        
        # SECURITY: No loguear comandos de lockdown remoto
        pass
        
        return {
            'success': True,
            'branch_id': branch_id,
            'command': 'LOCKDOWN',
            'message': f'Lockdown ordenado para sucursal {branch_id}'
        }
    
    def release_lockdown(self, branch_id: int, auth_code: str) -> Dict[str, Any]:
        """Libera el lockdown de una sucursal."""
        if not self.core.db:
            logger.warning("Database not available for release lockdown")
            return {'success': False, 'error': 'Database not available'}

        # FIX 2026-02-01: Usar comparacion segura y codigo desde config
        expected_code = _get_federation_auth_code()
        if not expected_code:
            return {'success': False, 'error': 'Codigo de autorizacion no configurado'}

        if not auth_code or not secrets.compare_digest(auth_code.encode(), expected_code.encode()):
            return {'success': False, 'error': 'Codigo de autorizacion invalido'}

        self.core.db.execute_write(
            "UPDATE branches SET lockdown_active = 0 WHERE id = %s",
            (branch_id,)
        )
        
        return {
            'success': True,
            'branch_id': branch_id,
            'message': f'Lockdown liberado para sucursal {branch_id}'
        }
