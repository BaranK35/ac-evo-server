"""Assetto Corsa EVO Dedicated Server sürüm tespit ve güncelleme denetimi."""
from __future__ import annotations

import os
import re
import time
import urllib.request
import json
from pathlib import Path

from .servers import SERVER_EXE
from .detect import steam_libraries

_CACHE = {
    "latest_buildid": None,
    "cached_at": 0.0,
}


def get_binary_version(target_path: Path | str) -> str:
    """AssettoCorsaEVOServer.exe dosyasından sürüm dizesini (örn: 0.9.1+release.4) okur."""
    p = Path(target_path)
    if p.is_dir():
        p = p / SERVER_EXE
    if not p.is_file():
        return "Bilinmiyor"
    try:
        data = p.read_bytes()
        m = re.search(rb"([0-9]+\.[0-9]+\.[0-9]+\+release\.[0-9]+)", data)
        if m:
            return m.group(1).decode("ascii", errors="replace")
        m2 = re.search(rb"Build release ([0-9\.]+)", data)
        if m2:
            return m2.group(1).decode("ascii", errors="replace")
        m3 = re.search(rb"0\.9\.[0-9]+", data)
        if m3:
            return m3.group(0).decode("ascii", errors="replace")
    except Exception:
        pass
    return "0.9.1"


def get_steam_installed_buildid() -> str | None:
    """Yerel Steam kütüphanesindeki appmanifest_4564210.acf dosyasından buildid okur."""
    for lib in steam_libraries():
        acf = lib / "steamapps" / "appmanifest_4564210.acf"
        if acf.is_file():
            try:
                text = acf.read_text(encoding="utf-8", errors="replace")
                m = re.search(r'"buildid"\s+"([0-9]+)"', text)
                if m:
                    return m.group(1)
            except Exception:
                continue
    return None


def fetch_steam_latest_buildid() -> str | None:
    """SteamCMD Web API üzerinden Kunos'un en güncel public buildid'sini sorgular."""
    now = time.time()
    if _CACHE["latest_buildid"] and (now - _CACHE["cached_at"]) < 300:
        return _CACHE["latest_buildid"]
    try:
        url = "https://api.steamcmd.net/v1/info/4564210"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (EVO Server Manager)"})
        with urllib.request.urlopen(req, timeout=4) as res:
            data = json.loads(res.read().decode("utf-8"))
            buildid = data.get("data", {}).get("4564210", {}).get("depots", {}).get("branches", {}).get("public", {}).get("buildid")
            if buildid:
                _CACHE["latest_buildid"] = str(buildid)
                _CACHE["cached_at"] = now
                return str(buildid)
    except Exception:
        pass
    return _CACHE["latest_buildid"]


def check_server_version(server_dir: Path | str, bundled_dir: Path | str | None = None) -> dict:
    """Sunucu klasörünün sürüm durumunu ve Steam güncelliğini analiz eder."""
    sp = Path(server_dir) if server_dir else None
    bp = Path(bundled_dir) if bundled_dir else None

    is_bundled = False
    if sp and bp and sp.resolve() == bp.resolve():
        is_bundled = True

    bin_ver = get_binary_version(sp) if sp else "Yüklü Değil"
    local_buildid = get_steam_installed_buildid()
    latest_buildid = fetch_steam_latest_buildid()

    update_available = False
    status_text = "Sürüm Güncel"

    if is_bundled:
        source_type = "Gömülü Sürüm"
        status_text = "Gömülü Sürüm (Sabit & Bağımsız)"
        update_available = False  # Gömülü sürüm için asla kullanıcıya güncelleme uyarısı çıkmaz
    else:
        # Steam veya özel klasör
        is_steam = "steam" in str(sp).lower() if sp else False
        source_type = "Steam Kurulumu" if is_steam else "Özel Klasör"
        if latest_buildid and local_buildid:
            if str(local_buildid) != str(latest_buildid):
                update_available = True
                status_text = "Yeni Güncelleme Mevcut! Steam üzerinden güncelleyin."
            else:
                status_text = "Steam Sürümü En Güncel Durumda"
        else:
            status_text = "Sürüm Aktif"

    return {
        "ok": True,
        "is_bundled": is_bundled,
        "source_type": source_type,
        "binary_version": bin_ver,
        "local_buildid": local_buildid,
        "latest_buildid": latest_buildid,
        "update_available": update_available,
        "status_text": status_text,
    }
