#!/bin/bash
# Fix para PostgreSQL - Agregar constraints faltantes
# Ejecutar en la PC servidor (Lupita)

echo "==================================="
echo "  Fix PostgreSQL - TITAN POS"
echo "==================================="
echo ""

# Configuración de la base de datos
# Ajustar según tu configuración
DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="titan_pos"
DB_USER="titan"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SQL_FILE="$SCRIPT_DIR/fix_postgresql_constraints.sql"

if [ ! -f "$SQL_FILE" ]; then
    echo "ERROR: No se encontró $SQL_FILE"
    exit 1
fi

echo "Aplicando fix a la base de datos..."
echo "Host: $DB_HOST"
echo "Base de datos: $DB_NAME"
echo ""

# Ejecutar el script SQL
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$SQL_FILE"

if [ $? -eq 0 ]; then
    echo ""
    echo "==================================="
    echo "  FIX APLICADO CORRECTAMENTE"
    echo "==================================="
    echo ""
    echo "Reinicia TITAN POS para aplicar los cambios."
else
    echo ""
    echo "ERROR: Falló la aplicación del fix."
    echo "Verifica la configuración de la base de datos."
fi
