#!/bin/bash
# ============================================
# TITAN POS - Script de Backup Completo
# Respalda todos los datos críticos del cliente
# ============================================

set -e

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1" >&2; }
log_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
log_info() { echo -e "${BLUE}[i]${NC} $1"; }

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║        💾 BACKUP COMPLETO TITAN POS                         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ============================================
# DETECTAR INSTALACIÓN DE TITAN POS
# ============================================

# Opción 1: Directorio actual si tiene la estructura correcta
CURRENT_DIR="$(pwd)"
if [ -f "$CURRENT_DIR/data/databases/pos.db" ]; then
    INSTALL_DIR="$CURRENT_DIR"
    log_info "Usando directorio actual: $INSTALL_DIR"
# Opción 2: Directorio del script
else
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
    
    if [ -f "$PROJECT_ROOT/data/databases/pos.db" ]; then
        INSTALL_DIR="$PROJECT_ROOT"
        log_info "Usando directorio del script: $INSTALL_DIR"
    # Opción 3: Variable de entorno
    elif [ -n "$TITAN_POS_DIR" ] && [ -f "$TITAN_POS_DIR/data/databases/pos.db" ]; then
        INSTALL_DIR="$TITAN_POS_DIR"
        log_info "Usando variable TITAN_POS_DIR: $INSTALL_DIR"
    else
        log_error "No se encontró una instalación válida de TITAN POS"
        echo ""
        echo "Asegúrate de ejecutar este script desde el directorio de TITAN POS:"
        echo "  cd /ruta/a/TITAN_POS"
        echo "  bash scripts/backup_completo.sh"
        echo ""
        echo "O especifica la ubicación:"
        echo "  export TITAN_POS_DIR=/ruta/a/TITAN_POS"
        echo "  bash scripts/backup_completo.sh"
        exit 1
    fi
fi

# Verificar que existe la base de datos
if [ ! -f "$INSTALL_DIR/data/databases/pos.db" ]; then
    log_error "Base de datos no encontrada en: $INSTALL_DIR/data/databases/pos.db"
    exit 1
fi

cd "$INSTALL_DIR"

# Crear directorio de backup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$INSTALL_DIR/backups/pre-update/backup_completo_${TIMESTAMP}"
mkdir -p "$BACKUP_DIR"
mkdir -p "$BACKUP_DIR/database"
mkdir -p "$BACKUP_DIR/config"
mkdir -p "$BACKUP_DIR/app"
mkdir -p "$BACKUP_DIR/src"

log_info "Creando backup completo en: $BACKUP_DIR"

# ============================================
# 1. BACKUP DE BASE DE DATOS
# ============================================
log_info "[1/6] Respaldando base de datos..."

DB_PATH="$INSTALL_DIR/data/databases/pos.db"
cp "$DB_PATH" "$BACKUP_DIR/database/pos.db"
log_success "Base de datos respaldada ($(du -h "$BACKUP_DIR/database/pos.db" | cut -f1))"

# Verificar integridad
if command -v sqlite3 &> /dev/null; then
    INTEGRITY=$(sqlite3 "$BACKUP_DIR/database/pos.db" "PRAGMA integrity_check;" 2>/dev/null || echo "error")
    if [ "$INTEGRITY" = "ok" ]; then
        log_success "Integridad de la base de datos verificada"
    else
        log_warning "No se pudo verificar la integridad de la base de datos"
    fi
    
    # Exportar schema
    sqlite3 "$BACKUP_DIR/database/pos.db" ".schema" > "$BACKUP_DIR/database/schema_export.sql" 2>/dev/null || true
    if [ -s "$BACKUP_DIR/database/schema_export.sql" ]; then
        log_success "Schema exportado"
    fi
fi

# ============================================
# 2. BACKUP DE CONFIGURACIONES
# ============================================
log_info "[2/6] Respaldando configuraciones..."

# config.json
if [ -f "$INSTALL_DIR/data/config/config.json" ]; then
    cp "$INSTALL_DIR/data/config/config.json" "$BACKUP_DIR/config/config.json"
    log_success "config.json respaldado"
else
    log_warning "config.json no encontrado"
fi

# pos_config.json
if [ -f "$INSTALL_DIR/data/pos_config.json" ]; then
    cp "$INSTALL_DIR/data/pos_config.json" "$BACKUP_DIR/config/pos_config.json"
    log_success "pos_config.json respaldado (ticket, impresoras, caja)"
else
    log_warning "pos_config.json no encontrado"
fi

# feature_flags.json
if [ -f "$INSTALL_DIR/data/config/feature_flags.json" ]; then
    cp "$INSTALL_DIR/data/config/feature_flags.json" "$BACKUP_DIR/config/feature_flags.json"
    log_success "feature_flags.json respaldado"
fi

# Copiar todos los .json de config
if [ -d "$INSTALL_DIR/data/config" ]; then
    find "$INSTALL_DIR/data/config" -name "*.json" -exec cp {} "$BACKUP_DIR/config/" \; 2>/dev/null || true
fi

# ============================================
# 3. BACKUP DE CÓDIGO (app/ y src/)
# ============================================
log_info "[3/6] Respaldando código de la aplicación..."

if [ -d "$INSTALL_DIR/app" ]; then
    cp -r "$INSTALL_DIR/app" "$BACKUP_DIR/app/" 2>/dev/null || true
    # Eliminar logs y cache del backup
    rm -rf "$BACKUP_DIR/app/logs" 2>/dev/null || true
    find "$BACKUP_DIR/app" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    log_success "app/ respaldado"
else
    log_warning "Directorio app/ no encontrado"
fi

if [ -d "$INSTALL_DIR/src" ]; then
    cp -r "$INSTALL_DIR/src" "$BACKUP_DIR/src/" 2>/dev/null || true
    find "$BACKUP_DIR/src" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    log_success "src/ respaldado"
else
    log_warning "Directorio src/ no encontrado"
fi

if [ -d "$INSTALL_DIR/server" ]; then
    cp -r "$INSTALL_DIR/server" "$BACKUP_DIR/server/" 2>/dev/null || true
    find "$BACKUP_DIR/server" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    log_success "server/ respaldado"
fi

# ============================================
# 4. BACKUP DE CATÁLOGO SAT
# ============================================
log_info "[4/6] Respaldando catálogo SAT..."

if [ -d "$INSTALL_DIR/data/sat_catalog" ]; then
    mkdir -p "$BACKUP_DIR/sat_catalog"
    cp -r "$INSTALL_DIR/data/sat_catalog"/* "$BACKUP_DIR/sat_catalog/" 2>/dev/null || true
    log_success "Catálogo SAT respaldado"
elif [ -f "$INSTALL_DIR/data/sat_catalog.db" ]; then
    mkdir -p "$BACKUP_DIR/sat_catalog"
    cp "$INSTALL_DIR/data/sat_catalog.db" "$BACKUP_DIR/sat_catalog/sat_catalog.db"
    log_success "sat_catalog.db respaldado"
else
    log_warning "Catálogo SAT no encontrado"
fi

# ============================================
# 5. BACKUP DE LOGS RECIENTES
# ============================================
log_info "[5/6] Respaldando logs recientes..."

mkdir -p "$BACKUP_DIR/logs"
if [ -d "$INSTALL_DIR/logs" ]; then
    find "$INSTALL_DIR/logs" -name "*.log" -mtime -7 -exec cp {} "$BACKUP_DIR/logs/" \; 2>/dev/null || true
    log_success "Logs recientes respaldados"
elif [ -d "$INSTALL_DIR/app/logs" ]; then
    find "$INSTALL_DIR/app/logs" -name "*.log" -mtime -7 -exec cp {} "$BACKUP_DIR/logs/" \; 2>/dev/null || true
    log_success "Logs recientes respaldados"
else
    log_warning "No se encontraron logs"
fi

# ============================================
# 6. CREAR MANIFEST Y CHECKSUM
# ============================================
log_info "[6/6] Creando manifest y verificando integridad..."

# Crear manifest
cat > "$BACKUP_DIR/manifest.json" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "install_dir": "$INSTALL_DIR",
    "backup_dir": "$BACKUP_DIR",
    "components": {
        "database": $([ -f "$BACKUP_DIR/database/pos.db" ] && echo "true" || echo "false"),
        "config": $([ -f "$BACKUP_DIR/config/config.json" ] && echo "true" || echo "false"),
        "app": $([ -d "$BACKUP_DIR/app" ] && echo "true" || echo "false"),
        "src": $([ -d "$BACKUP_DIR/src" ] && echo "true" || echo "false"),
        "sat_catalog": $([ -d "$BACKUP_DIR/sat_catalog" ] && echo "true" || echo "false")
    }
}
EOF
log_success "Manifest creado"

# Calcular checksum
log_info "Calculando checksum del backup..."
cd "$BACKUP_DIR"
find . -type f -exec sha256sum {} \; > checksum.sha256 2>/dev/null || true
log_success "Checksum calculado"

# ============================================
# RESUMEN
# ============================================
BACKUP_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║        ✅ BACKUP COMPLETO FINALIZADO                        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
log_success "Backup completo creado en: $BACKUP_DIR"
echo ""
echo "📋 Componentes respaldados:"
[ -f "$BACKUP_DIR/database/pos.db" ] && echo "   ✓ Base de datos (pos.db)"
[ -f "$BACKUP_DIR/config/config.json" ] && echo "   ✓ config.json"
[ -f "$BACKUP_DIR/config/pos_config.json" ] && echo "   ✓ pos_config.json (ticket, impresoras, caja)"
[ -d "$BACKUP_DIR/app" ] && echo "   ✓ Código app/"
[ -d "$BACKUP_DIR/src" ] && echo "   ✓ Código src/"
[ -d "$BACKUP_DIR/sat_catalog" ] && echo "   ✓ Catálogo SAT"
echo ""
echo "📊 Tamaño total del backup: $BACKUP_SIZE"
echo ""
echo "💡 Para restaurar este backup, usa:"
echo "   bash scripts/rollback.sh"
echo ""
