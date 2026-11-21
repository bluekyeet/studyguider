// "Report a problem", shown only on a test system (reports.py, docs/test-system.md). It sends what the tester wrote, the page they
// were on, the browser and screen size, the last failed requests and script errors, and an optional screenshot (attached, pasted
// or captured). Testers see their own reports here; administrators see everyone's and mark them fixed.
import {el} from './web-common.js';

const recent = [];
function remember(entry) { recent.push({at: new Date().toISOString(), ...entry}); if (recent.length > 30) recent.shift(); }

// Recorded from the first moment, so a report made later still carries what went wrong before it.
const plainFetch = window.fetch.bind(window);
window.fetch = async (input, options = {}) => {
  const path = typeof input === 'string' ? input : input.url;
  const method = (options.method || 'GET').toUpperCase();
  try {
    const response = await plainFetch(input, options);
    if (!response.ok && !path.startsWith('/reports')) {
      const detail = await response.clone().text().catch(() => '');
      remember({kind: 'request', method, path, status: response.status, detail: detail.slice(0, 500)});
    }
    return response;
  } catch (error) {
    remember({kind: 'request', method, path, status: 'network error', detail: String(error)});
    throw error;
  }
};
window.addEventListener('error', event => remember({kind: 'script', message: event.message, where: `${event.filename}:${event.lineno}:${event.colno}`}));
window.addEventListener('unhandledrejection', event => remember({kind: 'promise', message: String(event.reason?.stack || event.reason)}));

const screenName = () => decodeURIComponent(location.hash.slice(1)) || 'home';
const device = () => `${navigator.userAgent} · ${innerWidth}×${innerHeight} @${devicePixelRatio}x · theme ${document.documentElement.dataset.theme}`;

async function capture() {
  // The browser asks which tab or screen to share; one frame is kept. Not offered where the browser cannot do it (phones).
  const stream = await navigator.mediaDevices.getDisplayMedia({video: true, preferCurrentTab: true});
  try {
    const video = el('video'); video.srcObject = stream; video.muted = true; await video.play();
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const canvas = el('canvas'); canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    return await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
  } finally { stream.getTracks().forEach(track => track.stop()); }
}

function form(dialog, me) {
  let picture = null;
  const where = screenName();
  const text = el('textarea'); text.rows = 6; text.required = true; text.maxLength = 5000;
  text.placeholder = 'What did you do, what happened, and what did you expect instead?';
  const label = el('label', 'What went wrong'); label.append(text);
  const preview = el('div', '', 'report-shot');
  const status = el('p', '', 'muted'); status.setAttribute('role', 'status');
  const setPicture = blob => {
    picture = blob; preview.replaceChildren();
    if (!blob) return;
    const img = el('img'); img.src = URL.createObjectURL(blob); img.alt = 'Screenshot to send';
    const remove = el('button', 'Remove screenshot', 'small quiet'); remove.type = 'button'; remove.onclick = () => setPicture(null);
    preview.append(img, remove);
  };
  const file = el('input'); file.type = 'file'; file.accept = 'image/*'; file.hidden = true;
  file.onchange = () => setPicture(file.files[0] || null);
  const attach = el('button', 'Attach screenshot', 'small'); attach.type = 'button'; attach.onclick = () => file.click();
  const tools = el('div', '', 'toolbar'); tools.append(attach, file);
  if (navigator.mediaDevices?.getDisplayMedia) {
    const grab = el('button', 'Capture screen', 'small'); grab.type = 'button';
    grab.onclick = async () => {
      dialog.close();
      try { setPicture(await capture()); } catch (error) { status.textContent = 'No screenshot taken: ' + error.message; }
      dialog.showModal();
    };
    tools.append(grab);
  }
  dialog.onpaste = event => { const item = [...event.clipboardData.items].find(i => i.type.startsWith('image/')); if (item) setPicture(item.getAsFile()); };
  const facts = el('p', `Sent with it: the page (${where}), your browser and screen size, and ${recent.length} recent error(s). Paste a screenshot with Ctrl+V.`, 'muted fine');
  const send = el('button', 'Send report', 'primary'); send.type = 'submit';
  const cancel = el('button', 'Cancel', 'quiet'); cancel.type = 'button'; cancel.onclick = () => dialog.close();
  const mine = el('button', me?.is_admin ? 'All reports' : 'My reports', 'quiet'); mine.type = 'button'; mine.onclick = () => list(dialog, me);
  const actions = el('div', '', 'toolbar'); actions.append(send, cancel, mine);
  const body = el('form'); body.append(el('h3', 'Report a problem'), label, tools, preview, facts, actions, status);
  body.onsubmit = async event => {
    event.preventDefault();
    if (!text.value.trim()) { status.textContent = 'Say what went wrong first.'; return; }
    const data = new FormData();
    data.append('description', text.value); data.append('client', 'web'); data.append('screen', where);
    data.append('app_version', 'website'); data.append('device', device());
    data.append('context', JSON.stringify({url: location.href, recent}));
    if (picture) data.append('screenshot', picture, 'screenshot.png');
    send.disabled = true; status.textContent = 'Sending…';
    try {
      const response = await plainFetch('/reports', {method: 'POST', body: data, credentials: 'same-origin'});
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : `Could not send (${response.status})`);
      body.replaceChildren(el('h3', 'Thank you'), el('p', `Report #${result.id} is saved. It will be looked at with the others.`));
      const done = el('button', 'Close', 'primary'); done.type = 'button'; done.onclick = () => dialog.close();
      body.append(done);
    } catch (error) { status.textContent = error.message; send.disabled = false; }
  };
  dialog.replaceChildren(body);
  text.focus();
}

async function list(dialog, me) {
  const back = el('button', 'New report', 'small'); back.type = 'button'; back.onclick = () => form(dialog, me);
  const close = el('button', 'Close', 'small quiet'); close.type = 'button'; close.onclick = () => dialog.close();
  const items = el('div', 'Loading…', 'report-list');
  const head = el('div', '', 'toolbar'); head.append(back, close);
  dialog.replaceChildren(el('h3', me?.is_admin ? 'All reports' : 'My reports'), head, items);
  try {
    const response = await plainFetch('/reports', {credentials: 'same-origin'});
    const reports = await response.json();
    if (!response.ok) throw new Error(reports.detail || 'Could not load reports');
    items.replaceChildren(...(reports.length ? reports.map(report => {
      const row = el('div', '', 'report-row');
      row.append(el('strong', `#${report.id} · ${report.screen || 'unknown'} · ${report.client}`),
        el('span', `${report.status}${report.note ? ' — ' + report.note : ''}`, `report-status ${report.status}`),
        el('p', report.description), el('p', `${report.username}, ${new Date(report.created_at).toLocaleString('en-NZ')}`, 'muted fine'));
      if (report.has_screenshot) { const link = el('a', 'Screenshot'); link.href = `/reports/${report.id}/screenshot`; link.target = '_blank'; row.append(link); }
      if (me?.is_admin) {
        const mark = (status, label) => {
          const button = el('button', label, 'small'); button.type = 'button';
          button.onclick = async () => {
            const note = status === 'open' ? '' : (prompt('Note (optional)', report.note) ?? report.note);
            await plainFetch(`/reports/${report.id}`, {method: 'PUT', credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({status, note})});
            list(dialog, me);
          };
          return button;
        };
        const tools = el('div', '', 'toolbar');
        tools.append(...(report.status === 'open' ? [mark('fixed', 'Fixed'), mark('wontfix', "Won't fix")] : [mark('open', 'Reopen')]));
        row.append(tools);
      }
      return row;
    }) : [el('p', 'No reports yet.', 'muted')]));
  } catch (error) { items.replaceChildren(el('p', error.message, 'error')); }
}

export async function startTestSystem(currentUser) {
  let test = false;
  try { test = (await (await plainFetch('/test-system')).json()).test_system === true; } catch { /* not reachable: no button */ }
  if (!test) return;
  document.body.classList.add('test-system');
  const banner = el('div', 'Test system: made-up data. Anything odd? Use Report a problem.', 'test-banner');
  document.body.prepend(banner);
  const dialog = el('dialog', undefined, 'report-dialog');
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  const button = el('button', 'Report a problem', 'report-button'); button.type = 'button';
  button.onclick = () => { form(dialog, currentUser()); if (!dialog.isConnected) document.body.append(dialog); dialog.showModal(); };
  document.body.append(button);
}
