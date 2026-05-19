from dataclasses import dataclass, field


@dataclass
class LibraryEntry:
    name: str
    content_dir: str
    snpid: str = ""
    found_in_registry: bool = False
    found_in_xml: bool = False
    found_in_json: bool = False
    exists_on_disk: bool = True
    is_kontakt_library: bool = True
    library_type: str = ""  # "standard", "nonstandard", or "registry"
    categories: list = field(default_factory=list)
    notes: str = ""
    hidden: bool = False
    registry_paths: list[str] = field(default_factory=list)
    xml_path: str = ""
    json_path: str = ""


@dataclass
class PatchEntry:
    name: str
    file_path: str
    library_name: str
    folder: str = ""
    size_mb: float = 0.0
    notes: str = ""
