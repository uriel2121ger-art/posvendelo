"""
Backup Engine - Complete backup and restore system
Supports local, NAS, and S3 backups with encryption
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import gzip
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
# sqlite3 removed - system now uses PostgreSQL exclusively

logger = logging.getLogger(__name__)

class BackupEngine:
    """Complete backup and restore engine for POS system."""
    
    def __init__(self, core, backup_dir: Optional[str] = None):
        """
        Initialize backup engine.
        
        Args:
            core: POSCore instance
            backup_dir: Optional backup directory (defaults to data/backups)
        """
        self.core = core
        
        if backup_dir:
            self.backup_dir = Path(backup_dir)
        else:
            from app.core import DATA_DIR
            self.backup_dir = Path(DATA_DIR) / "backups"
        
        self.backup_dir.mkdir(exist_ok=True, parents=True)
        
        # Get config
        self.config = self.core.read_local_config()
        
        logger.info(f"BackupEngine initialized: {self.backup_dir}")
    
    def create_local_backup(
        self,
        include_media: bool = True,
        compress: bool = True,
        encrypt: bool = False,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Create a complete local backup.
        
        Args:
            include_media: Include images/media files
            compress: Compress backup with gzip
            encrypt: Encrypt backup (requires backup_encrypt_key in config)
            notes: Optional notes for this backup
            
        Returns:
            Dictionary with backup info
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"backup_{timestamp}"
            
            logger.info(f"Creating backup: {backup_name}")
            
            # SECURITY: Create temp directory with restricted permissions
            import tempfile
            temp_dir = Path(tempfile.mkdtemp(
                prefix=f"titan_backup_{timestamp}_",
                dir=self.backup_dir
            ))
            # Restrict permissions to owner only (prevents other users from reading backup data)
            os.chmod(temp_dir, 0o700)
            
            # Step 1: Backup database
            db_backup_path = self._backup_database(temp_dir)
            
            # Step 2: Backup configuration
            config_backup_path = self._backup_configuration(temp_dir)
            
            # Step 3: Backup media (optional)
            if include_media:
                media_backup_path = self._backup_media(temp_dir)
            
            # Step 4: Create manifest
            manifest = {
                'timestamp': timestamp,
                'created': datetime.now().isoformat(),
                'version': '1.0',
                'database': db_backup_path.name if db_backup_path else None,
                'config': config_backup_path.name if config_backup_path else None,
                'media_included': include_media,
                'compressed': compress,
                'encrypted': encrypt,
                'notes': notes,
                'branch_id': self.core.state.branch_id if hasattr(self.core, 'state') else 1
            }
            
            manifest_path = temp_dir / "manifest.json"
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2)
            
            # Step 5: Package everything
            if compress:
                final_backup_path = self.backup_dir / f"{backup_name}.tar.gz"
                self._create_tarball(temp_dir, final_backup_path)
            else:
                final_backup_path = self.backup_dir / backup_name
                shutil.copytree(temp_dir, final_backup_path)
            
            # Step 6: Encrypt if requested
            if encrypt:
                final_backup_path = self._encrypt_backup(final_backup_path)
            
            # Step 7: Calculate checksum
            checksum = self._calculate_checksum(final_backup_path)
            
            # Step 8: Save backup metadata
            backup_info = {
                'path': str(final_backup_path),
                'filename': final_backup_path.name,
                'size': final_backup_path.stat().st_size,
                'checksum': checksum,
                'timestamp': timestamp,
                'created_at': manifest['created'],
                'compressed': compress,
                'encrypted': encrypt,
                'notes': notes
            }
            
            self._save_backup_metadata(backup_info)
            
            # Cleanup temp
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass  # Ignore errors when removing temp directory
            
            logger.info(f"Backup created successfully: {final_backup_path}")
            
            # Copy to NAS/cloud if configured
            self._sync_backup_to_remote(final_backup_path)
            
            return {
                'success': True,
                'backup_path': str(final_backup_path),
                'size': backup_info['size'],
                'checksum': checksum
            }
            
        except Exception as e:
            logger.error(f"Backup failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _backup_database(self, dest_dir: Path) -> Optional[Path]:
        """Backup database file (PostgreSQL dump)."""
        try:
            import subprocess
            import json
            from app.core import DATA_DIR
            
            # Get PostgreSQL config from database.json
            config_path = Path(DATA_DIR) / "data" / "config" / "database.json"
            if not config_path.exists():
                logger.warning(f"Database config not found: {config_path}")
                return None
            
            with open(config_path, 'r') as f:
                db_config = json.load(f)
            
            pg_config = db_config.get('postgresql', {})
            if not pg_config:
                logger.warning("PostgreSQL config not found in database.json")
                return None
            
            host = pg_config.get('host', 'localhost')
            port = pg_config.get('port', 5432)
            database = pg_config.get('database', 'titan_pos')
            user = pg_config.get('user', 'titan_user')
            password = pg_config.get('password', '')
            
            if not all([host, database, user]):
                logger.warning("Incomplete PostgreSQL configuration")
                return None
            
            # Create PostgreSQL dump
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = dest_dir / f"titan_pos_{timestamp}.dump"
            
            # Export password for pg_dump
            env = os.environ.copy()
            env['PGPASSWORD'] = password
            
            # Run pg_dump
            cmd = [
                'pg_dump',
                '-h', str(host),
                '-p', str(port),
                '-U', user,
                '-d', database,
                '-F', 'c',  # Custom format (compressed)
                '-f', str(backup_path)
            ]
            
            logger.info(f"Creating PostgreSQL backup: {database}@{host}:{port}")
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                size = backup_path.stat().st_size
                logger.info(f"PostgreSQL backup created: {backup_path} ({size/1024/1024:.2f} MB)")
                return backup_path
            else:
                logger.error(f"pg_dump failed: {result.stderr}")
                return None
            
        except FileNotFoundError:
            logger.warning("pg_dump not found. PostgreSQL client tools may not be installed.")
            logger.warning("Install with: sudo apt install postgresql-client")
            return None
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            return None
    
    def _backup_configuration(self, dest_dir: Path) -> Optional[Path]:
        """Backup ALL configuration files - expanded to include everything."""
        try:
            from app.core import DATA_DIR
            
            config_dir = dest_dir / "configs"
            config_dir.mkdir(exist_ok=True)
            
            # List of all config files to backup
            config_files = [
                "config.json",
                "local_config.json",
                "fiscal_config.json",
                "ticket_config.json",
                "permissions_config.json",
                "branch_config.json"
            ]
            
            backed_up = 0
            for config_name in config_files:
                config_path = Path(DATA_DIR) / config_name
                if config_path.exists():
                    shutil.copy2(config_path, config_dir / config_name)
                    backed_up += 1
                    logger.info(f"Config backed up: {config_name}")
            
            # NOTE: Loyalty and SAT catalog are now in PostgreSQL, not separate SQLite files
            # They are included in the main PostgreSQL dump from _backup_database()
            
            logger.info(f"Total configs backed up: {backed_up}")
            return config_dir
            
        except Exception as e:
            logger.error(f"Config backup failed: {e}")
            return None
    
    def _backup_media(self, dest_dir: Path) -> Optional[Path]:
        """Backup media files (images, receipts, CFDIs, logs, exports, etc)."""
        try:
            from app.core import DATA_DIR

            # Extended list of directories to backup
            media_sources = [
                Path(DATA_DIR) / "images",
                Path(DATA_DIR) / "receipts",
                Path(DATA_DIR) / "cfdis",
                Path(DATA_DIR) / "exports",
                Path(DATA_DIR) / "logs",
                Path(DATA_DIR) / "certificates",  # CSD certificates
                Path(DATA_DIR) / "reports",
                Path(DATA_DIR) / "product_images",
            ]
            
            media_dir = dest_dir / "media"
            media_dir.mkdir(exist_ok=True)
            
            total_files = 0
            for source in media_sources:
                if source.exists() and source.is_dir():
                    dest = media_dir / source.name
                    try:
                        # Remove destination if exists, then copy
                        if dest.exists():
                            shutil.rmtree(dest)
                        shutil.copytree(source, dest, dirs_exist_ok=True)
                        file_count = sum(1 for _ in dest.rglob('*') if _.is_file())
                        total_files += file_count
                        logger.info(f"Media dir backed up: {source.name} ({file_count} files)")
                    except Exception as e:
                        logger.warning(f"Could not backup {source.name}: {e}")
            
            logger.info(f"Total media files backed up: {total_files}")
            return media_dir
            
        except Exception as e:
            logger.error(f"Media backup failed: {e}")
            return None
    
    def _create_tarball(self, source_dir: Path, output_path: Path):
        """Create compressed tar.gz file."""
        import tarfile
        
        with tarfile.open(output_path, 'w:gz') as tar:
            tar.add(source_dir, arcname=source_dir.name)
        
        logger.info(f"Tarball created: {output_path}")
    
    def _encrypt_backup(self, backup_path: Path) -> Path:
        """Encrypt backup file with AES-256."""
        try:
            key = self.config.get('backup_encrypt_key', '')
            
            if not key:
                logger.warning("Encryption key not configured, skipping encryption")
                return backup_path
            
            import base64

            from cryptography.fernet import Fernet
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

            # FIX 2026-02-01: Usar salt aleatorio en lugar de constante
            # El salt se guarda al inicio del archivo encriptado
            salt = os.urandom(16)

            # Derive key from password with random salt
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )

            fernet_key = base64.urlsafe_b64encode(kdf.derive(key.encode()))
            fernet = Fernet(fernet_key)

            # Read and encrypt
            with open(backup_path, 'rb') as f:
                data = f.read()

            encrypted_data = fernet.encrypt(data)

            # Save encrypted file with salt prepended
            # Format: [16 bytes salt][encrypted data]
            encrypted_path = backup_path.with_suffix(backup_path.suffix + '.enc')
            with open(encrypted_path, 'wb') as f:
                f.write(salt + encrypted_data)
            
            # Remove unencrypted
            backup_path.unlink()
            
            logger.info(f"Backup encrypted: {encrypted_path}")
            return encrypted_path
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return backup_path
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum."""
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def _save_backup_metadata(self, backup_info: Dict[str, Any]):
        """Save backup metadata to database."""
        try:
            # Create backups table if not exists
            self.core.db.execute_write("""
                CREATE TABLE IF NOT EXISTS backups (
                    id INTEGER PRIMARY KEY,
                    filename TEXT NOT NULL,
                    path TEXT NOT NULL,
                    size INTEGER,
                    checksum TEXT,
                    timestamp TEXT,
                    created_at TEXT,
                    compressed INTEGER DEFAULT 0,
                    encrypted INTEGER DEFAULT 0,
                    notes TEXT,
                    status TEXT DEFAULT 'active'
                )
            """)
            
            # Insert backup record (PostgreSQL uses %s)
            self.core.db.execute_write("""
                INSERT INTO backups (filename, path, size, checksum, timestamp, created_at, compressed, encrypted, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                backup_info['filename'],
                backup_info['path'],
                backup_info['size'],
                backup_info['checksum'],
                backup_info['timestamp'],
                backup_info['created_at'],
                1 if backup_info['compressed'] else 0,
                1 if backup_info['encrypted'] else 0,
                backup_info.get('notes', '')
            ))
            
            logger.info("Backup metadata saved to database")
            
        except Exception as e:
            logger.error(f"Failed to save backup metadata: {e}")
    
    def _sync_backup_to_remote(self, backup_path: Path):
        """Sync backup to NAS and cloud storage IMMEDIATELY."""
        # NAS (local network)
        if self.config.get('backup_nas_enabled'):
            self._copy_to_nas(backup_path)
        
        # Google Drive (if rclone available and configured)
        if self.config.get('backup_gdrive_enabled', False):
            self._upload_to_gdrive(backup_path)
        
        # OneDrive (if rclone available and configured)
        if self.config.get('backup_onedrive_enabled', False):
            self._upload_to_onedrive(backup_path)
        
        # S3/Cloud (original)
        if self.config.get('backup_cloud_enabled'):
            self._upload_to_s3(backup_path)
    
    def _copy_to_nas(self, backup_path: Path):
        """Copy backup to NAS."""
        try:
            nas_path = Path(self.config.get('backup_nas_path', ''))
            
            if not nas_path or not nas_path.exists():
                logger.warning("NAS path not configured or not accessible")
                return
            
            dest = nas_path / backup_path.name
            shutil.copy2(backup_path, dest)
            
            logger.info(f"Backup copied to NAS: {dest}")
            
        except Exception as e:
            logger.error(f"NAS sync failed: {e}")
    
    def _upload_to_gdrive(self, backup_path: Path):
        """Upload backup to Google Drive using rclone."""
        try:
            import subprocess

            # Check if rclone is available
            result = subprocess.run(['which', 'rclone'], capture_output=True)
            if result.returncode != 0:
                logger.warning("rclone not installed, skipping Google Drive upload")
                return
            
            # Check if gdrive remote is configured
            result = subprocess.run(['rclone', 'listremotes'], capture_output=True, text=True)
            if 'gdrive:' not in result.stdout:
                logger.warning("Google Drive not configured in rclone")
                return
            
            # Upload to Google Drive
            dest_path = f"gdrive:POS_Backups/{backup_path.name}"
            
            logger.info(f"Uploading to Google Drive: {backup_path.name}")
            
            result = subprocess.run(
                ['rclone', 'copy', str(backup_path), 'gdrive:POS_Backups', '--verbose'],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode == 0:
                logger.info(f"✅ Backup uploaded to Google Drive: {backup_path.name}")
            else:
                logger.error(f"Google Drive upload failed: {result.stderr}")
            
        except subprocess.TimeoutExpired:
            logger.error("Google Drive upload timed out")
        except Exception as e:
            logger.error(f"Google Drive upload failed: {e}")
    
    def _upload_to_onedrive(self, backup_path: Path):
        """Upload backup to OneDrive using rclone."""
        try:
            import subprocess

            # Check if rclone is available
            result = subprocess.run(['which', 'rclone'], capture_output=True)
            if result.returncode != 0:
                logger.warning("rclone not installed, skipping OneDrive upload")
                return
            
            # Check if onedrive remote is configured
            result = subprocess.run(['rclone', 'listremotes'], capture_output=True, text=True)
            if 'onedrive:' not in result.stdout:
                logger.warning("OneDrive not configured in rclone")
                return
            
            # Upload to OneDrive
            dest_path = f"onedrive:POS_Backups/{backup_path.name}"
            
            logger.info(f"Uploading to OneDrive: {backup_path.name}")
            
            result = subprocess.run(
                ['rclone', 'copy', str(backup_path), 'onedrive:POS_Backups', '--verbose'],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode == 0:
                logger.info(f"✅ Backup uploaded to OneDrive: {backup_path.name}")
            else:
                logger.error(f"OneDrive upload failed: {result.stderr}")
            
        except subprocess.TimeoutExpired:
            logger.error("OneDrive upload timed out")
        except Exception as e:
            logger.error(f"OneDrive upload failed: {e}")
    
    def _upload_to_s3(self, backup_path: Path):
        """Upload backup to S3."""
        try:
            import boto3
            
            endpoint = self.config.get('backup_s3_endpoint', '')
            bucket = self.config.get('backup_s3_bucket', '')
            access_key = self.config.get('backup_s3_access_key', '')
            secret_key = self.config.get('backup_s3_secret_key', '')
            prefix = self.config.get('backup_s3_prefix', 'backups/')
            
            if not all([endpoint, bucket, access_key, secret_key]):
                logger.warning("S3 not fully configured")
                return
            
            s3 = boto3.client(
                's3',
                endpoint_url=endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key
            )
            
            key = f"{prefix}{backup_path.name}"
            
            s3.upload_file(str(backup_path), bucket, key)
            
            logger.info(f"Backup uploaded to S3: {key}")
            
        except ImportError:
            logger.warning("boto3 not installed, S3 upload skipped")
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
    
    def auto_backup_flow(self, force: bool = False):
        """
        Automatic backup flow (called after turn close or on app close).
        
        Args:
            force: If True, create backup even if backup_auto_on_close is disabled
                   (used for mandatory backups on app close)
        """
        try:
            # Check if auto-backup is enabled (unless forced)
            if not force and not self.config.get('backup_auto_on_close'):
                logger.info("Auto-backup disabled (use force=True to override)")
                return
            
            logger.info("Starting auto-backup...")
            
            result = self.create_local_backup(
                include_media=False,  # Quick backup, no media
                compress=True,
                encrypt=self.config.get('backup_encrypt', False),
                notes="Auto-backup al cerrar" + (" aplicación" if force else " turno")
            )
            
            if result.get('success'):
                logger.info("Auto-backup completed successfully")
            else:
                logger.error(f"Auto-backup failed: {result.get('error')}")
            
        except Exception as e:
            logger.error(f"Auto-backup flow failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise  # Re-raise to allow caller to handle
    
    def list_backups(self, limit: int = 50) -> List[Dict]:
        """List available backups."""
        try:
            # SECURITY: Especificar columnas y cap máximo para LIMIT
            limit = max(1, min(int(limit), 1000))
            result = self.core.db.execute_query("""
                SELECT id, filename, path, size, checksum, timestamp, created_at, compressed, encrypted, notes, status
                FROM backups
                WHERE status IN ('active', 'completed')
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            
            if result:
                backups = [dict(row) for row in result]
                return backups
            
            # If no backups in DB, try to find physical backup files
            # Include PostgreSQL dumps (.dump) instead of SQLite (.db)
            backup_files = list(self.backup_dir.glob("backup_*.tar.gz")) + list(self.backup_dir.glob("titan_pos_*.dump"))
            if backup_files:
                # Create backup records from physical files
                backups_from_files = []
                for backup_file in sorted(backup_files, key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
                    try:
                        stat = backup_file.stat()
                        backup_info = {
                            'id': len(backups_from_files) + 1,
                            'filename': backup_file.name,
                            'path': str(backup_file),
                            'size': stat.st_size,
                            'checksum': '',
                            'timestamp': datetime.fromtimestamp(stat.st_mtime).strftime('%Y%m%d_%H%M%S'),
                            'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            'compressed': 1 if backup_file.suffix == '.gz' else 0,
                            'encrypted': 0,
                            'notes': 'Respaldo encontrado en disco',
                            'status': 'active',
                            'backup_type': 'local'
                        }
                        backups_from_files.append(backup_info)
                    except Exception as e:
                        logger.warning(f"Error processing backup file {backup_file}: {e}")
                
                if backups_from_files:
                    return backups_from_files
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []
    
    def restore_backup(self, backup_id: int = None, backup_path: str = None, confirm: bool = False) -> Dict[str, Any]:
        """
        Restore from a backup - COMPLETE DISASTER RECOVERY.
        
        Args:
            backup_id: ID of backup to restore (if in database)
            backup_path: Direct path to backup file (if restoring from physical file)
            confirm: Must be True to actually restore
            
        Returns:
            Result dictionary
        """
        try:
            backup = None
            backup_path_obj = None
            
            # If backup_path is provided, use it directly (for physical files)
            if backup_path:
                backup_path_obj = Path(backup_path)
                if not backup_path_obj.exists():
                    return {'success': False, 'error': f'Backup file not found: {backup_path}'}
                
                # Create backup dict from file
                stat = backup_path_obj.stat()
                backup = {
                    'id': None,
                    'filename': backup_path_obj.name,
                    'path': str(backup_path_obj),
                    'size': stat.st_size,
                    'compressed': 1 if backup_path_obj.suffix in ('.gz', '.tar.gz') else 0,
                    'encrypted': 0,
                    'timestamp': datetime.fromtimestamp(stat.st_mtime).strftime('%Y%m%d_%H%M%S'),
                    'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat()
                }
            elif backup_id is not None:
                # Get backup info from database
                # SECURITY: Especificar columnas en lugar de SELECT *
                result = self.core.db.execute_query(
                    "SELECT id, filename, path, size, checksum, timestamp, created_at, compressed, encrypted, notes, status FROM backups WHERE id = %s",
                    (backup_id,)
                )
                
                if not result:
                    return {'success': False, 'error': 'Backup not found'}
                
                backup = dict(result[0])
                backup_path_obj = Path(backup['path'])
            else:
                return {'success': False, 'error': 'Either backup_id or backup_path must be provided'}
            
            if not backup_path_obj.exists():
                return {'success': False, 'error': f'Backup file not found: {backup_path_obj}'}
            
            if not confirm:
                return {
                    'success': False,
                    'error': 'Restore requires explicit confirmation',
                    'backup_info': backup
                }
            
            logger.warning(f"Starting restore from backup: {backup.get('filename', 'unknown')}")
            
            # Step 1: Decrypt if needed
            restore_path = backup_path_obj
            if backup.get('encrypted'):
                restore_path = self._decrypt_backup(backup_path_obj)
                if not restore_path:
                    return {'success': False, 'error': 'Failed to decrypt backup'}
            
            # Step 2: Extract backup
            import tempfile
            temp_dir = Path(tempfile.mkdtemp())
            
            try:
                # Check if it's a PostgreSQL dump file (.dump)
                if str(restore_path).endswith('.dump'):
                    # PostgreSQL dump - restore directly
                    logger.info(f"PostgreSQL dump detected: {restore_path}")
                    
                    # Restore PostgreSQL database directly from dump
                    success = self._restore_postgresql_database(restore_path)
                    if not success:
                        return {'success': False, 'error': 'Failed to restore PostgreSQL database'}
                    logger.info("✅ PostgreSQL database restored")
                    
                    # Create minimal manifest for compatibility
                    manifest = {
                        'timestamp': backup.get('timestamp', 'unknown'),
                        'created': backup.get('created_at', datetime.now().isoformat()),
                        'version': '1.0',
                        'database': 'postgresql_dump',
                        'database_file': str(restore_path),
                        'config': None,
                        'media_included': False,
                        'compressed': True,
                        'encrypted': False,
                        'notes': backup.get('notes', 'PostgreSQL database backup')
                    }
                    # Skip to end - database already restored
                    return {
                        'success': True,
                        'message': 'PostgreSQL backup restored successfully. Please restart the application.',
                        'backup_timestamp': manifest.get('timestamp'),
                        'requires_restart': True
                    }
                elif backup.get('compressed') or str(restore_path).endswith('.tar.gz') or str(restore_path).endswith('.gz'):
                    # Compressed backup - extract
                    import tarfile
                    with tarfile.open(restore_path, 'r:gz') as tar:
                        tar.extractall(temp_dir)
                    
                    # Find extracted directory
                    extracted_dirs = [d for d in temp_dir.iterdir() if d.is_dir()]
                    if not extracted_dirs:
                        return {'success': False, 'error': 'Invalid backup format'}
                    
                    source_dir = extracted_dirs[0]
                    logger.info(f"Backup extracted to: {source_dir}")
                    
                    # Step 3: Validate backup
                    manifest_path = source_dir / "manifest.json"
                    if not manifest_path.exists():
                        return {'success': False, 'error': 'Invalid backup: manifest not found'}
                    
                    import json
                    with open(manifest_path, 'r') as f:
                        manifest = json.load(f)
                else:
                    # Uncompressed directory backup
                    source_dir = restore_path
                    
                    # Step 3: Validate backup
                    manifest_path = source_dir / "manifest.json"
                    if not manifest_path.exists():
                        return {'success': False, 'error': 'Invalid backup: manifest not found'}
                    
                    import json
                    with open(manifest_path, 'r') as f:
                        manifest = json.load(f)
                
                logger.info(f"Manifest loaded: version {manifest.get('version')}")
                
                # Step 3.5: CLOSE all database connections before restore
                try:
                    import gc
                    self.core.db.close()  # Close primary connection
                    gc.collect()  # Force garbage collection
                    logger.info("✅ Database connections closed before restore")
                except Exception as e:
                    logger.warning(f"Could not close DB connections: {e}")
                
                # Step 4: Restore database
                # Check for PostgreSQL dump file in extracted directory
                dump_files = list(source_dir.glob("*.dump")) + list(source_dir.glob("titan_pos_*.dump"))
                if dump_files:
                    dump_file = dump_files[0]
                    logger.info(f"Found PostgreSQL dump in backup: {dump_file}")
                    success = self._restore_postgresql_database(dump_file)
                    if not success:
                        return {'success': False, 'error': 'Failed to restore PostgreSQL database'}
                    logger.info("✅ PostgreSQL database restored")
                else:
                    # Legacy: Check for SQLite .db file (for backwards compatibility)
                    db_file = source_dir / "pos.db"
                    if db_file.exists():
                        logger.warning("⚠️ SQLite backup detected. System now uses PostgreSQL.")
                        logger.warning("⚠️ Please use PostgreSQL dumps (.dump files) for backups.")
                        logger.warning("⚠️ Skipping SQLite restore - system requires PostgreSQL")
                        # Don't restore SQLite - system uses PostgreSQL
                    else:
                        logger.warning("⚠️ No database file found in backup (neither .dump nor .db)")
                
                # Step 5: Restore configuration
                config_file = source_dir / "config.json"
                if config_file.exists():
                    self._restore_configuration(config_file)
                    logger.info("✅ Configuration restored")
                
                # Step 6: Restore media
                media_dir = source_dir / "media"
                if media_dir.exists():
                    self._restore_media(media_dir)
                    logger.info("✅ Media restored")
                
                # Cleanup temp
                import shutil
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass  # Ignore errors when removing temp directory
                
                logger.warning("🎉 RESTORE COMPLETED SUCCESSFULLY")
                
                return {
                    'success': True,
                    'message': 'Backup restored successfully. Please restart the application.',
                    'backup_timestamp': manifest.get('timestamp'),
                    'requires_restart': True
                }
                
            except Exception as e:
                import shutil
                try:
                    shutil.rmtree(temp_dir)
                except Exception:
                    pass  # Ignore errors when removing temp directory
                raise
            
        except Exception as e:
            logger.error(f"Restore failed: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def _decrypt_backup(self, backup_path: Path) -> Optional[Path]:
        """Decrypt an encrypted backup."""
        try:
            key = self.config.get('backup_encrypt_key', '')
            
            if not key:
                logger.error("Encryption key not configured")
                return None
            
            import base64

            from cryptography.fernet import Fernet
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

            # FIX 2026-02-01: Leer salt del archivo encriptado
            # Format: [16 bytes salt][encrypted data]
            with open(backup_path, 'rb') as f:
                file_data = f.read()

            # Extraer salt de los primeros 16 bytes
            salt = file_data[:16]
            encrypted_data = file_data[16:]

            # Derive key from password with extracted salt
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )

            fernet_key = base64.urlsafe_b64encode(kdf.derive(key.encode()))
            fernet = Fernet(fernet_key)

            decrypted_data = fernet.decrypt(encrypted_data)
            
            # Save decrypted file
            decrypted_path = backup_path.with_suffix('')  # Remove .enc
            with open(decrypted_path, 'wb') as f:
                f.write(decrypted_data)
            
            logger.info(f"Backup decrypted: {decrypted_path}")
            return decrypted_path
            
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return None
    
    def _restore_postgresql_database(self, dump_file: Path) -> bool:
        """Restore PostgreSQL database from dump file."""
        try:
            import subprocess
            import json
            from app.core import DATA_DIR
            
            # Get PostgreSQL config from database.json
            config_path = Path(DATA_DIR) / "data" / "config" / "database.json"
            if not config_path.exists():
                logger.error(f"Database config not found: {config_path}")
                return False
            
            with open(config_path, 'r') as f:
                db_config = json.load(f)
            
            pg_config = db_config.get('postgresql', {})
            if not pg_config:
                logger.error("PostgreSQL config not found in database.json")
                return False
            
            host = pg_config.get('host', 'localhost')
            port = pg_config.get('port', 5432)
            database = pg_config.get('database', 'titan_pos')
            user = pg_config.get('user', 'titan_user')
            password = pg_config.get('password', '')
            
            if not all([host, database, user]):
                logger.error("Incomplete PostgreSQL configuration")
                return False
            
            # Export password for pg_restore
            env = os.environ.copy()
            env['PGPASSWORD'] = password
            
            # Run pg_restore with -c (clean) to drop objects before recreating
            cmd = [
                'pg_restore',
                '-h', str(host),
                '-p', str(port),
                '-U', user,
                '-d', database,
                '-c',  # Clean (drop) database objects before recreating
                '-v',  # Verbose
                str(dump_file)
            ]
            
            logger.info(f"Restoring PostgreSQL database: {database}@{host}:{port}")
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"✅ PostgreSQL database restored successfully")
                return True
            else:
                logger.error(f"pg_restore failed: {result.stderr}")
                return False
            
        except FileNotFoundError:
            logger.error("pg_restore not found. PostgreSQL client tools may not be installed.")
            logger.error("Install with: sudo apt install postgresql-client")
            return False
        except Exception as e:
            logger.error(f"PostgreSQL restore failed: {e}", exc_info=True)
            return False
    
    def _restore_database(self, db_file: Path) -> bool:
        """Legacy method for SQLite restore (deprecated - system uses PostgreSQL)."""
        logger.warning("⚠️ _restore_database() called with SQLite file - system now uses PostgreSQL")
        logger.warning("⚠️ This method is deprecated. Use _restore_postgresql_database() instead.")
        return False
    
    def _restore_configuration(self, config_file: Path):
        """Restore ALL configuration files."""
        try:
            import shutil

            from app.core import DATA_DIR

            # Check if it's the new format (configs directory) or old format (single file)
            if config_file.is_dir():
                # New format: configs directory
                for cfg_file in config_file.iterdir():
                    if cfg_file.is_file() and cfg_file.suffix == '.json':
                        dest = Path(DATA_DIR) / cfg_file.name
                        shutil.copy2(cfg_file, dest)
                        logger.info(f"Config restored: {cfg_file.name}")
            else:
                # Old format: single config.json
                config_dest = Path(DATA_DIR) / "config.json"
                shutil.copy2(config_file, config_dest)
                logger.info(f"Configuration restored: {config_dest}")
            
            # Check for additional databases in backup root
            backup_root = config_file.parent
            
            # NOTE: Loyalty and SAT catalog are now in PostgreSQL, not separate SQLite files
            # They are included in the main PostgreSQL dump/restore above
            
        except Exception as e:
            logger.error(f"Configuration restore failed: {e}")
    
    def _restore_media(self, media_dir: Path):
        """Restore media files."""
        try:
            import shutil

            from app.core import DATA_DIR

            # Restore each media subdirectory
            for subdir in media_dir.iterdir():
                if subdir.is_dir():
                    dest = Path(DATA_DIR) / subdir.name
                    
                    # Remove existing and copy
                    if dest.exists():
                        try:
                            shutil.rmtree(dest)
                        except Exception as e:
                            logger.warning(f"Could not remove existing {dest.name}: {e}")
                    
                    shutil.copytree(subdir, dest)
                    logger.info(f"Media restored: {subdir.name}")
            
        except Exception as e:
            logger.error(f"Media restore failed: {e}")
    
    def cleanup_old_backups(self):
        """Delete old backups based on retention policy."""
        try:
            if not self.config.get('backup_retention_enabled'):
                return
            
            retention_days = self.config.get('backup_retention_days', 30)
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            # SECURITY: Especificar columnas y agregar LIMIT
            old_backups = self.core.db.execute_query("""
                SELECT id, filename, path, size, checksum, timestamp, created_at, compressed, encrypted, notes, status
                FROM backups
                WHERE created_at < %s
                AND status = 'active'
                LIMIT 1000
            """, (cutoff_date.isoformat(),))
            
            if not old_backups:
                logger.info("No old backups to cleanup")
                return
            
            for backup in old_backups:
                backup_path = Path(backup['path'])
                
                if backup_path.exists():
                    backup_path.unlink()
                    logger.info(f"Deleted old backup: {backup_path.name}")
                
                # Mark as deleted in DB
                self.core.db.execute_write(
                    "UPDATE backups SET status = 'deleted' WHERE id = %s",
                    (backup['id'],)
                )
            
            logger.info(f"Cleanup completed: {len(old_backups)} backups removed")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
