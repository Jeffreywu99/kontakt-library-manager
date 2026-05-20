"""MainWindow: primary application window.

Left: category/type panel | Center: library table | Right: patch details + notes + source info
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QPushButton, QListWidget, QListWidgetItem,
    QStatusBar, QLabel, QMessageBox, QHeaderView, QTreeWidget, QTreeWidgetItem,
    QTextEdit, QMenu, QAbstractItemView, QScrollArea, QFrame, QCheckBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from src.manager import LibraryManager, LibraryManagerError
from src.models import LibraryEntry, PatchEntry
from src.storage import get_patch_notes
from src.ui.add_dialog import AddLibraryDialog
from src.ui.category_dialog import CategoryDialog
from src.ui.folder_dialog import FolderDialog
from src.ui.batch_add_dialog import BatchAddDialog

TYPE_LABELS = {"standard": "标准", "nonstandard": "非标准", "registry": "注册"}
TYPE_LABELS_FULL = {"standard": "标准库", "nonstandard": "非标准库", "registry": "注册库"}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._manager = LibraryManager()
        self._current_patches: list[PatchEntry] = []
        self._current_patch_path: str = ""
        self._selection_timer = QTimer()
        self._selection_timer.setSingleShot(True)
        self._selection_timer.setInterval(50)
        self._selection_timer.timeout.connect(self._on_library_selected_debounced)
        self._notes_timer = QTimer()
        self._notes_timer.setSingleShot(True)
        self._notes_timer.setInterval(300)
        self._notes_timer.timeout.connect(self._on_notes_save)
        self._setup_window()
        self._setup_ui()
        self._setup_status()
        QTimer.singleShot(0, self._on_initial_load)

    def _setup_window(self):
        self.setWindowTitle("Kontakt 音色库管理器")
        self.setMinimumSize(1100, 650)
        self.resize(1300, 750)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        toolbar = QHBoxLayout()
        self._add_btn = QPushButton("+ 添加音色库")
        self._add_btn.clicked.connect(self._on_add)
        toolbar.addWidget(self._add_btn)

        self._batch_add_btn = QPushButton("批量入库")
        self._batch_add_btn.clicked.connect(self._on_batch_add)
        toolbar.addWidget(self._batch_add_btn)

        self._remove_btn = QPushButton("- 移除音色库")
        self._remove_btn.clicked.connect(self._on_remove)
        toolbar.addWidget(self._remove_btn)

        self._batch_remove_btn = QPushButton("批量移除")
        self._batch_remove_btn.clicked.connect(self._on_batch_remove)
        toolbar.addWidget(self._batch_remove_btn)

        self._category_btn = QPushButton("管理分类")
        self._category_btn.clicked.connect(self._on_manage_categories)
        toolbar.addWidget(self._category_btn)

        self._folder_btn = QPushButton("管理库文件夹")
        self._folder_btn.clicked.connect(self._on_manage_folders)
        toolbar.addWidget(self._folder_btn)

        self._refresh_btn = QPushButton("刷新")
        self._refresh_btn.setToolTip("重新扫描所有库文件夹")
        self._refresh_btn.clicked.connect(self._on_refresh)
        toolbar.addWidget(self._refresh_btn)

        toolbar.addStretch()

        self._show_hidden_cb = QCheckBox("显示已隐藏")
        self._show_hidden_cb.stateChanged.connect(self._refresh_table)
        toolbar.addWidget(self._show_hidden_cb)

        main_layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal)

        # Left: Category panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        cat_label = QLabel("分类")
        cat_label.setStyleSheet("color: #888; font-size: 10px; padding: 4px 8px;")
        left_layout.addWidget(cat_label)
        self._category_list = QListWidget()
        self._category_list.currentRowChanged.connect(self._on_category_changed)
        left_layout.addWidget(self._category_list)
        splitter.addWidget(left_panel)

        # Center: Library table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["名称", "路径", "存在", "类型", "分类"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_table_context_menu)
        self._table.selectionModel().selectionChanged.connect(self._on_library_selected)
        header = self._table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.resizeSection(2, 40)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.resizeSection(3, 60)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.resizeSection(4, 70)
        self._table.verticalHeader().setDefaultSectionSize(28)
        splitter.addWidget(self._table)

        # Right: Detail panel
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(6)

        info_label = QLabel("音色库信息")
        info_label.setStyleSheet("color: #888; font-size: 10px; padding: 4px 0;")
        right_layout.addWidget(info_label)
        self._patch_info = QLabel("选择一个库以查看详情")
        self._patch_info.setStyleSheet("color: #666; font-size: 12px; padding: 8px;")
        self._patch_info.setWordWrap(True)
        right_layout.addWidget(self._patch_info)

        source_label = QLabel("注册来源")
        source_label.setStyleSheet("color: #888; font-size: 10px;")
        right_layout.addWidget(source_label)
        self._source_info = QLabel("")
        self._source_info.setStyleSheet("color: #999; font-size: 11px; padding: 4px 8px;")
        self._source_info.setWordWrap(True)
        right_layout.addWidget(self._source_info)
        self._view_source_btn = QPushButton("查看来源位置")
        self._view_source_btn.clicked.connect(self._on_view_source)
        self._view_source_btn.setEnabled(False)
        right_layout.addWidget(self._view_source_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("border: none; border-top: 1px solid #3a3a3a;")
        right_layout.addWidget(sep)

        lib_notes_label = QLabel("库备注")
        lib_notes_label.setStyleSheet("color: #888; font-size: 10px;")
        right_layout.addWidget(lib_notes_label)
        self._lib_notes_edit = QTextEdit()
        self._lib_notes_edit.setMaximumHeight(70)
        self._lib_notes_edit.setPlaceholderText("给这个库添加备注...")
        self._lib_notes_edit.textChanged.connect(self._on_lib_notes_changed)
        right_layout.addWidget(self._lib_notes_edit)

        patch_label = QLabel("音色列表")
        patch_label.setStyleSheet("color: #888; font-size: 10px;")
        right_layout.addWidget(patch_label)
        self._patch_tree = QTreeWidget()
        self._patch_tree.setHeaderLabels(["音色名称", "大小"])
        self._patch_tree.setColumnWidth(0, 180)
        self._patch_tree.setColumnWidth(1, 60)
        self._patch_tree.currentItemChanged.connect(self._on_patch_selected)
        self._patch_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._patch_tree.customContextMenuRequested.connect(self._on_patch_context_menu)
        right_layout.addWidget(self._patch_tree)

        patch_notes_label = QLabel("选中音色备注")
        patch_notes_label.setStyleSheet("color: #888; font-size: 10px;")
        right_layout.addWidget(patch_notes_label)
        self._patch_notes_edit = QTextEdit()
        self._patch_notes_edit.setMaximumHeight(60)
        self._patch_notes_edit.setPlaceholderText("给选中的音色添加备注...")
        self._patch_notes_edit.textChanged.connect(self._on_patch_notes_changed)
        self._patch_notes_edit.setEnabled(False)
        right_layout.addWidget(self._patch_notes_edit)
        right_layout.addStretch()

        scroll.setWidget(right_panel)
        splitter.addWidget(scroll)
        splitter.setSizes([160, 520, 360])
        main_layout.addWidget(splitter, 1)

    def _setup_status(self):
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status_label = QLabel()
        self._status.addWidget(self._status_label)
        self._admin_label = QLabel()
        self._status.addPermanentWidget(self._admin_label)

    # ====== Event Handlers ======

    def _on_initial_load(self):
        try:
            self._manager.refresh()
        except Exception:
            pass
        self._refresh_category_list()
        self._refresh_table()
        self._admin_label.setText("管理员模式")
        self._admin_label.setStyleSheet("color: #4caf50; padding-right: 8px;")

    def _refresh_category_list(self):
        self._category_list.blockSignals(True)
        self._category_list.clear()
        libs = self._manager.libraries

        std_count = sum(1 for l in libs if l.library_type == "standard" and not l.hidden)
        ns_count = sum(1 for l in libs if l.library_type == "nonstandard" and not l.hidden)
        hidden_count = sum(1 for l in libs if l.hidden)

        self._all_item = QListWidgetItem(f"全部 ({std_count + ns_count})")
        self._all_item.setData(Qt.UserRole, "")
        self._category_list.addItem(self._all_item)

        std_item = QListWidgetItem(f"标准库 ({std_count})")
        std_item.setData(Qt.UserRole, "[[standard]]")
        self._category_list.addItem(std_item)

        ns_item = QListWidgetItem(f"非标准库 ({ns_count})")
        ns_item.setData(Qt.UserRole, "[[nonstandard]]")
        self._category_list.addItem(ns_item)

        cats = self._manager.list_categories()
        for cat in cats:
            count = cat.get("count", 0)
            item = QListWidgetItem(f"  {cat['name']} ({count})")
            item.setData(Qt.UserRole, cat["name"])
            self._category_list.addItem(item)

        uncategorized = sum(1 for l in libs if not l.categories and not l.hidden)
        uncat_item = QListWidgetItem(f"  未分类 ({uncategorized})")
        uncat_item.setData(Qt.UserRole, "__uncategorized__")
        self._category_list.addItem(uncat_item)

        if hidden_count > 0 or self._show_hidden_cb.isChecked():
            hid_item = QListWidgetItem(f"隐藏的库 ({hidden_count})")
            hid_item.setData(Qt.UserRole, "[[hidden]]")
            self._category_list.addItem(hid_item)

        self._category_list.setCurrentRow(0)
        self._category_list.blockSignals(False)

    def _filtered_libraries(self) -> list[LibraryEntry]:
        libs = self._manager.libraries
        if not self._show_hidden_cb.isChecked():
            libs = [l for l in libs if not l.hidden]
        if self._category_list.currentItem():
            raw = self._category_list.currentItem().data(Qt.UserRole)
            if raw.startswith("[[") and raw.endswith("]]"):
                type_filter = raw[2:-2]
                if type_filter == "hidden":
                    libs = [l for l in libs if l.hidden]
                else:
                    libs = [l for l in libs if l.library_type == type_filter and not l.hidden]
            elif raw == "__uncategorized__":
                libs = [l for l in libs if not l.categories]
            elif raw:
                libs = [l for l in libs if raw in l.categories]
        return libs

    def _refresh_table(self):
        libs = self._filtered_libraries()
        self._table.setRowCount(0)
        for row, lib in enumerate(libs):
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(lib.name))
            self._table.setItem(row, 1, QTableWidgetItem(lib.content_dir))
            exists_item = QTableWidgetItem("是" if lib.exists_on_disk else "否")
            exists_item.setForeground(Qt.green if lib.exists_on_disk else Qt.red)
            self._table.setItem(row, 2, exists_item)
            type_item = QTableWidgetItem(TYPE_LABELS.get(lib.library_type, lib.library_type))
            self._table.setItem(row, 3, type_item)
            self._table.setItem(row, 4, QTableWidgetItem(", ".join(lib.categories)))
        total = len(self._manager.libraries)
        shown = len(libs)
        self._status_label.setText(f"显示 {shown} 个库（共 {total} 个）")

    def _on_category_changed(self):
        self._refresh_table()

    def _on_library_selected(self):
        self._selection_timer.start()

    def _on_library_selected_debounced(self):
        selected = self._table.currentRow()
        if selected < 0:
            return
        name_item = self._table.item(selected, 0)
        if not name_item:
            return
        lib = self._manager.get_library(name_item.text())
        if lib is None:
            return

        patches = self._manager.get_patches(lib.name)
        folder_size = self._manager.get_folder_size(lib.content_dir)
        if folder_size >= 1000:
            size_str = f"{folder_size/1024:.1f} GB"
        else:
            size_str = f"{folder_size:.0f} MB"
        lib_type = TYPE_LABELS_FULL.get(lib.library_type, lib.library_type)
        info_lines = [
            f"<b style='color:#fff'>{lib.name}</b>",
            f"<span style='color:#999;'>类型: {lib_type} · 音色数: {len(patches)} 个 · 大小: {size_str}</span>",
            f"<span style='color:#999;'>路径: {lib.content_dir}</span>",
        ]
        if not lib.exists_on_disk:
            info_lines.append("<span style='color:#f44336;'>路径不存在（文件夹已被移动/删除或外置硬盘未连接）</span>")
        self._patch_info.setText("<br>".join(info_lines))

        self._build_source_info(lib)

        self._lib_notes_edit.blockSignals(True)
        self._lib_notes_edit.setText(lib.notes)
        self._lib_notes_edit.blockSignals(False)

        self._patch_tree.clear()
        self._current_patches = patches
        folders: dict[str, QTreeWidgetItem] = {}
        for patch in patches:
            if patch.folder:
                parts = patch.folder.replace("\\", "/").split("/")
                parent = self._patch_tree.invisibleRootItem()
                current_path = ""
                for part in parts:
                    current_path = f"{current_path}/{part}" if current_path else part
                    if current_path not in folders:
                        folder_item = QTreeWidgetItem([part, ""])
                        folder_item.setData(0, Qt.UserRole, "__folder__")
                        parent.addChild(folder_item)
                        folders[current_path] = folder_item
                    parent = folders[current_path]
                note_mark = " *" if patch.notes else ""
                file_item = QTreeWidgetItem([f"{patch.name}{note_mark}", f"{patch.size_mb:.1f}MB"])
                file_item.setData(0, Qt.UserRole, patch.file_path)
                parent.addChild(file_item)
            else:
                note_mark = " *" if patch.notes else ""
                file_item = QTreeWidgetItem([f"{patch.name}{note_mark}", f"{patch.size_mb:.1f}MB"])
                file_item.setData(0, Qt.UserRole, patch.file_path)
                self._patch_tree.addTopLevelItem(file_item)
        self._patch_tree.expandAll()

        self._patch_notes_edit.blockSignals(True)
        self._patch_notes_edit.clear()
        self._patch_notes_edit.setEnabled(False)
        self._patch_notes_edit.blockSignals(False)

    def _build_source_info(self, lib: LibraryEntry):
        lines = []
        if lib.found_in_registry:
            for rp in lib.registry_paths:
                lines.append(f"注册表: {rp}")
        if lib.found_in_xml and lib.xml_path:
            lines.append(f"XML: {lib.xml_path}")
        if lib.found_in_json and lib.json_path:
            lines.append(f"JSON: {lib.json_path}")
        if not lines:
            if lib.library_type in ("standard", "nonstandard"):
                self._source_info.setText(f"来源: 用户指定的{TYPE_LABELS.get(lib.library_type, '')}文件夹")
            else:
                self._source_info.setText("来源: 未知")
        else:
            self._source_info.setText("\n".join(lines))
        if not lib.is_kontakt_library and lib.library_type != "nonstandard":
            self._source_info.setText(
                self._source_info.text() + "\n\n⚠ 此条目不是 Kontakt 音色库（无 .nicnt/.nki/.nkx 文件）"
            )
        self._view_source_btn.setEnabled(bool(lines) or bool(lib.content_dir))

    def _on_patch_selected(self):
        item = self._patch_tree.currentItem()
        if item is None:
            self._patch_notes_edit.setEnabled(False)
            return
        file_path = item.data(0, Qt.UserRole)
        if not file_path or file_path == "__folder__":
            self._patch_notes_edit.setEnabled(False)
            return
        self._current_patch_path = file_path
        current_notes = get_patch_notes(file_path)
        self._patch_notes_edit.blockSignals(True)
        self._patch_notes_edit.setText(current_notes)
        self._patch_notes_edit.setEnabled(True)
        self._patch_notes_edit.blockSignals(False)

    def _on_lib_notes_changed(self):
        self._notes_timer.start()

    def _on_patch_notes_changed(self):
        self._notes_timer.start()

    def _on_notes_save(self):
        selected = self._table.currentRow()
        if selected >= 0:
            name_item = self._table.item(selected, 0)
            if name_item:
                self._manager.set_library_notes(name_item.text(), self._lib_notes_edit.toPlainText())
        if hasattr(self, '_current_patch_path') and self._current_patch_path:
            self._manager.set_patch_notes(self._current_patch_path, self._patch_notes_edit.toPlainText())

    # ====== View Source ======

    def _on_view_source(self):
        selected = self._table.currentRow()
        if selected < 0:
            return
        name_item = self._table.item(selected, 0)
        if not name_item:
            return
        lib = self._manager.get_library(name_item.text())
        if lib is None:
            return
        menu = QMenu(self)
        if lib.found_in_registry and lib.registry_paths:
            reg_action = QAction("打开注册表编辑器 (regedit)", self)
            reg_action.triggered.connect(lambda: self._open_regedit(lib))
            menu.addAction(reg_action)
            menu.addSeparator()
        if lib.found_in_xml and lib.xml_path:
            xml_action = QAction("打开 XML 文件位置", self)
            xml_action.triggered.connect(lambda: self._open_file_location(lib.xml_path))
            menu.addAction(xml_action)
        if lib.found_in_json and lib.json_path:
            json_action = QAction("打开 JSON 文件位置", self)
            json_action.triggered.connect(lambda: self._open_file_location(lib.json_path))
            menu.addAction(json_action)
        if lib.content_dir and Path(lib.content_dir).is_dir():
            if menu.actions():
                menu.addSeparator()
            cd_action = QAction("打开音色库文件夹", self)
            cd_action.triggered.connect(lambda: self._open_file_location(lib.content_dir))
            menu.addAction(cd_action)
        point = self._view_source_btn.mapToGlobal(self._view_source_btn.rect().bottomLeft())
        menu.exec(point)

    def _open_regedit(self, lib: LibraryEntry):
        if lib.registry_paths:
            paths = "\n".join(lib.registry_paths)
            reply = QMessageBox.question(
                self, "注册表位置",
                f"此库的注册表路径:\n\n{paths}\n\n是否打开注册表编辑器？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                subprocess.Popen(["regedit.exe"])

    def _open_file_location(self, path_str: str):
        p = Path(path_str)
        if p.is_file():
            subprocess.Popen(["explorer", "/select,", str(p)])
        elif p.is_dir():
            subprocess.Popen(["explorer", str(p)])
        else:
            parent = p.parent
            if parent.is_dir():
                subprocess.Popen(["explorer", str(parent)])
            else:
                QMessageBox.information(self, "路径不存在", f"路径不存在:\n{path_str}")

    # ====== Add / Remove ======

    def _on_batch_add(self):
        dlg = BatchAddDialog(self._manager, self)
        if dlg.exec() == BatchAddDialog.Accepted:
            self._manager.refresh()
            self._refresh_category_list()
            self._refresh_table()
            self._status_label.setText("批量入库完成")

    def _on_add(self):
        dlg = AddLibraryDialog(self)
        if dlg.exec() != AddLibraryDialog.Accepted:
            return
        try:
            self._manager.add_library(dlg.library_name(), dlg.library_folder(), dlg.library_snpid())
        except LibraryManagerError as e:
            QMessageBox.critical(self, "添加失败", str(e))
            if e.details:
                detail_text = "\n".join(f"  {k}: {v}" for k, v in e.details.items())
                QMessageBox.information(self, "部分结果", f"已创建:\n{detail_text}")
            return
        self._refresh_category_list()
        self._refresh_table()
        self._status_label.setText(f"已添加 '{dlg.library_name()}'")

    def _on_remove(self):
        selected = self._table.currentRow()
        if selected < 0:
            QMessageBox.information(self, "提示", "请先选择一个要移除的音色库。")
            return
        name_item = self._table.item(selected, 0)
        name = name_item.text()
        reply = QMessageBox.question(
            self, "确认移除",
            f"将移除 '{name}' 的注册信息。\n\n"
            "这会删除注册表项、XML 和 JSON 文件，\n但不会删除磁盘上的音色库文件。\n\n确定移除？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            self._manager.remove_library(name)
        except LibraryManagerError as e:
            QMessageBox.critical(self, "移除失败", str(e))
            return
        self._refresh_category_list()
        self._refresh_table()
        self._patch_tree.clear()
        self._patch_info.setText("选择一个库以查看详情")
        self._source_info.setText("")
        self._view_source_btn.setEnabled(False)
        self._lib_notes_edit.clear()
        self._patch_notes_edit.clear()
        self._patch_notes_edit.setEnabled(False)
        self._status_label.setText(f"已移除 '{name}'")

    def _on_batch_remove(self):
        selected_rows = set()
        for item in self._table.selectedItems():
            selected_rows.add(item.row())
        if not selected_rows:
            QMessageBox.information(self, "提示",
                "请先选中要移除的音色库。\n\n提示: 按住 Ctrl 点击可多选，按住 Shift 可连选。")
            return
        names = []
        for row in sorted(selected_rows):
            name_item = self._table.item(row, 0)
            if name_item:
                names.append(name_item.text())
        if not names:
            return
        names_display = "\n".join(f"  - {n}" for n in names)
        reply = QMessageBox.question(
            self, "确认批量移除",
            f"将移除以下 {len(names)} 个音色库的注册信息：\n\n{names_display}\n\n"
            "这会删除注册表项、XML 和 JSON 文件，\n但不会删除磁盘上的音色库文件。\n\n确定批量移除？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        errors = []
        success = []
        for name in names:
            try:
                self._manager.remove_library(name)
                success.append(name)
            except LibraryManagerError as e:
                errors.append(f"{name}: {e}")
        self._refresh_category_list()
        self._refresh_table()
        self._patch_tree.clear()
        self._patch_info.setText("选择一个库以查看详情")
        self._source_info.setText("")
        self._view_source_btn.setEnabled(False)
        self._lib_notes_edit.clear()
        self._patch_notes_edit.clear()
        self._patch_notes_edit.setEnabled(False)
        msg = f"成功移除 {len(success)} 个音色库"
        if errors:
            msg += f"\n{len(errors)} 个失败:\n" + "\n".join(errors)
        self._status_label.setText(msg)

    def _on_refresh(self):
        self._manager.refresh()
        self._refresh_category_list()
        self._refresh_table()
        self._patch_tree.clear()
        self._patch_info.setText("选择一个库以查看详情")
        self._status_label.setText("已刷新")

    def _on_manage_folders(self):
        dlg = FolderDialog(self._manager, self)
        dlg.exec()
        self._refresh_category_list()
        self._refresh_table()

    # ====== Context Menus ======

    def _on_table_context_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0:
            return
        name_item = self._table.item(row, 0)
        lib_name = name_item.text()
        lib = self._manager.get_library(lib_name)
        menu = QMenu(self)

        # Category submenu (multi-select with checkmarks)
        cats = self._manager.list_categories()
        current_cats = lib.categories if lib else []
        cat_menu = QMenu("设置分类", self)
        if current_cats:
            clear_action = QAction("清除全部分类", self)
            clear_action.triggered.connect(lambda: self._clear_categories(lib_name))
            cat_menu.addAction(clear_action)
            cat_menu.addSeparator()
        for cat in cats:
            is_checked = cat['name'] in current_cats
            prefix = "✓ " if is_checked else "    "
            action = QAction(f"{prefix}{cat['name']}", self)
            action.triggered.connect(lambda checked, c=cat['name'], was=is_checked: self._toggle_category(lib_name, c, was))
            cat_menu.addAction(action)
        menu.addMenu(cat_menu)

        # Hide / Unhide
        menu.addSeparator()
        if lib and lib.hidden:
            unhide_action = QAction("取消隐藏", self)
            unhide_action.triggered.connect(lambda: self._unhide_library(lib_name))
            menu.addAction(unhide_action)
        else:
            hide_action = QAction("隐藏此库", self)
            hide_action.triggered.connect(lambda: self._hide_library(lib_name))
            menu.addAction(hide_action)

        # View source
        if lib and (lib.found_in_registry or lib.content_dir):
            source_menu = QMenu("查看来源", self)
            if lib.registry_paths:
                reg_action = QAction("打开注册表编辑器", self)
                reg_action.triggered.connect(lambda: self._open_regedit(lib))
                source_menu.addAction(reg_action)
            if lib.xml_path:
                xml_action = QAction("XML 文件位置", self)
                xml_action.triggered.connect(lambda: self._open_file_location(lib.xml_path))
                source_menu.addAction(xml_action)
            if lib.json_path:
                json_action = QAction("JSON 文件位置", self)
                json_action.triggered.connect(lambda: self._open_file_location(lib.json_path))
                source_menu.addAction(json_action)
            if lib.content_dir and Path(lib.content_dir).is_dir():
                cd_action = QAction("音色库文件夹", self)
                cd_action.triggered.connect(lambda: self._open_file_location(lib.content_dir))
                source_menu.addAction(cd_action)
            if source_menu.actions():
                menu.addMenu(source_menu)

        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _on_patch_context_menu(self, pos):
        item = self._patch_tree.itemAt(pos)
        if item is None:
            return
        file_path = item.data(0, Qt.UserRole)
        if not file_path or file_path == "__folder__":
            return
        menu = QMenu(self)
        open_action = QAction("打开文件位置", self)
        open_action.triggered.connect(lambda: self._open_file_location(file_path))
        menu.addAction(open_action)
        menu.exec(self._patch_tree.viewport().mapToGlobal(pos))

    def _toggle_category(self, lib_name: str, cat_name: str, currently_checked: bool):
        if currently_checked:
            self._manager.remove_library_from_category(lib_name, cat_name)
        else:
            self._manager.add_library_to_category(lib_name, cat_name)
        self._refresh_category_list()
        self._refresh_table()

    def _clear_categories(self, lib_name: str):
        self._manager.set_library_categories(lib_name, [])
        self._refresh_category_list()
        self._refresh_table()

    def _hide_library(self, lib_name: str):
        self._manager.hide_library(lib_name)
        self._refresh_category_list()
        self._refresh_table()
        self._status_label.setText(f"已隐藏 '{lib_name}'")

    def _unhide_library(self, lib_name: str):
        self._manager.unhide_library(lib_name)
        self._refresh_category_list()
        self._refresh_table()
        self._status_label.setText(f"已取消隐藏 '{lib_name}'")

    def _on_manage_categories(self):
        dlg = CategoryDialog(self._manager, self)
        dlg.exec()
        self._refresh_category_list()
        self._refresh_table()

    # ====== Helpers ======


