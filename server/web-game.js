// Rewards: points from correct work, a gacha and shop for cosmetic collectables, a dressable character and leaderboards.
// All art is drawn by the server (/game/art/...), so this page only places images and sends choices.
import { el, json } from './web-exam-shared.js';
import { countUp } from './web-common.js';

const RARITY = ['Common', 'Uncommon', 'Rare', 'Epic', 'Legendary', 'Mythic'];
const SUBS = [['', 'Character'], ['gacha', 'Gacha'], ['shop', 'Shop'], ['boards', 'Leaderboards']];
const BOARDS = [['networth', 'Net worth'], ['questions', 'Questions'], ['lessons', 'Lessons'], ['papers', 'Papers'], ['grade', 'Est. grade'], ['gpa', 'Est. GPA'], ['collection', 'Collection']];
const num = n => Number(n).toLocaleString('en-NZ');
const plural = (n, word) => `${num(n)} ${word}${n === 1 ? '' : 's'}`;

let artVersion = '';      // from the server; part of every picture address so redrawn art is not served from the browser's cache
export const avatarUrl = (outfit = {}, skin = '', build = '', crop = '') => {
  const query = new URLSearchParams(Object.entries(outfit || {}).filter(([, id]) => id));
  if (artVersion) query.set('v', artVersion);
  if (skin) query.set('skin', skin);
  if (build) query.set('build', build);
  if (crop) query.set('crop', crop);      // 'bust' is head and shoulders, for pictures too small to show the whole character
  return `/game/art/avatar.svg?${query}`;
};
const itemUrl = (id, skin) => `/game/art/item/${encodeURIComponent(id)}.svg?v=${artVersion}${skin ? `&skin=${encodeURIComponent(skin)}` : ''}`;
function picture(src, alt = '', className = '') {
  const image = new Image(); image.src = src; image.alt = alt; image.decoding = 'async';
  if (className) image.className = className;
  return image;
}
const coin = n => { const chip = el('span', '', 'coin'); chip.append(el('i', '', 'coin-dot'), document.createTextNode(num(n))); return chip; };
const rarityChip = rarity => el('span', RARITY[rarity], `rarity r${rarity}`);
function button(text, className, onclick, title) {
  const b = el('button', text, className); b.type = 'button'; b.onclick = onclick; if (title) { b.title = title; b.setAttribute('aria-label', title); }
  return b;
}
function bar(value, max, className = '') {
  const track = el('div', '', `meter ${className}`.trim()); track.setAttribute('role', 'progressbar');
  track.setAttribute('aria-valuemin', '0'); track.setAttribute('aria-valuemax', String(max)); track.setAttribute('aria-valuenow', String(value));
  const fill = el('span'); fill.style.width = `${max ? Math.min(100, (100 * value) / max) : 0}%`; track.append(fill);
  return track;
}

// One collectable: art on a plate tinted by rarity, its name, and whatever can be done with it.
function itemCard(item, skin, { badge = '', actions = [], footer = null, worn = false } = {}) {
  const card = el('article', '', `item r${item.rarity}${worn ? ' worn' : ''}`);
  const plate = el('div', '', 'plate'); plate.append(picture(itemUrl(item.id, skin), item.name));
  if (item.count > 1) plate.append(el('span', `×${item.count}`, 'stack-count'));
  if (badge) plate.append(el('span', badge, 'badge'));
  if (worn) plate.append(el('span', 'Wearing', 'badge worn-badge'));
  const text = el('div', '', 'item-text'); text.append(el('b', item.name), rarityChip(item.rarity));
  card.append(plate, text);
  if (footer) card.append(footer);
  if (actions.length) { const row = el('div', '', 'item-buttons'); row.append(...actions.filter(Boolean)); card.append(row); }
  return card;
}

export async function renderGame(container, api, params) {
  const sub = params?.get('sub') || '';
  const root = el('section', '', 'game');
  container.replaceChildren(root);
  let me = await api('/game/me');
  artVersion = String(me.catalog.art || '');
  const alive = () => root.isConnected;

  const fail = error => {
    root.querySelector('.game-error')?.remove();
    const p = el('p', error.message, 'error game-error'); p.setAttribute('role', 'alert'); root.prepend(p);
  };
  const act = async (path, method, body) => {
    try { const result = await api(path, json(method, body)); root.querySelector('.game-error')?.remove(); return result; }
    catch (error) { if (alive()) fail(error); return null; }
  };
  const apply = state => { if (state) { me = state; draw(); } };
  // The points figure counts up once when the page opens, then only moves when the balance actually changes.
  let shownBalance = null;
  function balanceFigure() {
    const value = el('span', num(me.balance));
    const from = shownBalance;
    shownBalance = me.balance;
    if (from === null) countUp(value, me.balance, { format: n => num(Math.round(n)) });
    else if (from !== me.balance) {
      const begin = performance.now(), duration = 600;
      const frame = now => {
        const t = Math.min(1, (now - begin) / duration);
        value.textContent = num(Math.round(from + (me.balance - from) * (1 - Math.pow(1 - t, 3))));
        if (t < 1 && value.isConnected) requestAnimationFrame(frame);
      };
      if (!matchMedia('(prefers-reduced-motion: reduce)').matches) { value.textContent = num(from); requestAnimationFrame(frame); }
    }
    return value;
  }

  // --- The banner every section shares: who you are, what you have, where to go -----------------------------------------
  function banner() {
    const hero = el('header', '', 'game-hero');
    const portrait = el('div', '', 'hero-portrait'); portrait.append(picture(avatarUrl(me.outfit, me.skin, me.build), 'Your character'));
    const middle = el('div', '', 'hero-text');
    middle.append(el('p', 'Rewards', 'eyebrow'), el('h1', 'Your collection'));
    const percent = me.catalog.total ? (100 * me.catalog.owned) / me.catalog.total : 0;
    const progress = el('div', '', 'hero-progress');
    progress.append(el('span', `${num(me.catalog.owned)} of ${num(me.catalog.total)} collected · ${percent.toFixed(1)}%`), bar(me.catalog.owned, me.catalog.total));
    middle.append(progress);
    const figures = el('div', '', 'hero-figures');
    const points = el('div', '', 'figure main'); const shown = el('b'); shown.append(el('i', '', 'coin-dot'), balanceFigure());
    points.append(el('span', 'Points'), shown);
    const worth = el('div', '', 'figure'); worth.append(el('span', 'Net worth'), el('b', num(me.networth)));
    figures.append(points, worth);
    hero.append(portrait, middle, figures);
    const tabs = el('nav', '', 'segmented'); tabs.setAttribute('aria-label', 'Rewards sections');
    for (const [key, label] of SUBS) { const a = el('a', label); a.href = key ? `#rewards/${key}` : '#rewards'; if (key === sub) a.setAttribute('aria-current', 'page'); tabs.append(a); }
    const wrap = el('div', '', 'game-top'); wrap.append(hero, tabs);
    return wrap;
  }

  // --- Character: the stage, the wardrobe, the showcase and how points are earned ------------------------------------------
  let slot = 'hat';
  function character() {
    const page = el('div', '', 'game-grid');
    const stage = el('section', '', 'card stage');
    const frame = el('div', '', 'stage-frame'); frame.append(picture(avatarUrl(me.outfit, me.skin, me.build), 'Your character'));
    stage.append(frame);
    const builds = el('div', '', 'segmented small builds'); builds.setAttribute('role', 'radiogroup'); builds.setAttribute('aria-label', 'Body');
    for (const build of me.catalog.builds) {
      const on = build.id === me.build;
      const b = button(build.name, on ? 'on' : '', async () => apply(await act('/game/outfit', 'PUT', { build: build.id })));
      b.setAttribute('role', 'radio'); b.setAttribute('aria-checked', String(on)); builds.append(b);
    }
    const skins = el('div', '', 'skins'); skins.setAttribute('role', 'radiogroup'); skins.setAttribute('aria-label', 'Skin tone');
    for (const tone of me.catalog.skins) {
      const b = button('', `skin${tone.id === me.skin ? ' on' : ''}`, async () => apply(await act('/game/outfit', 'PUT', { skin: tone.id })), tone.name);
      b.style.setProperty('--tone', tone.colour); b.setAttribute('role', 'radio'); b.setAttribute('aria-checked', String(tone.id === me.skin));
      skins.append(b);
    }
    const worn = Object.keys(me.outfit).length;
    const controls = el('div', '', 'stage-controls');
    controls.append(el('span', worn ? `Wearing ${plural(worn, 'piece')}` : 'Wearing nothing yet', 'muted'));
    if (worn) controls.append(button('Undress', 'small quiet', async () => apply(await act('/game/outfit', 'PUT', { clear: true }))));
    const privacy = el('label', '', 'switch'); const box = document.createElement('input'); box.type = 'checkbox'; box.checked = me.visible;
    box.onchange = async () => apply(await act('/game/settings', 'PUT', { visible: box.checked }));
    privacy.append(box, el('span', '', 'track'), el('span', 'Show me on leaderboards'));
    stage.append(el('h3', 'Body'), builds, el('h3', 'Skin tone'), skins, controls, privacy);

    const wardrobe = el('section', '', 'card wardrobe');
    const head = el('div', '', 'section-head'); head.append(el('h2', 'Wardrobe'), el('span', `${plural(me.owned.length, 'item')} owned`, 'muted'));
    wardrobe.append(head);
    const slots = el('div', '', 'slot-strip'); slots.setAttribute('role', 'tablist');
    for (const s of me.catalog.slots) {
      const count = me.catalog.by_slot[s.id].owned;
      const b = button('', `slot${s.id === slot ? ' on' : ''}${count ? '' : ' none'}`, () => { slot = s.id; draw(); });
      b.setAttribute('role', 'tab'); b.setAttribute('aria-selected', String(s.id === slot));
      b.append(picture(itemUrl(s.icon), ''), el('span', s.name), el('small', String(count)));
      slots.append(b);
    }
    wardrobe.append(slots);
    const info = me.catalog.slots.find(s => s.id === slot);
    const list = me.owned.filter(i => i.slot === slot);
    if (!list.length) {
      const empty = el('div', '', 'empty');
      empty.append(el('p', `No ${info.name.toLowerCase()} yet.`), el('div', '', 'toolbar'));
      const go = (text, hash) => { const a = el('a', text, 'button small'); a.href = hash; return a; };
      empty.lastChild.append(go('Visit the shop', '#rewards/shop'), go('Try the gacha', '#rewards/gacha'));
      wardrobe.append(empty);
    } else {
      const grid = el('div', '', 'item-grid');
      for (const item of list) {
        const isWorn = me.outfit[slot] === item.id;
        const shown = me.showcase.includes(item.id);
        const actions = [];
        if (info.worn) actions.push(button(isWorn ? 'Take off' : 'Wear', `small${isWorn ? ' quiet' : ' primary'}`, async () => apply(await act('/game/outfit', 'PUT', { slot, item_id: isWorn ? null : item.id }))));
        actions.push(button(shown ? '★' : '☆', `small icon${shown ? ' on' : ''}`, async () => {
          const next = shown ? me.showcase.filter(i => i !== item.id) : [...me.showcase, item.id];
          apply(await act('/game/showcase', 'PUT', { items: next }));
        }, shown ? 'Remove from showcase' : 'Add to showcase'));
        if (item.count > 1) actions.push(button('♻', 'small icon', async () => { const r = await act('/game/recycle', 'POST', { item_id: item.id, count: 1 }); if (r) apply(r.state); }, `Recycle one spare copy for ${Math.round(item.value * 0.4)} points`));
        grid.append(itemCard(item, me.skin, { actions, worn: isWorn }));
      }
      wardrobe.append(grid);
    }

    const shelf = el('section', '', 'card shelf-card');
    const shelfHead = el('div', '', 'section-head'); shelfHead.append(el('h2', 'Showcase'), el('span', `${me.showcase.length} / 6 · shown on your player card`, 'muted'));
    const shelf6 = el('div', '', 'shelf');
    for (let i = 0; i < 6; i++) {
      const item = me.owned.find(o => o.id === me.showcase[i]);
      if (item) shelf6.append(itemCard(item, me.skin));
      else shelf6.append(el('div', '☆', 'shelf-empty'));
    }
    shelf.append(shelfHead, shelf6);
    if (!me.showcase.length) shelf.append(el('p', 'Tap ☆ on anything in your wardrobe to put it here.', 'muted'));

    const earn = el('section', '', 'card earn');
    const earnHead = el('div', '', 'section-head'); earnHead.append(el('h2', 'How you earn'), coin(me.earned));
    earn.append(earnHead);
    const lines = el('ul', '', 'earn-list');
    for (const line of me.breakdown) {
      const li = el('li', '', line.count ? '' : 'none');
      li.append(el('span', line.label), el('small', `${num(line.count)} × ${line.each}`), el('b', num(line.points)));
      lines.append(li);
    }
    earn.append(lines, el('p', me.notice, 'muted fine'));
    if (me.estimate) earn.append(el('p', `Estimated grade ${me.estimate.grade} · GPA ${me.estimate.gpa} / 9, from ${plural(me.estimate.topics, 'topic')} with enough review answers. Unofficial.`, 'muted fine'));

    page.append(stage, wardrobe, shelf, earn);
    return page;
  }

  // --- Gacha -----------------------------------------------------------------------------------------------------------------
  let lastPull = null;
  function gacha() {
    const page = el('div', '', 'stack');
    const machine = el('section', '', 'card machine');
    const globe = el('div', '', 'globe'); globe.setAttribute('aria-hidden', 'true');
    for (let i = 0; i < 9; i++) { const ball = el('span', '', `ball r${[0, 0, 1, 0, 2, 1, 3, 0, 4][i]}`); ball.style.setProperty('--n', i); globe.append(ball); }
    const side = el('div', '', 'machine-side');
    side.append(el('h2', 'Gacha'), el('p', 'Each pull is a random collectable from the whole catalogue. Duplicates stack; recycle spares for points.', 'muted'));
    const pulls = el('div', '', 'pull-buttons');
    for (const [count, cost] of [[1, me.costs.pull], [10, me.costs.ten]]) {
      const b = button('', `pull${count === 10 ? ' ten' : ''}`, async () => {
        b.disabled = true; globe.classList.add('spin');
        const result = await act('/game/pull', 'POST', { count });
        if (result) { lastPull = result.results; apply(result.state); } else { b.disabled = false; globe.classList.remove('spin'); }
      });
      b.append(el('b', count === 10 ? 'Pull ×10' : 'Pull ×1'), coin(cost));
      if (count === 10) b.append(el('small', 'one free pull'));
      b.disabled = me.balance < cost;
      pulls.append(b);
    }
    side.append(pulls);
    if (me.balance < me.costs.pull) side.append(el('p', `You have ${num(me.balance)} points. Correct review answers, marked exam questions, lessons and passed papers earn more.`, 'muted'));
    const pity = el('div', '', 'pity');
    const rareDone = 10 - me.pity.rare_in, epicDone = 30 - me.pity.epic_in;
    const meter = (label, done, total, cls) => { const box = el('div'); box.append(el('span', label), bar(done, total, cls)); return box; };
    pity.append(meter(`Rare or better guaranteed in ${plural(me.pity.rare_in, 'pull')}`, rareDone, 10, 'm2'), meter(`Epic or better guaranteed in ${plural(me.pity.epic_in, 'pull')}`, epicDone, 30, 'm3'));
    side.append(pity);
    const odds = el('div', '', 'odds');
    const strip = el('div', '', 'odds-strip');
    const legend = el('div', '', 'odds-legend');
    RARITY.forEach((name, i) => {
      const share = me.odds[name.toLowerCase()];
      const seg = el('span', '', `r${i}`); seg.style.flexGrow = String(Math.max(share, 1.5)); seg.title = `${name} ${share}%`; strip.append(seg);
      const key = el('span', '', 'legend'); key.append(el('i', '', `dot r${i}`), document.createTextNode(`${name} ${share}%`)); legend.append(key);
    });
    odds.append(strip, legend);
    side.append(odds);
    machine.append(globe, side);
    page.append(machine);

    if (lastPull) {
      const best = Math.max(...lastPull.map(i => i.rarity));
      const reveal = el('section', '', 'card reveal');
      const head = el('div', '', 'section-head');
      head.append(el('h2', lastPull.length === 1 ? 'You pulled' : `You pulled ${lastPull.length}`), el('span', `Best: ${RARITY[best]} · ${lastPull.filter(i => i.new).length} new`, `rarity r${best}`));
      const grid = el('div', '', 'item-grid reveal-grid');
      lastPull.forEach((item, index) => {
        const card = itemCard(item, me.skin, { badge: item.new ? 'New' : '' });
        card.style.setProperty('--i', index);
        if (item.rarity === best && best >= 3) card.classList.add('best');
        grid.append(card);
      });
      reveal.append(head, grid);
      page.append(reveal);
      lastPull = null;
    }
    return page;
  }

  // --- Shop --------------------------------------------------------------------------------------------------------------------
  const shopState = { slot: 'hat', rarity: -1 };
  function shop() {
    const page = el('section', '', 'card shop');
    const head = el('div', '', 'section-head'); head.append(el('h2', 'Item shop'), el('span', 'Common to rare at fixed prices · epic and above are gacha-only', 'muted'));
    page.append(head);
    const slots = el('div', '', 'slot-strip');
    for (const s of me.catalog.slots) {
      const b = button('', `slot${s.id === shopState.slot ? ' on' : ''}`, () => { shopState.slot = s.id; draw(); });
      b.append(picture(itemUrl(s.icon), ''), el('span', s.name)); slots.append(b);
    }
    const rarities = el('div', '', 'segmented small');
    for (const [value, label] of [[-1, 'All'], [0, 'Common'], [1, 'Uncommon'], [2, 'Rare']]) {
      const b = button(label, value === shopState.rarity ? 'on' : '', () => { shopState.rarity = value; draw(); }); b.setAttribute('aria-pressed', String(value === shopState.rarity)); rarities.append(b);
    }
    page.append(slots, rarities);
    const grid = el('div', '', 'item-grid'); const more = el('div', '', 'toolbar center');
    let offset = 0;
    const tile = item => {
      const price = el('div', '', 'price'); price.append(coin(item.price)); if (item.owned) price.append(el('span', `owned ×${item.owned}`, 'muted'));
      const buy = button(item.owned ? 'Buy another' : 'Buy', `small${item.owned ? '' : ' primary'}`, async () => {
        buy.disabled = true;
        const r = await act('/game/shop/buy', 'POST', { item_id: item.id });
        if (r) { me = r.state; item.owned += 1; card.replaceWith(tile(item)); refreshBanner(); } else buy.disabled = false;
      });
      buy.disabled = me.balance < item.price;
      const card = itemCard(item, me.skin, { footer: price, actions: [buy] });
      return card;
    };
    const load = async () => {
      const query = new URLSearchParams({ slot: shopState.slot, offset, limit: 24 }); if (shopState.rarity >= 0) query.set('rarity', shopState.rarity);
      const result = await api(`/game/shop?${query}`); if (!alive()) return;
      for (const item of result.items) grid.append(tile(item));
      offset += result.items.length; more.replaceChildren();
      if (offset < result.total) more.append(button(`Show more · ${num(result.total - offset)} left`, 'quiet', () => load().catch(fail)));
    };
    page.append(grid, more);
    load().catch(fail);
    return page;
  }

  // --- Leaderboards and player cards -----------------------------------------------------------------------------------------
  let board = 'networth';
  const dialog = el('dialog', '', 'player-dialog');
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  function boards() {
    const page = el('section', '', 'card boards');
    const head = el('div', '', 'section-head'); head.append(el('h2', 'Leaderboards'));
    const picker = el('div', '', 'segmented small wrap');
    for (const [id, label] of BOARDS) { const b = button(label, id === board ? 'on' : '', () => { board = id; draw(); }); b.setAttribute('aria-pressed', String(id === board)); picker.append(b); }
    const body = el('div', '', 'board-body'); body.append(el('p', 'Loading…', 'muted'));
    page.append(head, picker, body, dialog);
    api(`/game/leaderboard/${board}`).then(data => {
      if (!alive()) return;
      body.replaceChildren();
      if (data.note) body.append(el('p', data.note, 'muted fine'));
      if (!data.rows.length) { body.append(el('p', 'Nobody is on this board yet. Correct answers put you on it.', 'muted')); return; }
      const podium = el('div', '', 'podium');
      for (const index of [1, 0, 2]) {
        const row = data.rows[index]; if (!row) continue;
        const spot = button('', `spot place${index + 1}${row.user_id === data.you ? ' you' : ''}`, () => openPlayer(row.user_id));
        spot.append(picture(avatarUrl(row.outfit, row.skin, row.build), ''), el('span', String(row.rank), 'medal'), el('b', row.username), el('span', row.text, 'score'), el('span', '', 'plinth'));
        podium.append(spot);
      }
      body.append(podium);
      const list = el('ol', '', 'board-list');
      for (const row of data.rows.slice(3)) list.append(boardRow(row, data.you));
      if (data.mine && !data.rows.some(r => r.user_id === data.you)) list.append(boardRow(data.mine, data.you));
      if (list.children.length) body.append(list);
    }).catch(fail);
    return page;
  }
  function boardRow(row, you) {
    const li = el('li');
    const b = button('', `board-row${row.user_id === you ? ' you' : ''}`, () => openPlayer(row.user_id));
    b.append(el('span', `#${row.rank}`, 'rank'), picture(avatarUrl(row.outfit, row.skin, row.build, 'bust'), '', 'mini'), el('span', row.user_id === you ? `${row.username} (you)` : row.username, 'who'), el('b', row.text));
    li.append(b);
    return li;
  }
  async function openPlayer(id) {
    try {
      const p = await api(`/game/players/${id}`);
      dialog.replaceChildren();
      const close = button('×', 'quiet icon close', () => dialog.close(), 'Close');
      const top = el('div', '', 'player-top');
      const frame = el('div', '', 'stage-frame small'); frame.append(picture(avatarUrl(p.outfit, p.skin, p.build), p.username));
      const facts = el('div', '', 'player-facts');
      facts.append(el('p', 'Player card', 'eyebrow'), el('h2', p.you ? `${p.username} (you)` : p.username));
      const grid = el('div', '', 'fact-grid');
      for (const [value, label] of [[num(p.networth), 'Net worth'], [num(p.questions), 'Questions'], [num(p.lessons), 'Lessons'], [num(p.papers), 'Papers'],
        [p.estimate ? p.estimate.grade : '—', 'Est. grade'], [p.estimate ? `${p.estimate.gpa}` : '—', 'Est. GPA / 9']]) {
        const cell = el('div'); cell.append(el('b', value), el('span', label)); grid.append(cell);
      }
      facts.append(grid, el('span', `Collection ${num(p.collection.owned)} / ${num(p.collection.total)} · ${p.collection.percent}%`, 'muted'), bar(p.collection.owned, p.collection.total));
      if (p.rarest) { const r = el('p', '', 'rarest'); r.append(document.createTextNode('Rarest: '), el('b', p.rarest.name), document.createTextNode(' '), rarityChip(p.rarest.rarity)); facts.append(r); }
      top.append(frame, facts);
      const shelf = el('div', '', 'shelf');
      for (const item of p.showcase) shelf.append(itemCard(item, p.skin));
      dialog.append(close, top, el('h3', 'Showcase'), p.showcase.length ? shelf : el('p', 'Nothing on the shelf yet.', 'muted'));
      if (!dialog.open) dialog.showModal();
    } catch (error) { fail(error); }
  }

  let bannerNode = null;
  const refreshBanner = () => { const next = banner(); bannerNode?.replaceWith(next); bannerNode = next; };
  function draw() {
    if (!alive()) return;
    const y = window.scrollY;
    bannerNode = banner();
    const body = sub === 'gacha' ? gacha() : sub === 'shop' ? shop() : sub === 'boards' ? boards() : character();
    root.replaceChildren(bannerNode, body);
    window.scrollTo(0, y);
  }
  draw();
}
