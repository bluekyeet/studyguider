// Small helpers shared by the classic exam page, the rapid-question player and the revision page.
import { mathText } from './web-common.js';

export const el = (tag, text = '', className = '') => {
  const node = document.createElement(tag);
  node.textContent = text;
  node.className = className;
  return node;
};
export const field = (title, input) => {
  const label = el('label', title);
  label.append(input);
  return label;
};
export const option = (select, value, label) => {
  const node = el('option', label);
  node.value = String(value);
  select.append(node);
};
// Level -> subject -> topic: the level select narrows the subject select, so a long subject list stays short.
// Changing the level repopulates the subjects and fires 'change' on the subject select so the caller reloads its topics.
export const levelPicker = (level, subject, subjects, { fire = true } = {}) => {
  const levels = [...new Set(subjects.map(s => s.level))].sort((a, b) => a - b);
  level.replaceChildren();
  levels.forEach(n => option(level, n, `NCEA Level ${n}`));
  if (!levels.length) option(level, '', 'No levels yet');
  const fill = () => {
    subject.replaceChildren();
    const here = subjects.filter(s => String(s.level) === level.value).sort((a, b) => a.name.localeCompare(b.name));
    here.forEach(s => option(subject, s.id, s.name));
    if (!here.length) option(subject, '', 'No subjects yet');
  };
  level.addEventListener('change', () => { fill(); if (fire) subject.dispatchEvent(new Event('change')); });
  fill();
};
// FastAPI only reads a JSON body when the request says it is JSON; fetch would otherwise send text/plain.
export const json = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

// Paper text keeps the PDF's line breaks. Join them back into sentences, but keep
// blank lines and lines that start a new source credit or sub-part.
// Paper text comes out of the PDF without subscripts or superscripts ("CH3CH2OH", "mol–1"). This is display only:
// it never changes what is stored, and it only touches digits after real element symbols and exponents after unit symbols.
const ELEMENTS = new Set('H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi U'.split(' '));
const SUB = '₀₁₂₃₄₅₆₇₈₉', SUP = '⁰¹²³⁴⁵⁶⁷⁸⁹';
const digits = (text, table) => text.replace(/\d/g, d => table[+d]);
const isGroup = chunk => /^(?:[A-Z][a-z]?\d*)+$/.test(chunk) && [...chunk.matchAll(/[A-Z][a-z]?/g)].every(m => ELEMENTS.has(m[0]));
const isFormula = chunk => /\d/.test(chunk) && isGroup(chunk);
const UNITS = 'mol|kJ|kg|mg|cm|dm|mm|nm|Pa|Hz|[smgLJKVNWA]';
export const scienceText = text => String(text || '')
  .replace(/\uf0ae/g, '→')
  .replace(/\(([A-Z][A-Za-z0-9]*)\)(\d+)/g, (all, inner, n) => isGroup(inner) ? `(${inner})${digits(n, SUB)}` : all)
  .replace(/(?<![A-Za-z0-9])(\d*)([A-Z][A-Za-z0-9]*)/g, (all, coefficient, chunk) => isFormula(chunk) ? coefficient + chunk.replace(/\d+/g, d => digits(d, SUB)) : all)
  .replace(new RegExp(`(?<![A-Za-z])(${UNITS})\\s?[–−-]\\s?(\\d)(?!\\d)`, 'g'), (all, unit, n) => `${unit}⁻${digits(n, SUP)}`)
  .replace(/Δr(?=[A-Z])/g, 'Δᵣ');
// Table rows ("| a | b |") keep their own lines, so a table in the question still renders as a table.
export const reflow = text => scienceText(String(text || '').replace(/(?<!\|[ \t]*)[ \t]*\n(?!\s*\n)(?!\s*\|)(?!\s*(?:Source|\([a-hivx]+\)))/gi, ' ')).trim();
// A part's wording often begins with its own label, which is already shown beside it.
export const withoutLabel = text => String(text || '').replace(/^\s*\([a-hivx]+\)\s*/i, '');
export const displayLabel = label => !label || label === 'context' ? ''
  : label.startsWith('(') ? label : `(${label.replaceAll('(', ')(')}${label.endsWith(')') ? '' : ')'}`;

// One to ten pages for handwriting recognition: PNG/JPEG photos (joined in the order given) or a single PDF.
const SCAN_LIMIT = 10 * 1024 * 1024;
// The whole-paper route only reads a `files` list; the per-question route also accepts a single `file`.
export function scanForm(files, listOnly = false) {
  if (!files.length || files.length > 10) throw new Error('Choose one to ten pages.');
  const pdf = files.some(f => f.type === 'application/pdf');
  if (pdf && files.length > 1) throw new Error('Upload one PDF on its own, or up to ten photos.');
  if (!pdf && !files.every(f => f.type === 'image/png' || f.type === 'image/jpeg')) throw new Error('Pages must be PNG or JPEG photos, or one PDF.');
  if (files.reduce((total, f) => total + f.size, 0) > SCAN_LIMIT) throw new Error('The pages are over 10 MiB in total. Use smaller photos.');
  const form = new FormData();
  if (files.length === 1 && !listOnly) form.append('file', files[0]); else files.forEach(f => form.append('files', f));
  return form;
}

export const mathsNote = () => el('p', 'Equations were read from the original page by AI. Check them against the paper.', 'muted');

// A question as the learner reads it: wording split into labelled parts, with the paper's figures under them.
// Works from the payload the rapid endpoints return (parts, question_text, paper_resource_id).
export function questionView(q) {
  const box = el('div', '', 'stack');
  if (q.maths_restored) box.append(mathsNote());
  const parts = (q.parts || []).filter(p => p && typeof p.text === 'string');
  const shown = new Set();
  const figures = p => (p.diagrams || []).filter(d => {
    if (!(q.paper_resource_id && Array.isArray(d.bbox) && d.bbox.length === 4)) return false;
    const key = `${d.page}:${d.bbox.join(',')}`;
    if (shown.has(key)) return false;
    shown.add(key); return true;
  }).map((d, number) => {
    const image = el('img', '', 'exam-figure'); image.loading = 'lazy';
    image.alt = `Figure ${number + 1} from page ${d.page} of the original paper`;
    const query = ['x0', 'y0', 'x1', 'y1'].map((name, i) => `${name}=${d.bbox[i]}`).join('&');
    image.src = `/resources/${encodeURIComponent(q.paper_resource_id)}/pages/${d.page}/diagram-image?${query}`;
    const open = el('a'); open.href = image.src; open.target = '_blank'; open.rel = 'noopener'; open.title = 'Open full size';
    open.append(image); return open;
  });
  if (!parts.length) { box.append(mathText(reflow(q.question_text || 'Question text unavailable.'))); return box; }
  for (const p of parts) {
    const label = displayLabel(p.label || '');
    let text = p.text, heading = '';
    if (label) text = withoutLabel(text);
    else {
      // "QUESTION ONE: TITLE" is a heading, not wording.
      const head = /^\s*QUESTION\s+(?:ONE|TWO|THREE|\d+)[ \t]*:?[ \t]*([^\n]*)\n?([\s\S]*)$/i.exec(text);
      if (head) { heading = head[1].trim(); text = head[2]; }
    }
    if (!text.trim() && !heading) continue;
    const row = el('div', '', 'exam-part'); const body = el('div', '', 'stack');
    row.append(el('div', label, 'exam-part-label'), body);
    if (heading) body.append(el('h4', heading));
    if (text.trim()) body.append(mathText(reflow(text)));
    body.append(...figures(p));
    box.append(row);
  }
  return box;
}
