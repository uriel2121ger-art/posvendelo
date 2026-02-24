"""
Cerebro Contable - Algoritmo de optimización fiscal IVA/ISR
Calcula la cantidad óptima de Serie B para factura global
minimizando el pago de impuestos legalmente
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
import logging

logger = logging.getLogger(__name__)

class CerebroContable:
    """
    Motor de inteligencia fiscal para optimización de impuestos.
    Calcula el balance óptimo entre Serie A y B.
    """
    
    # Tasas RESICO 2024-2025
    RESICO_RATES = {
        25000: 0.01,      # 1.00%
        50000: 0.011,     # 1.10%
        83333.33: 0.012,  # 1.20%
        208333.33: 0.014, # 1.40%
        291666.67: 0.017, # 1.70%
        416666.67: 0.021, # 2.10%
        3500000: 0.025,   # 2.50%
    }
    
    IVA_RATE = Decimal('0.16')
    
    def __init__(self, core):
        self.core = core
    
    def analyze_fiscal_position(self, year: int = None, month: int = None) -> Dict[str, Any]:
        """
        Analiza la posición fiscal actual.
        Retorna recomendaciones de optimización.
        """
        year = year or datetime.now().year
        month = month or datetime.now().month
        
        # Obtener datos
        ingresos = self._get_ingresos(year)
        gastos = self._get_gastos_estimados(year, month)
        serie_b_pendiente = self._get_serie_b_pendiente(year, month)
        
        # Calcular IVA
        iva_cobrado = ingresos['serie_a']['iva']
        iva_pagado = gastos['iva_pagado']
        iva_neto = iva_cobrado - iva_pagado
        
        # Calcular ISR RESICO
        isr_actual = self._calcular_isr_resico(ingresos['serie_a']['subtotal'])
        
        # Calcular optimización
        optimizacion = self._calcular_optimizacion(
            iva_pagado=iva_pagado,
            serie_b_disponible=serie_b_pendiente,
            gastos_subtotal=gastos['subtotal']
        )
        
        return {
            'periodo': f'{year}-{month:02d}',
            'ingresos': ingresos,
            'gastos': gastos,
            'iva': {
                'cobrado': float(iva_cobrado),
                'pagado': float(iva_pagado),
                'neto': float(iva_neto),
                'a_pagar': float(max(iva_neto, 0)),
                'a_favor': float(abs(min(iva_neto, 0)))
            },
            'isr': {
                'base': float(ingresos['serie_a']['subtotal']),
                'tasa': self._get_tasa_resico(ingresos['serie_a']['subtotal']),
                'a_pagar': float(isr_actual)
            },
            'serie_b_pendiente': serie_b_pendiente,
            'optimizacion': optimizacion,
            'recomendaciones': self._generar_recomendaciones(
                iva_neto, isr_actual, serie_b_pendiente, optimizacion
            )
        }
    
    def _get_ingresos(self, year: int) -> Dict[str, Any]:
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
                WHERE serie = %s 
                AND EXTRACT(YEAR FROM timestamp::timestamp) = %s
                AND status = 'completed'
            """
            data = list(self.core.db.execute_query(sql, (serie, str(year))))
            if data:
                result[f'serie_{serie.lower()}'] = {
                    'subtotal': Decimal(str(data[0]['subtotal'] or 0)),
                    'iva': Decimal(str(data[0]['iva'] or 0)),
                    'total': Decimal(str(data[0]['total'] or 0)),
                    'transacciones': data[0]['transacciones']
                }
        
        return result
    
    def _get_gastos_estimados(self, year: int, month: int) -> Dict[str, Any]:
        """
        Obtiene gastos deducibles.
        Por ahora usa estimación, en producción vendría de XMLs de compras.
        """
        # TODO: Integrar con XMLIngestor para gastos reales
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
        iva_pagado = subtotal_acum * float(self.IVA_RATE)
        
        return {
            'detalle': gastos_mensuales,
            'mensual': subtotal_mensual,
            'subtotal': Decimal(str(subtotal_acum)),
            'iva_pagado': Decimal(str(iva_pagado)),
            'total': Decimal(str(subtotal_acum + iva_pagado)),
            'nota': 'Estimación. Configura gastos reales en XML Ingestor.'
        }
    
    def _get_serie_b_pendiente(self, year: int, month: int) -> Dict[str, Any]:
        """Obtiene ventas Serie B sin factura global."""
        sql = """
            SELECT 
                s.id, s.folio_visible, s.timestamp,
                s.subtotal, s.tax, s.total
            FROM sales s
            LEFT JOIN sale_cfdi_relation scr ON s.id = scr.sale_id
            WHERE s.serie = 'B'
            AND scr.id IS NULL
            AND EXTRACT(YEAR FROM s.timestamp::timestamp) = %s
            AND s.status = 'completed'
            ORDER BY s.timestamp ASC
        """
        ventas = list(self.core.db.execute_query(sql, (str(year),)))
        
        total_subtotal = sum(Decimal(str(v['subtotal'] or 0)) for v in ventas)
        total_iva = sum(Decimal(str(v['tax'] or 0)) for v in ventas)
        total = sum(Decimal(str(v['total'] or 0)) for v in ventas)
        
        return {
            'ventas': [dict(v) for v in ventas],
            'count': len(ventas),
            'subtotal': float(total_subtotal),
            'iva': float(total_iva),
            'total': float(total)
        }
    
    def _calcular_isr_resico(self, ingresos: Decimal) -> Decimal:
        """Calcula ISR según tabla RESICO."""
        tasa = self._get_tasa_resico(ingresos)
        return (ingresos * Decimal(str(tasa))).quantize(Decimal('0.01'))
    
    def _get_tasa_resico(self, ingresos: Decimal) -> float:
        """Obtiene tasa RESICO según nivel de ingresos."""
        ingresos_float = float(ingresos)
        tasa = 0.0
        
        for limite, tasa_nivel in sorted(self.RESICO_RATES.items()):
            if ingresos_float <= limite:
                return tasa_nivel
            tasa = tasa_nivel
        
        return 0.025  # Tasa máxima
    
    def _calcular_optimizacion(self, iva_pagado: Decimal, 
                                serie_b_disponible: Dict,
                                gastos_subtotal: Decimal) -> Dict[str, Any]:
        """
        Calcula la cantidad óptima de Serie B para factura global.
        Objetivo: Que el IVA de la global sea igual al IVA a favor.
        """
        iva_a_favor = iva_pagado
        
        # Buscar ventas de Serie B cuyo IVA sume aproximadamente el IVA a favor
        ventas = serie_b_disponible.get('ventas', [])
        
        seleccionadas = []
        iva_acumulado = Decimal('0')
        subtotal_acumulado = Decimal('0')
        
        for venta in ventas:
            iva_venta = Decimal(str(venta.get('tax', 0) or 0))
            
            if iva_acumulado + iva_venta <= iva_a_favor:
                seleccionadas.append(venta)
                iva_acumulado += iva_venta
                subtotal_acumulado += Decimal(str(venta.get('subtotal', 0) or 0))
            
            # Si llegamos al IVA a favor, paramos
            if iva_acumulado >= iva_a_favor * Decimal('0.95'):
                break
        
        # Calcular impacto
        iva_global = iva_acumulado
        iva_neto_despues = Decimal('0')  # IVA a favor - IVA global = 0
        
        isr_adicional = self._calcular_isr_resico(subtotal_acumulado)
        
        return {
            'ventas_seleccionadas': len(seleccionadas),
            'ids_seleccionados': [v['id'] for v in seleccionadas],
            'subtotal_global': float(subtotal_acumulado),
            'iva_global': float(iva_acumulado),
            'iva_a_favor_usado': float(min(iva_a_favor, iva_acumulado)),
            'iva_a_pagar': float(max(Decimal('0'), iva_acumulado - iva_a_favor)),
            'isr_adicional': float(isr_adicional),
            'ahorro_total': float(iva_a_favor - (iva_acumulado - iva_a_favor).quantize(Decimal('0.01'))),
            'recomendacion': f'Genera factura global por ${float(subtotal_acumulado):,.2f} para optimizar IVA'
        }
    
    def _generar_recomendaciones(self, iva_neto: Decimal, isr: Decimal, 
                                  serie_b: Dict, optimizacion: Dict) -> List[str]:
        """Genera recomendaciones fiscales automáticas."""
        recomendaciones = []
        
        # IVA
        if iva_neto > 0:
            recomendaciones.append(
                f"💰 Tienes IVA a pagar: ${float(iva_neto):,.2f}"
            )
        else:
            recomendaciones.append(
                f"✅ Tienes IVA a favor: ${float(abs(iva_neto)):,.2f}"
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
    
    def get_optimal_global_selection(self, max_iva: float = None) -> List[int]:
        """
        Retorna IDs de ventas Serie B para factura global óptima.
        """
        analysis = self.analyze_fiscal_position()
        return analysis['optimizacion'].get('ids_seleccionados', [])
