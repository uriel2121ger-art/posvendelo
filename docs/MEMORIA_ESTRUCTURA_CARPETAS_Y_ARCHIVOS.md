# Memoria: Estructura de carpetas y archivos del proyecto

**Fecha de actualización:** 2026-02-24  
**Proyecto:** PUNTO DE VENTA (TITAN POS)

Este documento refleja la estructura actual del repositorio. No sustituye al código; sirve solo como referencia de carpetas y archivos principales.

---

## Raíz del proyecto

```
PUNTO DE VENTA/
├── .git/
├── .gitignore
├── claude.md
├── titan_gateway.log
│
├── CLIENTE/                    # Paquete cliente (solo ZIP)
│   └── titan_pos_client.zip
│
├── SERVIDOR/                   # Paquete servidor (solo ZIP)
│   └── titan_dist_server.zip
│
├── gateway_data/               # Datos del gateway (backups, branches, sales)
│   ├── backups/
│   ├── branches/
│   ├── exports/
│   └── sales/
│
├── titan-client/               # Stub/referencia cliente (README + config ejemplo)
│   ├── README.md
│   └── config.json.example
│
├── titan-server/               # Distribución servidor (instalador, data, server)
│   ├── README.md
│   ├── TITAN_POS.desktop
│   ├── instalar.sh
│   ├── titan_pos.sh
│   ├── requirements.txt
│   ├── data/
│   ├── migrations/
│   ├── scripts/
│   └── server/
│       ├── gateway_data/
│       ├── routers/
│       └── ...
│
├── backend/                     # Código principal Python (desarrollo)
│   ├── app/
│   ├── server/
│   ├── modules/
│   ├── src/
│   ├── data/
│   ├── main.py
│   ├── requirements.txt
│   └── ...
│
├── frontend/                    # Aplicación Electron + React (desarrollo)
│   ├── src/
│   ├── out/
│   ├── resources/
│   ├── scripts/
│   ├── package.json
│   ├── electron.vite.config.ts
│   └── ...
│
├── _archive/                    # Copias de respaldo del código original
│   ├── backend_original/
│   └── frontend_original/
│
└── [Documentación e informes en raíz]
    ├── ALERTAS_P1_OPERACION.md
    ├── ANEXO_*.md / *.csv
    ├── DOCUMENTACION_COMPLETA_DEBUG_Y_FIXES.md
    ├── INFORME_*.md / *.json
    ├── SOP_*.md
    ├── claude.md
    └── ...
```

---

## Backend (código Python)

- **Ubicación:** `backend/`
- **Entrada:** `backend/main.py`
- **Servidores API:** `backend/server/titan_gateway.py`, `backend/server/titan_gateway_modular.py`
- **Routers:** `backend/server/routers/` (alerts, backups, branches, logs, products, pwa, sales, terminals, tools)
- **App:** `backend/app/` (api, config, core, dialogs, exports, fiscal, intel, logistics, models, pos_core, repositories, services, startup, sync, turns, ui, utils, window, wizards)
- **Módulos:** `backend/modules/` (audit, auth, customers, dashboard, employees, expenses, fiscal, inventory, loyalty, mermas, products, remote, sales, sat, shared, sync, turns)
- **Servicios y más:** `backend/src/` (ai, api, core, infra, services, ui, utils)
- **Datos locales:** `backend/data/` (config, databases, db, exports, imports, logs, sat_catalog, temp)

---

## Frontend (Electron + React)

- **Ubicación:** `frontend/`
- **Main (Electron):** `frontend/src/main/index.ts`
- **Preload:** `frontend/src/preload/index.ts`
- **Renderer:** `frontend/src/renderer/`
  - Entrada: `main.tsx`, `index.html`
  - Estilos: `src/renderer/src/assets/` (base.css, main.css)
  - Componentes principales: `App.tsx`, `Terminal.tsx`, `Login.tsx`
  - Tabs: `CustomersTab`, `ProductsTab`, `InventoryTab`, `ShiftsTab`, `ReportsTab`, `HistoryTab`, `SettingsTab`, `DashboardStatsTab`, `ExpensesTab`, `MermasTab`
  - Componentes: `src/renderer/src/components/TopNavbar.tsx`
  - API cliente: `src/renderer/src/posApi.ts`
- **Build:** `frontend/out/` (salida de electron-vite)

---

## Archivo de memoria

- **Nombre:** `MEMORIA_ESTRUCTURA_CARPETAS_Y_ARCHIVOS.md`
- **Uso:** Consulta rápida de la estructura actual; no se modifica código desde este archivo.
