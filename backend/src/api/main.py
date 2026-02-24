from typing import List, Optional
import os
import sys

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# Importar núcleos
# from src.core.promo_engine import PromoEngine
# from src.ai.brain import AIBrain


# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.utils.paths import get_data_dir
from src.infra.database import db_instance

app = FastAPI(title="TITAN POS API", version="2.0.0")

def run_api(host="0.0.0.0", port=8000):
    uvicorn.run(app, host=host, port=port, log_level="info")

class Product(BaseModel):
    sku: str
    name: str
    price: float

class Sale(BaseModel):
    items: List[dict]
    total: float

@app.get("/")
def read_root():
    return {"status": "ONLINE", "system": "TITAN POS ULTIMATE"}

@app.get("/dashboard/stats")
def get_stats():
    """Endpoint para el Dashboard Web (React)."""
    sales_total = db_instance.execute_query("SELECT SUM(total) FROM sales")
    total_sales = sales_total[0][0] if sales_total and sales_total[0][0] else 0
    
    txn_count_result = db_instance.execute_query("SELECT COUNT(*) FROM sales")
    txn_count = txn_count_result[0][0] if txn_count_result else 0
    
    return {
        "total_sales": total_sales,
        "transactions": txn_count,
        "active_promos": 3 # Simulado
    }

@app.post("/sync/delta")
def sync_delta(data: dict):
    """Recibe cambios incrementales de sucursales."""
    # Lógica de Sync Delta
    return {"status": "SYNCED", "records_processed": len(data)}

@app.get("/ai/forecast/{sku}")
def get_forecast(sku: str):
    # brain = AIBrain(...)
    # return brain.forecast_demand(sku)
    return {"sku": sku, "predicted_demand": 42.5, "confidence": 0.89}
