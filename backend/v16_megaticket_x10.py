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
    return json.loads(urllib.request.urlopen(req).read().decode())['access_token']

token = get_token()
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

def open_turn():
    req = urllib.request.Request(
        runtime.api_url("/api/v1/turns/open"),
        method="POST",
        data=json.dumps({"initial_cash": 100, "branch_id": runtime.branch_id}).encode(),
        headers=headers,
    )
    try: urllib.request.urlopen(req)
    except Exception: pass

open_turn()

# Recuperar los 50 productos HEAVY creados en V14
print("Recuperando los 50 productos 'HEAVY' del catálogo...")
items = []
total_cobro = 0

req_s = urllib.request.Request(
    runtime.api_url("/api/v1/products/?search=HEAVY-&limit=50"),
    headers=headers,
)
res_s = json.loads(urllib.request.urlopen(req_s).read().decode())
products = []
if "data" in res_s and isinstance(res_s["data"], list):
    products = res_s["data"]
elif "data" in res_s and isinstance(res_s["data"], dict) and "data" in res_s["data"]:
    products = res_s["data"]["data"]

if len(products) < 50:
    print(f"Advertencia: Sólo se encontraron {len(products)} productos HEAVY. Ejecute V14 primero.")

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

if total_cobro == 0:
    print("El ticket está vacío. Abortando.")
    exit(1)

print(f"Ticket armado con {len(items)} líneas. Total: ${total_cobro:.2f}")

payment_methods = ["cash", "card", "transfer", "mixed"]

TOTAL_SALES = 500
success = 0
errors = 0

print(f"\n🚀 PROCESANDO {TOTAL_SALES} VENTAS PESADAS (TOTAL {TOTAL_SALES * len(items)} ITEMS)")
start_time = time.time()

for i in range(1, TOTAL_SALES + 1):
    pm = payment_methods[i % len(payment_methods)]
    
    sale_payload = {
        "items": items,
        "payment_method": pm,
        "cash_received": total_cobro,
        "branch_id": runtime.branch_id
    }
    
    if pm == "mixed":
        half = round(total_cobro / 2, 2)
        other_half = total_cobro - half
        sale_payload["mixed_cash"] = half
        sale_payload["mixed_card"] = other_half
    elif pm == "transfer":
        sale_payload["transfer_reference"] = f"SPEI-{i}"
    elif pm == "card":
        sale_payload["card_reference"] = f"VISA-{i}"
    
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
            if i % 50 == 0:
                print(f" -> Venta #{i} despachada (Método: {pm}).")
    except urllib.error.HTTPError as e: 
        errors += 1
        print(f" -> Venta #{i} falló: {e.read().decode()}")
    except Exception as e:
        errors += 1
        print(f" -> Venta #{i} falló críticamente: {e}")

end_time = time.time()
print(f"\n✅ PRUEBA V16 COMPLETADA en {end_time - start_time:.2f} segundos.")
print(f"Ventas Exitosas: {success} / {TOTAL_SALES}")
print(f"Errores: {errors}")
