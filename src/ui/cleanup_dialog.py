"""Dialog for scanning and cleaning orphaned HKCU library display preferences."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTreeWidget, QTreeWidgetItem, QMessageBox, QProgressBar,
)
from PySide6.QtCore import Qt, QThread, Signal
from src.manager import LibraryManager, LibraryManagerError
from src.registry import list_hkcu_display_entries, list_libraries as list_registry_libraries
from src.files import list_from_xml, list_from_json

_NOT_KONTAKT = {
    "kontakt 5", "kontakt 6", "kontakt 7", "kontakt 8",
    "kontakt factory library", "kontakt factory library 2",
    "battery 4", "massive", "massive x", "fm8",
    "guitar rig 5", "guitar rig 6", "guitar rig 7",
    "super 8", "super 8 r2",
    "native access", "service center", "service center 2",
    "shared", "alsupport", "reaktor", "reaktor 6", "absynth", "absynth 5",
}


class ScanWorker(QThread):
    finished = Signal(list)

    def run(self):
        # Step 1: collect ALL known library names from every source
        known = set()

        # Managed folders (user's own libraries)
        # (populated by the dialog from manager.libraries)

        # Registry (with ContentDir)
        reg_libs, _ = list_registry_libraries()
        known.update(reg_libs.keys())

        # XML
        xml_data, _ = list_from_xml()
        known.update(xml_data.keys())

        # JSON
        json_data, _ = list_from_json()
        known.update(json_data.keys())

        # Step 2: find HKCU display entries NOT in any known source
        hkcu = list_hkcu_display_entries()
        orphans = []
        for name in hkcu:
            nl = name.lower()
            if nl in _NOT_KONTAKT:
                continue
            skip = False
            for kw in ["arturia", "waves", "uadx", "uad ", "izotope", "ozone",
                       "pianoteq", "modartt", "vinyl", "ambient"]:
                if kw in nl:
                    skip = True
                    break
            if skip:
                continue
            if nl not in known:
                orphans.append(name)

        self.finished.emit(orphans)


class CleanupDialog(QDialog):
    def __init__(self, manager: LibraryManager, parent=None):
        super().__init__(parent)
        self._manager = manager
        self.setWindowTitle("扫描残留")
        self.setMinimumSize(520, 400)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hint = QLabel("扫描 HKCU 注册表中已删除库的显示偏好残留。\n"
                      "这些条目在硬盘上已不存在，但在 Kontakt 显示列表中仍有痕迹。")
        hint.setStyleSheet("color: #999; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        top = QHBoxLayout()
        self._scan_btn = QPushButton("开始扫描")
        self._scan_btn.clicked.connect(self._on_scan)
        top.addWidget(self._scan_btn)
        top.addStretch()
        layout.addLayout(top)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["       ", "库名称", "来源"])
        self._tree.setColumnWidth(0, 50)
        self._tree.setColumnWidth(1, 300)
        self._tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._tree, 1)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._stats = QLabel("")
        self._stats.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._stats)

        bottom = QHBoxLayout()
        bottom.addStretch()
        select_all = QPushButton("全选")
        select_all.clicked.connect(lambda: self._set_all(Qt.Checked))
        bottom.addWidget(select_all)
        deselect_all = QPushButton("取消全选")
        deselect_all.clicked.connect(lambda: self._set_all(Qt.Unchecked))
        bottom.addWidget(deselect_all)
        cancel_btn = QPushButton("关闭")
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(cancel_btn)
        self._delete_btn = QPushButton("删除选中")
        self._delete_btn.clicked.connect(self._on_delete)
        self._delete_btn.setEnabled(False)
        bottom.addWidget(self._delete_btn)
        layout.addLayout(bottom)

    def _on_item_clicked(self, item, col):
        if col == 0:
            ns = Qt.Unchecked if item.checkState(0) == Qt.Checked else Qt.Checked
            item.setCheckState(0, ns)
            self._update_delete_btn()

    def _set_all(self, state):
        for i in range(self._tree.topLevelItemCount()):
            self._tree.topLevelItem(i).setCheckState(0, state)
        self._update_delete_btn()

    def _update_delete_btn(self):
        count = sum(1 for i in range(self._tree.topLevelItemCount())
                    if self._tree.topLevelItem(i).checkState(0) == Qt.Checked)
        self._delete_btn.setEnabled(count > 0)
        self._delete_btn.setText(f"删除选中 ({count})")

    def _on_scan(self):
        self._scan_btn.setEnabled(False)
        self._tree.clear()
        self._stats.setText("扫描中...")

        # Pass user's managed library names to the worker
        self._worker = ScanWorker()
        self._worker.finished.connect(self._on_scan_done)
        self._worker.start()

    def _on_scan_done(self, orphans):
        self._tree.clear()

        # Also add managed library names to known set (in dialog, after scan returns)
        managed = set(lib.name.lower() for lib in self._manager.libraries)

        # Filter orphans: only show those not in managed list
        shown = 0
        for name in orphans:
            if name.lower() in managed:
                continue
            item = QTreeWidgetItem(["", name, "HKCU (硬盘已删除)"])
            item.setCheckState(0, Qt.Checked)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            self._tree.addTopLevelItem(item)
            shown += 1

        self._stats.setText(f"发现 {shown} 个残留（硬盘已删除，注册表/显示偏好还在）")
        self._scan_btn.setEnabled(True)
        self._update_delete_btn()

    def _on_delete(self):
        entries = []
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item.checkState(0) == Qt.Checked:
                entries.append(item.text(1))

        if not entries:
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"将删除 {len(entries)} 个库的 HKCU 显示偏好。\n"
            "这不会删除磁盘上的音色文件。\n\n确定？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._progress.setVisible(True)
        self._progress.setMaximum(len(entries))
        self._progress.setValue(0)

        import winreg
        success = 0
        fail = 0
        for idx, name in enumerate(entries):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                                 f"Software\\Native Instruments\\{name}")
                success += 1
            except OSError:
                fail += 1
            self._progress.setValue(idx + 1)

        self._stats.setText(f"删除完成：成功 {success} 个，失败 {fail} 个")
        self._progress.setVisible(False)
        self._update_delete_btn()

        if success > 0:
            self.accept()
