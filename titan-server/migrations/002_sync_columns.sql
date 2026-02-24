-- Migración 002: Agregar columnas faltantes de sincronización
-- Versión: 2.0.1

-- Agregar columna synced_from_terminal a sales si no existe
-- SQLite no soporta ADD COLUMN IF NOT EXISTS, usamos try/catch en Python

-- Esta migración se maneja via ALTER TABLE en el código
-- porque SQLite no soporta sintaxis condicional

-- Las columnas que se agregan:
-- sales.synced_from_terminal TEXT
-- sales.mixed_card REAL
-- sales.pos_id TEXT
-- sales.branch_id INTEGER

-- Nota: El código de migración detecta si la columna existe antes de agregarla
