"""
TITAN POS - Application Entry Points

Main entry functions for running the POS application.
"""

import logging
import os
import sys
from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from app.core import APP_NAME, POSCore
from app.startup import (
    ASSETS_DIR,
    DATA_DIR,
    install_crash_handler,
    SingleInstanceGuard,
)
from app.utils.theme_manager import theme_manager
from app.utils.animations import fade_in

logger = logging.getLogger(__name__)


def _load_custom_fonts(app: QtWidgets.QApplication) -> None:
    """
    Load custom fonts (Poppins) for the application.

    Args:
        app: QApplication instance
    """
    font_ids = [
        QtGui.QFontDatabase.addApplicationFont(str(ASSETS_DIR / "fonts/Poppins-Regular.ttf")),
        QtGui.QFontDatabase.addApplicationFont(str(ASSETS_DIR / "fonts/Poppins-Medium.ttf")),
        QtGui.QFontDatabase.addApplicationFont(str(ASSETS_DIR / "fonts/Poppins-Bold.ttf"))
    ]

    if any(fid != -1 for fid in font_ids):
        try:
            first_valid_id = next((fid for fid in font_ids if fid != -1), -1)

            if first_valid_id != -1:
                families = QtGui.QFontDatabase.applicationFontFamilies(first_valid_id)
            else:
                families = []
        except Exception as e:
            logger.warning(f"Error obteniendo familias de fuentes: {e}")
            families = []
        if families:
            font_family = families[0]
            app_font = QtGui.QFont(font_family)
            app_font.setPointSize(10)
            app.setFont(app_font)
            print(f"Font loaded: {font_family}")


def _setup_app_icon(app: QtWidgets.QApplication) -> None:
    """
    Set application icon.

    Args:
        app: QApplication instance
    """
    icon_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'icon.png')
    if os.path.exists(icon_path):
        app.setWindowIcon(QtGui.QIcon(icon_path))


def run_app(
    core: POSCore,
    *,
    mode: str = "server",
    network_client=None,
    theme_name: str = "Cyber Night",
    app_instance: Optional[QtWidgets.QApplication] = None,
) -> None:
    """
    Run the main POS application.

    Args:
        core: POSCore instance
        mode: Operating mode ("server" or "client")
        network_client: Network client for client mode
        theme_name: Theme name to apply
        app_instance: Optional existing QApplication instance
    """
    app = app_instance or QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    try:
        from app.ui.themes.loader import load_fonts
        load_fonts(app)
    except Exception as e:
        logger.warning(f"Could not load Cyber Night fonts, trying fallback: {e}")
        try:
            _load_custom_fonts(app)
        except Exception as fallback_e:
            logger.warning(f"Fallback font loading also failed: {fallback_e}")

    QtWidgets.QApplication.setStyle(QtWidgets.QStyleFactory.create("Fusion"))

    try:
        from app.utils.theme_manager import theme_manager
        cfg = core.read_local_config() if core else {}
        theme_name = cfg.get("theme", "Cyber Night")

        theme_manager.apply_theme(app, theme_name)
        logger.info(f"Tema '{theme_name}' aplicado")

        if theme_name == "Cyber Night":
            from app.ui.themes.loader import load_theme
            try:
                if load_theme(app, "cyber_night"):
                    logger.info("QSS Cyber Night cargado")
            except Exception as qss_error:
                logger.warning(f"No se pudo cargar QSS Cyber Night: {qss_error}")
    except Exception as e:
        logger.error(f"Error cargando tema: {e}")
        try:
            from app.ui.themes.loader import load_theme
            load_theme(app, "cyber_night")
        except Exception as fallback_error:
            logger.warning(f"Fallback QSS tambien fallo: {fallback_error}")

    from app.dialogs.login_dialog import LoginDialog
    login = LoginDialog(core)
    if login.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        sys.exit(0)

    from app.main import POSWindow
    window = POSWindow(core, mode=mode, network_client=network_client)

    window.showMaximized()
    window.raise_()
    window.activateWindow()

    try:
        exit_code = app.exec()
    except Exception as e:
        logger.error(f"Error during application execution: {e}", exc_info=True)
        exit_code = 1
    finally:
        try:
            if hasattr(core, 'db') and core.db:
                if hasattr(core.db, 'backend') and hasattr(core.db.backend, 'connection_pool'):
                    if core.db.backend.connection_pool:
                        try:
                            core.db.backend.connection_pool.closeall()
                        except Exception as e:
                            logger.debug("connection_pool.closeall: %s", e)
        except Exception as e:
            logger.debug("Entry cleanup: %s", e)

    sys.exit(exit_code)


def run_wizard(
    core: POSCore,
    *,
    mode: str = "server",
    network_client=None,
    theme_name: str = "Cyber Night",
    app_instance: Optional[QtWidgets.QApplication] = None,
) -> None:
    """
    Run the setup wizard followed by the main application.

    Args:
        core: POSCore instance
        mode: Operating mode
        network_client: Network client for client mode
        theme_name: Theme name to apply
        app_instance: Optional existing QApplication instance
    """
    app = app_instance or QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    QtWidgets.QApplication.setStyle(QtWidgets.QStyleFactory.create("Fusion"))

    try:
        from app.ui.themes.loader import load_theme, load_fonts
        load_fonts(app)
        if load_theme(app, "cyber_night"):
            logger.info("Tema Cyber Night cargado en wizard")
        else:
            logger.error("No se pudo cargar el tema Cyber Night")
    except Exception as e:
        logger.error(f"Error cargando tema Cyber Night: {e}")

    from app.ui.welcome_wizard import WelcomeWizard
    wizard = WelcomeWizard(core)
    fade_in(wizard)

    if wizard.exec() == QtWidgets.QDialog.DialogCode.Accepted:
        run_app(
            core,
            mode=mode,
            network_client=network_client,
            theme_name=theme_name,
            app_instance=app
        )


def main() -> None:
    """
    Main entry point for TITAN POS.

    Handles:
    - Single instance check
    - Crash handler installation
    - Core initialization
    - Network client setup (for client mode)
    - Auto-sync startup (if configured)
    - Wizard or main app launch
    """
    original_excepthook = sys.excepthook
    install_crash_handler()

    def pyqt_exception_handler(exc_type, exc_value, exc_traceback):
        """Handle unhandled exceptions in PyQt6 event loop."""
        import traceback
        from pathlib import Path

        try:
            crash_log_file = Path(DATA_DIR) / "logs" / "crash_debug.log"
            crash_log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(crash_log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*80}\n")
                f.write(f"[PYQT6 UNHANDLED EXCEPTION] {exc_type.__name__}\n")
                f.write(f"Message: {str(exc_value)}\n")
                f.write(f"\nTraceback:\n{''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))}\n")
                f.write(f"{'='*80}\n\n")
                f.flush()
        except Exception as log_err:
            print(f"[CRASH_DEBUG] Failed to log PyQt6 exception: {log_err}", file=sys.stderr)

        logger.critical(
            f"Unhandled PyQt6 exception: {exc_type.__name__}: {exc_value}",
            exc_info=(exc_type, exc_value, exc_traceback)
        )

        original_excepthook(exc_type, exc_value, exc_traceback)

    sys.excepthook = pyqt_exception_handler

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    _setup_app_icon(app)

    try:
        from app.utils.dialog_center_filter import install_dialog_center_filter
        install_dialog_center_filter(app)
    # FIX 2026-02-01: Agregar logging mínimo en lugar de excepción silenciada
    except ImportError as e:
        logger.debug(f"Error importing dialog_center_filter: {e}")

    guard = SingleInstanceGuard.check_or_exit()
    app._instance_guard = guard

    core = POSCore()
    cfg = core.read_local_config()

    mode = cfg.get("mode", "server")
    network_client = None

    if mode == "client":
        from app.utils.network_client import MultiCajaClient
        server_url = f"http://{cfg.get('server_ip', '127.0.0.1')}:{cfg.get('server_port', 8000)}"
        token = cfg.get("api_dashboard_token", "")
        network_client = MultiCajaClient(server_url, token=token)

    setup_done = (cfg.get("setup_completed") or cfg.get("setup_complete")) and core.db is not None

    if setup_done:
        should_start = False
        if cfg.get("central_enabled"):
            should_start = True
            logger.info("Iniciando AutoSyncService para servidor central externo")
        elif mode == "client":
            should_start = True
            logger.info("Iniciando AutoSyncService para sincronizacion LAN")

        if should_start:
            try:
                from app.services.auto_sync import start_auto_sync
                start_auto_sync(core)
            except Exception as e:
                logger.warning(f"Could not start auto-sync: {e}")

    theme_name = "Cyber Night"

    if setup_done:
        run_app(
            core,
            mode=mode,
            network_client=network_client,
            theme_name=theme_name,
            app_instance=app
        )
    else:
        run_wizard(
            core,
            mode=mode,
            network_client=network_client,
            theme_name=theme_name,
            app_instance=app
        )


if __name__ == "__main__":
    main()
