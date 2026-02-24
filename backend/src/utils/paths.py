import logging
import os
import sys

logger = logging.getLogger(__name__)


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def get_data_dir():
    """Retorna el directorio persistente para datos de usuario."""
    if getattr(sys, 'frozen', False):
        home = os.path.expanduser("~")
        data_dir = os.path.join(home, ".titan_pos")
    else:
        data_dir = os.getcwd()

    if not os.path.exists(data_dir):
        try:
            os.makedirs(data_dir)
        except OSError as e:
            logger.debug(f"Could not create data directory {data_dir}: {e}")
    return data_dir
