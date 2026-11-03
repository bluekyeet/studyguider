// Your account: profile picture, username and password, and (for administrators) adding, editing and removing accounts.
import { session, avatar } from './web-common.js';
import { el, json } from './web-exam-shared.js';

const note = () => { const p = el('p', '', 'muted'); p.setAttribute('role', 'status'); p.setAttribute('aria-live', 'polite'); return p; };
const say = (p, text, bad = false) => { p.textContent = text; p.className = bad ? 'error' : 'muted'; };
const field = (label, type, attrs = {}) => {
  const wrap = el('label', label, 'stack'); const input = el('input'); input.type = type;
  Object.assign(input, attrs); wrap.append(input); return [wrap, input];
};

export async function renderAccount(container, api) {
  const root = el('section', '', 'stack'); container.replaceChildren(root);
  const alive = () => root.isConnected;
  const head = el('div', '', 'page-head'); const left = el('div');
  left.append(el('h1', 'Account'), el('p', 'Your picture, username and password. Everything you study here is private to your account.', 'muted'));
  head.append(left); root.append(head);

  // ---- profile ---------------------------------------------------------------------------------
  const profile = el('section', '', 'card stack'); root.append(profile);
  const drawProfile = () => {
    const user = session.user;
    const row = el('div', '', 'profile-row');
    const picture = avatar(user, 96);
    const side = el('div', '', 'stack');
    side.append(el('h2', user.username), el('span', user.is_admin ? 'Administrator' : 'User', 'chip'));
    const file = el('input'); file.type = 'file'; file.accept = 'image/jpeg,image/png,image/webp,image/gif'; file.hidden = true;
    const choose = el('button', user.has_avatar ? 'Change picture' : 'Add a picture', 'small'); choose.type = 'button';
    const remove = el('button', 'Remove picture', 'small quiet'); remove.type = 'button'; remove.hidden = !user.has_avatar;
    const status = note();
    const bar = el('div', '', 'toolbar'); bar.append(choose, remove, file);
    choose.onclick = () => file.click();
    file.onchange = async () => {
      if (!file.files[0]) return;
      const form = new FormData(); form.append('file', file.files[0]);
      say(status, 'Uploading…'); choose.disabled = true;
      try { session.set(await api('/me/avatar', { method: 'POST', body: form })); drawProfile(); }
      catch (error) { say(status, error.message, true); choose.disabled = false; }
    };
    remove.onclick = async () => {
      try { session.set(await api('/me/avatar', { method: 'DELETE' })); drawProfile(); } catch (error) { say(status, error.message, true); }
    };
    side.append(bar, status); row.append(picture, side);
    profile.replaceChildren(row);
  };
  drawProfile();

  // ---- username --------------------------------------------------------------------------------
  const rename = el('form', '', 'card stack'); root.append(rename);
  const [nameLabel, nameInput] = field('New username', 'text', { autocomplete: 'username', maxLength: 32, required: true });
  const [nameCurrentLabel, nameCurrent] = field('Current password (to confirm)', 'password', { autocomplete: 'current-password', required: true });
  const nameStatus = note(); const nameButton = el('button', 'Change username', 'primary');
  rename.append(el('h2', 'Username'), el('p', 'Letters, numbers, dots, dashes and underscores; 3 to 32 characters.', 'muted'), nameLabel, nameCurrentLabel, nameButton, nameStatus);
  rename.onsubmit = async event => {
    event.preventDefault(); nameButton.disabled = true;
    try {
      const user = await api('/me/username', json('PUT', { username: nameInput.value, current_password: nameCurrent.value }));
      session.set({ ...session.user, username: user.username }); nameInput.value = nameCurrent.value = ''; say(nameStatus, 'Username changed'); drawProfile();
    } catch (error) { say(nameStatus, error.message, true); } finally { nameButton.disabled = false; }
  };

  // ---- password --------------------------------------------------------------------------------
  const change = el('form', '', 'card stack'); root.append(change);
  const [curLabel, current] = field('Current password', 'password', { autocomplete: 'current-password', required: true });
  const [newLabel, next] = field('New password', 'password', { autocomplete: 'new-password', minLength: 12, required: true });
  const [againLabel, again] = field('Repeat the new password', 'password', { autocomplete: 'new-password', minLength: 12, required: true });
  const passStatus = note(); const passButton = el('button', 'Change password', 'primary');
  change.append(el('h2', 'Password'), el('p', 'At least 12 characters. Changing it signs you out on your other devices.', 'muted'), curLabel, newLabel, againLabel, passButton, passStatus);
  change.onsubmit = async event => {
    event.preventDefault();
    if (next.value !== again.value) return say(passStatus, 'The new passwords do not match', true);
    passButton.disabled = true;
    try { await api('/me/password', json('PUT', { current_password: current.value, new_password: next.value })); current.value = next.value = again.value = ''; say(passStatus, 'Password changed'); }
    catch (error) { say(passStatus, error.message, true); } finally { passButton.disabled = false; }
  };

  if (session.user.is_admin) await adminUsers(root, api, alive);
}

// ---- administrators: all accounts -----------------------------------------------------------------
async function adminUsers(root, api, alive) {
  const card = el('section', '', 'card stack'); root.append(card);
  card.append(el('h2', 'Accounts'), el('p', 'Only administrators can add or remove accounts. Each account has its own subjects, files, lessons and teaching style; nobody else can see them, including you here.', 'muted'));
  const status = note();
  const list = el('div', '', 'stack');
  const add = el('form', '', 'stack');
  const [nLabel, nInput] = field('Username', 'text', { maxLength: 32, required: true, autocomplete: 'off' });
  const [pLabel, pInput] = field('Starting password (at least 12 characters)', 'password', { minLength: 12, required: true, autocomplete: 'new-password' });
  const adminLabel = el('label', '', 'check'); const adminBox = el('input'); adminBox.type = 'checkbox'; adminLabel.append(adminBox, el('span', 'Administrator'));
  const addButton = el('button', 'Add account', 'primary');
  add.append(el('h3', 'Add an account'), nLabel, pLabel, adminLabel, addButton);
  card.append(list, add, status);

  async function load() {
    const users = await api('/users');
    if (!alive()) return;
    list.replaceChildren();
    const table = el('table', '', 'table'); const head = el('tr');
    for (const h of ['Account', 'Role', '']) head.append(el('th', h));
    const thead = el('thead'); thead.append(head); const body = el('tbody'); table.append(thead, body);
    for (const user of users) body.append(row(user));
    list.append(table);
  }

  function row(user) {
    const tr = el('tr'); const who = el('td'); const holder = el('span', '', 'who');
    holder.append(avatar(user, 32, `/users/${user.id}/avatar`), el('strong', user.username)); if (user.id === session.user.id) holder.append(el('span', 'you', 'chip'));
    who.append(holder);
    const role = el('td', user.is_admin ? 'Administrator' : 'User');
    const actions = el('td'); const editor = el('div', '', 'stack'); editor.hidden = true;
    if (user.id !== session.user.id) {
      const edit = el('button', 'Edit', 'small'); edit.type = 'button';
      const remove = el('button', 'Remove', 'small quiet'); remove.type = 'button';
      const bar = el('div', '', 'toolbar'); bar.append(edit, remove); actions.append(bar, editor);
      edit.onclick = () => { editor.hidden = !editor.hidden; if (!editor.hidden) buildEditor(editor, user); };
      remove.onclick = () => { editor.hidden = false; buildRemove(editor, user); };
    } else actions.append(el('span', 'Use the sections above for your own account', 'muted'));
    tr.append(who, role, actions);
    return tr;
  }

  function buildEditor(box, user) {
    const [a, name] = field('Username', 'text', { value: user.username, maxLength: 32 });
    const [b, pass] = field('New password (leave empty to keep)', 'password', { minLength: 12, autocomplete: 'new-password' });
    const roleLabel = el('label', '', 'check'); const roleBox = el('input'); roleBox.type = 'checkbox'; roleBox.checked = user.is_admin; roleLabel.append(roleBox, el('span', 'Administrator'));
    const save = el('button', 'Save changes', 'primary small'); save.type = 'button';
    const msg = note();
    save.onclick = async () => {
      const body = {};
      if (name.value !== user.username) body.username = name.value;
      if (pass.value) body.password = pass.value;
      if (roleBox.checked !== user.is_admin) body.is_admin = roleBox.checked;
      if (!Object.keys(body).length) return say(msg, 'Nothing changed');
      save.disabled = true;
      try { await api(`/users/${user.id}`, json('PUT', body)); say(status, `Saved ${name.value}`); await load(); }
      catch (error) { say(msg, error.message, true); save.disabled = false; }
    };
    box.replaceChildren(a, b, roleLabel, save, msg);
  }

  function buildRemove(box, user) {
    const [label, confirm] = field(`Type “${user.username}” to remove the account and everything it owns`, 'text', { autocomplete: 'off' });
    const go = el('button', 'Remove account and all its data', 'small danger'); go.type = 'button'; go.disabled = true;
    const msg = note();
    confirm.oninput = () => { go.disabled = confirm.value.trim().toLowerCase() !== user.username.toLowerCase(); };
    go.onclick = async () => {
      go.disabled = true;
      try { await api(`/users/${user.id}?confirm=${encodeURIComponent(confirm.value.trim())}`, { method: 'DELETE' }); say(status, `Removed ${user.username}`); await load(); }
      catch (error) { say(msg, error.message, true); go.disabled = false; }
    };
    box.replaceChildren(el('p', 'This permanently deletes their subjects, files, lessons, reviews, exams and teaching style. It cannot be undone.', 'error'), label, go, msg);
  }

  add.onsubmit = async event => {
    event.preventDefault(); addButton.disabled = true;
    try {
      await api('/users', json('POST', { username: nInput.value, password: pInput.value, is_admin: adminBox.checked }));
      say(status, `Added ${nInput.value}. Give them their username and starting password; they can change both.`); nInput.value = pInput.value = ''; adminBox.checked = false; await load();
    } catch (error) { say(status, error.message, true); } finally { addButton.disabled = false; }
  };
  await load();
}
