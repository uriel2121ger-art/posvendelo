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

def make_req(url, method="GET", payload=None):
    headers = {'Authorization': f'Bearer {token}'}
    data = None
    if payload:
        data = json.dumps(payload).encode()
        headers['Content-Type'] = 'application/json'
    
    req = urllib.request.Request(runtime.api_url(url), method=method, data=data, headers=headers)
    try: 
        res = urllib.request.urlopen(req)
        return {"status": res.status, "url": url}
    except urllib.error.HTTPError as e: 
        return {"status": e.code, "url": url}
    except Exception as e:
        return {"status": 500, "url": url}

endpoints = [
    {"url": "/api/v1/products/?limit=1", "method": "GET", "payload": None},
    {"url": "/api/v1/customers/?limit=1", "method": "GET", "payload": None},
    {"url": "/api/v1/inventory/movements?limit=1", "method": "GET", "payload": None},
    {"url": "/api/v1/dashboard/quick", "method": "GET", "payload": None},
    {"url": "/api/v1/sales/search?limit=1", "method": "GET", "payload": None},
    # Intencionalmente una ruta de error (fake POST) para probar tolerancia a 422/500
    {"url": "/api/v1/sales/", "method": "POST", "payload": {"items": []}} 
]

CALLS_PER_ENDPOINT = 500

print(f"\n🚀 FASE 1: ATAQUE INDIVIDUAL ({CALLS_PER_ENDPOINT} llamadas x endpoint)")
for ep in endpoints:
    url = ep["url"]
    print(f"Atacando {url} con {CALLS_PER_ENDPOINT} hilos concurrentes...")
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(make_req, url, ep["method"], ep["payload"]) for _ in range(CALLS_PER_ENDPOINT)]
        results = [f.result() for f in futures]
    
    end_time = time.time()
    statuses = [r["status"] for r in results]
    success_count = statuses.count(200)
    client_err_count = sum(1 for s in statuses if 400 <= s < 500)
    server_err_count = sum(1 for s in statuses if s >= 500)
    
    print(f" -> Tiempo: {end_time - start_time:.2f}s | 200 OK: {success_count} | 4XX: {client_err_count} | 5XX: {server_err_count}")


print(f"\n💥 FASE 2: GLOBAL FLOOD (Todas las rutas, {CALLS_PER_ENDPOINT} llamadas AL MISMO TIEMPO)")
# Crear una lista plana enorme de todas las llamadas mezcladas al azar
all_calls = []
for _ in range(CALLS_PER_ENDPOINT):
    for ep in endpoints:
        all_calls.append(ep)

# Mezclar para mayor aleatoriedad (opcional, pero realista)
import random
random.shuffle(all_calls)

print(f"Atacando backend con {len(all_calls)} peticiones globales simultáneas...")
start_time = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=200) as executor:
    futures = [executor.submit(make_req, call["url"], call["method"], call["payload"]) for call in all_calls]
    global_results = [f.result() for f in futures]
end_time = time.time()

global_statuses = [r["status"] for r in global_results]
g_success = global_statuses.count(200)
g_client_err = sum(1 for s in global_statuses if 400 <= s < 500)
g_server_err = sum(1 for s in global_statuses if s >= 500)

print(f" -> Tiempo Total: {end_time - start_time:.2f}s")
print(f" -> Balance Final: {g_success} Exitos (200) | {g_client_err} Errores Cliente (4XX) | {g_server_err} Errores Servidor (5XX)")

if g_server_err == 0:
    print("\n✅ FastAPI / AsyncPG resistieron el Ataque Total. 0 Crasheos de Backend.")
else:
    print("\n❌ Advertencia: Hubo Tiempos de Espera o 500s. El servidor se resintió.")
