import {renderHome} from './web-home.js';
import {renderLessons} from './web-lessons.js';
import {renderReviews} from './web-reviews.js';
import {renderExams} from './web-exams.js';
import {renderLibrary} from './web-library.js';
import {renderSettings} from './web-settings.js';

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
async function route() {
  if (!ready) return;
  const [page, query = ''] = (location.hash.slice(1) || 'home').split('?');
  const params = new URLSearchParams(query);
  if (cleanup?.canLeave && !cleanup.canLeave()) { history.replaceState(null,'','#'+activePage); return; }
  if (($('view').querySelector('[data-dirty="true"]') || $('view').querySelector('[data-busy="true"]')) && !confirm('Leave with an unsaved answer or request in progress?')) {
    history.replaceState(null,'','#'+activePage); return;
  }
  activePage = location.hash.slice(1) || page;
  if (cleanup) { cleanup(); cleanup=null; }
  document.querySelectorAll('nav a').forEach(link => {
    if (link.hash.slice(1) === page) link.setAttribute('aria-current','page'); else link.removeAttribute('aria-current');
  });
  $('notice').textContent = '';
  const container = document.createElement('section'); $('view').replaceChildren(container);
  try { const result = await ({home:renderHome,lessons:renderLessons,reviews:renderReviews,exams:renderExams,library:renderLibrary,settings:renderSettings}[page] || renderHome)(container,api,params); if (container.isConnected && typeof result === 'function') cleanup=result; else if (typeof result === 'function') result(); }
  catch(error) { if (container.isConnected) $('notice').textContent = error.message; }
}
$('login').onsubmit = async event => {
  event.preventDefault(); $('login-error').textContent='';
  const button = $('login').querySelector('button'); button.disabled=true;
  try {
    await api('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:$('password').value})});
    $('password').value=''; ready=true; $('login').hidden=true; $('study').hidden=false; $('logout').hidden=false; document.body.classList.remove('signed-out'); await route();
  } catch(error) { $('login-error').textContent=error.message; }
  finally { button.disabled=false; }
};
$('logout').onclick = async () => {
  try { await api('/logout',{method:'POST'}); location.reload(); } catch(error) { $('notice').textContent=error.message; }
};
window.addEventListener('hashchange',route);
window.addEventListener('beforeunload', event => {
  if ($('view').querySelector('[data-dirty="true"], [data-busy="true"]')) { event.preventDefault(); event.returnValue=''; }
});
try { await api('/session'); ready=true; $('study').hidden=false; $('logout').hidden=false; document.body.classList.remove('signed-out'); await route(); }
catch { $('login').hidden=false; }
