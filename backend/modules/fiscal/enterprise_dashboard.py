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

logger = logging.getLogger(__name__)

def _get_federation_auth_code() -> str:
    """Obtiene el código de autorización para operaciones federadas."""
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
    """Dashboard federado para múltiples sucursales y RFCs."""

    RESICO_LIMIT = Decimal('3500000')
    TAX_RATE = Decimal('0.16')
    TAX_FACTOR = Decimal('1.16')
    ISR_RESICO_RATE = Decimal('0.0125')
    
    def __init__(self, db):
        self.db = db
    
    # ==========================================================================
    # DASHBOARD OPERATIVO (Real-Time)
    # ==========================================================================
    
    async def get_operational_dashboard(self) -> Dict[str, Any]:
        """Dashboard operativo en tiempo real de todas las sucursales."""
        today = datetime.now().strftime('%Y-%m-%d')

        try:
            branches = await self.db.fetch("SELECT id, name, address FROM branches")
        except Exception:
            branches = [{'id': 1, 'name': 'Principal', 'address': ''}]
        
        branch_data = []
        total_sales = 0
        total_cash = 0
        
        for branch in branches:
            b_id = branch['id']
            try:
                sales = await self.db.fetch("SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total FROM sales WHERE SUBSTRING(timestamp FROM 1 FOR 10) = :today AND status = 'completed'", today=today)
            except Exception:
                sales = [{'count': 0, 'total': 0}]
            
            try:
                open_registers = await self.db.fetch("SELECT id as pos_id, initial_cash as fondo_inicial FROM turns WHERE status = 'open'")
            except Exception:
                open_registers = []
            
            try:
                low_stock = await self.db.fetch("SELECT COUNT(*) as count FROM products WHERE stock <= min_stock AND is_active = 1")
            except Exception:
                low_stock = [{'count': 0}]
            
            branch_total = round(float(sales[0].get('total') or 0), 2) if sales and len(sales) > 0 and sales[0] else 0
            total_sales += branch_total

            branch_data.append({
                'id': b_id,
                'name': branch['name'],
                'sales_count': sales[0].get('count', 0) if sales and len(sales) > 0 and sales[0] else 0,
                'sales_total': branch_total,
                'open_registers': len(open_registers),
                'registers': [{'pos_id': r['pos_id'], 'cash': round(float(r.get('fondo_inicial') or 0), 2)} for r in open_registers],
                'low_stock_count': low_stock[0].get('count', 0) if low_stock and len(low_stock) > 0 and low_stock[0] else 0,
                'status': 'active' if open_registers else 'closed'
            })
            
            for reg in open_registers:
                total_cash += round(float(reg.get('fondo_inicial') or 0), 2)
        
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
    
    async def get_inventory_alerts(self) -> List[Dict]:
        try:
            rows = await self.db.fetch("SELECT sku, name, stock, min_stock FROM products WHERE stock <= min_stock AND is_active = 1 ORDER BY (stock - min_stock) ASC LIMIT 50")
            return [dict(r) for r in rows]
        except Exception:
            return []
    
    async def get_transfer_opportunities(self) -> List[Dict]:
        try:
            sql = """
                SELECT p1.sku, p1.name, p1.branch_id as from_branch, b1.name as from_name, p1.stock as from_stock,
                       p2.branch_id as to_branch, b2.name as to_name, p2.stock as to_stock, p2.min_stock
                FROM products p1
                JOIN products p2 ON p1.sku = p2.sku AND p1.branch_id != p2.branch_id
                JOIN branches b1 ON p1.branch_id = b1.id
                JOIN branches b2 ON p2.branch_id = b2.id
                WHERE p1.stock > p1.min_stock * 3 AND p2.stock <= p2.min_stock
                LIMIT 20
            """
            opts = await self.db.fetch(sql)
            return [{
                'sku': o['sku'], 'product': o['name'],
                'from': {'branch_id': o['from_branch'], 'name': o['from_name'], 'stock': o['from_stock']},
                'to': {'branch_id': o['to_branch'], 'name': o['to_name'], 'stock': o['to_stock']},
                'suggested_quantity': min(o['from_stock'] - o['min_stock'], o['min_stock'] * 2 - o['to_stock'])
            } for o in opts]
        except Exception:
            return []
    
    # ==========================================================================
    # DASHBOARD FISCAL (RESICO Global)
    # ==========================================================================
    
    async def get_fiscal_intelligence(self) -> Dict[str, Any]:
        year = str(datetime.now().year)
        try:
            emitters = await self.db.fetch("SELECT id, rfc, razon_social, is_active FROM rfc_emitters WHERE is_active = true") # We updated to rfc_emitters in Phase 4
        except Exception:
            emitters = []
        
        rfc_data = []
        total_facturado = Decimal('0')
        
        year_start = f"{year}-01-01"
        year_end = f"{int(year) + 1}-01-01"
        
        for emitter in emitters:
            result = await self.db.fetchrow("""
                SELECT COALESCE(SUM(s.total), 0) as total
                FROM sales s JOIN cfdis c ON s.id = c.sale_id
                WHERE c.emitter_rfc = :rfc AND s.timestamp >= :ys AND s.timestamp < :ye AND s.status = 'completed'
            """, rfc=emitter['rfc'], ys=year_start, ye=year_end)
            facturado = Decimal(str(result['total'] or 0)) if result else Decimal('0')
            
            restante = self.RESICO_LIMIT - facturado
            porcentaje = (facturado / self.RESICO_LIMIT) * 100
            
            status = 'RED' if porcentaje >= 90 else 'YELLOW' if porcentaje >= 70 else 'GREEN'
            
            rfc_data.append({
                'rfc': emitter['rfc'], 'razon_social': emitter['razon_social'],
                'facturado': round(float(facturado), 2), 'limite': round(float(self.RESICO_LIMIT), 2),
                'restante': round(float(restante), 2), 'porcentaje': round(float(porcentaje), 2), 'status': status
            })
            total_facturado += facturado
            
        rfc_data.sort(key=lambda x: x['porcentaje'], reverse=True)
        return {
            'year': int(year), 'rfcs': rfc_data,
            'totals': {
                'total_facturado': round(float(total_facturado), 2), 'capacidad_total': round(float(self.RESICO_LIMIT * len(emitters)), 2),
                'capacidad_usada': round(float(total_facturado / (self.RESICO_LIMIT * len(emitters))) * 100, 2) if emitters else 0
            },
            'recommendation': self._generate_fiscal_recommendation(rfc_data)
        }
        
    def _generate_fiscal_recommendation(self, rfc_data: List[Dict]) -> Dict:
        if not rfc_data: return {'action': 'none', 'message': 'No RFCs'}
        most = max(rfc_data, key=lambda x: x['porcentaje'])
        least = min(rfc_data, key=lambda x: x['porcentaje'])
        if most['status'] == 'RED': return {'action': 'urgent_redirect', 'from_rfc': most['rfc'][:4]+'***', 'to_rfc': least['rfc'][:4]+'***', 'message': 'URGENTE desviar facturación.'}
        if most['status'] == 'YELLOW' and most['porcentaje'] - least['porcentaje'] > 20: return {'action': 'balance', 'message': 'Balance recomendado.'}
        return {'action': 'maintain', 'message': 'Distribución equilibrada.'}

    # ==========================================================================
    # DASHBOARD RIQUEZA
    # ==========================================================================
    
    async def get_wealth_dashboard(self) -> Dict[str, Any]:
        year = datetime.now().year
        year_start = f"{year}-01-01"
        year_end = f"{year + 1}-01-01"
        try:
            rb = await self.db.fetchrow("SELECT COALESCE(SUM(total), 0) as total FROM sales WHERE serie = 'B' AND timestamp >= :ys AND timestamp < :ye AND status = 'completed'", ys=year_start, ye=year_end)
            tb = round(float(rb['total'] or 0), 2) if rb else 0
            ra = await self.db.fetchrow("SELECT COALESCE(SUM(total), 0) as total FROM sales WHERE serie = 'A' AND timestamp >= :ys AND timestamp < :ye AND status = 'completed'", ys=year_start, ye=year_end)
            ta = round(float(ra['total'] or 0), 2) if ra else 0
            re = await self.db.fetchrow("SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count FROM cash_extractions WHERE extraction_date >= :ys AND extraction_date < :ye", ys=year_start, ye=year_end)
            te = round(float(re['total'] or 0), 2) if re else 0
        except Exception:
            tb = ta = te = 0
            re = {'count': 0}
            
        ingresos = ta + tb
        utilidad_bruta = ingresos * 0.20
        isr_estimado = round(float((Decimal(str(ta)) * self.ISR_RESICO_RATE).quantize(Decimal('0.01'))), 2)
        utilidad_neta = utilidad_bruta - isr_estimado
        disponible = utilidad_neta - te
        
        return {
            'timestamp': datetime.now().isoformat(),
            'ingresos': {'serie_a': ta, 'serie_b': tb, 'total': ingresos},
            'utilidad': {'bruta': utilidad_bruta, 'isr_estimado': isr_estimado, 'neta': utilidad_neta},
            'extracciones': {'total_extraido': te, 'operaciones': re['count'] if re else 0, 'disponible': disponible},
            'extraction_calculator': await self._calc_safe(disponible, te)
        }
        
    async def _calc_safe(self, disp: float, extraido: float) -> Dict:
        limit = 50000
        try:
            personas = await self.db.fetch("SELECT name, parentesco as relationship FROM related_persons WHERE is_active = 1")
        except Exception:
            personas = []
            
        pcnt = len(personas) or 1
        return {'recommended_today': min(disp, (limit * pcnt)/4) if disp > 0 else 0, 'contracts_needed': len(personas)}
    
    # ==========================================================================
    # LOCKDOWN REMOTO
    # ==========================================================================
    
    async def remote_lockdown(self, branch_id: int) -> Dict[str, Any]:
        await self.db.execute("UPDATE branches SET lockdown_active = true WHERE id = :bid", bid=branch_id)
        return {'success': True, 'branch_id': branch_id, 'message': 'Lockdown remote applied.'}
    
    async def release_lockdown(self, branch_id: int, auth_code: str) -> Dict[str, Any]:
        expected = _get_federation_auth_code()
        if not expected or not secrets.compare_digest(auth_code.encode(), expected.encode()):
            return {'success': False, 'error': 'Invalid code'}
        await self.db.execute("UPDATE branches SET lockdown_active = false WHERE id = :bid", bid=branch_id)
        return {'success': True, 'message': 'Lockdown released.'}
