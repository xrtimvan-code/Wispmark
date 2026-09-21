import {EditorState, StateField} from '@codemirror/state';
import {EditorView, Decoration, WidgetType, keymap, drawSelection, highlightActiveLine, placeholder} from '@codemirror/view';
import {defaultKeymap, history, historyKeymap, undo, undoDepth} from '@codemirror/commands';
import {markdown, markdownKeymap} from '@codemirror/lang-markdown';
import {previewBlocks} from './markdown.js';

class Preview extends WidgetType {
  constructor(block) { super(); this.block = block; }
  eq(other) { return this.block.from === other.block.from && this.block.html === other.block.html; }
  toDOM(view) {
    const dom = document.createElement('div');
    dom.className = 'cm-preview';
    dom.innerHTML = this.block.html;
    dom.addEventListener('mousedown', event => {
      if (event.button !== 0) return;
      const link = event.target.closest('a');
      if (link && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        bridge?.openLink(link.getAttribute('href'));
        return;
      }
      event.preventDefault();
      view.dispatch({selection: {anchor: this.block.from}});
      view.focus();
    });
    dom.addEventListener('click', event => event.preventDefault());
    return dom;
  }
  ignoreEvent() { return true; }
}

function decorations(state) {
  return Decoration.set(previewBlocks(state.doc.toString(), state.selection.ranges)
    .map(block => Decoration.replace({widget: new Preview(block), block: true}).range(block.from, block.to)));
}
const livePreview = StateField.define({
  create: decorations,
  update(value, tr) { return tr.docChanged || tr.selection ? decorations(tr.state) : value; },
  provide: field => EditorView.decorations.from(field)
});

let bridge = null;
let generation = 0;
// Native vertical movement can jump over replacement widgets. Move through
// source lines so keyboard users can enter every rendered line and code block.
function moveLine(direction, extend = false) {
  return view => {
    const {doc, selection} = view.state;
    const line = doc.lineAt(selection.main.head);
    const targetNumber = Math.max(1, Math.min(doc.lines, line.number + direction));
    if (targetNumber === line.number) return false;
    const target = doc.line(targetNumber);
    const head = target.from + Math.min(selection.main.head - line.from, target.length);
    view.dispatch({selection: {anchor: extend ? selection.main.anchor : head, head}, scrollIntoView: true});
    return true;
  };
}
const extensions = [
  history(), markdown(), livePreview, drawSelection(), highlightActiveLine(),
  EditorView.lineWrapping, placeholder('点击这里开始写 Markdown…'),
  keymap.of([
    {key: 'ArrowDown', run: moveLine(1), shift: moveLine(1, true)},
    {key: 'ArrowUp', run: moveLine(-1), shift: moveLine(-1, true)},
    ...markdownKeymap, ...defaultKeymap, ...historyKeymap
  ]),
  EditorView.contentAttributes.of({'aria-label': 'Markdown 笔记编辑器'}),
  EditorView.updateListener.of(update => {
    if (update.docChanged) bridge?.changed(generation, update.state.doc.toString(), undoDepth(update.state) > 0);
  })
];
const view = new EditorView({state: EditorState.create({extensions}), parent: document.querySelector('#editor')});
window.noteEditor = {
  load(text, id) {
    generation = id;
    view.setState(EditorState.create({doc: text, extensions}));
  },
  snapshot() { return {generation, text: view.state.doc.toString()}; },
  undo() { undo(view); view.focus(); },
  focus() { view.focus(); }
};
if (window.qt) {
  new QWebChannel(qt.webChannelTransport, channel => {
    bridge = channel.objects.bridge;
    bridge.ready();
  });
}
