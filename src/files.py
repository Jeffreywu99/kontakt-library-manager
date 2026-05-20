"""XML and JSON file operations for Kontakt library metadata.

Handles:
  - XML files in C:\\Program Files\\Common Files\\Native Instruments\\Service Center\\
  - JSON files in C:\\Users\\Public\\Documents\\Native Instruments\\installed_products\\
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

XML_DIR = Path(r"C:\Program Files\Common Files\Native Instruments\Service Center")
JSON_DIR = Path(r"C:\Users\Public\Documents\Native Instruments\installed_products")

XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<ProductHints>
  <Product version="3">
    <UPID>{upid}</UPID>
    <Name>{name}</Name>
    <Type>Content</Type>
    <RegKey>{name}</RegKey>
    <SNPID>{snpid}</SNPID>
    <AuthSystem>{auth_system}</AuthSystem>
    <Relevance>
      <Application minVersion="5" nativeContent="true">Kontakt</Application>
    </Relevance>
    <PoweredBy>{powered_by}</PoweredBy>
    <Visibility>0x07</Visibility>
    <ProductSpecific>
      <HU>{hu}</HU>
      <JDX>{jdx}</JDX>
      <Visibility type="Number">3</Visibility>
    </ProductSpecific>
    <Company>{company}</Company>
    <ContentDir>{content_dir}</ContentDir>
  </Product>
</ProductHints>"""

SANITIZE_CHARS = str.maketrans({c: "_" for c in '<>:"/\\|?*'})


def _safe_filename(name: str) -> str:
    return name.translate(SANITIZE_CHARS).strip()


def list_from_xml() -> tuple[dict[str, dict], dict[str, str]]:
    """Return (name->{snpid, content_dir}, name->xml_file_path)."""
    result: dict[str, dict] = {}
    sources: dict[str, str] = {}
    if not XML_DIR.is_dir():
        return result, sources
    for xml_file in XML_DIR.glob("*.xml"):
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            product = root.find("Product")
            if product is None:
                continue
            name_el = product.find("Name")
            cd_el = product.find("ContentDir")
            snpid_el = product.find("SNPID")
            if name_el is not None and name_el.text:
                name = name_el.text.strip()
                entry: dict = {"snpid": "", "content_dir": ""}
                if snpid_el is not None and snpid_el.text:
                    entry["snpid"] = snpid_el.text.strip()
                if cd_el is not None and cd_el.text:
                    entry["content_dir"] = cd_el.text.strip()
                result[name] = entry
                sources[name] = str(xml_file)
        except (ET.ParseError, OSError):
            continue
    return result, sources


def list_from_json() -> tuple[dict[str, dict], dict[str, str]]:
    """Return (name->{snpid, content_dir}, name->json_file_path)."""
    result: dict[str, dict] = {}
    sources: dict[str, str] = {}
    if not JSON_DIR.is_dir():
        return result, sources
    for json_file in JSON_DIR.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = data.get("Name", json_file.stem)
            entry: dict = {"snpid": data.get("SNPID", ""), "content_dir": ""}
            cd = data.get("ContentDir", data.get("content_dir", ""))
            if cd:
                entry["content_dir"] = cd
            result[name] = entry
            sources[name] = str(json_file)
        except (json.JSONDecodeError, OSError):
            continue
    return result, sources


def create_xml(name: str, content_dir: str, snpid: str = "",
               upid: str = "", hu: str = "", jdx: str = "",
               company: str = "", auth_system: str = "",
               powered_by: str = "") -> Path:
    XML_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(name)
    xml_path = XML_DIR / f"{safe_name}.xml"
    xml_content = XML_TEMPLATE.format(
        upid=upid or snpid or name,
        name=name,
        snpid=snpid or "000",
        auth_system=auth_system or "RAS2",
        powered_by=powered_by or "Kontakt",
        hu=hu or "0" * 32,
        jdx=jdx or "0" * 64,
        company=company or "Unknown",
        content_dir=content_dir,
    )
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml_content)
    return xml_path


def create_json(name: str, content_dir: str, snpid: str = "") -> Path:
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    json_path = JSON_DIR / f"{name}.json"
    data: dict = {
        "ContentDir": content_dir,
        "ContentVersion": "1.0.0",
    }
    if snpid:
        data["SNPID"] = snpid
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return json_path


def remove_xml(name: str) -> bool:
    safe_name = _safe_filename(name)
    xml_path = XML_DIR / f"{safe_name}.xml"
    try:
        xml_path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def remove_json(name: str) -> bool:
    json_path = JSON_DIR / f"{name}.json"
    try:
        json_path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def find_json_by_content_dir(content_dir: str) -> str:
    """Find JSON file whose ContentDir matches the given path.

    Returns the file path of the matching JSON, or empty string.
    """
    target = str(Path(content_dir).resolve()).lower() if content_dir else ""
    if not target or not JSON_DIR.is_dir():
        return ""
    for json_file in JSON_DIR.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            cd = data.get("ContentDir", data.get("content_dir", ""))
            if cd and str(Path(cd).resolve()).lower() == target:
                return str(json_file)
        except (json.JSONDecodeError, OSError):
            continue
    return ""
