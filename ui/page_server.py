"""Tek sunucunun sayfası: Konsol, ayarlar, pist/hava, araçlar, sonuçlar."""
from __future__ import annotations

import os
import re
import time
import webbrowser
from tkinter import filedialog, messagebox

import customtkinter as ctk

from evo_core.servers import ServerError

from . import theme as T
from .widgets import (Field, Form, error, ghost_btn, info, muted, primary_btn, section, title)

TABS = ["Konsol", "Genel", "Oturum", "Pist & Hava", "Araçlar", "Gelişmiş", "Sonuçlar"]

SESSION_TYPES = [("MultiplayerServerListSessionType_RANKED", "Ranked"),
                 ("MultiplayerServerListSessionType_UNRANKED", "Unranked")]
GAME_TYPES = [("GameModeType_PRACTICE", "Practice"), ("GameModeType_RACE_WEEKEND", "Race Weekend")]
WEATHER = [("GameModeSelectionWeatherType_CLEAR", "Açık"),
           ("GameModeSelectionWeatherType_SCATTERED_CLOUDS", "Az bulutlu"),
           ("GameModeSelectionWeatherType_BROKEN_CLOUDS", "Parçalı bulutlu"),
           ("GameModeSelectionWeatherType_OVERCAST", "Kapalı"),
           ("GameModeSelectionWeatherType_DRIZZLE", "Çisenti"),
           ("GameModeSelectionWeatherType_RAIN", "Yağmur"),
           ("GameModeSelectionWeatherType_HEAVY_RAIN", "Şiddetli yağmur"),
           ("GameModeSelectionWeatherType_DAMP", "Nemli")]
BEHAVIOUR = [("GameModeSelectionWeatherBehaviour_STATIC", "Sabit"),
             ("GameModeSelectionWeatherBehaviour_DYNAMIC", "Dinamik")]
GRIP = [("InitialGrip_GREEN", "Green (yeni asfalt)"), ("InitialGrip_FAST", "Fast"),
        ("InitialGrip_OPTIMUM", "Optimum")]
DURATION = [("GameModeSelectionDuration_TIME", "Süre"), ("GameModeSelectionDuration_LAPS", "Tur")]
TUNING = [("TuningAllowed", "İzinli"), ("TuningDenied", "Yasak")]


def session_fields(prefix: str) -> list[Field]:
    return [
        Field(f"{prefix}_length", "Süre (saniye)", "int", hint="Race için 'Tur' seçildiyse tur sayısı"
              if prefix == "race" else ""),
        Field(f"{prefix}_hour", "Başlangıç saati (0-23)", "int", width=100),
        Field(f"{prefix}_minute", "Başlangıç dakikası", "int", width=100),
        Field(f"{prefix}_time_multiplier", "Zaman çarpanı", "int", width=100),
        Field(f"{prefix}_max_wait_to_box", "Pite dönmek için azami bekleme (sn)", "int", width=100),
        Field(f"{prefix}_overtime", "Ek süre (sn)", "int", width=100),
    ]


def command_text(args: list[str]) -> str:
    return " ".join(f'"{a}"' if (" " in a or not a) else a for a in args)


# =============================================================================
class ConsoleView(ctk.CTkFrame):
    ERR = re.compile(r"error|fail|exception|fatal|crash|cannot|can't|could not|unable|invalid", re.I)
    WARN = re.compile(r"warn", re.I)

    def __init__(self, master, runner, sid: str, connection_text: str):
        super().__init__(master, fg_color="transparent")
        self.runner, self.sid = runner, sid
        self.ms = runner.get(sid)
        self.seq = 0
        self._job = None
        self._filter_job = None

        muted(self, connection_text, 12).pack(fill="x", pady=(2, 8))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 8))
        self.filter_var = ctk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self._schedule_rerender())
        ctk.CTkEntry(bar, textvariable=self.filter_var, placeholder_text="Konsolda ara / filtrele...", width=280,
                     height=32, fg_color=T.CARD2, border_color=T.BORDER).pack(side="left")
        self.auto_var = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(bar, text="Otomatik kaydır", variable=self.auto_var, progress_color=T.ACCENT,
                      font=T.font(12), text_color=T.MUTED).pack(side="left", padx=16)
        ghost_btn(bar, "Kaydet", self.save_log, width=80).pack(side="right", padx=(6, 0))
        ghost_btn(bar, "Temizle", self.clear, width=80).pack(side="right", padx=(6, 0))
        ghost_btn(bar, "Kopyala", self.copy_all, width=80).pack(side="right")

        self.text = ctk.CTkTextbox(self, fg_color=T.CONSOLE_BG, text_color="#cfd4dc", wrap="none",
                                   font=ctk.CTkFont(family=T.MONO, size=12), border_width=1,
                                   border_color=T.BORDER, corner_radius=8)
        self.text.pack(fill="both", expand=True)
        self.text.tag_config("ts", foreground="#586070")
        self.text.tag_config("out", foreground="#cfd4dc")
        self.text.tag_config("sys", foreground=T.CYAN)
        self.text.tag_config("err", foreground=T.RED)
        self.text.tag_config("warn", foreground=T.AMBER)
        self.text.configure(state="disabled")
        self.hint = muted(self, "", 11)
        self.hint.pack(fill="x", pady=(6, 0))
        self._pull()

    # --- akış -----------------------------------------------------------
    def _pull(self):
        items, newest = self.ms.since(self.seq)
        self.seq = newest
        if items:
            self._append(items)
        if not self.ms.lines:
            self.hint.configure(text="Sunucu başlatıldığında çıktısı burada canlı görünür.")
        else:
            self.hint.configure(text=f"{len(self.ms.lines)} satır")
        self._job = self.after(200, self._pull)

    def stop(self):
        for job in (self._job, self._filter_job):
            if job:
                try:
                    self.after_cancel(job)
                except Exception:  # noqa: BLE001
                    pass
        self._job = self._filter_job = None

    def _tag_for(self, kind: str, line: str) -> str:
        if kind in ("sys", "err"):
            return kind
        if self.ERR.search(line):
            return "err"
        if self.WARN.search(line):
            return "warn"
        return "out"

    def _append(self, items):
        needle = self.filter_var.get().strip().lower()
        rows = [(ts, line, self._tag_for(kind, line)) for _s, ts, kind, line in items
                if not needle or needle in line.lower()]
        if not rows:
            return
        self.text.configure(state="normal")
        for ts, line, tag in rows:
            self.text.insert("end", ts + "  ", "ts")
            self.text.insert("end", line + "\n", tag)
        total = int(self.text.index("end-1c").split(".")[0])
        if total > 6000:
            self.text.delete("1.0", f"{total - 5000}.0")
        self.text.configure(state="disabled")
        if self.auto_var.get():
            self.text.see("end")

    def _schedule_rerender(self):
        if self._filter_job:
            self.after_cancel(self._filter_job)
        self._filter_job = self.after(300, self._rerender)

    def _rerender(self):
        self._filter_job = None
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        items, newest = self.ms.since(0)
        self.seq = newest
        self._append(items)

    # --- araçlar --------------------------------------------------------
    def _plain(self) -> str:
        return "\n".join(f"{ts}  {line}" for _s, ts, _k, line in list(self.ms.lines))

    def copy_all(self):
        self.clipboard_clear()
        self.clipboard_append(self._plain())

    def clear(self):
        self.ms.clear()
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self.seq = self.ms.seq

    def save_log(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=f"{self.sid}_konsol.txt",
                                            filetypes=[("Metin", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self._plain())


# =============================================================================
class ServerPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=T.BG)
        self.app = app
        self.sid: str | None = None
        self.data: dict = {}
        self.forms: list[Form] = []
        self.console: ConsoleView | None = None
        self._job = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.holder = ctk.CTkFrame(self, fg_color="transparent")
        self.holder.grid(row=0, column=0, sticky="nsew")

    # --- yaşam döngüsü -------------------------------------------------------
    def on_show(self, sid: str, tab: str = "Konsol", **_kw):
        self.sid = sid
        try:
            self.data = self.app.store.load(sid)
        except ServerError as exc:
            error(str(exc))
            self.app.show("servers")
            return
        self._build(tab)
        self._tick()

    def on_hide(self):
        if self._job:
            self.after_cancel(self._job)
            self._job = None
        if self.console:
            self.console.stop()

    def _build(self, tab: str):
        if self.console:
            self.console.stop()
        for w in self.holder.winfo_children():
            w.destroy()
        self.forms = []
        self.holder.grid_columnconfigure(0, weight=1)
        self.holder.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(self.holder, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 10))
        ghost_btn(head, "←  Sunucular", lambda: self.app.show("servers"), width=120).pack(side="left")
        names = ctk.CTkFrame(head, fg_color="transparent")
        names.pack(side="left", padx=16)
        title(names, self.data.get("name", self.sid), 22).pack(anchor="w")
        self.status = muted(names, "", 12)
        self.status.pack(anchor="w")
        self.toggle_btn = primary_btn(head, "▶  Başlat", self.toggle, width=120)
        self.toggle_btn.pack(side="right")
        ghost_btn(head, "Kaydet & Yeniden Başlat", self.save_restart, width=190).pack(side="right", padx=8)
        ghost_btn(head, "Kaydet", lambda: self.save(), width=90).pack(side="right")

        self.tabs = ctk.CTkTabview(
            self.holder, fg_color=T.CARD, corner_radius=12, border_width=1, border_color=T.BORDER,
            segmented_button_fg_color=T.CARD2, segmented_button_selected_color=T.ACCENT,
            segmented_button_selected_hover_color=T.ACCENT_HOVER, segmented_button_unselected_color=T.CARD2,
            segmented_button_unselected_hover_color=T.BORDER, text_color=T.TEXT)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 20))
        frames = {name: self.tabs.add(name) for name in TABS}

        self._console_tab(frames["Konsol"])
        self._general_tab(self._scroll(frames["Genel"]))
        self._session_tab(self._scroll(frames["Oturum"]))
        self._track_tab(self._scroll(frames["Pist & Hava"]))
        self._cars_tab(frames["Araçlar"])
        self._advanced_tab(self._scroll(frames["Gelişmiş"]))
        self._results_tab(frames["Sonuçlar"])
        self.tabs.set(tab if tab in TABS else "Konsol")

    @staticmethod
    def _scroll(parent):
        frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True)
        return frame

    def _tick(self):
        ms = self.app.runner.get(self.sid)
        if ms.running:
            up = int(time.time() - ms.started_at)
            self.status.configure(text=f"● Çalışıyor  ·  PID {ms.pid}  ·  {up // 3600:02d}:{up % 3600 // 60:02d}:{up % 60:02d}",
                                  text_color=T.GREEN)
            self.toggle_btn.configure(text="■  Durdur", fg_color="#3a1d1f", hover_color="#5a2326", text_color=T.RED)
        else:
            self.status.configure(text="● Durdu", text_color=T.MUTED)
            self.toggle_btn.configure(text="▶  Başlat", fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                                      text_color="white")
        self._job = self.after(1000, self._tick)

    # --- başlat / durdur / kaydet -------------------------------------------------
    def toggle(self):
        if self.app.runner.is_running(self.sid):
            self.app.runner.stop(self.sid)
            return
        if not self.save(silent=True):
            return
        self._start()

    def _start(self):
        try:
            self.app.runner.start(self.sid)
            self.tabs.set("Konsol")
        except ServerError as exc:
            error(str(exc), "Sunucu başlatılamadı")

    def save_restart(self):
        if not self.save(silent=True):
            return
        self.app.runner.stop(self.sid)
        self._start()

    def _collect(self) -> dict:
        merged = dict(self.data)
        for form in self.forms:
            merged.update(form.collect())
        event = self.track_map.get(self.track_var.get())
        if event:
            merged.update(track=event["track"], layout=event["layout"], event_name=event["event_name"],
                          track_length=int(event["track_length"]), track_is_mod=bool(event.get("mod")))
        merged["cars"] = self._collect_cars()
        return merged

    def save(self, silent: bool = False) -> bool:
        try:
            merged = self._collect()
        except ValueError as exc:
            error(str(exc), "Ayar kaydedilemedi")
            return False
        clash = self._port_conflicts(merged)
        if clash:
            messagebox.showwarning("Port çakışması", clash)
        self.data = merged
        self.app.store.save(self.sid, merged)
        if not silent:
            info("Ayarlar kaydedildi. Sunucu çalışıyorsa değişiklikler yeniden başlatınca uygulanır.", "Kaydedildi")
        return True

    def _port_conflicts(self, merged: dict) -> str:
        mine = {merged["tcp_port"], merged["udp_port"], merged["http_port"]}
        for other in self.app.store.ids():
            if other == self.sid:
                continue
            o = self.app.store.load(other)
            shared = mine & {o.get("tcp_port"), o.get("udp_port"), o.get("http_port")}
            if shared:
                return (f"'{o.get('name')}' sunucusu ile ortak port var: {sorted(shared)}.\n"
                        "Aynı anda çalışacak sunucular farklı portlar kullanmalı.")
        return ""

    # --- sekmeler ----------------------------------------------------------------
    def _console_tab(self, frame):
        ip = self.app.local_ip()
        text = (f"Yerel ağdan bağlantı: {ip}:{self.data.get('tcp_port')}    ·    HTTP {self.data.get('http_port')}"
                f"    ·    İnternetten bağlanılacaksa TCP/UDP {self.data.get('tcp_port')} portunu modemde yönlendirin ve "
                "güvenlik duvarında izin verin.")
        self.console = ConsoleView(frame, self.app.runner, self.sid, text)
        self.console.pack(fill="both", expand=True)

    def _add_form(self, parent, fields) -> Form:
        form = Form(parent, fields, self.data)
        self.forms.append(form)
        return form

    def _general_tab(self, p):
        section(p, "Sunucu")
        self._add_form(p, [
            Field("name", "Sunucu adı", width=360),
            Field("max_players", "Azami oyuncu", "int", width=100),
            Field("type", "Liste türü", "choice", SESSION_TYPES),
            Field("cycle", "Oturumları döngüde çalıştır", "bool"),
        ])
        section(p, "Portlar")
        self._add_form(p, [
            Field("tcp_port", "TCP portu", "int", width=100),
            Field("udp_port", "UDP portu", "int", width=100, hint="TCP ile aynı olması önerilir"),
            Field("http_port", "HTTP portu", "int", width=100),
        ])
        section(p, "Şifreler")
        self._add_form(p, [
            Field("driver_password", "Sürücü şifresi", hint="Boşsa herkes katılabilir"),
            Field("spectator_password", "İzleyici şifresi"),
            Field("admin_password", "Yönetici şifresi"),
        ])

    def _session_tab(self, p):
        section(p, "Oturum modu")
        weekend = ctk.CTkFrame(p, fg_color="transparent")

        def toggle_weekend(value):
            if value == "GameModeType_RACE_WEEKEND":
                weekend.pack(fill="x")
            else:
                weekend.pack_forget()

        self._add_form(p, [Field("game_type", "Oyun modu", "choice", GAME_TYPES)])
        self.forms[-1].on_change["game_type"] = toggle_weekend
        section(p, "Practice")
        self._add_form(p, session_fields("practice"))
        section(weekend, "Qualify")
        self._add_form(weekend, session_fields("qualify"))
        section(weekend, "Warmup")
        self._add_form(weekend, session_fields("warmup"))
        section(weekend, "Yarış")
        self._add_form(weekend, [Field("race_duration_type", "Yarış uzunluğu türü", "choice", DURATION)]
                       + session_fields("race") + [
            Field("min_waiting_for_players", "Oyuncuları bekleme (en az, sn)", "int", width=100),
            Field("max_waiting_for_players", "Oyuncuları bekleme (en çok, sn)", "int", width=100)])
        section(weekend, "Zorunlu pit stop")
        self._add_form(weekend, [
            Field("mandatory_pitstop", "Zorunlu pit stop", "bool", hint="Yalnızca süreli ve 1200 sn'den uzun yarışlarda geçerli"),
            Field("mandatory_pitstop_tyre_change", "Lastik değişimi zorunlu", "bool"),
            Field("mandatory_pitstop_refuel", "Yakıt ikmali zorunlu", "bool"),
            Field("pit_window_time", "Pit penceresi (sn)", "int", width=100)])
        toggle_weekend(self.data.get("game_type"))

    def _catalog(self) -> list[dict]:
        mods = self.app.mods.track_events()
        keys = {(m["track"], m["layout"]) for m in mods}
        base = [dict(e, mod=False) for e in self.app.store.events(self.sid)
                if (e.get("track"), e.get("layout")) not in keys]
        return sorted(base, key=lambda e: (e["track"].lower(), e["layout"].lower())) + mods

    @staticmethod
    def _track_label(e: dict) -> str:
        km = int(e.get("track_length", 0)) / 1000
        return f"{'★ MOD  ' if e.get('mod') else ''}{e['track']}  —  {e['layout']}   ({km:.2f} km)"

    def _track_tab(self, p):
        section(p, "Pist")
        events = self._catalog()
        current = (self.data.get("track"), self.data.get("layout"))
        self.track_map = {self._track_label(e): e for e in events}
        selected = next((self._track_label(e) for e in events if (e["track"], e["layout"]) == current), None)
        if selected is None:
            saved = {"track": current[0], "layout": current[1], "event_name": self.data.get("event_name", ""),
                     "track_length": self.data.get("track_length", 0), "mod": bool(self.data.get("track_is_mod"))}
            selected = "(Kayıtlı)  " + self._track_label(saved)
            self.track_map[selected] = saved
        self.track_var = ctk.StringVar(value=selected)
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x", pady=(6, 0))
        ctk.CTkOptionMenu(row, values=list(self.track_map), variable=self.track_var, width=560,
                          fg_color=T.CARD2, button_color=T.BORDER, button_hover_color=T.ACCENT,
                          dropdown_fg_color=T.CARD2, dropdown_hover_color=T.BORDER, text_color=T.TEXT,
                          font=T.font(13)).pack(side="left")
        ghost_btn(row, "Mod pisti ekle", lambda: self.app.show("mods"), width=130).pack(side="left", padx=10)
        muted(p, "★ MOD ile başlayanlar Modlar sayfasından kurduğunuz pistlerdir. Oyuncuların da aynı modu "
                 "kurmuş olması gerekir.", 12).pack(anchor="w", pady=(6, 0))
        section(p, "Hava ve zemin")
        self._add_form(p, [
            Field("weather", "Hava durumu", "choice", WEATHER),
            Field("weather_behavior", "Hava davranışı", "choice", BEHAVIOUR),
            Field("initial_grip", "Başlangıç gribi", "choice", GRIP),
        ])

    # --- araçlar -------------------------------------------------------------------
    def _cars_tab(self, frame):
        cars = self.app.store.cars(self.sid)
        chosen = {c.get("car_name"): c for c in self.data.get("cars", [])}
        known = {c.get("name") for c in cars}
        self._unknown_cars = [c for name, c in chosen.items() if name not in known]
        self.car_rows: list[dict] = []

        bar = ctk.CTkFrame(frame, fg_color="transparent")
        bar.pack(fill="x", pady=(2, 8))
        self.car_filter = ctk.StringVar()
        self.car_filter.trace_add("write", lambda *_: self._filter_cars())
        ctk.CTkEntry(bar, textvariable=self.car_filter, placeholder_text="Araç ara...", width=240, height=32,
                     fg_color=T.CARD2, border_color=T.BORDER).pack(side="left")
        ghost_btn(bar, "Tümünü seç", lambda: self._set_all(True), width=100).pack(side="left", padx=(10, 4))
        ghost_btn(bar, "Hiçbiri", lambda: self._set_all(False), width=80).pack(side="left")
        self.car_count = muted(bar, "", 12)
        self.car_count.pack(side="right")

        if not cars:
            muted(frame, "cars.json bulunamadı. Sunucu klasörünü kontrol edin (Ayarlar > Sunucu dosyalarını güncelle).",
                  13).pack(anchor="w", pady=20)
            return
        header = ctk.CTkFrame(frame, fg_color=T.CARD2, corner_radius=6)
        header.pack(fill="x")
        for text, width in (("Araç", 330), ("PI", 60), ("P1", 50), ("P2", 50), ("P3", 50), ("Ağırlık (kg)", 100), ("Kısıtlayıcı", 100)):
            ctk.CTkLabel(header, text=text, width=width, anchor="w", font=T.font(11, True),
                         text_color=T.MUTED).pack(side="left", padx=(8, 0), pady=6)
        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        scroll.grid_columnconfigure(0, weight=1)
        for i, car in enumerate(cars):
            name = car.get("name")
            sel = chosen.get(name)
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.grid(row=i, column=0, sticky="ew")
            var = ctk.BooleanVar(value=sel is not None)
            ctk.CTkCheckBox(row, text=car.get("display_name", name), variable=var, width=330,
                            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, border_color=T.BORDER,
                            text_color=T.TEXT, font=T.font(13), command=self._update_car_count
                            ).pack(side="left", padx=(8, 0), pady=3)
            pi = car.get("performance_indicator", 0)
            for text, width in ((f"{float(pi):.1f}", 60), (str(car.get("property_1", "")), 50),
                                (str(car.get("property_2", "")), 50), (str(car.get("property_3", "")), 50)):
                ctk.CTkLabel(row, text=text, width=width, anchor="w", font=T.font(12),
                             text_color=T.MUTED).pack(side="left", padx=(8, 0))
            ballast = ctk.StringVar(value=str((sel or {}).get("ballast", 0)))
            restrictor = ctk.StringVar(value=str((sel or {}).get("restrictor", 0)))
            for v in (ballast, restrictor):
                ctk.CTkEntry(row, textvariable=v, width=90, height=28, fg_color=T.CARD2,
                             border_color=T.BORDER).pack(side="left", padx=(8, 0))
            self.car_rows.append({"name": name, "label": car.get("display_name", name), "var": var,
                                  "ballast": ballast, "restrictor": restrictor, "row": row, "index": i})
        self._update_car_count()

    def _update_car_count(self):
        count = sum(1 for r in self.car_rows if r["var"].get())
        self.car_count.configure(text=f"{count} araç seçili")

    def _set_all(self, value: bool):
        needle = self.car_filter.get().strip().lower()
        for r in self.car_rows:
            if not needle or needle in r["label"].lower():
                r["var"].set(value)
        self._update_car_count()

    def _filter_cars(self):
        needle = self.car_filter.get().strip().lower()
        for r in self.car_rows:
            if not needle or needle in r["label"].lower():
                r["row"].grid(row=r["index"], column=0, sticky="ew")
            else:
                r["row"].grid_remove()

    def _collect_cars(self) -> list[dict]:
        out = []
        for r in getattr(self, "car_rows", []):
            if not r["var"].get():
                continue
            try:
                out.append({"car_name": r["name"], "ballast": int(float(r["ballast"].get() or 0)),
                            "restrictor": int(float(r["restrictor"].get() or 0))})
            except ValueError:
                raise ValueError(f"'{r['label']}' için ağırlık/kısıtlayıcı sayı olmalı.") from None
        if not getattr(self, "car_rows", []):
            return list(self.data.get("cars", []))
        return out + list(self._unknown_cars)

    # --- gelişmiş ------------------------------------------------------------------
    def _advanced_tab(self, p):
        section(p, "Ağ ve denge")
        self._add_form(p, [
            Field("netcode_update_interval", "Netcode güncelleme aralığı", "int", width=100),
            Field("tuning_type", "Tuning", "choice", TUNING),
            Field("pi_min", "En düşük PI", "float", width=100, hint="0 = sınırsız"),
            Field("pi_max", "En yüksek PI", "float", width=100, hint="0 = sınırsız"),
        ])
        section(p, "Entry list ve sonuç gönderme")
        self._add_form(p, [
            Field("entry_list_server_url", "Entry list sunucu adresi", width=420),
            Field("token", "Token", width=420),
            Field("entry_list_path", "Entry list dosyası", "file", width=420),
            Field("results_post_url", "Sonuç gönderme adresi", width=420),
            Field("results_path", "Sonuç klasörü", "folder", width=420),
        ])
        section(p, "Başlatma")
        self._add_form(p, [
            Field("log_file_path", "Log dosyası", "file", width=420),
            Field("extra_arguments", "Ek başlatma argümanları", width=420),
            Field("custom_command", "Özel komut (Kunos launcher'dan)", width=420,
                  hint="Doluysa uygulamanın ürettiği komutun yerine geçer"),
        ])
        ghost_btn(p, "Başlatma komutunu göster", self.show_command, width=210).pack(anchor="w", pady=(16, 0))

    def show_command(self):
        try:
            merged = self._collect()
            cmd = self.app.store.build_command(self.sid, merged)
        except (ValueError, ServerError) as exc:
            error(str(exc))
            return
        dlg = ctk.CTkToplevel(self)
        dlg.title("Başlatma komutu")
        dlg.geometry("820x340")
        dlg.configure(fg_color=T.CARD)
        box = ctk.CTkTextbox(dlg, wrap="word", font=ctk.CTkFont(family=T.MONO, size=11), fg_color=T.CONSOLE_BG)
        box.pack(fill="both", expand=True, padx=16, pady=(16, 8))
        box.insert("1.0", command_text(cmd))

        def copy():
            self.clipboard_clear()
            self.clipboard_append(command_text(cmd))

        ghost_btn(dlg, "Kopyala", copy, width=100).pack(pady=(0, 14))
        dlg.after(150, lambda: dlg.focus())

    # --- sonuçlar --------------------------------------------------------------------
    def _results_tab(self, frame):
        bar = ctk.CTkFrame(frame, fg_color="transparent")
        bar.pack(fill="x", pady=(2, 8))
        self.results_list = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        ghost_btn(bar, "Yenile", self._fill_results, width=80).pack(side="left")
        ghost_btn(bar, "Klasörü aç", self._open_results_dir, width=110).pack(side="left", padx=8)
        self.results_list.pack(fill="both", expand=True)
        self._fill_results()

    def _fill_results(self):
        for w in self.results_list.winfo_children():
            w.destroy()
        files = self.app.store.result_files(self.sid)
        if not files:
            muted(self.results_list, "Henüz sonuç dosyası yok. Oturumlar bittikçe burada listelenir.", 13).pack(
                anchor="w", pady=16)
            return
        for f in files:
            row = ctk.CTkFrame(self.results_list, fg_color=T.CARD2, corner_radius=8)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=f["name"], font=T.font(13), text_color=T.TEXT, anchor="w").pack(side="left", padx=12, pady=8)
            muted(row, f"{f['modified']}   ·   {f['size'] / 1024:.1f} KB", 12).pack(side="left")
            ghost_btn(row, "Aç", lambda p=f["path"]: self._open(p), width=60).pack(side="right", padx=8, pady=4)

    def _open_results_dir(self):
        folder = self.app.store.result_dir(self.sid, self.data)
        folder.mkdir(parents=True, exist_ok=True)
        self._open(str(folder))

    @staticmethod
    def _open(path: str):
        if hasattr(os, "startfile"):
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            webbrowser.open(path)
