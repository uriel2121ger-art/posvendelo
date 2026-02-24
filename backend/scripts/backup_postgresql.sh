#!/bin/bash
# Script de Backup PostgreSQL para TITAN POS

# Cargar configuración
CONFIG_FILE="${1:-data/config/database.json}"

# Server-only policy
NODE_ROLE="${TITAN_NODE_ROLE:-server}"
if [ "$NODE_ROLE" != "server" ]; then
    echo "❌ Backups solo permitidos en nodo servidor (TITAN_NODE_ROLE=server)"
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Archivo de configuración no encontrado: $CONFIG_FILE"
    exit 1
fi

# Extraer configuración PostgreSQL
HOST=$(grep -o '"host"[[:space:]]*:[[:space:]]*"[^"]*"' "$CONFIG_FILE" | cut -d'"' -f4)
PORT=$(grep -o '"port"[[:space:]]*:[[:space:]]*[0-9]*' "$CONFIG_FILE" | grep -o '[0-9]*')
DATABASE=$(grep -o '"database"[[:space:]]*:[[:space:]]*"[^"]*"' "$CONFIG_FILE" | cut -d'"' -f4)
USER=$(grep -o '"user"[[:space:]]*:[[:space:]]*"[^"]*"' "$CONFIG_FILE" | cut -d'"' -f4)
PASSWORD_FILE=$(grep -o '"password"[[:space:]]*:[[:space:]]*"[^"]*"' "$CONFIG_FILE" | cut -d'"' -f4)
PASSWORD="${POSTGRES_PASSWORD:-$PASSWORD_FILE}"

if [ -z "$HOST" ] || [ -z "$DATABASE" ] || [ -z "$USER" ] || [ -z "$PASSWORD" ]; then
    echo "❌ Configuración PostgreSQL incompleta"
    exit 1
fi

# Directorio de backups
BACKUP_DIR="${2:-data/databases/backups}"
mkdir -p "$BACKUP_DIR"

# Timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/titan_pos_${TIMESTAMP}.dump"

echo "============================================================"
echo "PostgreSQL Backup - TITAN POS"
echo "============================================================"
echo "Host:     $HOST:$PORT"
echo "Database: $DATABASE"
echo "Backup:   $BACKUP_FILE"
echo "============================================================"
echo ""

# Exportar variable de contraseña
export PGPASSWORD="$PASSWORD"

# Crear backup
echo "💾 Creando backup..."
pg_dump -h "$HOST" -p "${PORT:-5432}" -U "$USER" -d "$DATABASE" -Fc -f "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "✅ Backup creado exitosamente: $BACKUP_FILE ($BACKUP_SIZE)"
    echo ""
    echo "Para restaurar:"
    echo "  ./scripts/restore_postgresql.sh $BACKUP_FILE"
    unset PGPASSWORD
    exit 0
else
    echo "❌ Error creando backup"
    unset PGPASSWORD
    exit 1
fi
