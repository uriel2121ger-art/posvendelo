"""
CFDI Service - Orchestrates the complete CFDI generation process
"""

from typing import Any, Dict, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class CFDIService:
    """
    Service for generating, signing, and stamping CFDIs.
    
    Soporta dos modos:
    1. PAC genérico (legacy) - Requiere configuración de CSD y PAC
    2. Facturapi (recomendado) - Solo requiere API key en .env
    
    Para usar Facturapi, configurar en .env:
        FACTURAPI_KEY=sk_test_xxxxx   # Test mode (sandbox)
        FACTURAPI_KEY=sk_live_xxxxx   # Producción (real)
    """
    
    def __init__(self, core):
        """
        Initialize CFDI service.
        
        Args:
            core: POSCore instance
        """
        self.core = core
        self._facturapi = None
    
    def _get_facturapi(self):
        """Get Facturapi client (lazy load)."""
        if self._facturapi is None:
            try:
                from app.fiscal.facturapi_connector import Facturapi

                # Priority: 1. Fiscal config (Settings), 2. Environment variable
                fiscal_cfg = self.core.get_fiscal_config() or {}
                api_key = fiscal_cfg.get('facturapi_api_key', '')
                
                if not api_key:
                    import os
                    api_key = os.getenv('FACTURAPI_KEY', '')
                
                if not api_key:
                    logger.warning("Facturapi API key no configurada en Settings → Facturación")
                    self._facturapi = False
                    return None
                
                self._facturapi = Facturapi(api_key)
                logger.info(f"Facturapi inicializado en modo: {self._facturapi.mode}")
            except Exception as e:
                logger.warning(f"Facturapi no disponible: {e}")
                self._facturapi = False
        return self._facturapi if self._facturapi else None
    
    def generate_cfdi_via_facturapi(
        self,
        sale_id: int,
        customer_rfc: str,
        customer_name: Optional[str] = None,
        customer_regime: str = '616',
        uso_cfdi: str = 'G03',
        customer_email: Optional[str] = None,
        customer_zip: str = '00000',
        payment_form_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate CFDI using Facturapi (recommended method).
        
        Args:
            sale_id: ID de la venta a facturar
            customer_rfc: RFC del cliente
            customer_name: Nombre/Razón social
            customer_regime: Régimen fiscal (default: 616 sin obligaciones)
            uso_cfdi: Uso del CFDI (default: G03 gastos en general)
            customer_email: Email para enviar factura
            customer_zip: Código postal del cliente
            
        Returns:
            Dictionary with success, uuid, pdf_url, xml_url, etc.
        """
        try:
            facturapi = self._get_facturapi()
            if not facturapi:
                return {
                    'success': False,
                    'error': 'Facturapi no configurado. Configure FACTURAPI_KEY en .env'
                }
            
            # Get sale data
            sale_data = self.core.get_sale_details(sale_id)
            if not sale_data:
                return {
                    'success': False,
                    'error': f'Venta {sale_id} no encontrada'
                }
            
            # Helper function to normalize SAT product key to 8 characters
            def normalize_sat_key(sat_code: str) -> str:
                """Normalize SAT product key to exactly 8 characters for Facturapi."""
                if not sat_code:
                    return '01010101'
                sat_code = str(sat_code).strip()
                # CRITICAL FIX: Facturapi requires exactly 8 characters
                if len(sat_code) == 8:
                    return sat_code
                elif len(sat_code) < 8:
                    # Pad with zeros on the right
                    return sat_code.ljust(8, '0')
                else:
                    # Truncate to 8 characters
                    return sat_code[:8]
            
            # CRITICAL FIX: Validate RFC for individual invoices
            # RFC "XAXX010101000" (Público en General) is ONLY for global invoices
            RFC_PUBLICO_GENERAL = 'XAXX010101000'
            if customer_rfc.upper() == RFC_PUBLICO_GENERAL:
                return {
                    'success': False,
                    'error': 'El RFC "XAXX010101000" (Público en General) solo puede usarse en facturas globales.\n\n'
                             'Para facturas individuales, debe proporcionar el RFC del cliente.'
                }
            
            # CRITICAL FIX: Validate postal code
            # Facturapi doesn't accept "00000" - use a valid default if not configured
            if not customer_zip or customer_zip == '00000':
                fiscal_config = self.core.get_fiscal_config()
                customer_zip = fiscal_config.get('codigo_postal') or fiscal_config.get('lugar_expedicion') or '01000'
                if customer_zip == '00000':
                    customer_zip = '01000'  # Default to Mexico City
            
            # Build Facturapi invoice data
            items = []
            for idx, item in enumerate(sale_data.get('items', [])):
                # CRITICAL FIX: Normalize SAT key to 8 characters
                sat_code_raw = item.get('sat_code', item.get('sat_clave_prod_serv', '01010101'))
                sat_code_normalized = normalize_sat_key(sat_code_raw)
                
                items.append({
                    'quantity': float(item.get('quantity', item.get('qty', 1))),
                    'product': {
                        'description': item.get('name', item.get('product_name', 'Producto')),
                        'product_key': sat_code_normalized,
                        'unit_key': item.get('sat_unit', item.get('sat_clave_unidad', 'H87')),
                        'price': float(item.get('price', item.get('unit_price', 0))),
                        'taxes': [{'type': 'IVA', 'rate': 0.16}]
                    }
                })
            
            if not items:
                return {
                    'success': False,
                    'error': 'La venta no tiene productos'
                }
            
            # Determine payment form (SAT code)
            # Priority: 1. Override from dialog, 2. Auto-detect from sale
            if payment_form_override:
                payment_form = payment_form_override
                # Si forma de pago es 99, usar PPD
                cfdi_payment_method = 'PPD' if payment_form == '99' else 'PUE'
            else:
                payment_method = sale_data.get('payment_method', 'cash')
                payment_form_map = {
                    'cash': '01',       # Efectivo
                    'card': '04',       # Tarjeta de crédito
                    'debit': '28',      # Tarjeta de débito
                    'transfer': '03',   # Transferencia
                    'check': '02',      # Cheque
                    'mixed': '01',      # Mixto → Efectivo (99 no válido con PUE)
                    'wallet': '01',     # Monedero → Efectivo
                    'voucher': '01',    # Vales → Efectivo
                    'usd': '01',        # Dólares → Efectivo
                    'credit': '99',     # Crédito → Por definir (usa PPD)
                }
                payment_form = payment_form_map.get(payment_method, '01')
                # Si es crédito, cambiar a PPD
                cfdi_payment_method = 'PPD' if payment_method == 'credit' else 'PUE'
            
            # Create invoice via Facturapi
            invoice_data = {
                'customer': {
                    'legal_name': customer_name or 'CLIENTE',
                    'tax_id': customer_rfc.upper(),
                    'tax_system': customer_regime,
                    'email': customer_email,
                    'address': {'zip': customer_zip}
                },
                'items': items,
                'payment_form': payment_form,
                'payment_method': cfdi_payment_method,  # PUE (contado) o PPD (crédito)
                'use': uso_cfdi,
                'folio_number': sale_id,
                'series': 'F'
            }
            
            logger.info(f"Enviando factura a Facturapi para venta {sale_id}...")
            try:
                result = facturapi.invoices.create(invoice_data)
            except Exception as e:
                error_str = str(e)
                logger.error(f"Facturapi error for individual invoice: {e}")
                
                # CRITICAL FIX: If error is about product_key, try with generic code
                if "product_key" in error_str.lower() or "couldn't find" in error_str.lower():
                    logger.warning(f"Facturapi rejected product_key, retrying with generic code '01010101'")
                    # Retry with generic product key for all items
                    for item in items:
                        if 'product' in item and 'product_key' in item['product']:
                            item['product']['product_key'] = '01010101'
                    
                    # Update invoice_data with new items
                    invoice_data['items'] = items
                    
                    # Retry with generic product keys
                    result = facturapi.invoices.create(invoice_data)
                else:
                    # Re-raise if it's not a product_key error
                    raise
            
            # Ensure result is a dict
            if not isinstance(result, dict):
                return {'success': False, 'error': f'Respuesta inesperada de Facturapi: {type(result).__name__}'}
            
            if not result.get('success'):
                error_msg = result.get('error', 'Error desconocido')
                # Translate SAT errors if possible
                try:
                    from app.fiscal.error_translator import SATErrorTranslator
                    translator = SATErrorTranslator()
                    translated = translator.translate(error_msg)
                    if translated != error_msg:
                        error_msg = f"{translated}\n(Original: {error_msg})"
                except Exception as e:
                    logger.error(f"Error translating SAT error message: {e}")
                
                return {
                    'success': False,
                    'error': error_msg,
                    'details': result.get('details')
                }
            
            # Success - extract data
            invoice = result['data']
            uuid = invoice.get('uuid')
            invoice_id = invoice.get('id')
            
            logger.info(f"✅ CFDI creado exitosamente: {uuid}")
            
            # Save to local database
            from datetime import datetime
            cfdi_record = {
                'sale_id': sale_id,
                'uuid': uuid,
                'folio': sale_id,
                'serie': 'POS',
                'rfc_receptor': customer_rfc.upper(),
                'nombre_receptor': customer_name or 'PUBLICO EN GENERAL',
                'regimen_receptor': customer_regime,
                'uso_cfdi': uso_cfdi,
                'total': float(invoice.get('total', sale_data.get('total', 0))),
                'subtotal': float(sale_data.get('subtotal', 0)),
                'impuestos': float(sale_data.get('tax', 0)),
                'estado': 'valid',
                'facturapi_id': invoice_id,
                'fecha_emision': datetime.now().isoformat(),
            }
            
            cfdi_id = self._save_cfdi(cfdi_record)
            
            # Promote Sale from Serie B to Serie A
            self._promote_sale_to_serie_a(sale_id, uuid, {
                **sale_data,
                'customer_rfc': customer_rfc.upper()
            })
            
            # Build result
            result_data = {
                'success': True,
                'cfdi_id': cfdi_id,
                'uuid': uuid,
                'facturapi_id': invoice_id,
                'total': invoice.get('total'),
                'pdf_url': f"https://www.facturapi.io/v2/invoices/{invoice_id}/pdf",
                'xml_url': f"https://www.facturapi.io/v2/invoices/{invoice_id}/xml",
                'status': invoice.get('status'),
                'mode': facturapi.mode  # 'test' o 'live'
            }
            
            # Send email if provided
            if customer_email:
                try:
                    facturapi.invoices.send_by_email(invoice_id, customer_email)
                    result_data['email_sent'] = True
                    logger.info(f"📧 Factura enviada a {customer_email}")
                except Exception as e:
                    logger.warning(f"Error enviando email: {e}")
                    result_data['email_error'] = str(e)
            
            return result_data
            
        except Exception as e:
            logger.error(f"Error generando CFDI via Facturapi: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def cancel_cfdi_via_facturapi(
        self,
        uuid: str,
        motive: str = '02'
    ) -> Dict[str, Any]:
        """
        Cancel a CFDI using Facturapi.
        
        Args:
            uuid: UUID del CFDI a cancelar
            motive: Motivo de cancelación (01-04)
        """
        try:
            facturapi = self._get_facturapi()
            if not facturapi:
                return {'success': False, 'error': 'Facturapi no configurado'}
            
            # Get facturapi_id from our database
            cfdi_rows = self.core.db.execute_query(
                "SELECT facturapi_id FROM cfdis WHERE uuid = %s",
                (uuid,)
            )
            
            if not cfdi_rows:
                return {
                    'success': False,
                    'error': f'CFDI {uuid} no encontrado'
                }
            
            # Convert sqlite3.Row to dict
            cfdi = dict(cfdi_rows[0]) if cfdi_rows else {}
            facturapi_id = cfdi.get('facturapi_id')
            
            if not facturapi_id:
                return {
                    'success': False,
                    'error': f'CFDI {uuid} no tiene ID de Facturapi'
                }
            
            # Cancel via Facturapi
            result = facturapi.invoices.cancel(facturapi_id, motive)
            
            # Ensure result is a dict
            if not isinstance(result, dict):
                return {'success': False, 'error': f'Respuesta inesperada: {type(result).__name__}'}
            
            if result.get('success'):
                from datetime import datetime
                self.core.db.execute_write(
                    """UPDATE cfdis 
                       SET estado = 'canceled',
                           motivo_cancelacion = %s,
                           fecha_cancelacion = %s
                       WHERE uuid = %s""",
                    (motive, datetime.now().isoformat(), uuid)
                )
                logger.info(f"✅ CFDI {uuid} cancelado exitosamente")
            
            return result
            
        except Exception as e:
            logger.error(f"Error cancelando CFDI: {e}")
            return {'success': False, 'error': str(e)}
    
    def generate_cfdi_for_sale(
        self,
        sale_id: int,
        customer_rfc: str,
        customer_name: Optional[str] = None,
        customer_regime: str = '616',
        uso_cfdi: str = 'G03',
        forma_pago: str = '01',
        customer_zip: str = '00000'
    ) -> Dict[str, Any]:
        """
        Generate complete CFDI for a sale.
        
        Args:
            sale_id: ID of the sale to invoice
            customer_rfc: Customer's RFC
            customer_name: Customer's legal name
            customer_regime: Customer's fiscal regime
            uso_cfdi: CFDI use code (G03 = general expenses)
            
        Returns:
            Dictionary with:
            - success: bool
            - cfdi_id: int (database ID)
            - uuid: str (fiscal folio)
            - xml_path: str
            - pdf_path: str (if generated)
            - error: str (if failed)
        """
        try:
            # Step 1: Get fiscal configuration
            fiscal_config = self.core.get_fiscal_config()
            if not fiscal_config or not fiscal_config.get('rfc_emisor'):
                return {
                    'success': False,
                    'error': 'Configuración fiscal no encontrada. Configure en Settings → Facturación'
                }
            
            # Check if Facturapi is enabled - use it instead of PAC
            if fiscal_config.get('facturapi_enabled') and fiscal_config.get('facturapi_api_key'):
                logger.info(f"Using Facturapi for sale {sale_id}")
                return self.generate_cfdi_via_facturapi(
                    sale_id=sale_id,
                    customer_rfc=customer_rfc,
                    customer_name=customer_name,
                    customer_regime=customer_regime,
                    uso_cfdi=uso_cfdi,
                    customer_zip=customer_zip or fiscal_config.get('codigo_postal', '00000'),
                    payment_form_override=forma_pago
                )
            
            # Step 2: Get sale data with items (PAC tradicional)
            sale_data = self.core.get_sale_details(sale_id)
            if not sale_data:
                return {
                    'success': False,
                    'error': f'Venta {sale_id} no encontrada'
                }
            
            # Step 3: Prepare customer data
            customer_data = {
                'rfc': customer_rfc.upper(),
                'nombre': customer_name or 'PUBLICO EN GENERAL',
                'codigo_postal': '00000',  # Should get from customer record
                'regimen_fiscal': customer_regime,
                'uso_cfdi': uso_cfdi
            }
            
            # Step 4: Build XML
            from app.fiscal.cfdi_builder import CFDIBuilder
            builder = CFDIBuilder(fiscal_config)
            xml_unsigned = builder.build(sale_data, customer_data)
            
            logger.info(f"CFDI XML generated for sale {sale_id}")
            
            # Step 5: Sign XML with CSD
            from app.fiscal.signature import sign_cfdi_xml
            xml_signed = sign_cfdi_xml(xml_unsigned, fiscal_config)
            
            logger.info(f"CFDI XML signed for sale {sale_id}")
            
            # Step 6: Send to PAC for timbrado
            from app.fiscal.pac_connector import create_pac_connector
            pac = create_pac_connector(fiscal_config)
            
            timbrado_result = pac.timbrar_cfdi(xml_signed)
            
            if not timbrado_result.get('success'):
                return {
                    'success': False,
                    'error': f"Error en timbrado: {timbrado_result.get('error', 'Unknown')}"
                }
            
            # Step 7: Save to database and file system
            uuid = timbrado_result['uuid']
            xml_timbrado = timbrado_result['xml_timbrado']
            
            cfdi_record = {
                'sale_id': sale_id,
                'uuid': uuid,
                'folio': fiscal_config.get('folio_actual', 1),
                'serie': fiscal_config.get('serie_factura', 'F'),
                'rfc_receptor': customer_rfc,
                'nombre_receptor': customer_data['nombre'],
                'regimen_receptor': customer_regime,
                'uso_cfdi': uso_cfdi,
                'xml_original': xml_signed,
                'xml_timbrado': xml_timbrado,
                'fecha_emision': sale_data.get('timestamp'),
                'fecha_timbrado': timbrado_result.get('fecha_timbrado'),
                'total': sale_data.get('total'),
                'subtotal': sale_data.get('subtotal'),
                'impuestos': sale_data.get('tax'),
            }
            
            cfdi_id = self._save_cfdi(cfdi_record)
            
            # Increment folio
            self.core.update_fiscal_config({
                'folio_actual': fiscal_config.get('folio_actual', 1) + 1
            })
            
            # Step 8: Save XML file
            xml_path = self._save_xml_file(uuid, xml_timbrado)
            
            logger.info(f"CFDI {uuid} created successfully for sale {sale_id}")
            
            # Step 8.1: PROMOTE SALE FROM SERIE B TO A (if applicable)
            self._promote_sale_to_serie_a(sale_id, uuid, sale_data)
            
            result_data = {
                'success': True,
                'cfdi_id': cfdi_id,
                'uuid': uuid,
                'xml_path': xml_path,
                'xml_timbrado': xml_timbrado
            }
            
            # Step 9: Generate PDF (optional, but recommended)
            try:
                from app.fiscal.pdf_generator import generate_cfdi_pdf
                pdf_path = generate_cfdi_pdf(cfdi_id, self.core)
                result_data['pdf_path'] = pdf_path
                logger.info(f"PDF generated: {pdf_path}")
            except Exception as e:
                logger.warning(f"PDF generation failed (non-critical): {e}")
                result_data['pdf_warning'] = 'PDF no generado'
            
            # Step 10: Send email (if configured and customer has email)
            customer_email = None  # TODO: Get from customer record
            if customer_email:
                try:
                    from app.fiscal.email_service import send_cfdi_email
                    email_result = send_cfdi_email(cfdi_id, customer_email, self.core)
                    if email_result.get('success'):
                        logger.info(f"Email sent to {customer_email}")
                        result_data['email_sent'] = True
                except Exception as e:
                    logger.warning(f"Email send failed (non-critical): {e}")
                    result_data['email_warning'] = 'Email no enviado'
            
            return result_data
            
        except Exception as e:
            logger.error(f"Error generating CFDI for sale {sale_id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _save_cfdi(self, cfdi_data: Dict[str, Any]) -> int:
        """Save CFDI record to database."""
        columns = ', '.join(cfdi_data.keys())
        placeholders = ', '.join(['?' for _ in cfdi_data])
        
        sql = f"INSERT INTO cfdis ({columns}) VALUES ({placeholders})"
        cfdi_id = self.core.db.execute_write(sql, tuple(cfdi_data.values()))
        
        return cfdi_id
    
    def _save_xml_file(self, uuid: str, xml_content: str) -> str:
        """Save XML to file system."""
        from app.core import DATA_DIR
        
        cfdi_dir = Path(DATA_DIR) / "cfdis"
        cfdi_dir.mkdir(exist_ok=True)
        
        xml_path = cfdi_dir / f"{uuid}.xml"
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        
        return str(xml_path)
    
    def _promote_sale_to_serie_a(self, sale_id: int, cfdi_uuid: str, sale_data: Dict[str, Any]):
        """
        Promote a Serie B sale to Serie A when invoiced.
        
        This method:
        1. Updates the sale's serie from B to A
        2. Links the CFDI UUID to the sale
        3. Adjusts shadow_stock for all products in the sale
        4. Records the promotion for audit trail
        
        Args:
            sale_id: ID of the sale being invoiced
            cfdi_uuid: UUID of the generated CFDI
            sale_data: Sale data including items
        """
        from datetime import datetime
        
        try:
            # Get current sale serie
            sale_info = self.core.db.execute_query(
                "SELECT serie, timestamp FROM sales WHERE id = %s",
                (sale_id,)
            )
            
            if not sale_info:
                logger.warning(f"Sale {sale_id} not found for promotion")
                return
            
            current_serie = sale_info[0].get('serie', 'B') if isinstance(sale_info[0], dict) else sale_info[0][0]
            sale_date = sale_info[0].get('timestamp', '') if isinstance(sale_info[0], dict) else sale_info[0][1]
            
            # Only promote if currently Serie B
            if current_serie != 'B':
                logger.info(f"Sale {sale_id} already Serie A, skipping promotion")
                # Still update cfdi_uuid
                self.core.db.execute_write(
                    """UPDATE sales 
                       SET cfdi_uuid = %s, rfc_used = %s
                       WHERE id = %s""",
                    (cfdi_uuid, sale_data.get('customer_rfc', ''), sale_id)
                )
                return
            
            # Update sale: Serie B → A, add CFDI UUID
            self.core.db.execute_write(
                """UPDATE sales 
                   SET serie = 'A',
                       cfdi_uuid = %s,
                       rfc_used = %s,
                       updated_at = %s
                   WHERE id = %s""",
                (cfdi_uuid, sale_data.get('customer_rfc', ''), 
                 datetime.now().isoformat(), sale_id)
            )
            
            logger.info(f"✅ Sale {sale_id} promoted from Serie B → Serie A")
            
            # Adjust shadow_stock for each product
            items = sale_data.get('items', [])
            if items:
                try:
                    from app.fiscal.shadow_inventory import ShadowInventory
                    shadow = ShadowInventory(self.core)
                    
                    for item in items:
                        product_id = item.get('product_id')
                        quantity = float(item.get('quantity', 0))
                        
                        if product_id and quantity > 0:
                            # When promoting B→A, we need to "return" shadow to fiscal
                            # Because when sold as B, it reduced shadow_stock
                            # Now that it's A, it should have reduced fiscal instead
                            # So we ADD back to shadow_stock (reverse the B sale)
                            # and the A sale is already reflected in real stock
                            
                            # Actually, the correct logic:
                            # Serie B sale reduced: real_stock - qty, shadow_stock - qty
                            # When promoting to A, we need shadow to match fiscal again
                            # So we ADD qty back to shadow_stock
                            
                            self.core.db.execute_write(
                                """UPDATE products 
                                   SET shadow_stock = COALESCE(shadow_stock, 0) + %s
                                   WHERE id = %s""",
                                (quantity, product_id)
                            )
                            
                    logger.info(f"✅ Shadow stock adjusted for {len(items)} products")
                    
                except Exception as e:
                    logger.warning(f"Shadow stock adjustment failed (non-critical): {e}")
            
            # Record promotion in shadow_movements for audit
            try:
                self.core.db.execute_write(
                    """INSERT INTO shadow_movements
                       (product_id, movement_type, quantity, source, notes, created_at)
                       VALUES (0, 'SALE_PROMOTION', 0, %s, %s, %s)""",
                    (f"Sale {sale_id} promoted B→A",
                     f"CFDI {cfdi_uuid}, Original date: {sale_date}",
                     datetime.now().isoformat())
                )
            except Exception as e:
                logger.debug(f"Could not record sale promotion audit (non-critical): {e}")
            
            logger.info(f"✅ Sale {sale_id} fully promoted to Serie A with CFDI {cfdi_uuid}")
            
        except Exception as e:
            logger.error(f"Error promoting sale {sale_id} to Serie A: {e}")
            # Don't fail the whole CFDI generation for this
    
    def get_cfdi_by_sale(self, sale_id: int) -> Optional[Dict[str, Any]]:
        """Get CFDI record for a sale."""
        result = self.core.db.execute_query(
            "SELECT * FROM cfdis WHERE sale_id = %s",
            (sale_id,)
        )
        
        if result:
            return dict(result[0])
        return None
    
    def cancel_cfdi(
        self,
        uuid: str,
        motivo: str = '02',
        folio_sustitucion: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cancel a CFDI.
        
        Args:
            uuid: UUID of CFDI to cancel
            motivo: Cancellation reason (01-04)
            folio_sustitucion: Replacement UUID if motivo='01'
            
        Returns:
            Result dictionary
        """
        try:
            fiscal_config = self.core.get_fiscal_config()
            
            from app.fiscal.pac_connector import create_pac_connector
            pac = create_pac_connector(fiscal_config)
            
            result = pac.cancelar_cfdi(uuid, motivo, folio_sustitucion)
            
            if result.get('success'):
                # Update database
                self.core.db.execute_write(
                    """UPDATE cfdis 
                       SET estado = 'cancelado',
                           motivo_cancelacion = %s,
                           fecha_cancelacion = %s
                       WHERE uuid = %s""",
                    (motivo, result.get('fecha_cancelacion'), uuid)
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Error canceling CFDI {uuid}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_credit_note(
        self,
        original_uuid: str,
        customer_rfc: str,
        customer_name: Optional[str] = None,
        customer_regime: str = '616',
        uso_cfdi: str = 'G02',
        items: Optional[list] = None,
        descripcion: str = 'Nota de crédito por devolución'
    ) -> Dict[str, Any]:
        """
        Generate a credit note (Nota de Crédito - CFDI tipo E).
        
        Args:
            original_uuid: UUID of the original CFDI being credited
            customer_rfc: Customer's RFC
            customer_name: Customer's legal name
            customer_regime: Customer's fiscal regime
            uso_cfdi: CFDI use code (G02 = devolución/descuento)
            items: List of items to credit (if None, uses original CFDI items)
            descripcion: Description of the credit note
            
        Returns:
            Dictionary with success, uuid, xml_path, etc.
        """
        try:
            # Step 1: Get original CFDI
            original_cfdi = self.core.db.execute_query(
                "SELECT * FROM cfdis WHERE uuid = %s",
                (original_uuid,)
            )
            
            if not original_cfdi:
                return {
                    'success': False,
                    'error': f'CFDI original {original_uuid} no encontrado'
                }
            
            original = dict(original_cfdi[0])
            original_sale_id = original.get('sale_id')
            
            # Step 2: Get fiscal configuration
            fiscal_config = self.core.get_fiscal_config()
            if not fiscal_config or not fiscal_config.get('rfc_emisor'):
                return {
                    'success': False,
                    'error': 'Configuración fiscal no encontrada'
                }
            
            # Step 3: Prepare credit note data
            if items is None and original_sale_id:
                # Get items from original sale
                sale_data = self.core.get_sale_details(original_sale_id)
                items = sale_data.get('items', []) if sale_data else []
            
            if not items:
                return {
                    'success': False,
                    'error': 'No hay productos para la nota de crédito'
                }
            
            # Calculate totals
            subtotal = sum(float(item.get('total', 0)) for item in items)
            tax_rate = 0.16  # IVA
            tax = subtotal * tax_rate
            total = subtotal + tax
            
            credit_note_data = {
                'tipo_comprobante': 'E',  # Egreso (Nota de Crédito)
                'subtotal': subtotal,
                'tax': tax,
                'total': total,
                'items': items,
                'timestamp': None,  # Will use current time
                'cfdi_relacionado': original_uuid,
                'tipo_relacion': '01',  # 01 = Nota de crédito
                'descripcion_nota': descripcion
            }
            
            customer_data = {
                'rfc': customer_rfc.upper(),
                'nombre': customer_name or original.get('nombre_receptor', 'PUBLICO EN GENERAL'),
                'codigo_postal': '00000',
                'regimen_fiscal': customer_regime,
                'uso_cfdi': uso_cfdi
            }
            
            # Step 4: Build XML with tipo E
            from app.fiscal.cfdi_builder import CFDIBuilder
            builder = CFDIBuilder(fiscal_config)
            xml_unsigned = builder.build_credit_note(credit_note_data, customer_data)
            
            logger.info(f"Credit note XML generated for original CFDI {original_uuid}")
            
            # Step 5: Sign XML
            from app.fiscal.signature import sign_cfdi_xml
            xml_signed = sign_cfdi_xml(xml_unsigned, fiscal_config)
            
            # Step 6: Send to PAC
            from app.fiscal.pac_connector import create_pac_connector
            pac = create_pac_connector(fiscal_config)
            
            timbrado_result = pac.timbrar_cfdi(xml_signed)
            
            if not timbrado_result.get('success'):
                return {
                    'success': False,
                    'error': f"Error en timbrado: {timbrado_result.get('error', 'Unknown')}"
                }
            
            # Step 7: Save
            uuid = timbrado_result['uuid']
            xml_timbrado = timbrado_result['xml_timbrado']
            
            cfdi_record = {
                'sale_id': None,  # Credit notes don't link to sales directly
                'uuid': uuid,
                'folio': fiscal_config.get('folio_actual', 1),
                'serie': fiscal_config.get('serie_nota_credito', 'NC'),
                'tipo_comprobante': 'E',
                'rfc_receptor': customer_rfc,
                'nombre_receptor': customer_data['nombre'],
                'regimen_receptor': customer_regime,
                'uso_cfdi': uso_cfdi,
                'xml_original': xml_signed,
                'xml_timbrado': xml_timbrado,
                'total': total,
                'subtotal': subtotal,
                'impuestos': tax,
                'cfdi_relacionado': original_uuid,
                'tipo_relacion': '01',
            }
            
            cfdi_id = self._save_cfdi(cfdi_record)
            
            # Increment folio
            self.core.update_fiscal_config({
                'folio_actual': fiscal_config.get('folio_actual', 1) + 1
            })
            
            xml_path = self._save_xml_file(uuid, xml_timbrado)
            
            logger.info(f"Credit note {uuid} created successfully")
            
            result_data = {
                'success': True,
                'cfdi_id': cfdi_id,
                'uuid': uuid,
                'xml_path': xml_path,
                'total': total,
                'original_uuid': original_uuid
            }
            
            # Generate PDF
            try:
                from app.fiscal.pdf_generator import generate_cfdi_pdf
                pdf_path = generate_cfdi_pdf(cfdi_id, self.core)
                result_data['pdf_path'] = pdf_path
            except Exception as e:
                logger.warning(f"PDF generation failed: {e}")
            
            return result_data
            
        except Exception as e:
            logger.error(f"Error generating credit note: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
