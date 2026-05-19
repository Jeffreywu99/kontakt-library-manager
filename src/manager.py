"""LibraryManager: central business logic facade.

The UI layer talks only to this class. Pure Python — no Qt imports.
"""

import logging
from pathlib import Path
from src.models import LibraryEntry, PatchEntry
from src.scanner import scan_all, scan_patches
from src.registry import add_library as reg_add, remove_library as reg_remove, is_admin
from src.files import create_xml, create_json, remove_xml, remove_json
from src.storage import (
    get_library_roots,
    add_library_root,
    remove_library_root,
    get_custom_libraries,
    add_custom_library,
    remove_custom_library,
    hide_library,
    unhide_library,
    get_hidden_libraries,
    get_show_registry,
    set_show_registry,
    get_categories,
    add_category,
    remove_category,
    rename_category,
    get_library_categories,
    set_library_categories,
    add_library_to_category,
    remove_library_from_category,
    get_library_notes,
    set_library_notes,
    get_patch_notes,
    set_patch_notes,
    clear_patch_cache,
)

logger = logging.getLogger(__name__)


class LibraryManagerError(Exception):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


class LibraryManager:
    def __init__(self):
        self._libraries: list[LibraryEntry] = []
        self._patches_cache: dict[str, list[PatchEntry]] = {}

    @property
    def libraries(self) -> list[LibraryEntry]:
        return list(self._libraries)

    @property
    def is_admin(self) -> bool:
        return is_admin()

    # ---- Refresh ----

    def refresh(self) -> list[LibraryEntry]:
        self._libraries = scan_all()
        self._patches_cache = {}
        return self._libraries

    # ---- Library Roots ----

    def list_roots(self) -> list[dict]:
        return get_library_roots()

    def add_root(self, path_str: str, root_type: str = "standard") -> None:
        p = Path(path_str)
        if not p.is_dir():
            raise LibraryManagerError(f"文件夹不存在: {path_str}")
        add_library_root(path_str, root_type)
        self.refresh()

    def remove_root(self, path_str: str) -> None:
        remove_library_root(path_str)
        self.refresh()

    # ---- Custom Libraries ----

    def list_custom_libraries(self) -> list[dict]:
        return get_custom_libraries()

    def add_custom_library(self, name: str, path_str: str) -> None:
        p = Path(path_str)
        if not p.is_dir():
            raise LibraryManagerError(f"文件夹不存在: {path_str}")
        if not name.strip():
            name = p.name
        add_custom_library(name.strip(), path_str)
        self.refresh()

    def remove_custom_library(self, path_str: str) -> None:
        remove_custom_library(path_str)
        self.refresh()

    # ---- Hide / Unhide ----

    def hide_library(self, name: str) -> None:
        hide_library(name)
        lib = self.get_library(name)
        if lib:
            lib.hidden = True

    def unhide_library(self, name: str) -> None:
        unhide_library(name)
        lib = self.get_library(name)
        if lib:
            lib.hidden = False

    def get_hidden_libraries(self) -> list[str]:
        return get_hidden_libraries()

    # ---- Show Registry Toggle ----

    @property
    def show_registry(self) -> bool:
        return get_show_registry()

    @show_registry.setter
    def show_registry(self, value: bool) -> None:
        set_show_registry(value)
        self.refresh()

    # ---- Add / Remove (Kontakt registration) ----

    def add_libraries_batch(self, entries: list[tuple[str, str]]) -> dict[str, str]:
        """Batch add multiple libraries. entries = [(name, path), ...].
        Returns {name: "success"|"error: message"}.
        """
        if not is_admin():
            raise LibraryManagerError("需要管理员权限。请以管理员身份运行。")
        results: dict[str, str] = {}
        for name, path_str in entries:
            try:
                self.add_library(name, path_str)
                results[name] = "success"
            except LibraryManagerError as e:
                results[name] = f"error: {e}"
        self.refresh()
        return results

    def add_library(self, name: str, folder_path: str, snpid: str = "") -> LibraryEntry:
        if not name.strip():
            raise LibraryManagerError("库名称不能为空。")
        name = name.strip()
        folder = Path(folder_path)
        if not folder.is_dir():
            raise LibraryManagerError(f"文件夹不存在: {folder_path}")
        if not is_admin():
            raise LibraryManagerError("需要管理员权限才能添加音色库。请以管理员身份运行。")

        existing = self.get_library(name)
        if existing is not None:
            raise LibraryManagerError(f"音色库 '{name}' 已经存在。")

        folder_str = str(folder)
        details: dict = {}
        try:
            reg_add(name, folder_str)
            details["registry"] = "created"
        except OSError as e:
            raise LibraryManagerError(f"注册表写入失败: {e}")

        try:
            create_xml(name, folder_str, snpid)
            details["xml"] = "created"
        except OSError as e:
            raise LibraryManagerError(
                f"XML 文件创建失败（注册表已写入，请手动清理）。\n{e}",
                details=details,
            )

        try:
            create_json(name, folder_str)
            details["json"] = "created"
        except OSError as e:
            raise LibraryManagerError(
                f"JSON 文件创建失败（注册表和 XML 已写入）。\n{e}",
                details=details,
            )

        self.refresh()
        entry = self.get_library(name)
        if entry is None:
            raise LibraryManagerError(f"添加后未能找到库 '{name}'，请检查。")
        return entry

    def remove_library(self, name: str) -> dict:
        if not name.strip():
            raise LibraryManagerError("库名称不能为空。")
        if not is_admin():
            raise LibraryManagerError("需要管理员权限才能移除音色库。请以管理员身份运行。")

        results: dict = {}
        failed_reg = reg_remove(name)
        results["registry"] = len(failed_reg) == 0
        results["xml"] = remove_xml(name)
        results["json"] = remove_json(name)

        set_library_categories(name, [])
        set_library_notes(name, "")
        clear_patch_cache(name)
        self._patches_cache.pop(name, None)

        self.refresh()
        return results

    def get_library(self, name: str) -> LibraryEntry | None:
        for lib in self._libraries:
            if lib.name.lower() == name.lower():
                return lib
        return None

    # ---- Patch Operations ----

    def get_patches(self, library_name: str, force_rescan: bool = False) -> list[PatchEntry]:
        if not force_rescan and library_name in self._patches_cache:
            return self._patches_cache[library_name]

        lib = self.get_library(library_name)
        if lib is None:
            return []

        if force_rescan:
            clear_patch_cache(library_name)

        patches = scan_patches(library_name, lib.content_dir)
        self._patches_cache[library_name] = patches
        return patches

    # ---- Category Operations ----

    def list_categories(self) -> list[dict]:
        cats = get_categories()
        for cat in cats:
            count = sum(1 for lib in self._libraries if cat["name"] in lib.categories)
            cat["count"] = count
        return cats

    def add_category(self, name: str) -> None:
        if not name.strip():
            raise LibraryManagerError("分类名称不能为空。")
        add_category(name.strip())

    def remove_category(self, name: str) -> None:
        remove_category(name)
        self._libraries = scan_all()

    def rename_category(self, old_name: str, new_name: str) -> None:
        if not new_name.strip():
            raise LibraryManagerError("新分类名称不能为空。")
        rename_category(old_name, new_name.strip())
        self._libraries = scan_all()

    def get_library_categories(self, library_name: str) -> list[str]:
        return get_library_categories(library_name)

    def set_library_categories(self, library_name: str, categories: list[str]) -> None:
        set_library_categories(library_name, categories)
        lib = self.get_library(library_name)
        if lib:
            lib.categories = list(categories)

    def add_library_to_category(self, library_name: str, category_name: str) -> None:
        add_library_to_category(library_name, category_name)
        lib = self.get_library(library_name)
        if lib and category_name not in lib.categories:
            lib.categories.append(category_name)

    def remove_library_from_category(self, library_name: str, category_name: str) -> None:
        remove_library_from_category(library_name, category_name)
        lib = self.get_library(library_name)
        if lib and category_name in lib.categories:
            lib.categories.remove(category_name)

    # ---- Notes Operations ----

    def set_library_notes(self, name: str, text: str) -> None:
        set_library_notes(name, text)
        lib = self.get_library(name)
        if lib:
            lib.notes = text

    def set_patch_notes(self, file_path: str, text: str) -> None:
        set_patch_notes(file_path, text)
