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
- **库来源**：仅用户指定的文件夹（标准 + 非标准），不扫描注册表

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
