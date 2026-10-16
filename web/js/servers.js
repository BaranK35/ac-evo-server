/* Sunucu listesi ve sunucu ayar sayfası */
const SESSION_TYPES = [
  ['MultiplayerServerListSessionType_BOTH', 'Her İkisi (Ranked & Unranked - Önerilen)'],
  ['MultiplayerServerListSessionType_RANKED', 'Ranked'],
  ['MultiplayerServerListSessionType_UNRANKED', 'Unranked']
];
const WEATHERS = [['GameModeSelectionWeatherType_CLEAR', 'Açık', '☀️'], ['GameModeSelectionWeatherType_SCATTERED_CLOUDS', 'Az bulutlu', '🌤️'], ['GameModeSelectionWeatherType_BROKEN_CLOUDS', 'Parçalı bulutlu', '⛅'],
  ['GameModeSelectionWeatherType_OVERCAST', 'Kapalı', '☁️'], ['GameModeSelectionWeatherType_DRIZZLE', 'Çisenti', '🌦️'], ['GameModeSelectionWeatherType_RAIN', 'Yağmur', '🌧️'],
  ['GameModeSelectionWeatherType_HEAVY_RAIN', 'Şiddetli yağmur', '⛈️'], ['GameModeSelectionWeatherType_DAMP', 'Nemli', '💧']];
const GRIPS = [['InitialGrip_GREEN', 'Green (yeni asfalt)'], ['InitialGrip_FAST', 'Fast'], ['InitialGrip_OPTIMUM', 'Optimum']];
const BEHAV = [['GameModeSelectionWeatherBehaviour_STATIC', 'Sabit'], ['GameModeSelectionWeatherBehaviour_DYNAMIC', 'Dinamik']];

async function startServer(sid) {
  const bar = h('div', { class: 'bar ind' }, h('i')), msg = h('div', { class: 'muted', style: { marginTop: '8px', fontSize: '12.5px' } }, 'Hazırlanıyor…');
  const t = toastCard('Sunucu başlatılıyor', h('div', {}, bar, msg));
  try {
    const id = await api.start_server(sid);
    await pollJob(id, j => { msg.textContent = j.msg || 'Başlatılıyor…'; if (j.percent != null) { bar.classList.remove('ind'); bar.firstChild.style.width = j.percent + '%'; } });
    return true;
  } catch (e) {
    console.error('startServer error:', e);
    toast(e.message || 'Sunucu başlatılamadı', 'error');
    return false;
  } finally {
    t.close();
  }
}

/* ============================ SUNUCU LİSTESİ ============================ */
async function pageServers(view) {
  const page = h('div', { class: 'page' }); view.append(page);
  const sub = h('p', {}, ''), grid = h('div', { class: 'grid' });
  page.append(h('div', { class: 'pagehead' }, h('div', {}, h('h1', {}, 'Sunucular'), sub),
    h('div', { class: 'row' },
      h('button', { class: 'btn', onclick: async (e) => {
        const btn = e.currentTarget; btn.disabled = true;
        try { const errs = await api.start_all(); if (errs && errs.length) toast(errs.join('\n'), 'error'); } finally { btn.disabled = false; load(); }
      } }, ico('play'), 'Tümünü başlat'),
      h('button', { class: 'btn', onclick: async (e) => {
        const btn = e.currentTarget; btn.disabled = true;
        try { await api.stop_all(); } finally { btn.disabled = false; load(); }
      } }, ico('stop'), 'Tümünü durdur'),
      h('button', { class: 'btn primary', onclick: createServer }, ico('plus'), 'Yeni sunucu'))), grid);

  async function createServer() {
    try { const sid = await jobModal('Sunucu oluşturuluyor', () => api.create_server()); go('server', { sid, tab: 'Genel' }); }
    catch (e) { toast(e.message, 'error'); }
  }
  const cards = new Map();
  async function load() {
    let list; try { list = await api.list_servers(); } catch (e) { toast(e.message, 'error'); return; }
    const run = list.filter(s => s.running).length;
    sub.textContent = list.length ? `${list.length} sunucu · ${run} çalışıyor` : 'Henüz sunucu yok';
    if (!list.length) { grid.replaceChildren(); cards.clear(); grid.replaceWith(h('div', { class: 'empty', id: 'emp' }, h('div', { class: 'big' }, '🏁'), h('h2', {}, 'İlk sunucunuzu oluşturun'), h('p', {}, 'Sunucu dosyaları kopyalanır, sonra pist, hava ve araçları ayarlarsınız.'), h('div', { class: 'sp' }), h('button', { class: 'btn primary', onclick: createServer }, ico('plus'), 'Sunucu oluştur'))); return; }
    if (!grid.isConnected) { const e = $('#emp'); if (e) e.replaceWith(grid); }
    
    const seen = new Set(list.map(s => s.id));
    for (const [id, el] of cards) if (!seen.has(id)) { el.remove(); cards.delete(id); }

    list.forEach(s => {
      const stateKey = `${s.running}|${s.name}|${s.track}|${s.layout}|${s.max_players}|${s.cars}|${s.tcp_port}|${s.game_type}`;
      let el = cards.get(s.id);
      if (!el) { el = serverCard(s, true); cards.set(s.id, el); grid.append(el); }
      else if (el.dataset.state !== stateKey) { const fresh = serverCard(s, false); el.replaceWith(fresh); cards.set(s.id, fresh); }
    });
  }
  function serverCard(s, isNew) {
    const cover = h('div', { class: 'cover' }, h('span', { class: 'pill ' + (s.running ? 'on' : '') }, h('i'), s.running ? 'Çalışıyor' : 'Durdu'));
    getMap(s.track, 'track').then(uri => { if (uri) cover.append(h('img', { src: uri })); });
    const mode = s.game_type === 'GameModeType_RACE_WEEKEND' ? 'Race Weekend' : 'Practice';
    const cls = 'card hover scard' + (isNew ? ' fadein' : '');
    return h('div', { class: cls, 'data-state': `${s.running}|${s.name}|${s.track}|${s.layout}|${s.max_players}|${s.cars}|${s.tcp_port}|${s.game_type}`, onclick: () => go('server', { sid: s.id, tab: s.running ? 'Konsol' : 'Genel' }) },
      cover, h('h3', {}, s.name, s.track_is_mod ? h('span', { class: 'pill mod', style: { marginLeft: '8px' } }, 'MOD') : null),
      h('div', { class: 'sub' }, `${s.track} · ${s.layout}`),
      h('div', { class: 'chips' }, h('span', { class: 'chip' }, mode), h('span', { class: 'chip' }, `${s.max_players} oyuncu`), h('span', { class: 'chip' }, `${s.cars} araç`), h('span', { class: 'chip' }, `Port ${s.tcp_port}`)),
      h('div', { class: 'acts', onclick: e => e.stopPropagation() },
        s.running ? h('button', { class: 'btn stopbtn', onclick: async (e) => {
            const btn = e.currentTarget; btn.disabled = true; btn.textContent = 'Durduruluyor…';
            try { await api.stop_server(s.id); } catch(err) { console.error(err); } finally { btn.disabled = false; load(); }
          } }, ico('stop'), 'Durdur')
          : h('button', { class: 'btn primary', onclick: async (e) => {
            const btn = e.currentTarget; btn.disabled = true;
            try { if (await startServer(s.id)) go('server', { sid: s.id, tab: 'Konsol' }); } finally { btn.disabled = false; load(); }
          } }, ico('play'), 'Başlat'),
        h('button', { class: 'btn icon', title: 'Konsol', onclick: () => go('server', { sid: s.id, tab: 'Konsol' }) }, ico('term')),
        h('button', { class: 'btn icon', title: 'Paylaşım Kartı & Discord', onclick: () => showShareModal(s.id) }, ico('share')),
        h('button', { class: 'btn icon', title: 'Klasörü aç', onclick: () => api.open_server_folder(s.id) }, ico('folder')),
        h('button', { class: 'btn icon', title: 'Çoğalt', onclick: async () => { try { await jobModal('Sunucu çoğaltılıyor', () => api.clone_server(s.id)); load(); } catch (e) { toast(e.message, 'error'); } } }, ico('copy')),
        h('button', { class: 'btn icon danger', title: 'Sil', onclick: async () => { if (await confirmBox('Sunucuyu sil', `'${s.name}' sunucusu ve dosyaları kalıcı olarak silinsin mi?`, 'Sil')) { await api.delete_server(s.id); load(); } } }, ico('trash'))));
  }
  S.refresh = load; await load();
}

/* ============================ SUNUCU AYAR SAYFASI ============================ */
async function pageServer(view, { sid, tab = 'Konsol' }) {
  const page = h('div', { class: 'page' }); view.append(page);
  let pack;
  try { pack = await api.get_server(sid); } catch (e) { toast(e.message, 'error'); return go('servers'); }
  const F = JSON.parse(JSON.stringify(pack.data));
  F.serverconfig_extra = JSON.stringify(F.serverconfig_extra || {}, null, 2);
  F.seasondefinition_extra = JSON.stringify(F.seasondefinition_extra || {}, null, 2);
  const TRACKS = pack.tracks, CARS = pack.cars;
  let dirty = false, current = tab, running = !!pack.running, started = 0, now = 0;
  let lastPaintedRunning = null, isBusy = false;
  const C = { seq: 0, lines: [], filter: 'all', q: '', diag: '', stick: true };
  let autoSaveTimer = null;
  const autoSaveBadge = h('span', { class: 'pill ok', style: { transition: 'all 0.3s', fontSize: '12px', padding: '4px 10px', display: 'inline-flex', alignItems: 'center', gap: '5px' } }, ico('check'), 'Ayarlar güncel');

  function scheduleAutoSave() {
    autoSaveBadge.className = 'pill warn';
    autoSaveBadge.replaceChildren(ico('refresh'), 'Kaydediliyor…');
    if (autoSaveTimer) clearTimeout(autoSaveTimer);
    autoSaveTimer = setTimeout(async () => {
      const ok = await save(true);
      if (ok) {
        autoSaveBadge.className = 'pill ok';
        autoSaveBadge.replaceChildren(ico('check'), 'Otomatik kaydedildi');
        setTimeout(() => {
          if (!dirty) {
            autoSaveBadge.className = 'pill ok';
            autoSaveBadge.replaceChildren(ico('check'), 'Ayarlar güncel');
          }
        }, 2000);
      } else {
        autoSaveBadge.className = 'pill warn';
        autoSaveBadge.replaceChildren(ico('alert'), 'Kaydedilemedi');
      }
    }, 400);
  }

  const mark = () => {
    dirty = true;
    scheduleAutoSave();
  };

  const restartBtn = h('button', { class: 'btn', onclick: async (e) => {
    const btn = e.currentTarget; btn.disabled = true;
    try {
      if (await save(true)) {
        await api.stop_server(sid);
        running = false; paintRun(true);
        C.lines = []; C.seq = 0;
        if (term) term.replaceChildren();
        if (await startServer(sid)) {
          running = true; paintRun(true); switchTab('Konsol');
          await pollConsole();
        }
      }
    } finally {
      btn.disabled = false;
      paintRun(true);
    }
  } }, ico('refresh'), 'Yeniden başlat');

  const runBtn = h('button', { class: 'btn primary', onclick: toggleRun });
  const statusPill = h('span', { class: 'pill' }, h('i'), 'Durdu'), statusExtra = h('span', { class: 'muted', style: { fontSize: '12.5px' } });

  function paintRun(force = false) {
    if (!force && lastPaintedRunning === running) return;
    lastPaintedRunning = running;
    runBtn.className = 'btn ' + (running ? 'stopbtn' : 'primary');
    runBtn.replaceChildren(ico(running ? 'stop' : 'play'), running ? 'Durdur' : 'Başlat');
    runBtn.disabled = false;
    statusPill.className = 'pill ' + (running ? 'on' : '');
    statusPill.replaceChildren(h('i'), document.createTextNode(running ? 'Çalışıyor' : 'Durdu'));
  }

  async function toggleRun() {
    if (isBusy) return;
    isBusy = true;
    runBtn.disabled = true;

    try {
      if (running) {
        runBtn.textContent = 'Durduruluyor…';
        await api.stop_server(sid);
        running = false;
        paintRun(true);
        await pollConsole();
      } else {
        if (dirty && !(await save(true))) return;
        runBtn.textContent = 'Başlatılıyor…';
        C.lines = [];
        C.seq = 0;
        if (term) term.replaceChildren();
        const ok = await startServer(sid);
        if (ok) {
          running = true;
          paintRun(true);
          switchTab('Konsol');
          await pollConsole();
        } else {
          running = false;
          paintRun(true);
        }
      }
    } catch (err) {
      console.error('Sunucu durum hatası:', err);
      toast(err.message || 'İşlem sırasında hata oluştu', 'error');
    } finally {
      isBusy = false;
      runBtn.disabled = false;
      paintRun(true);
    }
  }

  async function save(silent) {
    try {
      const body = JSON.parse(JSON.stringify(F));
      const r = await api.save_server(sid, body);
      dirty = false;
      (r.warnings || []).forEach(w => toast(w, 'info', 7000));
      if (!silent) toast('Ayarlar kaydedildi', 'ok'); return true;
    } catch (e) { toast(e.message, 'error'); return false; }
  }

  /* ---- form yardımcıları ---- */
  function fld(label, key, kind = 'text', o = {}) {
    let ctl;
    if (kind === 'bool') {
      const i = h('input', { type: 'checkbox', onchange: () => { F[key] = i.checked; mark(); o.onchange && o.onchange(i.checked); } }); i.checked = !!F[key];
      ctl = h('label', { class: 'switch' }, i, h('span'));
    } else if (kind === 'select') {
      const s = h('select', { class: 'sel', onchange: () => { F[key] = s.value; mark(); o.onchange && o.onchange(s.value); } }, o.options.map(([v, l]) => h('option', { value: v }, l)));
      s.value = F[key]; ctl = s;
    } else if (kind === 'area') {
      ctl = h('textarea', { class: 'ta', spellcheck: 'false', oninput: e => { F[key] = e.target.value; mark(); } }); ctl.value = F[key] || '';
    } else {
      const num = kind === 'int' || kind === 'float';
      const i = h('input', { class: 'in ' + (num ? 'num' : ''), type: num ? 'number' : 'text', step: kind === 'float' ? '0.1' : '1', spellcheck: 'false', placeholder: o.ph || '',
        oninput: () => { F[key] = num ? (i.value === '' ? 0 : Number(i.value)) : i.value; mark(); sfx && (sfx.textContent = o.dur ? fmtDur(F[key]) : ''); } });
      i.value = F[key] ?? '';
      var sfx = o.dur ? h('span', { class: 'suffix' }, fmtDur(F[key])) : (o.suffix ? h('span', { class: 'suffix' }, o.suffix) : null);
      ctl = h('div', { class: 'row' }, i, sfx);
    }
    return h('div', { class: 'field' }, h('label', {}, label), ctl, o.hint ? h('div', { class: 'hint' }, o.hint) : null);
  }
  const section = (title, ...fields) => h('div', { class: 'section' }, h('h3', {}, title), h('div', { class: 'card' }, fields));
  const seg = (key, options, after) => { const box = h('div', { class: 'seg' }); const paint = () => $$('button', box).forEach((b, i) => b.classList.toggle('on', options[i][0] === F[key])); options.forEach(([v, l]) => box.append(h('button', { onclick: () => { F[key] = v; mark(); paint(); after && after(v); } }, l))); paint(); return box; };

  /* ---- konsol ---- */
  const classify = (kind, text) => kind === 'sys' ? 'sys' : kind === 'err' ? 'err' : /error|fail|exception|fatal|crash|cannot|unable|invalid/i.test(text) ? 'err' : /warn/i.test(text) ? 'warn' : 'out';
  function lineEl(l) {
    const d = document.createElement('div');
    d.className = 'ln ' + (l.cls || 'out');
    const s = document.createElement('span');
    s.className = 't';
    s.textContent = l.ts || '';
    d.append(s, document.createTextNode(l.text || ''));
    return d;
  }
  const passes = l => (C.filter === 'all' || (C.filter === 'err' && l.cls === 'err') || (C.filter === 'warn' && (l.cls === 'warn' || l.cls === 'err')) || (C.filter === 'sys' && l.cls === 'sys')) && (!C.q || (l.text && l.text.toLowerCase().includes(C.q)));
  let term;
  let diagBox = h('div', {});
  function consoleTab() {
    const wrap = h('div', { class: 'console' });
    diagBox = h('div', {});

    const info = h('div', { class: 'conninfo' },
      h('span', {}, 'Yerel ağ: ', h('b', {}, `${pack.ip}:${F.tcp_port}`)),
      h('span', {}, 'HTTP API: ', h('b', {}, F.http_port)),
      h('span', {}, 'TCP/UDP: ', h('b', {}, F.tcp_port)),
      h('span', { class: 'grow' }),
      h('button', { class: 'btn sm', onclick: async () => { await api.fix_firewall(sid); toast('Güvenlik duvarı izinleri uygulandı. Açılan Windows penceresinde Evet\'e basın.', 'ok', 6000); } }, ico('bolt'), 'Güvenlik Duvarı İzni Ver'));

    term = h('div', { class: 'term', onscroll: () => { C.stick = term.scrollTop + term.clientHeight >= term.scrollHeight - 50; } });
    const chips = h('div', { class: 'seg' }, [['all', 'Tümü'], ['err', 'Hatalar'], ['warn', 'Uyarılar'], ['sys', 'Sistem']].map(([k, l]) => h('button', { class: C.filter === k ? 'on' : '', onclick: e => { C.filter = k; $$('button', chips).forEach(b => b.classList.toggle('on', b === e.target)); rerender(); } }, l)));
    const q = h('input', { class: 'in', placeholder: 'Konsolda ara…', oninput: e => { C.q = e.target.value.toLowerCase(); rerender(); } }); q.value = C.q;

    wrap.append(diagBox, info, h('div', { class: 'cbar' }, chips, q, h('span', { class: 'grow' }),
      h('button', { class: 'btn sm', onclick: () => {
        try {
          const text = C.lines.map(l => l.ts + '  ' + l.text).join('\n');
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text);
          } else {
            const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove();
          }
          toast('Konsol panoya kopyalandı', 'ok');
        } catch(e) { toast('Kopyalanamadı: ' + e.message, 'error'); }
      } }, ico('copy'), 'Kopyala'),
      h('button', { class: 'btn sm', onclick: async () => {
        try {
          await api.console_clear(sid);
          C.lines = [];
          C.seq = 0;
          const activeTerm = (term && term.isConnected) ? term : ($('.term') || term);
          if (activeTerm) activeTerm.replaceChildren();
          rerender();
          toast('Konsol temizlendi', 'info', 2000);
        } catch (e) {
          toast('Temizlenemedi: ' + e.message, 'error');
        }
      } }, ico('trash'), 'Temizle')), term);

    rerender();
    paintDiag();
    return wrap;
  }

  function rerender() {
    const activeTerm = (term && term.isConnected) ? term : ($('.term') || term);
    if (!activeTerm) return;
    activeTerm.replaceChildren();
    const vis = C.lines.filter(passes).slice(-400);
    if (!vis.length) {
      activeTerm.append(h('div', { class: 'ph' }, C.lines.length ? 'Bu filtreyle eşleşen satır yok' : 'Sunucu başlatıldığında çıktısı burada canlı görünür.'));
    } else {
      const f = document.createDocumentFragment();
      vis.forEach(l => f.append(lineEl(l)));
      activeTerm.append(f);
      if (C.stick) {
        activeTerm.scrollTop = activeTerm.scrollHeight;
      }
    }
  }

  function paintDiag() {
    const activeDiag = (diagBox && diagBox.isConnected) ? diagBox : ($('.console > div:first-child') || diagBox);
    if (!activeDiag) return;
    activeDiag.replaceChildren();
    const list = Array.isArray(C.diagList) ? C.diagList : [];
    list.forEach(d => {
      if (!d || typeof d !== 'object' || !d.title || !d.detail) return;
      const level = d.level === 'warn' ? 'warn' : d.level === 'info' ? 'info' : 'error';
      const icoChar = level === 'error' ? '⛔' : level === 'warn' ? '⚠️' : 'ℹ️';
      activeDiag.append(h('div', { class: 'diag ' + level },
        h('div', { class: 'dico' }, icoChar),
        h('div', { class: 'grow' }, h('b', {}, String(d.title)), h('p', {}, String(d.detail))),
        d.action ? h('button', { class: 'btn sm', onclick: async () => {
          if (d.action === 'mods') go('mods');
          else if (d.action === 'firewall') {
            await api.fix_firewall(sid);
            toast('Güvenlik duvarı izinleri uygulandı. Açılan Windows penceresinde Evet\'e basın.', 'ok', 6000);
          } else if (d.action === 'tunnel') {
            try {
              const res = await api.tunnel_test();
              if (res.ok) {
                await api.tunnel_ensure(sid);
                toast(`VPS Tüneli Hazır! IP: ${res.vps_ip} (${res.latency_ms}ms). Sunucuyu 'Yeniden Başlat' tuşuyla başlatabilirsiniz.`, 'ok', 8000);
              } else {
                toast(`Tünel hatası: ${res.message}`, 'error', 6000);
              }
            } catch(e) { toast('Tünel hatası: ' + e.message, 'error'); }
          } else switchTab('Genel');
        } }, d.action === 'mods' ? 'Modlar' : d.action === 'firewall' ? 'Güvenlik Duvarı İzni Ver' : d.action === 'tunnel' ? 'Tüneli Test Et / Başlat' : 'Ayarlar') : null
      ));
    });
  }

  let isPolling = false;
  async function pollConsole() {
    if (isPolling) return;
    isPolling = true;
    try {
      const r = await api.get_console(sid, C.seq);
      if (!r) return;
      if (r.running !== running) {
        running = !!r.running;
        paintRun(true);
      }
      started = r.started; now = r.now;
      statusExtra.textContent = running ? `PID ${r.pid} · ${clock(now - started)}` : (r.exit_code != null ? `Çıkış kodu ${r.exit_code}` : '');
      const key = JSON.stringify(r.diagnosis || []);
      if (key !== C.diag) {
        C.diag = key;
        C.diagList = Array.isArray(r.diagnosis) ? r.diagnosis : [];
        paintDiag();
      }

      const activeTerm = (term && term.isConnected) ? term : ($('.term') || term);

      if (r.reset) {
        C.lines = [];
        if (activeTerm) activeTerm.replaceChildren();
      }

      if (r.lines && r.lines.length) {
        const fresh = r.lines.map(([, ts, kind, text]) => ({ ts: ts || '', text: text || '', cls: classify(kind, text) }));
        C.lines.push(...fresh);
        if (C.lines.length > 2500) C.lines.splice(0, C.lines.length - 2500);

        if (current === 'Konsol' && activeTerm) {
          const ph = activeTerm.querySelector('.ph');
          if (ph || activeTerm.childElementCount === 0) {
            rerender();
          } else {
            const vis = fresh.filter(passes);
            if (vis.length) {
              const f = document.createDocumentFragment();
              vis.forEach(l => f.append(lineEl(l)));
              activeTerm.append(f);
              while (activeTerm.childElementCount > 600) activeTerm.firstChild.remove();
              if (C.stick) {
                activeTerm.scrollTop = activeTerm.scrollHeight;
              }
            }
          }
        }
      } else if (current === 'Konsol' && activeTerm) {
        const ph = activeTerm.querySelector('.ph');
        if (C.lines.length && (ph || activeTerm.childElementCount === 0)) {
          rerender();
        }
      }

      C.seq = r.seq || 0;
    } catch (e) {
      console.error('pollConsole error:', e);
    } finally {
      isPolling = false;
    }
  }

  /* ---- sekmeler ---- */
  const TABS = ['Konsol', 'Canlı Oyuncular', 'Genel', 'Oturumlar', 'Pist', 'Hava ve zemin', 'Araçlar', 'Cezalar ve Kurallar', 'Gelişmiş', 'Sonuçlar'];
  const body = h('div', { class: 'tabbody' }), tabsEl = h('div', { class: 'tabs' });
  function switchTab(name) {
    current = name;
    $$('.tab', tabsEl).forEach(t => t.classList.toggle('active', t.dataset.n === name));
    body.replaceChildren(h('div', { class: 'fadein' }, renderTab(name)));
    if (name === 'Konsol') {
      rerender();
      paintDiag();
    }
  }
  TABS.forEach(n => tabsEl.append(h('div', { class: 'tab', 'data-n': n, onclick: () => switchTab(n) }, n)));
  function renderTab(n) {
    switch (n) {
      case 'Konsol': return consoleTab();
      case 'Canlı Oyuncular': return tabPlayers();
      case 'Genel': return tabGeneral();
      case 'Oturumlar': return tabSessions();
      case 'Pist': return tabTrack();
      case 'Hava ve zemin': return tabWeather();
      case 'Araçlar': return tabCars();
      case 'Cezalar ve Kurallar': return tabRules();
      case 'Gelişmiş': return tabAdvanced();
      default: return tabResults();
    }
  }
  function tabGeneral() {
    return h('div', { class: 'twocol' }, h('div', {},
      section('Sunucu', fld('Sunucu adı', 'name', 'text', { hint: 'Sunucu listesinde görünen ad' }), fld('Azami oyuncu', 'max_players', 'int'), fld('Liste türü', 'type', 'select', { options: SESSION_TYPES }), fld('Oturumları döngüde çalıştır', 'cycle', 'bool', { hint: 'Açıkken oturumlar bitince sunucu baştan başlar' })),
      section('Şifreler', fld('Sürücü şifresi', 'driver_password', 'text', { hint: 'Boş bırakırsanız herkes katılabilir' }), fld('İzleyici şifresi', 'spectator_password'), fld('Yönetici şifresi', 'admin_password', 'text', { hint: 'Oyunda sohbetten /admin <şifre> ile yetki alırsınız' }))),
      h('div', {}, section('Portlar', fld('TCP portu', 'tcp_port', 'int'), fld('UDP portu', 'udp_port', 'int', { hint: 'TCP ile aynı olması önerilir' }), fld('HTTP portu', 'http_port', 'int')),
        h('div', { class: 'note' }, `Yerel ağdaki oyuncular ${pack.ip}:${F.tcp_port} adresiyle bağlanır. Dış ağdaki arkadaşlarınızın bağlanabilmesi için modeminizden bu portları (TCP ve UDP) açmanız veya gerekirse port yönlendirme tüneli kullanmanız yeterlidir.`)));
  }
  function sessionCard(prefix, title) {
    return section(title, fld('Süre (saniye)', prefix + '_length', 'int', { dur: true, hint: prefix === 'race' && F.race_duration_type === 'GameModeSelectionDuration_LAPS' ? 'Tur sayısı olarak okunur' : '' }), fld('Başlangıç saati (0-23)', prefix + '_hour', 'int'), fld('Başlangıç dakikası', prefix + '_minute', 'int'),
      fld('Zaman çarpanı', prefix + '_time_multiplier', 'int', { suffix: '× gerçek zaman' }), fld('Pite dönmek için azami bekleme (sn)', prefix + '_max_wait_to_box', 'int'), fld('Ek süre (sn)', prefix + '_overtime', 'int', { hint: 'Sonraki oturuma geçmeden önceki bekleme' }));
  }
  function tabSessions() {
    const wk = F.game_type === 'GameModeType_RACE_WEEKEND', box = h('div', {});
    const paint = () => { box.replaceChildren(); const w = F.game_type === 'GameModeType_RACE_WEEKEND';
      box.append(h('div', { class: 'twocol' }, sessionCard('practice', 'Practice'), w ? sessionCard('qualify', 'Qualify') : null, w ? sessionCard('warmup', 'Warmup') : null, w ? h('div', {},
        section('Yarış', fld('Yarış uzunluğu türü', 'race_duration_type', 'select', { options: [['GameModeSelectionDuration_TIME', 'Süre'], ['GameModeSelectionDuration_LAPS', 'Tur']], onchange: paint }), fld('Süre / tur', 'race_length', 'int', { dur: F.race_duration_type !== 'GameModeSelectionDuration_LAPS' }), fld('Başlangıç saati', 'race_hour', 'int'), fld('Başlangıç dakikası', 'race_minute', 'int'), fld('Zaman çarpanı', 'race_time_multiplier', 'int'), fld('Pite dönmek için azami bekleme (sn)', 'race_max_wait_to_box', 'int'), fld('Ek süre (sn)', 'race_overtime', 'int'),
          fld('Oyuncuları bekleme, en az (sn)', 'min_waiting_for_players', 'int'), fld('Oyuncuları bekleme, en çok (sn)', 'max_waiting_for_players', 'int')),
        section('Zorunlu pit stop', fld('Zorunlu pit stop', 'mandatory_pitstop', 'bool', { hint: 'Yalnızca süreli ve 1200 sn\'den uzun yarışlarda geçerli' }), fld('Lastik değişimi zorunlu', 'mandatory_pitstop_tyre_change', 'bool'), fld('Yakıt ikmali zorunlu', 'mandatory_pitstop_refuel', 'bool'), fld('Pit penceresi (sn)', 'pit_window_time', 'int'))) : null)); };
    const mode = h('div', { class: 'row', style: { marginBottom: '20px' } }, h('b', {}, 'Oyun modu'), seg('game_type', [['GameModeType_PRACTICE', 'Practice'], ['GameModeType_RACE_WEEKEND', 'Race Weekend']], paint));
    paint(); return h('div', {}, mode, box);
  }
  function tabTrack() {
    let filter = 'all', q = ''; const grid = h('div', { class: 'grid wide' });
    const selKey = () => F.track + '|' + F.layout;
    const paint = () => {
      grid.replaceChildren(); let n = 0;
      TRACKS.forEach(t => {
        if ((filter === 'mod' && !t.mod) || (filter === 'off' && t.mod)) return;
        if (q && !(t.track + ' ' + t.layout).toLowerCase().includes(q)) return; n++;
        const card = h('div', { class: 'tcard ' + (selKey() === t.track + '|' + t.layout ? 'sel' : ''), onclick: () => { Object.assign(F, { track: t.track, layout: t.layout, event_name: t.event_name, track_length: t.track_length, track_is_mod: !!t.mod }); mark(); paint(); } },
          t.mod ? h('span', { class: 'pill mod' }, 'MOD') : null, h('b', {}, t.track), h('small', {}, `${t.layout} · ${km(t.track_length)}`));
        if (t.mod) { const tm = h('div', { class: 'tm' }, ''); card.prepend(tm); getMap(t.mod_folder || t.track).then(u => { if (u) tm.append(h('img', { src: u })); else tm.remove(); }); }
        grid.append(card);
      });
      if (!n) grid.append(h('div', { class: 'muted' }, 'Eşleşen pist yok.'));
    };
    const chips = h('div', { class: 'seg' }, [['all', 'Tümü'], ['off', 'Resmi'], ['mod', 'Modlar']].map(([k, l]) => h('button', { class: filter === k ? 'on' : '', onclick: e => { filter = k; $$('button', chips).forEach(b => b.classList.toggle('on', b === e.target)); paint(); } }, l)));
    paint();
    return h('div', {}, h('div', { class: 'cbar' }, chips, h('input', { class: 'in', placeholder: 'Pist ara…', oninput: e => { q = e.target.value.toLowerCase(); paint(); } }), h('span', { class: 'grow' }),
      h('button', { class: 'btn sm', onclick: () => go('mods') }, ico('plus'), 'Mod pisti ekle')), grid);
  }
  function tabWeather() {
    const tiles = h('div', { class: 'wtiles' }); const paint = () => { tiles.replaceChildren(); WEATHERS.forEach(([v, l, e]) => tiles.append(h('div', { class: 'wt ' + (F.weather === v ? 'sel' : ''), onclick: () => { F.weather = v; mark(); paint(); } }, h('span', { class: 'e' }, e), l))); }; paint();
    return h('div', { class: 'twocol' }, h('div', {}, h('div', { class: 'section' }, h('h3', {}, 'Hava durumu'), tiles), section('Hava davranışı', h('div', { class: 'field' }, h('label', {}, 'Davranış'), seg('weather_behavior', BEHAV)), h('div', { class: 'field' }, h('label', {}, 'Başlangıç gribi'), seg('initial_grip', GRIPS)))),
      h('div', {}, section('Tarih', fld('Yıl', 'year', 'int'), fld('Ay', 'month', 'int'), fld('Gün', 'day', 'int'), fld('Saniye', 'second', 'int')), h('div', { class: 'note' }, 'Her oturumun saati ve zaman çarpanı "Oturumlar" sekmesinde ayarlanır.')));
  }
  function tabCars() {
    const sel = new Map(F.cars.map(c => [c.car_name, c])); let q = '';
    const known = new Set(CARS.map(c => c.name)); const extra = F.cars.filter(c => !known.has(c.car_name)).map(c => ({ name: c.car_name, display_name: c.car_name + ' (katalogda yok)', performance_indicator: 0 }));
    const rows = [...CARS, ...extra]; const tb = h('tbody'), count = h('span', { class: 'pill cyan' });
    const preview = h('div', { class: 'car-preview', style: { width: '240px', height: '140px', background: 'var(--card)', borderRadius: '8px', marginLeft: '20px', backgroundSize: 'contain', backgroundRepeat: 'no-repeat', backgroundPosition: 'center', flexShrink: 0 } });
    const sync = () => { F.cars = [...sel.values()]; count.textContent = F.cars.length + ' araç seçili'; mark(); };
    const vis = () => rows.filter(c => !q || (c.display_name + ' ' + c.name).toLowerCase().includes(q));
    const paint = () => {
      tb.replaceChildren();
      vis().forEach(c => {
        const on = sel.has(c.name), cur = sel.get(c.name) || { car_name: c.name, ballast: 0, restrictor: 0 };
        const cb = h('input', { type: 'checkbox', class: 'cbx', onchange: () => { if (cb.checked) sel.set(c.name, cur); else sel.delete(c.name); bal.disabled = res.disabled = !cb.checked; sync(); } }); cb.checked = on;
        const bal = h('input', { class: 'in sm', type: 'number', value: cur.ballast, oninput: e => { cur.ballast = Number(e.target.value) || 0; sync(); } }), res = h('input', { class: 'in sm', type: 'number', value: cur.restrictor, oninput: e => { cur.restrictor = Number(e.target.value) || 0; sync(); } });
        bal.disabled = res.disabled = !on;
        tb.append(h('tr', { onmouseenter: () => getMap(c.name, 'car').then(u => { preview.style.backgroundImage = u ? `url(${u})` : 'none'; }) }, h('td', {}, cb), h('td', {}, c.display_name || c.name, c.mod ? h('span', { class: 'pill mod', style: { marginLeft: '8px' } }, 'MOD') : null), h('td', { class: 'muted' }, c.performance_indicator != null ? Number(c.performance_indicator).toFixed(1) : ''), h('td', {}, bal), h('td', {}, res)));
      });
    };
    const setAll = v => { vis().forEach(c => v ? sel.set(c.name, sel.get(c.name) || { car_name: c.name, ballast: 0, restrictor: 0 }) : sel.delete(c.name)); sync(); paint(); };
    paint(); count.textContent = F.cars.length + ' araç seçili';
    return h('div', {}, h('div', { class: 'cbar' }, h('input', { class: 'in', placeholder: 'Araç ara…', oninput: e => { q = e.target.value.toLowerCase(); paint(); } }), h('button', { class: 'btn sm', onclick: () => setAll(true) }, 'Görünenleri seç'), h('button', { class: 'btn sm', onclick: () => setAll(false) }, 'Görünenleri kaldır'), h('span', { class: 'grow' }), count),
      h('div', { class: 'row', style: { alignItems: 'flex-start' } }, h('div', { class: 'card', style: { padding: '0', overflow: 'auto', maxHeight: 'calc(100vh - 340px)', flexGrow: 1 } }, h('table', { class: 'tbl' }, h('thead', {}, h('tr', {}, h('th', { style: { width: '44px' } }), h('th', {}, 'Araç'), h('th', {}, 'PI'), h('th', {}, 'Ağırlık (kg)'), h('th', {}, 'Kısıtlayıcı'))), tb)), preview));
  }
  function tabPlayers() {
    const box = h('div', {});
    const head = h('div', { class: 'cbar', style: { marginBottom: '16px', gap: '12px' } },
      h('span', { class: 'pill ' + (running ? 'ok' : 'muted') }, running ? '● Sunucu Çalışıyor' : '○ Sunucu Kapalı'),
      h('span', { class: 'muted', style: { fontSize: '13px' } }, 'Oyuncular sunucuya bağlandıkça veya ceza aldıkça anlık burada listelenir.'),
      h('span', { class: 'grow' }),
      h('button', { class: 'btn sm', onclick: () => refreshPlayers() }, ico('refresh'), 'Yenile')
    );

    const playersTable = h('div', { class: 'card', style: { padding: '0', overflow: 'hidden', marginBottom: '20px' } });
    const blCard = h('div', { class: 'card', style: { marginBottom: '20px' } });
    const stewardBox = h('div', { class: 'steward-box', style: { display: 'none' } });

    async function refreshSteward() {
      if (!running) { stewardBox.style.display = 'none'; return; }
      try {
        const rep = await api.get_steward_report(sid);
        paintSteward(rep);
      } catch (e) {
        console.error('get_steward_report err:', e);
      }
    }

    function paintSteward(rep) {
      if (!running) { stewardBox.style.display = 'none'; return; }
      stewardBox.style.display = 'block';
      stewardBox.replaceChildren();
      const score = rep.fair_play_score ?? 100;
      const scoreCls = score >= 80 ? 'high' : score >= 50 ? 'med' : 'low';

      const sHead = h('div', { class: 'steward-head' },
        h('div', { class: 'steward-gauge' },
          ico('shield'),
          h('div', {},
            h('b', { style: { fontSize: '14px', display: 'block' } }, '🛡️ AI Race Director & Telemetry Sentinel'),
            h('small', { class: 'muted' }, 'Canlı temas, kaza, şikan kesme ve ters yön ihlallerini analiz eder')
          )
        ),
        h('div', { class: 'row' },
          h('span', { class: 'muted', style: { fontSize: '12px' } }, 'Fair-Play Skoru:'),
          h('span', { class: 'steward-score ' + scoreCls }, score + '%'),
          h('span', { class: 'pill ' + (rep.unresolved_critical ? 'bad' : 'ok') },
            rep.unresolved_critical ? `${rep.unresolved_critical} Kritik Olay` : 'Temiz Seans'
          )
        )
      );

      const sList = h('div', { class: 'steward-list' });
      if (!rep.recent_incidents || !rep.recent_incidents.length) {
        sList.append(h('div', { class: 'muted', style: { padding: '12px', textAlign: 'center', fontSize: '12.5px' } }, '✨ Henüz kural ihlali veya kaza tespit edilmedi. Yarış sportmence ilerliyor.'));
      } else {
        rep.recent_incidents.forEach(inc => {
          const item = h('div', { class: 'steward-item ' + inc.severity },
            h('span', { class: 'pill ' + (inc.severity === 'critical' ? 'bad' : inc.severity === 'high' ? 'warn' : 'ok') }, inc.timestamp),
            h('span', { style: { fontWeight: 'bold' } }, `[Araç #${inc.car_number}]`),
            h('span', { class: 'grow' }, inc.description),
            inc.recommended_action && !inc.applied ? h('button', {
              class: 'btn sm primary',
              title: 'Hakem kararını oyunda hemen uygula',
              onclick: async (e) => {
                const btn = e.currentTarget; btn.disabled = true;
                try {
                  await api.apply_steward_action(sid, inc.id, inc.recommended_action, inc.car_number, inc.recommended_param);
                  toast(`Hakem cezası uygulandı: ${inc.action_label}`, 'ok');
                  refreshSteward();
                  refreshPlayers();
                } catch(err) {
                  toast('Ceza uygulanamadı: ' + err.message, 'error');
                }
              }
            }, ico('bolt'), inc.action_label || 'Uygula') : (inc.applied ? h('span', { class: 'pill ok' }, 'Uygulandı') : null)
          );
          sList.append(item);
        });
      }
      stewardBox.append(sHead, sList);
    }

    async function refreshPlayers() {
      try {
        const players = await api.get_players(sid);
        paintPlayers(players);
      } catch (e) {
        console.error('get_players err:', e);
      }
      await refreshSteward();
      try {
        const bl = await api.get_blacklist(sid);
        paintBlacklist(bl);
      } catch (e) {
        console.error('get_blacklist err:', e);
      }
    }

    async function showCommandActionModal(action, carNo, driverName, title, param = "") {
      try {
        await api.admin_action(sid, action, carNo, param);
        toast(`✔ ${title || 'Eylem'}: Araç #${carNo} uygulandı.`, 'ok');
      } catch (err) {
        toast(err.message, 'error');
      }
    }

    function showPenaltyModal(carNo, driverName, p, onApplied) {
      let selectedType = 'dt';
      let timeSeconds = 10;

      const cardDt = h('div', { class: 'pen-card active', onclick: () => select('dt') },
        h('div', { class: 'pen-card-head' }, '⚡ Drive-Through (DT)'),
        h('div', { class: 'pen-card-desc' }, 'Pitten hız sınırı ile geçiş yapma zorunluluğu cezası.')
      );
      const cardSg = h('div', { class: 'pen-card', onclick: () => select('sg') },
        h('div', { class: 'pen-card-head' }, '🛑 Stop & Go (SG)'),
        h('div', { class: 'pen-card-desc' }, 'Pitte durup bekleme (dur & kalk) cezası.')
      );
      const cardTime = h('div', { class: 'pen-card', onclick: () => select('time') },
        h('div', { class: 'pen-card-head' }, '⏱️ Zaman Cezası (+Süre)'),
        h('div', { class: 'pen-card-desc' }, 'Yarış süresine eklenen saniye cinsinden ceza.')
      );
      const cardDisq = h('div', { class: 'pen-card', onclick: () => select('disq') },
        h('div', { class: 'pen-card-head' }, '🚫 Diskalifiye (Siyah Bayrak)'),
        h('div', { class: 'pen-card-desc' }, 'Sürücüyü seans veya yarıştan tamamen ihraç eder.')
      );

      const cards = { dt: cardDt, sg: cardSg, time: cardTime, disq: cardDisq };

      const timeInput = h('input', {
        type: 'number',
        class: 'in sm',
        value: '10',
        min: '1',
        max: '300',
        oninput: e => { timeSeconds = parseInt(e.target.value) || 10; updatePreview(); }
      });

      const chip5 = h('button', { class: 'pen-chip', onclick: () => setTime(5) }, '+5s');
      const chip10 = h('button', { class: 'pen-chip active', onclick: () => setTime(10) }, '+10s');
      const chip30 = h('button', { class: 'pen-chip', onclick: () => setTime(30) }, '+30s');

      function setTime(sec) {
        timeSeconds = sec;
        timeInput.value = sec;
        [chip5, chip10, chip30].forEach(c => c.classList.remove('active'));
        if (sec === 5) chip5.classList.add('active');
        if (sec === 10) chip10.classList.add('active');
        if (sec === 30) chip30.classList.add('active');
        updatePreview();
      }

      const timeRow = h('div', { class: 'pen-time-row', style: { display: 'none' } },
        h('span', { class: 'muted', style: { fontSize: '13px', fontWeight: 'bold' } }, 'Ceza Süresi:'),
        timeInput,
        h('span', { class: 'muted', style: { fontSize: '13px' } }, 'saniye'),
        h('div', { class: 'pen-chips', style: { marginLeft: '8px' } }, chip5, chip10, chip30)
      );

      const cmdPreview = h('code', { style: { color: '#38bdf8', fontWeight: 'bold' } }, `\\add_penalty ${carNo} dt`);

      function updatePreview() {
        if (selectedType === 'time') {
          cmdPreview.textContent = `\\add_time ${carNo} ${timeSeconds}`;
        } else {
          cmdPreview.textContent = `\\add_penalty ${carNo} ${selectedType}`;
        }
      }

      function select(type) {
        selectedType = type;
        Object.keys(cards).forEach(k => cards[k].classList.toggle('active', k === type));
        timeRow.style.display = type === 'time' ? 'flex' : 'none';
        updatePreview();
      }

      const body = h('div', { class: 'pen-modal-body' },
        h('div', { class: 'pen-target-banner' },
          h('div', {},
            h('b', { style: { fontSize: '15px', color: '#fff' } }, `Araç #${carNo} — ${driverName}`),
            p.car_model ? h('div', { class: 'muted', style: { fontSize: '12px', marginTop: '2px' } }, p.car_model) : null
          ),
          h('span', { class: 'pill warn' }, 'Ceza Yaptırımı')
        ),
        h('div', { class: 'pen-grid' }, cardDt, cardSg, cardTime, cardDisq),
        timeRow,
        h('div', { style: { background: 'rgba(0,0,0,0.3)', padding: '10px 14px', borderRadius: '10px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' } },
          h('span', { class: 'muted', style: { fontSize: '12.5px' } }, 'Oluşturulacak Oyun Komutu:'),
          cmdPreview
        )
      );

      modal({
        title: '⚖️ Sürücü Ceza Yönetimi',
        sub: `Araç #${carNo} (${driverName}) için kural ihlali cezası uygulayın`,
        body,
        actions: [
          { label: 'Vazgeç' },
          {
            label: 'Cezayı Uygula',
            kind: 'primary',
            onClick: async (e, { close }) => {
              const param = selectedType === 'time' ? String(timeSeconds) : selectedType;
              close();
              await showCommandActionModal('add_penalty', carNo, driverName, 'Ceza Uygulandı', param);
              p.penalties = p.penalties || [];
              const penLabel = selectedType === 'time' ? `+${timeSeconds}s` : selectedType.toUpperCase();
              if (!p.penalties.includes(penLabel)) p.penalties.push(penLabel);
              if (onApplied) onApplied();
            }
          }
        ]
      });
    }

    function paintPlayers(list) {
      playersTable.replaceChildren();
      if (!running) {
        playersTable.append(h('div', { class: 'ph', style: { padding: '36px', textAlign: 'center' } },
          ico('car'),
          h('div', { style: { marginTop: '8px', fontWeight: 'bold' } }, 'Sunucu Şu Anda Kapalı'),
          h('div', { class: 'muted', style: { fontSize: '13px', marginTop: '4px' } }, 'Oyuncuları görebilmek ve oyundayken anlık ceza/ban işlemlerini yönetebilmek için sağ üstteki "Başlat" butonuna tıklayın.')
        ));
        return;
      }

      // Ghost filtreleme
      const activeList = (list || []).filter(p => {
        const name = String(p.driver_name || p.name || '').trim();
        return !(name.startsWith('Sürücü #') && !p.steam_id);
      });

      if (!activeList || !activeList.length) {
        playersTable.append(h('div', { class: 'ph', style: { padding: '36px', textAlign: 'center' } },
          ico('car'),
          h('div', { style: { marginTop: '8px', fontWeight: 'bold' } }, 'Şu Anda Bağlı Oyuncu Yok'),
          h('div', { class: 'muted', style: { fontSize: '13px', marginTop: '4px' } }, 'Sunucuya bir sürücü katıldığında Araç No, Sürücü Adı, SteamID, Ceza durumu ve anlık yönetim butonları burada listelenecektir.')
        ));
        return;
      }

      const tb = h('tbody');
      activeList.forEach(p => {
        const carNo = String(p.car_number || p.car_id || p.id || '1');
        const driverName = p.driver_name || p.name || ('Sürücü #' + carNo);
        const steamId = p.steam_id || (p.id && String(p.id) !== carNo ? p.id : '—');
        const carModel = p.car_model || '';
        const isAdmin = Boolean(p.is_admin);

        const hasPenalty = p.penalties && p.penalties.length > 0;
        const penBadge = hasPenalty
          ? h('span', { class: 'pill penalized', style: { cursor: 'pointer' }, title: `Ceza: ${p.penalties.join(', ')}` }, `⚠️ CEZALI: ${p.penalties.join(', ')}`)
          : h('span', { class: 'pill ok', title: 'Ceza kaydı bulunmuyor' }, `🛡️ ${p.state || 'Pistte'} • Ceza Yok`);

        const adminBadge = isAdmin
          ? h('span', { class: 'pill admin', style: { marginLeft: '8px' }, title: 'Sunucu Yöneticisi / Admin Yetkili' }, '👑 Admin')
          : null;

        const btnClearPen = hasPenalty
          ? h('button', {
              class: 'btn sm primary pulse',
              title: `Cezayı anında sil`,
              onclick: async () => {
                try {
                  await api.admin_action(sid, 'del_penalty', carNo, '1');
                  p.penalties = [];
                  paintPlayers(activeList);
                  toast(`Araç #${carNo} (${driverName}) cezası kaldırıldı.`, 'ok');
                } catch(e) { toast(e.message, 'error'); }
              }
            }, ico('check'), 'Cezayı Sil')
          : h('button', {
              class: 'btn sm',
              disabled: true,
              style: { opacity: '0.45' },
              title: 'Sürücünün aktif cezası bulunmuyor'
            }, ico('check'), 'Ceza Yok');

        const btnAddPen = h('button', {
          class: 'btn sm',
          title: `Ceza uygula (Drive-Through, Stop&Go, Süre)`,
          onclick: () => showPenaltyModal(carNo, driverName, p, () => paintPlayers(activeList))
        }, ico('alert'), 'Ceza Ver');

        const btnToPit = h('button', {
          class: 'btn sm',
          title: `Aracı pite ışınla`,
          onclick: () => showCommandActionModal('to_pit', carNo, driverName, 'Aracı Pite Işınla')
        }, 'Pite Işınla');

        const btnToggleAdmin = h('button', {
          class: 'btn sm',
          title: isAdmin ? 'Admin yetkisini geri al' : 'Admin yetkisi ver',
          onclick: async () => {
            try {
              const res = await api.toggle_player_admin(sid, carNo);
              p.is_admin = res.is_admin;
              paintPlayers(activeList);
              toast(`Araç #${carNo} (${driverName}) ${p.is_admin ? 'Admin yapıldı 👑 (entry_list senkronize edildi)' : 'Adminliği kaldırıldı'}`, 'ok');
            } catch (e) {
              toast(e.message, 'error');
            }
          }
        }, ico('shield'), isAdmin ? 'Admin Al' : 'Admin Yap');

        const btnKick = h('button', {
          class: 'btn sm',
          title: `Oyuncuyu sunucudan at`,
          onclick: async () => {
            if (!confirm(`Araç #${carNo} (${driverName}) sunucudan atılsın mı?`)) return;
            try {
              await api.kick_player(sid, carNo, steamId, p.ip || '');
              toast(`Araç #${carNo} (${driverName}) sunucudan atıldı.`, 'ok');
              setTimeout(refreshPlayers, 500);
            } catch(e) { toast(e.message, 'error'); }
          }
        }, ico('x'), 'Kick');

        const btnBan = h('button', {
          class: 'btn sm',
          title: 'Kalıcı Ban (Firewall engeli + Kara liste)',
          style: { color: 'var(--red, #f43f5e)' },
          onclick: async () => {
            if (!confirm(`Sürücü ${driverName} (SteamID: ${steamId}) kalıcı olarak Güvenlik Duvarı ve Kara Liste ile banlansın mı?`)) return;
            try {
              await api.ban_player_host(sid, carNo, steamId, p.ip || '');
              toast(`⛔ ${driverName} banlandı! Güvenlik Duvarı engeli ve kara liste aktif.`, 'ok', 5000);
              setTimeout(refreshPlayers, 500);
            } catch (e) { toast(e.message, 'error'); }
          }
        }, ico('alert'), 'Ban');

        tb.append(h('tr', {},
          h('td', { style: { fontWeight: 'bold', width: '60px' } }, '#' + carNo),
          h('td', {},
            h('div', { style: { display: 'flex', alignItems: 'center' } },
              h('b', {}, driverName),
              adminBadge
            ),
            carModel ? h('div', { class: 'muted', style: { fontSize: '11px', marginTop: '2px' } }, carModel) : null
          ),
          h('td', { class: 'muted', style: { fontFamily: 'monospace', fontSize: '12px' } }, steamId),
          h('td', {}, penBadge),
          h('td', { style: { textAlign: 'right' } },
            h('div', { class: 'row', style: { justifyContent: 'flex-end', gap: '6px' } },
              btnClearPen, btnAddPen, btnToPit, btnToggleAdmin, btnKick, btnBan
            )
          )
        ));
      });

      playersTable.append(h('table', { class: 'tbl' },
        h('thead', {},
          h('tr', {},
            h('th', { style: { width: '60px' } }, 'Araç #'),
            h('th', {}, 'Sürücü Adı & Model'),
            h('th', {}, 'SteamID'),
            h('th', {}, 'Durum / Ceza'),
            h('th', { style: { textAlign: 'right' } }, 'Hızlı Eylemler')
          )
        ),
        tb
      ));
    }

    function paintBlacklist(list) {
      blCard.replaceChildren();
      const inId = h('input', { class: 'in', placeholder: 'Örn: 76561198000000000', style: { flex: '1', minWidth: '220px' } });
      const addBtn = h('button', {
        class: 'btn sm primary',
        onclick: async () => {
          const val = inId.value.trim();
          if (!val) return;
          try {
            const updated = await api.add_blacklist(sid, val);
            inId.value = '';
            toast(`SteamID ${val} kara listeye eklendi.`, 'ok');
            paintBlacklist(updated);
          } catch(e) { toast(e.message, 'error'); }
        }
      }, ico('plus'), 'Kara Listeye Ekle');

      const itemsBox = h('div', { class: 'row wrap', style: { gap: '8px', marginTop: '12px' } });
      if (!list || !list.length) {
        itemsBox.append(h('div', { class: 'muted', style: { fontSize: '13px' } }, 'Kara listede kayıtlı oyuncu yok. Yasaklanan SteamID\'ler Kunos sunucusunun [blacklist] yapılandırmasına kaydedilir ve sunucuya giremez.'));
      } else {
        list.forEach(id => {
          itemsBox.append(h('div', {
            class: 'pill',
            style: { display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '5px 10px', background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.3)' }
          },
            h('span', { style: { fontFamily: 'monospace', fontWeight: 'bold' } }, id),
            h('button', {
              class: 'btn sm icon',
              title: 'Yasağı Kaldır',
              style: { padding: '2px 6px', height: 'auto', border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--red, #f43f5e)' },
              onclick: async () => {
                try {
                  const updated = await api.remove_blacklist(sid, id);
                  toast(`SteamID ${id} yasağı kaldırıldı.`, 'ok');
                  paintBlacklist(updated);
                } catch(e) { toast(e.message, 'error'); }
              }
            }, ico('x'))
          ));
        });
      }

      blCard.append(
        h('h3', {}, 'SteamID Kara Liste (Sunucu Ban Listesi)'),
        h('div', { class: 'hint', style: { marginBottom: '10px' } }, 'Kunos Dedicated Server protokolü tarafından resmi olarak desteklenir. Bu listedeki SteamID\'ler sunucuya bağlanmaya çalıştığında "User is blacklisted" yanıtı alır ve reddedilir.'),
        h('div', { class: 'row', style: { gap: '8px', width: '100%', alignItems: 'center' } }, inId, addBtn),
        itemsBox
      );
    }

    const faqCard = h('div', { class: 'card', style: { marginTop: '20px' } },
      h('h3', {}, 'Admin Ayrıcalıkları & Ceza Yönetimi Rehberi'),
      h('div', { class: 'row', style: { gap: '16px', alignItems: 'flex-start', marginTop: '12px' } },
        h('div', { style: { flex: '1' } },
          h('div', { class: 'note' },
            h('b', {}, '❓ "Admin şifresi ile girdiğimde yine ceza yiyor muyum?"'),
            h('p', { style: { margin: '6px 0 0 0', lineHeight: '1.5' } },
              'Evet! Assetto Corsa EVO Dedicated Server fizik motoru (Track Limits, beyaz çizgiler, pit hızı vb.) admin ayrımı gözetmeksizin pistteki tüm araçlar için çalışır. Ancak ',
              h('b', {}, 'Adminlerin sınırsız müdahale ayrıcalığı vardır:'),
              ' Chat ekranına ', h('code', {}, '/del_penalty <araç_no>'), ' yazarak veya yukarıdaki listeden "Cezayı Sil" butonuna tıklayarak saniyeler içinde kendinizin veya arkadaşınızın cezasını tek hamlede kaldırabilirsiniz!'
            )
          )
        ),
        h('div', { style: { flex: '1' } },
          h('div', { class: 'note ok' },
            h('b', {}, '🎮 Oyun İçi Admin Komutları (Chat Ekranı)'),
            h('ul', { style: { margin: '6px 0 0 16px', padding: '0', fontSize: '13px', lineHeight: '1.6' } },
              h('li', {}, h('code', {}, '/admin <şifre>'), ' — Yönetici yetkisini aktifleştirir'),
              h('li', {}, h('code', {}, '/del_penalty <araç_no>'), ' — Cezayı anında siler'),
              h('li', {}, h('code', {}, '/to_pit <araç_no>'), ' — Aracı pite ışınlar'),
              h('li', {}, h('code', {}, '/ballast <araç_no> <kg>'), ' — Balast (ağırlık) yükler'),
              h('li', {}, h('code', {}, '/kick <araç_no>'), ' — Oyuncuyu sunucudan atar'),
              h('li', {}, h('code', {}, '/ban <araç_no>'), ' — Oyuncuyu banlar')
            )
          )
        )
      )
    );

    refreshPlayers();
    box.append(head, stewardBox, playersTable, blCard, faqCard);
    return box;
  }

  function tabRules() {
    return h('div', { class: 'twocol' },
      h('div', {},
        section('Kural, Pist İhlali ve Ceza Yönetimi (Override)',
          h('div', { class: 'note ok', style: { marginBottom: '14px' } },
            h('b', {}, '⚡ AC EVO Kural ve Ceza Zorlama Sistemi:'),
            h('p', { style: { margin: '4px 0 0 0', fontSize: '12px' } }, 'Resmi başlatıcının izin vermediği kısıtlamalar kaldırılmıştır. Bu ayarlar sunucu motoru (serverconfig / seasondefinition) yapılandırmasına doğrudan zorlanır.')
          ),
          fld('Ters yön sürüş cezası (Ters Şerit İzni)', 'wrong_way_penalty', 'bool', { hint: 'Kapalı tutulduğunda ters şeritte/yönde serbest sürüşe izin verilir; ceza sayacı ve pite atma devre dışı kalır' }),
          fld('Ters yön uyarı sayacı (sn)', 'warning_trigger_countdown', 'int', { hint: 'Ters şeritte sürerken pite atılmadan önceki süre (Ters şerit serbestken otomatik 2.000.000 saniyeye ayarlanır)' }),
          fld('Pist kesme cezaları (Track Limits)', 'penalties', 'bool', { hint: 'Kapalıyken beyaz çizgi ve bordür ihlalleri ceza puanı ve yavaşlama yazmaz' }),
          fld('Pist dışı toleransı (Tekerlek Sayısı)', 'car_cut_tyres_out', 'int', { hint: 'Pist dışı sayılması için gereken tekerlek sayısı (Ceza kapalıyken 10 tekerleğe zorlanır)' }),
          fld('Pit yolu hız kontrolü & Limitör', 'pit_limiter', 'bool', { hint: 'Kapalıyken pitte hız sınırı (60 km/s) aşımında ceza verilmez' }),
          fld('Tuning / Araç Ayarları', 'tuning_type', 'select', { options: [['TuningAllowed', 'İzinli (TuningAllowed)'], ['TuningDenied', 'Yasak (TuningDenied)']], hint: 'Oyuncuların araç ayarlarını değiştirmesine izin verilip verilmeyeceğini belirler' })
        )
      ),
      h('div', {},
        section('Sunucu Performansı & Pit Kuralları',
          fld('Düşük CPU / Headless Modu (GPU Gereksiz)', 'low_cpu_mode', 'bool', { hint: 'Sunucu komut satırına -disable_lpp ve -minimumcores 2 ekler, yazılımsal render zorlar ve işlemci önceliğini optimize eder' }),
          fld('Netcode güncelleme sıklığı (Hz)', 'netcode_update_interval', 'int', { hint: 'Varsayılan: 55. Sunucu ile istemciler arasındaki fizik paket sıklığı' }),
          h('div', { class: 'note', style: { margin: '14px 0 8px 0' } },
            h('b', {}, '🏁 Zorunlu Pit Stop Şartları:'),
            h('p', { style: { margin: '4px 0 0 0', fontSize: '12px' } }, 'Zorunlu pit stop yalnızca Race Weekend modunda ve yarış süresi 20 dakikadan (1200 sn) uzun olduğunda geçerlidir.')
          ),
          fld('Zorunlu pit stop', 'mandatory_pitstop', 'bool'),
          fld('Lastik değişimi zorunlu', 'mandatory_pitstop_tyre_change', 'bool'),
          fld('Yakıt ikmali zorunlu', 'mandatory_pitstop_refuel', 'bool'),
          fld('Pit penceresi (sn)', 'pit_window_time', 'int', { hint: 'Yarış süresini aşarsa otomatik kırpılır' })
        )
      )
    );
  }

  function tabAdvanced() {
    return h('div', { class: 'twocol' }, h('div', {},
      section('Ağ ve denge', fld('Netcode güncelleme aralığı', 'netcode_update_interval', 'int'), fld('En düşük PI', 'pi_min', 'float', { hint: '0 = sınırsız' }), fld('En yüksek PI', 'pi_max', 'float', { hint: '0 = sınırsız' })),
      section('Entry list ve sonuçlar', fld('Entry list sunucu adresi', 'entry_list_server_url'), fld('Token', 'token'), fld('Entry list dosyası', 'entry_list_path'), fld('Sonuç gönderme adresi', 'results_post_url'), fld('Sonuç klasörü', 'results_path'), fld('Sonuçları JSON dışa aktar', 'export_json', 'bool')),
      section('Başlatma', fld('Ayrı CMD konsol penceresi göster', 'show_console_window', 'bool', { hint: 'Sunucu başlatıldığında Windows komut satırı penceresini de görünür açar' }), fld('Log dosyası', 'log_file_path'), fld('Ek başlatma argümanları', 'extra_arguments'), fld('Özel komut', 'custom_command', 'text', { hint: 'Doluysa uygulamanın ürettiği komutun yerine geçer' }),
        h('div', { class: 'field' }, h('label', {}, 'Çalıştırılacak komut'), h('button', { class: 'btn sm', onclick: showCmd }, ico('term'), 'Komutu göster')))),
      h('div', {}, section('Ham ek ayarlar (ileri düzey)',
        h('div', { class: 'note', style: { margin: '14px 0' } }, 'Sunucu yeni bir ayar kazanırsa burada JSON olarak ekleyebilirsiniz; uygulamanın ürettiği yapıya birleştirilir. Bilmediğiniz anahtarları eklemeyin, sunucu hata verebilir.'),
        fld('serverconfig ek ayarları', 'serverconfig_extra', 'area', { hint: 'Örnek: {"max_players": 12}' }), fld('seasondefinition ek ayarları', 'seasondefinition_extra', 'area', { hint: 'Örnek: {"game_config": {"practice_duration": 900}}' }))));
  }
  async function showCmd() { if (!(await save(true))) return; try { const cmd = await api.command_preview(sid); modal({ title: 'Başlatma komutu', body: h('div', { class: 'logbox', style: { maxHeight: '260px' } }, cmd), actions: [{ label: 'Kopyala', keep: true, onClick: () => { navigator.clipboard.writeText(cmd); toast('Kopyalandı', 'ok'); } }, { label: 'Kapat', kind: 'primary' }] }); } catch (e) { toast(e.message, 'error'); } }
  function tabResults() {
    const box = h('div', { class: 'card' }, h('div', { class: 'muted' }, 'Yükleniyor…'));
    api.results(sid).then(list => { box.replaceChildren(); if (!list.length) { box.append(h('div', { class: 'muted', style: { padding: '30px', textAlign: 'center' } }, 'Henüz sonuç dosyası yok. Oturumlar bittikçe burada listelenir.')); return; }
      list.forEach(f => box.append(h('div', { class: 'field', style: { gridTemplateColumns: '1fr auto auto' } }, h('b', {}, f.name), h('span', { class: 'muted' }, `${f.modified} · ${fmtSize(f.size)}`), h('button', { class: 'btn sm', onclick: () => api.open_path(f.path) }, 'Aç')))); });
    return h('div', {}, h('div', { class: 'cbar' }, h('button', { class: 'btn sm', onclick: () => api.open_results_dir(sid) }, ico('folder'), 'Klasörü aç')), box);
  }

  /* ---- sayfa iskeleti ---- */
  const folderBtn = h('button', { class: 'btn', title: 'Sunucu klasörünü aç', onclick: () => api.open_server_folder(sid) }, ico('folder'), 'Klasör');
  const shareBtn = h('button', { class: 'btn', title: 'Topluluk Paylaşım & Discord Kartı', onclick: () => showShareModal(sid) }, ico('share'), 'Paylaş');
  const simLabBtn = h('button', { class: 'btn', title: 'SimLab Hazır Senaryolar', onclick: () => showPresetsModal(sid) }, ico('trophy'), 'SimLab Senaryoları');
  page.append(h('div', { class: 'pagehead' },
    h('div', {},
      h('div', { class: 'row', style: { marginBottom: '8px' } }, h('button', { class: 'btn sm', onclick: () => go('servers') }, '← Sunucular')),
      h('div', { class: 'row' }, h('h1', {}, F.name), statusPill, statusExtra, autoSaveBadge)
    ),
    h('div', { class: 'row' }, simLabBtn, shareBtn, folderBtn, restartBtn, runBtn)
  ), tabsEl, body);
  paintRun(); switchTab(tab); await pollConsole();

  const timer = setInterval(pollConsole, 500);
  S.cleanup = () => { clearInterval(timer); if (dirty) save(true); };
}

/* ============================ MODALLER: PAYLAŞIM & SİM-LAB ============================ */
async function showShareModal(sid) {
  try {
    const card = await api.get_server_share_card(sid);
    const body = h('div', { class: 'share-box' },
      h('div', { html: card.svg_card, style: { width: '100%', marginBottom: '6px' } }),
      h('div', { class: 'field' },
        h('label', {}, 'Steam Doğrudan Bağlantı'),
        h('div', { class: 'row' },
          h('input', { class: 'in', readonly: true, value: card.steam_url }),
          h('button', { class: 'btn sm', onclick: () => { navigator.clipboard.writeText(card.steam_url); toast('Steam katılım linki kopyalandı', 'ok'); } }, ico('copy'), 'Kopyala')
        )
      ),
      h('div', { class: 'field' },
        h('label', {}, 'Discord Paylaşım Metni'),
        h('div', { style: { width: '100%' } },
          h('div', { class: 'discord-preview' }, card.discord_markdown),
          h('div', { style: { marginTop: '8px', display: 'flex', justifyContent: 'flex-end' } },
            h('button', { class: 'btn sm primary', onclick: () => { navigator.clipboard.writeText(card.discord_markdown); toast('Discord metni panoya kopyalandı!', 'ok'); } }, ico('copy'), 'Discord Formatında Kopyala')
          )
        )
      )
    );
    modal({ title: 'Topluluk Paylaşım Kartı & Katılım Kodu', sub: card.server_name, body, actions: [{ label: 'Kapat', kind: 'primary' }] });
  } catch (e) {
    toast('Paylaşım kartı üretilemedi: ' + e.message, 'error');
  }
}

async function showPresetsModal(sid) {
  try {
    const list = await api.list_presets();
    const grid = h('div', { class: 'preset-grid' });
    const m = modal({
      title: '🏁 SimLab Senaryo & Hazır Şablon Yöneticisi',
      sub: 'Tek tıkla hazır bir yarış disiplinini uygulayın veya mevcut ayarlarınızı özel şablon olarak kaydedin.',
      body: h('div', {},
        h('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' } },
          h('b', {}, 'Kullanılabilir Senaryolar'),
          h('button', { class: 'btn sm primary', onclick: () => saveCustomPresetModal(sid, () => { m.close(); showPresetsModal(sid); }) }, ico('plus'), 'Mevcut Ayarları Şablon Yap')
        ),
        grid
      ),
      actions: [{ label: 'Kapat' }]
    });

    list.forEach(p => {
      const card = h('div', { class: 'preset-card' },
        h('div', { class: 'phead' },
          h('div', {},
            h('span', { class: 'pill cyan', style: { marginBottom: '6px' } }, p.badge || '🏁'),
            h('h4', {}, p.name)
          ),
          p.custom ? h('button', { class: 'btn icon danger sm', title: 'Şablonu sil', onclick: async (e) => {
            e.stopPropagation();
            if (await confirmBox('Şablonu Sil', `'${p.name}' özel şablonunu silmek istiyor musunuz?`)) {
              await api.delete_custom_preset(p.id);
              m.close();
              showPresetsModal(sid);
            }
          } }, ico('trash')) : null
        ),
        h('p', {}, p.description),
        h('button', { class: 'btn primary sm', style: { width: '100%', marginTop: 'auto' }, onclick: async () => {
          try {
            const res = await api.apply_preset(sid, p.id);
            toast(`'${res.name}' senaryosu başarıyla uygulandı!`, 'ok', 5000);
            m.close();
            go('server', { sid, tab: 'Genel' });
          } catch(err) {
            toast('Şablon uygulanamadı: ' + err.message, 'error');
          }
        } }, ico('check'), 'Senaryoyu Uygula')
      );
      grid.append(card);
    });
  } catch (e) {
    toast('Senaryolar yüklenemedi: ' + e.message, 'error');
  }
}

function saveCustomPresetModal(sid, onSaved) {
  const nameIn = h('input', { class: 'in', placeholder: 'Örn: Cuma Gecesi Drift Ligi' });
  const descIn = h('textarea', { class: 'ta', placeholder: 'Senaryo açıklaması...', style: { minHeight: '80px' } });
  modal({
    title: 'Mevcut Ayarları Özel Şablon Olarak Kaydet',
    sub: 'Bu sunucunun tüm pist, hava, kural ve oturum ayarları yeni bir şablon olarak saklanır.',
    body: h('div', {},
      h('div', { class: 'field' }, h('label', {}, 'Şablon Adı'), nameIn),
      h('div', { class: 'field' }, h('label', {}, 'Açıklama'), descIn)
    ),
    actions: [
      { label: 'Vazgeç' },
      { label: 'Kaydet', kind: 'primary', onClick: async () => {
        if (!nameIn.value.trim()) { toast('Lütfen bir şablon adı girin', 'error'); return false; }
        try {
          await api.save_custom_preset(sid, nameIn.value, descIn.value);
          toast('Özel şablon kaydedildi!', 'ok');
          onSaved && onSaved();
          return true;
        } catch(e) {
          toast(e.message, 'error');
          return false;
        }
      } }
    ]
  });
}

