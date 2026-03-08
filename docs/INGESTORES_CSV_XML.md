# Ingestores CSV/XML — Productos, Clientes, Inventario, Historial

Resumen de qué existe y qué se puede añadir para importar datos desde CSV o XML en cada módulo.

---

## Estado actual

| Módulo | CSV/Excel | XML | Notas |
|--------|-----------|-----|--------|
| **Productos** | Sí (UI) | No | Frontend: Importar CSV/Excel en ProductsTab; mapeo de columnas y N× `createProduct`. |
| **Clientes** | Sí (UI) | No | Frontend: Importar CSV/Excel en CustomersTab; N× `createCustomer`. |
| **Inventario** | No | No | Solo ajustes unitarios desde el drawer (movimiento por producto). |
| **Historial (ventas)** | No import | No | Solo export a CSV desde HistoryTab. Las ventas se crean desde Terminal. |
| **Fiscal** | No | Sí | XML Ingestor (CFDI 4.0) para facturas de proveedores → productos con simetría SAT. |

Lectura/escritura de Excel en frontend (Productos y Clientes): **SheetJS Community Edition 0.20.3** instalado desde el CDN oficial (ver `frontend/package.json` y [SECURITY_CHECKLIST.md](SECURITY_CHECKLIST.md)).

---

## Sí puede haber ingestores en todos

Se puede extender el sistema con:

### 1. Productos

- **Ya hay:** importación CSV/Excel en la UI (archivo → mapeo columnas → muchas llamadas a la API).
- **Añadir (opcional):**
  - **Backend:** `POST /api/v1/products/bulk-import`: aceptar JSON (lista de ítems) o CSV/XML en body o multipart, validar y insertar/actualizar en una transacción. Así se soporta XML (catálogo proveedor, otro POS) y se reduce a una sola petición.
  - **XML:** formato acordado (ej. nodos `<producto>` con `<sku>`, `<nombre>`, `<precio>`, etc.) o reutilizar estructura tipo CFDI conceptos para catálogos.

### 2. Clientes

- **Ya hay:** importación CSV/Excel en la UI (N× `createCustomer`).
- **Añadir (opcional):**
  - **Backend:** `POST /api/v1/customers/bulk-import`: JSON o CSV (y opcionalmente XML) en una sola petición.
  - **XML:** esquema simple (ej. `<cliente><nombre/><telefono/><email/><rfc/>...</cliente>`).

### 3. Inventario

- **No hay hoy:** solo movimientos uno a uno desde la UI.
- **Añadir:**
  - **Backend:** `POST /api/v1/inventory/bulk-update` (o `bulk-adjust`): aceptar lista de `{ sku, quantity }` o `{ sku, stock_final }` para conteo físico o cargas masivas.
  - **CSV:** columnas por ejemplo `sku,cantidad` o `sku,stock_final`; el backend parsea y aplica ajustes (tipo `adjust`) por producto.
  - **XML:** mismo contenido en XML (ej. `<item sku="X" cantidad="10"/>`) para integraciones con almacén o ERP.

### 4. Historial (ventas)

- **Export:** ya existe export a CSV desde Historial.
- **Import:** no es un ingestor “de uso diario”; tendría sentido como **migración** desde otro POS o sistema.
  - **Opcional:** `POST /api/v1/sales/import` o endpoint interno que reciba ventas históricas (fecha, total, ítems, cliente, etc.) en JSON/CSV/XML para poblar el historial al cambiar de sistema. Requiere definir bien folios, turnos y consistencia con `sale_events`.

---

## Formatos sugeridos

### CSV (común para todos)

- **Productos:** `sku,nombre,precio,stock,categoria,barcode,...`
- **Clientes:** `nombre,telefono,email,rfc,direccion,...`
- **Inventario (conteo):** `sku,cantidad` o `sku,stock_final`
- **Historial (migración):** `fecha,folio,total,cliente_id,items_json,...` (más delicado; mejor JSON/XML para ítems anidados).

### XML (ejemplo de estructura)

- **Productos:** raíz con muchos `<producto>`; cada uno con `<sku>`, `<nombre>`, `<precio>`, `<stock>`, `<categoria>`, etc.
- **Clientes:** raíz con muchos `<cliente>`; `<nombre>`, `<telefono>`, `<email>`, `<rfc>`, etc.
- **Inventario:** raíz con muchos `<item sku="..." cantidad="..."/>` o `<item><sku/><cantidad/></item>`.
- **Historial:** raíz con muchas `<venta>`; dentro ítems, totales, fecha; alineado con el modelo de `sales` y `sale_items`.

---

## Seguridad y buenas prácticas

- **RBAC:** todos los endpoints de import (bulk/bulk-import/bulk-update/import) solo para roles con permiso (p. ej. admin/manager/owner).
- **Límites:** máximo de filas por petición (ej. 2000 productos, 5000 clientes, 10 000 líneas de inventario) y timeout razonable.
- **Validación:** mismos esquemas Pydantic que en create/update (ProductCreate, CustomerCreate, etc.); rechazar filas inválidas y devolver resumen (insertados, actualizados, errores por fila).
- **XML:** usar **defusedxml** (como en el ingestor fiscal) para evitar XXE.
- **Transacciones:** bulk en una transacción; en caso de error configurable: todo rollback o “todo lo válido” según política.

---

## Próximos pasos

1. **Productos / Clientes:** decidir si se añade solo bulk por JSON (y el frontend sigue enviando CSV parseado como JSON) o también parser CSV/XML en backend.
2. **Inventario:** implementar `POST /api/v1/inventory/bulk-update` (JSON) y, si aplica, aceptar CSV/XML en el mismo endpoint o en uno dedicado.
3. **Historial:** solo si se necesita migración; diseñar esquema y reglas de folios/turnos antes de implementar.

Si quieres, el siguiente paso puede ser implementar los endpoints de **bulk-import** (productos y clientes) y **bulk-update** (inventario) en el backend, con soporte al menos para JSON y CSV (y después XML reutilizando la misma lógica de negocio).
