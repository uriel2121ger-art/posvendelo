"""
TITAN POS - Crash Handler

Global exception handler for unhandled exceptions.
Writes crash reports to user's home directory for easy access.
"""

from datetime import datetime
import io
import os
import sys
import traceback


def _sanitize_path(text: str, home: str) -> str:
    """Replace home directory path with ~ for privacy."""
    if isinstance(text, str):
        return text.replace(home, "~")
    return text


def log_crash(exc_type, exc_value, exc_traceback) -> None:
    """
    Write fatal error to a visible file in user's home directory.

    This handler is designed to capture crashes even when the GUI
    is not responsive, writing to a simple text file.

    Args:
        exc_type: Exception type
        exc_value: Exception value
        exc_traceback: Exception traceback
    """
    home = os.path.expanduser("~")
    log_path = os.path.join(home, "TITAN_POS_CRASH.txt")

    # Import DATA_DIR lazily to avoid circular imports
    try:
        from app.startup.bootstrap import DATA_DIR
        data_dir = DATA_DIR
    except ImportError:
        data_dir = os.getcwd()

    try:
        with open(log_path, "w") as f:
            f.write(f"TITAN POS CRASH REPORT - {datetime.now()}\n")
            f.write("=" * 60 + "\n")
            f.write(f"Type: {exc_type.__name__}\n")
            f.write(f"Message: {_sanitize_path(str(exc_value), home)}\n")
            f.write("=" * 60 + "\n")

            # Capture and sanitize traceback
            tb_buffer = io.StringIO()
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=tb_buffer)
            f.write(_sanitize_path(tb_buffer.getvalue(), home))

            f.write("\n" + "=" * 60 + "\n")
            f.write(f"Data Dir: {_sanitize_path(data_dir, home)}\n")
            f.write(f"Frozen: {getattr(sys, 'frozen', False)}\n")
            f.write(f"Platform: {sys.platform}\n")
            f.write(f"Python: {sys.version}\n")
    except Exception:
        pass

    # Console output (non-blocking)
    print(f"\n{'=' * 60}")
    print(f"FATAL ERROR: {exc_type.__name__}")
    print(f"Message: {exc_value}")
    print(f"Report saved to: {log_path}")
    print(f"{'=' * 60}\n")

    # Call original excepthook
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def install_crash_handler() -> None:
    """
    Install the global crash handler.

    This should be called early in application startup.
    """
    sys.excepthook = log_crash
