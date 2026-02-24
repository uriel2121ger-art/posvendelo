#!/usr/bin/env python3
"""
Script para corregir permisos de PostgreSQL sin sudo
Usa las credenciales del usuario postgres desde database.json
"""

import sys
import json
import re
from pathlib import Path

def main():
    """Corrige permisos de PostgreSQL"""
    print("=" * 60)
    print("🔧 CORRIGIENDO PERMISOS DE POSTGRESQL")
    print("=" * 60)
    print()
    
    # Cargar configuración
    config_paths = [
        "data/config/database.json",
        "data/local_config.json",
        "config/database.json",
    ]
    
    config = None
    config_path = None
    for path in config_paths:
        if Path(path).exists():
            config_path = path
            try:
                with open(path, 'r') as f:
                    config = json.load(f)
                break
            except Exception as e:
                print(f"⚠️  Error leyendo {path}: {e}")
                continue
    
    if not config:
        print("❌ No se encontró archivo de configuración")
        print("   Busca en:", ", ".join(config_paths))
        return 1
    
    pg_config = config.get('postgresql', {})
    user = pg_config.get('user', 'titan')
    db_name = pg_config.get('database', 'titan_pos')
    password = pg_config.get('password', '')
    
    if not password:
        print("❌ Password no configurado en database.json")
        return 1
    
    print(f"📋 Configuración:")
    print(f"   Usuario: {user}")
    print(f"   Base de datos: {db_name}")
    print()
    
    try:
        import psycopg2
    except ImportError:
        print("❌ psycopg2 no está instalado")
        print("   Instala con: pip install psycopg2-binary")
        return 1
    
    try:
        # Conectar como el usuario para verificar permisos
        conn = psycopg2.connect(
            host=pg_config.get('host', 'localhost'),
            port=pg_config.get('port', 5432),
            database=db_name,
            user=user,
            password=password
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Validate username (defense against SQL injection from config file)
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', user):
            print(f"❌ Nombre de usuario inválido: {user}")
            print("   Solo se permiten caracteres alfanuméricos y guión bajo")
            return 1

        from psycopg2 import sql

        print("🔧 Otorgando permisos...")
        print()

        # 1. Otorgar CREATE en schema public
        print("1️⃣ Otorgando CREATE en schema public...")
        try:
            cursor.execute(sql.SQL("GRANT CREATE ON SCHEMA public TO {}").format(sql.Identifier(user)))
            print("   ✅ Permiso CREATE otorgado")
        except Exception as e:
            print(f"   ⚠️  {e}")

        # 2. Hacer propietario del schema (requiere ser superuser o owner actual)
        print("2️⃣ Intentando hacer propietario del schema...")
        try:
            cursor.execute(sql.SQL("ALTER SCHEMA public OWNER TO {}").format(sql.Identifier(user)))
            print("   ✅ Schema public ahora es propiedad de", user)
        except Exception as e:
            print(f"   ⚠️  No se pudo cambiar propietario (requiere sudo): {e}")
            print("   💡 Ejecuta manualmente:")
            print(f"      sudo -u postgres psql -d {db_name} -c \"ALTER SCHEMA public OWNER TO {user};\"")

        # 3. Permisos por defecto
        print("3️⃣ Configurando permisos por defecto...")
        try:
            cursor.execute(sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {}").format(sql.Identifier(user)))
            cursor.execute(sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {}").format(sql.Identifier(user)))
            print("   ✅ Permisos por defecto configurados")
        except Exception as e:
            print(f"   ⚠️  {e}")

        # 4. Cambiar propietario de tablas existentes
        print("4️⃣ Cambiando propietario de tablas existentes...")
        try:
            # user ya fue validado con regex arriba, seguro para PL/pgSQL
            cursor.execute(sql.SQL("""
                DO $$
                DECLARE
                    r RECORD;
                BEGIN
                    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                        EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) || ' OWNER TO {}';
                    END LOOP;
                END $$;
            """).format(sql.Identifier(user)))
            cursor.execute("SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';")
            count = cursor.fetchone()[0]
            if count > 0:
                print(f"   ✅ {count} tablas actualizadas")
            else:
                print("   ℹ️  No hay tablas aún")
        except Exception as e:
            print(f"   ⚠️  {e}")
        
        # 5. Cambiar propietario de secuencias existentes
        print("5️⃣ Cambiando propietario de secuencias existentes...")
        try:
            cursor.execute(sql.SQL("""
                DO $$
                DECLARE
                    r RECORD;
                BEGIN
                    FOR r IN (SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public') LOOP
                        EXECUTE 'ALTER SEQUENCE public.' || quote_ident(r.sequence_name) || ' OWNER TO {}';
                    END LOOP;
                END $$;
            """).format(sql.Identifier(user)))
            cursor.execute("SELECT COUNT(*) FROM information_schema.sequences WHERE sequence_schema = 'public';")
            count = cursor.fetchone()[0]
            if count > 0:
                print(f"   ✅ {count} secuencias actualizadas")
            else:
                print("   ℹ️  No hay secuencias aún")
        except Exception as e:
            print(f"   ⚠️  {e}")
        
        cursor.close()
        conn.close()
        
        print()
        print("✅ Permisos corregidos")
        print()
        print("💡 Si aún hay errores de permisos, ejecuta:")
        print(f"   sudo -u postgres psql -d {db_name} -c \"ALTER SCHEMA public OWNER TO {user};\"")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
