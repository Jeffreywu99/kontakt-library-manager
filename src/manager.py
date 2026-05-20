"""LibraryManager: central business logic facade.

The UI layer talks only to this class. Pure Python — no Qt imports.
"""

import logging
from pathlib import Path
from datetime import datetime
from src.models import LibraryEntry, PatchEntry
from src.scanner import scan_all, scan_patches
from src.registry import (
    add_library as reg_add, remove_library as reg_remove, is_admin,
    list_libraries as list_registry_libraries,
)

def _trace(msg: str) -> None:
    try:
        with open(Path.home() / "klm_debug.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass
from src.files import create_xml, create_json, remove_xml, remove_json, list_from_xml, list_from_json
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
        return results

    def add_library(self, name: str, folder_path: str, snpid: str = "") -> LibraryEntry:
        _trace(f"add_library ENTER: name={name!r} folder={folder_path!r} snpid={snpid!r}")
        if not name.strip():
            _trace("add_library FAIL: empty name")
            raise LibraryManagerError("库名称不能为空。")
        name = name.strip()
        folder = Path(folder_path)
        if not folder.is_dir():
            _trace(f"add_library FAIL: folder not found: {folder_path}")
            raise LibraryManagerError(f"文件夹不存在: {folder_path}")
        if not is_admin():
            _trace("add_library FAIL: not admin")
            raise LibraryManagerError("需要管理员权限才能添加音色库。请以管理员身份运行。")

        existing = self.get_library(name)
        if existing is not None and (existing.found_in_registry or existing.found_in_xml or existing.found_in_json):
            _trace(f"add_library FAIL: already registered: {existing}")
            raise LibraryManagerError(f"音色库 '{name}' 已注册在 Kontakt 中。")

        folder_str = str(folder)
        try:
            reg_add(name, folder_str)
            _trace("add_library: reg_add OK")
        except OSError as e:
            _trace(f"add_library FAIL: reg_add error: {e}")
            raise LibraryManagerError(f"注册表写入失败: {e}")

        try:
            create_xml(name, folder_str, snpid)
            _trace("add_library: create_xml OK")
        except OSError as e:
            _trace(f"add_library FAIL: create_xml error: {e}")
            raise LibraryManagerError(f"XML 文件创建失败（注册表已写入，请手动清理）。\n{e}")

        try:
            create_json(name, folder_str)
            _trace("add_library: create_json OK")
        except OSError as e:
            _trace(f"add_library FAIL: create_json error: {e}")
            raise LibraryManagerError(f"JSON 文件创建失败（注册表和 XML 已写入）。\n{e}")

        # Read back registration metadata (fast — no folder scan)
        _, reg_sources = list_registry_libraries()
        xml_data, xml_sources = list_from_xml()
        json_data, json_sources = list_from_json()
        registry_paths = reg_sources.get(name, [])
        xml_path = xml_sources.get(name, "")
        json_path = json_sources.get(name, "")

        folder_norm = str(folder.resolve())
        existing_idx = None
        for i, lib in enumerate(self._libraries):
            try:
                if str(Path(lib.content_dir).resolve()) == folder_norm:
                    existing_idx = i
                    break
            except Exception:
                pass

        if existing_idx is not None:
            lib = self._libraries[existing_idx]
            lib.found_in_registry = True
            lib.found_in_xml = True
            lib.found_in_json = True
            lib.registry_paths = registry_paths
            lib.xml_path = xml_path
            lib.json_path = json_path
            lib.snpid = snpid or lib.snpid
            _trace(f"add_library SUCCESS (merged): {lib}")
            return lib

        entry = LibraryEntry(
            name=name, content_dir=folder_str, snpid=snpid,
            found_in_registry=True, found_in_xml=True, found_in_json=True,
            exists_on_disk=True, is_kontakt_library=True,
            library_type="registry",
            categories=get_library_categories(name),
            notes=get_library_notes(name), hidden=False,
            registry_paths=registry_paths,
            xml_path=xml_path, json_path=json_path,
        )
        self._libraries.append(entry)
        self._libraries.sort(key=lambda e: e.name.lower())
        _trace(f"add_library SUCCESS (new): {entry}")
        return entry

    def remove_library(self, name: str) -> dict:
        _trace(f"remove_library ENTER: name={name!r}")
        if not name.strip():
            _trace("remove_library FAIL: empty name")
            raise LibraryManagerError("库名称不能为空。")
        if not is_admin():
            _trace("remove_library FAIL: not admin")
            raise LibraryManagerError("需要管理员权限才能移除音色库。请以管理员身份运行。")

        # Look up stored paths (may differ from name-derived paths)
        lib = self.get_library(name)
        xml_path = lib.xml_path if lib else ""
        json_path = lib.json_path if lib else ""

        results: dict = {}
        failed_reg = reg_remove(name)
        _trace(f"remove_library: reg_remove failed={failed_reg}")
        results["registry"] = len(failed_reg) == 0

        # Delete using stored paths (handles name mismatches)
        if xml_path:
            try:
                Path(xml_path).unlink(missing_ok=True)
                results["xml"] = True
                _trace(f"remove_library: deleted xml by path: {xml_path}")
            except OSError:
                results["xml"] = False
        # Always also try name-derived path as fallback
        if not xml_path or not results.get("xml"):
            results["xml"] = remove_xml(name)

        if json_path:
            try:
                Path(json_path).unlink(missing_ok=True)
                results["json"] = True
                _trace(f"remove_library: deleted json by path: {json_path}")
            except OSError:
                results["json"] = False
        # Always also try name-derived path as fallback
        if not json_path or not results.get("json"):
            results["json"] = remove_json(name)

        _trace(f"remove_library results: {results}")

        set_library_categories(name, [])
        set_library_notes(name, "")
        clear_patch_cache(name)
        self._patches_cache.pop(name, None)

        # Remove from in-memory list
        self._libraries = [l for l in self._libraries if l.name.lower() != name.lower()]
        _trace(f"remove_library: in-memory remove done, libraries: {len(self._libraries)}")
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

    def get_folder_size(self, path_str: str) -> float:
        """Get total folder size in MB. Uses cache if available."""
        if not path_str:
            return 0.0
        # Try cache first
        for lib in self._libraries:
            if lib.content_dir == path_str and hasattr(lib, '_cached_size_mb'):
                return lib._cached_size_mb
        p = Path(path_str)
        if not p.is_dir():
            return 0.0
        total = 0
        try:
            for f in p.rglob("*"):
                if f.is_file():
                    try:
                        total += f.stat().st_size
                    except OSError:
                        pass
        except OSError:
            return 0.0
        size_mb = round(total / (1024 * 1024), 1)
        # Cache on the library entry
        for lib in self._libraries:
            if lib.content_dir == path_str:
                lib._cached_size_mb = size_mb
                break
        return size_mb
