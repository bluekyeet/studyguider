// An escaped dollar is money ("\$560"), not the start of maths; $x$ beside it is still a formula.
import assert from 'assert';
import { pathToFileURL } from 'url';

// Just enough DOM for the inline renderer: text and element nodes that know their text.
const node = tag => ({ tag, children: [], className: '', set textContent(v) { this.children = [{ text: String(v) }]; },
  get textContent() { return this.children.map(c => c.text ?? c.textContent).join(''); },
  append(...nodes) { this.children.push(...nodes); }, appendChild(n) { this.children.push(n); return n; } });
globalThis.window = {};      // no KaTeX: a formula is shown as its $...$ source
globalThis.document = { createElement: node, createTextNode: text => ({ text }) };

const { inlineMath } = await import(pathToFileURL('server/web-common.js'));
const shown = inlineMath('A bus for \\$560 for a day; \\$1.50 each and $x$ students.');
const maths = shown.children.filter(c => c.className === 'math-inline').map(c => c.textContent);
assert.deepStrictEqual(maths, ['$x$']);
assert.strictEqual(shown.textContent, 'A bus for $560 for a day; $1.50 each and $x$ students.');
assert.deepStrictEqual(inlineMath('$a + b$ and $$c$$').children.map(c => c.className || 'text'), ['math-inline', 'text', 'math-display']);
console.log('escaped dollars: ok');
