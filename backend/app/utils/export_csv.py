import csv
import logging
import os

logger = logging.getLogger(__name__)

def export_inventory_to_csv(data, filename):
    """Exporta lista de diccionarios a CSV."""
    if not data: return
    keys = data[0].keys()
    with open(filename, 'w', newline='', encoding='utf-8') as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(data)

def export_product_catalog_to_csv(data, filename):
    export_inventory_to_csv(data, filename)

def export_sales_to_csv(data, filename):
    """Exporta historial de ventas a CSV con TODAS las columnas disponibles."""
    if not data:
        logger.warning("No hay ventas para exportar")
        return False
    
    try:
        # Exportar TODAS las columnas dinámicamente
        keys = list(data[0].keys())
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
        
        logger.info(f"✅ Ventas exportadas a {filename} ({len(data)} registros, {len(keys)} columnas)")
        return True
    except Exception as e:
        logger.error(f"❌ Error exportando ventas: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def export_sales_detailed_to_csv(sales_data, sale_items_getter, filename):
    """
    Exporta historial de ventas SUPER DETALLADO a CSV.
    Incluye cada producto de cada transacción.
    
    Args:
        sales_data: Lista de ventas (diccionarios)
        sale_items_getter: Función que recibe sale_id y retorna items
        filename: Ruta del archivo a crear
    """
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Headers súper detallados
            writer.writerow([
                "FOLIO",
                "SERIE", 
                "FECHA",
                "HORA",
                "CLIENTE",
                "RFC_CLIENTE",
                "SKU",
                "CÓDIGO_BARRAS",
                "PRODUCTO",
                "CANTIDAD",
                "PRECIO_UNITARIO",
                "DESCUENTO",
                "SUBTOTAL_PRODUCTO",
                "MÉTODO_PAGO",
                "TOTAL_VENTA",
                "USUARIO",
                "SUCURSAL",
                "NOTAS"
            ])
            
            for sale in sales_data:
                sale_id = sale.get('id')
                folio = sale.get('folio_visible') or f"#{sale_id}"
                serie = sale.get('serie', 'A')
                
                # Separar fecha y hora
                timestamp = sale.get('timestamp', '')
                if ' ' in str(timestamp):
                    fecha, hora = str(timestamp).split(' ', 1)
                else:
                    fecha = str(timestamp)[:10] if timestamp else ''
                    hora = str(timestamp)[11:19] if timestamp and len(str(timestamp)) > 10 else ''
                
                cliente = sale.get('customer_name') or 'Público General'
                rfc_cliente = sale.get('customer_rfc') or ''
                metodo_pago = sale.get('payment_method') or sale.get('payment_methods') or ''
                total_venta = sale.get('total', 0)
                usuario = sale.get('username') or sale.get('user_id') or ''
                sucursal = sale.get('branch_name') or sale.get('branch_id') or ''
                notas = sale.get('notes') or ''
                
                # Obtener items de esta venta
                try:
                    items = sale_items_getter(sale_id)
                except Exception:
                    items = []
                
                if items:
                    for item in items:
                        # SKU desde products (via JOIN)
                        sku = item.get('sku') or item.get('product_sku') or ''
                        codigo_barras = item.get('barcode') or ''
                        producto = item.get('name') or item.get('product_name') or ''
                        
                        # Campos de sale_items (nombres reales en DB: qty, price, subtotal)
                        cantidad = item.get('qty') or item.get('quantity') or 0
                        precio_unitario = item.get('price') or item.get('unit_price') or 0
                        descuento = item.get('discount') or 0
                        
                        # Calcular subtotal si no viene
                        subtotal_item = item.get('subtotal') or (float(cantidad) * float(precio_unitario) - float(descuento or 0))
                        
                        writer.writerow([
                            folio,
                            serie,
                            fecha,
                            hora,
                            cliente,
                            rfc_cliente,
                            sku,
                            codigo_barras,
                            producto,
                            cantidad,
                            f"{float(precio_unitario):.2f}",
                            f"{float(descuento or 0):.2f}",
                            f"{float(subtotal_item):.2f}",
                            metodo_pago,
                            f"{float(total_venta):.2f}",
                            usuario,
                            sucursal,
                            notas
                        ])
                else:
                    # Venta sin items detallados (legacy)
                    writer.writerow([
                        folio,
                        serie,
                        fecha,
                        hora,
                        cliente,
                        rfc_cliente,
                        "",  # SKU
                        "",  # Código barras
                        "(Sin detalle de productos)",
                        "",  # Cantidad
                        "",  # Precio unitario
                        "",  # Descuento
                        "",  # Subtotal producto
                        metodo_pago,
                        f"{float(total_venta):.2f}",
                        usuario,
                        sucursal,
                        notas
                    ])
            
        logger.info(f"Ventas detalladas exportadas a {filename}")
        return True
    except Exception as e:
        logger.error(f"Error exportando ventas detalladas: {e}")
        import traceback
        traceback.print_exc()
        return False

def export_turn_to_csv(data, filename):
    """Exporta reporte de turno a CSV."""
    # Data suele ser un dict con resumen, no una lista plana.
    # Si es dict, lo escribimos como clave-valor
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if isinstance(data, dict):
                writer.writerow(["Concepto", "Valor"])
                for k, v in data.items():
                    writer.writerow([k, v])
            else:
                # Asumir lista
                writer.writerow(["Data"])
                for item in data:
                    writer.writerow([str(item)])
        return True
    except Exception as e:
        logger.error(f"Error exportando turno: {e}")
        return False

def export_report_to_csv(data, filename):
    """Exporta reporte genérico a CSV."""
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Intentar deducir headers del primer elemento
            if data and isinstance(data, list) and isinstance(data[0], dict):
                headers = list(data[0].keys())
                writer.writerow(headers)
                for item in data:
                    writer.writerow([item.get(h) for h in headers])
            else:
                writer.writerow(["Reporte"])
                writer.writerow([str(data)])
        return True
    except Exception as e:
        logger.error(f"Error exportando reporte: {e}")
        return False

def export_layaways_to_csv(data, filename):
    """Exporta apartados a CSV con TODAS las columnas disponibles."""
    if not data:
        logger.warning("No hay apartados para exportar")
        return False
    
    try:
        # Exportar TODAS las columnas dinámicamente
        keys = list(data[0].keys())
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
        
        logger.info(f"✅ Apartados exportados a {filename} ({len(data)} registros, {len(keys)} columnas)")
        return True
    except Exception as e:
        logger.error(f"❌ Error exportando apartados: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
