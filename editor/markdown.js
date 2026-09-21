import MarkdownIt from 'markdown-it';

const md = new MarkdownIt({html: false, breaks: true, linkify: false});

// Inline HTML is escaped. External images are represented as text so reading
// a note never makes network requests or loads arbitrary local files.
md.renderer.rules.image = (tokens, i) =>
  `<span class="image-label">🖼 ${md.utils.escapeHtml(tokens[i].content || '图片')}</span>`;

export function previewBlocks(source, selections) {
  const lines = source.split('\n');
  const starts = [];
  let offset = 0;
  for (const line of lines) { starts.push(offset); offset += line.length + 1; }
  const groups = new Map();
  for (const token of md.parse(source, {})) {
    if (token.map && ['fence', 'code_block', 'table_open'].includes(token.type)) {
      groups.set(token.map[0], token.map[1]);
    }
  }
  const result = [];
  for (let i = 0; i < lines.length;) {
    const end = Math.min(groups.get(i) ?? i + 1, lines.length);
    const from = starts[i], to = starts[end - 1] + lines[end - 1].length;
    const active = selections.some(s => s.from <= to && s.to >= from);
    if (to > from && !active) {
      result.push({from, to, html: md.render(source.slice(from, to))});
    }
    i = end;
  }
  return result;
}
