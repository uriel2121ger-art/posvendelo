"""
Rich Tooltips - TITAN POS
Sistema de tooltips enriquecidos con formato, atajos y tips.
Compatible con tema oscuro.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt6 import QtWidgets

# Catálogo completo de tooltips para todos los botones principales
TOOLTIPS_CATALOG: Dict[str, Dict[str, Any]] = {
    # === VENTAS ===
    "charge_btn": {
        "title": "💳 COBRAR",
        "description": "Finaliza la venta actual y procesa el pago.",
        "shortcut": "F12",
        "tips": [
            "Acepta efectivo, tarjeta, transferencia y métodos mixtos",
            "El cambio se calcula automáticamente",
            "Puedes dividir el pago entre varios métodos",
        ],
    },
    "search_btn": {
        "title": "🔍 BÚSQUEDA AVANZADA",
        "description": "Busca productos por nombre, SKU, código de barras o categoría.",
        "shortcut": "F10",
        "tips": [
            "Usa * para búsqueda parcial (ej: *coca*)",
            "Filtra por categoría para resultados más rápidos",
            "Doble-click en resultado para agregar al carrito",
        ],
    },
    "add_btn": {
        "title": "➕ AGREGAR PRODUCTO",
        "description": "Agrega el producto escaneado o buscado al carrito.",
        "shortcut": "Enter",
        "tips": [
            "Escanea códigos de barras directamente",
            "Usa formato 5*codigo para agregar 5 unidades",
            "También puedes escribir el nombre del producto",
        ],
    },
    "price_checker_btn": {
        "title": "💵 VERIFICADOR DE PRECIOS",
        "description": "Consulta el precio de un producto sin agregarlo al carrito.",
        "shortcut": "F9",
        "tips": [
            "Escanea o escribe el código del producto",
            "Muestra precio, stock y descripciones",
            "Útil para clientes que preguntan precios",
        ],
    },
    "mayoreo_btn": {
        "title": "📦 PRECIO MAYOREO",
        "description": "Cambia al precio de mayoreo del producto seleccionado.",
        "shortcut": "F11",
        "tips": [
            "Solo aplica si el producto tiene precio de mayoreo configurado",
            "La cantidad mínima se verifica automáticamente",
            "El precio cambia solo para esa línea",
        ],
    },
    "common_product_btn": {
        "title": "📋 PRODUCTO COMÚN",
        "description": "Vende un producto genérico sin registro en el catálogo.",
        "shortcut": "Ctrl+P",
        "tips": [
            "Útil para ventas rápidas de productos ocasionales",
            "Puedes definir nombre, precio e IVA manualmente",
            "No afecta el inventario",
        ],
    },
    
    # === DESCUENTOS ===
    "discount_btn": {
        "title": "🏷️ DESCUENTO DE LÍNEA",
        "description": "Aplica un descuento (% o $) al producto seleccionado.",
        "shortcut": "Ctrl+D",
        "tips": [
            "Requiere seleccionar un producto primero",
            "Puede requerir autorización según el monto",
            "El descuento se muestra en el ticket",
        ],
    },
    "global_discount_lbl": {
        "title": "💰 DESCUENTO GLOBAL",
        "description": "Aplica un descuento a TODA la venta actual.",
        "shortcut": "Ctrl+Shift+D",
        "tips": [
            "Haz clic en el total para activar",
            "Perfecto para descuentos por volumen",
            "Se aplica después de descuentos de línea",
        ],
    },
    
    # === CAJA ===
    "cash_in_btn": {
        "title": "💵 ENTRADA DE EFECTIVO",
        "description": "Registra dinero que entra a la caja por motivos distintos a ventas.",
        "shortcut": "F7",
        "tips": [
            "Ej: Fondo inicial, devolución de proveedor",
            "Se registra en el corte de turno",
            "Requiere especificar un motivo",
        ],
    },
    "cash_out_btn": {
        "title": "💸 SALIDA DE EFECTIVO",
        "description": "Registra dinero que sale de la caja por motivos distintos a cambio.",
        "shortcut": "F8",
        "tips": [
            "Ej: Pago a proveedor, retiro parcial",
            "Requiere justificación obligatoria",
            "Puede requerir autorización",
        ],
    },
    "open_drawer_btn": {
        "title": "🗄️ ABRIR CAJÓN",
        "description": "Abre el cajón de dinero manualmente.",
        "shortcut": "Ctrl+O",
        "tips": [
            "Requiere autorización de supervisor",
            "Se registra en el log de actividad",
            "Usa solo cuando sea necesario",
        ],
    },
    
    # === TICKETS Y CLIENTES ===
    "layaway_btn": {
        "title": "💳 CREAR APARTADO",
        "description": "Convierte el carrito actual en un apartado para pago diferido.",
        "shortcut": None,
        "tips": [
            "Requiere asignar un cliente primero",
            "El cliente puede realizar abonos parciales",
            "Los productos se reservan del inventario",
        ],
    },
    "pending_btn": {
        "title": "💾 TICKETS PENDIENTES",
        "description": "Guarda el ticket actual o recupera tickets guardados anteriormente.",
        "shortcut": "F6",
        "tips": [
            "Útil cuando el cliente olvida algo",
            "Los tickets se mantienen entre sesiones",
            "Puedes tener múltiples tickets pendientes",
        ],
    },
    "new_ticket_btn": {
        "title": "➕ NUEVA VENTA",
        "description": "Abre un nuevo ticket sin cerrar el actual.",
        "shortcut": "Ctrl+T",
        "tips": [
            "Ideal para atender a varios clientes simultáneamente",
            "Usa Tab para cambiar entre tickets",
            "Cada ticket mantiene su propio carrito",
        ],
    },
    "note_btn": {
        "title": "📝 NOTA DE TICKET",
        "description": "Agrega instrucciones especiales que se imprimen en el ticket.",
        "shortcut": "F4",
        "tips": [
            "Ej: 'Para llevar', 'Sin bolsa', 'Facturar'",
            "La nota aparece al final del ticket",
            "Visible solo en esta venta",
        ],
    },
    "reprint_btn": {
        "title": "🖨️ REIMPRIMIR TICKET",
        "description": "Imprime una copia del último ticket emitido.",
        "shortcut": "PgDn",
        "tips": [
            "Solo reimprime el ticket más reciente",
            "Para tickets anteriores, usa Historial (Ctrl+H)",
            "La copia indica que es reimpresión",
        ],
    },
    "change_client_btn": {
        "title": "👤 ASIGNAR CLIENTE",
        "description": "Asigna un cliente registrado a la venta actual.",
        "shortcut": "=",
        "tips": [
            "Permite acumular puntos de lealtad",
            "Accede al historial de compras",
            "Aplica precios especiales del cliente",
        ],
    },
    
    # === GESTIÓN ===
    "cancel_sale_btn": {
        "title": "❌ CANCELAR VENTA",
        "description": "Cancela la última venta realizada.",
        "shortcut": "Ctrl+X",
        "tips": [
            "Requiere autorización de supervisor",
            "El inventario se restaura automáticamente",
            "Genera un registro de cancelación",
        ],
    },
    "turn_history_btn": {
        "title": "📊 HISTORIAL DEL TURNO",
        "description": "Muestra todas las ventas realizadas en el turno actual.",
        "shortcut": "Ctrl+H",
        "tips": [
            "Desde aquí puedes cancelar ventas específicas",
            "Incluye detalles de cada transacción",
            "Muestra resumen de métodos de pago",
        ],
    },
    
    # === CARRITO ===
    "qty_increase": {
        "title": "➕ AUMENTAR CANTIDAD",
        "description": "Incrementa en 1 la cantidad del producto seleccionado.",
        "shortcut": "+ / =",
        "tips": [
            "Selecciona el producto en la tabla primero",
            "Verifica el stock disponible",
        ],
    },
    "qty_decrease": {
        "title": "➖ DISMINUIR CANTIDAD",
        "description": "Reduce en 1 la cantidad del producto seleccionado.",
        "shortcut": "-",
        "tips": [
            "Si llega a 0, el producto se elimina",
            "Selecciona el producto en la tabla primero",
        ],
    },
    "delete_item": {
        "title": "🗑️ ELIMINAR PRODUCTO",
        "description": "Elimina el producto seleccionado del carrito.",
        "shortcut": "Del / Backspace",
        "tips": [
            "Selecciona el producto en la tabla primero",
            "No se puede deshacer",
        ],
    },
}

class RichTooltips:
    """
    Generador de tooltips enriquecidos con formato HTML.
    
    Uso:
        RichTooltips.apply(my_button, "charge_btn")
        
        # O generar manualmente:
        tooltip_html = RichTooltips.generate({
            "title": "Mi Botón",
            "description": "Hace algo",
            "shortcut": "F5",
            "tips": ["Tip 1", "Tip 2"]
        })
        widget.setToolTip(tooltip_html)
    """
    
    @staticmethod
    def generate(config: Dict[str, Any]) -> str:
        """
        Genera HTML para un tooltip rico.
        
        El tooltip incluye:
        - Título con emoji
        - Descripción
        - Atajo de teclado (si existe)
        - Lista de tips útiles
        """
        lines = []
        
        # Título
        title = config.get('title', 'Sin título')
        lines.append(f"<div style='font-size: 14px; font-weight: bold; color: #00C896; margin-bottom: 8px;'>{title}</div>")
        
        # Descripción
        description = config.get('description', '')
        if description:
            lines.append(f"<div style='color: #e8eaed; margin-bottom: 8px;'>{description}</div>")
        
        # Atajo
        shortcut = config.get('shortcut')
        if shortcut:
            lines.append(
                f"<div style='margin: 8px 0;'>"
                f"<span style='color: #888;'>⌨️ Atajo:</span> "
                f"<code style='background: rgba(0, 200, 150, 0.2); "
                f"padding: 2px 8px; border-radius: 4px; "
                f"font-family: Consolas, Monaco, monospace; "
                f"color: #00C896; font-weight: bold;'>{shortcut}</code>"
                f"</div>"
            )
        
        # Tips
        tips = config.get('tips', [])
        if tips:
            lines.append("<div style='margin-top: 8px; color: #888;'>💡 <b>Tips:</b></div>")
            lines.append("<ul style='margin: 4px 0 0 16px; padding: 0; color: #a0a4ab;'>")
            for tip in tips:
                lines.append(f"<li style='margin: 2px 0;'>{tip}</li>")
            lines.append("</ul>")
        
        return "".join(lines)
    
    @staticmethod
    def apply(widget: QtWidgets.QWidget, key: str) -> bool:
        """
        Aplica un tooltip del catálogo a un widget.
        
        Args:
            widget: El widget al que aplicar el tooltip
            key: La clave del tooltip en TOOLTIPS_CATALOG
            
        Returns:
            True si se aplicó exitosamente, False si la clave no existe
        """
        if key not in TOOLTIPS_CATALOG:
            return False
        
        config = TOOLTIPS_CATALOG[key]
        tooltip_html = RichTooltips.generate(config)
        widget.setToolTip(tooltip_html)
        return True
    
    @staticmethod
    def apply_custom(
        widget: QtWidgets.QWidget,
        title: str,
        description: str,
        shortcut: Optional[str] = None,
        tips: Optional[List[str]] = None,
    ):
        """
        Aplica un tooltip personalizado a un widget.
        
        Útil para widgets que no están en el catálogo.
        """
        config = {
            "title": title,
            "description": description,
            "shortcut": shortcut,
            "tips": tips or [],
        }
        tooltip_html = RichTooltips.generate(config)
        widget.setToolTip(tooltip_html)
    
    @staticmethod
    def get_simple(key: str) -> str:
        """
        Obtiene un tooltip simple (texto plano) para un widget.
        
        Útil cuando no se soporta HTML.
        """
        if key not in TOOLTIPS_CATALOG:
            return ""
        
        config = TOOLTIPS_CATALOG[key]
        parts = [config.get('title', ''), config.get('description', '')]
        
        if config.get('shortcut'):
            parts.append(f"Atajo: {config['shortcut']}")
        
        return "\n".join(filter(None, parts))

def apply_rich_tooltips(widgets_map: Dict[str, QtWidgets.QWidget]):
    """
    Aplica tooltips ricos a múltiples widgets de una vez.
    
    Args:
        widgets_map: Diccionario de {tooltip_key: widget}
        
    Ejemplo:
        apply_rich_tooltips({
            "charge_btn": self.charge_btn,
            "search_btn": self.search_btn,
            "discount_btn": self.discount_btn,
        })
    """
    for key, widget in widgets_map.items():
        RichTooltips.apply(widget, key)

# Configuración global de estilo para tooltips de Qt
TOOLTIP_STYLESHEET = """
QToolTip {
    background-color: #1e2128;
    color: #e8eaed;
    border: 1px solid #3d4148;
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 12px;
}
"""

def apply_tooltip_stylesheet(app: QtWidgets.QApplication):
    """
    Aplica el estilo oscuro global para todos los tooltips.
    
    Llamar una vez al iniciar la aplicación:
        apply_tooltip_stylesheet(QApplication.instance())
    """
    current_style = app.styleSheet()
    if "QToolTip" not in current_style:
        app.setStyleSheet(current_style + TOOLTIP_STYLESHEET)
