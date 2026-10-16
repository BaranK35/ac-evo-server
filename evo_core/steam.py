"""Dedicated Server'ı SteamCMD ile indirir/günceller (Steam hesabı gerekebilir)."""
from __future__ import annotations

import os
import re
import subprocess
import threading
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from .servers import SERVER_EXE, ServerError

STEAMCMD_URL = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"
SERVER_APP_ID = 4564210          # "Assetto Corsa EVO Dedicated Server" (SteamDB)
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
PROGRESS_RE = re.compile(r"progress:\s*([0-9.]+)")


class SteamError(ServerError):
    def __init__(self, message: str, code: str = "error"):
        super().__init__(message)
        self.code = code        # need_guard | bad_password | not_owned | rate_limit | error


def classify(output: str) -> tuple[str, str] | None:
    low = output.lower()
    if "steam guard" in low or "two-factor" in low or "twofactor" in low:
        return "need_guard", "Steam Guard kodu gerekiyor. E-postanıza/telefonunuza gelen kodu girip tekrar deneyin."
    if "invalid password" in low or "invalidpassword" in low:
        return "bad_password", "Kullanıcı adı ya da şifre hatalı."
    if "rate limit" in low:
        return "rate_limit", "Steam çok fazla deneme nedeniyle geçici engel koydu. Birkaç dakika sonra tekrar deneyin."
    if "no subscription" in low or "access denied" in low or "failed to install app" in low and "license" in low:
        return "not_owned", ("Bu hesap Dedicated Server'ı indiremiyor. Assetto Corsa EVO'ya sahip olan hesapla giriş yapın.")
    return None


class SteamInstaller:
    def __init__(self, work_dir: Path, log: Callable[[str], None], progress: Callable[[float, str], None]):
        self.work_dir = Path(work_dir)
        self.log, self.progress = log, progress
        self.cancelled = False
        self.proc: subprocess.Popen | None = None

    @property
    def exe(self) -> Path:
        return self.work_dir / "steamcmd.exe"

    def ensure_steamcmd(self) -> None:
        if self.exe.is_file():
            return
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.progress(0.0, "SteamCMD indiriliyor...")
        archive = self.work_dir / "steamcmd.zip"
        try:
            urllib.request.urlretrieve(STEAMCMD_URL, archive)
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(self.work_dir)
        except Exception as exc:  # noqa: BLE001
            raise SteamError(f"SteamCMD indirilemedi: {exc}. İnternet bağlantınızı kontrol edin.") from exc
        finally:
            archive.unlink(missing_ok=True)

    def _run(self, args: list[str]) -> str:
        self.proc = subprocess.Popen([str(self.exe), *args], cwd=str(self.work_dir), stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=NO_WINDOW, bufsize=0)
        captured, pending = [], ""
        while True:
            chunk = self.proc.stdout.read(4096)
            if not chunk:
                break
            pending += chunk.decode("utf-8", errors="replace")
            *lines, pending = re.split(r"[\r\n]+", pending)
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                captured.append(line)
                match = PROGRESS_RE.search(line)
                if match:
                    self.progress(float(match.group(1)), line[:90])
                else:
                    self.log(line)
            if self.cancelled:
                self.proc.kill()
                raise SteamError("İndirme iptal edildi.", "cancelled")
        self.proc.wait()
        return "\n".join(captured)

    def install(self, target: Path, user: str = "", password: str = "", guard: str = "") -> Path:
        self.ensure_steamcmd()
        target = Path(target)
        target.mkdir(parents=True, exist_ok=True)
        self.progress(0.0, "Steam'e bağlanılıyor...")
        login = ["+login", user, password] + ([guard] if guard else []) if user else ["+login", "anonymous"]
        args = ["+@ShutdownOnFailedCommand", "1", "+@NoPromptForPassword", "1",
                "+@sSteamCmdForcePlatformType", "windows", "+force_install_dir", str(target), *login,
                "+app_update", str(SERVER_APP_ID), "validate", "+quit"]
        output = self._run(args)
        if (target / SERVER_EXE).is_file():
            self.progress(100.0, "Kurulum tamamlandı")
            return target
        issue = classify(output)
        if issue:
            raise SteamError(issue[1], issue[0])
        tail = output.strip().splitlines()[-3:]
        raise SteamError("Sunucu dosyaları indirilemedi. SteamCMD son çıktısı:\n" + "\n".join(tail))
