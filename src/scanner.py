"""扫描用户指定的音色库文件夹。"""

from pathlib import Path
from src.models import LibraryEntry, PatchEntry
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
