"""
Global Invoicing Service (Factura Global SAT)
Generates daily/weekly/monthly CFDIs for cash register sales (Serie B)
Requisitos SAT:
- RFC Generico: XAXX010101000 (Publico en General)
- Uso CFDI: S01 (Sin efectos fiscales)
- Solo incluir ventas Serie B no facturadas individualmente
- Periodo maximo: mensual

Refactored: receives `db` (DB wrapper) instead of `core`.
Uses :name params and db.fetch/db.fetchrow/db.execute.
Removed dead PERIODICIDADES dict and stub schedule_automatic_generation.
"""

from typing import Any, Dict, List, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal
import logging
from modules.fiscal.constants import IVA_RATE
from modules.shared.constants import money

logger = logging.getLogger(__name__)


class GlobalInvoicingService:
    RFC_PUBLICO_GENERAL = 'XAXX010101000'
    # SAT periodicity codes (the only dict needed)
    PERIODICIDADES_SAT = {
        'daily': '01',
        'weekly': '02',
        'biweekly': '03',
        'monthly': '04',
        'bimonthly': '05',
    }

    def __init__(self, db, branch_id: int | None = None):
        self.db = db
        self.branch_id = branch_id

    def _resolve_branch_id(self, sales: List[Dict]) -> int | None:
        branch_ids = {
            int(sale.get('branch_id'))
            for sale in sales
            if sale.get('branch_id') is not None
        }
        if len(branch_ids) == 1:
            self.branch_id = next(iter(branch_ids))
            return self.branch_id
        return self.branch_id

    def _parse_date(self, value: str) -> date:
        """Parse 'YYYY-MM-DD' to date for asyncpg (evita 'str' has no attribute 'toordinal')."""
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        return datetime.strptime(str(value).strip()[:10], '%Y-%m-%d').date()

    async def get_pending_sales_summary(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        if not start_date:
            start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        d1, d2 = self._parse_date(start_date), self._parse_date(end_date)

        row = await self.db.fetchrow(
            """SELECT COUNT(*) as count,
                      COALESCE(SUM(subtotal), 0) as subtotal,
                      COALESCE(SUM(tax), 0) as tax,
                      COALESCE(SUM(total), 0) as total
               FROM sales s
               WHERE s.serie = 'B'
                 AND CAST(s.timestamp AS DATE) BETWEEN :d1 AND :d2
                 AND s.status != 'cancelled'
                 AND NOT EXISTS (SELECT 1 FROM cfdis c WHERE c.sale_id = s.id)""",
            {"d1": d1, "d2": d2},
        )
        if row:
            return {
                'period': f"{start_date} - {end_date}",
                'count': row['count'],
                'subtotal': money(row['subtotal']),
                'tax': money(row['tax']),
                'total': money(row['total']),
            }
        return {'count': 0, 'subtotal': 0, 'tax': 0, 'total': 0}

    async def generate_global_cfdi(
        self, period_type: str, date: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            if not date:
                date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            start_date, end_date = self._calculate_period(date, period_type)
            sales = await self._get_uninvoiced_serie_b_sales(start_date, end_date)
            if not sales:
                return {
                    'success': False,
                    'error': f'No hay ventas Serie B sin facturar en el periodo {start_date} - {end_date}',
                }

            aggregated_data = await self._aggregate_sales_detailed(sales)
            result = await self._generate_cfdi_data(period_type, start_date, end_date, aggregated_data, sales)

            if result.get('success'):
                cfdi_id = result.get('cfdi_id')
                conn = self.db.connection
                async with conn.transaction():
                    for sale in sales:
                        await self.db.execute(
                            "UPDATE sales SET serie = 'A', synced = 0, updated_at = CURRENT_TIMESTAMP "
                            "WHERE id = :sid AND serie = 'B'",
                            {"sid": sale['id']},
                        )
                        if cfdi_id:
                            existing = await self.db.fetchrow(
                                "SELECT id FROM sale_cfdi_relation WHERE sale_id = :sid AND cfdi_id = :cid",
                                {"sid": sale['id'], "cid": cfdi_id},
                            )
                            if not existing:
                                try:
                                    await self.db.execute(
                                        "INSERT INTO sale_cfdi_relation (sale_id, cfdi_id, is_global) "
                                        "VALUES (:sid, :cid, 1)",
                                        {"sid": sale['id'], "cid": cfdi_id},
                                    )
                                except Exception as e:
                                    logger.warning(f"Could not link sale {sale['id']} to CFDI {cfdi_id}: {e}")
                result['sales_count'] = len(sales)
                result['period'] = f"{start_date} - {end_date}"
            return result
        except Exception as e:
            logger.error(f"Error generating global CFDI: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    async def generate_global_cfdi_from_selection(
        self, sale_ids: List[int], start_date: str, end_date: str
    ) -> Dict[str, Any]:
        try:
            if not sale_ids:
                return {'success': False, 'error': 'No hay ventas seleccionadas'}

            # Build positional-safe IN clause with named params
            id_params = {f"id_{i}": sid for i, sid in enumerate(sale_ids)}
            placeholders = ", ".join([f":id_{i}" for i in range(len(sale_ids))])
            sql = (
                f"SELECT s.* FROM sales s WHERE s.id IN ({placeholders}) "
                "AND s.status != 'cancelled' ORDER BY s.timestamp"
            )
            rows = await self.db.fetch(sql, id_params)
            sales = rows if rows else []

            if not sales:
                return {'success': False, 'error': 'No se encontraron las ventas seleccionadas'}

            aggregated_data = await self._aggregate_sales_detailed(sales)

            try:
                d_start = datetime.strptime(start_date, '%Y-%m-%d')
                d_end = datetime.strptime(end_date, '%Y-%m-%d')
            except (ValueError, TypeError):
                return {'success': False, 'error': f'Formato de fecha invalido: {start_date} / {end_date}'}
            days = (d_end - d_start).days
            period_type = 'daily' if days <= 1 else ('weekly' if days <= 7 else 'monthly')

            result = await self._generate_cfdi_data(period_type, start_date, end_date, aggregated_data, sales)
            if result.get('success'):
                cfdi_id = result.get('cfdi_id')
                conn = self.db.connection
                async with conn.transaction():
                    for sale in sales:
                        await self.db.execute(
                            "UPDATE sales SET serie = 'A', synced = 0, updated_at = CURRENT_TIMESTAMP "
                            "WHERE id = :sid AND serie = 'B'",
                            {"sid": sale['id']},
                        )
                        if cfdi_id:
                            existing = await self.db.fetchrow(
                                "SELECT id FROM sale_cfdi_relation WHERE sale_id = :sid AND cfdi_id = :cid",
                                {"sid": sale['id'], "cid": cfdi_id},
                            )
                            if not existing:
                                try:
                                    await self.db.execute(
                                        "INSERT INTO sale_cfdi_relation (sale_id, cfdi_id, is_global) "
                                        "VALUES (:sid, :cid, 1)",
                                        {"sid": sale['id'], "cid": cfdi_id},
                                    )
                                except Exception as e:
                                    logger.warning(f"Could not link sale {sale['id']} to CFDI {cfdi_id}: {e}")
                result['sales_count'] = len(sales)
                result['period'] = f"{start_date} - {end_date}"
            return result
        except Exception as e:
            logger.error(f"Error generating global CFDI from selection: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    async def generate_report(self, start_date: str, end_date: str, format: str = 'text') -> Any:
        sales = await self._get_uninvoiced_serie_b_sales(start_date, end_date)
        if not sales:
            if format == 'text':
                return "No hay ventas Serie B pendientes de facturar en este periodo."
            return {'error': 'No hay ventas pendientes'}

        aggregated = await self._aggregate_sales_detailed(sales)
        by_payment = {}
        for sale in sales:
            method = sale.get('payment_method', 'cash')
            if method not in by_payment:
                by_payment[method] = {'count': 0, 'total': 0}
            by_payment[method]['count'] += 1
            by_payment[method]['total'] += money(sale.get('total', 0))

        if format == 'text':
            return self._format_report_text(start_date, end_date, sales, aggregated, by_payment)
        elif format == 'dict':
            return {
                'period': {'start': start_date, 'end': end_date},
                'sales_count': len(sales),
                'aggregated': aggregated,
                'by_payment': by_payment,
                'sales': sales,
            }
        else:
            return self._format_report_html(start_date, end_date, sales, aggregated, by_payment)

    def _format_report_text(self, start_date, end_date, sales, aggregated, by_payment) -> str:
        lines, width = [], 48
        lines.append("=" * width)
        lines.append("REPORTE FACTURA GLOBAL".center(width))
        lines.append("=" * width)
        lines.append("")
        lines.append(f"Periodo: {start_date} a {end_date}")
        lines.append(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        lines.append("")
        lines.append("-" * width)
        lines.append("RESUMEN GENERAL")
        lines.append("-" * width)
        lines.append(f"Total de ventas:     {len(sales)}")
        lines.append(f"RFC Receptor:        {self.RFC_PUBLICO_GENERAL}")
        lines.append(f"Uso CFDI:            S01 (Sin efectos fiscales)")
        lines.append("")
        lines.append("-" * width)
        lines.append("TOTALES")
        lines.append("-" * width)
        lines.append(f"Subtotal:            ${aggregated['subtotal']:,.2f}")
        lines.append(f"IVA (16%):           ${aggregated['tax']:,.2f}")
        lines.append(f"TOTAL:               ${aggregated['total']:,.2f}")
        lines.append("")
        lines.append("-" * width)
        lines.append("DESGLOSE POR METODO DE PAGO")
        lines.append("-" * width)
        for method, data in by_payment.items():
            name = {
                'cash': 'Efectivo', 'card': 'Tarjeta', 'transfer': 'Transferencia',
                'mixed': 'Mixto', 'credit': 'Credito', 'wallet': 'Puntos',
            }.get(method, method.title())
            lines.append(f"{name:20} {data['count']:3} ops  ${data['total']:>10,.2f}")
        lines.append("")
        lines.append("-" * width)
        lines.append("TOP 10 PRODUCTOS (Por ingreso)")
        lines.append("-" * width)
        for i, item in enumerate(aggregated['items'][:10], 1):
            lines.append(f"{i:2}. {item['name'][:25]:25} ${item['total']:>10,.2f}")
        lines.append("")
        lines.append("=" * width)
        lines.append("ESTE REPORTE ES PARA FACTURA GLOBAL".center(width))
        lines.append(f"RFC: {self.RFC_PUBLICO_GENERAL}".center(width))
        lines.append("=" * width)
        return "\n".join(lines)

    def _format_report_html(self, start_date, end_date, sales, aggregated, by_payment) -> str:
        return f"""
        <div class="global-invoice-report">
            <h2>Reporte Factura Global</h2>
            <p><strong>Periodo:</strong> {start_date} a {end_date}</p>
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

    def _calculate_period(self, ref_date: str, period_type: str) -> tuple:
        try:
            ref = datetime.strptime(ref_date, '%Y-%m-%d')
        except (ValueError, TypeError):
            ref = datetime.now()

        if period_type == 'daily':
            start = end = ref
        elif period_type == 'weekly':
            start = ref - timedelta(days=ref.weekday())
            end = start + timedelta(days=6)
        elif period_type == 'monthly':
            start = ref.replace(day=1)
            if ref.month == 12:
                end = ref.replace(day=31)
            else:
                end = ref.replace(month=ref.month + 1, day=1) - timedelta(days=1)
        else:
            raise ValueError(f"Invalid period_type: {period_type}")
        return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')

    async def _get_uninvoiced_serie_b_sales(self, start_date: str, end_date: str) -> List[Dict]:
        d1, d2 = self._parse_date(start_date), self._parse_date(end_date)
        rows = await self.db.fetch(
            """SELECT s.* FROM sales s
               WHERE s.serie = 'B'
                 AND CAST(s.timestamp AS DATE) BETWEEN :d1 AND :d2
                 AND s.status != 'cancelled'
                 AND NOT EXISTS (SELECT 1 FROM cfdis c WHERE c.sale_id = s.id)
               ORDER BY s.timestamp""",
            {"d1": d1, "d2": d2},
        )
        return rows if rows else []

    async def _aggregate_sales_detailed(self, sales: List[Dict]) -> Dict[str, Any]:
        total_sales = len(sales)
        subtotal = money(sum(Decimal(str(sale.get('subtotal', 0) or 0)) for sale in sales))
        tax = money(sum(Decimal(str(sale.get('tax', 0) or 0)) for sale in sales))
        total = money(sum(Decimal(str(sale.get('total', 0) or 0)) for sale in sales))

        sale_ids = [s['id'] for s in sales]
        items = []
        if sale_ids:
            id_params = {f"id_{i}": sid for i, sid in enumerate(sale_ids)}
            placeholders = ", ".join([f":id_{i}" for i in range(len(sale_ids))])
            items_sql = f"""
                SELECT COALESCE(p.name, 'Producto') as name,
                       COALESCE(p.sat_clave_prod_serv, '01010101') as sat_code,
                       COALESCE(p.sat_clave_unidad, 'H87') as sat_unit,
                       COALESCE(SUM(si.qty), 0) as qty,
                       COALESCE(SUM(si.subtotal), 0) as total
                FROM sale_items si LEFT JOIN products p ON si.product_id = p.id
                WHERE si.sale_id IN ({placeholders})
                GROUP BY p.id, p.name, p.sat_clave_prod_serv, p.sat_clave_unidad
                ORDER BY total DESC
            """
            items = await self.db.fetch(items_sql, id_params)
        return {'total_sales': total_sales, 'subtotal': subtotal, 'tax': tax, 'total': total, 'items': items}

    async def _generate_cfdi_data(
        self,
        period_type: str,
        start_date: str,
        end_date: str,
        aggregated: Dict,
        sales: List[Dict],
    ) -> Dict[str, Any]:
        try:
            branch_id = self._resolve_branch_id(sales)
            if branch_id is None:
                return {
                    'success': False,
                    'error': 'No se pudo determinar una sucursal unica para la factura global',
                }

            periodicidad = self.PERIODICIDADES_SAT.get(period_type, '04')

            fiscal_data = await self.db.fetchrow(
                "SELECT * FROM fiscal_config WHERE branch_id = :bid LIMIT 1",
                {"bid": branch_id},
            )
            fiscal_data = fiscal_data or {}

            facturapi_enabled = fiscal_data.get('facturapi_enabled', 0)
            facturapi_api_key = fiscal_data.get('facturapi_api_key') or fiscal_data.get('facturapi_key')
            emitter_rfc = None

            # --- MULTI-EMITTER INTEGRATION ---
            try:
                if facturapi_enabled:
                    from modules.fiscal.multi_emitter import MultiEmitterManager
                    from decimal import Decimal
                    emitter_mgr = MultiEmitterManager(self.db)
                    invoice_total = Decimal(str(aggregated['total']))
                    optimal_emitter = await emitter_mgr.select_optimal_rfc(invoice_total)
                    
                    if optimal_emitter:
                        emitter_rfc = optimal_emitter['rfc']
                        if optimal_emitter.get('facturapi_api_key'):
                            facturapi_api_key = optimal_emitter['facturapi_api_key']
                        logger.info(f"Multi-Emitter selected RFC {emitter_rfc} for Global Invoice of ${invoice_total:,.2f}")
                    else:
                        logger.warning(f"Multi-Emitter: No RFC has enough capacity for ${invoice_total:,.2f}. Falling back to default.")
            except Exception as e:
                logger.warning(f"Failed to use MultiEmitterManager: {e}")
            # ---------------------------------

            def normalize_sat_key(sat_code: str) -> str:
                sat_code = str(sat_code).strip() if sat_code else '01010101'
                if len(sat_code) == 8:
                    return sat_code
                return sat_code.ljust(8, '0') if len(sat_code) < 8 else sat_code[:8]

            items = []
            if len(aggregated['items']) <= 50:
                for item in aggregated['items']:
                    qty = float(item.get('qty', 1)) or 1
                    total_val = money(item.get('total', 0))
                    unit_price = total_val / qty if qty else total_val

                    sat_code_raw = item.get('sat_code', '01010101')
                    sat_code_normalized = normalize_sat_key(sat_code_raw)
                    product_key = sat_code_normalized if sat_code_normalized != '01010101' and len(sat_code_normalized) == 8 else '01010101'

                    items.append({
                        'product': {
                            'description': item.get('name', 'Producto')[:1000],
                            'product_key': product_key,
                            'unit_key': item.get('sat_unit', 'H87'),
                            'unit_name': 'Pieza',
                            'price': round(unit_price, 2),
                            'taxes': [{'type': 'IVA', 'rate': IVA_RATE}],
                        },
                        'quantity': qty,
                    })
            else:
                items.append({
                    'product': {
                        'description': f'Venta global - {aggregated["total_sales"]} operaciones',
                        'product_key': '01010101',
                        'unit_key': 'ACT',
                        'unit_name': 'Actividad',
                        'price': round(aggregated['subtotal'], 2),
                        'taxes': [{'type': 'IVA', 'rate': IVA_RATE}],
                    },
                    'quantity': 1,
                })

            if facturapi_enabled and facturapi_api_key:
                try:
                    from modules.fiscal.facturapi_connector import Facturapi
                    facturapi = Facturapi(facturapi_api_key)

                    if facturapi:
                        try:
                            _date_parsed = datetime.strptime(start_date, '%Y-%m-%d')
                        except (ValueError, TypeError):
                            _date_parsed = datetime.now()

                        postal_code = fiscal_data.get('codigo_postal') or fiscal_data.get('lugar_expedicion')
                        if not postal_code or postal_code == '00000':
                            return {
                                'success': False,
                                'error': 'Lugar de expedicion no configurado para la sucursal seleccionada',
                            }

                        invoice_data = {
                            'customer': {
                                'legal_name': 'PUBLICO EN GENERAL',
                                'tax_id': self.RFC_PUBLICO_GENERAL,
                                'tax_system': '616',
                                'address': {'zip': postal_code},
                            },
                            'items': items,
                            'payment_form': '01',
                            'payment_method': 'PUE',
                            'use': 'S01',
                            'series': 'G',
                            'global': {
                                'periodicity': periodicidad,
                                'months': _date_parsed.strftime('%m'),
                                'year': int(_date_parsed.strftime('%Y')),
                            },
                        }

                        try:
                            result = await facturapi.invoices.create(invoice_data)
                        except Exception as e:
                            error_str = str(e)
                            if "product_key" in error_str.lower() or "couldn't find" in error_str.lower():
                                logger.warning("Facturapi rejected product_key, retrying with generic code '01010101'")
                                for item in items:
                                    if 'product' in item and 'product_key' in item['product']:
                                        item['product']['product_key'] = '01010101'
                                invoice_data['items'] = items
                                result = await facturapi.invoices.create(invoice_data)
                            else:
                                raise

                        if result and isinstance(result, dict):
                            data = (
                                result.get('data', {})
                                if 'success' in result and result.get('success')
                                else (result if 'success' not in result else {})
                            )
                            if 'success' in result and not result.get('success'):
                                raise Exception(f"Facturapi error: {result.get('error', 'Error desconocido')}")

                            uuid = data.get('uuid')
                            facturapi_id = data.get('id')
                            folio = data.get('folio_number', str(aggregated['total_sales']))
                            if not uuid:
                                raise Exception(f"Facturapi no devolvio UUID. Response: {result}")

                            row = await self.db.fetchrow(
                                """INSERT INTO cfdis
                                   (uuid, serie, folio, fecha_emision, total, subtotal, impuestos,
                                    rfc_receptor, nombre_receptor, uso_cfdi, forma_pago, metodo_pago,
                                    estado, facturapi_id, sync_status, created_at)
                                   VALUES (:uuid, 'G', :folio, :fecha, :total, :subtotal, :tax,
                                    :rfc_rec, :nom_rec, :uso, '01', 'PUE',
                                    'ACTIVO', :fid, 1, CURRENT_TIMESTAMP)
                                   RETURNING id""",
                                {
                                    "uuid": uuid,
                                    "folio": folio,
                                    "fecha": datetime.now().isoformat(),
                                    "total": aggregated['total'],
                                    "subtotal": aggregated['subtotal'],
                                    "tax": aggregated['tax'],
                                    "rfc_rec": self.RFC_PUBLICO_GENERAL,
                                    "nom_rec": "PUBLICO EN GENERAL",
                                    "uso": "S01",
                                    "fid": facturapi_id,
                                },
                            )
                            cfdi_id = row['id'] if row else None
                            if row and emitter_rfc:
                                try:
                                    from modules.fiscal.multi_emitter import MultiEmitterManager
                                    from decimal import Decimal
                                    mgr = MultiEmitterManager(self.db)
                                    await mgr.update_accumulated_amount(emitter_rfc, Decimal(str(aggregated['total'])))
                                except Exception as update_err:
                                    logger.error(f"Failed to update MultiEmitter amount: {update_err}")

                            return {
                                'success': True,
                                'cfdi_id': cfdi_id,
                                'uuid': uuid,
                                'facturapi_id': facturapi_id,
                                'folio': f'G{folio}',
                                'message': f"Factura global timbrada: {uuid}",
                            }
                        else:
                            raise Exception(f"Facturapi response invalid: {result}")
                except Exception as e:
                    return {'success': False, 'error': str(e)}

            import json
            cfdi_data = {
                'receptor': {'rfc': self.RFC_PUBLICO_GENERAL, 'nombre': 'PUBLICO EN GENERAL'},
                'items': items,
                'subtotal': aggregated['subtotal'],
                'total': aggregated['total'],
            }
            row = await self.db.fetchrow(
                """INSERT INTO cfdis
                   (uuid, serie, folio, fecha_emision, total, subtotal, impuestos,
                    rfc_receptor, nombre_receptor, uso_cfdi, forma_pago, metodo_pago,
                    estado, xml_content, created_at)
                   VALUES (:uuid, 'G', :folio, :fecha, :total, :subtotal, :tax,
                    :rfc, 'PUBLICO EN GENERAL', 'S01', '01', 'PUE',
                    'pendiente', :xml_content, :now)
                   RETURNING id""",
                {
                    "uuid": f"GLOBAL-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    "folio": str(aggregated['total_sales']),
                    "fecha": datetime.now().isoformat(),
                    "total": aggregated['total'],
                    "subtotal": aggregated['subtotal'],
                    "tax": aggregated['tax'],
                    "rfc": self.RFC_PUBLICO_GENERAL,
                    "xml_content": json.dumps(cfdi_data),
                    "now": datetime.now().isoformat(),
                },
            )
            cfdi_id = row['id'] if row else None
            return {
                'success': True,
                'cfdi_id': cfdi_id,
                'cfdi_data': cfdi_data,
                'message': f"Factura global guardada localmente (pendiente de timbrar) - {aggregated['total_sales']} ventas",
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
