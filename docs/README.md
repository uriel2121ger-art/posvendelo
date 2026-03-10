# Documentación del proyecto — TITAN POS

Carpeta central de documentación del punto de venta.

---

## Índice

### Distribución e instalación

| Documento | Descripción |
|-----------|--------------|
| [INSTRUCCIONES_DISTRIBUCION.md](INSTRUCCIONES_DISTRIBUCION.md) | Instrucciones para publicar una release y distribuir a cajeros y sucursales. |
| [INSTALACION_EQUIPOS.md](INSTALACION_EQUIPOS.md) | Instalación en equipos nuevos: Release (instalador), script de nodo, o clonado. |
| [PLAN_NUBE_TITAN.md](PLAN_NUBE_TITAN.md) | Plan Nube TITAN: cuenta opcional, app dueño, sincronización y comandos remotos. |

### Testing (Plan V6)

| Documento | Descripción |
|-----------|--------------|
| [PLAN_TESTING_V6.md](PLAN_TESTING_V6.md) | Plan de Testing V6: Chaos Engineering, Edge Cases y E2E por pestaña (FASE 0, E2E-1 a E2E-17, EC, Chaos 1–9). |
| [LOG_TESTING_V6.md](LOG_TESTING_V6.md) | Registro de ejecución: pre-requisitos, pruebas ejecutadas, resultados, incidencias y resumen por sesión. |
| [MANUAL_TEST_BROWSER.md](MANUAL_TEST_BROWSER.md) | Guía de pruebas manuales en navegador (E2E-1, E2E-17, carga de pestañas, atajos F1–F11). |
| [CHAOS_EXECUTION_V6.md](CHAOS_EXECUTION_V6.md) | Estado de ejecución de las fases Chaos 1–9 (manual vs automático, tests relacionados). |

### Tests E2E (Playwright)

- Los specs y la guía de ejecución están en **`frontend/e2e/`**; ver [frontend/e2e/README.md](../frontend/e2e/README.md) para requisitos y comandos (`npm run test:e2e`).

### Otros

| Documento | Descripción |
|-----------|--------------|
| [INFORME_TOTAL_ARCHIVOS.json](INFORME_TOTAL_ARCHIVOS.json) | Informe de archivos del proyecto. |
| [INFORME_CAPA_2_TECNICA.json](INFORME_CAPA_2_TECNICA.json) | Informe técnico capa 2. |
| ANEXO_CAPA_4_HALLAZGOS_SEGURIDAD.csv | Anexo hallazgos de seguridad. |
| ANEXO_CAPA_5_PUNTOS_LOGGING.csv | Anexo puntos de logging. |
| ANEXO_CAPA_6_*.csv | Plan 90 días y RACI. |
| INVENTARIO_TOTAL_ARCHIVOS.csv | Inventario de archivos. |

---

*Última actualización: documentación de distribución, instalación en equipos y plan Nube TITAN (2026-03-10).*
