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
// FastAPI only reads a JSON body when the request says it is JSON; fetch would otherwise send text/plain.
export const json = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

// Paper text keeps the PDF's line breaks. Join them back into sentences, but keep
// blank lines and lines that start a new source credit or sub-part.
export const reflow = text => String(text || '').replace(/[ \t]*\n(?!\s*\n)(?!\s*(?:Source|\([a-hivx]+\)))/gi, ' ').trim();
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

// A question as the learner reads it: wording split into labelled parts, with the paper's figures under them.
// Works from the payload the rapid endpoints return (parts, question_text, paper_resource_id).
export function questionView(q) {
  const box = el('div', '', 'stack');
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
      const head = /^\s*QUESTION\s+(?:ONE|TWO|THREE|\d+)\s*:?\s*([^\n]*)\n?([\s\S]*)$/i.exec(text);
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
