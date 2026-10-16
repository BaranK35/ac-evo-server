"""EVO'nun beklediği -serverconfig / -seasondefinition kodlaması."""
from __future__ import annotations

import base64
import json
import struct
import zlib


def encode_evo_payload(data) -> str:
    # AC EVO intermittently exits while reading some Huffman-coded
    # payloads. Stored DEFLATE blocks (level=0) keep the standard zlib envelope
    # while avoiding that data-dependent native decoder crash.
    raw = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    compressed = zlib.compress(raw, level=0)
    payload = struct.pack(">I", len(raw)) + compressed
    return base64.b64encode(payload).decode("ascii").rstrip("=")


def decode_evo_payload(text: str):
    """Test ve hata ayıklama için ters işlem."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Payload metni boş veya geçersiz.")
    text = text.strip()
    text += "=" * (-len(text) % 4)
    try:
        payload = base64.b64decode(text)
    except Exception as exc:
        raise ValueError(f"Geçersiz base64 verisi: {exc}") from exc
    if len(payload) < 4:
        raise ValueError("Payload verisi 4 bayttan kısa (başlık eksik).")
    (length,) = struct.unpack(">I", payload[:4])
    try:
        raw = zlib.decompress(payload[4:])
    except Exception as exc:
        raise ValueError(f"Sıkıştırılmış veri açılamadı (zlib hatası): {exc}") from exc
    if len(raw) != length:
        raise ValueError(f"Açılan veri boyutu ({len(raw)}) beklenen boyuttan ({length}) farklı.")
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Geçersiz JSON verisi: {exc}") from exc


def _merge(base: dict, extra) -> dict:
    """Ham 'ek ayarlar' JSON'unu üretilen yapıya (iç içe sözlükler dahil) ekler."""
    if not isinstance(extra, dict):
        return base
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def build_serverconfig(server: dict) -> dict:
    return _merge(_build_serverconfig(server), server.get("serverconfig_extra"))


def build_seasondefinition(server: dict) -> dict:
    return _merge(_build_seasondefinition(server), server.get("seasondefinition_extra"))


def _build_serverconfig(server: dict) -> dict:
    tcp_port = int(server.get("tcp_port", 9700))
    udp_port = int(server.get("udp_port", 9700))
    http_port = int(server.get("http_port", 8080))
    doc = {
        "server_tcp_listener_port": tcp_port,
        "server_udp_listener_port": udp_port,
        "server_tcp_internal_port": tcp_port,
        "server_udp_internal_port": udp_port,
        "server_http_port": http_port,
        "server_name": server.get("name", "EVO Server"),
        "netcode_update_interval": int(server.get("netcode_update_interval", 55)),
        "driver_password": server.get("driver_password", ""),
        "spectator_password": server.get("spectator_password", ""),
        "max_players": int(server.get("max_players", 8)),
        "allowed_cars_list_full": server.get("cars", []),
        "type": server.get("type", "MultiplayerServerListSessionType_BOTH"),
        "cycle": bool(server.get("cycle", True)),
        "admin_password": server.get("admin_password", ""),
        "pi_min": float(server.get("pi_min", 0) or 0),
        "pi_max": float(server.get("pi_max", 0) or 0),
        "tuning_type": server.get("tuning_type", "TuningAllowed"),
    }
    # launch_path, entry_list_path ve urls: Kunos boş dize ("") gördüğünde
    # "Trying to load a message with an empty path" hatası atarak çöker.
    # Bu nedenle yalnızca içi dolu olan opsiyonel yollar eklenir.
    for k in ("launch_path", "entry_list_server_url", "results_post_url", "token", "entry_list_path", "results_path"):
        val = str(server.get(k, "")).strip()
        if val:
            doc[k] = val
    return doc


def _time_of_day(server: dict, prefix: str) -> dict:
    return {
        "year": int(server.get("year", 2024)),
        "month": int(server.get("month", 8)),
        "day": int(server.get("day", 15)),
        "hour": int(server.get(f"{prefix}_hour", server.get("practice_hour", 16))),
        "minute": int(server.get(f"{prefix}_minute", server.get("practice_minute", 0))),
        "second": int(server.get("second", 0)),
        "time_multiplier": int(server.get(f"{prefix}_time_multiplier", server.get("time_multiplier", 1))),
    }


def _build_seasondefinition(server: dict) -> dict:
    game_type = server.get("game_type", "GameModeType_PRACTICE")

    # Tüm 4 seansı protobuf şemasına tam uygun tanımla
    game_config = {
        "practice_duration": int(server.get("practice_length", 300)),
        "practice_time_of_day": _time_of_day(server, "practice"),
        "practice_overtime_waiting_next_session": int(server.get("practice_overtime", server.get("overtime", 10))),
        "practice_max_wait_to_box": int(server.get("practice_max_wait_to_box", server.get("max_wait_to_box", 10))),

        "qualify_duration": 0,
        "qualify_time_of_day": _time_of_day(server, "practice"),
        "qualify_overtime_waiting_next_session": 0,
        "qualify_max_wait_to_box": 0,

        "warmup_duration": 0,
        "warmup_time_of_day": _time_of_day(server, "practice"),
        "warmup_overtime_waiting_next_session": 0,
        "warmup_max_wait_to_box": 0,

        "race_duration": 0,
        "race_time_of_day": _time_of_day(server, "practice"),
        "race_overtime_waiting_next_session": 0,
        "race_max_wait_to_box": 0,
        "race_duration_type": server.get("race_duration_type", "GameModeSelectionDuration_TIME"),
        "min_waiting_for_players": int(server.get("min_waiting_for_players", 10)),
        "max_waiting_for_players": int(server.get("max_waiting_for_players", 30)),
    }

    if game_type == "GameModeType_RACE_WEEKEND":
        game_config.update({
            "qualify_duration": int(server.get("qualify_length", 300)),
            "qualify_time_of_day": _time_of_day(server, "qualify"),
            "qualify_overtime_waiting_next_session": int(server.get("qualify_overtime", 10)),
            "qualify_max_wait_to_box": int(server.get("qualify_max_wait_to_box", 10)),

            "warmup_duration": int(server.get("warmup_length", 300)),
            "warmup_time_of_day": _time_of_day(server, "warmup"),
            "warmup_overtime_waiting_next_session": int(server.get("warmup_overtime", 10)),
            "warmup_max_wait_to_box": int(server.get("warmup_max_wait_to_box", 10)),

            "race_duration": int(server.get("race_length", 300)),
            "race_time_of_day": _time_of_day(server, "race"),
            "race_overtime_waiting_next_session": int(server.get("race_overtime", 10)),
            "race_max_wait_to_box": int(server.get("race_max_wait_to_box", 10)),
        })

        pitstop_allowed = (
            server.get("race_duration_type", "GameModeSelectionDuration_TIME") == "GameModeSelectionDuration_TIME"
            and int(server.get("race_length", 300)) > 1200
        )
        if server.get("mandatory_pitstop", False) and pitstop_allowed:
            game_config["mandatory_pit_stop"] = True
            game_config["requires_tyre_change"] = bool(server.get("mandatory_pitstop_tyre_change", False))
            game_config["requires_refuelling"] = bool(server.get("mandatory_pitstop_refuel", False))
            game_config["pit_window"] = int(server.get("pit_window_time", 600))

    # Cezalar ve Ters Yön (Wrong Way) kuralları
    penalties_enabled = bool(server.get("penalties", True))
    wrong_way_enabled = bool(server.get("wrong_way_penalty", True))
    pit_limiter_enabled = bool(server.get("pit_limiter", True))

    # Kunos AC EVO SimpleGameConfig kural motoru:
    # enable_custom_penalities True yapılarak sunucunun warning_trigger_countdown,
    # car_cut_tyres_out ve time_penalty_ms ayarlarını zorla kabul etmesi sağlanır.
    game_config["enable_custom_penalities"] = True

    if not penalties_enabled:
        game_config["car_cut_tyres_out"] = 10
        game_config["time_penalty_ms"] = 0
    else:
        game_config["car_cut_tyres_out"] = int(server.get("car_cut_tyres_out", 3))
        game_config["time_penalty_ms"] = int(server.get("time_penalty_ms", 5000))

    if not wrong_way_enabled:
        # Ters yönde sürüş cezası kapalı: geri sayımı 2.000.000 sn ve ceza süresini 0ms yap
        game_config["warning_trigger_countdown"] = 2000000
        game_config["time_penalty_ms"] = 0
    else:
        game_config["warning_trigger_countdown"] = int(server.get("warning_trigger_countdown", 10))

    if not pit_limiter_enabled:
        game_config["time_penalty_ms"] = 0

    # Serbest Dolaşım (Freeroam) Modu desteği
    is_freeroam = game_type == "GameModeType_FREEROAM" or "freeroam" in str(server.get("layout", "")).lower()
    if is_freeroam:
        game_config["freeroam_time_of_day"] = _time_of_day(server, "practice")
        game_config["freeroam_enable_traffic"] = bool(server.get("freeroam_enable_traffic", True))
        # freeroam_spawn_park protobuf şemasında TYPE_INT32'dir (1 veya 0, bool kabul etmez)
        game_config["freeroam_spawn_park"] = 1 if server.get("freeroam_spawn_park", True) else 0
        if not wrong_way_enabled:
            game_config["warning_trigger_countdown"] = 2000000
        if not penalties_enabled:
            game_config["car_cut_tyres_out"] = 10
            game_config["time_penalty_ms"] = 0

    return {
        "game_type": game_type,
        "event": {
            "track": server.get("track", "Imola"),
            "layout": server.get("layout", "GP"),
            "event_name": server.get("event_name", "GP Time Attack"),
            "track_length": str(server.get("track_length", "4909")),
        },
        "export_json": bool(server.get("export_json", False)),
        "game_config": game_config,
        "weather_type": server.get("weather", "GameModeSelectionWeatherType_CLEAR"),
        "weather_behaviour": server.get("weather_behavior", "GameModeSelectionWeatherBehaviour_STATIC"),
        "initial_grip": server.get("initial_grip", "InitialGrip_GREEN"),
    }

