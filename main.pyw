"""Kontakt 音色库管理器 - 入口文件

Windows 桌面应用，管理 Kontakt 8 音色库（BobDule 版本）。
以管理员身份运行（通过 UAC 清单）。
"""

import sys
import os
from pathlib import Path


def main():
    project_root = Path(__file__).resolve().parent
    os.chdir(str(project_root))

    from PySide6.QtWidgets import QApplication
    from src.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Kontakt Library Manager")
    app.setOrganizationName("KontaktTools")
    app.setStyleSheet(DARK_STYLESHEET)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


DARK_STYLESHEET = """
QMainWindow {
    background-color: #1e1e1e;
}
QWidget {
    background-color: #1e1e1e;
    color: #ffffff;
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 12px;
}

/* Toolbar buttons */
QPushButton {
    background-color: #3a3a3a;
    color: #ddd;
    border: none;
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #4a4a4a;
}
QPushButton:pressed {
    background-color: #555;
}
QPushButton:disabled {
    background-color: #2a2a2a;
    color: #666;
}

/* Table */
QTableWidget {
    background-color: #1e1e1e;
    alternate-background-color: #222;
    border: 1px solid #3a3a3a;
    gridline-color: #333;
    selection-background-color: #3d3d3d;
    selection-color: #ffffff;
}
QTableWidget::item {
    padding: 4px 8px;
    border-bottom: 1px solid #2a2a2a;
}
QHeaderView::section {
    background-color: #2d2d2d;
    color: #aaa;
    border: none;
    border-bottom: 1px solid #3a3a3a;
    border-right: 1px solid #3a3a3a;
    padding: 5px 8px;
    font-weight: bold;
    font-size: 11px;
}

/* List widgets (category sidebar) */
QListWidget {
    background-color: #252525;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    outline: none;
}
QListWidget::item {
    color: #ccc;
    padding: 6px 10px;
    border-radius: 3px;
}
QListWidget::item:hover {
    background-color: #353535;
}
QListWidget::item:selected {
    background-color: #3d3d3d;
    color: #fff;
}

/* Tree widget (patch list) */
QTreeWidget {
    background-color: #1e1e1e;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    alternate-background-color: #222;
}
QTreeWidget::item {
    padding: 2px 4px;
    color: #ccc;
}
QTreeWidget::item:hover {
    background-color: #353535;
}
QTreeWidget::item:selected {
    background-color: #3d3d3d;
    color: #fff;
}
QTreeWidget::branch {
    background-color: #1e1e1e;
}

/* Text inputs */
QLineEdit {
    background-color: #2d2d2d;
    color: #fff;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 6px 10px;
    selection-background-color: #555;
}
QLineEdit:focus {
    border-color: #777;
}

/* Text edit (notes) */
QTextEdit {
    background-color: #2d2d2d;
    color: #ccc;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 6px;
    selection-background-color: #555;
}
QTextEdit:focus {
    border-color: #666;
}

/* Labels */
QLabel {
    background-color: transparent;
    color: #ccc;
}

/* Scrollbars */
QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 10px;
    border: none;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #555;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background-color: #777;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background-color: #1e1e1e;
    height: 10px;
    border: none;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background-color: #555;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #777;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* Splitter */
QSplitter::handle {
    background-color: #3a3a3a;
    width: 2px;
}

/* Status bar */
QStatusBar {
    background-color: #007acc;
    color: #fff;
    border: none;
    font-size: 11px;
    padding: 2px 8px;
}

/* Dialogs */
QDialog {
    background-color: #1e1e1e;
}

/* Menu */
QMenu {
    background-color: #2d2d2d;
    color: #ccc;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 4px;
}
QMenu::item {
    padding: 5px 24px;
    border-radius: 3px;
}
QMenu::item:selected {
    background-color: #3d3d3d;
}
QMenu::separator {
    height: 1px;
    background-color: #3a3a3a;
    margin: 4px 8px;
}

/* Tooltips */
QToolTip {
    background-color: #2d2d2d;
    color: #ddd;
    border: 1px solid #555;
    border-radius: 3px;
    padding: 4px 8px;
    font-size: 11px;
}

/* Message boxes */
QMessageBox {
    background-color: #1e1e1e;
}
QMessageBox QLabel {
    color: #ccc;
}
"""


if __name__ == "__main__":
    main()
