"""Windows registry operations for Kontakt library entries."""

from pathlib import Path
import winreg

VALUE_NAME = "ContentDir"
REG_ENTRIES = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Native Instruments", "HKLM"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Native Instruments", "HKLM"),
    (winreg.HKEY_CURRENT_USER, r"Software\Native Instruments", "HKCU"),
]


def is_admin() -> bool:
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def list_libraries() -> tuple:
    result: dict[str, str] = {}
    sources: dict[str, list[str]] = {}
    for base_key, reg_path, prefix in REG_ENTRIES:
        try:
            with winreg.OpenKey(base_key, reg_path, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                    except OSError:
                        break
                    try:
                        subkey_full = f"{prefix}\\{reg_path}\\{subkey_name}"
                        with winreg.OpenKey(key, subkey_name, 0, winreg.KEY_READ) as subkey:
                            content_dir, _ = winreg.QueryValueEx(subkey, VALUE_NAME)
                            if content_dir:
                                result[subkey_name] = content_dir
                                sources.setdefault(subkey_name, []).append(subkey_full)
                    except OSError:
                        pass
                    i += 1
        except OSError:
            continue
    return result, sources


def add_library(name: str, content_dir: str,
                hu: str = "", jdx: str = "") -> None:
    success_count = 0
    last_error = None
    for base_key, reg_path, prefix in REG_ENTRIES:
        try:
            with winreg.CreateKey(base_key, f"{reg_path}\\{name}") as key:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, content_dir)
                winreg.SetValueEx(key, "Visibility", 0, winreg.REG_DWORD, 3)
                winreg.SetValueEx(key, "ContentVersion", 0, winreg.REG_SZ, "1.0.0")
                if hu:
                    winreg.SetValueEx(key, "HU", 0, winreg.REG_SZ, hu)
                if jdx:
                    winreg.SetValueEx(key, "JDX", 0, winreg.REG_SZ, jdx)
            success_count += 1
        except OSError as e:
            last_error = e
    if success_count == 0:
        raise OSError(
            f"无法写入注册表。请确认以管理员身份运行。\n{last_error}"
        )


def _delete_key_recursive(base_key: int, sub_path: str) -> None:
    """Delete a registry key and all its subkeys recursively."""
    try:
        with winreg.OpenKey(base_key, sub_path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            while True:
                try:
                    child_name = winreg.EnumKey(key, 0)
                    _delete_key_recursive(base_key, f"{sub_path}\\{child_name}")
                except OSError:
                    break
    except OSError:
        return
    winreg.DeleteKey(base_key, sub_path)


def find_registry_names_by_dir(content_dir: str) -> list[str]:
    """Find all registry key names that have the given ContentDir.

    A library's folder name may differ from its registry key name
    (e.g. folder "Abbey Road 50s Drummer Library", key "Abbey Road 50s Drummer").
    This function resolves the actual key name(s) to use for deletion.
    """
    target = str(Path(content_dir).resolve()).lower() if content_dir else ""
    if not target:
        return []
    names: list[str] = []
    for base_key, reg_path, _ in REG_ENTRIES:
        try:
            with winreg.OpenKey(base_key, reg_path, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                    except OSError:
                        break
                    try:
                        with winreg.OpenKey(key, subkey_name, 0, winreg.KEY_READ) as subkey:
                            cd, _ = winreg.QueryValueEx(subkey, VALUE_NAME)
                            if cd and str(Path(cd).resolve()).lower() == target:
                                if subkey_name not in names:
                                    names.append(subkey_name)
                    except OSError:
                        pass
                    i += 1
        except OSError:
            continue
    return names


def remove_library(name: str) -> list[str]:
    failed: list[str] = []
    for base_key, reg_path, prefix in REG_ENTRIES:
        try:
            _delete_key_recursive(base_key, f"{reg_path}\\{name}")
        except OSError:
            pass
        try:
            with winreg.OpenKey(base_key, f"{reg_path}\\{name}", 0, winreg.KEY_READ):
                failed.append(f"{prefix}\\{reg_path}\\{name}")
        except OSError:
            pass
    return failed


def _is_hex(s: str, expected_len: int = 0) -> bool:
    """Check if string is a hex string of expected length."""
    if not s:
        return False
    if expected_len and len(s) != expected_len:
        return False
    return all(c in "0123456789ABCDEFabcdef" for c in s)


def _is_third_party_presets(content_dir: str) -> bool:
    """Check if path matches known third-party NKS preset patterns."""
    cd = content_dir.lower()
    markers = [
        r"\third party\native instruments\presets",   # Arturia
        r"\universal audio\plug-ins",                 # UAD
        r"\nks",                                       # NKS presets
    ]
    return any(m in cd for m in markers)


def list_kontakt_libraries() -> list[dict]:
    """List all Kontakt libraries from registry using the definitive rule:
    Visibility=3 + HU (32-char hex) + JDX (64-char hex).

    Returns a deduplicated list (by ContentDir) of dicts with keys:
    name, content_dir, snpid, hu, jdx, content_version, visibility, source_paths.
    """
    result: dict[str, dict] = {}  # keyed by normalized content_dir
    for base_key, reg_path, prefix in REG_ENTRIES:
        try:
            with winreg.OpenKey(base_key, reg_path, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                    except OSError:
                        break
                    try:
                        with winreg.OpenKey(key, subkey_name, 0, winreg.KEY_READ) as subkey:
                            values = {}
                            j = 0
                            while True:
                                try:
                                    vn, vd, vt = winreg.EnumValue(subkey, j)
                                    values[vn] = int(vd) if vt == winreg.REG_DWORD else str(vd)
                                    j += 1
                                except OSError:
                                    break

                            cd = values.get("ContentDir", "")
                            vis = values.get("Visibility", 0)
                            hu = values.get("HU", "")
                            jdx = values.get("JDX", "")

                            if not cd:
                                i += 1
                                continue
                            if vis != 3:
                                i += 1
                                continue
                            if not _is_hex(hu, 32):
                                i += 1
                                continue
                            if not _is_hex(jdx, 64):
                                i += 1
                                continue
                            if _is_third_party_presets(cd):
                                i += 1
                                continue

                            normalized = str(Path(cd).resolve()).lower()
                            if normalized in result:
                                result[normalized]["source_paths"].append(
                                    f"{prefix}\\{reg_path}\\{subkey_name}"
                                )
                                # Keep the name with more information (non-Library suffix etc.)
                                existing = result[normalized]
                                if len(subkey_name) > len(existing["name"]):
                                    existing["name"] = subkey_name
                            else:
                                result[normalized] = {
                                    "name": subkey_name,
                                    "content_dir": cd,
                                    "snpid": values.get("SNPID", ""),
                                    "hu": hu,
                                    "jdx": jdx,
                                    "content_version": values.get("ContentVersion", ""),
                                    "visibility": vis,
                                    "source_paths": [f"{prefix}\\{reg_path}\\{subkey_name}"],
                                }
                    except OSError:
                        pass
                    i += 1
        except OSError:
            continue
    return list(result.values())


def read_registry_values(name: str) -> dict:
    """Read all values for a given library name from the registry.

    Returns a dict of {value_name: value, ...} for the first registry path
    that contains the given name. Returns empty dict if not found.
    """
    for base_key, reg_path, _ in REG_ENTRIES:
        try:
            with winreg.OpenKey(base_key, f"{reg_path}\\{name}", 0, winreg.KEY_READ) as key:
                values = {}
                i = 0
                while True:
                    try:
                        val_name, val_data, val_type = winreg.EnumValue(key, i)
                        if val_type == winreg.REG_DWORD:
                            values[val_name] = int(val_data)
                        else:
                            values[val_name] = str(val_data)
                        i += 1
                    except OSError:
                        break
                return values
        except OSError:
            continue
    return {}
