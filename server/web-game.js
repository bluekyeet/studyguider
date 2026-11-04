// Rewards: points from correct work, a gacha and shop for cosmetic collectables, a dressable character and leaderboards.
// All art is drawn by the server (/game/art/...), so this page only places images and sends choices.
import { el, json } from './web-exam-shared.js';
import { countUp } from './web-common.js';

const RARITY = ['common', 'uncommon', 'rare', 'epic', 'legendary', 'mythic'];
const SUBS = [['', 'Character'], ['gacha', 'Gacha'], ['shop', 'Shop'], ['boards', 'Leaderboards']];
const BOARDS = [['networth', 'Net worth'], ['questions', 'Questions'], ['lessons', 'Lessons'], ['papers', 'Papers'], ['grade', 'Est. grade'], ['gpa', 'Est. GPA'], ['collection', 'Collection']];
const num = n => Number(n).toLocaleString('en-NZ');

export const avatarUrl = (outfit = {}, skin = '', version = '') => {
  const query = new URLSearchParams(Object.entries(outfit).filter(([, id]) => id));
  if (skin) query.set('skin', skin);
  if (version) query.set('v', version);
  return `/game/art/avatar.svg?${query}`;
};
const itemUrl = (id, skin) => `/game/art/item/${encodeURIComponent(id)}.svg${skin ? `?skin=${encodeURIComponent(skin)}` : ''}`;
function picture(src, alt, className = '') {
  const image = new Image(); image.src = src; image.alt = alt; image.loading = 'lazy'; image.decoding = 'async';
  if (className) image.className = className;
  return image;
}
const rarityChip = item => el('span', RARITY[item.rarity], `rarity r${item.rarity}`);
const points = n => { const chip = el('span', '', 'coins'); chip.append(el('i', '●'), document.createTextNode(` ${num(n)}`)); return chip; };

function itemTile(item, skin, ...actions) {
  const tile = el('div', '', `item-tile r${item.rarity}`);
  tile.append(picture(itemUrl(item.id, skin), item.name, 'item-art'));
  const info = el('div', '', 'item-info');
  info.append(el('b', item.name), el('span', `${item.slot_name || item.slot}`, 'muted'));
  const meta = el('div', '', 'item-meta'); meta.append(rarityChip(item));
  if (item.count > 1) meta.append(el('span', `×${item.count}`, 'count'));
  if (item.owned > 0) meta.append(el('span', `owned ×${item.owned}`, 'count'));
  info.append(meta);
  const row = el('div', '', 'item-actions'); row.append(...actions.filter(Boolean));
  tile.append(info, row);
  return tile;
}

export async function renderGame(container, api, params) {
  const sub = params?.get('sub') || '';
  const root = el('section', '', 'stack game');
  container.replaceChildren(root);
  let me = await api('/game/me');
  let alive = () => root.isConnected;

  const header = () => {
    const card = el('div', '', 'game-head');
    const left = el('div'); left.append(el('h1', 'Rewards'), el('p', 'Earn points for work recorded as correct. Spend them on collectables for your character.', 'muted'));
    const wallet = el('div', '', 'wallet');
    const balance = el('div', '', 'wallet-cell'); const figure = el('b', num(me.balance)); countUp(figure, me.balance, { format: n => num(Math.round(n)) });
    balance.append(el('span', 'Points'), figure);
    const worth = el('div', '', 'wallet-cell'); worth.append(el('span', 'Net worth'), el('b', num(me.networth)));
    const owned = el('div', '', 'wallet-cell'); owned.append(el('span', 'Collected'), el('b', `${num(me.catalog.owned)} / ${num(me.catalog.total)}`));
    wallet.append(balance, worth, owned);
    card.append(left, wallet);
    const tabs = el('nav', '', 'tabs'); tabs.setAttribute('aria-label', 'Rewards sections');
    for (const [key, label] of SUBS) { const a = el('a', label); a.href = key ? `#rewards/${key}` : '#rewards'; if (key === sub) a.setAttribute('aria-current', 'page'); tabs.append(a); }
    const wrap = el('div'); wrap.append(card, tabs);
    return wrap;
  };
  const fail = error => { root.querySelector('.game-error')?.remove(); const p = el('p', error.message, 'error game-error'); p.setAttribute('role', 'alert'); root.prepend(p); };
  const apply = state => { me = state; draw(); };
  const act = async (path, method, body) => {
    try { const result = await api(path, json(method, body)); if (alive()) { root.querySelector('.game-error')?.remove(); } return result; }
    catch (error) { if (alive()) fail(error); return null; }
  };

  // --- Character: wear what you own, pick a skin tone, choose the showcase -------------------------------------------------
  let slot = me.catalog.slots.find(s => s.worn)?.id || 'hat';
  function character() {
    const view = el('div', '', 'two-col wardrobe');
    const left = el('div', '', 'card stage');
    left.append(picture(avatarUrl(me.outfit, me.skin, me.owned.length), 'Your character', 'hero-avatar'));
    const skins = el('div', '', 'skins'); skins.setAttribute('role', 'group'); skins.setAttribute('aria-label', 'Skin tone');
    for (const tone of me.catalog.skins) {
      const b = el('button', '', `skin${tone.id === me.skin ? ' on' : ''}`); b.style.background = tone.colour; b.title = tone.name; b.setAttribute('aria-label', tone.name); b.setAttribute('aria-pressed', String(tone.id === me.skin));
      b.onclick = async () => { const s = await act('/game/outfit', 'PUT', { skin: tone.id }); if (s) apply(s); };
      skins.append(b);
    }
    const bare = el('button', 'Take everything off', 'small quiet'); bare.onclick = async () => { const s = await act('/game/outfit', 'PUT', { clear: true }); if (s) apply(s); };
    const privacy = el('label', '', 'check'); const box = document.createElement('input'); box.type = 'checkbox'; box.checked = me.visible;
    box.onchange = async () => { const s = await act('/game/settings', 'PUT', { visible: box.checked }); if (s) apply(s); };
    privacy.append(box, document.createTextNode(' Show me on leaderboards'));
    left.append(skins, el('div', '', 'toolbar center'), privacy); left.querySelector('.toolbar').append(bare);

    const right = el('div', '', 'card');
    right.append(el('h2', 'Wardrobe'));
    const chips = el('div', '', 'slot-chips');
    for (const s of me.catalog.slots) {
      const stats = me.catalog.by_slot[s.id];
      const b = el('button', `${s.name} ${stats.owned}`, `chipbtn${s.id === slot ? ' on' : ''}`); b.onclick = () => { slot = s.id; draw(); };
      chips.append(b);
    }
    right.append(chips);
    const list = me.owned.filter(i => i.slot === slot);
    const info = me.catalog.slots.find(s => s.id === slot);
    const grid = el('div', '', 'item-grid');
    for (const item of list) {
      const worn = me.outfit[slot] === item.id;
      const shown = me.showcase.includes(item.id);
      const wear = info.worn ? Object.assign(el('button', worn ? 'Take off' : 'Wear', `small${worn ? '' : ' primary'}`), { onclick: async () => { const s = await act('/game/outfit', 'PUT', { slot, item_id: worn ? null : item.id }); if (s) apply(s); } }) : null;
      const show = Object.assign(el('button', shown ? 'Unshow' : 'Showcase', 'small quiet'), { onclick: async () => {
        const next = shown ? me.showcase.filter(i => i !== item.id) : [...me.showcase, item.id];
        const s = await act('/game/showcase', 'PUT', { items: next }); if (s) apply(s);
      } });
      const spare = item.count > 1 ? Object.assign(el('button', `Recycle spare (+${Math.round(item.value * 0.4)})`, 'small quiet'), { onclick: async () => { const r = await act('/game/recycle', 'POST', { item_id: item.id, count: 1 }); if (r) apply(r.state); } }) : null;
      const tile = itemTile(item, me.skin, wear, show, spare);
      if (worn) tile.classList.add('worn');
      grid.append(tile);
    }
    right.append(list.length ? grid : el('p', `You have no ${info.name.toLowerCase()} yet. Try the shop or the gacha.`, 'muted'));
    view.append(left, right);

    const shelf = el('div', '', 'card');
    shelf.append(el('h2', 'Your showcase'), el('p', `Up to six pieces shown on your player card. ${me.showcase.length} of 6 chosen.`, 'muted'));
    const strip = el('div', '', 'item-grid showcase');
    for (const id of me.showcase) { const item = me.owned.find(i => i.id === id); if (item) strip.append(itemTile(item, me.skin)); }
    shelf.append(strip);

    const how = el('div', '', 'card');
    how.append(el('h2', 'How you earn'), el('p', me.notice, 'muted'));
    const table = el('table', '', 'table'); table.setAttribute('aria-label', 'Points earned');
    table.innerHTML = '<thead><tr><th>Work</th><th>Count</th><th>Each</th><th>Points</th></tr></thead>';
    const body = el('tbody');
    for (const line of me.breakdown) {
      const tr = el('tr'); for (const cell of [line.label, num(line.count), line.each, num(line.points)]) tr.append(el('td', String(cell)));
      body.append(tr);
    }
    const total = el('tr'); for (const cell of ['Earned in total', '', '', num(me.earned)]) total.append(el('td', cell)); total.className = 'total'; body.append(total);
    table.append(body);
    how.append(table);
    if (me.estimate) how.append(el('p', `Estimated grade ${me.estimate.grade} · GPA ${me.estimate.gpa} / 9 · from ${me.estimate.topics} topic${me.estimate.topics === 1 ? '' : 's'} with enough review answers. Unofficial.`, 'muted'));
    const stack = el('div', '', 'stack'); stack.append(view, shelf, how);
    return stack;
  }

  // --- Gacha ---------------------------------------------------------------------------------------------------------------
  let lastPull = null;
  function gacha() {
    const stack = el('div', '', 'stack');
    const card = el('div', '', 'card');
    card.append(el('h2', 'Gacha'), el('p', 'Pull a random collectable. Duplicates stack and can be recycled for points.', 'muted'));
    const buttons = el('div', '', 'toolbar');
    for (const [count, cost, label] of [[1, me.costs.pull, 'Pull ×1'], [10, me.costs.ten, 'Pull ×10']]) {
      const b = el('button', `${label} · ${num(cost)}`, 'primary'); b.disabled = me.balance < cost;
      b.onclick = async () => {
        b.disabled = true; const result = await act('/game/pull', 'POST', { count });
        if (result) { lastPull = result.results; apply(result.state); } else b.disabled = false;
      };
      buttons.append(b);
    }
    card.append(buttons);
    if (me.balance < me.costs.pull) card.append(el('p', `You have ${num(me.balance)} points. A pull is ${me.costs.pull}; correct answers, lessons and passed papers earn them.`, 'muted'));
    const pity = el('p', `Guaranteed rare or better in ${me.pity.rare_in} pull${me.pity.rare_in === 1 ? '' : 's'}, epic or better in ${me.pity.epic_in}. ${num(me.pity.pulls)} pulls so far.`, 'muted');
    const odds = el('div', '', 'odds');
    for (const [i, name] of RARITY.entries()) odds.append(Object.assign(el('span', `${name} ${me.odds[name]}%`, `rarity r${i}`)));
    card.append(pity, odds);
    stack.append(card);
    if (lastPull) {
      const results = el('div', '', 'card'); results.append(el('h2', 'You pulled'));
      const grid = el('div', '', 'item-grid pulled');
      lastPull.forEach((item, index) => {
        const tile = itemTile(item, me.skin); tile.style.setProperty('--i', index);
        if (item.new) tile.append(el('span', 'NEW', 'new-badge'));
        grid.append(tile);
      });
      results.append(grid); stack.append(results);
    }
    return stack;
  }

  // --- Shop ----------------------------------------------------------------------------------------------------------------
  const shopState = { slot: 'hat', rarity: -1 };
  function shop() {
    const stack = el('div', '', 'stack');
    const card = el('div', '', 'card');
    card.append(el('h2', 'Item shop'), el('p', 'Common to rare pieces at a fixed price. Epic and above only come from the gacha.', 'muted'));
    const chips = el('div', '', 'slot-chips');
    for (const s of me.catalog.slots) { const b = el('button', s.name, `chipbtn${s.id === shopState.slot ? ' on' : ''}`); b.onclick = () => { shopState.slot = s.id; draw(); }; chips.append(b); }
    const rarities = el('div', '', 'slot-chips');
    for (const [value, label] of [[-1, 'All'], [0, 'Common'], [1, 'Uncommon'], [2, 'Rare']]) { const b = el('button', label, `chipbtn${value === shopState.rarity ? ' on' : ''}`); b.onclick = () => { shopState.rarity = value; draw(); }; rarities.append(b); }
    card.append(chips, rarities);
    const grid = el('div', '', 'item-grid'); const more = el('div', '', 'toolbar center');
    let offset = 0;
    const load = async () => {
      const query = new URLSearchParams({ slot: shopState.slot, offset, limit: 24 }); if (shopState.rarity >= 0) query.set('rarity', shopState.rarity);
      const page = await api(`/game/shop?${query}`); if (!alive()) return;
      for (const item of page.items) {
        const buy = el('button', `Buy · ${num(item.price)}`, 'small primary'); buy.disabled = me.balance < item.price;
        buy.onclick = async () => { buy.disabled = true; const r = await act('/game/shop/buy', 'POST', { item_id: item.id }); if (r) { me = r.state; header_refresh(); item.owned += 1; tile.replaceWith(itemTile(item, me.skin, buyAgain(item))); } else buy.disabled = false; };
        const tile = itemTile(item, me.skin, buy); grid.append(tile);
      }
      offset += page.items.length; more.replaceChildren();
      if (offset < page.total) { const b = el('button', `Show more (${page.total - offset} left)`, 'quiet'); b.onclick = () => load().catch(fail); more.append(b); }
    };
    const buyAgain = item => { const b = el('button', `Buy another · ${num(item.price)}`, 'small quiet'); b.disabled = me.balance < item.price; b.onclick = async () => { const r = await act('/game/shop/buy', 'POST', { item_id: item.id }); if (r) { me = r.state; draw(); } }; return b; };
    card.append(grid, more); stack.append(card);
    load().catch(fail);
    return stack;
  }

  // --- Leaderboards and player cards ---------------------------------------------------------------------------------------
  let board = 'networth';
  function boards() {
    const stack = el('div', '', 'stack');
    const card = el('div', '', 'card');
    card.append(el('h2', 'Leaderboards'));
    const chips = el('div', '', 'slot-chips');
    for (const [id, label] of BOARDS) { const b = el('button', label, `chipbtn${id === board ? ' on' : ''}`); b.onclick = () => { board = id; draw(); }; chips.append(b); }
    card.append(chips);
    const body = el('div', '', 'board'); card.append(body);
    const profile = el('div', '', 'card player'); profile.hidden = true;
    api(`/game/leaderboard/${board}`).then(data => {
      if (!alive()) return;
      if (data.note) body.append(el('p', data.note, 'muted'));
      if (!data.rows.length) body.append(el('p', 'Nobody is on this board yet.', 'muted'));
      for (const row of data.rows) {
        const line = el('button', '', `board-row${row.user_id === data.you ? ' you' : ''}`);
        line.append(el('span', `#${row.rank}`, 'rank'), picture(avatarUrl(row.outfit, row.skin), '', 'mini-avatar'), el('span', row.user_id === data.you ? `${row.username} (you)` : row.username, 'who'), el('b', row.text));
        line.onclick = () => openPlayer(row.user_id, profile);
        body.append(line);
      }
    }).catch(fail);
    stack.append(card, profile);
    return stack;
  }
  async function openPlayer(id, target) {
    try {
      const p = await api(`/game/players/${id}`);
      target.hidden = false; target.replaceChildren();
      const top = el('div', '', 'player-top');
      top.append(picture(avatarUrl(p.outfit, p.skin), p.username, 'hero-avatar small'));
      const facts = el('div'); facts.append(el('h2', p.you ? `${p.username} (you)` : p.username));
      const stats = el('div', '', 'stat-row');
      for (const [value, label] of [[num(p.networth), 'Net worth'], [num(p.questions), 'Questions'], [num(p.lessons), 'Lessons'], [num(p.papers), 'Papers'],
        [p.estimate ? p.estimate.grade : '—', 'Est. grade'], [p.estimate ? `${p.estimate.gpa} / 9` : '—', 'Est. GPA'], [`${p.collection.owned} / ${p.collection.total}`, `Collection ${p.collection.percent}%`]]) {
        const s = el('div', '', 'stat'); s.append(el('b', value), el('span', label)); stats.append(s);
      }
      facts.append(stats);
      if (p.rarest) facts.append(el('p', `Rarest piece: ${p.rarest.name} (${p.rarest.rarity_name})`, 'muted'));
      top.append(facts); target.append(top, el('h3', 'Showcase'));
      const grid = el('div', '', 'item-grid showcase');
      for (const item of p.showcase) grid.append(itemTile(item, p.skin));
      target.append(p.showcase.length ? grid : el('p', 'Nothing on the shelf yet.', 'muted'));
      target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } catch (error) { fail(error); }
  }

  let headerNode = null, bodyNode = null;
  const header_refresh = () => { const next = header(); headerNode.replaceWith(next); headerNode = next; };
  function draw() {
    if (!alive()) return;
    const y = window.scrollY;
    headerNode = header();
    bodyNode = sub === 'gacha' ? gacha() : sub === 'shop' ? shop() : sub === 'boards' ? boards() : character();
    root.querySelectorAll('.game-error').forEach(n => n.remove());
    root.replaceChildren(headerNode, bodyNode);
    window.scrollTo(0, y);
  }
  draw();
}
