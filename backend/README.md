# TITAN POS v3.0.2

Sistema de Punto de Venta profesional con soporte multi-sucursal, facturación electrónica CFDI 4.0, y sincronización en tiempo real.

## Características Principales

### Ventas y Facturación
- **Punto de Venta Intuitivo**: Interfaz táctil optimizada para operación rápida
- **Facturación CFDI 4.0**: Integración con PAC para timbrado automático
- **Múltiples Métodos de Pago**: Efectivo, tarjeta, crédito, mixto
- **Descuentos Flexibles**: Por porcentaje o monto fijo, a nivel producto o venta
- **Tickets Personalizables**: Diseño configurable con logo y datos fiscales

### Inventario
- **Control de Stock**: Seguimiento en tiempo real por sucursal
- **Alertas de Inventario**: Notificaciones de stock bajo
- **Códigos de Barras**: Soporte EAN-13, generación automática de SKU
- **Importación Masiva**: CSV/Excel para productos, clientes, ventas históricas

### Clientes y Fidelización
- **Sistema MIDAS**: Programa de puntos con acumulación y redención
- **Crédito a Clientes**: Control de límites y saldos
- **Historial Completo**: Todas las transacciones por cliente
- **Tarjetas de Regalo**: Sistema integrado de gift cards

### Multi-Sucursal
- **Sincronización Bidireccional**: Datos sincronizados entre sucursales
- **Gateway Central**: Servidor de sincronización para múltiples puntos
- **Modo Offline**: Operación continua sin conexión, sincronización posterior
- **Reportes Consolidados**: Vista unificada de todas las sucursales

### Administración
- **Turnos de Caja**: Apertura, cortes parciales, cierre con arqueo
- **Reportes Detallados**: Ventas, inventario, clientes, fiscal
- **Usuarios y Permisos**: Control de acceso granular
- **Respaldos Automáticos**: Protección de datos configurable

---

## Instalación Rápida

### Requisitos
- **Sistema Operativo**: Windows 10/11, Ubuntu 20.04+, macOS 10.15+
- **Python**: 3.10 o superior
- **PostgreSQL**: 14 o superior
- **RAM**: 4GB mínimo, 8GB recomendado

### Pasos

1. **Extraer el archivo ZIP**
   ```bash
   unzip TITAN_POS_v3.0.2_*.zip
   cd TITAN_POS_v3.0.2_*
   ```

2. **Crear entorno virtual**
   ```bash
   # Linux/macOS
   python3 -m venv venv
   source venv/bin/activate

   # Windows
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Instalar dependencias**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar PostgreSQL**
   ```sql
   CREATE DATABASE titan_pos;
   CREATE USER titan_user WITH PASSWORD 'tu_password';
   GRANT ALL PRIVILEGES ON DATABASE titan_pos TO titan_user;
   ```

5. **Configurar conexión**
   ```bash
   cp data/config/database.json.template data/config/database.json
   # Editar con tus credenciales
   ```

6. **Iniciar aplicación**
   ```bash
   # Linux/macOS
   ./TITAN_POS.sh

   # Windows
   TITAN_POS.bat

   # O directamente
   python -m app.main
   ```

---

## Primer Inicio

1. La aplicación detectará que no hay configuración y mostrará el **Wizard de Configuración**
2. Ingresa los datos de conexión a PostgreSQL
3. El sistema creará las tablas automáticamente
4. Usuario por defecto: `admin` / `admin123`
5. **Cambiar la contraseña inmediatamente** desde Configuración > Usuarios

---

## Estructura del Proyecto

```
TITAN_POS/
├── app/                    # Código principal de la aplicación
│   ├── core.py            # Lógica de negocio central
│   ├── main.py            # Punto de entrada
│   ├── dialogs/           # Ventanas de diálogo
│   ├── ui/                # Componentes de interfaz
│   ├── wizards/           # Asistentes (importación, configuración)
│   ├── services/          # Servicios (sync, backup, offline)
│   ├── fiscal/            # Módulo de facturación CFDI
│   └── utils/             # Utilidades generales
├── src/
│   └── infra/             # Infraestructura (base de datos, migraciones)
├── data/
│   └── config/            # Archivos de configuración
├── docs/                  # Documentación técnica
├── server/                # Gateway de sincronización
└── requirements.txt       # Dependencias Python
```

---

## Documentación

| Documento | Descripción |
|-----------|-------------|
| [MANUAL_USUARIO.md](docs/MANUAL_USUARIO.md) | Guía completa para usuarios |
| [GUIA_INSTALACION.md](docs/installation/GUIA_INSTALACION.md) | Instalación detallada |
| [DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) | Guía para desarrolladores |
| [ARQUITECTURA.md](docs/ARQUITECTURA_COMPLETA.md) | Arquitectura del sistema |
| [API.md](docs/API.md) | Referencia de API interna |
| [SECURITY.md](docs/SECURITY.md) | Guía de seguridad |
| [CHANGELOG.md](CHANGELOG.md) | Historial de cambios |

---

## Soporte

### Problemas Comunes

**Error: psycopg2 no instalado**
```bash
pip install psycopg2-binary
```

**Error de conexión a PostgreSQL**
- Verificar que PostgreSQL esté corriendo: `sudo systemctl status postgresql`
- Verificar credenciales en `data/config/database.json`
- Verificar que el usuario tenga permisos sobre la base de datos

**La aplicación no inicia**
- Verificar versión de Python: `python3 --version` (requiere 3.10+)
- Verificar dependencias: `pip install -r requirements.txt`
- Revisar logs en `logs/` para más detalles

### Logs

Los logs se guardan en:
- `logs/titan_pos.log` - Log principal de la aplicación
- `logs/sync.log` - Log de sincronización
- `logs/fiscal.log` - Log de facturación

---

## Licencia

TITAN POS es software propietario. Todos los derechos reservados.

---

## Versión

- **Versión**: 3.0.2
- **Fecha**: 2026-01-30
- **Build**: 20260130_230954

---

*TITAN POS © 2026 - Sistema de Punto de Venta Profesional*
