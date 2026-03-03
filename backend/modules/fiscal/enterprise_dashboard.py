"""
Federation Dashboard - Vista consolidada de todas las sucursales
El "Pentágono" que controla el imperio desde la PWA
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import logging
import os
import secrets

from ..shared.constants import RESICO_ANNUAL_LIMIT

logger = logging.getLogger(__name__)

def _get_federation_auth_code() -> str:
    """Obtiene el código de autorización para operaciones federadas (solo env vars)."""
    code = os.environ.get('TITAN_FEDERATION_CODE', '')
    if code and len(code) >= 8:
        return code
    logger.warning("TITAN_FEDERATION_CODE not configured — set via environment variable")
    return ""

class FederationDashboard:
    """Dashboard federado para múltiples sucursales y RFCs."""

    RESICO_LIMIT = RESICO_ANNUAL_LIMIT
    TAX_RATE = Decimal('0.16')
    TAX_FACTOR = Decimal('1.16')
    ISR_RESICO_RATE = Decimal('0.0125')
    
    def __init__(self, db):
        self.db = db
    
    # ==========================================================================
    # DASHBOARD OPERATIVO (Real-Time)
    # ==========================================================================
    
    async def get_operational_dashboard(self) -> Dict[str, Any]:
        """Dashboard operativo en tiempo real de todas las sucursales (batch queries)."""
        today = datetime.now().strftime('%Y-%m-%d')

        try:
            branches = await self.db.fetch("SELECT id, name, address FROM branches")
        except Exception as e:
            logger.warning("Failed to fetch branches: %s", e)
            branches = [{'id': 1, 'name': 'Principal', 'address': ''}]

        # Batch queries instead of N+1 per branch
        try:
            sales_by_branch = await self.db.fetch(
                "SELECT branch_id, COUNT(*) as count, COALESCE(SUM(total), 0) as total "
                "FROM sales WHERE SUBSTRING(timestamp FROM 1 FOR 10) = :today AND status = 'completed' "
                "GROUP BY branch_id", today=today)
        except Exception as e:
            logger.warning("Failed to fetch sales by branch: %s", e)
            sales_by_branch = []

        try:
            open_registers = await self.db.fetch(
                "SELECT id as pos_id, branch_id, initial_cash as fondo_inicial "
                "FROM turns WHERE status = 'open'")
        except Exception as e:
            logger.warning("Failed to fetch open registers: %s", e)
            open_registers = []

        try:
            low_stock_by_branch = await self.db.fetch(
                "SELECT branch_id, COUNT(*) as count FROM products "
                "WHERE stock <= min_stock AND is_active = 1 GROUP BY branch_id")
        except Exception as e:
            logger.warning("Failed to fetch low stock: %s", e)
            low_stock_by_branch = []

        # Index results by branch_id
        sales_map: Dict[int, Dict] = {int(s['branch_id']): s for s in sales_by_branch}
        regs_map: Dict[int, list] = {}
        for r in open_registers:
            regs_map.setdefault(int(r['branch_id']), []).append(r)
        stock_map: Dict[int, int] = {int(s['branch_id']): int(s['count']) for s in low_stock_by_branch}

        branch_data = []
        total_sales = Decimal('0')
        total_cash = Decimal('0')

        for branch in branches:
            b_id = int(branch['id'])
            s = sales_map.get(b_id, {'count': 0, 'total': 0})
            regs = regs_map.get(b_id, [])
            ls_count = stock_map.get(b_id, 0)

            branch_total = Decimal(str(s.get('total') or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            total_sales += branch_total

            reg_list = []
            for r in regs:
                cash = Decimal(str(r.get('fondo_inicial') or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                total_cash += cash
                reg_list.append({'pos_id': r['pos_id'], 'cash': float(cash)})

            branch_data.append({
                'id': b_id, 'name': branch['name'],
                'sales_count': int(s.get('count', 0)),
                'sales_total': float(branch_total),
                'open_registers': len(regs),
                'registers': reg_list,
                'low_stock_count': ls_count,
                'status': 'active' if regs else 'closed'
            })

        return {
            'timestamp': datetime.now().isoformat(),
            'branches': branch_data,
            'totals': {
                'branches_active': len([b for b in branch_data if b['status'] == 'active']),
                'total_sales': float(total_sales),
                'total_cash_in_registers': float(total_cash),
                'low_stock_alerts': sum(b['low_stock_count'] for b in branch_data)
            }
        }
    
    async def get_inventory_alerts(self) -> List[Dict]:
        try:
            rows = await self.db.fetch("SELECT sku, name, stock, min_stock FROM products WHERE stock <= min_stock AND is_active = 1 ORDER BY (stock - min_stock) ASC LIMIT 50")
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning("Failed to fetch inventory alerts: %s", e)
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
        except Exception as e:
            logger.warning("Failed to fetch transfer opportunities: %s", e)
            return []
    
    # ==========================================================================
    # DASHBOARD FISCAL (RESICO Global)
    # ==========================================================================
    
    async def get_fiscal_intelligence(self) -> Dict[str, Any]:
        year = str(datetime.now().year)
        try:
            emitters = await self.db.fetch("SELECT id, rfc, razon_social, is_active FROM rfc_emitters WHERE is_active = true") # We updated to rfc_emitters in Phase 4
        except Exception as e:
            logger.warning("Failed to fetch emitters: %s", e)
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
                'facturado': float(facturado.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
                'limite': float(self.RESICO_LIMIT),
                'restante': float(restante.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
                'porcentaje': float(porcentaje.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
                'status': status
            })
            total_facturado += facturado
            
        rfc_data.sort(key=lambda x: x['porcentaje'], reverse=True)
        return {
            'year': int(year), 'rfcs': rfc_data,
            'totals': {
                'total_facturado': float(total_facturado.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
                'capacidad_total': float((self.RESICO_LIMIT * len(emitters)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
                'capacidad_usada': float(((total_facturado / (self.RESICO_LIMIT * len(emitters))) * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)) if emitters else 0
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
            tb = Decimal(str(rb['total'] or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if rb else Decimal('0')
            ra = await self.db.fetchrow("SELECT COALESCE(SUM(total), 0) as total FROM sales WHERE serie = 'A' AND timestamp >= :ys AND timestamp < :ye AND status = 'completed'", ys=year_start, ye=year_end)
            ta = Decimal(str(ra['total'] or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if ra else Decimal('0')
            re = await self.db.fetchrow("SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count FROM cash_extractions WHERE extraction_date >= :ys AND extraction_date < :ye", ys=year_start, ye=year_end)
            te = Decimal(str(re['total'] or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if re else Decimal('0')
        except Exception as e:
            logger.warning("Failed to fetch wealth data: %s", e)
            tb = ta = te = Decimal('0')
            re = {'count': 0}

        ingresos = ta + tb
        utilidad_bruta = (ingresos * Decimal('0.20')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        isr_estimado = (ta * self.ISR_RESICO_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        utilidad_neta = utilidad_bruta - isr_estimado
        disponible = utilidad_neta - te

        return {
            'timestamp': datetime.now().isoformat(),
            'ingresos': {'serie_a': float(ta), 'serie_b': float(tb), 'total': float(ingresos)},
            'utilidad': {'bruta': float(utilidad_bruta), 'isr_estimado': float(isr_estimado), 'neta': float(utilidad_neta)},
            'extracciones': {'total_extraido': float(te), 'operaciones': re['count'] if re else 0, 'disponible': float(disponible)},
            'extraction_calculator': await self._calc_safe(disponible, te)
        }
        
    async def _calc_safe(self, disp: Decimal, extraido: Decimal) -> Dict:
        limit = Decimal('50000')
        try:
            personas = await self.db.fetch("SELECT name, parentesco as relationship FROM related_persons WHERE is_active = 1")
        except Exception as e:
            logger.warning("Failed to fetch related persons: %s", e)
            personas = []

        pcnt = Decimal(str(len(personas) or 1))
        recommended = min(disp, (limit * pcnt) / 4) if disp > 0 else Decimal('0')
        return {'recommended_today': float(recommended.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), 'contracts_needed': len(personas)}
    
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
