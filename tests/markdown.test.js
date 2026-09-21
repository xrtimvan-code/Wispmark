import test from 'node:test';
import assert from 'node:assert/strict';
import { previewBlocks } from '../editor/markdown.js';

test('only the cursor line stays as source', () => {
  const source = '# 标题\n**编辑这里**\n*第三行*';
  const blocks = previewBlocks(source, [{from: 8, to: 8}]);
  assert.deepEqual(blocks.map(b => [b.from, b.to]), [[0, 4], [14, 19]]);
  assert.match(blocks[0].html, /<h1>标题<\/h1>/);
  assert.match(blocks[1].html, /<em>第三行<\/em>/);
});

test('a selection exposes every intersecting line without changing the source', () => {
  assert.deepEqual(previewBlocks('# A\n**B**\nC', [{from: 0, to: 12}]), []);
});

test('fenced code and tables are edited as whole blocks', () => {
  const source = '```py\nprint(1)\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\nend';
  const blocks = previewBlocks(source, [{from: 8, to: 8}]);
  assert.equal(blocks.some(b => b.from === 0), false);
  assert.match(blocks.find(b => b.html.includes('<table>')).html, /<td>2<\/td>/);
  const tablePosition = source.indexOf('| 1');
  assert.equal(previewBlocks(source, [{from: tablePosition, to: tablePosition}]).some(b => b.html.includes('<table>')), false);
});

test('HTML and unsafe links in notes do not execute', () => {
  const blocks = previewBlocks('<script>alert(1)</script>\n[x](javascript:alert(1))\nend', [{from: 60, to: 60}]);
  assert.match(blocks[0].html, /&lt;script&gt;/);
  assert.equal(blocks.some(b => /href="javascript:/.test(b.html)), false);
});
