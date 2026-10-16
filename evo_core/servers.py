"""Sunucu klasörleri, ayar dosyaları ve başlatma komutu."""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import time
from pathlib import Path
from typing import Callable

from .encoding import build_seasondefinition, build_serverconfig, encode_evo_payload

SERVER_EXE = "AssettoCorsaEVOServer.exe"
SKIP_ON_SYNC = {"server.json", "result", "results", "logs", "serverConfig", "__pycache__"}

ProgressCb = Callable[[int, int, str], None]


class ServerError(Exception):
    """Kullanıcıya olduğu gibi gösterilebilecek anlaşılır hata."""


def validate_server_folder(path: str | Path) -> tuple[bool, str]:
    p = Path(path) if path else None
    if not p or not str(path).strip():
        return False, "Klasör seçilmedi."
    if not p.is_dir():
        return False, "Bu klasör bulunamadı."
    if not (p / SERVER_EXE).is_file():
        return False, f"Bu klasörde {SERVER_EXE} yok. Dedicated Server klasörünü seçtiğinizden emin olun."
    return True, "Geçerli EVO Dedicated Server klasörü."


def load_json(path: Path, default):
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def default_server(server_id: str, folder: Path) -> dict:
    num = server_number(server_id)
    return {
        "id": server_id,
        "name": f"Sunucu {num}",
        "tcp_port": 9700 + num - 1,
        "udp_port": 9700 + num - 1,
        "http_port": 8080 + num - 1,
        "max_players": 8,
        "cycle": True,
        "launch_path": "",
        "netcode_update_interval": 55,
        "driver_password": "",
        "spectator_password": "",
        "admin_password": "admin",
        "pi_min": 0, "pi_max": 0,
        "property_1": [], "property_2": [], "property_3": [],
        "entry_list_server_url": "", "results_post_url": "", "token": "",
        "entry_list_path": "",
        "results_path": str(folder / "result") + os.sep,
        "log_file_path": str(default_log_path(folder)),
        "extra_arguments": "",
        "tuning_type": "TuningAllowed",
        "type": "MultiplayerServerListSessionType_UNRANKED",
        "game_type": "GameModeType_PRACTICE",
        "year": 2024, "month": 8, "day": 15, "second": 0,
        "export_json": False,
        "track": "Imola", "layout": "GP", "event_name": "GP Time Attack", "track_length": 4909,
        "track_is_mod": False,
        "weather": "GameModeSelectionWeatherType_CLEAR",
        "weather_behavior": "GameModeSelectionWeatherBehaviour_STATIC",
        "initial_grip": "InitialGrip_GREEN",
        "cars": [{"car_name": "preset_m4gt3_mech_1", "ballast": 0, "restrictor": 0}],
        **{f"{p}_{k}": v for p in ("practice", "qualify", "warmup", "race") for k, v in (
            ("length", 300), ("hour", 16), ("minute", 0), ("time_multiplier", 1),
            ("max_wait_to_box", 10), ("overtime", 10))},
        "race_duration_type": "GameModeSelectionDuration_TIME",
        "min_waiting_for_players": 10, "max_waiting_for_players": 30,
        "mandatory_pitstop": False, "mandatory_pitstop_refuel": False,
        "mandatory_pitstop_tyre_change": False, "pit_window_time": 600,
        "custom_command": "",
        "serverconfig_extra": {},
        "seasondefinition_extra": {},
        "car_damage": True,
        "penalties": True,
        "pit_limiter": True,
        "wrong_way_penalty": True,
        "show_console_window": True,
        "low_cpu_mode": True,
        "admin_steam_ids": [],
        "steamid_blacklist": [],
        "steamid_whitelist": [],
    }


def default_log_path(folder: Path) -> Path:
    return folder / "serverConfig" / "Assetto Corsa EVO Server.txt"


def server_number(server_id: str) -> int:
    match = re.search(r"(\d+)$", str(server_id or ""))
    return int(match.group(1)) if match else 10 ** 9


def copy_tree(src: Path, dst: Path, progress: ProgressCb | None = None, skip: set[str] | None = None,
              link: bool = False) -> None:
    """Büyük klasörleri ilerleme bildirerek kopyalar. link=True ise aynı diskte sabit bağ kurar (anında, ek yer yok)."""
    skip = skip or set()
    files: list[tuple[Path, Path]] = []
    for root, dirs, names in os.walk(src):
        dirs[:] = [d for d in dirs if d not in skip]
        rel = Path(root).relative_to(src)
        for name in names:
            if name in skip:
                continue
            files.append((Path(root) / name, dst / rel / name))
    total = len(files)
    for index, (source, target) in enumerate(files, 1):
        target.parent.mkdir(parents=True, exist_ok=True)
        if link:
            try:
                if target.exists():
                    target.unlink()
                os.link(source, target)
            except OSError:
                shutil.copy2(source, target)
        else:
            shutil.copy2(source, target)
        if progress:
            progress(index, total, source.name)
    if not files:
        dst.mkdir(parents=True, exist_ok=True)


class ServerStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # --- yollar -------------------------------------------------
    def path(self, sid: str) -> Path:
        return self.root / sid

    def exe_path(self, sid: str) -> Path:
        return self.path(sid) / SERVER_EXE

    def config_path(self, sid: str) -> Path:
        return self.path(sid) / "server.json"

    def result_dir(self, sid: str, data: dict | None = None) -> Path:
        data = data or self.load(sid)
        configured = (data.get("results_path") or "").strip()
        return Path(configured) if configured else self.path(sid) / "result"

    # --- okuma / yazma -----------------------------------------
    def ids(self) -> list[str]:
        found = [d.name for d in self.root.iterdir() if d.is_dir() and (d / "server.json").is_file()]
        return sorted(found, key=server_number)

    def load(self, sid: str) -> dict:
        data = load_json(self.config_path(sid), None)
        if data is None:
            raise ServerError(f"'{sid}' sunucusunun ayar dosyası okunamadı.")
        base = default_server(sid, self.path(sid))
        base.update(data)
        return base

    def save(self, sid: str, data: dict) -> None:
        tmp = self.config_path(sid).with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, self.config_path(sid))

    def next_id(self) -> str:
        i = 1
        while self.path(f"server_{i}").exists():
            i += 1
        return f"server_{i}"

    # --- oluşturma / klonlama / silme --------------------------
    def create(self, evo_path: str, progress: ProgressCb | None = None) -> str:
        ok, msg = validate_server_folder(evo_path)
        if not ok:
            raise ServerError(msg)
        sid = self.next_id()
        dst = self.path(sid)
        try:
            copy_tree(Path(evo_path), dst, progress, skip={"result", "results", "logs", "serverConfig"})
            (dst / "result").mkdir(exist_ok=True)
            self.save(sid, default_server(sid, dst))
        except Exception:
            shutil.rmtree(dst, ignore_errors=True)
            raise
        return sid

    def clone(self, sid: str, progress: ProgressCb | None = None) -> str:
        new_id = self.next_id()
        dst = self.path(new_id)
        try:
            copy_tree(self.path(sid), dst, progress, skip={"result", "results", "logs", "serverConfig"})
            (dst / "result").mkdir(exist_ok=True)
            data = self.load(sid)
            num = server_number(new_id)
            data.update({
                "id": new_id,
                "name": f"{data.get('name', sid)} (Kopya)",
                "tcp_port": 9700 + num - 1, "udp_port": 9700 + num - 1, "http_port": 8080 + num - 1,
                "results_path": str(dst / "result") + os.sep,
                "log_file_path": str(default_log_path(dst)),
                "custom_command": "",
            })
            self.save(new_id, data)
        except Exception:
            shutil.rmtree(dst, ignore_errors=True)
            raise
        return new_id

    def delete(self, sid: str) -> None:
        shutil.rmtree(self.path(sid), ignore_errors=True)

    def sync_server(self, sid: str, evo_path: str, progress: ProgressCb | None = None) -> None:
        ok, msg = validate_server_folder(evo_path)
        if not ok:
            raise ServerError(msg)
        copy_tree(Path(evo_path), self.path(sid), progress, skip=SKIP_ON_SYNC)

    def sync_from(self, evo_path: str, progress: ProgressCb | None = None) -> int:
        ok, msg = validate_server_folder(evo_path)
        if not ok:
            raise ServerError(msg)
        count = 0
        for sid in self.ids():
            copy_tree(Path(evo_path), self.path(sid), progress, skip=SKIP_ON_SYNC)
            count += 1
        return count


    # --- listeler ----------------------------------------------
    def events(self, sid: str) -> list[dict]:
        base = self.path(sid)
        seen, out = set(), []
        for fname in ("events_practice.json", "events_race_weekend.json"):
            for ev in load_json(base / fname, {"events": []}).get("events", []):
                key = (ev.get("track"), ev.get("layout"))
                if key not in seen:
                    seen.add(key)
                    out.append(ev)
        return out

    def cars(self, sid: str) -> list[dict]:
        return load_json(self.path(sid) / "cars.json", {"cars": []}).get("cars", [])

    def result_files(self, sid: str) -> list[dict]:
        folder = self.result_dir(sid)
        if not folder.is_dir():
            return []
        items = []
        for p in folder.iterdir():
            if p.is_file() and p.suffix.lower() == ".json":
                st = p.stat()
                items.append({"name": p.name, "path": str(p), "size": st.st_size,
                              "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
                              "mtime": st.st_mtime})
        items.sort(key=lambda i: i["mtime"], reverse=True)
        return items

    # --- komut --------------------------------------------------
    def effective_log_path(self, sid: str, data: dict) -> Path:
        configured = (data.get("log_file_path") or "").strip()
        return Path(configured) if configured else default_log_path(self.path(sid))

    def build_command(self, sid: str, data: dict) -> list[str]:
        exe = str(self.exe_path(sid))
        manual = " ".join((data.get("custom_command") or "").split())
        if manual:
            try:
                parts = [p.strip('"') for p in shlex.split(manual, posix=False)]
            except ValueError:
                parts = [p.strip('"') for p in manual.split()]
            if parts and not parts[0].startswith("-"):
                return parts
            return [exe, *parts]

        args = [exe, "-serverconfig", encode_evo_payload(build_serverconfig(data)),
                "-seasondefinition", encode_evo_payload(build_seasondefinition(data))]
        log_path = self.effective_log_path(sid, data)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        args += ["-log_file", str(log_path)]
        if data.get("low_cpu_mode", True):
            if "-disable_lpp" not in args:
                args += ["-disable_lpp"]
            if "-minimumcores" not in args:
                args += ["-minimumcores", "2"]
        extra = " ".join((data.get("extra_arguments") or "").split())
        if extra:
            try:
                parts = [p.strip('"') for p in shlex.split(extra, posix=False)]
            except ValueError:
                parts = [p.strip('"') for p in extra.split()]
            args += parts
        return args

    def preflight(self, sid: str, data: dict) -> list[str]:
        """Başlatmadan önce bariz sorunları anlaşılır cümlelerle listeler."""
        problems = []
        if not self.exe_path(sid).is_file():
            problems.append(f"{SERVER_EXE} sunucu klasöründe bulunamadı. Ayarlar > 'Sunucuları güncelle' deneyin.")
        if not data.get("cars"):
            problems.append("Hiç araç seçilmemiş. 'Araçlar' sekmesinden en az bir araç seçin.")
        ports = [data.get("tcp_port"), data.get("udp_port"), data.get("http_port")]
        if any(not isinstance(p, int) or not (1 <= p <= 65535) for p in ports):
            problems.append("Port numaraları 1-65535 arasında olmalı.")
        elif data.get("tcp_port") == data.get("http_port"):
            problems.append("TCP Portu ile HTTP Portu aynı olamaz (her ikisi de TCP soketi dinler).")
        if not str(data.get("track") or "").strip():
            problems.append("Pist seçilmemiş. 'Pist' sekmesinden bir pist seçin.")
        return problems
