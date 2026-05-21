"""Dialog for batch-adding Kontakt libraries from a root folder."""

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QMessageBox, QProgressBar,
)
from PySide6.QtCore import Qt, QThread, Signal
from src.manager import LibraryManager, LibraryManagerError
from src.scanner import _dir_has_kontakt_content


class ScanWorker(QThread):
    """Background thread to scan a root folder for Kontakt libraries."""
    found = Signal(list)  # list of (name, path, has_content, is_registered)

    def __init__(self, root_path: str, manager: LibraryManager):
        super().__init__()
        self.root_path = root_path
        self._manager = manager
        self.setObjectName("ScanWorker")

    def run(self):
        results = []
        root = Path(self.root_path)
        if not root.is_dir():
            self.found.emit(results)
            return

        # Get all registered library paths for comparison
        registered_dirs = set()
        for lib in self._manager.libraries:
            if lib.content_dir:
                try:
                    registered_dirs.add(str(Path(lib.content_dir).resolve()).lower())
                except Exception:
                    pass

        for subfolder in sorted(root.iterdir()):
            if subfolder.is_dir():
                has_nicnt = _dir_has_kontakt_content(subfolder)
                is_registered = False
                if has_nicnt:
                    try:
                        is_registered = str(subfolder.resolve()).lower() in registered_dirs
                    except Exception:
                        pass
                results.append((subfolder.name, str(subfolder), has_nicnt, is_registered))
        self.found.emit(results)


class BatchAddDialog(QDialog):
    def __init__(self, manager: LibraryManager, parent=None):
        super().__init__(parent)
        self._manager = manager
        self.setWindowTitle("批量入库")
        self.setMinimumSize(640, 480)
        self.resize(720, 540)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Top: folder selection
        hint = QLabel("选择一个根文件夹，其子文件夹将被扫描并注册为音色库。")
        hint.setStyleSheet("color: #999; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        top = QHBoxLayout()
        self._path_label = QLabel("未选择文件夹")
        self._path_label.setStyleSheet("color: #666; font-size: 12px;")
        top.addWidget(self._path_label, 1)
        browse_btn = QPushButton("选择文件夹...")
        browse_btn.clicked.connect(self._on_browse)
        top.addWidget(browse_btn)
        layout.addLayout(top)

        self._scan_btn = QPushButton("扫描子文件夹")
        self._scan_btn.clicked.connect(self._on_scan)
        self._scan_btn.setEnabled(False)
        layout.addWidget(self._scan_btn)

        # Tree: checkable library list
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["", "库名称", "路径"])
        self._tree.setColumnWidth(0, 40)
        self._tree.setColumnWidth(1, 220)
        self._tree.header().setStretchLastSection(True)
        self._tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._tree, 1)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # Stats label
        self._stats = QLabel("")
        self._stats.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._stats)

        # Bottom: action buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        select_all = QPushButton("全选")
        select_all.clicked.connect(lambda: self._set_all(Qt.Checked))
        btn_layout.addWidget(select_all)

        deselect_all = QPushButton("取消全选")
        deselect_all.clicked.connect(lambda: self._set_all(Qt.Unchecked))
        btn_layout.addWidget(deselect_all)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self._confirm_btn = QPushButton("确认入库")
        self._confirm_btn.setDefault(True)
        self._confirm_btn.clicked.connect(self._on_confirm)
        self._confirm_btn.setEnabled(False)
        btn_layout.addWidget(self._confirm_btn)

        layout.addLayout(btn_layout)

    def _on_item_changed(self, item, col):
        if col == 0:
            self._update_count()

    def _set_all(self, state):
        self._tree.blockSignals(True)
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            item.setCheckState(0, state)
        self._tree.blockSignals(False)
        self._update_count()

    def _update_count(self):
        checked = 0
        total = 0
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            # Skip separator rows (disabled items)
            if not (item.flags() & Qt.ItemIsEnabled):
                continue
            total += 1
            if item.checkState(0) == Qt.Checked:
                checked += 1
        self._stats.setText(f"已选 {checked} / {total} 个库")
        self._confirm_btn.setEnabled(checked > 0)

    def _on_browse(self):
        folder = QFileDialog.getExistingDirectory(self, "选择根文件夹")
        if folder:
            self._path_label.setText(folder)
            self._scan_btn.setEnabled(True)

    def _on_scan(self):
        root = self._path_label.text()
        self._scan_btn.setEnabled(False)
        self._tree.clear()
        self._stats.setText("扫描中...")

        self._worker = ScanWorker(root, self._manager)
        self._worker.found.connect(self._on_scan_done)
        self._worker.start()

    def _on_scan_done(self, results):
        self._tree.clear()
        self._tree.blockSignals(True)

        new_libs = []  # Not registered yet
        registered_libs = []  # Already registered
        skipped_no_content = 0

        for name, path, has_content, is_registered in results:
            if has_content:
                if is_registered:
                    registered_libs.append((name, path))
                else:
                    new_libs.append((name, path))
            else:
                skipped_no_content += 1

        # Add new libraries first (checked by default)
        for name, path in new_libs:
            item = QTreeWidgetItem(["", name, path])
            item.setCheckState(0, Qt.Checked)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            self._tree.addTopLevelItem(item)

        # Add separator if both types exist
        if new_libs and registered_libs:
            separator = QTreeWidgetItem(["", "--- 已入库 ---", ""])
            separator.setFlags(separator.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsEnabled)
            separator.setForeground(1, Qt.gray)
            self._tree.addTopLevelItem(separator)

        # Add registered libraries (unchecked by default)
        for name, path in registered_libs:
            item = QTreeWidgetItem(["✓", name, path])
            item.setCheckState(0, Qt.Unchecked)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setForeground(1, Qt.gray)
            self._tree.addTopLevelItem(item)

        self._tree.blockSignals(False)

        # Build stats message
        msg_parts = []
        if new_libs:
            msg_parts.append(f"{len(new_libs)} 个新库")
        if registered_libs:
            msg_parts.append(f"{len(registered_libs)} 个已入库")
        if skipped_no_content:
            msg_parts.append(f"{skipped_no_content} 个无 Kontakt 文件")

        if msg_parts:
            self._stats.setText("找到 " + "、".join(msg_parts))
        else:
            self._stats.setText("未找到有效的音色库")

        self._update_count()
        self._scan_btn.setEnabled(True)

    def _on_confirm(self):
        entries: list[tuple[str, str]] = []
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item.checkState(0) == Qt.Checked:
                entries.append((item.text(1), item.text(2)))

        if not entries:
            return

        self._progress.setVisible(True)
        self._progress.setMaximum(len(entries))
        self._progress.setValue(0)
        self._confirm_btn.setEnabled(False)

        success = 0
        fail = 0
        for idx, (name, path) in enumerate(entries):
            try:
                self._manager.add_library(name, path)
                success += 1
            except LibraryManagerError as e:
                fail += 1
                # Show the error in the tree
                for j in range(self._tree.topLevelItemCount()):
                    item = self._tree.topLevelItem(j)
                    if item.text(1) == name:
                        item.setText(0, "✗")
                        item.setToolTip(2, str(e))
                        break
            self._progress.setValue(idx + 1)

        msg = f"成功 {success} 个"
        if fail:
            msg += f"，失败 {fail} 个"
        self._stats.setText(msg)

        if fail == 0:
            QMessageBox.information(self, "批量入库完成", f"成功注册 {success} 个音色库。")
            self.accept()
        else:
            self._confirm_btn.setEnabled(True)
            self._progress.setVisible(False)
            QMessageBox.warning(self, "批量入库完成",
                f"成功 {success} 个，失败 {fail} 个。\n失败项已标注 ✗，可取消勾选后重试。")
