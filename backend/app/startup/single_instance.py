"""
TITAN POS - Single Instance Guard

Ensures only one instance of the application can run at a time.
"""

import sys

from PyQt6 import QtCore


class SingleInstanceGuard:
    """
    Prevents multiple instances of the application from running.

    Uses Qt's QSharedMemory to create a system-wide lock.

    Usage:
        guard = SingleInstanceGuard("MyApp_Instance_Lock")
        if not guard.try_lock():
            print("Application is already running")
            sys.exit(0)

        # Keep reference to guard throughout application lifetime
        app._instance_guard = guard
    """

    def __init__(self, key: str = "POS_Novedades_Lupita_Instance_Lock"):
        """
        Initialize the instance guard.

        Args:
            key: Unique identifier for the shared memory lock
        """
        self.key = key
        self.shared_memory = QtCore.QSharedMemory(key)
        self._locked = False

    def try_lock(self) -> bool:
        """
        Attempt to acquire the instance lock.

        Returns:
            True if lock was acquired (this is the first instance),
            False if another instance is already running.
        """
        if self.shared_memory.create(1):
            self._locked = True
            return True
        return False

    def is_locked(self) -> bool:
        """Check if this guard holds the lock."""
        return self._locked

    def release(self) -> None:
        """Release the instance lock."""
        if self._locked and self.shared_memory.isAttached():
            self.shared_memory.detach()
            self._locked = False

    @staticmethod
    def check_or_exit(key: str = "POS_Novedades_Lupita_Instance_Lock") -> "SingleInstanceGuard":
        """
        Check for existing instance and exit if found.

        Convenience method that creates a guard, checks for lock,
        and exits the application if another instance is running.

        Args:
            key: Unique identifier for the shared memory lock

        Returns:
            SingleInstanceGuard instance if lock was acquired
        """
        guard = SingleInstanceGuard(key)

        if not guard.try_lock():
            print("\n" + "=" * 50)
            print("The point of sale is already open.")
            print("Cannot open more than one instance.")
            print("=" * 50 + "\n")
            sys.exit(0)

        return guard
