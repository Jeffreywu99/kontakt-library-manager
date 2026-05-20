"""Dialog for scanning and cleaning orphaned Kontakt library registrations."""

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTreeWidget, QTreeWidgetItem, QMessageBox, QProgressBar,
)
from PySide6.QtCore import Qt, QThread, Signal
from src.manager import LibraryManager, LibraryManagerError
from src.registry import list_libraries as list_registry_libraries
from src.files import list_from_xml, list_from_json
from src.scanner import _dir_has_kontakt_content

# Known non-Kontakt app names to exclude
_NOT_KONTAKT = {
    "kontakt 5", "kontakt 6", "kontakt 7", "kontakt 8",
    "kontakt factory library", "kontakt factory library 2",
    "battery 4", "massive", "massive x", "fm8",
    "guitar rig 5", "guitar rig 6", "guitar rig 7",
    "super 8", "super 8 r2",
    "native access", "service center", "service center 2",
    "shared", "alsupport", "reaktor", "reaktor 6",
    "absynth", "absynth 5", "sample modeling",
}


def _is_kontakt_library(name: str, content_dir: str) -> bool:
    """Check if an entry is actually a Kontakt library (not a plugin/app)."""
    name_lower = name.lower()
    # Filter out known non-Kontakt apps
    if name_lower in _NOT_KONTAKT:
        return False
    # Filter NKS preset packs (Arturia, Waves, UAD, etc.)
    arturia_kw = ["arturia", "waves", "uad", "izotope", "ozone", "insight",
                  "pianoteq", "modartt", "vinyl", "ambient"]
    for kw in arturia_kw:
        if kw in name_lower:
            return False
    if not content_dir:
        return False
    p = Path(content_dir)
    if p.is_dir():
        return _dir_has_kontakt_content(p)
    # If dir doesn't exist, trust the XML/JSON registration
    return True


class ScanWorker(QThread):
    """Scan all Kontakt registration sources in background."""
    finished = Signal(list)  # list of {name, content_dir, source_type}

    def run(self):
        results = []
        seen = set()

        # 1. Registry
        reg_libs, _ = list_registry_libraries()
        for name, content_dir in reg_libs.items():
            if name not in seen and _is_kontakt_library(name, content_dir):
                results.append({"name": name, "content_dir": content_dir, "source": "注册表"})
                seen.add(name)

        # 2. XML
        xml_data, _ = list_from_xml()
        for name, data in xml_data.items():
            if name not in seen:
                cd = data.get("content_dir", "")
                if _is_kontakt_library(name, cd):
                    results.append({"name": name, "content_dir": cd, "source": "Service Center"})
                    seen.add(name)

        # 3. JSON
        json_data, _ = list_from_json()
        for name, data in json_data.items():
            if name not in seen:
                cd = data.get("content_dir", "")
                if _is_kontakt_library(name, cd):
                    results.append({"name": name, "content_dir": cd, "source": "installed_products"})
                    seen.add(name)

        self.finished.emit(results)


class CleanupDialog(QDialog):
    def __init__(self, manager: LibraryManager, parent=None):
        super().__init__(parent)
        self._manager = manager
        self._scan_results: list[dict] = []
        self.setWindowTitle("扫描残留")
        self.setMinimumSize(560, 420)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hint = QLabel("扫描所有注册位置（注册表 + Service Center + installed_products），\n"
                      "找出不在当前管理列表中的 Kontakt 音色库残留。")
        hint.setStyleSheet("color: #999; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        btn_layout = QHBoxLayout()
        self._scan_btn = QPushButton("开始扫描")
        self._scan_btn.clicked.connect(self._on_scan)
        btn_layout.addWidget(self._scan_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["", "库名称", "路径", "来源"])
        self._tree.setColumnWidth(0, 30)
        self._tree.setColumnWidth(1, 200)
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
        self._delete_btn.setDefault(True)
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
        self._worker = ScanWorker()
        self._worker.finished.connect(self._on_scan_done)
        self._worker.start()

    def _on_scan_done(self, results):
        self._scan_results = results
        self._tree.clear()

        # Which libraries are in the user's managed list?
        managed_names = set(lib.name.lower() for lib in self._manager.libraries)

        orphan_count = 0
        for r in results:
            name = r["name"]
            is_orphan = name.lower() not in managed_names
            if is_orphan:
                item = QTreeWidgetItem(["", name, r["content_dir"], r["source"]])
                item.setCheckState(0, Qt.Checked)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                self._tree.addTopLevelItem(item)
                orphan_count += 1

        total = len(results)
        self._stats.setText(f"共找到 {total} 个 Kontakt 库，{orphan_count} 个不在管理列表中")
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
            f"将删除 {len(entries)} 个库的注册信息（注册表 + XML + JSON），\n"
            "不会删除磁盘上的音色文件。\n\n确定？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._progress.setVisible(True)
        self._progress.setMaximum(len(entries))
        self._progress.setValue(0)

        success = 0
        fail = 0
        for idx, name in enumerate(entries):
            try:
                self._manager.remove_library(name)
                success += 1
            except LibraryManagerError:
                fail += 1
            self._progress.setValue(idx + 1)

        self._stats.setText(f"删除完成：成功 {success} 个，失败 {fail} 个")
        self._progress.setVisible(False)
        self._update_delete_btn()

        if success > 0:
            self.accept()
