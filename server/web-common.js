// Shared rendering: a small Markdown subset with KaTeX maths, and a maths-aware text input.
const el = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};

// Models often double the backslash before a command or spacing (text, frac, comma), which LaTeX reads as a line break and wraps the formula.
// Same rule as the Android app: repair only known commands and spacing, never a row break between matrix or aligned rows.
const DOUBLED = /\\\\(?=(?:text|mathrm|mathbf|vec|frac|tfrac|sqrt|ce)\b|[,;!])/g;
// A degree sign inside \text ("\text{^\circ C}") is not valid LaTeX: the sign goes in the formula and the unit stays text.
const DEGREE_IN_TEXT = /\\text\{\s*\^\s*\\circ\s*([^{}]*)\}/g;
export const repairEscapes = source => source.replace(DOUBLED, '\\').replace(DEGREE_IN_TEXT, (_, unit) => `^\\circ\\text{${unit.trim()}}`);

function renderMath(source, display) {
  source = repairEscapes(source);
  const holder = el('span', undefined, display ? 'math-display' : 'math-inline');
  if (window.katex) {
    try { window.katex.render(source, holder, { displayMode: display, throwOnError: true, trust: false, maxExpand: 1000 }); return holder; }
    catch { /* Fall through and show the source so nothing is lost. */ }
  }
  holder.textContent = display ? `$$${source}$$` : `$${source}$`;
  return holder;
}

// **bold**, *italic*, `code`, [text](https://link). Maths is swapped for a placeholder first, so emphasis may wrap a formula
// ("**Wavelength ($\lambda$):**") and underscores or asterisks inside a formula are never read as Markdown.
// An underscore only marks emphasis at a word edge, so file names like Phy_91170_Waves.pdf stay as written.
const INLINE = /(\*\*|__)(?=\S)([\s\S]+?)(?<=\S)\1|\*(?=\S)([^*]+?)(?<=\S)\*|(?<![A-Za-z0-9])_(?=\S)([^_]+?)(?<=\S)_(?![A-Za-z0-9])|`([^`]+)`|\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g;
const HOLD = /(\d+)/g;

// Plain text with any held formulae put back as drawn maths.
function plain(text, parent, maths) {
  let index = 0;
  for (const match of text.matchAll(HOLD)) {
    if (match.index > index) parent.append(document.createTextNode(text.slice(index, match.index)));
    parent.append(renderMath(...maths[Number(match[1])]));
    index = match.index + match[0].length;
  }
  if (index < text.length) parent.append(document.createTextNode(text.slice(index)));
}

function markdown(text, parent, maths) {
  let index = 0;
  for (const match of text.matchAll(INLINE)) {
    if (match.index > index) plain(text.slice(index, match.index), parent, maths);
    if (match[1]) markdown(match[2], parent.appendChild(el('strong')), maths);
    else if (match[3] !== undefined) markdown(match[3], parent.appendChild(el('em')), maths);
    else if (match[4] !== undefined) markdown(match[4], parent.appendChild(el('em')), maths);
    else if (match[5] !== undefined) parent.append(el('code', match[5].replace(HOLD, (_, n) => { const [source, display] = maths[Number(n)]; return display ? `$$${source}$$` : `$${source}$`; })));
    else { const a = parent.appendChild(el('a')); a.href = match[7]; a.target = '_blank'; a.rel = 'noopener noreferrer'; markdown(match[6], a, maths); }
    index = match.index + match[0].length;
  }
  if (index < text.length) plain(text.slice(index), parent, maths);
  return parent;
}

function withInline(parent, text) {
  const maths = [];
  // \( ... \) and \[ ... \] are the same maths as $ ... $ and $$ ... $$.
  const held = String(text).replace(/\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\$([^$\n]+)\$|\\\(([\s\S]+?)\\\)/g, (_, dollars, bracket, dollar, paren) => {
    const block = dollars ?? bracket;
    maths.push([(block ?? dollar ?? paren).trim(), block !== undefined]);
    return `${maths.length - 1}`;
  });
  return markdown(held, parent, maths);
}

// One line of text with its $...$ maths drawn, for titles and labels (mathText makes whole blocks).
export const inlineMath = (text, tag = 'span') => withInline(el(tag), String(text || ''));

const isTableRow = line => /^\s*\|.*\|\s*$/.test(line);
const isTableRule = line => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(line) && line.includes('-');
const cells = line => line.trim().replace(/^\||\|$/g, '').split('|').map(cell => cell.trim());
const LIST = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;

// The global library: everyone reads it, only an administrator edits it. An administrator chooses on the Library page whether they
// are working in their own library or in the global one; while it is global, library requests carry X-Library: global.
export const library = {
  scope: false,   // true while the Library page is the one showing
  global() { try { return Boolean(session.user?.is_admin && this.scope && localStorage.getItem('library') === 'global'); } catch { return false; } },
  set(on) { try { localStorage.setItem('library', on ? 'global' : 'mine'); } catch { /* the choice just is not remembered */ } },
};
export const LIBRARY_PATHS = /^\/(subjects|standards|resources)(\/|$)|^\/topics\/\d+\/(resources|standards|import-papers|search|chunks)(\/|$)/;

// Presentation only: source snapshots and saved questions keep their citations.
export function readable(text) {
  return String(text || '')
    .replace(/[ \t]*[\[(](?:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}|S\d+)\s*[,;]\s*[a-z]+(?:_[a-z]+)+\s*[\])]/gi, '')
    .replace(/\[?\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b\]?/gi, '')
    // A citation that names the file instead of its id: "(Phy_91170_Waves.pdf, p. 6)" or "[notes.pdf, pp. 2-3; slides.pptx]".
    .replace(/[ \t]*[(\[]\s*[^()\[\]\n]*?\.(?:pdf|pptx?|docx?|xlsx?|png|jpe?g|txt)\b(?:\s*[,;]\s*(?:pp?\.|pages?)?\s*\d+(?:\s*[-–,]\s*\d+)*)?(?:\s*;\s*[^()\[\]\n]*?\.(?:pdf|pptx?|docx?|xlsx?|png|jpe?g|txt)\b(?:\s*[,;]\s*(?:pp?\.|pages?)?\s*\d+(?:\s*[-–,]\s*\d+)*)?)*\s*[)\]]/gi, '')
    .replace(/\[S\d+(?:\s*[,;]\s*S?\d+)*\]/g, '')
    .replace(/\bS\d+\b/g, '')
    // A citation whose source id was removed leaves only its page behind: "(, p. 1)" or "(, p. 1;, p. 3)".
    .replace(/[ \t]*[(\[]\s*(?:,?\s*(?:pp?\.|pages?)\s*\d+(?:\s*[-–,]\s*\d+)*\s*;?\s*)+[)\]]/gi, '')
    .replace(/\(\s*\)|\[\s*\]/g, '')
    // Removing a citation can leave a gap before the full stop or comma that followed it.
    .replace(/[ \t]+([.,;:!?])/g, '$1').replace(/[ \t]{2,}/g, ' ');
}

export function mathText(target, content) {
  const text = content === undefined ? target : content;
  const root = el('div', undefined, 'math-content');
  const lines = String(text || '').replace(/\r\n?/g, '\n').split('\n');
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }

    const fence = /^\s*(```|~~~)/.exec(line);
    if (fence) {
      const code = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith(fence[1])) code.push(lines[i++]);
      i++;
      root.append(el('pre', code.join('\n')));
      continue;
    }

    if (/^\s*\$\$/.test(line)) {
      let body = line.trim().slice(2);
      if (!body.includes('$$')) {
        i++;
        while (i < lines.length && !lines[i].includes('$$')) body += '\n' + lines[i++];
        if (i < lines.length) body += '\n' + lines[i];
      }
      i++;
      const closing = body.lastIndexOf('$$');
      const math = closing >= 0 ? body.slice(0, closing) : body;
      const rest = closing >= 0 ? body.slice(closing + 2).trim() : '';
      root.append(renderMath(math.trim(), true));
      if (rest) root.append(withInline(el('p'), rest));
      continue;
    }

    const heading = /^\s*(#{1,6})\s+(.+?)\s*#*\s*$/.exec(line);
    if (heading) { root.append(withInline(el(`h${Math.min(6, heading[1].length + 1)}`), heading[2])); i++; continue; }

    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { root.append(el('hr')); i++; continue; }

    if (/^\s*>/.test(line)) {
      const quote = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) quote.push(lines[i++].replace(/^\s*>\s?/, ''));
      root.append(withInline(el('blockquote'), quote.join('\n')));
      continue;
    }

    if (isTableRow(line) && i + 1 < lines.length && isTableRule(lines[i + 1])) {
      const table = el('table'); const head = el('thead'); const body = el('tbody');
      const headRow = el('tr'); for (const cell of cells(line)) headRow.append(withInline(el('th'), cell));
      head.append(headRow); i += 2;
      while (i < lines.length && isTableRow(lines[i])) {
        const row = el('tr'); for (const cell of cells(lines[i++])) row.append(withInline(el('td'), cell));
        body.append(row);
      }
      table.append(head, body);
      const wrap = el('div', undefined, 'table-scroll'); wrap.append(table); root.append(wrap);
      continue;
    }

    const item = LIST.exec(line);
    if (item) {
      const ordered = /\d/.test(item[2]);
      const list = el(ordered ? 'ol' : 'ul');
      const base = item[1].length;
      while (i < lines.length) {
        const next = LIST.exec(lines[i]);
        if (!next || next[1].length < base || /\d/.test(next[2]) !== ordered) break;
        if (next[1].length > base) { // deeper items belong to the previous entry as a nested list
          const nested = [];
          while (i < lines.length && (LIST.exec(lines[i])?.[1].length ?? 0) > base) nested.push(lines[i++]);
          list.lastElementChild?.append(mathText(nested.join('\n')));
          continue;
        }
        const entry = el('li'); withInline(entry, next[3]); i++;
        // A wrapped continuation line is indented and is not itself a list item or blank.
        while (i < lines.length && lines[i].trim() && /^\s{2,}\S/.test(lines[i]) && !LIST.test(lines[i])) { entry.append(document.createTextNode(' ')); withInline(entry, lines[i++].trim()); }
        list.append(entry);
      }
      root.append(list);
      continue;
    }

    const paragraph = [];
    while (i < lines.length && lines[i].trim() && !/^\s*(#{1,6}\s|```|~~~|>|\$\$)/.test(lines[i]) && !(paragraph.length && (LIST.test(lines[i]) || /^\s*([-*_])(\s*\1){2,}\s*$/.test(lines[i])))) paragraph.push(lines[i++]);
    root.append(withInline(el('p'), paragraph.join('\n')));
  }
  if (content !== undefined) { target.replaceChildren(root); return target; }
  return root;
}

// AI output always sits in the dashed teal container with its verification badge.
export function aiBox(...children) {
  const box = el('div', undefined, 'ai-box');
  box.append(el('span', 'AI generated · verify with sources', 'ai-badge'), ...children);
  return box;
}

// ---- maths input -----------------------------------------------------------
// Each snippet inserts LaTeX; "|" marks where the cursor lands.
const SNIPPETS = [
  ['a⁄b', '\\frac{|}{}', 'Fraction'], ['x²', '^{|}', 'Power'], ['xₙ', '_{|}', 'Subscript'], ['√', '\\sqrt{|}', 'Square root'],
  ['×', '\\times ', 'Times'], ['÷', '\\div ', 'Divide'], ['±', '\\pm ', 'Plus or minus'], ['≈', '\\approx ', 'Approximately'],
  ['≤', '\\leq ', 'Less than or equal'], ['≥', '\\geq ', 'Greater than or equal'], ['Δ', '\\Delta ', 'Delta'], ['π', '\\pi ', 'Pi'],
  ['θ', '\\theta ', 'Theta'], ['λ', '\\lambda ', 'Lambda'], ['μ', '\\mu ', 'Mu'], ['ρ', '\\rho ', 'Rho'], ['→', '\\rightarrow ', 'Arrow'],
  ['⇌', '\\rightleftharpoons ', 'Equilibrium arrow'], ['°', '^{\\circ}', 'Degrees'], ['m s⁻¹', '\\text{ m s}^{-1}', 'Metres per second'],
  ['Chem', '\\ce{|}', 'Chemical formula or equation'],
];

export function mathInput(textarea, { collapsed = false } = {}) {
  const wrap = el('div', undefined, 'math-input');
  const bar = el('div', undefined, 'math-toolbar'); bar.setAttribute('role', 'toolbar'); bar.setAttribute('aria-label', 'Insert maths');
  const preview = el('div', undefined, 'math-preview'); preview.hidden = true;
  const inMaths = () => ((textarea.value.slice(0, textarea.selectionStart).match(/\$/g) || []).length % 2) === 1;
  for (const [label, latex, name] of SNIPPETS) {
    const button = el('button', label, 'small quiet'); button.type = 'button'; button.title = name; button.setAttribute('aria-label', name);
    button.addEventListener('mousedown', event => event.preventDefault()); // keep the cursor in the text box
    button.addEventListener('click', () => {
      const start = textarea.selectionStart, end = textarea.selectionEnd;
      const selected = textarea.value.slice(start, end);
      const cursor = latex.indexOf('|');
      let body = cursor >= 0 ? latex.replace('|', selected) : latex;
      let caret = cursor >= 0 ? cursor + selected.length : body.length;
      if (!inMaths()) { body = `$${body.trimEnd()}$`; caret = cursor >= 0 ? cursor + 1 + (selected ? selected.length : 0) : body.length - 1; }
      textarea.setRangeText(body, start, end, 'end');
      const place = start + caret;
      textarea.focus(); textarea.setSelectionRange(place, place);
      textarea.dispatchEvent(new Event('input', { bubbles: true }));
    });
    bar.append(button);
  }
  let timer = null;
  const draw = () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      const has = /\$[^$]+\$/.test(textarea.value);
      preview.hidden = !has;
      if (has) { preview.replaceChildren(el('span', 'Preview', 'muted'), mathText(textarea.value)); }
    }, 250);
  };
  textarea.addEventListener('input', draw);
  const hint = el('p', 'Write maths between dollar signs, for example $v = f\\lambda$. Use the buttons to insert symbols.', 'muted');
  if (collapsed) {
    // Many answer boxes on one page: keep the symbol bar one tap away instead of repeating it.
    const toggle = el('button', 'Σ Maths', 'small quiet'); toggle.type = 'button'; toggle.setAttribute('aria-expanded', 'false');
    bar.hidden = hint.hidden = true;
    toggle.onclick = () => { bar.hidden = hint.hidden = toggle.getAttribute('aria-expanded') === 'true'; toggle.setAttribute('aria-expanded', String(!bar.hidden)); };
    const tools = el('div', undefined, 'math-tools'); tools.append(toggle, bar);
    wrap.append(textarea, tools, hint, preview);
  } else wrap.append(bar, textarea, preview, hint);
  draw();
  return wrap;
}

// ---- autosave and local recovery --------------------------------------------
// Debounced saver shared by lesson answers and exam answers. The caller owns the data:
// isDirty() says whether the server copy is behind, save() writes it (and must update that
// state on success), status(kind, error) reports 'saving' | 'saved' | 'error' | 'conflict'.
export function autosave({ isDirty, save, status, delay = 800, retryAfter = 6000 }) {
  let timer = null, running = false, again = false, conflict = false;
  const schedule = (wait = delay) => { clearTimeout(timer); timer = setTimeout(run, wait); };
  async function run() {
    clearTimeout(timer);
    if (conflict) return;
    if (running) { again = true; return; }
    running = true;
    try {
      for (let pass = 0; pass < 5; pass++) {
        again = false;
        if (!isDirty()) break;
        status('saving'); await save();
        if (!again && !isDirty()) break;
      }
      status(isDirty() ? 'saving' : 'saved');
      if (isDirty()) schedule();
    } catch (error) {
      if (error?.status === 409 || /another device|changed (?:on|elsewhere)/i.test(error?.message || '')) { conflict = true; status('conflict', error); }
      else { status('error', error); schedule(retryAfter); }
    } finally { running = false; }
  }
  return {
    touch: () => { if (!conflict) { status('saving'); schedule(); } },
    flush: run,
    // After the caller has chosen a side and updated its data, resume saving.
    resume: () => { conflict = false; schedule(0); },
    get conflicted() { return conflict; },
  };
}

// Unsaved text survives a reload or lost connection; the server copy stays the source of truth.
export const stash = {
  read(key) { try { return JSON.parse(localStorage.getItem('sg:' + key) || 'null'); } catch { return null; } },
  write(key, value) { try { localStorage.setItem('sg:' + key, JSON.stringify(value)); } catch { /* private window or full */ } },
  clear(key) { try { localStorage.removeItem('sg:' + key); } catch { /* ignore */ } },
};

// Matches the Android app's SHA-256 answer keys. crypto.subtle only exists on https or
// localhost, so a small fallback keeps keys identical when the site is opened by IP address.
export async function sha256Hex(text) {
  const bytes = new TextEncoder().encode(text);
  if (globalThis.crypto?.subtle) {
    return [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(b => b.toString(16).padStart(2, '0')).join('');
  }
  const K = [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2];
  const h = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
  const length = bytes.length, padded = new Uint8Array(((length + 9 + 63) >> 6) << 6);
  padded.set(bytes); padded[length] = 0x80;
  const view = new DataView(padded.buffer);
  view.setUint32(padded.length - 8, Math.floor(length * 8 / 2 ** 32)); view.setUint32(padded.length - 4, (length * 8) >>> 0);
  const rotr = (x, n) => (x >>> n) | (x << (32 - n));
  const w = new Uint32Array(64);
  for (let offset = 0; offset < padded.length; offset += 64) {
    for (let i = 0; i < 16; i++) w[i] = view.getUint32(offset + i * 4);
    for (let i = 16; i < 64; i++) {
      const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3), s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0;
    }
    let [a, b, c, d, e, f, g, hh] = h;
    for (let i = 0; i < 64; i++) {
      const t1 = (hh + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i]) >>> 0;
      const t2 = ((rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) >>> 0;
      hh = g; g = f; f = e; e = (d + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0;
    }
    [a, b, c, d, e, f, g, hh].forEach((v, i) => { h[i] = (h[i] + v) >>> 0; });
  }
  return h.map(v => v.toString(16).padStart(8, '0')).join('');
}

// Numbers count up to their value with an ease-out curve (no spinner, no placeholder).
export function countUp(node, to, { format = n => String(Math.round(n)), duration = 800 } = {}) {
  if (!Number.isFinite(to) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) { node.textContent = format(to); return; }
  const begin = performance.now();
  node.textContent = format(0);
  const frame = now => {
    const t = Math.min(1, (now - begin) / duration);
    node.textContent = format(to * (1 - Math.pow(1 - t, 3)));
    if (t < 1) requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}


// ---- the signed-in account ---------------------------------------------------------------------
export const session = {
  user: null,
  listeners: [],
  set(user) { this.user = user; for (const listener of this.listeners) listener(user); },
};

// A round profile picture, or the first letter of the username when there is none.
export function avatar(user, size = 32, src = '/me/avatar') {
  const box = el('span', '', 'avatar'); box.style.setProperty('--size', `${size}px`);
  const initial = (user.username || '?').trim()[0]?.toUpperCase() || '?';
  if (user.has_avatar) {
    const image = document.createElement('img'); image.alt = ''; image.src = `${src}?v=${user.avatar_version}`;
    image.onerror = () => { image.remove(); box.textContent = initial; };
    box.append(image);
  } else box.textContent = initial;
  return box;
}

// One saved hint per practice question (hints.py): the first press writes it from what has been answered so far, and every later
// press, on any device, shows that same hint. Used in Review, lessons, revision and rapid questions; never in exams.
export function hintButton(api, { kind, ref, answer = () => '', question = () => '' }) {
  const button = el('button', 'Hint', 'small hint-button'); button.type = 'button';
  const dialog = el('dialog', undefined, 'hint-dialog');
  const path = `/hints/${kind}/${encodeURIComponent(ref)}`;
  const show = (...content) => {
    const close = el('button', 'Close', 'small'); close.type = 'button'; close.onclick = () => dialog.close();
    dialog.replaceChildren(el('h3', 'Hint'), ...content, close);
    if (!dialog.isConnected) document.body.append(dialog);
    if (!dialog.open) dialog.showModal();
  };
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  button.onclick = async () => {
    button.disabled = true; const label = button.textContent; button.textContent = 'Thinking…';
    try {
      const result = await api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answer: answer(), question: question() }) });
      button.textContent = 'Show hint';
      show(mathText(result.hint), el('p', 'One hint per question. It stays the same here and on your other devices.', 'muted'));
    } catch (error) {
      button.textContent = label;
      show(el('p', error.message, 'error'));
    } finally { button.disabled = false; }
  };
  api(path).then(result => { if (result?.hint && !button.disabled) button.textContent = 'Show hint'; }).catch(() => {});
  return button;
}

// A "complete the table" question: the first Markdown table in the question that has empty cells becomes a grid to fill in. The
// filled table is written into the answer box as a Markdown table (replacing an earlier one there), so it is saved, marked and
// restored like any other answer.
const tableLine = line => /^\s*\|.*\|\s*$/.test(line);
const tableCells = line => line.trim().replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/).map(cell => cell.trim());
function firstTable(text) {
  const lines = String(text || '').split('\n');
  for (let i = 0; i < lines.length; i++) {
    if (!tableLine(lines[i])) continue;
    let end = i; while (end < lines.length && tableLine(lines[end])) end++;
    const block = lines.slice(i, end);
    const rows = block.filter(line => !/^\s*\|(\s*:?-{3,}:?\s*\|)+\s*$/.test(line)).map(tableCells);
    if (rows.length >= 2) return { start: i, end, rows };
    i = end;
  }
  return null;
}
export function tableAnswer(question, textarea) {
  const template = firstTable(question);
  if (!template) return null;
  const [header, ...body] = template.rows;
  if (!body.some(row => row.slice(1).some(cell => !cell))) return null;
  const width = header.length;
  const saved = firstTable(textarea.value);
  const values = body.map((row, r) => Array.from({ length: width }, (_, c) => row[c] || (saved?.rows[r + 1]?.[c] ?? '')));
  const write = () => {
    const line = row => `| ${row.map(cell => cell.replace(/\|/g, '\\|').replace(/\s*\n\s*/g, ' ')).join(' | ')} |`;
    const table = [line(header), `| ${header.map(() => '---').join(' | ')} |`, ...values.map(line)].join('\n');
    const lines = textarea.value.split('\n');
    const current = firstTable(textarea.value);
    textarea.value = current ? [...lines.slice(0, current.start), table, ...lines.slice(current.end)].join('\n')
      : textarea.value.trim() ? `${table}\n\n${textarea.value}` : table;
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
  };
  const wrap = el('div', undefined, 'table-answer');
  wrap.append(el('p', 'Fill in the table. It is added to your answer below.', 'muted'));
  const scroll = el('div', undefined, 'table-scroll');
  const table = el('table', undefined, 'table fill-table');
  const head = el('tr');
  for (const cell of header) { const th = el('th'); th.append(inlineMath(cell)); head.append(th); }
  const thead = el('thead'); thead.append(head);
  const tbody = el('tbody');
  body.forEach((row, r) => {
    const tr = el('tr');
    for (let c = 0; c < width; c++) {
      const td = el('td');
      if (row[c]) td.append(inlineMath(row[c]));
      else {
        const input = el('textarea'); input.rows = 2; input.value = values[r][c];
        input.setAttribute('aria-label', `${row[0] || `Row ${r + 1}`}: ${header[c] || `column ${c + 1}`}`);
        input.addEventListener('input', () => { values[r][c] = input.value; write(); });
        td.append(input);
      }
      tr.append(td);
    }
    tbody.append(tr);
  });
  table.append(thead, tbody); scroll.append(table); wrap.append(scroll);
  return wrap;
}
