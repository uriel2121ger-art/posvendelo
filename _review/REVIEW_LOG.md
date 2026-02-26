# TITAN POS — Revisión Exhaustiva (20 pasadas)
**Fecha**: 2026-02-25
**Objetivo**: Buscar bugs, optimizar, refactorizar, documentar
**Estado**: COMPLETADO — ~85+ bugs identificados

## Resumen de Pasadas
| # | Área | Bugs | Severidad |
|---|------|------|-----------|
| 1 | Auth module | 3 | 1 CRIT, 2 MED |
| 2 | Products module | 5 | 2 CRIT, 3 MED |
| 3 | Sales module | 7 | 3 CRIT, 4 MED |
| 4 | Customers module | 4 | 1 CRIT, 3 MED |
| 5 | Employees module | 4 | 2 CRIT, 2 MED |
| 6 | Turns module | 6 | 2 CRIT, 4 MED |
| 7 | Expenses module | 3 | 1 CRIT, 2 MED |
| 8 | Dashboard module | 3 | 0 CRIT, 3 MED |
| 9 | Inventory module | 3 | 1 CRIT, 2 MED |
| 10 | Sync module | 6 | 2 CRIT, 4 MED |
| 11 | DB connection layer | 1 | 1 CRIT |
| 12 | Shared (auth, event_bridge) | 2 | 1 CRIT, 1 MED |
| 13 | Fiscal module | 10 | 5 CRIT, 5 MED |
| 14 | Remote/Mermas modules | 9 | 3 CRIT, 6 MED |
| 15 | Terminal.tsx (POS) | 6 | 2 CRIT, 4 MED |
| 16 | Tab components | 6 | 1 CRIT, 5 MED |
| 17 | posApi.ts + utils | 2 | 0 CRIT, 2 MED |
| 18 | App/Login/TopNavbar | 2 | 2 CRIT |
| 19 | Tests + migrations + SQL | 9 | 3 CRIT, 6 MED |
| 20 | Schemas/types/config/docker | 7 | 3 CRIT, 4 MED |

---

## Hallazgos por Ronda

### Ronda 1: Auth Module
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| AUTH-1 | `auth/routes.py:50-58` | CRIT | `bcrypt` importado dentro de `try` pero usado en `except` — NameError si import falla |
| AUTH-2 | `shared/auth.py:58` | MED | JTI generado pero nunca almacenado — no hay revocación de tokens |
| AUTH-3 | `auth/routes.py:82` | MED | Role default `"cajero"` no está en lista canónica CLAUDE.md |

### Ronda 2: Products Module
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| PROD-1 | `products/routes.py:95,264,400` | CRIT | Rutas `/scan/{sku}` y `/categories/list` sombreadas por `/{product_id}` |
| PROD-2 | `products/routes.py:210,343,387` | CRIT | `int(auth["sub"])` sin try/except — crash si sub no es numérico |
| PROD-3 | `products/routes.py:329-331` | MED | `float - Decimal` TypeError en operation="set" |
| PROD-4 | `products/schemas.py:15-17` | MED | `float` para precios — viola regla Decimal |
| PROD-5 | `products/routes.py` | MED | Missing `synced=0` en algunas mutaciones |

### Ronda 3: Sales Module
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| SALE-1 | `sales/routes.py:332,499,761` | CRIT | `NOW()::text` en columna TIMESTAMP |
| SALE-2 | `sales/routes.py:780` | CRIT | Wallet reversal FOR UPDATE solo selecciona `id` — falta `balance` |
| SALE-3 | `sales/saga.py:382-399` | CRIT | `_confirm_source_deduction` falta FOR UPDATE lock |
| SALE-4 | `sales/routes.py:224` | MED | Kit demand usa `float` en vez de Decimal |
| SALE-5 | `sales/routes.py:687` | MED | Cancel stock usa `float` |
| SALE-6 | `sales/schemas.py:39` | MED | `cash_received` falta `ge=0` |
| SALE-7 | `sales/event_sourcing.py:301-312` | MED | `rebuild_state()` ignora descuentos por ítem |

### Ronda 4: Customers Module
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| CUST-1 | `customers/routes.py` | CRIT | `credit_limit` como float, `available_credit` con float subtraction |
| CUST-2 | `customers/schemas.py:27` | MED | `credit_limit: Optional[float]` debe ser Decimal |
| CUST-3 | `customers/routes.py` | MED | Missing FOR UPDATE en operaciones de crédito |
| CUST-4 | `customers/routes.py` | MED | `synced=0` inconsistente |

### Ronda 5: Employees Module
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| EMP-1 | `employees/routes.py:90,110` | CRIT | `created_at` pasado como `.isoformat()` string a TIMESTAMP |
| EMP-2 | `employees/routes.py:104` | CRIT | `hire_date` como string en vez de `datetime.date` |
| EMP-3 | `employees/schemas.py:18,30` | MED | `base_salary`/`commission_rate` como float |
| EMP-4 | `employees/routes.py` | MED | Missing `updated_at = NOW()` en update/delete |

### Ronda 6: Turns Module
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| TURN-1 | `turns/routes.py:45,87,316` | CRIT | `datetime.now(timezone.utc)` (tz-aware) a TIMESTAMP WITHOUT TZ — **ROOT CAUSE BUG-001** |
| TURN-2 | `turns/schemas.py` | CRIT | `"^(in|out)$"` bloquea tipo 'expense' usado en close_turn |
| TURN-3 | `turns/routes.py` | MED | Falta validación de turno activo antes de movimientos |
| TURN-4 | `turns/routes.py` | MED | `float` para montos de caja |
| TURN-5 | `turns/routes.py` | MED | Missing NOWAIT en FOR UPDATE |
| TURN-6 | `turns/routes.py` | MED | `synced=0` inconsistente |

### Ronda 7: Expenses Module
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| EXP-1 | `expenses/routes.py:35-54` | CRIT | `/summary` sin try/except — **ROOT CAUSE BUG-006** |
| EXP-2 | `expenses/routes.py:79` | MED | FOR UPDATE sin NOWAIT |
| EXP-3 | `expenses/routes.py:72,94` | MED | datetime obj vs posible TEXT column — tipo inconsistente |

### Ronda 8: Dashboard Module
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| DASH-1 | `dashboard/routes.py:79-80,262-279` | MED | `CURRENT_DATE::text` en 8 lugares — debe ser `to_char()` |
| DASH-2 | `dashboard/schemas.py:7-13` | MED | `float` para montos en respuestas |
| DASH-3 | `dashboard/routes.py` | MED | Sin paginación en queries que pueden retornar muchos registros |

### Ronda 9: Inventory Module
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| INV-1 | `inventory/routes.py:121` | CRIT | `int(auth["sub"])` sin try/except dentro de transacción |
| INV-2 | `inventory/routes.py:133` | MED | `body.reference_id or "manual_adjust"` — falsy pattern (0 sería falsy) |
| INV-3 | `inventory/routes.py` | MED | Falta validación de cantidades negativas |

### Ronda 10: Sync Module
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| SYNC-1 | `sync/routes.py:131` | CRIT | `since` pasado como raw string a asyncpg |
| SYNC-2 | `sync/routes.py:273-279` | CRIT | `stock`/`min_stock` missing en ON CONFLICT UPDATE |
| SYNC-3 | `sync/schemas.py:11` | MED | `Field(max_length=5000)` ignorado en `List` Pydantic v2 — DoS |
| SYNC-4 | `sync/routes.py:316` | MED | customers read-then-write sin FOR UPDATE |
| SYNC-5 | `sync/routes.py` | MED | Sin límite de batch size |
| SYNC-6 | `sync/routes.py` | MED | Timestamps inconsistentes (string vs datetime) |

### Ronda 11: DB Connection Layer
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| DB-1 | `db/connection.py:87` | CRIT | `_named_to_positional` regex matchea dentro de string literals SQL |

### Ronda 12: Shared Modules
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| SHARED-1 | `shared/event_bridge.py:96` | CRIT | `.event_type` chequeado antes de `.type` — viola regla explícita |
| SHARED-2 | `shared/domain_event.py:337-361` | MED | `replay_unprocessed()` nunca marca eventos como procesados |

### Ronda 13: Fiscal Module
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| FISC-1 | `fiscal/cfdi_builder.py:420-438` | CRIT | Nota crédito usa PUE+FormaPago99 — ilegal SAT |
| FISC-2 | `fiscal/cfdi_builder.py:192-193` | CRIT | Montos usan `:.2f` rounding — debe ser ROUND_DOWN truncation |
| FISC-3 | `fiscal/signature.py:171-207` | CRIT | Cadena original simplificada invalida todos los CFDI auto-firmados |
| FISC-4 | `fiscal/routes.py:511-522` | CRIT | `/stealth/verify-pin` SIN autenticación |
| FISC-5 | `fiscal/xml_ingestor.py:16-24` | CRIT | Fallback a XML parser vulnerable a XXE |
| FISC-6 | `fiscal/cfdi_service.py:339-356` | MED | `_CFDI_ALLOWED_COLS` falta 9 columnas — pérdida silenciosa de datos |
| FISC-7 | `fiscal/cfdi_service.py:192,250,393,419` | MED | `datetime.now()` naive (sin timezone) |
| FISC-8 | `fiscal/sat_catalog.py` | MED | Módulo completo es in-memory sync — no async PostgreSQL |
| FISC-9 | `fiscal/routes.py:549,703` | MED | RBAC inconsistente — excluye `gerente`/`manager` en algunos endpoints |
| FISC-10 | `fiscal/cfdi_builder.py` | MED | Missing validación de RFC format |

### Ronda 14: Remote + Mermas Modules
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| REM-1 | `remote/routes.py:68,179,257` | CRIT | `int(auth["sub"])` sin try/except |
| REM-2 | `remote/routes.py:245,253` | CRIT | `old_price` como float rompe round() precision |
| REM-3 | `remote/schemas.py:17` | MED | `PriceChangeRemote.new_price` es float no Decimal |
| REM-4 | `remote/routes.py:291-293` | MED | Date filter via `::text` |
| MERM-1 | `mermas/routes.py:100-112` | CRIT | Missing null-check post FOR UPDATE en product |
| MERM-2 | `mermas/routes.py:83-93` | MED | `synced=0` faltante en loss_records |
| MERM-3 | `mermas/routes.py:98` | MED | qty como float |
| REM-5 | `remote/routes.py` | MED | Missing paginación |
| MERM-4 | `mermas/routes.py` | MED | No valida qty > 0 |

### Ronda 15: Terminal.tsx (POS Frontend)
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| TERM-1 | `Terminal.tsx:779` | CRIT | F-keys disparan sin token guard — API calls sin auth |
| TERM-2 | `Terminal.tsx:22-33` | CRIT | `CartItem` falta `priceRetail`/`priceWholesale` |
| TERM-3 | `Terminal.tsx:231-250` | MED | `cancelledRef` pattern en vez de `requestIdRef` |
| TERM-4 | `Terminal.tsx:485-501` | MED | `updateItemQty` acepta NaN |
| TERM-5 | `Terminal.tsx:841` | MED | Ctrl+D prompt NaN propagation |
| TERM-6 | `Terminal.tsx:850` | MED | Ctrl+G prompt NaN propagation |

### Ronda 16: Tab Components Frontend
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| TAB-1 | `TopNavbar.tsx:83-84` | CRIT | **ROOT CAUSE BUG-005**: `hash + reload()` race en Electron |
| TAB-2 | `TopNavbar.tsx:79` | MED | Logout borra pendingTickets — viola regla preservación |
| TAB-3 | `ShiftsTab.tsx:252-254` | MED | `history` stale closure en saveHistory |
| TAB-4 | `ShiftsTab.tsx` | MED | Missing busy guards en openShift/closeShift |
| TAB-5 | `ProductsTab.tsx:109` | MED | Precio guardado sin `Math.round(x * 100) / 100` |
| TAB-6 | `ShiftsTab.tsx` | MED | No maneja error de API en operaciones de turno |

### Ronda 17: posApi.ts + Utils + Stores
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| API-1 | `posApi.ts:347-359` | MED | `CreateSalePayload` falta `mixed_wallet`/`mixed_gift_card` |
| API-2 | `posApi.ts` | MED | Response types usan `number` para montos — debería documentar precisión |

### Ronda 18: App/Login/TopNavbar
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| APP-1 | `TopNavbar.tsx:83-84` | CRIT | **BUG-005 ROOT CAUSE** confirmado — race condition Electron |
| APP-2 | `TopNavbar.tsx:79` | CRIT | Logout destruye datos de tickets pendientes |

### Ronda 19: Tests + Migrations + SQL Schemas
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| TEST-1 | `test_sale_creation.py:30`, `test_module_mermas.py:32,56`, `test_module_remote.py:45` | CRIT | `NOW()::text` a TIMESTAMP columnas |
| TEST-2 | `test_sale_creation.py:285-286` | CRIT | `IN (:u1, :u2)` — syntax inválido para asyncpg wrapper |
| TEST-3 | `migrations/007_audit_log.sql:21` | CRIT | `BOOLEAN DEFAULT 1` — SQL inválido en PostgreSQL |
| MIG-1 | `migrations/017_unify_*.sql:35,40,58` | MED | Syntax SQLite (`INSERT OR IGNORE`, `datetime('now')`) en migraciones PostgreSQL |
| MIG-2 | `migrations/016_fix_backups_*.sql:12-20` | MED | `ADD COLUMN` sin `IF NOT EXISTS` — no idempotente |
| MIG-3 | `migrations/016_*.sql`, `014_*.sql` | MED | Sin `BEGIN/COMMIT` — schema parcial en error |
| MIG-4 | `migrations/add_domain_events_table.sql:12,16` | MED | `TIMESTAMP` sin timezone inconsistente con migraciones nuevas |
| TEST-4 | `test_db_routes.py:73-94` | MED | Materialized views assert `len > 0` — siempre falla en test DB |
| TEST-5 | `test_sale_creation.py:120-145` | MED | Stock deducido sin FOR UPDATE ni inventory_movements |

### Ronda 20: Schemas/Types/Config/Docker
| Bug | Archivo:Línea | Severidad | Descripción |
|-----|--------------|-----------|-------------|
| CFG-1 | `titan-server/server/models.py:9` | CRIT | `condecimal` removido en Pydantic v2 — crash al iniciar |
| CFG-2 | `titan-server/server/titan_gateway.py:248-254` | CRIT | `allow_credentials=True` + `origins=["*"]` — violación spec CORS |
| CFG-3 | `employees/routes.py:90,110` | CRIT | `.isoformat()` string a TIMESTAMP (confirmado R5) |
| CFG-4 | Todos `*/schemas.py` | MED | `float` para campos monetarios en TODOS los schemas — viola regla Decimal |
| CFG-5 | `posApi.ts:347-359` | MED | `CreateSalePayload` falta `mixed_wallet`/`mixed_gift_card` (confirmado R17) |
| CFG-6 | Todas las rutas | MED | RBAC roles inconsistentes — `gerente`/`dueño` vs `manager`/`owner` |
| CFG-7 | `conftest.py:22-32` | MED | Conflicto savepoint en transacciones anidadas de tests |

---

## Root Causes Identificados
| Bug Original | Root Cause | Ubicación |
|-------------|-----------|-----------|
| BUG-001 (turnos crash) | `datetime.now(timezone.utc)` → tz-aware a TIMESTAMP WITHOUT TZ | `turns/routes.py:45,87,316` |
| BUG-005 (logout loop) | `window.location.hash + reload()` race en Electron | `TopNavbar.tsx:83-84` |
| BUG-006 (expenses 500) | `/summary` endpoint sin try/except | `expenses/routes.py:35-54` |

## Bugs Más Críticos (Top 10)
1. **FISC-4**: Endpoint `/stealth/verify-pin` sin autenticación (seguridad)
2. **FISC-5**: XML parser vulnerable a XXE (seguridad)
3. **CFG-1**: `condecimal` crash en Pydantic v2 (titan-server no inicia)
4. **CFG-2**: CORS credentials+wildcard (titan-gateway CORS roto)
5. **DB-1**: Regex de named params matchea dentro de string literals SQL
6. **TURN-1/BUG-001**: datetime tz-aware a TIMESTAMP WITHOUT TZ
7. **SALE-1**: `NOW()::text` en columnas TIMESTAMP
8. **PROD-1**: Route shadowing — `/scan/{sku}` inaccesible
9. **TEST-3/MIG-1**: Migraciones con syntax SQLite/inválido PostgreSQL
10. **FISC-1**: Nota crédito CFDI con método/forma de pago ilegales SAT

## Estadísticas Globales
- **Total bugs encontrados**: ~85+
- **Críticos**: ~30
- **Medio**: ~55
- **Archivos afectados**: ~40+
- **Módulos con más bugs**: Fiscal (10), Sales (7), Sync (6), Turns (6), Remote+Mermas (9)
