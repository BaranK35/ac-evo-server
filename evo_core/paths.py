"""Uygulama yolları ve kalıcı ayarlar."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_NAME = "EVOX Server Manager"
DATA_DIR_NAME = "EVO Server Manager"   # klasör adı sürümler arasında sabit: kullanıcının sunucuları korunur
APP_VERSION = "3.0.0"

DEFAULT_CONFIG = {
    "evo_server_path": "",
    "mods_root": "",
    "server_mods_root": "",
    "mirror_mods_to_server": True,
    "steam_user": "",
    "setup_done": False,
    "auto_restart": False,
    "auto_restart_max": 3,
    "inject_mod_events": True,
    "tunnel_enabled": False,
    "tunnel_vps_ip": "",
    "tunnel_vps_user": "",
    "tunnel_frp_token": "",
    "tunnel_socks_port": 1080,
}


def data_root() -> Path:
    """Ayar ve sunucuların tutulduğu, kullanıcının yazabildiği klasör."""
    override = os.environ.get("EVO_MANAGER_HOME")
    if override:
        root = Path(override)
    else:
        base = os.environ.get("LOCALAPPDATA")
        root = Path(base) / DATA_DIR_NAME if base else Path.home() / ".evo-server-manager"
    root.mkdir(parents=True, exist_ok=True)
    return root


def servers_dir() -> Path:
    path = data_root() / "servers"
    path.mkdir(parents=True, exist_ok=True)
    return path


def app_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def bundled_server_dir() -> Path:
    """Uygulamaya gömülü Dedicated Server dosyalarının tutulduğu klasör."""
    local = app_root() / "bundled_server"
    if (local / "AssettoCorsaEVOServer.exe").is_file():
        return local
    data_bundled = data_root() / "bundled_server"
    if (data_bundled / "AssettoCorsaEVOServer.exe").is_file():
        return data_bundled
    return local


def default_mods_root() -> Path:
    """Oyunun (istemci) mod klasörü: Kullanıcı\\Saved Games\\ACE\\mods"""
    return Path.home() / "Saved Games" / "ACE" / "mods"


def default_server_mods_root() -> Path:
    """Dedicated Server kendi kullanıcı klasörünü kullanır: Saved Games\\ACE-Server\\mods"""
    return Path.home() / "Saved Games" / "ACE-Server" / "mods"


class Config:
    def __init__(self, path: Path | None = None):
        self.path = path or (data_root() / "config.json")
        self.data: dict = dict(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                stored = json.load(fh)
            if isinstance(stored, dict):
                self.data.update(stored)
        except (OSError, ValueError):
            pass
        if not self.data.get("mods_root"):
            self.data["mods_root"] = str(default_mods_root())
        if not self.data.get("server_mods_root"):
            self.data["server_mods_root"] = str(default_server_mods_root())

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    def __getitem__(self, key):
        return self.data.get(key, DEFAULT_CONFIG.get(key))

    def get(self, key, default=None):
        return self.data.get(key, DEFAULT_CONFIG.get(key, default))

    def __setitem__(self, key, value):
        self.data[key] = value
