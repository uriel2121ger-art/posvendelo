# Parsear XML (CFDI 4.0) — Documentación

Funcionalidad en **Fiscal → Facturación** que permite subir un archivo XML de CFDI 4.0 (factura de proveedor) y extraer comprobante, emisor, receptor y conceptos (líneas/productos).

---

## 1. Qué hace

- **Frontend:** En la pestaña Fiscal, sección «Parsear XML»: selector de archivo (`.xml`) y botón «Parsear».
- **Backend:** `POST /api/v1/fiscal/xml/parse` recibe el archivo, lo guarda en temporal y lo procesa con `XMLIngestor`.
- **Parser:** Extrae del XML CFDI 4.0:
  - **Comprobante:** UUID, Fecha, TipoDeComprobante, SubTotal, Total, Moneda.
  - **Emisor:** RFC, Nombre, RégimenFiscal (proveedor).
  - **Receptor:** RFC, Nombre, UsoCFDI (tu negocio).
  - **Conceptos:** por cada línea (producto): ClaveProdServ, Descripción, Cantidad, ValorUnitario, Importe, ClaveUnidad, etc.

El resultado se muestra en el visor de resultados del panel fiscal. **No** se importan productos al inventario automáticamente; para eso haría falta un paso adicional (ej. botón «Importar a inventario» que use `import_to_database()` del ingestor).

---

## 2. Dependencia obligatoria: defusedxml

El parser usa **defusedxml** para evitar ataques XXE (XML External Entity). Sin esta librería, el endpoint **falla** al importar el módulo.

| Paquete     | Uso                    | En requirements.txt |
|------------|------------------------|----------------------|
| **defusedxml** | Parseo seguro de XML CFDI | Sí (`defusedxml>=0.7.1`) |

### Instalación

Desde `backend/` (recomendado: usar entorno virtual):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

O solo la dependencia para Parsear XML:

```bash
pip install defusedxml>=0.7.1
```

En **Docker** la imagen del backend ya incluye `requirements.txt`, por lo que defusedxml está instalado.

---

## 3. Cómo probar

### Test automático

Con el **entorno virtual activado** (`source .venv/bin/activate` en Linux/macOS):

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt

# Variables de entorno para tests (solo si otros tests necesitan DB)
export DATABASE_URL="postgresql+asyncpg://titan_user:PASSWORD@localhost:5433/titan_pos"
export JWT_SECRET="test-secret"

python3 -m pytest tests/test_xml_parse.py -v
```

Si **defusedxml** no está instalado, el test se **omite** con el mensaje:  
`defusedxml no instalado; ejecuta: pip install -r requirements.txt`.

### Prueba manual en la app

1. Iniciar backend (con dependencias instaladas) y frontend.
2. Ir a **Fiscal → Facturación**.
3. En «Parsear XML», elegir un archivo `.xml` de CFDI 4.0 (factura de proveedor o de prueba).
4. Pulsar **Parsear**. Debe mostrarse el JSON con `comprobante`, `emisor`, `receptor`, `conceptos`.

### Formato del XML

Debe ser **CFDI 4.0** con namespaces SAT, por ejemplo:

- `xmlns:cfdi="http://www.sat.gob.mx/cfd/4"`
- `xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"`
- Nodos: `cfdi:Comprobante`, `cfdi:Emisor`, `cfdi:Receptor`, `cfdi:Conceptos`, `cfdi:Concepto`, y opcionalmente `tfd:TimbreFiscalDigital` para el UUID.

Solo se acepta extensión **.xml** y tamaño máximo **5 MB**.

---

## 4. Errores frecuentes

| Síntoma | Causa | Solución |
|--------|--------|----------|
| 503 "Requisito no cumplido: instalar defusedxml" | El backend no tiene instalada la librería | `cd backend && source .venv/bin/activate && pip install -r requirements.txt` |
| 403 "Sin permisos para parsear XML fiscal" | Usuario sin rol privilegiado (admin/manager/owner) | Usar cuenta con rol permitido o asignar rol en el sistema |
| 400 "El archivo debe ser XML" | Nombre de archivo sin extensión `.xml` o tipo incorrecto | Subir un archivo con extensión `.xml` |
| 413 "Archivo XML demasiado grande" | Archivo mayor a 5 MB | Reducir tamaño o dividir en varios CFDIs |
| 400 "XML invalido: ..." | Contenido del XML mal formado o no es CFDI 4.0 | Verificar que sea un CFDI 4.0 válido con namespaces SAT |

---

## 5. Permisos y entorno

- **Permisos:** Solo usuarios con rol **admin**, **manager** u **owner** pueden llamar a `POST /api/v1/fiscal/xml/parse`. Los cajeros reciben 403.
- **Windows:** El backend usa `tempfile.mkstemp()` para el archivo temporal; funciona en Windows, Linux y macOS.
- **Venv:** En la sección «Cómo probar», ejecuta los comandos con el **entorno virtual activado** (`source .venv/bin/activate` en Linux/macOS) para que `pip install` y `pytest` usen las dependencias del proyecto.

---

## 6. Resumen para documentación importante

| Tema | Detalle |
|------|---------|
| **Dónde está** | Fiscal → Facturación → «Parsear XML» |
| **Permisos** | Solo roles admin, manager, owner (403 para cajero) |
| **Dependencia** | **defusedxml** (obligatoria); en `backend/requirements.txt` |
| **Instalación** | `cd backend && source .venv/bin/activate && pip install -r requirements.txt` |
| **Test** | `pytest tests/test_xml_parse.py -v` (5 tests: 2 ingestor + 3 API 403/400/200; se omiten si falta defusedxml) |
| **Limitación** | Solo parsea y muestra datos; no importa productos al inventario por sí solo |
