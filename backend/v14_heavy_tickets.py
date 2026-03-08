import json, urllib.request, urllib.error
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
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

def open_turn():
    req = urllib.request.Request(
        runtime.api_url("/api/v1/turns/open"),
        method="POST",
        data=json.dumps({"initial_cash": 100, "branch_id": runtime.branch_id}).encode(),
        headers=headers,
    )
    try:
        urllib.request.urlopen(req)
        print("Turno re-abierto o inicializado correctamente.")
    except Exception:
        pass # Turno ya abierto

def create_product(i):
    prefix = "HEAVY"
    payload = {
        "sku": f"{prefix}-{i:03d}",
        "name": f"Producto Test V14 #{i}",
        "price": 10.0 + i,
        "cost": 5.0,
        "stock": 5000,
        "tax_rate": 0.16,
        "is_active": 1,
        "sat_clave_prod_serv": "01010101",
        "sat_clave_unidad": "H87"
    }
    req = urllib.request.Request(
        runtime.api_url("/api/v1/products/"),
        method="POST",
        data=json.dumps(payload).encode(),
        headers=headers,
    )
    try:
        res = urllib.request.urlopen(req)
        pd = json.loads(res.read().decode())['data']
        # if the created product is directly in data
        if "id" in pd: return pd
        return None
    except urllib.error.HTTPError as e:
        if e.code == 400: # Probably already exists, let's fetch it
            req_s = urllib.request.Request(
                runtime.api_url(f"/api/v1/products/?search={prefix}-{i:03d}&limit=1"),
                headers=headers,
            )
            res_s = json.loads(urllib.request.urlopen(req_s).read().decode())
            if "data" in res_s and isinstance(res_s["data"], list) and len(res_s["data"]) > 0:
                return res_s["data"][0]
        print(f"Error creando producto #{i}: {e.read().decode()}")
        return None

open_turn()

print("Verificando/Creando 50 Productos Únicos con precios distintos...")
products = []
for i in range(1, 51):
    p = create_product(i)
    if p:
        products.append(p)
    else:
        print(f"Fallo al obtener producto target {i}")

if len(products) < 50:
    print(f"Precaución: Sólo se obtuvieron {len(products)} productos.")

print(f"\nArmando el 'Ticket Pesado' con {len(products)} items distintos...")
items = []
total_cobro = 0
for p in products:
    price = float(p['price'])
    items.append({
        "product_id": p['id'],
        "qty": 1,
        "price": price,
        "discount": 0,
        "is_wholesale": False,
        "price_includes_tax": True
    })
    total_cobro += price

sale_payload = {
    "items": items,
    "payment_method": "cash",
    "cash_received": total_cobro,
    "branch_id": runtime.branch_id
}

print(f"El ticket pesará {len(items)} líneas. Total a cobrar: ${total_cobro:.2f}")
print("Procesando 50 ventas (Simulación Manual / Secuencial)...")

success = 0
errors = 0
start_time = time.time()

for i in range(1, 51):
    req = urllib.request.Request(
        runtime.api_url("/api/v1/sales/"),
        method="POST",
        data=json.dumps(sale_payload).encode(),
        headers=headers,
    )
    try: 
        res = urllib.request.urlopen(req)
        if res.status == 200:
            success += 1
            if i % 10 == 0:
                print(f" -> Venta #{i} despachada con éxito.")
    except urllib.error.HTTPError as e: 
        errors += 1
        print(f" -> Venta #{i} falló: {e.read().decode()}")
    except Exception as e:
        errors += 1
        print(f" -> Venta #{i} falló críticamente: {e}")

end_time = time.time()
print(f"\n✅ PRUEBA V14 COMPLETADA en {end_time - start_time:.2f} segundos.")
print(f"Ventas Exitosas: {success} / 50")
print(f"Errores (Timeouts/Validación): {errors}")
