# Scripts — POSVENDELO

Scripts de utilidad en la raíz del proyecto.

| Script | Uso |
|--------|-----|
| `api_edge_cases.sh` | Pruebas de edge cases contra la API. |
| `test_fastapi.py` | Test rápido de conectividad FastAPI. |
| `homelab-auto-deploy.example.sh` | Plantilla de auto-deploy en el servidor central (192.168.10.90): copiar a `/opt/posvendelo/auto-deploy.sh` en el homelab. Ver [docs/operacion/HOMELAB.md](../docs/operacion/HOMELAB.md). |

Ejecución desde la raíz del repo:

```bash
bash scripts/api_edge_cases.sh
python3 scripts/test_fastapi.py
```
