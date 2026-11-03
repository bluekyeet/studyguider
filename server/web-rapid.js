// Rapid exam questions and the Exam revision page.
// A rapid session is one-way: questions flash up, you answer or skip and move on, and you see nothing about
// how you are doing until you end the session. The server enforces that; this page just never asks for results early.
import { mathText, mathInput, stash, aiBox, countUp } from './web-common.js';
import { el, field, option, json, scanForm, questionView } from './web-exam-shared.js';

const GRADE = { not_achieved: 'Not achieved', achieved: 'Achieved', merit: 'Merit', excellence: 'Excellence' };
const gradeChip = outcome => el('span', GRADE[outcome] || 'Unclear', `chip ${outcome === 'merit' || outcome === 'excellence' ? 'ok' : outcome === 'not_achieved' ? 'warn' : ''}`.trim());
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
const minutes = seconds => seconds >= 90 ? `${Math.round(seconds / 60)} min` : `${seconds} s`;
const sourceLine = q => q.source === 'ai' ? 'AI-written question · unofficial' : `Past paper · AS ${q.standard_number} · ${q.year}${q.label ? ` · Question ${q.label}` : ''}`;
const link = (text, href) => { const a = el('a', text, 'button'); a.href = href; return a; };
const sourceLinks = item => {
  const row = el('div', '', 'toolbar');
  for (const [text, id, page] of [['Original paper', item.paper_resource_id, item.paper_page], ['Original schedule', item.schedule_resource_id, item.schedule_page]]) {
    if (!id) continue;
    const a = el('a', `${text} · page ${page}`); a.href = `/resources/${encodeURIComponent(id)}/download#page=${page}`; a.target = '_blank'; a.rel = 'noopener'; row.append(a);
  }
  return row;
};

export async function revisionCount(api) { return (await api('/exam-revision/summary')).total; }

// What a question looked like, what you wrote and what the marker said. Used by results and by revision.
function reviewBody(item) {
  const body = el('div', '', 'stack');
  body.append(questionView(item));
  body.append(el('h4', 'Your answer'), item.answer ? mathText(item.answer) : el('p', 'You skipped this question.', 'muted'));
  if (item.feedback) {
    const parts = [mathText(item.feedback)];
    for (const evidence of item.evidence || []) parts.push(el('blockquote', evidence.quote), mathText(`${evidence.marks} marks: ${evidence.explanation || ''}`));
    if (item.missing?.length) { parts.push(el('h4', 'Missing evidence / next steps')); for (const m of item.missing) parts.push(mathText(m)); }
    body.append(aiBox(...parts));
    if (item.second_review_disagrees) body.append(el('p', 'A second marker disagreed. Check the original schedule; marks are advisory.', 'muted'));
  }
  if (item.schedule_text) {
    const schedule = el('details');
    schedule.append(el('summary', item.source === 'ai' ? 'AI-written rubric (unofficial)' : 'Schedule excerpt'));
    if (item.source === 'ai') schedule.append(mathText(item.schedule_text));
    else schedule.append(el('p', 'Extracted text; table layout is lost. Use the original schedule page to compare.', 'muted'), el('pre', item.schedule_text, 'schedule-text'));
    body.append(schedule);
  }
  body.append(sourceLinks(item), el('p', item.rubric_type, 'muted'));
  return body;
}

export async function renderRapid(container, api) {
  const root = el('section', '', 'stack');
  container.replaceChildren(root);
  let alive = () => root.isConnected;
  let clock = null, poll = null;
  const stop = () => { clearInterval(clock); clearTimeout(poll); };
  const error = el('p', '', 'error'); error.setAttribute('role', 'alert');
  const view = el('div', '', 'stack');
  root.append(error, view);
  const report = err => { if (alive()) error.textContent = err?.message || String(err); };
  const show = (...nodes) => { error.textContent = ''; view.replaceChildren(...nodes); };

  // ---- setup ---------------------------------------------------------------------------------
  async function setup() {
    stop();
    const form = el('form', '', 'card stack');
    const subject = el('select'), topic = el('select'), source = el('select'), length = el('select');
    option(source, 'mix', 'Mix of past-paper and AI questions');
    option(source, 'past', 'Past-paper questions only');
    option(source, 'ai', 'AI-generated questions only');
    for (const n of [10, 20, 30, 50]) option(length, n, `${n} questions`);
    option(length, 'unlimited', 'Unlimited, until I end the session');
    const fields = el('div', '', 'fields');
    fields.append(field('Subject', subject), field('Topic', topic), field('Questions from', source), field('Session length', length));
    const start = el('button', 'Start session', 'primary'); start.type = 'submit'; start.disabled = true;
    form.append(el('h2', 'Start a rapid session'),
      el('p', 'Questions flash up one after another and you cannot go back. You will not see any marks or feedback until you end the session; answers are marked quietly as you go. AI-written questions are unofficial practice.', 'muted'),
      fields, start);
    const history = el('section', '', 'card stack');
    show(form, history);
    const loadTopics = async () => {
      topic.replaceChildren();
      if (!subject.value) return;
      try {
        const rows = await api(`/subjects/${encodeURIComponent(subject.value)}/topics`);
        rows.forEach(t => option(topic, t.id, t.name));
        if (!rows.length) option(topic, '', 'No topics yet');
        start.disabled = !topic.value;
      } catch (err) { report(err); }
    };
    subject.addEventListener('change', loadTopics);
    topic.addEventListener('change', () => { start.disabled = !topic.value; });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (start.disabled) return;
      start.disabled = true;
      try {
        const count = length.value === 'unlimited' ? null : Number(length.value);
        const session = await api('/rapid', json('POST', { topic_id: Number(topic.value), source: source.value, count }));
        play(session.id, session.target_count, session.question, 0);
      } catch (err) { report(err); start.disabled = false; }
    });
    try {
      const subjects = await api('/subjects');
      subjects.forEach(s => option(subject, s.id, `${s.name} · Level ${s.level}`));
      await loadTopics();
    } catch (err) { report(err); }
    try {
      const past = await api('/rapid');
      history.append(el('h2', 'Earlier sessions'));
      if (!past.length) history.append(el('p', 'No finished sessions yet.', 'muted'));
      for (const s of past) {
        const row = el('div', '', 'toolbar');
        const open = el('button', 'View results', 'small'); open.type = 'button'; open.onclick = () => results(s.id);
        row.append(el('span', new Intl.DateTimeFormat('en-CA', { timeZone: 'Pacific/Auckland' }).format(new Date(s.ended_at)), 'chip'),
          el('span', s.topic), el('span', `${plural(s.answered, 'answer')}, ${s.skipped} skipped`, 'muted'), open);
        history.append(row);
      }
    } catch (err) { /* history is optional */ }
  }

  // ---- a session in progress is offered back, so a reload never loses it ---------------------
  async function home() {
    try {
      const { active } = await api('/rapid/active');
      if (!alive()) return;
      if (active && sessionStorage.getItem('sg:autostart') === String(active.id) && active.question) {
        sessionStorage.removeItem('sg:autostart');
        return play(active.id, active.target_count, active.question, active.answered);
      }
      if (active) {
        const card = el('div', '', 'card stack');
        card.append(el('h2', 'You have a session in progress'),
          el('p', `${active.topic} · ${plural(active.answered, 'question')} answered so far.`, 'muted'));
        const row = el('div', '', 'toolbar');
        const resume = el('button', 'Continue session', 'primary'); resume.type = 'button';
        const finish = el('button', 'End it and see results'); finish.type = 'button';
        resume.onclick = () => active.question ? play(active.id, active.target_count, active.question, active.answered) : endSession(active.id);
        finish.onclick = () => endSession(active.id);
        row.append(resume, finish); card.append(row);
        show(card);
        return;
      }
    } catch (err) { report(err); }
    setup();
  }

  // ---- the flashing player -------------------------------------------------------------------
  function play(id, target, first, answered) {
    stop();
    let current = first, started = Date.now(), busy = false, scanRevision = 0, count = answered;
    const heading = el('div', '', 'toolbar');
    const status = el('p', '', 'muted'); status.setAttribute('role', 'status');
    const draw = () => {
      started = Date.now(); scanRevision = 0; status.textContent = '';
      const stashKey = `rapid:${id}:${current.question_id}`;
      const card = el('article', '', 'card stack');
      const head = el('div', '', 'toolbar');
      head.append(el('h2', `Question ${current.position}${target ? ` of ${target}` : ''}`), el('span', sourceLine(current), 'chip'));
      const answer = el('textarea'); answer.rows = 6; answer.maxLength = 100000;
      answer.value = stash.read(stashKey)?.text || '';
      answer.setAttribute('aria-label', 'Your answer');
      answer.addEventListener('input', () => stash.write(stashKey, { text: answer.value }));
      const box = el('label', 'Your answer'); box.append(mathInput(answer, { collapsed: true }));
      // Optional: a photo of handwriting fills the box; moving on confirms it.
      const photos = el('details');
      photos.append(el('summary', 'Answer on paper? Upload a photo instead'));
      const picker = el('input'); picker.type = 'file'; picker.multiple = true; picker.accept = 'image/png,image/jpeg,application/pdf';
      picker.setAttribute('aria-label', 'Photos of your handwritten answer');
      const read = el('button', 'Read my handwriting', 'small'); read.type = 'button';
      read.onclick = async () => {
        if (busy) return;
        try {
          const form = scanForm([...picker.files]);
          busy = true; read.disabled = true; status.textContent = 'Reading your handwriting…';
          const result = await api(`/exams/${id}/answers/${current.question_id}/scan`, { method: 'POST', body: form });
          answer.value = result.transcription; scanRevision = result.scan_revision; stash.write(stashKey, { text: answer.value });
          answer.dispatchEvent(new Event('input', { bubbles: true }));
          status.textContent = 'Read from your page. Check it, then press Next.';
        } catch (err) { status.textContent = err.message; }
        finally { busy = false; read.disabled = false; }
      };
      photos.append(picker, read);
      const next = el('button', 'Next', 'primary'); next.type = 'button';
      const skip = el('button', 'Skip'); skip.type = 'button';
      const finish = el('button', 'End session', 'small quiet'); finish.type = 'button';
      const controls = el('div', '', 'toolbar'); controls.append(next, skip, finish);
      const lock = on => { busy = on; for (const b of [next, skip, finish, read]) b.disabled = on; };
      const move = async kind => {
        if (busy) return;
        lock(true); status.textContent = '';
        try {
          const reply = await api(`/rapid/${id}/next`, json('POST', {
            question_id: current.question_id, answer: kind === 'skip' ? '' : answer.value, scan_revision: scanRevision,
            seconds: Math.round((Date.now() - started) / 1000), skip: kind === 'skip' }));
          stash.clear(stashKey); count += 1;
          if (reply.question) { current = reply.question; lock(false); swap(); }
          else endSession(id, null, reply.finished ? 'You reached the end of your session.' : 'You have used every question available for this topic.');
        } catch (err) { lock(false); status.textContent = `${err.message} Your answer is kept; press Next to try again.`; }
      };
      next.onclick = () => move('next');
      skip.onclick = () => move('skip');
      finish.onclick = () => {
        if (busy) return;
        if (!window.confirm('End the session now? Your results appear straight away.')) return;
        endSession(id, { question_id: current.question_id, answer: answer.value, scan_revision: scanRevision, seconds: Math.round((Date.now() - started) / 1000) });
      };
      answer.addEventListener('keydown', event => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); move('next'); } });
      card.append(head, questionView(current), box, photos, controls, status);
      return { card, focus: () => answer.focus({ preventScroll: true }) };
    };
    const swap = () => {
      const built = draw();
      show(heading, built.card);
      window.scrollTo({ top: 0, behavior: 'smooth' });
      built.focus();
    };
    heading.className = 'toolbar';
    heading.append(el('p', 'Rapid session · no going back · results appear when you end it', 'muted'));
    swap();
  }

  // ---- ending and results --------------------------------------------------------------------
  async function endSession(id, body, note) {
    stop();
    try { await api(`/rapid/${id}/end`, json('POST', body || {})); } catch (err) { return report(err); }
    results(id, note);
  }

  async function results(id, note) {
    stop();
    const wrap = el('div', '', 'stack');
    show(wrap);
    const opened = new Set();
    const shown = {};   // stat figures keep their node so numbers count up once and then just update
    let first = true;
    const draw = data => {
      const b = data.breakdown;
      const head = el('div', '', 'page-head'); const title = el('div');
      title.append(el('h1', 'Session results'),
        el('p', `${data.topic} · ${plural(data.answered, 'question')} answered, ${b.skipped} skipped · ${minutes(data.seconds)} in total`, 'muted'));
      head.append(title);
      const parts = [head];
      if (note) parts.push(el('p', note, 'muted'));
      if (data.pending) parts.push(el('p', `Marking is finishing: ${plural(data.pending, 'answer')} still being marked. Grades appear below as they arrive.`, 'muted'));
      // Grade breakdown
      const stats = el('div', '', 'stat-row');
      for (const [key, label] of [['not_achieved', 'Not achieved'], ['achieved', 'Achieved'], ['merit', 'Merit'], ['excellence', 'Excellence'], ['skipped', 'Skipped'], ['unclear', 'Unclear'], ['failed', 'Could not mark']]) {
        if (['skipped', 'unclear', 'failed'].includes(key) && !b[key]) continue;
        const box = el('div', '', `stat grade-${key}`); const figure = el('b', String(b[key]));
        if (first) countUp(figure, b[key]);
        box.append(figure, el('span', label)); stats.append(box);
      }
      const total = ['not_achieved', 'achieved', 'merit', 'excellence', 'skipped', 'unclear'].reduce((n, k) => n + b[k], 0);
      const bar = el('div', '', 'grade-bar'); bar.setAttribute('role', 'img');
      bar.setAttribute('aria-label', `Grades: ${['not_achieved', 'achieved', 'merit', 'excellence'].map(k => `${b[k]} ${GRADE[k]}`).join(', ')}`);
      for (const k of ['not_achieved', 'skipped', 'achieved', 'merit', 'excellence', 'unclear']) {
        if (!b[k]) continue;
        const seg = el('i', '', `g-${k}`); seg.style.flexGrow = String(b[k]); bar.append(seg);
      }
      parts.push(stats, total ? bar : el('span'));
      if (b.failed) {
        const retry = el('button', 'Try marking again', 'small'); retry.type = 'button';
        retry.onclick = async () => { try { await api(`/rapid/${id}/remark`, json('POST', {})); poll = setTimeout(tick, 2500); } catch (err) { report(err); } };
        parts.push(retry);
      }
      const missed = b.not_achieved + b.skipped;
      parts.push(el('p', missed
        ? `${plural(data.revision_added, 'missed question')} added to Exam revision and sent to your lessons, so your next lessons revisit them.`
        : (data.pending ? '' : 'No misses in this session.'), 'muted'));
      const actions = el('div', '', 'toolbar');
      const again = el('button', 'New session', 'primary'); again.type = 'button'; again.onclick = () => setup();
      actions.append(again, link('Exam revision', '#exams/revision')); parts.push(actions);
      // Each question, in order
      const list = el('div', '', 'stack');
      for (const item of data.items) {
        const row = el('details', '', 'card'); row.open = opened.has(item.question_id);
        row.addEventListener('toggle', () => { if (row.open) opened.add(item.question_id); else opened.delete(item.question_id); });
        const summary = el('summary'); summary.append(`Question ${item.position} `);
        summary.append(item.status === 'pending' ? el('span', 'Marking…', 'chip') : item.status === 'failed' ? el('span', 'Could not mark', 'chip warn')
          : item.status === 'skipped' ? el('span', 'Skipped', 'chip warn') : gradeChip(item.outcome));
        summary.append(' ', el('span', sourceLine(item), 'muted'));
        row.append(summary, reviewBody(item)); list.append(row);
      }
      parts.push(el('h2', 'Question by question'), el('p', data.notice, 'muted'), list);
      // Later polls rebuild the page with new marks; only the first build plays the entrance motion.
      wrap.classList.toggle('settled', !first);
      first = false;
      wrap.replaceChildren(...parts);
    };
    const tick = async () => {
      try {
        const data = await api(`/rapid/${id}/results`);
        if (!alive()) return;
        draw(data);
        if (data.pending > 0) poll = setTimeout(tick, 2500);
      } catch (err) { report(err); }
    };
    tick();
  }

  home();
  return () => { stop(); alive = () => false; };
}

// ---- Exam revision --------------------------------------------------------------------------
export async function renderRevision(container, api) {
  const root = el('section', '', 'stack');
  container.replaceChildren(root);
  const alive = () => root.isConnected;
  const error = el('p', '', 'error'); error.setAttribute('role', 'alert');
  const head = el('div', '', 'page-head'); const title = el('div');
  title.append(el('h1', 'Exam revision'),
    el('p', 'Questions you have missed or skipped in rapid sessions. Look at the schedule, then redo them; a question clears when you next get it Achieved or better. Misses also feed your next lessons.', 'muted'));
  head.append(title);
  const filters = el('div', '', 'toolbar'), cleared = el('input'), list = el('div', '', 'stack');
  cleared.type = 'checkbox';
  const clearedLabel = el('label', 'Show cleared', 'check'); clearedLabel.prepend(cleared);
  root.append(head, error, filters, list);
  let topicId = null, summary = { total: 0, topics: [] };
  const report = err => { if (alive()) error.textContent = err?.message || String(err); };

  const redo = async id => {
    try {
      const session = await api('/rapid', json('POST', { topic_id: id, source: 'revision', count: null }));
      sessionStorage.setItem('sg:autostart', String(session.id));
      location.hash = '#exams/rapid';
    } catch (err) { report(err); }
  };

  const draw = async () => {
    try {
      const rows = await api(`/exam-revision${topicId ? `?topic_id=${topicId}&` : '?'}include_resolved=${cleared.checked}`);
      if (!alive()) return;
      error.textContent = '';
      list.replaceChildren();
      if (!rows.length) { list.append(el('p', summary.total ? 'Nothing in this view.' : 'Nothing to revise. Questions you miss in rapid sessions will appear here.', 'empty')); return; }
      const byTopic = new Map();
      for (const row of rows) { if (!byTopic.has(row.topic_id)) byTopic.set(row.topic_id, []); byTopic.get(row.topic_id).push(row); }
      for (const [id, items] of byTopic) {
        const section = el('section', '', 'stack');
        const bar = el('div', '', 'toolbar');
        const open = items.filter(i => !i.resolved_at).length;
        bar.append(el('h2', `${items[0].subject} · ${items[0].topic}`));
        if (open) { const go = el('button', `Redo ${plural(open, 'question')}`, 'primary'); go.type = 'button'; go.onclick = () => redo(id); bar.append(go); }
        section.append(bar);
        for (const item of items) {
          const row = el('details', '', 'card');
          const head = el('summary'); head.append(item.resolved_at ? el('span', 'Cleared', 'chip ok') : el('span', `Tried ${item.attempts} time${item.attempts === 1 ? '' : 's'}`, 'chip warn'), ' ',
            el('span', sourceLine(item), 'muted'), ' ', el('span', (item.question_text || '').replace(/\s+/g, ' ').slice(0, 90)));
          row.append(head, reviewBody({ ...item, answer: item.your_answer, feedback: item.feedback }));
          section.append(row);
        }
        list.append(section);
      }
    } catch (err) { report(err); }
  };

  try {
    summary = await api('/exam-revision/summary');
    const chip = (label, id, n) => {
      const b = el('button', n === undefined ? label : `${label} (${n})`, 'small'); b.type = 'button';
      b.setAttribute('aria-pressed', String(topicId === id));
      b.onclick = () => { topicId = id; for (const x of filters.querySelectorAll('button')) x.setAttribute('aria-pressed', String(x === b)); draw(); };
      return b;
    };
    filters.append(chip('All topics', null, summary.total));
    for (const t of summary.topics) filters.append(chip(`${t.subject} · ${t.topic}`, t.topic_id, t.outstanding));
    filters.append(clearedLabel);
    cleared.addEventListener('change', draw);
    await draw();
  } catch (err) { report(err); }
  return () => {};
}
