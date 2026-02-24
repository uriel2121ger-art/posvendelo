"""
TITAN POS - Sync Compression Utilities

Compresses sync payloads to reduce bandwidth usage between
terminals and the Gateway.
"""

from typing import Any, Dict, Optional, Union
import base64
from datetime import datetime
import gzip
import json
import logging
import re

logger = logging.getLogger(__name__)

# SECURITY: Whitelist of valid table names to prevent SQL injection
VALID_TABLES = frozenset({
    'products', 'sales', 'sale_items', 'customers', 'users', 'branches',
    'categories', 'inventory', 'cash_movements', 'shifts', 'loyalty_rules',
    'anonymous_wallet', 'suppliers', 'purchase_orders', 'purchase_order_items',
    'price_history', 'audit_log', 'sync_log', 'settings', 'tickets'
})

# SECURITY: Pattern for valid SQL identifiers (alphanumeric + underscore, not starting with number)
VALID_IDENTIFIER_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

def _validate_identifier(name: str, identifier_type: str = "identifier") -> bool:
    """Validate SQL identifier to prevent SQL injection."""
    if not name or not isinstance(name, str):
        return False
    if len(name) > 64:  # Max reasonable identifier length
        return False
    return bool(VALID_IDENTIFIER_PATTERN.match(name))

class SyncCompressor:
    """
    Compresses and decompresses sync payloads.
    
    Features:
    - GZIP compression
    - Base64 encoding for JSON transport
    - Automatic fallback if compression fails
    - Size reduction metrics
    """
    
    def __init__(self, min_size: int = 1024, compression_level: int = 6):
        """
        Initialize compressor.
        
        Args:
            min_size: Minimum payload size to compress (bytes)
            compression_level: GZIP compression level (1-9)
        """
        self.min_size = min_size
        self.compression_level = compression_level
        self._stats = {
            "compressed": 0,
            "skipped": 0,
            "bytes_saved": 0,
            "errors": 0
        }
    
    def compress(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compress a sync payload.
        
        Args:
            data: Dictionary to compress
            
        Returns:
            Dictionary with compressed data or original if too small
        """
        try:
            # Serialize to JSON
            json_str = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
            original_size = len(json_str.encode('utf-8'))
            
            # Skip if too small
            if original_size < self.min_size:
                self._stats["skipped"] += 1
                return {"_compressed": False, "data": data}
            
            # Compress
            compressed = gzip.compress(
                json_str.encode('utf-8'),
                compresslevel=self.compression_level
            )
            
            # Base64 encode for JSON transport
            encoded = base64.b64encode(compressed).decode('ascii')
            
            compressed_size = len(encoded)
            savings = original_size - compressed_size
            
            # Only use compression if it actually saves space
            if savings > 0:
                self._stats["compressed"] += 1
                self._stats["bytes_saved"] += savings
                
                return {
                    "_compressed": True,
                    "_original_size": original_size,
                    "_compressed_size": compressed_size,
                    "_ratio": round(compressed_size / original_size, 2) if original_size > 0 else 0,
                    "data": encoded
                }
            else:
                self._stats["skipped"] += 1
                return {"_compressed": False, "data": data}
                
        except Exception as e:
            logger.error(f"Compression error: {e}")
            self._stats["errors"] += 1
            return {"_compressed": False, "data": data}
    
    def decompress(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decompress a sync payload.
        
        Args:
            payload: Payload that may contain compressed data
            
        Returns:
            Original uncompressed data
        """
        if not payload.get("_compressed", False):
            return payload.get("data", payload)
            
        try:
            # Decode base64
            raw_data = payload.get("data")
            if not raw_data:
                logger.warning("Compressed payload missing 'data' key")
                return payload
            compressed = base64.b64decode(raw_data)
            
            # Decompress
            json_str = gzip.decompress(compressed).decode('utf-8')
            
            # Parse JSON
            return json.loads(json_str)
            
        except Exception as e:
            logger.error(f"Decompression error: {e}")
            # Return original data as fallback
            return payload.get("data", payload)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get compression statistics."""
        total = self._stats["compressed"] + self._stats["skipped"]
        return {
            **self._stats,
            "total_operations": total,
            "compression_rate": round(self._stats["compressed"] / total, 2) if total > 0 else 0,
            "avg_savings_per_compressed": round(
                self._stats["bytes_saved"] / self._stats["compressed"], 0
            ) if self._stats["compressed"] > 0 else 0
        }

class DeltaSync:
    """
    Delta synchronization - only sends changes since last sync.
    
    Features:
    - Tracks last sync timestamp per table
    - Only sends modified records
    - Significant bandwidth reduction for large datasets
    """
    
    def __init__(self):
        self._last_sync: Dict[str, str] = {}  # table -> timestamp
    
    def get_changes_since(self, 
                          conn, 
                          table: str, 
                          timestamp_column: str = "updated_at",
                          columns: list = None) -> Dict[str, Any]:
        """
        Get records modified since last sync.
        
        Args:
            conn: SQLite connection
            table: Table name
            timestamp_column: Column with modification timestamp
            columns: Columns to select (None = all)
            
        Returns:
            Dict with changes and metadata
        """
        # SECURITY: Validate table name against whitelist to prevent SQL injection
        if table not in VALID_TABLES:
            logger.error(f"Invalid table name for delta sync: {table}")
            return {
                "table": table,
                "error": f"Invalid table name: {table}",
                "records": [],
                "is_delta": False
            }

        # SECURITY: Validate timestamp column name
        if not _validate_identifier(timestamp_column, "column"):
            logger.error(f"Invalid timestamp column name: {timestamp_column}")
            return {
                "table": table,
                "error": f"Invalid timestamp column: {timestamp_column}",
                "records": [],
                "is_delta": False
            }

        # SECURITY: Validate all column names if specified
        if columns:
            for col in columns:
                if not _validate_identifier(col, "column"):
                    logger.error(f"Invalid column name: {col}")
                    return {
                        "table": table,
                        "error": f"Invalid column name: {col}",
                        "records": [],
                        "is_delta": False
                    }

        last_sync = self._last_sync.get(table, "1970-01-01T00:00:00")

        col_str = ", ".join(columns) if columns else "*"

        try:
            # SECURITY: Table/column names are now validated, safe to use in query
            # nosec B608 - table validated against VALID_TABLES whitelist, columns validated with _validate_identifier
            cursor = conn.execute(f"""
                SELECT {col_str} FROM {table}
                WHERE {timestamp_column} > %s
                ORDER BY {timestamp_column}
            """, (last_sync,))
            
            records = []
            column_names = [desc[0] for desc in cursor.description]
            
            for row in cursor.fetchall():
                records.append(dict(zip(column_names, row)))
            
            # Update last sync time
            now = datetime.now().isoformat()
            self._last_sync[table] = now
            
            return {
                "table": table,
                "since": last_sync,
                "until": now,
                "count": len(records),
                "records": records,
                "is_delta": True
            }
            
        except Exception as e:
            logger.error(f"Delta sync error for {table}: {e}")
            return {
                "table": table,
                "error": str(e),
                "records": [],
                "is_delta": False
            }
    
    def reset(self, table: str = None):
        """Reset sync state, forcing full sync next time."""
        if table:
            self._last_sync.pop(table, None)
        else:
            self._last_sync.clear()

# Singleton instances
_compressor: Optional[SyncCompressor] = None
_delta_sync: Optional[DeltaSync] = None

def get_compressor() -> SyncCompressor:
    """Get singleton compressor instance."""
    global _compressor
    if _compressor is None:
        _compressor = SyncCompressor()
    return _compressor

def get_delta_sync() -> DeltaSync:
    """Get singleton delta sync instance."""
    global _delta_sync
    if _delta_sync is None:
        _delta_sync = DeltaSync()
    return _delta_sync

def compress_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to compress a payload."""
    return get_compressor().compress(data)

def decompress_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to decompress a payload."""
    return get_compressor().decompress(payload)
