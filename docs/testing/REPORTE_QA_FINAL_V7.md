# Reporte Final de Aseguramiento de Calidad (QA) - Suite V7

Este documento consolida los esfuerzos de pruebas manuales exhaustivas, de exploración (Exploratory Testing), de estrés (Stress Testing) y de ingeniería del caos (Chaos Engineering), ejecutados sobre la versión V7 unificada del Punto de Venta. 

Las pruebas se llevaron a cabo interactuando agresivamente con la Interfaz de Usuario (Navegador) simulando condiciones extremas, red defectuosa y mala intención por parte del operador operando como verdaderos Testers Manuales.

---

## 1. Fases Completadas y Principales Hallazgos

### Fases 1 y 2: Casos de Borde (Edge Cases) y Flujos Básicos
Se validó la robustez de los formularios y lógica de negocio primaria:
- **Terminal de Ventas:** Preventiva ante montos insuficientes. Bloqueó exitosamente cobros con cantidades tramposas ($0.01).
- **Gastos e Inventarios:** El frontend sanitiza y evita montos negativos que descuadren la caja o el stock, aunque en Inventario la conversión automática de `-500` a `500` puede resultar contraintuitiva.
- **Clientes:** El sistema bloquea correctamente la creación de clientes sin nombre (botón deshabilitado).
- **Reportes:** Se blindaron los filtros de fechas incongruentes (Desde > Hasta).

### Fases 3 y 4: Chaos Engineering y Pruebas Extremas
Se sometió la UI a cargas inusuales:
- **Split-Brain (Doble Clic):** La aplicación absorbió ráfagas de clics al cerrar turno sin corromper la DB local o remota.
- **Textos Corruptos (XSS y Zalgo):** Inyecciones de código `<script>` y texto `H̸̟͑e̴͉̅...` en buscadores fueron sanitizadas correctamente sin quebrar el DOM.
- **The Billionaire Test:** Tickets con totales absurdos de `$4,598,999,999,999,952.00` fueron calculados limpiamente, demostrando nulo desbordamiento técnico (Overflow System), aunque exponen la necesidad de limitar la cantidad de ítems por negocio.
- **⚠️ BUG CRÍTICO ENCONTRADO (Empleados):** El botón "Guardar" al intentar crear un empleado nuevo muere en el Frontend, impidiendo levantar el request POST. Imposibilita el alta de personal.

### Fases 5, 6 y 7: Pruebas Continuas, Mutación de Estado y Componentes
- **Desincronización Multi-Pestaña:** Al borrar un producto desde "Pestaña B" e intentar cobrarlo en "Pestaña A", el backend protege la transacción rechazándola ordenadamente ("Producto no encontrado").
- **Corrupción de API URL (Ajustes):** Al forzar una IP caída (`localhost:1111`), la app sobrevive. Aísla el error devolviendo un Toast de `Failed to Fetch` permitiendo navegar de regreso y salvaguardar el entorno (Excelente esquema de Error Boundary React).
- **Pérdida de Estado Sucio (Ajustes):** Salir de ajustes sin guardar descarta los inputs introducidos silenciosamente sin advertencia.
- **⚠️ ÁREA DE MEJORA ENCONTRADA (Clientes):** El sistema permite duplicar nombres exactos de clientes indefinidamente sin restricciones únicas (`UNIQUE Constraint`).

### Fase 8 (Volumen - Prueba de Concepto Parcial)
Previo a la fase estricta comandada manual, se inyectó una carga sustancial de ventas vía paralela para verificar la resistencia de los visores de datos:
- **Hallazgos Panel:** `Historial` carga limpiamente los últimos 200 tickets asíncronamente, y `Reportes` los consolida eficientemente, tolerando grandes paginaciones sin lag de memoria.
- **⚠️ BUG ENCONTRADO (Contador Turno):** El badge superior con la estadística del turno en vivo ignora las transacciones consolidadas que no provengan del ciclo temporal local de esa específica sesión de navegador.

---

## 2. Retos Pendientes y Requisitos de Prueba Estricta (Fase 8 UI)

La fase culminante de validación de volumen, que fue conceptualizada e intercelada por requisitos superiores, requiere la simulación de un día entero de altísima demanda operado en tiempo real. 

Queda en registro el siguiente **Plan de Ejecución Estricto (Pendiente)**:

- [ ] **Ciclo de Volumen Estricto (500 Ventas Manuales):**
  - Efectuar **500 ventas** iterativas manejadas única y exclusivamente operando clics sobre la Terminal (Sin scripts o inyección de código).
  - **Composición de cada Venta:** Cada ticket conformado debe contener rígidamente entre **2 y 3 productos comunes** (preexistentes), integrados en cada venta con **entre 2 y 5 productos nuevos** de los creados recientemente.
  - **Ticket Promedio:** Configurar las cantidades de los ítems para promediar aproximadamente `$267.00` pesos por transacción.
  - **Restricción Unitaria (Centavos):** Los precios base de registro de todo producto deben culminar en números enteros (`.00`). La única forma orgánica legal de generar un ticket que despliegue centavos en su monto final es mediante el botón de **Aplicar Descuento**.
  - **Rotación de Inventario Dinámica:** Por cada bloque perimetral de **7 ventas**, la operadora deberá suspender el cobro y virar a inventario para crear in-situ **al menos 15 productos enteramente nuevos**.
  - **Reglas de Nuevos Productos:** Todo producto nuevo inyectado dinámicamente deberá poseer un stock natural de entre `12 y 36` unidades y un precio entero.
  - **Validación Gobernal (Claves SAT):** Se deberá garantizar dogmáticamente que **absolutamente todos** los productos (tanto los usos preexistentes comunes como los 15 de nueva formación) lleven debidamente completado su campo de **Clave SAT** válida en el apartado Fiscal (ej. `50192701`).

---

## 3. Conclusión de la Auditoría QA Parcial V7

Las arquitecturas y librerías que fundamentan la V7 exhiben uno de los frentes de React más resilientes logrados en el recorrido del proyecto POSVENDELO. El diseño modular defensivo absorbe elegantemente anomalías externas e intenciones destructivas internas. 

Resolviendo los parches lógicos expuestos *(Alta Empleados y Duplicidad)* y culminando el asedio manual agendado en la Fase 8, el proyecto será enteramente merecedor de sus certificaciones definitivas de Producción.
