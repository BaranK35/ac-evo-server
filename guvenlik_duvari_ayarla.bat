@echo off
chcp 65001 >nul
echo ========================================================
echo   Assetto Corsa EVO - Kalici Guvenlik Duvari Kurulumu
echo ========================================================
echo.

:: Eski kurallari temizle
netsh advfirewall firewall delete rule name="AC EVO Server Executable" >nul 2>&1
netsh advfirewall firewall delete rule name="AC EVO Dedicated Ports TCP" >nul 2>&1
netsh advfirewall firewall delete rule name="AC EVO Dedicated Ports UDP" >nul 2>&1
netsh advfirewall firewall delete rule name="AC EVO Dedicated Ports HTTP" >nul 2>&1

:: Program kurallari (Tum ag profilleri: Domain, Private, Public)
echo 1. Sunucu calistirilabilir dosyasina izin veriliyor...
netsh advfirewall firewall add rule name="AC EVO Server Executable" dir=in action=allow program="%LOCALAPPDATA%\EVO Server Manager\servers\server_1\AssettoCorsaEVOServer.exe" enable=yes profile=any

:: Port kurallari (TCP ve UDP - 9700-9710, HTTP 8080-8090)
echo 2. TCP ve UDP portlarina izin veriliyor...
netsh advfirewall firewall add rule name="AC EVO Dedicated Ports TCP" dir=in action=allow protocol=TCP localport=9700-9710 enable=yes profile=any
netsh advfirewall firewall add rule name="AC EVO Dedicated Ports UDP" dir=in action=allow protocol=UDP localport=9700-9710 enable=yes profile=any
netsh advfirewall firewall add rule name="AC EVO Dedicated Ports HTTP" dir=in action=allow protocol=TCP localport=8080-8090 enable=yes profile=any

echo.
echo [OK] Guvenlik duvari kurallari Windows Kayit Defterine kalici olarak kaydedildi.
echo      Bilgisayari yeniden baslatsaniz bile bu ayarlar asla sifirlanmaz.
echo ========================================================
timeout /t 3 >nul
