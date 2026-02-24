from pathlib import Path

"""
General de Guerra - Reporte Semanal Inteligente
Auditoría cruzada automática con IA que llega cada domingo
"""

from typing import Any, Dict, List
from datetime import datetime, timedelta
from decimal import Decimal
import json
import logging
import sys

logger = logging.getLogger(__name__)

class GeneralDeGuerra:
    """
    Sistema de Análisis Semanal con IA.
    
    Funciones:
    - Auditoría cruzada automática
    - Detección de anomalías
    - Sugerencias accionables
    - Generación de reporte Telegram/PWA
    """
    
    def __init__(self, core):
        self.core = core
        self.findings = []
        self.report = {}
    
    def run_weekly_analysis(self) -> Dict[str, Any]:
        """
        Ejecuta análisis completo semanal.
        Retorna reporte estructurado.
        """
        logger.info("🎖️ General de Guerra: Iniciando análisis semanal")
        
        self.findings = []
        
        # 1. Análisis de Inventario
        inventory_findings = self._analyze_inventory()
        self.findings.extend(inventory_findings)
        
        # 2. Análisis de Materialidad
        materiality_findings = self._analyze_materiality()
        self.findings.extend(materiality_findings)
        
        # 3. Análisis Fiscal (RESICO)
        fiscal_findings = self._analyze_fiscal()
        self.findings.extend(fiscal_findings)
        
        # 4. Análisis de Cash Extraction
        cash_findings = self._analyze_cash_extraction()
        self.findings.extend(cash_findings)
        
        # 5. Análisis de Cajeras (Sentinel)
        cashier_findings = self._analyze_cashiers()
        self.findings.extend(cashier_findings)
        
        # Generar reporte
        self.report = self._generate_report()
        
        logger.info(f"🎖️ Análisis completado: {len(self.findings)} hallazgos")
        
        return self.report
    
    # =========================================
    # ANÁLISIS DE INVENTARIO
    # =========================================
    
    def _analyze_inventory(self) -> List[Dict]:
        """Analiza varianzas de inventario."""
        findings = []
        
        # Buscar productos con varianza significativa
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Comparar stock registrado vs movimientos
        products = list(self.core.db.execute_query("""
            SELECT p.id, p.name, p.stock,
                   COALESCE(SUM(CASE WHEN si.sale_id IS NOT NULL THEN si.qty ELSE 0 END), 0) as sold,
                   COALESCE(SUM(CASE WHEN pc.id IS NOT NULL THEN pc.quantity ELSE 0 END), 0) as purchased
            FROM products p
            LEFT JOIN sale_items si ON p.id = si.product_id 
                AND EXISTS(SELECT 1 FROM sales s WHERE s.id = si.sale_id AND CAST(s.timestamp AS DATE) >= %s)
            LEFT JOIN purchase_costs pc ON p.id = pc.product_id 
                AND CAST(pc.purchase_date AS DATE) >= %s
            WHERE p.stock > 0
            GROUP BY p.id
            HAVING (sold > 0 OR purchased > 0)
            LIMIT 50
        """, (week_ago, week_ago)))
        
        for p in products:
            sold = float(p['sold'] or 0)
            purchased = float(p['purchased'] or 0)
            stock = float(p['stock'] or 0)
            
            # Calcular varianza esperada vs real
            expected_variance = purchased - sold
            
            # Si hay discrepancia mayor a 10%, reportar
            if abs(expected_variance) > stock * 0.1:
                findings.append({
                    'type': 'inventory',
                    'severity': 'medium',
                    'title': f'Varianza en inventario',
                    'message': f'{p["name"]}: Varianza de {expected_variance:+.0f} unidades',
                    'action': f'Realizar conteo físico del producto #{p["id"]}'
                })
        
        return findings
    
    # =========================================
    # ANÁLISIS DE MATERIALIDAD
    # =========================================
    
    def _analyze_materiality(self) -> List[Dict]:
        """Verifica que las mermas tengan evidencia."""
        findings = []
        
        # Mermas sin foto de evidencia
        mermas_sin_foto = list(self.core.db.execute_query("""
            SELECT COUNT(*) as count
            FROM shrinkage
            WHERE (photo_url IS NULL OR photo_url = '')
            AND CAST(timestamp AS DATE) >= CURRENT_DATE - INTERVAL '7 days'
        """))
        
        count = int(mermas_sin_foto[0]['count'] or 0) if mermas_sin_foto else 0
        
        if count > 0:
            findings.append({
                'type': 'materiality',
                'severity': 'high' if count > 5 else 'medium',
                'title': f'{count} mermas sin foto',
                'message': f'{count} registros de merma sin evidencia fotográfica esta semana',
                'action': 'Exigir fotos obligatorias a cajeras del turno matutino'
            })
        
        # Mermas sin acta generada
        mermas_sin_acta = list(self.core.db.execute_query("""
            SELECT COUNT(*) as count
            FROM shrinkage
            WHERE (acta_id IS NULL)
            AND CAST(timestamp AS DATE) >= CURRENT_DATE - INTERVAL '7 days'
            AND approved = 1
        """))
        
        count_acta = int(mermas_sin_acta[0]['count'] or 0) if mermas_sin_acta else 0
        
        if count_acta > 0:
            findings.append({
                'type': 'materiality',
                'severity': 'high',
                'title': f'{count_acta} mermas sin acta Helios',
                'message': f'Mermas aprobadas sin acta de respaldo legal',
                'action': 'Generar actas Helios pendientes'
            })
        
        return findings
    
    # =========================================
    # ANÁLISIS FISCAL (RESICO)
    # =========================================
    
    def _analyze_fiscal(self) -> List[Dict]:
        """Analiza situación fiscal multi-RFC."""
        findings = []
        
        ANNUAL_LIMIT = 3500000
        
        # Obtener facturación por RFC
        try:
            rfcs = list(self.core.db.execute_query("""
                SELECT rfc, COALESCE(SUM(total), 0) as total
                FROM invoices
                WHERE EXTRACT(YEAR FROM fecha) = EXTRACT(YEAR FROM CURRENT_DATE)
                GROUP BY rfc
            """))
        except Exception as e:
            logger.debug(f"Error fetching RFC data: {e}")
            rfcs = []
        
        for rfc_data in rfcs:
            rfc = rfc_data.get('rfc', 'Unknown')
            total = float(rfc_data.get('total', 0))
            percentage = (total / ANNUAL_LIMIT) * 100
            
            if percentage >= 85:
                findings.append({
                    'type': 'fiscal',
                    'severity': 'high' if percentage >= 95 else 'medium',
                    'title': f'RFC {rfc[:4]}*** al {percentage:.0f}%',
                    'message': f'RFC cerca del límite RESICO. Quedan ${ANNUAL_LIMIT - total:,.0f}',
                    'action': f'Rotar facturas a otro RFC'
                })
        
        return findings
    
    # =========================================
    # ANÁLISIS DE CASH EXTRACTION
    # =========================================
    
    def _analyze_cash_extraction(self) -> List[Dict]:
        """Verifica estado de extracción de efectivo."""
        findings = []
        
        # Efectivo pendiente de extracción
        try:
            pending = list(self.core.db.execute_query("""
                SELECT COALESCE(SUM(total), 0) as total
                FROM sales
                WHERE serie = 'B'
                AND payment_method = 'cash'
                AND CAST(timestamp AS DATE) >= CURRENT_DATE - INTERVAL '30 days'
            """))
            
            extractions = list(self.core.db.execute_query("""
                SELECT COALESCE(SUM(amount), 0) as total
                FROM cash_extractions
                WHERE CAST(extraction_date AS DATE) >= CURRENT_DATE - INTERVAL '30 days'
            """))
            
            pending_cash = (float(pending[0]['total'] or 0) if pending else 0) - (float(extractions[0]['total'] or 0) if extractions else 0)
            
            if pending_cash > 50000:
                findings.append({
                    'type': 'cash',
                    'severity': 'medium',
                    'title': f'${pending_cash:,.0f} pendientes de extraer',
                    'message': f'Efectivo Serie B acumulado sin contrato de extracción',
                    'action': 'Generar contratos de donación en PWA'
                })
        except Exception as e:
            logger.debug(f"Error analyzing cash extraction: {e}")
        
        return findings
    
    # =========================================
    # ANÁLISIS DE CAJERAS (SENTINEL)
    # =========================================
    
    def _analyze_cashiers(self) -> List[Dict]:
        """Detecta comportamiento anómalo de cajeras."""
        findings = []
        
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Cajeras con muchas anulaciones
        try:
            voids = list(self.core.db.execute_query("""
                SELECT u.name, COUNT(*) as void_count
                FROM sale_voids sv
                JOIN users u ON sv.voided_by = u.id
                WHERE sv.void_date::date >= %s
                GROUP BY u.name
                HAVING COUNT(*) > 10
            """, (week_ago,)))

            for v in voids:
                findings.append({
                    'type': 'cashier',
                    'severity': 'high',
                    'title': f'Cajera con {v["void_count"]} anulaciones',
                    'message': f'{v["name"]} tiene un número inusual de anulaciones esta semana',
                    'action': 'Revisar tickets anulados y hablar con empleada'
                })
        except Exception as e:
            logger.debug(f"Error analyzing voids: {e}")
        
        # Descuentos excesivos
        try:
            discounts = list(self.core.db.execute_query("""
                SELECT u.name, COALESCE(SUM(s.discount_amount), 0) as total_discount
                FROM sales s
                JOIN users u ON s.cashier_id = u.id
                WHERE s.timestamp::date >= %s
                AND s.discount_amount > 0
                GROUP BY u.name
                HAVING SUM(s.discount_amount) > 5000
            """, (week_ago,)))

            for d in discounts:
                findings.append({
                    'type': 'cashier',
                    'severity': 'medium',
                    'title': f'${d["total_discount"]:,.0f} en descuentos',
                    'message': f'{d["name"]} otorgó descuentos excesivos esta semana',
                    'action': 'Verificar autorización de descuentos'
                })
        except Exception as e:
            logger.debug(f"Error analyzing discounts: {e}")
        
        return findings
    
    # =========================================
    # GENERACIÓN DE REPORTE
    # =========================================
    
    def _generate_report(self) -> Dict[str, Any]:
        """Genera el reporte estructurado."""
        # Agrupar por tipo
        by_type = {}
        for f in self.findings:
            t = f['type']
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(f)
        
        # Contar severidades
        severity_count = {
            'high': len([f for f in self.findings if f['severity'] == 'high']),
            'medium': len([f for f in self.findings if f['severity'] == 'medium']),
            'low': len([f for f in self.findings if f['severity'] == 'low'])
        }
        
        return {
            'generated_at': datetime.now().isoformat(),
            'total_findings': len(self.findings),
            'severity_breakdown': severity_count,
            'by_category': by_type,
            'findings': self.findings,
            'summary': self._generate_summary(severity_count)
        }
    
    def _generate_summary(self, severity_count: Dict) -> str:
        """Genera resumen ejecutivo."""
        if severity_count['high'] > 0:
            return f"⚠️ ATENCIÓN: {severity_count['high']} hallazgos críticos requieren acción inmediata"
        elif severity_count['medium'] > 0:
            return f"📋 {severity_count['medium']} hallazgos moderados para revisar"
        else:
            return "✅ Sistema operando dentro de parámetros normales"
    
    def format_telegram(self) -> str:
        """Formatea reporte para Telegram."""
        r = self.report
        
        msg = f"""
🎖️ *GENERAL DE GUERRA - REPORTE SEMANAL*
📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}

{r.get('summary', '')}

📊 *RESUMEN:*
• 🔴 Críticos: {r['severity_breakdown']['high']}
• 🟡 Moderados: {r['severity_breakdown']['medium']}
• 🟢 Menores: {r['severity_breakdown']['low']}

"""
        
        # Agregar hallazgos críticos
        high_priority = [f for f in self.findings if f['severity'] == 'high']
        if high_priority:
            msg += "🚨 *ACCIONES URGENTES:*\n"
            for f in high_priority[:5]:
                msg += f"• {f['title']}\n  → {f['action']}\n"
        
        msg += "\n📱 _Revisa la PWA para más detalles_"
        
        return msg
    
    def send_telegram(self, bot_token: str, chat_id: str) -> bool:
        """Envía reporte a Telegram."""
        import urllib.parse
        import urllib.request
        
        message = self.format_telegram()
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = urllib.parse.urlencode({
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'Markdown'
        }).encode()
        
        try:
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=10) as response:
                _ = response.read()  # Consume response to release connection
            return True
        except Exception as e:
            logger.error(f"Error enviando Telegram: {e}")
            return False

# Función para cron job
def run_weekly_report(core):
    """Ejecutar desde cron cada domingo a las 23:59."""
    general = GeneralDeGuerra(core)
    report = general.run_weekly_analysis()
    
    # Enviar a Telegram
    try:
        config_rows = core.db.execute_query("SELECT key, value FROM config WHERE key IN ('telegram_bot_token', 'telegram_chat_id')")
        config = {row['key']: row['value'] for row in config_rows} if config_rows else {}
        bot_token = config.get('telegram_bot_token')
        chat_id = config.get('telegram_chat_id')

        if bot_token and chat_id:
            general.send_telegram(bot_token, chat_id)
    except Exception as e:
        logger.warning(f"Could not send Telegram notification: {e}")
    
    return report
