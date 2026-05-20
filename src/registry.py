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
