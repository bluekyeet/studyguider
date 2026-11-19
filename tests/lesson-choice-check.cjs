// A multiple-choice block in lesson text is read into a question; a block that is not one stays a code block.
const fs = require('fs');
const source = fs.readFileSync('server/web-common.js', 'utf8');
const start = source.indexOf('export function parseChoiceBlock');
const end = source.indexOf('\nlet lessonChoices');
const parseChoiceBlock = new Function(source.slice(start, end).replace('export function', 'return function'))();
const assert = require('assert');
const block = parseChoiceBlock(['Which change increases the rate?', 'A. Lowering the temperature', 'B. Adding a catalyst *', 'C. Larger lumps', '---',
  'B: A catalyst lowers the activation energy.', 'A: Fewer collisions have enough energy.']);
assert.deepStrictEqual(block.options.map(o => [o.key, o.correct]), [['A', false], ['B', true], ['C', false]]);
assert.strictEqual(block.stem, 'Which change increases the rate?');
assert.strictEqual(block.reasons.B, 'A catalyst lowers the activation energy.');
assert.strictEqual(parseChoiceBlock(['A. one *', 'B. two', '---', 'A: right *']).reasons.A, 'right');
assert.strictEqual(block.multiple, false);
assert.strictEqual(parseChoiceBlock(['A. one *', 'B. two *', 'C. three']).multiple, true);
assert.strictEqual(parseChoiceBlock(['print("hello")']), null);
assert.strictEqual(parseChoiceBlock(['A. one', 'B. two']), null);      // no correct option marked
console.log('lesson choice blocks: ok');
