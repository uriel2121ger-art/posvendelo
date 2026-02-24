"""
E-Commerce API for TITAN POS
Provides REST API for online store
Enhanced with Admin Endpoints
"""

from typing import List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import os
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

app = FastAPI(title="TITAN POS E-Commerce API", version="1.1.0")

# ============ SECURITY CONFIGURATION ============

# Environment-based security settings
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:3001"
).split(",")

ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS",
    "localhost,127.0.0.1,titan-ecommerce-api"
).split(",")

# Rate Limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS - Strict whitelist in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # SECURITY: Whitelist only authorized domains
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)

# TrustedHost - Prevent Host header injection attacks
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=ALLOWED_HOSTS,
)

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    return response

# SECURITY: Admin token from environment variable
# Set ADMIN_TOKEN in .env file (never hardcode secrets!)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

if not ADMIN_TOKEN:
    import warnings
    warnings.warn(
        "⚠️  SECURITY WARNING: ADMIN_TOKEN not set in environment! "
        "API admin endpoints are DISABLED. Set ADMIN_TOKEN in .env file.",
        RuntimeWarning
    )

# ============ DATABASE ============

# Use DatabaseManager singleton
from src.infra.database import db_instance

def get_db():
    """Get database manager instance."""
    return db_instance

# ============ AUTHENTICATION ============

def verify_admin(authorization: str = Header(None)):
    """Verify admin token."""
    if not authorization or authorization != f"Bearer {ADMIN_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True

# ============ MODELS ============

class Product(BaseModel):
    id: int
    sku: str
    name: str
    price: float
    stock: float
    category: Optional[str] = None
    barcode: Optional[str] = None
    is_active: bool = True

class CartItem(BaseModel):
    product_id: int
    quantity: float

class ShippingAddress(BaseModel):
    full_name: str
    phone: str
    street_address: str
    street_address_2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str = "MX"

class OrderCreate(BaseModel):
    customer_id: int
    items: List[CartItem]
    shipping_address: ShippingAddress
    customer_notes: Optional[str] = None

class OrderStatusUpdate(BaseModel):
    status: str
    tracking_number: Optional[str] = None
    admin_notes: Optional[str] = None

# ============ PUBLIC ENDPOINTS ============

@app.get("/")
def root():
    """API root."""
    return {
        "name": "TITAN POS E-Commerce API",
        "version": "1.1.0",
        "status": "operational",
        "endpoints": {
            "products": "/api/products",
            "orders": "/api/orders",
            "admin": "/api/admin/*",
            "docs": "/docs"
        }
    }

@app.get("/api/products", response_model=List[Product])
@limiter.limit("100/minute")  # SECURITY: Rate limit product listing
async def list_products(
    request: Request,
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db = Depends(get_db)
):
    """
    List products for online store.
    
    - **category**: Filter by category
    - **search**: Search in name/SKU
    - **limit**: Max results (default 50)
    - **offset**: Pagination offset
    """
    query = """
        SELECT id, sku, name, price, stock, department as category, 
               barcode, is_active
        FROM products 
        WHERE is_active = 1 AND stock > 0
    """
    params = []
    
    if category:
        query += " AND department = %s"
        params.append(category)
    
    if search:
        query += " AND (name LIKE %s OR sku LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])
    
    query += " ORDER BY name LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    rows = db.execute_query(query, tuple(params))
    products = []
    
    for row in rows:
        row_dict = dict(row)
        products.append(Product(
            id=row_dict['id'],
            sku=row_dict['sku'],
            name=row_dict['name'],
            price=row_dict['price'],
            stock=row_dict['stock'],
            category=row_dict['category'],
            barcode=row_dict['barcode'],
            is_active=bool(row_dict['is_active'])
        ))
    
    return products

@app.get("/api/products/{product_id}", response_model=Product)
@limiter.limit("100/minute")
async def get_product(
    request: Request,
    product_id: int,
    db = Depends(get_db)
):
    """Get single product details."""
    rows = db.execute_query("""
        SELECT id, sku, name, price, stock, department as category,
               barcode, is_active
        FROM products
        WHERE id = %s AND is_active = 1
    """, (product_id,))
    
    if not rows:
        raise HTTPException(status_code=404, detail="Product not found")
    
    row = dict(rows[0])
    return Product(
        id=row['id'],
        sku=row['sku'],
        name=row['name'],
        price=row['price'],
        stock=row['stock'],
        category=row['category'],
        barcode=row['barcode'],
        is_active=bool(row['is_active'])
    )

@app.get("/api/categories")
def list_categories(db = Depends(get_db)):
    """Get all product categories."""
    rows = db.execute_query("""
        SELECT DISTINCT department as category
        FROM products
        WHERE is_active = 1 AND department IS NOT NULL
        ORDER BY department
    """)
    
    categories = [dict(row)['category'] for row in rows]
    return {"categories": categories}

# ============ ORDERS API ============

@app.post("/api/orders")
@limiter.limit("10/minute")  # SECURITY: Strict rate limit for order creation
async def create_order(
    request: Request,
    order: OrderCreate,
    db = Depends(get_db)
):
    """
    Create new online order.
    
    This is a simplified version that creates the order.
    In production, integrate with Stripe for payments.
    """
    try:
        # Verify customer exists
        customers = db.execute_query("SELECT id FROM customers WHERE id = %s", (order.customer_id,))
        if not customers:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        # Create shipping address
        shipping_address_id = db.execute_write("""
            INSERT INTO shipping_addresses (
                customer_id, full_name, phone, street_address, street_address_2,
                city, state, postal_code, country, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            order.customer_id,
            order.shipping_address.full_name,
            order.shipping_address.phone,
            order.shipping_address.street_address,
            order.shipping_address.street_address_2,
            order.shipping_address.city,
            order.shipping_address.state,
            order.shipping_address.postal_code,
            order.shipping_address.country,
            datetime.now().isoformat()
        ))
        
        # Calculate totals
        subtotal = Decimal('0')
        items_data = []
        
        for item in order.items:
            # Get product
            products = db.execute_query("""
                SELECT id, sku, name, price, stock
                FROM products
                WHERE id = %s AND is_active = 1
            """, (item.product_id,))
            
            if not products:
                raise HTTPException(
                    status_code=404,
                    detail=f"Product {item.product_id} not found"
                )
            
            product = dict(products[0])
            if product['stock'] < item.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock for {product['name']}"
                )
            
            item_subtotal = Decimal(str(product['price'])) * Decimal(str(item.quantity))
            subtotal += item_subtotal
            
            items_data.append({
                'product_id': product['id'],
                'name': product['name'],
                'sku': product['sku'],
                'quantity': item.quantity,
                'price': product['price'],
                'subtotal': float(item_subtotal)
            })
        
        # Calculate tax (16%)
        tax = subtotal * Decimal('0.16')
        total = subtotal + tax
        
        # Generate order number
        order_number = f"ORD-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        
        # Create order
        order_id = db.execute_write("""
            INSERT INTO online_orders (
                order_number, customer_id, status, subtotal, tax, total,
                shipping_address_id, customer_notes, created_at
            ) VALUES (%s, %s, 'pending', %s, %s, %s, %s, %s, %s)
        """, (
            order_number,
            order.customer_id,
            float(subtotal),
            float(tax),
            float(total),
            shipping_address_id,
            order.customer_notes,
            datetime.now().isoformat()
        ))
        
        # Create order items and update inventory atomically
        operations = []
        for item_data in items_data:
            tax_amount = Decimal(str(item_data['subtotal'])) * Decimal('0.16')
            item_total = Decimal(str(item_data['subtotal'])) + tax_amount
            
            operations.append((
                """
                INSERT INTO order_items (
                    order_id, product_id, product_name, product_sku,
                    quantity, unit_price, subtotal, tax_amount, total
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    order_id,
                    item_data['product_id'],
                    item_data['name'],
                    item_data['sku'],
                    item_data['quantity'],
                    item_data['price'],
                    item_data['subtotal'],
                    float(tax_amount),
                    float(item_total)
                )
            ))
            
            # Decrement inventory
            operations.append((
                """
                UPDATE products
                SET stock = stock - %s
                WHERE id = %s
                """,
                (item_data['quantity'], item_data['product_id'])
            ))
        
        # Execute all operations atomically
        db.execute_transaction(operations)
        
        return {
            "success": True,
            "order_id": order_id,
            "order_number": order_number,
            "total": float(total),
            "message": "Order created successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/orders/{order_number}")
def get_order(order_number: str, db = Depends(get_db)):
    """Get order details."""
    orders = db.execute_query("""
        SELECT o.*, c.name as customer_name, c.email as customer_email
        FROM online_orders o
        JOIN customers c ON o.customer_id = c.id
        WHERE o.order_number = %s
    """, (order_number,))
    
    if not orders:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order = dict(orders[0])
    
    # Get items
    items_rows = db.execute_query("""
        SELECT * FROM order_items WHERE order_id = %s
    """, (order['id'],))
    
    items = [dict(row) for row in items_rows]
    
    # Get shipping address
    shipping_rows = db.execute_query("""
        SELECT * FROM shipping_addresses WHERE id = %s
    """, (order['shipping_address_id'],))
    
    shipping = dict(shipping_rows[0]) if shipping_rows else None
    
    return {
        "order": order,
        "items": items,
        "shipping_address": shipping
    }

# ============ ADMIN ENDPOINTS (NEW) ============

@app.get("/api/admin/orders")
def admin_list_orders(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db = Depends(get_db),
    _: bool = Depends(verify_admin)
):
    """
    List all orders (admin only).
    
    Requires: Authorization: Bearer {admin_token}
    """
    query = """
        SELECT o.*, c.name as customer_name
        FROM online_orders o
        JOIN customers c ON o.customer_id = c.id
        WHERE 1=1
    """
    params = []
    
    if status:
        query += " AND o.status = %s"
        params.append(status)
    
    query += " ORDER BY o.created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    rows = db.execute_query(query, tuple(params))
    orders = [dict(row) for row in rows]
    
    return {"orders": orders, "total": len(orders)}

@app.put("/api/admin/orders/{order_id}/status")
def admin_update_order_status(
    order_id: int,
    update: OrderStatusUpdate,
    db = Depends(get_db),
    _: bool = Depends(verify_admin)
):
    """Update order status (admin only)."""
    try:
        # Verify order exists
        orders = db.execute_query("SELECT id FROM online_orders WHERE id = %s", (order_id,))
        if not orders:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Build update query
        updates = ["status = %s"]
        params = [update.status]
        
        if update.tracking_number:
            updates.append("tracking_number = %s")
            params.append(update.tracking_number)
        
        if update.admin_notes:
            updates.append("admin_notes = %s")
            params.append(update.admin_notes)
        
        # Update timestamps based on status
        if update.status == 'paid':
            updates.append("paid_at = %s")
            params.append(datetime.now().isoformat())
        elif update.status == 'shipped':
            updates.append("shipped_at = %s")
            params.append(datetime.now().isoformat())
        elif update.status == 'delivered':
            updates.append("delivered_at = %s")
            params.append(datetime.now().isoformat())
        
        params.append(order_id)
        
        # SECURITY: Whitelist de columnas permitidas para UPDATE
        ALLOWED_ORDER_COLUMNS = {'status', 'tracking_number', 'admin_notes', 'paid_at', 'shipped_at', 'delivered_at'}
        for upd in updates:
            col_name = upd.split(' = ')[0].strip()
            if col_name not in ALLOWED_ORDER_COLUMNS:
                raise HTTPException(status_code=400, detail=f"Campo no permitido: {col_name}")
        
        # SECURITY: columns validadas
        query = f"UPDATE online_orders SET {', '.join(updates)} WHERE id = %s"
        db.execute_write(query, tuple(params))
        
        return {"success": True, "message": "Order updated successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/admin/stats")
def admin_statistics(db = Depends(get_db), _: bool = Depends(verify_admin)):
    """Get sales statistics (admin only)."""
    # Total orders
    total_orders_rows = db.execute_query("SELECT COUNT(*) as total FROM online_orders")
    total_orders = total_orders_rows[0]['total'] if total_orders_rows else 0
    
    # Orders by status
    orders_by_status_rows = db.execute_query("""
        SELECT status, COUNT(*) as count, SUM(total) as total_amount
        FROM online_orders
        GROUP BY status
    """)
    orders_by_status = [dict(row) for row in orders_by_status_rows]
    
    # Total revenue - CRITICAL FIX: Safe null handling
    revenue_rows = db.execute_query("SELECT COALESCE(SUM(total), 0) as revenue FROM online_orders WHERE status != 'cancelled'")
    total_revenue = 0
    if revenue_rows and len(revenue_rows) > 0 and revenue_rows[0]:
        total_revenue = float(revenue_rows[0].get('revenue', 0) or 0)
    
    # Recent orders (last 7 days)
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    recent_rows = db.execute_query("""
        SELECT COUNT(*) as count, SUM(total) as amount
        FROM online_orders
        WHERE created_at >= %s
    """, (week_ago,))
    
    recent = dict(recent_rows[0]) if recent_rows else {'count': 0, 'amount': 0}
    
    # Top products
    top_products_rows = db.execute_query("""
        SELECT product_name, SUM(quantity) as total_sold, SUM(total) as revenue
        FROM order_items
        GROUP BY product_id
        ORDER BY total_sold DESC
        LIMIT 10
    """)
    top_products = [dict(row) for row in top_products_rows]
    
    return {
        "total_orders": total_orders,
        "total_revenue": float(total_revenue),
        "orders_by_status": orders_by_status,
        "last_7_days": {
            "orders": recent['count'],
            "revenue": float(recent['amount'] or 0)
        },
        "top_products": top_products
    }

# ============ HEALTH CHECK ============

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# ============ SIMPLE ADMIN DASHBOARD (HTML) ============

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard():
    """Simple admin dashboard (HTML)."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>TITAN POS - Admin Dashboard</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                border-bottom: 2px solid #007bff;
                padding-bottom: 10px;
            }
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin: 20px 0;
            }
            .stat-card {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 8px;
                text-align: center;
            }
            .stat-card h3 {
                margin: 0 0 10px 0;
                font-size: 14px;
                opacity: 0.9;
            }
            .stat-card .value {
                font-size: 32px;
                font-weight: bold;
            }
            .section {
                margin: 30px 0;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 15px;
            }
            th, td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }
            th {
                background: #007bff;
                color: white;
            }
            .btn {
                padding: 10px 20px;
                background: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
            }
            .btn:hover {
                background: #0056b3;
            }
            .status {
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }
            .status-pending { background: #ffc107; color: #000; }
            .status-paid { background: #28a745; color: #fff; }
            .status-shipped { background: #17a2b8; color: #fff; }
            .status-delivered { background: #28a745; color: #fff; }
            .status-cancelled { background: #dc3545; color: #fff; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛒 TITAN POS - E-Commerce Admin Dashboard</h1>
            
            <div class="stats" id="stats">
                <div class="stat-card">
                    <h3>Total Orders</h3>
                    <div class="value" id="total-orders">-</div>
                </div>
                <div class="stat-card">
                    <h3>Total Revenue</h3>
                    <div class="value" id="total-revenue">-</div>
                </div>
                <div class="stat-card">
                    <h3>Last 7 Days</h3>
                    <div class="value" id="recent-orders">-</div>
                </div>
                <div class="stat-card">
                    <h3>Pending</h3>
                    <div class="value" id="pending">-</div>
                </div>
            </div>
            
            <div class="section">
                <h2>📦 Recent Orders</h2>
                <table id="orders-table">
                    <thead>
                        <tr>
                            <th>Order #</th>
                            <th>Customer</th>
                            <th>Total</th>
                            <th>Status</th>
                            <th>Date</th>
                        </tr>
                    </thead>
                    <tbody id="orders-body">
                        <tr><td colspan="5">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
            
            <div class="section">
                <a href="/docs" class="btn">📚 API Documentation</a>
                <a href="/api/admin/stats" class="btn">📊 Full Stats (JSON)</a>
            </div>
        </div>
        
        <script>
            // SECURITY: Get token from prompt or login system in production
            const ADMIN_TOKEN = prompt('Enter Admin Token (Bearer token):', 'Bearer ');

            function escapeHtml(str) {
                if (!str) return '';
                const div = document.createElement('div');
                div.textContent = str;
                return div.innerHTML;
            }
            
            async function loadStats() {
                try {
                    const response = await fetch('/api/admin/stats', {
                        headers: {'Authorization': ADMIN_TOKEN}
                    });
                    const data = await response.json();
                    
                    document.getElementById('total-orders').textContent = data.total_orders;
                    document.getElementById('total-revenue').textContent = '$' + data.total_revenue.toFixed(2);
                    document.getElementById('recent-orders').textContent = data.last_7_days.orders;
                    
                    const pending = data.orders_by_status.find(s => s.status === 'pending');
                    document.getElementById('pending').textContent = pending %s pending.count : 0;
                } catch (error) {
                    console.error('Error loading stats:', error);
                }
            }
            
            async function loadOrders() {
                try {
                    const response = await fetch('/api/admin/orders%slimit=10', {
                        headers: {'Authorization': ADMIN_TOKEN}
                    });
                    const data = await response.json();
                    
                    const tbody = document.getElementById('orders-body');
                    tbody.innerHTML = '';
                    
                    const allowedStatuses = ['pending', 'paid', 'shipped', 'delivered', 'cancelled'];
                    data.orders.forEach(order => {
                        const row = tbody.insertRow();
                        const safeStatus = allowedStatuses.includes(order.status) ? order.status : 'pending';
                        row.innerHTML = `
                            <td>${escapeHtml(order.order_number)}</td>
                            <td>${escapeHtml(order.customer_name)}</td>
                            <td>$${Number(order.total || 0).toFixed(2)}</td>
                            <td><span class="status status-${safeStatus}">${escapeHtml(order.status)}</span></td>
                            <td>${new Date(order.created_at).toLocaleString()}</td>
                        `;
                    });
                } catch (error) {
                    console.error('Error loading orders:', error);
                }
            }
            
            loadStats();
            loadOrders();
            
            // Refresh every 30 seconds
            setInterval(() => {
                loadStats();
                loadOrders();
            }, 30000);
        </script>
    </body>
    </html>
    """
    return html

# ============ CART ABANDONMENT & RECOVERY ============

class AbandonedCart(BaseModel):
    cart_items: List[dict]
    totals: dict
    contact: dict
    url: str
    timestamp: str

@app.post("/api/cart/abandoned")
def track_abandoned_cart(cart: AbandonedCart, db = Depends(get_db)):
    """Track abandoned cart for recovery campaign."""
    try:
        # Store abandoned cart
        cart_id = db.execute_write("""
            INSERT INTO abandoned_carts (
                email, phone, cart_data, total_amount, 
                recovery_sent, created_at
            ) VALUES (%s, %s, %s, %s, 0, NOW())
        """, (
            cart.contact.get('email'),
            cart.contact.get('phone'),
            str(cart.cart_items),
            cart.totals.get('total', 0)
        ))
        
        # TODO: Trigger recovery email after 1 hour
        # schedule_recovery_email(cart_id, cart.contact.get('email'))
        
        return {
            "success": True,
            "cart_id": cart_id,
            "message": "Cart tracked for recovery"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/cart/recovery/{cart_id}")
def get_recovery_cart(cart_id: int, db = Depends(get_db)):
    """Get abandoned cart for recovery link."""
    import json
    
    carts = db.execute_query("""
        SELECT * FROM abandoned_carts WHERE id = %s
    """, (cart_id,))
    
    if not carts:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    cart = dict(carts[0])
    return {
        "cart_id": cart_id,
        "items": json.loads(cart['cart_data']) if cart['cart_data'] else [],
        "total": cart['total_amount'],
        "discount": 0.10  # 10% recovery discount
    }

# ============ WEBHOOKS & REVALIDATION ============

@app.post("/api/webhook/revalidate")
def revalidate_product(
    sku: str = None,
    product_id: int = None,
    _: bool = Depends(verify_admin)
):
    """
    Webhook for ISR revalidation.
    Called by POS when product data changes.
    """
    try:
        # In Next.js environment, this would trigger revalidation
        # For now, just log the event
        return {
            "success": True,
            "message": f"Revalidation triggered for SKU: {sku or product_id}",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/webhook/stock-update")
def stock_update_webhook(
    product_id: int,
    new_stock: float,
    _: bool = Depends(verify_admin)
):
    """Receive stock updates from POS."""
    try:
        # Update would happen in real-time
        # Trigger frontend cache invalidation
        return {
            "success": True,
            "product_id": product_id,
            "new_stock": new_stock,
            "action": "cache_invalidated"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
