"""
Camera Scanner Thread stub.

This is a placeholder for camera-based barcode scanning functionality.
Implement with OpenCV or similar library when camera scanning is needed.
"""
from PyQt6.QtCore import QThread


class CameraScannerThread(QThread):
    """
    Thread for camera-based barcode scanning.

    This is a stub implementation. To enable camera scanning:
    1. Install opencv-python: pip install opencv-python
    2. Install pyzbar: pip install pyzbar
    3. Implement run() to capture frames and decode barcodes
    """

    def __init__(self, *args):
        super().__init__()
        self._running = False

    def run(self):
        """
        Main thread loop for camera scanning.

        Raises:
            NotImplementedError: Camera scanning not yet implemented.
        """
        raise NotImplementedError(
            "CameraScannerThread.run() not implemented. "
            "Install opencv-python and pyzbar, then implement frame capture and barcode decoding."
        )

    def stop(self):
        """Signal the thread to stop."""
        self._running = False
