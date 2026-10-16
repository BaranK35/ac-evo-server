/* Yönlendirme, gezinme, arka plan döngüsü ve sürükle-bırak */
const NAV = [['servers', 'flag', 'Sunucular'], ['mods', 'box', 'Modlar'], ['settings', 'sliders', 'Ayarlar']];
const PAGES = { servers: pageServers, server: pageServer, mods: pageMods, settings: pageSettings, setup: pageSetup };
let navToken = 0;

async function go(route, params = {}) {
  const token = ++navToken;
  if (S.cleanup) { try { S.cleanup(); } catch (e) { /* yoksay */ } S.cleanup = null; }
  S.refresh = null; S.route = route;
  const view = $('#view'); view.replaceChildren(); view.scrollTop = 0;
  $('#app').classList.toggle('nosidebar', route === 'setup');
  const active = route === 'server' ? 'servers' : route;
  $$('.navbtn').forEach(b => b.classList.toggle('active', b.dataset.r === active));
  try { await PAGES[route](view, params); } catch (e) { if (token === navToken) { view.replaceChildren(h('div', { class: 'empty' }, h('h2', {}, 'Bir sorun oluştu'), h('p', {}, e.message))); } }
}
async function bootApp() { S.boot = await api.boot(); S.ip = S.boot.ip; $('#ver').textContent = `v${S.boot.version}`; }

function buildNav() { const nav = $('#nav'); nav.replaceChildren(); NAV.forEach(([r, i, l]) => nav.append(h('div', { class: 'navbtn', 'data-r': r, onclick: () => go(r) }, ico(i), l))); }

async function backgroundTick() {
  try {
    const t = await api.tick();
    S.running = new Set(t.running);
    const el = $('#runstat'); el.classList.toggle('on', t.running.length > 0); el.lastChild.textContent = t.running.length ? `${t.running.length} sunucu çalışıyor` : 'Çalışan sunucu yok';
    for (const ev of t.events) if (ev.type === 'drop') { hideVeil(); window.__dropHandled(); showDropCard(ev.sources); }
  } catch (e) { /* kısa süreli kopukluk */ }
}

/* sürükle-bırak: görsel örtü (yolu Python tarafı alır) */
let veilTimer = null, dropGuard = null;
const veil = () => $('#dropveil');
function showVeil() { veil().classList.add('on'); clearTimeout(veilTimer); veilTimer = setTimeout(hideVeil, 150); }
function hideVeil() { veil().classList.remove('on'); }
window.addEventListener('dragenter', e => { if (e.dataTransfer && [...e.dataTransfer.types].includes('Files')) showVeil(); });
window.addEventListener('dragover', e => { e.preventDefault(); if (e.dataTransfer && [...e.dataTransfer.types].includes('Files')) showVeil(); });
window.addEventListener('drop', e => { e.preventDefault(); hideVeil(); clearTimeout(dropGuard);
  dropGuard = setTimeout(() => toast('Sürükle-bırak dosya yolunu alamadı. "Mod ekle" düğmesini kullanın.', 'info', 6000), 2500); });
window.__dropHandled = () => clearTimeout(dropGuard);

(async function init() {
  buildNav();
  try { await bootApp(); } catch (e) { $('#view').append(h('div', { class: 'empty' }, h('h2', {}, 'Başlatılamadı'), h('p', {}, e.message))); return; }
  await go(S.boot.setup_done ? 'servers' : 'setup');
  setInterval(backgroundTick, 800);
  setInterval(() => { if (S.refresh && (S.route === 'servers')) S.refresh(); }, 3000);
})();
