"""
Cerebro Contable - Algoritmo de optimización fiscal IVA/ISR
Calcula la cantidad óptima de Serie B para factura global
minimizando el pago de impuestos legalmente
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
import logging

from modules.shared.constants import money

logger = logging.getLogger(__name__)

class CerebroContable:
    """
    Motor de inteligencia fiscal para optimización de impuestos.
    Calcula el balance óptimo entre Serie A y B.
    """
    
    # Tasas RESICO 2024-2025 (Decimal para precisión fiscal)
    RESICO_RATES = [
        (Decimal('25000'), Decimal('0.0100')),       # 1.00%
        (Decimal('50000'), Decimal('0.0110')),       # 1.10%
        (Decimal('83333.33'), Decimal('0.0120')),    # 1.20%
        (Decimal('208333.33'), Decimal('0.0140')),   # 1.40%
        (Decimal('291666.67'), Decimal('0.0170')),   # 1.70%
        (Decimal('416666.67'), Decimal('0.0210')),   # 2.10%
        (Decimal('3500000'), Decimal('0.0250')),     # 2.50%
    ]
    
    IVA_RATE = Decimal('0.16')
    
    def __init__(self, db):
        self.db = db
    
    async def analyze_fiscal_position(self, year: int = None, month: int = None) -> Dict[str, Any]:
        """
        Analiza la posición fiscal actual.
        Retorna recomendaciones de optimización.
        """
        year = year or datetime.now().year
        month = month or datetime.now().month
        
        # Obtener datos
        ingresos = await self._get_ingresos(year)
        gastos = await self._get_gastos_estimados(year, month)
        serie_b_pendiente = await self._get_serie_b_pendiente(year, month)
        
        # Calcular IVA
        iva_cobrado = ingresos['serie_a']['iva']
        iva_pagado = gastos['iva_pagado']
        iva_neto = iva_cobrado - iva_pagado
        
        # Calcular ISR RESICO
        isr_actual = await self._calcular_isr_resico(ingresos['serie_a']['subtotal'])
        
        # Calcular optimización
        optimizacion = await self._calcular_optimizacion(
            iva_pagado=iva_pagado,
            serie_b_disponible=serie_b_pendiente,
            gastos_subtotal=gastos['subtotal']
        )
        
        return {
            'periodo': f'{year}-{month:02d}',
            'ingresos': ingresos,
            'gastos': gastos,
            'iva': {
                'cobrado': money(iva_cobrado),
                'pagado': money(iva_pagado),
                'neto': money(iva_neto),
                'a_pagar': money(max(iva_neto, Decimal("0"))),
                'a_favor': money(abs(min(iva_neto, Decimal("0"))))
            },
            'isr': {
                'base': money(ingresos['serie_a']['subtotal']),
                'tasa': money(await self._get_tasa_resico(ingresos['serie_a']['subtotal']), 4),
                'a_pagar': money(isr_actual)
            },
            'serie_b_pendiente': serie_b_pendiente,
            'optimizacion': optimizacion,
            'recomendaciones': await self._generar_recomendaciones(
                iva_neto, isr_actual, serie_b_pendiente, optimizacion
            )
        }
    
    async def _get_ingresos(self, year: int) -> Dict[str, Any]:
        """Obtiene ingresos facturados por serie."""
        result = {}
        
        for serie in ['A', 'B']:
            sql = """
                SELECT 
                    COALESCE(SUM(subtotal), 0) as subtotal,
                    COALESCE(SUM(tax), 0) as iva,
                    COALESCE(SUM(total), 0) as total,
                    COUNT(*) as transacciones
                FROM sales 
                WHERE serie = :serie 
                AND EXTRACT(YEAR FROM timestamp::timestamp) = :year
                AND status = 'completed'
            """
            data = await self.db.fetch(sql, serie=serie, year=int(year))
            if data and data[0]['transacciones'] > 0:
                result[f'serie_{serie.lower()}'] = {
                    'subtotal': Decimal(str(data[0]['subtotal'] or 0)),
                    'iva': Decimal(str(data[0]['iva'] or 0)),
                    'total': Decimal(str(data[0]['total'] or 0)),
                    'transacciones': data[0]['transacciones']
                }
            else:
                result[f'serie_{serie.lower()}'] = {
                    'subtotal': Decimal('0'), 'iva': Decimal('0'),
                    'total': Decimal('0'), 'transacciones': 0
                }
        
        return result
    
    async def _get_gastos_estimados(self, year: int, month: int) -> Dict[str, Any]:
        """
        Obtiene gastos deducibles.
        Por ahora usa estimación, en producción vendría de XMLs de compras.
        """
        # Gastos estimados — cuando XMLIngestor esté activo, reemplazar con datos reales de CFDIs de compras
        meses = month
        
        # Gastos mensuales típicos de comercio
        gastos_mensuales = {
            'renta': 8000,
            'luz': 2500,
            'agua': 500,
            'internet': 800,
            'sueldos': 15000,
            'mercancia': 50000,
            'otros': 3000
        }
        
        subtotal_mensual = sum(gastos_mensuales.values())
        subtotal_acum = subtotal_mensual * meses
        iva_pagado = (Decimal(str(subtotal_acum)) * self.IVA_RATE).quantize(Decimal('0.01'))
        
        return {
            'detalle': gastos_mensuales,
            'mensual': subtotal_mensual,
            'subtotal': Decimal(str(subtotal_acum)),
            'iva_pagado': Decimal(str(iva_pagado)),
            'total': Decimal(str(subtotal_acum + iva_pagado)),
            'nota': 'Estimación. Configura gastos reales en XML Ingestor.'
        }
    
    async def _get_serie_b_pendiente(self, year: int, month: int) -> Dict[str, Any]:
        """Obtiene ventas Serie B sin factura global."""
        sql = """
            SELECT 
                s.id, s.folio_visible, s.timestamp,
                s.subtotal, s.tax, s.total,
                (SELECT COALESCE(SUM((si.price - COALESCE(p.cost, si.price * 0.5)) * si.qty), 0) 
                 FROM sale_items si 
                 LEFT JOIN products p ON si.product_id = p.id 
                 WHERE si.sale_id = s.id) as fiscal_margin
            FROM sales s
            LEFT JOIN sale_cfdi_relation scr ON s.id = scr.sale_id
            WHERE s.serie = 'B'
            AND scr.id IS NULL
            AND EXTRACT(YEAR FROM s.timestamp::timestamp) = :year
            AND s.status = 'completed'
            ORDER BY fiscal_margin DESC NULLS LAST, s.timestamp ASC
        """
        ventas = await self.db.fetch(sql, year=int(year))
        
        total_subtotal = sum(Decimal(str(v['subtotal'] or 0)) for v in ventas)
        total_iva = sum(Decimal(str(v['tax'] or 0)) for v in ventas)
        total = sum(Decimal(str(v['total'] or 0)) for v in ventas)
        
        return {
            'ventas': [dict(v) for v in ventas],
            'count': len(ventas),
            'subtotal': money(total_subtotal),
            'iva': money(total_iva),
            'total': money(total)
        }
    
    async def _calcular_isr_resico(self, ingresos: Decimal) -> Decimal:
        """Calcula ISR según tabla RESICO."""
        tasa = await self._get_tasa_resico(ingresos)
        return (ingresos * tasa).quantize(Decimal('0.01'))

    async def _get_tasa_resico(self, ingresos: Decimal) -> Decimal:
        """Obtiene tasa RESICO según nivel de ingresos."""
        for limite, tasa in self.RESICO_RATES:
            if ingresos <= limite:
                return tasa
        return Decimal('0.0250')  # Tasa máxima
    
    async def _calcular_optimizacion(self, iva_pagado: Decimal, 
                                serie_b_disponible: Dict,
                                gastos_subtotal: Decimal) -> Dict[str, Any]:
        """
        Calcula la cantidad óptima de Serie B para factura global.
        Objetivo: Que el IVA de la global sea igual al IVA a favor.
        """
        iva_a_favor = iva_pagado
        
        # Buscar ventas de Serie B cuyo IVA sume aproximadamente el IVA a favor
        # Las ventas ya vienen ordenadas por 'fiscal_margin' DESC desde SQL
        ventas = serie_b_disponible.get('ventas', [])
        
        seleccionadas = []
        iva_acumulado = Decimal('0')
        subtotal_acumulado = Decimal('0')
        
        for venta in ventas:
            iva_venta = Decimal(str(venta.get('tax', 0) or 0))
            
            # Priorizamos el mayor margen_fiscal sin exceder el IVA a favor disponible drásticamente
            if iva_acumulado + iva_venta <= iva_a_favor * Decimal('1.05'):
                seleccionadas.append(venta)
                iva_acumulado += iva_venta
                subtotal_acumulado += Decimal(str(venta.get('subtotal', 0) or 0))
            
            # Si llegamos al IVA a favor, paramos
            if iva_acumulado >= iva_a_favor * Decimal('0.95'):
                break
        
        # Calcular impacto
        iva_global = iva_acumulado
        iva_neto_despues = Decimal('0')  # IVA a favor - IVA global = 0
        
        isr_adicional = await self._calcular_isr_resico(subtotal_acumulado)
        
        return {
            'ventas_seleccionadas': len(seleccionadas),
            'ids_seleccionados': [v['id'] for v in seleccionadas],
            'subtotal_global': money(subtotal_acumulado),
            'iva_global': money(iva_acumulado),
            'iva_a_favor_usado': money(min(iva_a_favor, iva_acumulado)),
            'iva_a_pagar': money(max(Decimal('0'), iva_acumulado - iva_a_favor)),
            'isr_adicional': money(isr_adicional),
            'ahorro_total': money(iva_a_favor - (iva_acumulado - iva_a_favor)),
            'recomendacion': f'Genera factura global por ${money(subtotal_acumulado):,.2f} para optimizar IVA'
        }
    
    async def _generar_recomendaciones(self, iva_neto: Decimal, isr: Decimal, 
                                  serie_b: Dict, optimizacion: Dict) -> List[str]:
        """Genera recomendaciones fiscales automáticas."""
        recomendaciones = []
        
        # IVA
        if iva_neto > 0:
            recomendaciones.append(
                f"💰 Tienes IVA a pagar: ${float(iva_neto.quantize(Decimal('0.01'))):,.2f}"
            )
        else:
            recomendaciones.append(
                f"✅ Tienes IVA a favor: ${float(abs(iva_neto).quantize(Decimal('0.01'))):,.2f}"
            )
        
        # Serie B pendiente
        if serie_b['count'] > 0:
            recomendaciones.append(
                f"📋 {serie_b['count']} ventas Serie B pendientes: ${serie_b['total']:,.2f}"
            )
        
        # Optimización
        if optimizacion['ventas_seleccionadas'] > 0:
            recomendaciones.append(
                f"🎯 {optimizacion['recomendacion']}"
            )
            recomendaciones.append(
                f"   ISR adicional: ${optimizacion['isr_adicional']:,.2f}"
            )
        
        return recomendaciones
    
    async def get_optimal_global_selection(self, max_iva: float = None) -> List[int]:
        """
        Retorna IDs de ventas Serie B para factura global óptima.
        """
        analysis = await self.analyze_fiscal_position()
        return analysis['optimizacion'].get('ids_seleccionados', [])
