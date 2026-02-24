"""
Production Configuration for TITAN POS
Environment-specific settings
"""

from typing import Any, Dict
import os
from pathlib import Path


class Config:
    """Base configuration."""
    
    # App
    APP_NAME = "TITAN POS"
    VERSION = "2.0.0"
    DEBUG = False
    
    # Database
    DB_PATH = "data/databases/pos.db"
    DB_BACKUP_DIR = "data/backups"
    
    # API
    API_HOST = "0.0.0.0"
    API_PORT = 8000
    API_WORKERS = 4
    
    # Security - MUST be set via environment variables
    SECRET_KEY = os.getenv("SECRET_KEY")
    ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")

    # SECURITY: Validate required secrets at import time
    if not SECRET_KEY:
        import warnings
        warnings.warn(
            "⚠️  SECURITY: SECRET_KEY not set! Using random key (sessions won't persist). "
            "Set SECRET_KEY environment variable for production.",
            RuntimeWarning
        )
        import secrets as _secrets
        SECRET_KEY = _secrets.token_hex(32)

    if not ADMIN_TOKEN:
        import warnings
        warnings.warn(
            "⚠️  SECURITY: ADMIN_TOKEN not set! Admin API endpoints are DISABLED. "
            "Set ADMIN_TOKEN environment variable to enable admin access.",
            RuntimeWarning
        )
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = 24
    
    # CORS - SECURITY: Never use ["*"] in production
    # Set CORS_ALLOWED_ORIGINS environment variable with comma-separated domains
    _cors_env = os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
    if not _cors_env or _cors_env == ['']:
        # Default seguro: solo localhost para desarrollo
        CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
    else:
        CORS_ORIGINS = [origin.strip() for origin in _cors_env if origin.strip()]
    
    # Cache
    CACHE_TTL = 300  # 5 minutes
    CACHE_MAX_SIZE = 1000
    
    # Email
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@titanpos.com")
    
    # File Upload
    UPLOAD_DIR = "data/uploads"
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".pdf"}
    
    # Logging
    LOG_LEVEL = "INFO"
    LOG_DIR = "logs"
    LOG_ROTATION = "midnight"
    LOG_RETENTION_DAYS = 30
    
    # Performance
    MAX_CONCURRENT_REQUESTS = 100
    REQUEST_TIMEOUT = 30
    
    # Monitoring
    ENABLE_PROFILING = False
    ENABLE_METRICS = True
    
    @classmethod
    def load_from_env(cls) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        return {
            'app_name': cls.APP_NAME,
            'version': cls.VERSION,
            'debug': cls.DEBUG,
            'db_path': cls.DB_PATH,
            'api_host': cls.API_HOST,
            'api_port': cls.API_PORT,
            'secret_key': cls.SECRET_KEY,
        }

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    LOG_LEVEL = "DEBUG"
    ENABLE_PROFILING = True
    API_HOST = "localhost"
    CORS_ORIGINS = ["http://localhost:3000", "http://localhost:8080"]

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    LOG_LEVEL = "WARNING"
    ENABLE_PROFILING = False
    
    # Production security
    CORS_ORIGINS = [
        os.getenv("FRONTEND_URL", "https://yourdomain.com")
    ]
    
    # Use PostgreSQL in production
    DB_URL = os.getenv("DATABASE_URL", "")
    
    # Redis for caching
    REDIS_URL = os.getenv("REDIS_URL", "")
    
    # Sentry for error tracking
    SENTRY_DSN = os.getenv("SENTRY_DSN", "")

class TestingConfig(Config):
    """Testing configuration."""
    DEBUG = True
    TESTING = True
    DB_PATH = ":memory:"  # In-memory database for tests

# Config factory
def get_config() -> Config:
    """Get configuration based on environment."""
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    configs = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": TestingConfig
    }
    
    return configs.get(env, DevelopmentConfig)()

# Global config instance
config = get_config()
