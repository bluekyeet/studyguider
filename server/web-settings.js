// Settings: what to study, how to teach it, and AI usage. Library content lives in Library.
const el = (tag, text = '', className = '') => {
  const node = document.createElement(tag);
  if (text !== '') node.textContent = text;
  if (className) node.className = className;
  return node;
};
const json = body => ({ headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const when = value => { const d = new Date(value); return isNaN(d) ? '' : d.toLocaleString('en-NZ', { dateStyle: 'medium', timeStyle: 'short' }); };
const number = value => Number(value || 0).toLocaleString('en-NZ');

export async function renderSettings(root, api) {
  const head = el('div', '', 'page-head'); const left = el('div');
  left.append(el('h1', 'Settings'), el('p', 'Choose what you study and how it is taught.'));
  head.append(left); root.append(head);
  // Cards are placed in order up front, then each loads on its own so one failure does not hide the others.
  await Promise.all([studyTopics, teaching, usage, advanced].map(async build => {
    const card = el('section', '', 'card stack'); root.append(card);
    try { await build(card, api); } catch (error) { card.append(el('p', error.message, 'error')); }
  }));
}

async function studyTopics(card, api) {
  card.append(el('h2', 'Topics you’re learning'),
    el('p', 'Each topic you switch on gets a new lesson prepared overnight (New Zealand time). Switching one off keeps its files and history.', 'muted'));
  const note = el('p', '', 'muted'); note.setAttribute('role', 'status'); note.setAttribute('aria-live', 'polite');
  const [subjects, courses] = await Promise.all([api('/subjects'), api('/courses')]);
  const active = new Map(courses.map(course => [String(course.topic_id), course.id]));
  const groups = await Promise.all(subjects.sort((a, b) => a.level - b.level || a.name.localeCompare(b.name))
    .map(async subject => [subject, await api(`/subjects/${subject.id}/topics`)]));
  const box = el('div', '', 'switch-list');
  for (const [subject, topics] of groups) {
    if (!topics.length) continue;
    box.append(el('h3', `Level ${subject.level} · ${subject.name}`));
    for (const topic of topics) {
      const label = el('label', '', 'check'); const check = el('input'); check.type = 'checkbox'; check.checked = active.has(String(topic.id));
      label.append(check, el('span', topic.name)); box.append(label);
      check.onchange = async () => {
        const enabled = check.checked; check.disabled = true; note.textContent = 'Saving…'; note.className = 'muted';
        try {
          if (enabled) active.set(String(topic.id), (await api('/courses', { method: 'POST', ...json({ topic_id: topic.id }) })).id);
          else { await api(`/courses/${active.get(String(topic.id))}`, { method: 'DELETE' }); active.delete(String(topic.id)); }
          note.textContent = 'Saved';
        } catch (error) { check.checked = !enabled; note.textContent = error.message; note.className = 'error'; }
        finally { check.disabled = false; }
      };
    }
  }
  if (!box.children.length) {
    const empty = el('p', '', 'empty'); empty.append('Add a subject and topic in ');
    const link = el('a', 'Library'); link.href = '#library'; empty.append(link, ' first.'); card.append(empty);
  } else card.append(box);
  card.append(note);
}

async function teaching(card, api) {
  card.append(el('h2', 'Teaching style'),
    el('p', 'One teaching method across every subject. Describe how you learn best, for example “short steps, a worked example first, then questions”. This shapes how lessons and explanations are written, not what counts as correct.', 'muted'));
  const profile = await api('/style-profile');
  const area = el('textarea'); area.rows = 6; area.maxLength = 50000; area.value = profile.content; area.setAttribute('aria-label', 'Teaching instructions');
  const save = el('button', 'Save teaching style', 'primary'); const revert = el('button', 'Revert');
  const note = el('p', '', 'muted'); note.setAttribute('role', 'status'); note.setAttribute('aria-live', 'polite');
  const bar = el('div', '', 'toolbar'); bar.append(save, revert, note);
  let saved = profile.content;
  revert.onclick = () => { area.value = saved; note.textContent = ''; };
  save.onclick = async () => {
    save.disabled = true; note.textContent = 'Saving…'; note.className = 'muted';
    try { const result = await api('/style-profile', { method: 'PUT', ...json({ content: area.value }) }); saved = result.content; note.textContent = 'Saved'; }
    catch (error) { note.textContent = error.message; note.className = 'error'; }
    finally { save.disabled = false; }
  };
  card.append(area, bar);
}

async function usage(card, api) {
  card.append(el('h2', 'AI usage'),
    el('p', 'Calls, errors and the token counts the gateway reports. This is not a bill: dollar costs are not available.', 'muted'));
  const days = el('select'); for (const n of [1, 7, 30, 90, 365]) days.add(new Option(n === 1 ? 'Last 24 hours' : `Last ${n} days`, n, n === 30, n === 30));
  const label = el('label', 'Period', 'stack'); label.append(days);
  const out = el('div', '', 'stack'); const recent = el('ul', '', 'list');
  card.append(label, out, el('h3', 'Recent calls'), recent);
  async function load() {
    const data = await api(`/usage?days=${encodeURIComponent(days.value)}`);
    out.replaceChildren();
    if (data.failure_warning) out.append(el('p', data.failure_warning, 'chip bad'));
    const stats = el('div', '', 'stat-row');
    for (const [value, name] of [[data.calls, 'Calls'], [data.errors, 'Errors'], [data.prompt_tokens, 'Prompt tokens'], [data.completion_tokens, 'Reply tokens']]) {
      const stat = el('div', '', 'stat'); stat.append(el('b', number(value)), el('span', name)); stats.append(stat);
    }
    out.append(stats);
    if (data.warning) out.append(el('p', data.warning, 'muted'));
    if (data.by_model.length) {
      const list = el('ul', '', 'list');
      for (const row of data.by_model) { const li = el('li'); li.append(el('span', row.model, 'grow'), el('span', `${number(row.calls)} calls · ${number(row.errors)} errors`, 'muted')); list.append(li); }
      out.append(list);
    }
    recent.replaceChildren();
    const rows = await api('/usage/recent?limit=20');
    if (!rows.length) recent.append(el('li', 'No calls recorded yet.', 'empty'));
    for (const row of rows) {
      const li = el('li'); const text = el('div', '', 'grow');
      text.append(el('strong', row.task), el('div', `${row.model} · ${when(row.created_at)}${row.error ? ` · ${row.error}` : ''}`, 'muted'));
      li.append(text, el('span', row.outcome, `chip ${row.outcome === 'error' ? 'bad' : 'ok'}`)); recent.append(li);
    }
  }
  days.onchange = () => load().catch(error => out.replaceChildren(el('p', error.message, 'error')));
  await load();
}

async function advanced(card) {
  card.append(el('h2', 'More tools'),
    el('p', 'Question checks, marking checks, diagram management, exam assembly and saved-lesson history are still in the original manager. Everyday study, files and settings are all on this site.', 'muted'));
  const link = el('a', 'Open advanced tools'); link.href = '/manage'; card.append(link);
}
