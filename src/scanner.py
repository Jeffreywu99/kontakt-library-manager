"""扫描所有数据源，只返回已注册的库。

核心理念：入库即显示，删除即消失。
只显示在注册表/XML/JSON 中有记录的库。
"""

import re
from pathlib import Path
from src.models import LibraryEntry, PatchEntry
from src.registry import list_libraries as list_registry_libraries
from src.files import list_from_xml, list_from_json
from src.storage import (
    get_library_folders,
    get_library_categories,
    get_library_notes,
    get_patch_notes,
    get_patch_cache,
    set_patch_cache,
)


def _extract_nicnt_info(folder: Path) -> dict:
    """Extract metadata from .nicnt file in the library folder.

    Returns dict with keys: snpid, upid, hu, jdx, company, auth_system, powered_by, regkey, name.
    Missing fields are empty strings.
    """
    result = {
        "snpid": "", "upid": "", "hu": "", "jdx": "",
        "company": "", "auth_system": "", "powered_by": "",
        "regkey": "", "name": "",
    }
    for nicnt in folder.glob("*.nicnt"):
        try:
            data = nicnt.read_bytes()
            start = data.find(b"<?xml")
            if start < 0:
                start = data.find(b"<ProductHints")
            if start < 0:
                continue
            end = data.find(b"</ProductHints>", start)
            if end < 0:
                continue
            xml_text = data[start:end + len(b"</ProductHints>")].decode("utf-8", errors="replace")
            for tag, key in [
                ("SNPID", "snpid"), ("UPID", "upid"),
                ("HU", "hu"), ("JDX", "jdx"),
                ("Company", "company"), ("AuthSystem", "auth_system"),
                ("PoweredBy", "powered_by"), ("RegKey", "regkey"),
                ("Name", "name"),
            ]:
                m = re.search(f"<{tag}[^>]*>(.*?)</{tag}>", xml_text)
                if m and m.group(1).strip():
                    result[key] = m.group(1).strip()
            break
        except OSError:
            continue
    return result


def _dir_has_kontakt_content(p: Path) -> bool:
    dirs_to_check = [p]
    parent = p.parent
    if parent != p:
        dirs_to_check.append(parent)
    for d in dirs_to_check:
        if (bool(list(d.glob("*.nicnt"))) or
            bool(list(d.glob("*.nki"))) or
            bool(list(d.glob("*.nkx")))):
            return True
    return False


def _get_registered_map() -> tuple[dict, dict, dict, dict, dict, dict]:
    """Collect all registered libraries from registry, XML, JSON.

    Returns: (registry_map, reg_sources, xml_data, xml_sources, json_data, json_sources)
    - registry_map: {name: content_dir}
    - reg_sources: {name: [registry_paths...]}
    - xml_data: {name: {content_dir, snpid, ...}}
    - xml_sources: {name: xml_file_path}
    - json_data: {name: {content_dir, snpid, ...}}
    - json_sources: {name: json_file_path}
    """
    registry_map, reg_sources = list_registry_libraries()
    xml_data, xml_sources = list_from_xml()
    json_data, json_sources = list_from_json()
    return registry_map, reg_sources, xml_data, xml_sources, json_data, json_sources


def _build_registered_entry(
    name: str,
    registry_map: dict,
    reg_sources: dict,
    xml_data: dict,
    xml_sources: dict,
    json_data: dict,
    json_sources: dict,
) -> LibraryEntry | None:
    """Build a LibraryEntry from registration data."""
    content_dir = ""
    snpid = ""
    found_reg = name in registry_map
    found_xml = name in xml_data
    found_json = name in json_data

    if found_xml:
        content_dir = xml_data[name].get("content_dir", "")
        snpid = xml_data[name].get("snpid", "")
    if not content_dir and found_json:
        content_dir = json_data[name].get("content_dir", "")
        if not snpid:
            snpid = json_data[name].get("snpid", "")
    if not content_dir and found_reg:
        content_dir = registry_map[name]

    if not content_dir:
        return None

    exists = Path(content_dir).is_dir() if content_dir else False
    has_content = _dir_has_kontakt_content(Path(content_dir)) if exists else True

    return LibraryEntry(
        name=name,
        content_dir=content_dir,
        snpid=snpid,
        found_in_registry=found_reg,
        found_in_xml=found_xml,
        found_in_json=found_json,
        exists_on_disk=exists,
        is_kontakt_library=has_content,
        categories=get_library_categories(name),
        notes=get_library_notes(name),
        registry_paths=reg_sources.get(name, []),
        xml_path=xml_sources.get(name, ""),
        json_path=json_sources.get(name, ""),
    )


def scan_all() -> list[LibraryEntry]:
    """Scan all registered libraries.

    Returns only libraries that have registration info (registry/XML/JSON).
    Libraries in library_folders without registration are not shown.
    """
    results: list[LibraryEntry] = []
    seen_dirs: set[str] = set()

    # Get all registration data
    registry_map, reg_sources, xml_data, xml_sources, json_data, json_sources = _get_registered_map()

    # Collect all unique names from registration sources
    all_names = set()
    all_names.update(registry_map.keys())
    all_names.update(xml_data.keys())
    all_names.update(json_data.keys())

    # Build entries for all registered libraries
    for name in all_names:
        entry = _build_registered_entry(
            name, registry_map, reg_sources, xml_data, xml_sources, json_data, json_sources
        )
        if entry is None:
            continue
        normalized = str(Path(entry.content_dir).resolve()) if entry.content_dir else ""
        if normalized and normalized in seen_dirs:
            continue
        if normalized:
            seen_dirs.add(normalized)
        results.append(entry)

    results.sort(key=lambda e: e.name.lower())
    return results


def scan_patches(library_name: str, content_dir: str) -> list[PatchEntry]:
    cached = get_patch_cache(library_name)
    if cached is not None:
        patches = []
        for p in cached["patches"]:
            entry = PatchEntry(
                name=p.get("name", ""), file_path=p.get("file_path", ""),
                library_name=p.get("library_name", library_name),
                folder=p.get("folder", ""), size_mb=p.get("size_mb", 0.0),
                notes=get_patch_notes(p.get("file_path", "")),
            )
            patches.append(entry)
        return patches

    lib_path = Path(content_dir)
    if not lib_path.is_dir():
        return []

    patches: list[PatchEntry] = []
    for nki_path in lib_path.rglob("*.nki"):
        if nki_path.is_file():
            try:
                size_mb = nki_path.stat().st_size / (1024 * 1024)
            except OSError:
                size_mb = 0.0
            relative = nki_path.relative_to(lib_path)
            folder = str(relative.parent) if str(relative.parent) != "." else ""
            entry = PatchEntry(
                name=nki_path.stem, file_path=str(nki_path),
                library_name=library_name, folder=folder,
                size_mb=round(size_mb, 1),
                notes=get_patch_notes(str(nki_path)),
            )
            patches.append(entry)

    cache_data = [
        {"name": p.name, "file_path": p.file_path, "library_name": p.library_name,
         "folder": p.folder, "size_mb": p.size_mb}
        for p in patches
    ]
    set_patch_cache(library_name, cache_data)
    return patches
