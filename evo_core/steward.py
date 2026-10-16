"""AI Race Director & Telemetry Sentinel Motoru.

Assetto Corsa EVO Dedicated Server log akışını ve yarış içi telemetri olaylarını
anlık olarak analiz eder; pist dışına çıkışları, çarpışmaları, ters yön ihlallerini
kümeleyerek hakemlik kararları ve otomatik ceza tavsiyeleri üretir.
"""
from __future__ import annotations

import re
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Literal

SeverityLevel = Literal["info", "low", "medium", "high", "critical"]


@dataclass
class StewardIncident:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: str = field(default_factory=lambda: time.strftime("%H:%M:%S"))
    car_number: str = ""
    driver_name: str = ""
    incident_type: str = "track_limits"  # track_limits, collision, wrong_way, pit_speed, unsportsmanlike
    severity: SeverityLevel = "low"
    description: str = ""
    lap: int = 1
    recommended_action: str = ""  # add_time, add_penalty, to_pit, warning, kick
    recommended_param: str = ""   # e.g. "5", "dt", "sg"
    action_label: str = ""
    applied: bool = False


class StewardSentinel:
    """Tek bir sunucu örneği için hakemlik ve telemetri analiz motoru."""

    def __init__(self, sid: str, max_incidents: int = 200, wrong_way_enabled: bool = True):
        self.sid = sid
        self.lock = threading.Lock()
        self.incidents: deque[StewardIncident] = deque(maxlen=max_incidents)
        self.driver_cuts: dict[str, int] = {}       # car_number -> count
        self.driver_contacts: dict[str, int] = {}   # car_number -> count
        self.driver_laps: dict[str, int] = {}       # car_number -> lap count
        self.mode: Literal["advisory", "autonomous"] = "advisory"
        self.wrong_way_enabled = wrong_way_enabled
        self.total_analyzed = 0

    def analyze_line(self, line: str, players: dict[str, dict] | None = None) -> StewardIncident | None:
        """Sunucu log satırını analiz eder ve kural ihlali varsa StewardIncident döner."""
        with self.lock:
            self.total_analyzed += 1
            players = players or {}
            incident: StewardIncident | None = None

            # 1. Pist Sınırları & Şikan Kesme (Track Limits / Cut Track)
            cut_triggers = r"cut track|cutting detected|track limits|tyres out|exceeded track"
            m_cut_1 = re.search(rf"(?:car\s*(?:n\.)?|competitor\s*)?(\d+).*?(?:{cut_triggers})", line, re.I)
            m_cut_2 = re.search(rf"(?:{cut_triggers}).*?(?:car\s*(?:n\.)?|competitor\s*)?(\d+)", line, re.I)
            cnum_cut = (m_cut_1.group(1) if m_cut_1 and m_cut_1.group(1) else (m_cut_2.group(1) if m_cut_2 and m_cut_2.group(1) else None))

            if cnum_cut:
                cnum = str(cnum_cut).strip()
                driver = self._resolve_driver(cnum, players)
                cuts = self.driver_cuts.get(cnum, 0) + 1
                self.driver_cuts[cnum] = cuts

                if cuts >= 4:
                    severity: SeverityLevel = "high"
                    action = "add_penalty"
                    param = "dt"
                    lbl = f"Araç #{cnum} ({driver}) 4. kez pist sınırını aştı -> Drive-Through Cezası Önerilir"
                    act_label = "Drive-Through Ver"
                elif cuts >= 3:
                    severity = "medium"
                    action = "add_time"
                    param = "5"
                    lbl = f"Araç #{cnum} ({driver}) 3. kez şikan kesti -> +5s Zaman Cezası Önerilir"
                    act_label = "+5s Süre Cezası"
                else:
                    severity = "low"
                    action = "warning"
                    param = ""
                    lbl = f"Araç #{cnum} ({driver}) pist dışına taştı ({cuts}. ihlal)"
                    act_label = "İhlali Kaydet"

                incident = StewardIncident(
                    car_number=cnum,
                    driver_name=driver,
                    incident_type="track_limits",
                    severity=severity,
                    description=lbl,
                    recommended_action=action,
                    recommended_param=param,
                    action_label=act_label,
                )

            # 2. Ters Yön Sürüşü (Wrong Direction / Wrong Way)
            if self.wrong_way_enabled:
                ww_triggers = r"wrong\s*way|wrong\s*direction|driving opposite"
                m_ww_1 = re.search(rf"(?:car\s*(?:n\.)?|competitor\s*)?(\d+).*?(?:{ww_triggers})", line, re.I)
                m_ww_2 = re.search(rf"(?:{ww_triggers}).*?(?:car\s*(?:n\.)?|competitor\s*)?(\d+)", line, re.I)
                cnum_ww = (m_ww_1.group(1) if m_ww_1 and m_ww_1.group(1) else (m_ww_2.group(1) if m_ww_2 and m_ww_2.group(1) else None))
                if cnum_ww:
                    cnum = str(cnum_ww).strip()
                    driver = self._resolve_driver(cnum, players)
                    incident = StewardIncident(
                        car_number=cnum,
                        driver_name=driver,
                        incident_type="wrong_way",
                        severity="critical",
                        description=f"Araç #{cnum} ({driver}) ters yönde seyrediyor! Pist güvenliği tehdit altında.",
                        recommended_action="to_pit",
                        recommended_param="",
                        action_label="Pite Gönder",
                    )

            # 3. Temas & Kaza (Collision / Severe Impact)
            m_col = re.search(r"Collision between Car (\d+) and Car (\d+)", line, re.I)
            if m_col:
                c1, c2 = str(m_col.group(1)).strip(), str(m_col.group(2)).strip()
                d1 = self._resolve_driver(c1, players)
                d2 = self._resolve_driver(c2, players)
                self.driver_contacts[c1] = self.driver_contacts.get(c1, 0) + 1
                self.driver_contacts[c2] = self.driver_contacts.get(c2, 0) + 1
                incident = StewardIncident(
                    car_number=f"{c1}&{c2}",
                    driver_name=f"{d1} & {d2}",
                    incident_type="collision",
                    severity="medium",
                    description=f"Temas tespit edildi: Araç #{c1} ({d1}) ile Araç #{c2} ({d2}) çarpıştı.",
                    recommended_action="review",
                    recommended_param="",
                    action_label="İncelemeye Al",
                )

            # 4. Pit Hız Sınırı İhlali (Pit Speed Limiter Violation)
            pit_triggers = r"pit.*?speed|pitlane speed|speed limit exceeded"
            m_pit_1 = re.search(rf"(?:car\s*(?:n\.)?|competitor\s*)?(\d+).*?(?:{pit_triggers})", line, re.I)
            m_pit_2 = re.search(rf"(?:{pit_triggers}).*?(?:car\s*(?:n\.)?|competitor\s*)?(\d+)", line, re.I)
            cnum_pit = (m_pit_1.group(1) if m_pit_1 and m_pit_1.group(1) else (m_pit_2.group(1) if m_pit_2 and m_pit_2.group(1) else None))
            if cnum_pit:
                cnum = str(cnum_pit).strip()
                driver = self._resolve_driver(cnum, players)
                incident = StewardIncident(
                    car_number=cnum,
                    driver_name=driver,
                    incident_type="pit_speed",
                    severity="high",
                    description=f"Araç #{cnum} ({driver}) pit yolunda hız limitini aştı.",
                    recommended_action="add_penalty",
                    recommended_param="dt",
                    action_label="Drive-Through Ver",
                )

            if incident:
                self.incidents.appendleft(incident)
                return incident

            return None

    def _resolve_driver(self, cnum: str, players: dict[str, dict]) -> str:
        for p in players.values():
            if str(p.get("car_number")) == cnum or str(p.get("car_id")) == cnum:
                return p.get("driver_name") or p.get("name") or f"Sürücü #{cnum}"
        return f"Sürücü #{cnum}"

    def get_report(self) -> dict:
        """Hakemlik paneline sunulacak kapsamlı durum ve olay raporunu döndürür."""
        with self.lock:
            incident_list = [asdict(inc) for inc in list(self.incidents)[:30]]
            high_count = sum(1 for inc in incident_list if inc["severity"] in ("high", "critical") and not inc["applied"])
            fair_play_score = max(0, 100 - (len(incident_list) * 4) - (high_count * 15))

            return {
                "sid": self.sid,
                "fair_play_score": fair_play_score,
                "total_incidents": len(self.incidents),
                "unresolved_critical": high_count,
                "mode": self.mode,
                "driver_cuts": dict(self.driver_cuts),
                "driver_contacts": dict(self.driver_contacts),
                "recent_incidents": incident_list,
            }

    def mark_applied(self, incident_id: str) -> bool:
        with self.lock:
            for inc in self.incidents:
                if inc.id == incident_id:
                    inc.applied = True
                    return True
            return False

    def clear(self) -> None:
        with self.lock:
            self.incidents.clear()
            self.driver_cuts.clear()
            self.driver_contacts.clear()
            self.driver_laps.clear()
