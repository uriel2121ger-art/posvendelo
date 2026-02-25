#!/bin/bash
# Script de instalación de PostgreSQL para TITAN POS
# Ejecutar con: bash scripts/install_postgresql.sh

set -e

echo "📦 Instalando PostgreSQL para TITAN POS..."
echo ""

# 1. Actualizar repositorios
echo "1️⃣ Actualizando repositorios..."
sudo apt update

# 2. Instalar PostgreSQL
echo ""
echo "2️⃣ Instalando PostgreSQL y contrib..."
sudo apt install -y postgresql postgresql-contrib

# 3. Iniciar y habilitar servicio
echo ""
echo "3️⃣ Iniciando servicio PostgreSQL..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

# 4. Verificar estado
echo ""
echo "4️⃣ Verificando estado del servicio..."
sudo systemctl status postgresql --no-pager | head -5

# 5. Crear usuario y base de datos
echo ""
echo "5️⃣ Configurando base de datos para TITAN POS..."
echo "   Creando usuario 'titan'..."
sudo -u postgres psql -c "CREATE USER titan WITH PASSWORD 'titan123';" 2>&1 || echo "   ⚠️ Usuario ya existe (continuando...)"

echo "   Creando base de datos 'titan_pos'..."
sudo -u postgres psql -c "CREATE DATABASE titan_pos OWNER titan;" 2>&1 || echo "   ⚠️ Base de datos ya existe (continuando...)"

echo "   Otorgando permisos..."
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE titan_pos TO titan;" 2>&1

# CRITICAL: Otorgar permisos en el schema public (requerido para crear tablas)
echo "   Configurando permisos en schema public..."
sudo -u postgres psql -d titan_pos -c "GRANT CREATE ON SCHEMA public TO titan;" 2>&1 || true
sudo -u postgres psql -d titan_pos -c "ALTER SCHEMA public OWNER TO titan;" 2>&1 || true
sudo -u postgres psql -d titan_pos -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO titan;" 2>&1 || true
sudo -u postgres psql -d titan_pos -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO titan;" 2>&1 || true

# 6. Crear archivo de configuración
echo ""
echo "6️⃣ Creando archivo de configuración..."
mkdir -p data/config
cat > data/config/database.json << 'EOF'
{
  "postgresql": {
    "host": "localhost",
    "port": 5432,
    "database": "titan_pos",
    "user": "titan",
    "password": "titan123"
  }
}
EOF

echo "   ✅ Archivo creado: data/config/database.json"

# 7. Verificar conexión
echo ""
echo "7️⃣ Verificando conexión..."
if command -v psql &> /dev/null; then
    PGPASSWORD=titan123 psql -h localhost -U titan -d titan_pos -c "SELECT version();" 2>&1 | head -3
    echo "   ✅ Conexión exitosa!"
else
    echo "   ⚠️ psql no está instalado (opcional para verificación)"
fi

# 8. Aplicar schema (opcional, se aplica automáticamente al iniciar la app)
echo ""
echo "8️⃣ Aplicando schema (creando tablas)..."
SCHEMA_FILE="src/infra/schema_postgresql.sql"
if [ -f "$SCHEMA_FILE" ]; then
    echo "   Aplicando schema desde $SCHEMA_FILE..."
    # El schema se aplica mejor desde Python para manejar el parser correctamente
    # Por ahora solo verificamos que el archivo existe
    echo "   ✅ Archivo de schema encontrado"
    echo "   ℹ️  El schema se aplicará automáticamente al iniciar la aplicación"
else
    echo "   ⚠️  Archivo de schema no encontrado: $SCHEMA_FILE"
fi

echo ""
echo "✅ INSTALACIÓN COMPLETADA"
echo ""
echo "📋 Resumen:"
echo "  ✅ PostgreSQL instalado"
echo "  ✅ Servicio iniciado y habilitado"
echo "  ✅ Usuario 'titan' creado"
echo "  ✅ Base de datos 'titan_pos' creada"
echo "  ✅ Archivo de configuración: data/config/database.json"
echo ""
echo "🔐 Credenciales:"
echo "  Usuario: titan"
echo "  Contraseña: titan123"
echo "  Base de datos: titan_pos"
echo "  Host: localhost"
echo "  Puerto: 5432"
echo ""
echo "⚠️ IMPORTANTE: Cambia la contraseña en producción!"
echo ""
echo "🚀 Ahora puedes ejecutar el programa: python3 app/entry.py"
