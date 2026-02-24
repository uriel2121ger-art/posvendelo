#!/bin/bash
# Script de Restauración PostgreSQL para TITAN POS

if [ -z "$1" ]; then
    echo "Uso: $0 <backup_file.dump> [config_file]"
    exit 1
fi

BACKUP_FILE="$1"
CONFIG_FILE="${2:-data/config/database.json}"

# Server-only policy
NODE_ROLE="${TITAN_NODE_ROLE:-server}"
if [ "$NODE_ROLE" != "server" ]; then
    echo "❌ Restore solo permitido en nodo servidor (TITAN_NODE_ROLE=server)"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Archivo de backup no encontrado: $BACKUP_FILE"
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

echo "============================================================"
echo "PostgreSQL Restore - TITAN POS"
echo "============================================================"
echo "Host:     $HOST:$PORT"
echo "Database: $DATABASE"
echo "Backup:   $BACKUP_FILE"
echo "============================================================"
echo ""
echo "⚠️  ADVERTENCIA: Esto SOBRESCRIBIRÁ la base de datos actual"
echo "¿Continuar? (s/N)"
read -r CONFIRM

if [ "$CONFIRM" != "s" ] && [ "$CONFIRM" != "S" ]; then
    echo "❌ Restauración cancelada"
    exit 0
fi

# Exportar variable de contraseña
export PGPASSWORD="$PASSWORD"

# Restaurar backup
echo "🔄 Restaurando backup..."
pg_restore -h "$HOST" -p "${PORT:-5432}" -U "$USER" -d "$DATABASE" -c -f "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "✅ Restauración completada exitosamente"
    unset PGPASSWORD
    exit 0
else
    echo "❌ Error restaurando backup"
    unset PGPASSWORD
    exit 1
fi
