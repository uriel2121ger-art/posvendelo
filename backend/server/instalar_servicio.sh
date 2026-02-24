#!/bin/bash
# ============================================
# TITAN Gateway - Script de Instalación
# ============================================

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║         TITAN Gateway - Instalación de Servicio              ║"
echo "╚══════════════════════════════════════════════════════════════╝"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/titan-gateway.service"

# Verificar si existe el archivo de servicio
if [ ! -f "$SERVICE_FILE" ]; then
    echo "❌ Error: No se encontró titan-gateway.service"
    exit 1
fi

# Matar proceso actual si existe
echo "🔄 Deteniendo procesos anteriores..."
pkill -f titan_gateway.py 2>/dev/null || true
fuser -k 8000/tcp 2>/dev/null || true
sleep 2

echo "📦 Instalando servicio systemd..."

# Copiar servicio a systemd
sudo cp "$SERVICE_FILE" /etc/systemd/system/titan-gateway.service

# Recargar systemd
sudo systemctl daemon-reload

# Habilitar inicio automático
sudo systemctl enable titan-gateway.service

# Iniciar servicio
sudo systemctl start titan-gateway.service

# Esperar a que inicie
sleep 3

# Verificar estado
echo ""
echo "═══════════════════════════════════════════════════════════════"
if sudo systemctl is-active --quiet titan-gateway.service; then
    echo "✅ TITAN Gateway instalado y activo"
    echo ""
    echo "📋 Comandos útiles:"
    echo "   sudo systemctl status titan-gateway   # Ver estado"
    echo "   sudo systemctl restart titan-gateway  # Reiniciar"
    echo "   sudo systemctl stop titan-gateway     # Detener"
    echo "   sudo journalctl -u titan-gateway -f   # Ver logs"
    echo ""
    echo "🌐 Gateway: http://100.81.7.8:8000"
    curl -s http://127.0.0.1:8000/health 2>/dev/null && echo ""
else
    echo "❌ Error al iniciar el servicio"
    sudo systemctl status titan-gateway.service
fi
echo "═══════════════════════════════════════════════════════════════"
