"""Dialog for managing library root folders and custom libraries."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QMessageBox, QLabel, QFileDialog, QTabWidget, QWidget, QLineEdit,
)
from PySide6.QtCore import Qt
from src.manager import LibraryManager, LibraryManagerError


class FolderDialog(QDialog):
    def __init__(self, manager: LibraryManager, parent=None):
        super().__init__(parent)
        self._manager = manager
        self.setWindowTitle("管理库文件夹")
        self.setMinimumSize(520, 400)
        self.setModal(True)
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        tabs = QTabWidget()

        # Tab 1: Standard library roots
        standard_tab = QWidget()
        standard_layout = QVBoxLayout(standard_tab)
        standard_layout.setContentsMargins(0, 8, 0, 0)
        standard_layout.setSpacing(8)

        hint1 = QLabel("标准库文件夹：子文件夹中带 .nicnt 文件的将被识别为音色库。")
        hint1.setStyleSheet("color: #999; font-size: 11px;")
        hint1.setWordWrap(True)
        standard_layout.addWidget(hint1)

        self._standard_list = QListWidget()
        standard_layout.addWidget(self._standard_list)

        std_btn_layout = QHBoxLayout()
        add_std_btn = QPushButton("+ 添加标准库文件夹")
        add_std_btn.clicked.connect(lambda: self._add_root("standard"))
        std_btn_layout.addWidget(add_std_btn)
        del_std_btn = QPushButton("- 删除选中")
        del_std_btn.clicked.connect(lambda: self._remove_root("standard"))
        std_btn_layout.addWidget(del_std_btn)
        std_btn_layout.addStretch()
        standard_layout.addLayout(std_btn_layout)

        tabs.addTab(standard_tab, "标准库")

        # Tab 2: Non-standard library roots
        ns_tab = QWidget()
        ns_layout = QVBoxLayout(ns_tab)
        ns_layout.setContentsMargins(0, 8, 0, 0)
        ns_layout.setSpacing(8)

        hint2 = QLabel("非标准库文件夹：一级子文件夹将被识别为音色库（无需 .nicnt）。")
        hint2.setStyleSheet("color: #999; font-size: 11px;")
        hint2.setWordWrap(True)
        ns_layout.addWidget(hint2)

        self._nonstandard_list = QListWidget()
        ns_layout.addWidget(self._nonstandard_list)

        ns_btn_layout = QHBoxLayout()
        add_ns_btn = QPushButton("+ 添加非标准库文件夹")
        add_ns_btn.clicked.connect(lambda: self._add_root("nonstandard"))
        ns_btn_layout.addWidget(add_ns_btn)
        del_ns_btn = QPushButton("- 删除选中")
        del_ns_btn.clicked.connect(lambda: self._remove_root("nonstandard"))
        ns_btn_layout.addWidget(del_ns_btn)
        ns_btn_layout.addStretch()
        ns_layout.addLayout(ns_btn_layout)

        tabs.addTab(ns_tab, "非标准库")

        # Tab 3: Individual custom libraries
        custom_tab = QWidget()
        custom_layout = QVBoxLayout(custom_tab)
        custom_layout.setContentsMargins(0, 8, 0, 0)
        custom_layout.setSpacing(8)

        hint3 = QLabel("手动添加单个音色库文件夹（任意位置）。")
        hint3.setStyleSheet("color: #999; font-size: 11px;")
        hint3.setWordWrap(True)
        custom_layout.addWidget(hint3)

        add_single_layout = QHBoxLayout()
        self._custom_name = QLineEdit()
        self._custom_name.setPlaceholderText("库名称（可选，留空自动用文件夹名）")
        add_single_layout.addWidget(self._custom_name)
        add_custom_btn = QPushButton("添加单个库...")
        add_custom_btn.clicked.connect(self._add_single)
        add_single_layout.addWidget(add_custom_btn)
        custom_layout.addLayout(add_single_layout)

        self._custom_list = QListWidget()
        custom_layout.addWidget(self._custom_list)

        del_custom_btn_layout = QHBoxLayout()
        del_custom_btn = QPushButton("- 删除选中")
        del_custom_btn.clicked.connect(self._remove_custom)
        del_custom_btn_layout.addWidget(del_custom_btn)
        del_custom_btn_layout.addStretch()
        custom_layout.addLayout(del_custom_btn_layout)

        tabs.addTab(custom_tab, "独立库")

        layout.addWidget(tabs)

        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        close_layout.addWidget(close_btn)
        layout.addLayout(close_layout)

    def _refresh(self):
        self._standard_list.clear()
        self._nonstandard_list.clear()
        self._custom_list.clear()

        for root in self._manager.list_roots():
            path = root.get("path", "")
            rtype = root.get("type", "standard")
            item = QListWidgetItem(path)
            item.setData(Qt.UserRole, path)
            if rtype == "standard":
                self._standard_list.addItem(item)
            else:
                self._nonstandard_list.addItem(item)

        for c in self._manager.list_custom_libraries():
            name = c.get("name", "")
            path = c.get("path", "")
            item = QListWidgetItem(f"{name}  ({path})")
            item.setData(Qt.UserRole, path)
            self._custom_list.addItem(item)

    def _add_root(self, root_type: str):
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择标准库文件夹" if root_type == "standard" else "选择非标准库文件夹",
        )
        if not folder:
            return
        try:
            self._manager.add_root(folder, root_type)
        except LibraryManagerError as e:
            QMessageBox.warning(self, "错误", str(e))
            return
        self._refresh()

    def _remove_root(self, root_type: str):
        lst = self._standard_list if root_type == "standard" else self._nonstandard_list
        item = lst.currentItem()
        if item is None:
            QMessageBox.information(self, "提示", "请先选择一个文件夹。")
            return
        path = item.data(Qt.UserRole)
        self._manager.remove_root(path)
        self._refresh()

    def _add_single(self):
        folder = QFileDialog.getExistingDirectory(self, "选择音色库文件夹")
        if not folder:
            return
        name = self._custom_name.text().strip()
        try:
            self._manager.add_custom_library(name, folder)
        except LibraryManagerError as e:
            QMessageBox.warning(self, "错误", str(e))
            return
        self._custom_name.clear()
        self._refresh()

    def _remove_custom(self):
        item = self._custom_list.currentItem()
        if item is None:
            QMessageBox.information(self, "提示", "请先选择一个库。")
            return
        path = item.data(Qt.UserRole)
        self._manager.remove_custom_library(path)
        self._refresh()
