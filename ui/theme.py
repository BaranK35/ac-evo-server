"""Renkler ve yazı tipleri."""
import customtkinter as ctk

BG = "#0d0f13"
SIDEBAR = "#11141a"
CARD = "#171b23"
CARD2 = "#1e232d"
BORDER = "#2a303c"
ACCENT = "#e5322d"
ACCENT_HOVER = "#c42823"
GREEN = "#2ecc71"
AMBER = "#f5a623"
RED = "#ff5c5c"
CYAN = "#5ec2ff"
TEXT = "#e8eaed"
MUTED = "#8b93a1"
CONSOLE_BG = "#090b0f"
FONT_FAMILY = "Segoe UI"
MONO = "Consolas"


def font(size: int = 13, bold: bool = False) -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight="bold" if bold else "normal")
