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


def add_library(name: str, content_dir: str, snpid: str = "",
                hu: str = "", jdx: str = "") -> None:
    success_count = 0
    last_error = None
    for base_key, reg_path, prefix in REG_ENTRIES:
        try:
            with winreg.CreateKey(base_key, f"{reg_path}\\{name}") as key:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, content_dir)
                winreg.SetValueEx(key, "Visibility", 0, winreg.REG_DWORD, 3)
                winreg.SetValueEx(key, "ContentVersion", 0, winreg.REG_SZ, "1.0.0")
                if snpid:
                    winreg.SetValueEx(key, "SNPID", 0, winreg.REG_SZ, snpid)
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
