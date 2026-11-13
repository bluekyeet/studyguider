import { mathText, mathInput, autosave, aiBox } from './web-common.js';
import { answerBox, choiceResultView } from './web-answer.js';
import { el, field, option, json, levelPicker, reflow, withoutLabel, displayLabel, scanForm, mathsNote } from './web-exam-shared.js';
import { renderRapid } from './web-rapid.js';
import { renderRevision } from './web-revision.js';

// Answer boxes get the maths toolbar and a live preview.
const mathField = (title, textarea) => {
  const label = el('label', title);
  label.append(mathInput(textarea, { collapsed: true }));
  return label;
};

async function renderClassicExams(container, api) {
  const root = el('section', '', 'stack');
  container.replaceChildren(root);
  const alive = () => root.isConnected;
  const error = el('p', '', 'error');
  error.setAttribute('role', 'alert');
  const report = (err) => { if (alive()) error.textContent = err.message || String(err); };
  const builder = el('form', '', 'card stack');
  const fields = el('div', '', 'fields');
  const level = el('select');
  const subject = el('select');
  const topic = el('select');
  const mode = el('select');
  const answerMode = el('select');
  option(answerMode, 'digital', 'Type my answers');
  option(answerMode, 'handwritten', 'Write on paper, then upload photos');
  const paper = el('select');
  const count = el('input');
  count.type = 'number'; count.min = '1'; count.max = '10'; count.value = '3'; count.required = true;
  option(mode, 'original', 'Original paper — registered questions');
  option(mode, 'mixed', 'Mixed practice — registered questions across years');
  option(mode, 'ai', 'AI practice — generated questions and rubric (unofficial)');
  const paperField = field('Original year / paper', paper);
  const countField = field('Question count (1–10)', count);
  fields.append(field('Level', level), field('Subject', subject), field('Topic', topic), field('Exam mode', mode), paperField, countField, field('How will you answer?', answerMode));
  const start = el('button', 'Start exam', 'primary');
  start.type = 'submit'; start.disabled = true;
  const modeNotice = el('p', '', 'muted');
  builder.append(el('h2', 'Start an exam'), fields, modeNotice, start);
  // Past exams and tests of a university paper are uploaded here and read by AI (exam_import.py). NCEA papers are paired from
  // the Library by their NZQA file names.
  const importer = el('section', '', 'card stack'); importer.hidden = true;
  const importForm = el('form', '', 'stack');
  const paperFile = el('input'); paperFile.type = 'file'; paperFile.required = true; paperFile.accept = '.pdf,.docx,.txt,.md,.png,.jpg,.jpeg';
  const guideFile = el('input'); guideFile.type = 'file'; guideFile.accept = paperFile.accept;
  const importTitle = el('input'); importTitle.maxLength = 200; importTitle.placeholder = 'For example: Mid-semester test 2025';
  const importYear = el('input'); importYear.type = 'number'; importYear.min = '1950'; importYear.max = '2100'; importYear.value = String(new Date().getFullYear());
  const importKind = el('select'); option(importKind, 'exam', 'Exam'); option(importKind, 'test', 'Test'); option(importKind, 'quiz', 'Quiz');
  const importFields = el('div', '', 'fields');
  importFields.append(field('The exam or test paper', paperFile), field('Marking guide, model answers or answer key (optional)', guideFile),
    field('Name', importTitle), field('Year', importYear), field('Kind', importKind));
  const importStart = el('button', 'Import this paper', 'primary'); importStart.type = 'submit';
  importForm.append(importFields, el('p', 'The questions, their marks and any multiple-choice options are read by AI and checked against the paper\u2019s own wording. If you have no marking guide, AI writes one and it is labelled as AI-written wherever it is used. Reading a paper takes a few minutes.', 'muted'), importStart);
  const importList = el('div', '', 'stack');
  importer.append(el('h2', 'Import a past exam or test'), importForm, importList);
  const saved = el('section', '', 'card stack');
  const detail = el('section', '', 'stack');
  detail.append(el('p', 'Start a new exam on the left, or open a saved one, to see the paper here.', 'empty'));
  const head = el('div', '', 'page-head'); const title = el('div');
  title.append(el('h1', 'Exams'), el('p', 'AI marking is study feedback, not an official or verified grade from NZQA or your university. Compare questions, diagrams and marking guides with the originals.', 'muted'));
  head.append(title);
  const rail = el('div', '', 'exam-rail stack'); rail.append(builder, importer, saved);
  const layout = el('div', '', 'exam-layout'); layout.append(rail, detail);
  root.append(head, error, layout);
  let papers = [], subjectRequest = 0, topicRequest = 0, openRequest = 0;
  let drafts = [], busy = false, stopClock = () => {};
  const dirty = () => drafts.some(d => d.value() !== d.saved);
  const canLeave = () => !busy && (!dirty() || window.confirm('Discard unsaved exam answers?'));
  let subjectKinds = new Map(), importTimer = null;
  const isPaper = () => subjectKinds.get(String(subject.value)) === 'paper';
  const updateMode = () => {
    paperField.hidden = mode.value !== 'original';
    countField.hidden = mode.value === 'original';
    count.disabled = mode.value === 'original';
    start.disabled = !topic.value || (mode.value === 'original' && !papers[paper.value]);
    modeNotice.replaceChildren();
    if (mode.value === 'ai') modeNotice.textContent = isPaper() ? 'Starting generates an AI practice paper from the files you have uploaded for this topic. It is not one of the paper\u2019s own exams.'
      : 'Starting generates an AI practice paper from the files you have uploaded for this topic, not official NZQA material.';
    else if (topic.value && !papers.length && isPaper()) {
      modeNotice.textContent = 'No past exams or tests are imported for this topic yet. Import one below (they are kept under the topic \u201cPast exams and tests\u201d unless you are on another topic), or choose AI practice.';
    } else if (topic.value && !papers.length) {
      // A new account has no past papers yet: say how to add them and what works in the meantime.
      const library = el('a', 'Library'); library.href = '#library';
      modeNotice.append('No past papers are registered for this topic yet. Upload an NZQA exam paper and its marking schedule in the ', library,
        ' (named like 91577-exm-2023.pdf and 91577-ass-2023.pdf); they are paired and added automatically. Until then, choose AI practice, which writes questions from the notes and files you have uploaded for this topic.');
    } else modeNotice.textContent = 'Registered questions may not cover a complete paper. Check original wording, diagrams and schedule; bank human review may be outstanding.';
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
      papers.forEach((p, index) => option(paper, index, p.standard_number ? `${p.year} · AS ${p.standard_number} · ${p.question_count} registered questions`
        : `${p.title || 'Imported paper'} · ${p.year} · ${p.question_count} questions${p.guide === 'ai' ? ' · AI-written guide' : ''}`));
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
  // ---- importing a past exam or test ----
  const importRow = (item) => {
    const row = el('div', '', 'import-status');
    const state = item.status === 'reading' ? ['Reading…', ''] : item.status === 'imported' ? ['Imported', 'ok']
      : item.status === 'needs_attention' ? ['Imported · check the notes', 'warn'] : ['Could not import', 'bad'];
    const head = el('div', '', 'toolbar');
    head.append(el('strong', `${item.title} · ${item.year}`), el('span', state[0], `chip ${state[1]}`.trim()));
    row.append(head);
    if (item.status === 'reading') row.append(el('p', item.stage || 'Waiting to start', 'muted'));
    else if (item.status === 'failed') row.append(el('p', item.error || 'The import stopped.', 'error'));
    else {
      row.append(el('p', `${item.question_count} questions${item.choice_count ? ` (${item.choice_count} multiple choice)` : ''} · ${item.total_marks} marks`, 'muted'));
      if (item.guide_note) row.append(el('p', item.guide_note, item.guide === 'official' ? 'muted' : 'choice-penalty'));
    }
    if (item.warnings?.length) {
      const notes = el('details'); notes.append(el('summary', `${item.warnings.length} note${item.warnings.length === 1 ? '' : 's'} to check`));
      const list = el('ul'); for (const warning of item.warnings) list.append(el('li', warning));
      notes.append(list); row.append(notes);
    }
    const actions = el('div', '', 'toolbar');
    if (item.status === 'imported' || item.status === 'needs_attention') {
      const sit = el('button', 'Sit this paper', 'small primary'); sit.type = 'button';
      sit.onclick = async () => {
        topic.value = String(item.topic_id); mode.value = 'original'; await loadPapers();
        const index = papers.findIndex(p => p.paper_resource_id === item.paper_resource_id);
        if (index >= 0) { paper.value = String(index); updateMode(); builder.requestSubmit(); }
      };
      actions.append(sit);
    }
    if (item.status === 'failed') {
      const again = el('button', 'Try again', 'small'); again.type = 'button';
      again.onclick = async () => { again.disabled = true; try { await api(`/exam-imports/${item.id}/retry`, { method: 'POST' }); await loadImports(); } catch (err) { report(err); } };
      actions.append(again);
    }
    if (item.status !== 'reading') {
      const remove = el('button', 'Delete', 'small danger'); remove.type = 'button'; remove.setAttribute('aria-label', `Delete the import ${item.title}`);
      remove.onclick = async () => {
        if (!window.confirm(`Delete the imported paper "${item.title}" and its questions? The uploaded files stay in the Library.`)) return;
        remove.disabled = true;
        try { await api(`/exam-imports/${item.id}`, { method: 'DELETE' }); await Promise.all([loadImports(), loadPapers()]); } catch (err) { report(err); remove.disabled = false; }
      };
      actions.append(remove);
    }
    row.append(actions);
    return row;
  };
  const loadImports = async () => {
    clearTimeout(importTimer);
    importer.hidden = !subject.value || !isPaper();
    if (importer.hidden) return;
    const wanted = subject.value;
    try {
      const rows = await api(`/subjects/${encodeURIComponent(wanted)}/exam-imports`);
      if (!alive() || wanted !== subject.value) return;
      const wasReading = importList.dataset.reading === 'true';
      const reading = rows.some(r => r.status === 'reading');
      importList.replaceChildren(...rows.map(importRow));
      importList.dataset.reading = String(reading);
      // While a paper is being read its progress is refreshed; when it finishes, the topic and paper lists pick it up.
      if (reading) importTimer = setTimeout(loadImports, 4000);
      else if (wasReading) { const keep = topic.value; await loadTopics(); if ([...topic.options].some(o => o.value === keep)) { topic.value = keep; await loadPapers(); } }
    } catch (err) { report(err); }
  };
  importForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!paperFile.files[0] || !subject.value) return;
    const form = new FormData();
    form.append('paper', paperFile.files[0]);
    if (guideFile.files[0]) form.append('guide', guideFile.files[0]);
    form.append('title', importTitle.value.trim()); form.append('year', importYear.value || String(new Date().getFullYear())); form.append('kind', importKind.value);
    importStart.disabled = true; error.textContent = '';
    try {
      await api(`/subjects/${encodeURIComponent(subject.value)}/exam-imports`, { method: 'POST', body: form });
      importForm.reset(); importYear.value = String(new Date().getFullYear());
      importList.dataset.reading = 'true';
      await loadImports();
    } catch (err) { report(err); }
    finally { importStart.disabled = false; }
  });
  subject.addEventListener('change', () => { loadTopics(); loadImports(); });
  topic.addEventListener('change', loadPapers);

  const link = (label, path) => {
    const a = el('a', label); a.href = path; a.target = '_blank'; a.rel = 'noopener';
    return a;
  };
  const feedbackView = (result) => {
    // Multiple choice marked against its answer key: no AI marker took part, so it is shown as a result, not as AI feedback.
    const keyed = result.marked_by === 'answer-key' ? result : (result.marks || []).find(mark => mark.marked_by === 'answer-key');
    if (keyed) {
      const view = el('div', '', 'stack');
      view.append(el('h4', `Marked against the answer key: ${keyed.net_marks ?? keyed.marks_awarded} / ${keyed.net_marks_available ?? keyed.marks_available} marks`));
      for (const [label, outcome] of Object.entries(keyed.choice_results || {})) view.append(choiceResultView(outcome, label ? `Part ${displayLabel(label)}:` : ''));
      if (result.override) view.append(el('p', `Your separate override: ${result.override.outcome}`), mathText(result.override.note || ''));
      return view;
    }
    const view = el('div', '', 'ai-box stack');
    view.append(el('span', 'AI generated · unofficial practice feedback', 'ai-badge'), el('p', result.disclaimer || 'AI-generated study feedback, not an official or verified grade.', 'muted'));
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
      heading.append(el('h2', info.title || `Exam ${id}`), el('p', `${exam.kind.replaceAll('_', ' ')} · ${exam.total_marks > 0 ? `${exam.total_marks} registered marks` : 'marks not recorded'} · ${info.answer_mode} answer mode`, 'muted'), link('Download text-only practice PDF (original diagrams not included)', `/exams/${id}/print`));
      const handwritten = info.answer_mode === 'handwritten';
      // Same switch as the Android app: the choice belongs to this exam and can change at any time.
      const modes = el('div', '', 'toolbar'); modes.setAttribute('role', 'group'); modes.setAttribute('aria-label', 'How you answer');
      for (const [value, label] of [['digital', 'Type answers'], ['handwritten', 'Write on paper']]) {
        const choice = el('button', label, value === info.answer_mode ? 'primary' : ''); choice.type = 'button';
        choice.setAttribute('aria-pressed', String(value === info.answer_mode));
        choice.onclick = async () => {
          if (value === info.answer_mode || busy) return;
          if (dirty() && !window.confirm('Discard unsaved exam answers and switch how you answer?')) return;
          try {
            await api(`/exams/${id}/answer-mode`, json('PUT', { answer_mode: value }));
            drafts.forEach(d => { d.saved = d.value(); });   // the learner chose to discard; reopen without a second prompt
            container.dataset.dirty = 'false';
            await openExam(id);
          } catch (err) { report(err); }
        };
        modes.append(choice);
      }
      heading.append(modes);
      const appliers = new Map();   // question id -> function that shows a recognised answer in its card
      if (handwritten) {
        const all = el('div', '', 'stack');
        all.append(el('h3', 'Upload your whole paper'),
          el('p', 'Photograph every page in order (up to 10 pages, or one PDF). Each question is read from the same pages, so include the question numbers and part labels. You can also upload pages for one question below.', 'muted'));
        const picker = el('input'); picker.type = 'file'; picker.multiple = true; picker.accept = 'image/png,image/jpeg,application/pdf';
        picker.setAttribute('aria-label', 'Pages of your whole paper');
        const go = el('button', 'Read my handwriting', 'primary'); go.type = 'button';
        const note = el('p', '', 'muted'); note.setAttribute('role', 'status');
        go.onclick = async () => {
          if (busy) return;
          try {
            const form = scanForm([...picker.files], true);
            busy = true; go.disabled = true; container.dataset.busy = 'true'; note.textContent = 'Reading your handwriting. This can take a minute or two…';
            const result = await api(`/exams/${id}/scan`, { method: 'POST', body: form });
            let applied = 0;
            for (const item of result.answers || []) { const apply = appliers.get(item.question_id); if (apply && item.transcription) { apply(item.transcription, item.scan_revision); applied++; } }
            const missing = (result.answers || []).filter(item => item.found === false).length;
            note.textContent = `Read ${applied} answer${applied === 1 ? '' : 's'}${missing ? `; ${missing} question${missing === 1 ? ' had' : 's had'} no answer on these pages and keep what you already saved` : ''}. Check each one against your page, then confirm it.`;
          } catch (err) { note.textContent = ''; report(err); }
          finally { busy = false; go.disabled = false; container.dataset.busy = 'false'; }
        };
        all.append(picker, go, note); heading.append(all);
      }
      detail.append(heading);
      const cards = [], navButtons = [];
      let shownQuestion = 0;
      const showQuestion = index => {
        const step = Math.sign(index - shownQuestion);
        shownQuestion = index;
        if (step && cards[index]) { cards[index].style.setProperty('--ex', step * 28 + 'px'); cards[index].style.setProperty('--ey', '0px'); }
        cards.forEach((c, i) => { c.hidden = i !== index; });
        navButtons.forEach((b, i) => { if (i === index) b.setAttribute('aria-current', 'step'); else b.removeAttribute('aria-current'); });
        pager.hidden = cards.length < 2;
        prevQuestion.disabled = index === 0; nextQuestion.disabled = index === cards.length - 1;
      };
      // Optional timer: runs in this browser only; it never locks or submits answers.
      const timerBox = el('div', '', 'toolbar'); const clock = el('span', '0:00:00', 'timer');
      const startTimer = el('button', 'Start timer', 'small'); const resetTimer = el('button', 'Reset', 'small quiet');
      let elapsed = 0, ticking = null;
      stopClock(); stopClock = () => clearInterval(ticking);
      const drawClock = () => { const t = elapsed, h = Math.floor(t / 3600), m = Math.floor(t % 3600 / 60), sec = t % 60; clock.textContent = `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`; };
      startTimer.onclick = () => {
        if (ticking) { clearInterval(ticking); ticking = null; startTimer.textContent = 'Resume timer'; return; }
        ticking = setInterval(() => { if (!alive()) { clearInterval(ticking); return; } elapsed++; drawClock(); }, 1000);
        startTimer.textContent = 'Pause timer';
      };
      resetTimer.onclick = () => { clearInterval(ticking); ticking = null; elapsed = 0; drawClock(); startTimer.textContent = 'Start timer'; };
      timerBox.append(clock, startTimer, resetTimer);
      const nav = el('div', '', 'qnav'); nav.setAttribute('role', 'group'); nav.setAttribute('aria-label', 'Questions');
      heading.append(timerBox, nav);
      const pager = el('div', '', 'toolbar');
      const prevQuestion = el('button', '← Previous question'); const nextQuestion = el('button', 'Next question →', 'primary');
      prevQuestion.onclick = () => { showQuestion(shownQuestion - 1); heading.scrollIntoView({ block: 'start' }); };
      nextQuestion.onclick = () => { showQuestion(shownQuestion + 1); heading.scrollIntoView({ block: 'start' }); };
      pager.append(prevQuestion, nextQuestion);
      for (const [questionIndex, q] of exam.questions.entries()) {
        const navButton = el('button', `Q${q.position}`, 'small'); navButton.type = 'button';
        navButton.setAttribute('aria-label', `Question ${q.position}`);
        navButton.onclick = () => showQuestion(questionIndex);
        navButtons.push(navButton); nav.append(navButton);
        const card = el('article', '', 'card stack');
        const title = el('div', '', 'toolbar');
        title.append(el('h3', `Question ${q.position}`), el('span', q.standard_number ? `AS ${q.standard_number} · ${q.year}` : `${q.paper_title || 'AI practice'} · ${q.year}`, 'chip'));
        const printed = q.marks_exact ?? q.marks;
        if (printed > 0) title.append(el('span', `${printed} mark${printed === 1 ? '' : 's'}`, 'chip'));
        // An imported paper with no marking guide of its own: the guide, and so the marking, is the AI's.
        if (q.guide_source === 'ai' || q.guide_source === 'mixed') title.append(el('span', q.guide_source === 'ai' ? 'AI-written marking guide' : 'Marking guide partly AI-written', 'chip warn'));
        for (const code of q.outcome_codes || []) title.append(el('span', code, 'chip'));
        if (String(q.question_number) !== String(q.position)) title.append(el('span', `Paper question ${q.question_number}`, 'chip'));
        card.append(title);
        const sources = el('div', '', 'toolbar');
        if (q.paper_resource_id) sources.append(link(`Original paper · page ${q.paper_page}`, `/resources/${encodeURIComponent(q.paper_resource_id)}/download#page=${q.paper_page}`));
        if (q.schedule_resource_id) sources.append(link(q.guide_source ? 'Uploaded marking guide' : `Original schedule · page ${q.schedule_page}`, `/resources/${encodeURIComponent(q.schedule_resource_id)}/download#page=${q.schedule_page}`));
        if (q.figure_pages?.length) card.append(el('p', `Check original figure pages: ${q.figure_pages.join(', ')}`, 'muted'));
        card.append(sources);
        if (q.schedule_text) {
          const schedule = el('details');
          schedule.append(el('summary', q.guide_source === 'ai' ? 'Compare with the AI-written marking guide (not the examiner\u2019s)'
            : q.guide_source ? 'Compare with the marking guide' : q.schedule_resource_id ? 'Compare with schedule excerpt' : 'Compare with AI practice rubric (unofficial)'));
          if (q.guide_source) schedule.append(mathText(q.schedule_text));
          else if (q.schedule_resource_id) {
            // PDF tables lose their columns when extracted, so show the text as-is and point to the original.
            schedule.append(el('p', 'Extracted text; table layout is lost. Use the original schedule page above to compare.', 'muted'), el('pre', q.schedule_text, 'schedule-text'));
          } else schedule.append(mathText(q.schedule_text));
          card.append(schedule);
        }
        const raw = el('textarea'); raw.rows = 7; raw.maxLength = 100000; raw.value = q.answer || '';
        const rawField = mathField(handwritten ? 'Recognised answer (check it against your page)' : 'Answer text / JSON (preserved exactly unless edited)', raw);
        const partsBox = el('div', '', 'stack');
        if (q.maths_restored) partsBox.append(mathsNote());
        let parsed;
        try { parsed = JSON.parse(raw.value); } catch { /* Plain text stays plain text. */ }
        const structured = parsed && typeof parsed === 'object' && !Array.isArray(parsed)
          && parsed.parts && typeof parsed.parts === 'object' && !Array.isArray(parsed.parts)
          && Object.values(parsed.parts).every(v => typeof v === 'string');
        const definitions = (q.parts || [])
          .filter(p => p && typeof p.label === 'string' && typeof p.text === 'string')
          .map(p => ({ ...p, label: displayLabel(p.label) }))
          // A bare "QUESTION ONE" line is only a heading; "QUESTION ONE: TITLE" keeps its title.
          .map(p => {
            if (p.label) return { ...p, text: withoutLabel(p.text) };
            const head = /^\s*QUESTION\s+(?:ONE|TWO|THREE|\d+)[ \t]*:?[ \t]*([^\n]*)\n?([\s\S]*)$/i.exec(p.text);
            return head ? { ...p, heading: head[1].trim(), text: head[2] } : p;
          })
          .filter(p => p.text.trim() || p.heading);
        const partMode = !!structured || (!handwritten && !raw.value && definitions.some(p => p.label));
        const documentAnswer = structured ? parsed : { parts: {} };
        const partInputs = new Map();
        // Only the lowest-level parts take an answer; a parent such as (b) just introduces (b)(i) and (b)(ii).
        const answerable = p => p.label && !definitions.some(other => other.label.startsWith(p.label + '('));
        // The same figure can be listed under several parts; show each region once, under the first part that has it.
        const shownFigures = new Set();
        const diagrams = p => (p.diagrams || []).filter(d => {
          if (!(q.paper_resource_id && Array.isArray(d.bbox) && d.bbox.length === 4)) return false;
          const key = `${d.page}:${d.bbox.join(',')}`;
          if (shownFigures.has(key)) return false;
          shownFigures.add(key); return true;
        }).map((d, number) => {
          const image = el('img', '', 'exam-figure'); image.loading = 'lazy'; image.alt = `Figure ${p.label ? `for part ${p.label} ` : ''}${number + 1}, from page ${d.page} of the original paper`;
          const query = ['x0', 'y0', 'x1', 'y1'].map((name, i) => `${name}=${d.bbox[i]}`).join('&');
          image.src = `/resources/${encodeURIComponent(q.paper_resource_id)}/pages/${d.page}/diagram-image?${query}`;
          const open = el('a'); open.href = image.src; open.target = '_blank'; open.rel = 'noopener'; open.title = 'Open full size';
          open.append(image); return open;
        });
        // A drawing over the question's figure uses the first figure of that part, from the original paper page.
        const figureOf = p => {
          const d = (p?.diagrams || []).find(item => q.paper_resource_id && Array.isArray(item.bbox) && item.bbox.length === 4);
          return d ? `/resources/${encodeURIComponent(q.paper_resource_id)}/pages/${d.page}/diagram-image?${['x0', 'y0', 'x1', 'y1'].map((name, i) => `${name}=${d.bbox[i]}`).join('&')}` : null;
        };
        const formsFor = label => q.answer_forms?.[label] || q.answer_forms?.[''] || null;
        const addPart = (label, wording, extras = [], input = null, heading = '') => {
          const part = el('div', '', 'exam-part'); const body = el('div', '', 'stack');
          part.append(el('div', label, 'exam-part-label'), body);
          if (heading) body.append(el('h4', heading));
          if (wording) body.append(mathText(reflow(wording)));
          body.append(...extras);
          if (input) body.append(el('span', `Your answer ${label}`.trim(), 'field-label'), input);
          partsBox.append(part);
        };
        if (definitions.length) {
          for (const p of definitions) {
            let input = null;
            if (partMode && answerable(p)) {
              const original = (q.parts || []).find(part => displayLabel(part.label || '') === p.label);
              input = answerBox({ api, forms: formsFor(original?.label) || formsFor(p.label), value: documentAnswer.parts[p.label] || '',
                figure: figureOf(original), collapsed: true, rows: 4, maxLength: 100000, label: `Answer ${p.label}` });
              partInputs.set(p.label, input);
            }
            addPart(p.label, p.text, diagrams(p), input, p.heading);
          }
          // Keep saved answers whose part no longer exists in the question.
          for (const [label, value] of Object.entries(partMode ? documentAnswer.parts : {})) {
            if (partInputs.has(label)) continue;
            const input = answerBox({ api, value, collapsed: true, rows: 4, maxLength: 100000 }); partInputs.set(label, input);
            addPart(label, '', [], input);
          }
        } else {
          partsBox.append(mathText(reflow(q.question_text || 'Question text unavailable. Open the original paper for the full wording and diagrams.')));
        }
        // A question without parts, typed: one answer box for the whole question, kept in step with the raw text.
        let whole = null;
        if (!partMode && !handwritten && !/^\s*\{/.test(raw.value)) {
          whole = answerBox({ api, forms: formsFor(''), value: raw.value, figure: figureOf((q.parts || []).find(part => part.diagrams?.length)),
            collapsed: true, maxLength: 100000 });
          whole.addEventListener('input', () => { raw.value = whole.value; raw.dispatchEvent(new Event('input')); });
          partsBox.append(el('span', 'Your answer', 'field-label'), whole);
          rawField.hidden = true;
        }
        card.append(partsBox);
        const controls = el('div', '', 'toolbar');
        const save = el('button', 'Save answer');
        const mark = el('button', 'Save & mark', 'primary');
        const previous = el('button', 'Load saved feedback');
        const status = el('p', '', 'state'); status.setAttribute('role', 'status');
        const feedback = el('div', '', 'stack');
        const draft = { saved: raw.value, value: () => raw.value };
        drafts.push(draft);
        // Answers save themselves a moment after typing stops, and again when the box loses focus.
        const conflictBox = el('div', '', 'toolbar'); conflictBox.hidden = true;
        // A freshly recognised answer is not saved (and so not confirmed) until the learner has checked it.
        let scanPending = false;
        const saver = autosave({
          isDirty: () => !scanPending && draft.value() !== draft.saved,
          status: (kind, err) => {
            if (scanPending) return;
            conflictBox.hidden = kind !== 'conflict';
            status.dataset.state = kind;
            status.textContent = kind === 'saving' ? 'Saving…' : kind === 'saved' ? 'Saved · on all your devices'
              : kind === 'conflict' ? 'Changed on another device. Choose which version to keep.'
              : `Local draft · not saved yet (${err?.message || 'offline'}). Retrying.`;
            if (kind === 'saved') navButton.classList.add('done');
          },
          save: async () => {
            const answer = draft.value();
            if (answer.length > 100000) throw new Error('Answer exceeds 100,000 characters. Shorten it before saving.');
            const result = await api(`/exams/${id}/answers/${q.id}`, json('PUT', { answer, revision: q.answer_revision, scan_revision: q.scan_revision }));
            q.answer_revision = result.revision; draft.saved = answer;
            container.dataset.dirty = String(dirty());
          },
        });
        const keepMine = el('button', 'Keep my version', 'small');
        keepMine.addEventListener('click', async () => {
          const latest = (await api(`/exams/${id}`)).questions.find(item => item.id === q.id);
          q.answer_revision = latest.answer_revision; q.scan_revision = latest.scan_revision; saver.resume();
        });
        const useTheirs = el('button', 'Use the other version', 'small');
        useTheirs.addEventListener('click', () => { draft.saved = draft.value(); container.dataset.dirty = String(dirty()); openExam(id); });
        conflictBox.append(keepMine, useTheirs);
        raw.addEventListener('blur', () => { if (dirty()) saver.flush(); });
        const changed = () => { container.dataset.dirty = String(dirty()); feedback.replaceChildren(); saver.touch(); };
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
          card.append(toggle);
        }
        const run = async (action) => {
          if (busy) return;
          busy = true; error.textContent = '';
          container.dataset.busy = 'true';
          const buttons = root.querySelectorAll('button');
          const disabled = [...buttons].map(b => b.disabled);
          buttons.forEach(b => { b.disabled = true; });
          raw.disabled = true; partInputs.forEach(i => { i.disabled = true; }); if (whole) whole.disabled = true;
          status.textContent = action === 'feedback' ? 'Loading saved feedback…' : 'Saving…';
          try {
            const path = `/exams/${id}/answers/${q.id}`;
            if (action !== 'feedback') {
              if (draft.value().length > 100000) throw new Error('Answer exceeds 100,000 characters. Shorten it before saving.');
              // Drawings still uploading become part of the answer before it is saved and marked.
              await Promise.all([...partInputs.values(), ...(whole ? [whole] : [])].map(box => box.flush?.()));
              await saver.flush();   // the autosaver owns the revision, so a click never races it
              if (saver.conflicted || draft.value() !== draft.saved) throw new Error('Your answer could not be saved yet; see the message under the box.');
              container.dataset.dirty = String(dirty());
              if (!alive()) return;
              feedback.replaceChildren(); status.textContent = 'Saved'; navButton.classList.add('done');
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
              raw.disabled = false; partInputs.forEach(i => { i.disabled = false; }); if (whole) whole.disabled = false;
            }
          }
        };
        const confirmScan = el('button', 'Confirm recognised answer', 'primary'); confirmScan.hidden = true;
        const accept = () => { scanPending = false; confirmScan.hidden = true; };
        confirmScan.addEventListener('click', () => { accept(); run('save'); });
        save.addEventListener('click', () => { accept(); run('save'); });
        mark.addEventListener('click', () => {
          if (scanPending) { report(new Error('Check the recognised text, fix any mistakes and press Confirm recognised answer before marking.')); return; }
          run('mark');
        });
        previous.addEventListener('click', () => run('feedback'));
        controls.append(confirmScan, save, mark, previous);
        const scanBox = el('div', '', 'stack');
        if (handwritten) {
          const applyScan = (transcription, scanRevision) => {
            raw.value = transcription; q.scan_revision = scanRevision; scanPending = true;
            feedback.replaceChildren(); container.dataset.dirty = 'true'; confirmScan.hidden = false;
            status.dataset.state = 'error';
            status.textContent = 'Recognised from your handwriting, not saved yet. Check it against your page, fix any mistakes, then press Confirm recognised answer.';
            raw.dispatchEvent(new Event('input', { bubbles: true }));
          };
          appliers.set(q.id, applyScan);
          scanBox.append(el('h4', 'Your handwritten answer'),
            el('p', 'Photograph the pages with your answer to this question (up to 10, or one PDF). Include the question number and part labels. The text is read by AI and may contain mistakes, so check it before confirming.', 'muted'));
          const picker = el('input'); picker.type = 'file'; picker.multiple = true; picker.accept = 'image/png,image/jpeg,application/pdf';
          picker.setAttribute('aria-label', `Pages for question ${q.position}`);
          const preview = el('div', '', 'toolbar');
          picker.addEventListener('change', () => {
            preview.replaceChildren();
            for (const file of picker.files) if (file.type.startsWith('image/')) {
              const thumb = el('img', '', 'scan-thumb'); thumb.alt = file.name; thumb.src = URL.createObjectURL(file); thumb.onload = () => URL.revokeObjectURL(thumb.src); preview.append(thumb);
            }
          });
          const read = el('button', q.scan_revision ? 'Replace with new pages' : 'Read my handwriting', 'primary'); read.type = 'button';
          read.addEventListener('click', async () => {
            if (busy) return;
            try {
              const form = scanForm([...picker.files]);
              if (draft.value().trim() && !window.confirm('Replace the current answer with the text read from these pages?')) return;
              busy = true; read.disabled = true; container.dataset.busy = 'true'; status.dataset.state = 'saving'; status.textContent = 'Reading your handwriting. This can take a minute…';
              const result = await api(`/exams/${id}/answers/${q.id}/scan`, { method: 'POST', body: form });
              applyScan(result.transcription, result.scan_revision);
            } catch (err) { status.textContent = ''; report(err); }
            finally { busy = false; read.disabled = false; container.dataset.busy = 'false'; }
          });
          scanBox.append(picker, preview, read);
        }
        card.append(scanBox, rawField, controls, conflictBox, status, feedback); detail.append(card); cards.push(card);
        if (q.answer) navButton.classList.add('done');
      }
      detail.append(pager); showQuestion(0);
      detail.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (err) { if (request === openRequest) report(err); }
  };

  const loadSaved = async () => {
    const rows = await api('/exams');
    if (!alive()) return;
    saved.replaceChildren(el('h2', 'Saved exams'));
    const list = el('ul', '', 'list'); saved.append(list);
    if (!rows.length) list.append(el('li', 'No saved exams yet.', 'empty'));
    for (const exam of rows) {
      const row = el('li');
      const open = el('button', 'Open', 'small primary');
      open.setAttribute('aria-label', `Open exam ${exam.id}`);
      const remove = el('button', 'Delete', 'small danger');
      remove.setAttribute('aria-label', `Delete exam ${exam.id}`);
      open.addEventListener('click', () => openExam(exam.id));
      remove.addEventListener('click', async () => {
        if (!canLeave() || !window.confirm(`Delete exam ${exam.id}, its answers, scans and marks? Bank questions will remain.`)) return;
        remove.disabled = true;
        try {
          await api(`/exams/${exam.id}`, { method: 'DELETE' });
          if (!alive()) return;
          ++openRequest; detail.replaceChildren(el('p', 'Exam deleted.', 'empty')); drafts = [];
          await loadSaved();
        } catch (err) { report(err); if (alive()) remove.disabled = false; }
      });
      const text = el('div', '', 'grow');
      text.append(el('strong', `Exam ${exam.id} · ${exam.kind.replaceAll('_', ' ')}`), el('div', `${exam.question_count} questions · ${exam.total_marks > 0 ? `${exam.total_marks} marks` : 'marks not recorded'} · ${new Date(exam.created_at).toLocaleDateString('en-NZ')}`, 'muted'));
      row.append(text, open, remove);
      list.append(row);
    }
  };
  builder.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!canLeave() || start.disabled) return;
    const selected = papers[paper.value];
    const payload = { topic_id: Number(topic.value), mode: mode.value, answer_mode: answerMode.value };
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
        subjectKinds = new Map(subjects.map(s => [String(s.id), s.kind]));
        levelPicker(level, subject, subjects);
        if (!subjects.length) option(subject, '', 'Add subjects in management first');
        await Promise.all([loadTopics(), loadImports()]);
      } catch (err) { report(err); }
    })(),
  ]);
  return () => { stopClock(); clearTimeout(importTimer); };
}

// Exams is a hub of three sections so the main menu stays short.
export async function renderExams(container, api, params) {
  const sub = params?.get('sub') || '';
  const bar = el('nav', '', 'tabs'); bar.setAttribute('aria-label', 'Exam sections');
  const body = el('div', '', 'stack');
  const links = {};
  for (const [key, label, href] of [['', 'Classic exam papers', '#exams'], ['rapid', 'Rapid questions', '#exams/rapid'], ['revision', 'Exam revision', '#exams/revision']]) {
    const a = el('a', label); a.href = href; if (key === sub) a.setAttribute('aria-current', 'page');
    bar.append(a); links[key] = a;
  }
  container.replaceChildren(bar, body);
  const render = sub === 'rapid' ? renderRapid : sub === 'revision' ? renderRevision : renderClassicExams;
  return render(body, api, params);
}
