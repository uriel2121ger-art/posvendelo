"""
HTTP server for TITAN POS multi-terminal (MultiCaja) synchronization.

This FastAPI server runs on the master terminal and provides endpoints
for client terminals to synchronize inventory, sales, and customer data.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, date, time as time_type
from decimal import Decimal
import json
import logging
from pathlib import Path
import time


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
        elif isinstance(value, time_type):
            result[key] = value.isoformat()
        elif isinstance(value, Decimal):
            result[key] = float(value)
        else:
            result[key] = value
    return result

try:
    from fastapi import Depends, FastAPI, Header, HTTPException, Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    # Define all FastAPI-related variables as None when FastAPI is not available
    FastAPI = None
    Depends = None
    Header = None
    HTTPException = None
    Request = None
    RequestValidationError = None
    JSONResponse = None
    BaseModel = None
    uvicorn = None

logger = logging.getLogger(__name__)

# Import centralized debug logger
from app.utils.debug_logger import log_debug, get_debug_log_path
from app.utils.path_utils import get_debug_log_path_str, get_debug_log_path, agent_log_enabled

# Pydantic models for request validation
if BaseModel:
    class SyncInventoryRequest(BaseModel):
        """Request model for inventory synchronization."""
        products: List[Dict[str, Any]] = []
        timestamp: Optional[str] = None
        terminal_id: Optional[str] = None
    
    class SyncSalesRequest(BaseModel):
        """Request model for sales synchronization."""
        sales: List[Dict[str, Any]] = []
        timestamp: Optional[str] = None
        terminal_id: Optional[str] = None
    
    class SyncCustomersRequest(BaseModel):
        """Request model for customer synchronization."""
        customers: List[Dict[str, Any]] = []
        timestamp: Optional[str] = None
        terminal_id: Optional[str] = None

    class SyncInventoryMovementsRequest(BaseModel):
        """Request model for inventory movements (Parte A Fase 2 - delta sync)."""
        movements: List[Dict[str, Any]] = []
        terminal_id: Optional[str] = None
    
    class StockCheckRequest(BaseModel):
        """Request model for real-time stock check."""
        items: List[Dict[str, Any]]  # List of {sku: str, qty: float}
        terminal_id: str
    
    class SyncBatch(BaseModel):
        """
        Request model for batch synchronization.
        Compatible with auto_sync.py format.
        """
        branch_id: int
        terminal_id: int
        timestamp: str
        sales: Optional[List[Dict[str, Any]]] = None
        inventory_changes: Optional[List[Dict[str, Any]]] = None
        customers: Optional[List[Dict[str, Any]]] = None

class POSHTTPServer:
    """
    FastAPI-based HTTP server for POS synchronization.
    
    Provides REST API endpoints for multi-terminal data sync.
    """
    
    def __init__(self, pos_core, api_token: str, host: str = "0.0.0.0", port: int = 8000):
        """
        Initialize HTTP server.
        
        Args:
            pos_core: POSCore instance for database access
            api_token: Authentication token for API access
            host: Server host (default: 0.0.0.0 for all interfaces)
            port: Server port (default: 8000)
        """
        if not FastAPI:
            raise ImportError("FastAPI not installed. Run: pip install fastapi uvicorn")
        
        self.core = pos_core
        self.api_token = api_token
        self.host = host
        self.port = port
        
        # Verify database access
        logger.warning(f"🔍 [DEBUG] Verificando acceso a base de datos...")
        logger.warning(f"🔍 [DEBUG] core type: {type(self.core)}")
        logger.warning(f"🔍 [DEBUG] core tiene 'db': {hasattr(self.core, 'db')}")
        
        if not hasattr(self.core, 'db'):
            logger.error("❌ [DEBUG] POSCore no tiene atributo 'db'")
            raise ValueError("POSCore does not have 'db' attribute")
        
        logger.warning(f"🔍 [DEBUG] core.db type: {type(self.core.db)}")
        logger.warning(f"🔍 [DEBUG] core.db tiene 'execute_transaction': {hasattr(self.core.db, 'execute_transaction')}")
        
        if not hasattr(self.core.db, 'execute_transaction'):
            logger.error(f"❌ [DEBUG] DatabaseManager missing execute_transaction method. Type: {type(self.core.db)}")
            available_methods = [m for m in dir(self.core.db) if not m.startswith('_')]
            logger.error(f"❌ [DEBUG] Available methods: {available_methods[:10]}...")  # Primeros 10
            raise ValueError("DatabaseManager does not have execute_transaction method")
        
        logger.warning(f"✅ [DEBUG] HTTP Server initialized with DatabaseManager: {type(self.core.db).__name__}")
        logger.warning(f"✅ [DEBUG] Database path: {getattr(self.core.db, 'db_path', 'unknown')}")
        
        logger.warning("🔍 [DEBUG] Creando instancia FastAPI...")
        self.app = FastAPI(
            title="TITAN POS API",
            description="Multi-terminal synchronization API",
            version="1.0.0"
        )
        logger.warning("✅ [DEBUG] FastAPI app creada")
        
        # Add exception handler for validation errors (422)
        logger.warning("🔍 [DEBUG] Configurando exception handlers...")
        if RequestValidationError:
            @self.app.exception_handler(RequestValidationError)
            async def validation_exception_handler(request: Request, exc: RequestValidationError):
                # Log validation error
                log_debug(
                    "http_server.py:validation_error",
                    "Validation error 422",
                    {
                        "path": str(request.url.path),
                        "errors": exc.errors(),
                        "body": str(exc.body)[:500] if hasattr(exc, 'body') else None
                    },
                    "M"
                )
                logger.error(f"Validation error on {request.url.path}: {exc.errors()}")
                return JSONResponse(
                    status_code=422,
                    content={"detail": exc.errors(), "body": str(exc.body)[:500]}
                )
        
        # Add middleware to log all requests
        @self.app.middleware("http")
        async def log_requests(request, call_next):
            import json
            import os
            import time
            debug_log_path = get_debug_log_path_str() or ""
            def log_debug(location, message, data, hypothesis_id):
                try:
                    if debug_log_path:
                        os.makedirs(os.path.dirname(debug_log_path), exist_ok=True)
                        log_entry = {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": hypothesis_id,
                            "location": location,
                            "message": message,
                            "data": data,
                            "timestamp": int(time.time() * 1000)
                        }
                        with open(debug_log_path, "a") as f:
                            f.write(json.dumps(log_entry) + "\n")
                            f.flush()
                except Exception as e:
                    logger.debug("Middleware debug log write failed: %s", e)
            
            # Log incoming request
            log_debug("http_server.py:middleware:request_received", "HTTP request received", {
                "method": request.method,
                "path": str(request.url.path),
                "client": request.client.host if request.client else None
            }, "H")
            
            try:
                response = await call_next(request)
                log_debug("http_server.py:middleware:request_completed", "HTTP request completed", {
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": response.status_code
                }, "H")
                return response
            except Exception as e:
                log_debug("http_server.py:middleware:request_error", "HTTP request error", {
                    "method": request.method,
                    "path": str(request.url.path),
                    "error": str(e),
                    "error_type": type(e).__name__
                }, "H")
                raise
        
        logger.warning("🔍 [DEBUG] Configurando rutas...")
        try:
            self._setup_routes()
            logger.warning("✅ [DEBUG] Rutas configuradas exitosamente")
        except Exception as e:
            logger.error(f"❌ [DEBUG] ERROR CRÍTICO al configurar rutas: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"❌ [DEBUG] Traceback completo:\n{traceback.format_exc()}")
            # NO re-raise: permitir que el servidor se cree aunque algunas rutas fallen
            # Solo loguear el error para diagnóstico
            logger.warning("⚠️ [DEBUG] Continuando con creación del servidor (algunas rutas pueden no estar disponibles)")
        
        # Log that routes are set up
        logger.info(f"✅ HTTP Server routes configured. Endpoints available:")
        logger.info(f"   POST /api/v1/sync/sales")
        logger.info(f"   POST /api/v1/sync/inventory")
        logger.info(f"   POST /api/v1/sync/customers")
        logger.info(f"   GET /api/v1/sync/sales")
        logger.info(f"   GET /api/v1/sync/inventory")
        logger.info(f"   GET /api/v1/sync/customers")
    
    def verify_token(self, authorization: Optional[str] = Header(None) if Header is not None else None) -> bool:
        """Verify API token from Authorization header."""
        if Header is None:
            # FastAPI not available, skip token verification
            return True
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing authorization header")
        
        try:
            scheme, token = authorization.split()
            if scheme.lower() != "bearer":
                raise HTTPException(status_code=401, detail="Invalid authentication scheme")
            
            if token != self.api_token:
                raise HTTPException(status_code=401, detail="Invalid token")
            
            return True
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    def _setup_routes(self):
        """Configure API routes."""
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint with detailed terminal status."""
            try:
                cfg = self.core.read_local_config() if hasattr(self.core, 'read_local_config') else {}

                # Get sales count for today
                today_sales = 0
                today_total = 0.0
                active_turn = None

                try:
                    if not self.core.db:
                        logger.warning("Database not available for health check")
                    else:
                        # Use DatabaseManager for consistent connection handling
                        rows = self.core.db.execute_query("""
                            SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total
                            FROM sales
                            WHERE CAST(created_at AS DATE) = CURRENT_DATE
                            AND status = 'completed'
                        """)
                        if rows:
                            today_sales = rows[0]['count'] or 0
                            today_total = rows[0]['total'] or 0.0

                        # Active turn
                        turns = self.core.db.execute_query("""
                            SELECT id, user_id, start_timestamp
                            FROM turns
                            WHERE status = 'open'
                            ORDER BY id DESC LIMIT 1
                        """)
                        if turns:
                            turn = turns[0]
                            active_turn = {"id": turn['id'], "user_id": turn['user_id'], "started": turn['start_timestamp']}
                except Exception as e:
                    logger.debug("Health check query failed: %s", e)
                
                return JSONResponse({
                    "status": "ok",
                    "timestamp": datetime.now().isoformat(),
                    "service": "TITAN POS",
                    "terminal_id": cfg.get("terminal_id", 0),
                    "terminal_name": cfg.get("terminal_name", "Unknown"),
                    "branch_id": cfg.get("branch_id", 0),
                    "branch_name": cfg.get("branch_name", "Unknown"),
                    "mode": cfg.get("db_mode", "standalone"),
                    "today": {
                        "sales_count": today_sales,
                        "total": round(today_total, 2)
                    },
                    "active_turn": active_turn,
                    "uptime_seconds": (datetime.now() - getattr(self, '_start_time', datetime.now())).total_seconds() if hasattr(self, '_start_time') else 0
                })
            except Exception as e:
                logger.error(f"Health check error: {e}")
                return JSONResponse({
                    "status": "ok",
                    "timestamp": datetime.now().isoformat(),
                    "service": "TITAN POS",
                    "error": str(e)
                })
        
        @self.app.get("/api/v1/info")
        async def get_info(authorized: bool = Depends(self.verify_token)):
            """Get server information."""
            cfg = self.core.read_local_config()
            return JSONResponse({
                "server_name": cfg.get("business_name", "TITAN POS"),
                "version": "1.0.0",
                "mode": "server",
                "timestamp": datetime.now().isoformat()
            })
        
        # Alias endpoints for compatibility
        @self.app.get("/api/health")
        async def health_check_alias():
            """Alias for /health endpoint - same implementation."""
            try:
                cfg = self.core.read_local_config() if hasattr(self.core, 'read_local_config') else {}

                # Get sales count for today
                today_sales = 0
                today_total = 0.0
                active_turn = None

                try:
                    if not self.core.db:
                        logger.warning("Database not available for health check")
                    else:
                        rows = self.core.db.execute_query("""
                            SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as total
                            FROM sales
                            WHERE CAST(created_at AS DATE) = CURRENT_DATE
                            AND status = 'completed'
                        """)
                        if rows:
                            today_sales = rows[0]['count'] or 0
                            today_total = rows[0]['total'] or 0.0

                        turns = self.core.db.execute_query("""
                            SELECT id, user_id, start_timestamp
                            FROM turns
                            WHERE status = 'open'
                            ORDER BY id DESC LIMIT 1
                        """)
                        if turns:
                            turn = turns[0]
                            active_turn = {"id": turn['id'], "user_id": turn['user_id'], "started": turn['start_timestamp']}
                except Exception as e:
                    logger.debug("Health check query failed: %s", e)
                
                return JSONResponse({
                    "status": "ok",
                    "timestamp": datetime.now().isoformat(),
                    "service": "TITAN POS",
                    "terminal_id": cfg.get("terminal_id", 0),
                    "terminal_name": cfg.get("terminal_name", "Unknown"),
                    "branch_id": cfg.get("branch_id", 0),
                    "branch_name": cfg.get("branch_name", "Unknown"),
                    "mode": cfg.get("db_mode", "standalone"),
                    "today": {
                        "sales_count": today_sales,
                        "total": round(today_total, 2)
                    },
                    "active_turn": active_turn,
                    "uptime_seconds": (datetime.now() - getattr(self, '_start_time', datetime.now())).total_seconds() if hasattr(self, '_start_time') else 0
                })
            except Exception as e:
                logger.error(f"Health check error: {e}")
                return JSONResponse({
                    "status": "ok",
                    "timestamp": datetime.now().isoformat(),
                    "service": "TITAN POS",
                    "error": str(e)
                })
        
        @self.app.get("/api/info")
        async def info_alias(authorized: bool = Depends(self.verify_token)):
            """Alias for /api/v1/info endpoint - same implementation."""
            cfg = self.core.read_local_config()
            return JSONResponse({
                "server_name": cfg.get("business_name", "TITAN POS"),
                "version": "1.0.0",
                "mode": "server",
                "timestamp": datetime.now().isoformat()
            })
        
        @self.app.get("/api/v1/auth/validate")
        async def validate_token(authorized: bool = Depends(self.verify_token)):
            """Validate authentication token."""
            return JSONResponse({
                "valid": True,
                "message": "Token is valid"
            })

        # ========== BATCH SYNC ENDPOINT (auto_sync.py compatible) ==========
        
        @self.app.post("/api/sync")
        async def sync_batch(
            batch: SyncBatch,
            authorized: bool = Depends(self.verify_token)
        ):
            """
            Receive batch sync data from auto_sync.py.
            
            This endpoint is compatible with the format sent by auto_sync.py:
            - sales: List of sales with items
            - customers: List of customers
            - inventory_changes: List of inventory updates
            """
            if not self.core.db:
                logger.warning("Database not available for batch sync")
                raise HTTPException(status_code=503, detail="Database not available")

            try:
                result = {
                    "success": True,
                    "sales_received": 0,
                    "customers_received": 0,
                    "inventory_received": 0,
                    "errors": []
                }
                
                # Use DatabaseManager's transaction method to handle locks properly
                operations = []
                
                # Process sales
                if batch.sales:
                    for sale in batch.sales:
                        try:
                            sale_id = sale.get('id')
                            if not sale_id:
                                continue
                            
                            # Check if sale already exists (prevent duplicates by ID or UUID)
                            sale_uuid = sale.get('uuid')
                            existing = None
                            
                            # First check by ID (PostgreSQL uses %s)
                            existing = self.core.db.execute_query(
                                "SELECT id, uuid FROM sales WHERE id = %s", 
                                (sale_id,)
                            )
                            
                            # If not found by ID, check by UUID (if provided)
                            if not existing and sale_uuid:
                                existing = self.core.db.execute_query(
                                    "SELECT id, uuid FROM sales WHERE uuid = %s", 
                                    (sale_uuid,)
                                )
                            
                            if existing:
                                continue  # Skip duplicates
                            
                            # Prepare insert sale operation - Match exact schema_postgresql.sql structure
                            # Include UUID, serie, and folio for proper tracking
                            # Obtener origin_pc desde la venta sincronizada o usar terminal_id
                            origin_pc = sale.get('origin_pc') or str(batch.terminal_id or "unknown")
                            
                            operations.append((
                                """INSERT INTO sales (
                                    id, uuid, timestamp, subtotal, tax, total, discount, payment_method, 
                                    customer_id, user_id, cashier_id, turn_id, serie, folio, folio_visible, branch_id,
                                    synced, synced_from_terminal, status, origin_pc
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s, 'completed', %s)""",
                                (
                                    sale_id,
                                    sale_uuid,  # UUID for uniqueness
                                    sale.get('timestamp'),
                                    sale.get('subtotal', sale.get('total', 0.0) * 0.84),  # Calculate if not provided
                                    sale.get('tax', sale.get('total', 0.0) * 0.16),  # Calculate if not provided
                                    sale.get('total', 0.0),
                                    sale.get('discount', 0.0),
                                    sale.get('payment_method', 'cash'),
                                    sale.get('customer_id'),
                                    sale.get('user_id'),
                                    sale.get('cashier_id') or sale.get('user_id'),
                                    None,  # FIX: turn_id = NULL para ventas de otras PCs (turnos son locales)
                                    sale.get('serie', 'B'),  # Default to serie B if not provided
                                    sale.get('folio'),
                                    sale.get('folio_visible') or sale.get('folio'),
                                    batch.branch_id or 1,
                                    str(batch.terminal_id),
                                    origin_pc
                                )
                            ))
                            
                            # Prepare insert sale items operations
                            items = sale.get('items', [])
                            for item in items:
                                item_subtotal = item.get('subtotal', 0)
                                item_discount = item.get('discount', 0)
                                item_total = item.get('total', item_subtotal - item_discount)
                                operations.append((
                                    """INSERT INTO sale_items (
                                        sale_id, product_id, qty, price, subtotal, discount, total, name, synced
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)""",
                                    (
                                        sale_id,
                                        item.get('product_id'),
                                        item.get('quantity', item.get('qty', 1)),
                                        item.get('unit_price', item.get('price', 0)),
                                        item_subtotal,
                                        item_discount,
                                        item_total,
                                        item.get('name', '')
                                    )
                                ))
                            
                            result["sales_received"] += 1
                            
                        except Exception as e:
                            result["errors"].append(f"Sale {sale.get('id')}: {str(e)}")
                
                # Process customers
                if batch.customers:
                    for customer in batch.customers:
                        try:
                            customer_id = customer.get('id')
                            if not customer_id:
                                continue
                            
                            # Combine first_name + last_name if sent separately
                            name = customer.get('name')
                            if not name:
                                first_name = customer.get('first_name', '')
                                last_name = customer.get('last_name', '')
                                name = f"{first_name} {last_name}".strip()
                            
                            # Check if customer exists (PostgreSQL uses %s)
                            existing = self.core.db.execute_query(
                                "SELECT id FROM customers WHERE id = %s", 
                                (customer_id,)
                            )
                            if existing:
                                # Update existing customer
                                operations.append((
                                    """UPDATE customers SET
                                        name = COALESCE(%s, name),
                                        phone = COALESCE(%s, phone),
                                        email = COALESCE(%s, email),
                                        rfc = COALESCE(%s, rfc),
                                        synced = 0,
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE id = %s""",
                                    (
                                        name if name else None,
                                        customer.get('phone'),
                                        customer.get('email'),
                                        customer.get('rfc'),
                                        customer_id
                                    )
                                ))
                            else:
                                # Insert new customer - Match schema_postgresql.sql structure
                                operations.append((
                                    """INSERT INTO customers (
                                        id, name, phone, email, rfc, synced, is_active
                                    ) VALUES (%s, %s, %s, %s, %s, 0, 1)""",
                                    (
                                        customer_id,
                                        name or 'Cliente',
                                        customer.get('phone'),
                                        customer.get('email'),
                                        customer.get('rfc')
                                    )
                                ))
                            
                            result["customers_received"] += 1
                            
                        except Exception as e:
                            result["errors"].append(f"Customer {customer.get('id')}: {str(e)}")
                
                # Process inventory changes
                if batch.inventory_changes:
                    # #region agent log
                    if agent_log_enabled():
                        import json, time
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"http_server.py:sync_batch","message":"Processing inventory changes","data":{"changes_count":len(batch.inventory_changes),"changes":batch.inventory_changes[:3]},"timestamp":int(time.time()*1000)})+"\n")
                    # #endregion
                    for change in batch.inventory_changes:
                        try:
                            sku = change.get('sku')
                            product_id = change.get('product_id')
                            
                            if not sku and not product_id:
                                continue
                            
                            # Update product stock
                            if sku:
                                # #region agent log
                                if agent_log_enabled():
                                    with open(get_debug_log_path_str(), "a") as f:
                                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"http_server.py:sync_batch","message":"Adding inventory sync operation","data":{"sku":sku,"stock":change.get('stock'),"price":change.get('price')},"timestamp":int(time.time()*1000)})+"\n")
                                # #endregion
                                operations.append((
                                    """UPDATE products SET
                                        stock = COALESCE(%s, stock),
                                        price = COALESCE(%s, price),
                                        updated_at = CURRENT_TIMESTAMP,
                                        synced = 0
                                    WHERE sku = %s""",
                                    (
                                        change.get('stock'),
                                        change.get('price'),
                                        sku
                                    )
                                ))
                            elif product_id:
                                operations.append((
                                    """UPDATE products SET
                                        stock = COALESCE(%s, stock),
                                        price = COALESCE(%s, price),
                                        updated_at = CURRENT_TIMESTAMP,
                                        synced = 0
                                    WHERE id = %s""",
                                    (
                                        change.get('stock'),
                                        change.get('price'),
                                        product_id
                                    )
                                ))
                            
                            result["inventory_received"] += 1
                            
                        except Exception as e:
                            result["errors"].append(f"Inventory {change.get('sku')}: {str(e)}")
                
                # Execute all operations in a single transaction with retry logic
                if operations:
                    log_debug("http_server.py:379", "Executing batch sync transaction", {
                        "operations_count": len(operations),
                        "sales_count": result["sales_received"],
                        "customers_count": result["customers_received"],
                        "inventory_count": result["inventory_received"]
                    }, "E")
                    try:
                        result = self.core.db.execute_transaction(operations)
                        if result is None:
                            raise Exception("Transaction returned None - database error")
                        success = result.get('success') if isinstance(result, dict) else result
                        log_debug("http_server.py:385", "Batch sync transaction result", {
                            "success": success,
                            "operations_count": len(operations)
                        }, "E")
                        if not success:
                            log_debug("http_server.py:387", "Batch sync transaction returned False", {}, "E")
                            raise Exception("Batch sync transaction failed to commit (returned False)")
                    except Exception as tx_error:
                        log_debug("http_server.py:390", "Batch sync transaction exception", {
                            "error": str(tx_error),
                            "error_type": type(tx_error).__name__,
                            "operations_count": len(operations)
                        }, "E")
                        raise
                
                logger.info(f"✅ Batch sync: {result['sales_received']} sales, "
                           f"{result['customers_received']} customers, "
                           f"{result['inventory_received']} inventory from terminal {batch.terminal_id}")
                
                return JSONResponse(result)
                
            except Exception as e:
                logger.error(f"❌ Batch sync error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/sync/products")
        async def sync_products_download(
            since: Optional[str] = None,
            authorized: bool = Depends(self.verify_token)
        ):
            """
            Download product updates for auto_sync.py.
            """
            if not self.core.db:
                logger.warning("Database not available for products download")
                raise HTTPException(status_code=503, detail="Database not available")

            try:
                # Use DatabaseManager for consistent connection handling
                if since:
                    rows = self.core.db.execute_query("""
                        SELECT id, sku, name, price, cost, stock, category,
                               is_active, updated_at
                        FROM products
                        WHERE updated_at > %s
                        ORDER BY updated_at DESC
                        LIMIT 50000
                    """, (since,))
                else:
                    rows = self.core.db.execute_query("""
                        SELECT id, sku, name, price, cost, stock, category,
                               is_active, updated_at
                        FROM products
                        WHERE is_active = 1
                        ORDER BY id DESC
                        LIMIT 50000
                    """)
                
                products = [serialize_row(dict(row)) for row in rows]

                logger.info(f"📤 Products download: {len(products)} products")
                
                return JSONResponse({
                    "success": True,
                    "products": products,
                    "count": len(products),
                    "timestamp": datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Products download error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # ========== POST ENDPOINTS (Clients send data to server) ==========
        
        @self.app.post("/api/v1/sync/inventory")
        async def sync_inventory_push(
            request: SyncInventoryRequest,
            authorized: bool = Depends(self.verify_token)
        ):
            """
            Receive inventory data from client terminal and save to database.

            Implements conflict resolution using timestamps.
            """
            if not self.core.db:
                logger.warning("Database not available for inventory sync")
                raise HTTPException(status_code=503, detail="Database not available")

            try:
                terminal_id = request.terminal_id or "unknown"
                logger.info(f"📦 Inventory sync from {terminal_id}: {len(request.products)} products")
                
                updated_count = 0
                created_count = 0
                skipped_count = 0
                conflicts = []
                accepted_ids = []  # B.5: IDs que el cliente puede marcar como synced
                
                log_debug("http_server.py:479", "Starting inventory save process", {
                    "products_count": len(request.products),
                    "has_db_lock": hasattr(self.core, 'db_lock')
                }, "E")
                
                try:
                    # Use DatabaseManager's transaction method to handle locks properly
                    operations = []
                    
                    for idx, product in enumerate(request.products):
                        try:
                            product_id = product.get('id')
                            sku = product.get('sku')
                            
                            # CRITICAL VALIDATION: Required fields before processing
                            if not sku:
                                conflicts.append({
                                    "sku": None,
                                    "error": f"Product {idx}: Missing required field 'sku'"
                                })
                                skipped_count += 1
                                logger.warning(f"Product {idx} rejected: Missing 'sku'")
                                continue
                            
                            # Validate price if provided
                            price = product.get('price', 0.0)
                            try:
                                price = float(price)
                                if price < 0:
                                    conflicts.append({
                                        "sku": sku,
                                        "error": f"Invalid price (negative): {price}"
                                    })
                                    skipped_count += 1
                                    logger.warning(f"Product {sku} rejected: Negative price")
                                    continue
                            except (TypeError, ValueError):
                                conflicts.append({
                                    "sku": sku,
                                    "error": f"Invalid price (not a number): {price}"
                                })
                                skipped_count += 1
                                logger.warning(f"Product {sku} rejected: Invalid price")
                                continue
                            
                            # Check if product exists (PostgreSQL uses %s)
                            existing = self.core.db.execute_query(
                                "SELECT id, updated_at FROM products WHERE sku = %s", 
                                (sku,)
                            )
                            
                            if existing:
                                # Parte A Fase 3: NO actualizar stock en PUSH de productos; solo metadata (stock solo vía movimientos)
                                from app.utils.sync_helpers import prepare_sync_update_by_sku
                                sync_updates = {
                                    "name": product.get('name'),
                                    "price": product.get('price'),
                                    "category": product.get('category'),
                                    "provider": product.get('provider'),
                                    "is_favorite": product.get('is_favorite', 0),
                                    "sale_type": product.get('sale_type', 'unit'),
                                    "min_stock": product.get('min_stock'),
                                    "max_stock": product.get('max_stock'),
                                    "synced": 0
                                }
                                query, values = prepare_sync_update_by_sku(
                                    self.core, "products", sku, sync_updates
                                )
                                operations.append((query, values))
                                if product_id is not None:
                                    accepted_ids.append(product_id)
                                updated_count += 1
                            else:
                                # Create new product
                                operations.append((
                                    """INSERT INTO products (
                                        sku, name, price, stock, category, provider,
                                        is_favorite, sale_type, min_stock, max_stock, synced
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)""",
                                    (
                                        sku,
                                        product.get('name'),
                                        product.get('price'),
                                        product.get('stock', 0),
                                        product.get('category'),
                                        product.get('provider'),
                                        product.get('is_favorite', 0),
                                        product.get('sale_type', 'unit'),
                                        product.get('min_stock'),
                                        product.get('max_stock')
                                    )
                                ))
                                if product_id is not None:
                                    accepted_ids.append(product_id)
                                created_count += 1
                                
                        except Exception as e:
                            logger.error(f"Error syncing product {product.get('sku')}: {e}")
                            conflicts.append({
                                "sku": product.get('sku'),
                                "error": str(e)
                            })
                            skipped_count += 1
                    
                    # Execute all operations in a single transaction with retry logic
                    if operations:
                        log_debug("http_server.py:551", "Executing inventory transaction", {
                            "operations_count": len(operations),
                            "updated_count": updated_count,
                            "created_count": created_count,
                            "first_operation": operations[0][0][:100] if operations else None
                        }, "E")
                        try:
                            result = self.core.db.execute_transaction(operations)
                            if result is None:
                                raise Exception("Transaction returned None - database error")
                            success = result.get('success') if isinstance(result, dict) else result
                            log_debug("http_server.py:553", "Inventory transaction result", {
                                "success": success,
                                "operations_count": len(operations)
                            }, "E")
                            if success:
                                log_debug("http_server.py:555", "Inventory transaction committed successfully", {}, "E")
                            else:
                                log_debug("http_server.py:557", "Inventory transaction returned False", {
                                    "operations_count": len(operations)
                                }, "E")
                                raise Exception("Inventory transaction failed to commit (returned False)")
                        except Exception as tx_error:
                            log_debug("http_server.py:562", "Inventory transaction exception", {
                                "error": str(tx_error),
                                "error_type": type(tx_error).__name__,
                                "operations_count": len(operations)
                            }, "E")
                            raise
                        
                except Exception as e:
                    log_debug("http_server.py:557", "Critical error in inventory save", {
                        "error": str(e),
                        "error_type": type(e).__name__
                    }, "E")
                    logger.error(f"Critical error saving inventory: {e}")
                    raise
                
                logger.info(f"✅ Inventory sync complete: {updated_count} updated, {created_count} created, {skipped_count} skipped")
                
                return JSONResponse({
                    "success": True,
                    "updated": updated_count,
                    "created": created_count,
                    "skipped": skipped_count,
                    "conflicts": conflicts,
                    "accepted_ids": accepted_ids,
                    "timestamp": datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"❌ Inventory sync error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/v1/sync/sales")
        async def sync_sales_push(
            request: SyncSalesRequest,
            authorized: bool = Depends(self.verify_token)
        ):
            """
            Receive sales data from client terminal and save to database.
            
            Prevents duplicate sales using unique constraints.
            """
            # #region agent log
            if agent_log_enabled():
                import json
                import os
                import time
                try:
                    with open(str(get_debug_log_path()), "a") as f:
                        f.write(json.dumps({"sessionId": "debug-session", "runId": "post-fix", "hypothesisId": "M", "location": "http_server.py:755", "message": "sync_sales_push called", "data": {"sales_count": len(request.sales) if request.sales else 0, "has_timestamp": bool(request.timestamp), "has_terminal_id": bool(request.terminal_id)}, "timestamp": int(time.time() * 1000)}) + "\n")
                except Exception as e:
                    logger.debug("Debug log write failed for sync_sales_push: %s", e)
            # #endregion
            if not self.core.db:
                logger.warning("Database not available for sales sync")
                raise HTTPException(status_code=503, detail="Database not available")

            try:
                terminal_id = request.terminal_id or "unknown"
                logger.info(f"💰 Sales sync from {terminal_id}: {len(request.sales)} sales")
                
                saved_count = 0
                duplicate_count = 0
                error_count = 0
                errors = []
                accepted_sale_ids = []  # B.5: IDs que el cliente puede marcar como synced
                
                log_debug("http_server.py:607", "Starting sales save process", {
                    "sales_count": len(request.sales),
                    "has_db_lock": hasattr(self.core, 'db_lock')
                }, "E")
                
                try:
                    # Use DatabaseManager's transaction method to handle locks properly
                    operations = []
                    
                    for idx, sale in enumerate(request.sales):
                        use_uuid_insert = False  # Reset each iteration; set True only on ID collision
                        try:
                            # CRITICAL VALIDATION: Required fields before processing

                            sale_id = sale.get('id')
                            if not sale_id:
                                error_count += 1
                                error_msg = f"Sale {idx}: Missing required field 'id'"
                                errors.append(error_msg)
                                logger.warning(f"Sale {idx} rejected: Missing 'id'")
                                
                                continue
                            
                            # Validate timestamp - accept empty string as invalid but log it
                            timestamp = sale.get('timestamp')
                            if not timestamp or (isinstance(timestamp, str) and timestamp.strip() == ''):
                                error_count += 1
                                error_msg = f"Sale {sale_id}: Missing required field 'timestamp'"
                                errors.append(error_msg)
                                logger.warning(f"Sale {sale_id} rejected: Missing 'timestamp' (value: {repr(timestamp)})")
                                
                                continue
                            
                            # Validate total - handle None, empty string, and various numeric types
                            total_raw = sale.get('total', 0.0)

                            try:
                                # Handle None, empty string, or already numeric
                                if total_raw is None:
                                    total = 0.0
                                elif isinstance(total_raw, str):
                                    if total_raw.strip() == '':
                                        total = 0.0
                                    else:
                                        total = float(total_raw)
                                else:
                                    total = float(total_raw)
                                
                                if total < 0:
                                    error_count += 1
                                    error_msg = f"Sale {sale_id}: Invalid total (negative): {total}"
                                    errors.append(error_msg)
                                    logger.warning(f"Sale {sale_id} rejected: Negative total: {total}")
                                    
                                    continue
                            except (TypeError, ValueError) as e:
                                error_count += 1
                                error_msg = f"Sale {sale_id}: Invalid total (not a number): {repr(total_raw)}"
                                errors.append(error_msg)
                                logger.warning(f"Sale {sale_id} rejected: Invalid total {repr(total_raw)} - {e}")
                                
                                continue

                            log_debug(f"http_server.py:616_{idx}", "Processing sale", {
                                "sale_id": sale_id,
                                "total": total,
                                "timestamp": timestamp
                            }, "E")
                            
                            # Check if sale already exists (prevent duplicates by UUID first, then ID)
                            # UUID is more reliable for offline sync since IDs can collide across terminals
                            sale_uuid = sale.get('uuid')
                            existing = None
                            existing_by_id = None
                            existing_by_uuid = None
                            
                            # CRITICAL: Check by UUID FIRST (more reliable for offline sync)
                            if sale_uuid:
                                existing_by_uuid = self.core.db.execute_query(
                                    "SELECT id, uuid FROM sales WHERE uuid = %s", 
                                    (sale_uuid,)
                                )
                            
                            # If found by UUID, it's definitely a duplicate
                            if existing_by_uuid:
                                existing = existing_by_uuid
                            else:
                                # If not found by UUID, check by ID (may have collisions)
                                existing_by_id = self.core.db.execute_query(
                                    "SELECT id, uuid FROM sales WHERE id = %s", 
                                    (sale_id,)
                                )
                                
                                # If found by ID, verify UUID matches (prevent false duplicates)
                                if existing_by_id:
                                    existing_id_data = dict(existing_by_id[0]) if existing_by_id else {}
                                    existing_uuid = existing_id_data.get('uuid')
                                    
                                    # If UUIDs match, it's a duplicate
                                    if existing_uuid == sale_uuid:
                                        existing = existing_by_id
                                    # If UUIDs differ, it's an ID collision - use UUID-based insert
                                    # We'll use INSERT with UUID and let server assign new ID
                                    # Then use UUID to find the new ID for sale_items
                                    elif sale_uuid:
                                        # ID collision but different UUID = new sale
                                        # Mark that we need to use UUID-based insert
                                        use_uuid_insert = True
                                        existing = None
                                    else:
                                        # No UUID provided, treat as duplicate if ID matches
                                        existing = existing_by_id
                            
                            if existing:
                                log_debug(f"http_server.py:624_{idx}", "Sale already exists, checking items", {
                                    "sale_id": sale_id,
                                    "uuid": sale_uuid,
                                    "found_by": "uuid" if existing_by_uuid else "id",
                                    "has_items": bool(sale.get('items'))
                                }, "E")
                                
                                # CRÍTICO: Aunque la venta sea duplicada, debemos actualizar los items
                                # porque pueden haber cambiado o no existir aún
                                # Buscar items con múltiples nombres posibles
                                items = sale.get('items', []) or sale.get('sale_items', []) or sale.get('items_list', [])
                                if items:
                                    # E8: Acceso por nombre de columna (backend devuelve dict-like)
                                    r0 = existing[0] if existing else None
                                    existing_sale_id = (r0.get('id') if r0 and hasattr(r0, 'get') else (r0[0] if r0 else None)) or sale_id
                                    logger.info(f"🔄 Updating {len(items)} items for existing sale {existing_sale_id}")
                                    
                                    # Borrar items existentes y reinsertar (más seguro)
                                    operations.append((
                                        "DELETE FROM sale_items WHERE sale_id = %s",
                                        (existing_sale_id,)
                                    ))
                                    
                                    # E9: INSERT sin ON CONFLICT (sale_items no tiene UNIQUE(sale_id, product_id) en esquema)
                                    for item in items:
                                        item_subtotal = item.get('subtotal', 0)
                                        item_discount = item.get('discount', 0)
                                        item_total = item.get('total', item_subtotal - item_discount)
                                        operations.append((
                                            """INSERT INTO sale_items (
                                                sale_id, product_id, qty, price, subtotal, discount, total, name, synced
                                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)""",
                                            (
                                                existing_sale_id,
                                                item.get('product_id'),
                                                item.get('quantity', item.get('qty', 1)),
                                                item.get('unit_price', item.get('price', 0)),
                                                item_subtotal,
                                                item_discount,
                                                item_total,
                                                item.get('name', '')
                                            )
                                        ))
                                    logger.info(f"✅ Prepared {len(items)} item operations for existing sale {existing_sale_id}")
                                
                                duplicate_count += 1
                                continue
                            
                            # Prepare insert operation - Match exact schema_postgresql.sql structure
                            # Include UUID, serie, and folio for proper tracking and atomicity
                            # All required fields already validated above
                            
                            # If ID collision detected, use INSERT without ID (AUTOINCREMENT)
                            # We'll use UUID to find the new ID after insert for sale_items
                            # Obtener origin_pc desde la venta sincronizada o usar terminal_id
                            origin_pc = sale.get('origin_pc') or str(request.terminal_id or "unknown")
                            
                            if use_uuid_insert:
                                insert_sql = """INSERT INTO sales (
                                    uuid, timestamp, subtotal, tax, total, discount, payment_method, 
                                    customer_id, user_id, cashier_id, turn_id, serie, folio, folio_visible, branch_id,
                                    synced, synced_from_terminal, status, origin_pc
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s, 'completed', %s)"""
                                insert_params = (
                                    sale_uuid,  # UUID for uniqueness
                                    timestamp,  # Validated: not None
                                    sale.get('subtotal', total * 0.84),  # Calculate if not provided
                                    sale.get('tax', total * 0.16),  # Calculate if not provided
                                    total,  # Validated: float >= 0
                                    sale.get('discount', 0.0),
                                    sale.get('payment_method', 'cash'),
                                    sale.get('customer_id'),
                                    sale.get('user_id'),
                                    sale.get('cashier_id') or sale.get('user_id'),
                                    None,  # FIX: turn_id = NULL para ventas de otras PCs (turnos son locales)
                                    sale.get('serie', 'B'),  # Default to serie B if not provided
                                    sale.get('folio'),
                                    sale.get('folio_visible') or sale.get('folio'),
                                    sale.get('branch_id', 1),
                                    str(request.terminal_id or "unknown"),
                                    origin_pc
                                )
                            else:
                                insert_sql = """INSERT INTO sales (
                                    id, uuid, timestamp, subtotal, tax, total, discount, payment_method,
                                    customer_id, user_id, cashier_id, turn_id, serie, folio, folio_visible, branch_id,
                                    synced, synced_from_terminal, status, origin_pc
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s, 'completed', %s)"""
                                insert_params = (
                                    sale_id,  # Validated: not None
                                    sale_uuid,  # UUID for uniqueness (can be None)
                                    timestamp,  # Validated: not None
                                    sale.get('subtotal', total * 0.84),  # Calculate if not provided
                                    sale.get('tax', total * 0.16),  # Calculate if not provided
                                    total,  # Validated: float >= 0
                                    sale.get('discount', 0.0),
                                    sale.get('payment_method', 'cash'),
                                    sale.get('customer_id'),
                                    sale.get('user_id'),
                                    sale.get('cashier_id') or sale.get('user_id'),
                                    None,  # FIX: turn_id = NULL para ventas de otras PCs (turnos son locales)
                                    sale.get('serie', 'B'),  # Default to serie B if not provided
                                    sale.get('folio'),
                                    sale.get('folio_visible') or sale.get('folio'),
                                    sale.get('branch_id', 1),
                                    str(request.terminal_id or "unknown"),
                                    origin_pc
                                )
                            
                            operations.append((insert_sql, insert_params))
                            accepted_sale_ids.append(sale_id)
                            
                            # Prepare insert sale items operations (atomic with sale)
                            # If we used UUID-based insert, we need to use a subquery to find the ID
                            # CRÍTICO: Verificar múltiples nombres posibles para items
                            items = sale.get('items', []) or sale.get('sale_items', []) or sale.get('items_list', [])
                            
                            # Log items for debugging
                            if items:
                                logger.info(f"📦 Sale {sale_id} has {len(items)} items to sync")
                                # Log first item structure for debugging
                                if items and len(items) > 0:
                                    first_item = items[0]
                                    logger.debug(f"📋 First item structure: {list(first_item.keys()) if isinstance(first_item, dict) else 'not a dict'}")
                            else:
                                logger.warning(f"⚠️ Sale {sale_id} has NO items (checked: items, sale_items, items_list) - this may be an error")
                            
                            if use_uuid_insert and sale_uuid:
                                # Use UUID to find the sale_id after insert
                                for item in items:
                                    item_subtotal = item.get('subtotal', 0)
                                    item_discount = item.get('discount', 0)
                                    item_total = item.get('total', item_subtotal - item_discount)
                                    operations.append((
                                        """INSERT INTO sale_items (
                                            sale_id, product_id, qty, price, subtotal, discount, total, name, synced
                                        ) VALUES (
                                            (SELECT id FROM sales WHERE uuid = %s),
                                            %s, %s, %s, %s, %s, %s, %s, 1
                                        )""",
                                        (
                                            sale_uuid,  # Use UUID to find the sale_id
                                            item.get('product_id'),
                                            item.get('quantity', item.get('qty', 1)),
                                            item.get('unit_price', item.get('price', 0)),
                                            item_subtotal,
                                            item_discount,
                                            item_total,
                                            item.get('name', '')
                                        )
                                    ))
                            else:
                                # Normal insert with explicit sale_id
                                for item in items:
                                    item_subtotal = item.get('subtotal', 0)
                                    item_discount = item.get('discount', 0)
                                    item_total = item.get('total', item_subtotal - item_discount)
                                    operations.append((
                                        """INSERT INTO sale_items (
                                            sale_id, product_id, qty, price, subtotal, discount, total, name, synced
                                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)""",
                                        (
                                            sale_id,
                                            item.get('product_id'),
                                            item.get('quantity', item.get('qty', 1)),
                                            item.get('unit_price', item.get('price', 0)),
                                            item_subtotal,
                                            item_discount,
                                            item_total,
                                            item.get('name', '')
                                        )
                                    ))
                            
                            saved_count += 1
                            
                        except Exception as e:
                            error_count += 1
                            error_msg = str(e)
                            errors.append(f"Sale {sale.get('id')}: {error_msg}")
                            log_debug(f"http_server.py:652_{idx}", "Error preparing sale insert", {
                                "sale_id": sale.get('id'),
                                "error": error_msg,
                                "error_type": type(e).__name__
                            }, "E")
                            logger.error(f"Error preparing sale {sale.get('id')}: {e}")
                    
                    # Execute all inserts in a single transaction with retry logic
                    if operations:
                        logger.info(f"🔄 Executing sales transaction: {len(operations)} operations, {saved_count} sales to save")
                        logger.info(f"📋 DatabaseManager type: {type(self.core.db).__name__}")
                        logger.info(f"📋 Has execute_transaction: {hasattr(self.core.db, 'execute_transaction')}")
                        
                        # Verify database manager
                        if not hasattr(self.core.db, 'execute_transaction'):
                            error_msg = f"DatabaseManager does not have execute_transaction method. Type: {type(self.core.db)}"
                            logger.error(f"❌ {error_msg}")
                            raise AttributeError(error_msg)
                        
                        log_debug("http_server.py:658", "Executing transaction", {
                            "operations_count": len(operations),
                            "saved_count": saved_count,
                            "db_type": type(self.core.db).__name__
                        }, "E")
                        try:
                            
                            # Log first operation for debugging
                            if operations:
                                first_op = operations[0]
                                logger.info(f"📝 First operation preview: {first_op[0][:150]}...")
                                logger.info(f"📝 First operation params count: {len(first_op[1]) if len(first_op) > 1 else 0}")
                            
                            result = self.core.db.execute_transaction(operations)
                            if result is None:
                                logger.error("❌ Transaction returned None - database error")
                                raise Exception("Transaction returned None")
                            success = result.get('success') if isinstance(result, dict) else result
                            logger.info(f"📊 Sales transaction result: success={success}, operations={len(operations)}")
                            if success:
                                logger.info(f"✅ Sales transaction committed: {saved_count} sales saved")
                                log_debug("http_server.py:660", "Transaction committed successfully", {}, "E")
                            else:
                                logger.error(f"❌ Sales transaction FAILED: returned False, {len(operations)} operations lost")
                                log_debug("http_server.py:662", "Transaction failed", {}, "E")
                                error_count += len(operations)
                                raise Exception("Transaction failed to commit (returned False)")
                        except Exception as tx_error:
                            logger.error(f"❌ Sales transaction EXCEPTION: {tx_error}, type={type(tx_error).__name__}")
                            import traceback
                            logger.error(f"❌ Traceback: {traceback.format_exc()}")
                            raise
                    else:
                        logger.warning("⚠️ No sales operations to execute (operations list is empty)")
                        
                except Exception as e:
                    logger.error(f"❌ Critical error in sales save: {e}, type={type(e).__name__}")
                    log_debug("http_server.py:663", "Critical error in sales save", {
                        "error": str(e),
                        "error_type": type(e).__name__
                    }, "E")
                    raise
                
                logger.info(f"✅ Sales sync complete: {saved_count} saved, {duplicate_count} duplicates skipped, {error_count} errors")
                
                log_debug("http_server.py:675", "Sales sync response prepared", {
                    "saved_count": saved_count,
                    "duplicate_count": duplicate_count,
                    "error_count": error_count
                }, "E")
                
                return JSONResponse({
                    "success": True,
                    "saved": saved_count,
                    "duplicates": duplicate_count,
                    "errors": error_count,
                    "error_details": errors[:10] if errors else [],
                    "accepted_ids": accepted_sale_ids,
                    "message": f"Saved {saved_count} sales from {request.terminal_id or 'unknown'}",
                    "timestamp": datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"❌ Sales sync error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/v1/sync/customers")
        async def sync_customers_push(
            request: SyncCustomersRequest,
            authorized: bool = Depends(self.verify_token)
        ):
            """
            Receive customer data from client terminal and save to database.

            Updates existing customers or creates new ones.
            """
            if not self.core.db:
                logger.warning("Database not available for customers sync")
                raise HTTPException(status_code=503, detail="Database not available")

            try:
                terminal_id = request.terminal_id or "unknown"
                logger.info(f"👥 Customer sync from {terminal_id}: {len(request.customers)} customers")
                
                updated_count = 0
                created_count = 0
                accepted_customer_ids = []  # B.5: IDs que el cliente puede marcar como synced
                
                # Use DatabaseManager's transaction method to handle locks properly
                operations = []
                
                for idx, customer in enumerate(request.customers):
                    try:
                        customer_id = customer.get('id')
                        
                        # CRITICAL VALIDATION: Required fields before processing
                        if not customer_id:
                            logger.warning(f"Customer {idx} rejected: Missing 'id'")
                            continue
                        
                        # Validate name (required for customers)
                        name = customer.get('name')
                        if not name:
                            # Try to construct from first_name + last_name
                            first_name = customer.get('first_name', '')
                            last_name = customer.get('last_name', '')
                            name = f"{first_name} {last_name}".strip()
                            
                            if not name:
                                logger.warning(f"Customer {customer_id} rejected: Missing 'name'")
                                continue
                        
                        # Check if customer exists (PostgreSQL uses %s)
                        existing = self.core.db.execute_query(
                            "SELECT id FROM customers WHERE id = %s", 
                            (customer_id,)
                        )
                        
                        if existing:
                            # Update existing customer
                            operations.append((
                                """UPDATE customers 
                                SET name = %s, phone = %s, email = %s, address = %s,
                                    credit_limit = %s, loyalty_points = %s, notes = %s, synced = 0
                                WHERE id = %s""",
                                (
                                    customer.get('name'),
                                    customer.get('phone'),
                                    customer.get('email'),
                                    customer.get('address'),
                                    customer.get('credit_limit'),
                                    customer.get('loyalty_points'),
                                    customer.get('notes'),
                                    customer_id
                                )
                            ))
                            accepted_customer_ids.append(customer_id)
                            updated_count += 1
                        else:
                            # Create new customer - Match schema_postgresql.sql structure
                            operations.append((
                                """INSERT INTO customers (
                                    id, name, phone, email, address,
                                    credit_limit, loyalty_points, notes, synced, is_active
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, 1)""",
                                (
                                    customer_id,
                                    customer.get('name'),
                                    customer.get('phone'),
                                    customer.get('email'),
                                    customer.get('address'),
                                    customer.get('credit_limit', 0),
                                    customer.get('loyalty_points', 0),
                                    customer.get('notes')
                                )
                            ))
                            accepted_customer_ids.append(customer_id)
                            created_count += 1
                            
                    except Exception as e:
                        logger.error(f"Error syncing customer {customer.get('id')}: {e}")
                
                # Execute all operations in a single transaction with retry logic
                if operations:
                    log_debug("http_server.py:834", "Executing customer transaction", {
                        "operations_count": len(operations),
                        "updated_count": updated_count,
                        "created_count": created_count
                    }, "E")
                    try:
                        result = self.core.db.execute_transaction(operations)
                        if result is None:
                            raise Exception("Transaction returned None - database error")
                        log_debug("http_server.py:836", "Customer transaction result", {
                            "success": result.get('success') if isinstance(result, dict) else result,
                            "operations_count": len(operations)
                        }, "E")
                        if not (result.get('success') if isinstance(result, dict) else result):
                            log_debug("http_server.py:838", "Customer transaction returned False", {}, "E")
                            raise Exception("Customer transaction failed to commit (returned False)")
                    except Exception as tx_error:
                        log_debug("http_server.py:841", "Customer transaction exception", {
                            "error": str(tx_error),
                            "error_type": type(tx_error).__name__
                        }, "E")
                        raise
                
                logger.info(f"✅ Customer sync complete: {updated_count} updated, {created_count} created")
                
                return JSONResponse({
                    "success": True,
                    "updated": updated_count,
                    "created": created_count,
                    "accepted_ids": accepted_customer_ids,
                    "timestamp": datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"❌ Customer sync error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/v1/sync/inventory-movements")
        async def sync_inventory_movements_push(
            request: SyncInventoryMovementsRequest,
            authorized: bool = Depends(self.verify_token)
        ):
            """
            Receive inventory movements (Parte A Fase 2 + 2.4 + 4).
            Idempotencia: (terminal_id, movement_id) en applied_inventory_movements.
            Orden: por (timestamp, id). Stock negativo: rechazar ítem (politica A).
            """
            if not self.core.db:
                logger.warning("Database not available for inventory movements sync")
                raise HTTPException(status_code=503, detail="Database not available")

            try:
                movements = request.movements or []
                terminal_id = str(request.terminal_id or "unknown")
                logger.info(f"📦 Inventory movements sync from {terminal_id}: {len(movements)} movements")

                # Fase 4: Ordenar por (timestamp, id); sin timestamp al final (E6)
                def sort_key(m):
                    ts = m.get("timestamp") or "9999-12-31T23:59:59"
                    mid = m.get("id") or 0
                    return (ts, mid)
                movements = sorted(movements, key=sort_key)

                # Fase 2.4: Idempotencia - cargar ya aplicados (normalizar IDs a int para comparación)
                applied_keys = set()
                mov_ids = []
                for m in movements:
                    mid = m.get("id")
                    if mid is not None:
                        try:
                            mov_ids.append(int(mid))
                        except (TypeError, ValueError):
                            pass
                if mov_ids and terminal_id != "unknown":
                    try:
                        placeholders = ",".join(["%s"] * len(mov_ids))
                        rows = self.core.db.execute_query(
                            "SELECT terminal_id, movement_local_id FROM applied_inventory_movements WHERE terminal_id = %s AND movement_local_id IN (" + placeholders + ")",
                            (terminal_id,) + tuple(mov_ids)
                        )
                        if rows:
                            for r in rows:
                                applied_keys.add((str(r.get("terminal_id") or r[0]), int(r.get("movement_local_id") or r[1])))
                    except Exception as e:
                        logger.debug("applied_inventory_movements check: %s", e)

                accepted_ids = []
                applied = 0
                errors = []
                operations = []
                to_record = []  # (terminal_id, movement_local_id) para idempotencia

                for mov in movements:
                    mov_id = mov.get("id")
                    try:
                        mov_id_int = int(mov_id) if mov_id is not None else None
                    except (TypeError, ValueError):
                        mov_id_int = None
                    sku = mov.get("sku")
                    product_id = mov.get("product_id")
                    quantity = mov.get("quantity")
                    if quantity is None:
                        errors.append(f"Movement {mov_id}: missing quantity")
                        continue
                    try:
                        qty = float(quantity)
                    except (TypeError, ValueError):
                        errors.append(f"Movement {mov_id}: invalid quantity")
                        continue
                    if not sku and product_id is None:
                        errors.append(f"Movement {mov_id}: missing sku and product_id")
                        continue

                    # Idempotencia: ya aplicado → aceptar sin aplicar de nuevo
                    if mov_id_int is not None and (terminal_id, mov_id_int) in applied_keys:
                        accepted_ids.append(mov_id)
                        applied += 1
                        continue

                    # E1: Verificar que el producto exista en el servidor antes de aceptar
                    product_exists = False
                    try:
                        if sku:
                            row = self.core.db.execute_query("SELECT 1 FROM products WHERE sku = %s", (sku,))
                        else:
                            row = self.core.db.execute_query("SELECT 1 FROM products WHERE id = %s", (product_id,))
                        product_exists = bool(row)
                    except Exception as e:
                        logger.debug("product existence check: %s", e)
                    if not product_exists:
                        errors.append(f"Movement {mov_id}: product not found (sku={sku}, product_id={product_id})")
                        continue

                    # Fase 4 política (A): rechazar movimiento que dejaría stock < 0
                    if qty < 0:
                        try:
                            if sku:
                                row = self.core.db.execute_query("SELECT stock FROM products WHERE sku = %s", (sku,))
                            else:
                                row = self.core.db.execute_query("SELECT stock FROM products WHERE id = %s", (product_id,))
                            if row:
                                current = float(row[0].get("stock", row[0][0]) or 0)
                                if current + qty < 0:
                                    errors.append(f"Movement {mov_id}: would leave stock negative (current={current}, delta={qty})")
                                    continue
                        except Exception as e:
                            logger.debug("stock check: %s", e)

                    if sku:
                        operations.append((
                            "UPDATE products SET stock = stock + %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE sku = %s",
                            (qty, sku)
                        ))
                    else:
                        operations.append((
                            "UPDATE products SET stock = stock + %s, synced = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                            (qty, product_id)
                        ))
                    if mov_id_int is not None:
                        accepted_ids.append(mov_id)
                        to_record.append((terminal_id, mov_id_int))
                    applied += 1

                # E2: Incluir INSERTs de idempotencia en la misma transacción (rollback si falla alguno)
                for tid, mid in to_record:
                    operations.append((
                        """INSERT INTO applied_inventory_movements (terminal_id, movement_local_id)
                           VALUES (%s, %s) ON CONFLICT (terminal_id, movement_local_id) DO NOTHING""",
                        (tid, mid)
                    ))

                if operations:
                    try:
                        result = self.core.db.execute_transaction(operations)
                        if not result or not (result.get("success") if isinstance(result, dict) else result):
                            raise Exception("Transaction failed")
                        logger.info(f"✅ Applied {applied} inventory movements")
                    except Exception as tx_e:
                        logger.error(f"Inventory movements transaction error: {tx_e}")
                        raise
                return JSONResponse({
                    "success": True,
                    "applied": applied,
                    "accepted_ids": accepted_ids,
                    "errors": errors[:20],
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"❌ Inventory movements sync error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # ========== GET ENDPOINTS (Clients pull data from server) ==========
        
        @self.app.get("/api/v1/sync/inventory")
        async def sync_inventory_pull(authorized: bool = Depends(self.verify_token)):
            """
            Send current inventory to client terminals.

            Returns all products with current stock levels.
            """
            if not self.core.db:
                logger.warning("Database not available for inventory pull")
                raise HTTPException(status_code=503, detail="Database not available")

            try:
                # Use DatabaseManager for consistent connection handling
                rows = self.core.db.execute_query("""
                    SELECT 
                        id, sku, name, price, price_wholesale, cost, cost_price, stock,
                        category_id, category, department, provider, min_stock, max_stock,
                        is_active, is_kit, tax_scheme, tax_rate, sale_type, barcode,
                        is_favorite, description, notes, shadow_stock,
                        sat_clave_prod_serv, sat_clave_unidad, sat_descripcion, sat_code, sat_unit,
                        entry_date, visible, cost_a, cost_b, qty_from_a, qty_from_b,
                        created_at, updated_at
                    FROM products
                    WHERE is_active = 1
                    ORDER BY id DESC
                """)
                
                products = [serialize_row(dict(row)) for row in rows]

                logger.info(f"📤 Sending {len(products)} products to client")

                return JSONResponse({
                    "success": True,
                    "products": products,
                    "count": len(products),
                    "timestamp": datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Error fetching inventory: {e}")
                
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/v1/sync/sales")
        async def sync_sales_pull(
            since: Optional[str] = None,
            limit: int = 1000,
            authorized: bool = Depends(self.verify_token)
        ):
            """
            Send sales history to client terminals.

            Returns sales with their items, respecting UUID and atomicity.
            """
            if not self.core.db:
                logger.warning("Database not available for sales pull")
                raise HTTPException(status_code=503, detail="Database not available")

            try:
                # E10: Validar límite para evitar carga excesiva
                limit_safe = max(1, min(int(limit) if limit is not None else 1000, 50000))

                # Build query with optional date filter
                if since:
                    query = """
                        SELECT id, uuid, timestamp, subtotal, tax, total, discount, payment_method,
                               customer_id, user_id, cashier_id, turn_id, serie, folio, folio_visible,
                               branch_id, status, synced_from_terminal
                        FROM sales
                        WHERE timestamp::timestamp >= %s::timestamp
                        ORDER BY id DESC
                        LIMIT %s
                    """
                    params = (since, limit_safe)
                else:
                    query = """
                        SELECT id, uuid, timestamp, subtotal, tax, total, discount, payment_method,
                               customer_id, user_id, cashier_id, turn_id, serie, folio, folio_visible,
                               branch_id, status, synced_from_terminal
                        FROM sales
                        WHERE timestamp::timestamp >= NOW() - INTERVAL '7 days'
                        ORDER BY id DESC
                        LIMIT %s
                    """
                    params = (limit_safe,)
                
                # Use DatabaseManager for consistent connection handling
                rows = self.core.db.execute_query(query, params)
                
                sales = []
                for row in rows:
                    sale = serialize_row(dict(row))
                    sale_id = sale.get('id')

                    # Get sale items for each sale (atomic with sale)
                    items_query = """
                        SELECT id, product_id, qty, price, subtotal, name
                        FROM sale_items
                        WHERE sale_id = %s
                        ORDER BY id
                    """
                    items_rows = self.core.db.execute_query(items_query, (sale_id,))
                    sale['items'] = [serialize_row(dict(item)) for item in items_rows]
                    sales.append(sale)
                
                logger.info(f"📤 Sending {len(sales)} sales to client")

                return JSONResponse({
                    "success": True,
                    "sales": sales,
                    "count": len(sales),
                    "timestamp": datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Error fetching sales: {e}")
                
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/v1/sync/customers")
        async def sync_customers_pull(authorized: bool = Depends(self.verify_token)):
            """
            Send current customer list to client terminals.
            """
            if not self.core.db:
                logger.warning("Database not available for customers pull")
                raise HTTPException(status_code=503, detail="Database not available")

            try:
                # Use DatabaseManager for consistent connection handling
                rows = self.core.db.execute_query("""
                    SELECT id, name, phone, email, address,
                           credit_limit, points, wallet_balance, notes
                    FROM customers
                    WHERE is_active = 1
                    ORDER BY id DESC
                    LIMIT 2000
                """)
                
                customers = [serialize_row(dict(row)) for row in rows]

                logger.info(f"📤 Sending {len(customers)} customers to client")

                return JSONResponse({
                    "success": True,
                    "customers": customers,
                    "count": len(customers),
                    "timestamp": datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Error fetching customers: {e}")
                
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/v1/stock/check")
        async def check_stock(
            request: StockCheckRequest,
            authorized: bool = Depends(self.verify_token)
        ):
            """
            Check real-time stock availability for a list of items.
            """
            if not self.core.db:
                logger.warning("Database not available for stock check")
                raise HTTPException(status_code=503, detail="Database not available")

            try:
                # logger.info(f"🔎 Real-time stock check from {request.terminal_id} for {len(request.items)} items")
                
                allowed = True
                insufficient_items = []
                
                # Use DatabaseManager for consistent connection handling
                for item in request.items:
                    sku = item.get('sku')
                    requested_qty = float(item.get('qty', 0))
                    
                    if not sku or requested_qty <= 0:
                        continue
                        
                    # Get current real-time stock (PostgreSQL uses %s)
                    rows = self.core.db.execute_query(
                        "SELECT stock, name FROM products WHERE sku = %s", 
                        (sku,)
                    )
                    
                    if rows:
                        row = rows[0]
                        current_stock = float(row['stock'])
                        name = row['name']
                        
                        if current_stock < requested_qty:
                            allowed = False
                            insufficient_items.append({
                                "sku": sku,
                                "name": name,
                                "available": current_stock,
                                "requested": requested_qty
                            })
                    else:
                        # Product not found
                        allowed = False
                        insufficient_items.append({
                            "sku": sku,
                            "name": "Unknown Product",
                            "available": 0,
                            "requested": requested_qty,
                            "error": "Product not found"
                        })
                
                if not allowed:
                    terminal_id = request.terminal_id or "unknown"
                    logger.warning(f"🚫 Stock check FAILED for {terminal_id}: {len(insufficient_items)} items insufficient")
                
                return JSONResponse({
                    "allowed": allowed,
                    "insufficient_items": insufficient_items,
                    "timestamp": datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Stock check error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # ========== GENERIC ENDPOINTS FOR ALL CONFIGURED TABLES ==========
        
        # Endpoints v1 (mantener para compatibilidad)
        try:
            from app.utils.sync_endpoints import create_sync_endpoints
            create_sync_endpoints(self.app, self.core, self.verify_token)
            logger.info("✅ Generic sync endpoints v1 created")
        except Exception as e:
            logger.warning(f"Could not create generic sync endpoints v1: {e}")
        
        # Endpoints v2 (nuevos con soporte padre-hijo)
        try:
            from app.utils.sync_endpoints_v2 import create_parent_child_sync_endpoints
            create_parent_child_sync_endpoints(self.app, self.core, self.verify_token)
            logger.info("✅ Parent-child sync endpoints v2 created")
        except Exception as e:
            logger.error(f"Could not create parent-child sync endpoints v2: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def start(self):
        """Start the HTTP server (blocking)."""
        import socket

        # Check if port is available
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((self.host if self.host != "0.0.0.0" else "127.0.0.1", self.port))
            sock.close()
            if result == 0:
                raise OSError(f"Port {self.port} is already in use")
        except OSError:
            raise
        except Exception as e:
            logger.warning(f"Could not check port availability: {e}")
        
        logger.info(f"Starting POS HTTP server on {self.host}:{self.port}")
        try:
            uvicorn.run(
                self.app,
                host=self.host,
                port=self.port,
                log_level="info",
                access_log=True
            )
        except OSError as e:
            if "Address already in use" in str(e) or "address already in use" in str(e).lower():
                raise OSError(f"Port {self.port} is already in use. Please change the port in config.json")
            raise
    
    def start_background(self):
        """Start server in background thread with error handling and port conflict detection."""
        import json
        import socket
        import threading
        import time

        debug_log_path = get_debug_log_path_str() or ""

        def log_debug(location, message, data, hypothesis_id):
            try:
                if debug_log_path:
                    log_entry = {
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": hypothesis_id,
                        "location": location,
                        "message": message,
                        "data": data,
                        "timestamp": int(time.time() * 1000)
                    }
                    with open(debug_log_path, "a") as f:
                        f.write(json.dumps(log_entry) + "\n")
                        f.flush()
            except Exception as e:
                logger.debug("start_server debug log write: %s", e)
        
        # Check if port is available before starting
        def check_port(host, port):
            """Check if port is available."""
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((host if host != "0.0.0.0" else "127.0.0.1", port))
                sock.close()
                return result != 0  # True if port is available
            except Exception as e:
                log_debug("http_server.py:check_port:error", "Error checking port", {
                    "error": str(e)
                }, "H")
                return True  # Assume available if check fails
        
        # Verify port availability
        if not check_port(self.host, self.port):
            error_msg = f"Port {self.port} is already in use"
            logger.error(f"❌ {error_msg}")
            log_debug("http_server.py:port_conflict", "Port conflict detected", {
                "port": self.port,
                "host": self.host
            }, "H")
            raise OSError(error_msg)
        
        def run_server():
            try:
                log_debug("http_server.py:start_background:before_start", "Starting HTTP server", {
                    "host": self.host,
                    "port": self.port
                }, "H")
                
                # Use uvicorn with proper error handling
                import uvicorn
                logger.warning(f"🚀 [DEBUG] Iniciando uvicorn en {self.host}:{self.port}...")
                logger.warning(f"🔍 [DEBUG] host={self.host}, port={self.port}, type(host)={type(self.host)}")
                
                config = uvicorn.Config(
                    self.app,
                    host=self.host,
                    port=self.port,
                    log_level="info",
                    access_log=True
                )
                logger.warning(f"✅ [DEBUG] uvicorn.Config creado: host={config.host}, port={config.port}")
                
                server = uvicorn.Server(config)
                logger.warning(f"✅ [DEBUG] uvicorn.Server creado, iniciando server.run()...")
                
                # CRÍTICO: server.run() es bloqueante, esto debería iniciar el servidor
                server.run()
                logger.warning(f"✅ [DEBUG] uvicorn servidor iniciado en puerto {self.port}")
                
                log_debug("http_server.py:start_background:server_started", "HTTP server started successfully", {
                    "host": self.host,
                    "port": self.port
                }, "H")
            except OSError as e:
                logger.error(f"❌ [DEBUG] OSError en run_server: {type(e).__name__}: {e}")
                if "Address already in use" in str(e) or "address already in use" in str(e).lower():
                    error_msg = f"Port {self.port} is already in use"
                    logger.error(f"❌ {error_msg}")
                    log_debug("http_server.py:start_background:port_error", "Port already in use", {
                        "port": self.port,
                        "error": str(e)
                    }, "H")
                else:
                    import traceback
                    logger.error(f"❌ [DEBUG] OSError traceback:\n{traceback.format_exc()}")
                    log_debug("http_server.py:start_background:os_error", "OS error starting server", {
                        "error": str(e),
                        "error_type": type(e).__name__
                    }, "H")
            except Exception as e:
                logger.error(f"❌ [DEBUG] Exception en run_server: {type(e).__name__}: {e}")
                import traceback
                logger.error(f"❌ [DEBUG] Exception traceback:\n{traceback.format_exc()}")
                import traceback
                logger.error(f"❌ Traceback: {traceback.format_exc()}")
                log_debug("http_server.py:start_background:exception", "Exception starting server", {
                    "error": str(e),
                    "error_type": type(e).__name__
                }, "H")
        
        thread = threading.Thread(target=run_server, daemon=True, name="FastAPI-Server")
        thread.start()
        
        # Wait a moment to check if thread started successfully
        import time as time_module
        time_module.sleep(0.5)
        
        if thread.is_alive():
            logger.info(f"✅ HTTP server started in background on port {self.port}")
            log_debug("http_server.py:start_background:success", "HTTP server thread started", {
                "host": self.host,
                "port": self.port,
                "thread_alive": thread.is_alive(),
                "thread_name": thread.name
            }, "H")
        else:
            logger.error(f"❌ HTTP server thread failed to start on port {self.port}")
            log_debug("http_server.py:start_background:thread_failed", "Thread failed to start", {
                "port": self.port
            }, "H")
        
        return thread

def create_pos_server(pos_core, config: Dict[str, Any]) -> Optional[POSHTTPServer]:
    """
    Factory function to create POS HTTP server.
    
    Args:
        pos_core: POSCore instance
        config: Configuration dictionary
    
    Returns:
        POSHTTPServer instance or None if disabled/not available
    """
    logger.debug("=" * 60)
    logger.debug("🔍 [DEBUG] ===== create_pos_server() LLAMADO =====")
    logger.debug(f"🔍 [DEBUG] Config recibida: {list(config.keys())}")
    logger.debug("=" * 60)
    
    # Check 1: FastAPI availability
    logger.debug(f"🔍 [DEBUG] Verificando FastAPI...")
    if not FastAPI:
        logger.warning("FastAPI not available, HTTP server disabled")
        log_debug("http_server.py:create_pos_server:no_fastapi", "FastAPI not available", {}, "H")
        return None
    logger.debug(f"✅ [DEBUG] FastAPI disponible")
    
    # Check 2: Mode
    mode = config.get("mode", "standalone")
    logger.debug(f"🔍 [DEBUG] Mode: '{mode}'")
    if mode != "server":
        logger.info(f"Mode is '{mode}', HTTP server disabled (requires mode='server')")
        log_debug("http_server.py:create_pos_server:wrong_mode", "Wrong mode for server", {
            "mode": mode
        }, "H")
        return None
    logger.debug(f"✅ [DEBUG] Mode correcto: 'server'")
    
    # Check 3: API Token
    api_token = config.get("api_dashboard_token", "")
    logger.debug(f"🔍 [DEBUG] API token: {'✅ presente' if api_token else '❌ faltante'} (length: {len(api_token)})")
    if not api_token:
        logger.warning("No API token configured, HTTP server disabled")
        logger.info("   Configure 'api_dashboard_token' in data/config/pos_config.json")
        log_debug("http_server.py:create_pos_server:no_token", "No API token", {}, "H")
        return None
    logger.debug(f"✅ [DEBUG] API token presente")
    
    # Check 4: Port
    port = config.get("server_port", 8000)
    logger.debug(f"🔍 [DEBUG] Port: {port}")
    
    log_debug("http_server.py:create_pos_server:creating", "Creating POSHTTPServer instance", {
        "host": "0.0.0.0",
        "port": port,
        "token_length": len(api_token)
    }, "H")
    
    # Check 5: Create server instance
    logger.debug(f"🔧 [DEBUG] Intentando crear POSHTTPServer en puerto {port}...")
    try:
        logger.debug(f"🔍 [DEBUG] Llamando POSHTTPServer.__init__()...")
        server = POSHTTPServer(
            pos_core,
            api_token=api_token,
            host="0.0.0.0",
            port=port
        )
        logger.debug(f"✅ [DEBUG] POSHTTPServer creado exitosamente: {type(server)}")
        log_debug("http_server.py:create_pos_server:success", "POSHTTPServer created successfully", {
            "port": port
        }, "H")
        return server
    except OSError as e:
        logger.error(f"OSError al crear servidor: {e}")
        if "already in use" in str(e).lower() or "Address already in use" in str(e):
            logger.error(f"Port {port} is already in use. Change server_port in config.json")
            log_debug("http_server.py:create_pos_server:port_conflict", "Port conflict", {
                "port": port,
                "error": str(e)
            }, "H")
        else:
            logger.error(f"Failed to create HTTP server (OSError): {e}")
            log_debug("http_server.py:create_pos_server:os_error", "OS error", {
                "error": str(e)
            }, "H")
        return None
    except ImportError as e:
        logger.error(f"ImportError al crear servidor: {e}")
        logger.info("   Install with: pip install fastapi uvicorn")
        log_debug("http_server.py:create_pos_server:import_error", "Import error", {
            "error": str(e)
        }, "H")
        return None
    except ValueError as e:
        logger.error(f"ValueError al crear servidor: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        log_debug("http_server.py:create_pos_server:value_error", "Value error", {
            "error": str(e),
            "error_type": type(e).__name__
        }, "H")
        return None
    except Exception as e:
        logger.error(f"Exception inesperada al crear servidor: {type(e).__name__}: {e}")
        import traceback
        logger.debug(f"Traceback completo:\n{traceback.format_exc()}")
        log_debug("http_server.py:create_pos_server:exception", "Exception creating server", {
            "error": str(e),
            "error_type": type(e).__name__
        }, "H")
        return None
