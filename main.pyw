"""Kontakt 音色库管理器 - 入口文件

Windows 桌面应用，管理 Kontakt 8 音色库（BobDule 版本）。
"""

import sys
import os
import ctypes
from pathlib import Path

# Set working directory first
project_root = Path(__file__).resolve().parent
os.chdir(str(project_root))


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_as_admin():
    """Re-run the script with admin privileges."""
    if sys.executable.endswith("pythonw.exe"):
        # Use pythonw.exe for no console
        exe = sys.executable
    else:
        # Try to find pythonw.exe
        exe = sys.executable.replace("python.exe", "pythonw.exe")
        if not Path(exe).exists():
            exe = sys.executable

    script = str(Path(__file__).resolve())
    params = f'"{script}"'

    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, params, str(project_root), 1
        )
    except Exception:
        pass
    sys.exit(0)


def main():
    # Check for admin privileges
    if not is_admin():
        run_as_admin()
        return

    # Import Qt modules after setting working directory
    from PySide6.QtWidgets import QApplication, QSplashScreen
    from PySide6.QtGui import QPixmap, QColor, QPainter, QFont
    from PySide6.QtCore import Qt

    # Create app immediately
    app = QApplication(sys.argv)
    app.setApplicationName("Kontakt Library Manager")
    app.setOrganizationName("KontaktTools")

    # Set style before showing anything
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLESHEET)

    # Show splash screen with dark background
    splash = QSplashScreen()
    splash.setFixedSize(400, 180)
    splash.setStyleSheet("background-color: #1e1e1e;")
    splash.show()
    splash.showMessage("加载中...", Qt.AlignBottom | Qt.AlignHCenter, QColor("#666666"))
    app.processEvents()

    # Import and create window
    from src.ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    splash.finish(window)

    sys.exit(app.exec())


DARK_STYLESHEET = """
/* Global */
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #cccccc;
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 12px;
}

/* Buttons */
QPushButton {
    background-color: #2d2d30;
    color: #cccccc;
    border: 1px solid #3e3e42;
    border-radius: 3px;
    padding: 5px 12px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #3e3e42;
    border-color: #4e4e52;
}
QPushButton:pressed {
    background-color: #4e4e52;
}
QPushButton:disabled {
    background-color: #252526;
    color: #5a5a5a;
}

/* Table */
QTableWidget {
    background-color: #1e1e1e;
    alternate-background-color: #252526;
    border: none;
    gridline-color: transparent;
    selection-background-color: #094771;
    selection-color: #ffffff;
    outline: none;
}
QTableWidget::item {
    padding: 4px 10px;
    border-bottom: 1px solid #2d2d30;
}
QTableWidget::item:hover {
    background-color: #2a2d2e;
}
QHeaderView::section {
    background-color: #252526;
    color: #bbbbbb;
    border: none;
    border-bottom: 1px solid #3e3e42;
    padding: 6px 10px;
    font-weight: normal;
    font-size: 11px;
}

/* List widgets */
QListWidget {
    background-color: #252526;
    border: none;
    outline: none;
}
QListWidget::item {
    color: #cccccc;
    padding: 6px 12px;
    border-radius: 2px;
    margin: 1px 4px;
}
QListWidget::item:hover {
    background-color: #2a2d2e;
}
QListWidget::item:selected {
    background-color: #094771;
    color: #ffffff;
}

/* Tree widget */
QTreeWidget {
    background-color: #1e1e1e;
    border: 1px solid #3e3e42;
    border-radius: 2px;
    outline: none;
}
QTreeWidget::item {
    padding: 3px 6px;
    color: #cccccc;
}
QTreeWidget::item:hover {
    background-color: #2a2d2e;
}
QTreeWidget::item:selected {
    background-color: #094771;
    color: #ffffff;
}
QTreeWidget::branch {
    background-color: transparent;
}

/* Text inputs */
QLineEdit {
    background-color: #3c3c3c;
    color: #cccccc;
    border: 1px solid #3e3e42;
    border-radius: 2px;
    padding: 5px 8px;
    selection-background-color: #264f78;
}
QLineEdit:hover {
    border-color: #4e4e52;
}
QLineEdit:focus {
    border-color: #0078d4;
}

QTextEdit {
    background-color: #3c3c3c;
    color: #cccccc;
    border: 1px solid #3e3e42;
    border-radius: 2px;
    padding: 6px;
    selection-background-color: #264f78;
}
QTextEdit:focus {
    border-color: #0078d4;
}

/* Labels */
QLabel {
    background-color: transparent;
    color: #9d9d9d;
}

/* Scrollbars */
QScrollBar:vertical {
    background-color: transparent;
    width: 10px;
}
QScrollBar::handle:vertical {
    background-color: #424242;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background-color: #4f4f4f;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background-color: transparent;
    height: 10px;
}
QScrollBar::handle:horizontal {
    background-color: #424242;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #4f4f4f;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* Splitter */
QSplitter::handle {
    background-color: #3e3e42;
}

/* Status bar */
QStatusBar {
    background-color: #252526;
    color: #888888;
    border-top: 1px solid #3e3e42;
    font-size: 11px;
    padding: 4px 12px;
    min-height: 24px;
}

/* Dialogs */
QDialog {
    background-color: #1e1e1e;
}

/* GroupBox */
QGroupBox {
    color: #cccccc;
    border: 1px solid #3e3e42;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #aaaaaa;
}

/* Menu */
QMenu {
    background-color: #252526;
    color: #cccccc;
    border: 1px solid #454545;
    padding: 4px 0;
}
QMenu::item {
    padding: 6px 24px;
}
QMenu::item:selected {
    background-color: #094771;
}
QMenu::separator {
    height: 1px;
    background-color: #3e3e42;
    margin: 4px 0;
}

/* Tooltips */
QToolTip {
    background-color: #252526;
    color: #cccccc;
    border: 1px solid #454545;
    padding: 4px 8px;
    font-size: 11px;
}

/* Message boxes */
QMessageBox {
    background-color: #1e1e1e;
}
QMessageBox QLabel {
    color: #cccccc;
}

/* Progress bar */
QProgressBar {
    background-color: #3c3c3c;
    border: none;
    border-radius: 2px;
    text-align: center;
    min-height: 4px;
    max-height: 4px;
}
QProgressBar::chunk {
    background-color: #0078d4;
    border-radius: 2px;
}
"""


if __name__ == "__main__":
    main()
