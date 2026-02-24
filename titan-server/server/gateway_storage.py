"""
TITAN Gateway - Persistencia SQLite

Almacena heartbeats, logs y alertas de forma persistente en SQLite
para que no se pierdan al reiniciar el gateway.
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import threading

logger = logging.getLogger(__name__)

class GatewayStorage:
    """
    Almacenamiento persistente para el Gateway.
    
    Almacena:
    - Heartbeats de terminales
    - Logs centralizados
    - Alertas de stock
    """
    
    def __init__(self, db_path: str = "gateway_data/gateway.db"):
        """
        Initialize storage.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        
        self._init_db()
        
    def _init_db(self):
        """Initialize database schema."""
        with self._lock:
            conn = self._get_conn()
            with conn:  # Context manager for transaction
                cursor = conn.cursor()
                try:
                    # Tabla de heartbeats
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS heartbeats (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            terminal_key TEXT UNIQUE NOT NULL,
                            terminal_id INTEGER NOT NULL,
                            branch_id INTEGER NOT NULL,
                            terminal_name TEXT,
                            status TEXT DEFAULT 'online',
                            today_sales INTEGER DEFAULT 0,
                            today_total REAL DEFAULT 0,
                            pending_sync INTEGER DEFAULT 0,
                            product_count INTEGER DEFAULT 0,
                            active_turn TEXT,
                            extra_data TEXT,
                            last_seen TEXT NOT NULL,
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP
                        )
                    """)

                    # Tabla de logs centralizados
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS centralized_logs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            terminal_id INTEGER NOT NULL,
                            branch_id INTEGER NOT NULL,
                            level TEXT NOT NULL,
                            message TEXT NOT NULL,
                            module TEXT,
                            log_timestamp TEXT NOT NULL,
                            extra_data TEXT,
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP
                        )
                    """)

                    # Índices para logs
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_logs_level ON centralized_logs(level)
                    """)
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_logs_terminal ON centralized_logs(terminal_id, branch_id)
                    """)
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON centralized_logs(log_timestamp)
                    """)

                    # Tabla de alertas de stock
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS stock_alerts (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            terminal_id INTEGER NOT NULL,
                            branch_id INTEGER NOT NULL,
                            sku TEXT NOT NULL,
                            name TEXT NOT NULL,
                            current_stock REAL DEFAULT 0,
                            min_stock REAL DEFAULT 0,
                            severity TEXT DEFAULT 'warning',
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(terminal_id, branch_id, sku)
                        )
                    """)

                    # Índice para alertas
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_alerts_severity ON stock_alerts(severity)
                    """)
                finally:
                    cursor.close()
            logger.info(f"📁 Gateway storage initialized: {self.db_path}")
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HEARTBEATS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def save_heartbeat(self, data: Dict[str, Any]) -> bool:
        """Save or update a terminal heartbeat."""
        try:
            with self._lock:
                conn = self._get_conn()
                cursor = conn.cursor()
                try:
                    terminal_key = f"B{data['branch_id']}-T{data['terminal_id']}"

                    cursor.execute("""
                        INSERT INTO heartbeats (
                            terminal_key, terminal_id, branch_id, terminal_name,
                            status, today_sales, today_total, pending_sync,
                            product_count, active_turn, extra_data, last_seen
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(terminal_key) DO UPDATE SET
                            terminal_name = excluded.terminal_name,
                            status = excluded.status,
                            today_sales = excluded.today_sales,
                            today_total = excluded.today_total,
                            pending_sync = excluded.pending_sync,
                            product_count = excluded.product_count,
                            active_turn = excluded.active_turn,
                            extra_data = excluded.extra_data,
                            last_seen = excluded.last_seen
                    """, (
                        terminal_key,
                        data["terminal_id"],
                        data["branch_id"],
                        data.get("terminal_name", ""),
                        data.get("status", "online"),
                        data.get("today_sales", 0),
                        data.get("today_total", 0),
                        data.get("pending_sync", 0),
                        data.get("product_count", 0),
                        json.dumps(data.get("active_turn")) if data.get("active_turn") else None,
                        json.dumps({k: v for k, v in data.items() if k not in
                                   ["terminal_id", "branch_id", "terminal_name", "status",
                                    "today_sales", "today_total", "pending_sync", "product_count", "active_turn"]}),
                        data.get("timestamp", datetime.now().isoformat())
                    ))

                    conn.commit()
                    return True
                finally:
                    cursor.close()

        except Exception as e:
            logger.error(f"Error saving heartbeat: {e}")
            return False
    
    def get_terminals(self, timeout_seconds: int = 180) -> Dict[str, Any]:
        """Get all terminals with online/offline status."""
        try:
            with self._lock:
                conn = self._get_conn()
                cursor = conn.cursor()
                try:
                    # SECURITY: Especificar columnas y agregar LIMIT
                    cursor.execute("""
                        SELECT id, terminal_key, terminal_id, branch_id, terminal_name, status,
                               today_sales, today_total, pending_sync, product_count, active_turn,
                               extra_data, last_seen, created_at
                        FROM heartbeats ORDER BY last_seen DESC LIMIT 1000
                    """)
                    rows = cursor.fetchall()

                    terminals = []
                    online = 0
                    offline = 0
                    cutoff = datetime.now() - timedelta(seconds=timeout_seconds)

                    for row in rows:
                        last_seen = datetime.fromisoformat(row["last_seen"])
                        is_online = last_seen > cutoff

                        terminal = {
                            "terminal_id": row["terminal_id"],
                            "branch_id": row["branch_id"],
                            "terminal_name": row["terminal_name"],
                            "status": "online" if is_online else "offline",
                            "today_sales": row["today_sales"],
                            "today_total": row["today_total"],
                            "pending_sync": row["pending_sync"],
                            "last_seen": row["last_seen"]
                        }

                        if row["active_turn"]:
                            terminal["active_turn"] = json.loads(row["active_turn"])

                        terminals.append(terminal)

                        if is_online:
                            online += 1
                        else:
                            offline += 1

                    return {
                        "terminals": terminals,
                        "total": len(terminals),
                        "online": online,
                        "offline": offline
                    }
                finally:
                    cursor.close()

        except Exception as e:
            logger.error(f"Error getting terminals: {e}")
            return {"terminals": [], "total": 0, "online": 0, "offline": 0}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LOGS CENTRALIZADOS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def save_logs(self, terminal_id: int, branch_id: int, entries: List[Dict]) -> int:
        """Save log entries."""
        try:
            with self._lock:
                conn = self._get_conn()
                cursor = conn.cursor()
                try:
                    count = 0
                    for entry in entries:
                        cursor.execute("""
                            INSERT INTO centralized_logs (
                                terminal_id, branch_id, level, message, module, log_timestamp, extra_data
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            terminal_id,
                            branch_id,
                            entry.get("level", "info"),
                            entry.get("message", "")[:1000],
                            entry.get("module", "unknown"),
                            entry.get("timestamp", datetime.now().isoformat()),
                            json.dumps(entry.get("extra")) if entry.get("extra") else None
                        ))
                        count += 1

                    conn.commit()

                    # Cleanup old logs (keep last 10000)
                    cursor.execute("""
                        DELETE FROM centralized_logs
                        WHERE id NOT IN (
                            SELECT id FROM centralized_logs ORDER BY id DESC LIMIT 10000
                        )
                    """)
                    conn.commit()

                    return count
                finally:
                    cursor.close()

        except Exception as e:
            logger.error(f"Error saving logs: {e}")
            return 0
    
    def get_logs(self,
                 level: Optional[str] = None,
                 terminal_id: Optional[int] = None,
                 branch_id: Optional[int] = None,
                 limit: int = 100) -> Dict[str, Any]:
        """Get logs with optional filters."""
        try:
            with self._lock:
                conn = self._get_conn()
                cursor = conn.cursor()
                try:
                    # SECURITY: Especificar columnas en lugar de SELECT *
                    query = "SELECT id, terminal_id, branch_id, level, message, module, log_timestamp, extra_data, created_at FROM centralized_logs WHERE 1=1"
                    params = []

                    if level:
                        query += " AND level = ?"
                        params.append(level)

                    if terminal_id is not None:
                        query += " AND terminal_id = ?"
                        params.append(terminal_id)

                    if branch_id is not None:
                        query += " AND branch_id = ?"
                        params.append(branch_id)

                    # SECURITY: Cap máximo para LIMIT
                    effective_limit = max(1, min(int(limit), 10000))
                    query += " ORDER BY id DESC LIMIT ?"
                    params.append(effective_limit)

                    cursor.execute(query, params)
                    rows = cursor.fetchall()

                    logs = []
                    for row in rows:
                        logs.append({
                            "id": row["id"],
                            "terminal_id": row["terminal_id"],
                            "branch_id": row["branch_id"],
                            "level": row["level"],
                            "message": row["message"],
                            "module": row["module"],
                            "timestamp": row["log_timestamp"]
                        })

                    # Get total count
                    cursor.execute("SELECT COUNT(*) FROM centralized_logs")
                    # FIX 2026-02-01: Validar fetchone() antes de acceder a [0]
                    row = cursor.fetchone()
                    conn.commit()  # Cerrar transacción implícita
                    total = row[0] if row else 0

                    return {
                        "logs": logs,
                        "total": len(logs),
                        "total_stored": total
                    }
                finally:
                    cursor.close()

        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            return {"logs": [], "total": 0, "total_stored": 0}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ALERTAS DE STOCK
    # ═══════════════════════════════════════════════════════════════════════════
    
    def save_alerts(self, terminal_id: int, branch_id: int, alerts: List[Dict]) -> int:
        """Save stock alerts (upsert by terminal/branch/sku)."""
        try:
            with self._lock:
                conn = self._get_conn()
                cursor = conn.cursor()
                try:
                    count = 0
                    for alert in alerts:
                        cursor.execute("""
                            INSERT INTO stock_alerts (
                                terminal_id, branch_id, sku, name, current_stock, min_stock, severity
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(terminal_id, branch_id, sku) DO UPDATE SET
                                name = excluded.name,
                                current_stock = excluded.current_stock,
                                min_stock = excluded.min_stock,
                                severity = excluded.severity,
                                created_at = CURRENT_TIMESTAMP
                        """, (
                            terminal_id,
                            branch_id,
                            alert.get("sku", ""),
                            alert.get("name", ""),
                            alert.get("current_stock", 0),
                            alert.get("min_stock", 0),
                            alert.get("severity", "warning")
                        ))
                        count += 1

                    conn.commit()
                    return count
                finally:
                    cursor.close()

        except Exception as e:
            logger.error(f"Error saving alerts: {e}")
            return 0
    
    def get_alerts(self) -> Dict[str, Any]:
        """Get all stock alerts with summary."""
        try:
            with self._lock:
                conn = self._get_conn()
                cursor = conn.cursor()
                try:
                    cursor.execute("""
                        SELECT id, terminal_id, branch_id, sku, name, current_stock,
                               min_stock, severity, created_at
                        FROM stock_alerts ORDER BY
                            CASE severity
                                WHEN 'out_of_stock' THEN 1
                                WHEN 'critical' THEN 2
                                ELSE 3
                            END,
                            created_at DESC
                    """)
                    rows = cursor.fetchall()

                    alerts = []
                    summary = {"out_of_stock": 0, "critical": 0, "warning": 0}

                    for row in rows:
                        severity = row["severity"]
                        summary[severity] = summary.get(severity, 0) + 1

                        alerts.append({
                            "sku": row["sku"],
                            "name": row["name"],
                            "current_stock": row["current_stock"],
                            "min_stock": row["min_stock"],
                            "severity": severity,
                            "terminal_id": row["terminal_id"],
                            "branch_id": row["branch_id"],
                            "created_at": row["created_at"]
                        })

                    return {
                        "alerts": alerts,
                        "total": len(alerts),
                        "summary": summary
                    }
                finally:
                    cursor.close()

        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            return {"alerts": [], "total": 0, "summary": {}}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MÉTRICAS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get storage metrics."""
        try:
            with self._lock:
                conn = self._get_conn()
                cursor = conn.cursor()
                try:
                    # FIX 2026-02-01: Validar fetchone() antes de acceder a [0] en cada query
                    cursor.execute("SELECT COUNT(*) FROM heartbeats")
                    row = cursor.fetchone()
                    terminals = row[0] if row else 0

                    cursor.execute("SELECT COUNT(*) FROM centralized_logs")
                    row = cursor.fetchone()
                    logs = row[0] if row else 0

                    cursor.execute("SELECT COUNT(*) FROM stock_alerts")
                    row = cursor.fetchone()
                    conn.commit()  # Cerrar transacción implícita
                    alerts = row[0] if row else 0

                    # DB size
                    db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

                    return {
                        "terminals": terminals,
                        "logs": logs,
                        "alerts": alerts,
                        "db_size_bytes": db_size,
                        "db_size_mb": round(db_size / 1024 / 1024, 2)
                    }
                finally:
                    cursor.close()

        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return {}
    
    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

# Singleton instance
_storage: Optional[GatewayStorage] = None

def get_storage() -> GatewayStorage:
    """Get singleton storage instance."""
    global _storage
    if _storage is None:
        _storage = GatewayStorage()
    return _storage
