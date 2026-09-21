"""Local CodeMirror editor; Markdown source stays separate from its display."""
import json
import os
import sys

from PySide6.QtCore import QEventLoop, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView


class EditorBridge(QObject):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    @Slot()
    def ready(self):
        self.editor.is_ready = True
        self.editor._load_source()

    @Slot(int, str, bool)
    def changed(self, generation, text, can_undo):
        if generation != self.editor._generation:
            return
        self.editor._text = text
        self.editor.undoAvailable.emit(can_undo)
        self.editor.textChanged.emit()

    @Slot(str)
    def openLink(self, link):
        url = QUrl(link)
        if url.scheme().lower() in ('http', 'https', 'mailto'):
            QDesktopServices.openUrl(url)


class MarkdownEditor(QWebEngineView):
    textChanged = Signal()
    undoAvailable = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ''
        self._generation = 0
        self._flushing = False
        self.is_ready = False
        self.page().setBackgroundColor(QColor('#FDFCF7'))
        self.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
        self.channel = QWebChannel(self.page())
        self.bridge = EditorBridge(self)
        self.channel.registerObject('bridge', self.bridge)
        self.page().setWebChannel(self.channel)
        root = getattr(
            sys, '_MEIPASS',
            os.path.dirname(sys.executable) if getattr(sys, 'frozen', False)
            else os.path.dirname(os.path.abspath(__file__)))
        self.load(QUrl.fromLocalFile(os.path.join(root, 'editor', 'index.html')))

    def _load_source(self):
        self.page().runJavaScript(
            f'noteEditor.load({json.dumps(self._text)}, {self._generation})')

    def setPlainText(self, text):
        self._generation += 1
        self._text = text
        self.undoAvailable.emit(False)
        if self.is_ready:
            self._load_source()

    def toPlainText(self):
        return self._text

    def flush(self):
        """Wait for queued browser edits before saving or changing notebooks."""
        if not self.is_ready or self._flushing:
            return
        self._flushing = True
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        result = []

        def received(value):
            result.append(value)
            loop.quit()

        try:
            self.page().runJavaScript('JSON.stringify(noteEditor.snapshot())', received)
            timer.start(5000)
            loop.exec(QEventLoop.ExcludeUserInputEvents)
            if not result or not result[0]:
                raise RuntimeError('编辑器未响应，笔记尚未保存。请稍后重试。')
            snapshot = json.loads(result[0])
            if snapshot.get('generation') != self._generation:
                raise RuntimeError('笔记仍在加载，请稍后重试。')
            self._text = snapshot['text']
        finally:
            timer.stop()
            self._flushing = False

    def undo(self):
        if self.is_ready:
            self.page().runJavaScript('noteEditor.undo()')

    def setFocus(self, *args):
        super().setFocus(*args)
        if self.is_ready:
            self.page().runJavaScript('noteEditor.focus()')
