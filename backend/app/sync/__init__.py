"""
TITAN POS - Synchronization Module

Handles MultiCaja synchronization, connectivity monitoring, and data sync.
"""

# Import with error handling for installations that may be missing some modules
try:
    from .sync_manager import SyncManager
except ImportError:
    # Fallback if sync_manager doesn't exist
    SyncManager = None

try:
    from .data_appliers import DataApplier
except ImportError:
    DataApplier = None

try:
    from .data_extractors import DataExtractor
except ImportError:
    DataExtractor = None

try:
    from .connectivity import ConnectivityMonitor
except ImportError:
    ConnectivityMonitor = None

__all__ = [
    "SyncManager",
    "DataApplier",
    "DataExtractor",
    "ConnectivityMonitor",
]
