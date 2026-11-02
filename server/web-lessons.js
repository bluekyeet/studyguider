import { mathText } from './web-common.js';

const element = (tag, text = '', className = '') => {
  const node = document.createElement(tag);
  node.textContent = text;
  node.className = className;
  return node;
};
const json = body => ({ headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const message = error => error?.message || String(error);

// Presentation only: source snapshots and saved questions keep their citations.
function readable(text) {
  return String(text || '')
    .replace(/\[?\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b\]?/gi, '')
    .replace(/\[S\d+(?:\s*[,;]\s*S?\d+)*\]/g, '')
    .replace(/\bS\d+\b/g, '')
    .replace(/\(\s*\)|\[\s*\]/g, '');
}

function sections(markdown) {
  const result = [];
  let title = 'Overview', lines = [], fence = false;
  const flush = () => {
    if (lines.some(line => line.trim())) result.push({ title, body: lines.join('\n').trim() });
    lines = [];
  };
  for (const line of String(markdown || '').split(/\r?\n/)) {
    if (/^\s*```/.test(line)) fence = !fence;
    const heading = !fence && line.match(/^\s*#{1,6}\s+(.+?)\s*#*\s*$/);
    if (heading) { flush(); title = heading[1]; }
    else lines.push(line);
  }
  flush();
  return result.length ? result : [{ title: 'Lesson', body: String(markdown || '') }];
}

export async function renderLessons(container, api) {
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
      const head = element('div', '', 'page-head'); const title = element('div');
      title.append(element('h1', 'Lessons'), element('p', 'A new lesson is prepared overnight for each topic you are learning.', 'muted'));
      head.append(title); content.append(head);
      if (!lessons.length) {
        content.append(element('p', 'No lessons yet. Choose the topics you are learning in Settings and your first lesson will be ready tomorrow.', 'empty'));
        return;
      }
      const todo = lessons.filter(l => !l.completed_at);
      const total = lessons.length, done = total - todo.length;
      if (todo.length) {
        const next = todo[0];
        const hero = element('section', '', 'card stack hero');
        hero.append(element('span', 'Up next', 'chip'), element('h2', readable(next.query)),
          element('p', `${next.subject} · ${next.topic}`, 'muted'), button('Start lesson', () => open(next), 'primary'));
        const bar = element('div', '', 'progress'); const fill = element('i'); fill.style.width = `${Math.round(done / total * 100)}%`; bar.append(fill);
        hero.append(bar, element('p', `${done} of ${total} lessons completed`, 'muted'));
        content.append(hero);
      }
      const groups = new Map();
      for (const lesson of lessons) {
        const key = `${lesson.subject} · ${lesson.topic}`;
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(lesson);
      }
      const grid = element('div', '', 'card-grid wide');
      for (const [name, items] of groups) {
        const card = element('section', '', 'card stack');
        card.append(element('h2', name));
        const list = element('ul', '', 'list');
        for (const lesson of items) {
          const li = element('li'); const text = element('div', '', 'grow');
          text.append(element('strong', readable(lesson.query)));
          li.append(text, element('span', lesson.completed_at ? 'Completed' : 'To do', `chip ${lesson.completed_at ? 'ok' : ''}`),
            button(lesson.completed_at ? 'Review' : 'Open', () => open(lesson), 'small'));
          list.append(li);
        }
        card.append(list); grid.append(card);
      }
      content.append(grid);
    } finally { loading = false; }
  }

  async function open(summary) {
    if (loading || !canLeave()) return;
    loading = true;
    try {
      const [lesson, answers] = await Promise.all([
        api(`/lessons/${summary.id}`), api(`/lessons/${summary.id}/answers`),
      ]);
      if (disposed) return;
      drafts.clear();
      const chunks = sections(lesson.lesson);
      // Match existing saved question text first, including Android section keys.
      for (let index = 0; index < chunks.length; index++) {
        const chunk = chunks[index];
        if (!/your turn|question|check|quiz/i.test(chunk.title)) continue;
        const question = `${chunk.title}\n${chunk.body}`;
        const saved = answers.find(row => row.question === question);
        const digest = saved ? null : await crypto.subtle.digest('SHA-256', new TextEncoder().encode(question));
        const key = saved?.question_key || [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, '0')).join('');
        drafts.set(index, { key, question, answer: saved?.answer || '', feedback: saved?.feedback || '',
          savedAnswer: saved?.answer || '', savedFeedback: saved?.feedback || '', revision: saved?.revision || 0, busy: false });
      }
      if (disposed) return;
      active = { ...lesson, chunks, completed_at: summary.completed_at, history: [], questionDraft: '', replies: [] };
      current = 0;
      showLesson();
    } finally { loading = false; }
  }

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
      go.append(element('span', String(index + 1), 'num'), element('span', readable(section.title)));
      if (index === current) go.setAttribute('aria-current', 'step');
      go.onclick = () => { current = index; showLesson(); window.scrollTo({ top: 0 }); };
      li.append(go); items.append(li);
    });
    outline.append(element('p', `Section ${current + 1} of ${lesson.chunks.length}`, 'muted'), items);

    const main = element('div', '', 'reader-main stack');
    const card = element('article', '', 'card stack');
    card.append(element('h2', readable(chunk.title)), rendered(chunk.body));
    main.append(element('h1', readable(lesson.query)),
      element('p', lesson.warning || 'AI-generated lesson: check against the original sources.', 'muted'), card);
    const draft = drafts.get(current);
    if (draft) practice(card, draft, lesson);
    const pager = element('div', '', 'toolbar');
    if (current > 0) pager.append(button('← Previous', () => { current--; showLesson(); window.scrollTo({ top: 0 }); }));
    if (current + 1 < lesson.chunks.length) pager.append(button('Next →', () => { current++; showLesson(); window.scrollTo({ top: 0 }); }, 'primary'));
    else {
      const complete = button(lesson.completed_at ? 'Lesson completed' : 'Complete lesson', async () => {
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
    const label = element('label', 'Your answer', 'stack');
    const input = element('textarea');
    input.rows = 6; input.maxLength = 50000; input.value = draft.answer;
    const status = element('p', '', 'muted');
    input.oninput = () => { draft.answer = input.value; status.textContent = 'Unsaved answer'; };
    label.append(input);
    const feedback = element('div');
    if (draft.feedback) feedback.append(rendered(draft.feedback));
    const save = button('Save answer and feedback', async () => {
      if (draft.busy) return;
      draft.busy = true;
      const sent = { question: draft.question, answer: draft.answer, feedback: draft.feedback, revision: draft.revision };
      try {
        const result = await api(`/lessons/${lesson.id}/answers/${draft.key}`, { method: 'PUT', ...json(sent) });
        draft.revision = result.revision; draft.savedAnswer = sent.answer; draft.savedFeedback = sent.feedback;
        status.textContent = draft.answer === sent.answer && draft.feedback === sent.feedback ? 'Saved' : 'New changes not yet saved';
      } catch (error) {
        status.textContent = 'Not saved. Your local draft is retained. If another device changed it, copy your draft before reopening the lesson.';
        throw error;
      } finally { draft.busy = false; }
    });
    const mark = button('Check my answer', async () => {
      if (draft.busy) return;
      if (!draft.answer.trim()) throw new Error('Write an answer first.');
      const question = `Mark my answer to this lesson question.\n${draft.question}\nMy answer:\n${draft.answer}`;
      if (question.length > 2000) throw new Error('The question and answer exceed the marking endpoint’s 2,000-character limit. Shorten your answer or ask a focused explanation question.');
      draft.busy = true;
      try {
        const result = await api(`/lessons/${lesson.id}/explain`, { method: 'POST', ...json({ question }) });
        draft.feedback = result.explanation; feedback.replaceChildren(rendered(draft.feedback));
        status.textContent = 'AI feedback is unverified. Save explicitly to keep it.';
      } finally { draft.busy = false; }
    });
    card.append(label, element('div', '', 'toolbar'), status, feedback);
    label.nextSibling.append(mark, save);
  }

  function explainPanel(lesson, chunk, target) {
    const panel = element('section', '', 'card stack');
    panel.append(element('h2', 'Explain this section'), element('p', 'Follow-ups include the last three exchanges. Replies are unverified.', 'muted'));
    const label = element('label', 'Your question', 'stack');
    const input = element('textarea');
    input.maxLength = 2000; input.rows = 3; input.value = lesson.questionDraft;
    input.oninput = () => { lesson.questionDraft = input.value; };
    label.append(input); panel.append(label);
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
      entry.append(element('h3', readable(reply.question)), rendered(reply.answer), save); replies.append(entry);
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
    panel.append(ask, replies); target.append(panel);
  }

  try { await feed(); }
  catch (error) {
    errorBox.textContent = message(error);
    content.append(button('Retry loading lessons', feed));
  }
  return dispose;
}
