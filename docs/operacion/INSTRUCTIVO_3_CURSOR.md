# Instructivo 3 — Cursor: Configuración Completa Sin Choques

> **Para:** Cursor IDE (v2.5+) en PC de desarrollo  
> **Propósito:** Configurar Cursor para que comparta MCPs con Claude Code, use AGENTS.md unificado, instale plugins del marketplace, y NO choque con lo ya instalado en Claude Code.  
> **Prerequisito:** Instructivos 1 y 2 ejecutados en Claude Code.

---

## Principio clave — qué se comparte y qué es exclusivo

```
~/.claude/agents/    ← Cursor LOS LEE TAMBIÉN (no duplicar)
~/.claude/skills/    ← Cursor LOS LEE TAMBIÉN (no duplicar)
~/.claude/settings.json ← Solo Claude Code
~/.cursor/mcp.json   ← Solo Cursor (copiar los MCPs del inst. 2)
.cursor/rules/*.mdc  ← Solo Cursor
AGENTS.md            ← UNIVERSAL (Claude Code + Cursor + Codex)
```

**Regla de oro:** lo que ya instalaste en `~/.claude/agents/` no lo instales de nuevo en Cursor. Ya lo puede usar.

---

## Paso 1 — Verificar versión de Cursor

```bash
cursor --version
# Necesitas 2.4+ para subagentes, 2.5+ para marketplace plugins
```

Si tienes menos de 2.5: Help → Check for Updates.

---

## Paso 2 — AGENTS.md (formato universal)

En TITAN POS ya está creado: **`AGENTS.md`** en la raíz del proyecto (basado en CLAUDE.md).

Para otros proyectos (CatálogoPro, FacturaMeEsta) ver las plantillas en el instructivo original o en Cursor docs.

---

## Paso 3 — Configurar MCPs en Cursor

Cursor usa `~/.cursor/mcp.json`. En este proyecto tienes una plantilla:

- **`docs/otros/cursor-mcp.json.ejemplo`** — cópiala a `~/.cursor/mcp.json`:

```bash
mkdir -p ~/.cursor
cp "docs/otros/cursor-mcp.json.ejemplo" ~/.cursor/mcp.json
```

Define en tu entorno (o en `.env` que Cursor cargue) las variables: `TITAN_DATABASE_URL`, `GITHUB_TOKEN`, etc.  
Luego en Cursor: Settings → Tools & MCP → verificar que todos los MCPs aparezcan activos.

---

## Paso 4 — Rules de Cursor (.mdc)

En TITAN POS ya están creadas en **`.cursor/rules/`**:

- `fastapi-python.mdc` — alwaysApply, FastAPI + asyncpg para este proyecto
- `security.mdc` — auth, token, fiscal
- `git-workflow.mdc` — commits, branches

---

## Paso 5 — Plugins del Marketplace

Instalar dentro de Cursor con `/add-plugin` o desde cursor.com/marketplace.

Recomendados: Context7, Cursor Team Kit, Runlayer, Slack (opcional).  
No instalar: agents duplicados de `~/.claude/agents/`, Figma/Stripe si no los usas.

---

## Paso 6 — User Rules globales

En Cursor: **Settings → Rules → User Rules**.  
Pegar el contenido de **`docs/otros/cursor-USER-RULES.txt`** (está en este repo).

---

## Paso 7 — AGENTS.md global (User-level)

Cursor puede leer `~/.cursor/AGENTS.md` para contexto global.  
Plantilla en este repo: **`docs/otros/cursor-AGENTS-global.ejemplo.md`**.  
Cópiala a tu home:

```bash
cp "docs/otros/cursor-AGENTS-global.ejemplo.md" ~/.cursor/AGENTS.md
```

---

## Paso 8 — Herramientas de comunidad (opcionales)

- cursor.directory — buscar rules por framework
- rule-porter — convertir rules entre Cursor y Claude
- chrisboden/cursor-skills — orchestrator mode (añadir MCP en ~/.cursor/mcp.json si lo usas)

---

## Referencia — Claude Code vs Cursor

| Tarea | Herramienta |
|-------|-------------|
| Refactor grande 10+ archivos | Claude Code (Swarm) |
| Escribir código en el editor | Cursor (Composer) |
| Ver diff inline, aceptar cambios | Cursor |
| Tareas largas autónomas | Cursor Long-Running Agents |
| Diagnóstico DB / MCP PostgreSQL | Claude Code o Cursor (si MCP configurado) |

---

## Lo que NO instalar en Cursor para evitar choques

- Agents que ya están en `~/.claude/agents/`
- Todo-en-uno que pise la config de Claude Code
- MCP de PostgreSQL duplicado con la misma DB
- Usar `.cursorrules` legacy; usar `.cursor/rules/*.mdc` + AGENTS.md

---

*Documento de referencia guardado en el repo. Para el checklist de pasos pendientes ver `docs/operacion/INSTRUCTIVO_3_CHECKLIST.md`.*
