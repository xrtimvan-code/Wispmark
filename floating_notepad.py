# -*- coding: utf-8 -*-
"""
浮窗记事本
==========

单一窗口, 两个页面原地切换:
- 列表页: 显示所有记事本, 可新建 / 打开 / 删除
- 详情页: 编辑某本记事本的内容, 点「←」返回列表

其他:
- 启动或点击半圆按钮: 窗口从屏幕右侧滑入, 首先显示列表页
- 无边框置顶, 顶部工具栏可拖动, 支持最小化/最大化/关闭
- 最小化: 收起为贴在屏幕右缘的竖排小标签, 点击展开
- 关闭(X): 向右滑出隐藏, 屏幕右侧的半圆按钮随时呼出
- 内容实时自动保存, 每本记事本独立存为 notes/ 下的一个文件
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid

from PySide6.QtCore import (
    QEasingCurve, QEvent, QObject, QPoint, QPointF, QPropertyAnimation, QRect,
    QRectF, QSize, Qt, QTimer, Signal,
)
from PySide6.QtGui import (
    QColor, QCursor, QFont, QFontMetrics, QGuiApplication, QIcon, QPainter,
    QPainterPath, QPen, QPixmap, QRegion, QSyntaxHighlighter, QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
    QStyle, QStyledItemDelegate, QVBoxLayout, QWidget,
)

# 打包成 exe 时: 笔记/配置等数据存在 exe 旁边, 打包资源在临时解压目录
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
NOTES_DIR = os.path.join(APP_DIR, "notes")
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
OCR_PS1 = os.path.join(BUNDLE_DIR, "ocr_scan.ps1")

SLIDE_MS = 260        # 滑入/滑出动画时长(毫秒)
SEMICIRCLE_R = 30     # 半圆呼出按钮半径(像素)
MIN_W = 300           # 窗口最小宽度
MIN_H = 240           # 窗口最小高度
CORNER = 14           # 左下/右下角缩放感应区大小(像素)
TIME_ROLE = Qt.UserRole + 1   # 卡片"最后更改时间"的角色

STYLE = """
QFrame#container {
    background: #FDFCF7;
    border: 1px solid #E3DED2;
    border-radius: 12px;
}
QFrame#toolbar {
    background: transparent;
    border: none;
    border-bottom: 1px solid #EEE9DC;
}
QLabel#title {
    color: #6B675F;
    font-family: "Microsoft YaHei UI", "Microsoft YaHei";
    font-size: 10pt;
}
QLabel#vtitle {
    color: #6B675F;
    font-family: "Microsoft YaHei UI", "Microsoft YaHei";
    font-size: 10pt;
    padding: 10px 2px;
}
QPlainTextEdit {
    background: transparent;
    border: none;
    color: #3A3A3A;
    font-family: "Microsoft YaHei UI", "Microsoft YaHei";
    font-size: 13pt;
    padding: 10px;
    selection-background-color: #FFE9A8;
}
QPushButton#tb_btn {
    border: none;
    border-radius: 6px;
    background: transparent;
    color: #6B675F;
    font-family: "Segoe UI Symbol";
    font-size: 11pt;
}
QPushButton#tb_btn:hover { background: rgba(0, 0, 0, 0.07); }
QPushButton#tb_btn:pressed { background: rgba(0, 0, 0, 0.12); }
QPushButton#tb_close { border: none; border-radius: 6px; background: transparent;
    color: #6B675F; font-family: "Segoe UI Symbol"; font-size: 11pt; }
QPushButton#tb_close:hover { background: #E81123; color: white; }
QPushButton#tb_close:pressed { background: #C50F1F; color: white; }
QPushButton#tb_new {
    border: none;
    border-radius: 6px;
    background: transparent;
    color: #4C8DFF;
    font-family: "Microsoft YaHei UI";
    font-size: 12pt;
    font-weight: bold;
}
QPushButton#tb_new:hover { background: rgba(76, 141, 255, 0.12); }
QPushButton#tb_new:pressed { background: rgba(76, 141, 255, 0.20); }
QPushButton#btn_new {
    background: #4C8DFF;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0 16px;
    font-family: "Microsoft YaHei UI", "Microsoft YaHei";
    font-size: 10pt;
}
QPushButton#btn_new:hover { background: #3B7BE8; }
QPushButton#btn_new:pressed { background: #2F68C9; }
QListWidget#note_list {
    background: transparent;
    border: none;
    outline: none;
}
QLabel#hint {
    color: #A8A29A;
    font-family: "Microsoft YaHei UI", "Microsoft YaHei";
    font-size: 11pt;
}
"""


def first_line(text):
    """取第一行非空文字作为标题"""
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            return line
    return ""


class NoteEditor(QPlainTextEdit):
    """编辑区: 拼音输入未上屏(组合中)时也立即隐藏占位提示;
    双击空白处直接插入换行"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ph_restore = None

    def inputMethodEvent(self, e):
        if e.preeditString():
            # 正在用输入法组合拼音: 先藏起占位提示
            if self.placeholderText() and self._ph_restore is None:
                self._ph_restore = self.placeholderText()
                self.setPlaceholderText("")
        elif self._ph_restore is not None:
            self.setPlaceholderText(self._ph_restore)
            self._ph_restore = None
        super().inputMethodEvent(e)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            cursor = self.cursorForPosition(e.position().toPoint())
            pos = cursor.position()
            pos_in_block = cursor.positionInBlock()
            line_text = cursor.block().text()
            # 空白处 = 行尾文字之外, 或该位置字符本身是空白
            is_blank = (pos_in_block >= len(line_text)
                        or line_text[pos_in_block].isspace())
            if is_blank:
                # 双击空白处: 在此处插入换行, 取代默认的选词行为
                cursor = self.textCursor()
                cursor.setPosition(pos)
                cursor.insertText("\n")
                self.setTextCursor(cursor)
                self.ensureCursorVisible()
                return
        # 双击在文字上: 保持默认行为(选中该词)
        super().mouseDoubleClickEvent(e)


class TitleHighlighter(QSyntaxHighlighter):
    """第一行非空文字作为标题, 字体比正文稍大且加粗"""

    def __init__(self, doc):
        super().__init__(doc)
        fmt = QTextCharFormat()
        f = QFont("Microsoft YaHei UI", 16)
        f.setBold(True)
        fmt.setFont(f)
        fmt.setForeground(QColor("#1F1F1F"))
        self._fmt = fmt
        self._pending = False
        # 文档变化后延迟到事件循环空闲时全量重刷,
        # 避免在编辑过程中同步重入 QTextDocument 导致崩溃
        doc.contentsChanged.connect(self._schedule)

    def _schedule(self):
        if not self._pending:
            self._pending = True
            QTimer.singleShot(0, self._do_rehighlight)

    def _do_rehighlight(self):
        self._pending = False
        self.rehighlight()

    def highlightBlock(self, text):
        if not text.strip():
            return
        prev = self.currentBlock().previous()
        while prev.isValid() and not prev.text().strip():
            prev = prev.previous()
        if not prev.isValid():
            self.setFormat(0, len(text), self._fmt)


def load_note_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def list_note_files():
    """按最近使用时间排序的笔记文件列表"""
    try:
        items = []
        for name in os.listdir(NOTES_DIR):
            if name.endswith(".json"):
                p = os.path.join(NOTES_DIR, name)
                items.append((p, load_note_file(p).get("last_opened", 0)))
        items.sort(key=lambda t: -t[1])
        return [p for p, _ in items]
    except OSError:
        return []


def write_note_file(path, text):
    data = load_note_file(path)
    data["id"] = os.path.basename(path)[:-5]
    data["text"] = text
    data["last_opened"] = time.time()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def migrate_legacy():
    """旧版数据迁移"""
    os.makedirs(NOTES_DIR, exist_ok=True)
    legacy = os.path.join(APP_DIR, "notes_data.json")
    if os.path.exists(legacy) and not list_note_files():
        try:
            with open(legacy, encoding="utf-8") as f:
                old = json.load(f)
            path = os.path.join(NOTES_DIR, uuid.uuid4().hex[:12] + ".json")
            write_note_file(path, old.get("text", ""))
            os.rename(legacy, legacy + ".bak")
        except Exception:
            pass


def run_windows_ocr(img_path):
    """调用 Windows 自带 OCR 识别图片中的文字 (通过 PowerShell 子进程)"""
    out_path = img_path + ".txt"
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", OCR_PS1, img_path, out_path],
            capture_output=True, timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW)
        if r.returncode != 0:
            err = (r.stderr or b"").decode("utf-8", "replace").strip()
            raise RuntimeError("OCR 执行失败: " + (err or "未知错误"))
        if not os.path.exists(out_path):
            raise RuntimeError("OCR 无输出")
        with open(out_path, encoding="utf-8-sig") as f:
            text = f.read()
    finally:
        try:
            os.remove(out_path)
        except OSError:
            pass
    # Windows OCR 会在中文字符间插入空格, 去掉让中文保持连贯
    text = re.sub(r"(?<=[一-鿿＀-￯]) (?=[一-鿿＀-￯])",
                  "", text).strip()
    if not text:
        raise RuntimeError("未识别到文字")
    return text


class SelectionOverlay(QWidget):
    """全屏半透明遮罩: 拖拽框选要识别的屏幕区域"""

    selected = Signal(QRect)   # 框选完成, 矩形为虚拟桌面坐标
    canceled = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self._start = None
        self._end = None

    def show_on_screen_under_cursor(self):
        s = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        self.setGeometry(s.geometry())
        self.show()
        self.raise_()
        self.activateWindow()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 80))
        if self._start is not None and self._end is not None:
            sel = QRect(self._start, self._end).normalized()
            # 挖空选区, 露出原始屏幕内容
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.fillRect(sel, QColor(0, 0, 0, 255))
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            p.setPen(QPen(QColor(255, 255, 255), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRect(sel)
            # 选区尺寸提示
            tip_rect = QRect(sel.left(), max(4, sel.top() - 26), sel.width(), 22)
            p.setPen(QColor(255, 255, 255, 230))
            p.drawText(tip_rect, Qt.AlignCenter, f"{sel.width()} × {sel.height()}")
        else:
            p.setPen(QColor(255, 255, 255, 220))
            p.setFont(QFont("Microsoft YaHei UI", 12))
            p.drawText(self.rect().adjusted(0, 40, 0, 0), Qt.AlignHCenter | Qt.AlignTop,
                       "拖动鼠标框选要识别的文字区域\n右键或 Esc 取消")
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.canceled.emit()
            return
        if e.button() == Qt.LeftButton:
            self._start = e.position().toPoint()
            self._end = self._start

    def mouseMoveEvent(self, e):
        if self._start is not None and (e.buttons() & Qt.LeftButton):
            self._end = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._start is not None:
            sel = QRect(self._start, self._end).normalized()
            if sel.width() >= 8 and sel.height() >= 8:
                self.selected.emit(QRect(sel.topLeft() + self.pos(), sel.size()))
            else:
                self.canceled.emit()
            self._start = None
            self._end = None

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.canceled.emit()


class OcrBridge(QObject):
    """后台 OCR 线程 → 主线程的信号桥"""

    done = Signal(str, bool)   # (文本, 是否成功)


class PageSwitcher(QWidget):
    """页面切换容器, 带左右滑动过渡 (0=列表页, 1=详情页)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pages = []
        self.current = 0
        self._anims = []

    def add_page(self, page):
        page.setParent(self)
        page.hide()
        self.pages.append(page)
        return page

    def show_index(self, index):
        for i, p in enumerate(self.pages):
            if i == index:
                p.resize(self.size())
                p.move(0, 0)
                p.show()
                p.raise_()
            else:
                p.hide()
        self.current = index

    def resizeEvent(self, e):
        super().resizeEvent(e)
        for p in self.pages:
            if p.isVisible():
                p.resize(self.size())
                p.move(0, 0)

    def go(self, index):
        """切换页面: 直接切换, 不依赖动画, 保证目标页面立即可见"""
        if index == self.current or not self.pages:
            return
        self.show_index(index)


class ToolBar(QFrame):
    """顶部工具栏: 可拖动; 列表页/详情页两种形态"""

    def __init__(self, notepad):
        super().__init__()
        self.np = notepad
        self.setObjectName("toolbar")
        self.setFixedHeight(notepad.toolbar_h)
        self._drag_offset = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 6, 0)
        lay.setSpacing(2)

        self.back_btn = self._btn("←", notepad.show_list)
        self.back_btn.setToolTip("返回列表")

        self.title = QLabel("📚 我的记事本")
        self.title.setObjectName("title")

        self.btn_undo = self._btn("↶", notepad.undo)
        self.btn_undo.setToolTip("撤销 (Ctrl+Z)")
        self.btn_undo.setEnabled(False)
        self.btn_scan = self._btn("扫", notepad.start_scan, "tb_new")
        self.btn_scan.setToolTip("扫描屏幕文字并复制到剪贴板")
        self.btn_new = self._btn("＋", notepad.create_note, "tb_new")
        self.btn_new.setToolTip("新建记事本")
        self.btn_min = self._btn("─", notepad.minimize)
        self.btn_max = self._btn("□", notepad.toggle_max)
        self.btn_close = self._btn("✕", notepad.close_clicked, "tb_close")

        lay.addWidget(self.back_btn)
        lay.addWidget(self.title)
        lay.addStretch(1)
        lay.addWidget(self.btn_undo)
        lay.addWidget(self.btn_scan)
        lay.addWidget(self.btn_new)
        lay.addWidget(self.btn_min)
        lay.addWidget(self.btn_max)
        lay.addWidget(self.btn_close)

        self.set_list_mode()

    def _btn(self, text, slot, objname="tb_btn"):
        b = QPushButton(text)
        b.setFixedSize(int(self.np.toolbar_h * 0.9), int(self.np.toolbar_h * 0.78))
        b.setCursor(Qt.PointingHandCursor)
        b.setObjectName(objname)
        b.clicked.connect(slot)
        return b

    def set_list_mode(self):
        self.back_btn.hide()
        self.btn_undo.hide()
        self.btn_scan.hide()
        self.title.setText("📚 Er记事本")

    def set_editor_mode(self, note_title):
        t = note_title or "无标题"
        self.back_btn.show()
        self.btn_undo.show()
        self.btn_scan.show()
        self.title.setText("📝 " + (t if len(t) <= 10 else t[:10] + "…"))

    def update_max_icon(self, maximized):
        self.btn_max.setText("❐" if maximized else "□")

    # ---------- 拖动 ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            self.np.toolbar_menu(e.globalPosition().toPoint())
            return
        if e.button() != Qt.LeftButton:
            return
        if self.np.maximized:
            self.np.restore_for_drag(e.globalPosition().toPoint())
        self._drag_offset = e.globalPosition().toPoint() - self.np.pos()

    def mouseMoveEvent(self, e):
        if self._drag_offset is not None and (e.buttons() & Qt.LeftButton):
            self.np.move(e.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, e):
        if self._drag_offset is not None:
            self._drag_offset = None
            self.np.save_data()

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.np.toggle_max()


class VTabLabel(QLabel):
    """最小化后的竖排小标签, 点击展开"""

    def __init__(self, notepad):
        super().__init__()
        self.np = notepad
        self.setObjectName("vtitle")
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(False)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("点击展开记事本")
        self._chars = []

    def update_text(self, title):
        self._chars = list((title or "记事本").strip())[:6] or list("记事本")
        self.setText("📝\n" + "\n".join(self._chars))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.np.expand()
        elif e.button() == Qt.RightButton:
            self.np.toolbar_menu(e.globalPosition().toPoint())


class NoteItemDelegate(QStyledItemDelegate):
    """列表卡片: 标题 + 最后更改时间, 直接绘制, 高度按字体精确计算"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._f_title = QFont("Microsoft YaHei UI", 11)
        self._f_time = QFont("Microsoft YaHei UI", 9)
        self._bg_hover = QColor(76, 141, 255, 26)
        self._bg_sel = QColor(76, 141, 255, 46)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        r = QRectF(option.rect).adjusted(4, 2, -4, -2)
        if option.state & QStyle.State_Selected:
            painter.setBrush(self._bg_sel)
        elif option.state & QStyle.State_MouseOver:
            painter.setBrush(self._bg_hover)
        else:
            painter.setBrush(Qt.NoBrush)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(r, 8, 8)

        title = index.data(Qt.DisplayRole) or ""
        tstr = index.data(TIME_ROLE) or ""
        inner = option.rect.adjusted(14, 10, -14, -10)
        painter.setFont(self._f_title)
        painter.setPen(QColor("#3A3A3A"))
        painter.drawText(inner, Qt.AlignLeft | Qt.AlignTop, title)
        if tstr:
            painter.setFont(self._f_time)
            painter.setPen(QColor("#A8A29A"))
            painter.drawText(inner, Qt.AlignLeft | Qt.AlignBottom, tstr)
        painter.restore()

    def sizeHint(self, option, index):
        fm1 = QFontMetrics(self._f_title)
        fm2 = QFontMetrics(self._f_time)
        return QSize(0, fm1.height() + fm2.height() + 24)


class ListPage(QWidget):
    """列表页: 显示所有记事本"""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self._menu_guard = False

        v = QVBoxLayout(self)
        v.setContentsMargins(14, 10, 14, 12)
        v.setSpacing(8)

        self.list = QListWidget()
        self.list.setObjectName("note_list")
        self.list.setItemDelegate(NoteItemDelegate(self.list))
        self.list.setMouseTracking(True)
        self.list.viewport().setMouseTracking(True)
        self.list.itemClicked.connect(self._open_item)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        v.addWidget(self.list)

        # 空状态: 提示 + 新建按钮
        self.empty_box = QWidget()
        ev = QVBoxLayout(self.empty_box)
        ev.setContentsMargins(0, 30, 0, 30)
        self.hint = QLabel("还没有记事本\n\n点击下方按钮\n创建你的第一本记事本")
        self.hint.setObjectName("hint")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setWordWrap(True)
        self.empty_btn = QPushButton("＋ 新建记事本")
        self.empty_btn.setObjectName("btn_new")
        self.empty_btn.setFixedHeight(34)
        self.empty_btn.setCursor(Qt.PointingHandCursor)
        self.empty_btn.clicked.connect(self.win.create_note)
        ev.addStretch(1)
        ev.addWidget(self.hint)
        ev.addSpacing(18)
        ev.addWidget(self.empty_btn, 0, Qt.AlignHCenter)
        ev.addStretch(1)
        v.addWidget(self.empty_box)
        self.empty_box.hide()

    def refresh(self):
        paths = list_note_files()
        self.list.clear()
        if not paths:
            self.list.hide()
            self.empty_box.show()
            return
        self.empty_box.hide()
        self.list.show()
        for p in paths:
            data = load_note_file(p)
            title = first_line(data.get("text", "")) or "无标题"
            ts = data.get("last_opened", 0)
            tstr = "最后更改 " + time.strftime("%m-%d %H:%M", time.localtime(ts)) if ts else ""
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, p)
            item.setData(TIME_ROLE, tstr)
            item.setToolTip("点击打开")
            self.list.addItem(item)

    def _open_item(self, item):
        if self._menu_guard:
            return
        path = item.data(Qt.UserRole)
        if path:
            self.win.open_note(path)

    def _menu(self, pos):
        item = self.list.itemAt(pos)
        if item is None:
            return
        self._menu_guard = True
        try:
            m = QMenu(self)
            m.addAction("打开", lambda: self.win.open_note(item.data(Qt.UserRole)))
            m.addAction("删除", lambda: self.win.ask_delete_note(item.data(Qt.UserRole)))
            m.exec(self.list.mapToGlobal(pos))
        finally:
            self._menu_guard = False


class NoteWindow(QWidget):
    """主窗口: 列表页与详情页原地切换"""

    def __init__(self, semicircle):
        super().__init__()
        self.semicircle = semicircle
        self.setWindowTitle("Er记事本")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(STYLE)
        self.setWindowIcon(make_app_icon())

        scr = QGuiApplication.primaryScreen()
        # 工具栏高度 ≈ 1 厘米(按屏幕物理 DPI 换算)
        self.toolbar_h = max(30, round(1 / 2.54 * scr.physicalDotsPerInch()))

        self.current_note = None   # 当前打开的笔记文件路径
        self.collapsed = False
        self.maximized = False
        self._normal_geo = None    # 常规状态的窗口几何
        self._expand_geo = None    # 收起前的窗口几何
        self._anim = None

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        self.container = QFrame()
        self.container.setObjectName("container")
        root.addWidget(self.container)

        v = QVBoxLayout(self.container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self.toolbar = ToolBar(self)
        v.addWidget(self.toolbar)

        self.switcher = PageSwitcher()
        v.addWidget(self.switcher, 1)

        self.list_page = ListPage(self)
        self.switcher.add_page(self.list_page)

        self.editor_page = QWidget()
        ev = QVBoxLayout(self.editor_page)
        ev.setContentsMargins(0, 0, 0, 0)
        self.editor = NoteEditor()
        self.editor.setPlaceholderText("在这里输入内容…")
        self.editor.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self._highlighter = TitleHighlighter(self.editor.document())
        self.editor.document().undoAvailable.connect(self.toolbar.btn_undo.setEnabled)
        ev.addWidget(self.editor)
        self.switcher.add_page(self.editor_page)

        self.vtab = VTabLabel(self)
        v.addWidget(self.vtab)
        self.vtab.hide()

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(800)
        self._save_timer.timeout.connect(self.save_data)
        self.editor.textChanged.connect(self._on_text_changed)

        # 左下/右下角缩放状态
        self._resizing = None        # "bl" / "br"
        self._resize_start = None
        self._resize_geo = None
        self._corner_obj = None      # 正在显示斜向光标的控件
        QApplication.instance().installEventFilter(self)

        # 屏幕文字扫描状态
        self._scan_overlay = None
        self._flash_token = 0
        self._ocr_bridge = OcrBridge()
        self._ocr_bridge.done.connect(self._on_ocr_done)

        self._load_config()
        self.list_page.refresh()
        self.switcher.show_index(0)
        self._update_tab_text()

    # ---------- 屏幕 / 几何 ----------
    def screen_at(self):
        center = (self._normal_geo or self.geometry()).center()
        return QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()

    def default_rect(self):
        s = QGuiApplication.primaryScreen().availableGeometry()
        # 按需求: 宽 = 屏幕宽度 1/3, 高 = 屏幕宽度 1/2
        w = s.width() // 3
        h = min(s.width() // 2, s.height() - 40)
        return QRect(s.right() - w + 1, s.top() + (s.height() - h) // 2, w, h)

    def _clamp_to_screen(self, rect):
        s = QGuiApplication.screenAt(rect.center()) or QGuiApplication.primaryScreen()
        av = s.availableGeometry()
        rect.moveLeft(max(av.left(), min(rect.left(), av.right() - rect.width() + 1)))
        rect.moveTop(max(av.top(), min(rect.top(), av.bottom() - rect.height() + 1)))
        return rect

    def collapsed_rect(self):
        av = self.screen_at().availableGeometry()
        w = self.toolbar_h + 6
        n = len(self.vtab._chars)
        h = min(300, max(110, 56 + 30 * n))
        y = av.top() + (av.height() - h) // 2
        return QRect(av.right() - w + 1, y, w, h)

    def _start_anim(self, anim):
        if self._anim is not None:
            self._anim.stop()
        self._anim = anim
        anim.start()

    def _anim_pos(self, end, on_done=None):
        anim = QPropertyAnimation(self, b"pos", self)
        anim.setDuration(SLIDE_MS)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.setStartValue(self.pos())
        anim.setEndValue(end)
        if on_done:
            anim.finished.connect(on_done)
        self._start_anim(anim)

    def _anim_geometry(self, end, on_done=None):
        anim = QPropertyAnimation(self, b"geometry", self)
        anim.setDuration(SLIDE_MS)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.setStartValue(self.geometry())
        anim.setEndValue(end)
        if on_done:
            anim.finished.connect(on_done)
        self._start_anim(anim)

    # ---------- 滑入 / 滑出 ----------
    def slide_in(self, to_list=True):
        if to_list:
            self.show_list()
        rect = self._normal_geo
        self.setGeometry(QRect(QPoint(rect.right() + 10, rect.y()), rect.size()))
        self.show()
        self.raise_()

        def _done():
            self.activateWindow()

        self._anim_pos(QPoint(rect.x(), rect.y()), _done)

    def slide_out(self):
        s = self.screen_at()

        def _done():
            self.hide()
            self.save_data()

        self._anim_pos(QPoint(s.geometry().right() + 10, self.y()), _done)

    def semi_open(self):
        """半圆按钮点击: 呼出窗口并显示列表页"""
        if self.collapsed:
            self.expand()
            self.show_list()
        elif self.isVisible():
            self.raise_()
            self.activateWindow()
            self.show_list()
        else:
            self.slide_in()

    # ---------- 左下/右下角缩放 ----------
    def _corner_zone(self, gp):
        """返回鼠标所在的角落: None / 'bl'(左下) / 'br'(右下)"""
        if not self.isVisible() or self.collapsed or self.maximized:
            return None
        r = self.geometry()
        x = gp.x() - r.x()
        y = gp.y() - r.y()
        if y < r.height() - CORNER:
            return None
        if x <= CORNER:
            return "bl"
        if x >= r.width() - CORNER:
            return "br"
        return None

    def _do_resize(self, gp):
        dx = gp.x() - self._resize_start.x()
        dy = gp.y() - self._resize_start.y()
        g = QRect(self._resize_geo)
        if self._resizing == "br":
            g.setRight(g.left() + max(MIN_W, g.width() + dx))
        else:  # "bl": 右缘固定, 左缘随鼠标移动
            g.setLeft(min(g.left() + dx, g.right() - MIN_W + 1))
        g.setBottom(g.top() + max(MIN_H, g.height() + dy))
        self.setGeometry(g)

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t not in (QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
            return super().eventFilter(obj, ev)
        if obj is None or not hasattr(obj, "window") or obj.window() is not self:
            return super().eventFilter(obj, ev)

        gp = ev.globalPosition().toPoint()
        if t == QEvent.MouseMove:
            if self._resizing:
                self._do_resize(gp)
                return True
            zone = self._corner_zone(gp)
            if zone:
                obj.setCursor(Qt.SizeBDiagCursor)
                self._corner_obj = obj
            elif self._corner_obj is not None:
                self._corner_obj.unsetCursor()
                self._corner_obj = None
        elif t == QEvent.MouseButtonPress:
            if ev.button() == Qt.LeftButton:
                zone = self._corner_zone(gp)
                if zone:
                    self._resizing = zone
                    self._resize_start = gp
                    self._resize_geo = self.geometry()
                    self.grabMouse()
                    self.setCursor(Qt.SizeBDiagCursor)
                    return True
        elif t == QEvent.MouseButtonRelease:
            if self._resizing:
                self._resizing = None
                self._resize_start = None
                self._resize_geo = None
                self.releaseMouse()
                self.unsetCursor()
                self._normal_geo = self.geometry()
                self.save_data()
        return super().eventFilter(obj, ev)

    def leaveEvent(self, e):
        if self._corner_obj is not None:
            self._corner_obj.unsetCursor()
            self._corner_obj = None
        super().leaveEvent(e)

    # ---------- 页面切换 ----------
    def _set_page(self, index):
        self.switcher.go(index)
        self._update_tab_text()

    def show_list(self):
        if self.current_note:
            self._flush_save()
        self.list_page.refresh()
        self.toolbar.set_list_mode()
        self._set_page(0)

    def open_note(self, path):
        if self.current_note and self.current_note != path:
            self._flush_save()
        self.current_note = path
        data = load_note_file(path)
        self.editor.setPlainText(data.get("text", ""))
        write_note_file(path, self.editor.toPlainText())  # 刷新最近使用时间
        self.toolbar.set_editor_mode(first_line(self.editor.toPlainText()))
        self._set_page(1)
        self.editor.setFocus()

    def undo(self):
        """撤销上一步编辑"""
        self.editor.undo()

    # ---------- 屏幕文字扫描 ----------
    def start_scan(self):
        """隐藏窗口 → 框选屏幕区域 → 后台 OCR → 自动复制到剪贴板"""
        if self._scan_overlay is not None:
            return
        if self.collapsed:
            self.expand()
        self.hide()
        # 等窗口完全从画面消失后再弹出选区遮罩
        QTimer.singleShot(400, self._show_scan_overlay)

    def _show_scan_overlay(self):
        self._scan_overlay = SelectionOverlay()
        self._scan_overlay.selected.connect(self._on_scan_selected)
        self._scan_overlay.canceled.connect(self._on_scan_canceled)
        self._scan_overlay.show_on_screen_under_cursor()

    def _on_scan_selected(self, rect):
        self._scan_overlay.close()
        self._scan_overlay = None
        self.slide_in()   # 记事本立即回来, OCR 在后台进行
        self._run_ocr(rect)

    def _on_scan_canceled(self):
        self._scan_overlay.close()
        self._scan_overlay = None
        self.slide_in()

    def _run_ocr(self, rect):
        screen = QGuiApplication.screenAt(rect.center()) or QGuiApplication.primaryScreen()
        sg = screen.geometry()
        pix = screen.grabWindow(0, rect.x() - sg.x(), rect.y() - sg.y(),
                                rect.width(), rect.height())
        img_path = os.path.join(tempfile.gettempdir(),
                                f"er_ocr_{uuid.uuid4().hex[:8]}.png")
        pix.save(img_path, "PNG")
        threading.Thread(target=self._ocr_worker, args=(img_path,), daemon=True).start()

    def _ocr_worker(self, img_path):
        try:
            text = run_windows_ocr(img_path)
            self._ocr_bridge.done.emit(text, True)
        except Exception as e:
            self._ocr_bridge.done.emit(str(e), False)
        finally:
            try:
                os.remove(img_path)
            except OSError:
                pass

    def _on_ocr_done(self, text, ok):
        if ok:
            QApplication.clipboard().setText(text)
            self._flash_title("扫描完成，已复制到剪贴板", 3000)
        else:
            self._flash_title("扫描失败：" + text, 6000)

    def _flash_title(self, msg, ms):
        self._flash_token += 1
        tok = self._flash_token
        self.toolbar.title.setText(msg)
        QTimer.singleShot(ms, lambda: self._restore_title(tok))

    def _restore_title(self, tok):
        if tok != self._flash_token:
            return
        if self.current_note:
            self.toolbar.set_editor_mode(first_line(self.editor.toPlainText()))
        else:
            self.toolbar.set_list_mode()

    def create_note(self):
        if self.current_note:
            self._flush_save()
        path = os.path.join(NOTES_DIR, uuid.uuid4().hex[:12] + ".json")
        write_note_file(path, "")
        self.current_note = path
        self.editor.setPlainText("")
        self.toolbar.set_editor_mode("无标题")
        self._set_page(1)
        if self.collapsed:
            self.expand()
        if not self.isVisible():
            self.slide_in(to_list=False)
        else:
            self.raise_()
            self.activateWindow()
        self.editor.setFocus()

    def ask_delete_note(self, path):
        data = load_note_file(path)
        t = first_line(data.get("text", "")) or "无标题"
        r = QMessageBox.question(
            self, "删除记事本", f"确定删除「{t}」吗？\n删除后内容无法恢复。",
            QMessageBox.Yes | QMessageBox.No)
        if r != QMessageBox.Yes:
            return
        if self.current_note == path:
            self._save_timer.stop()
            self.current_note = None
            self.editor.setPlainText("")
        try:
            os.remove(path)
        except OSError:
            pass
        self.show_list()

    # ---------- 按钮行为 ----------
    def close_clicked(self):
        if self.collapsed:
            self.collapsed = False
            self.vtab.hide()
            self.toolbar.show()
            self.switcher.show()
            self.slide_out()
            return
        if self.maximized:
            self._set_maximized(False)
        else:
            self._normal_geo = self.geometry()
        self.slide_out()

    def minimize(self):
        """收起为贴在屏幕右缘的竖排小标签"""
        if self.collapsed:
            return
        if self.maximized:
            self.setGeometry(self._normal_geo)
            self._set_maximized(False)
        self.collapsed = True
        self._expand_geo = self.geometry()
        self.toolbar.hide()
        self.switcher.hide()
        self.vtab.show()
        self._anim_geometry(self.collapsed_rect())

    def expand(self):
        if not self.collapsed:
            return
        self.collapsed = False
        self.vtab.hide()
        self.toolbar.show()
        self.switcher.show()
        target = self._clamp_to_screen(QRect(self._expand_geo))
        self._anim_geometry(target)

    def toggle_max(self):
        if self.collapsed:
            return
        if self.maximized:
            self._set_maximized(False)
            self.switcher.hide()
            self._anim_geometry(self._normal_geo, lambda: self.switcher.show())
        else:
            self._normal_geo = self.geometry()
            self._set_maximized(True)
            self.switcher.hide()
            self._anim_geometry(self.screen_at().availableGeometry(), lambda: self.switcher.show())

    def _set_maximized(self, value):
        self.maximized = value
        self.toolbar.update_max_icon(value)

    def restore_for_drag(self, cursor):
        """最大化状态下拖动: 先还原为常规大小, 且让标题栏落在光标处"""
        s = self.screen_at()
        av = s.availableGeometry()
        w, h = self._normal_geo.width(), self._normal_geo.height()
        x = int(min(max(cursor.x() - w // 2, av.left()), av.right() - w + 1))
        y = int(min(max(cursor.y() - self.toolbar_h // 2, av.top()), av.bottom() - h + 1))
        self.setGeometry(x, y, w, h)
        self._set_maximized(False)

    # ---------- 菜单 ----------
    def toolbar_menu(self, pos):
        m = QMenu(self)
        if self.collapsed:
            m.addAction("展开窗口", self.expand)
            m.addAction("隐藏到屏幕边缘", self.close_clicked)
        else:
            m.addAction("新建记事本", self.create_note)
            if self.switcher.current == 1:
                m.addAction("返回列表", self.show_list)
            m.addAction("收起（最小化）", self.minimize)
            m.addAction("最大化" if not self.maximized else "还原", self.toggle_max)
            m.addAction("隐藏到屏幕边缘", self.close_clicked)
        if self.current_note:
            m.addSeparator()
            m.addAction("删除当前记事本", lambda: self.ask_delete_note(self.current_note))
        m.addSeparator()
        m.addAction("退出程序", QApplication.instance().quit)
        m.exec(pos)

    # ---------- 数据持久化 ----------
    def _load_config(self):
        rect = None
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, encoding="utf-8") as f:
                    g = json.load(f).get("geometry")
                if g and len(g) == 4:
                    r = QRect(*g)
                    if QGuiApplication.screenAt(r.center()):
                        rect = r
            else:
                # 从旧版多窗口笔记文件里找回窗口位置
                for p in list_note_files():
                    g = load_note_file(p).get("geometry")
                    if g and len(g) == 4:
                        r = QRect(*g)
                        if QGuiApplication.screenAt(r.center()):
                            rect = r
                            break
        except Exception:
            rect = None
        self._normal_geo = rect or self.default_rect()

    def _flush_save(self):
        if self.current_note:
            try:
                write_note_file(self.current_note, self.editor.toPlainText())
            except Exception:
                pass

    def save_data(self):
        try:
            if self.isVisible() and not self.maximized and not self.collapsed:
                self._normal_geo = self.geometry()
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"geometry": [self._normal_geo.x(), self._normal_geo.y(),
                                        self._normal_geo.width(), self._normal_geo.height()]},
                          f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        self._flush_save()

    def _on_text_changed(self):
        if not self.current_note:
            return
        self._save_timer.start()
        t = first_line(self.editor.toPlainText())
        self.toolbar.set_editor_mode(t)
        self.vtab.update_text(t)

    def _update_tab_text(self):
        t = first_line(self.editor.toPlainText()) if self.current_note else ""
        self.vtab.update_text(t)


class SemicircleButton(QWidget):
    """屏幕右缘的半圆呼出按钮(始终显示)"""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setWindowTitle("Er记事本呼出按钮")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(SEMICIRCLE_R, SEMICIRCLE_R * 2)
        self.setMouseTracking(True)
        self.hovered = False
        self.setToolTip("打开Er记事本")

        # 半圆路径: 直边贴屏幕右缘, 圆弧向左凸出
        self._path = QPainterPath()
        self._path.moveTo(SEMICIRCLE_R, 0)
        self._path.arcTo(0, 0, SEMICIRCLE_R * 2, SEMICIRCLE_R * 2, 90, -180)
        self._path.closeSubpath()
        self.setMask(QRegion(self._path.toFillPolygon().toPolygon()))

    def show_at_edge(self):
        av = QGuiApplication.primaryScreen().availableGeometry()
        self.setGeometry(av.right() - SEMICIRCLE_R + 1,
                         av.top() + (av.height() - SEMICIRCLE_R * 2) // 2,
                         SEMICIRCLE_R, SEMICIRCLE_R * 2)
        self.show()
        self.raise_()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        color = QColor("#4C8DFF")
        if self.hovered:
            color = color.lighter(115)
        p.fillPath(self._path, color)

        pen = p.pen()
        pen.setColor(QColor(255, 255, 255, 235))
        pen.setWidthF(2.4)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        cy = SEMICIRCLE_R
        x1, x2 = SEMICIRCLE_R * 0.60, SEMICIRCLE_R * 0.38
        p.drawLine(QPointF(x1, cy - 7), QPointF(x2, cy))
        p.drawLine(QPointF(x1, cy + 7), QPointF(x2, cy))

    def enterEvent(self, e):
        self.hovered = True
        self.update()

    def leaveEvent(self, e):
        self.hovered = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.win.semi_open()
        elif e.button() == Qt.RightButton:
            m = QMenu(self)
            m.addAction("打开记事本", self.win.semi_open)
            m.addAction("新建记事本", self.win.create_note)
            m.addSeparator()
            m.addAction("退出程序", QApplication.instance().quit)
            m.exec(e.globalPosition().toPoint())


def make_app_icon():
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    f = QFont("Segoe UI Emoji")
    f.setPixelSize(44)
    p.setFont(f)
    p.drawText(pix.rect(), Qt.AlignCenter, "📝")
    p.end()
    return QIcon(pix)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Er记事本")
    app.setWindowIcon(make_app_icon())

    migrate_legacy()

    semi = SemicircleButton(None)
    win = NoteWindow(semi)
    semi.win = win
    semi.show_at_edge()

    QTimer.singleShot(120, lambda: win.slide_in())  # 启动滑入, 首先显示列表页
    app.aboutToQuit.connect(win.save_data)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
