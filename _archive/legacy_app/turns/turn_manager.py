"""
TITAN POS - Turn Manager

Handles turn lifecycle: opening, closing, and state management.
"""

from typing import Any, Dict, Optional
import logging

from PyQt6 import QtCore, QtWidgets

from app.core import STATE
from app.dialogs.turn_close_dialog import TurnCloseDialog
from app.dialogs.turn_open_dialog import TurnOpenDialog
from app.utils import permissions

logger = logging.getLogger(__name__)


class TurnManager(QtCore.QObject):
    """
    Manages turn lifecycle for the POS application.

    Handles:
    - Detecting existing open turns
    - Opening new turns
    - Closing turns
    - Syncing turn state with POSEngine
    """

    # Signals
    turn_opened = QtCore.pyqtSignal(int)  # turn_id
    turn_closed = QtCore.pyqtSignal(int)  # turn_id
    turn_continued = QtCore.pyqtSignal(int)  # turn_id

    def __init__(
        self,
        core,
        parent_window: QtWidgets.QMainWindow,
        parent: Optional[QtCore.QObject] = None
    ):
        """
        Initialize the turn manager.

        Args:
            core: POSCore instance
            parent_window: Parent window for dialogs
            parent: Parent QObject
        """
        super().__init__(parent)
        self.core = core
        self.parent_window = parent_window
        self._current_turn_id: Optional[int] = None

    @property
    def current_turn_id(self) -> Optional[int]:
        """Get current turn ID."""
        return self._current_turn_id

    @current_turn_id.setter
    def current_turn_id(self, value: Optional[int]) -> None:
        """Set current turn ID and sync with engine."""
        self._current_turn_id = value
        # Sync with POSEngine and STATE
        if hasattr(self.core, 'engine'):
            self.core.engine.current_turn_id = value
        STATE.current_turn_id = value

    def ensure_turn(self, sync_callback: Optional[callable] = None) -> None:
        """
        Ensure a turn is open, prompting user if necessary.

        This method handles:
        1. Detecting existing open turns
        2. Asking user to continue or close existing turn
        3. Opening a new turn if needed

        Args:
            sync_callback: Optional callback to call after opening turn (for sync)
        """
        existing = self.core.get_current_turn(STATE.branch_id, STATE.user_id)

        if existing:
            if self._handle_existing_turn(existing):
                return

        # Open new turn
        self._open_new_turn(sync_callback)

    def _handle_existing_turn(self, existing: Dict[str, Any]) -> bool:
        """
        Handle an existing open turn.

        Args:
            existing: Existing turn data

        Returns:
            True if turn was continued, False if it was closed
        """
        # Mostrar diálogo más claro con opciones explícitas
        msg = QtWidgets.QMessageBox(self.parent_window)
        msg.setWindowTitle("Turno Pendiente Detectado")
        msg.setIcon(QtWidgets.QMessageBox.Icon.Question)
        msg.setText(
            f"Se detectó un turno abierto iniciado el:\n"
            f"<b>{existing.get('start_timestamp', 'desconocido')}</b>\n\n"
            f"¿Qué deseas hacer?"
        )
        
        btn_continuar = msg.addButton("Continuar Turno", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        btn_cerrar = msg.addButton("Cerrar y Abrir Nuevo", QtWidgets.QMessageBox.ButtonRole.DestructiveRole)
        btn_cancelar = msg.addButton("Cancelar", QtWidgets.QMessageBox.ButtonRole.RejectRole)
        
        msg.setDefaultButton(btn_continuar)
        msg.exec()
        
        clicked = msg.clickedButton()
        
        if clicked == btn_continuar:
            # Continuar con el turno existente
            self.current_turn_id = existing["id"]
            logger.info(f"Continuing previous turn: ID={existing['id']}")
            self.turn_continued.emit(existing["id"])
            
            # Abrir cajón al continuar turno
            try:
                from app.utils.ticket_engine import open_cash_drawer_safe
                open_cash_drawer_safe(core=self.core)
            except Exception as e:
                logger.warning(f"No se pudo abrir cajón al continuar turno: {e}")
            
            return True
        
        elif clicked == btn_cerrar:
            # Cerrar turno anterior y abrir uno nuevo
            try:
                summary = self.core.get_turn_summary(existing["id"])
                dlg_close = TurnCloseDialog(summary, self.core, self.parent_window)

                if dlg_close.exec() != QtWidgets.QDialog.DialogCode.Accepted or not dlg_close.result_data:
                    # Usuario canceló el cierre, volver a preguntar
                    return self._handle_existing_turn(existing)

                # Cerrar turno anterior
                self.core.close_turn(
                    STATE.user_id,
                    dlg_close.result_data["closing_amount"],
                    dlg_close.result_data.get("notes")
                )

                # Abrir cajón después de cerrar turno anterior (para contar efectivo)
                try:
                    from app.utils.ticket_engine import open_cash_drawer_safe
                    open_cash_drawer_safe(core=self.core)
                except Exception as e:
                    logger.warning(f"No se pudo abrir cajón al cerrar turno anterior: {e}")

                self.turn_closed.emit(existing["id"])
                logger.info(f"Previous turn closed: ID={existing['id']}, opening new turn...")
                
                # Ahora abrir nuevo turno con fondo de caja inicial
                self.current_turn_id = None
                return False  # Retornar False para que se abra un nuevo turno

            except Exception as exc:
                logger.error(f"Error closing previous turn: {exc}")
                QtWidgets.QMessageBox.critical(
                    self.parent_window,
                    "Error al cerrar turno anterior",
                    f"No se pudo cerrar el turno anterior:\n{exc}\n\n"
                    "Se continuará con el turno existente."
                )
                # En caso de error, continuar con el turno existente
                self.current_turn_id = existing["id"]
                self.turn_continued.emit(existing["id"])
                return True
        
        else:  # Cancelar
            # Usuario canceló, cerrar aplicación
            logger.info("User cancelled turn handling, closing application")
            self.parent_window.close()
            return True  # Retornar True para evitar loop infinito

    def _open_new_turn(self, sync_callback: Optional[callable] = None) -> None:
        """
        Open a new turn with mandatory loop.

        Args:
            sync_callback: Optional callback after turn is opened
        """
        if not permissions.can_open_turn():
            QtWidgets.QMessageBox.critical(
                self.parent_window,
                "Permisos Insuficientes",
                "No tienes permiso para abrir turnos.\n\nContacta al administrador del sistema."
            )
            self.parent_window.close()
            return

        # FIX 2026-02-01: Loop obligatorio con salidas claras (break en éxito, return en Close)
        # Mandatory loop until turn is opened
        while True:
            dlg = TurnOpenDialog(STATE.username or "Usuario", self.core, self.parent_window)

            if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted and dlg.result_data:
                try:
                    turn_id = self.core.open_turn(
                        STATE.branch_id,
                        STATE.user_id,
                        dlg.result_data["opening_amount"],
                        dlg.result_data.get("notes")
                    )
                    self.current_turn_id = turn_id

                    logger.info(f"✅ Nuevo turno abierto exitosamente: ID={turn_id}, Fondo inicial: ${dlg.result_data['opening_amount']:.2f}")
                    
                    # Abrir cajón después de abrir turno (para contar fondo de caja)
                    try:
                        from app.utils.ticket_engine import open_cash_drawer_safe
                        open_cash_drawer_safe(core=self.core)
                    except Exception as e:
                        logger.warning(f"No se pudo abrir cajón al abrir turno: {e}")
                    
                    self.turn_opened.emit(turn_id)

                    # Call sync callback if provided
                    if sync_callback:
                        QtCore.QTimer.singleShot(1000, sync_callback)
                        logger.info("Turn opened - auto-sync scheduled")

                    # Mostrar mensaje de confirmación
                    QtWidgets.QMessageBox.information(
                        self.parent_window,
                        "✅ Turno Abierto",
                        f"Turno #{turn_id} abierto correctamente.\n"
                        f"Fondo de caja inicial: ${dlg.result_data['opening_amount']:.2f}"
                    )

                    break

                except Exception as exc:
                    logger.error(f"Error opening turn: {exc}")
                    QtWidgets.QMessageBox.critical(
                        self.parent_window,
                        "Error al Abrir Turno",
                        str(exc)
                    )
            else:
                # User cancelled
                reply = QtWidgets.QMessageBox.critical(
                    self.parent_window,
                    "Turno Requerido",
                    "Debes abrir un turno para usar el sistema de punto de venta.\n\n"
                    "El turno es necesario para:\n"
                    "- Registrar ventas correctamente\n"
                    "- Llevar control de efectivo en caja\n"
                    "- Generar reportes precisos\n\n"
                    "¿Qué deseas hacer?",
                    QtWidgets.QMessageBox.StandardButton.Retry | QtWidgets.QMessageBox.StandardButton.Close,
                    QtWidgets.QMessageBox.StandardButton.Retry
                )

                if reply == QtWidgets.QMessageBox.StandardButton.Close:
                    logger.info("User chose to close application instead of opening turn")
                    self.parent_window.close()
                    return

    def close_turn(self) -> bool:
        """
        Close the current turn.

        Returns:
            True if turn was closed successfully, False otherwise
        """
        if not permissions.can_close_turn():
            QtWidgets.QMessageBox.warning(
                self.parent_window,
                "Permisos",
                "No puedes cerrar turno"
            )
            return False

        turn = self.core.get_current_turn(STATE.branch_id, STATE.user_id)
        if not turn:
            QtWidgets.QMessageBox.information(
                self.parent_window,
                "Turno",
                "No hay turno abierto"
            )
            return False

        summary = self.core.get_turn_summary(turn["id"])
        dlg = TurnCloseDialog(summary, self.core, self.parent_window)

        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted and dlg.result_data:
            try:
                self.core.close_turn(
                    turn["id"],
                    dlg.result_data["closing_amount"],
                    dlg.result_data.get("notes")
                )
                
                # Abrir cajón después de cerrar turno (para contar efectivo final)
                try:
                    from app.utils.ticket_engine import open_cash_drawer_safe
                    open_cash_drawer_safe(core=self.core)
                except Exception as e:
                    logger.warning(f"No se pudo abrir cajón al cerrar turno: {e}")

                self.turn_closed.emit(turn["id"])
                self.current_turn_id = None

                QtWidgets.QMessageBox.information(
                    self.parent_window,
                    "Turno",
                    "Turno cerrado"
                )
                return True

            except Exception as exc:
                QtWidgets.QMessageBox.critical(
                    self.parent_window,
                    "Error",
                    str(exc)
                )

        return False

    def close_turn_on_exit(self) -> bool:
        """
        Handle turn closing when application exits.

        Returns:
            True if exit should proceed, False to cancel
        """
        turn = self.core.get_current_turn(STATE.branch_id, STATE.user_id)
        if not turn:
            logger.info("No open turn found, exit allowed")
            return True

        # Mostrar diálogo más claro con opciones explícitas
        msg = QtWidgets.QMessageBox(self.parent_window)
        msg.setWindowTitle("Turno Pendiente")
        msg.setIcon(QtWidgets.QMessageBox.Icon.Question)
        msg.setText(
            f"Tienes un turno abierto iniciado el:\n"
            f"<b>{turn.get('start_timestamp', 'desconocido')}</b>\n\n"
            f"¿Qué deseas hacer antes de cerrar la aplicación?"
        )
        
        btn_cerrar_turno = msg.addButton("Cerrar Turno y Salir", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        btn_dejar_pendiente = msg.addButton("Dejar Pendiente y Salir", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
        btn_cancelar = msg.addButton("Cancelar", QtWidgets.QMessageBox.ButtonRole.RejectRole)
        
        msg.setDefaultButton(btn_cerrar_turno)
        msg.exec()
        
        clicked = msg.clickedButton()
        
        if clicked == btn_cancelar:
            logger.info("User cancelled exit")
            return False
        
        if clicked == btn_cerrar_turno:
            # Cerrar turno con corte de caja
            try:
                summary = self.core.get_turn_summary(turn["id"])
                dlg = TurnCloseDialog(summary, self.core, self.parent_window)

                if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted and dlg.result_data:
                    # Show progress
                    progress = QtWidgets.QProgressDialog(
                        "Cerrando turno y realizando corte de caja...",
                        None, 0, 0,
                        self.parent_window
                    )
                    progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
                    progress.show()
                    QtWidgets.QApplication.processEvents()

                    try:
                        self.core.close_turn(
                            turn["id"],
                            dlg.result_data["closing_amount"],
                            dlg.result_data.get("notes"),
                            expected_cash=summary.get("expected_cash", 0.0)
                        )
                        logger.info(f"Turn closed on exit: ID={turn['id']}")
                        
                        # Abrir cajón después de cerrar turno (para contar efectivo final)
                        try:
                            from app.utils.ticket_engine import open_cash_drawer_safe
                            open_cash_drawer_safe(core=self.core)
                        except Exception as e:
                            logger.warning(f"No se pudo abrir cajón al cerrar turno: {e}")
                        
                        self.turn_closed.emit(turn["id"])
                        self.current_turn_id = None
                    finally:
                        progress.close()

                    QtWidgets.QApplication.processEvents()
                    return True
                else:
                    # Usuario canceló el cierre de turno
                    logger.info("User cancelled turn close dialog")
                    return False

            except Exception as exc:
                logger.error(f"Error closing turn on exit: {exc}")
                QtWidgets.QMessageBox.critical(
                    self.parent_window,
                    "Error",
                    f"No se pudo cerrar el turno:\n{exc}\n\n"
                    "El turno quedará pendiente."
                )
                # Permitir salir aunque haya error
                return True
        
        elif clicked == btn_dejar_pendiente:
            # Dejar turno pendiente y salir
            logger.info(f"Leaving turn open on exit: ID={turn['id']}")
            return True

        return True
