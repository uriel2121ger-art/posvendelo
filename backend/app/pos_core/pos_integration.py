"""
Integración del Sistema POS Optimizado con SalesTab
Proporciona funciones de callback para impresión y cajón
"""
import logging
import subprocess
import threading
import time
from typing import Optional

from app.pos_core.pos_optimized import OptimizedPOSSystem, Sale
from app.utils import ticket_engine
from app.utils.path_utils import get_debug_log_path_str

logger = logging.getLogger(__name__)

# Lock global para impresora (compartido entre todas las instancias)
_printer_lock = threading.Lock()
_drawer_lock = threading.Lock()


def create_print_callback(core, cfg):
    """
    Crea callback para imprimir tickets usando el sistema optimizado
    
    Args:
        core: Instancia de POSCore
        cfg: Configuración de la app
    
    Returns:
        Función callback (sale, full_ticket) -> None
    """
    printer_name = cfg.get("printer_name", "")
    
    def print_ticket_callback(sale: Sale, full_ticket: bool = True):
        """
        Callback para imprimir ticket
        
        Args:
            sale: Objeto Sale con datos de la venta
            full_ticket: Si True, imprime ticket completo; si False, comprobante temporal
        """
        if not printer_name:
            logger.warning("No hay impresora configurada")
            return
        
        try:
            # Convertir Sale a formato sale_data para ticket_engine
            sale_data = {
                'id': sale.sale_id,
                'folio_visible': sale.folio,
                'serie': sale.folio.split('-')[0] if '-' in sale.folio else 'B',
                'created_at': sale.timestamp.isoformat(),
                'subtotal': sale.subtotal,
                'tax': sale.tax,
                'discount': sale.discount,
                'total': sale.total,
                'payment_method': sale.payment_method,
                'items': [
                    {
                        'product_id': item.product_id,
                        'sku': item.sku,
                        'name': item.name,
                        'qty': item.qty,
                        'price': item.price,
                        'base_price': item.base_price,
                        'discount': item.discount,
                        'subtotal': item.qty * item.price - item.discount,
                        'total': item.qty * item.price - item.discount,
                        'is_wholesale': item.is_wholesale,
                        'sale_type': item.sale_type
                    }
                    for item in sale.items
                ]
            }
            
            # Construir contenido del ticket (siempre completo)
            ticket_content = ticket_engine.build_custom_ticket(cfg, sale_data, core)
            
            # ESC/POS Initialization
            init_sequence = b'\x1B\x40'
            # Encoding para impresora termica ESC/POS (requiere latin-1/CP437)
            full_content = init_sequence + ticket_content.encode('latin-1', errors='replace')
            
            # Timeout fijo de 20 segundos
            timeout = 20
            
            # Log antes de imprimir
            import json
            import os
            log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.cursor', 'debug.log')
            print_start = time.time()
            try:
                with open(log_path, 'a', encoding='utf-8') as f:
                    json.dump({
                        'timestamp': print_start * 1000,
                        'location': 'pos_integration.py:87',
                        'message': 'Iniciando impresión de ticket',
                        'data': {
                            'sale_id': sale.sale_id,
                            'items_count': len(sale.items),
                            'timeout_seconds': timeout,
                            'full_ticket': full_ticket
                        },
                        'sessionId': 'debug-session',
                        'runId': 'test-run',
                        'hypothesisId': 'C'
                    }, f, ensure_ascii=False)
                    f.write('\n')
            except Exception:
                pass
            
            # Imprimir con timeout
            result = subprocess.run(
                ["lp", "-d", printer_name, "-o", "raw", "-"],
                input=full_content,
                capture_output=True,
                timeout=timeout
            )
            
            print_elapsed = time.time() - print_start
            
            if result.returncode == 0:
                logger.info(f"✅ Ticket impreso: Sale #{sale.sale_id} ({'completo' if full_ticket else 'temporal'})")
                try:
                    with open(log_path, 'a', encoding='utf-8') as f:
                        json.dump({
                            'timestamp': time.time() * 1000,
                            'location': 'pos_integration.py:97',
                            'message': 'Ticket impreso exitosamente',
                            'data': {
                                'sale_id': sale.sale_id,
                                'elapsed_ms': print_elapsed * 1000,
                                'timeout_seconds': timeout,
                                'within_timeout': print_elapsed <= timeout
                            },
                            'sessionId': 'debug-session',
                            'runId': 'test-run',
                            'hypothesisId': 'C'
                        }, f, ensure_ascii=False)
                        f.write('\n')
                except Exception:
                    pass
            else:
                error = result.stderr.decode('utf-8', errors='ignore')
                logger.error(f"❌ Error imprimiendo: {error}")
                try:
                    with open(log_path, 'a', encoding='utf-8') as f:
                        json.dump({
                            'timestamp': time.time() * 1000,
                            'location': 'pos_integration.py:98',
                            'message': 'Error imprimiendo ticket',
                            'data': {
                                'sale_id': sale.sale_id,
                                'elapsed_ms': print_elapsed * 1000,
                                'error': error,
                                'returncode': result.returncode
                            },
                            'sessionId': 'debug-session',
                            'runId': 'test-run',
                            'hypothesisId': 'C'
                        }, f, ensure_ascii=False)
                        f.write('\n')
                except Exception:
                    pass
                
        except subprocess.TimeoutExpired:
            print_elapsed = time.time() - print_start
            logger.error(f"⏱️ Timeout imprimiendo Sale #{sale.sale_id}")
            try:
                with open(log_path, 'a', encoding='utf-8') as f:
                    json.dump({
                        'timestamp': time.time() * 1000,
                        'location': 'pos_integration.py:101',
                        'message': 'Timeout al imprimir ticket',
                        'data': {
                            'sale_id': sale.sale_id,
                            'elapsed_ms': print_elapsed * 1000,
                            'timeout_seconds': timeout,
                            'exceeded_by_ms': (print_elapsed - timeout) * 1000
                        },
                        'sessionId': 'debug-session',
                        'runId': 'test-run',
                        'hypothesisId': 'C'
                    }, f, ensure_ascii=False)
                    f.write('\n')
            except Exception:
                pass
        except Exception as e:
            logger.exception(f"❌ Error en callback de impresión: {e}")
    
    return print_ticket_callback


def create_drawer_callback(cfg):
    """
    Crea callback para abrir cajón
    
    Args:
        cfg: Configuración de la app
    
    Returns:
        Función callback () -> None
    """
    printer_name = cfg.get("printer_name", "")
    pulse_str = cfg.get("cash_drawer_pulse_bytes", "\\x1B\\x70\\x00\\x19\\xFA")
    
    def open_drawer_callback():
        """Callback para abrir cajón"""
        if not printer_name:
            logger.warning("No hay impresora configurada para cajón")
            return
        
        try:
            ticket_engine.open_cash_drawer(printer_name, pulse_str)
            logger.info("💵 Cajón abierto")
        except Exception as e:
            logger.exception(f"❌ Error abriendo cajón: {e}")
    
    return open_drawer_callback
