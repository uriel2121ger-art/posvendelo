"""
Generic sync endpoints generator for FastAPI server.

Automatically creates endpoints for all configured tables in sync_config.
Supports bidirectional sync (GET and POST) for all tables in BIDIRECTIONAL_SYNC_TABLES.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, date, time
from decimal import Decimal

logger = logging.getLogger(__name__)


def serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize a database row to JSON-compatible format.
    Converts datetime, date, time, and Decimal objects to strings.
    """
    result = {}
    for key, value in row.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, date):
            result[key] = value.isoformat()
        elif isinstance(value, time):
            result[key] = value.isoformat()
        elif isinstance(value, Decimal):
            result[key] = float(value)
        else:
            result[key] = value
    return result

def create_sync_endpoints(app, core, verify_token):
    """
    Create generic sync endpoints for all configured tables.
    
    Creates:
    - POST /api/v1/sync/{table_name} - Push data to server
    - GET /api/v1/sync/{table_name} - Pull data from server
    
    Args:
        app: FastAPI application instance
        core: POSCore instance
        verify_token: Dependency function for token verification
    """
    try:
        from app.utils.sync_config import BIDIRECTIONAL_SYNC_TABLES
        from fastapi import Depends, HTTPException, Path
        from fastapi.responses import JSONResponse
        from pydantic import BaseModel
        
        logger.info(f"Creating generic sync endpoints for {len(BIDIRECTIONAL_SYNC_TABLES)} bidirectional tables")
        
        # Modelo para datos de tabla genérica
        class TableDataRequest(BaseModel):
            data: List[Dict[str, Any]]
        
        # POST endpoint genérico: Cliente envía datos al servidor
        @app.post("/api/v1/sync/{table_name}")
        async def sync_table_push(
            table_name: str = Path(..., description="Nombre de la tabla a sincronizar"),
            request: TableDataRequest = None,
            authorized: bool = Depends(verify_token)
        ):
            """
            Receive data for a specific table from client and save to database.
            Supports all tables in BIDIRECTIONAL_SYNC_TABLES.
            """
            try:
                table_config = BIDIRECTIONAL_SYNC_TABLES.get(table_name)
                if not table_config:
                    raise HTTPException(status_code=404, detail=f"Table {table_name} not configured for bidirectional sync")
                
                from app.utils.sync_client import apply_table_data
                
                # Aplicar datos usando la función genérica
                apply_table_data(core, table_name, table_config, request.data)
                
                logger.info(f"📥 Received {len(request.data)} {table_name} records from client")
                
                return JSONResponse({
                    "success": True,
                    "table": table_name,
                    "received": len(request.data),
                    "timestamp": datetime.now().isoformat()
                })
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error syncing {table_name}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                raise HTTPException(status_code=500, detail=str(e))
        
        # GET endpoint genérico: Servidor envía datos al cliente
        @app.get("/api/v1/sync/{table_name}")
        async def sync_table_pull(
            table_name: str = Path(..., description="Nombre de la tabla a sincronizar"),
            authorized: bool = Depends(verify_token)
        ):
            """
            Send data for a specific table to client.
            Supports all tables in BIDIRECTIONAL_SYNC_TABLES.
            """
            try:
                table_config = BIDIRECTIONAL_SYNC_TABLES.get(table_name)
                if not table_config:
                    raise HTTPException(status_code=404, detail=f"Table {table_name} not configured for bidirectional sync")
                
                columns = table_config["columns"]
                id_column = table_config["id_column"]
                limit = table_config.get("limit", 50000)
                
                # Verificar si tiene columna synced
                try:
                    table_info = core.db.get_table_info(table_name)
                    has_synced = any(col[1] == "synced" for col in table_info)
                except Exception:
                    has_synced = False
                
                # SECURITY: table_name is validated against BIDIRECTIONAL_SYNC_TABLES whitelist (line 88-90)
                # LIMIT parameterized; techo 50000 alineado con http_server y sync_client (B.3)
                limit = max(1, min(int(limit), 50000))

                if has_synced and "synced" in columns:
                    query = f"SELECT {', '.join(columns)} FROM {table_name} WHERE (synced = 0 OR synced IS NULL) ORDER BY {id_column} DESC LIMIT %s"
                else:
                    query = f"SELECT {', '.join(columns)} FROM {table_name} ORDER BY {id_column} DESC LIMIT %s"

                rows = core.db.execute_query(query, (limit,))
                data = [serialize_row(dict(row)) for row in rows]
                
                logger.info(f"📤 Sending {len(data)} {table_name} records to client")
                
                return JSONResponse({
                    "success": True,
                    "table": table_name,
                    "data": data,
                    "count": len(data),
                    "timestamp": datetime.now().isoformat()
                })
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error fetching {table_name}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                raise HTTPException(status_code=500, detail=str(e))
        
        logger.info(f"✅ Created 2 generic sync endpoints (GET + POST) for {len(BIDIRECTIONAL_SYNC_TABLES)} bidirectional tables")
        
    except ImportError as e:
        logger.warning(f"Could not import sync_config: {e}")
    except Exception as e:
        logger.error(f"Error creating generic sync endpoints: {e}")
        import traceback
        logger.error(traceback.format_exc())
