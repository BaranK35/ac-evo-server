"""Uygulamaya gömülü CGNAT ve VPS Tünel Yöneticisi (FRP + SSH SOCKS5 Lobi Köprüsü)."""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .paths import app_root, data_root

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class TunnelManager:
    """EVO Server Manager için gömülü tünel yöneticisi.
    
    CGNAT arkasındaki kullanıcıların Kunos lobisine ve oyunculara
    VPS (89.144.10.75) üzerinden kesintisiz erişmesini sağlar.
    """

    def __init__(self, data_dir: Path, config_getter=None):
        self.data_dir = Path(data_dir)
        self.config_getter = config_getter or (lambda: {})
        self._ssh_proc: subprocess.Popen | None = None
        self._frpc_proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._last_ports: tuple[int, int, int] | None = None
        self._last_error: str | None = None

    @property
    def vps_ip(self) -> str:
        cfg = self.config_getter()
        return str(cfg.get("tunnel_vps_ip") or "").strip()

    @property
    def vps_user(self) -> str:
        cfg = self.config_getter()
        return str(cfg.get("tunnel_vps_user") or "").strip()

    @property
    def frp_token(self) -> str:
        cfg = self.config_getter()
        return str(cfg.get("tunnel_frp_token") or "").strip()

    @property
    def socks_port(self) -> int:
        cfg = self.config_getter()
        return int(cfg.get("tunnel_socks_port") or 1080)

    def is_enabled(self) -> bool:
        cfg = self.config_getter()
        return bool(cfg.get("tunnel_enabled", False)) and bool(self.vps_ip)

    def _find_frpc_exe(self) -> str | None:
        # 1. Uygulama içine gömülü binary (kaynak veya PyInstaller _MEIPASS)
        bundled_bin = app_root() / "system" / "frpc.exe"
        if bundled_bin.is_file():
            return str(bundled_bin)
        # 2. Veri dizini içi
        user_bin = data_root() / "system" / "frpc.exe"
        if user_bin.is_file():
            return str(user_bin)
        # 3. Klasik kaynak dizini yedeği
        local_bin = Path(__file__).resolve().parent.parent / "system" / "frpc.exe"
        if local_bin.is_file():
            return str(local_bin)
        # 4. C:\trvps\frp\frpc.exe
        trvps_bin = Path(r"C:\trvps\frp\frpc.exe")
        if trvps_bin.is_file():
            return str(trvps_bin)
        # 5. PATH
        which = shutil.which("frpc.exe") or shutil.which("frpc")
        return which

    def _write_frpc_config(self, tcp_port: int, udp_port: int, http_port: int) -> Path:
        """Sunucunun portlarına göre frpc.toml dosyasını oluşturur."""
        cfg_path = self.data_dir / "frpc_active.toml"
        content = f"""serverAddr = "{self.vps_ip}"
serverPort = 7000
auth.token = "{self.frp_token}"

# Assetto Corsa EVO Dedicated Server (Oyun TCP Portu)
[[proxies]]
name = "evo_tcp_{tcp_port}"
type = "tcp"
localIP = "127.0.0.1"
localPort = {tcp_port}
remotePort = {tcp_port}

# Assetto Corsa EVO Dedicated Server (Oyun & Kunos Lobi UDP Portu)
[[proxies]]
name = "evo_udp_{udp_port}"
type = "udp"
localIP = "127.0.0.1"
localPort = {udp_port}
remotePort = {udp_port}

# Assetto Corsa EVO Dedicated Server (HTTP API Portu)
[[proxies]]
name = "evo_http_{http_port}"
type = "tcp"
localIP = "127.0.0.1"
localPort = {http_port}
remotePort = {http_port}
"""
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(content)
        return cfg_path

    def _is_port_open(self, host: str, port: int, timeout: float = 0.5) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    def ensure_running(self, tcp_port: int, udp_port: int, http_port: int) -> dict[str, Any]:
        """Tüneli ve Kunos lobi köprüsünü belirtilen portlar için başlatır / doğrular."""
        with self._lock:
            # 1. SSH SOCKS5 Köprüsü (Kunos lobi kaydının VPS IP'siyle çıkmasını sağlar)
            if not self._is_port_open("127.0.0.1", self.socks_port, timeout=0.3):
                # SSH sürecini başlat
                if self._ssh_proc and self._ssh_proc.poll() is None:
                    try:
                        self._ssh_proc.terminate()
                    except OSError:
                        pass
                cmd_ssh = [
                    "ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
                    "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3",
                    "-D", str(self.socks_port), "-N", f"{self.vps_user}@{self.vps_ip}"
                ]
                try:
                    self._ssh_proc = subprocess.Popen(
                        cmd_ssh,
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=CREATE_NO_WINDOW
                    )
                    # SOCKS portunun açılmasını bekle
                    for _ in range(15):
                        time.sleep(0.2)
                        if self._is_port_open("127.0.0.1", self.socks_port, timeout=0.2):
                            break
                except Exception as e:
                    self._last_error = f"SSH SOCKS5 köprüsü başlatılamadı: {e}"

            # 2. FRPC Tüneli (Dışarıdan gelen oyuncu ve UDP ping paketlerini içeri aktarır)
            frpc_exe = self._find_frpc_exe()
            if not frpc_exe:
                raise RuntimeError("frpc.exe bulunamadı. Gömülü veya kurulu frpc dosyası eksik.")

            ports_tuple = (tcp_port, udp_port, http_port)
            need_restart = False

            if self._frpc_proc is None or self._frpc_proc.poll() is not None:
                need_restart = True
            elif self._last_ports != ports_tuple:
                need_restart = True

            if need_restart:
                if self._frpc_proc and self._frpc_proc.poll() is None:
                    try:
                        self._frpc_proc.terminate()
                        self._frpc_proc.wait(timeout=2)
                    except Exception:
                        pass

                config_path = self._write_frpc_config(tcp_port, udp_port, http_port)
                self._frpc_proc = subprocess.Popen(
                    [frpc_exe, "-c", str(config_path)],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=CREATE_NO_WINDOW
                )
                self._last_ports = ports_tuple
                time.sleep(0.5)

            return {
                "ok": True,
                "proxy_url": f"socks5h://127.0.0.1:{self.socks_port}",
                "vps_ip": self.vps_ip,
                "ports": {"tcp": tcp_port, "udp": udp_port, "http": http_port}
            }

    def test_connection(self) -> dict[str, Any]:
        """Tünel ve VPS erişimini test eder."""
        t0 = time.time()
        # SSH test
        try:
            res = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=4",
                 f"{self.vps_user}@{self.vps_ip}", "echo OK"],
                capture_output=True, text=True, timeout=5, creationflags=CREATE_NO_WINDOW
            )
            ssh_ok = (res.returncode == 0 and "OK" in res.stdout)
        except Exception as e:
            ssh_ok = False

        latency_ms = int((time.time() - t0) * 1000)

        frpc_exists = bool(self._find_frpc_exe())
        socks_alive = self._is_port_open("127.0.0.1", self.socks_port, timeout=0.3)
        frpc_alive = self._frpc_proc is not None and self._frpc_proc.poll() is None

        return {
            "ok": ssh_ok and frpc_exists,
            "ssh_ok": ssh_ok,
            "frpc_installed": frpc_exists,
            "socks_active": socks_alive,
            "frpc_active": frpc_alive,
            "vps_ip": self.vps_ip,
            "latency_ms": latency_ms if ssh_ok else None,
            "message": "VPS Tüneli ve Lobi Köprüsü Hazır!" if ssh_ok else "VPS SSH bağlantısı kurulamadı. SSH anahtarınızı veya VPS IP'sini kontrol edin."
        }

    def get_status(self) -> dict[str, Any]:
        socks_alive = self._is_port_open("127.0.0.1", self.socks_port, timeout=0.2)
        frpc_alive = self._frpc_proc is not None and self._frpc_proc.poll() is None
        return {
            "enabled": self.is_enabled(),
            "vps_ip": self.vps_ip,
            "socks_active": socks_alive,
            "frpc_active": frpc_alive,
            "ports": self._last_ports,
            "last_error": self._last_error
        }

    def stop(self) -> None:
        """Tünel süreçlerini kapatır."""
        with self._lock:
            if self._frpc_proc and self._frpc_proc.poll() is None:
                try:
                    self._frpc_proc.terminate()
                except OSError:
                    pass
                self._frpc_proc = None

            if self._ssh_proc and self._ssh_proc.poll() is None:
                try:
                    self._ssh_proc.terminate()
                except OSError:
                    pass
                self._ssh_proc = None
