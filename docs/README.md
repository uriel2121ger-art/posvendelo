# Documentacion — POSVENDELO

Indice por categoria. Documentos activos en subcarpetas. Archivos supersedidos en `otros/_archive/`.

---

## distribucion/

| Documento | Descripcion |
|-----------|-------------|
| [INSTRUCCIONES_DISTRIBUCION.md](distribucion/INSTRUCCIONES_DISTRIBUCION.md) | Publicar release y distribuir a cajeros y sucursales. |
| [INSTALACION_EQUIPOS.md](distribucion/INSTALACION_EQUIPOS.md) | Instalacion en equipos nuevos: .deb, AppImage, script de nodo. |
| [PLAN_NUBE_TITAN.md](distribucion/PLAN_NUBE_TITAN.md) | Plan Nube: cuenta opcional, app dueno, sync y comandos remotos. |
| [RELEASE_CHECKLIST_WINDOWS_LINUX.md](distribucion/RELEASE_CHECKLIST_WINDOWS_LINUX.md) | Checklist antes de publicar clientes (Windows/Linux). |

---

## operacion/

| Documento | Descripcion |
|-----------|-------------|
| [RUNBOOK_LICENCIAS_Y_SOPORTE.md](operacion/RUNBOOK_LICENCIAS_Y_SOPORTE.md) | Licencias: emision, renovacion, activacion offline. |
| [RUNBOOK_OPERACION_FLOTA.md](operacion/RUNBOOK_OPERACION_FLOTA.md) | Operacion de flota de nodos. |
| [ROLLOUT_UPDATES_Y_ROLLBACK.md](operacion/ROLLOUT_UPDATES_Y_ROLLBACK.md) | Publicacion de fixes, rollout y rollback. |
| [DESPUES_DE_DEPLOY.md](operacion/DESPUES_DE_DEPLOY.md) | Reinicio de servicios y limpieza de cache tras deploy. |
| [SECURITY_CHECKLIST.md](operacion/SECURITY_CHECKLIST.md) | Checklist de seguridad y controles. |
| [CHECKLIST_SALIDA_MERCADO_GA.md](operacion/CHECKLIST_SALIDA_MERCADO_GA.md) | Checklist salida a mercado (trial 120 dias). |

---

## testing/

| Documento | Descripcion |
|-----------|-------------|
| [QA_TESTING_CONSOLIDADO.md](testing/QA_TESTING_CONSOLIDADO.md) | Indice maestro QA: apunta a todos los reportes V10-V16. |
| [PLAN_PRUEBAS_MANUALES_V10.md](testing/PLAN_PRUEBAS_MANUALES_V10.md) | Plan de pruebas manuales canonico (regresion, monkey, CFDI, concurrencia). |
| [LOG_PRUEBAS_MANUALES_V10_2026-03-05.md](testing/LOG_PRUEBAS_MANUALES_V10_2026-03-05.md) | Log de ejecucion V10 con bugs encontrados. |
| [LOG_PRUEBAS_RUPTURA_2026-03-07.md](testing/LOG_PRUEBAS_RUPTURA_2026-03-07.md) | E2E, credenciales duras, baseline tests. |
| [REPORTE_VULNERABILIDADES_V10.md](testing/REPORTE_VULNERABILIDADES_V10.md) | Bugs UX: buscador, dirty state, Zalgo, cancelacion 422. |
| [REPORTE_VULNERABILIDADES_V15.md](testing/REPORTE_VULNERABILIDADES_V15.md) | Auditoria aritmetica: centavo huerfano IVA. |
| [REPORTE_VULNERABILIDADES_V16.md](testing/REPORTE_VULNERABILIDADES_V16.md) | Stress: 500 mega tickets con pagos mixtos. |
| [FLUJO_PRUEBAS_AUTONOMO.md](testing/FLUJO_PRUEBAS_AUTONOMO.md) | Metodologia loop tab-by-tab. |
| [LOG_PRUEBAS_TABS.md](testing/LOG_PRUEBAS_TABS.md) | Registro loop tab validation (baseline). |
| [MANUAL_TEST_BROWSER.md](testing/MANUAL_TEST_BROWSER.md) | Pruebas manuales en navegador (E2E, atajos F1-F11). |
| [PRUEBAS_MANUALES_CLIENTES_FACTURACION.md](testing/PRUEBAS_MANUALES_CLIENTES_FACTURACION.md) | Accesibilidad filas clientes, RFC opcional. |
| [PRUEBAS_MANUALES_PENDIENTES_Y_AVISOS.md](testing/PRUEBAS_MANUALES_PENDIENTES_Y_AVISOS.md) | Tickets pendientes con cambios precio/stock entre sesiones. |
| [REVISION_VISUAL_EXHAUSTIVA.md](testing/REVISION_VISUAL_EXHAUSTIVA.md) | Auditoria CSS Tailwind y estructura visual. |

E2E Playwright: ver [frontend/e2e/README.md](../frontend/e2e/README.md) y `npm run test:e2e`.

---

## referencia/

| Documento | Descripcion |
|-----------|-------------|
| [INSTALL_FLOW.md](referencia/INSTALL_FLOW.md) | Diseno del flujo plug-and-play (fases, fingerprint, endpoints). |
| [CHANGELOG_INSTALL_FLOW_2026_03_12.md](referencia/CHANGELOG_INSTALL_FLOW_2026_03_12.md) | Changelog instalacion plug-and-play, rename, wizard, deploy. |
| [CHANGELOG_TECH_DEBT_2026_03_03.md](referencia/CHANGELOG_TECH_DEBT_2026_03_03.md) | Changelog deuda tecnica (migraciones 035-041, NUMERIC, JTI). |
| [BUG_PATTERN_ASYNCPG_FECHAS.md](referencia/BUG_PATTERN_ASYNCPG_FECHAS.md) | Patrones de bug asyncpg con fechas. |
| [ARQUITECTURA_MOVIL_REDES.md](referencia/ARQUITECTURA_MOVIL_REDES.md) | Arquitectura movil, LAN y redes. |
| [MITIGACION_RIESGOS_10K.md](referencia/MITIGACION_RIESGOS_10K.md) | Mitigacion de riesgos a 10K nodos. |
| [PARSEAR_XML_FISCAL.md](referencia/PARSEAR_XML_FISCAL.md) | Parsear XML CFDI 4.0 (defusedxml). |
| [INGESTORES_CSV_XML.md](referencia/INGESTORES_CSV_XML.md) | Ingestores CSV/XML: productos, clientes, inventario. |
| [AUTOFIRMA_WINDOWS_CONTROLADA.md](referencia/AUTOFIRMA_WINDOWS_CONTROLADA.md) | Autofirma Windows controlada. |

---

## informes/

| Documento | Descripcion |
|-----------|-------------|
| [AUDITORIA_COMPLETA.md](informes/AUDITORIA_COMPLETA.md) | Auditoria completa del proyecto. |
| [PENDIENTES_APLICADOS.md](informes/PENDIENTES_APLICADOS.md) | Pendientes resueltos. |
| [VERIFICACION_20_RONDAS.md](informes/VERIFICACION_20_RONDAS.md) | Verificacion 20 rondas. |

---

## otros/

| Documento | Descripcion |
|-----------|-------------|
| [bug-investigation-cierre-turno-500.md](otros/bug-investigation-cierre-turno-500.md) | Investigacion bug cierre turno 500. |
| [electron-conectar.md](otros/electron-conectar.md) | Notas Electron/conectar. |
| [99-docker-unmanaged.conf.example](otros/99-docker-unmanaged.conf.example) | Ejemplo config systemd Docker. |
| [fix-apt-warnings.sh](otros/fix-apt-warnings.sh) | Script correccion avisos apt. |
| _archive/ | 15 documentos archivados (testing V6-V9, V11-V14, Cursor, apt-notices). |

---

*Ultima actualizacion: optimizacion y archivo de docs obsoletos (2026-03-12).*
