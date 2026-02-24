"""
MIDAS TICKET PRINTER - Enhanced ESC/POS Printing with Loyalty Info
Módulo de impresión de tickets con información del Monedero Electrónico

Agrega al pie del ticket:
- Saldo anterior
- Puntos ganados en esta compra
- Nuevo saldo
"""

from typing import Any, Dict, Optional
from decimal import Decimal
import logging

logger = logging.getLogger("MIDAS_PRINTER")

class MidasTicketPrinter:
    """
    Extensión del motor de tickets para incluir información de lealtad.
    
    Compatible con impresoras ESC/POS (80mm y 58mm).
    """
    
    def __init__(self, printer_interface=None):
        """
        Args:
            printer_interface: Instancia de escpos.printer (Usb, Network, Serial, etc.)
        """
        self.printer = printer_interface
    
    def print_loyalty_section(
        self,
        saldo_anterior: Decimal,
        puntos_ganados: Decimal,
        saldo_nuevo: Decimal,
        puntos_usados: Decimal = Decimal('0.00'),
        customer_name: str = "",
        nivel_lealtad: str = "BRONCE"
    ):
        """
        Imprime la sección de monedero electrónico en el ticket.
        
        Args:
            saldo_anterior: Saldo antes de esta transacción
            puntos_ganados: Puntos ganados en esta compra
            saldo_nuevo: Saldo después de esta transacción
            puntos_usados: Puntos usados para pagar (si aplica)
            customer_name: Nombre del cliente
            nivel_lealtad: Nivel de lealtad del cliente
        """
        if not self.printer:
            logger.warning("No hay impresora configurada")
            return
        
        try:
            # Línea separadora
            self.printer.text("\n")
            self.printer.set(align='center', text_type='B')
            self.printer.text("================================\n")
            
            # Título del monedero
            self.printer.set(align='center', text_type='BU', width=2, height=2)
            self.printer.text("MONEDERO ELECTRONICO\n")
            
            self.printer.set(align='center', text_type='NORMAL', width=1, height=1)
            if customer_name:
                self.printer.text(f"{customer_name}\n")
            
            # Emoji del nivel (usando caracteres compatibles)
            nivel_icons = {
                "BRONCE": "[*]",
                "PLATA": "[**]",
                "ORO": "[***]",
                "PLATINO": "[****]"
            }
            icon = nivel_icons.get(nivel_lealtad, "[*]")
            self.printer.text(f"{icon} {nivel_lealtad} {icon}\n")
            
            # Línea separadora
            self.printer.set(align='center', text_type='B')
            self.printer.text("--------------------------------\n")
            
            # Información de puntos
            self.printer.set(align='left', text_type='NORMAL')
            
            # Saldo anterior
            self.printer.text(f"Saldo Anterior:       ${saldo_anterior:>10.2f}\n")
            
            # Puntos usados (si aplica)
            if puntos_usados > 0:
                self.printer.set(align='left', text_type='B')
                self.printer.text(f"Puntos Usados:       -${puntos_usados:>10.2f}\n")
                self.printer.set(align='left', text_type='NORMAL')
            
            # Puntos ganados
            if puntos_ganados > 0:
                self.printer.set(align='left', text_type='B')
                self.printer.text(f"Puntos Ganados:      +${puntos_ganados:>10.2f}\n")
                self.printer.set(align='left', text_type='NORMAL')
            
            # Línea separadora
            self.printer.set(align='center', text_type='B')
            self.printer.text("--------------------------------\n")
            
            # Nuevo saldo (DESTACADO)
            self.printer.set(align='center', text_type='BU', width=2, height=2)
            self.printer.text(f"SALDO: ${saldo_nuevo:.2f}\n")
            
            # Línea separadora final
            self.printer.set(align='center', text_type='NORMAL', width=1, height=1)
            self.printer.text("================================\n")
            
            # Mensaje promocional
            self.printer.set(align='center', text_type='NORMAL')
            self.printer.text("\nUsa tus puntos en tu proxima\n")
            self.printer.text("compra. $1 Punto = $1 Peso\n")
            
            logger.info(f"✅ Sección de lealtad impresa: Saldo ${saldo_nuevo:.2f}")
            
        except Exception as e:
            logger.error(f"Error al imprimir sección de lealtad: {e}")
    
    def print_full_ticket_with_loyalty(
        self,
        ticket_data: Dict[str, Any],
        loyalty_data: Optional[Dict[str, Any]] = None
    ):
        """
        Imprime un ticket completo con información de lealtad.
        
        Args:
            ticket_data: Datos del ticket (header, items, total, payment, etc.)
            loyalty_data: Datos de lealtad (saldo_anterior, puntos_ganados, etc.)
        """
        if not self.printer:
            logger.warning("No hay impresora configurada")
            return
        
        try:
            # Inicializar impresora
            self.printer.hw('init')
            
            # ================================================================
            # HEADER
            # ================================================================
            self.printer.set(align='center', text_type='B')
            
            store_name = ticket_data.get('store_name', 'MI TIENDA')
            self.printer.set(width=2, height=2)
            self.printer.text(f"{store_name}\n")
            
            self.printer.set(width=1, height=1)
            store_address = ticket_data.get('store_address', '')
            if store_address:
                self.printer.text(f"{store_address}\n")
            
            store_phone = ticket_data.get('store_phone', '')
            if store_phone:
                self.printer.text(f"Tel: {store_phone}\n")
            
            store_rfc = ticket_data.get('store_rfc', '')
            if store_rfc:
                self.printer.text(f"RFC: {store_rfc}\n")
            
            # Fecha y hora
            fecha = ticket_data.get('fecha', '')
            hora = ticket_data.get('hora', '')
            self.printer.text(f"\n{fecha} {hora}\n")
            
            # Ticket ID
            ticket_id = ticket_data.get('ticket_id', '')
            self.printer.text(f"Ticket: {ticket_id}\n")
            
            # Cajero
            cajero = ticket_data.get('cajero', '')
            if cajero:
                self.printer.text(f"Cajero: {cajero}\n")
            
            # Cliente
            customer_name = ticket_data.get('customer_name', '')
            if customer_name:
                self.printer.text(f"Cliente: {customer_name}\n")
            
            # Línea separadora
            self.printer.text("================================\n")
            
            # ================================================================
            # PRODUCTOS
            # ================================================================
            self.printer.set(align='left', text_type='NORMAL')
            
            items = ticket_data.get('items', [])
            for item in items:
                # Nombre del producto
                nombre = item.get('nombre', '')[:32]  # Max 32 chars
                self.printer.text(f"{nombre}\n")
                
                # Cantidad, precio, subtotal
                qty = item.get('qty', 0)
                precio = item.get('precio', 0)
                subtotal = item.get('subtotal', 0)
                
                linea_detalle = f"  {qty} x ${precio:.2f}"
                espacios = 32 - len(linea_detalle) - len(f"${subtotal:.2f}")
                linea_detalle += " " * espacios + f"${subtotal:.2f}\n"
                
                self.printer.text(linea_detalle)
            
            # Línea separadora
            self.printer.set(align='center', text_type='B')
            self.printer.text("================================\n")
            
            # ================================================================
            # TOTALES
            # ================================================================
            self.printer.set(align='left', text_type='NORMAL')
            
            subtotal = ticket_data.get('subtotal', 0)
            self.printer.text(f"Subtotal:             ${subtotal:>10.2f}\n")
            
            tax = ticket_data.get('tax', 0)
            if tax > 0:
                self.printer.text(f"IVA:                  ${tax:>10.2f}\n")
            
            descuento = ticket_data.get('descuento', 0)
            if descuento > 0:
                self.printer.text(f"Descuento:           -${descuento:>10.2f}\n")
            
            # Total (DESTACADO)
            total = ticket_data.get('total', 0)
            self.printer.set(align='left', text_type='BU', width=2, height=2)
            self.printer.text(f"TOTAL: ${total:.2f}\n")
            
            # ================================================================
            # PAGO
            # ================================================================
            self.printer.set(align='left', text_type='NORMAL', width=1, height=1)
            self.printer.text("\n")
            
            payment_method = ticket_data.get('payment_method', 'cash')
            payment_breakdown = ticket_data.get('payment_breakdown', {})
            
            if payment_method == 'mixed':
                # Pago mixto: desglosar cada método
                if payment_breakdown.get('efectivo', 0) > 0:
                    self.printer.text(f"Efectivo:             ${payment_breakdown['efectivo']:>10.2f}\n")
                if payment_breakdown.get('tarjeta', 0) > 0:
                    self.printer.text(f"Tarjeta:              ${payment_breakdown['tarjeta']:>10.2f}\n")
                if payment_breakdown.get('puntos', 0) > 0:
                    self.printer.text(f"Puntos:               ${payment_breakdown['puntos']:>10.2f}\n")
                
                cambio = payment_breakdown.get('cambio', 0)
                if cambio > 0:
                    self.printer.set(text_type='B')
                    self.printer.text(f"Cambio:               ${cambio:>10.2f}\n")
            else:
                # Pago simple
                metodo_str = {
                    'cash': 'Efectivo',
                    'card': 'Tarjeta',
                    'points': 'Puntos'
                }.get(payment_method, 'Efectivo')
                
                self.printer.text(f"Pago: {metodo_str}\n")
                
                cambio = ticket_data.get('cambio', 0)
                if cambio > 0:
                    self.printer.set(text_type='B')
                    self.printer.text(f"Cambio:               ${cambio:>10.2f}\n")
            
            # ================================================================
            # MONEDERO ELECTRÓNICO (si aplica)
            # ================================================================
            if loyalty_data:
                self.print_loyalty_section(
                    saldo_anterior=Decimal(str(loyalty_data.get('saldo_anterior', 0))),
                    puntos_ganados=Decimal(str(loyalty_data.get('puntos_ganados', 0))),
                    saldo_nuevo=Decimal(str(loyalty_data.get('saldo_nuevo', 0))),
                    puntos_usados=Decimal(str(loyalty_data.get('puntos_usados', 0))),
                    customer_name=ticket_data.get('customer_name', ''),
                    nivel_lealtad=loyalty_data.get('nivel_lealtad', 'BRONCE')
                )
            
            # ================================================================
            # FOOTER
            # ================================================================
            self.printer.set(align='center', text_type='NORMAL', width=1, height=1)
            self.printer.text("\n")
            
            footer_message = ticket_data.get('footer_message', 'Gracias por su compra')
            self.printer.text(f"{footer_message}\n")
            
            website = ticket_data.get('website', '')
            if website:
                self.printer.text(f"{website}\n")
            
            # QR Code (opcional)
            qr_data = ticket_data.get('qr_data')
            if qr_data:
                try:
                    self.printer.qr(qr_data, size=6)
                except Exception:
                    pass
            
            # Cortar papel
            self.printer.text("\n\n\n")
            self.printer.cut()
            
            logger.info(f"✅ Ticket completo impreso con información de lealtad")
            
        except Exception as e:
            logger.error(f"Error al imprimir ticket: {e}")

def generate_loyalty_data(
    loyalty_engine,
    customer_id: int,
    puntos_ganados: Decimal,
    puntos_usados: Decimal = Decimal('0.00')
) -> Dict[str, Any]:
    """
    Genera los datos de lealtad para incluir en el ticket.
    
    Args:
        loyalty_engine: Instancia de LoyaltyEngine
        customer_id: ID del cliente
        puntos_ganados: Puntos ganados en esta compra
        puntos_usados: Puntos usados para pagar
        
    Returns:
        Diccionario con los datos de lealtad
    """
    try:
        # Obtener cuenta
        account = loyalty_engine.get_or_create_account(customer_id)
        if not account:
            return {}
        
        # El saldo nuevo ya incluye los cambios
        saldo_nuevo = account.saldo_actual
        
        # Calcular saldo anterior
        saldo_anterior = saldo_nuevo - puntos_ganados + puntos_usados
        
        return {
            'saldo_anterior': float(saldo_anterior),
            'puntos_ganados': float(puntos_ganados),
            'puntos_usados': float(puntos_usados),
            'saldo_nuevo': float(saldo_nuevo),
            'nivel_lealtad': account.nivel_lealtad
        }
    except Exception as e:
        logger.error(f"Error al generar datos de lealtad: {e}")
        return {}

# ============================================================================
# TEXTO PLANO PARA PREVIEW (Sin impresora)
# ============================================================================

def generate_text_ticket_with_loyalty(
    ticket_data: Dict[str, Any],
    loyalty_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Genera una representación en texto plano del ticket con lealtad.
    Útil para preview o log.
    
    Args:
        ticket_data: Datos del ticket
        loyalty_data: Datos de lealtad
        
    Returns:
        String con el ticket en formato texto
    """
    lines = []
    
    # Header
    store_name = ticket_data.get('store_name', 'MI TIENDA')
    lines.append(f"{'=' * 40}")
    lines.append(f"{store_name.center(40)}")
    lines.append(f"{'=' * 40}")
    
    store_address = ticket_data.get('store_address', '')
    if store_address:
        lines.append(store_address.center(40))
    
    fecha = ticket_data.get('fecha', '')
    hora = ticket_data.get('hora', '')
    lines.append(f"{fecha} {hora}".center(40))
    
    ticket_id = ticket_data.get('ticket_id', '')
    lines.append(f"Ticket: {ticket_id}".center(40))
    
    lines.append(f"{'=' * 40}")
    
    # Items
    for item in ticket_data.get('items', []):
        nombre = item.get('nombre', '')[:32]
        qty = item.get('qty', 0)
        precio = item.get('precio', 0)
        subtotal = item.get('subtotal', 0)
        
        lines.append(nombre)
        lines.append(f"  {qty} x ${precio:.2f} = ${subtotal:.2f}")
    
    lines.append(f"{'=' * 40}")
    
    # Totales
    subtotal = ticket_data.get('subtotal', 0)
    lines.append(f"Subtotal: ${subtotal:>30.2f}")
    
    total = ticket_data.get('total', 0)
    lines.append(f"{'TOTAL: $' + f'{total:.2f}':^40}")
    
    lines.append(f"{'=' * 40}")
    
    # Monedero (si aplica)
    if loyalty_data:
        lines.append("")
        lines.append(f"{'MONEDERO ELECTRONICO'.center(40)}")
        lines.append(f"{'-' * 40}")
        
        saldo_anterior = loyalty_data.get('saldo_anterior', 0)
        puntos_ganados = loyalty_data.get('puntos_ganados', 0)
        puntos_usados = loyalty_data.get('puntos_usados', 0)
        saldo_nuevo = loyalty_data.get('saldo_nuevo', 0)
        
        lines.append(f"Saldo Anterior: ${saldo_anterior:>23.2f}")
        if puntos_usados > 0:
            lines.append(f"Puntos Usados: -${puntos_usados:>22.2f}")
        if puntos_ganados > 0:
            lines.append(f"Puntos Ganados: +${puntos_ganados:>21.2f}")
        
        lines.append(f"{'-' * 40}")
        lines.append(f"{'SALDO: $' + f'{saldo_nuevo:.2f}':^40}")
        lines.append(f"{'=' * 40}")
    
    lines.append("")
    lines.append("Gracias por su compra".center(40))
    lines.append("")
    
    return "\n".join(lines)
