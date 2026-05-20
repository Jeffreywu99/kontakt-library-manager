"""Windows registry operations for Kontakt library entries.

Manipulates subkeys under:
  - HKLM\\SOFTWARE\\Native Instruments\\
  - HKLM\\SOFTWARE\\WOW6432Node\\Native Instruments\\
  - HKCU\\Software\\Native Instruments\\
"""

import winreg

VALUE_NAME = "ContentDir"

# (base_key, sub_path, display_prefix)
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
                        subkey_full = f"{prefix}\\{reg_path}\\{subkey_name}"
                        with winreg.OpenKey(key, subkey_name, 0, winreg.KEY_READ) as subkey:
                            content_dir, _ = winreg.QueryValueEx(subkey, VALUE_NAME)
                            if content_dir:
                                result[subkey_name] = content_dir
                                sources.setdefault(subkey_name, []).append(subkey_full)
                        i += 1
                    except OSError:
                        break
        except OSError:
            continue
    return result, sources


def add_library(name: str, content_dir: str) -> None:
    last_error = None
    for base_key, reg_path, _ in REG_ENTRIES:
        try:
            with winreg.CreateKey(base_key, f"{reg_path}\\{name}") as key:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, content_dir)
        except OSError as e:
            last_error = e
    if last_error:
        raise OSError(
            f"无法写入注册表（部分路径可能失败）。请确认以管理员身份运行。\n{last_error}"
        )


def remove_library(name: str) -> list[str]:
    failed: list[str] = []
    for base_key, reg_path, prefix in REG_ENTRIES:
        try:
            winreg.DeleteKey(base_key, f"{reg_path}\\{name}")
        except OSError:
            pass
        else:
            continue
        try:
            with winreg.OpenKey(base_key, f"{reg_path}\\{name}", 0, winreg.KEY_READ):
                failed.append(f"{prefix}\\{reg_path}\\{name}")
        except OSError:
            pass
    return failed


def list_hkcu_display_entries() -> list[str]:
    """Get HKCU entries that have UserListIndex (library display prefs, not ContentDir)."""
    entries = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Native Instruments", 0, winreg.KEY_READ) as key:
            i = 0
            while True:
                try:
                    name = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, name, 0, winreg.KEY_READ) as subkey:
                        try:
                            winreg.QueryValueEx(subkey, "UserListIndex")
                            entries.append(name)
                        except OSError:
                            pass
                    i += 1
                except OSError:
                    break
    except OSError:
        pass
    return entries


# Known NI application names — never clean these from HKCU
_NI_APPS = {
    "kontakt 5", "kontakt 6", "kontakt 7", "kontakt 8",
    "kontakt factory library", "kontakt factory library 2",
    "battery 4", "massive", "massive x", "fm8",
    "guitar rig 6", "guitar rig 7", "super 8", "super 8 r2",
    "native access", "shared", "alsupport", "reaktor", "reaktor 6",
    "absynth", "absynth 5", "service center", "service center 2",
}


def cleanup_stale_hkcu(known_library_names: set[str]) -> int:
    """Delete HKCU display entries for libraries that no longer exist in HKLM.
    Skips known NI application names. Returns number of cleaned entries."""
    hkcu_entries = list_hkcu_display_entries()
    cleaned = 0
    for name in hkcu_entries:
        if name not in known_library_names and name.lower() not in _NI_APPS:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                                 f"Software\\Native Instruments\\{name}")
                cleaned += 1
            except OSError:
                pass
    return cleaned
