"""EVO Dedicated Server klasörünü (Steam vb.) otomatik bulur."""
from __future__ import annotations

import os
import re
from pathlib import Path

from .servers import SERVER_EXE


def steam_roots() -> list[Path]:
    roots: list[Path] = []
    try:
        import winreg  # type: ignore
        for hive, key, value in (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
        ):
            try:
                with winreg.OpenKey(hive, key) as handle:
                    roots.append(Path(winreg.QueryValueEx(handle, value)[0]))
            except OSError:
                pass
    except ImportError:
        pass
    for env in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
        base = os.environ.get(env)
        if base:
            roots.append(Path(base) / "Steam")
    return roots


def steam_libraries() -> list[Path]:
    libs: list[Path] = []
    for root in steam_roots():
        libs.append(root)
        vdf = root / "steamapps" / "libraryfolders.vdf"
        try:
            text = vdf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in re.finditer(r'"path"\s+"([^"]+)"', text):
            libs.append(Path(match.group(1).replace("\\\\", "\\")))
    unique, seen = [], set()
    for lib in libs:
        key = str(lib).lower()
        if key not in seen and lib.is_dir():
            seen.add(key)
            unique.append(lib)
    return unique


def find_server_folders(extra_dirs: list[Path] | None = None) -> list[Path]:
    """İçinde AssettoCorsaEVOServer.exe bulunan klasörleri döndürür."""
    found: list[Path] = []
    candidates: list[Path] = list(extra_dirs or [])
    for lib in steam_libraries():
        common = lib / "steamapps" / "common"
        if common.is_dir():
            candidates.extend(p for p in common.iterdir() if p.is_dir() and "assetto" in p.name.lower())
    for drive in "CDEFG":
        for sub in ("", "Games", "Program Files", "Program Files (x86)"):
            base = Path(f"{drive}:/") / sub
            try:
                if base.is_dir():
                    candidates.extend(p for p in base.iterdir() if p.is_dir() and "assetto" in p.name.lower())
            except OSError:
                pass
    seen = set()
    for cand in candidates:
        for folder in (cand, *(cand / s for s in ("server", "Server", "DedicatedServer"))):
            try:
                if (folder / SERVER_EXE).is_file() and str(folder).lower() not in seen:
                    seen.add(str(folder).lower())
                    found.append(folder)
            except OSError:
                pass
        # bir seviye daha derine bak
        try:
            for sub in cand.iterdir():
                if sub.is_dir() and (sub / SERVER_EXE).is_file() and str(sub).lower() not in seen:
                    seen.add(str(sub).lower())
                    found.append(sub)
        except OSError:
            pass
    return found
