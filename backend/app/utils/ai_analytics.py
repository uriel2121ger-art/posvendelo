"""
AI Analytics - Módulo de Inteligencia Artificial para TITAN POS
Predicciones de stock, detección de anomalías, y recomendaciones inteligentes
"""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class AlertPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class StockPrediction:
    """Predicción de agotamiento de stock."""
    product_id: int
    product_name: str
    current_stock: float
    avg_daily_sales: float
    days_until_stockout: int
    recommended_order: int
    urgency: AlertPriority
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "current_stock": self.current_stock,
            "avg_daily_sales": round(self.avg_daily_sales, 2),
            "days_until_stockout": self.days_until_stockout,
            "recommended_order": self.recommended_order,
            "urgency": self.urgency.value
        }

@dataclass
class SalesAnomaly:
    """Anomalía detectada en ventas."""
    detected_at: str
    anomaly_type: str
    description: str
    metric_value: float
    expected_value: float
    deviation_percent: float
    severity: AlertPriority
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "detected_at": self.detected_at,
            "type": self.anomaly_type,
            "description": self.description,
            "value": self.metric_value,
            "expected": self.expected_value,
            "deviation": round(self.deviation_percent, 1),
            "severity": self.severity.value
        }

class AIAnalytics:
    """
    Motor de análisis con IA para TITAN POS.
    Proporciona predicciones y detección de anomalías.
    """
    
    def __init__(self, core):
        self.core = core
        self.db = core.db
    
    # =========================================================================
    # PREDICCIÓN DE STOCK
    # =========================================================================
    
    def predict_stockouts(self, days_ahead: int = 7) -> List[StockPrediction]:
        """
        Predice qué productos se agotarán en los próximos días.
        
        Args:
            days_ahead: Días a futuro para predecir
            
        Returns:
            Lista de predicciones ordenadas por urgencia
        """
        predictions = []
        
        # Obtener productos con ventas recientes
        sql = """
            SELECT 
                p.id, p.name, p.stock, p.min_stock,
                COALESCE(SUM(si.qty), 0) as total_sold,
                COUNT(DISTINCT s.timestamp::date) as days_with_sales
            FROM products p
            LEFT JOIN sale_items si ON p.id = si.product_id
            LEFT JOIN sales s ON si.sale_id = s.id 
                AND s.timestamp >= CURRENT_DATE - INTERVAL '30 days'
                AND s.status = 'completed'
            WHERE p.stock >= 0 AND p.status = 'active'
            GROUP BY p.id
            HAVING total_sold > 0
        """
        
        try:
            products = list(self.db.execute_query(sql))
        except Exception as e:
            logger.error(f"Error getting products for prediction: {e}")
            return []
        
        for p in products:
            stock = float(p['stock'] or 0)
            total_sold = float(p['total_sold'] or 0)
            days_active = max(int(p['days_with_sales'] or 1), 1)
            
            # Calcular promedio diario de ventas
            avg_daily = total_sold / 30  # Promedio mensual
            
            if avg_daily <= 0:
                continue
            
            # Días hasta agotamiento
            days_until_out = int(stock / avg_daily) if avg_daily > 0 else 999
            
            # Solo reportar si se agotará pronto
            if days_until_out <= days_ahead or stock <= (p['min_stock'] or 5):
                urgency = self._calculate_urgency(days_until_out, stock)
                
                predictions.append(StockPrediction(
                    product_id=p['id'],
                    product_name=p['name'],
                    current_stock=stock,
                    avg_daily_sales=avg_daily,
                    days_until_stockout=max(0, days_until_out),
                    recommended_order=self._calculate_order_quantity(avg_daily, stock),
                    urgency=urgency
                ))
        
        # Ordenar por urgencia
        priority_order = {AlertPriority.CRITICAL: 0, AlertPriority.HIGH: 1, 
                         AlertPriority.MEDIUM: 2, AlertPriority.LOW: 3}
        predictions.sort(key=lambda x: (priority_order[x.urgency], x.days_until_stockout))
        
        return predictions[:20]  # Top 20
    
    def _calculate_urgency(self, days_until_out: int, current_stock: float) -> AlertPriority:
        """Calcula la urgencia basada en días y stock actual."""
        if days_until_out <= 1 or current_stock <= 2:
            return AlertPriority.CRITICAL
        elif days_until_out <= 3 or current_stock <= 5:
            return AlertPriority.HIGH
        elif days_until_out <= 7:
            return AlertPriority.MEDIUM
        else:
            return AlertPriority.LOW
    
    def _calculate_order_quantity(self, avg_daily: float, current_stock: float) -> int:
        """Calcula cantidad recomendada a ordenar (14 días de stock)."""
        target_stock = avg_daily * 14  # 2 semanas de inventario
        order_qty = max(0, target_stock - current_stock)
        return int(order_qty + 0.5)  # Redondear
    
    # =========================================================================
    # DETECCIÓN DE ANOMALÍAS
    # =========================================================================
    
    def detect_anomalies(self) -> List[SalesAnomaly]:
        """
        Detecta anomalías en las ventas del día actual.
        
        Returns:
            Lista de anomalías detectadas
        """
        anomalies = []
        
        # Comparar ventas de hoy vs promedio histórico
        today_anomaly = self._check_daily_sales_anomaly()
        if today_anomaly:
            anomalies.append(today_anomaly)
        
        # Detectar cancelaciones excesivas
        cancel_anomaly = self._check_cancellation_rate()
        if cancel_anomaly:
            anomalies.append(cancel_anomaly)
        
        # Detectar tickets pequeños inusuales
        ticket_anomaly = self._check_avg_ticket_anomaly()
        if ticket_anomaly:
            anomalies.append(ticket_anomaly)
        
        return anomalies
    
    def _check_daily_sales_anomaly(self) -> Optional[SalesAnomaly]:
        """Verifica si las ventas del día son anormales."""
        try:
            # Ventas de hoy
            today_sql = """
                SELECT COALESCE(SUM(total), 0) as total
                FROM sales 
                WHERE timestamp::date = CURRENT_DATE
                AND status = 'completed'
            """
            today_result = list(self.db.execute_query(today_sql))
            today_sales = float(today_result[0]['total']) if today_result else 0
            
            # Promedio de los últimos 30 días (mismos días de la semana)
            avg_sql = """
                SELECT AVG(daily_total) as avg_sales
                FROM (
                    SELECT timestamp::date as sale_date, COALESCE(SUM(total), 0) as daily_total
                    FROM sales
                    WHERE timestamp >= CURRENT_DATE - INTERVAL '30 days'
                    AND status = 'completed'
                    GROUP BY timestamp::date
                )
            """
            avg_result = list(self.db.execute_query(avg_sql))
            avg_sales = float(avg_result[0]['avg_sales'] or 0) if avg_result else 0
            
            if avg_sales <= 0:
                return None
            
            # Calcular desviación
            deviation = ((today_sales - avg_sales) / avg_sales) * 100
            
            # Solo alertar si la desviación es significativa
            if abs(deviation) > 40:  # Más del 40% de diferencia
                severity = AlertPriority.CRITICAL if abs(deviation) > 70 else AlertPriority.HIGH
                
                if deviation < 0:
                    desc = f"Ventas {abs(deviation):.0f}% por debajo del promedio"
                    anomaly_type = "low_sales"
                else:
                    desc = f"Ventas {deviation:.0f}% por encima del promedio"
                    anomaly_type = "high_sales"
                
                return SalesAnomaly(
                    detected_at=datetime.now().isoformat(),
                    anomaly_type=anomaly_type,
                    description=desc,
                    metric_value=today_sales,
                    expected_value=avg_sales,
                    deviation_percent=deviation,
                    severity=severity
                )
        except Exception as e:
            logger.error(f"Error checking daily sales anomaly: {e}")
        
        return None
    
    def _check_cancellation_rate(self) -> Optional[SalesAnomaly]:
        """Verifica si hay muchas cancelaciones hoy."""
        try:
            sql = """
                SELECT 
                    COALESCE(SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END), 0) as cancelled,
                    COUNT(*) as total
                FROM sales
                WHERE timestamp::date = CURRENT_DATE
            """
            result = list(self.db.execute_query(sql))
            
            if not result or result[0]['total'] < 5:
                return None
            
            cancelled = int(result[0]['cancelled'] or 0)
            total = int(result[0]['total'] or 1)
            rate = (cancelled / total) * 100
            
            # Alertar si más del 10% son cancelaciones
            if rate > 10:
                return SalesAnomaly(
                    detected_at=datetime.now().isoformat(),
                    anomaly_type="high_cancellations",
                    description=f"Tasa de cancelación alta: {rate:.0f}%",
                    metric_value=rate,
                    expected_value=3.0,  # Normal: 3%
                    deviation_percent=rate - 3.0,
                    severity=AlertPriority.HIGH if rate > 20 else AlertPriority.MEDIUM
                )
        except Exception as e:
            logger.error(f"Error checking cancellation rate: {e}")
        
        return None
    
    def _check_avg_ticket_anomaly(self) -> Optional[SalesAnomaly]:
        """Verifica si el ticket promedio es anormalmente bajo/alto."""
        try:
            # Ticket promedio hoy
            today_sql = """
                SELECT AVG(total) as avg_ticket
                FROM sales 
                WHERE timestamp::date = CURRENT_DATE
                AND status = 'completed'
            """
            today_result = list(self.db.execute_query(today_sql))
            today_avg = float(today_result[0]['avg_ticket'] or 0) if today_result else 0
            
            # Ticket promedio histórico
            hist_sql = """
                SELECT AVG(total) as avg_ticket
                FROM sales
                WHERE timestamp >= CURRENT_DATE - INTERVAL '30 days'
                AND status = 'completed'
            """
            hist_result = list(self.db.execute_query(hist_sql))
            hist_avg = float(hist_result[0]['avg_ticket'] or 0) if hist_result else 0
            
            if hist_avg <= 0 or today_avg <= 0:
                return None
            
            deviation = ((today_avg - hist_avg) / hist_avg) * 100
            
            if abs(deviation) > 30:
                if deviation < 0:
                    desc = f"Ticket promedio {abs(deviation):.0f}% menor"
                else:
                    desc = f"Ticket promedio {deviation:.0f}% mayor"
                
                return SalesAnomaly(
                    detected_at=datetime.now().isoformat(),
                    anomaly_type="ticket_anomaly",
                    description=desc,
                    metric_value=today_avg,
                    expected_value=hist_avg,
                    deviation_percent=deviation,
                    severity=AlertPriority.LOW
                )
        except Exception as e:
            logger.error(f"Error checking ticket anomaly: {e}")
        
        return None
    
    # =========================================================================
    # TOP PRODUCTOS INTELIGENTE
    # =========================================================================
    
    def get_smart_top_products(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene top productos con métricas avanzadas.
        
        Returns:
            Lista de productos con ventas, tendencia, y recomendaciones
        """
        sql = """
            SELECT 
                p.id, p.name, p.price, p.stock,
                COALESCE(SUM(CASE WHEN s.timestamp >= CURRENT_DATE - INTERVAL '7 days' 
                    THEN si.qty ELSE 0 END), 0) as weekly_sales,
                COALESCE(SUM(CASE WHEN s.timestamp >= CURRENT_DATE - INTERVAL '30 days' 
                    THEN si.qty ELSE 0 END), 0) as monthly_sales,
                COALESCE(SUM(CASE WHEN s.timestamp >= CURRENT_DATE - INTERVAL '7 days' 
                    THEN si.qty * si.price ELSE 0 END), 0) as weekly_revenue
            FROM products p
            LEFT JOIN sale_items si ON p.id = si.product_id
            LEFT JOIN sales s ON si.sale_id = s.id AND s.status = 'completed'
            WHERE p.status = 'active'
            GROUP BY p.id
            HAVING weekly_sales > 0
            ORDER BY weekly_revenue DESC
            LIMIT %s
        """
        
        try:
            products = list(self.db.execute_query(sql, (limit,)))
            
            result = []
            for p in products:
                weekly = float(p['weekly_sales'] or 0)
                monthly = float(p['monthly_sales'] or 0)
                
                # Calcular tendencia (comparar este semana vs promedio mensual semanal)
                weekly_avg = monthly / 4 if monthly > 0 else 0
                if weekly_avg > 0:
                    trend = ((weekly - weekly_avg) / weekly_avg) * 100
                else:
                    trend = 0
                
                result.append({
                    "id": p['id'],
                    "name": p['name'],
                    "price": float(p['price'] or 0),
                    "stock": float(p['stock'] or 0),
                    "weekly_sales": int(weekly),
                    "monthly_sales": int(monthly),
                    "weekly_revenue": float(p['weekly_revenue'] or 0),
                    "trend": round(trend, 1),
                    "trend_label": "🔺" if trend > 10 else ("🔻" if trend < -10 else "➖")
                })
            
            return result
        except Exception as e:
            logger.error(f"Error getting smart top products: {e}")
            return []
    
    # =========================================================================
    # DASHBOARD EJECUTIVO
    # =========================================================================
    
    def get_executive_dashboard(self) -> Dict[str, Any]:
        """
        Genera datos completos para el dashboard ejecutivo.
        
        Returns:
            Dict con métricas, alertas, predicciones, y gráficas
        """
        return {
            "generated_at": datetime.now().isoformat(),
            "kpis": self._get_kpis(),
            "hourly_sales": self._get_hourly_sales(),
            "comparison": self._get_day_comparison(),
            "stock_predictions": [p.to_dict() for p in self.predict_stockouts(7)[:5]],
            "anomalies": [a.to_dict() for a in self.detect_anomalies()],
            "top_products": self.get_smart_top_products(5)
        }
    
    def _get_kpis(self) -> Dict[str, Any]:
        """Obtiene KPIs principales del día."""
        try:
            sql = """
                SELECT 
                    COUNT(*) as transactions,
                    COALESCE(SUM(total), 0) as revenue,
                    COALESCE(AVG(total), 0) as avg_ticket,
                    MAX(total) as max_ticket
                FROM sales
                WHERE timestamp::date = CURRENT_DATE
                AND status = 'completed'
            """
            result = list(self.db.execute_query(sql))
            r = result[0] if result else {}
            
            return {
                "transactions": int(r.get('transactions', 0)),
                "revenue": float(r.get('revenue', 0)),
                "avg_ticket": float(r.get('avg_ticket', 0)),
                "max_ticket": float(r.get('max_ticket', 0))
            }
        except Exception:
            return {"transactions": 0, "revenue": 0, "avg_ticket": 0, "max_ticket": 0}
    
    def _get_hourly_sales(self) -> List[Dict[str, Any]]:
        """Obtiene ventas por hora del día actual."""
        try:
            sql = """
                SELECT 
                    EXTRACT(HOUR FROM timestamp::timestamp) as hour,
                    COUNT(*) as count,
                    COALESCE(SUM(total), 0) as total
                FROM sales
                WHERE timestamp::date = CURRENT_DATE
                AND status = 'completed'
                GROUP BY EXTRACT(HOUR FROM timestamp::timestamp)
                ORDER BY hour
            """
            results = list(self.db.execute_query(sql))
            
            # Llenar horas faltantes con ceros
            hourly = {str(i).zfill(2): {"count": 0, "total": 0} for i in range(24)}
            for r in results:
                h = r['hour']
                hourly[h] = {"count": int(r['count']), "total": float(r['total'])}
            
            return [{"hour": k, **v} for k, v in hourly.items()]
        except Exception:
            return []
    
    def _get_day_comparison(self) -> Dict[str, Any]:
        """Compara hoy vs ayer y vs mismo día semana pasada."""
        try:
            today_sql = """
                SELECT COALESCE(SUM(total), 0) as total
                FROM sales WHERE timestamp::date = CURRENT_DATE AND status = 'completed'
            """
            yesterday_sql = """
                SELECT COALESCE(SUM(total), 0) as total
                FROM sales WHERE timestamp::date = CURRENT_DATE - INTERVAL '1 day' AND status = 'completed'
            """
            last_week_sql = """
                SELECT COALESCE(SUM(total), 0) as total
                FROM sales WHERE timestamp::date = CURRENT_DATE - INTERVAL '7 days' AND status = 'completed'
            """
            
            today_result = list(self.db.execute_query(today_sql))
            yesterday_result = list(self.db.execute_query(yesterday_sql))
            last_week_result = list(self.db.execute_query(last_week_sql))
            
            today = float(today_result[0]['total']) if today_result else 0
            yesterday = float(yesterday_result[0]['total']) if yesterday_result else 0
            last_week = float(last_week_result[0]['total']) if last_week_result else 0
            
            return {
                "today": today,
                "yesterday": yesterday,
                "last_week": last_week,
                "vs_yesterday": round(((today - yesterday) / yesterday * 100) if yesterday > 0 else 0, 1),
                "vs_last_week": round(((today - last_week) / last_week * 100) if last_week > 0 else 0, 1)
            }
        except Exception:
            return {"today": 0, "yesterday": 0, "last_week": 0, "vs_yesterday": 0, "vs_last_week": 0}
