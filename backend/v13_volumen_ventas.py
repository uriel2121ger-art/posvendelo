import json, urllib.request, urllib.error
import concurrent.futures
import time
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

def get_product():
    req = urllib.request.Request(
        runtime.api_url("/api/v1/products/?limit=200"),
        headers={'Authorization': f'Bearer {token}'},
    )
    try:
        res = json.loads(urllib.request.urlopen(req).read().decode())
        if "data" in res and isinstance(res["data"], list):
            for product in res["data"]:
                try:
                    if float(product.get("stock") or 0) <= 0:
                        continue
                    if float(product.get("price") or 0) <= 0:
                        continue
                    if int(product.get("is_active", 1)) != 1:
                        continue
                    return product
                except Exception:
                    continue
    except Exception as e:
        print("Fallo al obtener producto:", e)
    return None

def open_turn():
    req = urllib.request.Request(
        runtime.api_url("/api/v1/turns/open"),
        method="POST",
        data=json.dumps({"initial_cash": 100, "branch_id": runtime.branch_id}).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'},
    )
    try:
        urllib.request.urlopen(req)
        print("Turno abierto para las pruebas.")
    except urllib.error.HTTPError as e:
        if e.code == 400: # Ya hay turno abierto
            print("Turno ya estaba abierto, excelente.")
        else:
            print("Fallo abriendo turno:", e.read().decode())
    except Exception as e:
        print("Excepcion abriendo turno:", e)

def make_sale(payload):
    req = urllib.request.Request(
        runtime.api_url("/api/v1/sales/"),
        method="POST",
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'},
    )
    try: 
        res = urllib.request.urlopen(req)
        return {"status": res.status}
    except urllib.error.HTTPError as e: 
        return {"status": e.code, "error": e.read().decode()}
    except Exception as e:
        return {"status": 500, "error": str(e)}


print("Preparando el entorno para el ataque de 10,000 ventas...")
open_turn()
product = get_product()

if not product:
    print("No hay productos en la base de datos para vender. Abortando.")
    exit(1)

# Aseguramos que el producto tenga id y precio válidos
pid = product['id']
price = product['price']

sale_payload = {
    "items": [{
        "product_id": pid, 
        "qty": 1, 
        "price": price, 
        "discount": 0, 
        "is_wholesale": False, 
        "price_includes_tax": True
    }],
    "payment_method": "cash", 
    "cash_received": price, 
    "branch_id": runtime.branch_id
}

TOTAL_SALES = 10000
CONCURRENCY = 150  # 150 hilos empujando ventas al mismo tiempo

print(f"\n🚀 FASE DE VOLUMEN V13: Procesando {TOTAL_SALES} VENTAS CONCURRENTES")
print(f"Producto Objetivo: {product.get('name') or product.get('description') or pid} (ID: {pid})")
print(f"Hilos Concurrentes: {CONCURRENCY}")
print("Iniciando inyección (esto puede tomar varios segundos o minutos, PostgreSQL estará bajo estrés máximo)...")

start_time = time.time()

with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
    futures = [executor.submit(make_sale, sale_payload) for _ in range(TOTAL_SALES)]
    
    # Simple progress tracker
    results = []
    for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
        results.append(future.result())
        if i % 1000 == 0:
            print(f"[{i}/{TOTAL_SALES}] Ventas enviadas... ({(time.time() - start_time):.2f}s transcurridos)")

end_time = time.time()
total_time = end_time - start_time

statuses = [r["status"] for r in results]
success_count = statuses.count(200)
client_err_count = sum(1 for s in statuses if 400 <= s < 500)
server_err_count = sum(1 for s in statuses if s >= 500)

print("\n================================================")
print(f"🏁 RESULTADOS DEL TEST DE CARGA (10,000 VENTAS)")
print("================================================")
print(f"⏱️ Tiempo Total        : {total_time:.2f} segundos")
if total_time > 0:
    print(f"⚡ Velocidad Transacc  : {(TOTAL_SALES / total_time):.2f} ventas por segundo (TPS)")
print(f"✅ Ventas Exitosas     : {success_count} (200 OK)")
print(f"⚠️ Errores Validación  : {client_err_count} (4XX)")
print(f"❌ Errores Críticos    : {server_err_count} (5XX Deadlocks / Connection Drops)")

if server_err_count > 0:
    print("\nDetalle del primer error de servidor/cliente para diagnóstico:")
    errs = [r for r in results if r["status"] != 200]
    if errs:
        print(errs[0])
else:
    print("\n🥇 PostgreSQL y FastAPI procesaron el bloque masivo sin corromper conexiones o crear deadlocks.")
