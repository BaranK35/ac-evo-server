"""SimLab Senaryo & Hazır Şablon Yöneticisi (Preset & Scenario Engine).

Topluluk yöneticilerinin tek tıkla farklı yarış disiplinlerine (GT3 Sprint,
Endurance Rain, Midnight Drift / Freeroam, Time Attack) geçiş yapmasını sağlar.
Ayrıca yöneticilerin kendi özel şablonlarını kaydetmesine ve yönetmesine olanak tanır.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .paths import data_root

BUILTIN_PRESETS: list[dict[str, Any]] = [
    {
        "id": "gt3_sprint",
        "name": "GT3 Championship Sprint",
        "category": "Motorsport",
        "badge": "🏁 GT3",
        "icon": "trophy",
        "description": "20 dakikalık kıran kırana GT3 sprint yarışı. Optimum zemin tutuşu, katı şikan cezaları ve netcode akıcılığı.",
        "config_patch": {
            "game_type": "GameModeType_RACE_WEEKEND",
            "track": "Imola",
            "layout": "GP",
            "weather": "GameModeSelectionWeatherType_CLEAR",
            "weather_behavior": "GameModeSelectionWeatherBehaviour_STATIC",
            "initial_grip": "InitialGrip_OPTIMUM",
            "penalties": True,
            "wrong_way_penalty": True,
            "pit_limiter": True,
            "car_cut_tyres_out": 3,
            "time_penalty_ms": 5000,
            "race_length": 1200,
            "race_duration_type": "GameModeSelectionDuration_TIME",
            "practice_length": 300,
            "qualify_length": 600,
            "mandatory_pitstop": False,
        }
    },
    {
        "id": "endurance_wet",
        "name": "2.4h Spa-Francorchamps Endurance",
        "category": "Endurance",
        "badge": "🌧️ Dayanıklılık",
        "icon": "cloud-rain",
        "description": "Zorlu yağmur koşulları, değişken hava davranışı ve zorunlu lastik/yakıt stratejisi gerektiren dayanıklılık yarışı.",
        "config_patch": {
            "game_type": "GameModeType_RACE_WEEKEND",
            "track": "Spa",
            "layout": "GP",
            "weather": "GameModeSelectionWeatherType_RAIN",
            "weather_behavior": "GameModeSelectionWeatherBehaviour_DYNAMIC",
            "initial_grip": "InitialGrip_GREEN",
            "penalties": True,
            "wrong_way_penalty": True,
            "pit_limiter": True,
            "race_length": 3600,
            "race_time_multiplier": 5,
            "mandatory_pitstop": True,
            "mandatory_pitstop_refuel": True,
            "mandatory_pitstop_tyre_change": True,
            "pit_window_time": 900,
            "practice_length": 600,
            "qualify_length": 900,
        }
    },
    {
        "id": "midnight_drift",
        "name": "Midnight Freeroam & Drift (Ters Şerit Serbest)",
        "category": "Freeroam & Drift",
        "badge": "🌙 Drift / Serbest",
        "icon": "zap",
        "description": "Ters şerit ve serbest yön sürüşünün açık olduğu gece drift / serbest dolaşım senaryosu. Ceza sayacı devredışı.",
        "config_patch": {
            "game_type": "GameModeType_PRACTICE",
            "track": "BrandsHatch",
            "layout": "Indy",
            "weather": "GameModeSelectionWeatherType_CLEAR",
            "weather_behavior": "GameModeSelectionWeatherBehaviour_STATIC",
            "initial_grip": "InitialGrip_FAST",
            "penalties": False,
            "wrong_way_penalty": False,
            "car_cut_tyres_out": 4,
            "time_penalty_ms": 0,
            "practice_length": 7200,
            "practice_hour": 23,
            "practice_minute": 0,
            "practice_time_multiplier": 1,
            "mandatory_pitstop": False,
        }
    },
    {
        "id": "time_attack_hotlap",
        "name": "Time Attack & Hotlap Eleme",
        "category": "Hotlap",
        "badge": "⚡ Hotlap",
        "icon": "clock",
        "description": "En hızlı tur zamanını kaydetmeye yönelik sıcak asfalt seansı. Hızlı araç ayarları ve sıfır gecikme.",
        "config_patch": {
            "game_type": "GameModeType_PRACTICE",
            "track": "Monza",
            "layout": "GP",
            "weather": "GameModeSelectionWeatherType_CLEAR",
            "weather_behavior": "GameModeSelectionWeatherBehaviour_STATIC",
            "initial_grip": "InitialGrip_OPTIMUM",
            "penalties": True,
            "wrong_way_penalty": True,
            "practice_length": 900,
            "practice_hour": 14,
            "practice_minute": 0,
            "mandatory_pitstop": False,
        }
    }
]


def _custom_presets_file() -> Path:
    return data_root() / "presets.json"


def list_presets() -> list[dict[str, Any]]:
    """Tüm yerleşik ve kullanıcı tarafından kaydedilmiş senaryo şablonlarını listeler."""
    presets = [dict(p) for p in BUILTIN_PRESETS]
    f = _custom_presets_file()
    if f.is_file():
        try:
            custom = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(custom, list):
                presets.extend(custom)
        except Exception:
            pass
    return presets


def apply_preset(server_data: dict[str, Any], preset_id: str) -> tuple[dict[str, Any], str]:
    """Seçilen senaryo şablonunu sunucu verisine enjekte eder ve güncellenmiş sözlüğü döner."""
    all_p = list_presets()
    target = next((p for p in all_p if p["id"] == preset_id), None)
    if not target:
        raise ValueError(f"Senaryo şablonu bulunamadı: {preset_id}")

    patch = target.get("config_patch", {})
    updated = dict(server_data)
    for k, v in patch.items():
        updated[k] = v

    return updated, target["name"]


def save_custom_preset(name: str, description: str, server_data: dict[str, Any]) -> dict[str, Any]:
    """Mevcut sunucu yapılandırmasını yeni bir özel şablon olarak kaydeder."""
    import uuid
    pid = "custom_" + uuid.uuid4().hex[:6]
    
    # Sunucu verisinden kritik konfigürasyon anahtarlarını çek
    keys = [
        "game_type", "track", "layout", "weather", "weather_behavior", "initial_grip",
        "penalties", "wrong_way_penalty", "pit_limiter", "car_cut_tyres_out", "time_penalty_ms",
        "race_length", "race_duration_type", "race_time_multiplier", "practice_length",
        "practice_hour", "practice_minute", "practice_time_multiplier", "qualify_length",
        "mandatory_pitstop", "mandatory_pitstop_refuel", "mandatory_pitstop_tyre_change", "pit_window_time"
    ]
    patch = {k: server_data[k] for k in keys if k in server_data}

    new_preset = {
        "id": pid,
        "name": name.strip() or "Özel Senaryo",
        "category": "Özel Topluluk Şablonu",
        "badge": "⭐ Özel",
        "icon": "star",
        "description": description.strip() or "Kullanıcı tarafından kaydedilen özel sunucu yapılandırması.",
        "config_patch": patch,
        "custom": True,
    }

    f = _custom_presets_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    custom_list = []
    if f.is_file():
        try:
            custom_list = json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(custom_list, list):
                custom_list = []
        except Exception:
            custom_list = []

    custom_list.append(new_preset)
    f.write_text(json.dumps(custom_list, ensure_ascii=False, indent=2), encoding="utf-8")
    return new_preset


def delete_custom_preset(preset_id: str) -> bool:
    """Kullanıcının oluşturduğu özel şablonu siler (yerleşik şablonlar silinemez)."""
    f = _custom_presets_file()
    if not f.is_file():
        return False

    try:
        custom_list = json.loads(f.read_text(encoding="utf-8"))
        filtered = [p for p in custom_list if p.get("id") != preset_id]
        if len(filtered) == len(custom_list):
            return False
        f.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False
