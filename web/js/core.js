/* Çekirdek yardımcılar: DOM, ikonlar, API köprüsü, bildirimler, pencereler */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
function add(el, kids) { for (const k of kids.flat(9)) { if (k == null || k === false || k === undefined || k === 'undefined') continue; el.append(k.nodeType ? k : document.createTextNode(k)); } }
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'html') el.innerHTML = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'value') el.value = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  add(el, kids); return el;
}
const ICONS = {
  flag: '<path d="M5 21V4m0 0h12l-2.5 4L17 12H5"/>', box: '<path d="M12 2.5l8.5 4.7v9.6L12 21.5l-8.5-4.7V7.2z"/><path d="M12 12L3.5 7.2M12 12l8.5-4.8M12 12v9.5"/>',
  sliders: '<path d="M4 7h9m4 0h3M4 12h3m4 0h9M4 17h11m4 0h1"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="17" r="2"/>',
  play: '<path d="M7 4.5l12 7.5-12 7.5z" fill="currentColor"/>', stop: '<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/>',
  term: '<rect x="3" y="4.5" width="18" height="15" rx="2.5"/><path d="M7 10l3 2.2L7 14.5M12.5 15h4.5"/>', plus: '<path d="M12 5v14M5 12h14"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2.5"/><path d="M16 8V6a2 2 0 00-2-2H6a2 2 0 00-2 2v8a2 2 0 002 2h2"/>', trash: '<path d="M4 7h16M10 11v6m4-6v6M6 7l1 12a2 2 0 002 2h6a2 2 0 002-2l1-12M9 7V4h6v3"/>',
  folder: '<path d="M3 7a2 2 0 012-2h4l2 2.5h8a2 2 0 012 2V17a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>', download: '<path d="M12 4v11m0 0l-4-4m4 4l4-4M5 19h14"/>',
  car: '<path d="M4 15l1.6-5A2 2 0 017.5 8.5h9a2 2 0 011.9 1.5L20 15v3h-2.5v-1.5h-11V18H4z"/><circle cx="7.6" cy="13.6" r="1"/><circle cx="16.4" cy="13.6" r="1"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>', alert: '<path d="M12 4l9 16H3z"/><path d="M12 10v4m0 3v.1"/>', search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>', edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/>', refresh: '<path d="M20 11a8 8 0 10-2.3 5.7M20 5v6h-6"/>',
  cloud: '<path d="M7 18a4.5 4.5 0 01-.6-8.96A6 6 0 0118 10.5a3.75 3.75 0 01-.5 7.5z"/><path d="M12 12v6m0 0l-2-2m2 2l2-2"/>', bolt: '<path d="M13 3L5 13.5h6L10 21l8-10.5h-6z"/>',
  more: '<circle cx="5" cy="12" r="1.6" fill="currentColor"/><circle cx="12" cy="12" r="1.6" fill="currentColor"/><circle cx="19" cy="12" r="1.6" fill="currentColor"/>', link: '<path d="M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1"/>',
  wand: '<path d="M4 20L15 9M14 5l1-2 1 2 2 1-2 1-1 2-1-2-2-1zM19 12l.7-1.4L21 10l-1.3-.6L19 8l-.7 1.4L17 10l1.3.6z"/>', gear: '<circle cx="12" cy="12" r="3"/><path d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M18.4 5.6l-1.8 1.8M7.4 16.6l-1.8 1.8"/>',
  share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>',
  trophy: '<path d="M6 9H4a2 2 0 01-2-2V5a2 2 0 012-2h2M18 9h2a2 2 0 002-2V5a2 2 0 00-2-2h-2M4 22h16M10 14.66V17c0 .55-.45 1-1 1H7v4h10v-4h-2c-.55 0-1-.45-1-1v-2.34M6 3h12v7a6 6 0 01-12 0V3z"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  sparkles: '<path d="M12 3l1.9 5.8a2 2 0 001.3 1.3L21 12l-5.8 1.9a2 2 0 00-1.3 1.3L12 21l-1.9-5.8a2 2 0 00-1.3-1.3L3 12l5.8-1.9a2 2 0 001.3-1.3L12 3z"/>'
};
function ico(name, cls = '') { return h('span', { class: 'ico ' + cls, html: `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ''}</svg>`, style: { display: 'inline-flex' } }); }

// Global klavye kısayolları (Ctrl+S kaydetme, Escape pencere kapatma)
window.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S')) {
    e.preventDefault();
    const saveBtn = document.querySelector('.savebar .btn.primary') || document.querySelector('button.btn.primary.pulse');
    if (saveBtn && !saveBtn.disabled) saveBtn.click();
  } else if (e.key === 'Escape') {
    const modalBack = document.querySelector('.mback');
    if (modalBack && !modal.lock) modalBack.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
  }
});

/* ---------- API köprüsü ---------- */
const ready = new Promise(res => {
  if (window.pywebview && window.pywebview.api) res();
  else window.addEventListener('pywebviewready', () => res());
});
const api = new Proxy({}, {
  get: (_, name) => async (...args) => {
    await ready;
    const r = await window.pywebview.api[name](...args);
    if (!r || !r.ok) { const e = new Error(r ? r.error : 'Uygulama ile bağlantı kurulamadı'); e.code = r && r.code; throw e; }
    return r.data;
  }
});

/* ---------- biçimlendirme ---------- */
const fmtSize = b => b == null ? '…' : b > 1073741824 ? (b / 1073741824).toFixed(1) + ' GB' : b > 1048576 ? Math.round(b / 1048576) + ' MB' : Math.max(1, Math.round(b / 1024)) + ' KB';
const fmtDur = s => { s = Math.max(0, Math.floor(s)); const hh = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), ss = s % 60; return (hh ? hh + ' sa ' : '') + (m || hh ? m + ' dk ' : '') + ss + ' sn'; };
const clock = s => { s = Math.max(0, Math.floor(s)); return [Math.floor(s / 3600), Math.floor(s % 3600 / 60), s % 60].map(n => String(n).padStart(2, '0')).join(':'); };
const km = m => (Number(m) / 1000).toFixed(2) + ' km';
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

/* ---------- bildirimler ---------- */
function toast(msg, type = 'info', ms = 4200) {
  const t = h('div', { class: 'toast simple ' + type }, ico(type === 'error' ? 'alert' : type === 'ok' ? 'check' : 'bolt'), h('span', {}, msg));
  $('#toasts').append(t);
  const kill = () => { t.classList.add('out'); setTimeout(() => t.remove(), 260); };
  setTimeout(kill, type === 'error' ? ms + 3000 : ms); t.addEventListener('click', kill); return t;
}
function toastCard(title, body, { onClose } = {}) {
  const close = () => { card.classList.add('out'); setTimeout(() => card.remove(), 260); onClose && onClose(); };
  const head = h('h4', {}, h('span', {}, title), h('span', { class: 'x', onclick: close }, ico('x')));
  const content = h('div', {}, body);
  const card = h('div', { class: 'toast' }, head, content);
  $('#toasts').append(card);
  return { el: card, content, close, title: head.firstChild };
}

/* ---------- pencere (modal) ---------- */
function modal({ title, sub, body, actions = [], onClose }) {
  const root = $('#modal-root');
  const close = () => { back.remove(); onClose && onClose(); };
  const foot = h('div', { class: 'foot' }, actions.map(a => h('button', {
    class: 'btn ' + (a.kind || ''), onclick: async (e) => { if (a.onClick) { const r = await a.onClick(e, { close }); if (r === false) return; } if (!a.keep) close(); }
  }, a.label)));
  const box = h('div', { class: 'modal' }, h('h2', {}, title), sub ? h('div', { class: 'sub' }, sub) : null, body, actions.length ? foot : null);
  const back = h('div', { class: 'mback', onmousedown: e => { if (e.target === back && !modal.lock) close(); } }, box);
  root.append(back); return { close, el: box, foot };
}
function confirmBox(title, msg, okLabel = 'Evet', kind = 'danger') {
  return new Promise(res => modal({ title, body: h('p', { class: 'muted' }, msg), onClose: () => res(false),
    actions: [{ label: 'Vazgeç' }, { label: okLabel, kind, onClick: () => { res(true); } }] }));
}

/* ---------- uzun işler (kopyalama, indirme, ...) ---------- */
async function pollJob(id, onTick) {
  for (;;) {
    const j = await api.job_status(id);
    onTick && onTick(j);
    if (j.done) { if (j.error) { const e = new Error(j.error); e.code = j.code; throw e; } return j.result; }
    await new Promise(r => setTimeout(r, 300));
  }
}
async function jobModal(title, startFn, { cancelable = false } = {}) {
  const bar = h('div', { class: 'bar ind' }, h('i')), msg = h('div', { class: 'muted', style: { marginTop: '10px' } }, 'Hazırlanıyor…'), log = h('div', { class: 'logbox', style: { display: 'none' } });
  let jobId = null, cancel = false;
  const m = modal({ title, body: h('div', {}, bar, msg, log), actions: cancelable ? [{ label: 'İptal', keep: true, onClick: async () => { cancel = true; if (jobId) await api.cancel_job(jobId); } }] : [] });
  modal.lock = true;
  try {
    jobId = await startFn();
    return await pollJob(jobId, j => {
      if (j.percent != null) { bar.classList.remove('ind'); bar.firstChild.style.width = Math.min(100, j.percent) + '%'; } else bar.classList.add('ind');
      msg.textContent = j.msg || title;
      if (j.logs.length) { log.style.display = 'block'; log.textContent = j.logs.join('\n'); log.scrollTop = 1e9; }
    });
  } finally { modal.lock = false; m.close(); }
}

/* ---------- uygulama durumu ---------- */
const S = { route: '', running: new Set(), boot: null, ip: '', cleanup: null, refresh: null, mapCache: {} };
function getMap(name, kind = 'track') { const key = name + '|' + kind; return S.mapCache[key] || (S.mapCache[key] = api.mod_map(name, kind).catch(() => null)); }
