# Contexto Global — Desarrollador Full Stack

## Stack principal
- Backend: FastAPI + SQLAlchemy 2.0 + PostgreSQL + Alembic (en otros proyectos asyncpg sin ORM, ej. TITAN POS)
- Deploy: Docker Compose + infraestructura propia
- IDE: Cursor + Claude Code en paralelo
- Idioma de trabajo: español para comunicación, inglés para código

## Proyectos activos
- TITAN POS: sistema POS retail multi-sucursal
- CatálogoPro: SaaS de catálogos digitales, multitenant
- FacturaMeEsta: plataforma CFDI 4.0, integración PAC

## Reglas universales
- Async siempre para I/O
- Pydantic v2 para schemas
- Nunca credenciales en código
- Tests antes de merge
- Commits en español con tipo/scope
