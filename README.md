# Apex Server Manager 3.0

Assetto Corsa EVO Dedicated Server için tek pencereli yönetim uygulaması (tarayıcı, port, şifre yok).

## EXE oluşturma
1. Python 3.11 veya 3.12 kurun (kurulumda **Add python.exe to PATH** işaretli olsun).
2. `build_exe.bat` dosyasına çift tıklayın.
3. Sonuç: `dist\Apex Server Manager.exe` (tek dosya, simgeli).

Gereksinim: Windows 10/11 + WebView2 Runtime (Windows 11'de ve Edge kuruluysa hazırdır).

## İlk açılış
Sihirbaz: Dedicated Server (Steam'de otomatik bulunur / Steam'den indirilir / klasör seçilir) ve mod klasörleri.

## Mod kurma
Modu pencereye sürükleyip bırakın → sağ altta algılama kartı çıkar → **Kur**.
Mod hem oyunun (`Saved Games\ACE\mods`) hem sunucunun (`Saved Games\ACE-Server\mods`) klasörüne kurulur.
Pist adı/layout emin değilseniz: Modlar > **Pist testi** doğru kombinasyonu otomatik bulur.

## Sunucu çökerse
Konsol sekmesi hatayı anlaşılır bir uyarıyla açıklar (örn. "Sunucu seçilen pisti bulamadı").
