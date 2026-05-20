# Kontakt Library Manager

Windows 桌面应用，管理 Kontakt 8 音色库（BobDule 版本）。

## 技术栈

- Python 3.12 + PySide6
- 入口：`main.pyw`（pythonw 启动，无控制台）
- 打包：PyInstaller + Inno Setup

## 项目结构

```
kontakt-library-manager/
├── main.pyw                  # 入口 + 暗色主题 CSS + 应用级事件过滤器
├── requirements.txt          # PySide6>=6.5.0
├── CHANGELOG.md
├── CLAUDE.md
├── setup.iss                 # Inno Setup 安装包脚本
├── icons/                    # SVG 源文件 + ICO + PNG
├── dist/                     # 构建输出（exe + 安装包）
└── src/
    ├── models.py             # LibraryEntry, PatchEntry 数据类
    ├── storage.py            # 本地 JSON 持久化（分类/备注/缓存/隐藏/根文件夹）
    ├── registry.py           # Windows 注册表读写（winreg）
    ├── files.py              # Service Center XML + installed_products JSON
    ├── scanner.py            # 扫描 + 合并 + .nki 文件扫描
    ├── manager.py            # 业务逻辑外观层（纯 Python，无 Qt 依赖）
    └── ui/
        ├── main_window.py    # 主窗口（三栏布局）
        ├── add_dialog.py     # 添加音色库对话框
        ├── batch_add_dialog.py # 批量入库对话框
        ├── category_dialog.py# 管理分类对话框
        └── folder_dialog.py  # 管理库文件夹对话框
```

## 架构设计

- **分层**：UI (PySide6) → Manager (纯 Python) → Scanner / Registry / Files / Storage
- **数据流**：Scanner 扫描用户文件夹 → Manager 缓存 → UI 展示
- **本地存储**：`%APPDATA%\KontaktLibraryManager\data.json`，独立于 Kontakt
- **库来源**：用户指定的文件夹 + 注册表 + XML + JSON（始终扫描，无条件）

## 当前状态（2026-05-21 commit 08a9823）

分支 `v0.2.0`，版本号 0.2.1 WIP。

### v0.2.0 引入的回归（已部分修复）

v0.2.0 删除了 `scan_all()` 中的注册表/XML/JSON 扫描 → 入库/删除完全失效。
已在 commit `08a9823` 中恢复，但用户反馈仍然不行。

### 关键文件当前状态

- **scanner.py**: 恢复 `_scan_registry_libraries()`，`scan_all()` 无条件扫描全部 4 个来源（文件夹+注册表+XML+JSON），有路径去重和注册信息融合
- **registry.py**: `add_library()` 3 个位置全失败才报错；`remove_library()` 使用递归删除 `_delete_key_recursive()`
- **manager.py**: `add_library()`/`remove_library()` 不再内部调用慢速 `refresh()`，改为直接操作 `_libraries` 内存列表；`remove_library()` 用存储的精确 json_path/xml_path 删文件
- **main_window.py**: 补回 `import subprocess`；批量操作去掉冗余 refresh

### 调试日志

程序运行时会写 `%USERPROFILE%\klm_debug.log`（即 `C:\Users\Jeffrey\klm_debug.log`），记录每次 add/remove 的完整执行路径。

### 已知未解决问题

1. Native Access 创建的 JSON 文件名与库名不一致（如 "In Session Audio Taiko Creator" 的 JSON 叫 "Taiko Creator.json"），可能导致删除残留
2. 用户反馈入库"没有任何反应"、删除旧库后 Kontakt 里仍在，原因待确认
3. `dist/KontaktLibraryManager.exe` 是 64-bit PyInstaller 打包，含 UAC 提权

## 关键常量

| 路径 | 用途 |
|------|------|
| `HKLM\SOFTWARE\Native Instruments\` | 添加/移除库时写入的注册表路径 |
| `HKLM\SOFTWARE\WOW6432Node\Native Instruments\` | 32 位兼容路径 |
| `HKCU\Software\Native Instruments\` | 当前用户注册表路径 |
| `C:\Program Files\Common Files\Native Instruments\Service Center\` | XML 激活文件 |
| `C:\Users\Public\Documents\Native Instruments\installed_products\` | K8 JSON 文件 |

## 多标签分类

`data.json` 中 `library_categories` 格式为 `{name: ["cat1", "cat2"]}`。旧版单分类格式（字符串）会被自动迁移。右键库 → "设置分类" → 点击切换 ✓。

## 管理员权限

应用通过 UAC 清单 (`uac_admin=True`) 始终以管理员身份运行。启动时自动弹出 UAC 确认窗口。

## 打包

```bash
# 生成 spec 后，后续直接
pyinstaller KontaktLibraryManager.spec

# 安装包
iscc setup.iss
```
