@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul

where python >nul 2>nul
if errorlevel 1 (
  echo Python bulunamadi. https://www.python.org/downloads/ adresinden 3.11 veya 3.12 kurun
  echo ve kurulumda "Add python.exe to PATH" kutusunu isaretleyin.
  pause
  exit /b 1
)

echo [1/3] Sanal ortam hazirlaniyor...
if not exist ".venv\Scripts\python.exe" python -m venv .venv
call ".venv\Scripts\activate.bat"

echo [2/3] Gerekli paketler kuruluyor...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo [3/3] Tek dosya EXE olusturuluyor...
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "EVOX Server Manager" ^
  --icon "assets\icon.ico" ^
  --add-data "web;web" ^
  --add-data "assets;assets" ^
  --add-data "bundled_server;bundled_server" ^
  --add-data "system;system" ^
  --collect-all webview ^
  --hidden-import py7zr ^
  main.py
if errorlevel 1 goto :failed

echo.
echo Tamam! Uygulama: dist\EVOX Server Manager.exe
pause
exit /b 0

:failed
echo.
echo Islem basarisiz oldu. Yukaridaki hata mesajini bana gonderin.
pause
exit /b 1
