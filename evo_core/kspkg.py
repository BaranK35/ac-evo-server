"""AC EVO .kspkg paket okuyucusu ve ayrıştırıcısı.

Zino1337 (acevo-server) ve ACEvo.Package spesifikasyonuna dayanır.
Paketler son 64 MiB veya 32 MiB içinde dosya tablosunu (file table) tutar.
Kunos'un statik XOR anahtarı (0x9F9721A97D1135C1) ile şifrelenmiş girdileri
ve protobuf başlıklarını belleğe yüklemeden ayrıştırır.
"""

from __future__ import annotations

import os
import struct
import threading
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

XOR_KEY = 0x9F9721A97D1135C1
XOR_BYTES = XOR_KEY.to_bytes(8, "little")
TABLE_SIZES = (0x4000000, 0x2000000)
ENTRY_SIZE = 0x100
ENTRY_STRUCT = struct.Struct("<224siHhQqq")
FLAG_DIRECTORY = 1
FLAG_ENCRYPTED = 1 << 8
MAX_METADATA_SIZE = 8 * 1024 * 1024


class KspkgError(ValueError):
    """Paket okuma hatası."""


@dataclass(frozen=True)
class PackageEntry:
    path: str
    flags: int
    size: int
    offset: int


@dataclass(frozen=True)
class ModVariant:
    preset_id: str
    display_name: str


@dataclass(frozen=True)
class ModCar:
    display_name: str
    variants: tuple[ModVariant, ...]
    runtime_name: str = ""


@dataclass(frozen=True)
class ModTrack:
    name: str
    display_name: str
    layouts: tuple[str, ...]
    track_file: str = ""


@dataclass(frozen=True)
class ModPackage:
    filename: str
    size: int
    cars: tuple[ModCar, ...]
    tracks: tuple[ModTrack, ...] = ()

    @property
    def preset_ids(self) -> tuple[str, ...]:
        return tuple(variant.preset_id for car in self.cars for variant in car.variants)


_cache_lock = threading.Lock()
_package_cache: dict[tuple[str, int, int], ModPackage] = {}
_runtime_name_cache: dict[tuple[str, int, int], dict[str, str]] = {}


def _xor(data: bytes) -> bytes:
    return bytes(v ^ XOR_BYTES[i % len(XOR_BYTES)] for i, v in enumerate(data))


def _decode_entry(raw: bytes, data_end: int, *, require_content_path: bool = False) -> tuple[PackageEntry | None, int]:
    if len(raw) != ENTRY_SIZE:
        raise KspkgError("truncated file table")
    name_buffer, _unknown, flags, name_length, path_hash, size, offset = ENTRY_STRUCT.unpack(_xor(raw))
    if path_hash == 0:
        return None, path_hash
    if name_length <= 0 or name_length > len(name_buffer):
        raise KspkgError("invalid file name length in file table")
    try:
        name = name_buffer[:name_length].decode("ascii")
    except UnicodeDecodeError as exc:
        raise KspkgError("non-ASCII file name in file table") from exc
    if require_content_path and not name.lower().startswith("content\\"):
        raise KspkgError("file table does not start with a content path")
    if size < 0 or offset < 0 or offset > data_end or size > data_end - offset:
        raise KspkgError(f"invalid offset or size for {name}")
    return PackageEntry(name, flags, size, offset), path_hash


def _table_size(handle, file_size: int) -> int:
    for table_size in TABLE_SIZES:
        if file_size <= table_size:
            continue
        handle.seek(file_size - table_size)
        raw = handle.read(ENTRY_SIZE)
        try:
            entry, _path_hash = _decode_entry(raw, file_size - table_size, require_content_path=True)
        except KspkgError:
            continue
        if entry is not None:
            return table_size
    raise KspkgError("could not detect a supported KSPKG file table")


def read_entries(path: Path) -> tuple[PackageEntry, ...]:
    """Paket dosya tablosunu belleğe yığmadan doğrular ve listeler."""
    try:
        file_size = path.stat().st_size
        with path.open("rb") as handle:
            table_size = _table_size(handle, file_size)
            table_start = file_size - table_size
            handle.seek(table_start)
            entries: list[PackageEntry] = []
            for _ in range(table_size // ENTRY_SIZE):
                entry, _path_hash = _decode_entry(handle.read(ENTRY_SIZE), table_start)
                if entry is None:
                    break
                entries.append(entry)
            else:
                raise KspkgError("file table has no terminator")
    except OSError as exc:
        raise KspkgError(f"cannot read package: {exc}") from exc
    if not entries:
        raise KspkgError("empty KSPKG file table")
    return tuple(entries)


def _read_entry(path: Path, entry: PackageEntry) -> bytes:
    if entry.flags & FLAG_DIRECTORY:
        return b""
    if entry.size > MAX_METADATA_SIZE:
        raise KspkgError(f"metadata file is unexpectedly large: {entry.path}")
    try:
        with path.open("rb") as handle:
            handle.seek(entry.offset)
            data = handle.read(entry.size)
    except OSError as exc:
        raise KspkgError(f"cannot read {entry.path}: {exc}") from exc
    if len(data) != entry.size:
        raise KspkgError(f"truncated metadata file: {entry.path}")
    return _xor(data) if entry.flags & FLAG_ENCRYPTED else data


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while offset < len(data) and shift < 70:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7
    raise KspkgError("invalid protobuf varint")


def _protobuf_strings(data: bytes) -> dict[int, list[str]]:
    fields: dict[int, list[str]] = {}
    offset = 0
    while offset < len(data):
        key, offset = _read_varint(data, offset)
        field_number, wire_type = key >> 3, key & 7
        if field_number <= 0:
            raise KspkgError("invalid protobuf field")
        if wire_type == 0:
            _value, offset = _read_varint(data, offset)
        elif wire_type == 1:
            offset += 8
        elif wire_type == 2:
            length, offset = _read_varint(data, offset)
            end = offset + length
            if length < 0 or end > len(data):
                raise KspkgError("truncated protobuf field")
            raw = data[offset:end]
            offset = end
            try:
                value = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if value.isprintable() and value.strip():
                fields.setdefault(field_number, []).append(value.strip())
        elif wire_type == 5:
            offset += 4
        else:
            raise KspkgError("unsupported protobuf wire type")
        if offset > len(data):
            raise KspkgError("truncated protobuf value")
    return fields


def _car_root(internal_path: str) -> str:
    parts = internal_path.replace("/", "\\").split("\\")
    if len(parts) >= 3 and parts[0].lower() == "content" and parts[1].lower() == "cars":
        return "\\".join(parts[:3]).lower()
    return str(PureWindowsPath(internal_path).parent).lower()


def _runtime_name(root: str) -> str:
    return PureWindowsPath(root).name


def _fallback_car_name(root: str, package_stem: str) -> str:
    tail = package_stem or PureWindowsPath(root).name
    return tail.replace("_", " ").strip().title() or package_stem


def _variant_label(fields: dict[int, list[str]], preset_id: str) -> str:
    candidates = [*(fields.get(2) or []), *(fields.get(3) or [])]
    generic = {"standard", "modded car base preset", "base preset", "default"}
    for candidate in candidates:
        if candidate.casefold().replace("_", " ") not in generic:
            return candidate
    for candidate in candidates:
        if candidate:
            return candidate
    return preset_id


def inspect_package(path: Path) -> ModPackage:
    entries = read_entries(path)
    car_names: dict[str, str] = {}
    variants: dict[str, list[tuple[str, str]]] = {}
    tracks_map: dict[str, set[str]] = {}

    for entry in entries:
        norm = entry.path.replace("/", "\\")
        lower = norm.lower()

        # Araç Modları
        if lower.endswith(".moddedcarcontent"):
            fields = _protobuf_strings(_read_entry(path, entry))
            display_name = (fields.get(4) or [""])[0]
            if display_name:
                car_names[_car_root(norm)] = display_name
        elif lower.endswith(".mechanicalcarpreset"):
            preset_id = PureWindowsPath(norm).stem
            if preset_id:
                fields = _protobuf_strings(_read_entry(path, entry))
                variants.setdefault(_car_root(norm), []).append((preset_id, _variant_label(fields, preset_id)))

        # Pist Modları (content\tracks\<track_name>\...)
        parts = norm.split("\\")
        if len(parts) >= 3 and parts[0].lower() == "content" and parts[1].lower() == "tracks":
            t_name = parts[2]
            tracks_map.setdefault(t_name, set())
            fname = parts[-1].lower()
            if fname.startswith("layout_") and fname.endswith(".scene"):
                l_name = fname[len("layout_"):-len(".scene")].strip("_")
                tracks_map[t_name].add(l_name)
            elif fname.endswith(".scene") and not fname.startswith("camera_") and not fname.startswith("marshall") and not fname.startswith("barriers_"):
                base_scene = fname[:-len(".scene")].strip("_")
                if base_scene and base_scene != t_name.lower():
                    tracks_map[t_name].add(base_scene)
            if "freeroam" in lower or "traffic" in lower:
                tracks_map[t_name].add("freeroam")

    # Araçları oluştur
    cars: list[ModCar] = []
    multiple_variants = sum(len(v) for v in variants.values()) > 1
    for root, raw_variants in sorted(variants.items()):
        car_name = car_names.get(root) or _fallback_car_name(root, path.stem)
        rendered = []
        for preset_id, variant_name in sorted(raw_variants):
            display_name = f"{car_name} - {variant_name}" if multiple_variants else car_name
            rendered.append(ModVariant(preset_id=preset_id, display_name=display_name))
        cars.append(ModCar(display_name=car_name, variants=tuple(rendered), runtime_name=_runtime_name(root)))

    # Pistleri oluştur
    tracks: list[ModTrack] = []
    for t_name, layouts_set in sorted(tracks_map.items()):
        if not layouts_set:
            layouts_set.add("Default")
            layouts_set.add("GP")
        layouts = tuple(sorted(layouts_set))
        disp = t_name.replace("_", " ").title()
        tracks.append(ModTrack(name=t_name, display_name=disp, layouts=layouts))

    return ModPackage(filename=path.name, size=path.stat().st_size, cars=tuple(cars), tracks=tuple(tracks))


def inspect_package_cached(path: Path) -> ModPackage:
    stat = path.stat()
    key = (str(path.resolve()), stat.st_size, stat.st_mtime_ns)
    with _cache_lock:
        cached = _package_cache.get(key)
    if cached is not None:
        return cached
    package = inspect_package(path)
    with _cache_lock:
        _package_cache[key] = package
    return package


def scan_kspkg_mods(mods_dir: Path) -> list[dict]:
    """mods_dir içindeki tüm .kspkg dosyalarını tarar, arabalar ve pistleri döndürür."""
    if not mods_dir.is_dir():
        return []
    result = []
    for f in sorted(mods_dir.glob("*.kspkg")):
        try:
            pkg = inspect_package_cached(f)
            result.append({
                "filename": f.name,
                "path": str(f),
                "size": pkg.size,
                "cars": [
                    {
                        "display_name": c.display_name,
                        "runtime_name": c.runtime_name,
                        "variants": [{"preset_id": v.preset_id, "display_name": v.display_name} for v in c.variants]
                    }
                    for c in pkg.cars
                ],
                "tracks": [
                    {
                        "name": t.name,
                        "display_name": t.display_name,
                        "layouts": list(t.layouts)
                    }
                    for t in pkg.tracks
                ]
            })
        except Exception:
            continue
    return result
