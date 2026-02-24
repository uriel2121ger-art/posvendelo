"""
TITAN POS - Sistema de Actualizaciones
=======================================

Maneja actualizaciones automáticas del sistema y migraciones de base de datos.
"""

from typing import Dict, Optional, Tuple
from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import zipfile

import requests

logger = logging.getLogger(__name__)

# Versión actual del sistema
CURRENT_VERSION = "2.0.0"
VERSION_FILE = "version.json"

class UpdateManager:
    """
    Gestor de actualizaciones para TITAN POS.
    
    Funcionalidades:
    - Verificar nuevas versiones disponibles
    - Descargar y aplicar actualizaciones
    - Ejecutar migraciones de base de datos
    - Rollback en caso de error
    """
    
    def __init__(self, app_dir: str, update_server: str = None):
        self.app_dir = Path(app_dir)
        self.update_server = update_server
        self.backup_dir = self.app_dir / "backups" / "updates"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.version_info = self._load_version_info()
    
    def _load_version_info(self) -> Dict:
        """Carga información de versión actual."""
        version_file = self.app_dir / VERSION_FILE
        if version_file.exists():
            try:
                with open(version_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        
        return {
            "version": CURRENT_VERSION,
            "installed_at": datetime.now().isoformat(),
            "last_update_check": None,
            "update_history": []
        }
    
    def _save_version_info(self):
        """Guarda información de versión."""
        version_file = self.app_dir / VERSION_FILE
        with open(version_file, 'w') as f:
            json.dump(self.version_info, f, indent=2)
    
    def get_current_version(self) -> str:
        """Retorna versión actual."""
        return self.version_info.get("version", CURRENT_VERSION)
    
    def check_for_updates(self) -> Optional[Dict]:
        """
        Verifica si hay actualizaciones disponibles.
        
        Returns:
            Dict con info de actualización si hay nueva versión, None si no.
        """
        if not self.update_server:
            logger.warning("No hay servidor de actualizaciones configurado")
            return None
        
        try:
            response = requests.get(
                f"{self.update_server}/api/v1/updates/latest",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                latest_version = data.get("version")
                current_version = self.get_current_version()
                
                self.version_info["last_update_check"] = datetime.now().isoformat()
                self._save_version_info()
                
                if self._compare_versions(latest_version, current_version) > 0:
                    return {
                        "available": True,
                        "current_version": current_version,
                        "latest_version": latest_version,
                        "release_notes": data.get("release_notes", ""),
                        "download_url": data.get("download_url"),
                        "file_size": data.get("file_size"),
                        "checksum": data.get("checksum")
                    }
                
                return {"available": False, "current_version": current_version}
            
        except Exception as e:
            logger.error(f"Error verificando actualizaciones: {e}")
            return None
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compara versiones. Retorna 1 si v1 > v2, -1 si v1 < v2, 0 si iguales."""
        try:
            parts1 = [int(x) for x in v1.split('.')]
            parts2 = [int(x) for x in v2.split('.')]
            
            for i in range(max(len(parts1), len(parts2))):
                p1 = parts1[i] if i < len(parts1) else 0
                p2 = parts2[i] if i < len(parts2) else 0
                if p1 > p2:
                    return 1
                elif p1 < p2:
                    return -1
            return 0
        except Exception:
            return 0
    
    def download_update(self, download_url: str, checksum: str = None) -> Optional[Path]:
        """
        Descarga actualización.
        
        Args:
            download_url: URL del archivo de actualización
            checksum: SHA256 esperado del archivo
            
        Returns:
            Path al archivo descargado o None si falla
        """
        try:
            logger.info(f"Descargando actualización desde {download_url}")
            
            response = requests.get(download_url, stream=True, timeout=300)
            
            if response.status_code == 200:
                update_file = self.backup_dir / "update_package.zip"
                
                with open(update_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Verificar checksum
                if checksum:
                    file_hash = hashlib.sha256()
                    with open(update_file, 'rb') as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            file_hash.update(chunk)
                    
                    if file_hash.hexdigest() != checksum:
                        logger.error("Checksum no coincide - archivo corrupto")
                        os.remove(update_file)
                        return None
                
                logger.info("Actualización descargada correctamente")
                return update_file
            
        except Exception as e:
            logger.error(f"Error descargando actualización: {e}")
            return None
    
    def create_backup(self) -> Optional[Path]:
        """
        Crea backup antes de actualizar.
        
        Returns:
            Path al archivo de backup
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"pre_update_backup_{timestamp}"
            backup_path = self.backup_dir / backup_name
            
            # Copiar archivos críticos
            critical_dirs = ["app", "src"]
            critical_files = ["requirements.txt", "version.json"]
            
            backup_path.mkdir(parents=True, exist_ok=True)
            
            for dir_name in critical_dirs:
                src_dir = self.app_dir / dir_name
                if src_dir.exists():
                    shutil.copytree(src_dir, backup_path / dir_name)
            
            for file_name in critical_files:
                src_file = self.app_dir / file_name
                if src_file.exists():
                    shutil.copy2(src_file, backup_path / file_name)
            
            logger.info(f"Backup creado: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Error creando backup: {e}")
            return None
    
    def apply_update(self, update_file: Path) -> Tuple[bool, str]:
        """
        Aplica actualización.
        
        Args:
            update_file: Path al archivo ZIP de actualización
            
        Returns:
            Tuple (éxito, mensaje)
        """
        try:
            # Crear backup primero
            backup_path = self.create_backup()
            if not backup_path:
                return False, "No se pudo crear backup"
            
            # Extraer actualización
            extract_dir = self.backup_dir / "update_extract"
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            
            with zipfile.ZipFile(update_file, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # Aplicar archivos actualizados
            for item in extract_dir.iterdir():
                dest = self.app_dir / item.name
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
            
            # Actualizar version.json
            new_version_file = extract_dir / VERSION_FILE
            if new_version_file.exists():
                with open(new_version_file, 'r') as f:
                    new_version = json.load(f).get("version", CURRENT_VERSION)
            else:
                new_version = CURRENT_VERSION
            
            self.version_info["version"] = new_version
            self.version_info["update_history"].append({
                "from": self.get_current_version(),
                "to": new_version,
                "applied_at": datetime.now().isoformat(),
                "backup_path": str(backup_path)
            })
            self._save_version_info()
            
            # Limpiar
            shutil.rmtree(extract_dir)
            os.remove(update_file)
            
            logger.info(f"Actualización aplicada: {new_version}")
            return True, f"Actualizado a versión {new_version}"
            
        except Exception as e:
            logger.error(f"Error aplicando actualización: {e}")
            return False, str(e)
    
    def rollback(self, backup_path: Path) -> Tuple[bool, str]:
        """
        Revierte a un backup anterior.
        
        Args:
            backup_path: Path al directorio de backup
            
        Returns:
            Tuple (éxito, mensaje)
        """
        try:
            if not backup_path.exists():
                return False, "Backup no encontrado"
            
            for item in backup_path.iterdir():
                dest = self.app_dir / item.name
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
            
            logger.info(f"Rollback exitoso desde {backup_path}")
            return True, "Rollback completado"
            
        except Exception as e:
            logger.error(f"Error en rollback: {e}")
            return False, str(e)

class MigrationManager:
    """
    Gestor de migraciones de base de datos.
    
    Maneja cambios de schema entre versiones.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.migrations_dir = Path(__file__).parent.parent / "migrations"
    
    def get_current_schema_version(self) -> int:
        """Obtiene versión actual del schema."""
        # Try to use DatabaseManager if available (PostgreSQL compatible)
        try:
            from src.infra.database import DatabaseManager
            try:
                from app.core import get_core_instance
                core = get_core_instance()
                if core and hasattr(core, 'db'):
                    result = core.db.execute_query(
                        "SELECT version FROM schema_version ORDER BY id DESC LIMIT 1"
                    )
                    return result[0]['version'] if result else 0
            except Exception:
                pass
        except Exception:
            pass
        
        # Fallback: SQLite direct connection (legacy)
        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT version FROM schema_version ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else 0
        except Exception:
            return 0
    
    def run_pending_migrations(self) -> Tuple[bool, str]:
        """
        Ejecuta migraciones pendientes.
        
        Returns:
            Tuple (éxito, mensaje)
        """
        import sqlite3
        
        current = self.get_current_schema_version()
        migrations = self._get_pending_migrations(current)
        
        if not migrations:
            return True, "No hay migraciones pendientes"
        
        try:
            # Try to use DatabaseManager if available (PostgreSQL compatible)
            try:
                from src.infra.database import DatabaseManager
                # Try to get DatabaseManager from core if available
                # This is a fallback - update_manager should ideally receive db_manager
                db_manager = None
                try:
                    from app.core import get_core_instance
                    core = get_core_instance()
                    if core and hasattr(core, 'db'):
                        db_manager = core.db
                except Exception:
                    pass
                
                if db_manager:
                    # Use DatabaseManager (PostgreSQL compatible)
                    for version, sql in migrations:
                        logger.info(f"Ejecutando migración {version}")
                        # Split SQL into individual statements (PostgreSQL doesn't support executescript)
                        statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]
                        for statement in statements:
                            if statement:
                                try:
                                    db_manager.execute_write(statement)
                                except Exception as stmt_err:
                                    # Ignore "already exists" errors during migrations
                                    if 'already exists' not in str(stmt_err).lower() and 'does not exist' not in str(stmt_err).lower():
                                        logger.warning(f"Statement error (may be expected): {stmt_err}")
                        
                        # Record migration
                        db_manager.execute_write(
                            "INSERT INTO schema_version (version, applied_at) VALUES (%s, %s)",
                            (version, datetime.now().isoformat())
                        )
                    
                    return True, f"Aplicadas {len(migrations)} migraciones"
            except Exception as db_manager_err:
                logger.debug(f"DatabaseManager not available, using SQLite fallback: {db_manager_err}")
            
            # Fallback: SQLite direct connection (legacy)
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for version, sql in migrations:
                logger.info(f"Ejecutando migración {version}")
                cursor.executescript(sql)
                cursor.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (%s, %s)",
                    (version, datetime.now().isoformat())
                )
            
            conn.commit()
            conn.close()
            
            return True, f"Aplicadas {len(migrations)} migraciones"
            
        except Exception as e:
            logger.error(f"Error en migración: {e}")
            return False, str(e)
    
    def _get_pending_migrations(self, current_version: int):
        """Obtiene lista de migraciones pendientes."""
        migrations = []
        
        if not self.migrations_dir.exists():
            return migrations
        
        for file in sorted(self.migrations_dir.glob("*.sql")):
            try:
                # Formato: 001_descripcion.sql
                version = int(file.stem.split("_")[0])
                if version > current_version:
                    with open(file, 'r') as f:
                        migrations.append((version, f.read()))
            except Exception:
                continue
        
        return migrations

# API Endpoints para servidor de actualizaciones
def create_update_endpoints(app, version: str, update_dir: str):
    """
    Crea endpoints para servir actualizaciones.
    
    Args:
        app: FastAPI app
        version: Versión actual del servidor
        update_dir: Directorio con archivos de actualización
    """
    from fastapi import HTTPException
    from fastapi.responses import FileResponse, JSONResponse
    
    update_path = Path(update_dir)
    
    @app.get("/api/v1/updates/latest")
    async def get_latest_version():
        """Retorna información de la última versión."""
        version_file = update_path / "latest.json"
        if version_file.exists():
            with open(version_file, 'r') as f:
                return JSONResponse(json.load(f))
        
        return JSONResponse({
            "version": version,
            "release_notes": "",
            "download_url": None
        })
    
    @app.get("/api/v1/updates/download/{version}")
    async def download_version(version: str):
        """Descarga archivo de actualización."""
        update_file = update_path / f"update_{version}.zip"
        if update_file.exists():
            return FileResponse(update_file)
        raise HTTPException(status_code=404, detail="Versión no encontrada")
