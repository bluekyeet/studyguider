import { mathText, mathInput, stash, aiBox, hintButton, tableAnswer, inlineMath } from './web-common.js';
import { scanForm } from './web-exam-shared.js';

const element = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};
const button = (text, className) => {
  const node = element('button', text, className);
  node.type = 'button';
  return node;
};
const CONFIDENCE = ['Not confident', 'Slightly', 'Somewhat', 'Confident', 'Very confident'];

export async function renderReviews(container, api) {
  const auckland = () => {
    const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Pacific/Auckland', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
    const part = type => parts.find(item => item.type === type).value;
    return `${part('year')}-${part('month')}-${part('day')}`;
  };
  let today = auckland();
  let all = [];            // every saved question, due or not
  let queue = [];          // what the practice view is working through
  let mode = 'due';        // 'due' | 'all' | 'practice'
  let returnTo = 'due';
  let loading = false, submitting = false, scanning = false;
  const labels = new Map();
  const drafts = new Map();
  const filters = { topic: '', status: 'all', text: '' };

  const head = element('div', undefined, 'page-head');
  const title = element('div');
  title.append(element('h1', 'Review'), element('p', 'Short questions on what you have learned, scheduled to come back just before you forget.', 'muted'));
  const refresh = button('Refresh', 'small');
  head.append(title, refresh);
  const stats = element('div', undefined, 'stat-row');
  const tabs = element('div', undefined, 'tabs');
  const status = element('p', undefined, 'muted');
  status.setAttribute('role', 'status');
  const content = element('div', undefined, 'stack');
  container.replaceChildren(head, stats, tabs, status, content);

  const isDue = question => question.due_date <= today;
  const dueQuestions = () => all.filter(isDue);

  async function loadLabels() {
    const subjects = await api('/subjects');
    await Promise.all(subjects.map(async subject => {
      for (const topic of await api(`/subjects/${subject.id}/topics`)) labels.set(topic.id, { subject: subject.name, topic: topic.name, level: subject.level });
    }));
  }
  const labelOf = id => labels.has(id) ? `${labels.get(id).subject} · ${labels.get(id).topic}` : `Topic ${id}`;

  function drawChrome() {
    const due = dueQuestions().length;
    stats.replaceChildren();
    for (const [value, name] of [[due, 'Due now'], [all.length - due, 'Coming up'], [all.length, 'Total questions']]) {
      const stat = element('div', undefined, 'stat'); stat.append(element('b', String(value)), element('span', name)); stats.append(stat);
    }
    tabs.replaceChildren();
    for (const [key, label] of [['due', `Due now (${due})`], ['all', `All questions (${all.length})`]]) {
      const tab = element('a', label); tab.href = '#reviews'; tab.setAttribute('role', 'button');
      if ((mode === 'practice' ? returnTo : mode) === key) tab.setAttribute('aria-current', 'page');
      tab.onclick = event => { event.preventDefault(); if (submitting) return; mode = key; show(); };
      tabs.append(tab);
    }
  }

  function show(focus = false) {
    content.replaceChildren();
    drawChrome();
    if (mode === 'due') { queue = dueQuestions(); return practice(queue, focus, 'due'); }
    if (mode === 'practice') return practice(queue, focus, returnTo);
    return browse();
  }

  // ---- all questions ---------------------------------------------------
  function browse() {
    const bar = element('div', undefined, 'toolbar');
    const topic = element('select'); topic.setAttribute('aria-label', 'Topic');
    topic.add(new Option('All topics', ''));
    for (const id of [...new Set(all.map(q => q.topic_id))].sort((a, b) => labelOf(a).localeCompare(labelOf(b)))) topic.add(new Option(labelOf(id), id));
    topic.value = filters.topic;
    const state = element('select'); state.setAttribute('aria-label', 'Status');
    for (const [value, label] of [['all', 'Any status'], ['due', 'Due now'], ['upcoming', 'Coming up'], ['new', 'Never answered']]) state.add(new Option(label, value));
    state.value = filters.status;
    const text = element('input', undefined, 'grow'); text.type = 'search'; text.placeholder = 'Search questions'; text.value = filters.text; text.setAttribute('aria-label', 'Search questions');
    bar.append(topic, state, text);
    const list = element('ul', undefined, 'list card');
    content.append(bar, list);
    const draw = () => {
      filters.topic = topic.value; filters.status = state.value; filters.text = text.value.trim().toLowerCase();
      list.replaceChildren();
      const rows = all.filter(q => (!filters.topic || String(q.topic_id) === filters.topic)
        && (filters.status === 'all' || (filters.status === 'due' && isDue(q)) || (filters.status === 'upcoming' && !isDue(q)) || (filters.status === 'new' && !q.answer_count))
        && (!filters.text || `${q.question} ${q.concept}`.toLowerCase().includes(filters.text)));
      if (!rows.length) { list.append(element('li', all.length ? 'No questions match these filters.' : 'No review questions yet. They are created when you complete a lesson or get an exam answer wrong.', 'empty')); return; }
      for (const q of rows) {
        const li = element('li');
        const text = element('div', undefined, 'grow');
        const snippet = q.question.replace(/\s+/g, ' ').replace(/\$/g, '');
        text.append(q.concept ? inlineMath(q.concept, 'strong') : element('strong', snippet.slice(0, 80)));
        text.append(element('div', q.concept ? (snippet.length > 140 ? snippet.slice(0, 140) + '…' : snippet) : '', 'muted'));
        const meta = element('div', undefined, 'muted');
        meta.append(element('span', isDue(q) ? 'Due now' : `Due ${q.due_date}`, `chip ${isDue(q) ? 'warn' : ''}`),
          ` ${labelOf(q.topic_id)} · ${q.answer_count ? `answered ${q.answer_count}×` : 'not answered yet'} · mastery ${Math.round((q.mastery || 0) * 100)}%`);
        text.append(meta);
        const go = button(isDue(q) ? 'Answer' : 'Practise now', 'small'); if (isDue(q)) go.classList.add('primary');
        go.onclick = () => { queue = [q]; mode = 'practice'; returnTo = 'all'; show(true); };
        li.append(text, go); list.append(li);
      }
    };
    topic.onchange = state.onchange = draw; text.oninput = draw;
    draw();
  }

  // ---- answering ---------------------------------------------------------
  function practice(questions, focus, back) {
    if (!questions.length) {
      const empty = element('div', undefined, 'empty');
      empty.append(element('p', back === 'due' ? 'Nothing is due. You are all caught up.' : 'No more questions.'));
      if (back === 'due' && all.length) {
        const more = button('Browse all questions', 'primary'); more.onclick = () => { mode = 'all'; show(); };
        empty.append(more);
      } else if (back === 'all') {
        const list = button('Back to all questions', 'primary'); list.onclick = () => { mode = 'all'; show(); };
        empty.append(list);
      }
      content.append(empty);
      return;
    }
    const question = questions[0];
    const card = element('section', undefined, 'card stack narrow');
    const meta = element('div', undefined, 'toolbar');
    meta.append(element('span', labelOf(question.topic_id), 'chip'), element('span', isDue(question) ? `Due ${question.due_date}` : `Not due until ${question.due_date}`, `chip ${isDue(question) ? 'warn' : ''}`));
    if (back === 'due') meta.append(element('span', `${questions.length} left`, 'muted'));
    card.append(meta);
    if (question.concept) card.append(inlineMath(question.concept, 'h2'));     // titles can carry maths, such as $K_c$
    const prompt = element('div'); mathText(prompt, question.question); card.append(prompt);

    const form = element('form', undefined, 'stack');
    const answerLabel = element('label', 'Your answer', 'stack');
    const answer = element('textarea');
    answer.required = true; answer.maxLength = 50000; answer.rows = 6;
    // An unsent answer survives a reload or a closed tab on this device.
    const draft = drafts.get(question.id) || stash.read(`review:${question.id}`) || { answer: '', confidence: '' };
    answer.value = draft.answer;
    answer.addEventListener('input', () => { container.dataset.dirty = String(!!answer.value.trim()); answer.setCustomValidity(''); });
    answerLabel.append(mathInput(answer));
    const hint = element('div', undefined, 'toolbar'); hint.append(hintButton(api, { kind: 'review', ref: question.id, answer: () => answer.value }));
    // Working done on paper: a photo (taken now, or from the gallery) is read into the box above, to be checked before it is submitted.
    const photo = element('div', undefined, 'toolbar');
    const scanned = (label, capture) => {
      const input = element('input'); input.type = 'file'; input.hidden = true; input.multiple = !capture;
      input.accept = capture ? 'image/*' : 'image/png,image/jpeg,application/pdf';
      if (capture) input.setAttribute('capture', 'environment');
      const open = button(label, 'small'); open.onclick = () => input.click();
      input.addEventListener('change', async () => {
        const files = [...input.files]; input.value = '';
        if (!files.length || submitting || scanning) return;
        try {
          const form = scanForm(files);
          if (answer.value.trim() && !window.confirm('Replace your answer with the text read from this photo?')) return;
          scanning = true; for (const node of [open, ...photo.querySelectorAll('button')]) node.disabled = true;
          status.textContent = 'Reading your handwriting. This can take a minute…';
          const result = await api(`/review-questions/${question.id}/scan`, { method: 'POST', body: form });
          answer.value = result.transcription; answer.dispatchEvent(new Event('input', { bubbles: true }));
          status.textContent = result.notice;
        } catch (error) { status.textContent = error.message || 'Could not read the photo.'; }
        finally { scanning = false; for (const node of photo.querySelectorAll('button')) node.disabled = false; }
      });
      photo.append(open, input);
    };
    scanned('Take a photo', true); scanned('Upload photos', false);
    const scale = element('fieldset', undefined, 'scale');
    scale.append(element('legend', 'How confident are you?'));
    const row = element('div', undefined, 'segmented');
    for (let value = 1; value <= 5; value++) {
      const label = element('label', undefined, 'pill');
      const input = element('input'); input.type = 'radio'; input.name = 'confidence'; input.value = String(value); input.required = true;
      input.checked = draft.confidence === input.value;
      label.append(input, element('span', `${value} · ${CONFIDENCE[value - 1]}`));
      row.append(label);
    }
    scale.append(row);
    const saveDraft = () => {
      const value = { answer: answer.value, confidence: form.querySelector('input[name="confidence"]:checked')?.value || '' };
      drafts.set(question.id, value);
      if (value.answer || value.confidence) stash.write(`review:${question.id}`, value); else stash.clear(`review:${question.id}`);
    };
    form.addEventListener('input', saveDraft); form.addEventListener('change', saveDraft);
    const submit = button('Submit answer', 'primary'); submit.type = 'submit';
    const toolbar = element('div', undefined, 'toolbar'); toolbar.append(submit);
    if (back === 'all') { const cancel = button('Back to list'); cancel.onclick = () => { mode = 'all'; show(); }; toolbar.append(cancel); }
    const feedback = element('div', undefined, 'stack'); feedback.setAttribute('role', 'status');
    const grid = tableAnswer(question.question, answer);
    form.append(...(grid ? [grid] : []), answerLabel, photo, hint, scale, toolbar);
    card.append(form, feedback);
    content.append(card);
    if (focus) answer.focus();

    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (submitting || loading || scanning) return;
      answer.setCustomValidity(answer.value.trim() ? '' : 'Please enter an answer.');
      if (!form.reportValidity()) return;
      saveDraft();
      const selected = Number(drafts.get(question.id).confidence);
      if (!Number.isInteger(selected) || selected < 1 || selected > 5) return;
      submitting = true; container.dataset.busy = 'true';
      for (const node of [submit, refresh, answer, scale]) node.disabled = true;
      status.textContent = 'Saving and checking your answer…';
      try {
        const result = await api(`/review-questions/${question.id}/answers`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ answer: answer.value, confidence: selected }),
        });
        drafts.delete(question.id); stash.clear(`review:${question.id}`); container.dataset.dirty = 'false';
        const stored = all.find(q => q.id === question.id);
        if (stored) { stored.due_date = result.next_due; stored.answer_count = (stored.answer_count || 0) + 1; stored.mastery = Math.min(1, (stored.mastery || 0) * 0.75 + (result.correct ? 0.25 : 0)); }
        const outcome = result.outcome === 'correct' ? ['Correct', 'ok'] : result.outcome === 'incorrect' ? ['Not quite', 'bad'] : ['Not independently marked', 'warn'];
        const verdict = element('p'); verdict.append(element('span', outcome[0], `chip ${outcome[1]}`), element('span', ' AI judgement, advisory only.', 'muted'));
        feedback.append(verdict);
        if (result.outcome === 'confidence-based') feedback.append(element('p', 'Scheduled using your confidence.', 'muted'));
        if (result.feedback) { const explanation = element('div'); mathText(explanation, result.feedback); feedback.append(aiBox(explanation)); }
        const mastery = typeof result.mastery === 'number' && Number.isFinite(result.mastery) ? `${Math.round(result.mastery * 100)}%` : 'not provided';
        feedback.append(element('p', `Next due ${result.next_due || 'not provided'} · topic mastery estimate ${mastery}, a scheduling estimate and not proof of mastery.`, 'muted'));
        const finished = back === 'due' ? questions.length <= 1 : true;
        const next = button(back === 'due' ? (finished ? 'Finish review' : 'Next question') : 'Back to all questions', 'primary');
        next.onclick = () => {
          status.textContent = '';
          if (back === 'due') show(true);
          else { mode = 'all'; show(); }
        };
        feedback.append(next);
        drawChrome();
        status.textContent = 'Answer saved.';
        next.focus();
      } catch (error) {
        status.textContent = `${error.message || 'Could not save your answer.'} Your draft is preserved. If the connection failed, the answer may already have been saved; refreshing checks the due list before you retry.`;
        submit.disabled = false; answer.disabled = false; scale.disabled = false;
      } finally {
        submitting = false; container.dataset.busy = 'false'; refresh.disabled = false;
      }
    });
  }

  async function load() {
    if (loading || submitting) return;
    loading = true; refresh.disabled = true; status.textContent = 'Loading questions…';
    today = auckland();
    try {
      // The due call also writes review questions for lessons completed since the last visit.
      const [due] = await Promise.all([api(`/review-questions/due?as_of=${today}`), loadLabels().catch(() => { labels.clear(); status.dataset.names = 'failed'; })]);
      if (!Array.isArray(due)) throw new Error('Invalid due-question response.');
      all = await api('/review-questions?limit=500');
      if (!Array.isArray(all)) throw new Error('Invalid question list.');
      show();
      status.textContent = status.dataset.names === 'failed' ? 'Some topic names could not be loaded. Questions are still available.' : '';
    } catch (error) {
      status.textContent = `${error.message || 'Could not load reviews.'} Any current draft is unchanged. Use Refresh to retry.`;
    } finally { loading = false; refresh.disabled = false; }
  }
  refresh.addEventListener('click', load);
  await load();
}
