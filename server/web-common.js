// Shared rendering: a small Markdown subset with KaTeX maths, and a maths-aware text input.
const el = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};

function renderMath(source, display) {
  const holder = el('span', undefined, display ? 'math-display' : 'math-inline');
  if (window.katex) {
    try { window.katex.render(source, holder, { displayMode: display, throwOnError: true, trust: false, maxExpand: 1000 }); return holder; }
    catch { /* Fall through and show the source so nothing is lost. */ }
  }
  holder.textContent = display ? `$$${source}$$` : `$${source}$`;
  return holder;
}

// **bold**, *italic*, `code`, [text](https://link) inside a run of non-maths text.
const INLINE = /(\*\*|__)(?=\S)([\s\S]+?)(?<=\S)\1|(\*|_)(?=\S)([^*_]+?)(?<=\S)\3|`([^`]+)`|\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g;
function markdown(text, parent) {
  let index = 0;
  for (const match of text.matchAll(INLINE)) {
    if (match.index > index) parent.append(document.createTextNode(text.slice(index, match.index)));
    if (match[1]) parent.append(withInline(el('strong'), match[2]));
    else if (match[3]) parent.append(withInline(el('em'), match[4]));
    else if (match[5] !== undefined) parent.append(el('code', match[5]));
    else { const a = el('a'); a.href = match[7]; a.target = '_blank'; a.rel = 'noopener noreferrer'; a.append(withInline(el('span'), match[6])); parent.append(a); }
    index = match.index + match[0].length;
  }
  if (index < text.length) parent.append(document.createTextNode(text.slice(index)));
  return parent;
}

// Maths is cut out first so underscores and asterisks inside formulae are never read as Markdown.
function withInline(parent, text) {
  let index = 0;
  for (const match of text.matchAll(/\$\$([\s\S]+?)\$\$|\$([^$\n]+)\$/g)) {
    markdown(text.slice(index, match.index), parent);
    parent.append(renderMath(match[1] ?? match[2], match[1] !== undefined));
    index = match.index + match[0].length;
  }
  return markdown(text.slice(index), parent);
}

const isTableRow = line => /^\s*\|.*\|\s*$/.test(line);
const isTableRule = line => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(line) && line.includes('-');
const cells = line => line.trim().replace(/^\||\|$/g, '').split('|').map(cell => cell.trim());
const LIST = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;

// Presentation only: source snapshots and saved questions keep their citations.
export function readable(text) {
  return String(text || '')
    .replace(/[ \t]*[\[(](?:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}|S\d+)\s*[,;]\s*[a-z]+(?:_[a-z]+)+\s*[\])]/gi, '')
    .replace(/\[?\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b\]?/gi, '')
    .replace(/\[S\d+(?:\s*[,;]\s*S?\d+)*\]/g, '')
    .replace(/\bS\d+\b/g, '')
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
