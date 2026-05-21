"""Dialog for managing library folders (standard and non-standard)."""

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QMessageBox, QLabel, QFileDialog, QGroupBox,
)
from PySide6.QtCore import Qt
from src.manager import LibraryManager, LibraryManagerError
from src.scanner import _dir_has_kontakt_content


class FolderDialog(QDialog):
    def __init__(self, manager: LibraryManager, parent=None):
        super().__init__(parent)
        self._manager = manager
        self.setWindowTitle("管理库文件夹")
        self.setMinimumSize(550, 450)
        self.setModal(True)
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Standard folders group
        std_group = QGroupBox("标准库目录（含 .nicnt 的 Kontakt 库）")
        std_layout = QVBoxLayout(std_group)

        std_hint = QLabel("添加包含 Kontakt 音色库的目录，程序会自动扫描其中的已注册库。")
        std_hint.setStyleSheet("color: #888; font-size: 11px;")
        std_hint.setWordWrap(True)
        std_layout.addWidget(std_hint)

        self._std_list = QListWidget()
        std_layout.addWidget(self._std_list)

        std_btn_layout = QHBoxLayout()
        add_std_btn = QPushButton("+ 添加")
        add_std_btn.clicked.connect(self._add_standard_folder)
        std_btn_layout.addWidget(add_std_btn)
        del_std_btn = QPushButton("- 移除")
        del_std_btn.clicked.connect(self._remove_standard_folder)
        std_btn_layout.addWidget(del_std_btn)
        std_btn_layout.addStretch()
        std_layout.addLayout(std_btn_layout)

        layout.addWidget(std_group)

        # Non-standard folders group
        nonstd_group = QGroupBox("非标准库目录（无 .nicnt 的第三方采样库）")
        nonstd_layout = QVBoxLayout(nonstd_group)

        nonstd_hint = QLabel("添加包含第三方采样库的目录，程序会自动扫描其中的子文件夹作为非标准库。")
        nonstd_hint.setStyleSheet("color: #888; font-size: 11px;")
        nonstd_hint.setWordWrap(True)
        nonstd_layout.addWidget(nonstd_hint)

        self._nonstd_list = QListWidget()
        nonstd_layout.addWidget(self._nonstd_list)

        nonstd_btn_layout = QHBoxLayout()
        add_nonstd_btn = QPushButton("+ 添加")
        add_nonstd_btn.clicked.connect(self._add_nonstandard_folder)
        nonstd_btn_layout.addWidget(add_nonstd_btn)
        del_nonstd_btn = QPushButton("- 移除")
        del_nonstd_btn.clicked.connect(self._remove_nonstandard_folder)
        nonstd_btn_layout.addWidget(del_nonstd_btn)
        nonstd_btn_layout.addStretch()
        nonstd_layout.addLayout(nonstd_btn_layout)

        layout.addWidget(nonstd_group)

        # Close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        close_layout.addWidget(close_btn)
        layout.addLayout(close_layout)

    def _refresh(self):
        # Standard folders
        self._std_list.clear()
        for path in self._manager.list_folders():
            item = QListWidgetItem(path)
            item.setData(Qt.UserRole, path)
            self._std_list.addItem(item)

        # Non-standard folders
        self._nonstd_list.clear()
        for path in self._manager.list_nonstandard_folders():
            item = QListWidgetItem(path)
            item.setData(Qt.UserRole, path)
            self._nonstd_list.addItem(item)

    def _add_standard_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择标准库目录")
        if not folder:
            return

        # Scan for unregistered libraries
        unregistered = []
        folder_path = Path(folder)
        if folder_path.is_dir():
            registered_dirs = set()
            for lib in self._manager.libraries:
                if lib.content_dir:
                    try:
                        registered_dirs.add(str(Path(lib.content_dir).resolve()).lower())
                    except Exception:
                        pass

            for subfolder in folder_path.iterdir():
                if subfolder.is_dir() and _dir_has_kontakt_content(subfolder):
                    try:
                        if str(subfolder.resolve()).lower() not in registered_dirs:
                            unregistered.append(subfolder.name)
                    except Exception:
                        pass

        # Add the folder first
        try:
            self._manager.add_folder(folder)
        except LibraryManagerError as e:
            QMessageBox.warning(self, "错误", str(e))
            return

        # Ask if user wants to register unregistered libraries
        if unregistered:
            msg = f"发现 {len(unregistered)} 个未入库的音色库：\n\n"
            msg += "\n".join(f"• {name}" for name in unregistered[:10])
            if len(unregistered) > 10:
                msg += f"\n... 等 {len(unregistered)} 个"
            msg += "\n\n是否全部入库？"

            reply = QMessageBox.question(
                self, "发现未入库的音色库", msg,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                self._batch_add(folder, unregistered)

        self._refresh()

    def _batch_add(self, folder: str, names: list[str]):
        """Batch add libraries from the folder."""
        folder_path = Path(folder)
        success = 0
        failed = []

        for name in names:
            subfolder = folder_path / name
            if subfolder.is_dir():
                try:
                    self._manager.add_library(name, str(subfolder))
                    success += 1
                except LibraryManagerError as e:
                    failed.append(f"{name}: {e}")

        if success:
            self._manager.refresh()

        if failed:
            QMessageBox.warning(
                self, "入库结果",
                f"成功 {success} 个，失败 {len(failed)} 个。\n\n" + "\n".join(failed[:5])
            )
        elif success:
            QMessageBox.information(self, "入库完成", f"成功入库 {success} 个音色库。")

    def _remove_standard_folder(self):
        item = self._std_list.currentItem()
        if item is None:
            QMessageBox.information(self, "提示", "请先选择一个目录。")
            return

        path = item.data(Qt.UserRole)

        # Count registered libraries in this folder
        registered_count = 0
        registered_names = []
        folder_path = Path(path)
        for lib in self._manager.libraries:
            if lib.content_dir:
                try:
                    lib_dir = Path(lib.content_dir)
                    if lib_dir.parent.resolve() == folder_path.resolve():
                        if lib.found_in_registry or lib.found_in_xml or lib.found_in_json:
                            registered_count += 1
                            registered_names.append(lib.name)
                except Exception:
                    pass

        # Ask user
        msg = f"确定要移除目录吗？\n\n{path}"
        if registered_count > 0:
            msg += f"\n\n该目录中有 {registered_count} 个已入库的音色库。"
            msg += "\n\n是否同时从 Kontakt 中移除？"

            reply = QMessageBox.question(
                self, "移除目录", msg,
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Cancel
            )

            if reply == QMessageBox.Cancel:
                return

            # Remove from Kontakt first
            if reply == QMessageBox.Yes:
                for name in registered_names:
                    try:
                        self._manager.remove_library(name)
                    except LibraryManagerError:
                        pass
        else:
            reply = QMessageBox.question(
                self, "移除目录", msg,
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Yes
            )
            if reply != QMessageBox.Yes:
                return

        self._manager.remove_folder(path)
        self._manager.refresh()
        self._refresh()

    def _add_nonstandard_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择非标准库目录")
        if not folder:
            return
        try:
            self._manager.add_nonstandard_folder(folder)
        except LibraryManagerError as e:
            QMessageBox.warning(self, "错误", str(e))
            return
        self._refresh()

    def _remove_nonstandard_folder(self):
        item = self._nonstd_list.currentItem()
        if item is None:
            QMessageBox.information(self, "提示", "请先选择一个目录。")
            return

        path = item.data(Qt.UserRole)

        reply = QMessageBox.question(
            self, "移除目录",
            f"确定要移除非标准库目录吗？\n\n{path}\n\n这只会从软件中隐藏这些库，不会删除文件。",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Yes
        )

        if reply != QMessageBox.Yes:
            return

        self._manager.remove_nonstandard_folder(path)
        self._refresh()
