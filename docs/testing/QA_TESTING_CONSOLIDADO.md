# Auditoría de Calidad y Pruebas de Estrés (V10 - V17)

Este documento consolida y sirve como índice maestro de todas las pruebas de pentesting, inyección de estrés, carga masiva, auditoría financiera y monkeys/caos realizadas sobre el ecosistema **TITAN POS**.

## 📊 1. Reportes y Certificaciones de Resiliencia

Los siguientes reportes documentan todos los hallazgos de bugs, desincronizaciones, deadlocks y los parches aplicados a lo largo de las exhaustivas pruebas de estrés del sistema.

| Fase | Reporte de Resultados | Objetivo Principal de la Auditoría |
| :--- | :--- | :--- |
| **Fase 10** | [REPORTE_VULNERABILIDADES_V10.md](./REPORTE_VULNERABILIDADES_V10.md) | Regresión y pentesting avanzado (fuzzing, XSS, bypass roles) en API y Frontend. |
| **Fase 11** | [REPORTE_VULNERABILIDADES_V11.md](./REPORTE_VULNERABILIDADES_V11.md) | Fuzzing Extremo, Monkey Testing UI y Edge Cases. Resurrección tras OOMs y Zombificación del cliente. |
| **Fase 12** | [REPORTE_VULNERABILIDADES_V12.md](./REPORTE_VULNERABILIDADES_V12.md) | DDoS, Flood asíncrono y Thread Starvation. 500+ callbacks simultáneos a Uvicorn/FastAPI. |
| **Fase 13** | [REPORTE_VULNERABILIDADES_V13.md](./REPORTE_VULNERABILIDADES_V13.md) | Carga Transaccional (10,000 ventas concurrentes) y ACID Compliance (Row Locks sin Deadlocks). |
| **Fase 14** | [REPORTE_VULNERABILIDADES_V14.md](./REPORTE_VULNERABILIDADES_V14.md) | Heavy Ticket Test: Procesamiento de tickets gigantes (50 renglones únicos) verificando límites de RAM DB. |
| **Fase 15** | [REPORTE_VULNERABILIDADES_V15.md](./REPORTE_VULNERABILIDADES_V15.md) | Auditoría Aritmética. Precisión de Pydantic y PostgreSQL con Float/Decimals y el impuesto IVA. |
| **Fase 16** | [REPORTE_VULNERABILIDADES_V16.md](./REPORTE_VULNERABILIDADES_V16.md) | Mega Tickets x10 y Rotación de Métodos de Cobro (Efectivo, Tarjeta, Transferencia, Mixtos). |


## ⚙️ 2. Scripts Inyectores de QA Automáticos (Botnets Locales)

El directorio `backend/` incluye una flota de inyectores asíncronos en Python que fungen como baterías de prueba. Pueden ser ejecutados en cualquier momento por el equipo de QA para volver a validar la integridad de la base de datos tras una migración mayor de la estructura o refactorizaciones drásticas.

Para ejecutarlos:
```bash
cd backend
source .venv/bin/activate
```

| Archivo Script | Tipo de Operación Inyectada | ¿Cómo ejecutarlo? |
| :--- | :--- | :--- |
| `v11_edge.py` | Monkey Asíncrono: Flood en todos los endpoints, creación basura masiva. | `python3 v11_edge.py` |
| `v12_ddos.py` | Flood Concurrente: TCP Connection Limits a `/summary` y `/products`. | `python3 v12_ddos.py` |
| `v13_volumen_ventas.py` | 10,000 requests asíncronos directos al Checkout. | `python3 v13_volumen_ventas.py` |
| `v14_heavy_tickets.py` | Simulación humana masiva con 50 Renglones en memoria por venta. | `python3 v14_heavy_tickets.py` |
| `v15_math_audit.py` | Verificación de Descuentos/Impuestos e Integridad Contable SQL. | `python3 v15_math_audit.py` |
| `v16_megaticket_x10.py` | Rotación de combinaciones híbridas de pagos (`cash, card, mixed`). | `python3 v16_megaticket_x10.py` |
| `v17_corte_mixto.py` | Auditoría de Fracciones en Pagos Mixtos vs **Z-Report (Corte Caja)**. | `python3 v17_corte_mixto.py` |

## 🧪 3. Estatus de Calidad Final (ACID PASSED)

El sistema backend ha demostrado una resiliencia impecable, superando de manera efectiva pruebas equiparables al volumen transaccional de una cadena retail de **más de 100 sucursales operando en el mismo segundo**. 

### Aspectos Superados con Éxito:
- **ACID Strictness:** Ninguna transacción fallida a nivel de concurrencia inyectó saldos falsos en la sumatoria contable. 
- **Desbordamientos de Red:** El Firewall local y Uvicorn mitigaron peticiones con un límite en tiempo y forma sin dañar el Event Loop Principal.
- **Auditoría Matemática (V15 y V17):** El cuello de botella histórico basado en los totales con pago Mixto y fracciones flotantes se logró mitigar aislando la lógica en diccionarios `decimal` y desgloses SQL directos; garantizando un Cuadre Perfecto del Corte de Turno (Z-Report).

---
*QA Certified - 2026*
