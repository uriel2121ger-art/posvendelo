"""
WebSocket Server - Notificaciones en Tiempo Real para TITAN POS
Permite comunicación bidireccional entre POS y PWA/Dashboard
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================

logger = logging.getLogger(__name__)

# SECURITY: CORS origins from environment variable
_cors_env = os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
if not _cors_env or _cors_env == ['']:
    # Default seguro: solo localhost para desarrollo
    ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080"
    ]
else:
    ALLOWED_ORIGINS = [origin.strip() for origin in _cors_env if origin.strip()]

# Store de conexiones activas
class ConnectionManager:
    """Gestiona conexiones WebSocket activas."""
    
    def __init__(self):
        # Conexiones por tipo: {"pos": set(), "pwa": set(), "dashboard": set()}
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "pos": set(),
            "pwa": set(),
            "dashboard": set(),
            "all": set()
        }
        self.connection_info: Dict[WebSocket, Dict] = {}
    
    async def connect(self, websocket: WebSocket, client_type: str = "pwa", user_id: Optional[str] = None):
        """Acepta una nueva conexión WebSocket."""
        await websocket.accept()
        
        self.active_connections[client_type].add(websocket)
        self.active_connections["all"].add(websocket)
        
        self.connection_info[websocket] = {
            "type": client_type,
            "user_id": user_id,
            "connected_at": datetime.now().isoformat()
        }
        
        logger.info(f"🔌 Nueva conexión {client_type}: {len(self.active_connections[client_type])} activas")
        
        # Enviar mensaje de bienvenida
        await websocket.send_json({
            "type": "connected",
            "message": f"Conectado como {client_type}",
            "timestamp": datetime.now().isoformat()
        })
    
    def disconnect(self, websocket: WebSocket):
        """Elimina una conexión cerrada."""
        info = self.connection_info.get(websocket, {})
        client_type = info.get("type", "pwa")
        
        self.active_connections[client_type].discard(websocket)
        self.active_connections["all"].discard(websocket)
        self.connection_info.pop(websocket, None)
        
        logger.info(f"🔌 Conexión cerrada: {len(self.active_connections['all'])} restantes")
    
    async def broadcast(self, message: Dict[str, Any], target: str = "all"):
        """Envía mensaje a todas las conexiones de un tipo."""
        message["timestamp"] = datetime.now().isoformat()
        
        connections = self.active_connections.get(target, set())
        disconnected = set()
        
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        
        # Limpiar conexiones muertas
        for conn in disconnected:
            self.disconnect(conn)
    
    async def send_to_user(self, user_id: str, message: Dict[str, Any]):
        """Envía mensaje a un usuario específico."""
        message["timestamp"] = datetime.now().isoformat()
        
        for ws, info in self.connection_info.items():
            if info.get("user_id") == user_id:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.debug("WebSocket send_json: %s", e)
    
    def get_stats(self) -> Dict[str, int]:
        """Retorna estadísticas de conexiones."""
        return {
            "total": len(self.active_connections["all"]),
            "pos": len(self.active_connections["pos"]),
            "pwa": len(self.active_connections["pwa"]),
            "dashboard": len(self.active_connections["dashboard"])
        }

manager = ConnectionManager()

# ==============================================================================
# APP WEBSOCKET
# ==============================================================================

ws_app = FastAPI(title="TITAN POS WebSocket Server")

# SECURITY: Use environment-configured origins instead of wildcard
ws_app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # SECURITY: Whitelist from environment
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

@ws_app.websocket("/ws/{client_type}")
async def websocket_endpoint(websocket: WebSocket, client_type: str):
    """Endpoint principal de WebSocket."""
    user_id = websocket.query_params.get("user_id")
    
    await manager.connect(websocket, client_type, user_id)
    
    try:
        while True:
            # Recibir mensajes del cliente
            data = await websocket.receive_json()
            
            # Procesar comandos
            await handle_message(websocket, data, client_type)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

async def handle_message(websocket: WebSocket, data: Dict, client_type: str):
    """Procesa mensajes entrantes de clientes."""
    msg_type = data.get("type", "")
    
    if msg_type == "ping":
        await websocket.send_json({"type": "pong"})
    
    elif msg_type == "subscribe":
        # Suscribirse a eventos específicos
        events = data.get("events", [])
        logger.info(f"Cliente suscrito a: {events}")
        await websocket.send_json({"type": "subscribed", "events": events})
    
    elif msg_type == "command":
        # Reenviar comando al POS
        await manager.broadcast(data, target="pos")
        await websocket.send_json({"type": "command_sent", "command": data.get("action")})
    
    elif msg_type == "notification":
        # Reenviar notificación a PWAs
        await manager.broadcast(data, target="pwa")

# ==============================================================================
# FUNCIONES PARA EMITIR EVENTOS (llamar desde el POS)
# ==============================================================================

async def emit_sale_completed(sale_data: Dict):
    """Emite evento cuando se completa una venta."""
    await manager.broadcast({
        "type": "sale_completed",
        "data": {
            "id": sale_data.get("id"),
            "folio": sale_data.get("folio_visible"),
            "total": sale_data.get("total"),
            "payment_method": sale_data.get("payment_method"),
            "items_count": len(sale_data.get("items", []))
        }
    }, target="all")

async def emit_turn_event(event_type: str, turn_data: Dict):
    """Emite evento de turno (abrir/cerrar)."""
    await manager.broadcast({
        "type": f"turn_{event_type}",
        "data": turn_data
    }, target="all")

async def emit_stock_alert(product: Dict, alert_type: str = "low"):
    """Emite alerta de stock."""
    await manager.broadcast({
        "type": "stock_alert",
        "alert_type": alert_type,
        "data": {
            "product_id": product.get("id"),
            "product_name": product.get("name"),
            "current_stock": product.get("stock"),
            "min_stock": product.get("min_stock")
        }
    }, target="all")

async def emit_notification(title: str, message: str, priority: str = "normal"):
    """Emite notificación general."""
    await manager.broadcast({
        "type": "notification",
        "data": {
            "title": title,
            "message": message,
            "priority": priority
        }
    }, target="all")

# ==============================================================================
# HELPER SÍNCRONO (para llamar desde código PyQt)
# ==============================================================================

def sync_emit_sale(sale_data: Dict):
    """Versión síncrona para emitir venta desde PyQt."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(emit_sale_completed(sale_data))
        else:
            loop.run_until_complete(emit_sale_completed(sale_data))
    except Exception as e:
        logger.warning(f"Could not emit sale event: {e}")

def sync_emit_notification(title: str, message: str, priority: str = "normal"):
    """Versión síncrona para emitir notificación desde PyQt."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(emit_notification(title, message, priority))
        else:
            loop.run_until_complete(emit_notification(title, message, priority))
    except Exception as e:
        logger.warning(f"Could not emit notification: {e}")

# ==============================================================================
# STATS ENDPOINT
# ==============================================================================

@ws_app.get("/ws/stats")
async def get_ws_stats():
    """Retorna estadísticas de conexiones."""
    return manager.get_stats()

@ws_app.post("/broadcast")
async def http_broadcast(event: Dict[str, Any]):
    """
    Endpoint HTTP para recibir eventos del POS y reenviarlos via WebSocket.
    Esto permite que el POS (PyQt) envíe eventos sin necesidad de WebSocket client.
    """
    await manager.broadcast(event, target="all")
    return {"success": True, "sent_to": manager.get_stats()["total"]}

@ws_app.post("/broadcast/{target}")
async def http_broadcast_target(target: str, event: Dict[str, Any]):
    """Broadcast a un grupo específico (pos, pwa, dashboard)."""
    await manager.broadcast(event, target=target)
    return {"success": True, "target": target}

# ==============================================================================
# RUN
# ==============================================================================

# Para ejecutar:
# uvicorn app.api.websocket_server:ws_app --host 0.0.0.0 --port 8082

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(ws_app, host="0.0.0.0", port=8082)

