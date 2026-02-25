#!/bin/bash
# Fix para ToastManager - PC Lupita
# Corrige: TypeError: ToastManager.warning() got an unexpected keyword argument 'duration'

set -e

TITAN_DIR="$HOME/Escritorio/titan_dist"
BACKUP_DIR="$TITAN_DIR/backups/fix_$(date +%Y%m%d_%H%M%S)"

echo "==================================="
echo "  Fix ToastManager - TITAN POS"
echo "==================================="
echo ""

# Verificar que existe el directorio de TITAN
if [ ! -d "$TITAN_DIR" ]; then
    echo "ERROR: No se encontro $TITAN_DIR"
    echo "Verifica la ruta de instalacion de TITAN POS"
    exit 1
fi

# Crear backup
echo "[1/3] Creando backup..."
mkdir -p "$BACKUP_DIR"
cp "$TITAN_DIR/app/ui/components/toast.py" "$BACKUP_DIR/toast.py.bak"
echo "      Backup guardado en: $BACKUP_DIR"

# Copiar archivo corregido
echo "[2/3] Instalando fix..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$SCRIPT_DIR/toast.py" "$TITAN_DIR/app/ui/components/toast.py"
echo "      toast.py actualizado"

# Verificar
echo "[3/3] Verificando instalacion..."
if grep -q "duration: int = 0" "$TITAN_DIR/app/ui/components/toast.py"; then
    echo ""
    echo "==================================="
    echo "  FIX INSTALADO CORRECTAMENTE"
    echo "==================================="
    echo ""
    echo "Reinicia TITAN POS para aplicar los cambios."
    echo ""
else
    echo "ERROR: La verificacion fallo. Restaurando backup..."
    cp "$BACKUP_DIR/toast.py.bak" "$TITAN_DIR/app/ui/components/toast.py"
    exit 1
fi
