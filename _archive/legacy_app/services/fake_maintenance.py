from pathlib import Path

"""
Fake Maintenance Screens - Pantallas de Distracción
Windows Update / BIOS Error para ganar tiempo
"""

from typing import Any, Callable, Dict, Optional
from datetime import datetime
import logging
import os
import random
import sys
import threading
import time

logger = logging.getLogger(__name__)

class FakeMaintenanceScreen:
    """
    Pantallas de distracción que se activan con el pánico.
    
    Mientras el auditor espera, el sistema:
    - Desmonta RAMFS
    - Borra logs
    - Cifra datos
    
    Tipos de pantallas:
    - Windows Update (lento, creíble)
    - BIOS/SMART Error (más agresivo)
    - Disk Check (alternativa)
    """
    
    def __init__(self, on_background_complete: Callable = None):
        self.on_background_complete = on_background_complete
        self.is_active = False
        self.progress = 0
        self.screen_type = 'windows_update'
        self.secret_exit_code = "exit"
        self.keys_entered = ""
    
    def show_windows_update(self, background_task: Callable = None):
        """
        Muestra pantalla de Windows Update a pantalla completa.
        """
        self.screen_type = 'windows_update'
        self.is_active = True
        self.progress = 0
        
        # Iniciar tarea en background
        if background_task:
            thread = threading.Thread(target=background_task, daemon=True)
            thread.start()
        
        # Intentar mostrar con PyQt
        try:
            self._show_pyqt_update_screen()
        except ImportError:
            # Fallback a terminal
            self._show_terminal_update_screen()
    
    def show_bios_error(self, background_task: Callable = None):
        """
        Muestra pantalla de error BIOS/SMART.
        Más intimidante - el auditor no tocará la PC.
        """
        self.screen_type = 'bios_error'
        self.is_active = True
        
        # Iniciar tarea en background
        if background_task:
            thread = threading.Thread(target=background_task, daemon=True)
            thread.start()
        
        try:
            self._show_pyqt_bios_screen()
        except ImportError:
            self._show_terminal_bios_screen()
    
    def show_disk_check(self, background_task: Callable = None):
        """
        Muestra pantalla de CHKDSK / fsck.
        """
        self.screen_type = 'disk_check'
        self.is_active = True
        self.progress = 0
        
        if background_task:
            thread = threading.Thread(target=background_task, daemon=True)
            thread.start()
        
        try:
            self._show_pyqt_diskcheck_screen()
        except ImportError:
            self._show_terminal_diskcheck_screen()
    
    def _show_pyqt_update_screen(self):
        """Pantalla de Windows Update mejorada con círculo girando."""
        from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
        from PyQt6.QtGui import QColor, QFont, QPainter, QPen
        from PyQt6.QtWidgets import (
            QApplication,
            QGraphicsOpacityEffect,
            QLabel,
            QMainWindow,
            QVBoxLayout,
            QWidget,
        )
        
        app = QApplication.instance() or QApplication([])
        
        class SpinnerWidget(QWidget):
            """Círculo de bolitas girando estilo Windows 11."""
            def __init__(self):
                super().__init__()
                self.angle = 0
                self.setFixedSize(120, 120)
                
            def paintEvent(self, event):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                center_x, center_y = 60, 60
                radius = 40
                
                import math

                # 5 bolitas que van desapareciendo
                for i in range(5):
                    angle = math.radians(self.angle - i * 25)
                    x = center_x + radius * math.cos(angle)
                    y = center_y + radius * math.sin(angle)
                    
                    # Tamaño y opacidad decreciente
                    size = 12 - i * 2
                    opacity = 255 - i * 50
                    
                    painter.setBrush(QColor(255, 255, 255, opacity))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(int(x - size/2), int(y - size/2), size, size)
                
            def rotate(self):
                self.angle = (self.angle + 8) % 360
                self.update()
        
        class UpdateWindow(QMainWindow):
            def __init__(self, parent_screen):
                super().__init__()
                self.parent_screen = parent_screen
                # Nombres para parecer Windows Update real
                self.setObjectName("WindowsUpdate")
                self.setWindowTitle("Windows Update")
                # Cambiar el nombre del proceso visible
                try:
                    import ctypes
                    libc = ctypes.CDLL('libc.so.6')
                    libc.prctl(15, b'wuauclt.exe', 0, 0, 0)  # PR_SET_NAME
                except Exception:
                    pass  # Process name change is optional
                self.setWindowFlags(
                    Qt.WindowType.FramelessWindowHint |
                    Qt.WindowType.WindowStaysOnTopHint |
                    Qt.WindowType.X11BypassWindowManagerHint
                )
                self.showFullScreen()
                self.setCursor(Qt.CursorShape.BlankCursor)
                self._disable_alt_tab()  # Deshabilitar Alt+Tab del sistema
                self.setup_ui()
                self.grabKeyboard()
                self.grabMouse()
                
            def _disable_alt_tab(self):
                import subprocess

                # Intentar deshabilitar Alt+Tab en diferentes entornos
                try:
                    # GNOME
                    subprocess.run(['gsettings', 'set', 'org.gnome.desktop.wm.keybindings', 
                                   'switch-applications', '[]'], capture_output=True)
                    subprocess.run(['gsettings', 'set', 'org.gnome.desktop.wm.keybindings', 
                                   'switch-windows', '[]'], capture_output=True)
                except Exception:
                    pass  # GNOME not available
                try:
                    # Cinnamon
                    subprocess.run(['gsettings', 'set', 'org.cinnamon.desktop.keybindings.wm', 
                                   'switch-windows', '[]'], capture_output=True)
                except Exception:
                    pass  # Cinnamon not available
                
            def _restore_alt_tab(self):
                import subprocess
                try:
                    subprocess.run(['gsettings', 'reset', 'org.gnome.desktop.wm.keybindings', 
                                   'switch-applications'], capture_output=True)
                    subprocess.run(['gsettings', 'reset', 'org.gnome.desktop.wm.keybindings', 
                                   'switch-windows'], capture_output=True)
                except Exception:
                    pass  # GNOME restore optional
                try:
                    subprocess.run(['gsettings', 'reset', 'org.cinnamon.desktop.keybindings.wm', 
                                   'switch-windows'], capture_output=True)
                except Exception:
                    pass  # Cinnamon restore optional
                
            def closeEvent(self, event):
                # Solo cerrar si se escribió "exit"
                if self.parent_screen.secret_exit_code in self.parent_screen.keys_entered:
                    self._restore_alt_tab()  # Restaurar Alt+Tab
                    self.releaseKeyboard()
                    self.releaseMouse()
                    event.accept()
                else:
                    event.ignore()  # Bloquear Alt+F4
                
            def setup_ui(self):
                # Estilo Windows 11 Update (más oscuro)
                self.setStyleSheet("""
                    QMainWindow { background-color: #000000; }
                    QLabel { color: white; }
                """)
                
                central = QWidget()
                self.setCentralWidget(central)
                layout = QVBoxLayout(central)
                layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                
                layout.addStretch()
                
                # Spinner
                self.spinner = SpinnerWidget()
                layout.addWidget(self.spinner, alignment=Qt.AlignmentFlag.AlignCenter)
                
                layout.addSpacing(40)
                
                # Progreso
                self.progress_label = QLabel("0%")
                self.progress_label.setFont(QFont("Segoe UI", 48, QFont.Weight.Light))
                self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(self.progress_label)
                
                layout.addSpacing(20)
                
                # Mensaje principal
                self.message = QLabel("Trabajando en actualizaciones")
                self.message.setFont(QFont("Segoe UI", 18))
                self.message.setStyleSheet("color: rgba(255,255,255,0.8);")
                self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(self.message)
                
                layout.addSpacing(10)
                
                # Advertencia
                warning = QLabel("No apagues el equipo")
                warning.setFont(QFont("Segoe UI", 14))
                warning.setStyleSheet("color: rgba(255,255,255,0.5);")
                warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(warning)
                
                layout.addStretch()
                
                # Timer para spinner
                self.spin_timer = QTimer(self)
                self.spin_timer.timeout.connect(self.spinner.rotate)
                self.spin_timer.start(100)
                
                # Timer para progreso lento
                self.timer = QTimer(self)
                self.timer.timeout.connect(self._update_progress)
                self.timer.start(random.randint(3000, 6000))
                
                # Timer para mantener ventana al frente (anti Alt+Tab)
                self.focus_timer = QTimer(self)
                self.focus_timer.timeout.connect(self._force_focus)
                self.focus_timer.start(200)
                
            def _force_focus(self):
                self.raise_()
                self.activateWindow()
                self.showFullScreen()
                self.grabKeyboard()
                self.grabMouse()
                
            def _update_progress(self):
                if self.parent_screen.progress < 100:
                    increment = random.uniform(0.2, 1.0)
                    self.parent_screen.progress = min(99, self.parent_screen.progress + increment)
                    
                    self.progress_label.setText(f"{int(self.parent_screen.progress)}%")
                    
                    # Mensajes rotativos
                    messages = [
                        "Trabajando en actualizaciones",
                        "Instalando actualización 1 de 3",
                        "Instalando actualización 2 de 3",
                        "Configurando Windows",
                        "Preparando Windows",
                        "Esto puede tardar un momento",
                        "Tu PC se reiniciará varias veces",
                    ]
                    if random.random() > 0.85:
                        self.message.setText(random.choice(messages))
                    
                    self.timer.setInterval(random.randint(2000, 8000))
                    
            def keyPressEvent(self, event):
                # Solo aceptar letras (a-z) para escribir "exit"
                text = event.text().lower()
                if text.isalpha():
                    self.parent_screen.keys_entered += text
                    if self.parent_screen.secret_exit_code in self.parent_screen.keys_entered:
                        self.parent_screen.is_active = False
                        self.close()
                # Ignorar TODO lo demás (Alt, Ctrl, Tab, F4, etc.)
                event.accept()  # Consumir el evento
                    
        self.update_window = UpdateWindow(self)
        self.update_window.show()
        # NO llamar app.exec() - ya hay un event loop corriendo
    
    def _show_pyqt_bios_screen(self):
        """Pantalla de error BIOS/SMART con PyQt6."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QFont
        from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget
        
        app = QApplication.instance() or QApplication([])
        
        class BIOSWindow(QMainWindow):
            def __init__(self, parent_screen):
                super().__init__()
                self.parent_screen = parent_screen
                self.setWindowTitle("System BIOS")
                self.setWindowFlags(
                    Qt.WindowType.FramelessWindowHint |
                    Qt.WindowType.WindowStaysOnTopHint |
                    Qt.WindowType.X11BypassWindowManagerHint
                )
                self.showFullScreen()
                self.setCursor(Qt.CursorShape.BlankCursor)
                self.setup_ui()  # Configurar UI
                self.grabKeyboard()
                self.grabMouse()
                
            def closeEvent(self, event):
                if self.parent_screen.secret_exit_code in self.parent_screen.keys_entered:
                    self.releaseKeyboard()
                    self.releaseMouse()
                    event.accept()
                else:
                    event.ignore()
            
            def setup_ui(self):
                
                # Estilo BIOS (negro con texto blanco/gris)
                self.setStyleSheet("""
                    QMainWindow { background-color: #000000; }
                    QLabel { color: #AAAAAA; }
                """)
                
                central = QWidget()
                self.setCentralWidget(central)
                layout = QVBoxLayout(central)
                layout.setContentsMargins(50, 50, 50, 50)
                
                font_mono = QFont("Courier New", 14)
                
                # Header tipo BIOS
                header = QLabel("American Megatrends Inc. BIOS Setup Utility")
                header.setFont(font_mono)
                header.setStyleSheet("color: #00FFFF;")
                layout.addWidget(header)
                
                layout.addSpacing(20)
                
                # Línea separadora
                sep = QLabel("─" * 70)
                sep.setFont(font_mono)
                layout.addWidget(sep)
                
                layout.addSpacing(30)
                
                # Mensaje de error SMART
                error_title = QLabel("!! SMART Status Bad, Backup and Replace !!")
                error_title.setFont(QFont("Courier New", 16, QFont.Weight.Bold))
                error_title.setStyleSheet("color: #FF0000;")
                layout.addWidget(error_title)
                
                layout.addSpacing(20)
                
                errors = [
                    "SMART Hard Drive Detects Imminent Failure",
                    "",
                    "Error: 0171 - Disk Sector Read Failure",
                    "Error: 0250 - SSD Controller Failure Imminent",
                    "Error: 0301 - Hard Disk SMART Status: FAILING",
                    "",
                    f"Device: KINGSTON SA400S37240G  Serial: {random.randint(100000, 999999)}",
                    f"Firmware: SBFK71E0  Sectors: 468,862,128",
                    "",
                    "SMART Error Count: 2847",
                    "Reallocated Sector Count: 1589",
                    "Current Pending Sector: 847",
                    "Uncorrectable Sector Count: 215",
                    "",
                    "WARNING: Data on this drive may be corrupted or unrecoverable.",
                    "         Immediate backup is recommended before total failure.",
                ]
                
                for line in errors:
                    lbl = QLabel(line)
                    lbl.setFont(font_mono)
                    if "WARNING" in line or "Error" in line or "!!" in line:
                        lbl.setStyleSheet("color: #FFFF00;")
                    layout.addWidget(lbl)
                
                layout.addSpacing(30)
                
                # Instrucciones (que no funcionan excepto con código secreto)
                instructions = QLabel("Press F1 to Attempt Recovery or ESC to Exit Setup")
                instructions.setFont(font_mono)
                instructions.setStyleSheet("color: #00FF00;")
                layout.addWidget(instructions)
                
                # Blink cursor simulado
                self.cursor = QLabel("_")
                self.cursor.setFont(font_mono)
                self.cursor.setStyleSheet("color: #AAAAAA;")
                layout.addWidget(self.cursor)
                
                layout.addStretch()
                
                # Blink timer
                from PyQt6.QtCore import QTimer
                self.blink_timer = QTimer(self)
                self.blink_timer.timeout.connect(self._blink)
                self.blink_timer.start(500)
                self.blink_state = True
                
            def _blink(self):
                self.blink_state = not self.blink_state
                self.cursor.setText("_" if self.blink_state else " ")
                
            def keyPressEvent(self, event):
                # Solo aceptar letras (a-z)
                text = event.text().lower()
                if text.isalpha():
                    self.parent_screen.keys_entered += text
                    if self.parent_screen.secret_exit_code in self.parent_screen.keys_entered:
                        self.parent_screen.is_active = False
                        self.close()
                event.accept()
        
        self.bios_window = BIOSWindow(self)
        self.bios_window.show()
        # NO llamar app.exec() - ya hay un event loop corriendo
    
    def _show_pyqt_diskcheck_screen(self):
        """Pantalla de CHKDSK."""
        from PyQt6.QtCore import Qt, QTimer
        from PyQt6.QtGui import QFont
        from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget
        
        app = QApplication.instance() or QApplication([])
        
        class DiskCheckWindow(QMainWindow):
            def __init__(self, parent_screen):
                super().__init__()
                self.parent_screen = parent_screen
                self.stage = 1
                self.setWindowTitle("Disk Check")
                self.setWindowFlags(
                    Qt.WindowType.FramelessWindowHint |
                    Qt.WindowType.WindowStaysOnTopHint |
                    Qt.WindowType.X11BypassWindowManagerHint
                )
                self.showFullScreen()
                self.setCursor(Qt.CursorShape.BlankCursor)
                self.setup_ui()  # Configurar UI
                self.grabKeyboard()
                self.grabMouse()
                
            def closeEvent(self, event):
                if self.parent_screen.secret_exit_code in self.parent_screen.keys_entered:
                    self.releaseKeyboard()
                    self.releaseMouse()
                    event.accept()
                else:
                    event.ignore()
            
            def setup_ui(self):
                self.setStyleSheet("QMainWindow { background-color: #0C0C0C; }")
                
                central = QWidget()
                self.setCentralWidget(central)
                layout = QVBoxLayout(central)
                layout.setContentsMargins(30, 30, 30, 30)
                layout.setSpacing(2)
                
                font_mono = QFont("Courier New", 11)
                
                # Área de scroll de líneas
                from PyQt6.QtWidgets import QFrame, QScrollArea
                
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setFrameShape(QFrame.Shape.NoFrame)
                scroll.setStyleSheet("background: transparent; border: none;")
                
                self.content = QWidget()
                self.content_layout = QVBoxLayout(self.content)
                self.content_layout.setSpacing(1)
                self.content_layout.setContentsMargins(0, 0, 0, 0)
                
                scroll.setWidget(self.content)
                layout.addWidget(scroll)
                
                self.scroll = scroll
                self.font_mono = font_mono
                self.line_count = 0
                
                # Líneas iniciales
                self._add_line("[    0.000000] Linux version 6.5.0-titan-pos (gcc 12.3.0)", "#00FF00")
                self._add_line("[    0.000000] Command line: BOOT_IMAGE=/vmlinuz-6.5.0", "#AAAAAA")
                self._add_line("[    0.034521] ACPI: RSDP 0x00000000000F0490", "#AAAAAA")
                self._add_line("[    0.089234] Initializing cgroup subsys cpuset", "#AAAAAA")
                self._add_line("[    0.156789] KERNEL PANIC - FILESYSTEM CORRUPTION DETECTED", "#FF0000")
                self._add_line("", "#AAAAAA")
                self._add_line("fsck from util-linux 2.39.3", "#00FFFF")
                self._add_line("/dev/sda1: recovering journal", "#FFFF00")
                self._add_line("/dev/sda1: Clearing orphaned inode 2847593", "#FFFF00")
                
                # Timer rápido para efecto Matrix
                self.timer = QTimer(self)
                self.timer.timeout.connect(self._add_random_line)
                self.timer.start(150)  # Muy rápido
                
            def _add_line(self, text, color):
                label = QLabel(text)
                label.setFont(self.font_mono)
                label.setStyleSheet(f"color: {color}; background: transparent;")
                self.content_layout.addWidget(label)
                self.line_count += 1
                
                # Auto-scroll al final
                QTimer.singleShot(10, lambda: self.scroll.verticalScrollBar().setValue(
                    self.scroll.verticalScrollBar().maximum()
                ))
                
            def _add_random_line(self):
                import random
                
                lines_pool = [
                    ("[{:10.6f}] EXT4-fs error (device sda1): ext4_lookup: bad entry", "#FF6600"),
                    ("[{:10.6f}] Buffer I/O error on dev sda1, sector {}", "#FF0000"),
                    ("[{:10.6f}] JBD2: Error -5 detected when freeing journal", "#FF0000"),
                    ("[{:10.6f}] Attempting to recover orphaned data block {}", "#FFFF00"),
                    ("[{:10.6f}] Inode {} has imagic flag set", "#FFFF00"),
                    ("[{:10.6f}] e2fsck: Block bitmap differences: -{}", "#FF6600"),
                    ("[{:10.6f}] /dev/sda1: ***** FILE SYSTEM WAS MODIFIED *****", "#FF00FF"),
                    ("[{:10.6f}] Clearing inode {} ({} blocks)", "#AAAAAA"),
                    ("[{:10.6f}] Duplicate block {} found in inode {}", "#FF0000"),
                    ("[{:10.6f}] Entry '..' in ??? ({}) has bad inode", "#FF6600"),
                    ("[{:10.6f}] Unconnected directory inode {} (???)", "#FFFF00"),
                    ("Pass {}: Checking directory structure", "#00FFFF"),
                    ("Pass {}: Checking reference counts", "#00FFFF"),
                    ("{} inodes, {} blocks", "#AAAAAA"),
                    ("Free blocks count wrong ({}, counted={})", "#FF6600"),
                    ("[{:10.6f}] SCSI error: Bad sector at LBA {}", "#FF0000"),
                    ("[{:10.6f}] ata1.00: status: {{ DRDY ERR }}", "#FF0000"),
                    ("[{:10.6f}] ata1.00: error: {{ UNC }}", "#FF0000"),
                    ("[{:10.6f}] Reallocating bad sector to spare area", "#FFFF00"),
                    ("[{:10.6f}] SMART: Current Pending Sector Count: {}", "#FF6600"),
                ]
                
                template, color = random.choice(lines_pool)
                
                # Generar valores aleatorios
                timestamp = self.line_count * 0.003 + random.uniform(0, 0.01)
                rand_vals = [random.randint(1000, 9999999) for _ in range(5)]
                
                try:
                    text = template.format(timestamp, *rand_vals[:4])
                except Exception:
                    text = template
                
                self._add_line(text, color)
                
                # Limitar líneas (para no consumir memoria)
                if self.line_count > 500:
                    item = self.content_layout.takeAt(0)
                    if item and item.widget():
                        item.widget().deleteLater()
                    self.line_count -= 1
                
            def keyPressEvent(self, event):
                text = event.text().lower()
                if text.isalpha():
                    self.parent_screen.keys_entered += text
                    if self.parent_screen.secret_exit_code in self.parent_screen.keys_entered:
                        self.parent_screen.is_active = False
                        self.close()
                event.accept()
                
            def _update_progress(self):
                stages = [
                    "Examining basic file system structure",
                    "Examining file name linkage",
                    "Examining security descriptors",
                    "Verifying free space",
                    "Recovering orphaned files"
                ]
                
                increment = random.uniform(0.5, 2.0)
                self.parent_screen.progress += increment
                
                if self.parent_screen.progress >= 100 and self.stage < 5:
                    self.stage += 1
                    self.parent_screen.progress = 0
                
                self.stage_label.setText(f"Stage {self.stage} of 5: {stages[self.stage-1]}...")
                self.progress_label.setText(f"{int(self.parent_screen.progress)} percent completed.")
                
                files = random.randint(10000, 999999)
                self.detail_label.setText(f"{files} file records processed.")
                
                self.timer.setInterval(random.randint(2000, 6000))
                
            def keyPressEvent(self, event):
                self.parent_screen.keys_entered += event.text()
                if self.parent_screen.secret_exit_code in self.parent_screen.keys_entered:
                    self.parent_screen.is_active = False
                    self.close()
        
        self.diskcheck_window = DiskCheckWindow(self)
        self.diskcheck_window.show()
        # NO llamar app.exec() - ya hay un event loop corriendo
    
    def _show_terminal_update_screen(self):
        """Fallback de terminal para Windows Update."""
        os.system('clear')
        
        while self.is_active and self.progress < 99:
            self.progress += random.uniform(0.3, 1.0)
            
            print("\033[2J\033[H")  # Clear screen
            print("\n" * 10)
            print("     ⊞ Windows Update")
            print()
            print(f"     Actualizando Windows... {int(self.progress)}%")
            print()
            print("     No apague el equipo.")
            print()
            print("     [" + "█" * int(self.progress / 2) + "░" * (50 - int(self.progress / 2)) + "]")
            
            time.sleep(random.uniform(2, 5))
    
    def _show_terminal_bios_screen(self):
        """Fallback de terminal para BIOS error."""
        os.system('clear')
        
        print("\n" * 3)
        print("American Megatrends Inc. BIOS Setup Utility")
        print("═" * 60)
        print()
        print("\033[91m!! SMART Status Bad, Backup and Replace !!\033[0m")
        print()
        print("SMART Hard Drive Detects Imminent Failure")
        print()
        print("Error: 0171 - Disk Sector Read Failure")
        print("Error: 0250 - SSD Controller Failure Imminent")
        print()
        print(f"Device: KINGSTON SA400S37240G  Serial: {random.randint(100000, 999999)}")
        print()
        print("SMART Error Count: 2847")
        print("Reallocated Sector Count: 1589")
        print()
        print("\033[93mWARNING: Data may be corrupted or unrecoverable.\033[0m")
        print()
        print("\033[92mPress F1 to Attempt Recovery or ESC to Exit\033[0m")
        
        while self.is_active:
            time.sleep(1)
    
    def _show_terminal_diskcheck_screen(self):
        """Fallback de terminal para disk check."""
        os.system('clear')
        
        print("Checking file system on C:")
        print("The type of the file system is NTFS.")
        print()
        
        while self.is_active and self.progress < 99:
            stage = min(5, int(self.progress / 20) + 1)
            print(f"\rStage {stage} of 5: {int(self.progress)}% complete. "
                  f"{random.randint(10000, 99999)} file records processed.", end="")
            
            self.progress += random.uniform(0.5, 1.5)
            time.sleep(random.uniform(2, 5))
    
    def dismiss(self):
        """Cierra la pantalla de distracción."""
        self.is_active = False
        if self.on_background_complete:
            self.on_background_complete()

class PanicScreenManager:
    """
    Manager de pantallas de pánico.
    Integra con el sistema de protección real.
    """
    
    def __init__(self, core=None):
        self.core = core
        self.screen = FakeMaintenanceScreen()
        self.protection_complete = False
    
    def trigger_windows_update(self):
        """Activa Windows Update falso + protección real."""
        # SECURITY: No loguear activación de pantallas falsas
        pass
        self.screen.show_windows_update(self._run_protection)
    
    def trigger_bios_error(self):
        """Activa error BIOS/SMART + protección real."""
        # SECURITY: No loguear activación de pantallas falsas
        pass
        self.screen.show_bios_error(self._run_protection)
    
    def trigger_disk_check(self):
        """Activa CHKDSK + protección real."""
        # SECURITY: No loguear activación de pantallas falsas
        pass
        self.screen.show_disk_check(self._run_protection)
    
    def _run_protection(self):
        """Ejecuta protección real mientras se muestra la pantalla."""
        try:
            # 1. Desmontar RAMFS
            # SECURITY: No loguear desmontaje de RAMFS
            pass
            os.system('sudo umount -f /mnt/ramfs 2>/dev/null')
            
            # 2. Borrar logs sensibles
            # SECURITY: No loguear borrado de logs
            pass
            os.system('sudo shred -vfz /var/log/antigravity/* 2>/dev/null')
            
            # 3. Limpiar caché de BD
            if self.core:
                try:
                    self.core.db.execute_write("DELETE FROM session_cache")
                    self.core.db.execute_write("DELETE FROM activity_log WHERE timestamp > NOW() - INTERVAL '4 hours'")
                except Exception:
                    pass
            
            # 4. Forzar sync de filesystem
            os.system('sync')
            
            self.protection_complete = True
            # SECURITY: No loguear protección completada
            pass
            
        except Exception as e:
            logger.error(f"Error en protección: {e}")

# Funciones de conveniencia para Panic Button
def show_fake_update(core = None):
    """Wrapper para Windows Update falso."""
    manager = PanicScreenManager(core)
    manager.trigger_windows_update()

def show_bios_error(core=None):
    """Wrapper para error BIOS."""
    manager = PanicScreenManager(core)
    manager.trigger_bios_error()

def show_disk_check(core=None):
    """Wrapper para disk check."""
    manager = PanicScreenManager(core)
    manager.trigger_disk_check()
