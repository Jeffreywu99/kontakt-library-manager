"""扫描用户目录中的音色库。

核心理念：只显示用户添加的目录中的库。
- 标准库目录：有 .nicnt 且有注册信息的子文件夹
- 非标准库目录：所有子文件夹（无 .nicnt）
"""

import re
from pathlib import Path
from src.models import LibraryEntry, PatchEntry
from src.registry import list_libraries as list_registry_libraries
from src.files import list_from_xml, list_from_json
from src.storage import (
    get_library_folders,
    get_nonstandard_folders,
    get_library_categories,
    get_library_notes,
    get_patch_notes,
    get_patch_cache,
    set_patch_cache,
    get_nonstandard_libraries,
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


def _get_registration_info() -> tuple[dict, dict, dict, dict, dict, dict]:
    """Get all registration data from registry, XML, JSON."""
    registry_map, reg_sources = list_registry_libraries()
    xml_data, xml_sources = list_from_xml()
    json_data, json_sources = list_from_json()
    return registry_map, reg_sources, xml_data, xml_sources, json_data, json_sources


def _find_registered_library_by_dir(content_dir: str, registry_map: dict, reg_sources: dict,
                                     xml_data: dict, xml_sources: dict, json_data: dict, json_sources: dict) -> LibraryEntry | None:
    """Find registration info for a library by its content directory."""
    target = str(Path(content_dir).resolve()).lower() if content_dir else ""
    if not target:
        return None

    # Find by content_dir in registration data
    found_name = None
    for name, cd in registry_map.items():
        if cd and str(Path(cd).resolve()).lower() == target:
            found_name = name
            break
    if not found_name:
        for name, info in xml_data.items():
            cd = info.get("content_dir", "")
            if cd and str(Path(cd).resolve()).lower() == target:
                found_name = name
                break
    if not found_name:
        for name, info in json_data.items():
            cd = info.get("content_dir", "")
            if cd and str(Path(cd).resolve()).lower() == target:
                found_name = name
                break

    if not found_name:
        return None

    # Build entry with registration info
    snpid = ""
    if found_name in xml_data:
        snpid = xml_data[found_name].get("snpid", "")
    if not snpid and found_name in json_data:
        snpid = json_data[found_name].get("snpid", "")

    return LibraryEntry(
        name=found_name,
        content_dir=content_dir,
        snpid=snpid,
        found_in_registry=found_name in registry_map,
        found_in_xml=found_name in xml_data,
        found_in_json=found_name in json_data,
        exists_on_disk=True,
        is_kontakt_library=True,
        is_nonstandard=False,
        categories=get_library_categories(found_name),
        notes=get_library_notes(found_name),
        registry_paths=reg_sources.get(found_name, []),
        xml_path=xml_sources.get(found_name, ""),
        json_path=json_sources.get(found_name, ""),
    )


def _scan_standard_folders(registry_map: dict, reg_sources: dict,
                           xml_data: dict, xml_sources: dict, json_data: dict, json_sources: dict) -> list[LibraryEntry]:
    """Scan standard library folders for registered Kontakt libraries."""
    results = []
    seen_dirs = set()

    for folder_path in get_library_folders():
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

            # Check if has Kontakt content
            if not _dir_has_kontakt_content(subfolder):
                continue

            # Find registration info
            entry = _find_registered_library_by_dir(
                str(subfolder), registry_map, reg_sources, xml_data, xml_sources, json_data, json_sources
            )
            if entry:
                results.append(entry)

    return results


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

            # Skip if has Kontakt content (should be in standard folder)
            if _dir_has_kontakt_content(subfolder):
                continue

            # Get saved info or use defaults
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
    """Scan all libraries from user-configured folders.

    Standard folders: registered Kontakt libraries with .nicnt
    Non-standard folders: third-party sample libraries without .nicnt
    """
    registry_map, reg_sources, xml_data, xml_sources, json_data, json_sources = _get_registration_info()

    standard = _scan_standard_folders(registry_map, reg_sources, xml_data, xml_sources, json_data, json_sources)
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
