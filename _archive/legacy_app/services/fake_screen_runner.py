#!/usr/bin/env python3
"""
Script independiente para mostrar pantallas falsas.
Se ejecuta en un proceso separado para no afectar al POS principal.
"""

import os
import sys

# Agregar path del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    if len(sys.argv) < 2:
        print("Uso: python fake_screen_runner.py [windows_update|bios_error|disk_check]")
        sys.exit(1)
    
    screen_type = sys.argv[1]
    
    from PyQt6 import QtCore, QtWidgets
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QColor, QFont, QPainter
    
    app = QtWidgets.QApplication(sys.argv)
    
    secret_code = "exit"
    keys_entered = ""
    
    if screen_type == "windows_update":
        # Pantalla de Windows Update
        import math
        import random
        
        class SpinnerWidget(QtWidgets.QWidget):
            def __init__(self):
                super().__init__()
                self.angle = 0
                self.setFixedSize(120, 120)
                
            def paintEvent(self, event):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                center_x, center_y = 60, 60
                radius = 40
                for i in range(5):
                    angle = math.radians(self.angle - i * 25)
                    x = center_x + radius * math.cos(angle)
                    y = center_y + radius * math.sin(angle)
                    size = 12 - i * 2
                    opacity = 255 - i * 50
                    painter.setBrush(QColor(255, 255, 255, opacity))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(int(x - size/2), int(y - size/2), size, size)
                    
            def rotate(self):
                self.angle = (self.angle + 8) % 360
                self.update()
        
        class UpdateWindow(QtWidgets.QMainWindow):
            def __init__(self):
                super().__init__()
                self.keys = ""
                self.progress = 0
                
                self.setWindowTitle("Windows Update")
                self.setWindowFlags(
                    Qt.WindowType.FramelessWindowHint |
                    Qt.WindowType.WindowStaysOnTopHint
                )
                self.showFullScreen()
                self.setCursor(Qt.CursorShape.BlankCursor)
                self.setStyleSheet("QMainWindow { background-color: #000000; } QLabel { color: white; }")
                
                central = QtWidgets.QWidget()
                self.setCentralWidget(central)
                layout = QtWidgets.QVBoxLayout(central)
                layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                
                layout.addStretch()
                
                self.spinner = SpinnerWidget()
                layout.addWidget(self.spinner, alignment=Qt.AlignmentFlag.AlignCenter)
                
                layout.addSpacing(40)
                
                self.progress_label = QtWidgets.QLabel("0%")
                self.progress_label.setFont(QFont("Segoe UI", 48, QFont.Weight.Light))
                self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(self.progress_label)
                
                self.message = QtWidgets.QLabel("Trabajando en actualizaciones")
                self.message.setFont(QFont("Segoe UI", 18))
                self.message.setStyleSheet("color: rgba(255,255,255,0.8);")
                self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(self.message)
                
                self.submessage = QtWidgets.QLabel("No apagues el equipo")
                self.submessage.setFont(QFont("Segoe UI", 12))
                self.submessage.setStyleSheet("color: rgba(255,255,255,0.5);")
                self.submessage.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(self.submessage)
                
                layout.addStretch()
                
                # Timers
                self.spin_timer = QTimer(self)
                self.spin_timer.timeout.connect(self.spinner.rotate)
                self.spin_timer.start(100)
                
                self.progress_timer = QTimer(self)
                self.progress_timer.timeout.connect(self._update_progress)
                self.progress_timer.start(random.randint(3000, 6000))
                
                self.grabKeyboard()
                
            def _update_progress(self):
                import random
                if self.progress < 99:
                    self.progress = min(99, self.progress + random.uniform(0.2, 1.0))
                    self.progress_label.setText(f"{int(self.progress)}%")
                    
                    messages = [
                        "Trabajando en actualizaciones",
                        "Instalando actualización 1 de 3",
                        "Instalando actualización 2 de 3", 
                        "Configurando Windows",
                        "Preparando Windows",
                        "Esto puede tardar un momento",
                    ]
                    if random.random() > 0.85:
                        self.message.setText(random.choice(messages))
                    
                    self.progress_timer.setInterval(random.randint(2000, 8000))
                    
            def keyPressEvent(self, event):
                text = event.text().lower()
                if text.isalpha():
                    self.keys += text
                    if "exit" in self.keys:
                        self.close()
                        app.quit()
                event.accept()
                
            def closeEvent(self, event):
                self.releaseKeyboard()
                event.accept()
        
        window = UpdateWindow()
        window.show()
        
    elif screen_type == "bios_error":
        # Pantalla de error BIOS
        import random
        
        class BIOSWindow(QtWidgets.QMainWindow):
            def __init__(self):
                super().__init__()
                self.keys = ""
                
                self.setWindowTitle("System BIOS")
                self.setWindowFlags(
                    Qt.WindowType.FramelessWindowHint |
                    Qt.WindowType.WindowStaysOnTopHint
                )
                self.showFullScreen()
                self.setCursor(Qt.CursorShape.BlankCursor)
                self.setStyleSheet("QMainWindow { background-color: #000080; } QLabel { color: white; font-family: 'Courier New', monospace; }")
                
                central = QtWidgets.QWidget()
                self.setCentralWidget(central)
                layout = QtWidgets.QVBoxLayout(central)
                layout.setContentsMargins(50, 50, 50, 50)
                
                header = QtWidgets.QLabel("American Megatrends Inc. BIOS Setup Utility")
                header.setFont(QFont("Courier New", 14))
                layout.addWidget(header)
                
                layout.addSpacing(20)
                
                error1 = QtWidgets.QLabel("!! SMART Status Bad, Backup and Replace !!")
                error1.setStyleSheet("color: #FF0000; font-weight: bold;")
                error1.setFont(QFont("Courier New", 16))
                layout.addWidget(error1)
                
                layout.addSpacing(10)
                
                details = [
                    "SMART Hard Drive Detects Imminent Failure",
                    "",
                    f"Error: 0171 - Disk Sector Read Failure",
                    f"Error: 0250 - SSD Controller Failure Imminent",
                    "",
                    f"Device: KINGSTON SA400S37240G  Serial: {random.randint(100000, 999999)}",
                    "",
                    f"SMART Error Count: {random.randint(2000, 3000)}",
                    f"Reallocated Sector Count: {random.randint(1000, 2000)}",
                ]
                
                for line in details:
                    lbl = QtWidgets.QLabel(line)
                    lbl.setFont(QFont("Courier New", 12))
                    layout.addWidget(lbl)
                
                layout.addSpacing(20)
                
                warning = QtWidgets.QLabel("WARNING: Data may be corrupted or unrecoverable.")
                warning.setStyleSheet("color: #FFFF00;")
                warning.setFont(QFont("Courier New", 12))
                layout.addWidget(warning)
                
                layout.addStretch()
                
                footer = QtWidgets.QLabel("Press F1 to Attempt Recovery or ESC to Exit")
                footer.setStyleSheet("color: #00FF00;")
                footer.setFont(QFont("Courier New", 12))
                layout.addWidget(footer)
                
                self.grabKeyboard()
                
            def keyPressEvent(self, event):
                text = event.text().lower()
                if text.isalpha():
                    self.keys += text
                    if "exit" in self.keys:
                        self.close()
                        app.quit()
                event.accept()
                
            def closeEvent(self, event):
                self.releaseKeyboard()
                event.accept()
        
        window = BIOSWindow()
        window.show()
        
    else:  # disk_check
        import random
        
        class DiskCheckWindow(QtWidgets.QMainWindow):
            def __init__(self):
                super().__init__()
                self.keys = ""
                self.stage = 1
                
                self.setWindowTitle("Disk Check")
                self.setWindowFlags(
                    Qt.WindowType.FramelessWindowHint |
                    Qt.WindowType.WindowStaysOnTopHint
                )
                self.showFullScreen()
                self.setCursor(Qt.CursorShape.BlankCursor)
                self.setStyleSheet("QMainWindow { background-color: #000000; } QLabel { color: white; font-family: 'Courier New'; }")
                
                central = QtWidgets.QWidget()
                self.setCentralWidget(central)
                layout = QtWidgets.QVBoxLayout(central)
                layout.setContentsMargins(50, 50, 50, 50)
                
                header = QtWidgets.QLabel("Checking file system on C:")
                header.setFont(QFont("Courier New", 14))
                layout.addWidget(header)
                
                self.type_label = QtWidgets.QLabel("The type of the file system is NTFS.")
                self.type_label.setFont(QFont("Courier New", 12))
                layout.addWidget(self.type_label)
                
                layout.addSpacing(20)
                
                self.stage_label = QtWidgets.QLabel("Stage 1 of 5: Examining basic file system structure...")
                self.stage_label.setFont(QFont("Courier New", 12))
                layout.addWidget(self.stage_label)
                
                self.progress_label = QtWidgets.QLabel("0 percent complete.")
                self.progress_label.setFont(QFont("Courier New", 12))
                layout.addWidget(self.progress_label)
                
                layout.addStretch()
                
                self.progress = 0
                self.timer = QTimer(self)
                self.timer.timeout.connect(self._update)
                self.timer.start(random.randint(500, 2000))
                
                self.grabKeyboard()
                
            def _update(self):
                import random
                self.progress += random.randint(1, 3)
                if self.progress >= 100:
                    self.stage += 1
                    self.progress = 0
                    if self.stage > 5:
                        self.stage = 5
                        self.progress = 99
                
                stages = [
                    "Examining basic file system structure",
                    "Examining file name linkage",
                    "Examining security descriptors",
                    "Looking for bad clusters",
                    "Verifying free space"
                ]
                
                self.stage_label.setText(f"Stage {self.stage} of 5: {stages[self.stage-1]}...")
                self.progress_label.setText(f"{self.progress} percent complete. ({random.randint(1000, 99999)} file records processed)")
                self.timer.setInterval(random.randint(500, 2000))
                
            def keyPressEvent(self, event):
                text = event.text().lower()
                if text.isalpha():
                    self.keys += text
                    if "exit" in self.keys:
                        self.close()
                        app.quit()
                event.accept()
                
            def closeEvent(self, event):
                self.releaseKeyboard()
                event.accept()
        
        window = DiskCheckWindow()
        window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
