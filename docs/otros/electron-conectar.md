# Conectar y arrancar Electron (POSVENDELO)

## Orden recomendado

1. **Backend en marcha** (API + Postgres)  
   Desde la raíz del proyecto:
   ```bash
   docker compose up -d
   ```
   O en desarrollo local:
   ```bash
   cd backend && export $(grep -v '^#' ../.env | xargs) && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```

2. **Electron (solo con `dev`)**  
   Desde `frontend/`:
   ```bash
   cd frontend
   npm run dev
   ```
   Eso levanta el dev server de Vite y abre la ventana de Electron. **No uses** `npm run dev:browser` si quieres Electron; ese comando es solo para probar en Chrome.

## Si la ventana sale en blanco o “no conecta”

- Comprueba que **no** haya otro proceso usando el puerto del dev server (p. ej. 5173).
- Cierra todas las ventanas de Electron y en la terminal donde corría `npm run dev` vuelve a ejecutar:
  ```bash
  npm run dev
  ```
- Revisa la consola de desarrollo en Electron (F12 o Ver > Developer > Developer Tools) por errores de red o CORS. La API debe estar en `http://127.0.0.1:8000` o `http://localhost:8000`.
- Si usas backend en Docker, la API está en el puerto **8000** (mapeado en `docker-compose.yml`). El frontend hace auto-descubrimiento en 8000, 8080, 8090, 3000.

## Resumen

| Qué quieres      | Comando              | Dónde      |
|------------------|----------------------|------------|
| App Electron     | `npm run dev`        | `frontend/` |
| Solo navegador  | `npm run dev:browser`| `frontend/` |
| API + DB        | `docker compose up -d` | raíz del repo |
