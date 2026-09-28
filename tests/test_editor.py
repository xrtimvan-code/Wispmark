import os
import tempfile
import time
import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from markdown_editor import MarkdownEditor


APP = QApplication.instance() or QApplication([])


def wait_for(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        APP.processEvents()
        if predicate():
            return
        QTest.qWait(20)
    raise AssertionError('Editor did not become ready')


class EditorTests(unittest.TestCase):
    def setUp(self):
        self.clipboard_text = APP.clipboard().text()
        self.editor = MarkdownEditor()
        self.editor.resize(500, 600)
        self.editor.show()
        wait_for(lambda: self.editor.is_ready)

    def tearDown(self):
        APP.clipboard().setText(self.clipboard_text)
        self.editor.close()
        self.editor.deleteLater()
        APP.processEvents()

    def js(self, script):
        result = []
        self.editor.page().runJavaScript(script, lambda value: result.append(value))
        wait_for(lambda: bool(result))
        return result[0]

    def test_click_only_reveals_target_line_and_preserves_markdown(self):
        source = '# 标题\n**第二行**\n*第三行*'
        self.editor.setPlainText(source)
        self.js('document.querySelector(".cm-preview").dispatchEvent(new MouseEvent("mousedown", {bubbles:true, button:0}))')
        self.assertIn('**第二行**', self.js('document.querySelector(".cm-line").textContent'))
        self.assertEqual(self.js('document.querySelector(".cm-preview h1").textContent'), '标题')
        self.assertEqual(self.js('document.querySelector(".cm-preview em").textContent'), '第三行')
        self.editor.flush()
        self.assertEqual(self.editor.toPlainText(), source)

    def test_typing_undo_and_reload_keep_source(self):
        self.editor.setPlainText('# title\nbody')
        self.editor.setFocus()
        self.js('noteEditor.focus()')
        QTest.keyClick(self.editor.focusProxy(), Qt.Key_End)
        QTest.keyClicks(self.editor.focusProxy(), '!')
        self.editor.flush()
        self.assertEqual(self.editor.toPlainText(), '# title!\nbody')
        self.editor.undo()
        self.editor.flush()
        self.assertEqual(self.editor.toPlainText(), '# title\nbody')
        self.editor.setPlainText('another note')
        self.editor.undo()
        self.editor.flush()
        self.assertEqual(self.editor.toPlainText(), 'another note')

    def test_keyboard_navigation_and_select_all_preserve_source(self):
        source = '# title\n**bold**\nlast'
        self.editor.setPlainText(source)
        self.js('noteEditor.focus()')
        QTest.keyClick(self.editor.focusProxy(), Qt.Key_Down)
        wait_for(lambda: self.js('document.querySelector(".cm-preview h1")?.textContent') == 'title')
        self.assertEqual(self.js('document.querySelector(".cm-preview h1").textContent'), 'title')
        self.assertIn('**bold**', self.js('document.querySelector(".cm-line").textContent'))
        QTest.keyClick(self.editor.focusProxy(), Qt.Key_A, Qt.ControlModifier)
        wait_for(lambda: self.js('document.querySelectorAll(".cm-preview").length') == 0)
        self.assertEqual(self.js('document.querySelectorAll(".cm-preview").length'), 0)
        QTest.keyClick(self.editor.focusProxy(), Qt.Key_C, Qt.ControlModifier)
        wait_for(lambda: APP.clipboard().text() == source)
        self.assertEqual(APP.clipboard().text(), source)
        self.editor.flush()
        self.assertEqual(self.editor.toPlainText(), source)

    def test_note_switch_flushes_pending_edits(self):
        import floating_notepad as app
        with tempfile.TemporaryDirectory() as directory:
            old_notes, old_config = app.NOTES_DIR, app.CONFIG_FILE
            app.NOTES_DIR = directory
            app.CONFIG_FILE = os.path.join(directory, 'config.json')
            window = app.NoteWindow(None)
            try:
                self.assertEqual(window.windowTitle(), 'Wispmark')
                wait_for(lambda: window.editor.is_ready)
                a, b = os.path.join(directory, 'a.json'), os.path.join(directory, 'b.json')
                app.write_note_file(a, '# first')
                app.write_note_file(b, 'second')
                window.open_note(a)
                window.editor.page().runJavaScript('document.execCommand("insertText", false, "X")')
                window.open_note(b)
                self.assertEqual(app.load_note_file(a)['text'], 'X# first')
                self.assertEqual(window.editor.toPlainText(), 'second')
            finally:
                window._save_timer.stop()
                window.close()
                window.deleteLater()
                APP.processEvents()
                app.NOTES_DIR, app.CONFIG_FILE = old_notes, old_config


if __name__ == '__main__':
    unittest.main()
