from typing import List
import random


class AIBrain:
    def __init__(self, db_conn):
        self.db = db_conn

    def forecast_demand(self, sku: str) -> float:
        """
        Predice la demanda para la próxima semana basada en histórico.
        (Implementación simple de Media Móvil por ahora)
        """
        # Obtener ventas de las últimas 4 semanas
        # SQL Simulado
        sales_history = [random.randint(10, 50) for _ in range(4)] 
        
        avg_demand = sum(sales_history) / len(sales_history)
        
        # Factor estacional (ej. Viernes +20%)
        seasonal_factor = 1.2 
        
        return avg_demand * seasonal_factor

    def detect_fraud(self, cashier_id: int) -> dict:
        """
        Analiza patrones de comportamiento del cajero.
        """
        # Obtener métricas
        # void_count = self.db.execute(...)
        void_count = random.randint(0, 10) # Simulado
        avg_voids = 2.0
        
        risk_score = 0
        reasons = []
        
        if void_count > (avg_voids * 3):
            risk_score += 50
            reasons.append("Excessive Void Transactions")
            
        # Verificar ventas fuera de horario
        # ...
        
        return {
            "cashier_id": cashier_id,
            "risk_score": risk_score, # 0-100
            "status": "RED_FLAG" if risk_score > 40 else "GREEN",
            "reasons": reasons
        }
