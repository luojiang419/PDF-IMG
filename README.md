# PDF 图片提取工具

一个面向 Windows 桌面端的 PDF 图片提取工具，基于 PySide6 构建。当前界面采用固定标签页结构，支持快速提取、进阶操作、运行日志和设置页，并提供深色/浅色主题切换、导出预览、全屏浏览和图片复制到剪贴板等功能。

## 功能亮点

- 快速提取：导入 PDF、点击提取、选择保存位置、完成后打开导出文件夹。
- 进阶操作：批量队列、导出预览、处理结果和操作日志。
- 导出预览：支持图片悬浮复制、点击全屏、左右键切换、按钮切换和 Esc 退出。
- 主题切换：右上角一键动态切换深色/浅色主题。
- 固定布局：整体框架不随滚轮滚动，适配不同分辨率。

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
