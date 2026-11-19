// Exam revision: pick a topic and get a pack built from the mistakes you have made in it.
// A pack is a short re-teach plus questions for each weak concept. Answers are marked straight away (the daily review marking),
// and a wrong answer comes back through spaced repetition. Everything in a pack is AI-written and unofficial.
import { mathText, aiBox, countUp, hintButton } from './web-common.js';
import { answerBox, choiceResultView } from './web-answer.js';
import { el, json, field, option } from './web-exam-shared.js';

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
const when = iso => new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });

export async function renderRevision(container, api, params) {
  const root = el('section', '', 'stack');
  container.replaceChildren(root);
  const alive = () => root.isConnected;
  const error = el('p', '', 'error'); error.setAttribute('role', 'alert');
  const report = err => { if (alive()) error.textContent = err?.message || String(err); };
  let timer = null;
  const stop = () => { clearTimeout(timer); timer = null; };

  // ---- the topic list -------------------------------------------------------------------------
  async function home() {
    stop();
    const head = el('div', '', 'page-head'); const title = el('div');
    title.append(el('h1', 'Exam revision'),
      el('p', 'Pick a topic. A revision pack is built from the mistakes you have made in it (rapid questions, marked exams and the daily review): a short re-teach and questions on each weak concept.', 'muted'));
    head.append(title);
    const table = el('table', '', 'table');
    const body = el('tbody');
    const header = el('tr'); for (const h of ['Topic', 'Mistakes', 'Latest pack', '']) header.append(el('th', h));
    table.append(el('thead')); table.firstChild.append(header); table.append(body);
    const filters = el('div', '', 'fields'); const levelSel = el('select'), subjectSel = el('select');
    filters.append(field('Level', levelSel), field('Subject', subjectSel));
    root.replaceChildren(head, filters, error, table);
    let topics, packs;
    try { [topics, packs] = await Promise.all([api('/revision/topics'), api('/revision/packs?limit=50')]); } catch (err) { return report(err); }
    if (!alive()) return;
    error.textContent = '';
    const latest = new Map();
    for (const p of packs) if (!latest.has(p.topic_id)) latest.set(p.topic_id, p);
    topics.sort((a, b) => b.mistakes - a.mistakes || a.level - b.level || a.subject.localeCompare(b.subject) || a.topic.localeCompare(b.topic));
    // Level, then subject, narrow the list; each row hides itself rather than being rebuilt.
    const rows = [];
    // University papers (kind 'paper') share one "Papers" choice instead of an NCEA level, as in the other pickers.
    const shelf = t => t.kind === 'paper' ? 'papers' : String(t.level);
    const applyFilter = () => { for (const [t, row] of rows) row.hidden = (levelSel.value !== '' && shelf(t) !== levelSel.value) || (subjectSel.value !== '' && t.subject !== subjectSel.value); };
    const fillSubjects = () => {
      subjectSel.replaceChildren(); option(subjectSel, '', 'All subjects');
      [...new Set(topics.filter(t => levelSel.value === '' || shelf(t) === levelSel.value).map(t => t.subject))].sort().forEach(name => option(subjectSel, name, name));
      applyFilter();
    };
    option(levelSel, '', 'All levels and papers');
    [...new Set(topics.map(shelf))].sort((a, b) => (a === 'papers') - (b === 'papers') || a - b)
      .forEach(n => option(levelSel, n, n === 'papers' ? 'Papers' : `NCEA Level ${n}`));
    levelSel.addEventListener('change', fillSubjects); subjectSel.addEventListener('change', applyFilter);
    fillSubjects();
    for (const t of topics) {
      const row = el('tr'); rows.push([t, row]);
      const count = el('td', '', 'num'); count.append(el('span', '0'));
      countUp(count.firstChild, t.mistakes);
      const last = latest.get(t.topic_id);
      const status = el('td');
      if (last) {
        const text = last.status === 'ready' ? `${last.answered} of ${last.total} answered · ${when(last.created_at)}` : last.status === 'generating' ? 'Building…' : 'Could not build';
        const a = el('a', text); a.href = `#exams/revision?pack=${last.id}`; status.append(a);
      } else status.append(el('span', 'None yet', 'muted'));
      const action = el('td');
      const build = el('button', t.mistakes ? 'Build pack' : 'No mistakes yet', t.mistakes ? 'primary small' : 'small'); build.type = 'button'; build.disabled = !t.mistakes;
      build.onclick = async () => {
        build.disabled = true;
        try { const started = await api('/revision/packs', json('POST', { topic_id: t.topic_id })); location.hash = `#exams/revision?pack=${started.id}`; }
        catch (err) { report(err); build.disabled = false; }
      };
      action.append(build);
      const name = el('td'); name.append(el('strong', t.topic), ' ', el('span', t.kind === 'paper' ? `Paper · ${t.subject}` : `Level ${t.level} · ${t.subject}`, 'muted'));
      row.append(name, count, status, action);
      body.append(row);
    }
    applyFilter();
  }

  // ---- one pack -------------------------------------------------------------------------------
  async function pack(id) {
    const back = el('a', '← All topics'); back.href = '#exams/revision';
    const holder = el('div', '', 'stack');
    root.replaceChildren(back, error, holder);
    let drawn = false;

    const draw = data => {
      const head = el('div', '', 'page-head'); const title = el('div');
      title.append(el('h1', `${data.topic} revision`),
        el('p', `Built ${when(data.created_at)} from ${plural(data.mistake_count, 'mistake')}. AI-written from your resources and your answers; unofficial, so check it against your resources.`, 'muted'));
      head.append(title);
      const progress = el('p', `${data.answered} of ${data.total} answered · ${data.correct} correct`, 'muted');
      const basis = el('details'); basis.append(el('summary', 'What it was built from'));
      const list = el('ul');
      for (const m of data.mistakes) list.append(el('li', `${m.from}${m.label ? ` ${m.label}` : ''}: ${m.question}`));
      basis.append(list);
      holder.replaceChildren(head, progress, basis);
      data.sections.forEach((section, index) => {
        const s = el('section', '', 'stack'); s.style.setProperty('--i', index);
        s.append(el('h2', section.concept));
        if (section.why) s.append(el('p', section.why, 'muted'));
        s.append(mathText(section.teaching));
        section.questions.forEach((q, n) => s.append(question(q, n + 1, progress, data)));
        holder.append(s);
      });
      drawn = true;
    };

    const question = (q, number, progress, data) => {
      const box = el('div', '', 'card stack');
      box.append(el('strong', `Question ${number}`), mathText(q.question));
      const out = el('div', '', 'stack');
      const answer = answerBox({ api, forms: q.answer_forms, value: q.result?.your_answer || '', collapsed: true, rows: 3, label: `Answer to question ${number}` });
      const label = el('div', '', 'stack'); label.append(el('span', 'Your answer', 'field-label'), answer);
      const check = el('button', q.result ? 'Try again' : 'Check answer', 'primary'); check.type = 'button';
      const show = result => {
        out.replaceChildren();
        const chip = el('span', result.correct ? 'Correct' : 'Not quite', `chip ${result.correct ? 'ok' : 'warn'}`);
        out.append(chip, ' ', el('span', result.correct ? 'It will come back later to keep it fresh.' : 'It comes back tomorrow.', 'muted'));
        if (result.feedback) out.append(aiBox(mathText(result.feedback)));
        if (result.expected_answer) { const d = el('details'); d.append(el('summary', 'Worked answer'), mathText(result.expected_answer)); out.append(d); }
      };
      check.onclick = async () => {
        check.disabled = true;
        await answer.flush();
        if (!answer.value.trim()) { answer.focus(); check.disabled = false; return; }
        try {
          const reply = await api(`/review-questions/${q.id}/answers`, json('POST', { answer: answer.value, confidence: 3 }));
          const full = await api(`/revision/packs/${id}`);
          const fresh = full.sections.flatMap(s => s.questions).find(x => x.id === q.id);
          show(fresh?.result || { correct: reply.correct, feedback: reply.feedback });
          if (reply.choice_result) { out.querySelector('.ai-box')?.remove(); out.append(choiceResultView(reply.choice_result)); }
          progress.textContent = `${full.answered} of ${full.total} answered · ${full.correct} correct`;
          check.textContent = 'Try again';
        } catch (err) { report(err); }
        check.disabled = false;
      };
      if (q.result) show(q.result);
      const actions = el('div', '', 'toolbar'); actions.append(check, hintButton(api, { kind: 'review', ref: q.id, answer: () => answer.value }));
      box.append(label, actions, out);
      return box;
    };

    const load = async () => {
      let data;
      try { data = await api(`/revision/packs/${id}`); } catch (err) { return report(err); }
      if (!alive()) return;
      error.textContent = '';
      if (data.status === 'generating') {
        holder.replaceChildren(el('h1', `${data.topic} revision`),
          el('p', 'Reading your mistakes and writing questions. This takes about a minute; you can leave this page and come back.', 'muted'));
        timer = setTimeout(load, 3000);
      } else if (data.status === 'failed') {
        holder.replaceChildren(el('h1', `${data.topic} revision`), el('p', data.error || 'The pack could not be built.', 'error'));
      } else if (!drawn) draw(data);
    };
    await load();
  }

  const id = params?.get?.('pack');
  if (id) await pack(Number(id)); else await home();
  return stop;
}
