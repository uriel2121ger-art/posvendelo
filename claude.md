# PUNTO DE VENTA — TITAN POS

Archivo de contexto inicial del proyecto. Lee esto al cargar el proyecto por primera vez.

## Cómo se instala (importante)

**Todas las PCs instalan el mismo software.** Una máquina se designa como **servidor** y el resto como **clientes**. No hay dos aplicaciones distintas: es la misma app, con el rol (servidor o cliente) definido por configuración en cada equipo.

## Estructura del repo

- **frontend/** y **backend/** — Contienen la misma base de código (TITAN POS). Se duplicó por el origen de los zips (cliente vs servidor); en la práctica es un solo proyecto.
- **CLIENTE/**, **SERVIDOR/** — Zips de respaldo (mismo contenido que frontend/backend, solo que uno trae .venv).

## Objetivo

Sistema de punto de venta (POS) en producción: ventas, inventario, reportes, fiscal (CFDI México), multi-sucursal. Una PC = servidor (API, BD, sync); las demás = clientes (cajas) que se conectan a ese servidor.

## Stack

- Python 3.10+, PyQt6, FastAPI, Uvicorn, PostgreSQL 14+. Fiscal: CFDI 4.0, Facturapi, PAC, SAT.

## Notas

- Este archivo sirve como punto de entrada de contexto para el asistente.
