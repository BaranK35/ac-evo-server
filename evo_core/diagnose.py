"""Konsol çıktısını okuyup bilinen sorunları anlaşılır Türkçe açıklamalara çevirir."""
from __future__ import annotations

import re

RULES = [
    (re.compile(r"empty path", re.I), "error", "Sunucu seçilen pisti/içeriği bulamadı",
     "Genelde mod sunucunun kendi klasöründe (Saved Games\\ACE-Server\\mods) yoktur ya da pist adı/layout yanlıştır. "
     "Modlar sayfasında modu 'Sunucuya eşitle' yapın veya 'Pist Testi' ile doğru adı otomatik bulun.", "mods"),
    (re.compile(r"Failed to find file:\s*\"([^\"]+)\"", re.I), "error", "Eksik Sunucu / Mod Dosyası",
     "Sunucu gerekli bir dosya veya kaplama tablosunu bulamadı ({0}). "
     "Sunucu klasörünün eksiksiz olduğundan veya modun sunucuya eşitlendiğinden emin olun.", "mods"),
    (re.compile(r"address already in use|bind.*fail|port.*(in use|kullan)|WSAEADDRINUSE", re.I), "error",
     "Port başka bir uygulama tarafından kullanılıyor", "Genel sekmesinden TCP/UDP/HTTP portlarını değiştirin "
     "ya da aynı portu kullanan diğer sunucuyu durdurun.", "general"),
    (re.compile(r"WSAEACCES|Permission denied", re.I), "error", "Port Erişim Yetkisi Hatası",
     "Seçilen port sistem veya güvenlik duvarı tarafından engellendi. Uygulamayı yönetici olarak çalıştırmayı veya port numarasını değiştirmeyi deneyin.", "firewall"),
    (re.compile(r"Server can't be reached by UDP messages", re.I), "error",
     "UDP Portuna Dışarıdan Erişilemedi (Kunos Lobi Doğrulaması)",
     "Kunos lobi sunucusu, sunucunuzun UDP portuna dışarıdan erişemediği için oturumu kapattı. "
     "Lütfen modeminizden UDP portunun (varsayılan 9700) yönlendirildiğinden ve Windows Güvenlik Duvarı'nın bu porta izin verdiğinden emin olun.", "firewall"),
    (re.compile(r"JSON.*(?:parse|syntax|error)|failed to parse json", re.I), "error",
     "Ayar Dosyası Ayrıştırma Hatası",
     "Sunucunun yapılandırma veya etkinlik (events) dosyalarından biri bozuk ya da geçersiz JSON içeriyor. Ayarlar > 'Sunucu dosyalarını güncelle' seçeneğini deneyin.", "general"),
    (re.compile(r"CRASH DETECTED"), "error", "Sunucu çöktü",
     "Çöküş dökümü Saved Games\\ACE-Server\\crashdumps klasörüne yazıldı. Yukarıdaki hata satırları nedeni gösterir.", None),
    (re.compile(r"steam.*(init|not running|failed)|SteamAPI", re.I), "warn", "Steam ile ilgili uyarı",
     "Steam istemcisinin açık ve hesabınızın oturum açmış olması gerekebilir.", None),
    (re.compile(r"packet.*(?:size.*exceed|corrupt|overflow)", re.I), "warn", "Ağ Paketi Boyut Uyarısı",
     "Ağ paket boyutu sınırları aştı veya bozuldu. Ağ gecikmesini (ping) ve netcode güncelleme aralığını kontrol edin.", "general"),
    (re.compile(r"can't be loaded into SeasonDefinition", re.I), "info", "Zararsız bir mesaj",
     "'practice.seasondefinition' satırı normal sunucu açılışında da görülür; hata değildir.", None),
]


def diagnose(lines: list[str]) -> list[dict]:
    text = "\n".join(lines[-400:])
    found, seen = [], set()
    for pattern, level, title, detail, action in RULES:
        if title in seen:
            continue
        m = pattern.search(text)
        if not m or not detail:
            continue
        seen.add(title)
        if "{" in detail and m.groups():
            try:
                formatted_detail = detail.format(*m.groups())
            except Exception:
                formatted_detail = detail
        else:
            formatted_detail = detail
        found.append({"level": level, "title": title, "detail": formatted_detail, "action": action})
    order = {"error": 0, "warn": 1, "info": 2}
    return sorted(found, key=lambda f: order[f["level"]])
