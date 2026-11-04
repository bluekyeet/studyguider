// Library: subjects -> topics -> files, standards, notes and search for one topic.
import { mathText, readable, session, library } from './web-common.js';
const el = (tag, text = '', className = '') => {
  const node = document.createElement(tag);
  if (text !== '') node.textContent = text;
  if (className) node.className = className;
  return node;
};
const json = body => ({ headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const FOLDERS = [
  ['all', 'All files', () => true],
  ['exams', 'Exams', r => ['exam_paper', 'exam_answers'].includes(r.category)],
  ['slides', 'Slides', r => r.category === 'slides'],
  ['extra', 'Extra', r => r.category === 'extra'],
  ['pending', 'Sorting', r => r.category === 'auto'],
];
const TABS = [['files', 'Files'], ['standards', 'Standards'], ['notes', 'Notes'], ['search', 'Search']];
// Re-render the current route in place, keeping the sidebar and scroll position.
const refresh = () => window.dispatchEvent(new HashChangeEvent('hashchange'));
const size = bytes => bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.ceil(bytes / 1024))} KB`;
const when = value => { const d = new Date(value); return isNaN(d) ? '' : d.toLocaleString('en-NZ', { dateStyle: 'medium', timeStyle: 'short' }); };

export const libraryUrl = ({ subject, topic, tab, folder } = {}) => {
  const params = new URLSearchParams();
  if (subject) params.set('subject', subject);
  if (subject && topic) params.set('topic', topic);
  if (subject && topic && tab && tab !== 'files') params.set('tab', tab);
  if (subject && topic && folder && folder !== 'all') params.set('folder', folder);
  return '#library' + (params.size ? '?' + params : '');
};

function crumbs(parts) {
  const nav = el('nav', '', 'crumbs'); nav.setAttribute('aria-label', 'Library location');
  parts.forEach((part, index) => {
    if (index) nav.append(el('span', '/'));
    if (part.href) { const a = el('a', part.label); a.href = part.href; nav.append(a); }
    else { const s = el('span', part.label); s.setAttribute('aria-current', 'page'); nav.append(s); }
  });
  return nav;
}

const chip = text => el('span', text, 'chip');
// Administrators choose between their own library and the global one; everyone else only ever works in their own.
function libraryMode() {
  if (!session.user?.is_admin) return null;
  const box = el('div', '', 'stack');
  const seg = el('div', '', 'segmented'); seg.setAttribute('role', 'group'); seg.setAttribute('aria-label', 'Which library to work in');
  for (const [global, label] of [[false, 'My library'], [true, 'Global library']]) {
    const button = el('button', label, 'small'); button.setAttribute('aria-pressed', String(library.global() === global));
    button.onclick = () => { library.set(global); location.hash = '#library'; refresh(); };
    seg.append(button);
  }
  box.append(seg);
  if (library.global()) box.append(el('p', 'You are editing the global library. Everyone can see what you change here.', 'muted'));
  return box;
}

function head(title, subtitle, trail) {
  const wrap = el('div', '', 'page-head');
  const left = el('div');
  if (trail) left.append(trail);
  left.append(el('h1', title));
  if (subtitle) left.append(el('p', subtitle));
  const mode = libraryMode(); if (mode) left.append(mode);
  wrap.append(left);
  return { wrap, actions: wrap.appendChild(el('div', '', 'toolbar')) };
}

function field(label, input) {
  const wrap = el('label', label, 'stack'); wrap.append(input); return wrap;
}

function status(root) {
  const note = el('p', '', 'muted'); note.setAttribute('role', 'status'); note.setAttribute('aria-live', 'polite');
  return note;
}

async function guard(button, note, work) {
  button.disabled = true; note.textContent = ''; note.className = 'muted';
  try { await work(); } catch (error) { note.textContent = error.message; note.className = 'error'; }
  finally { button.disabled = false; }
}

export async function renderLibrary(root, api, params) {
  const subjectId = params.get('subject') || '';
  const topicId = params.get('topic') || '';
  if (!subjectId) return subjects(root, api);
  const subjects_ = await api('/subjects');
  const subject = subjects_.find(s => String(s.id) === subjectId);
  if (!subject) { location.hash = libraryUrl(); return; }
  if (!topicId) return topics(root, api, subject);
  const list = await api(`/subjects/${subjectId}/topics`);
  const topic = list.find(t => String(t.id) === topicId);
  if (!topic) { location.hash = libraryUrl({ subject: subjectId }); return; }
  return topicView(root, api, subject, topic, params);
}

async function subjects(root, api) {
  const all = (await api('/subjects')).sort((a, b) => a.level - b.level || a.name.localeCompare(b.name));
  const { wrap } = head('Library', 'The global library, plus your own subjects, topics and study files.');
  root.append(wrap);
  if (!all.length) root.append(el('p', 'No subjects yet. Add your first one below.', 'empty'));
  for (const level of [...new Set(all.map(s => s.level))]) {
    root.append(el('h2', `NCEA Level ${level}`));
    const grid = el('div', '', 'card-grid');
    for (const subject of all.filter(s => s.level === level)) {
      const tile = el('a', '', 'tile'); tile.href = libraryUrl({ subject: subject.id });
      tile.append(el('strong', subject.name), el('p', `Level ${subject.level}`, 'muted'));
      if (subject.global) tile.append(chip('Global'));
      grid.append(tile);
    }
    root.append(grid);
  }
  const card = el('form', '', 'card stack');
  const name = el('input'); name.maxLength = 200; name.required = true;
  const level = el('select'); for (const n of [1, 2, 3]) level.add(new Option(`Level ${n}`, n, n === 2, n === 2));
  const fields = el('div', '', 'fields'); fields.append(field('Subject name', name), field('NCEA level', level));
  const submit = el('button', 'Add subject', 'primary'); const note = status();
  const bar = el('div', '', 'toolbar'); bar.append(submit, note);
  card.append(el('h2', library.global() ? 'Add a global subject' : 'Add my own subject'), fields, bar);
  card.onsubmit = async event => {
    event.preventDefault();
    await guard(submit, note, async () => {
      const created = await api('/subjects', { method: 'POST', ...json({ name: name.value, level: Number(level.value) }) });
      location.hash = libraryUrl({ subject: created.id });
    });
  };
  root.append(card);
}

async function topics(root, api, subject) {
  const list = await api(`/subjects/${subject.id}/topics`);
  const { wrap, actions } = head(subject.name, `NCEA Level ${subject.level}`, crumbs([{ label: 'Library', href: libraryUrl() }, { label: subject.name }]));
  const remove = el('button', 'Delete subject', 'danger small'); if (!subject.global) actions.append(remove);
  const note = status(); root.append(wrap);
  remove.onclick = () => guard(remove, note, async () => {
    if (!confirm(`Delete the subject "${subject.name}"? This only works when it has no topics.`)) return;
    await api(`/subjects/${subject.id}`, { method: 'DELETE' });
    location.hash = libraryUrl();
  });
  if (!list.length) root.append(el('p', 'No topics yet. Add the first topic below.', 'empty'));
  const grid = el('div', '', 'card-grid');
  for (const topic of list) {
    const tile = el('a', '', 'tile'); tile.href = libraryUrl({ subject: subject.id, topic: topic.id });
    tile.append(el('strong', topic.name), el('p', 'Files, standards and notes', 'muted'));
    if (topic.global) tile.append(chip('Global'));
    grid.append(tile);
  }
  root.append(grid);
  const card = el('form', '', 'card stack');
  const name = el('input'); name.maxLength = 200; name.required = true;
  const submit = el('button', 'Add topic', 'primary'); const addNote = status();
  const bar = el('div', '', 'toolbar'); bar.append(submit, addNote);
  card.append(el('h2', library.global() ? 'Add a global topic' : 'Add my own topic'), field('Topic name', name), bar);
  card.onsubmit = async event => {
    event.preventDefault();
    await guard(submit, addNote, async () => {
      const created = await api(`/subjects/${subject.id}/topics`, { method: 'POST', ...json({ name: name.value }) });
      location.hash = libraryUrl({ subject: subject.id, topic: created.id });
    });
  };
  root.append(card, note);
}

async function topicView(root, api, subject, topic, params) {
  const tab = TABS.some(([key]) => key === params.get('tab')) ? params.get('tab') : 'files';
  const { wrap, actions } = head(topic.name, `${subject.name} · Level ${subject.level}`, crumbs([
    { label: 'Library', href: libraryUrl() },
    { label: subject.name, href: libraryUrl({ subject: subject.id }) },
    { label: topic.name },
  ]));
  const remove = el('button', 'Delete topic', 'danger small'); const removeNote = status(); if (!topic.global) actions.append(remove);
  remove.onclick = () => guard(remove, removeNote, async () => {
    if (!confirm(`Delete the topic "${topic.name}"? This only works when it has no files, notes, lessons or review history.`)) return;
    await api(`/subjects/${subject.id}/topics/${topic.id}`, { method: 'DELETE' });
    location.hash = libraryUrl({ subject: subject.id });
  });
  const tabs = el('nav', '', 'tabs'); tabs.setAttribute('aria-label', 'Topic sections');
  for (const [key, label] of TABS) {
    const a = el('a', label); a.href = libraryUrl({ subject: subject.id, topic: topic.id, tab: key });
    if (key === tab) a.setAttribute('aria-current', 'page');
    tabs.append(a);
  }
  const body = el('div');
  // Real counts for the topic. They are waited for, so the page appears whole instead of growing a row a moment later.
  const stats = el('div', '', 'stat-row');
  try {
    const [resources, linked, saved] = await Promise.all([api(`/topics/${topic.id}/resources`), api(`/topics/${topic.id}/standards`), api(`/topics/${topic.id}/notes`)]);
    for (const [value, name] of [[resources.filter(r => r.status !== 'deleting').length, 'Files'], [linked.length, 'Standards'], [saved.length, 'Notes']]) {
      const stat = el('div', '', 'stat'); stat.append(el('b', String(value)), el('span', name)); stats.append(stat);
    }
  } catch { /* the counts are optional */ }
  root.append(wrap, removeNote, stats, tabs, body);
  const ctx = { api, subject, topic, params };
  return { files, standards, notes, search }[tab](body, ctx);
}

function files(body, { api, subject, topic, params }) {
  const folder = FOLDERS.some(([key]) => key === params.get('folder')) ? params.get('folder') : 'all';
  const selected = new Set();
  let items = [], timer = null, alive = true, filter = '';

  const upload = el('form', '', 'card stack');
  const input = el('input'); input.type = 'file'; input.multiple = true; input.setAttribute('aria-label', 'Choose files to upload');
  input.accept = '.zip,.pdf,.docx,.pptx,.xlsx,.csv,.txt,.md,.html,.png,.jpg,.jpeg,.mp3,.mp4,.m4a,.wav';
  const category = el('select');
  for (const [value, label] of [['auto', 'Detect automatically'], ['exam_paper', 'Exam paper'], ['exam_answers', 'Exam answers or schedule'], ['slides', 'Slides'], ['extra', 'Extra resource']]) category.add(new Option(label, value));
  const zone = el('div', '', 'dropzone'); zone.append(el('p', 'Drop files or a ZIP here, or choose them below. Up to 50 MiB per document; duplicates are kept once. Recordings (mp3, mp4, m4a, wav, up to 500 MiB and 2 hours) are transcribed on the server, and only the transcript is kept.'), input);
  zone.ondragover = event => { event.preventDefault(); zone.classList.add('over'); };
  zone.ondragleave = () => zone.classList.remove('over');
  zone.ondrop = event => { event.preventDefault(); zone.classList.remove('over'); if (event.dataTransfer.files.length) input.files = event.dataTransfer.files; };
  const send = el('button', 'Upload', 'primary'); const uploadNote = status();
  const bar = el('div', '', 'toolbar'); bar.append(send, uploadNote);
  const override = el('details'); override.append(el('summary', 'Choose the category myself'), field('Category', category));
  const ownOnly = topic.global && !library.global();   // files added beside a global topic are visible only to this account
  upload.append(el('h2', ownOnly ? 'Add your own files' : 'Add files'), ...(ownOnly ? [el('p', 'Only you can see files you add here. The global files are read-only.', 'muted')] : []), zone, override, bar);
  upload.onsubmit = async event => {
    event.preventDefault();
    await guard(send, uploadNote, async () => {
      if (!input.files.length) throw new Error('Choose at least one file first.');
      const data = new FormData();
      for (const file of input.files) data.append('files', file);
      data.append('category', category.value);
      const result = await api(`/topics/${topic.id}/resources/batch`, { method: 'POST', body: data });
      input.value = '';
      uploadNote.textContent = `Accepted ${result.accepted.length}, ${result.duplicates} duplicate(s), ${result.skipped.length} skipped.`;
      await load();
    });
  };

  const card = el('section', '', 'card');
  const seg = el('div', '', 'segmented'); seg.setAttribute('role', 'group'); seg.setAttribute('aria-label', 'Folder');
  const search = el('input', '', 'grow'); search.type = 'search'; search.placeholder = 'Filter by file name'; search.setAttribute('aria-label', 'Filter files by name');
  search.oninput = () => { filter = search.value.trim().toLowerCase(); draw(); };
  const tools = el('div', '', 'toolbar'); tools.append(seg, search);
  const selectAll = el('input'); selectAll.type = 'checkbox'; selectAll.setAttribute('aria-label', 'Select all shown files');
  const count = el('span', '0 selected', 'muted');
  const delSelected = el('button', 'Delete selected', 'danger small'); delSelected.disabled = true;
  const bulk = el('div', '', 'toolbar'); bulk.append(selectAll, count, delSelected);
  const list = el('ul', '', 'list'); const note = status();
  card.append(tools, bulk, list, note);
  body.append(upload, card);

  const shown = () => items.filter(FOLDERS.find(([key]) => key === folder)[2]).filter(r => r.filename.toLowerCase().includes(filter));
  FOLDERS.forEach(([key, label]) => {
    const button = el('button', label, 'small'); button.setAttribute('aria-pressed', String(key === folder));
    button.onclick = () => { location.hash = libraryUrl({ subject: subject.id, topic: topic.id, folder: key }); };
    seg.append(button);
  });

  function updateSelection() {
    count.textContent = `${selected.size} selected`; delSelected.disabled = !selected.size;
    const visible = shown().filter(r => !r.is_global); selectAll.checked = visible.length > 0 && visible.every(r => selected.has(r.id));
  }
  async function removeFiles(entries) {
    if (!confirm(`Delete ${entries.length === 1 ? entries[0].filename : entries.length + ' files'} and the extracted text? Lessons that cite a file must be deleted first.`)) return;
    const failed = [];
    for (const entry of entries) {
      try { await api(`/resources/${entry.id}`, { method: 'DELETE' }); selected.delete(entry.id); }
      catch (error) { failed.push(`${entry.filename}: ${error.message}`); }
    }
    note.textContent = failed.join('\n'); note.className = failed.length ? 'error' : 'muted';
    await load();
  }
  delSelected.onclick = () => removeFiles(items.filter(r => selected.has(r.id)));
  selectAll.onchange = () => { for (const r of shown().filter(r => !r.is_global)) selectAll.checked ? selected.add(r.id) : selected.delete(r.id); draw(); };

  function draw() {
    list.replaceChildren();
    const rows = shown();
    if (!rows.length) { const li = el('li', items.length ? 'No files match.' : 'This folder is empty. Add files above.', 'empty'); list.append(li); updateSelection(); return; }
    for (const item of rows) {
      const li = el('li');
      const box = el('input'); box.type = 'checkbox'; box.checked = selected.has(item.id); box.setAttribute('aria-label', `Select ${item.filename}`); box.disabled = Boolean(item.is_global);
      box.onchange = () => { box.checked ? selected.add(item.id) : selected.delete(item.id); updateSelection(); };
      const type = el('span', item.filename.split('.').pop().toUpperCase().slice(0, 4), 'filetype'); type.setAttribute('aria-hidden', 'true');
      const text = el('div', '', 'grow');
      const link = el('a', item.filename); link.href = `/resources/${item.id}/download`; link.target = '_blank'; link.rel = 'noopener';
      const tone = item.status === 'extracted' ? 'ok' : item.status === 'failed' ? 'bad' : 'warn';
      const meta = el('div', '', 'muted'); meta.append(el('span', item.display_status, `chip ${tone}`), ...(item.is_global ? [chip('Global')] : []), ` ${item.page_count || 0} pages · ${size(item.size)}`);
      text.append(link, meta);
      if (item.error) text.append(el('div', item.error, 'error'));
      const actions = el('div', '', 'toolbar');
      if (item.is_global) { /* read-only: an administrator manages it in the global library */ }
      else if (item.status === 'failed') { const retry = el('button', 'Retry', 'small'); retry.onclick = () => act(retry, `/resources/${item.id}/retry`); actions.append(retry); }
      else if (item.status === 'extracted') { const again = el('button', 'Re-extract', 'small quiet'); again.onclick = () => act(again, `/resources/${item.id}/extract`); actions.append(again); }
      if (!item.is_global) { const del = el('button', 'Delete', 'small danger'); del.onclick = () => removeFiles([item]); actions.append(del); }
      li.append(box, type, text, actions); list.append(li);
    }
    updateSelection();
  }
  async function act(button, path) {
    await guard(button, note, async () => { await api(path, { method: 'POST' }); await load(); });
  }
  async function load() {
    clearTimeout(timer);
    items = (await api(`/topics/${topic.id}/resources`)).filter(r => r.status !== 'deleting')
      .sort((a, b) => a.filename.localeCompare(b.filename, undefined, { numeric: true }));
    if (!alive) return;
    draw();
    // Keep status fresh while anything is still being read.
    if (items.some(r => ['pending', 'extracting'].includes(r.status))) timer = setTimeout(() => load().catch(() => {}), 4000);
  }
  return load().then(() => () => { alive = false; clearTimeout(timer); });
}

async function standards(body, { api, topic }) {
  const [linked, all] = await Promise.all([api(`/topics/${topic.id}/standards`), api('/standards')]);
  const card = el('section', '', 'card stack'); card.append(el('h2', 'Standards for this topic'));
  const note = status();
  const list = el('ul', '', 'list');
  if (!linked.length) list.append(el('li', 'No standards linked yet.', 'empty'));
  for (const standard of linked) {
    const li = el('li'); const text = el('div', '', 'grow');
    text.append(el('strong', `${standard.number} · ${standard.title}`));
    if (standard.description) { const d = el('details'); d.append(el('summary', 'Criteria and notes'), el('p', standard.description, 'muted')); text.append(d); }
    const unlink = el('button', 'Unlink', 'small'); unlink.onclick = () => guard(unlink, note, async () => {
      await api(`/topics/${topic.id}/standards/${standard.number}`, { method: 'DELETE' }); refresh();
    });
    li.append(text, unlink); list.append(li);
  }
  card.append(list);
  const unlinked = all.filter(s => !linked.some(l => l.number === s.number));
  if (unlinked.length) {
    const select = el('select'); for (const s of unlinked) select.add(new Option(`${s.number} — ${s.title}`, s.number));
    const link = el('button', 'Link to this topic', 'primary'); const bar = el('div', '', 'toolbar');
    bar.append(field('Existing standard', select), link);
    link.onclick = () => guard(link, note, async () => { await api(`/topics/${topic.id}/standards/${select.value}`, { method: 'PUT' }); refresh(); });
    card.append(bar);
  }
  card.append(note);

  const form = el('form', '', 'card stack');
  const number = el('input'); number.type = 'number'; number.min = 1; number.max = 2147483647; number.required = true;
  const title = el('input'); title.maxLength = 200; title.required = true;
  const description = el('textarea'); description.maxLength = 50000; description.rows = 4;
  const fields = el('div', '', 'fields'); fields.append(field('Standard number', number), field('Title', title));
  const save = el('button', 'Save and link', 'primary'); const saveNote = status();
  const bar = el('div', '', 'toolbar'); bar.append(save, saveNote);
  form.append(el('h2', 'Add or update a standard'), el('p', 'Saving a number that already exists updates its title and criteria for every topic that uses it.', 'muted'),
    fields, field('Criteria or notes', description), bar);
  form.onsubmit = async event => {
    event.preventDefault();
    await guard(save, saveNote, async () => {
      await api(`/standards/${Number(number.value)}`, { method: 'PUT', ...json({ title: title.value, description: description.value }) });
      await api(`/topics/${topic.id}/standards/${Number(number.value)}`, { method: 'PUT' });
      refresh();
    });
  };
  body.append(card, form);
}

async function notes(body, { api, topic }) {
  const items = await api(`/topics/${topic.id}/notes`);
  const form = el('form', '', 'card stack');
  const text = el('textarea'); text.maxLength = 50000; text.required = true; text.rows = 4;
  const save = el('button', 'Save note', 'primary'); const note = status();
  const bar = el('div', '', 'toolbar'); bar.append(save, note);
  form.append(el('h2', 'New note'), field('Note', text), bar);
  form.onsubmit = async event => {
    event.preventDefault();
    await guard(save, note, async () => { await api(`/topics/${topic.id}/notes`, { method: 'POST', ...json({ content: text.value }) }); refresh(); });
  };
  body.append(form);
  const card = el('section', '', 'card stack'); card.append(el('h2', 'Saved notes'));
  if (!items.length) card.append(el('p', 'No notes yet. Notes saved from Explain also appear here.', 'empty'));
  for (const item of items) {
    const article = el('article', '', 'stack');
    const content = mathText(readable(item.content));
    const meta = el('p', when(item.created_at), 'muted');
    const actions = el('div', '', 'toolbar'); const edit = el('button', 'Edit', 'small'); const del = el('button', 'Delete', 'small danger');
    const err = status();
    del.onclick = () => guard(del, err, async () => {
      if (!confirm('Delete this note?')) return;
      await api(`/topics/${topic.id}/notes/${item.id}`, { method: 'DELETE' }); refresh();
    });
    edit.onclick = () => {
      const area = el('textarea'); area.value = item.content; area.maxLength = 50000;
      const ok = el('button', 'Save changes', 'primary small'); const cancel = el('button', 'Cancel', 'small');
      const row = el('div', '', 'toolbar'); row.append(ok, cancel);
      content.replaceWith(area); actions.replaceWith(row);
      cancel.onclick = () => refresh();
      ok.onclick = () => guard(ok, err, async () => {
        // The server only accepts the edit if the note is unchanged; a 409 keeps this draft on screen.
        await api(`/topics/${topic.id}/notes/${item.id}`, { method: 'PUT', ...json({ content: area.value, original_content: item.content }) });
        refresh();
      });
    };
    actions.append(edit, del); article.append(content, meta, actions, err); card.append(article);
  }
  body.append(card);
}

function search(body, { api, topic, subject }) {
  const form = el('form', '', 'card stack');
  const query = el('input'); query.type = 'search'; query.maxLength = 200; query.required = true; query.placeholder = 'e.g. conservation of momentum';
  const go = el('button', 'Search', 'primary'); const note = status();
  const bar = el('div', '', 'toolbar'); bar.append(go, note);
  form.append(el('h2', 'Search this topic’s files'), el('p', 'Looks through the extracted text of every file in this topic.', 'muted'), field('Search terms', query), bar);
  const results = el('div', '', 'stack');
  form.onsubmit = async event => {
    event.preventDefault();
    await guard(go, note, async () => {
      const rows = await api(`/topics/${topic.id}/search?q=${encodeURIComponent(query.value)}`);
      results.replaceChildren();
      note.textContent = rows.length ? `${rows.length} match${rows.length === 1 ? '' : 'es'}` : 'Nothing found. Try fewer or simpler words.';
      for (const row of rows) {
        const card = el('article', '', 'card stack');
        const link = el('a', `${row.filename}${row.page ? ` · page ${row.page}` : ''}`); link.href = `/resources/${row.resource_id}/download`; link.target = '_blank'; link.rel = 'noopener';
        card.append(link);
        if (row.standard_number) card.append(el('span', `Standard ${row.standard_number}`, 'chip'));
        card.append(el('p', row.content.length > 600 ? row.content.slice(0, 600) + '…' : row.content, 'muted'));
        results.append(card);
      }
    });
  };
  body.append(form, results);
}
