# Wispmark

基于 [ananan07/ErNotepad](https://github.com/ananan07/ErNotepad) 的 Markdown 修改版，由 [xrtimvan-code](https://github.com/xrtimvan-code) 维护，保留原项目 MIT 许可证及作者署名。

Windows 悬浮笔记本：**光标所在行显示 Markdown 原文，其他行显示排版效果**。点击另一行，上一行自动恢复阅读效果。表格和代码块作为一个整体进入编辑。

## 下载和使用

从本仓库 [Releases](https://github.com/xrtimvan-code/Wispmark/releases) 下载 `Wispmark-Windows-x64.zip`，解压到可写文件夹后双击 `Wispmark.exe`，无需安装 Python 或 Node.js。所有编辑器资源已包含在程序中，日常编辑无需联网。

程序包含 Qt WebEngine，体积较原版大，首次启动解压会稍慢。请保持压缩包内的许可证文件随程序一起分发。

exe 暂未做代码签名，Windows SmartScreen 首次运行时可能显示保护提示。请先核对 Release 页面公布的 SHA256；确认一致后，可选择“更多信息 → 仍要运行”。

## Markdown 编辑

- 点击需要修改的行，显示原文；鼠标仅经过不会切换。
- 支持 `# 标题`、`**粗体**`、`*斜体*`、`~~删除线~~`、列表、引用、行内代码、围栏代码块、表格和链接。
- 方向键可以移动光标；选中多行时，对应内容全部展开为原文。
- Enter 换行；Ctrl+Z 或工具栏「↶」撤销，Ctrl+Y 重做，Ctrl+A 全选原文。
- 按住 Ctrl 点击阅读状态下的链接，在系统默认浏览器打开。
- 图片目前显示为图片说明文字，不自动加载本地或网络图片。原始 HTML 按文字显示。
- 笔记始终保存 Markdown 原文，渲染和切换行不会改写源文本。

保留原版的置顶悬浮、列表/笔记切换、拖动与缩放、最小化、屏幕边缘呼出、自动保存和 OCR。双击空白处换行改为标准 Enter 换行，以配合编辑器的选词与选择行为。

## 旧笔记和数据

每本笔记仍保存在 exe 同目录 `notes/` 下的 JSON 文件，窗口设置仍在 `config.json`。普通文本笔记可直接继续使用；若原文包含 Markdown 符号，阅读状态会按 Markdown 排版，但保存的文字不变。

迁移时，先退出原版程序，备份后把原版 `notes/` 文件夹复制到新版 exe 旁边。不要让两个版本同时编辑同一份笔记目录。

## 从源码运行

Windows 10/11 x64，Python 3.10+。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python floating_notepad.py
```

也可使用 `启动Wispmark.bat`。仓库包含已构建的 `editor/bundle.js`，运行源码无需 Node.js。

## 开发、测试与打包

修改 `editor/` 中的 JavaScript 后，使用 Node.js 20+ 重建资源：

```powershell
npm ci
npm test
npm run build
python -m unittest discover -s tests -v
```

请在 Visual Studio 的“x64 Native Tools Command Prompt”中运行：

```powershell
.\build_windows.ps1
```

打包脚本使用 PyInstaller。Qt 集成测试会短暂创建测试窗口，使用临时笔记目录。构建结果为 `dist/Wispmark.exe`。分发压缩包同时附上 `LICENSE`、`THIRD_PARTY_NOTICES.txt` 和 `licenses/`。

## OCR

沿用 Windows 自带 OCR 引擎。点击「扫」框选区域后，识别文字复制到剪贴板。中文识别需要系统中文 OCR 语言包。调用随附 `ocr_scan.ps1`，无需下载识别模型。

## 许可证

本项目采用 MIT 许可证，见 [LICENSE](LICENSE)。第三方编辑器和 Qt 组件的许可见 `THIRD_PARTY_NOTICES.txt` 及 `licenses/`。
