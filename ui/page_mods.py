"""Pist modları: kurma, düzenleme, kaldırma."""
from __future__ import annotations

import os
import webbrowser
from tkinter import filedialog, messagebox

import customtkinter as ctk

from evo_core.mods import ModTrack

from . import theme as T
from .widgets import (Field, Form, card, danger_btn, error, ghost_btn, muted, primary_btn, run_bg, run_task,
                      title)


def fmt_size(num: int) -> str:
    return f"{num / 1024 / 1024:.0f} MB" if num > 1024 * 1024 else f"{num / 1024:.0f} KB"


class EditModDialog(ctk.CTkToplevel):
    """Pist adı, layout ve uzunluk gibi sunucuya bildirilecek bilgiler."""

    def __init__(self, master, app, mod: ModTrack, on_saved):
        super().__init__(master)
        self.app, self.mod, self.on_saved = app, mod, on_saved
        self.title(f"Pist bilgileri - {mod.name}")
        self.geometry("620x560")
        self.configure(fg_color=T.CARD)
        self.transient(master.winfo_toplevel())
        entry = app.mods.entry_for(mod)
        title(self, mod.name, 20).pack(anchor="w", padx=24, pady=(20, 2))
        muted(self, "Sunucu bu bilgilerle pisti yükler. Değerler modun yapımcısının verdiği adlarla birebir "
                    "aynı olmalıdır.", 12).pack(anchor="w", padx=24, fill="x")
        self.winfo_children()[-1].configure(wraplength=560)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=24, pady=10)
        self.form = Form(body, [
            Field("track", "Pist adı", width=300, hint="Genelde mod klasörünün adı"),
            Field("layout", "Layout", width=300,
                  hint="Bulunan adaylar: " + (", ".join(mod.layouts) if mod.layouts else "bulunamadı")),
            Field("event_name", "Etkinlik adı", width=300),
            Field("track_length", "Pist uzunluğu (metre)", "int", width=120,
                  hint="Tahmini değer; gerçek uzunluğu biliyorsanız girin"),
            Field("max_pit_slot", "Pit kutusu sayısı", "int", width=120),
        ], entry, label_width=170)
        if mod.track_text:
            muted(self, f".track dosyası içeriği:  {mod.track_text[:120]}", 11).pack(anchor="w", padx=24)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(side="bottom", fill="x", padx=24, pady=20)
        primary_btn(row, "Kaydet", self.save, width=120).pack(side="right")
        ghost_btn(row, "Vazgeç", self.destroy, width=100).pack(side="right", padx=8)
        self.after(150, self._grab)

    def _grab(self):
        try:
            self.grab_set()
        except Exception:  # noqa: BLE001
            pass

    def save(self):
        try:
            values = self.form.collect()
        except ValueError as exc:
            error(str(exc))
            return
        if not values["track"] or not values["layout"]:
            error("Pist adı ve layout boş olamaz.")
            return
        if values["track_length"] <= 0:
            error("Pist uzunluğu 0'dan büyük olmalı.")
            return
        self.app.mods.set_entry(self.mod.name, values)
        self.on_saved()
        self.destroy()


class ModsPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=T.BG)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 6))
        left = ctk.CTkFrame(head, fg_color="transparent")
        left.pack(side="left")
        title(left, "Pist Modları", 26).pack(anchor="w")
        self.path_label = muted(left, "", 12)
        self.path_label.pack(anchor="w")
        right = ctk.CTkFrame(head, fg_color="transparent")
        right.pack(side="right")
        primary_btn(right, "＋  Arşivden Ekle", self.add_archive, width=150).pack(side="left", padx=4)
        ghost_btn(right, "Klasörden Ekle", self.add_folder, width=130).pack(side="left", padx=4)
        ghost_btn(right, "Mod klasörünü aç", self.open_dir, width=140).pack(side="left", padx=4)

        note = card(self)
        note.grid(row=1, column=0, sticky="ew", padx=28, pady=(8, 8))
        muted(note, "İndirdiğiniz modun .zip / .7z dosyasını ya da açılmış klasörünü seçin. Uygulama içindeki pisti "
                    "bulur, oyunun mod klasörüne kurar ve Sunucu > Pist & Hava listesine ★ MOD olarak ekler. "
                    "Sunucuya bağlanacak herkesin aynı modu kurmuş olması gerekir.", 12).pack(
            anchor="w", padx=16, pady=12, fill="x")
        note.winfo_children()[-1].configure(wraplength=900)

        self.listing = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.listing.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 16))
        self.listing.grid_columnconfigure(0, weight=1)

    def on_show(self, **_kw):
        self.refresh()

    def on_hide(self):
        pass

    def refresh(self):
        self.path_label.configure(text=f"Klasör: {self.app.mods.tracks_dir}")
        for w in self.listing.winfo_children():
            w.destroy()
        run_bg(self, self.app.mods.scan, self._render)

    def _render(self, mods, err):
        if err:
            error(f"Mod klasörü okunamadı: {err}")
            return
        for w in self.listing.winfo_children():
            w.destroy()
        if not mods:
            box = card(self.listing)
            box.grid(row=0, column=0, sticky="ew", pady=6)
            ctk.CTkLabel(box, text="🧩", font=T.font(36)).pack(pady=(30, 4))
            title(box, "Henüz mod pisti kurulu değil", 18).pack()
            muted(box, "Sağ üstteki 'Arşivden Ekle' ile indirdiğiniz modu seçin.", 13).pack(pady=(4, 30))
            return
        for i, mod in enumerate(mods):
            self._card(i, mod)

    def _card(self, row: int, mod: ModTrack):
        entry = self.app.mods.entry_for(mod)
        box = card(self.listing)
        box.grid(row=row, column=0, sticky="ew", pady=6)
        box.grid_columnconfigure(0, weight=1)
        left = ctk.CTkFrame(box, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=16, pady=12)
        top = ctk.CTkFrame(left, fg_color="transparent")
        top.pack(anchor="w")
        ctk.CTkLabel(top, text=mod.name, font=T.font(16, True), text_color=T.TEXT).pack(side="left")
        ctk.CTkLabel(top, text=" MOD ", font=T.font(10, True), fg_color=T.ACCENT, text_color="white",
                     corner_radius=4).pack(side="left", padx=8)
        muted(left, f"Layout: {entry['layout']}   ·   Uzunluk: {entry['track_length']} m   ·   "
                    f"Boyut: {fmt_size(mod.size)}   ·   Önizleme: {'var' if mod.has_preview else 'yok'}", 12).pack(anchor="w")
        muted(left, str(mod.path), 11).pack(anchor="w")
        actions = ctk.CTkFrame(box, fg_color="transparent")
        actions.grid(row=0, column=1, padx=14)
        ghost_btn(actions, "Düzenle", lambda m=mod: self.edit(m), width=90).pack(side="left", padx=4)
        danger_btn(actions, "Kaldır", lambda m=mod: self.remove(m), width=80).pack(side="left", padx=4)

    # --- eylemler -------------------------------------------------------
    def edit(self, mod: ModTrack):
        EditModDialog(self, self.app, mod, self.refresh)

    def remove(self, mod: ModTrack):
        if not messagebox.askyesno("Modu kaldır", f"'{mod.name}' oyunun mod klasöründen silinsin mi?"):
            return
        self.app.mods.remove(mod.name)
        self.refresh()

    def add_archive(self):
        path = filedialog.askopenfilename(title="Mod arşivini seçin",
                                          filetypes=[("Mod arşivi", "*.zip *.7z"), ("Tüm dosyalar", "*.*")])
        if path:
            self._install(path)

    def add_folder(self):
        path = filedialog.askdirectory(title="Açılmış mod klasörünü seçin")
        if path:
            self._install(path)

    def _install(self, path: str):
        run_task(self, "Mod kuruluyor", lambda p: self.app.mods.install(path, True, p), self._installed)

    def _installed(self, names, err):
        if err:
            error(str(err), "Mod kurulamadı")
            return
        self.refresh()
        mods = {m.name: m for m in self.app.mods.scan()}
        for name in names:
            if name in mods:
                EditModDialog(self, self.app, mods[name], self.refresh)

    def open_dir(self):
        folder = self.app.mods.tracks_dir
        folder.mkdir(parents=True, exist_ok=True)
        if hasattr(os, "startfile"):
            os.startfile(str(folder))  # type: ignore[attr-defined]
        else:
            webbrowser.open(str(folder))
