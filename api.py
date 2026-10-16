"""Arayüz (HTML) ile Python çekirdeği arasındaki köprü. Tüm public metotlar JS'ten çağrılabilir."""
from __future__ import annotations

import functools
import json
import os
import re
import socket
import threading
import time
import traceback
import uuid
from pathlib import Path

from evo_core.detect import find_server_folders
from evo_core.diagnose import diagnose
from evo_core.mods import ModManager
from evo_core.paths import APP_NAME, APP_VERSION, Config, data_root, servers_dir, bundled_server_dir
from evo_core.runner import Runner, probe_candidates
from evo_core.servers import ServerError, ServerStore, validate_server_folder, copy_tree
from evo_core.steam import SERVER_APP_ID, SteamError, SteamInstaller
from evo_core.tunnel import TunnelManager
from evo_core.presets import list_presets, apply_preset, save_custom_preset, delete_custom_preset
from evo_core.share import generate_share_card


def safe(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            return {"ok": True, "data": fn(self, *args, **kwargs)}
        except ServerError as exc:
            return {"ok": False, "error": str(exc), "code": getattr(exc, "code", "")}
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            return {"ok": False, "error": f"Beklenmeyen hata: {exc}"}
    return wrapper


class Job:
    def __init__(self, title: str):
        self.id, self.title = uuid.uuid4().hex[:8], title
        self.cur = self.total = 0
        self.percent: float | None = None
        self.msg = ""
        self.logs: list[str] = []
        self.done, self.error, self.error_code, self.result = False, "", "", None
        self.cancelled = False

    def progress(self, cur, total, msg=""):
        self.cur, self.total, self.msg = cur, total, msg
        self.percent = (cur / total * 100) if total else None

    def pct(self, percent: float, msg: str = ""):
        self.percent, self.msg = percent, msg

    def log(self, line: str):
        self.logs.append(line)
        del self.logs[:-80]

    def view(self) -> dict:
        return {"id": self.id, "title": self.title, "done": self.done, "error": self.error, "code": self.error_code,
                "percent": self.percent, "msg": self.msg, "logs": self.logs[-12:], "result": self.result}


class Api:
    def __init__(self):
        self._window = None
        self._cfg = Config()
        self._store = ServerStore(servers_dir())
        self._mods = ModManager(self._cfg["mods_root"], self._cfg["server_mods_root"],
                                data_root() / "mods.json", self._cfg["mirror_mods_to_server"])
        self._tunnel = TunnelManager(data_root(), config_getter=lambda: self._cfg)
        self._runner = Runner(
            self._store,
            settings=lambda: {"auto_restart": self._cfg["auto_restart"], "auto_restart_max": self._cfg["auto_restart_max"]},
            before_start=self._prepare_server,
            tunnel=self._tunnel)
        self._jobs: dict[str, Job] = {}
        self._events: list[dict] = []
        self._lock = threading.Lock()
        self._diag_cache: dict[str, tuple[int, list]] = {}
        threading.Thread(target=self._mods.compute_sizes, daemon=True).start()

    # ------------------------------------------------------------------ iç yardımcılar
    def attach(self, window) -> None:
        self._window = window

    def _handle_drop(self, paths: list) -> None:
        """Pencereye bırakılan dosya/klasörleri arka planda inceleyip arayüze bildirir."""
        def work():
            sources = [self._mods.inspect_source(p) for p in paths]
            self.push_event({"type": "drop", "sources": sources})
        threading.Thread(target=work, daemon=True).start()

    def push_event(self, event: dict) -> None:
        with self._lock:
            self._events.append(event)

    def sync_entry_list(self, sid: str) -> Path:
        """Sunucu için entry_list.json dosyasını admin SteamID'leri ile senkronize eder."""
        server_dir = self._store.path(sid)
        data = self._store.load(sid)
        admins = list(data.get("admin_steam_ids", []))
        blacklist = set(str(x).strip() for x in data.get("steamid_blacklist", []))

        entries = []
        for idx, adm_id in enumerate(admins, start=1):
            adm_str = str(adm_id).strip()
            if not adm_str or adm_str in blacklist:
                continue
            entries.append({
                "drivers": [
                    {
                        "steamId": adm_str,
                        "firstName": "Admin",
                        "lastName": f"Pilot_{idx}",
                        "shortName": f"A{idx}"
                    }
                ],
                "carModel": "",
                "carNumber": idx,
                "isAdmin": True,
                "ballastKg": 0,
                "restrictor": 0.0,
                "isServerAdmin": True
            })

        entry_file = server_dir / "entry_list.json"
        with open(entry_file, "w", encoding="utf-8") as fh:
            json.dump({"entries": entries}, fh, indent=2, ensure_ascii=False)
        return entry_file

    def _prepare_server(self, sid: str) -> None:
        """Sunucu başlamadan önce mod pist/araç kayıtlarını sunucunun json dosyalarına ekler ve entry_list.json senkronize eder."""
        self.sync_entry_list(sid)
        d = self._store.load(sid)
        if not d.get("entry_list_path"):
            d["entry_list_path"] = "entry_list.json"
            self._store.save(sid, d)
        if self._cfg["inject_mod_events"]:
            self._mods.inject_events(self._store.path(sid))
            self._mods.inject_cars(self._store.path(sid))

    def _job(self, title: str, work) -> str:
        job = Job(title)
        self._jobs[job.id] = job

        def target():
            try:
                job.result = work(job)
            except SteamError as exc:
                job.error, job.error_code = str(exc), exc.code
            except ServerError as exc:
                job.error = str(exc)
            except Exception as exc:  # noqa: BLE001
                traceback.print_exc()
                job.error = f"Beklenmeyen hata: {exc}"
            finally:
                job.done = True

        threading.Thread(target=target, daemon=True).start()
        return job.id

    def _summary(self, sid: str) -> dict:
        d = self._store.load(sid)
        return {"id": sid, "name": d["name"], "track": d["track"], "layout": d["layout"],
                "track_is_mod": bool(d.get("track_is_mod")), "game_type": d["game_type"],
                "max_players": d["max_players"], "tcp_port": d["tcp_port"], "udp_port": d["udp_port"],
                "http_port": d["http_port"], "cars": len(d.get("cars", [])), "weather": d["weather"],
                "running": self._runner.is_running(sid)}

    # ------------------------------------------------------------------ genel durum
    def _ensure_permanent_firewall(self) -> None:
        """Windows Güvenlik Duvarı kurallarının kalıcı olarak aktif olmasını sağlar."""
        if os.name != "nt":
            return
        try:
            import subprocess
            out = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule", "name=AC EVO Dedicated Ports TCP"],
                                 capture_output=True, text=True, check=False)
            if "Rule Name:" not in out.stdout and "Kural Adı:" not in out.stdout:
                bat = Path(__file__).resolve().parent / "guvenlik_duvari_ayarla.bat"
                if bat.is_file():
                    subprocess.Popen(["powershell", "-Command", f'Start-Process cmd.exe -ArgumentList \'/c "{bat}"\' -Verb RunAs'])
        except Exception:
            pass

    @safe
    def boot(self):
        self._ensure_permanent_firewall()
        ok, _ = validate_server_folder(self._cfg["evo_server_path"])
        return {"app": APP_NAME, "version": APP_VERSION, "setup_done": bool(self._cfg["setup_done"]) and ok,
                "ip": self.local_ip(), "settings": self._settings_view(), "dnd": True}

    @safe
    def tick(self):
        with self._lock:
            events, self._events = self._events, []
        return {"running": self._runner.running_ids(), "events": events}

    @staticmethod
    def local_ip() -> str:
        ips = []
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ips.append(s.getsockname()[0])
        except OSError:
            pass
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("192.168.1.1", 80))
                ip = s.getsockname()[0]
                if ip not in ips:
                    ips.append(ip)
        except OSError:
            pass
        return " / ".join(ips) if ips else "127.0.0.1"

    # ------------------------------------------------------------------ kurulum sihirbazı
    @safe
    def detect_servers(self):
        return [str(p) for p in find_server_folders([data_root() / "dedicated_server"])]

    @safe
    def validate_server_path(self, path: str):
        ok, msg = validate_server_folder(path)
        return {"ok": ok, "message": msg}

    @safe
    def pick_folder(self, title: str = "Klasör seçin"):
        import webview
        dialog = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
        res = self._window.create_file_dialog(dialog, directory="", allow_multiple=False)
        return str(res[0]) if res else ""

    @safe
    def pick_files(self, title: str = "Mod dosyası seçin"):
        import webview
        dialog = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        res = self._window.create_file_dialog(dialog, allow_multiple=True,
                                              file_types=("Mod arşivi (*.zip;*.7z)", "Tüm dosyalar (*.*)"))
        return [str(p) for p in res] if res else []

    @safe
    def finish_setup(self, server_path: str, mods_root: str, server_mods_root: str):
        ok, msg = validate_server_folder(server_path)
        if not ok:
            raise ServerError(msg)
        for root in (mods_root, server_mods_root):
            (Path(root) / "content" / "tracks").mkdir(parents=True, exist_ok=True)
            (Path(root) / "content" / "cars").mkdir(parents=True, exist_ok=True)
        self._cfg["evo_server_path"], self._cfg["mods_root"] = server_path, mods_root
        self._cfg["server_mods_root"], self._cfg["setup_done"] = server_mods_root, True
        self._cfg.save()
        self._mods.configure(mods_root, server_mods_root, self._cfg["mirror_mods_to_server"])
        return True

    @safe
    def default_roots(self):
        return {"mods_root": self._cfg["mods_root"], "server_mods_root": self._cfg["server_mods_root"],
                "server_path": self._cfg["evo_server_path"], "steam_user": self._cfg["steam_user"],
                "app_id": SERVER_APP_ID}

    @safe
    def check_server_version(self):
        """Dedicated server sürüm durumunu ve Steam güncelliğini analiz eder."""
        from evo_core.version import check_server_version
        from evo_core.paths import bundled_server_dir
        path = self._cfg.get("evo_server_path", "")
        return check_server_version(path, bundled_server_dir())

    @safe
    def install_dedicated(self, user: str = "", password: str = "", guard: str = ""):
        target = data_root() / "dedicated_server"

        def work(job: Job):
            inst = SteamInstaller(data_root() / "steamcmd", job.log, lambda p, m: job.pct(p, m))
            job.cancel_hook = inst
            path = inst.install(target, user.strip(), password, guard.strip())
            if user.strip():
                self._cfg["steam_user"] = user.strip()
                self._cfg.save()
            return str(path)

        return self._job("Dedicated Server indiriliyor", work)

    @safe
    def bundled_server_status(self):
        """Uygulamaya gömülü Dedicated Server durumunu döndürür."""
        path = bundled_server_dir()
        ok, msg = validate_server_folder(path)
        return {"path": str(path), "ok": ok, "message": msg}

    @safe
    def use_bundled_server(self):
        """Gömülü Dedicated Server'ı aktif sunucu yolu olarak ayarlar."""
        path = bundled_server_dir()
        ok, msg = validate_server_folder(path)
        if not ok:
            raise ServerError(f"Gömülü sunucu klasörü geçerli değil: {msg}")
        self._cfg["evo_server_path"] = str(path)
        self._cfg.save()
        return str(path)

    @safe
    def auto_detect_and_apply_server(self, sid: str = ""):
        """Dedicated Server'ı otomatik tarar (gömülü veya Steam), bulup konfigürasyona kaydeder ve onaylar."""
        bundled = bundled_server_dir()
        b_ok, b_msg = validate_server_folder(bundled)
        found = find_server_folders()

        chosen_path = ""
        source_type = ""
        if found:
            chosen_path = str(found[0])
            source_type = "Steam / Harici Kurulum"
        elif b_ok:
            chosen_path = str(bundled)
            source_type = "Uygulamaya Gömülü Sürüm"

        if not chosen_path:
            raise ServerError("Sistemde Dedicated Server bulunamadı. Lütfen klasörü elle seçin veya Steam'den kurun.")

        self._cfg["evo_server_path"] = chosen_path
        self._cfg.save()

        # Eğer sid verilmişse ve sunucu dosyaları eksikse senkronize et
        if sid:
            try:
                exe = self._store.exe_path(sid)
                if not exe.is_file():
                    self._store.sync_server(sid, chosen_path)
            except Exception:
                pass

        return {
            "path": chosen_path,
            "type": source_type,
            "message": f"Dedicated Server başarıyla algılandı ve onaylandı ({source_type})."
        }

    @safe
    def sync_single_server(self, sid: str):
        """Bu sunucunun dosyalarını ayarlanmış Dedicated Server kaynağından günceller."""
        if self._runner.is_running(sid):
            raise ServerError("Sunucu çalışıyor. Önce durdurun.")
        path = self._cfg["evo_server_path"]
        ok, msg = validate_server_folder(path)
        if not ok:
            raise ServerError(f"Geçerli Dedicated Server bulunamadı: {msg}")
        return self._job("Sunucu dosyaları güncelleniyor", lambda job: self._store.sync_server(sid, path, job.progress))

    @safe
    def update_bundled_server(self, source_path: str = ""):
        """Gömülü Dedicated Server dosyalarını harici bir kaynaktan veya Steam kurulumundan günceller."""
        def work(job: Job):
            src = Path(source_path) if source_path else None
            if not src or not src.is_dir() or not (src / "AssettoCorsaEVOServer.exe").is_file():
                found = find_server_folders()
                if not found:
                    raise ServerError("Güncelleme için harici Dedicated Server klasörü bulunamadı.")
                src = found[0]
            dst = bundled_server_dir()
            dst.mkdir(parents=True, exist_ok=True)
            job.progress(0, 0, f"Gömülü sunucu güncelleniyor: {src.name}...")
            copy_tree(src, dst, lambda done, tot, m: job.progress(done, tot, m))
            return str(dst)

        return self._job("Gömülü Dedicated Server güncelleniyor", work)

    # ------------------------------------------------------------------ işler
    @safe
    def job_status(self, job_id: str):
        job = self._jobs.get(job_id)
        if not job:
            raise ServerError("İş bulunamadı.")
        return job.view()

    @safe
    def cancel_job(self, job_id: str):
        job = self._jobs.get(job_id)
        if job:
            job.cancelled = True
            hook = getattr(job, "cancel_hook", None)
            if hook:
                hook.cancelled = True
        return True

    # ------------------------------------------------------------------ sunucular
    @safe
    def list_servers(self):
        return [self._summary(sid) for sid in self._store.ids()]

    @safe
    def create_server(self):
        path = self._cfg["evo_server_path"]
        return self._job("Sunucu oluşturuluyor", lambda job: self._store.create(path, job.progress))

    @safe
    def clone_server(self, sid: str):
        return self._job("Sunucu çoğaltılıyor", lambda job: self._store.clone(sid, job.progress))

    @safe
    def delete_server(self, sid: str):
        self._runner.stop(sid)
        self._store.delete(sid)
        return True

    @safe
    def get_server(self, sid: str):
        data = self._store.load(sid)
        known = {(e.get("track"), e.get("layout")) for e in self._mods.track_events()}
        tracks = [dict(e, mod=False) for e in self._store.events(sid) if (e.get("track"), e.get("layout")) not in known]
        tracks.sort(key=lambda e: (str(e["track"]).lower(), str(e["layout"]).lower()))
        tracks += self._mods.track_events()
        mod_cars = {c["name"] for c in self._mods.car_entries()}
        cars = [dict(c, mod=False) for c in self._store.cars(sid) if c.get("name") not in mod_cars]
        cars += self._mods.car_entries()
        return {"data": data, "tracks": tracks, "cars": cars, "ip": self.local_ip(),
                "running": self._runner.is_running(sid)}

    @safe
    def save_server(self, sid: str, incoming: dict):
        data = self._store.load(sid)
        for key in ("serverconfig_extra", "seasondefinition_extra"):
            raw = incoming.get(key)
            if isinstance(raw, str):
                try:
                    incoming[key] = json.loads(raw) if raw.strip() else {}
                except ValueError as exc:
                    raise ServerError(f"'{key}' geçerli bir JSON değil: {exc}") from None
                if not isinstance(incoming[key], dict):
                    raise ServerError(f"'{key}' bir JSON nesnesi ({{...}}) olmalı.")
        data.update(incoming)
        for key in ("tcp_port", "udp_port", "http_port"):
            data[key] = int(data[key])
            if not 1 <= data[key] <= 65535:
                raise ServerError("Port numaraları 1-65535 arasında olmalı.")
        mine = {data["tcp_port"], data["udp_port"], data["http_port"]}
        warnings = []
        for other in self._store.ids():
            if other != sid:
                o = self._store.load(other)
                shared = mine & {o["tcp_port"], o["udp_port"], o["http_port"]}
                if shared:
                    warnings.append(f"'{o['name']}' ile ortak port: {sorted(shared)}. Aynı anda çalışacaksa değiştirin.")
        self._store.save(sid, data)
        return {"warnings": warnings}

    @safe
    def command_preview(self, sid: str):
        data = self._store.load(sid)
        parts = self._store.build_command(sid, data)
        return " ".join(f'"{p}"' if (" " in p or not p) else p for p in parts)

    # ------------------------------------------------------------------ çalıştırma
    @safe
    def start_server(self, sid: str):
        def work(job: Job):
            job.progress(0, 0, "Modlar sunucu klasörüne eşitleniyor...")
            copied = self._mods.sync_to_server(job.progress)
            if copied:
                job.log("Sunucuya eşitlendi: " + ", ".join(copied))
            job.progress(0, 0, "Sunucu başlatılıyor...")
            self._runner.start(sid)
            return True

        return self._job("Sunucu başlatılıyor", work)

    @safe
    def stop_server(self, sid: str):
        self._runner.stop(sid)
        return True

    @safe
    def start_all(self):
        self._mods.sync_to_server()
        return self._runner.start_all()

    @safe
    def stop_all(self):
        self._runner.stop_all()
        return True

    @safe
    def get_console(self, sid: str, since: int = 0):
        return self._console_data(sid, since)

    @safe
    def console(self, sid: str, since: int = 0):
        return self._console_data(sid, since)

    def _console_data(self, sid: str, since: int = 0):
        ms = self._runner.get(sid)
        # Eğer hafızada hiç satır yoksa ve kullanıcı konsolu özellikle temizlemediyse diskteki log dosyasından son satırları yükle
        if not ms.lines and not getattr(ms, "cleared", False):
            try:
                data = self._store.load(sid)
                log_path = self._store.effective_log_path(sid, data)
                if log_path.is_file():
                    with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
                        raw_lines = [l.rstrip("\r\n") for l in fh.readlines()]
                        for l in raw_lines[-150:]:
                            if l.strip():
                                ms.add("out", l)
            except Exception:
                pass

        with ms.lock:
            cur_seq = ms.seq
            all_lines = list(ms.lines)
            was_cleared = getattr(ms, "cleared", False)

        # Eğer kullanıcı konsolu temizlediyse ve yeni satır gelmediyse boş ve reset döner
        if was_cleared and cur_seq == 0:
            return {
                "lines": [],
                "seq": 0,
                "reset": True,
                "running": ms.running,
                "exit_code": ms.last_exit_code,
                "pid": ms.external_pid or (ms.proc.pid if ms.proc else None),
                "started": ms.started_at,
                "now": time.time(),
                "diagnosis": [],
            }

        # Oturum sıfırlanması veya ilk açılış tespiti
        reset = False
        if since <= 0:
            # Sıfırdan açılış: en fazla son 150 satırı gönder
            sent_lines = all_lines[-150:]
        elif since > cur_seq:
            # Sunucu yeniden başlatılmış, istemcinin seq'i önde kalmış: sıfırla ve son 150 satırı ver
            reset = True
            sent_lines = all_lines[-150:]
        else:
            # Normal akış: since'ten sonraki yeni satırlar (en fazla 150 satır chunk)
            sent_lines = [l for l in all_lines if l[0] > since]
            if len(sent_lines) > 150:
                sent_lines = sent_lines[-150:]

        cached = self._diag_cache.get(sid)
        if not cached or cached[0] != cur_seq:
            diag = diagnose([l[3] for l in all_lines[-50:]])
            self._diag_cache[sid] = (cur_seq, diag)
        else:
            diag = cached[1]

        clean_diag = []
        for d in (diag or []):
            if isinstance(d, dict) and d.get("title") and d.get("detail"):
                clean_diag.append({
                    "level": str(d.get("level") or "error"),
                    "title": str(d.get("title") or ""),
                    "detail": str(d.get("detail") or ""),
                    "action": d.get("action")
                })

        def _clean_str(s: str) -> str:
            if not isinstance(s, str):
                return ""
            return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', s)

        return {
            "lines": [[l[0], l[1], l[2], _clean_str(l[3])] for l in sent_lines],
            "seq": cur_seq,
            "reset": reset,
            "running": ms.running,
            "pid": ms.pid,
            "started": ms.started_at,
            "now": time.time(),
            "exit_code": ms.last_exit_code,
            "diagnosis": clean_diag
        }

    @safe
    def fix_firewall(self, sid: str = ""):
        """Windows Güvenlik Duvarı kurallarını ekler (UAC onay penceresi açar)."""
        import tempfile
        import subprocess
        exe = str(self._store.exe_path(sid)) if sid else ""
        lines = [
            "@echo off",
            "chcp 65001 >nul",
            "echo AC EVO Guvenlik Duvari Kurallari Ekleniyor...",
        ]
        tcp_p, udp_p, http_p = 9700, 9700, 8080
        if sid:
            try:
                sd = self._store.load(sid)
                tcp_p = int(sd.get("tcp_port", 9700))
                udp_p = int(sd.get("udp_port", 9700))
                http_p = int(sd.get("http_port", 8080))
            except Exception:
                pass
        if exe:
            lines.append(f'netsh advfirewall firewall add rule name="AC EVO Server Executable" dir=in action=allow program="{exe}" enable=yes profile=any')
        lines += [
            f'netsh advfirewall firewall add rule name="AC EVO TCP {tcp_p}" dir=in action=allow protocol=TCP localport={tcp_p} enable=yes profile=any',
            f'netsh advfirewall firewall add rule name="AC EVO UDP {udp_p}" dir=in action=allow protocol=UDP localport={udp_p} enable=yes profile=any',
            f'netsh advfirewall firewall add rule name="AC EVO TCP {http_p}" dir=in action=allow protocol=TCP localport={http_p} enable=yes profile=any',
            "echo Islem tamamlandi.",
            "timeout /t 3 >nul",
        ]
        tmp_bat = Path(tempfile.gettempdir()) / "ac_evo_firewall.bat"
        tmp_bat.write_text("\r\n".join(lines), encoding="utf-8")
        subprocess.Popen(["powershell", "-Command", f'Start-Process cmd.exe -ArgumentList \'/c "{tmp_bat}"\' -Verb RunAs'])
        return True

    @safe
    def tunnel_status(self) -> dict:
        """CGNAT / VPS tünel durumunu döndürür."""
        return self._tunnel.get_status()

    @safe
    def tunnel_test(self) -> dict:
        """VPS tüneli ve lobi köprüsünü test eder."""
        return self._tunnel.test_connection()

    @safe
    def tunnel_ensure(self, sid: str) -> dict:
        """Seçili sunucunun portları için tüneli başlatır / günceller."""
        d = self._store.load(sid)
        return self._tunnel.ensure_running(int(d["tcp_port"]), int(d["udp_port"]), int(d["http_port"]))

    @safe
    def tunnel_stop(self) -> None:
        """Tüneli durdurur."""
        self._tunnel.stop()


    @safe
    def get_players(self, sid: str) -> list[dict]:
        """Canlı bağlı oyuncu listesini döndürür."""
        return self._runner.get(sid).get_players()

    @safe
    def get_blacklist(self, sid: str) -> list[str]:
        """Sunucunun SteamID kara listesini döndürür."""
        d = self._store.load(sid)
        return list(d.get("steamid_blacklist", []))

    @safe
    def add_blacklist(self, sid: str, steam_id: str) -> list[str]:
        """SteamID'yi kara listeye ekler ve kaydeder."""
        sid_clean = str(steam_id).strip()
        if not sid_clean:
            return []
        d = self._store.load(sid)
        bl = list(d.get("steamid_blacklist", []))
        if sid_clean not in bl:
            bl.append(sid_clean)
            d["steamid_blacklist"] = bl
            self._store.save(sid, d)
        return bl

    @safe
    def remove_blacklist(self, sid: str, steam_id: str) -> list[str]:
        """SteamID'yi kara listeden çıkarır ve kaydeder."""
        sid_clean = str(steam_id).strip()
        d = self._store.load(sid)
        bl = [x for x in d.get("steamid_blacklist", []) if str(x).strip() != sid_clean]
        d["steamid_blacklist"] = bl
        self._store.save(sid, d)
        return bl

    @safe
    def admin_action(self, sid: str, action: str, car_id: str = "", param: str = "") -> dict:
        """Admin eylemini loga yazar ve resmi AC EVO in-game komut dizesini döner."""
        ms = self._runner.get(sid)
        car = str(car_id).strip()
        p = str(param).strip()
        
        # Sunucunun admin şifresini yükle
        try:
            sd = self._store.load(sid)
            admin_pwd = sd.get("admin_password") or "admin"
        except Exception:
            admin_pwd = "admin"

        if action in ("admin", "admin_login"):
            raw_cmd = f"admin {admin_pwd}"
            desc = f"Oyunda admin yetkisi alma komutu: \\admin {admin_pwd}"
        elif action == "del_penalty":
            pen_idx = p or "1"
            raw_cmd = f"del_penalty {car} {pen_idx}"
            desc = f"Araç #{car} ceza kaldırma komutu (Ceza #{pen_idx})."
        elif action in ("penalty", "add_penalty"):
            if p.isdigit():
                raw_cmd = f"add_time {car} {p}"
                desc = f"Araç #{car} +{p} saniye zaman cezası komutu."
            else:
                pen_type = p if p in ("dt", "sg", "disq", "time") else "dt"
                raw_cmd = f"add_penalty {car} {pen_type}"
                desc = f"Araç #{car} '{pen_type.upper()}' cezası uygulama komutu."
        elif action == "add_time":
            sec = p or "10"
            raw_cmd = f"add_time {car} {sec}"
            desc = f"Araç #{car} +{sec} saniye zaman cezası komutu."
        elif action == "to_pit":
            raw_cmd = f"to_pit {car}"
            desc = f"Araç #{car} pite zorla gönderme komutu."
        elif action == "kick":
            raw_cmd = f"kick {car}"
            desc = f"Araç #{car} sunucudan atma komutu."
        elif action == "ban":
            raw_cmd = f"ban {car}"
            desc = f"Araç #{car} sunucudan yasaklama komutu."
        elif action in ("toggle_admin", "admin_toggle"):
            is_adm = ms.toggle_admin(car)
            state_str = "Admin yapıldı" if is_adm else "Adminliği kaldırıldı"
            raw_cmd = f"admin {admin_pwd}"
            desc = f"Araç #{car} ({state_str})."
        elif action == "ballast":
            weight = p or "25"
            raw_cmd = f"ballast {car} {weight}"
            desc = f"Araç #{car} balast (+{weight}kg) komutu."
        elif action == "restrictor":
            pct = p or "10"
            raw_cmd = f"restrictor {car} {pct}"
            desc = f"Araç #{car} motor kısıtlayıcı (%{pct}) komutu."
        elif action == "mute":
            raw_cmd = f"mute {car}"
            desc = f"Araç #{car} susturma komutu."
        elif action == "unmute":
            raw_cmd = f"unmute {car}"
            desc = f"Araç #{car} susturma kaldırma komutu."
        elif action == "skip":
            raw_cmd = "skip"
            desc = "Oturum bir sonraki aşamaya atlatma komutu."
        elif action == "starting_position":
            pos = p or "1"
            raw_cmd = f"starting_position {car} {pos}"
            desc = f"Araç #{car} grid pozisyonu {pos} yapma komutu."
        elif action == "reset_starting_positions":
            raw_cmd = "reset_starting_positions"
            desc = "Grid pozisyonları sıfırlama komutu."
        else:
            raw_cmd = f"{action} {car} {p}".strip()
            desc = f"{action} komutu."

        cmd = f"\\{raw_cmd}"
        alt_cmd = f"/{raw_cmd}"
        admin_login_cmd = f"\\admin {admin_pwd}"

        ms.add("sys", f">> [Admin Eylemi] {desc} -> Oyunda sohbet komutu: {cmd} (Alternatif: {alt_cmd}) | Önce admin olmak için: {admin_login_cmd}")
        return {
            "ok": True,
            "command": cmd,
            "alt_command": alt_cmd,
            "admin_command": admin_login_cmd,
            "admin_password": admin_pwd,
            "car_number": car,
            "desc": desc
        }

    @safe
    def toggle_player_admin(self, sid: str, car_id: str) -> dict:
        """Oyuncunun admin yetkisini açıp kapatır, sunucu kaydına işler ve entry_list.json senkronize eder."""
        ms = self._runner.get(sid)
        is_adm = ms.toggle_admin(car_id)
        target = str(car_id).strip()
        steam_id = None
        driver_name = f"Araç #{target}"
        for p in ms.players.values():
            if str(p.get("car_number")) == target or str(p.get("car_id")) == target or str(p.get("id")) == target or str(p.get("steam_id")) == target:
                steam_id = p.get("steam_id")
                driver_name = p.get("driver_name") or driver_name
                break
        if not steam_id and target.isdigit() and len(target) > 15:
            steam_id = target

        if steam_id:
            d = self._store.load(sid)
            admins = list(d.get("admin_steam_ids", []))
            if is_adm and steam_id not in admins:
                admins.append(steam_id)
            elif not is_adm and steam_id in admins:
                admins.remove(steam_id)
            d["admin_steam_ids"] = admins
            self._store.save(sid, d)
            self.sync_entry_list(sid)

        ms.add("sys", f">> [Admin] {driver_name} (SteamID: {steam_id or 'Bilinmiyor'}) {'Admin yapıldı 👑' if is_adm else 'Adminliği kaldırıldı'}. entry_list.json senkronize edildi.")
        return {"car_id": car_id, "is_admin": is_adm, "steam_id": steam_id}

    @safe
    def kick_player(self, sid: str, car_number: str, steam_id: str = "", ip: str = "") -> dict:
        """Sürücüyü sunucudan atar ve canlı listeden temizler."""
        ms = self._runner.get(sid)
        car = str(car_number).strip()
        s_id = str(steam_id).strip()
        ip_addr = str(ip).strip()

        removed = ms.players.pop(car, None)
        driver_name = (removed or {}).get("driver_name") or f"Araç #{car}"
        for k, p in list(ms.players.items()):
            if str(p.get("car_number")) == car or (s_id and p.get("steam_id") == s_id) or (ip_addr and p.get("ip") == ip_addr):
                ms.players.pop(k, None)

        if ip_addr:
            try:
                import subprocess
                rule_name = f"AC EVO Kick {ip_addr}"
                subprocess.Popen(
                    ["netsh", "advfirewall", "firewall", "add", "rule",
                     f"name={rule_name}", "dir=in", "action=block", f"remoteip={ip_addr}"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
                def remove_kick_rule():
                    time.sleep(15)
                    try:
                        subprocess.Popen(
                            ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule_name}"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                        )
                    except Exception:
                        pass
                threading.Thread(target=remove_kick_rule, daemon=True).start()
            except Exception:
                pass

        ms.add("sys", f">> [Kick] Araç #{car} ({driver_name}) sunucudan atıldı.")
        return {"ok": True, "car_number": car, "driver_name": driver_name}

    @safe
    def ban_player_host(self, sid: str, car_number: str, steam_id: str = "", ip: str = "") -> dict:
        """Kalıcı Ban: Windows Firewall kuralı ekler, SteamID'yi kara listeye ve entry_list dışına alır."""
        ms = self._runner.get(sid)
        car = str(car_number).strip()
        s_id = str(steam_id).strip()
        ip_addr = str(ip).strip()

        fw_blocked = False
        if ip_addr:
            try:
                import subprocess
                rule_name = f"AC EVO Ban {ip_addr}"
                subprocess.Popen(
                    ["netsh", "advfirewall", "firewall", "add", "rule",
                     f"name={rule_name}", "dir=in", "action=block", f"remoteip={ip_addr}"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
                fw_blocked = True
            except Exception:
                pass

        if s_id and s_id != "—":
            self.add_blacklist(sid, s_id)

        # entry_list'i güncelle ve senkronize et
        self.sync_entry_list(sid)

        # Canlı oyuncu listesinden çıkar
        removed = ms.players.pop(car, None)
        driver_name = (removed or {}).get("driver_name") or f"Araç #{car}"
        for k, p in list(ms.players.items()):
            if str(p.get("car_number")) == car or (s_id and p.get("steam_id") == s_id) or (ip_addr and p.get("ip") == ip_addr):
                ms.players.pop(k, None)

        ms.add("sys", f">> [Kalıcı Ban] Araç #{car} ({driver_name}, SteamID: {s_id or 'Bilinmiyor'}, IP: {ip_addr or 'Bilinmiyor'}) yasaklandı. Güvenlik Duvarı engeli: {'Uygulandı' if fw_blocked else 'Atlandı'}.")

        return {
            "ok": True,
            "kick_command": f"\\kick {car}",
            "steam_id": s_id,
            "ip": ip_addr,
            "firewall_blocked": fw_blocked
        }

    @safe
    def console_clear(self, sid: str):
        self._runner.get(sid).clear()
        return True

    @safe
    def console_save(self, sid: str):
        import webview
        dialog = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
        res = self._window.create_file_dialog(dialog, save_filename=f"{sid}_konsol.txt")
        if not res:
            return ""
        path = res if isinstance(res, str) else res[0]
        text = "\n".join(f"{l[1]}  {l[3]}" for l in list(self._runner.get(sid).lines))
        Path(path).write_text(text, encoding="utf-8")
        return str(path)

    @safe
    def results(self, sid: str):
        return self._store.result_files(sid)


    # ------------------------------------------------------------------ modlar
    @safe
    def list_mods(self):
        threading.Thread(target=self._mods.compute_sizes, daemon=True).start()
        return {"tracks": self._mods.scan("track"), "cars": self._mods.scan("car"),
                "game_root": str(self._mods.game_root), "server_root": str(self._mods.server_root),
                "mirror": self._mods.mirror}

    @safe
    def mod_map(self, name: str, kind: str = "track"):
        return self._mods.map_data_uri(name, kind)

    @safe
    def inspect_sources(self, paths: list):
        return [self._mods.inspect_source(p) for p in paths]

    @safe
    def install_mods(self, paths: list):
        def work(job: Job):
            installed = []
            for i, path in enumerate(paths, 1):
                job.log(f"Kuruluyor: {Path(path).name}")
                installed += self._mods.install(path, job.progress)
            self._mods.compute_sizes()
            return installed

        return self._job("Mod kuruluyor", work)

    @safe
    def save_mod_entry(self, kind: str, name: str, entry: dict):
        if kind == "track":
            entry["track_length"] = int(entry["track_length"])
            entry["max_pit_slot"] = int(entry.get("max_pit_slot", 20))
            if not str(entry.get("track", "")).strip() or not str(entry.get("layout", "")).strip():
                raise ServerError("Pist adı ve layout boş olamaz.")
            if entry["track_length"] <= 0:
                raise ServerError("Pist uzunluğu 0'dan büyük olmalı.")
        else:
            entry["performance_indicator"] = float(entry["performance_indicator"])
            for k in ("property_1", "property_2", "property_3"):
                entry[k] = int(entry[k])
        self._mods.set_entry(kind, name, entry)
        return True

    @safe
    def remove_mod(self, kind: str, name: str):
        self._mods.remove(kind, name)
        return True

    @safe
    def sync_mods(self):
        return self._job("Modlar sunucuya eşitleniyor", lambda job: self._mods.sync_to_server(job.progress))

    @safe
    def probe_track(self, sid: str, name: str):
        """Pist bilgilerini mod manifestinden veya konteyner dosyalarından doğrudan çözümler."""
        def work(job: Job):
            self._mods.sync_to_server()
            tracks = {i["name"]: i for i in self._mods.scan("track")}
            item = tracks.get(name)
            if item:
                layouts = item.get("layouts") or ["GP"]
                layout = layouts[0]
                entry = item["entry"]
                entry.update(track=name, layout=layout, event_name=f"{layout} Time Attack")
                self._mods.set_entry("track", name, entry)
                self._mods.inject_events(self._store.path(sid))
                return {"track": name, "layout": layout, "layouts": layouts}
            entry = self._mods.entry_for("track", name)
            self._mods.set_entry("track", name, entry)
            self._mods.inject_events(self._store.path(sid))
            return {"track": entry["track"], "layout": entry["layout"]}

        return self._job("Pist ayarı", work)

    def _open_path(self, target: str | Path) -> bool:
        p = Path(target)
        if not p.exists():
            return False
        import subprocess
        if os.name == 'nt':
            try:
                os.startfile(str(p))
            except Exception:
                subprocess.Popen(["explorer", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
        return True

    @safe
    def open_path(self, target: str):
        return self._open_path(target)

    @safe
    def open_folder(self, path: str = ""):
        target = Path(path) if path else data_root()
        return self._open_path(target)

    @safe
    def open_server_folder(self, sid: str):
        folder = self._store.path(sid)
        if folder.is_dir():
            return self._open_path(folder)
        return False

    @safe
    def open_results_dir(self, sid: str):
        folder = self._store.result_dir(sid)
        folder.mkdir(parents=True, exist_ok=True)
        return self._open_path(folder)

    @safe
    def open_mods_dir(self, which: str = "game"):
        root = self._mods.game_root if which == "game" else self._mods.server_root
        root.mkdir(parents=True, exist_ok=True)
        return self._open_path(root)



    # ------------------------------------------------------------------ ayarlar
    def _settings_view(self) -> dict:
        keys = ("evo_server_path", "mods_root", "server_mods_root", "mirror_mods_to_server", "auto_restart",
                "auto_restart_max", "inject_mod_events", "steam_user")
        return {k: self._cfg[k] for k in keys}

    @safe
    def get_settings(self):
        return self._settings_view()

    @safe
    def save_settings(self, values: dict):
        if values.get("evo_server_path"):
            ok, msg = validate_server_folder(values["evo_server_path"])
            if not ok:
                raise ServerError(msg)
        for key in self._settings_view():
            if key in values:
                self._cfg[key] = values[key]
        self._cfg["auto_restart_max"] = int(self._cfg["auto_restart_max"])
        self._cfg.save()
        self._mods.configure(self._cfg["mods_root"], self._cfg["server_mods_root"], self._cfg["mirror_mods_to_server"])
        return True

    @safe
    def sync_servers(self):
        if self._runner.running_ids():
            raise ServerError("Çalışan sunucular var. Önce hepsini durdurun.")
        path = self._cfg["evo_server_path"]
        return self._job("Sunucu dosyaları güncelleniyor", lambda job: self._store.sync_from(path, job.progress))

    # ------------------------------------------------------------------ SimLab & Presets
    @safe
    def list_presets(self):
        """Mevcut hazır yarış senaryolarını ve özel kullanıcı şablonlarını listeler."""
        return list_presets()

    @safe
    def apply_preset(self, sid: str, preset_id: str):
        """Seçilen senaryoyu sunucu konfigürasyonuna uygular ve kaydeder."""
        sd = self._store.load(sid)
        updated, preset_name = apply_preset(sd, preset_id)
        self._store.save(sid, updated)
        return {"name": preset_name, "server": updated}

    @safe
    def save_custom_preset(self, sid: str, name: str, description: str = ""):
        """Mevcut sunucu ayarlarını gelecekte kullanılmak üzere özel şablon olarak saklar."""
        sd = self._store.load(sid)
        return save_custom_preset(name, description, sd)

    @safe
    def delete_custom_preset(self, preset_id: str):
        """Kullanıcıya ait özel şablonu siler."""
        return delete_custom_preset(preset_id)

    # ------------------------------------------------------------------ AI Race Director / Sentinel
    @safe
    def get_steward_report(self, sid: str):
        """Sunucunun canlı hakemlik, temas ve kural ihlali durum raporunu döndürür."""
        ms = self._runner.get(sid)
        return ms.get_steward_report()

    @safe
    def apply_steward_action(self, sid: str, incident_id: str, action: str, car_id: str = "", param: str = ""):
        """AI Race Director tarafından önerilen hakemlik cezasını oyunda uygular."""
        ms = self._runner.get(sid)
        res = self.admin_action(sid, action, car_id, param)
        ms.mark_steward_applied(incident_id)
        return res

    # ------------------------------------------------------------------ Server Share & Discord Card
    @safe
    def get_server_share_card(self, sid: str):
        """Sunucu için 1-tıkla Discord zengin markdown, Steam join linki ve paylaşım kartı üretir."""
        sd = self._store.load(sid)
        host_ip = self.local_ip()
        return generate_share_card(sd, host_ip)

    @safe
    def shutdown(self):
        self._runner.stop_all()
        return True

    def running_count(self) -> int:
        return len(self._runner.running_ids())

