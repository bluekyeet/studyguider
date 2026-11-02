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

export function mathInput(textarea) {
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
  wrap.append(bar, textarea, preview, hint);
  draw();
  return wrap;
}
