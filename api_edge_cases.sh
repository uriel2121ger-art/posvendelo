TOKEN=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/auth/login" -H "Content-Type: application/json" -d '{"username":"admin","password":"admin"}' | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
if [ -z "$TOKEN" ]; then
    echo "Fallo al obtener TOKEN"
    curl -s -X POST "http://127.0.0.1:8000/api/v1/auth/login" -H "Content-Type: application/json" -d '{"username":"admin","password":"admin"}'
    exit 1
fi
echo "\n--- 1. Variante Float Precision ---"
curl -s -X POST "http://127.0.0.1:8000/api/v1/sales/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"items": [{"product_id": 1, "name": "Float Test", "qty": 3, "price": 9.99, "discount": 33.333, "is_wholesale": false, "price_includes_tax": true}], "payment_method": "cash", "cash_received": 19.98, "branch_id": 1}'

echo "\n\n--- 2. Variante Stock Negativo ---"
curl -s -X POST "http://127.0.0.1:8000/api/v1/sales/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"items": [{"product_id": 1, "name": "Negative Test", "qty": -5, "price": 10, "discount": 0, "is_wholesale": false, "price_includes_tax": true}], "payment_method": "cash", "cash_received": 50, "branch_id": 1}'

echo "\n\n--- 3. Variante Borrado Referencial (Test) ---"
CID=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/customers/" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"name": "Monkey Victim", "rfc": "XAXX010101000", "email": "a@a.com", "phone": "123"}' | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
echo "\nCliente creado con ID: $CID"

# Asignarlo a una venta
curl -s -X POST "http://127.0.0.1:8000/api/v1/sales/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"items": [{"product_id": 1, "name": "Orphan Test", "qty": 1, "price": 1, "discount": 0, "is_wholesale": false, "price_includes_tax": true}], "payment_method": "cash", "customer_id": '$CID', "cash_received": 1, "branch_id": 1}'

# Intentar borrarlo
echo "\nIntentando borrar cliente $CID..."
curl -s -X DELETE "http://127.0.0.1:8000/api/v1/customers/$CID" -H "Authorization: Bearer $TOKEN"
