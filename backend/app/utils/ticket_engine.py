import logging
import os
from datetime import datetime

# FIX 2026-02-01: Import agent_log_enabled ANTES de usarla
try:
    from app.utils.path_utils import agent_log_enabled
except ImportError:
    def agent_log_enabled(): return False

# CONFIGURACIÓN DE ENTORNO
# Por defecto PRODUCTION para Gold Master
ENV = os.environ.get("TITAN_ENV", "PRODUCTION") 

class HardwareError(Exception):
    pass

def _numero_a_letra(numero: float) -> str:
    """
    Convierte un número a su representación en letras (español mexicano).
    Ejemplo: 643.00 -> "SEISCIENTOS CUARENTA Y TRES PESOS 00/100 M.N."
    """
    try:
        # Separar entero y decimal
        entero = int(numero)
        centavos = int(round((numero - entero) * 100))
        
        # Diccionarios de conversión
        unidades = ['', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE']
        especiales = ['DIEZ', 'ONCE', 'DOCE', 'TRECE', 'CATORCE', 'QUINCE', 
                      'DIECISEIS', 'DIECISIETE', 'DIECIOCHO', 'DIECINUEVE']
        decenas = ['', 'DIEZ', 'VEINTE', 'TREINTA', 'CUARENTA', 'CINCUENTA', 
                   'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA']
        centenas = ['', 'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS', 
                    'QUINIENTOS', 'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS', 'NOVECIENTOS']
        
        def _convertir_grupo(n):
            """Convierte un número de 0 a 999 a letras."""
            if n == 0:
                return ''
            if n == 100:
                return 'CIEN'
            
            resultado = ''
            c = n // 100
            d = (n % 100) // 10
            u = n % 10
            
            if c > 0:
                resultado += centenas[c] + ' '
            
            if d == 1:  # 10-19
                resultado += especiales[u]
                return resultado.strip()
            elif d == 2 and u > 0:  # 21-29
                resultado += 'VEINTI' + unidades[u]
                return resultado.strip()
            elif d > 0:
                resultado += decenas[d]
                if u > 0:
                    resultado += ' Y ' + unidades[u]
            else:
                resultado += unidades[u]
            
            return resultado.strip()
        
        if entero == 0:
            texto = 'CERO'
        elif entero == 1:
            texto = 'UN'
        else:
            # Separar en millones, miles y unidades
            millones = entero // 1000000
            miles = (entero % 1000000) // 1000
            unidades_grupo = entero % 1000
            
            partes = []
            if millones > 0:
                if millones == 1:
                    partes.append('UN MILLON')
                else:
                    partes.append(_convertir_grupo(millones) + ' MILLONES')
            
            if miles > 0:
                if miles == 1:
                    partes.append('MIL')
                else:
                    partes.append(_convertir_grupo(miles) + ' MIL')
            
            if unidades_grupo > 0:
                partes.append(_convertir_grupo(unidades_grupo))
            
            texto = ' '.join(partes)
        
        return f"{texto} PESOS {centavos:02d}/100 M.N."
        
    except Exception:
        # Fallback simple
        return f"{numero:.2f} PESOS"

def print_ticket(core, sale_id):
    """Imprime un ticket de venta dado su ID."""
    try:
        sale = core.get_sale_details(sale_id)
        if not sale:
            logging.error(f"Sale {sale_id} not found for printing")
            return

        # Get printer configuration
        cfg = core.get_app_config()
        printer_name = cfg.get("printer_name", "")
        
        if not printer_name:
            raise HardwareError("No hay impresora configurada. Vaya a Configuración.")
        
        # Build ticket content
        ticket_content = build_custom_ticket(cfg, sale, core)
        
        # DEBUG: Log first 500 chars of ticket to verify content
        logging.info(f"=== TICKET CONTENT (first 500 chars) ===")
        logging.info(ticket_content[:500])
        logging.info(f"=== END TICKET CONTENT ===")
        
        # Print using CUPS lp command
        import subprocess
        
        logging.info(f"Printing Ticket #{sale_id} to {printer_name}")
        
        # ESC/POS Initialization: Reset printer to ensure clean state
        # ESC @ (0x1B 0x40) = Initialize printer
        init_sequence = b'\x1B\x40'
        
        # Combine init sequence with ticket content
        # Encoding para impresora termica ESC/POS (requiere latin-1/CP437)
        full_content = init_sequence + ticket_content.encode('latin-1', errors='replace')
        
        result = subprocess.run(
            ["lp", "-d", printer_name, "-o", "raw", "-"],
            input=full_content,
            capture_output=True,
            timeout=10
        )
        
        if result.returncode == 0:
            output = result.stdout.decode('utf-8', errors='ignore').strip()
            logging.info(f"Ticket printed successfully: {output}")
        else:
            error_msg = result.stderr.decode('utf-8', errors='ignore')
            logging.error(f"Print error: {error_msg}")
            raise HardwareError(f"Error de Impresora: {error_msg}")
            
    except subprocess.TimeoutExpired:
        raise HardwareError("Timeout: La impresora no responde")
    except FileNotFoundError:
        raise HardwareError("Comando 'lp' no encontrado. ¿CUPS instalado?")
    except HardwareError:
        raise  # Re-raise para UI
    except Exception as e:
        logging.error(f"Error printing ticket: {e}")
        raise HardwareError(f"Error al imprimir: {e}")

def build_custom_ticket(cfg, sale_data, core=None):
    """
    Construye el contenido del ticket basado en la configuración personalizada.
    Cumple con requisitos fiscales SAT México (CFDI 4.0):
    - Art. 29-A del CFF
    - Regla 2.7.1.24 de la RMF
    """
    try:
        from app.core import STATE
        
        # Load ticket design configuration from DATABASE
        if core:
            ticket_cfg = core.get_ticket_config(STATE.branch_id)
        else:
            # Fallback if core not provided (backward compatibility)
            from app.core import core_instance
            ticket_cfg = core_instance.get_ticket_config(STATE.branch_id)
        
        # If no config in DB, use defaults
        if not ticket_cfg:
            ticket_cfg = {
                "business_name": cfg.get('store_name', 'TITAN POS'),
                "business_address": cfg.get('store_address', ''),
                "business_phone": "",
                "business_rfc": "",
                "business_razon_social": "",
                "business_regime": "",
                "business_street": "",
                "business_cross_streets": "",
                "business_neighborhood": "",
                "business_city": "",
                "business_state": "",
                "business_postal_code": "",
                "show_product_code": True,
                "show_unit": False,
                "price_decimals": 2,
                "currency_symbol": "$",
                "show_separators": True,
                "thank_you_message": "¡Gracias por su compra!",
                "legal_text": "",
                "qr_enabled": False,
                "line_spacing": 1.0,
                "margin_chars": 0,
                "margin_top": 0,
                "margin_bottom": 0,
                "cut_lines": 3,
                "bold_headers": True,
                "show_invoice_code": True,
                "invoice_url": "",
                "invoice_days_limit": 3
            }
        
        # Get paper width for formatting
        paper_width = cfg.get("ticket_paper_width", "80mm")
        line_width = 48 if paper_width == "80mm" else 32
        
        # Apply margins
        margin = ticket_cfg.get("margin_chars", 0)
        usable_width = line_width - (margin * 2)
        margin_str = " " * margin
        
        lines = []
        
        # THERMAL PRINTER FIX: Add padding at the start
        # The printer "eats" the first few lines during initialization
        # Using spaces (not blank lines) forces the print head to activate
        for _ in range(3):
            lines.append(" " * usable_width)
        
        # Top margin (user-configurable blank lines)
        margin_top = ticket_cfg.get("margin_top", 0)
        lines.extend([""] * margin_top)
        
        # === HEADER - DATOS DEL EMISOR (Obligatorio SAT) ===
        if ticket_cfg.get("show_logo", False) and ticket_cfg.get("logo_path"):
            lines.append(margin_str + "[LOGO]".center(usable_width))
            lines.append("")
        
        # Business name (Nombre Comercial)
        business_name = ticket_cfg.get("business_name", "TITAN POS")
        if ticket_cfg.get("bold_headers", True):
            lines.append(margin_str + business_name.center(usable_width).upper())
        else:
            lines.append(margin_str + business_name.center(usable_width))
        
        # Razón Social (si es diferente al nombre comercial)
        # Primero intenta ticket config, luego fallback a config fiscal
        razon_social = ticket_cfg.get("business_razon_social", "")
        if not razon_social and core:
            try:
                fiscal_cfg = core.get_fiscal_config(STATE.branch_id)
                razon_social = fiscal_cfg.get("razon_social_emisor", "") if fiscal_cfg else ""
            except Exception:
                pass  # Config fiscal no disponible
        if razon_social and razon_social.strip() and razon_social.strip().upper() != business_name.strip().upper():
            lines.append(margin_str + razon_social.center(usable_width))
        
        # RFC del Emisor (Obligatorio)
        if ticket_cfg.get("business_rfc"):
            lines.append(margin_str + f"RFC: {ticket_cfg['business_rfc']}".center(usable_width))
        
        # Régimen Fiscal (Obligatorio SAT)
        if ticket_cfg.get("business_regime"):
            regime = ticket_cfg['business_regime']
            # Split long regime names across multiple lines if needed
            if len(regime) > usable_width:
                words = regime.split()
                current_line = ""
                for word in words:
                    if len(current_line) + len(word) + 1 <= usable_width:
                        current_line += word + " "
                    else:
                        if current_line:
                            lines.append(margin_str + current_line.strip().center(usable_width))
                        current_line = word + " "
                if current_line:
                    lines.append(margin_str + current_line.strip().center(usable_width))
            else:
                lines.append(margin_str + regime.center(usable_width))
        
        # Detailed address - Use new fields
        street = ticket_cfg.get("business_street", "")
        cross_streets = ticket_cfg.get("business_cross_streets", "")
        neighborhood = ticket_cfg.get("business_neighborhood", "")
        city = ticket_cfg.get("business_city", "")
        state = ticket_cfg.get("business_state", "")
        postal_code = ticket_cfg.get("business_postal_code", "")
        
        # Build address lines
        if street:
            lines.append(margin_str + street.center(usable_width))
        if cross_streets:
            lines.append(margin_str + cross_streets.center(usable_width))
        if neighborhood:
            lines.append(margin_str + neighborhood.center(usable_width))
        
        # Ciudad, Estado y CP (Obligatorio SAT - Lugar de Expedición)
        if city or state or postal_code:
            city_state = f"{city}, {state}" if city and state else (city or state)
            if postal_code:
                city_state += f", CP {postal_code}"
            lines.append(margin_str + city_state.center(usable_width))
        
        # Phone
        if ticket_cfg.get("business_phone"):
            lines.append(margin_str + f"Tel: {ticket_cfg['business_phone']}".center(usable_width))
        
        if ticket_cfg.get("show_separators", True):
            lines.append(margin_str + "=" * usable_width)
        else:
            lines.append("")
        
        # === SALE INFO - FOLIO Y FECHA ===
        # Folio con Serie (A-000001 o B-000001)
        serie = sale_data.get('serie', 'B')
        folio_visible = sale_data.get('folio_visible', '')
        sale_id = sale_data.get('id', 'N/A')
        
        if folio_visible:
            folio_display = folio_visible
        else:
            folio_display = f"{serie}-{sale_id:06d}" if isinstance(sale_id, int) else f"{serie}-{sale_id}"
        
        lines.append(margin_str + f"Ticket: #{sale_id}".ljust(usable_width//2) + f"Folio: {folio_display}".rjust(usable_width//2))
        
        # Format date (Obligatorio SAT - Fecha y Hora)
        created_at = sale_data.get('created_at', sale_data.get('timestamp', ''))
        if created_at:
            try:
                from datetime import datetime
                if 'T' in created_at:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    created_at = dt.strftime("%d/%m/%Y %H:%M")
            except Exception:
                pass  # Formato de fecha fallido, usar original
        lines.append(margin_str + f"Fecha: {created_at}")
        
        if ticket_cfg.get("show_separators", True):
            lines.append(margin_str + "-" * usable_width)
        else:
            lines.append("")
        
        # === ITEMS ===
        decimals = ticket_cfg.get("price_decimals", 2)
        currency = ticket_cfg.get("currency_symbol", "$")
        show_code = ticket_cfg.get("show_product_code", True)
        show_unit = ticket_cfg.get("show_unit", False)
        
        for item in sale_data.get('items', []):
            # Product name line
            qty = item.get('qty', 0)
            name = item.get('name', 'Producto')
            price = float(item.get('price', 0))  # Precio guardado (sin IVA si price_includes_tax era True)
            line_discount = float(item.get('discount', 0))
            is_wholesale = item.get('is_wholesale', False)
            
            # CRITICAL FIX: El precio guardado en sale_items.price es SIN IVA (porque price_includes_tax era True)
            # Por lo tanto, debemos calcular el precio con IVA para mostrarlo correctamente
            # El precio mostrado debe ser el precio final que el usuario espera ver (con IVA incluido)
            # TAX_RATE = 0.16 (16%)
            TAX_RATE = 0.16
            # Siempre mostrar el precio con IVA, ya que el precio guardado es sin IVA
            price_to_display = price * (1 + TAX_RATE)
            
            # CRITICAL FIX: item_total también debe calcularse con el precio con IVA
            # El subtotal de la BD es sin IVA, pero el usuario espera ver el total con IVA
            # Calcular: (qty * price_to_display) - line_discount
            item_total = (qty * price_to_display) - line_discount
            
            # First line: qty x name (with wholesale indicator)
            if is_wholesale:
                line1 = f"{qty} x {name} (Mayoreo)"
            else:
                line1 = f"{qty} x {name}"
            lines.append(margin_str + line1)
            
            # SAT Code line (for invoicing) - Always show SAT code with description
            sat_code = item.get('sat_clave_prod_serv', '01010101')
            sat_desc = item.get('sat_descripcion', '')
            if sat_code:
                if sat_desc:
                    lines.append(margin_str + f"  SAT: {sat_code} - {sat_desc}"[:usable_width])
                else:
                    lines.append(margin_str + f"  SAT: {sat_code}")
            
            # Second line: code (optional)
            if show_code and item.get('barcode'):
                lines.append(margin_str + f"  Cod: {item['barcode']}")
            
            # Third line: unit price and total
            # CRITICAL DEBUG: Log price calculation for debugging price discrepancies
            # #region agent log
            if agent_log_enabled():
                import json, time
                try:
                    from app.utils.path_utils import get_debug_log_path_str  # FIX: agent_log_enabled ya importado arriba
                    with open(get_debug_log_path_str(), "a") as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"PRICE_DEBUG","location":"ticket_engine.py:build_custom_ticket","message":"Price display in ticket","data":{"item_price":price,"item_total":item_total,"qty":qty,"line_discount":line_discount,"item_data":{k:v for k,v in item.items() if k in ['price','base_price','subtotal','total','discount']}},"timestamp":int(time.time()*1000)})+"\n")
                except Exception as e: logging.debug("Writing price display debug log: %s", e)
            # #endregion
            price_str = f"{currency}{price_to_display:.{decimals}f}"
            total_str = f"{currency}{item_total:.{decimals}f}"
            
            if show_unit and item.get('unit'):
                unit_line = f"  {price_str}/{item['unit']}"
            else:
                unit_line = f"  {price_str} c/u"
            
            # Right-align total
            spaces_needed = usable_width - len(unit_line) - len(total_str)
            lines.append(margin_str + unit_line + " " * max(0, spaces_needed) + total_str)
            
            # Show line discount if present
            if line_discount > 0:
                lines.append(margin_str + f"  Desc: -{currency}{line_discount:.{decimals}f}")
            
            # Add spacing between items
            spacing = int(ticket_cfg.get("line_spacing", 1.0))
            if spacing > 1:
                lines.extend([""] * (spacing - 1))
        
        if ticket_cfg.get("show_separators", True):
            lines.append(margin_str + "-" * usable_width)
        else:
            lines.append("")
        
        # === TOTALS ===
        subtotal = float(sale_data.get('subtotal', 0))
        tax = float(sale_data.get('tax', 0))
        discount = float(sale_data.get('discount', 0))
        total = float(sale_data.get('total', 0))
        
        # If subtotal is 0 or missing, calculate from total - tax
        if subtotal == 0 and total > 0:
            subtotal = total - tax
        
        # Show subtotal (always)
        lines.append(margin_str + f"Subtotal:".ljust(usable_width - 10) + f"{currency}{subtotal:.{decimals}f}".rjust(10))
        
        # Show tax/IVA if present
        if tax > 0:
            lines.append(margin_str + f"IVA:".ljust(usable_width - 10) + f"{currency}{tax:.{decimals}f}".rjust(10))
        
        # Show discount if present
        if discount > 0:
            lines.append(margin_str + f"Descuento:".ljust(usable_width - 10) + f"-{currency}{discount:.{decimals}f}".rjust(10))
        
        # Separator before total
        if ticket_cfg.get("show_separators", True):
            lines.append(margin_str + "-" * usable_width)
        
        # Total in bold if enabled
        total_line = f"TOTAL:".ljust(usable_width - 10) + f"{currency}{total:.{decimals}f}".rjust(10)
        if ticket_cfg.get("bold_headers", True):
            lines.append(margin_str + total_line.upper())
        else:
            lines.append(margin_str + total_line)
        
        # Total en letra (Obligatorio SAT)
        total_letra = _numero_a_letra(total)
        if len(total_letra) > usable_width:
            # Split into multiple lines if too long
            words = total_letra.split()
            current_line = "("
            for word in words:
                if len(current_line) + len(word) + 1 <= usable_width - 1:
                    current_line += word + " "
                else:
                    lines.append(margin_str + current_line.strip())
                    current_line = word + " "
            if current_line:
                lines.append(margin_str + current_line.strip() + ")")
        else:
            lines.append(margin_str + f"({total_letra})".center(usable_width))
        
        if ticket_cfg.get("show_separators", True):
            lines.append(margin_str + "=" * usable_width)
        else:
            lines.append("")
        
        # === PAYMENT INFO ===
        payment_method = sale_data.get('payment_method', '')
        
        # Mapeo de métodos de pago con claves SAT
        method_names = {
            'cash': 'Efectivo (01)',
            'card': 'Tarjeta de Crédito (04)',
            'credit_card': 'Tarjeta de Crédito (04)',
            'debit_card': 'Tarjeta de Débito (28)',
            'credit': 'Crédito (99)',
            'wallet': 'Monedero Electrónico (05)',
            'mixed': 'Pago Mixto (99)',
            'transfer': 'Transferencia (03)',
            'check': 'Cheque (02)',
            'cheque': 'Cheque (02)',
            'usd': 'Dólares USD (01)',
            'vales': 'Vales de Despensa (08)',
            'voucher': 'Vales (08)',
            'gift_card': 'Tarjeta de Regalo (05)'
        }
        
        if payment_method:
            method_display = method_names.get(payment_method, payment_method.title())
            lines.append(margin_str + f"Pago: {method_display}")
            
            # For cash payments, show amount paid and change
            if payment_method == 'cash':
                cash_received = float(sale_data.get('cash_received', 0))
                if cash_received > 0:
                    lines.append(margin_str + f"Recibido: {currency}{cash_received:.{decimals}f}")
                    change = cash_received - total
                    if change > 0:
                        lines.append(margin_str + f"Cambio: {currency}{change:.{decimals}f}")
            
            # For card payments, show last 4 digits if available
            elif payment_method == 'card':
                card_last4 = sale_data.get('card_last4', '')
                auth_code = sale_data.get('auth_code', '')
                if card_last4:
                    lines.append(margin_str + f"Tarjeta: ****{card_last4}")
                if auth_code:
                    lines.append(margin_str + f"Autorización: {auth_code}")
            
            # For transfer, show reference
            elif payment_method == 'transfer':
                reference = sale_data.get('transfer_reference', '')
                if reference:
                    lines.append(margin_str + f"Referencia: {reference}")
            
            # For mixed payments, show breakdown
            elif payment_method == 'mixed':
                cash_amount = float(sale_data.get('mixed_cash', 0))
                card_amount = float(sale_data.get('mixed_card', 0))
                if cash_amount > 0:
                    lines.append(margin_str + f"  Efectivo: {currency}{cash_amount:.{decimals}f}")
                if card_amount > 0:
                    lines.append(margin_str + f"  Tarjeta: {currency}{card_amount:.{decimals}f}")
        
        if ticket_cfg.get("show_separators", True):
            lines.append(margin_str + "=" * usable_width)
        else:
            lines.append("")
        
        # === FOOTER - INFORMACIÓN FISCAL ===
        serie = sale_data.get('serie', 'B')
        folio_visible = sale_data.get('folio_visible', '')
        sale_id = sale_data.get('id', 'N/A')
        
        # Código de facturación (para auto-factura posterior)
        if ticket_cfg.get("show_invoice_code", True):
            # Generate invoice code: A-YYYY-XXX-NN
            from datetime import datetime
            year = datetime.now().strftime("%Y")
            invoice_code = folio_visible if folio_visible else f"{serie}-{year}-{sale_id}"
            
            lines.append(margin_str + "-" * usable_width)
            lines.append(margin_str + "PARA FACTURAR ESTA COMPRA:".center(usable_width))
            
            invoice_url = ticket_cfg.get("invoice_url", "")
            if invoice_url:
                lines.append(margin_str + f"1. Ingrese a: {invoice_url}"[:usable_width])
            
            lines.append(margin_str + f"2. Use el Código: {invoice_code}".center(usable_width))
            
            invoice_days = ticket_cfg.get("invoice_days_limit", 3)
            lines.append(margin_str + f"Vigencia: {invoice_days} días naturales".center(usable_width))
            lines.append(margin_str + "-" * usable_width)
        
        # Leyenda según tipo de Serie
        if serie == 'B':
            # Serie B = Público en General → Va a Factura Global
            lines.append(margin_str + "RFC: XAXX010101000 (Público General)".center(usable_width))
            lines.append(margin_str + "Este ticket forma parte de la".center(usable_width))
            lines.append(margin_str + "factura global del período.".center(usable_width))
            lines.append(margin_str + "*IVA Incluido*".center(usable_width))
        else:
            # Serie A = Factura individual posible
            lines.append(margin_str + "Solicite su factura con este folio.".center(usable_width))
        
        lines.append("")
        
        # Thank you message
        thank_you = ticket_cfg.get("thank_you_message", "¡Gracias por su compra!")
        if thank_you:
            lines.append(margin_str + thank_you.center(usable_width))
            lines.append("")
        
        # Legal text
        legal = ticket_cfg.get("legal_text", "")
        if legal:
            # Wrap legal text if too long
            words = legal.split()
            current_line = ""
            for word in words:
                if len(current_line) + len(word) + 1 <= usable_width:
                    current_line += word + " "
                else:
                    lines.append(margin_str + current_line.strip())
                    current_line = word + " "
            if current_line:
                lines.append(margin_str + current_line.strip())
            lines.append("")
        
        # QR Code placeholder (para facturación)
        if ticket_cfg.get("qr_enabled", False):
            qr_content = ticket_cfg.get("qr_content_type", "url")
            invoice_url = ticket_cfg.get("invoice_url", ticket_cfg.get("website_url", ""))
            
            if qr_content == "invoice" and invoice_url:
                # QR para facturación con código embebido
                qr_url = f"{invoice_url}?code={folio_visible or sale_id}"
                lines.append(margin_str + f"[QR: {qr_url}]".center(usable_width))
            elif qr_content == "url" and ticket_cfg.get("website_url"):
                lines.append(margin_str + f"[QR: {ticket_cfg['website_url']}]".center(usable_width))
            elif qr_content == "folio":
                folio = folio_visible or f"#{sale_id}"
                lines.append(margin_str + f"[QR: Folio {folio}]".center(usable_width))
            lines.append("")
        
        # Website/social
        if ticket_cfg.get("website_url"):
            lines.append(margin_str + ticket_cfg["website_url"].center(usable_width))
        
        # Bottom margin (blank lines before cut)
        margin_bottom = ticket_cfg.get("margin_bottom", 0)
        lines.extend([""] * margin_bottom)
        
        # Cut lines
        cut_lines = ticket_cfg.get("cut_lines", 3)
        lines.extend([""] * cut_lines)
        
        return "\n".join(lines)
        
    except Exception as e:
        logging.error(f"Error building custom ticket: {e}", exc_info=True)
        # Fallback to simple format
        lines = []
        lines.append(f"{cfg.get('store_name', 'TITAN POS')}")
        folio = sale_data.get('folio_visible') or f"#{sale_data.get('id')}"
        lines.append(f"Folio: {folio}")
        lines.append(f"Total: ${sale_data.get('total', 0)}")
        lines.append("Error en formato personalizado")
        return "\n".join(lines)

def print_test_ticket(printer_name):
    """Imprime un ticket de prueba usando CUPS."""
    import subprocess
    from datetime import datetime
    
    logging.info(f"Printing test ticket to: {printer_name}")
    
    if not printer_name:
        raise HardwareError("Impresora no configurada.")
    
    # Build test ticket content
    test_content = f"""
{"=" * 40}
     TITAN POS - TICKET DE PRUEBA
{"=" * 40}

Impresora: {printer_name}
Fecha: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}

{"*" * 40}
     PRUEBA EXITOSA
{"*" * 40}

Si puedes leer este texto,
la impresora está configurada
correctamente.

"""
    
    try:
        result = subprocess.run(
            ["lp", "-d", printer_name, "-o", "raw", "-"],
            input=test_content.encode('latin-1', errors='replace'),
            capture_output=True,
            timeout=10
        )
        
        if result.returncode == 0:
            output = result.stdout.decode('utf-8', errors='ignore').strip()
            logging.info(f"Test ticket printed successfully: {output}")
            return True
        else:
            error_msg = result.stderr.decode('utf-8', errors='ignore')
            logging.error(f"Print test error: {error_msg}")
            raise HardwareError(f"Error de Impresora: {error_msg}")
            
    except subprocess.TimeoutExpired:
        raise HardwareError("Timeout: La impresora no responde")
    except FileNotFoundError:
        raise HardwareError("Comando 'lp' no encontrado. ¿CUPS instalado?")
    except HardwareError:
        raise
    except Exception as e:
        logging.error(f"Error printing test ticket: {e}")
        raise HardwareError(f"Error al imprimir prueba: {e}")

def open_cash_drawer_safe(core=None, config=None):
    """
    Abre el cajón de dinero de forma segura usando la configuración del core.
    Helper function para usar en múltiples lugares.
    
    Args:
        core: Instancia de POSCore (opcional, si no se proporciona usa STATE)
        config: Diccionario de configuración (opcional, si no se proporciona lo obtiene del core)
    
    Returns:
        bool: True si se abrió exitosamente, False si falló o está deshabilitado
    """
    try:
        from app.core import STATE
        
        if core is None:
            # Intentar obtener core desde STATE si está disponible
            if hasattr(STATE, 'core'):
                core = STATE.core
            else:
                logging.warning("No se pudo obtener core para abrir cajón")
                return False
        
        if config is None:
            cfg = core.get_ticket_config(STATE.branch_id) or {}
            if not cfg:
                cfg = core.get_app_config() or {}
        else:
            cfg = config
        
        if not cfg.get("cash_drawer_enabled"):
            return False
        
        printer_name = cfg.get("printer_name") or (core.get_app_config() or {}).get("printer_name", "")
        if not printer_name:
            return False
        
        pulse_str = cfg.get("cash_drawer_pulse_bytes", "\\x1B\\x70\\x00\\x19\\xFA")
        
        open_cash_drawer(printer_name, pulse_str)
        return True
    except Exception as e:
        logging.warning(f"No se pudo abrir el cajón: {e}")
        return False

def open_cash_drawer(printer_name, pulse_bytes=None):
    """
    Envía comando para abrir el cajón de dinero con bypass USB directo.
    
    OPTIMIZADO: Bypass USB directo para máxima velocidad
    - Pulso de 5ms (comando óptimo para Caysn/Ghia)
    - Escritura directa a /dev/usb/lpX
    - Tiempo: ~1-1.5 segundos (vs 5-10s con CUPS)
    
    Args:
        printer_name: Nombre de la impresora en CUPS (usado como fallback)
        pulse_bytes: Secuencia de bytes del comando. Si es None, usa el optimizado.
    
    Comando optimizado (5ms):
        b'\\x1B\\x70\\x00\\x05\\x30'  - ESC p 0 5 48 (Pin 2, 5ms on, 48ms off)
    """
    import subprocess
    import time
    import os
    
    start_time = time.time()
    logging.info(f"💵 Opening cash drawer (USB bypass)")
    
    if not printer_name:
        raise HardwareError("Cajón no configurado.")
    
    # Presets de comandos comunes
    DRAWER_PRESETS = {
        'optimizado': b'\x1B\x70\x00\x05\x30',       # 5ms (MÁS RÁPIDO)
        'epson_pin2': b'\x1B\x70\x00\x19\xFA',      # 25ms estándar
        'epson_pin5': b'\x1B\x70\x01\x19\xFA',      # Pin 5
        'dle_dc4': b'\x10\x14\x01\x00\x05',         # DLE DC4 (genéricos)
        'pulse_corto': b'\x1B\x70\x00\x0F\x50',     # 15ms
    }
    
    # Default: Comando OPTIMIZADO de 5ms
    if pulse_bytes is None:
        pulse_bytes = b'\x1B\x70\x00\x05\x30'  # Mejor rendimiento verificado
    elif isinstance(pulse_bytes, str):
        if pulse_bytes in DRAWER_PRESETS:
            pulse_bytes = DRAWER_PRESETS[pulse_bytes]
        else:
            try:
                pulse_bytes = bytes(pulse_bytes, 'utf-8').decode('unicode_escape').encode('latin-1')
            except Exception as e:
                logging.warning(f"Error parsing pulse_bytes: {e}, using optimized")
                pulse_bytes = b'\x1B\x70\x00\x05\x30'
    
    # ESTRATEGIA 1: Bypass USB directo (MÁS RÁPIDO)
    # Buscar dispositivo USB de la impresora
    usb_devices = []
    if os.path.exists('/dev/usb/'):
        usb_devices = [f'/dev/usb/{f}' for f in os.listdir('/dev/usb/') if f.startswith('lp')]
    
    for device in usb_devices:
        try:
            if os.path.exists(device):
                logging.debug(f"Trying USB bypass: {device}")
                with open(device, 'wb') as f:
                    f.write(pulse_bytes)
                
                elapsed = (time.time() - start_time) * 1000
                logging.info(f"✅ Cash drawer opened via USB bypass ({elapsed:.0f}ms)")
                return True
        except PermissionError:
            logging.debug(f"Permission denied for {device}, trying next...")
            continue
        except Exception as e:
            logging.debug(f"Failed to open {device}: {e}")
            continue
    
    # ESTRATEGIA 2: Fallback a CUPS con alta prioridad
    logging.warning("⚠️ USB bypass failed, falling back to CUPS...")
    try:
        logging.debug("Using CUPS with high priority (-q 100)")
        result = subprocess.run(
            ["lp", "-q", "100", "-d", printer_name, "-o", "raw", "-"],
            input=pulse_bytes,
            capture_output=True,
            timeout=2
        )
        
        if result.returncode == 0:
            elapsed = (time.time() - start_time) * 1000
            logging.info(f"✅ Cash drawer opened via CUPS fallback ({elapsed:.0f}ms)")
            return True
        else:
            error_msg = result.stderr.decode('utf-8', errors='ignore')
            logging.error(f"Cash drawer error: {error_msg}")
            raise HardwareError(f"Error al abrir cajón: {error_msg}")
            
    except subprocess.TimeoutExpired:
        elapsed = (time.time() - start_time) * 1000
        logging.error(f"❌ Cash drawer timeout after {elapsed:.0f}ms")
        raise HardwareError("Timeout: La impresora no responde (2s)")
    except FileNotFoundError:
        raise HardwareError("Comando 'lp' no encontrado. ¿CUPS instalado?")
    except HardwareError:
        raise
    except Exception as e:
        logging.error(f"Error opening cash drawer: {e}")
        raise HardwareError(f"Error al abrir cajón: {e}")

def get_drawer_presets():
    """Retorna los presets disponibles para cajón de dinero."""
    return {
        'epson_pin2': {
            'name': 'EPSON/Compatible (Pin 2)',
            'bytes': '\\x1B\\x70\\x00\\x19\\xFA',
            'description': 'Comando estándar ESC/POS para la mayoría de impresoras'
        },
        'epson_pin5': {
            'name': 'EPSON/Compatible (Pin 5)',
            'bytes': '\\x1B\\x70\\x01\\x19\\xFA',
            'description': 'Para cajones conectados al pin 5 del conector'
        },
        'star': {
            'name': 'STAR Micronics (Legacy)',
            'bytes': '\\x1B\\x07',
            'description': 'Comando legacy para impresoras STAR antiguas'
        },
        'dle_dc4': {
            'name': 'Genérico (DLE DC4)',
            'bytes': '\\x10\\x14\\x01\\x00\\x05',
            'description': 'Alternativo para genéricos chinos'
        },
        'pulse_largo': {
            'name': 'Pulso Largo (100ms)',
            'bytes': '\\x1B\\x70\\x00\\x32\\xFA',
            'description': 'Para cajones que necesitan pulso más largo'
        },
        'pulse_corto': {
            'name': 'Pulso Corto (30ms)',
            'bytes': '\\x1B\\x70\\x00\\x0F\\x50',
            'description': 'Para cajones sensibles con pulso corto'
        },
    }

def print_turn_report(summary, core, report_type="CIERRE"):
    """
    Imprime un reporte de turno (cierre o corte parcial).
    
    Args:
        summary: Diccionario con datos del turno
        core: Instancia de POSCore para obtener configuración
        report_type: "CIERRE" o "CORTE PARCIAL"
    """
    try:
        cfg = core.get_app_config()
        printer_name = cfg.get("printer_name", "")
        printer_width = int(cfg.get("printer_width", 58))  # 58mm or 80mm
        
        # Calculate line width based on printer
        if printer_width == 80:
            line_width = 48
        else:  # 58mm
            line_width = 32
        
        # Build ticket content
        lines = []
        
        # Header
        store_name = cfg.get("store_name", "TITAN POS")
        lines.append(store_name.center(line_width))
        store_address = cfg.get("store_address", "")
        if store_address:
            lines.append(store_address.center(line_width))
        lines.append("=" * line_width)
        lines.append(f"REPORTE DE TURNO - {report_type}".center(line_width))
        lines.append("=" * line_width)
        
        # Turn info
        now = datetime.now().strftime("%d/%m/%Y %H:%M")
        lines.append(f"Fecha: {now}")
        # Get turn_id from summary - it might be 'id' or 'turn_id'
        turn_id = summary.get("turn_id") or summary.get("id", "N/A")
        lines.append(f"Turno #: {turn_id}")
        lines.append("-" * line_width)
        
        lines.append("-" * line_width)
        
        # Cash summary
        initial_cash = float(summary.get("initial_cash", 0))
        cash_sales = float(summary.get("cash_sales", 0))
        total_in = float(summary.get("total_in", 0))
        total_out = float(summary.get("total_out", 0))
        total_expenses = float(summary.get("total_expenses", 0))
        expected_cash = float(summary.get("expected_cash", 0))
        
        lines.append("RESUMEN DE EFECTIVO")
        lines.append(f"Fondo Inicial:    ${initial_cash:>10,.2f}")
        lines.append(f"Ventas Efectivo:  ${cash_sales:>10,.2f}")
        lines.append(f"Entradas (+):     ${total_in:>10,.2f}")
        lines.append(f"Salidas (-):      ${total_out:>10,.2f}")
        if total_expenses > 0:
            lines.append(f"Gastos (-):       ${total_expenses:>10,.2f}")
        lines.append("-" * line_width)
        lines.append(f"Efectivo Esperado: ${expected_cash:>9,.2f}")
        
        # Add Real Cash and Diff if provided (Closing Report)
        if "real_cash" in summary:
            real_cash = float(summary["real_cash"])
            diff = real_cash - expected_cash
            lines.append(f"Efectivo Real:     ${real_cash:>9,.2f}")
            lines.append(f"Diferencia:        ${diff:>9,.2f}")
            
        lines.append("=" * line_width)
        
        # Payment breakdown
        payment_breakdown = summary.get("payment_breakdown", {})
        if payment_breakdown:
            lines.append("DESGLOSE POR METODO DE PAGO")
            lines.append("-" * line_width)
            
            method_names = {
                'cash': 'Efectivo',
                'card': 'Tarjeta',
                'credit': 'Credito',
                'wallet': 'Puntos',
                'gift_card': 'Gift Card',
                'mixed': 'Mixto',
                'transfer': 'Transferencia',
                'cheque': 'Cheque'
            }
            
            for method, data in sorted(payment_breakdown.items()):
                if method == 'mixed_details': continue # Skip metadata
                
                method_name = method_names.get(method, method.title())
                count = data.get('count', 0)
                total = float(data.get('total', 0))
                lines.append(f"{method_name}:")
                lines.append(f"  {count} trans. = ${total:,.2f}")
                
            # Show Mixed Details if available
            mixed_details = payment_breakdown.get('mixed_details')
            if mixed_details:
                lines.append("  (De Mixto: Efec=${:,.2f} Tarj=${:,.2f})".format(
                    mixed_details.get('cash_component', 0),
                    mixed_details.get('card_component', 0)
                ))
            
            lines.append("-" * line_width)
            total_sales = float(summary.get("total_sales_all_methods", 0))
            lines.append(f"TOTAL VENTAS:     ${total_sales:>10,.2f}")
        
        lines.append("=" * line_width)

        # Notes if available
        if summary.get("notes"):
            lines.append("NOTAS:")
            lines.append(str(summary["notes"])[:line_width])
            lines.append("-" * line_width)
            
        # User info
        user_id = summary.get("user_id", "Desconocido")
        lines.append(f"Usuario: {user_id}")
        
        # Footer
        if report_type == "CIERRE":
            lines.append("TURNO CERRADO".center(line_width))
            lines.append("")
            lines.append("_" * (line_width - 10))
            lines.append("Firma Cajero".center(line_width))
        else:
            lines.append("CORTE PARCIAL".center(line_width))
            lines.append("(Turno sigue activo)".center(line_width))
        
        lines.append("")
        lines.append("Gracias".center(line_width))
        lines.append("")
        
        # Print
        content = "\n".join(lines)
        
        if ENV == "PRODUCTION" or ENV == "DEVELOPMENT":  # Allow printing in DEV if configured
            if not printer_name:
                raise HardwareError("Impresora no configurada")
            
            import subprocess
            logging.info(f"Printing turn report to {printer_name}")
            
            result = subprocess.run(
                ["lp", "-d", printer_name, "-o", "raw", "-"],
                input=content.encode('latin-1', errors='replace'),
                capture_output=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logging.info("Turn report printed successfully")
            else:
                error_msg = result.stderr.decode('utf-8', errors='ignore')
                logging.error(f"Print error: {error_msg}")
                raise HardwareError(f"Error de Impresora: {error_msg}")
        else:
            logging.info("[MOCK] Turn Report:")
            logging.info(content)
            
    except HardwareError:
        raise
    except Exception as e:
        logging.error(f"Error printing turn report: {e}")
        raise

def print_turn_open(data):
    """Imprime un ticket de apertura de turno usando CUPS."""
    import subprocess
    
    logging.info(f"Printing turn open ticket: {data}")
    
    # Build ticket content
    lines = []
    lines.append("=" * 40)
    lines.append("       APERTURA DE TURNO       ".center(40))
    lines.append("=" * 40)
    lines.append("")
    lines.append(f"Turno #: {data.get('turn_id', data.get('id', 'N/A'))}")
    lines.append(f"Fecha: {data.get('timestamp', data.get('created_at', ''))[:19]}")
    lines.append(f"Usuario: {data.get('user_id', 'N/A')}")
    lines.append("-" * 40)
    lines.append(f"Fondo Inicial: ${float(data.get('initial_cash', 0)):,.2f}")
    lines.append("=" * 40)
    lines.append("")
    lines.append("  Turno abierto correctamente  ".center(40))
    lines.append("")
    lines.append("")
    lines.append("")
    
    content = "\n".join(lines)
    
    # Get printer from config
    from app.core import core_instance
    cfg = core_instance.get_app_config()
    printer_name = cfg.get("printer_name", "")
    
    if not printer_name:
        logging.warning("No printer configured for turn open ticket")
        return  # Silently return if no printer configured
    
    try:
        result = subprocess.run(
            ["lp", "-d", printer_name, "-o", "raw", "-"],
            input=content.encode('latin-1', errors='replace'),
            capture_output=True,
            timeout=10
        )
        
        if result.returncode == 0:
            logging.info("Turn open ticket printed successfully")
        else:
            error_msg = result.stderr.decode('utf-8', errors='ignore')
            logging.error(f"Turn open print error: {error_msg}")
    except Exception as e:
        logging.error(f"Error printing turn open ticket: {e}")

def print_layaway_payment(layaway_data, payment_data):
    """Imprime un ticket de abono a apartado."""
    import subprocess
    from app.core import core_instance
    
    logging.info(f"Printing layaway payment ticket: {layaway_data.get('id', 'N/A')}")
    
    # Get printer configuration from app config
    cfg = core_instance.get_app_config()
    printer_name = cfg.get("printer_name", "")
    
    if not printer_name:
        logging.warning("No printer configured for layaway payment")
        raise HardwareError("No hay impresora configurada. Vaya a Configuración.")
    
    lines = []
    lines.append("=" * 40)
    lines.append("    COMPROBANTE DE ABONO    ".center(40))
    lines.append("=" * 40)
    lines.append("")
    lines.append(f"Folio Apartado: #{layaway_data.get('id', 'N/A')}")
    lines.append(f"Cliente: {layaway_data.get('customer_name', 'Cliente')}")
    lines.append("-" * 40)
    
    amount = float(payment_data.get('amount', 0))
    lines.append(f"Monto Abonado: ${amount:,.2f}")
    
    if payment_data.get('notes'):
        lines.append(f"Notas: {payment_data['notes']}")
    
    lines.append("")
    
    total_amount = float(layaway_data.get('total', 0))
    paid_total = float(layaway_data.get('paid_total', 0))
    balance = float(layaway_data.get('balance_calc', layaway_data.get('balance', total_amount - paid_total)))
    
    lines.append("-" * 40)
    lines.append(f"Total Apartado:    ${total_amount:,.2f}")
    lines.append(f"Total Pagado:      ${paid_total:,.2f}")
    lines.append(f"Saldo Pendiente:   ${balance:,.2f}")
    lines.append("=" * 40)
    lines.append("")
    lines.append("Conserve este comprobante.".center(40))
    lines.append("¡Gracias por su abono!".center(40))
    lines.append("")
    lines.append("")
    lines.append("")
    
    content = "\n".join(lines)
    
    try:
        result = subprocess.run(
            ["lp", "-d", printer_name, "-o", "raw", "-"],
            input=content.encode('latin-1', errors='replace'),
            capture_output=True,
            timeout=10
        )
        if result.returncode == 0:
            logging.info("Layaway payment ticket printed successfully")
    except Exception as e:
        logging.error(f"Error printing layaway payment: {e}")

def print_layaway_liquidation(layaway_data):
    """Imprime un ticket de liquidación de apartado."""
    import subprocess
    from app.core import core_instance
    
    logging.info(f"Printing layaway liquidation ticket: {layaway_data.get('id', 'N/A')}")
    
    # Get printer configuration from app config
    cfg = core_instance.get_app_config()
    printer_name = cfg.get("printer_name", "")
    
    if not printer_name:
        logging.warning("No printer configured for layaway liquidation")
        raise HardwareError("No hay impresora configurada. Vaya a Configuración.")
    
    lines = []
    lines.append("=" * 40)
    lines.append("   LIQUIDACIÓN DE APARTADO   ".center(40))
    lines.append("=" * 40)
    lines.append("")
    lines.append(f"Folio: #{layaway_data.get('id', 'N/A')}")
    lines.append(f"Cliente: {layaway_data.get('customer_name', 'Cliente')}")
    lines.append("-" * 40)
    
    total_amount = float(layaway_data.get('total_amount', 0))
    amount_paid = float(layaway_data.get('amount_paid', 0))
    
    lines.append(f"Total Apartado: ${total_amount:,.2f}")
    lines.append(f"Total Pagado:   ${amount_paid:,.2f}")
    lines.append("")
    lines.append("=" * 40)
    lines.append("  *** APARTADO LIQUIDADO ***  ".center(40))
    lines.append("")
    lines.append("Puede recoger sus productos.".center(40))
    lines.append("")
    lines.append("¡Gracias por su preferencia!".center(40))
    lines.append("")
    lines.append("")
    lines.append("")
    
    content = "\n".join(lines)
    
    try:
        result = subprocess.run(
            ["lp", "-d", printer_name, "-o", "raw", "-"],
            input=content.encode('latin-1', errors='replace'),
            capture_output=True,
            timeout=10
        )
        if result.returncode == 0:
            logging.info("Layaway liquidation ticket printed successfully")
    except Exception as e:
        logging.error(f"Error printing layaway liquidation: {e}")

def print_layaway_create(layaway_data, items):
    """Imprime un ticket de creación de apartado."""
    import subprocess
    
    logging.info(f"Printing layaway create ticket: {layaway_data.get('id', 'N/A')}")
    
    lines = []
    lines.append("=" * 40)
    lines.append("     RECIBO DE APARTADO     ".center(40))
    lines.append("=" * 40)
    lines.append("")
    lines.append(f"Folio: #{layaway_data.get('id', 'N/A')}")
    lines.append(f"Fecha: {layaway_data.get('created_at', '')[:19] if layaway_data.get('created_at') else ''}")
    lines.append(f"Cliente: {layaway_data.get('customer_name', 'Cliente')}")
    lines.append("-" * 40)
    lines.append("PRODUCTOS:")
    
    for item in items:
        name = item.get('name', 'Producto')[:25]
        qty = item.get('qty', 1)
        price = float(item.get('price', 0))
        lines.append(f"{qty} x {name}")
        lines.append(f"      ${price:,.2f} c/u")
    
    lines.append("-" * 40)
    
    total_amount = float(layaway_data.get('total_amount', 0))
    down_payment = float(layaway_data.get('down_payment', layaway_data.get('amount_paid', 0)))
    balance = float(layaway_data.get('balance_due', total_amount - down_payment))
    
    lines.append(f"Total:              ${total_amount:,.2f}")
    lines.append(f"Anticipo:           ${down_payment:,.2f}")
    lines.append(f"Saldo Pendiente:    ${balance:,.2f}")
    lines.append("")
    lines.append(f"Vence: {layaway_data.get('due_date', 'N/A')}")
    lines.append("=" * 40)
    lines.append("")
    lines.append("Conserve este recibo.".center(40))
    lines.append("¡Gracias por su preferencia!".center(40))
    lines.append("")
    lines.append("")
    lines.append("")
    
    content = "\n".join(lines)
    
    # Get printer configuration from app config
    from app.core import core_instance
    cfg = core_instance.get_app_config()
    printer_name = cfg.get("printer_name", "")
    
    if not printer_name:
        logging.warning("No printer configured for layaway create")
        raise HardwareError("No hay impresora configurada. Vaya a Configuración.")
    
    try:
        result = subprocess.run(
            ["lp", "-d", printer_name, "-o", "raw", "-"],
            input=content.encode('latin-1', errors='replace'),
            capture_output=True,
            timeout=10
        )
        if result.returncode == 0:
            logging.info("Layaway create ticket printed successfully")
    except Exception as e:
        logging.error(f"Error printing layaway create: {e}")

def print_layaway_ticket(core, layaway_id, payment_data, amount):
    """Imprime un ticket de abono a apartado."""
    try:
        # Get layaway details
        layaway = core.get_layaway(layaway_id)
        if not layaway:
            logging.error(f"Layaway {layaway_id} not found for printing")
            return

        # Get printer configuration
        cfg = core.get_app_config()
        printer_name = cfg.get("printer_name", "")
        
        if not printer_name:
            raise HardwareError("No hay impresora configurada.")
        
        # Build ticket content
        ticket_content = build_layaway_ticket(cfg, layaway, payment_data, amount, core)
        
        # Print using CUPS lp command
        import subprocess
        
        logging.info(f"Printing Layaway Ticket #{layaway_id} to {printer_name}")
        
        result = subprocess.run(
            ["lp", "-d", printer_name, "-o", "raw", "-"],
            input=ticket_content.encode('latin-1', errors='replace'),
            capture_output=True,
            timeout=10
        )
        
        if result.returncode == 0:
            logging.info(f"Layaway Ticket printed successfully.")
        else:
            raise HardwareError(f"Error de Impresora: {result.stderr.decode('utf-8')}")
            
    except Exception as e:
        logging.error(f"Error printing layaway ticket: {e}")
        raise HardwareError(f"Error al imprimir: {e}")

def build_layaway_ticket(cfg, layaway, payment_data, amount_paid, core):
    """Construye el contenido del ticket de abono."""
    try:
        from app.core import STATE
        ticket_cfg = core.get_ticket_config(STATE.branch_id)
        if not ticket_cfg: ticket_cfg = {} # Fallback
        
        paper_width = cfg.get("ticket_paper_width", "80mm")
        line_width = 48 if paper_width == "80mm" else 32
        
        margin = ticket_cfg.get("margin_chars", 0)
        usable_width = line_width - (margin * 2)
        margin_str = " " * margin
        
        lines = []
        lines.extend([""] * ticket_cfg.get("margin_top", 0))
        
        # === HEADER (Same as Sale) ===
        business_name = ticket_cfg.get("business_name", cfg.get('store_name', 'TITAN POS'))
        lines.append(margin_str + business_name.center(usable_width).upper())
        
        address = ticket_cfg.get("business_address") or cfg.get('store_address', '')
        if address: lines.append(margin_str + address.center(usable_width))
        
        phone = ticket_cfg.get("business_phone") or cfg.get('store_phone', '')
        if phone: lines.append(margin_str + f"Tel: {phone}".center(usable_width))
        
        lines.append(margin_str + ("-" * usable_width))
        
        # === TICKET INFO ===
        lines.append(margin_str + "RECIBO DE APARTADO".center(usable_width))
        lines.append(margin_str + f"Folio: #{layaway['id']}")
        lines.append(margin_str + f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        
        lines.append(margin_str + f"Cliente: {layaway.get('customer_name', 'Cliente General')[:usable_width-9]}")
        lines.append(margin_str + ("-" * usable_width))
        
        # === PAYMENT DETAILS ===
        total_amount = float(layaway.get('total_amount', 0))
        # Note: layaway object passed MIGHT check old data before update if not refreshed.
        # But here we likely fetched it AFTER update (or before? Update flow calls this after payment).
        # Wait, core.add_layaway_payment updates DB. Then we fetch layaway in print function.
        # So 'amount_paid' is CURRENT (including this payment).
        
        current_paid = float(layaway.get('amount_paid', 0))
        current_balance = float(layaway.get('balance_due', 0))
        
        previous_balance = current_balance + amount_paid # Reconstruct old state
        
        # Format currency helper
        def fmt(val): return f"${val:,.2f}"
        
        # Show breakdown
        lines.append(margin_str + f"Total Apartado: {fmt(total_amount).rjust(usable_width - 16)}")
        lines.append(margin_str + f"Saldo Anterior: {fmt(previous_balance).rjust(usable_width - 16)}")
        lines.append(margin_str + f"ABONO REALIZADO: {fmt(amount_paid).rjust(usable_width - 17)}")
        lines.append(margin_str + f"Saldo Restante: {fmt(current_balance).rjust(usable_width - 16)}")
        
        lines.append(margin_str + ("-" * usable_width))
        
        # === PAYMENT METHOD ===
        method_map = {'cash': 'Efectivo', 'card': 'Tarjeta', 'transfer': 'Transferencia', 'mixed': 'Mixto'}
        method_str = method_map.get(payment_data.get('method'), payment_data.get('method'))
        lines.append(margin_str + f"Forma de Pago: {method_str}")
        if payment_data.get('reference'):
            lines.append(margin_str + f"Ref: {payment_data['reference']}")
            
        lines.append(margin_str + ("=" * usable_width))
        
        # === FOOTER ===
        if current_balance <= 0:
             lines.append(margin_str + "*** APARTADO LIQUIDADO ***".center(usable_width))
             lines.append(margin_str + "Puede pasar a recoger sus productos.".center(usable_width))
        else:
             lines.append(margin_str + f"Vence: {layaway.get('due_date', '')}".center(usable_width))
             
        lines.append(margin_str + "Gracias por su preferencia.".center(usable_width))
        lines.append("")
        lines.append("")
        
        # Cut
        lines.append("\x1d\x56\x42\x00") # GS V m n (Cut)
        
        return "\n".join(lines)
        
    except Exception as e:
        logging.error(f"Error building layaway ticket: {e}")
        return "Error Ticket"
