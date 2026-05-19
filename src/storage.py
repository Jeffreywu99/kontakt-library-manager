"""Local data persistence for categories, notes, library roots, and hidden state.

All data is stored in %APPDATA%/KontaktLibraryManager/data.json
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone


def _data_dir() -> Path:
    p = Path(os.environ["APPDATA"]) / "KontaktLibraryManager"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _data_file() -> Path:
    return _data_dir() / "data.json"


def _default_data() -> dict:
    return {
        "library_roots": [],
        "custom_libraries": [],
        "hidden_libraries": [],
        "show_registry_libraries": False,
        "categories": [],
        "library_categories": {},
        "library_notes": {},
        "patch_notes": {},
        "patch_scan_cache": {},
    }


def _load() -> dict:
    path = _data_file()
    if not path.exists():
        return _default_data()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key in _default_data():
            if key not in data:
                data[key] = _default_data()[key]
        return data
    except (json.JSONDecodeError, OSError):
        return _default_data()


def _save(data: dict) -> None:
    path = _data_file()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---- Library Roots ----

def get_library_roots() -> list[dict]:
    data = _load()
    return data.get("library_roots", [])


def add_library_root(path: str, root_type: str = "standard") -> None:
    data = _load()
    normalized = str(Path(path).resolve())
    if not any(r.get("path") == normalized for r in data["library_roots"]):
        data["library_roots"].append({"path": normalized, "type": root_type})
    _save(data)


def remove_library_root(path: str) -> None:
    data = _load()
    normalized = str(Path(path).resolve())
    data["library_roots"] = [
        r for r in data["library_roots"] if r.get("path") != normalized
    ]
    _save(data)


# ---- Custom Libraries (manually added, non-standard) ----

def get_custom_libraries() -> list[dict]:
    data = _load()
    return data.get("custom_libraries", [])


def add_custom_library(name: str, path_str: str) -> None:
    data = _load()
    normalized = str(Path(path_str).resolve())
    if not any(c.get("path") == normalized for c in data["custom_libraries"]):
        data["custom_libraries"].append({"name": name, "path": normalized})
    _save(data)


def remove_custom_library(path_str: str) -> None:
    data = _load()
    normalized = str(Path(path_str).resolve())
    data["custom_libraries"] = [
        c for c in data["custom_libraries"] if c.get("path") != normalized
    ]
    _save(data)


# ---- Hidden Libraries ----

def is_hidden(name: str) -> bool:
    data = _load()
    return name in data.get("hidden_libraries", [])


def hide_library(name: str) -> None:
    data = _load()
    if name not in data["hidden_libraries"]:
        data["hidden_libraries"].append(name)
    _save(data)


def unhide_library(name: str) -> None:
    data = _load()
    if name in data["hidden_libraries"]:
        data["hidden_libraries"].remove(name)
    _save(data)


def get_hidden_libraries() -> list[str]:
    data = _load()
    return list(data.get("hidden_libraries", []))


# ---- Show Registry Libraries toggle ----

def get_show_registry() -> bool:
    data = _load()
    return data.get("show_registry_libraries", False)


def set_show_registry(show: bool) -> None:
    data = _load()
    data["show_registry_libraries"] = show
    _save(data)


# ---- Categories ----

def get_categories() -> list[dict]:
    data = _load()
    return sorted(data["categories"], key=lambda c: c.get("order", 0))


def add_category(name: str) -> None:
    data = _load()
    if any(c["name"] == name for c in data["categories"]):
        return
    max_order = max((c.get("order", 0) for c in data["categories"]), default=-1)
    data["categories"].append({"name": name, "order": max_order + 1})
    _save(data)


def remove_category(name: str) -> None:
    data = _load()
    data["categories"] = [c for c in data["categories"] if c["name"] != name]
    for lib, cats in list(data["library_categories"].items()):
        if name in cats:
            cats.remove(name)
            if not cats:
                del data["library_categories"][lib]
    _save(data)


def rename_category(old_name: str, new_name: str) -> None:
    data = _load()
    for c in data["categories"]:
        if c["name"] == old_name:
            c["name"] = new_name
    for lib, cats in data["library_categories"].items():
        if old_name in cats:
            cats.remove(old_name)
            if new_name not in cats:
                cats.append(new_name)
    _save(data)


# ---- Library Categories (multi-tag) ----

def get_library_categories(name: str) -> list[str]:
    data = _load()
    cats = data["library_categories"].get(name, [])
    if isinstance(cats, str):
        # Migrate old single-category format
        cats = [cats] if cats else []
        data["library_categories"][name] = cats
        _save(data)
    return list(cats)


def set_library_categories(library_name: str, categories: list[str]) -> None:
    data = _load()
    if categories:
        data["library_categories"][library_name] = list(categories)
    else:
        data["library_categories"].pop(library_name, None)
    _save(data)


def add_library_to_category(library_name: str, category_name: str) -> None:
    data = _load()
    cats = data["library_categories"].get(library_name, [])
    if isinstance(cats, str):
        cats = [cats] if cats else []
    if category_name not in cats:
        cats.append(category_name)
    data["library_categories"][library_name] = cats
    _save(data)


def remove_library_from_category(library_name: str, category_name: str) -> None:
    data = _load()
    cats = data["library_categories"].get(library_name, [])
    if isinstance(cats, str):
        cats = [cats] if cats else []
    if category_name in cats:
        cats.remove(category_name)
    if cats:
        data["library_categories"][library_name] = cats
    else:
        data["library_categories"].pop(library_name, None)
    _save(data)


# ---- Library Notes ----

def get_library_notes(name: str) -> str:
    data = _load()
    return data["library_notes"].get(name, "")


def set_library_notes(name: str, text: str) -> None:
    data = _load()
    if text:
        data["library_notes"][name] = text
    else:
        data["library_notes"].pop(name, None)
    _save(data)


# ---- Patch Notes ----

def get_patch_notes(file_path: str) -> str:
    data = _load()
    return data["patch_notes"].get(file_path, "")


def set_patch_notes(file_path: str, text: str) -> None:
    data = _load()
    if text:
        data["patch_notes"][file_path] = text
    else:
        data["patch_notes"].pop(file_path, None)
    _save(data)


# ---- Patch Scan Cache ----

def get_patch_cache(library_name: str) -> dict | None:
    data = _load()
    cache = data["patch_scan_cache"].get(library_name)
    if cache is None:
        return None
    last_scan = cache.get("last_scan", "")
    if last_scan:
        try:
            scan_time = datetime.fromisoformat(last_scan)
            age = datetime.now(timezone.utc) - scan_time
            if age.total_seconds() > 86400:
                return None
        except ValueError:
            return None
    return cache


def set_patch_cache(library_name: str, patches: list[dict]) -> None:
    data = _load()
    data["patch_scan_cache"][library_name] = {
        "last_scan": datetime.now(timezone.utc).isoformat(),
        "patches": patches,
    }
    _save(data)


def clear_patch_cache(library_name: str | None = None) -> None:
    data = _load()
    if library_name:
        data["patch_scan_cache"].pop(library_name, None)
    else:
        data["patch_scan_cache"] = {}
    _save(data)
