"""
Print template system for customizable ticket printing.
Supports 80mm and 58mm thermal printers with ESC/POS commands.
"""
from __future__ import annotations

from typing import Any
from datetime import datetime


class PrintTemplate:
    """Base class for print templates."""
    
    def __init__(self, width_mm: int = 80):
        """Initialize template.
        
        Args:
            width_mm: Paper width in mm (58 or 80)
        """
        self.width_mm = width_mm
        self.chars_per_line = 48 if width_mm == 80 else 32
        
        # ESC/POS commands
        self.ESC = b'\x1b'
        self.GS = b'\x1d'
        
        # Commands
        self.INIT = self.ESC + b'@'
        self.CENTER = self.ESC + b'a\x01'
        self.LEFT = self.ESC + b'a\x00'
        self.RIGHT = self.ESC + b'a\x02'
        self.BOLD_ON = self.ESC + b'E\x01'
        self.BOLD_OFF = self.ESC + b'E\x00'
        self.DOUBLE_WIDTH = self.GS + b'!\x10'
        self.DOUBLE_HEIGHT = self.GS + b'!\x01'
        self.DOUBLE_SIZE = self.GS + b'!\x11'
        self.NORMAL_SIZE = self.GS + b'!\x00'
        self.CUT = self.GS + b'V\x00'
        self.FEED = b'\n'
        
    def _text(self, content: str, encoding: str = 'cp437') -> bytes:
        """Convert text to bytes."""
        return content.encode(encoding, errors='replace')
    
    def _line(self, char: str = '-') -> str:
        """Generate separator line."""
        return char * self.chars_per_line
    
    def _center_text(self, text: str) -> str:
        """Center text in line."""
        padding = (self.chars_per_line - len(text)) // 2
        return ' ' * padding + text
    
    def _two_columns(self, left: str, right: str) -> str:
        """Format text in two columns."""
        available_space = self.chars_per_line - len(right)
        left_truncated = left[:available_space]
        padding = self.chars_per_line - len(left_truncated) - len(right)
        return left_truncated + ' ' * padding + right
    
    def generate_sale_ticket(self, sale_data: dict[str, Any]) -> bytes:
        """Generate sale ticket."""
        output = bytearray()
        
        # Initialize printer
        output.extend(self.INIT)
        
        # Header
        output.extend(self.CENTER)
        output.extend(self.DOUBLE_SIZE)
        output.extend(self._text(sale_data.get('store_name', 'TITAN POS')))
        output.extend(self.FEED)
        output.extend(self.NORMAL_SIZE)
        
        # Store info
        if sale_data.get('store_address'):
            output.extend(self._text(self._center_text(sale_data['store_address'])))
            output.extend(self.FEED)
        if sale_data.get('store_phone'):
            output.extend(self._text(self._center_text(f"Tel: {sale_data['store_phone']}")))
            output.extend(self.FEED)
        if sale_data.get('store_rfc'):
            output.extend(self._text(self._center_text(f"RFC: {sale_data['store_rfc']}")))
            output.extend(self.FEED)
        
        output.extend(self.FEED)
        output.extend(self.LEFT)
        
        # Sale info
        output.extend(self._text(self._line('=')))
        output.extend(self.FEED)
        output.extend(self._text(f"Folio: {sale_data.get('folio', 'N/A')}"))
        output.extend(self.FEED)
        output.extend(self._text(f"Fecha: {sale_data.get('date', datetime.now().strftime('%d/%m/%Y %H:%M'))}"))
        output.extend(self.FEED)
        
        if sale_data.get('customer_name'):
            output.extend(self._text(f"Cliente: {sale_data['customer_name']}"))
            output.extend(self.FEED)
        
        if sale_data.get('cashier_name'):
            output.extend(self._text(f"Cajero: {sale_data['cashier_name']}"))
            output.extend(self.FEED)
        
        output.extend(self._text(self._line('=')))
        output.extend(self.FEED)
        output.extend(self.FEED)
        
        # Items
        output.extend(self.BOLD_ON)
        output.extend(self._text("PRODUCTO"))
        output.extend(self.FEED)
        output.extend(self.BOLD_OFF)
        
        for item in sale_data.get('items', []):
            # Product name
            name = item.get('name', '')
            output.extend(self._text(name[:self.chars_per_line]))
            output.extend(self.FEED)
            
            # Qty x Price = Subtotal
            qty = item.get('qty', 1)
            price = item.get('price', 0.0)
            subtotal = item.get('subtotal', qty * price)
            
            detail_line = f"  {qty:.2f} x ${price:.2f} = ${subtotal:.2f}"
            output.extend(self._text(detail_line))
            output.extend(self.FEED)
            
            # Discount if any
            discount = item.get('discount', 0.0)
            if discount > 0:
                output.extend(self._text(f"  Desc: -${discount:.2f}"))
                output.extend(self.FEED)
        
        output.extend(self.FEED)
        output.extend(self._text(self._line('-')))
        output.extend(self.FEED)
        
        # Totals
        subtotal = sale_data.get('subtotal', 0.0)
        tax = sale_data.get('tax', 0.0)
        discount = sale_data.get('discount', 0.0)
        total = sale_data.get('total', 0.0)
        
        output.extend(self._text(self._two_columns('Subtotal:', f'${subtotal:.2f}')))
        output.extend(self.FEED)
        
        if discount > 0:
            output.extend(self._text(self._two_columns('Descuento:', f'-${discount:.2f}')))
            output.extend(self.FEED)
        
        output.extend(self._text(self._two_columns('IVA:', f'${tax:.2f}')))
        output.extend(self.FEED)
        
        output.extend(self.BOLD_ON)
        output.extend(self.DOUBLE_WIDTH)
        output.extend(self._text(self._two_columns('TOTAL:', f'${total:.2f}')))
        output.extend(self.NORMAL_SIZE)
        output.extend(self.BOLD_OFF)
        output.extend(self.FEED)
        
        output.extend(self._text(self._line('-')))
        output.extend(self.FEED)
        
        # Payment info
        payment_method = sale_data.get('payment_method', 'Efectivo')
        output.extend(self._text(f"Pago: {payment_method}"))
        output.extend(self.FEED)
        
        if sale_data.get('amount_paid'):
            output.extend(self._text(f"Recibido: ${sale_data['amount_paid']:.2f}"))
            output.extend(self.FEED)
        
        change = sale_data.get('change', 0.0)
        if change > 0:
            output.extend(self._text(f"Cambio: ${change:.2f}"))
            output.extend(self.FEED)
        
        output.extend(self.FEED)
        output.extend(self._text(self._line('=')))
        output.extend(self.FEED)
        
        # Footer
        output.extend(self.CENTER)
        output.extend(self._text(sale_data.get('footer_message', '¡Gracias por su compra!')))
        output.extend(self.FEED)
        
        if sale_data.get('website'):
            output.extend(self._text(sale_data['website']))
            output.extend(self.FEED)
        
        # Feed and cut
        output.extend(self.FEED * 4)
        output.extend(self.CUT)
        
        return bytes(output)
    
    def generate_turn_report(self, turn_data: dict[str, Any]) -> bytes:
        """Generate turn closing report."""
        output = bytearray()
        
        # Initialize
        output.extend(self.INIT)
        
        # Header
        output.extend(self.CENTER)
        output.extend(self.BOLD_ON)
        output.extend(self.DOUBLE_SIZE)
        output.extend(self._text('CORTE DE CAJA'))
        output.extend(self.NORMAL_SIZE)
        output.extend(self.BOLD_OFF)
        output.extend(self.FEED * 2)
        
        output.extend(self.LEFT)
        
        # Turn info
        output.extend(self._text(f"Turno: {turn_data.get('turn_id', 'N/A')}"))
        output.extend(self.FEED)
        output.extend(self._text(f"Inicio: {turn_data.get('start_time', '')}"))
        output.extend(self.FEED)
        output.extend(self._text(f"Cierre: {turn_data.get('end_time', '')}"))
        output.extend(self.FEED)
        output.extend(self._text(f"Cajero: {turn_data.get('cashier', '')}"))
        output.extend(self.FEED)
        
        output.extend(self.FEED)
        output.extend(self._text(self._line('=')))
        output.extend(self.FEED)
        
        # Sales summary
        output.extend(self.BOLD_ON)
        output.extend(self._text('RESUMEN DE VENTAS'))
        output.extend(self.BOLD_OFF)
        output.extend(self.FEED)
        
        output.extend(self._text(self._two_columns('Ventas:', str(turn_data.get('sales_count', 0)))))
        output.extend(self.FEED)
        output.extend(self._text(self._two_columns('Total Ventas:', f"${turn_data.get('sales_total', 0):.2f}")))
        output.extend(self.FEED)
        
        output.extend(self.FEED)
        
        # Payment methods breakdown
        output.extend(self.BOLD_ON)
        output.extend(self._text('DESGLOSE POR FORMA DE PAGO'))
        output.extend(self.BOLD_OFF)
        output.extend(self.FEED)
        
        for method, amount in turn_data.get('payment_breakdown', {}).items():
            output.extend(self._text(self._two_columns(f"{method}:", f"${amount:.2f}")))
            output.extend(self.FEED)
        
        output.extend(self.FEED)
        output.extend(self._text(self._line('-')))
        output.extend(self.FEED)
        
        # Cash movements
        output.extend(self.BOLD_ON)
        output.extend(self._text('MOVIMIENTOS DE EFECTIVO'))
        output.extend(self.BOLD_OFF)
        output.extend(self.FEED)
        
        output.extend(self._text(self._two_columns('Efectivo Inicial:', f"${turn_data.get('initial_cash', 0):.2f}")))
        output.extend(self.FEED)
        output.extend(self._text(self._two_columns('Entradas:', f"${turn_data.get('cash_in', 0):.2f}")))
        output.extend(self.FEED)
        output.extend(self._text(self._two_columns('Salidas:', f"-${turn_data.get('cash_out', 0):.2f}")))
        output.extend(self.FEED)
        output.extend(self._text(self._two_columns('Ventas Efectivo:', f"${turn_data.get('cash_sales', 0):.2f}")))
        output.extend(self.FEED)
        
        output.extend(self.FEED)
        output.extend(self._text(self._line('-')))
        output.extend(self.FEED)
        
        # Expected vs counted
        expected = turn_data.get('expected_cash', 0.0)
        counted = turn_data.get('counted_cash', 0.0)
        difference = counted - expected
        
        output.extend(self.BOLD_ON)
        output.extend(self._text(self._two_columns('Efectivo Esperado:', f"${expected:.2f}")))
        output.extend(self.FEED)
        output.extend(self._text(self._two_columns('Efectivo Contado:', f"${counted:.2f}")))
        output.extend(self.FEED)
        
        diff_label = 'Diferencia:'
        diff_sign = '+' if difference >= 0 else ''
        output.extend(self._text(self._two_columns(diff_label, f"{diff_sign}${difference:.2f}")))
        output.extend(self.BOLD_OFF)
        output.extend(self.FEED)
        
        # Footer
        output.extend(self.FEED * 2)
        output.extend(self._text(self._line('=')))
        output.extend(self.FEED)
        output.extend(self.CENTER)
        output.extend(self._text('Firma de conformidad'))
        output.extend(self.FEED * 2)
        output.extend(self._text('_' * 30))
        output.extend(self.FEED)
        
        # Feed and cut
        output.extend(self.FEED * 4)
        output.extend(self.CUT)
        
        return bytes(output)

def print_to_file(data: bytes, filename: str) -> bool:
    """Save print data to file (for testing or PDF conversion)."""
    try:
        with open(filename, 'wb') as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"Error saving print data: {e}")
        return False

def print_to_printer(data: bytes, printer_name: str = None) -> bool:
    """Send print data to thermal printer.
    
    Args:
        data: Raw print data
        printer_name: Printer name/path (e.g., '/dev/usb/lp0' or 'POS-80')
        
    Returns:
        True if successful
    """
    try:
        if not printer_name:
            # Default printer on Linux
            printer_name = '/dev/usb/lp0'
        
        # Try to write directly to printer
        try:
            with open(printer_name, 'wb') as printer:
                printer.write(data)
            return True
        except Exception:
            # Fallback: use lp command
            import subprocess
            process = subprocess.Popen(
                ['lp', '-d', printer_name, '-o', 'raw'],
                stdin=subprocess.PIPE
            )
            process.communicate(input=data)
            return process.returncode == 0
            
    except Exception as e:
        print(f"Error printing: {e}")
        return False

# Global template instance
default_template = PrintTemplate(width_mm=80)
