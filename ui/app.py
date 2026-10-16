"""Ana pencere: kenar çubuğu, sayfa yönetimi, servisler."""
from __future__ import annotations

import socket
from tkinter import messagebox

import customtkinter as ctk

from evo_core.mods import ModManager
from evo_core.paths import APP_NAME, APP_VERSION, Config, data_root, servers_dir
from evo_core.runner import Runner
from evo_core.servers import ServerStore, validate_server_folder

from . import theme as T
from .page_mods import ModsPage
from .page_server import ServerPage
from .page_servers import ServersPage
from .page_settings import SettingsPage
from .page_setup import SetupPage
from .widgets import error


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1320x820")
        self.minsize(1120, 700)
        self.configure(fg_color=T.BG)

        self.cfg = Config()
        self.store = ServerStore(servers_dir())
        self.mods = ModManager(self.cfg["mods_root"], data_root() / "mods.json")
        self.runner = Runner(
            self.store,
            settings=lambda: {"auto_restart": self.cfg["auto_restart"], "auto_restart_max": self.cfg["auto_restart_max"]},
            before_start=self._before_start)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self.content = ctk.CTkFrame(self, fg_color=T.BG, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.pages = {
            "servers": ServersPage(self.content, self),
            "server": ServerPage(self.content, self),
            "mods": ModsPage(self.content, self),
            "settings": SettingsPage(self.content, self),
            "setup": SetupPage(self.content, self),
        }
        self.current: str | None = None
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        ok, _ = validate_server_folder(self.cfg["evo_server_path"])
        if self.cfg["setup_done"] and ok:
            self.show("servers")
        else:
            self.show("setup")
        self._sidebar_tick()

    # --- servisler ---------------------------------------------------------------
    def _before_start(self, sid: str) -> None:
        if self.cfg["inject_mod_events"]:
            self.mods.inject_events(self.store.path(sid))

    def require_server_folder(self) -> bool:
        ok, msg = validate_server_folder(self.cfg["evo_server_path"])
        if not ok:
            error(f"{msg}\n\nAyarlar sayfasından EVO Dedicated Server klasörünü seçin.", "Sunucu klasörü gerekli")
            self.show("settings")
        return ok

    @staticmethod
    def local_ip() -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("10.255.255.255", 1))
                return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"

    def finish_setup(self, server_path: str, mods_root: str) -> None:
        self.cfg["evo_server_path"] = server_path
        self.cfg["mods_root"] = mods_root
        self.cfg["setup_done"] = True
        self.cfg.save()
        self.mods.set_root(mods_root)
        self.show("servers")

    # --- sayfa yönetimi ----------------------------------------------------------------
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=230, fg_color=T.SIDEBAR, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.sidebar.grid_propagate(False)
        logo = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo.pack(fill="x", padx=22, pady=(28, 26))
        ctk.CTkLabel(logo, text="EVO", font=T.font(34, True), text_color=T.ACCENT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(logo, text="SERVER MANAGER", font=T.font(11, True), text_color=T.MUTED, anchor="w").pack(anchor="w")
        self.nav = {}
        for key, label in (("servers", "🏁   Sunucular"), ("mods", "🧩   Pist Modları"), ("settings", "⚙   Ayarlar")):
            btn = ctk.CTkButton(self.sidebar, text=label, anchor="w", height=42, corner_radius=8,
                                fg_color="transparent", hover_color=T.CARD2, text_color=T.TEXT, font=T.font(14),
                                command=lambda k=key: self.show(k))
            btn.pack(fill="x", padx=14, pady=3)
            self.nav[key] = btn
        self.running_label = ctk.CTkLabel(self.sidebar, text="", font=T.font(12), text_color=T.MUTED, anchor="w")
        self.running_label.pack(side="bottom", fill="x", padx=22, pady=20)

    def _sidebar_tick(self):
        count = len(self.runner.running_ids())
        self.running_label.configure(text=f"● {count} sunucu çalışıyor" if count else "○ Çalışan sunucu yok",
                                     text_color=T.GREEN if count else T.MUTED)
        self.after(1000, self._sidebar_tick)

    def show(self, name: str, **kw) -> None:
        if self.current:
            self.pages[self.current].on_hide()
            self.pages[self.current].grid_forget()
        self.current = name
        page = self.pages[name]
        page.grid(row=0, column=0, sticky="nsew")
        highlight = "servers" if name == "server" else name
        for key, btn in self.nav.items():
            btn.configure(fg_color=T.CARD2 if key == highlight else "transparent")
        if name == "setup":
            self.sidebar.grid_remove()
        else:
            self.sidebar.grid()
        page.on_show(**kw)

    def on_close(self) -> None:
        running = self.runner.running_ids()
        if running and not messagebox.askyesno(
                "Çıkış", f"{len(running)} sunucu çalışıyor. Durdurulup uygulama kapatılsın mı?"):
            return
        self.runner.stop_all()
        self.destroy()
