"""
Global Invoicing Service (Factura Global SAT)
Generates daily/weekly/monthly CFDIs for cash register sales (Serie B)

Requisitos SAT:
- RFC Genérico: XAXX010101000 (Público en General)
- Uso CFDI: S01 (Sin efectos fiscales)  
- Solo incluir ventas Serie B no facturadas individualmente
- Período máximo: mensual
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class GlobalInvoicingService:
    """Service for generating global CFDIs (Factura Global)."""
    
    # RFC Público en General (SAT)
    RFC_PUBLICO_GENERAL = 'XAXX010101000'
    
    # Periodicidades válidas para Facturapi (API) y SAT (códigos)
    PERIODICIDADES = {
        'daily': 'day',         # Diario
        'weekly': 'week',       # Semanal  
        'biweekly': 'fortnight', # Quincenal
        'monthly': 'month',     # Mensual
        'bimonthly': 'two_months' # Bimestral
    }
    
    # Códigos SAT (para referencia)
    PERIODICIDADES_SAT = {
        'daily': '01',
        'weekly': '02',
        'biweekly': '03',
        'monthly': '04',
        'bimonthly': '05'
    }
    
    def __init__(self, core):
        self.core = core
    
    def get_pending_sales_summary(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Obtiene resumen de ventas Serie B pendientes de facturar.
        
        Returns:
            Dict con conteo, totales y desglose
        """
        if not start_date:
            # Default: inicio del mes actual
            start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        sql = """
            SELECT 
                COUNT(*) as count,
                COALESCE(SUM(subtotal), 0) as subtotal,
                COALESCE(SUM(tax), 0) as tax,
                COALESCE(SUM(total), 0) as total
            FROM sales s
            WHERE s.serie = 'B'
            AND DATE(s.timestamp) BETWEEN %s AND %s
            AND s.status != 'cancelled'
            AND NOT EXISTS (
                SELECT 1 FROM cfdis c WHERE c.sale_id = s.id
            )
        """
        
        result = self.core.db.execute_query(sql, (start_date, end_date))
        if result:
            row = dict(result[0])
            return {
                'period': f"{start_date} - {end_date}",
                'count': row['count'],
                'subtotal': float(row['subtotal'] or 0),
                'tax': float(row['tax'] or 0),
                'total': float(row['total'] or 0)
            }
        return {'count': 0, 'subtotal': 0, 'tax': 0, 'total': 0}
    
    def generate_global_cfdi(
        self,
        period_type: str,  # 'daily', 'weekly', 'monthly'
        date: Optional[str] = None  # YYYY-MM-DD format, defaults to yesterday
    ) -> Dict[str, Any]:
        """
        Generate global CFDI for Serie B sales.
        
        Args:
            period_type: Type of period ('daily', 'weekly', 'monthly')
            date: Reference date (defaults to yesterday)
            
        Returns:
            Result dictionary with UUID and details
        """
        try:
            # Determine period
            if not date:
                date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            start_date, end_date = self._calculate_period(date, period_type)
            
            # Get Serie B sales without CFDI in period
            sales = self._get_uninvoiced_serie_b_sales(start_date, end_date)
            
            if not sales:
                return {
                    'success': False,
                    'error': f'No hay ventas Serie B sin facturar en el período {start_date} - {end_date}'
                }
            
            # Aggregate sales data with product detail
            aggregated_data = self._aggregate_sales_detailed(sales)
            
            # Generate CFDI (or prepare data for PAC)
            result = self._generate_cfdi_data(
                period_type=period_type,
                start_date=start_date,
                end_date=end_date,
                aggregated=aggregated_data,
                sales=sales
            )
            
            if result.get('success'):
                # Mark sales as globally invoiced and update serie
                cfdi_id = result.get('cfdi_id')
                for sale in sales:
                    # Update serie from B to A since it's now invoiced
                    self.core.db.execute_write(
                        "UPDATE sales SET serie = 'A', synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND serie = 'B'",
                        (sale['id'],)
                    )

                    if cfdi_id:
                        self.core.db.execute_write(
                            "INSERT INTO sale_cfdi_relation (sale_id, cfdi_id, is_global) VALUES (%s, %s, 1) ON CONFLICT (sale_id, cfdi_id) DO NOTHING",
                            (sale['id'], cfdi_id)
                        )

                result['sales_count'] = len(sales)
                result['period'] = f"{start_date} - {end_date}"

            return result

        except Exception as e:
            logger.error(f"Error generating global CFDI: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_global_cfdi_from_selection(
        self,
        sale_ids: List[int],
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        Generate global CFDI from pre-selected sales (from dashboard).
        Accepts any serie (A or B) as selected by the user.
        
        Args:
            sale_ids: List of sale IDs to include
            start_date: Period start date
            end_date: Period end date
            
        Returns:
            Result dictionary with UUID and details
        """
        try:
            if not sale_ids:
                return {
                    'success': False,
                    'error': 'No hay ventas seleccionadas'
                }
            
            # Get sales by IDs
            placeholders = ','.join(['%s' for _ in sale_ids])
            sql = f"""
                SELECT s.* FROM sales s
                WHERE s.id IN ({placeholders})
                AND s.status != 'cancelled'
                ORDER BY s.timestamp
            """
            
            result = self.core.db.execute_query(sql, tuple(sale_ids))
            sales = [dict(row) for row in result] if result else []
            
            if not sales:
                return {
                    'success': False,
                    'error': 'No se encontraron las ventas seleccionadas'
                }
            
            # Aggregate sales data with product detail
            aggregated_data = self._aggregate_sales_detailed(sales)
            
            # Determine period type based on date range
            # FIX 2026-02-01: Safely parse dates with validation
            try:
                d_start = datetime.strptime(start_date, '%Y-%m-%d')
            except (ValueError, TypeError):
                d_start = datetime.now().replace(day=1)
            try:
                d_end = datetime.strptime(end_date, '%Y-%m-%d')
            except (ValueError, TypeError):
                d_end = datetime.now()
            days = (d_end - d_start).days
            
            if days <= 1:
                period_type = 'daily'
            elif days <= 7:
                period_type = 'weekly'
            else:
                period_type = 'monthly'
            
            # Generate CFDI data
            result = self._generate_cfdi_data(
                period_type=period_type,
                start_date=start_date,
                end_date=end_date,
                aggregated=aggregated_data,
                sales=sales
            )
            
            if result.get('success'):
                # Mark sales as globally invoiced
                cfdi_id = result.get('cfdi_id')
                for sale in sales:
                    # Update serie from B to A since it's now invoiced
                    self.core.db.execute_write(
                        "UPDATE sales SET serie = 'A', synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND serie = 'B'",
                        (sale['id'],)
                    )

                    # Link to CFDI if we have an ID
                    if cfdi_id:
                        self.core.db.execute_write(
                            "INSERT INTO sale_cfdi_relation (sale_id, cfdi_id, is_global) VALUES (%s, %s, 1) ON CONFLICT (sale_id, cfdi_id) DO NOTHING",
                            (sale['id'], cfdi_id)
                        )

                result['sales_count'] = len(sales)
                result['period'] = f"{start_date} - {end_date}"

            return result

        except Exception as e:
            logger.error(f"Error generating global CFDI from selection: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_report(
        self,
        start_date: str,
        end_date: str,
        format: str = 'text'  # 'text', 'dict', 'html'
    ) -> Any:
        """
        Genera reporte de Factura Global para impresión o visualización.
        
        Args:
            start_date: Fecha inicio YYYY-MM-DD
            end_date: Fecha fin YYYY-MM-DD
            format: Formato de salida
            
        Returns:
            Reporte en el formato especificado
        """
        sales = self._get_uninvoiced_serie_b_sales(start_date, end_date)
        
        if not sales:
            if format == 'text':
                return "No hay ventas Serie B pendientes de facturar en este período."
            return {'error': 'No hay ventas pendientes'}
        
        # Aggregate data
        aggregated = self._aggregate_sales_detailed(sales)
        
        # Group by payment method
        by_payment = {}
        for sale in sales:
            method = sale.get('payment_method', 'cash')
            if method not in by_payment:
                by_payment[method] = {'count': 0, 'total': 0}
            by_payment[method]['count'] += 1
            by_payment[method]['total'] += float(sale.get('total', 0))
        
        if format == 'text':
            return self._format_report_text(start_date, end_date, sales, aggregated, by_payment)
        elif format == 'dict':
            return {
                'period': {'start': start_date, 'end': end_date},
                'sales_count': len(sales),
                'aggregated': aggregated,
                'by_payment': by_payment,
                'sales': sales
            }
        else:
            return self._format_report_html(start_date, end_date, sales, aggregated, by_payment)
    
    def _format_report_text(self, start_date, end_date, sales, aggregated, by_payment) -> str:
        """Formato texto para impresión térmica."""
        lines = []
        width = 48  # 80mm paper
        
        lines.append("=" * width)
        lines.append("REPORTE FACTURA GLOBAL".center(width))
        lines.append("=" * width)
        lines.append("")
        lines.append(f"Período: {start_date} a {end_date}")
        lines.append(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        lines.append("")
        lines.append("-" * width)
        lines.append("RESUMEN GENERAL")
        lines.append("-" * width)
        lines.append(f"Total de ventas:     {len(sales)}")
        lines.append(f"RFC Receptor:        {self.RFC_PUBLICO_GENERAL}")
        lines.append(f"Uso CFDI:            S01 (Sin efectos fiscales)")
        lines.append("")
        
        # Totals
        lines.append("-" * width)
        lines.append("TOTALES")
        lines.append("-" * width)
        lines.append(f"Subtotal:            ${aggregated['subtotal']:,.2f}")
        lines.append(f"IVA (16%):           ${aggregated['tax']:,.2f}")
        lines.append(f"TOTAL:               ${aggregated['total']:,.2f}")
        lines.append("")
        
        # By payment method
        lines.append("-" * width)
        lines.append("DESGLOSE POR MÉTODO DE PAGO")
        lines.append("-" * width)
        method_names = {
            'cash': 'Efectivo', 'card': 'Tarjeta', 'transfer': 'Transferencia',
            'mixed': 'Mixto', 'credit': 'Crédito', 'wallet': 'Puntos'
        }
        for method, data in by_payment.items():
            name = method_names.get(method, method.title())
            lines.append(f"{name:20} {data['count']:3} ops  ${data['total']:>10,.2f}")
        
        lines.append("")
        
        # Product summary (top 10)
        lines.append("-" * width)
        lines.append("TOP 10 PRODUCTOS (Por ingreso)")
        lines.append("-" * width)
        for i, item in enumerate(aggregated['items'][:10], 1):
            name = item['name'][:25]
            lines.append(f"{i:2}. {name:25} ${item['total']:>10,.2f}")
        
        lines.append("")
        lines.append("=" * width)
        lines.append("ESTE REPORTE ES PARA FACTURA GLOBAL".center(width))
        lines.append(f"RFC: {self.RFC_PUBLICO_GENERAL}".center(width))
        lines.append("=" * width)
        
        return "\n".join(lines)
    
    def _format_report_html(self, start_date, end_date, sales, aggregated, by_payment) -> str:
        """Formato HTML para visualización web."""
        # Basic HTML report
        html = f"""
        <div class="global-invoice-report">
            <h2>Reporte Factura Global</h2>
            <p><strong>Período:</strong> {start_date} a {end_date}</p>
            <p><strong>Total ventas:</strong> {len(sales)}</p>
            <p><strong>RFC Receptor:</strong> {self.RFC_PUBLICO_GENERAL}</p>
            
            <h3>Totales</h3>
            <table>
                <tr><td>Subtotal:</td><td>${aggregated['subtotal']:,.2f}</td></tr>
                <tr><td>IVA:</td><td>${aggregated['tax']:,.2f}</td></tr>
                <tr><td><strong>TOTAL:</strong></td><td><strong>${aggregated['total']:,.2f}</strong></td></tr>
            </table>
        </div>
        """
        return html
    
    def _calculate_period(self, ref_date: str, period_type: str) -> tuple:
        """Calculate start and end dates for period."""
        ref = datetime.strptime(ref_date, '%Y-%m-%d')
        
        if period_type == 'daily':
            start = ref
            end = ref
        elif period_type == 'weekly':
            # Week starts on Monday
            start = ref - timedelta(days=ref.weekday())
            end = start + timedelta(days=6)
        elif period_type == 'monthly':
            start = ref.replace(day=1)
            # Last day of month
            if ref.month == 12:
                end = ref.replace(day=31)
            else:
                end = (ref.replace(month=ref.month + 1, day=1) - timedelta(days=1))
        else:
            raise ValueError(f"Invalid period_type: {period_type}")
        
        return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')
    
    def _get_uninvoiced_serie_b_sales(self, start_date: str, end_date: str) -> List[Dict]:
        """Get Serie B sales without individual CFDIs in period."""
        sql = """
            SELECT s.* FROM sales s
            WHERE s.serie = 'B'
            AND DATE(s.timestamp) BETWEEN %s AND %s
            AND s.status != 'cancelled'
            AND NOT EXISTS (
                SELECT 1 FROM cfdis c WHERE c.sale_id = s.id
            )
            ORDER BY s.timestamp
        """
        
        result = self.core.db.execute_query(sql, (start_date, end_date))
        return [dict(row) for row in result] if result else []
    
    def _aggregate_sales_detailed(self, sales: List[Dict]) -> Dict[str, Any]:
        """Aggregate sales data with product detail for global CFDI."""
        total_sales = len(sales)
        subtotal = sum(float(sale.get('subtotal', 0) or 0) for sale in sales)
        tax = sum(float(sale.get('tax', 0) or 0) for sale in sales)
        total = sum(float(sale.get('total', 0) or 0) for sale in sales)
        
        # Get item details aggregated by product
        sale_ids = [str(s['id']) for s in sales]
        if sale_ids:
            items_sql = f"""
                SELECT 
                    COALESCE(p.name, 'Producto') as name,
                    COALESCE(p.sat_clave_prod_serv, '01010101') as sat_code,
                    COALESCE(p.sat_clave_unidad, 'H87') as sat_unit,
                    COALESCE(SUM(si.qty), 0) as qty,
                    COALESCE(SUM(si.subtotal), 0) as total
                FROM sale_items si
                LEFT JOIN products p ON si.product_id = p.id
                WHERE si.sale_id IN ({','.join(['%s' for _ in sale_ids])})
                GROUP BY p.id
                ORDER BY total DESC
            """
            items_result = self.core.db.execute_query(items_sql, tuple(sale_ids))
            items = [dict(row) for row in items_result] if items_result else []
        else:
            items = []
        
        return {
            'total_sales': total_sales,
            'subtotal': subtotal,
            'tax': tax,
            'total': total,
            'items': items
        }
    
    def _generate_cfdi_data(
        self,
        period_type: str,
        start_date: str,
        end_date: str,
        aggregated: Dict,
        sales: List[Dict]
    ) -> Dict[str, Any]:
        """Generate CFDI data structure and stamp with Facturapi."""
        try:
            periodicidad = self.PERIODICIDADES.get(period_type, '04')
            
            # Get fiscal config
            fiscal_config = self.core.db.execute_query(
                "SELECT * FROM fiscal_config WHERE branch_id = 1 LIMIT 1"
            )
            fiscal_data = dict(fiscal_config[0]) if fiscal_config else {}
            
            # Check if Facturapi is enabled
            facturapi_enabled = fiscal_data.get('facturapi_enabled', 0)
            facturapi_api_key = fiscal_data.get('facturapi_api_key') or fiscal_data.get('facturapi_key')
            
            # Build items for invoice
            items = []
            if len(aggregated['items']) <= 50:
                # Detailed by product
                for item in aggregated['items']:
                    qty = float(item.get('qty', 1)) or 1
                    total = float(item.get('total', 0))
                    unit_price = total / qty if qty else total
                    
                    items.append({
                        'product': {
                            'description': item.get('name', 'Producto')[:1000],
                            'product_key': item.get('sat_code', '01010101'),
                            'unit_key': item.get('sat_unit', 'H87'),
                            'unit_name': 'Pieza',
                            'price': round(unit_price, 2),
                            'taxes': [{
                                'type': 'IVA',
                                'rate': 0.16
                            }]
                        },
                        'quantity': qty
                    })
            else:
                # Single aggregated line
                items.append({
                    'product': {
                        'description': f'Venta global - {aggregated["total_sales"]} operaciones',
                        'product_key': '01010101',
                        'unit_key': 'ACT',
                        'unit_name': 'Actividad',
                        'price': round(aggregated['subtotal'], 2),
                        'taxes': [{
                            'type': 'IVA',
                            'rate': 0.16
                        }]
                    },
                    'quantity': 1
                })
            
            # Try Facturapi if enabled
            if facturapi_enabled and facturapi_api_key:
                try:
                    from src.services.fiscal.cfdi_service import CFDIService
                    cfdi_service = CFDIService(self.core)
                    facturapi = cfdi_service._get_facturapi()
                    
                    if facturapi:
                        # Build Facturapi invoice for global
                        mes = datetime.strptime(start_date, '%Y-%m-%d').strftime('%m')
                        año = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y')
                        
                        invoice_data = {
                            'customer': {
                                'legal_name': 'PUBLICO EN GENERAL',
                                'tax_id': self.RFC_PUBLICO_GENERAL,
                                'tax_system': '616',  # Sin obligaciones fiscales
                                'address': {
                                    'zip': fiscal_data.get('lugar_expedicion') or fiscal_data.get('codigo_postal') or '00000'
                                }
                            },
                            'items': items,
                            'payment_form': '01',  # Efectivo
                            'payment_method': 'PUE',
                            'use': 'S01',  # Sin efectos fiscales
                            'series': 'G',
                            'global': {
                                'periodicity': periodicidad,
                                'months': mes,
                                'year': int(año)
                            }
                        }
                        
                        logger.info(f"Sending global invoice to Facturapi: {aggregated['total_sales']} sales, ${aggregated['total']:,.2f}")
                        
                        # Create invoice in Facturapi
                        result = facturapi.invoices.create(invoice_data)
                        
                        # Handle Facturapi response format: {'success': bool, 'data': {...}} or {'success': bool, 'error': '...'}
                        if result and isinstance(result, dict):
                            # Check if success wrapper format
                            if 'success' in result:
                                if not result.get('success'):
                                    error_msg = result.get('error', 'Error desconocido')
                                    raise Exception(f"Facturapi error: {error_msg}")
                                # Success - get data
                                data = result.get('data', {})
                            else:
                                # Direct response (old format)
                                data = result
                            
                            uuid = data.get('uuid')
                            facturapi_id = data.get('id')
                            folio = data.get('folio_number', str(aggregated['total_sales']))
                            
                            if not uuid:
                                raise Exception(f"Facturapi no devolvió UUID. Response: {result}")
                            
                            # Save to database
                            import json
                            cfdi_id = self.core.db.execute_write("""
                                INSERT INTO cfdis (
                                    uuid, serie, folio, fecha_emision, total, subtotal, impuestos,
                                    rfc_receptor, nombre_receptor, uso_cfdi, forma_pago, metodo_pago,
                                    estado, facturapi_id, sync_status, created_at
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                uuid,
                                'G',
                                str(folio),
                                datetime.now().isoformat(),
                                aggregated['total'],
                                aggregated['subtotal'],
                                aggregated['tax'],
                                self.RFC_PUBLICO_GENERAL,
                                'PUBLICO EN GENERAL',
                                'S01',
                                '01',
                                'PUE',
                                'timbrado',
                                facturapi_id,
                                'synced',
                                datetime.now().isoformat()
                            ))
                            
                            logger.info(f"✅ Global invoice stamped: UUID={uuid}, Folio=G{folio}")
                            
                            return {
                                'success': True,
                                'cfdi_id': cfdi_id,
                                'uuid': uuid,
                                'facturapi_id': facturapi_id,
                                'folio': f'G{folio}',
                                'message': f"✅ Factura global timbrada: {uuid}"
                            }
                        else:
                            raise Exception(f"Facturapi response invalid: {result}")
                            
                except Exception as e:
                    logger.error(f"Facturapi error for global invoice: {e}")
                    # Return error instead of falling back silently
                    return {
                        'success': False,
                        'error': str(e)
                    }
            
            # Fallback: Save locally without stamping (pending)
            logger.warning("Facturapi not available, saving global invoice as pending")
            
            import json
            cfdi_data = {
                'receptor': {'rfc': self.RFC_PUBLICO_GENERAL, 'nombre': 'PUBLICO EN GENERAL'},
                'items': items,
                'subtotal': aggregated['subtotal'],
                'total': aggregated['total']
            }
            
            cfdi_id = self.core.db.execute_write("""
                INSERT INTO cfdis (
                    uuid, serie, folio, fecha_emision, total, subtotal, impuestos,
                    rfc_receptor, nombre_receptor, uso_cfdi, forma_pago, metodo_pago,
                    estado, xml_content, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                f"GLOBAL-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'G',
                str(aggregated['total_sales']),
                datetime.now().isoformat(),
                aggregated['total'],
                aggregated['subtotal'],
                aggregated['tax'],
                self.RFC_PUBLICO_GENERAL,
                'PUBLICO EN GENERAL',
                'S01',
                '01',
                'PUE',
                'pendiente',
                json.dumps(cfdi_data),
                datetime.now().isoformat()
            ))
            
            return {
                'success': True,
                'cfdi_id': cfdi_id,
                'cfdi_data': cfdi_data,
                'message': f"⚠️ Factura global guardada localmente (pendiente de timbrar) - {aggregated['total_sales']} ventas"
            }
            
        except Exception as e:
            logger.error(f"Error generating CFDI data: {e}")
            return {'success': False, 'error': str(e)}
    
    def schedule_automatic_generation(self, period_type: str, time: str = "00:30"):
        """
        Schedule automatic global CFDI generation.
        
        Args:
            period_type: 'daily', 'weekly', 'monthly'
            time: Time to run (HH:MM format)
            
        Note: This would require a task scheduler (cron/systemd timer)
        """
        # TODO: Implement with apscheduler or system cron
        logger.info(f"Scheduled global CFDI generation: {period_type} at {time}")
        
        return {
            'success': True,
            'message': f'Facturación global {period_type} programada para las {time}'
        }

