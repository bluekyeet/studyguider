import { mathText } from './web-common.js';

const el = (tag, text = '', className = '') => {
  const node = document.createElement(tag);
  node.textContent = text;
  node.className = className;
  return node;
};
const field = (title, input) => {
  const label = el('label', title);
  label.append(input);
  return label;
};
const option = (select, value, label) => {
  const node = el('option', label);
  node.value = String(value);
  select.append(node);
};
const json = (method, body) => ({ method, body: JSON.stringify(body) });

export async function renderExams(container, api) {
  const root = el('section', '', 'stack');
  container.replaceChildren(root);
  const alive = () => root.isConnected;
  const error = el('p');
  error.setAttribute('role', 'alert');
  const report = (err) => { if (alive()) error.textContent = err.message || String(err); };
  const builder = el('form', '', 'card stack');
  const fields = el('div', '', 'fields');
  const subject = el('select');
  const topic = el('select');
  const mode = el('select');
  const paper = el('select');
  const count = el('input');
  count.type = 'number'; count.min = '1'; count.max = '10'; count.value = '3'; count.required = true;
  option(mode, 'original', 'Original paper — registered questions');
  option(mode, 'mixed', 'Mixed practice — registered questions across years');
  option(mode, 'ai', 'AI practice — generated questions and rubric (unofficial)');
  const paperField = field('Original year / paper', paper);
  const countField = field('Question count (1–10)', count);
  fields.append(field('Subject', subject), field('Topic', topic), field('Exam mode', mode), paperField, countField);
  const start = el('button', 'Start exam', 'primary');
  start.type = 'submit'; start.disabled = true;
  const modeNotice = el('p', '', 'muted');
  builder.append(el('h2', 'Start an exam'), fields, modeNotice, start);
  const saved = el('section', '', 'card stack');
  const detail = el('section', '', 'stack');
  root.append(el('h1', 'Exams'), el('p', 'AI marking is study feedback, not an official or verified NZQA grade. Compare questions, diagrams and schedules with the originals.', 'muted'), error, builder, saved, detail);
  let papers = [], subjectRequest = 0, topicRequest = 0, openRequest = 0;
  let drafts = [], busy = false;
  const dirty = () => drafts.some(d => d.value() !== d.saved);
  const canLeave = () => !busy && (!dirty() || window.confirm('Discard unsaved exam answers?'));
  const updateMode = () => {
    paperField.hidden = mode.value !== 'original';
    countField.hidden = mode.value === 'original';
    count.disabled = mode.value === 'original';
    start.disabled = !topic.value || (mode.value === 'original' && !papers[paper.value]);
    modeNotice.textContent = mode.value === 'ai'
      ? 'Starting generates an AI practice paper, not official NZQA material.'
      : 'Registered questions may not cover a complete paper. Check original wording, diagrams and schedule; bank human review may be outstanding.';
  };
  mode.addEventListener('change', updateMode);
  paper.addEventListener('change', updateMode);
  const loadPapers = async () => {
    const request = ++topicRequest;
    papers = []; paper.replaceChildren(); start.disabled = true;
    if (!topic.value) { updateMode(); return; }
    try {
      const rows = await api(`/exam-papers?topic_id=${encodeURIComponent(topic.value)}`);
      if (!alive() || request !== topicRequest) return;
      papers = rows.filter(p => p.paper_resource_id);
      papers.forEach((p, index) => option(paper, index, `${p.year} · AS ${p.standard_number} · ${p.question_count} registered questions`));
      if (!papers.length) option(paper, '', 'No registered original papers');
      updateMode();
    } catch (err) { if (request === topicRequest) { report(err); updateMode(); } }
  };
  const loadTopics = async () => {
    const request = ++subjectRequest;
    ++topicRequest; topic.replaceChildren(); papers = []; paper.replaceChildren(); updateMode();
    if (!subject.value) return;
    try {
      const rows = await api(`/subjects/${encodeURIComponent(subject.value)}/topics`);
      if (!alive() || request !== subjectRequest) return;
      rows.forEach(t => option(topic, t.id, t.name));
      if (!rows.length) option(topic, '', 'No topics yet');
      await loadPapers();
    } catch (err) { if (request === subjectRequest) report(err); }
  };
  subject.addEventListener('change', loadTopics);
  topic.addEventListener('change', loadPapers);

  const link = (label, path) => {
    const a = el('a', label); a.href = path; a.target = '_blank'; a.rel = 'noopener';
    return a;
  };
  const feedbackView = (result) => {
    const view = el('div', '', 'stack');
    view.append(el('p', result.disclaimer || 'AI-generated study feedback, not an official or verified grade.', 'muted'));
    const marks = result.marks || [{ ...result, kind: 'first' }, ...(result.second_review ? [{ ...result.second_review, kind: 'second' }] : [])];
    for (const mark of marks) {
      view.append(el('h4', `${mark.kind === 'second' ? 'Advisory second review' : 'First mark'}: ${mark.marks_awarded}/${mark.marks_available} · ${mark.outcome}`), mathText(mark.feedback || ''));
      for (const evidence of mark.evidence || []) {
        const quote = el('blockquote'); quote.append(mathText(evidence.quote || ''));
        view.append(quote, mathText(`${evidence.marks} marks: ${evidence.explanation || ''}`));
      }
      if (mark.missing?.length) view.append(el('h4', 'Missing evidence / next steps'));
      for (const missing of mark.missing || []) view.append(mathText(missing));
    }
    if (result.disagreement || (marks.length > 1 && (marks[0].marks_awarded !== marks[1].marks_awarded || marks[0].outcome !== marks[1].outcome))) {
      view.append(el('p', 'Markers disagree. Check the original schedule; the second review is advisory.'));
    }
    if (result.override) view.append(el('p', `Your separate override: ${result.override.outcome}`), mathText(result.override.note || ''));
    return view;
  };

  const openExam = async (id) => {
    if (!canLeave()) return;
    const request = ++openRequest;
    error.textContent = '';
    try {
      const [exam, info] = await Promise.all([api(`/exams/${id}`), api(`/exams/${id}/details`)]);
      if (!alive() || request !== openRequest) return;
      drafts = []; detail.replaceChildren();
      const heading = el('div', '', 'card stack');
      heading.append(el('h2', info.title || `Exam ${id}`), el('p', `${exam.kind} · ${exam.total_marks} registered marks · ${info.answer_mode} answer mode`, 'muted'), link('Download text-only practice PDF (original diagrams not included)', `/exams/${id}/print`));
      if (info.answer_mode === 'handwritten') heading.append(el('p', 'This initial web version edits saved answer text only. Upload and handwriting recognition remain in the existing app.', 'muted'));
      detail.append(heading);
      for (const q of exam.questions) {
        const card = el('article', '', 'card stack');
        card.append(el('h3', `Question ${q.position} · ${q.question_number} · AS ${q.standard_number} · ${q.year} · ${q.marks} marks`), mathText(q.question_text || 'Question text unavailable. Open the original paper for the full wording and diagrams.'));
        const sources = el('div', '', 'toolbar');
        if (q.paper_resource_id) sources.append(link(`Original paper · page ${q.paper_page}`, `/resources/${encodeURIComponent(q.paper_resource_id)}/download#page=${q.paper_page}`));
        if (q.schedule_resource_id) sources.append(link(`Original schedule · page ${q.schedule_page}`, `/resources/${encodeURIComponent(q.schedule_resource_id)}/download#page=${q.schedule_page}`));
        if (q.figure_pages?.length) card.append(el('p', `Check original figure pages: ${q.figure_pages.join(', ')}`, 'muted'));
        card.append(sources);
        if (q.schedule_text) {
          const schedule = el('details');
          schedule.append(el('summary', q.schedule_resource_id ? 'Compare with schedule excerpt' : 'Compare with AI practice rubric (unofficial)'), mathText(q.schedule_text));
          card.append(schedule);
        }
        const raw = el('textarea'); raw.rows = 7; raw.maxLength = 100000; raw.value = q.answer || '';
        const rawField = field('Answer text / JSON (preserved exactly unless edited)', raw);
        const partsBox = el('div', '', 'stack');
        let parsed;
        try { parsed = JSON.parse(raw.value); } catch { /* Plain text stays plain text. */ }
        const structured = parsed && typeof parsed === 'object' && !Array.isArray(parsed)
          && parsed.parts && typeof parsed.parts === 'object' && !Array.isArray(parsed.parts)
          && Object.values(parsed.parts).every(v => typeof v === 'string');
        const definitions = (q.parts || [])
          .filter(p => typeof p.label === 'string' && p.label && p.label !== 'context' && typeof p.text === 'string')
          .map(p => ({ ...p, label: p.label.startsWith('(') ? p.label : `(${p.label.replaceAll('(', ')(')}${p.label.endsWith(')') ? '' : ')'}` }));
        const partMode = !!structured || (!raw.value && definitions.length > 0);
        const documentAnswer = structured ? parsed : { parts: {} };
        const partInputs = new Map();
        if (partMode) {
          const labels = [...new Set([...definitions.map(p => p.label), ...Object.keys(documentAnswer.parts)])];
          for (const label of labels) {
            const definition = definitions.find(p => p.label === label);
            if (definition) partsBox.append(mathText(`${label} ${definition.text}`));
            const input = el('textarea'); input.rows = 4; input.maxLength = 100000;
            input.value = documentAnswer.parts[label] || '';
            partInputs.set(label, input); partsBox.append(field(`Answer ${label}`, input));
          }
        } else {
          for (const p of definitions) card.append(mathText(`${p.label} ${p.text}`));
        }
        const controls = el('div', '', 'toolbar');
        const save = el('button', 'Save answer');
        const mark = el('button', 'Save & mark', 'primary');
        const previous = el('button', 'Load saved feedback');
        const status = el('p', '', 'muted'); status.setAttribute('role', 'status');
        const feedback = el('div', '', 'stack');
        const draft = { saved: raw.value, value: () => raw.value };
        drafts.push(draft);
        const changed = () => { container.dataset.dirty = String(dirty()); status.textContent = 'Unsaved changes'; feedback.replaceChildren(); };
        raw.addEventListener('input', changed);
        for (const input of partInputs.values()) input.addEventListener('input', () => {
          // ponytail: preserve unknown JSON fields; raw editing handles other answer schemas.
          for (const [label, textarea] of partInputs) Object.defineProperty(documentAnswer.parts, label, { value: textarea.value, enumerable: true, configurable: true, writable: true });
          raw.value = JSON.stringify(documentAnswer); changed();
        });
        if (partMode) {
          rawField.hidden = true;
          const toggle = el('button', 'Edit raw text / JSON instead');
          toggle.addEventListener('click', () => {
            if (!window.confirm('Switch to raw editing? Your current text / JSON will be retained.')) return;
            partsBox.hidden = true; rawField.hidden = false; toggle.remove();
          });
          card.append(partsBox, toggle);
        }
        const run = async (action) => {
          if (busy) return;
          busy = true; error.textContent = '';
          container.dataset.busy = 'true';
          const buttons = root.querySelectorAll('button');
          const disabled = [...buttons].map(b => b.disabled);
          buttons.forEach(b => { b.disabled = true; });
          raw.disabled = true; partInputs.forEach(i => { i.disabled = true; });
          status.textContent = action === 'feedback' ? 'Loading saved feedback…' : 'Saving…';
          try {
            const path = `/exams/${id}/answers/${q.id}`;
            if (action !== 'feedback') {
              const answer = draft.value();
              if (answer.length > 100000) throw new Error('Answer exceeds 100,000 characters. Shorten it before saving.');
              const result = await api(path, json('PUT', { answer, revision: q.answer_revision, scan_revision: q.scan_revision }));
              q.answer_revision = result.revision; draft.saved = answer;
              container.dataset.dirty = String(dirty());
              if (!alive()) return;
              feedback.replaceChildren(); status.textContent = 'Saved';
            }
            if (action === 'mark' || action === 'feedback') {
              status.textContent = action === 'mark' ? 'Saved. Marking…' : 'Loading saved feedback…';
              const result = await api(`${path}/feedback`, action === 'mark' ? json('POST', { second_review: false }) : {});
              if (!alive() || request !== openRequest) return;
              feedback.replaceChildren(feedbackView(result));
              status.textContent = draft.value() === draft.saved ? 'Feedback for the saved answer' : 'Feedback for the saved answer only; current edits are unsaved';
            }
          } catch (err) { report(err); if (alive()) status.textContent = 'Request failed. Your local draft is retained; copy it before reloading if there is a revision conflict.'; }
          finally {
            busy = false;
            container.dataset.busy = 'false';
            if (alive()) {
              buttons.forEach((b, i) => { b.disabled = disabled[i]; });
              raw.disabled = false; partInputs.forEach(i => { i.disabled = false; });
            }
          }
        };
        save.addEventListener('click', () => run('save'));
        mark.addEventListener('click', () => run('mark'));
        previous.addEventListener('click', () => run('feedback'));
        controls.append(save, mark, previous);
        card.append(rawField, controls, status, feedback); detail.append(card);
      }
      detail.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (err) { if (request === openRequest) report(err); }
  };

  const loadSaved = async () => {
    const rows = await api('/exams');
    if (!alive()) return;
    saved.replaceChildren(el('h2', 'Saved exams'));
    if (!rows.length) saved.append(el('p', 'No saved exams yet.', 'muted'));
    for (const exam of rows) {
      const row = el('div', '', 'toolbar');
      const open = el('button', `Open exam ${exam.id}`);
      const remove = el('button', `Delete exam ${exam.id}`);
      open.addEventListener('click', () => openExam(exam.id));
      remove.addEventListener('click', async () => {
        if (!canLeave() || !window.confirm(`Delete exam ${exam.id}, its answers, scans and marks? Bank questions will remain.`)) return;
        remove.disabled = true;
        try {
          await api(`/exams/${exam.id}`, { method: 'DELETE' });
          if (!alive()) return;
          ++openRequest; detail.replaceChildren(); drafts = [];
          await loadSaved();
        } catch (err) { report(err); if (alive()) remove.disabled = false; }
      });
      row.append(el('span', `${exam.kind} · ${exam.question_count} questions · ${exam.total_marks} marks · ${new Date(exam.created_at).toLocaleDateString()}`), open, remove);
      saved.append(row);
    }
  };
  builder.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!canLeave() || start.disabled) return;
    const selected = papers[paper.value];
    const payload = { topic_id: Number(topic.value), mode: mode.value, answer_mode: 'digital' };
    if (!Number.isSafeInteger(payload.topic_id) || payload.topic_id <= 0) { report(new Error('Choose a topic.')); return; }
    if (mode.value === 'original') {
      if (!selected) { report(new Error('Choose an original paper.')); return; }
      payload.year = selected.year; payload.paper_resource_id = selected.paper_resource_id;
    } else {
      payload.question_count = Number(count.value);
      if (!Number.isInteger(payload.question_count) || payload.question_count < 1 || payload.question_count > 10) { report(new Error('Choose 1–10 questions.')); return; }
    }
    start.disabled = true; error.textContent = '';
    try {
      const exam = await api('/exams/start', json('POST', payload));
      if (!alive()) return;
      drafts = []; await Promise.all([loadSaved(), openExam(exam.id)]);
    } catch (err) { report(err); }
    finally { if (alive()) updateMode(); }
  });
  updateMode();
  await Promise.all([
    loadSaved().catch(report),
    (async () => {
      try {
        const subjects = await api('/subjects');
        if (!alive()) return;
        subjects.forEach(s => option(subject, s.id, `${s.name} · Level ${s.level}`));
        if (!subjects.length) option(subject, '', 'Add subjects in management first');
        await loadTopics();
      } catch (err) { report(err); }
    })(),
  ]);
}
