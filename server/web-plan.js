// Plan: what you study (an NCEA programme or university papers), when each assessment is, and what the planner does with it.
// Getting a paper in: an AUT code fetches its public descriptor; any other outline is pasted or uploaded; anything can be typed.
// Every import is a draft you check and edit before it is saved.
const el = (tag, text = '', className = '') => {
  const node = document.createElement(tag);
  if (text !== '') node.textContent = text;
  if (className) node.className = className;
  return node;
};
const json = body => ({ headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const refresh = () => window.dispatchEvent(new HashChangeEvent('hashchange'));
const field = (label, input) => { const wrap = el('label', '', 'stack'); wrap.append(el('span', label, 'muted'), input); return wrap; };
const input = (type, value = '', attrs = {}) => { const node = el('input'); node.type = type; node.value = value ?? ''; Object.assign(node, attrs); return node; };
const select = (options, value) => { const node = el('select'); for (const [v, label] of options) node.add(new Option(label, v, false, String(v) === String(value ?? ''))); return node; };
const status = () => { const node = el('p', '', 'muted'); node.setAttribute('role', 'status'); node.setAttribute('aria-live', 'polite'); return node; };
const button = (text, className = '') => { const node = el('button', text, className); node.type = 'button'; return node; };
const day = value => value ? new Date(value + 'T00:00:00').toLocaleDateString('en-NZ', { day: 'numeric', month: 'short', year: 'numeric' }) : 'No date';
const pct = value => value == null ? '—' : `${Math.round(value * 100)}%`;
async function guard(control, note, work) {
  control.disabled = true; note.textContent = 'Saving…'; note.className = 'muted';
  try { await work(); note.textContent = 'Saved'; }
  catch (error) { note.textContent = error.message; note.className = 'error'; }
  finally { control.disabled = false; }
}

const INSTITUTIONS = [['nzqa', 'NCEA (school)'], ['aut', 'AUT'], ['uoa', 'University of Auckland'], ['other', 'Another university or course']];
const KINDS = [['exam', 'Exam'], ['test', 'Test'], ['assignment', 'Assignment'], ['lab', 'Lab'], ['project', 'Project'], ['presentation', 'Presentation'],
  ['portfolio', 'Portfolio'], ['practical', 'Practical'], ['quiz', 'Quiz'], ['internal', 'NCEA internal'], ['external_exam', 'NCEA external exam'], ['other', 'Other']];
const GOALS = [['long_term', 'Keep it long term'], ['foundation', 'Later papers build on it'], ['assessment', 'Only for its assessments']];
const SCALES = [['ncea', 'NCEA (N/A/M/E)'], ['aut9', 'AUT (A+ to D)'], ['uoa9', 'University of Auckland (A+ to D-)'], ['percent', 'Percentage']];

export async function renderPlan(root, api) {
  const [curriculum, calendars, plan, estimates] = await Promise.all([api('/curriculum'), api('/calendars'), api('/review-plan'), api('/grade-estimates')]);
  const head = el('div', '', 'page-head'); const left = el('div');
  left.append(el('h1', 'Plan'), el('p', 'Your programme, its assessment dates, and how reviews and lessons are planned around them.', 'muted'));
  head.append(left); root.append(head);
  if (!curriculum.set_up) { setup(root, api, curriculum); return; }
  root.append(today(api, curriculum, plan));
  root.append(upcoming(curriculum, plan));
  const estimateOf = new Map(estimates.map(e => [e.subject_id, e]));
  for (const programme of curriculum.programmes) root.append(programmeCard(api, programme, curriculum, calendars, estimateOf));
  const loose = curriculum.subjects.filter(s => !s.programme_id && s.studying);
  if (loose.length) {
    const card = el('section', '', 'card stack');
    card.append(el('h2', 'Subjects not in a programme'), el('p', 'These still get lessons and reviews as before. Add them to a programme to plan around their assessment dates.', 'muted'));
    for (const subject of loose) card.append(el('p', subject.name));
    root.append(card);
  }
  const another = el('section', '', 'card stack');
  another.append(el('h2', 'Another programme'), el('p', 'For example, the university you start next year while you finish NCEA: its papers get a refresher before they begin.', 'muted'));
  setupForm(another, api, curriculum, false);
  root.append(another);
}

// ---- first-time setup -------------------------------------------------------------------------------------------------
function setup(root, api, curriculum) {
  const card = el('section', '', 'card stack narrow');
  const existing = curriculum.subjects.filter(s => s.studying).length;
  card.append(el('h2', 'Set up your study plan'),
    el('p', 'Tell StudyGuider where you study and when your assessments are. Reviews then come back on a schedule that keeps what you learn, and lessons shift to exam practice as an assessment gets close.', 'muted'));
  if (existing) card.append(el('p', `Everything you already have stays as it is: your ${existing === 1 ? 'subject' : 'subjects'}, lessons, review history and files. Setting up only adds dates and details.`));
  setupForm(card, api, curriculum, true);
  root.append(card);
}

function setupForm(card, api, curriculum, first) {
  let institution = first ? 'nzqa' : 'aut';
  const group = el('div', '', 'segmented'); group.setAttribute('role', 'group'); group.setAttribute('aria-label', 'Where you study');
  const fields = el('div', '', 'fields');
  const level = select([['Level 1', 'NCEA Level 1'], ['Level 2', 'NCEA Level 2'], ['Level 3', 'NCEA Level 3']], 'Level 2');
  const year = input('number', new Date().getFullYear(), { min: 2024, max: 2100 });
  const name = input('text', '', { maxLength: 200, placeholder: 'Bachelor of Computer and Information Sciences' });
  const stage = input('text', 'Year 1', { maxLength: 100 });
  const hours = input('number', curriculum.hours_per_week ?? 10, { min: 0.5, max: 80, step: 0.5 });
  const drawFields = () => {
    fields.replaceChildren();
    if (institution === 'nzqa') fields.append(field('Level', level), field('Year', year));
    else fields.append(field('Programme', name), field('Year of study', stage), field('Starting year', year));
    if (first) fields.append(field('Hours a week you can study', hours));
  };
  const draw = () => {
    group.replaceChildren();
    for (const [value, label] of INSTITUTIONS) {
      const b = button(label); b.setAttribute('aria-pressed', String(value === institution));
      b.onclick = () => { institution = value; draw(); drawFields(); };
      group.append(b);
    }
  };
  draw(); drawFields();
  const save = el('button', first ? 'Save and continue' : 'Add programme', 'primary'); const note = status();
  const bar = el('div', '', 'toolbar'); bar.append(save, note);
  if (first) card.append(el('h3', 'Where do you study?'));
  card.append(group, fields);
  if (first) card.append(el('p', 'Time available sets how many reviews a day you get (about a third of your study time). You can change it later.', 'muted'));
  card.append(bar);
  save.onclick = () => guard(save, note, async () => {
    const ncea = institution === 'nzqa';
    const programme = await api('/programmes', { method: 'POST', ...json({
      kind: ncea ? 'ncea' : institution === 'other' ? 'other' : 'university', institution,
      name: ncea ? 'NCEA' : name.value.trim(), level: ncea ? level.value : stage.value.trim(), year: Number(year.value) || null }) });
    if (first) await api('/study-time', { method: 'PUT', ...json({ hours_per_week: Number(hours.value) || 10 }) });
    if (ncea) {
      // The NCEA subjects you already study join the programme, keeping everything they hold.
      for (const subject of curriculum.subjects.filter(s => s.studying && !s.programme_id && s.grade_scale === 'ncea'))
        await api(`/subjects/${subject.subject_id}/details`, { method: 'PUT', ...json(details(subject, { programme_id: programme.id })) });
    }
    refresh();
  });
}

const details = (subject, change = {}) => ({
  programme_id: subject.programme_id, code: subject.code || '', points: subject.points, term: subject.term || '', start_date: subject.start_date,
  end_date: subject.end_date, grade_scale: subject.grade_scale || 'ncea', pass_rule: subject.pass_rule || '', retention_goal: subject.retention_goal || 'long_term',
  outline_url: subject.outline_url || '', source: subject.source || 'manual', ...change });

// ---- today and the coming assessments ---------------------------------------------------------------------------------
function today(api, curriculum, plan) {
  const card = el('section', '', 'card stack');
  card.append(el('h2', 'Today'));
  const stats = el('div', '', 'stat-row');
  for (const [value, label] of [[plan.items.length, 'Reviews in today’s list'], [plan.left_out, 'Left for another day'], [plan.cap, 'Daily review limit']]) {
    const stat = el('div', '', 'stat'); stat.append(el('b', String(value)), el('span', label)); stats.append(stat);
  }
  card.append(stats);
  if (plan.left_out) card.append(el('p', `More is due than fits today. The most important first: questions for heavily weighted, close assessments that you are most likely to have forgotten.`, 'muted'));
  const hours = input('number', curriculum.hours_per_week ?? '', { min: 0.5, max: 80, step: 0.5, placeholder: 'Not set' });
  const save = button('Save'); const note = status();
  const row = el('div', '', 'toolbar'); row.append(field('Hours a week you can study', hours), save, note);
  save.onclick = () => guard(save, note, async () => { await api('/study-time', { method: 'PUT', ...json({ hours_per_week: Number(hours.value) }) }); refresh(); });
  card.append(row);
  if (plan.items.length) { const go = el('a', 'Start reviews', 'button primary'); go.href = '#reviews'; card.append(go); }
  return card;
}

function upcoming(curriculum, plan) {
  const card = el('section', '', 'card stack');
  card.append(el('h2', 'Coming assessments'));
  const names = new Map(curriculum.subjects.map(s => [s.subject_id, s.name]));
  const dated = curriculum.subjects.flatMap(s => s.assessments.filter(a => a.due_date && a.due_date >= curriculum.today && a.status !== 'done').map(a => ({ ...a, subject: names.get(s.subject_id) })))
    .sort((a, b) => a.due_date.localeCompare(b.due_date)).slice(0, 12);
  if (!dated.length) { card.append(el('p', 'No dated assessments yet. Add their dates below and the planner will work back from them.', 'muted')); return card; }
  const ready = new Map(plan.assessments.map(r => [r.assessment_id, r]));
  const table = el('table', '', 'table'); table.setAttribute('aria-label', 'Coming assessments');
  const headRow = el('tr'); for (const h of ['Date', 'Assessment', 'Weight', 'Predicted recall on the day', '']) headRow.append(el('th', h));
  const thead = el('thead'); thead.append(headRow); table.append(thead);
  const body = el('tbody');
  for (const a of dated) {
    const r = ready.get(a.id); const days = Math.round((new Date(a.due_date) - new Date(curriculum.today)) / 86400000);
    const tr = el('tr');
    const recall = !r || r.predicted_recall == null ? el('span', r && r.unanswered ? `${r.unanswered} questions not answered yet` : 'No reviews yet', 'muted')
      : el('span', `${pct(r.predicted_recall)}${r.at_risk ? ` · ${r.at_risk} at risk` : ''}${r.unanswered ? ` · ${r.unanswered} not answered yet` : ''}`);
    const phase = days <= 21 ? el('span', days <= 14 ? 'Final review' : 'Exam practice', 'chip warn') : el('span', '');
    for (const cell of [`${day(a.due_date)} (${days === 0 ? 'today' : days === 1 ? 'tomorrow' : `in ${days} days`})`, `${a.subject} · ${a.title}`,
      a.weight_pct != null ? `${a.weight_pct}%` : a.credits != null ? `${a.credits} credits` : '—', recall, phase]) {
      const td = el('td'); td.append(cell instanceof Node ? cell : document.createTextNode(cell)); tr.append(td);
    }
    body.append(tr);
  }
  table.append(body);
  const scroll = el('div', '', 'table-scroll'); scroll.append(table);
  card.append(scroll, el('p', 'Predicted recall: the chance you would remember the reviewed questions on the day if you did no more reviews, from your review history. In the last three weeks lessons turn into mixed exam-style practice; in the last two, reviews aim higher.', 'muted'));
  return card;
}

// ---- a programme and its subjects or papers ----------------------------------------------------------------------------
function programmeCard(api, programme, curriculum, calendars, estimateOf) {
  const wrap = el('section', '', 'stack');
  const title = programme.kind === 'ncea' ? `NCEA ${programme.level} ${programme.year || ''}`.trim()
    : `${programme.name || 'Programme'} · ${{ aut: 'AUT', uoa: 'University of Auckland' }[programme.institution] || 'Other'}${programme.level ? ` · ${programme.level}` : ''}`;
  const h = el('div', '', 'section-head'); h.append(el('h2', title));
  const remove = button('Remove programme', 'danger small');
  remove.onclick = async () => { if (confirm('Remove this programme? Its subjects, lessons and reviews stay; only the grouping goes.')) { await api(`/programmes/${programme.id}`, { method: 'DELETE' }); refresh(); } };
  h.append(remove); wrap.append(h);
  const subjects = curriculum.subjects.filter(s => s.programme_id === programme.id);
  if (!subjects.length) wrap.append(el('p', programme.kind === 'ncea' ? 'No subjects yet. Add one below.' : 'No papers yet. Add one below.', 'empty'));
  for (const subject of subjects) wrap.append(subjectCard(api, subject, programme, estimateOf.get(subject.subject_id)));
  if (programme.kind === 'ncea') wrap.append(addNceaSubject(api, programme, curriculum));
  else wrap.append(addPaper(api, programme, calendars));
  return wrap;
}

function estimateLine(estimate) {
  if (!estimate) return null;
  const box = el('div', '', 'toolbar');
  if (estimate.estimate) {
    const tone = estimate.kind === 'university' ? (estimate.passing ? 'ok' : 'bad') : ['Merit', 'Excellence'].includes(estimate.estimate) ? 'ok' : estimate.estimate === 'Not achieved' ? 'warn' : '';
    box.append(el('span', estimate.estimate, `chip ${tone}`.trim()), el('span', estimate.summary || '', 'muted'));
    if (estimate.must_pass_failed?.length) box.append(el('span', `Below the pass mark on: ${estimate.must_pass_failed.join(', ')}`, 'chip bad'));
  } else box.append(el('span', estimate.reason, 'muted'));
  return box;
}

function subjectCard(api, subject, programme, estimate) {
  const card = el('article', '', 'card stack');
  const top = el('div', '', 'section-head'); const name = el('div');
  name.append(el('h3', subject.name));
  const facts = [subject.points ? `${subject.points} points` : '', subject.level ? `Level ${subject.level}` : '', subject.term, subject.source === 'aut_descriptor' ? 'From AUT descriptor' : subject.source === 'outline' ? 'From your outline' : ''].filter(Boolean);
  if (facts.length) name.append(el('p', facts.join(' · '), 'muted'));
  top.append(name); card.append(top);
  const line = estimateLine(estimate); if (line) card.append(line);
  if (subject.pass_rule) card.append(el('p', `To pass: ${subject.pass_rule}`, 'muted'));
  // How long the knowledge must last sets the maintenance target after the assessments.
  const goal = select(GOALS, subject.retention_goal); const goalNote = status();
  goal.onchange = () => guard(goal, goalNote, () => api(`/subjects/${subject.subject_id}/details`, { method: 'PUT', ...json(details(subject, { retention_goal: goal.value })) }));
  const goalRow = el('div', '', 'toolbar'); goalRow.append(field('After its assessments', goal), goalNote); card.append(goalRow);

  card.append(el('h4', 'Assessments'));
  card.append(assessmentTable(api, subject));
  if (subject.outcomes.length) {
    card.append(el('h4', programme.kind === 'ncea' ? 'Standards' : 'Learning outcomes'));
    const list = el('ul', '', 'list');
    for (const o of subject.outcomes) { const li = el('li'); li.append(el('strong', o.code), el('span', ` ${o.title}${o.credits ? ` (${o.credits} credits)` : ''}`)); list.append(li); }
    card.append(list);
  }
  if (programme.kind === 'ncea') card.append(addStandard(api, subject));
  if (subject.topics.length) {
    const details = el('details'); details.append(el('summary', `Topics (${subject.topics.length})`));
    for (const topic of subject.topics) details.append(topicRow(api, topic, subject));
    const tip = el('p', '', 'muted'); tip.append('Upload slides and readings for each topic in ');
    const link = el('a', 'Library'); link.href = `#library?subject=${subject.subject_id}`; tip.append(link, ', and switch topics on in ');
    const settings = el('a', 'Settings'); settings.href = '#settings'; tip.append(settings, ' to get a lesson each night.');
    details.append(tip); card.append(details);
  }
  return card;
}

function topicRow(api, topic, subject) {
  const row = el('div', '', 'toolbar');
  row.append(el('span', topic.name, 'grow'), el('span', topic.active ? 'Learning' : 'Off', `chip ${topic.active ? 'ok' : ''}`.trim()));
  if (subject.outcomes.length) {
    const pick = el('select'); pick.multiple = true; pick.size = Math.min(4, subject.outcomes.length); pick.setAttribute('aria-label', `Outcomes covered by ${topic.name}`);
    for (const o of subject.outcomes) pick.add(new Option(o.code, o.id, false, topic.outcome_ids.includes(o.id)));
    const note = status();
    pick.onchange = () => guard(pick, note, () => api(`/topics/${topic.id}/outcomes`, { method: 'PUT', ...json({ outcome_ids: [...pick.selectedOptions].map(o => Number(o.value)) }) }));
    row.append(pick, note);
  }
  return row;
}

function assessmentTable(api, subject) {
  const wrap = el('div', '', 'stack');
  const table = el('table', '', 'table'); table.setAttribute('aria-label', `Assessments for ${subject.name}`);
  const headRow = el('tr'); for (const h of ['Assessment', 'Date', 'Weight %', 'Your mark %', '']) headRow.append(el('th', h));
  const thead = el('thead'); thead.append(headRow); table.append(thead);
  const body = el('tbody');
  for (const a of subject.assessments) {
    const tr = el('tr');
    const date = input('date', a.due_date || ''); date.setAttribute('aria-label', `Date of ${a.title}`);
    const weight = input('number', a.weight_pct ?? '', { min: 0, max: 100, step: 0.5 }); weight.setAttribute('aria-label', `Weight of ${a.title}`);
    const mark = input('number', a.result_pct ?? '', { min: 0, max: 100, step: 0.5, placeholder: 'Not back yet' }); mark.setAttribute('aria-label', `Your mark for ${a.title}`);
    const name = el('div'); name.append(el('strong', a.title));
    const tags = [KINDS.find(k => k[0] === a.kind)?.[1], a.must_pass ? 'Must pass' : '', a.outcome_codes.length ? a.outcome_codes.join(', ') : '', a.credits ? `${a.credits} credits` : ''].filter(Boolean);
    name.append(el('div', tags.join(' · '), 'muted'));
    const note = status(); const remove = button('Remove', 'small danger');
    const save = () => guard(date, note, () => api(`/assessments/${a.id}`, { method: 'PUT', ...json({
      title: a.title, kind: a.kind, due_date: date.value || null, weight_pct: weight.value === '' ? null : Number(weight.value), credits: a.credits,
      must_pass: a.must_pass, standard_number: a.standard_number, outcome_codes: a.outcome_codes,
      status: mark.value === '' ? 'planned' : 'done', result_pct: mark.value === '' ? null : Number(mark.value) }) }));
    date.onchange = weight.onchange = mark.onchange = save;
    remove.onclick = async () => { if (confirm(`Remove ${a.title}?`)) { await api(`/assessments/${a.id}`, { method: 'DELETE' }); refresh(); } };
    const actions = el('div', '', 'toolbar'); actions.append(remove, note);
    for (const cell of [name, date, weight, mark, actions]) { const td = el('td'); td.append(cell); tr.append(td); }
    body.append(tr);
  }
  table.append(body);
  const scroll = el('div', '', 'table-scroll'); scroll.append(table);
  if (subject.assessments.length) wrap.append(scroll); else wrap.append(el('p', 'No assessments yet.', 'muted'));
  // Adding one
  const form = el('form', '', 'fields');
  const title = input('text', '', { maxLength: 300, required: true, placeholder: 'Final exam' });
  const kind = select(KINDS, 'exam'); const date = input('date'); const weight = input('number', '', { min: 0, max: 100, step: 0.5 });
  const add = el('button', 'Add assessment'); const note = status();
  form.append(field('New assessment', title), field('Kind', kind), field('Date', date), field('Weight %', weight), add);
  form.onsubmit = event => { event.preventDefault(); guard(add, note, async () => {
    await api(`/subjects/${subject.subject_id}/assessments`, { method: 'POST', ...json({ title: title.value, kind: kind.value, due_date: date.value || null,
      weight_pct: weight.value === '' ? null : Number(weight.value) }) });
    refresh();
  }); };
  wrap.append(form, note);
  return wrap;
}

// ---- NCEA: subjects and standards --------------------------------------------------------------------------------------
function addNceaSubject(api, programme, curriculum) {
  const card = el('section', '', 'card stack');
  card.append(el('h3', 'Add a subject'));
  const free = curriculum.subjects.filter(s => !s.programme_id && s.grade_scale === 'ncea');
  if (!free.length) { const p = el('p', '', 'muted'); p.append('Every NCEA subject is in a programme. Add new subjects in '); const a = el('a', 'Library'); a.href = '#library'; p.append(a, '.'); card.append(p); return card; }
  const pick = select(free.map(s => [s.subject_id, s.name])); const add = el('button', 'Add to programme', 'primary'); const note = status();
  const row = el('div', '', 'toolbar'); row.append(pick, add, note); card.append(row);
  add.onclick = () => guard(add, note, async () => {
    const subject = free.find(s => String(s.subject_id) === pick.value);
    await api(`/subjects/${subject.subject_id}/details`, { method: 'PUT', ...json(details(subject, { programme_id: programme.id, grade_scale: 'ncea' })) });
    refresh();
  });
  return card;
}

function addStandard(api, subject) {
  const form = el('form', '', 'fields');
  const number = input('number', '', { min: 1, max: 99999, required: true, placeholder: '91171' });
  const title = input('text', '', { maxLength: 200, required: true, placeholder: 'Demonstrate understanding of mechanics' });
  const credits = input('number', '', { min: 0, max: 60, step: 1 });
  const kind = select([['external_exam', 'External exam'], ['internal', 'Internal']], 'external_exam');
  const date = input('date');
  const add = el('button', 'Add standard'); const note = status();
  form.append(field('Standard number', number), field('Title', title), field('Credits', credits), field('Assessed', kind), field('Date (exam or due date)', date), add);
  form.onsubmit = event => { event.preventDefault(); guard(add, note, async () => {
    const code = `AS${Number(number.value)}`;
    await api(`/subjects/${subject.subject_id}/outcomes`, { method: 'POST', ...json({ code, title: title.value, credits: credits.value === '' ? null : Number(credits.value), standard_number: Number(number.value) }) });
    await api(`/subjects/${subject.subject_id}/assessments`, { method: 'POST', ...json({ title: `${code} ${kind.value === 'internal' ? 'internal' : 'external exam'}`, kind: kind.value,
      due_date: date.value || null, credits: credits.value === '' ? null : Number(credits.value), standard_number: Number(number.value), outcome_codes: [code] }) });
    refresh();
  }); };
  const timetable = el('p', 'External exams with no date get this subject’s date from the NZQA timetable when it is known.', 'muted');
  const wrap = el('details'); wrap.append(el('summary', 'Add a standard and its assessment date'), form, note, timetable);
  // The subject's exam day in NZQA's published timetable, and a button to give it to the external standards still without a date.
  api(`/subjects/${subject.subject_id}/ncea-exam`).then(found => {
    if (!found.exam) { timetable.textContent = `${found.note} NCEA ${found.year} external exams run from mid November to early December.`; return; }
    const day = new Date(`${found.exam.date}T12:00:00`).toLocaleDateString('en-NZ', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    timetable.replaceChildren(`NZQA timetable: ${found.exam.subject} is on ${day}, ${found.exam.session}. `);
    const source = el('a', 'Source'); source.href = found.source; source.target = '_blank'; source.rel = 'noopener'; timetable.append(source, '. ');
    if (found.undated_external.length) {
      const use = el('button', `Use this date for ${found.undated_external.length} external standard${found.undated_external.length === 1 ? '' : 's'} without one`, 'small');
      use.type = 'button';
      use.onclick = () => guard(use, note, async () => { await api(`/subjects/${subject.subject_id}/ncea-exam`, { method: 'POST' }); refresh(); });
      timetable.append(use);
    }
  }).catch(() => {});
  return wrap;
}

// ---- university: adding a paper ---------------------------------------------------------------------------------------
function addPaper(api, programme, calendars) {
  const card = el('section', '', 'card stack');
  card.append(el('h3', 'Add a paper'));
  const tabs = el('div', '', 'tabs'); const body = el('div', '', 'stack'); const draftBox = el('div', '', 'stack');
  const ways = [['aut', 'AUT course code'], ['outline', 'Paste or upload the outline'], ['manual', 'Type it in']];
  let way = programme.institution === 'aut' ? 'aut' : 'outline';
  const drawTabs = () => {
    tabs.replaceChildren();
    for (const [key, label] of ways) {
      const tab = el('a', label); tab.href = '#plan'; tab.setAttribute('role', 'button');
      if (key === way) tab.setAttribute('aria-current', 'page');
      tab.onclick = event => { event.preventDefault(); way = key; drawTabs(); drawBody(); };
      tabs.append(tab);
    }
  };
  const showDraft = draft => { draftBox.replaceChildren(); draftBox.append(draftEditor(api, programme, calendars, draft)); };
  const drawBody = () => {
    body.replaceChildren();
    const note = status();
    if (way === 'aut') {
      const code = input('text', '', { maxLength: 10, placeholder: 'COMP500', required: true });
      const fetchIt = el('button', 'Fetch descriptor', 'primary');
      const row = el('div', '', 'toolbar'); row.append(field('Course code', code), fetchIt, note);
      body.append(el('p', 'AUT publishes every paper’s descriptor. The points, learning outcomes, assessments and pass rule are read from it for you to check; dates come from your course’s Canvas page.', 'muted'), row);
      fetchIt.onclick = () => guard(fetchIt, note, async () => { showDraft(await api(`/papers/aut/${encodeURIComponent(code.value.trim())}`)); note.textContent = 'Read. Check it below.'; });
    } else if (way === 'outline') {
      const text = el('textarea'); text.rows = 8; text.placeholder = 'Paste the course outline here (learning outcomes and the assessment table), or upload the file below.';
      const file = input('file'); file.accept = '.pdf,.docx,.txt,.md,.html';
      const read = el('button', 'Read outline', 'primary');
      body.append(el('p', 'University of Auckland outlines need your sign-in, so open yours, then paste its text or upload the PDF.', 'muted'),
        field('Outline text', text), field('Or upload the outline', file));
      const row = el('div', '', 'toolbar'); row.append(read, note); body.append(row);
      read.onclick = () => guard(read, note, async () => {
        const form = new FormData(); form.append('institution', programme.institution);
        if (file.files[0]) form.append('file', file.files[0]); else form.append('text', text.value);
        const draft = await api('/papers/outline', { method: 'POST', body: form });
        showDraft(draft); note.textContent = draft.notice;
      });
    } else {
      showDraft({ code: '', title: '', points: 15, level: 0, outcomes: [], assessments: [], pass_rule: '', source: 'manual', grade_scale: programme.institution === 'aut' ? 'aut9' : programme.institution === 'uoa' ? 'uoa9' : 'percent' });
    }
  };
  drawTabs(); drawBody();
  card.append(tabs, body, draftBox);
  return card;
}

function draftEditor(api, programme, calendars, draft) {
  const box = el('form', '', 'stack');
  box.append(el('h3', 'Check and save'));
  if (draft.notice) box.append(el('p', draft.notice, 'muted'));
  const code = input('text', draft.code, { maxLength: 40 }); const title = input('text', draft.title, { maxLength: 200, required: true });
  const points = input('number', draft.points ?? '', { min: 0, max: 200, step: 0.5 }); const level = input('number', draft.level || '', { min: 0, max: 10 });
  const calendar = calendars.calendars[programme.institution]?.terms || [];
  const term = select([['', 'Choose…'], ...calendar.map(t => [t.code, t.name])], '');
  const start = input('date'); const end = input('date');
  term.onchange = () => { const t = calendar.find(x => x.code === term.value); if (t) { start.value = t.start; end.value = t.end; } };
  const scale = select(SCALES, draft.grade_scale || 'percent');
  const fields = el('div', '', 'fields');
  fields.append(field('Code', code), field('Title', title), field('Points', points), field('Level', level));
  if (calendar.length) fields.append(field('Semester', term));
  fields.append(field('Starts', start), field('Ends', end), field('Grade scale', scale));
  box.append(fields);
  if (calendar.length) box.append(el('p', calendars.note, 'muted'));

  box.append(el('h4', 'Learning outcomes'));
  const outcomes = el('div', '', 'stack');
  const outcomeRow = (o = { code: '', title: '' }) => {
    const row = el('div', '', 'toolbar');
    const c = input('text', o.code, { maxLength: 40, placeholder: 'LO1' }); c.style.width = '6em'; c.setAttribute('aria-label', 'Outcome code');
    const t = input('text', o.title, { maxLength: 2000 }); t.className = 'grow'; t.setAttribute('aria-label', 'Outcome');
    const x = button('Remove', 'small'); x.onclick = () => row.remove();
    row.append(c, t, x); row.read = () => ({ code: c.value.trim(), title: t.value.trim() }); return row;
  };
  for (const o of draft.outcomes || []) outcomes.append(outcomeRow(o));
  const addOutcome = button('Add outcome', 'small'); addOutcome.onclick = () => outcomes.append(outcomeRow({ code: `LO${outcomes.children.length + 1}`, title: '' }));
  box.append(outcomes, addOutcome);

  box.append(el('h4', 'Assessments'));
  const assessments = el('div', '', 'stack');
  const assessmentRow = (a = {}) => {
    const row = el('div', '', 'fields');
    const t = input('text', a.title || '', { maxLength: 300 }); const k = select(KINDS, a.kind || 'other');
    const w = input('number', a.weight_pct ?? '', { min: 0, max: 100, step: 0.5 }); const d = input('date', a.due_date || '');
    const los = input('text', (a.outcome_codes || []).join(', '), { placeholder: 'LO1, LO2' });
    const must = input('checkbox'); must.checked = !!a.must_pass; const mustLabel = el('label', '', 'toolbar'); mustLabel.append(must, el('span', 'Must pass'));
    const x = button('Remove', 'small'); x.onclick = () => row.remove();
    row.append(field('Assessment', t), field('Kind', k), field('Weight %', w), field('Date', d), field('Outcomes', los), mustLabel, x);
    row.read = () => ({ title: t.value.trim(), kind: k.value, weight_pct: w.value === '' ? null : Number(w.value), due_date: d.value || null,
      outcome_codes: los.value.split(/[,\s]+/).filter(Boolean), must_pass: must.checked });
    return row;
  };
  for (const a of draft.assessments || []) assessments.append(assessmentRow(a));
  const addAssessment = button('Add assessment', 'small'); addAssessment.onclick = () => assessments.append(assessmentRow());
  const total = el('p', '', 'muted');
  const sum = () => { const s = [...assessments.children].reduce((n, r) => n + (r.read().weight_pct || 0), 0); total.textContent = `Weights add up to ${s}%${Math.abs(s - 100) > 0.01 ? ' (check: usually 100%)' : ''}.`; };
  box.addEventListener('input', sum); sum();
  box.append(assessments, addAssessment, total);
  const rule = el('textarea'); rule.rows = 2; rule.value = draft.pass_rule || '';
  const goal = select(GOALS, 'long_term');
  const topics = input('checkbox'); topics.checked = true; const topicsLabel = el('label', '', 'toolbar'); topicsLabel.append(topics, el('span', 'Make a topic for each learning outcome'));
  box.append(field('What you need to pass', rule), field('After its assessments', goal), topicsLabel);
  const save = el('button', 'Save paper', 'primary'); const note = status();
  const bar = el('div', '', 'toolbar'); bar.append(save, note); box.append(bar);
  box.onsubmit = event => { event.preventDefault(); guard(save, note, async () => {
    const t = calendar.find(x => x.code === term.value);
    await api('/papers', { method: 'POST', ...json({
      programme_id: programme.id, code: code.value.trim(), title: title.value.trim(), points: points.value === '' ? null : Number(points.value),
      level: Math.min(10, Math.max(0, Number(level.value) || 0)), term: t ? t.name : '', start_date: start.value || null, end_date: end.value || null,
      grade_scale: scale.value, pass_rule: rule.value.trim(), retention_goal: goal.value, outline_url: draft.outline_url || '', source: draft.source || 'manual',
      outcomes: [...outcomes.children].map(r => r.read()).filter(o => o.code && o.title),
      assessments: [...assessments.children].map(r => r.read()).filter(a => a.title), topics_from_outcomes: topics.checked }) });
    refresh();
  }); };
  return box;
}
