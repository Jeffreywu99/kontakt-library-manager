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
    ├── storage.py            # 本地 JSON 持久化（分类/备注/缓存/库文件夹）
    ├── registry.py           # Windows 注册表读写（winreg）
    ├── files.py              # Service Center XML + installed_products JSON
    ├── scanner.py            # 扫描 + .nicnt 元数据提取
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
- **数据流**：Scanner 扫描注册表/XML/JSON → Manager 缓存 → UI 展示
- **本地存储**：`%APPDATA%\KontaktLibraryManager\data.json`，独立于 Kontakt
- **核心理念**：入库即显示，删除即消失

## 当前状态（2026-05-21）

版本 v0.3.0。

### v0.3.0 架构重构

**核心改动**：
- 主列表只显示已注册的库（有注册表/XML/JSON 记录）
- 删除类型概念（标准库/非标准库/注册库）
- 删除隐藏功能
- 入库时自动把父目录加入库文件夹列表

**入库修复**：
- 使用 .nicnt 中的 `RegKey` 作为注册表键名（而非文件夹名）
- 使用 .nicnt 中的 `Name` 作为显示名称
- 这解决了"可见但不可用"的问题（文件夹名与注册表键名不一致）

### 调试日志

程序运行时会写 `%USERPROFILE%\klm_debug.log`，记录每次 add/remove 的完整执行路径。

## 关键常量

| 路径 | 用途 |
|------|------|
| `HKLM\SOFTWARE\Native Instruments\` | 添加/移除库时写入的注册表路径 |
| `HKLM\SOFTWARE\WOW6432Node\Native Instruments\` | 32 位兼容路径 |
| `HKCU\Software\Native Instruments\` | 当前用户注册表路径 |
| `C:\Program Files\Common Files\Native Instruments\Service Center\` | XML 激活文件 |
| `C:\Users\Public\Documents\Native Instruments\installed_products\` | K8 JSON 文件 |

## 入库写入内容

一个完整的入库操作会在三个位置写入数据：

**注册表**（HKLM + HKCU）：ContentDir, Visibility(3, DWORD), ContentVersion, SNPID, HU, JDX

**XML**（Service Center）：完整的 ProductHints XML，含 UPID/Name/Type/RegKey/SNPID/AuthSystem/Relevance/PoweredBy/Visibility/ProductSpecific(HU+JDX+Visibility)/Company/ContentDir

**JSON**（installed_products）：ContentDir + ContentVersion + SNPID（可选），ensure_ascii=False

所有可变字段（SNPID/UPID/HU/JDX/Company/AuthSystem/PoweredBy/RegKey/Name）从 `.nicnt` 文件自动提取。固定字段：Type=Content, Visibility=3, ContentVersion=1.0.0。

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
