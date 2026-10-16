"""Assetto Corsa EVO - Canli Yaris Kontrol, Ceza ve Otomasyon Paneli (Race Control Engine).

Bu modul; AC EVO Dedicated Server log akisini izleyerek surucu durumlarini,
Steam64 ID ve baglanti IP adreslerini anlik cikarir.
Kunos motorunun implement etmedigi \\ban komutunu Windows Firewall / Linux iptables
seviyesinde gercek kalici yasaklamaya cevirir, \\del_penalty, \\add_penalty, \\ballast
ve \\to_pit komutlarini yonetir.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

# Log Regex Tanimlari
RE_CONNECT = re.compile(r"connecting gamecar ([0-9a-fA-F-]+) \(([^|]+?) \| (\d+)\)")
RE_CAR = re.compile(r"connected \([a-z]+\) on car ([\w.-]+), with new carId ([0-9a-fA-F-]+)")
RE_NUMBER = re.compile(r"Car \[([0-9a-fA-F-]+)\] #(\d+) for driver")
RE_IP = re.compile(r"(?:Client|Peer|Remote)\s+(?:from\s+)?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")
RE_LAP = re.compile(r"New lap carId ([0-9a-fA-F-]+): (\d+:\d+\.\d+)")
RE_DISCONNECT = re.compile(r"Removing disconnected remote_car ([0-9a-fA-F-]+)")


@dataclass
class DriverRecord:
    guid: str
    driver_name: str = ""
    steam_id: str = ""
    car_model: str = ""
    car_number: str = ""
    ip_address: str = ""
    laps_completed: int = 0
    best_lap: str = ""
    penalties: list[str] = field(default_factory=list)
    is_admin: bool = False
    ballast_kg: int = 0
    restrictor_pct: float = 0.0


class RaceControlHub:
    def __init__(self, admin_password: str = "admin", blacklist_file: Path | None = None):
        self.admin_password = admin_password
        self.blacklist_file = blacklist_file or Path("blacklist.json")
        self.drivers: dict[str, DriverRecord] = {}  # guid -> DriverRecord
        self.car_to_guid: dict[str, str] = {}  # car_number -> guid
        self.lock = threading.Lock()
        self.blacklist: set[str] = self._load_blacklist()

    def _load_blacklist(self) -> set[str]:
        if self.blacklist_file.exists():
            try:
                data = json.loads(self.blacklist_file.read_text(encoding="utf-8"))
                return set(data) if isinstance(data, list) else set()
            except Exception:
                pass
        return set()

    def _save_blacklist(self) -> None:
        try:
            self.blacklist_file.write_text(json.dumps(sorted(self.blacklist), indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[RaceControl] Blacklist yazilamadi: {e}")

    def feed_log_line(self, line: str) -> None:
        """Sunucu log satirini tuketip surucu durum tablosunu gunceller."""
        with self.lock:
            # 1. Baglanti: GUID, Isim, SteamID
            if m := RE_CONNECT.search(line):
                guid, name, steam_id = m.group(1).lower(), m.group(2).strip(), m.group(3).strip()
                driver = self.drivers.setdefault(guid, DriverRecord(guid=guid))
                driver.driver_name = name
                driver.steam_id = steam_id
                # Eger bu SteamID kara listedeyse uyar
                if steam_id in self.blacklist:
                    print(f"[RaceControl] DIKKAT: Kara listedeki oyuncu baglandi! SteamID={steam_id}")

            # 2. Arac modeli
            elif m := RE_CAR.search(line):
                model, guid = m.group(1), m.group(2).lower()
                driver = self.drivers.setdefault(guid, DriverRecord(guid=guid))
                driver.car_model = model

            # 3. Kapi No / Arac Numarasi
            elif m := RE_NUMBER.search(line):
                guid, number = m.group(1).lower(), m.group(2)
                driver = self.drivers.setdefault(guid, DriverRecord(guid=guid))
                driver.car_number = number
                self.car_to_guid[number] = guid

            # 4. Baglanti IP tespiti
            elif m := RE_IP.search(line):
                ip = m.group(1)
                # Henuz IP atanmamis son baglanan surucuye eslestir
                for d in reversed(list(self.drivers.values())):
                    if not d.ip_address:
                        d.ip_address = ip
                        break

            # 5. Tur zamani
            elif m := RE_LAP.search(line):
                guid, lap_str = m.group(1).lower(), m.group(2)
                if guid in self.drivers:
                    self.drivers[guid].laps_completed += 1
                    self.drivers[guid].best_lap = lap_str

            # 6. Ayrilma
            elif m := RE_DISCONNECT.search(line):
                guid = m.group(1).lower()
                if guid in self.drivers:
                    c_no = self.drivers[guid].car_number
                    if c_no in self.car_to_guid:
                        del self.car_to_guid[c_no]
                    del self.drivers[guid]

    # --- Komut Ureticileri ---

    def cmd_admin_login(self) -> str:
        return f"\\admin {self.admin_password}"

    def cmd_add_penalty(self, car_no: str, pen_type: str = "dt") -> str:
        """dt (Drive-Through), sg (Stop & Go), disq (Diskalifiye)"""
        return f"\\add_penalty {car_no} {pen_type}"

    def cmd_add_time(self, car_no: str, seconds: int) -> str:
        return f"\\add_time {car_no} {seconds}"

    def cmd_del_penalty(self, car_no: str, pen_type_or_index: str = "1") -> str:
        """dt, sg, time veya ceza sira no (1)"""
        return f"\\del_penalty {car_no} {pen_type_or_index}"

    def cmd_ballast(self, car_no: str, kg: int) -> str:
        return f"\\ballast {car_no} {kg}"

    def cmd_restrictor(self, car_no: str, pct: float) -> str:
        """0.0 ile 0.20 arasi (ornegin 0.10 = %10)"""
        return f"\\restrictor {car_no} {pct:.2f}"

    def cmd_to_pit(self, car_no: str) -> str:
        return f"\\to_pit {car_no}"

    def cmd_mute(self, car_no: str) -> str:
        return f"\\mute {car_no}"

    def cmd_unmute(self, car_no: str) -> str:
        return f"\\unmute {car_no}"

    def cmd_kick(self, car_no: str) -> str:
        return f"\\kick {car_no}"

    def cmd_skip(self) -> str:
        return "\\skip"

    def ban_player(self, car_no: str) -> dict:
        """Host duzeyinde IP engelleyici + SteamID kara liste + Kick komutu."""
        with self.lock:
            guid = self.car_to_guid.get(str(car_no))
            driver = self.drivers.get(guid) if guid else None

            steam_id = driver.steam_id if driver else ""
            ip = driver.ip_address if driver else ""
            name = driver.driver_name if driver else f"Car #{car_no}"

            # 1. Kara listeye kaydet
            if steam_id:
                self.blacklist.add(steam_id)
                self._save_blacklist()

            # 2. Host isletim sistemi duzeyinde guvenlik duvari kurali
            fw_applied = False
            if ip:
                fw_applied = self._block_ip_at_os_level(ip)

            kick_cmd = self.cmd_kick(car_no)
            return {
                "car_number": car_no,
                "driver_name": name,
                "steam_id": steam_id,
                "ip_address": ip,
                "firewall_blocked": fw_applied,
                "kick_command": kick_cmd,
            }

    def _block_ip_at_os_level(self, ip: str) -> bool:
        try:
            if platform.system() == "Windows":
                rule_name = f"AC_EVO_BAN_{ip}"
                subprocess.run(
                    ["netsh", "advfirewall", "firewall", "add", "rule",
                     f"name={rule_name}", "dir=in", "action=block", f"remoteip={ip}"],
                    capture_output=True, check=False,
                )
                return True
            else:
                # Linux iptables / Docker host
                subprocess.run(
                    ["iptables", "-A", "INPUT", "-s", ip, "-p", "udp", "--dport", "9700", "-j", "DROP"],
                    capture_output=True, check=False,
                )
                subprocess.run(
                    ["iptables", "-A", "INPUT", "-s", ip, "-p", "tcp", "--dport", "9700", "-j", "DROP"],
                    capture_output=True, check=False,
                )
                return True
        except Exception as e:
            print(f"[RaceControl] Firewall kurali eklenirken hata: {e}")
            return False

    def get_live_overview(self) -> list[dict]:
        with self.lock:
            return [
                {
                    "car_number": d.car_number or "—",
                    "driver_name": d.driver_name,
                    "steam_id": d.steam_id,
                    "car_model": d.car_model,
                    "ip_address": d.ip_address or "—",
                    "laps": d.laps_completed,
                    "best_lap": d.best_lap or "—",
                    "is_admin": d.is_admin,
                    "ballast_kg": d.ballast_kg,
                    "restrictor_pct": d.restrictor_pct,
                }
                for d in self.drivers.values()
            ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AC EVO Canli Race Control Paneli")
    parser.add_argument("--log", type=str, help="Izlenecek server.log dosyasi")
    parser.add_argument("--password", type=str, default="admin", help="Admin sifresi")
    args = parser.parse_args()

    hub = RaceControlHub(admin_password=args.password)
    print(f"=== AC EVO Race Control Baslatildi ===")
    print(f"Admin Komutu: {hub.cmd_admin_login()}")
    if args.log and os.path.exists(args.log):
        print(f"Log dosyasi izleniyor: {args.log}")
        with open(args.log, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if line:
                    hub.feed_log_line(line)
                else:
                    time.sleep(0.5)
