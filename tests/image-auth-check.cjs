// Run: node tests/image-auth-check.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(require('node:path').join(__dirname, '../server/manage.html'), 'utf8');
const helper = html.slice(html.indexOf('async function authorisedImage('), html.indexOf('    function run(action)'));
const image = { dataset: {} };
let requested;
const context = {
  token: 'cookie-session',
  fetch: async (path, options) => {
    requested = { path, options };
    return { ok: true, blob: async () => ({}) };
  },
  URL: { createObjectURL: () => 'blob:test', revokeObjectURL: () => {} },
  image,
};
(async () => {
  await vm.runInNewContext(helper + '\nauthorisedImage(image, "/diagrams/8/image")', context);
  assert.equal(requested.path, '/diagrams/8/image');
  assert.equal(requested.options.credentials, 'same-origin');
  assert.equal(requested.options.headers, undefined);
  assert.equal(image.src, 'blob:test');
  assert.equal(image.dataset.loaded, 'true');
  console.log('Image cookie-auth check passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
