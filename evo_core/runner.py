"""Sunucu süreçlerini başlatır, konsol çıktısını yakalar, kapanınca yeniden başlatır."""
from __future__ import annotations

import os
import subprocess
import threading
import time
from collections import deque
from typing import Callable

from .servers import ServerError, ServerStore
from .steward import StewardSentinel

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
MAX_LINES = 20000


class ManagedServer:
    def __init__(self, sid: str):
        self.sid = sid
        self.proc: subprocess.Popen | None = None
        self.external_pid: int | None = None
        self.tailing_thread: threading.Thread | None = None
        self.lines: deque = deque(maxlen=MAX_LINES)   # (seq, zaman, tür, metin)
        self.seq = 0
        self.lock = threading.Lock()
        self.started_at = 0.0
        self.manual_stop = False
        self.got_stdout = False
        self.restart_times: list[float] = []
        self.last_exit_code: int | None = None
        self.players: dict[str, dict] = {}
        self.steward = StewardSentinel(sid)
        self.cleared = False

    def _parse_player_events(self, text: str) -> None:
        import re
        # 1. Tam Sürücü & Araç Bilgisi: Car [model] #number for driver Name [steam_id]
        m_driver = re.search(r"Car\s*\[(?P<model>[^\]]+)\]\s*#(?P<car_num>\d+)\s+for\s+driver\s+(?P<name>.+?)\s*\[(?P<steam_id>[^\]]+)\]", text, re.I)
        if m_driver:
            cnum = str(m_driver.group("car_num")).strip()
            name = str(m_driver.group("name")).strip()
            sid = str(m_driver.group("steam_id")).strip()
            model = str(m_driver.group("model")).strip()

            # Var olan kaydı steam_id veya car_number ile bul
            target_key = cnum
            for k, p in list(self.players.items()):
                if p.get("steam_id") == sid or p.get("id") == sid or p.get("car_number") == cnum:
                    target_key = k
                    break

            existing = self.players.get(target_key, {})
            self.players[target_key] = {
                "id": sid or cnum,
                "car_id": cnum,
                "car_number": cnum,
                "name": name,
                "driver_name": name,
                "steam_id": sid,
                "car_model": model,
                "ip": existing.get("ip", ""),
                "state": existing.get("state", "Pistte"),
                "penalties": existing.get("penalties", []),
                "joined_at": existing.get("joined_at", time.strftime("%H:%M:%S"))
            }
            return

        # 2. Pit slotu ve yarışçı ataması: assigning pit slot X to competitor Y car_number Z
        m_slot = re.search(r"assigning pit slot \d+.*?(?:competitor(?:_id)?\s+(\S+))?.*?car_number\s+(\d+)", text, re.I)
        if m_slot:
            cnum = str(m_slot.group(2))
            if cnum in self.players:
                self.players[cnum]["state"] = "Pitte"
            return

        # 3. Araç bağlanma / oluşturulma: Connecting Car X (...)
        m_car = re.search(r"Connecting Car\s*(\d+)|connecting gamecar\s*(\d+)", text, re.I)
        if m_car:
            cnum = str(m_car.group(1) or m_car.group(2))
            if cnum in self.players:
                self.players[cnum]["state"] = "Pistte"
            return

        # 4. İlk bağlantı isteği (kullanıcı steam id/hash): Connection with user X was successful
        m_conn = re.search(r"Connection with user ([\w\-]+) was successful", text, re.I)
        if m_conn:
            uid = m_conn.group(1)
            # Gerçek bir SteamID (15+ hane) veya geçerli kullanıcı adı ise ekle
            found = False
            for p in self.players.values():
                if p.get("steam_id") == uid or p.get("id") == uid:
                    found = True
                    break
            if not found:
                num = str(len(self.players) + 1)
                self.players[uid] = {
                    "id": uid,
                    "car_id": num,
                    "car_number": num,
                    "name": uid,
                    "driver_name": uid,
                    "steam_id": uid if uid.isdigit() and len(uid) > 10 else "",
                    "car_model": "",
                    "state": "Pistte",
                    "penalties": [],
                    "is_admin": False,
                    "joined_at": time.strftime("%H:%M:%S")
                }
            return

        # 5. Sunucu oyuncu durumu güncellemesi: Server updated: 0 players / Alive connections: 0
        m_srv = re.search(r"Server updated:\s*(\d+)\s*players|Alive connections:\s*0\b", text, re.I)
        if m_srv:
            count = int(m_srv.group(1)) if m_srv.group(1) is not None else 0
            if count == 0:
                self.players.clear()
            return

        # 6. Bağlantı kopması / ayrılma / kick / ban
        m_disc = re.search(r"Removing registered competitor \S+ car_number (\d+)|User with car (\d+) has been (?:kicked|banned)|Destroying Car\((\S+)\)|user (\S+) disconnected|disconnectCar", text, re.I)
        if m_disc:
            cnum = m_disc.group(1) or m_disc.group(2) or m_disc.group(3) or m_disc.group(4)
            if cnum:
                cnum_str = str(cnum).strip()
                to_delete = []
                for k, p in self.players.items():
                    if k == cnum_str or p.get("car_number") == cnum_str or p.get("car_id") == cnum_str or p.get("id") == cnum_str or p.get("steam_id") == cnum_str:
                        to_delete.append(k)
                for k in to_delete:
                    self.players.pop(k, None)
            return

        # 7. Admin Yetkisi Tespiti
        m_adm = re.search(r"(?:Car\s*#?(\d+)|User\s*(\S+)).*?(?:is now an admin|You are now an admin)|is_player_admin\s*=\s*true", text, re.I)
        if m_adm:
            target = str(m_adm.group(1) or m_adm.group(2) or "").strip()
            for p in self.players.values():
                if not target or p.get("car_number") == target or p.get("id") == target or p.get("steam_id") == target:
                    p["is_admin"] = True
            return

        # 6. Cezalar
        m_pen = re.search(r"Applied penalty (\S+) to (?:car\s*(?:n\.)?|competitor\s*)?(\S+)", text, re.I)
        if m_pen:
            pen = m_pen.group(1)
            target = str(m_pen.group(2)).strip()
            for p in self.players.values():
                if p.get("car_number") == target or p.get("car_id") == target or p.get("id") == target:
                    if pen not in p["penalties"]:
                        p["penalties"].append(pen)
            return

        m_time_pen = re.search(r"Applied time penalty (\d+) seconds to (\S+)", text, re.I)
        if m_time_pen:
            sec, target = m_time_pen.group(1), str(m_time_pen.group(2)).strip()
            pen_desc = f"+{sec}s"
            for p in self.players.values():
                if p.get("car_number") == target or p.get("car_id") == target or p.get("id") == target:
                    if pen_desc not in p["penalties"]:
                        p["penalties"].append(pen_desc)
            return

        # 7. Pite gönderilme / Pit giriş-çıkış
        m_pit = re.search(r"(\S+) has been forcefully sent to pits|Car (\d+) entering in pit|Car (\d+) in pit|teleported to pit position", text, re.I)
        if m_pit:
            target = m_pit.group(1) or m_pit.group(2) or m_pit.group(3)
            if target:
                t_str = str(target).strip()
                for p in self.players.values():
                    if p.get("car_number") == t_str or p.get("car_id") == t_str or p.get("id") == t_str:
                        p["state"] = "Pitte"
            return

        m_exit_pit = re.search(r"Car (\d+) exiting to pit|teleported to grid position|has started the race", text, re.I)
        if m_exit_pit:
            target = m_exit_pit.group(1)
            if target:
                t_str = str(target).strip()
                for p in self.players.values():
                    if p.get("car_number") == t_str or p.get("car_id") == t_str or p.get("id") == t_str:
                        p["state"] = "Pistte"

    def add(self, kind: str, text: str) -> None:
        with self.lock:
            self.cleared = False
            self.seq += 1
            self.lines.append((self.seq, time.strftime("%H:%M:%S"), kind, text.rstrip("\r\n")))
            try:
                self._parse_player_events(text)
            except Exception:
                pass
            try:
                self.steward.analyze_line(text, self.players)
            except Exception:
                pass

    def get_players(self) -> list[dict]:
        with self.lock:
            # Ghost/sahte slotları (adı "Sürücü #..." olup SteamID'si olmayan) filtrele
            valid = []
            for p in self.players.values():
                name = str(p.get("driver_name") or p.get("name") or "").strip()
                if name.startswith("Sürücü #") and not p.get("steam_id"):
                    continue
                valid.append(p)
            return valid

    def toggle_admin(self, car_id: str) -> bool:
        with self.lock:
            target = str(car_id).strip()
            for p in self.players.values():
                if str(p.get("car_number")) == target or str(p.get("car_id")) == target or str(p.get("id")) == target or str(p.get("steam_id")) == target:
                    p["is_admin"] = not p.get("is_admin", False)
                    return p["is_admin"]
            return False

    def get_steward_report(self) -> dict:
        return self.steward.get_report()

    def mark_steward_applied(self, incident_id: str) -> bool:
        return self.steward.mark_applied(incident_id)

    def since(self, seq: int) -> tuple[list, int]:
        with self.lock:
            items = [l for l in self.lines if l[0] > seq]
            return items, self.seq

    def clear(self) -> None:
        with self.lock:
            self.lines.clear()
            self.players.clear()
            self.steward.clear()
            self.seq = 0
            self.cleared = True

    @property
    def running(self) -> bool:
        if self.proc is not None and self.proc.poll() is None:
            return True
        if self.external_pid is not None:
            try:
                import psutil
                p = psutil.Process(self.external_pid)
                if p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
                    return True
            except Exception:
                self.external_pid = None
        return False

    @property
    def pid(self) -> int | None:
        if self.proc is not None and self.proc.poll() is None:
            return self.proc.pid
        return self.external_pid


class Runner:
    def __init__(self, store: ServerStore, settings: Callable[[], dict], before_start: Callable[[str], None] | None = None, tunnel=None):
        self.store = store
        self.settings = settings            # {"auto_restart": bool, "auto_restart_max": int}
        self.before_start = before_start    # mod pistlerini events dosyalarına ekleme vb.
        self.tunnel = tunnel
        self.servers: dict[str, ManagedServer] = {}
        self._watch_started = False

    def _find_external_pid(self, sid: str) -> int | None:
        """Sistemde bu sunucu klasörüne ait çalışan AssettoCorsaEVOServer.exe sürecini bulur."""
        try:
            import psutil
            target_exe = str(self.store.exe_path(sid)).lower()
            target_dir = str(self.store.path(sid)).lower()
            for p in psutil.process_iter(['pid', 'name', 'exe']):
                name = (p.info.get('name') or '').lower()
                if name == 'assettocorsaevoserver.exe':
                    exe = (p.info.get('exe') or '').lower()
                    if exe == target_exe or target_dir in exe:
                        return p.info['pid']
        except Exception:
            pass
        return None

    def _ensure_tailing(self, ms: ManagedServer, sid: str) -> None:
        if ms.tailing_thread is not None and ms.tailing_thread.is_alive():
            return
        data = self.store.load(sid)
        log_path = self.store.effective_log_path(sid, data)
        t = threading.Thread(target=self._tail_external, args=(ms, log_path), daemon=True)
        ms.tailing_thread = t
        t.start()

    def _tail_external(self, ms: ManagedServer, path) -> None:
        path = os.fspath(path)
        leftover = b""
        recent_hashes: deque = deque(maxlen=3000)
        position = 0
        try:
            if os.path.isfile(path):
                size = os.path.getsize(path)
                position = max(0, size - 40000)
        except OSError:
            position = 0
        while ms.running:
            try:
                if os.path.isfile(path):
                    size = os.path.getsize(path)
                    if size < position:
                        position = 0
                    if size > position:
                        with open(path, "rb") as fh:
                            fh.seek(position)
                            chunk = fh.read()
                            position = fh.tell()
                        leftover += chunk
                        *complete, leftover = leftover.split(b"\n")
                        for raw in complete:
                            text = raw.decode("utf-8", errors="replace").strip()
                            if text:
                                h = hash(text)
                                if h not in recent_hashes:
                                    recent_hashes.append(h)
                                    ms.add("out", text)
            except OSError:
                pass
            time.sleep(0.3)

    def get(self, sid: str) -> ManagedServer:
        if sid not in self.servers:
            self.servers[sid] = ManagedServer(sid)
        ms = self.servers[sid]
        if not ms.running:
            ext_pid = self._find_external_pid(sid)
            if ext_pid:
                ms.external_pid = ext_pid
                self._ensure_tailing(ms, sid)
        return ms

    def is_running(self, sid: str) -> bool:
        ms = self.get(sid)
        return ms.running

    def running_ids(self) -> list[str]:
        return [sid for sid in self.store.ids() if self.is_running(sid)]

    # --- başlat -------------------------------------------------
    def start(self, sid: str) -> None:
        ms = self.get(sid)
        if ms.running:
            return
        data = self.store.load(sid)
        problems = self.store.preflight(sid, data)
        if problems:
            raise ServerError("\n".join(problems))
        if self.before_start:
            self.before_start(sid)
        command = self.store.build_command(sid, data)
        log_path = self.store.effective_log_path(sid, data)

        # Önceki log dosyasının konumunu ayarla
        log_path = os.fspath(log_path)
        log_start = 0
        try:
            if os.path.isfile(log_path):
                # Yeni çalıştırma için logu sıfırlamayı dene, kilitliyse sonundan başla
                try:
                    os.remove(log_path)
                    log_start = 0
                except OSError:
                    log_start = os.path.getsize(log_path)
        except OSError:
            log_start = 0

        ms.clear()
        ms.manual_stop = False
        ms.got_stdout = True
        ms.last_exit_code = None
        ms.add("sys", f">> '{data.get('name', sid)}' başlatılıyor "
                      f"(pist: {data.get('track')} / {data.get('layout')}, port: {data.get('tcp_port')})")

        env = os.environ.copy()
        if self.tunnel and self.tunnel.is_enabled() and self.tunnel.vps_ip:
            tcp_p = int(data.get("tcp_port", 9700))
            udp_p = int(data.get("udp_port", 9700))
            http_p = int(data.get("http_port", 8080))
            try:
                t_info = self.tunnel.ensure_running(tcp_p, udp_p, http_p)
                proxy = t_info.get("proxy_url", "socks5h://127.0.0.1:1080")
                for k in ("all_proxy", "ALL_PROXY", "https_proxy", "HTTPS_PROXY", "wss_proxy", "WSS_PROXY"):
                    env[k] = proxy
            except Exception:
                pass

        try:
            flags = CREATE_NEW_PROCESS_GROUP
            if not data.get("show_console_window"):
                flags |= CREATE_NO_WINDOW
            if data.get("low_cpu_mode", True):
                # BELOW_NORMAL_PRIORITY_CLASS (0x00004000): Sunucu arka planda çalışırken
                # oyunun ve sistemin kasmasını/FPS düşmesini engeller.
                flags |= 0x00004000
            env["ACEVO_FORCE_SOFTWARE_RENDERING"] = "true"
            env["DXVK_LOG_LEVEL"] = "none"
            ms.proc = subprocess.Popen(
                command, cwd=str(self.store.path(sid)), env=env,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=flags)
        except OSError as exc:
            ms.add("err", f"Sunucu başlatılamadı: {exc}")
            raise ServerError(f"Sunucu başlatılamadı: {exc}") from exc
        ms.started_at = time.time()
        ms.add("sys", f">> Süreç başladı (PID {ms.proc.pid})")
        threading.Thread(target=self._watch_process, args=(ms, ms.proc), daemon=True).start()
        threading.Thread(target=self._tail_log, args=(ms, ms.proc, log_path, log_start), daemon=True).start()
        self._ensure_watchdog()

    def _watch_process(self, ms: ManagedServer, proc: subprocess.Popen) -> None:
        code = proc.wait()
        ms.last_exit_code = code
        if ms.manual_stop:
            ms.add("sys", "[*] Sunucu durduruldu.")
        else:
            ms.add("err", f"[!] Sunucu kapandı (çıkış kodu {code}).")

    def _tail_log(self, ms: ManagedServer, proc: subprocess.Popen, path: str, position: int = 0) -> None:
        """Sunucu log dosyasını (Assetto Corsa EVO Server.txt) canlı izler ve konsola aktarır."""
        import re
        leftover = b""
        while True:
            alive = proc.poll() is None
            try:
                if os.path.isfile(path):
                    size = os.path.getsize(path)
                    if size < position:
                        position = 0
                    if size > position:
                        with open(path, "rb") as fh:
                            fh.seek(position)
                            chunk = fh.read()
                            position = fh.tell()
                        leftover += chunk
                        *complete, leftover = leftover.split(b"\n")
                        for raw in complete:
                            text = raw.decode("utf-8", errors="replace").strip()
                            text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
                            if text:
                                ms.add("out", text)
            except OSError:
                pass
            if not alive:
                time.sleep(0.3)
                try:
                    if os.path.isfile(path):
                        size = os.path.getsize(path)
                        if size > position:
                            with open(path, "rb") as fh:
                                fh.seek(position)
                                chunk = fh.read()
                            leftover += chunk
                        if leftover:
                            for raw in leftover.split(b"\n"):
                                text = raw.decode("utf-8", errors="replace").strip()
                                text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
                                if text:
                                    ms.add("out", text)
                except OSError:
                    pass
                break
            time.sleep(0.25)

    # --- durdur -------------------------------------------------
    def stop(self, sid: str) -> None:
        ms = self.servers.get(sid)
        if ms:
            ms.manual_stop = True
        # Hem ms.pid'i hem de sistemde o klasöre ait çalışan tüm harici pid'leri sonlandır
        pids_to_kill = set()
        if ms and ms.pid:
            pids_to_kill.add(ms.pid)
        ext_pid = self._find_external_pid(sid)
        if ext_pid:
            pids_to_kill.add(ext_pid)

        for pid in pids_to_kill:
            try:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
                else:
                    os.kill(pid, 9)
            except Exception:
                pass

        if ms:
            if ms.proc:
                try:
                    ms.proc.kill()
                except Exception:
                    pass
            ms.external_pid = None

    def stop_all(self) -> None:
        for sid in self.running_ids():
            self.stop(sid)

    def start_all(self) -> list[str]:
        errors = []
        for sid in self.store.ids():
            try:
                self.start(sid)
            except ServerError as exc:
                errors.append(f"{sid}: {exc}")
        return errors

    # --- otomatik yeniden başlatma -------------------------------
    def _ensure_watchdog(self) -> None:
        if self._watch_started:
            return
        self._watch_started = True
        threading.Thread(target=self._watchdog, daemon=True).start()

    def _watchdog(self) -> None:
        while True:
            time.sleep(5)
            cfg = self.settings()
            if not cfg.get("auto_restart"):
                continue
            limit = max(1, int(cfg.get("auto_restart_max", 3)))
            now = time.time()
            for sid, ms in list(self.servers.items()):
                if ms.proc is None or ms.running or ms.manual_stop:
                    continue
                ms.restart_times = [t for t in ms.restart_times if now - t < 600]
                if len(ms.restart_times) >= limit:
                    continue
                ms.restart_times.append(now)
                ms.add("sys", f"↻ Otomatik yeniden başlatma ({len(ms.restart_times)}/{limit})")
                try:
                    self.start(sid)
                except ServerError as exc:
                    ms.add("err", str(exc))


# ---------------------------------------------------------------- pist testi
def probe_candidates(runner: "Runner", sid: str, candidates: list[tuple[str, str]], progress, cancelled,
                     settle: float = 7.0) -> dict | None:
    """Her (pist, layout) adayı ile sunucuyu kısa süre çalıştırır; çökmeden ayakta kalan ilk adayı döndürür."""
    store = runner.store
    original = store.load(sid)
    runner.stop(sid)
    try:
        for index, (track, layout) in enumerate(candidates, 1):
            if cancelled():
                return None
            progress(index, len(candidates), f"Deneniyor: {track} / {layout}")
            trial = dict(original, track=track, layout=layout, event_name=f"{layout} Time Attack")
            store.save(sid, trial)
            ms = runner.get(sid)
            ms.clear()
            try:
                runner.start(sid)
            except ServerError:
                continue
            deadline = time.time() + settle
            while time.time() < deadline and ms.running and not cancelled():
                time.sleep(0.25)
            crashed = (not ms.running) or any("CRASH DETECTED" in l[3] for l in list(ms.lines))
            runner.stop(sid)
            if not crashed:
                return {"track": track, "layout": layout}
        return None
    finally:
        runner.stop(sid)
        store.save(sid, original)
