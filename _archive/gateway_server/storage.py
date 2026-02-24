"""
TITAN Gateway - Global State Storage

Centralized state management for heartbeats, alerts, and logs.
Thread-safe implementation using locks for concurrent access.
"""
from datetime import datetime
import threading
from typing import Any, Dict, List

# Thread locks for concurrent access protection
_heartbeats_lock = threading.Lock()
_alerts_lock = threading.Lock()
_logs_lock = threading.Lock()
_cache_lock = threading.Lock()

# Global state for in-memory storage
TERMINAL_HEARTBEATS: Dict[str, Dict[str, Any]] = {}
STOCK_ALERTS: Dict[str, List[Dict[str, Any]]] = {}
CENTRALIZED_LOGS: List[Dict[str, Any]] = []
MAX_LOGS = 10000

# Cache system for performance
CACHE: Dict[str, tuple] = {}
CACHE_TTL = 60  # seconds


def get_cached(key: str) -> Any:
    """Get value from cache if exists and not expired. Thread-safe."""
    with _cache_lock:
        if key in CACHE:
            data, timestamp = CACHE[key]
            if (datetime.now() - timestamp).seconds < CACHE_TTL:
                return data
            # Expired, remove it
            del CACHE[key]
    return None


def set_cached(key: str, data: Any) -> None:
    """Set value in cache. Thread-safe."""
    with _cache_lock:
        CACHE[key] = (data, datetime.now())


def clear_cache() -> int:
    """Clear all cache entries. Thread-safe. Returns previous cache size."""
    with _cache_lock:
        size = len(CACHE)
        CACHE.clear()
        return size


# Thread-safe accessors for heartbeats
def get_heartbeat(terminal_id: str) -> Dict[str, Any] | None:
    """Get heartbeat for a terminal. Thread-safe."""
    with _heartbeats_lock:
        return TERMINAL_HEARTBEATS.get(terminal_id)


def set_heartbeat(terminal_id: str, heartbeat: Dict[str, Any]) -> None:
    """Set heartbeat for a terminal. Thread-safe."""
    with _heartbeats_lock:
        TERMINAL_HEARTBEATS[terminal_id] = heartbeat


def get_all_heartbeats() -> Dict[str, Dict[str, Any]]:
    """Get copy of all heartbeats. Thread-safe."""
    with _heartbeats_lock:
        return dict(TERMINAL_HEARTBEATS)


def clear_heartbeats() -> None:
    """Clear all heartbeats. Thread-safe."""
    with _heartbeats_lock:
        TERMINAL_HEARTBEATS.clear()


# Thread-safe accessors for stock alerts
def get_stock_alerts(branch_id: str) -> List[Dict[str, Any]]:
    """Get stock alerts for a branch. Thread-safe."""
    with _alerts_lock:
        return list(STOCK_ALERTS.get(branch_id, []))


def add_stock_alert(branch_id: str, alert: Dict[str, Any]) -> None:
    """Add stock alert for a branch. Thread-safe."""
    with _alerts_lock:
        if branch_id not in STOCK_ALERTS:
            STOCK_ALERTS[branch_id] = []
        STOCK_ALERTS[branch_id].append(alert)


def clear_stock_alerts(branch_id: str = None) -> None:
    """Clear stock alerts for a branch or all. Thread-safe."""
    with _alerts_lock:
        if branch_id:
            STOCK_ALERTS.pop(branch_id, None)
        else:
            STOCK_ALERTS.clear()


# Thread-safe accessors for centralized logs
def add_log(log_entry: Dict[str, Any]) -> None:
    """Add log entry. Thread-safe. Trims to MAX_LOGS."""
    with _logs_lock:
        CENTRALIZED_LOGS.append(log_entry)
        # Trim if exceeds max
        while len(CENTRALIZED_LOGS) > MAX_LOGS:
            CENTRALIZED_LOGS.pop(0)


def get_logs(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """Get logs with pagination. Thread-safe."""
    with _logs_lock:
        end = len(CENTRALIZED_LOGS) - offset
        start = max(0, end - limit)
        return list(CENTRALIZED_LOGS[start:end])


def clear_logs() -> int:
    """Clear all logs. Thread-safe. Returns previous count."""
    with _logs_lock:
        count = len(CENTRALIZED_LOGS)
        CENTRALIZED_LOGS.clear()
        return count
