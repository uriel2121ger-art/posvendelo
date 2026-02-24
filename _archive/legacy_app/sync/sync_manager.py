"""
TITAN POS - Sync Manager

Orchestrates bidirectional synchronization between local and remote databases.
"""

from typing import Optional
import logging
import threading

from PyQt6 import QtCore
from PyQt6.QtCore import QMetaObject, Qt, QThread, Q_ARG
from PyQt6.QtWidgets import QApplication

from app.startup.bootstrap import log_debug
from app.sync.data_appliers import DataApplier
from app.sync.data_extractors import DataExtractor

logger = logging.getLogger(__name__)


class SyncManager(QtCore.QObject):
    """
    Manages bidirectional MultiCaja synchronization.

    Handles both PUSH (local -> server) and PULL (server -> local)
    operations in a background thread to avoid UI blocking.
    """

    # Signals
    sync_started = QtCore.pyqtSignal()
    sync_completed = QtCore.pyqtSignal(bool, str)  # success, message
    sync_progress = QtCore.pyqtSignal(str, int, int)  # phase, current, total

    def __init__(self, core, network_client, parent: Optional[QtCore.QObject] = None):
        """
        Initialize the sync manager.

        Args:
            core: POSCore instance
            network_client: NetworkClient instance for server communication
            parent: Parent QObject
        """
        super().__init__(parent)
        self.core = core
        self.network_client = network_client
        self._sync_thread: Optional[threading.Thread] = None
        self._extractor = DataExtractor(core)
        self._applier = DataApplier(core)
        # FIX: Lock para evitar race conditions entre get_for_sync y mark_synced
        self._sync_lock = threading.Lock()

    # ========== Thread-safe signal emission methods ==========

    def _is_main_thread(self) -> bool:
        """Check if current thread is the main Qt thread."""
        app = QApplication.instance()
        if app is None:
            return True
        return QThread.currentThread() == app.thread()

    def _safe_emit_started(self) -> None:
        """Emit sync_started signal safely from any thread."""
        if self._is_main_thread():
            self.sync_started.emit()
        else:
            QMetaObject.invokeMethod(
                self, "_emit_started_slot",
                Qt.ConnectionType.QueuedConnection
            )

    @QtCore.pyqtSlot()
    def _emit_started_slot(self) -> None:
        """Slot to emit sync_started from main thread."""
        self.sync_started.emit()

    def _safe_emit_completed(self, success: bool, message: str) -> None:
        """Emit sync_completed signal safely from any thread."""
        if self._is_main_thread():
            self.sync_completed.emit(success, message)
        else:
            QMetaObject.invokeMethod(
                self, "_emit_completed_slot",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(bool, success),
                Q_ARG(str, message)
            )

    @QtCore.pyqtSlot(bool, str)
    def _emit_completed_slot(self, success: bool, message: str) -> None:
        """Slot to emit sync_completed from main thread."""
        self.sync_completed.emit(success, message)

    def _safe_emit_progress(self, phase: str, current: int, total: int) -> None:
        """Emit sync_progress signal safely from any thread."""
        if self._is_main_thread():
            self.sync_progress.emit(phase, current, total)
        else:
            QMetaObject.invokeMethod(
                self, "_emit_progress_slot",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, phase),
                Q_ARG(int, current),
                Q_ARG(int, total)
            )

    @QtCore.pyqtSlot(str, int, int)
    def _emit_progress_slot(self, phase: str, current: int, total: int) -> None:
        """Slot to emit sync_progress from main thread."""
        self.sync_progress.emit(phase, current, total)

    # ========== Public API ==========

    @property
    def is_syncing(self) -> bool:
        """Check if sync is currently in progress."""
        return self._sync_thread is not None and self._sync_thread.is_alive()

    def sync(self) -> None:
        """
        Perform bidirectional synchronization.

        This method starts the sync in a background thread.
        Use signals to track progress and completion.
        """
        if self.is_syncing:
            log_debug("sync_manager:sync", "Sync already in progress, skipping", {}, "A")
            logger.debug("Sync already in progress, skipping")
            return

        log_debug("sync_manager:sync", "Starting sync", {}, "A")
        self._safe_emit_started()

        self._sync_thread = threading.Thread(target=self._sync_worker, daemon=True)
        self._sync_thread.start()
        logger.debug("Sync thread started")

    def _sync_worker(self) -> None:
        """
        Worker function that runs in background thread.

        Performs both PUSH and PULL operations.
        """
        log_debug("sync_manager:worker", "Sync worker started", {
            "thread_name": threading.current_thread().name
        }, "A")

        try:
            if not self.network_client:
                log_debug("sync_manager:worker", "No network client", {}, "A")
                self._safe_emit_completed(False, "No network client configured")
                return

            # Get config
            cfg = self.core.get_app_config() or {}
            token = cfg.get("api_dashboard_token", "")

            if not token:
                log_debug("sync_manager:worker", "No API token", {}, "B")
                logger.warning("No API token configured, skipping sync")
                self._safe_emit_completed(False, "No API token configured")
                return

            # Create sync client
            from app.utils.network_client import MultiCajaClient
            sync_client = MultiCajaClient(
                self.network_client.base_url,
                timeout=15,
                token=token
            )

            # ========== PHASE 1: PUSH (Local -> Server) ==========
            self._push_to_server(sync_client)

            # ========== PHASE 2: PULL (Server -> Local) ==========
            self._pull_from_server(sync_client)

            self._safe_emit_completed(True, "Sync completed successfully")
            log_debug("sync_manager:worker", "Sync completed", {}, "A")

        except Exception as e:
            logger.error(f"MultiCaja sync error: {e}")
            self._safe_emit_completed(False, str(e))

    def _normalize_accepted_ids(self, raw_ids, fallback_ids):
        """E4/E5/E7: Normaliza accepted_ids a enteros; usa fallback si el servidor no envió lista."""
        normalized = []
        for x in (raw_ids if raw_ids is not None else []):
            try:
                if x is not None:
                    normalized.append(int(x))
            except (TypeError, ValueError):
                pass
        if not normalized and fallback_ids:
            for x in fallback_ids:
                try:
                    if x is not None:
                        normalized.append(int(x))
                except (TypeError, ValueError):
                    pass
        return normalized

    def _push_to_server(self, sync_client) -> None:
        """Push local data to server and mark as synced on success."""
        # FIX: Usar lock para evitar race conditions entre get_for_sync y mark_synced
        with self._sync_lock:
            # Products
            products = self._extractor.get_products_for_sync()
            if products:
                self._safe_emit_progress("push_products", 0, len(products))
                success, msg, data = sync_client.sync_inventory(products)
                if success:
                    all_ids = [p['id'] for p in products if p.get('id')]
                    raw = data.get('accepted_ids', all_ids) if isinstance(data, dict) else all_ids
                    accepted_ids = self._normalize_accepted_ids(raw, all_ids)
                    self._extractor.mark_products_synced(accepted_ids)
                    logger.info(f"📤 PUSH: {len(accepted_ids)}/{len(products)} products accepted by server")

            # Sales
            sales = self._extractor.get_sales_for_sync()
            if sales:
                self._safe_emit_progress("push_sales", 0, len(sales))
                success, msg, data = sync_client.sync_sales(sales)
                if success:
                    all_ids = [s['id'] for s in sales if s.get('id')]
                    raw = data.get('accepted_ids', all_ids) if isinstance(data, dict) else all_ids
                    accepted_ids = self._normalize_accepted_ids(raw, all_ids)
                    self._extractor.mark_sales_synced(accepted_ids)
                    logger.info(f"📤 PUSH: {len(accepted_ids)}/{len(sales)} sales accepted by server")

            # Customers
            customers = self._extractor.get_customers_for_sync()
            if customers:
                self._safe_emit_progress("push_customers", 0, len(customers))
                success, msg, data = sync_client.sync_customers(customers)
                if success:
                    all_ids = [c['id'] for c in customers if c.get('id')]
                    raw = data.get('accepted_ids', all_ids) if isinstance(data, dict) else all_ids
                    accepted_ids = self._normalize_accepted_ids(raw, all_ids)
                    self._extractor.mark_customers_synced(accepted_ids)
                    logger.info(f"📤 PUSH: {len(accepted_ids)}/{len(customers)} customers accepted by server")

            # Parte A Fase 2: PUSH inventory movements (delta sync); terminal_id para idempotencia (Fase 2.4)
            movements = self._extractor.get_inventory_movements_for_sync()
            if movements:
                self._safe_emit_progress("push_movements", 0, len(movements))
                cfg = self.core.get_app_config() or {}
                terminal_id = cfg.get("terminal_id") or cfg.get("pos_id") or 1
                success, msg, data = sync_client.sync_inventory_movements(movements, terminal_id=str(terminal_id))
                if success:
                    all_ids = [m['id'] for m in movements if m.get('id')]
                    raw = data.get('accepted_ids', all_ids) if isinstance(data, dict) else all_ids
                    accepted_ids = self._normalize_accepted_ids(raw, all_ids)
                    self._extractor.mark_inventory_movements_synced(accepted_ids)
                    logger.info(f"📤 PUSH: {len(accepted_ids)}/{len(movements)} inventory movements accepted")

    def _pull_from_server(self, sync_client) -> None:
        """Pull data from server and apply locally."""
        # FIX: Usar lock para evitar race conditions durante aplicación de datos
        with self._sync_lock:
            # Inventory
            self._safe_emit_progress("pull_inventory", 0, 0)
            success, msg, products = sync_client.pull_inventory()
            if success and products:
                log_debug("sync_manager:pull", "About to apply inventory", {
                    "products_count": len(products)
                }, "B")
                result = self._applier.apply_inventory(products)
                logger.info(f"📥 PULL: {len(products)} products from server applied")

            # Sales
            self._safe_emit_progress("pull_sales", 0, 0)
            success, msg, sales = sync_client.pull_sales(limit=500)
            if success and sales:
                result = self._applier.apply_sales(sales)
                logger.info(f"📥 PULL: {len(sales)} sales from server applied")

            # Customers
            self._safe_emit_progress("pull_customers", 0, 0)
            success, msg, customers = sync_client.pull_customers()
            if success and customers:
                result = self._applier.apply_customers(customers)
                logger.info(f"📥 PULL: {len(customers)} customers from server applied")


class AutoSyncScheduler:
    """
    Schedules automatic synchronization at regular intervals.

    Can be used to set up periodic sync for client mode.
    """

    def __init__(
        self,
        sync_manager: SyncManager,
        interval_seconds: int = 30
    ):
        """
        Initialize the scheduler.

        Args:
            sync_manager: SyncManager instance to use for syncing
            interval_seconds: Seconds between sync attempts
        """
        self.sync_manager = sync_manager
        self.interval_ms = interval_seconds * 1000
        self._timer: Optional[QtCore.QTimer] = None

    def start(self) -> None:
        """Start automatic synchronization."""
        if self._timer is not None:
            return

        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self.sync_manager.sync)
        self._timer.start(self.interval_ms)

        logger.info(f"Auto-sync scheduled every {self.interval_ms/1000}s")

    def stop(self) -> None:
        """Stop automatic synchronization."""
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
            logger.info("Auto-sync stopped")

    def sync_now(self) -> None:
        """Trigger immediate sync."""
        self.sync_manager.sync()
