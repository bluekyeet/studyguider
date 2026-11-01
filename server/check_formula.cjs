// Uses the same KaTeX/mhchem assets as Android. JSON in/out; never eval model text.
const fs = require('node:fs');
const path = require('node:path');
const root = process.env.KATEX_ASSET_DIR || path.resolve(__dirname, '../android/app/src/main/assets/katex');
const katex = require(path.join(root, 'katex.min.js'));
// The extension's CommonJS entry expects an installed module named katex.
const Module = require('node:module');
const original = Module._resolveFilename;
Module._resolveFilename = function(name, ...args) {
  return name === 'katex' ? path.join(root, 'katex.min.js') : original.call(this, name, ...args);
};
require(path.join(root, 'contrib/mhchem.min.js'));
const formulas = JSON.parse(fs.readFileSync(0, 'utf8'));
const errors = [];
for (const formula of formulas) {
  try {
    katex.renderToString(formula, {throwOnError: true, trust: false, maxExpand: 1000, maxSize: 20});
  } catch (error) {
    errors.push(String(error.message).slice(0, 500));
  }
}
process.stdout.write(JSON.stringify(errors.slice(0, 20)));
