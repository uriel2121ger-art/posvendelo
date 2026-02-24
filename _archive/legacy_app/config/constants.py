"""
TITAN POS - Configuration Constants
====================================

Centralized configuration values for the entire system.
Extracted to improve maintainability and reduce magic numbers.
"""

# ==================== SKU GENERATOR CONFIGURATION ====================

# SKU Format
SKU_LENGTH = 13  # Total digits in EAN-13
SKU_PREFIX_LENGTH = 2  # Prefix length (e.g., '20', '21')
SKU_NUMBER_LENGTH = 10  # Numeric sequence length
SKU_CHECKSUM_LENGTH = 1  # EAN-13 checksum digit

# Default Values
DEFAULT_SKU_PREFIX = '20'
MAX_SKU_SEQUENCE = 9999999999  # Maximum 10-digit number

# Prefixes
INTERNAL_SKU_PREFIXES = ['20', '21', '22', '23', '24', '29']
SPECIAL_PREFIX_WEIGHT = '29'  # Peso/Precio embebido

# ==================== UI CONFIGURATION ====================

# Product Editor
BARCODE_PREVIEW_MIN_HEIGHT = 60
GENERATE_BUTTON_MAX_WIDTH = 120
SKU_INPUT_MIN_LENGTH = 8  # Minimum characters for validation

# Colors (Barcode Preview States)
COLOR_VALID_BG = "#d4edda"
COLOR_VALID_BORDER = "#28a745"
COLOR_VALID_TEXT = "#155724"

COLOR_INVALID_BG = "#f8d7da"
COLOR_INVALID_BORDER = "#dc3545"
COLOR_INVALID_TEXT = "#721c24"

COLOR_CUSTOM_BG = "#d1ecf1"
COLOR_CUSTOM_BORDER = "#17a2b8"
COLOR_CUSTOM_TEXT = "#0c5460"

COLOR_WARNING_BG = "#fff3cd"
COLOR_WARNING_BORDER = "#ffc107"
COLOR_WARNING_TEXT = "#856404"

COLOR_NEUTRAL_BG = "#f5f5f5"
COLOR_NEUTRAL_BORDER = "#ddd"

# ==================== DATABASE CONFIGURATION ====================

# Query Limits
DEFAULT_PRODUCT_LIMIT = 50
MAX_SEARCH_RESULTS = 300
PAGINATION_SIZE = 50

# Retry Configuration
MAX_DB_RETRIES = 3
RETRY_BACKOFF_MS = 100  # Milliseconds

# Connection Pool
DB_TIMEOUT_SECONDS = 30
DB_CACHE_SIZE_MB = 64

# ==================== BUSINESS LOGIC ====================

# Tax
DEFAULT_TAX_RATE = 0.16  # 16% IVA

# Inventory
DEFAULT_MIN_STOCK = 5
STOCK_WARNING_THRESHOLD = 10

# Customer Credit
DEFAULT_CREDIT_LIMIT = 0.0
MIN_CREDIT_PAYMENT = 1.0

# Turns
TURN_STATUS_OPEN = 'OPEN'
TURN_STATUS_CLOSED = 'CLOSED'

# ==================== SECURITY ====================

# Password
MIN_PASSWORD_LENGTH = 6
PASSWORD_HASH_ROUNDS = 12

# Session
SESSION_TIMEOUT_MINUTES = 480  # 8 hours
MAX_FAILED_LOGIN_ATTEMPTS = 5

# ==================== PERFORMANCE ====================

# Caching
CACHE_TTL_SECONDS = 300  # 5 minutes
CACHE_MAX_SIZE = 1000  # items

# Batch Operations
MAX_BULK_SKU_GENERATION = 100
MAX_BULK_PRODUCT_IMPORT = 1000

# ==================== FILE PATHS ====================

# Data Directory Structure
DATA_DIR_NAME = "data"
DB_DIR_NAME = "databases"
CONFIG_DIR_NAME = "config"
BACKUP_DIR_NAME = "backups"

# Database
DEFAULT_DB_NAME = "pos.db"

# Configuration
CONFIG_FILE_NAME = "config.json"

# ==================== API / INTEGRATION ====================

# E-Commerce
DEFAULT_ECOMMERCE_PORT = 8000
API_RATE_LIMIT_PER_MINUTE = 60

# Export Formats
EXPORT_FORMAT_CSV = "csv"
EXPORT_FORMAT_EXCEL = "xlsx"
EXPORT_FORMAT_PDF = "pdf"
EXPORT_FORMAT_JSON = "json"

# ==================== LOGGING ====================

LOG_LEVEL_DEBUG = "DEBUG"
LOG_LEVEL_INFO = "INFO"
LOG_LEVEL_WARNING = "WARNING"
LOG_LEVEL_ERROR = "ERROR"

# ==================== VALIDATION ====================

# SKU Validation
MIN_CUSTOM_SKU_LENGTH = 3
MAX_CUSTOM_SKU_LENGTH = 50

# Product Names
MIN_PRODUCT_NAME_LENGTH = 2
MAX_PRODUCT_NAME_LENGTH = 200

# Customer Names
MIN_CUSTOMER_NAME_LENGTH = 2
MAX_CUSTOMER_NAME_LENGTH = 100

# ==================== MESSAGES ====================

# Success Messages
MSG_SKU_GENERATED = "✓ Código generado exitosamente"
MSG_PRODUCT_SAVED = "Producto guardado correctamente"
MSG_PRODUCT_UPDATED = "Producto actualizado correctamente"

# Error Messages
ERR_SKU_DUPLICATE = "El código ya existe en otro producto"
ERR_SKU_INVALID = "El código no es válido"
ERR_SKU_GENERATION_FAILED = "No se pudo generar el código automático"
ERR_FIELD_REQUIRED = "Este campo es obligatorio"
ERR_INVALID_PRICE = "El precio debe ser mayor a cero"

# Warning Messages
WARN_PRICE_ZERO = "El precio de venta es $0.00"
WARN_LOW_STOCK = "Stock por debajo del mínimo"
WARN_SKU_TOO_SHORT = "SKU muy corto (mínimo 8 dígitos)"

# ==================== REGEX PATTERNS ====================

REGEX_PATTERNS = {
    'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    'rfc_persona_fisica': r'^[A-ZÑ&]{4}\d{6}[A-Z0-9]{3}$',
    'rfc_persona_moral': r'^[A-ZÑ&]{3}\d{6}[A-Z0-9]{3}$',
    'phone_mx': r'^\d{10}$',
    'postal_code_mx': r'^\d{5}$',
    'barcode_ean13': r'^\d{13}$',
    'barcode_ean8': r'^\d{8}$',
}
