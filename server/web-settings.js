// Settings: what to study, how to teach it, and AI usage. Library content lives in Library.
import { session } from './web-common.js';
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
  await Promise.all([appearance, studyTopics, teaching, ...(session.user?.is_admin ? [usage, advanced] : [])].map(async build => {
    const card = el('section', '', 'card stack'); root.append(card);
    try { await build(card, api); } catch (error) { card.append(el('p', error.message, 'error')); }
  }));
}

// Light, dark, or the device's own setting. Kept in this browser only; the head of web.html applies it before the first paint.
function appearance(card) {
  card.append(el('h2', 'Appearance'), el('p', 'Choose light or dark, or follow this device’s setting.', 'muted'));
  const read = () => { try { return localStorage.getItem('theme') || 'dark'; } catch { return 'dark'; } };
  const group = el('div', '', 'segmented'); group.setAttribute('role', 'group'); group.setAttribute('aria-label', 'Theme');
  const draw = () => {
    group.replaceChildren();
    for (const [value, label] of [['light', 'Light'], ['dark', 'Dark'], ['system', 'System']]) {
      const b = el('button', label); b.type = 'button'; b.setAttribute('aria-pressed', String(value === read()));
      b.onclick = () => { try { localStorage.setItem('theme', value); } catch {} applyTheme(); draw(); };
      group.append(b);
    }
  };
  draw();
  card.append(group);
}

export function applyTheme() {
  let choice = 'dark';
  try { choice = localStorage.getItem('theme') || 'dark'; } catch {}
  const theme = choice === 'system' ? (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark') : choice;
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name=theme-color]')?.setAttribute('content', theme === 'light' ? '#f5f6fa' : '#121318');
}
matchMedia('(prefers-color-scheme: light)').addEventListener?.('change', applyTheme);

async function studyTopics(card, api) {
  card.append(el('h2', 'Topics you’re learning'),
    el('p', 'Each topic you switch on gets a new lesson prepared overnight (New Zealand time). Switching one off keeps its files and history.', 'muted'));
  const note = el('p', '', 'muted'); note.setAttribute('role', 'status'); note.setAttribute('aria-live', 'polite');
  const [subjects, courses] = await Promise.all([api('/subjects'), api('/courses')]);
  const active = new Map(courses.map(course => [String(course.topic_id), course.id]));
  const groups = await Promise.all(subjects.sort((a, b) => a.level - b.level || a.name.localeCompare(b.name))
    .map(async subject => [subject, await api(`/subjects/${subject.id}/topics`)]));
  const topicsById = new Map();
  for (const [subject, topics] of groups) for (const topic of topics) topicsById.set(String(topic.id), { topic, subject });
  if (!topicsById.size) {
    const empty = el('p', '', 'empty'); empty.append('Add a subject and topic in ');
    const link = el('a', 'Library'); link.href = '#library'; empty.append(link, ' first.'); card.append(empty);
    card.append(note); return;
  }
  // Topics being learned are listed compactly; the ones not yet switched on sit in a dropdown, so many topics take little room.
  const list = el('div', '', 'switch-list'); const picker = el('div', '', 'topic-add');
  const levelSel = el('select'), subjectSel = el('select'), select = el('select');
  levelSel.setAttribute('aria-label', 'Level'); subjectSel.setAttribute('aria-label', 'Subject'); select.setAttribute('aria-label', 'Topic to learn');
  const add = el('button', 'Add topic', 'primary'); add.type = 'button';
  picker.append(levelSel, subjectSel, select, add);
  // Only topics not yet switched on are offered, narrowed level → subject → topic so a long list stays short.
  const fill = (sel, items, empty) => {
    const keep = sel.value; sel.replaceChildren();
    for (const [value, label] of items) { const o = el('option', label); o.value = String(value); sel.append(o); }
    if (!items.length) { const o = el('option', empty); o.value = ''; sel.append(o); }
    if (items.some(([value]) => String(value) === keep)) sel.value = keep;
  };
  const free = subject => groups.find(([s]) => s.id === subject.id)[1].filter(topic => !active.has(String(topic.id)));
  const fillTopics = () => {
    const subject = groups.map(([s]) => s).find(s => String(s.id) === subjectSel.value);
    fill(select, subject ? free(subject).map(t => [t.id, t.name + (t.global ? ' (global)' : '')]) : [], 'Every topic is switched on');
    select.disabled = add.disabled = !select.value;
  };
  const fillSubjects = () => {
    const here = groups.map(([s]) => s).filter(s => String(s.level) === levelSel.value && free(s).length);
    fill(subjectSel, here.map(s => [s.id, s.name]), '—'); fillTopics();
  };
  const fillLevels = () => {
    const levels = [...new Set(groups.filter(([s]) => free(s).length).map(([s]) => s.level))].sort((a, b) => a - b);
    fill(levelSel, levels.map(n => [n, `NCEA Level ${n}`]), '—'); fillSubjects();
    levelSel.disabled = subjectSel.disabled = !levels.length;
  };
  levelSel.onchange = fillSubjects; subjectSel.onchange = fillTopics;
  const say = (text, bad) => { note.textContent = text; note.className = bad ? 'error' : 'muted'; };
  const draw = () => {
    list.replaceChildren();
    const shown = [...topicsById].filter(([id]) => active.has(id));
    if (!shown.length) list.append(el('p', 'No topics yet. Add one below to get a lesson each night.', 'muted'));
    for (const [id, { topic, subject }] of shown) {
      const row = el('div', '', 'topic-row'); const name = el('span', topic.name, 'topic-name');
      const meta = el('span', `Level ${subject.level} · ${subject.name}`, 'muted topic-meta');
      const text = el('div', '', 'topic-text'); text.append(name, meta);
      const remove = el('button', 'Switch off', 'danger'); remove.type = 'button'; remove.setAttribute('aria-label', `Stop learning ${topic.name}`);
      row.append(text, ...(topic.global ? [el('span', 'Global', 'chip')] : []), remove); list.append(row);
      remove.onclick = async () => {
        remove.disabled = true; say('Saving…');
        try { await api(`/courses/${active.get(id)}`, { method: 'DELETE' }); active.delete(id); say('Saved'); draw(); }
        catch (error) { say(error.message, true); remove.disabled = false; }
      };
    }
    fillLevels();
  };
  add.onclick = async () => {
    const id = select.value; if (!id) return;
    add.disabled = select.disabled = true; say('Saving…');
    try { active.set(id, (await api('/courses', { method: 'POST', ...json({ topic_id: Number(id) }) })).id); say('Saved'); }
    catch (error) { say(error.message, true); }
    draw();
  };
  draw();
  card.append(list, picker);
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
  // Only the first three calls show; the rest sit behind a blur until "View more".
  const fold = el('div', '', 'fold'); const veil = el('div', '', 'fold-veil'); veil.setAttribute('aria-hidden', 'true');
  const more = el('button', 'View more', 'fold-more'); more.type = 'button'; more.hidden = true;
  fold.append(recent, veil);
  card.append(label, out, el('h3', 'Recent calls'), fold, more);
  let open = false;
  const fit = () => {
    const rows = [...recent.children];
    const folds = rows.length > 3;
    more.hidden = !folds; veil.hidden = !folds || open;
    more.textContent = open ? 'Show less' : 'View more'; more.setAttribute('aria-expanded', String(open));
    // A sliver of the fourth row stays under the blur so it is clear there is more.
    fold.style.maxHeight = !folds || open ? `${recent.scrollHeight}px` : `${rows[3].offsetTop - rows[0].offsetTop + 40}px`;
  };
  more.onclick = () => { open = !open; fit(); };
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
    open = false; requestAnimationFrame(fit);
  }
  days.onchange = () => load().catch(error => out.replaceChildren(el('p', error.message, 'error')));
  await load();
}

async function advanced(card) {
  card.append(el('h2', 'More tools'),
    el('p', 'Question checks, marking checks, diagram management, exam assembly and saved-lesson history are still in the original manager. Everyday study, files and settings are all on this site.', 'muted'));
  const link = el('a', 'Open advanced tools'); link.href = '/manage'; card.append(link);
}
