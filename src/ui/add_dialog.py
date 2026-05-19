"""Dialog for adding a new Kontakt library."""

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLineEdit, QPushButton, QFileDialog, QMessageBox, QLabel,
)
from PySide6.QtCore import Qt


class AddLibraryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加音色库")
        self.setMinimumWidth(480)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(12)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("输入音色库名称")
        form.addRow("库名称 *", self._name_edit)

        folder_layout = QHBoxLayout()
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("选择音色库文件夹路径")
        self._folder_edit.setReadOnly(True)
        folder_layout.addWidget(self._folder_edit)

        browse_btn = QPushButton("浏览...")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._on_browse)
        folder_layout.addWidget(browse_btn)

        form.addRow("库文件夹 *", folder_layout)

        self._snpid_edit = QLineEdit()
        self._snpid_edit.setPlaceholderText("可选，如: ABC123")
        form.addRow("SNPID", self._snpid_edit)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        confirm_btn = QPushButton("确定添加")
        confirm_btn.setDefault(True)
        confirm_btn.clicked.connect(self._on_accept)
        btn_layout.addWidget(confirm_btn)

        layout.addLayout(btn_layout)

    def _on_browse(self):
        folder = QFileDialog.getExistingDirectory(self, "选择音色库文件夹")
        if folder:
            self._folder_edit.setText(folder)
            if not self._name_edit.text():
                self._name_edit.setText(Path(folder).name)

    def _on_accept(self):
        name = self._name_edit.text().strip()
        folder = self._folder_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "输入不完整", "请输入音色库名称。")
            self._name_edit.setFocus()
            return
        if not folder:
            QMessageBox.warning(self, "输入不完整", "请选择音色库文件夹。")
            return
        if not Path(folder).is_dir():
            QMessageBox.warning(self, "路径无效", f"文件夹不存在:\n{folder}")
            return

        self.accept()

    def library_name(self) -> str:
        return self._name_edit.text().strip()

    def library_folder(self) -> str:
        return self._folder_edit.text().strip()

    def library_snpid(self) -> str:
        return self._snpid_edit.text().strip()
