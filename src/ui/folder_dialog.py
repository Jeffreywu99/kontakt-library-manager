"""Dialog for managing library folders."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QMessageBox, QLabel, QFileDialog,
)
from PySide6.QtCore import Qt
from src.manager import LibraryManager, LibraryManagerError


class FolderDialog(QDialog):
    def __init__(self, manager: LibraryManager, parent=None):
        super().__init__(parent)
        self._manager = manager
        self.setWindowTitle("管理库文件夹")
        self.setMinimumSize(500, 350)
        self.setModal(True)
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hint = QLabel("库文件夹：入库时会自动添加父目录到此列表。\n这些文件夹用于批量入库时扫描子文件夹。")
        hint.setStyleSheet("color: #999; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._folder_list = QListWidget()
        layout.addWidget(self._folder_list)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("+ 添加文件夹")
        add_btn.clicked.connect(self._add_folder)
        btn_layout.addWidget(add_btn)
        del_btn = QPushButton("- 删除选中")
        del_btn.clicked.connect(self._remove_folder)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        close_layout.addWidget(close_btn)
        layout.addLayout(close_layout)

    def _refresh(self):
        self._folder_list.clear()
        for path in self._manager.list_folders():
            item = QListWidgetItem(path)
            item.setData(Qt.UserRole, path)
            self._folder_list.addItem(item)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择库文件夹")
        if not folder:
            return
        try:
            self._manager.add_folder(folder)
        except LibraryManagerError as e:
            QMessageBox.warning(self, "错误", str(e))
            return
        self._refresh()

    def _remove_folder(self):
        item = self._folder_list.currentItem()
        if item is None:
            QMessageBox.information(self, "提示", "请先选择一个文件夹。")
            return
        path = item.data(Qt.UserRole)
        self._manager.remove_folder(path)
        self._refresh()
