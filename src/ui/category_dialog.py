"""Dialog for managing library categories."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QMessageBox, QLabel,
)
from PySide6.QtCore import Qt
from src.manager import LibraryManager


class CategoryDialog(QDialog):
    def __init__(self, manager: LibraryManager, parent=None):
        super().__init__(parent)
        self._manager = manager
        self.setWindowTitle("管理分类")
        self.setMinimumWidth(400)
        self.setModal(True)
        self._setup_ui()
        self._refresh_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("管理分类")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)

        add_layout = QHBoxLayout()
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("输入新分类名称")
        self._name_edit.returnPressed.connect(self._on_add)
        add_layout.addWidget(self._name_edit)

        add_btn = QPushButton("+ 添加")
        add_btn.clicked.connect(self._on_add)
        add_layout.addWidget(add_btn)

        layout.addLayout(add_layout)

        self._list = QListWidget()
        layout.addWidget(self._list)

        btn_layout = QHBoxLayout()
        rename_btn = QPushButton("重命名")
        rename_btn.clicked.connect(self._on_rename)
        btn_layout.addWidget(rename_btn)

        delete_btn = QPushButton("删除")
        delete_btn.clicked.connect(self._on_delete)
        btn_layout.addWidget(delete_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _refresh_list(self):
        self._list.clear()
        cats = self._manager.list_categories()
        for cat in cats:
            item = QListWidgetItem(f"{cat['name']}  ({cat.get('count', 0)} 个库)")
            item.setData(Qt.UserRole, cat["name"])
            self._list.addItem(item)

    def _on_add(self):
        name = self._name_edit.text().strip()
        if not name:
            return
        try:
            self._manager.add_category(name)
        except Exception as e:
            QMessageBox.warning(self, "错误", str(e))
            return
        self._name_edit.clear()
        self._refresh_list()

    def _on_delete(self):
        item = self._list.currentItem()
        if item is None:
            QMessageBox.information(self, "提示", "请先选择一个分类。")
            return
        name = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"将删除分类 '{name}'，其中的库将变为未分类。\n确定删除？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._manager.remove_category(name)
            self._refresh_list()

    def _on_rename(self):
        item = self._list.currentItem()
        if item is None:
            QMessageBox.information(self, "提示", "请先选择一个分类。")
            return
        old_name = item.data(Qt.UserRole)
        new_name = self._name_edit.text().strip()
        if not new_name:
            QMessageBox.warning(self, "输入不完整", "请在输入框中输入新名称。")
            return
        try:
            self._manager.rename_category(old_name, new_name)
        except Exception as e:
            QMessageBox.warning(self, "错误", str(e))
            return
        self._name_edit.clear()
        self._refresh_list()
