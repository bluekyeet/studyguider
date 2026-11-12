// The answer box: text with a maths and chemistry toolbar, plus a table, drawing or graph when the question needs one
// (docs/design/answer-input-catalogue.md). The forms come from the server (answer_forms.py); the learner can add any other.
//
// The answer is still one piece of text, so saving, drafts, hints and marking are unchanged: the text block as typed, then each
// table as a Markdown table, each drawing as ![Drawing 1](/answer-images/42) and each graph as its image plus a "Graph 1:" line
// describing axes, points and curves (what the marker reads besides the picture). answer_media.py stores the pictures.
//
// answerBox() returns an element that behaves like a textarea for the pages using it: .value, .disabled, focus(), and an
// 'input' event on every change. await box.flush() before submitting, so a drawing still uploading is included.
import { mathText } from './web-common.js';

const el = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined && text !== '') node.textContent = text;
  if (className) node.className = className;
  return node;
};
const btn = (text, className = 'small', title = '') => {
  const node = el('button', text, className); node.type = 'button';
  if (title) { node.title = title; node.setAttribute('aria-label', title); }
  return node;
};

// ---- text with symbols ----------------------------------------------------------------------------------------------------
// [label, LaTeX ("|" is where the cursor lands), name, mhchem form used inside \ce{...}]
const PALETTES = {
  maths: [['a⁄b', '\\frac{|}{}', 'Fraction'], ['x²', '^{|}', 'Power'], ['xₙ', '_{|}', 'Subscript'], ['√', '\\sqrt{|}', 'Square root'],
    ['ⁿ√', '\\sqrt[]{|}', 'nth root'], ['×', '\\times ', 'Times'], ['÷', '\\div ', 'Divide'], ['±', '\\pm ', 'Plus or minus'],
    ['≠', '\\neq ', 'Not equal'], ['≈', '\\approx ', 'Approximately'], ['≤', '\\leq ', 'Less than or equal'], ['≥', '\\geq ', 'Greater than or equal'],
    ['π', '\\pi ', 'Pi'], ['θ', '\\theta ', 'Theta'], ['∞', '\\infty ', 'Infinity'], ['dy⁄dx', '\\frac{dy}{dx}', 'dy by dx'],
    ['d⁄dx', '\\frac{d}{dx}\\left(|\\right)', 'Derivative of'], ['∫', '\\int |\\,dx', 'Integral'], ['∫ₐᵇ', '\\int_{|}^{} \\,dx', 'Definite integral'],
    ['lim', '\\lim_{x \\to |}', 'Limit'], ['eˣ', 'e^{|}', 'e to the power'], ['ln', '\\ln(|)', 'Natural log'], ['sin', '\\sin ', 'Sine'],
    ['cos', '\\cos ', 'Cosine'], ['tan', '\\tan ', 'Tangent'], ['|x|', '\\left|\\,|\\,\\right|', 'Absolute value'], ['Σ', '\\sum ', 'Sum'],
    ['→', '\\rightarrow ', 'Arrow'], ['⇒', '\\Rightarrow ', 'Implies']],
  chemistry: [['Chem', '\\ce{|}', 'Chemical formula or equation'], ['→', '\\rightarrow ', 'Reaction arrow', '->'],
    ['⇌', '\\rightleftharpoons ', 'Equilibrium arrow', '<=>'], ['x₂', '_{|}', 'Subscript', '_'], ['x⁺', '^{+}', 'Positive charge', '^+'],
    ['x⁻', '^{-}', 'Negative charge', '^-'], ['x²⁺', '^{2+}', 'Charge 2+', '^2+'], ['x²⁻', '^{2-}', 'Charge 2−', '^2-'],
    ['(s)', '\\text{(s)}', 'Solid', '(s)'], ['(l)', '\\text{(l)}', 'Liquid', '(l)'], ['(g)', '\\text{(g)}', 'Gas', '(g)'], ['(aq)', '\\text{(aq)}', 'Aqueous', '(aq)'],
    ['e⁻', 'e^{-}', 'Electron', 'e-'], ['[ ]', '[\\ce{|}]', 'Concentration'], ['Kₐ', 'K_a', 'Acid constant'], ['Kₛ', 'K_s', 'Solubility product'],
    ['ΔH', '\\Delta H', 'Enthalpy change'], ['ΔᵣH°', '\\Delta_r H^\\circ', 'Standard reaction enthalpy'], ['kJ mol⁻¹', '\\text{ kJ mol}^{-1}', 'Kilojoules per mole'],
    ['mol L⁻¹', '\\text{ mol L}^{-1}', 'Moles per litre'], ['δ+', '\\delta^{+}', 'Partial positive'], ['δ−', '\\delta^{-}', 'Partial negative'],
    ['a⁄b', '\\frac{|}{}', 'Fraction'], ['×10ⁿ', '\\times 10^{|}', 'Times ten to the power'], ['°', '^{\\circ}', 'Degrees']],
  physics: [['a⁄b', '\\frac{|}{}', 'Fraction'], ['x²', '^{|}', 'Power'], ['xₙ', '_{|}', 'Subscript'], ['√', '\\sqrt{|}', 'Square root'],
    ['×', '\\times ', 'Times'], ['×10ⁿ', '\\times 10^{|}', 'Times ten to the power'], ['≈', '\\approx ', 'Approximately'], ['Δ', '\\Delta ', 'Delta'],
    ['v⃗', '\\vec{|}', 'Vector'], ['Σ', '\\Sigma ', 'Sum'], ['m s⁻¹', '\\text{ m s}^{-1}', 'Metres per second'], ['m s⁻²', '\\text{ m s}^{-2}', 'Metres per second squared'],
    ['N', '\\text{ N}', 'Newtons'], ['J', '\\text{ J}', 'Joules'], ['W', '\\text{ W}', 'Watts'], ['Ω', '\\,\\Omega', 'Ohms'], ['Hz', '\\text{ Hz}', 'Hertz'],
    ['rad s⁻¹', '\\text{ rad s}^{-1}', 'Radians per second'], ['kg m²', '\\text{ kg m}^{2}', 'Kilogram metre squared'], ['°', '^{\\circ}', 'Degrees'],
    ['sin', '\\sin ', 'Sine'], ['cos', '\\cos ', 'Cosine'], ['π', '\\pi ', 'Pi']],
  greek: [['α', '\\alpha ', 'Alpha'], ['β', '\\beta ', 'Beta'], ['γ', '\\gamma ', 'Gamma'], ['δ', '\\delta ', 'Delta'], ['Δ', '\\Delta ', 'Capital delta'],
    ['ε', '\\varepsilon ', 'Epsilon'], ['θ', '\\theta ', 'Theta'], ['λ', '\\lambda ', 'Lambda'], ['μ', '\\mu ', 'Mu'], ['π', '\\pi ', 'Pi'],
    ['ρ', '\\rho ', 'Rho'], ['σ', '\\sigma ', 'Sigma'], ['τ', '\\tau ', 'Tau'], ['φ', '\\phi ', 'Phi'], ['ω', '\\omega ', 'Omega'], ['Ω', '\\Omega ', 'Capital omega']],
};
const PALETTE_NAMES = { maths: 'Maths', chemistry: 'Chemistry', physics: 'Physics', greek: 'Greek' };

// Inside $...$ when an odd number of dollar signs precede the cursor; inside \ce{...} when one is open before it.
const inMaths = (text, at) => ((text.slice(0, at).match(/\$/g) || []).length % 2) === 1;
function inCe(text, at) {
  const open = text.lastIndexOf('\\ce{', at);
  if (open < 0) return false;
  let depth = 0;
  for (let i = open + 3; i < at; i++) { if (text[i] === '{') depth++; else if (text[i] === '}') depth--; }
  return depth > 0;
}

function insertSnippet(textarea, latex, ce) {
  const start = textarea.selectionStart, end = textarea.selectionEnd, text = textarea.value;
  const selected = text.slice(start, end);
  let body = inCe(text, start) && ce !== undefined ? ce : latex;
  const cursor = body.indexOf('|');
  let caret = cursor >= 0 ? cursor + selected.length : body.length;
  body = cursor >= 0 ? body.replace('|', selected) : body;
  if (!inMaths(text, start)) { body = `$${body.trimEnd()}$`; caret += 1; if (cursor < 0) caret = body.length; }
  textarea.setRangeText(body, start, end, 'end');
  textarea.focus(); textarea.setSelectionRange(start + caret, start + caret);
  textarea.dispatchEvent(new Event('input', { bubbles: true }));
}

function richText(textarea, { palette = 'general', collapsed = false }) {
  const wrap = el('div', undefined, 'math-input rich-text');
  const tools = el('div', undefined, 'rich-tools');
  const tabs = el('div', undefined, 'palette-tabs'); tabs.setAttribute('role', 'tablist'); tabs.setAttribute('aria-label', 'Symbol sets');
  const bar = el('div', undefined, 'math-toolbar'); bar.setAttribute('role', 'toolbar'); bar.setAttribute('aria-label', 'Insert symbols');
  let current = PALETTES[palette] ? palette : 'maths';
  const draw = () => {
    bar.replaceChildren();
    for (const [label, latex, name, ce] of PALETTES[current]) {
      const button = btn(label, 'small quiet', name);
      button.addEventListener('mousedown', event => event.preventDefault());     // keep the cursor in the text box
      button.addEventListener('click', () => insertSnippet(textarea, latex, ce));
      bar.append(button);
    }
    for (const tab of tabs.children) tab.setAttribute('aria-selected', String(tab.dataset.key === current));
  };
  for (const key of Object.keys(PALETTES)) {
    const tab = btn(PALETTE_NAMES[key], 'small quiet'); tab.dataset.key = key; tab.setAttribute('role', 'tab');
    tab.addEventListener('mousedown', event => event.preventDefault());
    tab.onclick = () => { current = key; draw(); };
    tabs.append(tab);
  }
  draw();
  tools.append(tabs, bar);
  // Chemistry: an equation typed as written (mhchem), shown as it will look, then added to the answer as $\ce{...}$.
  const equation = el('div', undefined, 'equation-line');
  const line = el('input'); line.type = 'text'; line.placeholder = 'Type an equation: Fe^3+ + 3OH- -> Fe(OH)3(s)';
  line.setAttribute('aria-label', 'Chemical equation'); line.autocapitalize = 'off'; line.spellcheck = false;
  const shown = el('span', undefined, 'equation-preview');
  const add = btn('Add equation', 'small');
  line.addEventListener('input', () => {
    shown.replaceChildren();
    if (line.value.trim() && window.katex) {
      try { window.katex.render(`\\ce{${line.value}}`, shown, { throwOnError: true }); } catch { shown.textContent = 'Keep typing…'; }
    }
  });
  const addLine = () => {
    if (!line.value.trim()) return;
    const value = textarea.value;
    textarea.value = `${value}${value && !value.endsWith('\n') ? '\n' : ''}$\\ce{${line.value.trim()}}$\n`;
    line.value = ''; shown.replaceChildren();
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
  };
  add.onclick = addLine;
  line.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); addLine(); } });
  equation.append(line, add, shown);
  equation.hidden = current !== 'chemistry';
  tabs.addEventListener('click', () => { equation.hidden = current !== 'chemistry'; });

  const preview = el('div', undefined, 'math-preview'); preview.hidden = true;
  let timer = null;
  const render = () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      const has = /\$[^$]+\$/.test(textarea.value);
      preview.hidden = !has;
      if (has) preview.replaceChildren(el('span', 'Preview', 'muted'), mathText(textarea.value));
    }, 250);
  };
  textarea.addEventListener('input', render);
  const hint = el('p', 'Maths goes between dollar signs, for example $v = f\\lambda$; the buttons add symbols for you.', 'muted');
  if (collapsed) {
    const toggle = btn('Σ Symbols', 'small quiet'); toggle.setAttribute('aria-expanded', 'false');
    tools.hidden = hint.hidden = equation.hidden = true;
    toggle.onclick = () => {
      const open = toggle.getAttribute('aria-expanded') !== 'true';
      toggle.setAttribute('aria-expanded', String(open));
      tools.hidden = hint.hidden = !open; equation.hidden = !open || current !== 'chemistry';
    };
    wrap.append(textarea, toggle, tools, equation, hint, preview);
  } else wrap.append(tools, equation, textarea, preview, hint);
  render();
  return wrap;
}

// ---- tables -----------------------------------------------------------------------------------------------------------------
const tableLine = line => /^\s*\|.*\|\s*$/.test(line);
const ruleLine = line => /^\s*\|(\s*:?-{3,}:?\s*\|)+\s*$/.test(line);
const tableCells = line => line.trim().replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/).map(cell => cell.trim().replace(/\\\|/g, '|'));

function tableBlock(form, saved, changed) {
  // Given cells (headers, row labels) are fixed; blank ones are filled in. With no template the learner builds the table.
  const fixed = form.columns?.length ? { columns: form.columns, rows: form.rows || [] } : null;
  let columns = saved?.[0] || fixed?.columns || ['', '', ''];
  let rows = saved ? saved.slice(1) : fixed ? fixed.rows.map(row => row.slice()) : [['', '', ''], ['', '', '']];
  const width = () => columns.length;
  rows = rows.map(row => Array.from({ length: width() }, (_, c) => row[c] ?? ''));
  const given = (r, c) => fixed && fixed.rows[r]?.[c];
  const node = el('div', undefined, 'answer-block table-answer');
  const head = el('div', undefined, 'block-head');
  head.append(el('strong', fixed ? 'Complete the table' : 'Your table'));
  const scroll = el('div', undefined, 'table-scroll');
  const tools = el('div', undefined, 'toolbar');
  const draw = () => {
    const table = el('table', undefined, 'table fill-table');
    const tr = el('tr');
    columns.forEach((name, c) => {
      const th = el('th');
      if (fixed) th.append(mathText(name)); else {
        const input = el('input'); input.value = name; input.placeholder = `Heading ${c + 1}`; input.setAttribute('aria-label', `Column ${c + 1} heading`);
        input.oninput = () => { columns[c] = input.value; changed(); };
        th.append(input);
      }
      tr.append(th);
    });
    const thead = el('thead'); thead.append(tr);
    const tbody = el('tbody');
    rows.forEach((row, r) => {
      const line = el('tr');
      row.forEach((cell, c) => {
        const td = el('td');
        if (given(r, c)) td.append(mathText(fixed.rows[r][c]));
        else {
          const input = el('textarea'); input.rows = 2; input.value = cell;
          input.setAttribute('aria-label', `${row[0] && c ? row[0] : `Row ${r + 1}`}, ${columns[c] || `column ${c + 1}`}`);
          input.oninput = () => { rows[r][c] = input.value; changed(); };
          td.append(input);
        }
        line.append(td);
      });
      tbody.append(line);
    });
    table.append(thead, tbody);
    scroll.replaceChildren(table);
  };
  if (!fixed) {
    const addRow = btn('+ Row'); addRow.onclick = () => { rows.push(Array(width()).fill('')); draw(); changed(); };
    const addColumn = btn('+ Column'); addColumn.onclick = () => { if (width() < 8) { columns.push(''); rows.forEach(row => row.push('')); draw(); changed(); } };
    const removeRow = btn('− Row'); removeRow.onclick = () => { if (rows.length > 1) { rows.pop(); draw(); changed(); } };
    const removeColumn = btn('− Column'); removeColumn.onclick = () => { if (width() > 1) { columns.pop(); rows.forEach(row => row.pop()); draw(); changed(); } };
    tools.append(addRow, removeRow, addColumn, removeColumn);
  }
  tools.hidden = Boolean(fixed);
  node.append(head, scroll, tools);
  draw();
  const clean = cell => String(cell).replace(/\|/g, '\\|').replace(/\s*\n\s*/g, ' ').trim();
  return {
    node, kind: 'table',
    text() {
      if (!rows.some((row, r) => row.some((cell, c) => !given(r, c) && cell.trim())) && !(!fixed && columns.some(c => c.trim()))) return '';
      const line = row => `| ${row.map(clean).join(' | ')} |`;
      return [line(columns), `| ${columns.map(() => '---').join(' | ')} |`, ...rows.map(line)].join('\n');
    },
    set disabled(on) { for (const input of node.querySelectorAll('input, textarea, button')) input.disabled = on; },
  };
}

// ---- drawing and graph canvas ------------------------------------------------------------------------------------------------
const INK = { ink: '#1a1c24', blue: '#2f48b8', red: '#c0262d' };
const PAPER = '#ffffff', GRID = '#dbe1ec', AXIS = '#3a3f4f';

const round = (value, step) => {
  const digits = Math.max(0, -Math.floor(Math.log10(step || 1)));
  return Number((Math.round(value / step) * step).toFixed(Math.min(digits, 6)));
};

function sketchBlock({ graph, form, saved, figure, upload, changed, number }) {
  const W = 800, H = graph ? 560 : 500;
  const state = saved?.items ? saved : { items: [] };
  const spec = graph ? {
    x_label: saved?.x_label ?? form.x_label ?? '', y_label: saved?.y_label ?? form.y_label ?? '',
    x_range: saved?.x_range ?? form.x_range ?? null, y_range: saved?.y_range ?? form.y_range ?? null,
  } : null;
  let background = saved?.background || form.background || 'blank';
  if (background === 'figure' && !figure) background = 'grid';
  let tool = 'pen', colour = 'ink', undone = [], imageId = saved?.imageId || null, dirty = false, pending = null, timer = null;
  const node = el('div', undefined, `answer-block sketch ${graph ? 'graph' : 'drawing'}`);
  const head = el('div', undefined, 'block-head');
  const title = el('strong', graph ? `Graph ${number}` : `Drawing ${number}`);
  const status = el('span', '', 'muted sketch-status'); status.setAttribute('role', 'status');
  head.append(title, status);
  const canvas = el('canvas'); canvas.width = W; canvas.height = H;
  canvas.setAttribute('aria-label', graph ? 'Graph area: draw with a finger, pen or mouse' : 'Drawing area: draw with a finger, pen or mouse');
  canvas.setAttribute('role', 'img');
  const frame = el('div', undefined, 'sketch-frame'); frame.style.aspectRatio = `${W} / ${H}`; frame.append(canvas);

  const tools = el('div', undefined, 'sketch-tools'); tools.setAttribute('role', 'toolbar'); tools.setAttribute('aria-label', 'Drawing tools');
  const toolNames = graph
    ? [['pen', 'Curve', 'Draw a freehand curve'], ['line', 'Line', 'Draw a straight line'], ['point', 'Point', 'Plot a point'], ['text', 'Label', 'Add a text label'], ['erase', 'Erase', 'Rub out whatever you touch']]
    : [['pen', 'Pen', 'Draw freehand'], ['line', 'Line', 'Draw a straight line or bond'], ['arrow', 'Arrow', 'Draw an arrow (force, ray, reaction step)'], ['text', 'Label', 'Add a text label, such as an atom symbol'], ['erase', 'Erase', 'Rub out whatever you touch']];
  const toolButtons = toolNames.map(([key, label, name]) => {
    const button = btn(label, 'small', name); button.dataset.tool = key;
    button.onclick = () => { tool = key; for (const b of toolButtons) b.setAttribute('aria-pressed', String(b.dataset.tool === tool)); };
    button.setAttribute('aria-pressed', String(key === tool));
    return button;
  });
  const colours = Object.keys(INK).map(key => {
    const button = btn('', 'small swatch', `${key === 'ink' ? 'Black' : key[0].toUpperCase() + key.slice(1)} ink`);
    button.style.setProperty('--swatch', INK[key]); button.dataset.colour = key;
    button.setAttribute('aria-pressed', String(key === colour));
    button.onclick = () => { colour = key; for (const b of colours) b.setAttribute('aria-pressed', String(b.dataset.colour === colour)); };
    return button;
  });
  const undo = btn('Undo', 'small quiet'), redo = btn('Redo', 'small quiet'), clear = btn('Clear', 'small quiet');
  undo.onclick = () => { if (state.items.length) { undone.push(state.items.pop()); edited(); } };
  redo.onclick = () => { if (undone.length) { state.items.push(undone.pop()); edited(); } };
  clear.onclick = () => { if (state.items.length && window.confirm('Clear this drawing?')) { undone = []; state.items = []; edited(); } };
  tools.append(...toolButtons, el('span', undefined, 'tool-gap'), ...colours, el('span', undefined, 'tool-gap'), undo, redo, clear);
  if (!graph) {
    const choose = el('select'); choose.setAttribute('aria-label', 'Background');
    for (const [value, label] of [['blank', 'Blank'], ['grid', 'Grid'], ...(figure ? [['figure', 'The question’s figure']] : [])]) choose.add(new Option(label, value));
    choose.value = background;
    choose.onchange = () => { background = choose.value; edited(); };
    tools.append(choose);
  }

  // Graph axes: labels and optional ranges. With no range the grid is counted in squares from the origin.
  const axes = el('div', undefined, 'graph-axes');
  if (graph) {
    const field = (label, value, set, type = 'text') => {
      const wrap = el('label', label);
      const input = el('input'); input.type = type; input.value = value ?? ''; if (type === 'number') input.step = 'any';
      input.oninput = () => { set(input.value); edited(false); };
      wrap.append(input); axes.append(wrap); return input;
    };
    field('x-axis label', spec.x_label, v => { spec.x_label = v.slice(0, 40); });
    field('y-axis label', spec.y_label, v => { spec.y_label = v.slice(0, 40); });
    const range = (axis, end) => field(`${axis} ${end ? 'max' : 'min'}`, spec[`${axis}_range`]?.[end], v => {
      const r = spec[`${axis}_range`] || [null, null]; r[end] = v === '' ? null : Number(v);
      spec[`${axis}_range`] = Number.isFinite(r[0]) && Number.isFinite(r[1]) && r[0] < r[1] ? r : (r[0] === null && r[1] === null ? null : r);
    }, 'number');
    range('x', 0); range('x', 1); range('y', 0); range('y', 1);
    axes.append(el('p', 'Ranges are optional: leave them empty to sketch, and positions are then given in grid squares from the origin.', 'muted'));
  }

  // ----- coordinates for graphs
  const GX = 20, GY = 14, cell = W / GX;      // 40 px squares
  const ranged = axis => { const r = spec?.[`${axis}_range`]; return Array.isArray(r) && Number.isFinite(r[0]) && Number.isFinite(r[1]) && r[0] < r[1] ? r : null; };
  const origin = () => {
    const xr = ranged('x'), yr = ranged('y');
    const ox = xr ? (xr[0] >= 0 ? 0 : xr[1] <= 0 ? W : (-xr[0] / (xr[1] - xr[0])) * W) : Math.round(GX / 2) * cell;
    const oy = yr ? (yr[0] >= 0 ? H : yr[1] <= 0 ? 0 : H - (-yr[0] / (yr[1] - yr[0])) * H) : Math.round(GY / 2) * cell;
    return [ox, oy];
  };
  const toData = ([px, py]) => {
    const xr = ranged('x'), yr = ranged('y'), [ox, oy] = origin();
    return [xr ? xr[0] + px / W * (xr[1] - xr[0]) : (px - ox) / cell, yr ? yr[0] + (H - py) / H * (yr[1] - yr[0]) : (oy - py) / cell];
  };
  const steps = () => { const xr = ranged('x'), yr = ranged('y'); return [xr ? (xr[1] - xr[0]) / 100 : 0.1, yr ? (yr[1] - yr[0]) / 100 : 0.1]; };
  const fmt = ([x, y]) => { const [sx, sy] = steps(); return `(${round(x, sx)}, ${round(y, sy)})`; };

  // ----- drawing
  let figureImage = null;
  if (figure) { figureImage = new Image(); figureImage.onload = () => paint(); figureImage.src = figure; }
  function paintBackground(ctx) {
    ctx.fillStyle = PAPER; ctx.fillRect(0, 0, W, H);
    if (background === 'figure' && figureImage?.complete && figureImage.naturalWidth) {
      const scale = Math.min(W / figureImage.naturalWidth, H / figureImage.naturalHeight);
      const w = figureImage.naturalWidth * scale, h = figureImage.naturalHeight * scale;
      ctx.drawImage(figureImage, (W - w) / 2, (H - h) / 2, w, h);
    }
    if (graph || background === 'grid') {
      ctx.strokeStyle = GRID; ctx.lineWidth = 1; ctx.beginPath();
      for (let x = cell; x < W; x += cell) { ctx.moveTo(x + .5, 0); ctx.lineTo(x + .5, H); }
      for (let y = cell; y < H; y += cell) { ctx.moveTo(0, y + .5); ctx.lineTo(W, y + .5); }
      ctx.stroke();
    }
    if (graph) {
      const [ox, oy] = origin();
      ctx.strokeStyle = AXIS; ctx.lineWidth = 2; ctx.beginPath();
      ctx.moveTo(Math.min(Math.max(ox, 1), W - 1), H); ctx.lineTo(Math.min(Math.max(ox, 1), W - 1), 0);
      ctx.moveTo(0, Math.min(Math.max(oy, 1), H - 1)); ctx.lineTo(W, Math.min(Math.max(oy, 1), H - 1)); ctx.stroke();
      ctx.fillStyle = AXIS; ctx.font = 'italic 20px serif';
      ctx.textAlign = 'right'; ctx.fillText(spec.x_label || 'x', W - 8, Math.min(Math.max(oy, 24), H - 4) - 8);
      ctx.textAlign = 'left'; ctx.fillText(spec.y_label || 'y', Math.min(Math.max(ox, 0), W - 80) + 8, 22);
      const xr = ranged('x'), yr = ranged('y');
      ctx.font = '13px sans-serif'; ctx.fillStyle = '#555b6e';
      if (xr) { ctx.textAlign = 'left'; ctx.fillText(String(xr[0]), 4, Math.min(Math.max(oy, 14), H - 4) + 16); ctx.textAlign = 'right'; ctx.fillText(String(xr[1]), W - 4, Math.min(Math.max(oy, 14), H - 22) + 16); }
      if (yr) { ctx.textAlign = 'left'; ctx.fillText(String(yr[1]), Math.min(Math.max(ox, 0), W - 60) + 6, 40); ctx.fillText(String(yr[0]), Math.min(Math.max(ox, 0), W - 60) + 6, H - 6); }
    }
  }
  function paintItem(ctx, item) {
    ctx.strokeStyle = ctx.fillStyle = INK[item.c] || INK.ink; ctx.lineWidth = item.t === 'pen' ? 3 : 2.5; ctx.lineCap = ctx.lineJoin = 'round';
    if (item.t === 'pen') {
      ctx.beginPath(); item.p.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      if (item.p.length === 1) ctx.lineTo(item.p[0][0] + .1, item.p[0][1]);
      ctx.stroke();
    } else if (item.t === 'line' || item.t === 'arrow') {
      const [[x0, y0], [x1, y1]] = item.p;
      ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
      if (item.t === 'arrow') {
        const a = Math.atan2(y1 - y0, x1 - x0), s = 16;
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x1 - s * Math.cos(a - .4), y1 - s * Math.sin(a - .4));
        ctx.lineTo(x1 - s * Math.cos(a + .4), y1 - s * Math.sin(a + .4)); ctx.closePath(); ctx.fill();
      }
    } else if (item.t === 'point') {
      const [x, y] = item.p[0]; ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2); ctx.fill();
      ctx.font = '13px sans-serif'; ctx.textAlign = 'left'; ctx.fillText(fmt(toData(item.p[0])), x + 8, y - 8);
    } else if (item.t === 'text') {
      ctx.font = '28px sans-serif'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillText(item.s, item.p[0][0], item.p[0][1]); ctx.textBaseline = 'alphabetic';
    }
  }
  function paint(target = canvas, scale = 1) {
    const ctx = target.getContext('2d');
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    paintBackground(ctx);
    for (const item of state.items) paintItem(ctx, item);
    if (live) paintItem(ctx, live);
  }
  // The canvas keeps a backing store matching the screen, so lines stay sharp on a phone.
  const fit = () => {
    const ratio = Math.min(2, window.devicePixelRatio || 1), width = frame.clientWidth || W;
    const scale = width / W * ratio;
    if (canvas.width !== Math.round(W * scale)) { canvas.width = Math.round(W * scale); canvas.height = Math.round(H * scale); }
    paint(canvas, scale);
  };
  const resize = new ResizeObserver(fit); resize.observe(frame);

  let live = null, drawing = false;
  const point = event => { const r = canvas.getBoundingClientRect(); return [Math.round((event.clientX - r.left) / r.width * W * 10) / 10, Math.round((event.clientY - r.top) / r.height * H * 10) / 10]; };
  const near = (item, [x, y]) => item.p.some(([px, py]) => Math.hypot(px - x, py - y) < 14)
    || ((item.t === 'line' || item.t === 'arrow') && (() => {
      const [[x0, y0], [x1, y1]] = item.p, len = Math.hypot(x1 - x0, y1 - y0) || 1;
      const t = Math.max(0, Math.min(1, ((x - x0) * (x1 - x0) + (y - y0) * (y1 - y0)) / len ** 2));
      return Math.hypot(x0 + t * (x1 - x0) - x, y0 + t * (y1 - y0) - y) < 12;
    })())
    || (item.t === 'text' && x >= item.p[0][0] - 6 && x <= item.p[0][0] + 16 * item.s.length && Math.abs(y - item.p[0][1]) < 16);
  canvas.addEventListener('pointerdown', event => {
    if (node.dataset.disabled === 'true') return;
    event.preventDefault(); canvas.setPointerCapture(event.pointerId);
    const p = point(event);
    if (tool === 'text') {
      const words = window.prompt(graph ? 'Label' : 'Label (for example Cl, F, δ+, N, Weight)');
      if (words && words.trim()) { state.items.push({ t: 'text', p: [p], s: words.trim().slice(0, 40), c: colour }); undone = []; edited(); }
      return;
    }
    if (tool === 'point') { state.items.push({ t: 'point', p: [p], c: colour }); undone = []; edited(); return; }
    drawing = true;
    if (tool === 'erase') { erase(p); return; }
    live = { t: tool, p: tool === 'pen' ? [p] : [p, p], c: colour };
    fit();
  });
  canvas.addEventListener('pointermove', event => {
    if (!drawing) return;
    const p = point(event);
    if (tool === 'erase') { erase(p); return; }
    if (!live) return;
    if (live.t === 'pen') { const last = live.p[live.p.length - 1]; if (Math.hypot(p[0] - last[0], p[1] - last[1]) > 1.5) live.p.push(p); }
    else live.p[1] = p;
    fit();
  });
  const end = () => {
    if (!drawing) return;
    drawing = false;
    if (live && (live.t === 'pen' || Math.hypot(live.p[1][0] - live.p[0][0], live.p[1][1] - live.p[0][1]) > 4)) { state.items.push(live); undone = []; }
    live = null; edited();
  };
  canvas.addEventListener('pointerup', end); canvas.addEventListener('pointercancel', end);
  function erase(p) {
    const before = state.items.length;
    state.items = state.items.filter(item => !near(item, p));
    if (state.items.length !== before) { undone = []; fit(); dirty = true; }
  }

  // ----- saving: a PNG with the vector items, uploaded a moment after the last change
  function edited(repaint = true) {
    if (repaint) fit(); else fit();
    dirty = true; imageId = state.items.length ? imageId : null;
    status.textContent = state.items.length ? 'Not saved yet…' : '';
    clearTimeout(timer); timer = setTimeout(save, 1200);
    changed();
  }
  async function save() {
    clearTimeout(timer);
    if (!dirty) return pending;
    dirty = false;
    if (!state.items.length) { imageId = null; status.textContent = ''; changed(); return; }
    const out = el('canvas'); out.width = W * 1.5; out.height = H * 1.5;
    paint(out, 1.5); fit();
    const blob = await new Promise(resolve => out.toBlob(resolve, 'image/png'));
    const form = new FormData();
    form.append('image', blob, 'drawing.png');
    form.append('drawing', JSON.stringify({ kind: graph ? 'graph' : 'drawing', background, items: state.items, ...(spec || {}) }));
    status.textContent = 'Saving drawing…';
    pending = upload(form).then(result => {
      if (!dirty) { imageId = result.id; status.textContent = 'Drawing saved'; changed(); }
    }).catch(error => { dirty = true; status.textContent = `Drawing not saved (${error.message || 'offline'}). Retrying…`; timer = setTimeout(save, 5000); });
    return pending;
  }

  // What the marker reads about a graph besides the picture: axes, points, lines, and the shape of each curve.
  function describe() {
    const units = ranged('x') && ranged('y') ? '' : ' (no scale given: positions are in grid squares from the origin)';
    const parts = [`x-axis "${spec.x_label || 'x'}"${ranged('x') ? ` from ${ranged('x')[0]} to ${ranged('x')[1]}` : ''}, y-axis "${spec.y_label || 'y'}"${ranged('y') ? ` from ${ranged('y')[0]} to ${ranged('y')[1]}` : ''}${units}.`];
    const points = state.items.filter(i => i.t === 'point').map(i => fmt(toData(i.p[0])));
    if (points.length) parts.push(`Points plotted: ${points.join(', ')}.`);
    state.items.filter(i => i.t === 'line').forEach((i, n) => parts.push(`Straight line ${n + 1} from ${fmt(toData(i.p[0]))} to ${fmt(toData(i.p[1]))}.`));
    state.items.filter(i => i.t === 'pen' && i.p.length > 2).slice(0, 6).forEach((i, n) => {
      const data = i.p.map(toData);
      const crossings = (axis) => {
        const found = [];
        for (let k = 1; k < data.length; k++) {
          const a = data[k - 1][axis], b = data[k][axis];
          if (a === 0 || (a < 0) !== (b < 0)) {
            const t = a === b ? 0 : a / (a - b), other = 1 - axis;
            const value = data[k - 1][other] + t * (data[k][other] - data[k - 1][other]);
            if (!found.some(v => Math.abs(v - value) < steps()[other] * 4)) found.push(value);
          }
        }
        return found.slice(0, 6).map(v => round(v, steps()[1 - axis]));
      };
      const xs = crossings(1), ys = crossings(0);
      // Turning points: where the curve's vertical direction reverses by more than a small wobble.
      const turns = [];
      let direction = 0, extreme = data[0];
      for (const p of data.slice(1)) {
        const change = p[1] - extreme[1], wobble = steps()[1] * 3;
        if (direction >= 0 && p[1] >= extreme[1]) { extreme = p; direction = 1; continue; }
        if (direction <= 0 && p[1] <= extreme[1]) { extreme = p; direction = -1; continue; }
        if (Math.abs(change) > wobble) { turns.push(`${direction > 0 ? 'maximum' : 'minimum'} near ${fmt(extreme)}`); direction = -direction; extreme = p; }
      }
      let line = `Curve ${n + 1} drawn from ${fmt(data[0])} to ${fmt(data[data.length - 1])}`;
      if (xs.length) line += `; crosses the x-axis near x = ${xs.join(', ')}`;
      if (ys.length) line += `; crosses the y-axis near y = ${ys.join(', ')}`;
      if (turns.length) line += `; ${turns.slice(0, 6).join(', ')}`;
      parts.push(line + '.');
    });
    const labels = state.items.filter(i => i.t === 'text').map(i => `"${i.s}" at ${fmt(toData(i.p[0]))}`);
    if (labels.length) parts.push(`Labels: ${labels.join(', ')}.`);
    return parts.join(' ');
  }

  node.append(head, ...(graph ? [axes] : []), frame, tools);
  if (!graph && form.purpose === 'lewis') node.append(el('p', 'Use Label for each atom symbol, Line for bonds and Pen for lone-pair dots. Or draw it on paper and upload a photo.', 'muted'));
  if (!graph && form.purpose === 'structure') node.append(el('p', 'Use Label for atoms and groups (CH₃, OH, C=O), Line for bonds and Arrow for reaction steps with the reagents labelled over them. A photo of a structure drawn on paper also works.', 'muted'));
  return {
    node, kind: graph ? 'graph' : 'drawing',
    set number(n) { number = n; title.textContent = `${graph ? 'Graph' : 'Drawing'} ${n}`; },
    text() {
      if (!imageId || !state.items.length) return '';
      const name = `${graph ? 'Graph' : 'Drawing'} ${number}`;
      return `![${name}](/answer-images/${imageId})` + (graph ? `\n${name}: ${describe()}` : '');
    },
    flush: () => (dirty ? save() : pending || Promise.resolve()),
    set disabled(on) { node.dataset.disabled = String(on); for (const b of node.querySelectorAll('button, input, select')) b.disabled = on; },
  };
}

// ---- the box ----------------------------------------------------------------------------------------------------------------
const IMAGE_LINE = /^!\[((?:Drawing|Graph) \d+)\]\(\/answer-images\/(\d+)\)\s*$/;

// Split saved answer text back into its blocks: tables, drawings (with a graph's description line) and the rest as text.
export function splitAnswer(value) {
  const lines = String(value || '').split('\n');
  const tables = [], images = [], text = [];
  for (let i = 0; i < lines.length; i++) {
    if (tableLine(lines[i]) && i + 1 < lines.length && ruleLine(lines[i + 1])) {
      const rows = [tableCells(lines[i])]; i += 2;
      while (i < lines.length && tableLine(lines[i])) rows.push(tableCells(lines[i++]));
      i--; tables.push(rows); continue;
    }
    const image = IMAGE_LINE.exec(lines[i].trim());
    if (image) {
      const graph = image[1].startsWith('Graph');
      if (graph && lines[i + 1]?.startsWith(`${image[1]}:`)) i++;
      images.push({ graph, id: Number(image[2]) }); continue;
    }
    text.push(lines[i]);
  }
  return { tables, images, text: text.join('\n').replace(/\n{3,}/g, '\n\n').trim() };
}

export function answerBox({ api, forms = null, value = '', figure = null, collapsed = false, rows = 6, maxLength = 50000, label = 'Your answer' } = {}) {
  const box = el('div', undefined, 'answer-box');
  const blocks = el('div', undefined, 'stack answer-blocks');
  const textarea = el('textarea'); textarea.rows = rows; textarea.maxLength = maxLength; textarea.setAttribute('aria-label', label);
  let items = [], palette = 'general', loading = 0;
  const emit = () => box.dispatchEvent(new Event('input', { bubbles: true }));
  const upload = form => api('/answer-images', { method: 'POST', body: form });
  const renumber = () => { let n = 0; for (const item of items) if (item.kind === 'drawing' || item.kind === 'graph') item.number = ++n; };
  const textBlock = { kind: 'text', node: null, text: () => textarea.value.trim() };
  const removable = item => {
    const remove = btn('Remove', 'small quiet', `Remove this ${item.kind}`);
    remove.onclick = () => {
      if (item.text() && !window.confirm(`Remove this ${item.kind} from your answer?`)) return;
      items = items.filter(other => other !== item); item.node.remove(); renumber(); emit();
    };
    item.node.querySelector('.block-head')?.append(remove);
    return item;
  };
  const make = (form, saved = null) => {
    if (form.kind === 'table') return removable(tableBlock(form, saved, emit));
    return removable(sketchBlock({ graph: form.kind === 'graph', form, saved, figure, upload, changed: emit, number: 1 }));
  };
  const place = item => {
    // Extra blocks go before the text, in the order the question asks for them.
    items.splice(items.indexOf(textBlock), 0, item);
    blocks.insertBefore(item.node, textBlock.node);
    renumber();
  };

  let rich = null;
  // make() for a saved drawing: fetch its strokes, then rebuild that block in place.
  const makeAny = (form, saved) => {
    if (!saved?.pendingId) return make(form, saved);
    const id = saved.pendingId;
    const holder = { kind: form.kind, node: el('div', 'Loading drawing…', 'answer-block muted'), number: 1, text: () => `![${form.kind === 'graph' ? 'Graph' : 'Drawing'} ${holder.number}](/answer-images/${id})`, flush: () => Promise.resolve() };
    loading++;
    api(`/answer-images/${id}/drawing`).then(strokes => {
      const real = make({ ...form, ...(strokes || {}) }, { ...(strokes || {}), imageId: id });
      // The graph description is rebuilt from the strokes, so it matches what is saved.
      real.number = holder.number;
      const at = items.indexOf(holder);
      if (at >= 0) { items[at] = real; holder.node.replaceWith(real.node); }
    }).catch(() => { holder.node.textContent = 'This drawing could not be loaded; it is still part of your saved answer.'; })
      .finally(() => { loading--; });
    return holder;
  };
  // Lay the blocks out for the forms asked for, filled from saved answer text.
  const rebuild = (wanted, saved) => {
    palette = (wanted || []).find(f => f.kind === 'text')?.palette || palette;
    rich = richText(textarea, { palette, collapsed });
    textBlock.node = el('div', undefined, 'answer-block text-block'); textBlock.node.append(rich);
    items = [textBlock]; blocks.replaceChildren(textBlock.node);
    const parsed = splitAnswer(saved);
    textarea.value = parsed.text;
    const tables = [...parsed.tables], images = [...parsed.images];
    for (const form of (wanted || []).filter(f => f.kind !== 'text')) {
      if (form.kind === 'table') place(makeAny(form, tables.shift() || null));
      else {
        const at = images.findIndex(image => image.graph === (form.kind === 'graph'));
        place(makeAny(form, at >= 0 ? { pendingId: images.splice(at, 1)[0].id } : null));
      }
    }
    for (const table of tables) place(makeAny({ kind: 'table' }, table));
    for (const image of images) place(makeAny({ kind: image.graph ? 'graph' : 'drawing' }, { pendingId: image.id }));
    quiet = true; textarea.dispatchEvent(new Event('input')); quiet = false;     // draws the maths preview
  };

  // "Add" lets the learner use any form the question did not ask for.
  const adders = el('div', undefined, 'toolbar answer-add');
  adders.append(el('span', 'Add to your answer:', 'muted'));
  for (const [kind, text] of [['table', '+ Table'], ['drawing', '+ Drawing'], ['graph', '+ Graph']]) {
    const add = btn(text, 'small');
    add.onclick = () => {
      const item = makeAny(kind === 'drawing' ? { kind, background: figure ? 'figure' : 'blank' } : { kind }, null);
      place(item); emit();
      item.node.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    };
    adders.append(add);
  }
  let quiet = false;
  textarea.addEventListener('input', () => { if (!quiet) emit(); });
  box.append(blocks, adders);

  const pendingForms = forms && typeof forms.then === 'function';
  let known = pendingForms ? null : forms;
  rebuild(known, value);
  if (pendingForms) {
    forms.then(found => {
      // Forms that arrive late are added unless the learner has already started a block of that kind.
      if (!Array.isArray(found)) return;
      known = found;
      const text = found.find(f => f.kind === 'text');
      if (text?.palette && text.palette !== palette && !textarea.value) { const saved = box.value; rebuild(found, saved); return; }
      for (const form of found.filter(f => f.kind !== 'text')) if (!items.some(item => item.kind === form.kind)) place(makeAny(form, null));
    }).catch(() => {});
  }

  Object.defineProperties(box, {
    value: {
      get: () => items.map(item => item.text()).filter(Boolean).join('\n\n'),
      set: next => { rebuild(known, next); },
    },
    disabled: { set: on => { textarea.disabled = on; for (const item of items) if (item !== textBlock) item.disabled = on; for (const b of adders.querySelectorAll('button')) b.disabled = on; } },
    textarea: { get: () => textarea },
  });
  // Replace only the typed text, keeping tables and drawings (used when handwriting is read from a photo).
  box.setText = text => { textarea.value = text; textarea.dispatchEvent(new Event('input', { bubbles: true })); };
  box.focus = options => textarea.focus(options);
  box.flush = async () => {
    for (let i = 0; i < 50 && loading; i++) await new Promise(resolve => setTimeout(resolve, 100));
    await Promise.all(items.map(item => item.flush?.()));
  };
  return box;
}
