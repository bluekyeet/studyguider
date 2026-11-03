import {renderHome} from './web-home.js';
import {renderLessons} from './web-lessons.js';
import {renderReviews} from './web-reviews.js';
import {renderExams} from './web-exams.js';
import {renderLibrary} from './web-library.js';
import {renderSettings} from './web-settings.js';
import {renderAccount} from './web-account.js';
import {session, avatar} from './web-common.js';

const $ = id => document.getElementById(id);
async function api(path, options={}) {
  const response = await fetch(path,{credentials:'same-origin',...options});
  if (!response.ok) {
    const data = await response.json().catch(()=>({}));
    const failure = new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${response.status})`);
    failure.status = response.status;
    throw failure;
  }
  return response.status === 204 ? null : response.json();
}
let ready = false;
let activePage = '';
let cleanup = null;
// Where each page sits, so a page entered from further down the menu arrives from below and one from above arrives from above.
// On a phone the menu runs sideways, so the same order becomes left and right. Going deeper in a page (a topic, a lesson) or to a
// later tab arrives from the right; going back arrives from the left.
const PAGES = ['home', 'lessons', 'reviews', 'exams', 'library', 'settings', 'account'];
const SUBS = ['', 'rapid', 'revision'];
const place = (page, sub, params) => ({ page: PAGES.indexOf(page), sub: Math.max(0, SUBS.indexOf(sub)), depth: ['subject', 'topic', 'lesson'].filter(key => params.get(key)).length });
let lastPlace = null;
let routeId = 0;
function arrival(now) {
  const was = lastPlace; lastPlace = now;
  if (!was) return [0, 14];
  const sign = n => n > 0 ? 1 : n < 0 ? -1 : 0;
  if (now.page !== was.page) {
    const step = sign(now.page - was.page) * 22;
    return matchMedia('(max-width:800px)').matches ? [step, 0] : [0, step];
  }
  const step = sign(now.depth - was.depth) || sign(now.sub - was.sub);
  return step ? [step * 28, 0] : [0, 14];
}
// One indicator glides between nav links instead of each link lighting up on its own.
function placePill() {
  const nav = document.querySelector('.sidebar nav');
  const current = nav?.querySelector('a[aria-current=page]');
  if (!nav || !current || !current.offsetWidth) return;
  let pill = nav.querySelector('.nav-pill');
  const first = !pill;
  if (first) {
    pill = document.createElement('span'); pill.className = 'nav-pill'; pill.setAttribute('aria-hidden', 'true');
    pill.style.transition = 'none'; nav.prepend(pill); nav.classList.add('has-pill');
  }
  pill.style.width = current.offsetWidth + 'px'; pill.style.height = current.offsetHeight + 'px';
  pill.style.transform = `translate(${current.offsetLeft}px,${current.offsetTop}px)`;
  if (first) requestAnimationFrame(() => requestAnimationFrame(() => { pill.style.transition = ''; }));
}
window.addEventListener('resize', placePill);
async function route() {
  if (!ready) return;
  const [path, query = ''] = (location.hash.slice(1) || 'home').split('?');
  const [page, sub = ''] = path.split('/');   // #exams/rapid is the Rapid questions section of Exams
  const params = new URLSearchParams(query);
  params.set('sub', sub);
  if (cleanup?.canLeave && !cleanup.canLeave()) { history.replaceState(null,'','#'+activePage); return; }
  if (($('view').querySelector('[data-dirty="true"]') || $('view').querySelector('[data-busy="true"]')) && !confirm('Leave with an unsaved answer or request in progress?')) {
    history.replaceState(null,'','#'+activePage); return;
  }
  // The same address again is a refresh in place (for example after saving): no entrance animation, scroll position kept.
  const same = (location.hash.slice(1) || page) === activePage;
  activePage = location.hash.slice(1) || page;
  if (cleanup) { cleanup(); cleanup=null; }
  $('me').classList.toggle('active', page === 'account');
  document.querySelectorAll('nav a').forEach(link => {
    if (link.hash.slice(1) === page) link.setAttribute('aria-current','page'); else link.removeAttribute('aria-current');
  });
  placePill();
  $('notice').textContent = '';
  // The page being left stays on screen, untouched, until the next one has its content; then the two swap in one step. Nothing
  // blanks or flashes while data loads, and a loading bar only appears if the wait is long.
  const mine = ++routeId;
  const container = document.createElement('section'); if (!same) container.className = 'entering'; container.hidden = true;
  for (const node of $('view').children) if (!node.hidden) node.inert = true;
  $('view').append(container); $('view').dataset.loading = '1';
  const [ex, ey] = same ? [0, 0] : arrival(place(page, sub, params));
  container.style.setProperty('--ex', ex + 'px'); container.style.setProperty('--ey', ey + 'px');
  try { const result = await ({home:renderHome,lessons:renderLessons,reviews:renderReviews,exams:renderExams,library:renderLibrary,settings:renderSettings,account:renderAccount}[page] || renderHome)(container,api,params); if (container.isConnected && typeof result === 'function') cleanup=result; else if (typeof result === 'function') result(); }
  catch(error) { if (container.isConnected) $('notice').textContent = error.message; }
  if (mine === routeId) {
    $('view').replaceChildren(container); container.hidden = false; delete $('view').dataset.loading;
    if (!same) window.scrollTo(0, 0);
  } else container.remove();
  // The entrance animation belongs to arriving on a page; later refreshes of its lists must not replay it.
  setTimeout(() => container.classList.remove('entering'), 1000);
}
$('login').onsubmit = async event => {
  event.preventDefault(); $('login-error').textContent='';
  const button = $('login').querySelector('button'); button.disabled=true;
  try {
    await api('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:$('username').value.trim(),password:$('password').value})}).then(result => session.set(result.user));
    $('password').value=''; ready=true; $('login').hidden=true; $('study').hidden=false; $('logout').hidden=false; document.body.classList.remove('signed-out'); await route();
  } catch(error) { $('login-error').textContent=error.message; }
  finally { button.disabled=false; }
};
$('logout').onclick = async () => {
  try { await api('/logout',{method:'POST'}); location.reload(); } catch(error) { $('notice').textContent=error.message; }
};
// The sidebar shows who is signed in; administrators also get the advanced tools.
session.listeners.push(user => {
  const me = $('me'); me.hidden = !user; me.replaceChildren();
  if (user) { me.append(avatar(user, 28), Object.assign(document.createElement('span'), { textContent: user.username })); me.title = 'Your account'; }
  $('advanced').hidden = !user?.is_admin;
  me.classList.toggle('active', activePage === 'account');
});
window.addEventListener('hashchange',route);
window.addEventListener('beforeunload', event => {
  if ($('view').querySelector('[data-dirty="true"], [data-busy="true"]')) { event.preventDefault(); event.returnValue=''; }
});
try { session.set((await api('/session')).user); ready=true; $('study').hidden=false; $('logout').hidden=false; document.body.classList.remove('signed-out'); await route(); }
catch { $('login').hidden=false; }
