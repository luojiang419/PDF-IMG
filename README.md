# PDF 图片提取工具

一个面向 Windows 桌面端的 PDF 图片提取工具，基于 PySide6 构建。当前界面采用固定标签页结构，支持快速提取、进阶操作、运行日志和设置页，并提供深色/浅色主题切换、导出预览、全屏浏览和图片复制到剪贴板等功能。

## 功能亮点

- 快速提取：导入 PDF、点击提取、选择保存位置、完成后打开导出文件夹。
- 进阶操作：批量队列、导出预览、处理结果和操作日志。
- 导出预览：支持图片悬浮复制、点击全屏、左右键切换、按钮切换和 Esc 退出。
- 主题切换：右上角一键动态切换深色/浅色主题。
- 固定布局：整体框架不随滚轮滚动，适配不同分辨率。
- 自动更新：启动后自动检查 GitHub Release，按当前平台筛选兼容资产，支持全量安装包更新和上一版本到当前版本的增量补丁更新。
- 代理下载：更新检查、补丁下载和回退全量安装器下载都支持走系统代理，适配国内常见代理环境。

## 本地开发

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pip install pyinstaller
python main.py
```

## 测试

```powershell
python -m unittest discover -s tests
```

## 构建发布

生成 PyInstaller 运行目录：

```powershell
python scripts\build_release.py
```

生成 Inno Setup 安装包：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_installer.ps1
```

安装包会输出到最新的 `dist\v*` 目录中。

生成上一版本到当前版本的增量补丁包：

```powershell
python scripts\build_delta_update.py --from-release dist\v0.1.18 --to-release dist\v0.1.19
```

自动递增 patch 版本、构建产物并上传 GitHub Release：

```powershell
python scripts\publish_github_release.py
```

## 自动更新说明

- 最新版本通过公开 GitHub Release 提供，客户端不依赖自建服务器。
- 每个平台的正式版本都会上传自己的更新资产，Windows 与 macOS 互不干扰：
  - Windows 全量包：`PDF-IMG-Extractor-vX.Y.Z-Setup.exe`
  - Windows 增量包：`PDF-IMG-Extractor-vA.B.C-to-vX.Y.Z-windows-patch.zip`
  - Windows 清单：`PDF-IMG-Extractor-vX.Y.Z-windows-manifest.json`
  - macOS 全量包：`PDF-IMG-Extractor-vX.Y.Z-mac-ARCH.dmg`
  - macOS 增量包：`PDF-IMG-Extractor-vA.B.C-to-vX.Y.Z-macos-patch.zip`
  - macOS 清单：`PDF-IMG-Extractor-vX.Y.Z-macos-manifest.json`
- 兼容旧版客户端时可同时上传旧清单名 `PDF-IMG-Extractor-vX.Y.Z-manifest.json`，客户端会根据清单内容和安装包后缀继续判断平台。
- 客户端会优先读取系统代理配置；如果系统已开启代理，更新状态文案和日志会显示“系统代理”以及当前使用的代理地址。
- 客户端更新决策顺序固定为：
  1. 从 GitHub Release 列表中查找当前平台最新的兼容 `manifest.json`
  2. 如果存在 `from_version == 当前版本` 的补丁包，则优先下载增量补丁
  3. 否则回退下载全量安装包
- 下载缓存目录默认位于 `%LOCALAPPDATA%\PDF-IMG-Extractor\updates`
- “下次启动更新”会把待执行更新状态写入 `%LOCALAPPDATA%\PDF-IMG-Extractor\update_state.json`
- 首个带自动更新能力的版本需要手动安装一次；之后才可通过应用内自动更新
