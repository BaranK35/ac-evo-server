/* Mod yöneticisi: pist ve araç modları, sürükle-bırak algılama */
const KIND_LABEL = { track: 'Pist', car: 'Araç' };

function field(label, ctl, hint) { return h('div', { class: 'field' }, h('label', {}, label), ctl, hint ? h('div', { class: 'hint' }, hint) : null); }
function textIn(v, o = {}) { const i = h('input', { class: 'in ' + (o.num ? 'num' : ''), type: o.num ? 'number' : 'text', spellcheck: 'false', list: o.list }); i.value = v ?? ''; return i; }

function editModModal(item, onSaved) {
  const e = item.entry, isTrack = item.kind === 'track';
  const f = isTrack
    ? { track: textIn(e.track), layout: textIn(e.layout, { list: 'layouts' }), event_name: textIn(e.event_name), track_length: textIn(e.track_length, { num: true }), max_pit_slot: textIn(e.max_pit_slot, { num: true }) }
    : { display_name: textIn(e.display_name), performance_indicator: textIn(e.performance_indicator, { num: true }), property_1: textIn(e.property_1, { num: true }), property_2: textIn(e.property_2, { num: true }), property_3: textIn(e.property_3, { num: true }) };
  const body = h('div', {}, h('datalist', { id: 'layouts' }, (item.layouts || []).map(l => h('option', { value: l }))),
    isTrack ? [field('Pist adı', f.track, 'Sunucunun pisti bulduğu ad. Emin değilseniz önce varsayılanla deneyin ya da "Pist testi" kullanın.'),
      field('Layout', f.layout, item.layouts.length ? 'Bulunan: ' + item.layouts.join(', ') : 'Layout bulunamadı'), field('Etkinlik adı', f.event_name),
      field('Pist uzunluğu (m)', f.track_length, 'Yaklaşık değer yeterlidir'), field('Pit kutusu sayısı', f.max_pit_slot)]
      : [field('Görünen ad', f.display_name), field('PI (performans)', f.performance_indicator), field('Özellik 1', f.property_1), field('Özellik 2', f.property_2), field('Özellik 3', f.property_3)],
    item.track_text ? h('div', { class: 'note', style: { marginTop: '12px' } }, '.track dosyası içeriği: ', h('code', {}, item.track_text.slice(0, 160))) : null);
  modal({ title: `${item.name}`, sub: `${KIND_LABEL[item.kind]} bilgileri: sunucu bu bilgilerle yükler`, body, actions: [{ label: 'Vazgeç' }, { label: 'Kaydet', kind: 'primary', onClick: async () => {
    const entry = {}; for (const [k, el] of Object.entries(f)) entry[k] = el.type === 'number' ? Number(el.value) : el.value.trim();
    try { await api.save_mod_entry(item.kind, item.name, entry); toast('Kaydedildi', 'ok'); onSaved && onSaved(); } catch (err) { toast(err.message, 'error'); return false; } } }] });
}

async function resolveTrackModal(item) {
  let servers = []; try { servers = await api.list_servers(); } catch (e) { return toast(e.message, 'error'); }
  if (!servers.length) return toast('Pist ayarı için önce bir sunucu oluşturun.', 'error');
  const sel = h('select', { class: 'sel' }, servers.map(s => h('option', { value: s.id }, s.name))); 
  try {
    const found = await jobModal('Pist yapılandırılıyor', () => api.probe_track(sel.value, item.name));
    if (found) {
      toast(`Pist ayarları sunucuya tanımlandı: ${found.track} / ${found.layout}`, 'ok', 5000);
      S.refresh && S.refresh();
    }
  } catch (err) {
    toast('Pist ayarı hatası: ' + err.message, 'error');
  }
}

async function installPaths(paths, { quiet } = {}) {
  try {
    const done = await jobModal('Mod kuruluyor', () => api.install_mods(paths));
    toast(`${done.length} mod kuruldu: ${done.map(d => d.name).join(', ')}`, 'ok', 6000);
    S.refresh && S.refresh(); return done;
  } catch (e) { toast(e.message, 'error'); return []; }
}

async function pageMods(view, { tab = 'track' } = {}) {
  const page = h('div', { class: 'page' }); view.append(page);
  const grid = h('div', { class: 'grid' }, [1, 2, 3].map(() => h('div', { class: 'sk' }))), sub = h('p', {}, '');
  let data = null, kind = tab;
  const segEl = h('div', { class: 'seg' }, [['track', 'Pistler'], ['car', 'Araçlar']].map(([k, l]) => h('button', { class: kind === k ? 'on' : '', onclick: e => { kind = k; $$('button', segEl).forEach(b => b.classList.toggle('on', b === e.target)); paint(); } }, l)));
  page.append(h('div', { class: 'pagehead' }, h('div', {}, h('h1', {}, 'Modlar'), sub), h('div', { class: 'row' },
    h('button', { class: 'btn', onclick: async () => { const r = await api.pick_folder('Açılmış mod klasörünü seçin'); if (r) installPaths([r]); } }, ico('folder'), 'Klasörden ekle'),
    h('button', { class: 'btn primary', onclick: async () => { const r = await api.pick_files(); if (r.length) installPaths(r); } }, ico('plus'), 'Mod ekle (.kspkg / .zip)'))),
    h('div', { class: 'dropzone' }, h('div', { class: 'dz' }, '📦'), h('div', {}, h('h3', {}, 'Modu pencereye sürükleyip bırakın'), h('p', {}, 'Pist ve araç modları (.kspkg, .zip, .7z ya da klasör) otomatik algılanır; hem oyunun hem sunucunun mod klasörüne kurulur.'))),
    h('div', { class: 'cbar' }, segEl, h('span', { class: 'grow' }), h('button', { class: 'btn sm', onclick: async () => { try { const c = await jobModal('Modlar eşitleniyor', () => api.sync_mods()); toast(c.length ? 'Sunucuya eşitlendi: ' + c.join(', ') : 'Her şey zaten eşit', 'ok'); load(); } catch (e) { toast(e.message, 'error'); } } }, ico('refresh'), 'Sunucuya eşitle'),
      h('button', { class: 'btn sm', onclick: () => api.open_mods_dir('game') }, ico('folder'), 'Oyun mod klasörü'), h('button', { class: 'btn sm', onclick: () => api.open_mods_dir('server') }, ico('folder'), 'Sunucu mod klasörü')), grid);

  function card(it) {
    const mb = h('div', { class: 'mapbox ' + (it.kind === 'car' ? 'car' : '') });
    getMap(it.name, it.kind).then(u => { if (u) { mb.replaceChildren(h('img', { src: u })); } else { mb.textContent = it.kind === 'car' ? '🏎️' : '🏁'; } });
    const e = it.entry;
    const info = it.kind === 'track' ? `${e.layout} · ${km(e.track_length)}` : `${e.display_name} · PI ${Number(e.performance_indicator).toFixed(1)}`;
    const pkgBadge = it.is_kspkg ? h('span', { class: 'chip', style: { color: 'var(--accent, #38bdf8)' } }, '📦 .kspkg') : null;
    return h('div', { class: 'card fadein scard' }, mb, h('h3', {}, it.name), h('div', { class: 'sub' }, info),
      h('div', { class: 'chips' }, h('span', { class: 'pill ' + (it.in_game ? 'ok' : 'bad') }, it.in_game ? 'Oyunda ✓' : 'Oyunda yok'), h('span', { class: 'pill ' + (it.in_server ? 'ok' : 'warn') }, it.in_server ? 'Sunucuda ✓' : 'Sunucuda yok'), pkgBadge, h('span', { class: 'chip' }, fmtSize(it.size))),
      h('div', { class: 'acts' }, h('button', { class: 'btn sm', onclick: () => editModModal(it, load) }, ico('edit'), 'Düzenle'),
        it.kind === 'track' ? h('button', { class: 'btn sm', title: 'Pist layoutlarını sunucu listesine aktarır', onclick: () => resolveTrackModal(it) }, ico('wand'), 'Sunucuya Aktar') : null,
        h('button', { class: 'btn sm icon danger', title: 'Kaldır', onclick: async () => { if (await confirmBox('Modu kaldır', `'${it.name}' hem oyundan hem sunucu klasöründen silinsin mi?`, 'Kaldır')) { await api.remove_mod(it.kind, it.name); load(); } } }, ico('trash'))));
  }
  function paint() {
    if (!data) return; const list = data[kind === 'track' ? 'tracks' : 'cars']; grid.replaceChildren();
    sub.textContent = `${data.tracks.length} pist · ${data.cars.length} araç modu kurulu`;
    if (!list.length) { grid.append(h('div', { class: 'empty', style: { gridColumn: '1/-1' } }, h('div', { class: 'big' }, kind === 'track' ? '🏁' : '🏎️'), h('h2', {}, `Kurulu ${KIND_LABEL[kind].toLowerCase()} modu yok`), h('p', {}, 'Bir mod arşivini bu pencereye sürükleyin ya da "Mod ekle"ye basın.'))); return; }
    list.forEach(it => grid.append(card(it)));
  }
  async function load() { try { data = await api.list_mods(); paint(); } catch (e) { toast(e.message, 'error'); } }
  S.refresh = load; await load();
  setTimeout(load, 2500);   // arka plan boyut hesabı bitince yenile
}

/* ============ Sürükle-bırak: algılama kartı (sağ alt) ============ */
function showDropCard(sources) {
  const valid = sources.filter(s => !s.error && s.items.length);
  const content = h('div', {});
  const t = toastCard(valid.length ? 'Mod algılandı' : 'Mod bulunamadı', content);
  const list = h('div', {});
  sources.forEach(s => {
    if (s.error) list.append(h('div', { class: 'drop-item' }, ico('alert'), h('b', {}, s.name), h('span', { class: 'pill bad' }, s.error.length > 54 ? 'Okunamadı' : s.error)));
    s.items.forEach(i => list.append(h('div', { class: 'drop-item' }, ico(i.kind === 'track' ? 'flag' : 'car'), h('b', {}, i.name), h('span', { class: 'pill cyan' }, KIND_LABEL[i.kind]), i.installed ? h('span', { class: 'pill warn' }, 'Kurulu · değişecek') : null)));
  });
  const actions = h('div', { class: 'row', style: { justifyContent: 'flex-end', marginTop: '12px' } }, h('button', { class: 'btn sm', onclick: t.close }, 'Kapat'),
    valid.length ? h('button', { class: 'btn sm primary', onclick: install }, ico('download'), valid.reduce((n, s) => n + s.items.length, 0) > 1 ? 'Hepsini kur' : 'Kur') : null);
  content.append(list, actions);
  async function install() {
    const bar = h('div', { class: 'bar ind' }, h('i')), msg = h('div', { class: 'muted', style: { marginTop: '8px', fontSize: '12.5px' } }, 'Kuruluyor…');
    content.replaceChildren(bar, msg); t.title.textContent = 'Mod kuruluyor';
    try {
      const id = await api.install_mods(valid.map(s => s.path));
      const done = await pollJob(id, j => { msg.textContent = j.msg || 'Kuruluyor…'; if (j.percent != null) { bar.classList.remove('ind'); bar.firstChild.style.width = j.percent + '%'; } });
      t.title.textContent = '✓ Kuruldu'; content.replaceChildren(h('p', { class: 'muted', style: { marginBottom: '10px' } }, 'Oyuna ve sunucuya kuruldu. Pist adı/layout bilgilerini kontrol edin.'),
        h('div', { class: 'row', style: { justifyContent: 'flex-end' } }, h('button', { class: 'btn sm', onclick: t.close }, 'Tamam'),
          h('button', { class: 'btn sm primary', onclick: async () => { t.close(); go('mods', { tab: done.some(d => d.kind === 'track') ? 'track' : 'car' }); const m = await api.list_mods(); const first = m[done[0].kind === 'track' ? 'tracks' : 'cars'].find(x => x.name === done[0].name); first && editModModal(first, () => S.refresh && S.refresh()); } }, 'Bilgileri düzenle')));
      S.refresh && S.refresh();
    } catch (e) { t.title.textContent = 'Kurulamadı'; content.replaceChildren(h('p', { class: 'muted' }, e.message), h('div', { class: 'row', style: { justifyContent: 'flex-end', marginTop: '10px' } }, h('button', { class: 'btn sm', onclick: t.close }, 'Kapat'))); }
  }
}
