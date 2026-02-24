"""
Weekly Intelligence Report - Reporte semanal de inteligencia
Ejecutar cada domingo vía cron para monitoreo continuo
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import Any, Dict, List
from datetime import date, datetime, timedelta
from decimal import Decimal
import hashlib
import json
import logging
from pathlib import Path
import subprocess

logger = logging.getLogger(__name__)

class WeeklyIntelligence:
    """
    Genera reporte semanal de inteligencia fiscal y operativa.
    Diseñado para ejecución automática via cron.
    """
    
    RESICO_LIMIT = Decimal('3500000')  # Límite anual RESICO
    
    def __init__(self, core=None):
        if core is None:
            from app.core import POSCore
            core = POSCore()
        self.core = core
    
    def generate_report(self) -> Dict[str, Any]:
        """Genera reporte completo de inteligencia."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'week': datetime.now().isocalendar()[1],
            'sections': {}
        }
        
        # 1. Status RESICO
        report['sections']['resico'] = self._get_resico_status()
        
        # 2. Status de Mermas
        report['sections']['mermas'] = self._get_mermas_status()
        
        # 3. Health Check Multi-RFC
        report['sections']['multi_rfc'] = self._get_multi_rfc_status()
        
        # 4. Extracciones pendientes
        report['sections']['extracciones'] = self._get_extractions_status()
        
        # 5. Security Status
        report['sections']['security'] = self._get_security_status()
        
        # 6. Alertas críticas
        report['alerts'] = self._generate_alerts(report['sections'])
        
        return report
    
    def _get_resico_status(self) -> Dict[str, Any]:
        """Status de cumplimiento RESICO."""
        year = datetime.now().year
        
        # Total facturado Serie A
        sql = """
            SELECT COALESCE(SUM(total), 0) as total
            FROM sales
            WHERE serie = 'A'
            AND EXTRACT(YEAR FROM timestamp::timestamp) = %s
            AND status = 'completed'
        """
        result = list(self.core.db.execute_query(sql, (year,)))
        facturado = Decimal(str(result[0]['total'] or 0)) if result else Decimal('0')
        
        # Calcular distancia al límite
        restante = self.RESICO_LIMIT - facturado
        porcentaje = (facturado / self.RESICO_LIMIT) * 100
        
        # Proyección anual
        dias_transcurridos = (datetime.now() - datetime(year, 1, 1)).days or 1
        proyeccion_anual = (facturado / dias_transcurridos) * 365
        
        return {
            'facturado_serie_a': float(facturado),
            'limite_resico': float(self.RESICO_LIMIT),
            'restante': float(restante),
            'porcentaje_usado': round(float(porcentaje), 2),
            'proyeccion_anual': float(proyeccion_anual),
            'status': 'GREEN' if porcentaje < 70 else ('YELLOW' if porcentaje < 90 else 'RED'),
            'dias_restantes_anio': 365 - dias_transcurridos
        }
    
    def _get_mermas_status(self) -> Dict[str, Any]:
        """Status de mermas y documentación."""
        # Mermas de este mes
        month = datetime.now().strftime('%Y-%m')
        
        sql = """
            SELECT COUNT(*) as total,
                   COALESCE(SUM(CASE WHEN photo_path IS NOT NULL THEN 1 ELSE 0 END), 0) as with_evidence
            FROM loss_records
            WHERE TO_CHAR(created_at::timestamp, 'YYYY-MM') = %s
        """
        result = list(self.core.db.execute_query(sql, (month,)))
        
        total = result[0]['total'] or 0 if result else 0
        with_evidence = result[0]['with_evidence'] or 0 if result else 0
        
        return {
            'mermas_mes': total,
            'con_evidencia': with_evidence,
            'sin_evidencia': total - with_evidence,
            'porcentaje_documentado': round((with_evidence / total) * 100, 2) if total > 0 else 100,
            'status': 'GREEN' if (total - with_evidence) == 0 else 'YELLOW'
        }
    
    def _get_multi_rfc_status(self) -> Dict[str, Any]:
        """Status de distribución Multi-RFC."""
        try:
            from app.fiscal.multi_emitter import MultiEmitterEngine
            multi = MultiEmitterEngine(self.core)
            
            emitters = multi.get_all_emitters()
            distribution = []
            
            for e in emitters:
                if e['is_active']:
                    stats = multi.get_emitter_stats(e['rfc'])
                    distribution.append({
                        'rfc': e['rfc'][:4] + '***',  # Ocultar RFC completo
                        'facturado': stats.get('facturado_anio', 0),
                        'capacidad_restante': stats.get('capacidad_restante', 0),
                        'porcentaje': stats.get('porcentaje_usado', 0)
                    })
            
            return {
                'emisores_activos': len([e for e in emitters if e['is_active']]),
                'distribucion': distribution,
                'balance': 'BALANCED' if len(distribution) > 1 else 'SINGLE'
            }
        except Exception:
            return {'emisores_activos': 0, 'error': 'No disponible'}
    
    def _get_extractions_status(self) -> Dict[str, Any]:
        """Status de extracciones de efectivo."""
        year = datetime.now().year
        month = datetime.now().month
        
        try:
            sql = """
                SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count
                FROM cash_extractions
                WHERE EXTRACT(YEAR FROM extraction_date::date) = %s
            """
            result = list(self.core.db.execute_query(sql, (year,)))
            
            total_anio = float(result[0]['total'] or 0) if result else 0
            count_anio = result[0]['count'] or 0 if result else 0
            
            # Este mes
            sql_mes = """
                SELECT COALESCE(SUM(amount), 0) as total
                FROM cash_extractions
                WHERE TO_CHAR(extraction_date::timestamp, 'YYYY-MM') = %s
            """
            result_mes = list(self.core.db.execute_query(
                sql_mes, (f"{year}-{month:02d}",)
            ))
            total_mes = float(result_mes[0]['total'] or 0) if result_mes else 0
            
            return {
                'extraido_anio': total_anio,
                'extraido_mes': total_mes,
                'operaciones_anio': count_anio,
                'promedio_operacion': total_anio / count_anio if count_anio > 0 else 0
            }
        except Exception:
            return {'extraido_anio': 0, 'extraido_mes': 0}
    
    def _get_security_status(self) -> Dict[str, Any]:
        """Status de seguridad del sistema."""
        status = {
            'ramfs_mounted': False,
            'lockdown_active': False,
            'yubikey_configured': False,
            'fail2ban_active': False
        }
        
        # Verificar RAMFS
        try:
            result = subprocess.run(['mountpoint', '-q', '/mnt/ghost_logs'])
            status['ramfs_mounted'] = result.returncode == 0
        except Exception:
            pass
        
        # Verificar lockdown
        status['lockdown_active'] = Path('/tmp/.antigravity_lockdown').exists()
        
        # Verificar YubiKey config
        status['yubikey_configured'] = Path.home().joinpath(
            '.config/Yubico/u2f_keys'
        ).exists()
        
        # Verificar fail2ban
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'fail2ban'],
                capture_output=True, text=True
            )
            status['fail2ban_active'] = result.stdout.strip() == 'active'
        except Exception:
            pass
        
        return status
    
    def _generate_alerts(self, sections: Dict) -> List[Dict[str, Any]]:
        """Genera alertas basadas en los datos."""
        alerts = []
        
        # Alerta RESICO
        resico = sections.get('resico', {})
        if resico.get('status') == 'RED':
            alerts.append({
                'level': 'CRITICAL',
                'category': 'RESICO',
                'message': f'⚠️ LÍMITE RESICO AL {resico["porcentaje_usado"]}% - CAMBIAR RFC'
            })
        elif resico.get('status') == 'YELLOW':
            alerts.append({
                'level': 'WARNING',
                'category': 'RESICO',
                'message': f'⚡ Acercándose al límite RESICO ({resico["porcentaje_usado"]}%)'
            })
        
        # Alerta mermas sin evidencia
        mermas = sections.get('mermas', {})
        if mermas.get('sin_evidencia', 0) > 0:
            alerts.append({
                'level': 'WARNING',
                'category': 'MERMAS',
                'message': f'📸 {mermas["sin_evidencia"]} mermas sin evidencia fotográfica'
            })
        
        # Alerta RAMFS
        security = sections.get('security', {})
        if not security.get('ramfs_mounted'):
            alerts.append({
                'level': 'WARNING',
                'category': 'SECURITY',
                'message': '💾 RAMFS no montado - Logs no volátiles'
            })
        
        return alerts
    
    def get_printable_report(self) -> str:
        """Genera reporte en formato texto."""
        report = self.generate_report()
        
        output = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    REPORTE DE INTELIGENCIA SEMANAL                           ║
║                    Semana {report['week']} - {datetime.now().strftime('%Y-%m-%d')}                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

📊 STATUS RESICO
───────────────────────────────────────────────────────────────────────────────
   Facturado Serie A:     ${report['sections']['resico']['facturado_serie_a']:,.2f}
   Límite RESICO:         ${report['sections']['resico']['limite_resico']:,.2f}
   Restante:              ${report['sections']['resico']['restante']:,.2f}
   Uso:                   {report['sections']['resico']['porcentaje_usado']}%
   Proyección Anual:      ${report['sections']['resico']['proyeccion_anual']:,.2f}
   Status:                [{report['sections']['resico']['status']}]

📋 STATUS MERMAS
───────────────────────────────────────────────────────────────────────────────
   Mermas este mes:       {report['sections']['mermas']['mermas_mes']}
   Con evidencia:         {report['sections']['mermas']['con_evidencia']}
   Sin evidencia:         {report['sections']['mermas']['sin_evidencia']}
   Documentación:         {report['sections']['mermas']['porcentaje_documentado']}%

💰 EXTRACCIONES
───────────────────────────────────────────────────────────────────────────────
   Extraído este año:     ${report['sections']['extracciones']['extraido_anio']:,.2f}
   Extraído este mes:     ${report['sections']['extracciones']['extraido_mes']:,.2f}
   Operaciones:           {report['sections']['extracciones']['operaciones_anio']}

🔒 SEGURIDAD
───────────────────────────────────────────────────────────────────────────────
   RAMFS:                 {'🟢 Montado' if report['sections']['security']['ramfs_mounted'] else '🔴 No montado'}
   Lockdown:              {'🟢 Activo' if report['sections']['security']['lockdown_active'] else '⚪ Inactivo'}
   YubiKey:               {'🟢 Configurada' if report['sections']['security']['yubikey_configured'] else '⚪ No configurada'}
   Fail2ban:              {'🟢 Activo' if report['sections']['security']['fail2ban_active'] else '⚪ Inactivo'}
"""
        
        if report['alerts']:
            output += """
⚠️ ALERTAS
───────────────────────────────────────────────────────────────────────────────
"""
            for alert in report['alerts']:
                output += f"   [{alert['level']}] {alert['message']}\n"
        
        output += """
═══════════════════════════════════════════════════════════════════════════════
                              FIN DEL REPORTE
═══════════════════════════════════════════════════════════════════════════════
"""
        
        return output
    
    def send_to_telegram(self, bot_token: str, chat_id: str) -> bool:
        """Envía reporte a Telegram."""
        import urllib.parse
        import urllib.request
        
        report = self.get_printable_report()
        
        # Telegram tiene límite de 4096 caracteres
        if len(report) > 4000:
            report = report[:4000] + "\n... [truncado]"
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = urllib.parse.urlencode({
            'chat_id': chat_id,
            'text': report,
            'parse_mode': 'Markdown'
        }).encode()
        
        try:
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=10) as response:
                _ = response.read()  # Consume response to release connection
            return True
        except Exception as e:
            logger.error(f"Error enviando a Telegram: {e}")
            return False
    
    def save_report(self, path: str = None) -> str:
        """Guarda reporte cifrado en disco."""
        if path is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
            path = str(base_dir / f"docs/intel/weekly_{datetime.now().strftime('%Y%m%d')}.txt")
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        report = self.get_printable_report()
        Path(path).write_text(report)
        
        # Crear hash de integridad
        hash_value = hashlib.sha256(report.encode()).hexdigest()
        Path(path + '.sha256').write_text(hash_value)
        
        return path

# CLI para ejecución directa
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Weekly Intelligence Report')
    parser.add_argument('--telegram', nargs=2, metavar=('BOT_TOKEN', 'CHAT_ID'))
    parser.add_argument('--save', type=str, help='Path to save report')
    parser.add_argument('--print', action='store_true', help='Print to stdout')
    args = parser.parse_args()
    
    intel = WeeklyIntelligence()
    
    if args.print or (not args.telegram and not args.save):
        print(intel.get_printable_report())
    
    if args.telegram:
        intel.send_to_telegram(args.telegram[0], args.telegram[1])
    
    if args.save:
        path = intel.save_report(args.save)
        print(f"Reporte guardado en: {path}")
