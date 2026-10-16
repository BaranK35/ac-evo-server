"""Ortak arayüz parçaları: butonlar, formlar, ilerleme penceresi."""
from __future__ import annotations

import os
import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import theme as T


def card(parent, **kw) -> ctk.CTkFrame:
    return ctk.CTkFrame(parent, fg_color=T.CARD, corner_radius=12, border_width=1, border_color=T.BORDER, **kw)


def primary_btn(parent, text, command, width=140, **kw) -> ctk.CTkButton:
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=34, corner_radius=8,
                         fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color="white",
                         font=T.font(13, True), **kw)


def ghost_btn(parent, text, command, width=110, **kw) -> ctk.CTkButton:
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=34, corner_radius=8,
                         fg_color=T.CARD2, hover_color=T.BORDER, text_color=T.TEXT,
                         border_width=1, border_color=T.BORDER, font=T.font(13), **kw)


def danger_btn(parent, text, command, width=90, **kw) -> ctk.CTkButton:
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=34, corner_radius=8,
                         fg_color="#3a1d1f", hover_color="#5a2326", text_color=T.RED,
                         border_width=1, border_color="#5a2326", font=T.font(13), **kw)


def title(parent, text, size=22) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=T.font(size, True), text_color=T.TEXT, anchor="w")


def muted(parent, text, size=12, **kw) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=T.font(size), text_color=T.MUTED, anchor="w",
                        justify="left", **kw)


def section(parent, text) -> ctk.CTkLabel:
    lbl = ctk.CTkLabel(parent, text=text.upper(), font=T.font(11, True), text_color=T.ACCENT, anchor="w")
    lbl.pack(fill="x", pady=(18, 2))
    return lbl


def info(msg: str, heading: str = "Bilgi") -> None:
    messagebox.showinfo(heading, msg)


def error(msg: str, heading: str = "Hata") -> None:
    messagebox.showerror(heading, msg)


# ---------------------------------------------------------------- arka plan işleri
def run_bg(master, work, on_done) -> None:
    """work() arka planda çalışır; on_done(sonuç, hata) ana iş parçacığında çağrılır."""
    state = {"done": False, "result": None, "error": None}

    def target():
        try:
            state["result"] = work()
        except Exception as exc:  # noqa: BLE001
            state["error"] = exc
        finally:
            state["done"] = True

    threading.Thread(target=target, daemon=True).start()

    def poll():
        if state["done"]:
            on_done(state["result"], state["error"])
        else:
            master.after(100, poll)

    poll()


class TaskDialog(ctk.CTkToplevel):
    def __init__(self, master, heading: str):
        super().__init__(master)
        self.title(heading)
        self.geometry("460x170")
        self.resizable(False, False)
        self.configure(fg_color=T.CARD)
        self.transient(master.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        ctk.CTkLabel(self, text=heading, font=T.font(16, True), text_color=T.TEXT).pack(pady=(22, 6))
        self.msg = ctk.CTkLabel(self, text="Hazırlanıyor...", font=T.font(12), text_color=T.MUTED)
        self.msg.pack()
        self.bar = ctk.CTkProgressBar(self, width=380, progress_color=T.ACCENT, fg_color=T.CARD2)
        self.bar.pack(pady=18)
        self._mode = None
        self._set_mode("indeterminate")
        self.after(150, self._grab)

    def _grab(self):
        try:
            self.grab_set()
        except Exception:  # noqa: BLE001
            pass

    def _set_mode(self, mode: str):
        if mode == self._mode:
            return
        self._mode = mode
        self.bar.configure(mode=mode)
        if mode == "indeterminate":
            self.bar.start()
        else:
            self.bar.stop()

    def update_state(self, state: dict):
        total, cur = state["total"], state["cur"]
        if total > 0:
            self._set_mode("determinate")
            self.bar.set(cur / total)
            self.msg.configure(text=f"{cur}/{total}  ·  {state['msg'][:48]}")
        else:
            self._set_mode("indeterminate")
            self.msg.configure(text=state["msg"] or "Çalışıyor...")


def run_task(master, heading: str, work, on_done=None) -> None:
    """work(progress_cb) arka planda çalışır, ilerleme penceresi gösterilir."""
    state = {"cur": 0, "total": 0, "msg": "", "done": False, "result": None, "error": None}

    def progress(cur, total, msg):
        state.update(cur=cur, total=total, msg=msg)

    def target():
        try:
            state["result"] = work(progress)
        except Exception as exc:  # noqa: BLE001
            state["error"] = exc
        finally:
            state["done"] = True

    dialog = TaskDialog(master, heading)
    threading.Thread(target=target, daemon=True).start()

    def poll():
        if state["done"]:
            try:
                dialog.grab_release()
            except Exception:  # noqa: BLE001
                pass
            dialog.destroy()
            if on_done:
                on_done(state["result"], state["error"])
            return
        dialog.update_state(state)
        master.after(100, poll)

    poll()


# ---------------------------------------------------------------- form oluşturucu
class Field:
    def __init__(self, key, label, kind="str", options=None, hint="", width=260):
        self.key, self.label, self.kind = key, label, kind
        self.options = options or []      # choice için [(değer, etiket), ...]
        self.hint, self.width = hint, width


class Form:
    """Alan tanımlarından satırlar üretir ve değerleri tipli olarak geri toplar."""

    def __init__(self, parent, fields: list[Field], data: dict, label_width=250, on_change=None):
        self.fields = fields
        self.vars: dict = {}
        self.maps: dict = {}
        self.on_change = on_change or {}
        for f in fields:
            self._row(parent, f, data.get(f.key), label_width)

    def _row(self, parent, f: Field, value, label_width):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(6, 0))
        row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(row, text=f.label, width=label_width, anchor="w", font=T.font(13),
                     text_color=T.TEXT).grid(row=0, column=0, sticky="w", padx=(0, 12))
        holder = ctk.CTkFrame(row, fg_color="transparent")
        holder.grid(row=0, column=1, sticky="w")

        if f.kind == "bool":
            var = ctk.BooleanVar(value=bool(value))
            ctk.CTkSwitch(holder, text="", variable=var, progress_color=T.ACCENT, width=46,
                          command=lambda k=f.key: self._fire(k)).pack(side="left")
        elif f.kind == "choice":
            self.maps[f.key] = {label: val for val, label in f.options}
            rev = {val: label for val, label in f.options}
            current = rev.get(value, f.options[0][1] if f.options else "")
            var = ctk.StringVar(value=current)
            ctk.CTkOptionMenu(holder, values=[l for _v, l in f.options], variable=var, width=f.width,
                              fg_color=T.CARD2, button_color=T.BORDER, button_hover_color=T.ACCENT,
                              dropdown_fg_color=T.CARD2, dropdown_hover_color=T.BORDER,
                              text_color=T.TEXT, font=T.font(13),
                              command=lambda _l, k=f.key: self._fire(k)).pack(side="left")
        else:
            var = ctk.StringVar(value="" if value is None else str(value))
            ctk.CTkEntry(holder, textvariable=var, width=f.width, height=32, fg_color=T.CARD2,
                         border_color=T.BORDER, text_color=T.TEXT, font=T.font(13)).pack(side="left")
            if f.kind in ("folder", "file"):
                ghost_btn(holder, "Gözat", lambda v=var, k=f.kind: self._browse(v, k), width=70).pack(
                    side="left", padx=(8, 0))
        self.vars[f.key] = var
        if f.hint:
            muted(row, f.hint, 11).grid(row=1, column=1, sticky="w", pady=(2, 0))

    def _browse(self, var, kind):
        chosen = (filedialog.askdirectory() if kind == "folder"
                  else filedialog.asksaveasfilename(confirmoverwrite=False))
        if chosen:
            var.set(os.path.normpath(chosen))

    def _fire(self, key):
        callback = self.on_change.get(key)
        if callback:
            callback(self.get(key))

    def get(self, key):
        f = next(x for x in self.fields if x.key == key)
        var = self.vars[key]
        if f.kind == "choice":
            return self.maps[key].get(var.get())
        return var.get()

    def set(self, key, value):
        f = next(x for x in self.fields if x.key == key)
        if f.kind == "choice":
            rev = {val: label for val, label in f.options}
            self.vars[key].set(rev.get(value, f.options[0][1]))
        else:
            self.vars[key].set(value)

    def collect(self) -> dict:
        out = {}
        for f in self.fields:
            raw = self.get(f.key)
            if f.kind == "int":
                try:
                    out[f.key] = int(float(str(raw).strip()))
                except ValueError:
                    raise ValueError(f"'{f.label}' bir sayı olmalı.") from None
            elif f.kind == "float":
                text = str(raw).strip().replace(",", ".") or "0"
                try:
                    out[f.key] = float(text)
                except ValueError:
                    raise ValueError(f"'{f.label}' bir sayı olmalı.") from None
            elif f.kind == "bool":
                out[f.key] = bool(raw)
            else:
                out[f.key] = str(raw).strip() if f.kind != "choice" else raw
        return out
