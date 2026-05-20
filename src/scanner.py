"""扫描所有数据源并合并为统一库列表。"""

from pathlib import Path
from src.models import LibraryEntry, PatchEntry
from src.registry import list_libraries as list_registry_libraries
from src.files import list_from_xml, list_from_json
from src.storage import (
    get_library_roots,
    get_custom_libraries,
    get_library_categories,
    get_library_notes,
    get_patch_notes,
    get_patch_cache,
    set_patch_cache,
    is_hidden,
)


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


def _scan_root_folder(root_path: str, root_type: str) -> list[LibraryEntry]:
    results: list[LibraryEntry] = []
    root = Path(root_path)
    if not root.is_dir():
        return results
    for subfolder in sorted(root.iterdir()):
        if not subfolder.is_dir():
            continue
        name = subfolder.name
        content_dir = str(subfolder)
        has_content = _dir_has_kontakt_content(subfolder)
        if root_type == "standard" and not has_content:
            continue
        entry = LibraryEntry(
            name=name, content_dir=content_dir,
            exists_on_disk=True, is_kontakt_library=has_content,
            library_type=root_type,
            categories=get_library_categories(name),
            notes=get_library_notes(name), hidden=is_hidden(name),
        )
        results.append(entry)
    return results


def _scan_custom_libraries() -> list[LibraryEntry]:
    results: list[LibraryEntry] = []
    for custom in get_custom_libraries():
        name = custom.get("name", "")
        path_str = custom.get("path", "")
        if not name or not path_str:
            continue
        p = Path(path_str)
        exists = p.is_dir()
        has_content = _dir_has_kontakt_content(p) if exists else False
        entry = LibraryEntry(
            name=name, content_dir=path_str,
            exists_on_disk=exists, is_kontakt_library=has_content,
            library_type="nonstandard",
            categories=get_library_categories(name),
            notes=get_library_notes(name), hidden=is_hidden(name),
        )
        results.append(entry)
    return results


def _scan_registry_libraries(
    existing_paths, reg_sources, xml_sources, json_sources,
    registry_map, xml_data, json_data,
) -> list[LibraryEntry]:
    results: list[LibraryEntry] = []
    all_names = set()
    all_names.update(registry_map.keys())
    all_names.update(xml_data.keys())
    all_names.update(json_data.keys())

    for name in all_names:
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

        if not (found_xml or found_json):
            continue
        if not content_dir:
            continue

        normalized = str(Path(content_dir).resolve()) if content_dir else ""

        exists = Path(content_dir).is_dir() if content_dir else False
        has_content = _dir_has_kontakt_content(Path(content_dir)) if exists else True

        entry = LibraryEntry(
            name=name, content_dir=content_dir, snpid=snpid,
            found_in_registry=found_reg, found_in_xml=found_xml,
            found_in_json=found_json, exists_on_disk=exists,
            is_kontakt_library=has_content, library_type="registry",
            categories=get_library_categories(name),
            notes=get_library_notes(name), hidden=is_hidden(name),
            registry_paths=reg_sources.get(name, []),
            xml_path=xml_sources.get(name, ""),
            json_path=json_sources.get(name, ""),
        )
        results.append(entry)
    return results


def scan_all() -> list[LibraryEntry]:
    results: list[LibraryEntry] = []
    existing_paths = set()

    for root in get_library_roots():
        root_path = root.get("path", "")
        root_type = root.get("type", "standard")
        if root_path:
            for lib in _scan_root_folder(root_path, root_type):
                normalized = str(Path(lib.content_dir).resolve())
                if normalized not in existing_paths:
                    results.append(lib)
                    existing_paths.add(normalized)

    for lib in _scan_custom_libraries():
        normalized = str(Path(lib.content_dir).resolve())
        if normalized not in existing_paths:
            results.append(lib)
            existing_paths.add(normalized)

    registry_map, reg_sources = list_registry_libraries()
    xml_data, xml_sources = list_from_xml()
    json_data, json_sources = list_from_json()
    reg_libs = _scan_registry_libraries(
        existing_paths, reg_sources, xml_sources, json_sources,
        registry_map, xml_data, json_data,
    )
    for lib in reg_libs:
        normalized = str(Path(lib.content_dir).resolve()) if lib.content_dir else ""
        if normalized not in existing_paths:
            results.append(lib)
            existing_paths.add(normalized)
        else:
            # Merge registry/XML/JSON info into existing folder entry
            for existing in results:
                existing_norm = str(Path(existing.content_dir).resolve()) if existing.content_dir else ""
                if existing_norm == normalized:
                    existing.found_in_registry = lib.found_in_registry
                    existing.found_in_xml = lib.found_in_xml
                    existing.found_in_json = lib.found_in_json
                    existing.registry_paths = lib.registry_paths
                    existing.xml_path = lib.xml_path
                    existing.json_path = lib.json_path
                    existing.snpid = lib.snpid
                    break

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
