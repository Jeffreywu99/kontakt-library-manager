"""Local data persistence for categories, notes, and library folders.

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
        "library_folders": [],
        "nonstandard_folders": [],
        "categories": [],
        "library_categories": {},
        "library_notes": {},
        "patch_notes": {},
        "patch_scan_cache": {},
        "nonstandard_libraries": [],
        "scan_cache": None,  # v0.5.0: auto-discovered libraries cache
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
        # Migrate old library_roots to library_folders
        if "library_roots" in data and "library_folders" not in data:
            data["library_folders"] = data.pop("library_roots")
        return data
    except (json.JSONDecodeError, OSError):
        return _default_data()


def _save(data: dict) -> None:
    path = _data_file()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---- Library Folders ----

def get_library_folders() -> list[str]:
    data = _load()
    return data.get("library_folders", [])


def add_library_folder(path: str) -> None:
    data = _load()
    normalized = str(Path(path).resolve())
    if normalized not in data["library_folders"]:
        data["library_folders"].append(normalized)
    _save(data)


def remove_library_folder(path: str) -> None:
    data = _load()
    normalized = str(Path(path).resolve())
    if normalized in data["library_folders"]:
        data["library_folders"].remove(normalized)
    _save(data)


# ---- Non-standard Folders ----

def get_nonstandard_folders() -> list[str]:
    data = _load()
    return data.get("nonstandard_folders", [])


def add_nonstandard_folder(path: str) -> None:
    data = _load()
    normalized = str(Path(path).resolve())
    if normalized not in data.get("nonstandard_folders", []):
        data.setdefault("nonstandard_folders", []).append(normalized)
    _save(data)


def remove_nonstandard_folder(path: str) -> None:
    data = _load()
    normalized = str(Path(path).resolve())
    if normalized in data.get("nonstandard_folders", []):
        data["nonstandard_folders"].remove(normalized)
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


# ---- Non-standard Libraries ----

def get_nonstandard_libraries() -> list[dict]:
    data = _load()
    return data.get("nonstandard_libraries", [])


def add_nonstandard_library(name: str, path: str, categories: list[str] | None = None, notes: str = "") -> None:
    data = _load()
    lib = {
        "name": name,
        "path": path,
        "categories": categories or [],
        "notes": notes,
    }
    # Check if already exists by path
    existing = [l for l in data["nonstandard_libraries"] if l.get("path") == path]
    if existing:
        # Update existing
        existing[0].update(lib)
    else:
        data["nonstandard_libraries"].append(lib)
    _save(data)


def update_nonstandard_library(path: str, name: str | None = None, categories: list[str] | None = None, notes: str | None = None) -> None:
    data = _load()
    for lib in data["nonstandard_libraries"]:
        if lib.get("path") == path:
            if name is not None:
                lib["name"] = name
            if categories is not None:
                lib["categories"] = categories
            if notes is not None:
                lib["notes"] = notes
            break
    _save(data)


def remove_nonstandard_library(path: str) -> None:
    data = _load()
    data["nonstandard_libraries"] = [l for l in data["nonstandard_libraries"] if l.get("path") != path]
    _save(data)


# ---- Scan Cache (v0.5.0 auto-discovery) ----

def get_scan_cache() -> dict | None:
    """Return cached scan result or None if no cache exists."""
    data = _load()
    return data.get("scan_cache")


def save_scan_cache(cache: dict) -> None:
    """Save scan result cache (overwrites previous)."""
    data = _load()
    data["scan_cache"] = cache
    _save(data)


def clear_scan_cache() -> None:
    """Clear scan cache, forcing a full re-scan on next refresh."""
    data = _load()
    data["scan_cache"] = None
    _save(data)
