/* İlk kurulum sihirbazı ve ayarlar sayfası */

/* Dedicated Server'ı SteamCMD ile indirme akışı (kurulum ve ayarlar paylaşır) */
function steamInstallModal(defaults, onDone) {
  const user = textIn(defaults.steam_user || ''), pass = h('input', { class: 'in', type: 'password' }), guard = textIn('');
  const body = h('div', {},
    h('div', { class: 'note', style: { marginBottom: '14px' } }, 'Dedicated Server, Kunos\'un dosyalarıdır; uygulamaya gömülemez. Steam\'den, Assetto Corsa EVO\'ya sahip hesapla indirilir. Şifreniz hiçbir yere kaydedilmez, yalnızca SteamCMD\'e iletilir.'),
    field('Steam kullanıcı adı', user, 'E-posta değil, hesap adı'), field('Şifre', pass), field('Steam Guard kodu', guard, 'Varsa; ilk denemede istenirse sonra girin'));
  modal({ title: 'Steam\'den Dedicated Server indir', sub: 'SteamCMD otomatik indirilir ve kullanılır', body, actions: [{ label: 'Vazgeç' }, { label: 'İndir ve kur', kind: 'primary', onClick: async (e, { close }) => {
    if (!user.value.trim() || !pass.value) { toast('Kullanıcı adı ve şifre gerekli', 'error'); return false; }
    close();
    try { const path = await jobModal('Dedicated Server indiriliyor', () => api.install_dedicated(user.value, pass.value, guard.value), { cancelable: true }); toast('Dedicated Server kuruldu', 'ok'); onDone(path); }
    catch (err) { toast(err.message, 'error', 9000); if (err.code === 'need_guard') setTimeout(() => steamInstallModal({ steam_user: user.value }, onDone), 400); }
    return false; } }] });
}

async function pageSetup(view) {
  const page = h('div', { class: 'page setup' }); view.append(page);
  const st = { step: 0, server: '', mods: '', smods: '', mirror: true };
  const def = await api.default_roots();
  st.server = def.server_path; st.mods = def.mods_root; st.smods = def.server_mods_root;
  const body = h('div', {}), steps = h('div', { class: 'steps' }, [0, 1, 2, 3].map(() => h('i')));
  page.append(steps, body);
  const nav = (back, next, nextLabel, nextOk = true) => h('div', { class: 'row', style: { justifyContent: 'space-between', marginTop: '26px' } },
    back ? h('button', { class: 'btn', onclick: back }, '← Geri') : h('span'), h('button', { class: 'btn primary', disabled: !nextOk, onclick: next }, nextLabel));
  async function paint() {
    $$('i', steps).forEach((e, i) => e.classList.toggle('on', i <= st.step)); body.replaceChildren(); body.className = 'fadein';
    if (st.step === 0) {
      body.append(h('div', { class: 'hero' }, h('div', { style: { fontSize: '46px', marginBottom: '14px' } }, '🏁'), h('h1', {}, 'EVOX Server Manager\'a hoş geldiniz'),
        h('p', {}, 'Assetto Corsa EVO sunucularınızı tek pencereden kurun, başlatın ve canlı konsoldan izleyin. Pist ve araç modlarını sürükleyip bırakarak kurun. Tarayıcı, şifre ya da ek kurulum gerekmez.')),
        h('div', { class: 'grid wide', style: { marginTop: '26px' } }, [['⚡', 'Hızlı kurulum', 'Dedicated Server\'ı bulur ya da indirir'], ['📦', 'Mod desteği', 'Sürükle, bırak, kurulsun'], ['🖥️', 'Canlı konsol', 'Hataları anlaşılır şekilde gösterir']].map(([i, t, d]) => h('div', { class: 'card' }, h('div', { style: { fontSize: '26px' } }, i), h('b', { style: { display: 'block', margin: '8px 0 3px' } }, t), h('span', { class: 'muted' }, d)))),
        nav(null, () => { st.step = 1; paint(); }, 'Başlayalım →'));
    } else if (st.step === 1) {
      let found = []; try { found = await api.detect_servers(); } catch (e) { /* yoksay */ }
      let bundled = { ok: false }; try { bundled = await api.bundled_server_status(); } catch (e) { /* yoksay */ }
      
      let valid = st.server ? await api.validate_server_path(st.server) : { ok: false, message: '' };
      // Geçerli bir yol seçili değilse gömülü veya bulunan sunucuyu otomatik seç
      if (!valid.ok) {
        if (bundled.ok) {
          st.server = bundled.path;
          valid = await api.validate_server_path(st.server);
        } else if (found.length) {
          st.server = found[0];
          valid = await api.validate_server_path(st.server);
        }
      }

      const opt = (path, title, desc, icon, badge) => h('div', { class: 'opt ' + (st.server === path ? 'sel' : ''), onclick: () => { st.server = path; paint(); } },
        h('div', { class: 'oi' }, icon),
        h('div', { class: 'grow' },
          h('div', { class: 'row', style: { justifyContent: 'space-between' } },
            h('b', {}, title),
            badge ? h('span', { class: 'pill on', style: { fontSize: '11px', padding: '2px 8px' } }, badge) : null
          ),
          h('span', {}, desc)
        )
      );

      const scanBtn = h('button', { class: 'btn primary sm', onclick: async (e) => {
        const btn = e.currentTarget; btn.disabled = true;
        toast('Dedicated Server taranıyor…', 'info', 2000);
        try {
          const freshFound = await api.detect_servers();
          const freshBundled = await api.bundled_server_status();
          if (freshBundled.ok) {
            st.server = freshBundled.path;
            toast('Uygulamaya gömülü Dedicated Server algılandı ve seçildi!', 'ok', 4000);
          } else if (freshFound.length) {
            st.server = freshFound[0];
            toast('Dedicated Server başarıyla algılandı ve seçildi: ' + freshFound[0], 'ok', 4000);
          } else {
            toast('Otomatik aramayla Dedicated Server bulunamadı. Lütfen klasörü elle seçin veya Steam\'den kurun.', 'warn', 5000);
          }
        } finally {
          btn.disabled = false;
          await paint();
        }
      } }, ico('refresh'), 'Yeniden Tara ve Otomatik Algıla');

      body.append(
        h('div', { class: 'hero' },
          h('h1', {}, 'Dedicated Server'),
          h('p', {}, 'Sunucu dosyalarının bulunduğu klasör. İster uygulamaya gömülü sürümü kullanın, ister Steam kurulumunuzu seçin.')
        ),
        h('div', { class: 'row', style: { marginTop: '18px', marginBottom: '14px', justifyContent: 'space-between', alignItems: 'center' } },
          h('span', { class: 'muted', style: { fontSize: '13px' } }, 'Kullanmak istediğiniz sunucu kaynağını seçin:'),
          scanBtn
        ),
        h('div', { style: { marginTop: '8px' } },
          bundled.ok ? opt(bundled.path, 'Uygulamaya gömülü sürüm', 'Uygulama ile birlikte gelen Dedicated Server. Harici indirme veya Steam gerektirmez.', '📦', 'Hızlı / Bağımsız Kurulum (Gömülü)') : null,
          found.map(p => opt(p, 'Bulunan Steam Kurulumu', p, '✅', 'Tavsiye Edilen (Steam)')),
          h('div', { class: 'opt', onclick: () => steamInstallModal(def, p => { st.server = p; paint(); }) },
            h('div', { class: 'oi' }, '☁️'),
            h('div', {}, h('b', {}, 'Steam\'den otomatik indir ve kur'), h('span', {}, 'SteamCMD ile indirilir; Steam hesabınız gerekir (EVO\'ya sahip olmalı).'))
          ),
          h('div', { class: 'opt', onclick: async () => { const p = await api.pick_folder('Dedicated Server klasörünü seçin'); if (p) { st.server = p; paint(); } } },
            h('div', { class: 'oi' }, '📁'),
            h('div', {}, h('b', {}, 'Klasörü ben seçeyim'), h('span', {}, 'İçinde AssettoCorsaEVOServer.exe olan özel bir klasör seçin'))
          )
        ),
        st.server ? h('div', { class: 'note ' + (valid.ok ? '' : 'warn'), style: { marginTop: '16px' } },
          (valid.ok ? '✔ ' : '✖ ') + valid.message,
          h('br'),
          h('small', {}, st.server)
        ) : null,
        nav(() => { st.step = 0; paint(); }, () => { st.step = 2; paint(); }, 'Devam →', valid.ok)
      );
    } else if (st.step === 2) {
      const row = (label, key, hint) => {
        const i = textIn(st[key]);
        i.style.flex = '1';
        i.style.minWidth = '0';
        i.oninput = () => st[key] = i.value;
        return field(label, h('div', { class: 'row', style: { width: '100%', gap: '8px' } },
          i,
          h('button', { class: 'btn sm', onclick: async () => { const p = await api.pick_folder(label); if (p) { st[key] = p; paint(); } } }, 'Gözat')
        ), hint);
      };
      const mir = h('input', { type: 'checkbox' }); mir.checked = st.mirror; mir.onchange = () => st.mirror = mir.checked;
      body.append(h('div', { class: 'hero' }, h('h1', {}, 'Mod klasörleri'), h('p', {}, 'Oyun ve Dedicated Server modları ayrı kullanıcı klasörlerinden okur. Uygulama her ikisini de yönetir; klasörler yoksa oluşturulur, elle bir şey yapmanız gerekmez.')),
        h('div', { class: 'card', style: { marginTop: '22px' } }, row('Oyun mod klasörü', 'mods', 'Varsayılan: Saved Games\\ACE\\mods'), row('Sunucu mod klasörü', 'smods', 'Varsayılan: Saved Games\\ACE-Server\\mods'),
          field('Modları sunucuya da kur', h('label', { class: 'switch' }, mir, h('span')), 'Önerilir: sunucu pisti kendi klasöründe bulamazsa çöker')),
        nav(() => { st.step = 1; paint(); }, () => { st.step = 3; paint(); }, 'Devam →'));
    } else {
      body.append(h('div', { class: 'hero' }, h('div', { style: { fontSize: '46px', marginBottom: '14px' } }, '🚀'), h('h1', {}, 'Her şey hazır'), h('p', {}, 'İlk sunucunuzu oluşturup başlatabilirsiniz.')),
        h('div', { class: 'card', style: { marginTop: '22px' } }, h('dl', { class: 'kv' }, h('dt', {}, 'Dedicated Server'), h('dd', {}, st.server), h('dt', {}, 'Oyun mod klasörü'), h('dd', {}, st.mods), h('dt', {}, 'Sunucu mod klasörü'), h('dd', {}, st.smods))),
        nav(() => { st.step = 2; paint(); }, async () => { try { await api.save_settings({ mirror_mods_to_server: st.mirror }); await api.finish_setup(st.server, st.mods, st.smods); await bootApp(); go('servers'); } catch (e) { toast(e.message, 'error'); } }, 'Başla ✓'));
    }
  }
  await paint();
}

async function pageSettings(view) {
  const page = h('div', { class: 'page' }); view.append(page);
  const v = await api.get_settings(), st = { ...v };

  let autoSaveTimer = null;
  const autoSaveBadge = h('span', { class: 'pill ok', style: { transition: 'all 0.3s', fontSize: '12px', padding: '4px 10px', display: 'inline-flex', alignItems: 'center', gap: '5px' } }, ico('check'), 'Ayarlar güncel');

  function scheduleAutoSave() {
    autoSaveBadge.className = 'pill warn';
    autoSaveBadge.replaceChildren(ico('refresh'), 'Kaydediliyor…');
    if (autoSaveTimer) clearTimeout(autoSaveTimer);
    autoSaveTimer = setTimeout(async () => {
      try {
        await api.save_settings(st);
        autoSaveBadge.className = 'pill ok';
        autoSaveBadge.replaceChildren(ico('check'), 'Otomatik kaydedildi');
        setTimeout(() => {
          autoSaveBadge.className = 'pill ok';
          autoSaveBadge.replaceChildren(ico('check'), 'Ayarlar güncel');
        }, 2000);
      } catch (e) {
        autoSaveBadge.className = 'pill warn';
        autoSaveBadge.replaceChildren(ico('alert'), 'Kaydedilemedi');
      }
    }, 400);
  }

  const bind = (key, num) => {
    const i = textIn(st[key], { num });
    i.oninput = () => { st[key] = num ? Number(i.value) : i.value; scheduleAutoSave(); };
    return i;
  };
  const sw = (key) => {
    const i = h('input', { type: 'checkbox', onchange: () => { st[key] = i.checked; scheduleAutoSave(); } });
    i.checked = !!st[key];
    return h('label', { class: 'switch' }, i, h('span'));
  };
  const pathRow = (key) => {
    const i = bind(key);
    i.style.flex = '1';
    i.style.minWidth = '0';
    return h('div', { class: 'row', style: { width: '100%', gap: '8px', alignItems: 'center' } },
      i,
      h('button', { class: 'btn sm', title: 'Klasör seç', onclick: async () => { const p = await api.pick_folder('Klasör seçin'); if (p) { st[key] = p; i.value = p; scheduleAutoSave(); } } }, ico('folder'), 'Gözat'),
      h('button', { class: 'btn sm icon', title: 'Dosya Gezgininde Aç', onclick: () => { if (st[key]) api.open_folder(st[key]); } }, ico('folder'))
    );
  };
  const valid = st.evo_server_path ? await api.validate_server_path(st.evo_server_path) : { ok: false, message: 'Seçilmedi' };
  async function save() { try { await api.save_settings(st); toast('Ayarlar kaydedildi', 'ok'); } catch (e) { toast(e.message, 'error'); } }

  const verCard = h('div', { class: 'card', style: { marginBottom: '14px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.08)' } });
  function paintVer(info) {
    verCard.replaceChildren();
    if (!info) return;
    const isBundled = !!info.is_bundled;
    const isUpToDate = !info.update_available;
    const statusPill = isBundled
      ? h('span', { class: 'pill', style: { background: 'rgba(56, 189, 248, 0.15)', color: 'var(--cyan, #38bdf8)' } }, '📦 Gömülü Sürüm (Sabit & Bağımsız)')
      : (isUpToDate
        ? h('span', { class: 'pill ok' }, '✔ Sürüm Güncel')
        : h('span', { class: 'pill bad' }, '⚠️ Güncelleme Mevcut!'));

    const checkBtn = h('button', {
      class: 'btn sm',
      title: 'Steam üzerinden en son sürümü denetle',
      onclick: async () => {
        try {
          const fresh = await api.check_server_version();
          paintVer(fresh);
          toast(fresh.update_available ? 'Steam üzerinde yeni bir sürüm tespit edildi!' : 'Dedicated Server sürümü güncel.', fresh.update_available ? 'warn' : 'ok');
        } catch(e) {
          toast('Sürüm denetlenemedi: ' + e.message, 'error');
        }
      }
    }, ico('refresh'), 'Sürümü Denetle');

    const updateNotice = (!isBundled && info.update_available) ? h('div', {
      class: 'note warn',
      style: { marginTop: '10px', fontSize: '13px', lineHeight: '1.5' }
    },
      h('b', {}, '⚠️ Yeni Assetto Corsa EVO Dedicated Server Güncellemesi Tespit Edildi!'),
      h('p', { style: { margin: '4px 0 0 0' } },
        `Steam'deki en yeni Build: `, h('code', {}, info.latest_buildid || '—'),
        ` (Mevcut: `, h('code', {}, info.local_buildid || '—'), `). `,
        `Sunucunuzun sorunsuz çalışması için lütfen Steam kütüphanenizden Dedicated Server'ı güncelleyin veya aşağıdaki "Steam'den indir / güncelle" butonunu kullanın.`
      )
    ) : null;

    verCard.append(
      h('div', { class: 'row', style: { justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' } },
        h('b', { style: { fontSize: '14px' } }, 'Dedicated Server Sürüm Durumu'),
        h('div', { class: 'row', style: { gap: '8px' } }, statusPill, checkBtn)
      ),
      h('div', { class: 'row wrap', style: { gap: '16px', fontSize: '13px', color: 'var(--muted)' } },
        h('span', {}, 'Kaynak: ', h('b', { style: { color: 'var(--text)' } }, info.source_type || '—')),
        h('span', {}, 'Program Sürümü: ', h('b', { style: { color: 'var(--text)' } }, info.binary_version || '0.9.1')),
        info.local_buildid ? h('span', {}, 'Steam Build ID: ', h('b', { style: { color: 'var(--text)' } }, info.local_buildid)) : null
      ),
      updateNotice
    );
  }
  api.check_server_version().then(paintVer).catch(() => {});
  
  page.append(h('div', { class: 'pagehead' },
    h('div', {},
      h('div', { class: 'row', style: { gap: '10px', alignItems: 'center' } },
        h('h1', {}, 'Ayarlar'),
        autoSaveBadge
      ),
      h('p', {}, 'Klasörler ve uygulama davranışı (Değişiklikler anında otomatik kaydedilir)')
    ),
    h('button', { class: 'btn primary', onclick: save }, ico('check'), 'Kaydet')
  ),
    h('div', { class: 'twocol' }, h('div', {},
      h('div', { class: 'section' }, h('h3', {}, 'Dedicated Server Dosyaları'),
        verCard,
        h('div', { class: 'card' },
        field('Sunucu Ana Klasörü', pathRow('evo_server_path'), (valid.ok ? '✔ ' : '✖ ') + valid.message),
        h('div', { class: 'row wrap', style: { padding: '12px 0 8px', gap: '8px' } },
          h('button', { class: 'btn sm primary', onclick: async () => {
            try {
              const res = await api.auto_detect_and_apply_server();
              st.evo_server_path = res.path;
              await save();
              toast(res.message, 'ok', 6000);
              go('settings');
            } catch (e) { toast(e.message, 'error'); }
          } }, ico('search'), 'Dedicated Server\'ı Otomatik Algıla ve Onayla'),
          h('button', { class: 'btn sm', onclick: async () => {
            try {
              const p = await api.use_bundled_server();
              st.evo_server_path = p;
              await save();
              toast('Gömülü Dedicated Server aktif edildi', 'ok');
              go('settings');
            } catch (e) { toast(e.message, 'error'); }
          } }, ico('box'), 'Gömülü sunucuyu kullan (Hızlı Kurulum)'),
          h('button', { class: 'btn sm', onclick: async () => {
            try {
              await jobModal('Gömülü sunucu güncelleniyor', () => api.update_bundled_server());
              toast('Gömülü sunucu dosyaları güncellendi', 'ok');
            } catch (e) { toast(e.message, 'error'); }
          } }, ico('refresh'), 'Gömülü sunucuyu güncelle'),
          h('button', { class: 'btn sm', onclick: () => steamInstallModal(st, async p => { st.evo_server_path = p; await save(); go('settings'); }) }, ico('cloud'), 'Steam\'den indir / güncelle'),
          h('button', { class: 'btn sm', onclick: async () => { try { await save(); await jobModal('Sunucu dosyaları güncelleniyor', () => api.sync_servers()); toast('Sunucular güncellendi', 'ok'); } catch (e) { toast(e.message, 'error'); } } }, ico('refresh'), 'Mevcut sunucuları güncelle')))),
      h('div', { class: 'section' }, h('h3', {}, 'Mod klasörleri'), h('div', { class: 'card' }, field('Oyun mod klasörü', pathRow('mods_root')), field('Sunucu mod klasörü', pathRow('server_mods_root')), field('Modları sunucuya da kur', sw('mirror_mods_to_server'), 'Sunucu kendi kullanıcı klasöründen okur')))),
      h('div', {}, h('div', { class: 'section' }, h('h3', {}, 'Davranış'), h('div', { class: 'card' }, field('Çöken sunucuyu yeniden başlat', sw('auto_restart')), field('10 dakikada en fazla', bind('auto_restart_max', true), 'Yeniden başlatma sayısı sınırı'), field('Mod pist/araçlarını sunucu listelerine ekle', sw('inject_mod_events'), 'Sunucu dosyalarına yedek alınarak eklenir'))),
        h('div', { class: 'section' }, h('h3', {}, 'Uygulama'), h('div', { class: 'card' }, field('Sürüm', h('span', {}, S.boot.app + ' ' + S.boot.version)), field('Kurulum sihirbazı', h('button', { class: 'btn sm', onclick: () => go('setup') }, 'Yeniden çalıştır')))))));
}
