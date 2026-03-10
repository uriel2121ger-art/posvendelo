# Checklist — Instructivo 3 (Cursor)

## Hecho en el proyecto TITAN POS

- [x] **AGENTS.md** en la raíz (Paso 2)
- [x] **.cursor/rules/** con `fastapi-python.mdc`, `security.mdc`, `git-workflow.mdc` (Paso 4)
- [x] **docs/otros/cursor-mcp.json.ejemplo** — plantilla MCP (Paso 3)
- [x] **docs/otros/cursor-AGENTS-global.ejemplo.md** — plantilla AGENTS global (Paso 7)
- [x] **docs/otros/cursor-USER-RULES.txt** — texto para User Rules (Paso 6)
- [x] **docs/INSTRUCTIVO_3_CURSOR.md** — instructivo de referencia

---

## Pendiente por hacer tú

### 1. Verificar Cursor
```bash
cursor --version   # 2.5+
```

### 2. MCPs en Cursor
- **Hecho:** `~/.cursor/mcp.json` ya fue creado desde la plantilla del repo.
- Definir en tu entorno (o donde Cursor lea env): `TITAN_DATABASE_URL`, `GITHUB_TOKEN`, `CATALOGO_DATABASE_URL`, `FACTURA_DATABASE_URL` según los MCPs que uses.
- En Cursor: **Settings → Tools & MCP** → comprobar que los servidores aparecen activos.

### 3. User Rules globales
- Cursor → **Settings → Rules → User Rules**.
- Pegar el contenido de **docs/otros/cursor-USER-RULES.txt**.

### 4. AGENTS.md global
- **Hecho:** `~/.cursor/AGENTS.md` ya fue creado desde la plantilla del repo.
- Puedes editarlo en `~/.cursor/AGENTS.md` si quieres ajustar el contexto global.

### 5. Plugins (opcional)
- En Cursor: `/add-plugin context7`, `/add-plugin cursor-team-kit`, `/add-plugin runlayer`, etc.

---

## Orden recomendado

1. Verificar Cursor 2.5+
2. Copiar `mcp.json` a `~/.cursor/` y configurar variables de entorno
3. Pegar User Rules en Settings
4. Copiar AGENTS global a `~/.cursor/AGENTS.md`
5. Instalar plugins si quieres
