# Er记事本

Windows 悬浮记事本 —— 常驻屏幕右侧、滑入滑出，支持多记事本和屏幕文字扫描（OCR）。

## 功能特性

- 🪟 **悬浮置顶窗口**：启动时从屏幕右侧滑入，永远置顶，无边框
- 📚 **多记事本**：列表页与详情页在同一个窗口内切换，每本独立保存
- 📝 **首行即标题**：第一行文字自动放大加粗作为标题（工具栏、列表卡片同步显示）
- 🔍 **屏幕文字扫描**：点击「扫」→ 隐藏窗口 → 框选屏幕任意区域 → Windows 自带 OCR 识别并自动复制到剪贴板（支持中文）
- ✏️ 双击空白处直接换行；「↶」按钮撤销（Ctrl+Z）
- 📐 鼠标放到窗口左下角/右下角拖拽调整大小
- ─ 最小化为屏幕右缘的**竖排小标签**，点击展开
- □ 最大化铺满工作区（双击工具栏也可切换）
- ✕ 向右滑出隐藏，屏幕右侧出现**半圆呼出按钮**随时唤回
- 💾 内容实时自动保存，窗口位置和大小自动记忆

## 运行环境

- Windows 10 / 11（开发与测试于 Windows 11）
- Python 3.10+（开发于 Python 3.14）

## 安装与运行

### 方式一：免安装版（推荐）

到 [Releases](https://github.com/ananan07/ErNotepad/releases) 页面下载最新版的 `ErNotepad.exe`，解压后**双击即用**，无需安装 Python。

> 提示：exe 未做代码签名，首次运行时 Windows SmartScreen 可能拦截，点「更多信息 → 仍要运行」即可。笔记数据保存在 exe 所在目录的 `notes/` 文件夹中。

### 方式二：源码运行

**第一次运行**：

1. 安装 [Python 3.10+](https://www.python.org/downloads/)（安装时勾选 "Add python.exe to PATH"）
2. 双击 `启动Er记事本.bat` —— 启动器会自动检测环境、自动安装依赖（PySide6，安装失败时自动改用清华镜像）

之后每次使用直接双击 `启动Er记事本.bat` 即可。

也可以手动安装依赖后运行：

```bash
pip install -r requirements.txt
python floating_notepad.py
```

## 屏幕文字扫描（OCR）说明

- 使用 Windows 自带的 OCR 引擎（`Windows.Media.Ocr`），**无需安装任何 OCR 模型或第三方库**
- 中文识别要求系统已安装中文 OCR 语言包（中文版 Windows 默认自带）
- 通过 PowerShell 子进程调用 `ocr_scan.ps1`，每次调用附带 `-ExecutionPolicy Bypass` 参数（只对单次调用生效，不修改系统设置）
- 识别结果会自动去掉 Windows OCR 在中文字符间插入的多余空格

## 数据存储

- 每本记事本独立保存为 `notes/` 文件夹下的 JSON 文件
- 窗口位置与大小保存在 `config.json`
- 以上数据均只在本地生成，删除 `notes/` 文件夹即可清除全部笔记

## 使用说明

详见 [使用说明.txt](使用说明.txt)

## 许可证

[MIT](LICENSE)
