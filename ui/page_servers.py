"""Sunucu listesi (ana sayfa)."""
from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from evo_core.servers import ServerError

from . import theme as T
from .widgets import card, danger_btn, error, ghost_btn, muted, primary_btn, run_task, title

GAME_TYPES = {"GameModeType_PRACTICE": "Practice", "GameModeType_RACE_WEEKEND": "Race Weekend"}


class ServersPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=T.BG)
        self.app = app
        self.cards: dict[str, dict] = {}
        self._job = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 10))
        left = ctk.CTkFrame(head, fg_color="transparent")
        left.pack(side="left")
        title(left, "Sunucular", 26).pack(anchor="w")
        self.subtitle = muted(left, "", 13)
        self.subtitle.pack(anchor="w")
        right = ctk.CTkFrame(head, fg_color="transparent")
        right.pack(side="right")
        primary_btn(right, "＋  Yeni Sunucu", self.new_server, width=150).pack(side="left", padx=4)
        ghost_btn(right, "▶ Tümünü Başlat", self.start_all, width=140).pack(side="left", padx=4)
        ghost_btn(right, "■ Tümünü Durdur", self.stop_all, width=140).pack(side="left", padx=4)

        self.listing = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.listing.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 16))
        self.listing.grid_columnconfigure(0, weight=1)

    # --- yaşam döngüsü ---------------------------------------------------
    def on_show(self, **_kw):
        self.refresh()
        self._tick()

    def on_hide(self):
        if self._job:
            self.after_cancel(self._job)
            self._job = None

    def _tick(self):
        for sid, c in self.cards.items():
            running = self.app.runner.is_running(sid)
            c["dot"].configure(text_color=T.GREEN if running else T.MUTED)
            c["state"].configure(text="Çalışıyor" if running else "Durdu",
                                 text_color=T.GREEN if running else T.MUTED)
            c["toggle"].configure(text="■  Durdur" if running else "▶  Başlat",
                                  fg_color="#3a1d1f" if running else T.ACCENT,
                                  hover_color="#5a2326" if running else T.ACCENT_HOVER,
                                  text_color=T.RED if running else "white")
        self._job = self.after(1000, self._tick)

    # --- liste -------------------------------------------------------------
    def refresh(self):
        for w in self.listing.winfo_children():
            w.destroy()
        self.cards.clear()
        ids = self.app.store.ids()
        running = len(self.app.runner.running_ids())
        self.subtitle.configure(text=f"{len(ids)} sunucu  ·  {running} çalışıyor" if ids else "Henüz sunucu yok")
        if not ids:
            empty = card(self.listing)
            empty.grid(row=0, column=0, sticky="ew", pady=6)
            ctk.CTkLabel(empty, text="🏁", font=T.font(40)).pack(pady=(34, 4))
            title(empty, "İlk sunucunuzu oluşturun", 20).pack()
            muted(empty, "Sunucu dosyaları kopyalanır ve hemen ayarlamaya başlayabilirsiniz.", 13).pack(pady=(4, 14))
            primary_btn(empty, "＋  Yeni Sunucu Oluştur", self.new_server, width=210).pack(pady=(0, 34))
            return
        for row, sid in enumerate(ids):
            self._card(row, sid)

    def _card(self, row: int, sid: str):
        try:
            data = self.app.store.load(sid)
        except ServerError:
            return
        box = card(self.listing)
        box.grid(row=row, column=0, sticky="ew", pady=6)
        box.grid_columnconfigure(1, weight=1)

        dot = ctk.CTkLabel(box, text="●", font=T.font(22), text_color=T.MUTED, width=40)
        dot.grid(row=0, column=0, rowspan=2, padx=(14, 0), pady=14)
        top = ctk.CTkFrame(box, fg_color="transparent")
        top.grid(row=0, column=1, sticky="w", pady=(14, 0))
        ctk.CTkLabel(top, text=data.get("name", sid), font=T.font(17, True), text_color=T.TEXT).pack(side="left")
        if data.get("track_is_mod"):
            ctk.CTkLabel(top, text=" MOD ", font=T.font(10, True), fg_color=T.ACCENT, text_color="white",
                         corner_radius=4).pack(side="left", padx=8)
        state = ctk.CTkLabel(top, text="Durdu", font=T.font(12), text_color=T.MUTED)
        state.pack(side="left", padx=10)
        mode = GAME_TYPES.get(data.get("game_type"), "Practice")
        details = (f"{data.get('track')}  ·  {data.get('layout')}  ·  {mode}  ·  {data.get('max_players')} oyuncu  ·  "
                   f"TCP/UDP {data.get('tcp_port')}  ·  HTTP {data.get('http_port')}  ·  {len(data.get('cars', []))} araç")
        muted(box, details, 12).grid(row=1, column=1, sticky="w", pady=(0, 14))

        actions = ctk.CTkFrame(box, fg_color="transparent")
        actions.grid(row=0, column=2, rowspan=2, padx=14)
        toggle = primary_btn(actions, "▶  Başlat", lambda s=sid: self.toggle(s), width=120)
        toggle.pack(side="left", padx=4)
        ghost_btn(actions, "Konsol", lambda s=sid: self.app.show("server", sid=s, tab="Konsol"), width=80).pack(side="left", padx=4)
        ghost_btn(actions, "Ayarlar", lambda s=sid: self.app.show("server", sid=s, tab="Genel"), width=80).pack(side="left", padx=4)
        ghost_btn(actions, "Çoğalt", lambda s=sid: self.clone(s), width=70).pack(side="left", padx=4)
        danger_btn(actions, "Sil", lambda s=sid: self.delete(s), width=60).pack(side="left", padx=4)
        self.cards[sid] = {"dot": dot, "state": state, "toggle": toggle}

    # --- eylemler ----------------------------------------------------------
    def toggle(self, sid: str):
        if self.app.runner.is_running(sid):
            self.app.runner.stop(sid)
            return
        try:
            self.app.runner.start(sid)
        except ServerError as exc:
            error(str(exc), "Sunucu başlatılamadı")
            return
        self.app.show("server", sid=sid, tab="Konsol")

    def start_all(self):
        errors = self.app.runner.start_all()
        if errors:
            error("\n\n".join(errors), "Bazı sunucular başlatılamadı")

    def stop_all(self):
        self.app.runner.stop_all()

    def new_server(self):
        ok = self.app.require_server_folder()
        if not ok:
            return
        path = self.app.cfg["evo_server_path"]
        run_task(self, "Sunucu oluşturuluyor", lambda p: self.app.store.create(path, p), self._created)

    def _created(self, sid, err):
        if err:
            error(str(err), "Sunucu oluşturulamadı")
            return
        self.app.show("server", sid=sid, tab="Genel")

    def clone(self, sid: str):
        run_task(self, "Sunucu çoğaltılıyor", lambda p: self.app.store.clone(sid, p),
                 lambda _r, err: error(str(err)) if err else self.refresh())

    def delete(self, sid: str):
        name = self.app.store.load(sid).get("name", sid)
        if not messagebox.askyesno("Sunucuyu sil", f"'{name}' sunucusu ve klasörü kalıcı olarak silinsin mi?"):
            return
        self.app.runner.stop(sid)
        self.app.store.delete(sid)
        self.refresh()
