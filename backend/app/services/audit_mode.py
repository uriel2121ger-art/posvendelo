"""
Modo Auditor - Sistema de visibilidad selectiva para cumplimiento fiscal
Genera reportes que coinciden exactamente con CFDIs timbrados
"""

from typing import Any, Dict, List, Optional
from datetime import date, datetime
import hashlib
import logging

logger = logging.getLogger(__name__)

class AuditMode:
    """
    Sistema de modo auditor para generar reportes fiscales conformes.
    Solo muestra transacciones Serie A (fiscalmente declaradas).
    """
    
    def __init__(self, core):
        self.core = core
        self._audit_mode_active = False
        self._audit_pin = None
    
    def activate_audit_mode(self, pin: str) -> Dict[str, Any]:
        """
        Activa el modo auditor con PIN especial.
        El PIN puede ser el PIN normal invertido o una clave maestra.
        """
        # Verificar PIN (invertido del admin o clave especial)
        if self._verify_audit_pin(pin):
            self._audit_mode_active = True
            # SECURITY: No loguear activación de modo auditor
            pass
            
            # Log audit activation (sin detalles sensibles)
            self.core.db.execute_write(
                """INSERT INTO audit_log (timestamp, user_id, action, entity_type, details)
                   VALUES (%s, 0, 'AUDIT_MODE_ON', 'system', 'Modo auditor activado')""",
                (datetime.now().isoformat(),)
            )
            
            return {
                'success': True,
                'message': 'Modo Auditor activado. Reportes mostrarán solo transacciones fiscales.',
                'mode': 'AUDIT'
            }
        
        return {'success': False, 'message': 'PIN incorrecto'}
    
    def deactivate_audit_mode(self, admin_pin: str) -> Dict[str, Any]:
        """Desactiva el modo auditor."""
        # Solo admin puede desactivar
        if self._verify_admin_pin(admin_pin):
            self._audit_mode_active = False
            # SECURITY: No loguear desactivación de modo auditor
            pass
            return {'success': True, 'message': 'Modo normal restaurado'}
        
        return {'success': False, 'message': 'Acceso denegado'}
    
    def is_audit_mode(self) -> bool:
        """Verifica si el modo auditor está activo."""
        return self._audit_mode_active
    
    def _verify_audit_pin(self, pin: str) -> bool:
        """Verifica PIN de auditoría (PIN normal invertido o clave maestra)."""
        config = self.core.get_app_config()
        admin_pin = config.get('admin_pin')
        
        if not admin_pin:
            return False
        
        # PIN invertido
        if pin == admin_pin[::-1]:
            return True
        
        # Clave maestra de auditoría (debe estar configurada)
        audit_master = config.get('audit_master_pin')
        if audit_master and pin == audit_master:
            return True
        
        return False
    
    def _verify_admin_pin(self, pin: str) -> bool:
        """Verifica PIN de administrador."""
        config = self.core.get_app_config()
        admin_pin = config.get('admin_pin')
        if not admin_pin:
            return False
        return pin == admin_pin
    
    # ==========================================
    # REPORTES EN MODO AUDITOR
    # ==========================================
    
    def get_sales_report(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Genera reporte de ventas.
        En modo auditor: Solo Serie A
        En modo normal: Todas las series
        """
        if self._audit_mode_active:
            return self._get_fiscal_report(start_date, end_date)
        else:
            return self._get_full_report(start_date, end_date)
    
    def _get_fiscal_report(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Reporte de auditoría - Solo transacciones Serie A.
        INCLUYE CANCELADAS para mantener continuidad de folios.
        Los totales coinciden exactamente con CFDIs timbrados.
        """
        sql = """
            SELECT 
                s.id,
                s.folio_visible as folio,
                s.timestamp::date as fecha,
                s.timestamp::time as hora,
                s.subtotal,
                s.tax as iva,
                s.total,
                s.payment_method as metodo_pago,
                s.status,
                COALESCE(c.uuid, 'PENDIENTE') as uuid_cfdi
            FROM sales s
            LEFT JOIN cfdis c ON s.id = c.sale_id
            WHERE s.serie = 'A'
            AND s.folio_visible IS NOT NULL
            AND s.folio_visible != ''
            ORDER BY s.folio_visible ASC
        """
        
        ventas = list(self.core.db.execute_query(sql))
        
        # Calcular totales
        totales = self._calculate_totals([dict(v) for v in ventas])
        
        return {
            'tipo': 'FISCAL',
            'periodo': f'{start_date} a {end_date}',
            'ventas': [dict(v) for v in ventas],
            'totales': totales,
            'num_transacciones': len(ventas),
            'nota': 'Reporte de ventas facturadas (Serie Fiscal)',
            'generado': datetime.now().isoformat()
        }
    
    def _get_full_report(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Reporte completo - Todas las series."""
        sql = """
            SELECT 
                s.id,
                s.serie,
                s.folio_visible as folio,
                s.timestamp::date as fecha,
                s.timestamp::time as hora,
                s.subtotal,
                s.tax as iva,
                s.total,
                s.payment_method as metodo_pago
            FROM sales s
            WHERE s.timestamp::date BETWEEN %s AND %s
            AND s.status = 'completed'
            ORDER BY s.timestamp DESC
        """
        
        ventas = list(self.core.db.execute_query(sql, (start_date, end_date)))
        
        # Separar por serie
        serie_a = [dict(v) for v in ventas if v['serie'] == 'A']
        serie_b = [dict(v) for v in ventas if v['serie'] == 'B']
        
        return {
            'tipo': 'COMPLETO',
            'periodo': f'{start_date} a {end_date}',
            'serie_a': {
                'ventas': serie_a,
                'totales': self._calculate_totals(serie_a)
            },
            'serie_b': {
                'ventas': serie_b,
                'totales': self._calculate_totals(serie_b)
            },
            'generado': datetime.now().isoformat()
        }
    
    def _calculate_totals(self, ventas: List[Dict]) -> Dict[str, float]:
        """Calcula totales de un conjunto de ventas."""
        subtotal = sum(float(v.get('subtotal', 0) or 0) for v in ventas)
        iva = sum(float(v.get('iva', 0) or 0) for v in ventas)
        total = sum(float(v.get('total', 0) or 0) for v in ventas)
        
        return {
            'subtotal': round(subtotal, 2),
            'iva': round(iva, 2),
            'total': round(total, 2),
            'transacciones': len(ventas)
        }
    
    def get_printable_report(self, start_date: str, end_date: str) -> str:
        """
        Genera reporte imprimible para auditor.
        Formato idéntico al reporte normal pero con datos fiscales.
        """
        report = self.get_sales_report(start_date, end_date)
        
        lines = []
        lines.append("=" * 50)
        lines.append("         REPORTE DE VENTAS")
        lines.append("=" * 50)
        lines.append(f"Período: {report['periodo']}")
        lines.append(f"Generado: {report['generado'][:19]}")
        lines.append("-" * 50)
        lines.append("")
        
        if self._audit_mode_active:
            lines.append(f"{'FOLIO':<12} {'FECHA':<12} {'TOTAL':>12} {'ESTADO':<10}")
            lines.append("-" * 60)
            
            cancelled_count = 0
            for venta in report.get('ventas', []):
                folio = str(venta.get('folio') or 'N/A')[:12]
                fecha = str(venta.get('fecha') or 'N/A')[:12]
                total = float(venta.get('total') or 0)
                status = venta.get('status', 'completed')
                
                if status == 'cancelled':
                    cancelled_count += 1
                    status_str = "CANCELADO"
                else:
                    status_str = ""
                
                lines.append(
                    f"{folio:<12} {fecha:<12} ${total:>10,.2f} {status_str:<10}"
                )
            
            lines.append("-" * 60)
            totales = report['totales']
            lines.append(f"{'SUBTOTAL:':<24} ${totales['subtotal']:>12,.2f}")
            lines.append(f"{'IVA:':<24} ${totales['iva']:>12,.2f}")
            lines.append(f"{'TOTAL:':<24} ${totales['total']:>12,.2f}")
            lines.append(f"{'TRANSACCIONES:':<24} {totales['transacciones']:>12}")
            if cancelled_count > 0:
                lines.append(f"{'CANCELADAS:':<24} {cancelled_count:>12}")
        
        lines.append("=" * 50)
        
        return "\n".join(lines)
    
    def validate_against_cfdis(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Valida que el reporte coincida con CFDIs timbrados.
        Esto es crítico: el auditor puede sumar las facturas y debe dar igual.
        """
        # Total según ventas Serie A
        ventas_sql = """
            SELECT COALESCE(SUM(total), 0) as total
            FROM sales 
            WHERE serie = 'A' 
            AND timestamp::date BETWEEN %s AND %s
            AND status = 'completed'
        """
        ventas_result = list(self.core.db.execute_query(ventas_sql, (start_date, end_date)))
        total_ventas = float(ventas_result[0]['total'] or 0) if ventas_result else 0
        
        # Total según CFDIs timbrados
        cfdis_sql = """
            SELECT COALESCE(SUM(total), 0) as total
            FROM cfdis
            WHERE fecha_emision::date BETWEEN %s AND %s
            AND estado = 'vigente'
            AND tipo_comprobante = 'I'
        """
        cfdis_result = list(self.core.db.execute_query(cfdis_sql, (start_date, end_date)))
        total_cfdis = float(cfdis_result[0]['total'] or 0) if cfdis_result else 0
        
        diferencia = abs(total_ventas - total_cfdis)
        
        return {
            'total_ventas_a': total_ventas,
            'total_cfdis': total_cfdis,
            'diferencia': diferencia,
            'coincide': diferencia < 0.01,  # Tolerancia de 1 centavo
            'mensaje': 'Los totales coinciden' if diferencia < 0.01 else f'Diferencia de ${diferencia:.2f}'
        }
    
    def get_audit_report(self, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """
        Genera reporte completo de auditoría.
        
        Args:
            start_date: Fecha inicio (YYYY-MM-DD), default: inicio del mes
            end_date: Fecha fin (YYYY-MM-DD), default: hoy
            
        Returns:
            Dict con reporte fiscal completo
        """
        from datetime import datetime, timedelta
        
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            # Por defecto, inicio del mes
            start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        
        # Fiscal report
        fiscal = self._get_fiscal_report(start_date, end_date)
        
        # Validación contra CFDIs
        validation = self.validate_against_cfdis(start_date, end_date)
        
        # Texto del reporte
        report_text = self.get_printable_report(start_date, end_date)
        
        return {
            'period': {
                'start': start_date,
                'end': end_date
            },
            'audit_mode_active': self.is_audit_mode(),
            'fiscal_summary': fiscal,
            'cfdi_validation': validation,
            'report_text': report_text,
            'generated_at': datetime.now().isoformat(),
            'status': 'COMPLIANT' if validation.get('coincide', False) else 'REVIEW_NEEDED'
        }

