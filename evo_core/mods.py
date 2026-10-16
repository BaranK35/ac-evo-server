"""Pist ve araç modları: algılama, kurma (oyun + sunucu klasörü), eşitleme ve sunucu listelerine ekleme."""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .servers import ServerError, copy_tree, load_json
from . import kspkg

ProgressCb = Callable[[int, int, str], None]
SUBDIR = {"track": "tracks", "car": "cars"}
SEVEN_ZIP_CANDIDATES = (r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class ModItem:
    kind: str       # "track" | "car" | "kspkg"
    name: str
    root: str       # kaynak içinde göreli klasör ("" = kaynağın kökü)


# --------------------------------------------------------------------- algılama
def analyze_paths(paths: Iterable[str]) -> list[ModItem]:
    """Dosya yollarından (klasör ya da arşiv listesi) pist/araç modlarını çıkarır."""
    found: dict[tuple[str, str], ModItem] = {}
    for raw in paths:
        parts = raw.replace("\\", "/").strip("/").split("/")
        if not parts or not parts[-1]:
            continue
        fname, low = parts[-1], [x.lower() for x in parts]
        if low[-1].endswith(".kspkg"):
            found.setdefault(("kspkg", fname), ModItem("kspkg", fname, "/".join(parts[:-1])))
        elif low[-1].endswith(".track"):
            found.setdefault(("track", fname[:-6]), ModItem("track", fname[:-6], "/".join(parts[:-1])))
        elif low[-1].endswith(".car"):
            found.setdefault(("car", fname[:-4]), ModItem("car", fname[:-4], "/".join(parts[:-1])))
        for i in range(1, len(parts) - 2):
            if low[i] == "cars" and low[i - 1] == "content":
                found.setdefault(("car", parts[i + 1]), ModItem("car", parts[i + 1], "/".join(parts[:i + 2])))
            elif low[i] == "tracks" and low[i - 1] == "content":
                found.setdefault(("track", parts[i + 1]), ModItem("track", parts[i + 1], "/".join(parts[:i + 2])))
    return sorted(found.values(), key=lambda m: (m.kind, m.name.lower()))


def walk_relative(base: Path, limit: int = 300_000) -> list[str]:
    out: list[str] = []
    for root, _dirs, files in os.walk(base):
        rel = Path(root).relative_to(base).as_posix()
        for name in files:
            out.append(name if rel == "." else f"{rel}/{name}")
            if len(out) >= limit:
                return out
    return out


def find_seven_zip() -> str | None:
    return shutil.which("7z") or shutil.which("7za") or next((c for c in SEVEN_ZIP_CANDIDATES if os.path.isfile(c)), None)


def list_archive(src: Path) -> list[str]:
    suffix = src.suffix.lower()
    if suffix == ".zip":
        with zipfile.ZipFile(src) as zf:
            return zf.namelist()
    seven = find_seven_zip()
    if seven:
        res = subprocess.run([seven, "l", "-slt", "-ba", str(src)], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
        return [line[7:].strip() for line in res.stdout.splitlines() if line.startswith("Path = ")]
    if suffix == ".7z":
        try:
            import py7zr  # type: ignore
            with py7zr.SevenZipFile(src) as archive:
                return archive.getnames()
        except ImportError:
            pass
    raise ServerError("Bu arşivi okumak için 7-Zip gerekli (https://www.7-zip.org). Ya da arşivi açıp klasör olarak ekleyin.")


def extract_archive(src: Path, dest: Path, progress: ProgressCb | None = None) -> None:
    suffix = src.suffix.lower()
    if progress:
        progress(0, 0, "Arşiv açılıyor...")
    if suffix == ".zip":
        with zipfile.ZipFile(src) as zf:
            members = zf.infolist()
            for i, member in enumerate(members, 1):
                zf.extract(member, dest)
                if progress and i % 25 == 0:
                    progress(i, len(members), member.filename)
        return
    seven = find_seven_zip()
    if seven:
        res = subprocess.run([seven, "x", "-y", f"-o{dest}", str(src)], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
        if res.returncode not in (0, 1):
            raise ServerError(f"7-Zip arşivi açamadı:\n{(res.stderr or res.stdout)[-400:]}")
        return
    if suffix == ".7z":
        try:
            import py7zr  # type: ignore
        except ImportError:
            raise ServerError("Bu .7z dosyasını açmak için 7-Zip gerekli.") from None
        with py7zr.SevenZipFile(src) as archive:
            archive.extractall(dest)
        return
    raise ServerError("Desteklenen türler: klasör, .zip, .7z")


def folder_size(path: Path) -> int:
    total = 0
    for root, _d, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def read_layouts(folder: Path, name: str) -> tuple[str, list[str]]:
    text, layouts = "", []
    try:
        text = (folder / f"{name}.track").read_text(encoding="utf-8-sig", errors="replace").strip()
    except OSError:
        pass
    if text:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                for key, value in parsed.items():
                    if "layout" in key.lower():
                        layouts += [str(v) for v in (value if isinstance(value, list) else [value])
                                    if isinstance(v, (str, int))]
        except ValueError:
            pass
    containers = folder / "containers"
    if containers.is_dir():
        layouts += [s.stem[len("layout_"):] for s in sorted(containers.glob("layout_*.scene"))]
        for s in sorted(containers.glob("*.scene")):
            if "freeroam" in s.stem.lower() and "freeroam" not in layouts:
                layouts.append("freeroam")
    layouts_dir = folder / "layouts"
    if layouts_dir.is_dir():
        layouts += [s.stem for s in sorted(layouts_dir.glob("*.track_layout"))]
        layouts += [s.stem[len("layout_"):] if s.stem.startswith("layout_") else s.stem
                    for s in sorted(layouts_dir.glob("*.scene"))]
    for s in sorted(folder.glob("layout_*.scene")):
        layouts.append(s.stem[len("layout_"):])
    out: list[str] = []
    for item in layouts:
        if item and item not in out:
            out.append(item)
    if not out:
        out = ["Default"]
    return text, out


def pretty(name: str) -> str:
    return name.replace("_", " ").strip().title()


# --------------------------------------------------------------------- yönetici
class ModManager:
    def __init__(self, game_root, server_root, registry_path: Path, mirror: bool = True):
        self.game_root, self.server_root = Path(game_root), Path(server_root)
        self.mirror = mirror
        self.registry_path = Path(registry_path)
        self._sizes: dict[str, tuple[float, int]] = {}
        data = load_json(self.registry_path, {})
        if "tracks" not in data and "cars" not in data:      # eski düz biçim
            data = {"tracks": data if isinstance(data, dict) else {}, "cars": {}}
        data.setdefault("tracks", {})
        data.setdefault("cars", {})
        self.registry = data

    def configure(self, game_root, server_root, mirror: bool) -> None:
        self.game_root, self.server_root, self.mirror = Path(game_root), Path(server_root), mirror

    def targets(self) -> list[Path]:
        return [self.game_root] + ([self.server_root] if self.mirror else [])

    def dir_for(self, root: Path, kind: str) -> Path:
        return root / "content" / SUBDIR[kind]

    # --- tarama ----------------------------------------------------------
    def _names(self, root: Path, kind: str) -> list[str]:
        base = self.dir_for(root, kind)
        if not base.is_dir():
            return []
        out = []
        for p in base.iterdir():
            if not p.is_dir():
                continue
            if kind == "track" and not any(p.glob("*.track")):
                continue
            out.append(p.name)
        return out

    def _kspkg_files(self) -> dict[str, tuple[Path, bool, bool]]:
        """Oyun ve sunucu mod klasörlerindeki .kspkg dosyalarını listeler."""
        found: dict[str, tuple[Path, bool, bool]] = {}
        roots = [(self.game_root, True), (self.server_root, False)]
        for root, is_game in roots:
            if not root.is_dir():
                continue
            for p in root.glob("*.kspkg"):
                fname = p.name
                if fname not in found:
                    in_game = (self.game_root / fname).is_file()
                    in_server = (self.server_root / fname).is_file() if self.mirror else in_game
                    found[fname] = (p, in_game, in_server)
        return found

    def scan(self, kind: str) -> list[dict]:
        """Klasör ve .kspkg modlarını tarar; arayüzü dondurmaz."""
        names = sorted(set(self._names(self.game_root, kind)) | set(self._names(self.server_root, kind)), key=str.lower)
        items = []
        for name in names:
            in_game = (self.dir_for(self.game_root, kind) / name).is_dir()
            in_server = (self.dir_for(self.server_root, kind) / name).is_dir()
            folder = self.dir_for(self.game_root if in_game else self.server_root, kind) / name
            item = {"kind": kind, "name": name, "path": str(folder), "in_game": in_game, "in_server": in_server,
                    "size": self.cached_size(folder), "has_map": (folder / "ui" / "map.svg").is_file(),
                    "has_preview": (folder / "ui" / "previews.json").is_file(), "layouts": [], "track_text": "",
                    "is_kspkg": False}
            if kind == "track":
                item["track_text"], item["layouts"] = read_layouts(folder, name)
            item["entry"] = self.entry_for(kind, name, item)
            items.append(item)

        # .kspkg arşiv modlarını ekle
        kspkg_dict = self._kspkg_files()
        seen_kspkg_names = set()
        for fname, (pkg_path, in_game, in_server) in kspkg_dict.items():
            try:
                pkg = kspkg.inspect_package_cached(pkg_path)
                if kind == "track":
                    for t in pkg.tracks:
                        if t.name in seen_kspkg_names:
                            continue
                        seen_kspkg_names.add(t.name)
                        item = {
                            "kind": "track",
                            "name": t.name,
                            "path": str(pkg_path),
                            "in_game": in_game,
                            "in_server": in_server,
                            "size": pkg.size,
                            "has_map": False,
                            "has_preview": False,
                            "layouts": list(t.layouts),
                            "track_text": f".kspkg arşivi: {fname}",
                            "is_kspkg": True,
                            "kspkg_file": fname
                        }
                        item["entry"] = self.entry_for("track", t.name, item)
                        items.append(item)
                elif kind == "car":
                    for c in pkg.cars:
                        for v in c.variants:
                            c_id = v.preset_id
                            if c_id in seen_kspkg_names:
                                continue
                            seen_kspkg_names.add(c_id)
                            item = {
                                "kind": "car",
                                "name": c_id,
                                "path": str(pkg_path),
                                "in_game": in_game,
                                "in_server": in_server,
                                "size": pkg.size,
                                "has_map": False,
                                "has_preview": False,
                                "layouts": [],
                                "track_text": f".kspkg arşivi: {fname}",
                                "is_kspkg": True,
                                "kspkg_file": fname,
                                "entry": {
                                    "name": c_id,
                                    "display_name": v.display_name,
                                    "runtime_name": c.runtime_name,
                                    "performance_indicator": 50.0,
                                    "property_1": 0, "property_2": 0, "property_3": 0
                                }
                            }
                            items.append(item)
            except Exception:
                continue

        return items

    def cached_size(self, folder: Path) -> int | None:
        try:
            mtime = folder.stat().st_mtime
        except OSError:
            return None
        hit = self._sizes.get(str(folder))
        return hit[1] if hit and hit[0] == mtime else None

    def compute_sizes(self) -> None:
        for kind in SUBDIR:
            for item in self.scan(kind):
                folder = Path(item["path"])
                try:
                    self._sizes[str(folder)] = (folder.stat().st_mtime, folder_size(folder))
                except OSError:
                    pass

    def map_data_uri(self, name: str, kind: str = "track") -> str | None:
        for root in (self.game_root, self.server_root):
            folder = self.dir_for(root, kind) / name / "ui"
            for ext in ("png", "jpg", "jpeg"):
                img = folder / f"preview.{ext}"
                try:
                    if img.is_file() and img.stat().st_size < 2_000_000:
                        import mimetypes
                        mime = mimetypes.guess_type(img.name)[0] or "image/png"
                        return f"data:{mime};base64," + base64.b64encode(img.read_bytes()).decode("ascii")
                except OSError:
                    pass
            if kind == "track":
                svg = folder / "map.svg"
                try:
                    if svg.is_file() and svg.stat().st_size < 400_000:
                        return "data:image/svg+xml;base64," + base64.b64encode(svg.read_bytes()).decode("ascii")
                except OSError:
                    pass
        return None

    # --- kayıt (sunucuya bildirilen bilgiler) ------------------------------
    def entry_for(self, kind: str, name: str, item: dict | None = None) -> dict:
        bucket = SUBDIR[kind]
        if kind == "track":
            layouts = (item or {}).get("layouts") or []
            layout = layouts[0] if layouts else "Default"
            entry = {"track": name, "layout": layout, "event_name": f"{layout} Time Attack",
                     "track_length": 5000, "max_pit_slot": 20}
        else:
            entry = {"name": name, "display_name": pretty(name), "performance_indicator": 50.0,
                     "property_1": 0, "property_2": 0, "property_3": 0}
        entry.update(self.registry[bucket].get(name, {}))
        return entry

    def set_entry(self, kind: str, name: str, entry: dict) -> None:
        self.registry[SUBDIR[kind]][name] = entry
        self._save()

    def _save(self) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.registry_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.registry, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, self.registry_path)

    def track_events(self) -> list[dict]:
        out = []
        for item in self.scan("track"):
            e = item["entry"]
            layouts = list(item.get("layouts") or [])
            if not layouts:
                layouts = [e.get("layout") or "Default"]
            for l in layouts:
                aliases = list(dict.fromkeys([e.get("track"), item.get("name"), pretty(item.get("name"))]))
                for t in aliases:
                    if t:
                        out.append({
                            "track": t, "layout": l, "event_name": f"{t} {l}",
                            "track_length": int(e.get("track_length", 5000)),
                            "max_pit_slot": int(e.get("max_pit_slot", 20)),
                            "spawns": [], "mod": True, "mod_folder": item["name"]
                        })
        return out

    def car_entries(self) -> list[dict]:
        return [dict(item["entry"], mod=True) for item in self.scan("car")]

    # --- inceleme / kurulum ---------------------------------------------------
    def inspect_source(self, src: str | Path) -> dict:
        src = Path(src)
        info = {"path": str(src), "name": src.name, "items": [], "error": "", "is_archive": src.is_file()}
        try:
            if src.is_dir():
                paths = walk_relative(src)
            elif src.suffix.lower() in (".zip", ".7z", ".rar"):
                paths = list_archive(src)
            else:
                info["error"] = "Desteklenmeyen dosya türü (klasör, .zip veya .7z olmalı)."
                return info
            items = analyze_paths(paths)
            info["items"] = [{"kind": m.kind, "name": m.name,
                              "installed": (self.dir_for(self.game_root, m.kind) / m.name).is_dir()} for m in items]
            if not items:
                info["error"] = "Bu pakette tanınan bir pist ya da araç modu bulunamadı."
        except (OSError, zipfile.BadZipFile, ServerError) as exc:
            info["error"] = str(exc)
        return info

    def install(self, src: str | Path, progress: ProgressCb | None = None) -> list[dict]:
        src = Path(src)
        if not src.exists():
            raise ServerError("Seçilen dosya ya da klasör bulunamadı.")

        # Doğrudan .kspkg dosyası kurulumu
        if src.is_file() and src.suffix.lower() == ".kspkg":
            done = []
            for root in self.targets():
                root.mkdir(parents=True, exist_ok=True)
                dst = root / src.name
                shutil.copy2(src, dst)
            try:
                pkg = kspkg.inspect_package_cached(src)
                for t in pkg.tracks:
                    done.append({"kind": "track", "name": t.name})
                for c in pkg.cars:
                    done.append({"kind": "car", "name": c.display_name})
            except Exception:
                pass
            if not done:
                done.append({"kind": "kspkg", "name": src.name})
            return done

        temp: Path | None = None
        try:
            if src.is_dir():
                base = src
            else:
                temp = Path(tempfile.mkdtemp(prefix="evo_mod_"))
                extract_archive(src, temp, progress)
                base = temp

            # Arşiv içinde .kspkg dosyaları var mı kontrol et
            kspkg_in_archive = list(base.rglob("*.kspkg"))
            if kspkg_in_archive:
                done = []
                for k_file in kspkg_in_archive:
                    for root in self.targets():
                        root.mkdir(parents=True, exist_ok=True)
                        dst = root / k_file.name
                        shutil.copy2(k_file, dst)
                    try:
                        pkg = kspkg.inspect_package_cached(k_file)
                        for t in pkg.tracks:
                            done.append({"kind": "track", "name": t.name})
                        for c in pkg.cars:
                            done.append({"kind": "car", "name": c.display_name})
                    except Exception:
                        done.append({"kind": "kspkg", "name": k_file.name})
                if done:
                    return done

            items = analyze_paths(walk_relative(base))
            if not items:
                raise ServerError("Bu pakette tanınan bir pist ya da araç modu bulunamadı. "
                                  "Mod dosyası .kspkg, .track veya .car içermelidir.")
            done = []
            for item in items:
                source_dir = base / item.root if item.root else base
                first = True
                for root in self.targets():
                    dst = self.dir_for(root, item.kind) / item.name
                    if dst.exists():
                        shutil.rmtree(dst, ignore_errors=True)
                    if first:
                        copy_tree(source_dir, dst, progress)
                        first_dst = dst
                        first = False
                    else:                                   # ikinci hedef: aynı diskteyse anında (sabit bağ)
                        copy_tree(first_dst, dst, progress, link=True)
                done.append({"kind": item.kind, "name": item.name})
            return done
        finally:
            if temp:
                shutil.rmtree(temp, ignore_errors=True)

    def remove(self, kind: str, name: str) -> None:
        for root in (self.game_root, self.server_root):
            shutil.rmtree(self.dir_for(root, kind) / name, ignore_errors=True)
        self.registry[SUBDIR[kind]].pop(name, None)
        self._save()

    def sync_to_server(self, progress: ProgressCb | None = None) -> list[str]:
        """Oyun mod klasöründe olup sunucu klasöründe olmayan modları sunucu tarafına getirir (sunucu çökmesinin ana nedeni)."""
        if not self.mirror:
            return []
        copied = []
        for kind in SUBDIR:
            for name in self._names(self.game_root, kind):
                dst = self.dir_for(self.server_root, kind) / name
                if not dst.is_dir():
                    copy_tree(self.dir_for(self.game_root, kind) / name, dst, progress, link=True)
                    copied.append(name)
        return copied

    # --- sunucu dosyalarına ekleme ---------------------------------------------------
    def inject_events(self, server_dir: Path) -> int:
        events, added = self.track_events(), 0
        for fname in ("events_practice.json", "events_race_weekend.json", "events_freeroam.json"):
            path = Path(server_dir) / fname
            if not path.is_file():
                continue
            doc = load_json(path, None)
            if not isinstance(doc, dict) or not isinstance(doc.get("events"), list):
                continue
            known = {(str(e.get("track")).lower(), str(e.get("layout")).lower()) for e in doc["events"]}
            fresh = [ev for ev in events if (str(ev["track"]).lower(), str(ev["layout"]).lower()) not in known]
            if fresh:
                self._backup_write(path, doc, "events", [{k: ev[k] for k in (
                    "track", "layout", "event_name", "track_length", "max_pit_slot", "spawns")} for ev in fresh])
                added += len(fresh)
        return added

    def inject_cars(self, server_dir: Path) -> int:
        path = Path(server_dir) / "cars.json"
        doc = load_json(path, None)
        if not isinstance(doc, dict) or not isinstance(doc.get("cars"), list):
            return 0
        known = {c.get("name") for c in doc["cars"]}
        fresh = [{k: c[k] for k in ("name", "display_name", "performance_indicator", "property_1", "property_2",
                                     "property_3")} for c in self.car_entries() if c["name"] not in known]
        if fresh:
            self._backup_write(path, doc, "cars", fresh)
        return len(fresh)

    @staticmethod
    def _backup_write(path: Path, doc: dict, key: str, extra: list) -> None:
        backup = path.with_suffix(".json.bak")
        if not backup.exists():
            shutil.copy2(path, backup)
        doc[key] = doc[key] + extra
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1, ensure_ascii=False)

    # --- pist testi adayları -------------------------------------------------------
    def probe_candidates(self, name: str) -> list[tuple[str, str]]:
        items = {i["name"]: i for i in self.scan("track")}
        item = items.get(name)
        if not item:
            return []
        entry = item["entry"]
        tracks = list(dict.fromkeys([entry["track"], name, name.lower(), pretty(name)]))
        layouts = list(dict.fromkeys([entry["layout"], *item["layouts"], "freeroam", "default", "Default", "GP"]))
        return [(t, l) for t in tracks for l in layouts][:16]
