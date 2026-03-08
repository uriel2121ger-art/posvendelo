import json
import os
import random
import urllib.error
import urllib.request

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
API_USER = os.environ.get("API_USER", "admin")
API_PASSWORD = os.environ.get("API_PASSWORD", "")

if not API_PASSWORD:
    raise SystemExit("Define API_PASSWORD antes de ejecutar este script.")

login_payload = json.dumps({"username": API_USER, "password": API_PASSWORD}).encode()
req = urllib.request.Request(
    f"{BASE_URL}/api/v1/auth/login",
    method="POST",
    data=login_payload,
    headers={"Content-Type": "application/json"},
)
token = json.loads(urllib.request.urlopen(req).read().decode())["access_token"]

def post(path, data):
    r = urllib.request.Request(
        BASE_URL + path,
        method="POST",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    try: return json.loads(urllib.request.urlopen(r).read().decode())
    except urllib.error.HTTPError as e: return json.loads(e.read().decode())

def delete(path):
    r = urllib.request.Request(BASE_URL + path, method="DELETE", headers={"Authorization": f"Bearer {token}"})
    try: return json.loads(urllib.request.urlopen(r).read().decode())
    except urllib.error.HTTPError as e: return json.loads(e.read().decode())

print("\n--- TEST 3: ELIMINACIÓN HUÉRFANA DE CLIENTE CON VENTAS ---")
cust = post('/api/v1/customers/', {"name": "Orphan Test " + str(random.randint(1000,9999)), "rfc": "XAXX010101000"})
cid = cust.get('data', {}).get('id') if 'data' in cust else cust.get('id')

prod = post('/api/v1/products/', {"sku": "MONKEY" + str(random.randint(1000,9999)), "name": "Monkey Prod", "price": 9.99, "stock": 100, "category_id": 1, "track_stock": True})
pid = prod.get('data', {}).get('id') if 'data' in prod else prod.get('id')

if cid and pid:
    s = post('/api/v1/sales/', {
        "items": [{"product_id": pid, "name": "Orphan Prod", "qty": 1, "price": 1.0, "discount": 0, "is_wholesale": False, "price_includes_tax": True}],
        "payment_method": "cash", "cash_received": 1.0, "customer_id": cid, "branch_id": 1
    })
    print("Venta exitosa para CID", cid)
    del_res = delete(f'/api/v1/customers/{cid}')
    print("Resultado intentando borrar cliente ligado:")
    print(json.dumps(del_res, indent=2))
