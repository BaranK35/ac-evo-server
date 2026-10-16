"""Sunucu Paylaşım Kartı ve Topluluk Katılım Linki Üreteci.

Discord Rich-Markdown formatında sunucu tanıtımı, Steam doğrudan bağlantı
protokolü (steam://connect/...) ve paylaşım verileri oluşturur.
"""
from __future__ import annotations

from typing import Any


def generate_share_card(server_data: dict[str, Any], host_ip: str) -> dict[str, Any]:
    name = server_data.get("name", "Assetto Corsa EVO Server")
    track = server_data.get("track", "Bilinmeyen Pist")
    layout = server_data.get("layout", "GP")
    port = server_data.get("tcp_port", 9700)
    udp_port = server_data.get("udp_port", port)
    max_players = server_data.get("max_players", 16)
    cars = server_data.get("cars", [])
    car_count = len(cars) if isinstance(cars, list) else 1
    weather = server_data.get("weather", "Açık").replace("GameModeSelectionWeatherType_", "").capitalize()
    pwd = server_data.get("driver_password", "").strip()
    pwd_text = pwd if pwd else "Şifresiz (Herkese Açık)"

    ip = host_ip.strip() if host_ip and host_ip != "0.0.0.0" else "127.0.0.1"
    steam_url = f"steam://connect/{ip}:{udp_port}"
    direct_address = f"{ip}:{port}"

    discord_md = (
        f"🏁 **{name}** | Assetto Corsa EVO Sunucusu\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 **Pist:** {track} ({layout})\n"
        f"🏎️ **Araçlar:** {car_count} Model Seçeneği (Azami {max_players} Pilot)\n"
        f"⛅ **Hava Durumu:** {weather}\n"
        f"🌐 **Doğrudan Katıl:** <{steam_url}>\n"
        f"📡 **Sunucu Adresi (IP:Port):** `{direct_address}`\n"
        f"🔑 **Giriş Şifresi:** `{pwd_text}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*Apex Server Manager 3.0 ile yayınlandı.*"
    )

    # Basit ve estetik SVG Bağlantı Rozeti / Kartı
    svg_badge = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 460 140" width="100%" height="140">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#ff4a36"/>
      <stop offset="100%" stop-color="#ff8a1f"/>
    </linearGradient>
  </defs>
  <rect width="460" height="140" rx="16" fill="#121620" stroke="rgba(255,255,255,0.1)"/>
  <rect x="0" y="0" width="10" height="140" rx="4" fill="url(#g)"/>
  <text x="26" y="34" font-family="'Segoe UI', sans-serif" font-size="16" font-weight="bold" fill="#ffffff">{name[:38]}</text>
  <text x="26" y="60" font-family="'Segoe UI', sans-serif" font-size="13" fill="#8b94a8">Pist: <tspan fill="#eef1f7">{track} ({layout})</tspan> | Kapasite: <tspan fill="#35d07f">{max_players} Pilot</tspan></text>
  <text x="26" y="84" font-family="'Segoe UI', sans-serif" font-size="13" fill="#8b94a8">Adres: <tspan fill="#4cc9f0" font-family="monospace">{direct_address}</tspan></text>
  <text x="26" y="112" font-family="'Segoe UI', sans-serif" font-size="12" fill="#5d667a">Katılım Protokolü: {steam_url}</text>
</svg>"""

    return {
        "server_name": name,
        "track": f"{track} ({layout})",
        "ip": ip,
        "tcp_port": port,
        "udp_port": udp_port,
        "direct_address": direct_address,
        "steam_url": steam_url,
        "password": pwd_text,
        "discord_markdown": discord_md,
        "svg_card": svg_badge,
    }
