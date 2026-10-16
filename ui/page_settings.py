"""Uygulama ayarları."""
from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from evo_core.paths import APP_NAME, APP_VERSION, data_root
from evo_core.servers import validate_server_folder

from . import theme as T
from .widgets import Field, Form, card, error, ghost_btn, info, muted, primary_btn, run_task, section, title


class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=T.BG)
        self.app = app
        self.form: Form | None = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=0, column=0, sticky="nsew", padx=20, pady=16)

    def on_show(self, **_kw):
        for w in self.scroll.winfo_children():
            w.destroy()
        title(self.scroll, "Ayarlar", 26).pack(anchor="w", padx=8, pady=(8, 0))
        box = card(self.scroll)
        box.pack(fill="x", padx=8, pady=12)
        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=14)
        section(inner, "Klasörler")
        self.form = Form(inner, [
            Field("evo_server_path", "EVO Dedicated Server klasörü", "folder", width=440,
                  hint="İçinde AssettoCorsaEVOServer.exe olan klasör"),
            Field("mods_root", "Oyun mod klasörü", "folder", width=440,
                  hint="Varsayılan: Saved Games\\ACE\\mods"),
        ], self.app.cfg.data)
        section(inner, "Davranış")
        self.behaviour = Form(inner, [
            Field("auto_restart", "Çöken sunucuyu otomatik yeniden başlat", "bool"),
            Field("auto_restart_max", "10 dakikada en fazla yeniden başlatma", "int", width=80),
            Field("inject_mod_events", "Mod pistlerini sunucu pist listelerine ekle", "bool",
                  hint="Sunucu başlamadan önce events_*.json dosyalarına yedek alarak ekler"),
        ], self.app.cfg.data)
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", pady=(20, 0))
        primary_btn(row, "Kaydet", self.save, width=120).pack(side="left")

        tools = card(self.scroll)
        tools.pack(fill="x", padx=8, pady=6)
        t_inner = ctk.CTkFrame(tools, fg_color="transparent")
        t_inner.pack(fill="x", padx=20, pady=14)
        section(t_inner, "Bakım")
        muted(t_inner, "Oyun sunucusu güncellendiyse yeni dosyaları mevcut tüm sunucularınıza kopyalar "
                       "(ayarlarınıza ve sonuçlara dokunmaz). Çalışan sunucu varsa önce durdurun.", 12).pack(anchor="w", fill="x")
        brow = ctk.CTkFrame(t_inner, fg_color="transparent")
        brow.pack(fill="x", pady=(10, 0))
        ghost_btn(brow, "Sunucu dosyalarını güncelle", self.sync, width=220).pack(side="left")
        ghost_btn(brow, "Kurulum sihirbazını çalıştır", lambda: self.app.show("setup"), width=220).pack(side="left", padx=10)
        ghost_btn(brow, "Veri klasörünü aç", self.open_data, width=170).pack(side="left")
        muted(t_inner, f"{APP_NAME} {APP_VERSION}   ·   Veri: {data_root()}", 11).pack(anchor="w", pady=(14, 0))

    def on_hide(self):
        pass

    def save(self):
        try:
            values = {**self.form.collect(), **self.behaviour.collect()}
        except ValueError as exc:
            error(str(exc))
            return
        if values["evo_server_path"]:
            ok, msg = validate_server_folder(values["evo_server_path"])
            if not ok:
                error(msg, "Sunucu klasörü geçersiz")
                return
        try:
            (Path(values["mods_root"]) / "content" / "tracks").mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            error(f"Mod klasörü oluşturulamadı: {exc}")
            return
        for key, value in values.items():
            self.app.cfg[key] = value
        self.app.cfg.save()
        self.app.mods.set_root(values["mods_root"])
        info("Ayarlar kaydedildi.", "Kaydedildi")

    def sync(self):
        if self.app.runner.running_ids():
            error("Çalışan sunucular var. Önce hepsini durdurun.")
            return
        if not self.app.require_server_folder():
            return
        path = self.app.cfg["evo_server_path"]
        run_task(self, "Sunucular güncelleniyor", lambda p: self.app.store.sync_from(path, p),
                 lambda count, err: error(str(err)) if err else info(f"{count} sunucu güncellendi."))

    def open_data(self):
        import os
        if hasattr(os, "startfile"):
            os.startfile(str(data_root()))  # type: ignore[attr-defined]
