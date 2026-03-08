# Reporte de Ejecucion - Plan de Pruebas Manuales V8

## Estado

Documento saneado para mantener hallazgos funcionales sin exponer rutas locales, nombres reales de operadores ni capturas almacenadas fuera del repositorio.

## Hallazgos relevantes

- Duplicidad de clientes: paso. La restriccion de unicidad evito altas repetidas.
- Alta de empleados: fallo critico observado. El boton `Guardar` permanecia deshabilitado aun con el formulario completo.
- Carrito vacio: el frontend permitia procesar ventas en `$0.00`; se marco como validacion faltante.
- Apertura de turno y cobro mixto: paso con montos con centavos y cambio en efectivo.
- Carrito dinamico y descuentos: paso; los recalculos de subtotal y total se mantuvieron estables.

## Evidencia

Las capturas originales se conservaron solo en almacenamiento local de QA y no deben versionarse dentro del repositorio. Si se requiere trazabilidad adicional, agregar referencias a un directorio compartido sanitizado o adjuntar evidencias anonimizadas dentro de `docs/evidencia/`.

## Recomendaciones

1. Mantener en reportes versionados unicamente hallazgos, pasos y resultados.
2. Excluir rutas absolutas de herramientas locales y nombres reales de clientes o sucursales.
3. Publicar evidencias visuales solo si viven dentro del repo en una ruta anonimizda y aprobada.
