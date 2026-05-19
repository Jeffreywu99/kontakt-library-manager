# Changelog

## [1.0.0] - 2026-05-19

首个可用版本。

### 功能

- 音色库文件夹管理：用户指定根目录，自动识别子文件夹为音色库（标准/非标准）
- 注册表库补充（可选显示）：扫描 `HKLM\SOFTWARE\Native Instruments\` 下的注册库
- 添加/移除音色库：修改注册表 + Service Center XML + installed_products JSON，不删除实际文件
- 批量入库：选择一个根文件夹，自动扫描子文件夹并一次性注册
- 批量选中和批量移除
- 多标签分类系统：一个库可同时属于多个分类，右键切换
- 隐藏/取消隐藏库
- 音色浏览：扫描 .nki 文件，按目录结构展示
- 库备注和音色备注：存本地 JSON，不影响 Kontakt
- 查看来源位置：注册表路径、XML/JSON 文件、库文件夹
- 打开注册表编辑器快捷按钮
- 暗色主题 UI：黑白灰简约风格
- 自定义应用图标
- 便携版（免安装）+ 安装版（Inno Setup）
- 管理员权限：UAC 清单嵌入，启动自动提权

### 技术

- Python 3.12 + PySide6
- 数据存 `%APPDATA%\KontaktLibraryManager\data.json`，独立于 Kontakt
- 注册表：`HKLM\SOFTWARE\Native Instruments\` 及 `WOW6432Node`
- XML：`C:\Program Files\Common Files\Native Instruments\Service Center\`
- JSON：`C:\Users\Public\Documents\Native Instruments\installed_products\`
