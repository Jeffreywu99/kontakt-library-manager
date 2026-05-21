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
    get_library_folders,
    add_library_folder,
    remove_library_folder,
    get_nonstandard_folders,
    add_nonstandard_folder,
    remove_nonstandard_folder,
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
    get_nonstandard_libraries,
    update_nonstandard_library,
    get_scan_cache,
    clear_scan_cache,
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

    def force_full_scan(self) -> list[LibraryEntry]:
        """Clear cache and perform a complete auto-discovery from registry."""
        clear_scan_cache()
        self._libraries = scan_all()
        self._patches_cache = {}
        return self._libraries

    def get_scan_info(self) -> dict:
        """Return information about the last scan."""
        cache = get_scan_cache()
        if not cache:
            return {"last_scan": None, "library_count": 0}
        return {
            "last_scan": cache.get("last_full_scan", ""),
            "library_count": len(cache.get("libraries", [])),
        }

    # ---- Library Folders ----

    def list_folders(self) -> list[str]:
        return get_library_folders()

    def add_folder(self, path_str: str) -> None:
        p = Path(path_str)
        if not p.is_dir():
            raise LibraryManagerError(f"文件夹不存在: {path_str}")
        add_library_folder(path_str)
        self.refresh()

    def remove_folder(self, path_str: str) -> None:
        remove_library_folder(path_str)
        self.refresh()

    # ---- Non-standard Library Folders ----

    def list_nonstandard_folders(self) -> list[str]:
        return get_nonstandard_folders()

    def add_nonstandard_folder(self, path_str: str) -> None:
        p = Path(path_str)
        if not p.is_dir():
            raise LibraryManagerError(f"文件夹不存在: {path_str}")
        add_nonstandard_folder(path_str)
        self.refresh()

    def remove_nonstandard_folder(self, path_str: str) -> None:
        remove_nonstandard_folder(path_str)
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

        from src.scanner import _extract_nicnt_info
        nicnt_info = _extract_nicnt_info(folder)
        if not snpid:
            snpid = nicnt_info.get("snpid", "")
        upid = nicnt_info.get("upid", "")
        hu = nicnt_info.get("hu", "")
        jdx = nicnt_info.get("jdx", "")
        company = nicnt_info.get("company", "")
        auth_system = nicnt_info.get("auth_system", "")
        powered_by = nicnt_info.get("powered_by", "")
        regkey = nicnt_info.get("regkey", "")
        nicnt_name = nicnt_info.get("name", "")

        # Use RegKey from .nicnt if available, otherwise use provided name
        reg_name = regkey if regkey else name
        # Use Name from .nicnt for display if available
        display_name = nicnt_name if nicnt_name else name

        _trace(f"add_library: nicnt_info snpid={snpid!r} upid={upid!r} hu={hu!r} jdx={jdx!r} company={company!r} auth_system={auth_system!r} powered_by={powered_by!r} regkey={regkey!r} name={nicnt_name!r}")
        _trace(f"add_library: reg_name={reg_name!r} display_name={display_name!r}")

        existing = self.get_library(reg_name)
        if existing is not None and (existing.found_in_registry or existing.found_in_xml or existing.found_in_json):
            _trace(f"add_library FAIL: already registered: {existing}")
            raise LibraryManagerError(f"音色库 '{reg_name}' 已注册在 Kontakt 中。")

        folder_str = str(folder)
        try:
            reg_add(reg_name, folder_str, hu=hu, jdx=jdx)
            _trace("add_library: reg_add OK")
        except OSError as e:
            _trace(f"add_library FAIL: reg_add error: {e}")
            raise LibraryManagerError(f"注册表写入失败: {e}")

        try:
            create_xml(reg_name, upid=upid, snpid=snpid, hu=hu, jdx=jdx,
                       company=company, auth_system=auth_system, powered_by=powered_by)
            _trace("add_library: create_xml OK")
        except OSError as e:
            _trace(f"add_library FAIL: create_xml error: {e}")
            raise LibraryManagerError(f"XML 文件创建失败（注册表已写入，请手动清理）。\n{e}")

        try:
            create_json(reg_name, folder_str)
            _trace("add_library: create_json OK")
        except OSError as e:
            _trace(f"add_library FAIL: create_json error: {e}")
            raise LibraryManagerError(f"JSON 文件创建失败（注册表和 XML 已写入）。\n{e}")

        # Auto-add parent folder to library_folders
        parent_folder = str(folder.parent)
        if parent_folder and parent_folder not in get_library_folders():
            add_library_folder(parent_folder)
            _trace(f"add_library: auto-added parent folder: {parent_folder}")

        # Read back registration metadata (fast — no folder scan)
        _, reg_sources = list_registry_libraries()
        xml_data, xml_sources = list_from_xml()
        json_data, json_sources = list_from_json()
        registry_paths = reg_sources.get(reg_name, [])
        xml_path = xml_sources.get(reg_name, "")
        json_path = json_sources.get(reg_name, "")

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
            lib.name = display_name
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
            name=display_name, content_dir=folder_str, snpid=snpid,
            found_in_registry=True, found_in_xml=True, found_in_json=True,
            exists_on_disk=True, is_kontakt_library=True,
            categories=get_library_categories(display_name),
            notes=get_library_notes(display_name),
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

        lib = self.get_library(name)
        content_dir = lib.content_dir if lib else ""

        results: dict = {}

        # Delete registry: resolve actual key names by content_dir
        from src.registry import find_registry_names_by_dir
        reg_names_to_remove = set()
        reg_names_to_remove.add(name)
        if content_dir:
            for alt_name in find_registry_names_by_dir(content_dir):
                reg_names_to_remove.add(alt_name)
        _trace(f"remove_library: registry names to remove: {reg_names_to_remove}")

        any_reg_failed = False
        for reg_name in reg_names_to_remove:
            failed = reg_remove(reg_name)
            _trace(f"remove_library: reg_remove('{reg_name}') failed={failed}")
            if failed:
                any_reg_failed = True
        results["registry"] = not any_reg_failed

        # Delete XML: try all names, then resolve by content_dir
        xml_deleted = False
        for reg_name in reg_names_to_remove:
            if remove_xml(reg_name):
                xml_deleted = True
        if not xml_deleted and content_dir:
            from src.files import list_from_xml
            xml_data, xml_sources = list_from_xml()
            for xml_name, info in xml_data.items():
                cd = info.get("content_dir", "")
                if cd and str(Path(cd).resolve()).lower() == str(Path(content_dir).resolve()).lower():
                    alt_xml_path = xml_sources.get(xml_name, "")
                    if alt_xml_path:
                        try:
                            Path(alt_xml_path).unlink(missing_ok=True)
                            xml_deleted = True
                            _trace(f"remove_library: deleted xml by content_dir match: {alt_xml_path}")
                        except OSError:
                            pass
                    break
        results["xml"] = xml_deleted

        # Delete JSON: try all names, then resolve by content_dir
        json_deleted = False
        for reg_name in reg_names_to_remove:
            if remove_json(reg_name):
                json_deleted = True
        if not json_deleted and content_dir:
            from src.files import find_json_by_content_dir
            alt_json = find_json_by_content_dir(content_dir)
            if alt_json:
                try:
                    Path(alt_json).unlink(missing_ok=True)
                    json_deleted = True
                    _trace(f"remove_library: deleted json by content_dir match: {alt_json}")
                except OSError:
                    pass
        results["json"] = json_deleted

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

    # ---- Non-standard Library Operations ----

    def list_nonstandard_libraries(self) -> list[dict]:
        return get_nonstandard_libraries()

    def update_nonstandard_library(self, path: str, name: str | None = None, categories: list[str] | None = None, notes: str | None = None) -> None:
        update_nonstandard_library(path, name, categories, notes)
        for lib in self._libraries:
            if lib.content_dir == path:
                if name is not None:
                    lib.name = name
                if categories is not None:
                    lib.categories = categories
                if notes is not None:
                    lib.notes = notes
                break
