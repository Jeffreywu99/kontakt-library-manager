"""Dialog for scanning and cleaning orphaned Kontakt library registrations."""

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTreeWidget, QTreeWidgetItem, QMessageBox, QProgressBar,
)
from PySide6.QtCore import Qt, QThread, Signal
from src.manager import LibraryManager, LibraryManagerError
from src.registry import list_libraries as list_registry_libraries
from src.registry import list_hkcu_display_entries
from src.files import list_from_xml, list_from_json
from src.scanner import _dir_has_kontakt_content

_NOT_KONTAKT = {
    "kontakt 5", "kontakt 6", "kontakt 7", "kontakt 8",
    "kontakt factory library", "kontakt factory library 2",
    "battery 4", "massive", "massive x", "fm8",
    "guitar rig 5", "guitar rig 6", "guitar rig 7",
    "super 8", "super 8 r2",
    "native access", "service center", "service center 2",
    "shared", "alsupport", "reaktor", "reaktor 6", "absynth", "absynth 5",
}


def _is_kontakt_library(name: str, content_dir: str) -> bool:
    name_lower = name.lower()
    if name_lower in _NOT_KONTAKT:
        return False
    for kw in ["arturia", "waves", "uadx", "uad ", "izotope", "ozone",
               "pianoteq", "modartt", "vinyl", "ambient"]:
        if kw in name_lower:
            return False
    if not content_dir:
        return False
    p = Path(content_dir)
    if p.is_dir():
        return _dir_has_kontakt_content(p)
    return True


class ScanWorker(QThread):
    finished = Signal(list)

    def run(self):
        results = []
        seen = set()

        # 1. Registry (entries WITH ContentDir)
        reg_libs, _ = list_registry_libraries()
        for name, content_dir in reg_libs.items():
            if name not in seen and _is_kontakt_library(name, content_dir):
                results.append({"name": name, "content_dir": content_dir, "source": "注册表", "has_files": True})
                seen.add(name)

        # 2. XML
        xml_data, _ = list_from_xml()
        for name, data in xml_data.items():
            if name not in seen:
                cd = data.get("content_dir", "")
                if _is_kontakt_library(name, cd):
                    results.append({"name": name, "content_dir": cd, "source": "Service Center", "has_files": True})
                    seen.add(name)

        # 3. JSON
        json_data, _ = list_from_json()
        for name, data in json_data.items():
            if name not in seen:
                cd = data.get("content_dir", "")
                if _is_kontakt_library(name, cd):
                    results.append({"name": name, "content_dir": cd, "source": "installed_products", "has_files": True})
                    seen.add(name)

        # 4. HKCU display entries (UserListIndex only, no ContentDir — these are UI prefs for deleted libs)
        name_lower = {n.lower() for n in seen}
        hkcu_entries = list_hkcu_display_entries()
        for name in hkcu_entries:
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
            if nl not in name_lower:
                results.append({"name": name, "content_dir": "", "source": "HKCU(显示偏好)", "has_files": False})
                seen.add(name)

        self.finished.emit(results)


class CleanupDialog(QDialog):
    def __init__(self, manager: LibraryManager, parent=None):
        super().__init__(parent)
        self._manager = manager
        self._scan_results: list[dict] = []
        self.setWindowTitle("扫描残留")
        self.setMinimumSize(600, 440)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        hint = QLabel("扫描所有注册位置，找出你已删除但注册信息还在的 Kontakt 音色库残留。\n"
                      "（硬盘不存在的 + HKCU 残留的都会列出来）")
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
        self._tree.setHeaderLabels(["", "库名称", "路径 / 状态", "来源"])
        self._tree.setColumnWidth(0, 36)
        self._tree.setColumnWidth(1, 220)
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
        self._worker = ScanWorker()
        self._worker.finished.connect(self._on_scan_done)
        self._worker.start()

    def _on_scan_done(self, all_results):
        self._tree.clear()
        managed_names = set(lib.name.lower() for lib in self._manager.libraries)

        # Separate into two groups
        orphans = []    # registered but not in managed list
        stale_hkcu = [] # HKCU display prefs for deleted libs

        for r in all_results:
            name = r["name"]
            if name.lower() in managed_names:
                continue  # skip - user already has this in their managed list
            if not r["has_files"]:
                stale_hkcu.append(r)
            else:
                orphans.append(r)

        for r in orphans:
            item = QTreeWidgetItem(["", r["name"], r["content_dir"], r["source"]])
            item.setCheckState(0, Qt.Checked)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            self._tree.addTopLevelItem(item)

        for r in stale_hkcu:
            item = QTreeWidgetItem(["", r["name"], "(硬盘已删除)", r["source"]])
            item.setCheckState(0, Qt.Checked)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            self._tree.addTopLevelItem(item)

        total = len(orphans) + len(stale_hkcu)
        self._stats.setText(
            f"找到 {len(orphans)} 个未管理库 + {len(stale_hkcu)} 个 HKCU 残留，共 {total} 个")
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
