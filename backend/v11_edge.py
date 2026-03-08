import json, urllib.request, urllib.error
import concurrent.futures
from scripts_runtime import load_runtime

runtime = load_runtime()

def get_token():
    payload = json.dumps(
        {"username": runtime.username, "password": runtime.password}
    ).encode()
    req = urllib.request.Request(
        runtime.api_url("/api/v1/auth/login"),
        method="POST",
        data=payload,
        headers={'Content-Type': 'application/json'},
    )
    try:
        return json.loads(urllib.request.urlopen(req).read().decode())['access_token']
    except Exception as e:
        print("Login failed", e)
        return None

token = get_token()

def post(path, data):
    r = urllib.request.Request(
        runtime.api_url(path),
        method="POST",
        data=json.dumps(data).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'},
    )
    try: 
        res = json.loads(urllib.request.urlopen(r).read().decode())
        return {"status": 200, "data": res}
    except urllib.error.HTTPError as e: 
        return {"status": e.code, "error": json.loads(e.read().decode())}
    except Exception as e:
        return {"status": 500, "error": str(e)}

def search_products(query):
    r = urllib.request.Request(
        runtime.api_url(f"/api/v1/products/?search={urllib.parse.quote(query)}&limit=100"),
        headers={'Authorization': f'Bearer {token}'},
    )
    try: return {"status": 200, "data": json.loads(urllib.request.urlopen(r).read().decode())}
    except urllib.error.HTTPError as e: return {"status": e.code, "error": e.read().decode()}
    except Exception as e: return {"status": 500, "error": str(e)}

def choose_sellable_product():
    prod_res = search_products("")
    products = prod_res.get('data', {}).get('data', [])
    if not isinstance(products, list):
        return None, "La respuesta de productos no devolvió una lista."

    for product in products:
        try:
            if int(product.get('is_active', 1)) != 1:
                continue
            if float(product.get('stock') or 0) <= 0:
                continue
            price = float(product.get('price') or 0)
            if price <= 0:
                continue
            return product, None
        except Exception:
            continue
    return None, "No se encontró un producto activo con stock y precio válidos."

print("\n--- EDGE CASE 1: Busqueda MASIVA con Payload (SQLi/XSS) Concurrente ---")
# Simular 50 peticiones simultáneas con basura unicode/SQLí
payload = "'; DROP TABLE users; -- \x00 <script> ñññ"
with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
    futures = [executor.submit(search_products, payload) for _ in range(50)]
    results_search = [f.result() for f in futures]

status_codes = [r['status'] for r in results_search]
print(f"Búsquedas lanzadas: 50. Códigos devueltos: {set(status_codes)}")
print("Ejemplo Respuesta:", results_search[0].get('error') or "Success (Array Vacio esperado)")

print("\n--- EDGE CASE 2: Race Condition en Turnos (Apertura Múltiple del mismo cajero) ---")
# Intentamos abrir 20 turnos exactos simultaneamente a ver si la base de datos permite registros duplicados en estado 'open'
with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
    futures = [
        executor.submit(
            post,
            '/api/v1/turns/open',
            {"initial_cash": 100, "branch_id": runtime.branch_id},
        )
        for _ in range(20)
    ]
    results_turns = [f.result() for f in futures]

success_turns = [r for r in results_turns if r['status'] == 200 and r.get('data', {}).get('success')]
error_turns = [r for r in results_turns if r['status'] != 200]
print(f"Turnos iniciados con éxito: {len(success_turns)}")
print(f"Peticiones rechazadas por validación (Esperando 19): {len(error_turns)}")
if error_turns:
    print("Ejemplo Reclamo:", error_turns[0]['error'])

print("\n--- EDGE CASE 3: Race Condition en Ventas Concurrentes Extrema (10 Cobros en paralelo del MISMO carrito) ---")
# Elegir un producto realmente vendible para evitar falsos negativos.
product, product_error = choose_sellable_product()
if not product:
    print(f"No hay productos para testear ventas. Motivo: {product_error}")
else:
    pid = product['id']
    price = float(product['price'])
    sale_payload = {
        "items": [{"product_id": pid, "qty": 1, "price": price, "discount": 0, "is_wholesale": False, "price_includes_tax": True}],
        "payment_method": "cash", "cash_received": price, "branch_id": runtime.branch_id
    }
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(post, '/api/v1/sales/', sale_payload) for _ in range(10)]
        results_sales = [f.result() for f in futures]
    
    success_sales = [r for r in results_sales if r['status'] == 200]
    client_errors = [r for r in results_sales if 400 <= r['status'] < 500]
    server_errors = [r for r in results_sales if r['status'] >= 500]
    print(f"Producto elegido: {product.get('name', product.get('description', pid))} (stock={product.get('stock')}, price={price})")
    print(f"Ventas procesadas 200 OK: {len(success_sales)}")
    print(f"Ventas rechazadas 4XX: {len(client_errors)}")
    print(f"Ventas fallidas 5XX: {len(server_errors)}")
    if client_errors:
        print("Ejemplo error 4XX:", client_errors[0].get('error'))
    if server_errors:
        print("Ejemplo error 5XX:", server_errors[0].get('error'))
    
print("\nPentest V11 completado.")
