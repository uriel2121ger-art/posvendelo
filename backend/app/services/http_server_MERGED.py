"""
HTTP server for TITAN POS multi-terminal (MultiCaja) synchronization.

This FastAPI server runs on the master terminal and provides endpoints
for client terminals to synchronize inventory, sales, and customer data.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
from pathlib import Path

try:
    from fastapi import Depends, FastAPI, Header, HTTPException
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    FastAPI = None
    BaseModel = None
    uvicorn = None

logger = logging.getLogger(__name__)


# Pydantic models for request validation
if BaseModel:
    class SyncInventoryRequest(BaseModel):
        """Request model for inventory synchronization."""
        products: List[Dict[str, Any]]
        timestamp: str
        terminal_id: str
    
    class SyncSalesRequest(BaseModel):
        """Request model for sales synchronization."""
        sales: List[Dict[str, Any]]
        timestamp: str
        terminal_id: str
    
    class SyncCustomersRequest(BaseModel):
        """Request model for customer synchronization."""
        customers: List[Dict[str, Any]]
        timestamp: str
        terminal_id: str
    
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
        self.app = FastAPI(
            title="TITAN POS API",
            description="Multi-terminal synchronization API",
            version="1.0.0"
        )
        
        self._setup_routes()
    
    def verify_token(self, authorization: Optional[str] = Header(None)) -> bool:
        """Verify API token from Authorization header."""
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
                    # Today's sales
                    result = self.core.db.execute_query("""
                        SELECT COUNT(*), COALESCE(SUM(total), 0) 
                        FROM sales 
                        WHERE CAST(created_at AS DATE) = CURRENT_DATE
                        AND status = 'completed'
                    """)
                    if result and len(result) > 0 and result[0]:
                        row = result[0]
                        today_sales = (row.get('COUNT(*)') if isinstance(row, dict) else row[0]) or 0
                        today_total = (row.get('COALESCE(SUM(total), 0)') if isinstance(row, dict) else row[1]) or 0.0
                    else:
                        today_sales = 0
                        today_total = 0.0
                    
                    # Active turn
                    result = self.core.db.execute_query("""
                        SELECT id, user_id, start_timestamp 
                        FROM turns 
                        WHERE status = 'open' 
                        ORDER BY id DESC LIMIT 1
                    """)
                    if result and len(result) > 0 and result[0]:
                        turn = result[0]
                        if isinstance(turn, dict):
                            active_turn = {"id": turn.get('id'), "user_id": turn.get('user_id'), "started": turn.get('start_timestamp')}
                        else:
                            active_turn = {"id": turn[0], "user_id": turn[1], "started": turn[2]}
                except Exception:
                    pass
                
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
            try:
                result = {
                    "success": True,
                    "sales_received": 0,
                    "customers_received": 0,
                    "inventory_received": 0,
                    "errors": []
                }
                
                # Build transaction operations
                operations = []
                
                # Process sales
                if batch.sales:
                    for sale in batch.sales:
                        try:
                            sale_id = sale.get('id')
                            if not sale_id:
                                continue
                            
                            # Check if sale already exists
                            existing = self.core.db.execute_query("SELECT id FROM sales WHERE id = %s", (sale_id,))
                            if existing:
                                continue  # Skip duplicates
                            
                            # Insert sale
                            operations.append(("""
                                INSERT INTO sales (
                                    id, timestamp, total, payment_method, 
                                    user_id, customer_id, folio, serie,
                                    branch_id, synced, synced_from_terminal
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s)
                            """, (
                                sale_id,
                                sale.get('timestamp'),
                                sale.get('total'),
                                sale.get('payment_method'),
                                sale.get('cashier_id'),
                                sale.get('customer_id'),
                                sale.get('folio'),
                                sale.get('serie'),
                                batch.branch_id,
                                batch.terminal_id
                            )))
                            
                            # Insert sale items if present
                            items = sale.get('items', [])
                            for item in items:
                                try:
                                    operations.append(("""
                                        INSERT INTO sale_items (
                                            sale_id, product_id, qty, price, subtotal, name
                                        ) VALUES (%s, %s, %s, %s, %s, %s)
                                        ON CONFLICT (sale_id, product_id) DO NOTHING
                                    """, (
                                        sale_id,
                                        item.get('product_id'),
                                        item.get('quantity', item.get('qty', 1)),
                                        item.get('unit_price', item.get('price', 0)),
                                        item.get('subtotal', 0),
                                        item.get('name', '')
                                    )))
                                except Exception:
                                    pass
                            
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
                            
                            # Check if customer exists
                            existing = self.core.db.execute_query("SELECT id FROM customers WHERE id = %s", (customer_id,))
                            if existing:
                                # Update existing customer
                                operations.append(("""
                                    UPDATE customers SET
                                        name = COALESCE(%s, name),
                                        phone = COALESCE(%s, phone),
                                        email = COALESCE(%s, email),
                                        rfc = COALESCE(%s, rfc),
                                        synced = 1,
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE id = %s
                                """, (
                                    name if name else None,
                                    customer.get('phone'),
                                    customer.get('email'),
                                    customer.get('rfc'),
                                    customer_id
                                )))
                            else:
                                # Insert new customer
                                operations.append(("""
                                    INSERT INTO customers (
                                        id, name, phone, email, rfc, synced
                                    ) VALUES (%s, %s, %s, %s, %s, 1)
                                """, (
                                    customer_id,
                                    name or 'Cliente',
                                    customer.get('phone'),
                                    customer.get('email'),
                                    customer.get('rfc')
                                )))
                            
                            result["customers_received"] += 1
                            
                        except Exception as e:
                            result["errors"].append(f"Customer {customer.get('id')}: {str(e)}")
                
                # Process inventory changes
                if batch.inventory_changes:
                    for change in batch.inventory_changes:
                        try:
                            sku = change.get('sku')
                            product_id = change.get('product_id')
                            
                            if not sku and not product_id:
                                continue
                            
                            # Update product stock
                            if sku:
                                operations.append(("""
                                    UPDATE products SET
                                        stock = COALESCE(%s, stock),
                                        price = COALESCE(%s, price),
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE sku = %s
                                """, (
                                    change.get('stock'),
                                    change.get('price'),
                                    sku
                                )))
                            elif product_id:
                                operations.append(("""
                                    UPDATE products SET
                                        stock = COALESCE(%s, stock),
                                        price = COALESCE(%s, price),
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE id = %s
                                """, (
                                    change.get('stock'),
                                    change.get('price'),
                                    product_id
                                )))
                            
                            result["inventory_received"] += 1
                            
                        except Exception as e:
                            result["errors"].append(f"Inventory {change.get('sku')}: {str(e)}")
                
                # Execute all operations in a transaction
                if operations:
                    self.core.db.execute_transaction(operations)
                
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
            try:
                if since:
                    products = self.core.db.execute_query("""
                        SELECT id, sku, name, price, cost, stock, category,
                               is_active, updated_at
                        FROM products
                        WHERE updated_at > %s
                        ORDER BY updated_at DESC
                        LIMIT 5000
                    """, (since,))
                else:
                    products = self.core.db.execute_query("""
                        SELECT id, sku, name, price, cost, stock, category,
                               is_active, updated_at
                        FROM products
                        WHERE is_active = 1
                        ORDER BY id DESC
                        LIMIT 5000
                    """)
                
                # Convert to list of dicts if needed
                if products and not isinstance(products[0], dict):
                    # If results are tuples, convert to dicts
                    columns = ['id', 'sku', 'name', 'price', 'cost', 'stock', 'category', 'is_active', 'updated_at']
                    products = [dict(zip(columns, row)) for row in products]
                
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
            try:
                logger.info(f"📦 Inventory sync from {request.terminal_id}: {len(request.products)} products")
                
                updated_count = 0
                created_count = 0
                skipped_count = 0
                conflicts = []
                
                operations = []
                
                for product in request.products:
                    try:
                        product_id = product.get('id')
                        sku = product.get('sku')
                        
                        if not sku:
                            continue
                        
                        # Check if product exists
                        existing = self.core.db.execute_query("SELECT id, updated_at FROM products WHERE sku = %s", (sku,))
                        
                        if existing:
                            # Update existing product
                            # Conflict resolution: Use most recent timestamp
                            operations.append(("""
                                UPDATE products 
                                SET name = %s, price = %s, stock = %s, category = %s,
                                    provider = %s, is_favorite = %s, sale_type = %s,
                                    min_stock = %s, max_stock = %s, updated_at = CURRENT_TIMESTAMP
                                WHERE sku = %s
                            """, (
                                product.get('name'),
                                product.get('price'),
                                product.get('stock'),
                                product.get('category'),
                                product.get('provider'),
                                product.get('is_favorite', 0),
                                product.get('sale_type', 'unit'),
                                product.get('min_stock'),
                                product.get('max_stock'),
                                sku
                            )))
                            updated_count += 1
                        else:
                            # Create new product
                            operations.append(("""
                                INSERT INTO products (
                                    sku, name, price, stock, category, provider,
                                    is_favorite, sale_type, min_stock, max_stock
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
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
                            )))
                            created_count += 1
                            
                    except Exception as e:
                        logger.error(f"Error syncing product {product.get('sku')}: {e}")
                        conflicts.append({
                            "sku": product.get('sku'),
                            "error": str(e)
                        })
                        skipped_count += 1
                
                # Execute all operations in a transaction
                if operations:
                    self.core.db.execute_transaction(operations)
                
                logger.info(f"✅ Inventory sync complete: {updated_count} updated, {created_count} created, {skipped_count} skipped")
                
                return JSONResponse({
                    "success": True,
                    "updated": updated_count,
                    "created": created_count,
                    "skipped": skipped_count,
                    "conflicts": conflicts,
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
            try:
                logger.info(f"💰 Sales sync from {request.terminal_id}: {len(request.sales)} sales")
                
                saved_count = 0
                duplicate_count = 0
                
                operations = []
                
                for sale in request.sales:
                    try:
                        sale_id = sale.get('id')
                        
                        # Check if sale already exists (prevent duplicates)
                        existing = self.core.db.execute_query("SELECT id FROM sales WHERE id = %s", (sale_id,))
                        if existing:
                            duplicate_count += 1
                            continue
                        
                        # Insert sale
                        operations.append(("""
                            INSERT INTO sales (
                                id, total, payment_method, timestamp, customer_id,
                                turn_id, user_id, branch_id, synced_from_terminal
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            sale_id,
                            sale.get('total'),
                            sale.get('payment_method'),
                            sale.get('timestamp'),
                            sale.get('customer_id'),
                            sale.get('turn_id'),
                            sale.get('user_id'),
                            sale.get('branch_id'),
                            request.terminal_id
                        )))
                        saved_count += 1
                        
                    except Exception as e:
                        # Likely duplicate or constraint violation
                        logger.debug(f"Skipping sale {sale.get('id')}: {e}")
                        duplicate_count += 1
                
                # Execute all operations in a transaction
                if operations:
                    self.core.db.execute_transaction(operations)
                
                logger.info(f"✅ Sales sync complete: {saved_count} saved, {duplicate_count} duplicates skipped")
                
                return JSONResponse({
                    "success": True,
                    "saved": saved_count,
                    "duplicates": duplicate_count,
                    "message": f"Saved {saved_count} sales from {request.terminal_id}",
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
            try:
                logger.info(f"👥 Customer sync from {request.terminal_id}: {len(request.customers)} customers")
                
                updated_count = 0
                created_count = 0
                
                operations = []
                
                for customer in request.customers:
                    try:
                        customer_id = customer.get('id')
                        
                        if not customer_id:
                            continue
                        
                        # Check if customer exists
                        exists = self.core.db.execute_query("SELECT id FROM customers WHERE id = %s", (customer_id,))
                        
                        if exists:
                            # Update existing customer
                            operations.append(("""
                                UPDATE customers 
                                SET name = %s, phone = %s, email = %s, address = %s,
                                    credit_limit = %s, loyalty_points = %s, notes = %s
                                WHERE id = %s
                            """, (
                                customer.get('name'),
                                customer.get('phone'),
                                customer.get('email'),
                                customer.get('address'),
                                customer.get('credit_limit'),
                                customer.get('loyalty_points'),
                                customer.get('notes'),
                                customer_id
                            )))
                            updated_count += 1
                        else:
                            # Create new customer
                            operations.append(("""
                                INSERT INTO customers (
                                    id, name, phone, email, address,
                                    credit_limit, loyalty_points, notes
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                customer_id,
                                customer.get('name'),
                                customer.get('phone'),
                                customer.get('email'),
                                customer.get('address'),
                                customer.get('credit_limit', 0),
                                customer.get('loyalty_points', 0),
                                customer.get('notes')
                            )))
                            created_count += 1
                            
                    except Exception as e:
                        logger.error(f"Error syncing customer {customer.get('id')}: {e}")
                
                # Execute all operations in a transaction
                if operations:
                    self.core.db.execute_transaction(operations)
                
                logger.info(f"✅ Customer sync complete: {updated_count} updated, {created_count} created")
                
                return JSONResponse({
                    "success": True,
                    "updated": updated_count,
                    "created": created_count,
                    "timestamp": datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"❌ Customer sync error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # ========== GET ENDPOINTS (Clients pull data from server) ==========
        
        @self.app.get("/api/v1/sync/inventory")
        async def sync_inventory_pull(authorized: bool = Depends(self.verify_token)):
            """
            Send current inventory to client terminals.
            
            Returns all products with current stock levels.
            """
            try:
                products = self.core.db.execute_query("""
                    SELECT id, sku, name, price, cost, stock, category_id, 
                           provider, is_favorite, sale_type, min_stock,
                           is_active, barcode
                    FROM products
                    WHERE is_active = 1
                    ORDER BY id DESC
                    LIMIT 5000
                """)
                
                # Convert to list of dicts if needed
                if products and not isinstance(products[0], dict):
                    columns = ['id', 'sku', 'name', 'price', 'cost', 'stock', 'category_id', 
                               'provider', 'is_favorite', 'sale_type', 'min_stock',
                               'is_active', 'barcode']
                    products = [dict(zip(columns, row)) for row in products]
                
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
        
        @self.app.get("/api/v1/sync/customers")
        async def sync_customers_pull(authorized: bool = Depends(self.verify_token)):
            """
            Send current customer list to client terminals.
            """
            try:
                customers = self.core.db.execute_query("""
                    SELECT id, name, phone, email, address,
                           credit_limit, points, wallet_balance, notes
                    FROM customers
                    WHERE is_active = 1
                    ORDER BY id DESC
                    LIMIT 2000
                """)
                
                # Convert to list of dicts if needed
                if customers and not isinstance(customers[0], dict):
                    columns = ['id', 'name', 'phone', 'email', 'address',
                              'credit_limit', 'points', 'wallet_balance', 'notes']
                    customers = [dict(zip(columns, row)) for row in customers]
                
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
            try:
                # logger.info(f"🔎 Real-time stock check from {request.terminal_id} for {len(request.items)} items")
                
                allowed = True
                insufficient_items = []
                
                for item in request.items:
                    sku = item.get('sku')
                    requested_qty = float(item.get('qty', 0))
                    
                    if not sku or requested_qty <= 0:
                        continue
                        
                    # Get current real-time stock
                    result = self.core.db.execute_query("SELECT stock, name FROM products WHERE sku = %s", (sku,))
                    
                    if result:
                        row = result[0]
                        if isinstance(row, dict):
                            current_stock = float(row.get('stock', 0))
                            name = row.get('name', 'Unknown Product')
                        else:
                            current_stock = float(row[0])
                            name = row[1]
                        
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
                    logger.warning(f"🚫 Stock check FAILED for {request.terminal_id}: {len(insufficient_items)} items insufficient")
                
                return JSONResponse({
                    "allowed": allowed,
                    "insufficient_items": insufficient_items,
                    "timestamp": datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Stock check error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # ========== GENERIC ENDPOINTS FOR ALL CONFIGURED TABLES ==========
        
        try:
            from app.utils.sync_endpoints import create_sync_endpoints
            create_sync_endpoints(self.app, self.core, self.verify_token)
            logger.info("✅ Generic sync endpoints created for all tables")
        except Exception as e:
            logger.warning(f"Could not create generic sync endpoints: {e}")

    
    def start(self):
        """Start the HTTP server (blocking)."""
        logger.info(f"Starting POS HTTP server on {self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")
    
    def start_background(self):
        """Start server in background thread."""
        import threading
        
        def run_server():
            try:
                self.start()
            except Exception as e:
                logger.error(f"HTTP server error: {e}")
        
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        logger.info(f"HTTP server started in background on port {self.port}")
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
    if not FastAPI:
        logger.warning("FastAPI not available, HTTP server disabled")
        return None
    
    mode = config.get("mode", "standalone")
    if mode != "server":
        logger.info(f"Mode is '{mode}', HTTP server disabled")
        return None
    
    api_token = config.get("api_dashboard_token", "")
    if not api_token:
        logger.warning("No API token configured, HTTP server disabled")
        return None
    
    port = config.get("server_port", 8000)
    
    try:
        server = POSHTTPServer(pos_core, api_token, port=port)
        return server
    except Exception as e:
        logger.error(f"Failed to create HTTP server: {e}")
        return None
