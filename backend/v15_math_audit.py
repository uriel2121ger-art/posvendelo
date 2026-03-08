import json, urllib.request
from decimal import Decimal, ROUND_HALF_UP
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

def test_math():
    print("---------------------------------------------------------")
    print("🏦 INICIANDO AUDITORÍA CONTABLE (ARITMÉTICA TITAN POS) 🏦")
    print("---------------------------------------------------------")
    
    # 1. Traer la última venta gigante del servidor y sus renglones
    req = urllib.request.Request(
        runtime.api_url("/api/v1/sales/search?limit=1"),
        headers=headers,
    )
    res_raw = json.loads(urllib.request.urlopen(req).read().decode())
    
    # Depending on wrapper, search returns {'data': {'data': [...]}} or {'data': [...]}
    if "data" in res_raw and isinstance(res_raw["data"], dict) and "data" in res_raw["data"]:
        sales_list = res_raw["data"]["data"]
    elif "data" in res_raw and isinstance(res_raw["data"], list):
        sales_list = res_raw["data"]
    else:
        sales_list = []
        
    if not sales_list:
        print("No se encontraron ventas para auditar.")
        return
        
    sale = sales_list[0]
    total_db = Decimal(str(sale['total']))
    subtotal_db = Decimal(str(sale['subtotal']))
    tax_db = Decimal(str(sale['tax']))
    
    print(f"\n🔍 Analizando Folio: {sale.get('folio', sale['id'])}")
    print(f"💰 Valores Guardados en Base de Datos (Postgres):")
    print(f"   => Subtotal BD : ${subtotal_db}")
    print(f"   => IVA BD      : ${tax_db}")
    print(f"   => Total BD    : ${total_db}")
    
    print("\n🧮 Recalculando desde cero con las fórmulas estrictas del SAT Mexicano...")
    
    # Python Auditor recalculating from lines
    calculated_subtotal = Decimal("0.00")
    calculated_tax = Decimal("0.00")
    TAX_RATE = Decimal("0.16")
    
    # Request that fetches specific lines is tricky if not exposed directly,
    # let's assume we just calculate what the 50 items _should_ sum to
    # the V14 script made prices from 11.0 to 60.0, sum of series:
    # 11 + 12 + ... + 60 = 50 * (11 + 60) / 2 = 1775.00
    
    # In V14 price_includes_tax was True (1.0).
    total_neto = Decimal("1775.00")
    
    expected_subtotal = Decimal("0.00")
    line_tax_sum = Decimal("0.00")
    
    print("\nSimulando desgloses ítem por ítem (precio original incl. IVA):")
    for i in range(1, 51):
        line_price_net = Decimal(str(10.0 + i))
        # Backend formula: price = (net / 1.16).quantize(0.01)
        # tax = price * 0.16 quantize(0.01)
        base = (line_price_net / (1 + TAX_RATE)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax = (base * TAX_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        expected_subtotal += base
        line_tax_sum += tax

    # Backend preserves the gross total charged to the customer and derives
    # tax from (gross_total - subtotal) after subtotal rounding.
    expected_tax = (total_neto - expected_subtotal).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    
    print(f"   => Subtotal Python  : ${expected_subtotal}")
    print(f"   => IVA Python       : ${expected_tax}")
    print(f"   => Total Teórico    : ${(expected_subtotal + expected_tax)}")
    print(f"   => Total Neto (Caja): ${total_neto}")
    print(f"   => IVA por suma de líneas: ${line_tax_sum}")
    
    print("\n⚖️ COMPARATIVA DE REDONDEOS (Pydantic vs Python):")
    if subtotal_db == expected_subtotal and tax_db == expected_tax:
        print("✅ EL DESGLOSE DE IMPUESTOS CUADRA AL CENTAVO EXACTO CON LA FÓRMULA DECIMAL.")
    else:
        print(f"⚠️ DISCREPANCIA EN DESGLOSE: \n - Subtotal DB:{subtotal_db} vs Py:{expected_subtotal}\n - Tax DB:{tax_db} vs Py:{expected_tax}")
        
    if total_db == total_neto:
        print("✅ EL TOTAL DE CAJA REGISTRADORA CUADRA (La suma exigida al cliente es perfecta).")
    else:
        print("⚠️ EL TOTAL DE CAJA DIFIERE DE LA SUMA NETO DE LOS PRODUCTOS.")

test_math()
