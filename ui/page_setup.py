"""İlk kurulum sihirbazı."""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from evo_core.detect import find_server_folders
from evo_core.paths import default_mods_root
from evo_core.servers import validate_server_folder

from . import theme as T
from .widgets import card, ghost_btn, muted, primary_btn, run_bg, title

STEPS = ["Hoş geldiniz", "Sunucu klasörü", "Mod klasörü", "Hazır"]


class SetupPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=T.BG)
        self.app = app
        self.step = 0
        self.server_var = ctk.StringVar(value=app.cfg["evo_server_path"])
        self.mods_var = ctk.StringVar(value=app.cfg["mods_root"] or str(default_mods_root()))
        self.detected: list[Path] = []
        self.server_var.trace_add("write", lambda *_: self._validate_server())

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.box = card(self, width=760, height=520)
        self.box.grid(row=0, column=0)
        self.box.grid_propagate(False)
        self.box.grid_rowconfigure(1, weight=1)
        self.box.grid_columnconfigure(0, weight=1)

        self.header = ctk.CTkFrame(self.box, fg_color="transparent")
        self.header.grid(row=0, column=0, sticky="ew", padx=32, pady=(26, 0))
        self.body = ctk.CTkFrame(self.box, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=32, pady=10)
        footer = ctk.CTkFrame(self.box, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=32, pady=(0, 26))
        self.back_btn = ghost_btn(footer, "← Geri", self.back, width=100)
        self.back_btn.pack(side="left")
        self.next_btn = primary_btn(footer, "İleri →", self.next, width=140)
        self.next_btn.pack(side="right")

    # ------------------------------------------------------------------
    def on_show(self, **_kw):
        self.step = 0
        self.server_var.set(self.app.cfg["evo_server_path"])
        self._render()

    def on_hide(self):
        pass

    def _render(self):
        for w in self.header.winfo_children():
            w.destroy()
        for w in self.body.winfo_children():
            w.destroy()
        dots = ctk.CTkFrame(self.header, fg_color="transparent")
        dots.pack(anchor="w")
        for i, name in enumerate(STEPS):
            active = i == self.step
            ctk.CTkLabel(dots, text=f"{i + 1}  {name}", font=T.font(12, active),
                         text_color=T.ACCENT if active else (T.TEXT if i < self.step else T.MUTED)
                         ).pack(side="left", padx=(0, 18))
        self.back_btn.configure(state="normal" if self.step > 0 else "disabled")
        self.next_btn.configure(text="Başla ✓" if self.step == len(STEPS) - 1 else "İleri →", state="normal")
        [self._welcome, self._server, self._mods, self._done][self.step]()

    def back(self):
        if self.step > 0:
            self.step -= 1
            self._render()

    def next(self):
        if self.step == 1:
            ok, _ = validate_server_folder(self.server_var.get())
            if not ok:
                return
        if self.step == 2:
            try:
                (Path(self.mods_var.get()) / "content" / "tracks").mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                self.mods_msg.configure(text=f"Klasör oluşturulamadı: {exc}", text_color=T.RED)
                return
        if self.step == len(STEPS) - 1:
            self.app.finish_setup(self.server_var.get().strip(), self.mods_var.get().strip())
            return
        self.step += 1
        self._render()

    # --- adımlar ------------------------------------------------------
    def _welcome(self):
        title(self.body, "EVO Server Manager'a hoş geldiniz", 24).pack(anchor="w", pady=(24, 8))
        muted(self.body, "Assetto Corsa EVO sunucularınızı tek pencereden kurun, başlatın ve canlı konsoldan "
                         "izleyin. Şifre, tarayıcı ya da ekstra kurulum yok.", 14).pack(anchor="w", fill="x")
        self.body.winfo_children()[-1].configure(wraplength=660)
        tips = ["Sunucuyu oluşturma, başlatma, durdurma ve canlı konsol",
                "İndirdiğiniz pist modlarını tek tıkla kurma",
                "Pist, hava, oturum süreleri, araçlar ve ağırlık/kısıtlayıcı ayarları",
                "Çöken sunucuyu otomatik yeniden başlatma"]
        for tip in tips:
            ctk.CTkLabel(self.body, text=f"•  {tip}", font=T.font(13), text_color=T.TEXT, anchor="w"
                         ).pack(anchor="w", pady=3, padx=(4, 0))
        muted(self.body, "Kurulum yaklaşık bir dakika sürer: 2 klasör seçeceksiniz.", 12).pack(anchor="w", pady=(24, 0))

    def _server(self):
        title(self.body, "EVO Dedicated Server klasörü", 20).pack(anchor="w", pady=(18, 4))
        muted(self.body, "İçinde AssettoCorsaEVOServer.exe bulunan klasör. Steam'deki kurulum otomatik aranıyor.",
              13).pack(anchor="w")
        self.found_box = ctk.CTkFrame(self.body, fg_color="transparent")
        self.found_box.pack(fill="x", pady=(10, 0))
        self.found_label = muted(self.found_box, "Aranıyor...", 12)
        self.found_label.pack(anchor="w")
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", pady=(14, 4))
        ctk.CTkEntry(row, textvariable=self.server_var, height=34, fg_color=T.CARD2, border_color=T.BORDER,
                     text_color=T.TEXT).pack(side="left", fill="x", expand=True)
        ghost_btn(row, "Gözat", self._browse_server, width=80).pack(side="left", padx=(8, 0))
        self.server_msg = ctk.CTkLabel(self.body, text="", font=T.font(12), anchor="w", justify="left", wraplength=660)
        self.server_msg.pack(anchor="w", pady=(4, 0))
        self._validate_server()
        run_bg(self, find_server_folders, self._on_found)

    def _on_found(self, result, _err):
        if not self.found_label.winfo_exists():
            return
        self.detected = list(result or [])
        self.found_label.destroy()
        if not self.detected:
            muted(self.found_box, "Otomatik bulunamadı. Aşağıdan 'Gözat' ile klasörü seçin.", 12).pack(anchor="w")
            return
        muted(self.found_box, "Bulunan kurulumlar (tıklayarak seçin):", 12).pack(anchor="w")
        for path in self.detected[:4]:
            ctk.CTkRadioButton(self.found_box, text=str(path), value=str(path), variable=self.server_var,
                               fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.TEXT,
                               font=T.font(12)).pack(anchor="w", pady=3)
        if not self.server_var.get():
            self.server_var.set(str(self.detected[0]))

    def _browse_server(self):
        chosen = filedialog.askdirectory(title="EVO Dedicated Server klasörünü seçin")
        if chosen:
            self.server_var.set(str(Path(chosen)))

    def _validate_server(self):
        if self.step != 1 or not hasattr(self, "server_msg") or not self.server_msg.winfo_exists():
            return
        ok, msg = validate_server_folder(self.server_var.get())
        self.server_msg.configure(text=("✔ " if ok else "✖ ") + msg, text_color=T.GREEN if ok else T.MUTED)
        self.next_btn.configure(state="normal" if ok else "disabled")

    def _mods(self):
        title(self.body, "Mod klasörü", 20).pack(anchor="w", pady=(18, 4))
        muted(self.body, "Oyun, pist modlarını bu klasörün içindeki 'content\\tracks' altından okur. "
                         "Klasör yoksa otomatik oluşturulur; elle oluşturmanıza gerek yok.", 13).pack(anchor="w")
        self.body.winfo_children()[-1].configure(wraplength=660)
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", pady=(16, 4))
        ctk.CTkEntry(row, textvariable=self.mods_var, height=34, fg_color=T.CARD2, border_color=T.BORDER,
                     text_color=T.TEXT).pack(side="left", fill="x", expand=True)
        ghost_btn(row, "Gözat", self._browse_mods, width=80).pack(side="left", padx=(8, 0))
        self.mods_msg = ctk.CTkLabel(self.body, text="Varsayılan: Kullanıcı\\Saved Games\\ACE\\mods",
                                     font=T.font(12), text_color=T.MUTED, anchor="w")
        self.mods_msg.pack(anchor="w", pady=(4, 0))

    def _browse_mods(self):
        chosen = filedialog.askdirectory(title="Mod klasörünü seçin")
        if chosen:
            self.mods_var.set(str(Path(chosen)))

    def _done(self):
        title(self.body, "Her şey hazır", 22).pack(anchor="w", pady=(24, 10))
        for label, value in (("Sunucu klasörü", self.server_var.get()), ("Mod klasörü", self.mods_var.get())):
            ctk.CTkLabel(self.body, text=label, font=T.font(11, True), text_color=T.MUTED, anchor="w").pack(anchor="w")
            ctk.CTkLabel(self.body, text=value, font=T.font(13), text_color=T.TEXT, anchor="w",
                         wraplength=660, justify="left").pack(anchor="w", pady=(0, 10))
        muted(self.body, "'Başla'ya basınca sunucular sayfası açılır. İlk sunucuyu oluştururken sunucu dosyaları "
                         "kopyalanır; bu birkaç dakika sürebilir.", 13).pack(anchor="w", pady=(8, 0))
        self.body.winfo_children()[-1].configure(wraplength=660)
