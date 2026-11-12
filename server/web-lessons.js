import { mathText, mathInput, autosave, stash, sha256Hex, aiBox, readable, inlineMath, hintButton } from './web-common.js';
import { answerBox } from './web-answer.js';

const element = (tag, text = '', className = '') => {
  const node = document.createElement(tag);
  node.textContent = text;
  node.className = className;
  return node;
};
const json = body => ({ headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const message = error => error?.message || String(error);

// Chunks a lesson exactly like the Android reader, so a section index saved on one device
// means the same section on the other, and both derive the same answer key.
// body keeps the original Markdown for display; question is the text Android hashes.
function sections(markdown) {
  const result = [];
  let title = 'Overview', lines = [], question = [];
  const flush = () => {
    if (question.length) result.push({ title, body: lines.join('\n').trim(), question: `${title}\n${question.join('\n\n')}` });
    lines = []; question = [];
  };
  for (const raw of String(markdown || '').split(/\r?\n/)) {
    const trim = raw.trim();
    if (/^#{1,6}\s+/.test(trim)) {
      flush();
      title = trim.replace(/^#+/, '').trim().replace(/\s+#+\s*$/, '') || 'Overview';
    } else if (trim) {
      lines.push(raw);
      if (!['---', '***', '___'].includes(trim)) {
        // Android drops list and quote markers but keeps numbered items as written.
        question.push(/^[*+-] /.test(trim) || trim.startsWith('> ') ? trim.slice(2).trim() : trim);
      }
    } else lines.push(raw);
  }
  flush();
  return result.length ? result : [{ title: 'Lesson', body: String(markdown || ''), question: `Lesson\n${String(markdown || '').trim()}` }];
}

export async function renderLessons(container, api, params) {
  let disposed = false, loading = false, active = null, current = 0;
  const drafts = new Map();
  const root = element('div', '', 'stack');
  container.replaceChildren(root);
  const errorBox = element('p');
  errorBox.setAttribute('role', 'alert');
  const content = element('div', '', 'stack');
  root.append(errorBox, content);
  const pending = () => [...drafts.values()].some(d => d.answer !== d.savedAnswer || d.feedback !== d.savedFeedback || d.busy)
    || Boolean(active?.questionDraft?.trim()) || Boolean(active?.explainBusy);
  const canLeave = () => !pending() || window.confirm('You have unsaved lesson work or a request in progress. Leave without saving?');
  const beforeUnload = event => {
    if (pending()) { event.preventDefault(); event.returnValue = ''; }
  };
  const outsideNavigation = event => {
    const target = event.target instanceof Element ? event.target.closest('a, button, [data-page]') : null;
    if (target && !container.contains(target) && !canLeave()) {
      event.preventDefault(); event.stopImmediatePropagation();
    }
  };
  window.addEventListener('beforeunload', beforeUnload);
  document.addEventListener('click', outsideNavigation, true);
  function dispose() {
    disposed = true;
    window.removeEventListener('beforeunload', beforeUnload);
    document.removeEventListener('click', outsideNavigation, true);
    document.removeEventListener('visibilitychange', onVisible);
    window.removeEventListener('focus', onVisible);
    // Push anything still waiting out of the debounce so leaving the page loses nothing.
    for (const draft of drafts.values()) if (draft.answer !== draft.savedAnswer || draft.feedback !== draft.savedFeedback) draft.saver.flush();
  }
  // The host router can use canLeave() for programmatic navigation, then dispose().
  dispose.canLeave = canLeave;
  function button(text, action, className = '') {
    const node = element('button', text, className);
    node.type = 'button';
    node.onclick = async () => {
      node.disabled = true;
      errorBox.textContent = '';
      try { await action(); }
      catch (error) { if (!disposed) errorBox.textContent = message(error); }
      finally { node.disabled = false; }
    };
    return node;
  }
  const rendered = text => mathText(readable(text));

  async function feed() {
    if (loading || !canLeave()) return;
    loading = true;
    try {
      const lessons = await api('/lessons');
      if (disposed) return;
      active = null; drafts.clear(); content.replaceChildren();
      // Lessons belong to the day they were prepared, in New Zealand time.
      const day = value => new Intl.DateTimeFormat('en-CA', { timeZone: 'Pacific/Auckland' }).format(new Date(value));
      const today = day(new Date());
      const fresh = lessons.filter(lesson => lesson.created_at && day(lesson.created_at) === today);
      // A lesson nobody opened moves on to the next day (one per topic, the newest). One that was started but not
      // finished stays in Earlier lessons; its topic gets a new lesson instead.
      const carried = new Map();
      for (const lesson of lessons) {
        if (lesson.completed_at || lesson.started || fresh.some(f => f.topic_id === lesson.topic_id) || carried.has(lesson.topic_id)) continue;
        carried.set(lesson.topic_id, lesson);
      }
      const todays = [...fresh, ...carried.values()];
      const head = element('div', '', 'page-head'); const title = element('div');
      title.append(element('h1', 'Today’s lessons'),
        element('p', new Intl.DateTimeFormat('en-NZ', { timeZone: 'Pacific/Auckland', weekday: 'long', day: 'numeric', month: 'long' }).format(new Date()), 'muted'));
      head.append(title); content.append(head);
      // Older lessons stay reachable, collapsed so the page remains about today.
      const earlier = () => {
        const older = lessons.filter(lesson => !todays.includes(lesson));
        if (!older.length) return null;
        const box = element('details', '', 'card stack'); box.append(element('summary', `Earlier lessons (${older.length})`));
        const rows = element('div', '', 'stack');
        for (const lesson of older) {
          const row = element('div', '', 'toolbar');
          row.append(element('span', lesson.created_at ? day(lesson.created_at) : '', 'chip'),
            element('span', `${lesson.subject} · ${lesson.topic}`, 'muted'),
            element('span', lesson.completed_at ? 'Completed' : 'Not finished', `chip ${lesson.completed_at ? 'ok' : 'warn'}`),
            button('Open', () => open(lesson)));
          rows.append(row);
        }
        box.append(rows);
        return box;
      };
      if (!todays.length) {
        const empty = element('div', '', 'empty');
        empty.append(element('p', lessons.length
          ? 'No lessons were prepared for today. A new one is made overnight for each topic you are learning.'
          : 'No lessons yet. Choose the topics you are learning in Settings and your first lesson will be ready tomorrow.'));
        const settings = element('a', 'Choose topics in Settings'); settings.href = '#settings'; empty.append(settings);
        content.append(empty);
        const past = earlier(); if (past) content.append(past);
        return;
      }
      // A saved reading position means this lesson was started, perhaps on another device.
      const where = await Promise.all(todays.map(lesson => api(`/lessons/${lesson.id}/progress`).catch(() => null)));
      const left = todays.filter(lesson => !lesson.completed_at).length;
      content.append(element('p', left ? `${todays.length - left} of ${todays.length} done` : 'All of today’s lessons are done. Well done.', 'muted'));
      const grid = element('div', '', 'card-grid wide');
      for (const [position, lesson] of todays.entries()) {
        const started = !lesson.completed_at && (where[position]?.section || 0) > 0;
        const card = element('article', '', 'card stack lesson-card');
        const done = Boolean(lesson.completed_at);
        const tags = element('div', '', 'toolbar');
        tags.append(element('span', `${lesson.subject} · ${lesson.topic}`, 'chip'), element('span', done ? 'Completed' : started ? 'In progress' : 'To do', `chip ${done ? 'ok' : 'warn'}`));
        if (carried.get(lesson.topic_id) === lesson) tags.append(element('span', `From ${day(lesson.created_at)}`, 'chip'));
        card.append(tags, element('h2', readable(lesson.query)),
          button(done ? 'Review lesson' : started ? 'Continue lesson' : 'Start lesson', () => open(lesson), done ? '' : 'primary'));
        grid.append(card);
      }
      content.append(grid);
      const past = earlier(); if (past) content.append(past);
    } finally { loading = false; }
  }

  async function open(summary) {
    if (loading || !canLeave()) return;
    loading = true;
    try {
      const [lesson, answers, progress] = await Promise.all([
        api(`/lessons/${summary.id}`), api(`/lessons/${summary.id}/answers`),
        api(`/lessons/${summary.id}/progress`).catch(() => ({ section: 0, revision: 0 })),
      ]);
      if (disposed) return;
      drafts.clear();
      const chunks = sections(lesson.lesson);
      for (let index = 0; index < chunks.length; index++) {
        const chunk = chunks[index];
        if (!/your turn|question|check|quiz/i.test(chunk.title)) continue;
        const key = await sha256Hex(chunk.question);
        const saved = answers.find(row => row.question_key === key);
        const draft = { index, key, question: chunk.question, answer: saved?.answer || '', feedback: saved?.feedback || '',
          savedAnswer: saved?.answer || '', savedFeedback: saved?.feedback || '', revision: saved?.revision || 0, busy: false, ui: null };
        // Text typed here but not yet saved (closed tab, lost connection) comes back first.
        const local = stash.read(`answer:${summary.id}:${key}`);
        if (local && (local.answer !== draft.answer || local.feedback !== draft.feedback)) { draft.answer = local.answer; draft.feedback = local.feedback; draft.restored = true; }
        draft.saver = autosave({
          isDirty: () => draft.answer !== draft.savedAnswer || draft.feedback !== draft.savedFeedback,
          status: (kind, error) => { draft.state = { kind, error }; draft.ui?.(kind, error); },
          save: async () => {
            const sent = { question: draft.question, answer: draft.answer, feedback: draft.feedback, revision: draft.revision };
            const result = await api(`/lessons/${summary.id}/answers/${key}`, { method: 'PUT', ...json(sent) });
            draft.revision = result.revision; draft.savedAnswer = sent.answer; draft.savedFeedback = sent.feedback;
            if (draft.answer === sent.answer && draft.feedback === sent.feedback) stash.clear(`answer:${summary.id}:${key}`);
          },
        });
        drafts.set(index, draft);
        if (draft.restored) draft.saver.touch();
      }
      if (disposed) return;
      const saved = Math.min(Math.max(Number(progress.section) || 0, 0), chunks.length - 1);
      active = { ...lesson, chunks, completed_at: summary.completed_at, history: [], questionDraft: '', replies: [], position: { saved, revision: progress.revision || 0 } };
      current = saved;
      showLesson();
    } finally { loading = false; }
  }

  // Remember where the learner is so any device can carry on from the same section.
  async function savePosition(lesson, section) {
    const position = lesson.position;
    if (position.saving) { position.next = section; return; }
    position.saving = true;
    try {
      for (let attempt = 0; attempt < 2; attempt++) {
        try {
          const result = await api(`/lessons/${lesson.id}/progress`, { method: 'PUT', ...json({ section, revision: position.revision }) });
          position.revision = result.revision; position.saved = section; return;
        } catch (error) {
          // Another device moved first; the newest position wins, so take its revision and write again.
          const latest = await api(`/lessons/${lesson.id}/progress`).catch(() => null);
          if (!latest || attempt) return;
          position.revision = latest.revision;
        }
      }
    } finally {
      position.saving = false;
      if (position.next !== undefined && position.next !== position.saved) { const next = position.next; position.next = undefined; savePosition(lesson, next); }
      else position.next = undefined;
    }
  }
  let readerStep = 0;
  function goTo(section) {
    readerStep = Math.sign(section - current); current = section; savePosition(active, section); showLesson(); window.scrollTo({ top: 0 });
  }

  // Coming back to the tab picks up answers written on another device, unless this one has newer text.
  async function refreshFromServer() {
    if (!active || disposed || document.hidden) return;
    const lesson = active;
    try {
      const rows = await api(`/lessons/${lesson.id}/answers`);
      if (active !== lesson) return;
      let changed = false;
      for (const draft of drafts.values()) {
        const row = rows.find(r => r.question_key === draft.key);
        if (!row || row.revision <= draft.revision) continue;
        if (draft.answer !== draft.savedAnswer || draft.feedback !== draft.savedFeedback || draft.busy) continue; // keep unsaved local work
        draft.answer = draft.savedAnswer = row.answer; draft.feedback = draft.savedFeedback = row.feedback; draft.revision = row.revision;
        stash.clear(`answer:${lesson.id}:${draft.key}`);
        changed = changed || draft === drafts.get(current);
      }
      if (changed && !document.activeElement?.matches?.('textarea')) showLesson();
    } catch { /* offline: the next focus tries again */ }
  }
  const onVisible = () => { if (!document.hidden) refreshFromServer(); };
  document.addEventListener('visibilitychange', onVisible);
  window.addEventListener('focus', onVisible);

  function showLesson() {
    const lesson = active, chunk = lesson.chunks[current];
    content.replaceChildren();
    const layout = element('div', '', 'reader');

    const outline = element('nav', '', 'reader-outline card');
    outline.setAttribute('aria-label', 'Lesson sections');
    outline.append(button('← All lessons', feed, 'small'));
    const items = element('ol');
    lesson.chunks.forEach((section, index) => {
      const li = element('li'); const go = element('button'); go.type = 'button';
      go.append(element('span', String(index + 1), 'num'), inlineMath(readable(section.title)));
      if (index === current) go.setAttribute('aria-current', 'step');
      go.onclick = () => goTo(index);
      li.append(go); items.append(li);
    });
    outline.append(element('p', `Section ${current + 1} of ${lesson.chunks.length}`, 'muted'), items);
    // On a phone the sections are a row of pills; bring the current one into view.
    requestAnimationFrame(() => { const here = items.querySelector('[aria-current]'); if (here) items.scrollLeft += here.getBoundingClientRect().left - items.getBoundingClientRect().left - 12; });

    const main = element('div', '', 'reader-main stack');
    if (readerStep) { main.style.setProperty('--ex', readerStep * 28 + 'px'); main.style.setProperty('--ey', '0px'); }
    const card = element('article', '', 'card stack');
    card.append(inlineMath(readable(chunk.title), 'h2'), rendered(chunk.body));
    const banner = element('div', '', 'toolbar');
    banner.append(element('span', 'AI generated · verify with sources', 'ai-badge'),
      element('span', lesson.warning || 'Check this lesson against the original sources.', 'muted'));
    main.append(element('h1', readable(lesson.query)), banner, card);
    const draft = drafts.get(current);
    if (draft) practice(card, draft, lesson);
    const pager = element('div', '', 'toolbar');
    if (current > 0) pager.append(button('← Previous', () => goTo(current - 1)));
    if (current + 1 < lesson.chunks.length) pager.append(button('Next →', () => goTo(current + 1), 'primary'));
    else {
      const complete = button(lesson.completed_at ? 'Lesson completed' : 'Complete lesson', async () => {
        await Promise.all([...drafts.values()].map(d => d.saver.flush()));
        if (pending()) throw new Error('Save your answers and finish or clear your explanation question before completing this lesson.');
        const result = await api(`/lessons/${lesson.id}/complete`, { method: 'POST' });
        lesson.completed_at = result.completed_at;
        if (!disposed && active === lesson) showLesson();
      }, 'primary');
      complete.disabled = Boolean(lesson.completed_at); pager.append(complete);
    }
    main.append(pager);

    const side = element('aside', '', 'reader-side stack');
    explainPanel(lesson, chunk, side);
    const sources = element('details', '', 'card');
    sources.append(element('summary', 'Inspect original sources and citations'));
    for (const source of lesson.sources || []) {
      const entry = element('div', '', 'stack');
      entry.append(element('h3', `${source.filename} · Page ${source.page}`),
        element('p', `Resource ${source.resource_id}`, 'muted'), mathText(source.content || ''));
      sources.append(entry);
    }
    const original = element('details');
    original.append(element('summary', 'Original lesson text'), element('pre', lesson.lesson));
    sources.append(original); side.append(sources);
    layout.append(outline, main, side); content.append(layout);
  }

  function practice(card, draft, lesson) {
    const label = element('div', '', 'stack');
    // The question lives in the lesson text, so the server reads which answer forms it asks for from its wording.
    draft.forms ??= api('/answer-forms', { method: 'POST', ...json({ question: draft.question.slice(0, 30000) }) }).then(r => r.answer_forms);
    const input = answerBox({ api, forms: draft.forms, value: draft.answer, maxLength: 50000 });
    const status = element('p', '', 'state'); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
    const choices = element('div', '', 'toolbar'); choices.hidden = true;
    const feedback = element('div');
    const showFeedback = text => feedback.replaceChildren(...(text ? [aiBox(rendered(text))] : []));
    showFeedback(draft.feedback);
    const stashKey = `answer:${lesson.id}:${draft.key}`;

    const say = (kind, error) => {
      status.dataset.state = kind;
      choices.hidden = kind !== 'conflict';
      status.textContent = kind === 'saving' ? 'Saving…'
        : kind === 'saved' ? 'Saved · on all your devices'
        : kind === 'conflict' ? 'Changed on another device. Choose which version to keep.'
        : `Local draft · not saved yet (${error?.message || 'offline'}). Retrying.`;
    };
    draft.ui = say;   // lets the autosaver update whichever copy of this panel is on screen
    if (draft.state) say(draft.state.kind, draft.state.error);
    else if (draft.restored) say('saving');
    else if (draft.savedAnswer || draft.savedFeedback) say('saved');
    else status.textContent = 'Your answers save automatically and follow you to other devices.';

    const changed = () => {
      stash.write(stashKey, { answer: draft.answer, feedback: draft.feedback });
      draft.saver.touch();
    };
    input.addEventListener('input', () => { draft.answer = input.value; changed(); });
    // Leaving the box saves straight away instead of waiting for the pause.
    input.addEventListener('focusout', () => { if (draft.answer !== draft.savedAnswer) draft.saver.flush(); });

    // A conflict means the server holds a newer revision: either overwrite it or adopt it.
    const latest = async () => (await api(`/lessons/${lesson.id}/answers`)).find(row => row.question_key === draft.key);
    const keepMine = button('Keep my version', async () => {
      const row = await latest(); draft.revision = row?.revision || 0; draft.saver.resume();
    });
    const useTheirs = button('Use the other version', async () => {
      const row = await latest();
      draft.answer = draft.savedAnswer = row?.answer || ''; draft.feedback = draft.savedFeedback = row?.feedback || '';
      draft.revision = row?.revision || 0; stash.clear(stashKey);
      input.value = draft.answer; showFeedback(draft.feedback);
      draft.saver.resume(); say('saved');
    });
    choices.append(keepMine, useTheirs);

    const mark = button('Check my answer', async () => {
      if (draft.busy) return;
      draft.busy = true;
      try {
        await input.flush();     // a drawing still uploading is part of the answer
        if (!draft.answer.trim()) throw new Error('Write an answer first.');
        // Checked against this lesson and its sources; drawings and graphs go to the marker as images.
        const result = await api(`/lessons/${lesson.id}/check`, { method: 'POST', ...json({ question: draft.question.slice(0, 20000), answer: draft.answer }) });
        draft.feedback = result.feedback; showFeedback(draft.feedback);
        changed(); // the feedback is saved with the answer, so both devices show it
      } finally { draft.busy = false; }
    });
    label.append(element('span', 'Your answer', 'field-label'), input);
    const actions = element('div', '', 'toolbar');
    actions.append(mark, hintButton(api, { kind: 'lesson', ref: `${lesson.id}:${draft.key}`, answer: () => draft.answer, question: () => draft.question }));
    card.append(label, actions, status, choices, feedback);
  }

  function explainPanel(lesson, chunk, target) {
    // Collapsed until needed so the reading column keeps the page.
    const panel = element('details', '', 'card');
    panel.open = Boolean(lesson.replies.length || lesson.questionDraft.trim() || lesson.explainBusy);
    const inner = element('div', '', 'stack');
    panel.append(element('summary', 'Ask about this section'), inner);
    inner.append(element('p', 'Follow-ups include the last three exchanges. Replies are unverified.', 'muted'));
    const label = element('label', 'Your question', 'stack');
    const input = element('textarea');
    input.maxLength = 2000; input.rows = 3; input.value = lesson.questionDraft;
    input.oninput = () => { lesson.questionDraft = input.value; };
    label.append(mathInput(input)); inner.append(label);
    const replies = element('div', '', 'stack');
    const appendReply = reply => {
      const entry = element('article', '', 'stack');
      const save = button('Save reply to topic notes', async () => {
        if (reply.answer.length > 50000) throw new Error('This reply exceeds the 50,000-character note limit.');
        await api(`/topics/${lesson.topic_id}/notes`, { method: 'POST', ...json({ content: reply.answer }) });
        reply.saved = true; save.textContent = 'Saved to notes';
      });
      save.disabled = reply.saved;
      if (reply.saved) save.textContent = 'Saved to notes';
      entry.append(element('h3', readable(reply.question)), aiBox(rendered(reply.answer)), save); replies.append(entry);
    };
    lesson.replies.forEach(appendReply);
    const ask = button('Explain', async () => {
      if (lesson.explainBusy) return;
      const question = input.value.trim();
      if (!question) throw new Error('Enter a question about this section.');
      const paragraph = `${chunk.title}\n${chunk.body}`;
      if (paragraph.length > 5000) throw new Error('This section exceeds the explanation endpoint’s 5,000-character context limit. Ask a focused question using a shorter section.');
      lesson.explainBusy = true;
      try {
        const result = await api(`/lessons/${lesson.id}/explain/paragraph`, { method: 'POST',
          ...json({ question, paragraph, history: lesson.history.slice(-3) }) });
        const reply = { question, answer: result.explanation, saved: false };
        lesson.replies.push(reply);
        lesson.history.push({ question, answer: reply.answer.slice(0, 8000) });
        lesson.history = lesson.history.slice(-3);
        if (lesson.questionDraft.trim() === question) { lesson.questionDraft = ''; input.value = ''; }
        lesson.explainBusy = false;
        if (!disposed && active === lesson) showLesson();
      } finally { lesson.explainBusy = false; }
    }, 'primary');
    ask.disabled = Boolean(lesson.explainBusy);
    inner.append(ask, replies); target.append(panel);
  }

  try {
    await feed();
    // #lessons?lesson=ID opens that lesson directly (used by the Home list).
    const wanted = Number(params?.get('lesson'));
    if (wanted) { const found = (await api('/lessons')).find(item => item.id === wanted); if (found) await open(found); }
  }
  catch (error) {
    errorBox.textContent = message(error);
    content.append(button('Retry loading lessons', feed));
  }
  return dispose;
}
