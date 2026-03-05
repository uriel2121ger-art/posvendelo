# Pruebas manuales: Tab Clientes y datos de facturación

Objetivo: verificar que la pestaña Clientes funciona correctamente con los campos opcionales de facturación (RFC, Código postal, Razón social, Régimen fiscal).

**Requisitos:** Backend en marcha, frontend en marcha (`npm run dev:browser`), navegador en `http://localhost:5173/#/clientes`.

---

## Resumen de 9 rondas de pruebas (verificación en navegador)

| Ronda | Prueba | Resultado |
|-------|--------|-----------|
| **1** | Formulario muestra sección "Datos de facturación (opcionales)" con RFC, Código postal, Razón social, Régimen fiscal | ✅ OK – Campos visibles al abrir Nuevo/Editar |
| **2** | Crear cliente solo con nombre (sin datos fiscales) | ✅ OK – Cliente guardado, contador sube (ej. 2 clientes) |
| **3** | Crear cliente con todos los datos fiscales (nombre, teléfono, email, RFC, CP, razón social, régimen 601) | ✅ OK – Cliente guardado (ej. 3 clientes), RFC XAXX010101000 aceptado |
| **4** | Editar cliente existente: cambiar nombre y ACTUALIZAR PERFIL | ✅ OK – Nombre actualizado en lista (ej. "Cliente Facturacion Full - Editado") |
| **5** | Seleccionar cliente con datos fiscales y verificar que el formulario carga RFC y datos | ✅ OK – Al hacer clic en la fila se abre el perfil con RFC y datos cargados |
| **6** | Filas de la tabla son clickeables (accesibilidad): seleccionar cliente desde la lista | ✅ OK – Filas con `role="button"` y `aria-label="Cliente {nombre}"` permiten clic y teclado |
| **7** | Crear cliente con solo algunos datos fiscales (nombre + RFC + Código postal, sin razón social ni régimen) | ✅ OK – Cliente "Cliente Solo RFC y CP" guardado (4 clientes) |
| **8** | Búsqueda por nombre: filtrar escribiendo en "Buscar por nombre, teléfono o email" | ✅ OK – Escribir "Facturacion" filtra y muestra 1 resultado |
| **9** | Guardar cliente sin llenar datos fiscales (solo nombre obligatorio) | ✅ OK – Mismo flujo que ronda 2; campos fiscales opcionales |

---

## Cambio de accesibilidad aplicado

Para que las filas de la tabla de clientes fueran identificables y clickeables en pruebas y por teclado/lectores de pantalla, se añadió en cada fila (`<tr>`) del listado:

- `role="button"`
- `tabIndex={0}`
- `onKeyDown` para Enter/Espacio (abre el perfil)
- `aria-label={"Cliente " + c.name}`

Así el snapshot del navegador expone refs como `Cliente Cliente Facturacion Full` y se puede hacer clic (o Enter) sobre la fila para abrir el perfil.

---

## Notas

- Los campos de facturación son **opcionales**: no es obligatorio llenar RFC, CP, razón social ni régimen fiscal.
- El backend valida formato de RFC (12 o 13 caracteres, patrón México); si se envía RFC inválido, la API devuelve error.
- Código postal en front se limita a dígitos; razón social y régimen fiscal son texto libre (régimen típicamente códigos como 601, 603, 612).
