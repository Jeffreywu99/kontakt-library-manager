"""Scan for Kontakt libraries.

v0.5.0: registry-driven auto-discovery with incremental caching.
First launch: auto-discovers ALL registered Kontakt libraries from registry.
Subsequent: quick registry re-scan, diffs against cache for changes.
Non-standard libraries: still folder-based (no registry entries).
"""

import re
from pathlib import Path
from datetime import datetime, timezone
from src.models import LibraryEntry, PatchEntry
from src.registry import list_kontakt_libraries
from src.files import list_from_xml, list_from_json
from src.storage import (
    get_library_folders,
    add_library_folder,
    get_nonstandard_folders,
    get_library_categories,
    get_library_notes,
    get_patch_notes,
    get_patch_cache,
    set_patch_cache,
    get_nonstandard_libraries,
    get_scan_cache,
    save_scan_cache,
)


def _extract_nicnt_info(folder: Path) -> dict:
    """Extract metadata from .nicnt file in the library folder."""
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
    """Check if folder has Kontakt content (.nicnt, .nki, or .nkx)."""
    try:
        return bool(list(p.glob("*.nicnt"))) or bool(list(p.glob("*.nki"))) or bool(list(p.glob("*.nkx")))
    except OSError:
        return False


def _resolve_display_name(reg_name: str, content_dir: str) -> str:
    """Resolve the best display name from .nicnt if available.

    Registry key names often differ from the actual library name on disk.
    .nicnt <Name> field has the official display name.
    """
    folder = Path(content_dir)
    if folder.is_dir():
        info = _extract_nicnt_info(folder)
        if info.get("name"):
            return info["name"]
    return reg_name


def _extract_auto_folders(entries: list[LibraryEntry]) -> list[str]:
    """Extract parent directories from discovered libraries as auto-folders."""
    folders = set()
    for entry in entries:
        parent = str(Path(entry.content_dir).parent.resolve())
        folders.add(parent)
    return sorted(folders)


def _build_library_entry(reg_info: dict, xml_data: dict, json_data: dict,
                         xml_sources: dict, json_sources: dict) -> LibraryEntry:
    """Build a LibraryEntry from registry discovery info, enriched with XML/JSON data."""
    reg_name = reg_info["name"]
    content_dir = reg_info["content_dir"]

    display_name = _resolve_display_name(reg_name, content_dir)

    snpid = reg_info.get("snpid", "")
    if not snpid:
        for name, info in xml_data.items():
            cd = info.get("content_dir", "")
            if cd and str(Path(cd).resolve()).lower() == str(Path(content_dir).resolve()).lower():
                snpid = info.get("snpid", "")
                break
    if not snpid:
        for name, info in json_data.items():
            cd = info.get("content_dir", "")
            if cd and str(Path(cd).resolve()).lower() == str(Path(content_dir).resolve()).lower():
                snpid = info.get("snpid", "")
                break

    found_in_xml = False
    xml_path = ""
    for name, info in xml_data.items():
        cd = info.get("content_dir", "")
        if cd and str(Path(cd).resolve()).lower() == str(Path(content_dir).resolve()).lower():
            found_in_xml = True
            xml_path = xml_sources.get(name, "")
            break

    found_in_json = False
    json_path = ""
    for name, info in json_data.items():
        cd = info.get("content_dir", "")
        if cd and str(Path(cd).resolve()).lower() == str(Path(content_dir).resolve()).lower():
            found_in_json = True
            json_path = json_sources.get(name, "")
            break

    exists_on_disk = Path(content_dir).is_dir()

    return LibraryEntry(
        name=display_name,
        content_dir=content_dir,
        snpid=snpid,
        hu=reg_info.get("hu", ""),
        jdx=reg_info.get("jdx", ""),
        reg_name=reg_name,
        found_in_registry=True,
        found_in_xml=found_in_xml,
        found_in_json=found_in_json,
        exists_on_disk=exists_on_disk,
        is_kontakt_library=True,
        is_nonstandard=False,
        categories=get_library_categories(display_name),
        notes=get_library_notes(display_name),
        registry_paths=reg_info.get("source_paths", []),
        xml_path=xml_path,
        json_path=json_path,
    )


def auto_discover_all() -> list[LibraryEntry]:
    """Full auto-discovery from registry.

    Scans the entire registry for Kontakt libraries (Visibility=3 + HU + JDX),
    enriches with XML/JSON data, auto-saves discovered library folders,
    and caches the result for future incremental scans.
    """
    reg_libraries = list_kontakt_libraries()
    xml_data, xml_sources = list_from_xml()
    json_data, json_sources = list_from_json()

    entries: list[LibraryEntry] = []
    for reg_info in reg_libraries:
        entry = _build_library_entry(reg_info, xml_data, json_data, xml_sources, json_sources)
        entries.append(entry)

    entries.sort(key=lambda e: e.name.lower())

    # Auto-save discovered library folders
    auto_folders = _extract_auto_folders(entries)
    for folder in auto_folders:
        add_library_folder(folder)

    # Save scan cache
    cache = {
        "last_full_scan": datetime.now(timezone.utc).isoformat(),
        "libraries": [
            {
                "name": e.name,
                "reg_name": e.reg_name,
                "content_dir": e.content_dir,
                "snpid": e.snpid,
                "hu": e.hu,
                "jdx": e.jdx,
            }
            for e in entries
        ],
        "auto_folders": auto_folders,
    }
    save_scan_cache(cache)

    return entries


def scan_incremental() -> list[LibraryEntry]:
    """Incremental scan: compare current registry against cache.

    Detects new libraries (found in registry but not in cache) and
    removed libraries (in cache but no longer in registry).
    Updates the cache with the new state.
    """
    cached = get_scan_cache()
    if not cached or not cached.get("libraries"):
        return auto_discover_all()

    cached_libs: dict[str, dict] = {}
    for lib in cached.get("libraries", []):
        cd = lib.get("content_dir", "")
        if cd:
            cached_libs[str(Path(cd).resolve()).lower()] = lib

    reg_libraries = list_kontakt_libraries()
    xml_data, xml_sources = list_from_xml()
    json_data, json_sources = list_from_json()

    current_dirs: set[str] = set()
    entries: list[LibraryEntry] = []
    new_count = 0

    for reg_info in reg_libraries:
        entry = _build_library_entry(reg_info, xml_data, json_data, xml_sources, json_sources)
        entries.append(entry)
        cd = str(Path(reg_info["content_dir"]).resolve()).lower()
        current_dirs.add(cd)
        if cd not in cached_libs:
            new_count += 1

    removed_count = len(cached_libs) - len([cd for cd in cached_libs if cd in current_dirs])

    entries.sort(key=lambda e: e.name.lower())

    # Update cache if there were changes
    if new_count > 0 or removed_count > 0:
        auto_folders = _extract_auto_folders(entries)
        for folder in auto_folders:
            add_library_folder(folder)
        cache = {
            "last_full_scan": datetime.now(timezone.utc).isoformat(),
            "last_changes": {
                "new": new_count,
                "removed": removed_count,
            },
            "libraries": [
                {
                    "name": e.name,
                    "reg_name": e.reg_name,
                    "content_dir": e.content_dir,
                    "snpid": e.snpid,
                    "hu": e.hu,
                    "jdx": e.jdx,
                }
                for e in entries
            ],
            "auto_folders": auto_folders,
        }
        save_scan_cache(cache)

    return entries


def _scan_nonstandard_folders() -> list[LibraryEntry]:
    """Scan non-standard library folders for third-party sample libraries."""
    results = []
    seen_dirs = set()
    saved_libs = {lib.get("path"): lib for lib in get_nonstandard_libraries()}

    for folder_path in get_nonstandard_folders():
        folder = Path(folder_path)
        if not folder.is_dir():
            continue

        for subfolder in folder.iterdir():
            if not subfolder.is_dir():
                continue

            normalized = str(subfolder.resolve())
            if normalized in seen_dirs:
                continue
            seen_dirs.add(normalized)

            # Skip if has Kontakt content (should be in standard library)
            if _dir_has_kontakt_content(subfolder):
                continue

            saved = saved_libs.get(normalized, {})
            name = saved.get("name", subfolder.name)
            categories = saved.get("categories", [])
            notes = saved.get("notes", "")

            entry = LibraryEntry(
                name=name,
                content_dir=normalized,
                snpid="",
                found_in_registry=False,
                found_in_xml=False,
                found_in_json=False,
                exists_on_disk=True,
                is_kontakt_library=False,
                is_nonstandard=True,
                categories=categories,
                notes=notes,
                registry_paths=[],
                xml_path="",
                json_path="",
            )
            results.append(entry)

    return results


def scan_all() -> list[LibraryEntry]:
    """Scan all libraries — auto-discovery or incremental + nonstandard.

    On first launch (no cache), performs a full auto-discovery from registry.
    On subsequent launches, does incremental comparison.
    Non-standard libraries are always scanned from configured folders.
    """
    cached = get_scan_cache()

    if cached and cached.get("libraries"):
        standard = scan_incremental()
    else:
        standard = auto_discover_all()

    nonstandard = _scan_nonstandard_folders()
    results = standard + nonstandard
    results.sort(key=lambda e: e.name.lower())
    return results


def scan_patches(library_name: str, content_dir: str) -> list[PatchEntry]:
    """Scan .nki files in a library folder."""
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
