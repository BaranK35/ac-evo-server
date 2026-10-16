"""Hata teşhisi (diagnose) modülü birim testleri."""
from __future__ import annotations

import unittest
from evo_core.diagnose import diagnose


class TestDiagnose(unittest.TestCase):
    def test_missing_asset_file_from_real_crash(self):
        lines = [
            '[2026-10-13 17:35:50.995] [network] [info] Backend URL: strategy always_dev, config release',
            '[2026-10-13 17:35:50.996] [others] [error] Exception thrown: Failed to find file: "content\\cars\\common_assets\\parts\\tyres\\tyre_compound_textures.table"',
            'CRASH DETECTED',
        ]
        results = diagnose(lines)
        titles = [r["title"] for r in results]
        self.assertIn("Eksik Sunucu / Mod Dosyası", titles)
        missing_rule = next(r for r in results if r["title"] == "Eksik Sunucu / Mod Dosyası")
        self.assertEqual(missing_rule["level"], "error")
        self.assertIn("content\\cars\\common_assets", missing_rule["detail"])
        self.assertEqual(missing_rule["action"], "mods")

    def test_empty_path(self):
        lines = ["[error] Exception thrown: Trying to load a message with an empty path"]
        results = diagnose(lines)
        self.assertTrue(any("pisti/içeriği bulamadı" in r["title"] for r in results))

    def test_port_in_use(self):
        lines = ["[error] bind failed: WSAEADDRINUSE (address already in use)"]
        results = diagnose(lines)
        self.assertTrue(any("Port başka bir uygulama" in r["title"] for r in results))

    def test_port_access_denied(self):
        lines = ["[error] socket creation failed: WSAEACCES"]
        results = diagnose(lines)
        self.assertTrue(any("Port Erişim Yetkisi" in r["title"] for r in results))

    def test_udp_unreachable(self):
        lines = ["[network] Server can't be reached by UDP messages from Kunos lobby"]
        results = diagnose(lines)
        self.assertTrue(any("UDP Portuna Dışarıdan Erişilemedi" in r["title"] for r in results))

    def test_json_parse_error(self):
        lines = ["[error] Failed to parse JSON configuration file: syntax error"]
        results = diagnose(lines)
        self.assertTrue(any("Ayar Dosyası Ayrıştırma Hatası" in r["title"] for r in results))

    def test_steam_warning_and_order(self):
        lines = [
            "[warning] SteamAPI init warning: steam client not running",
            "CRASH DETECTED",
            "[info] can't be loaded into SeasonDefinition (practice.seasondefinition)",
        ]
        results = diagnose(lines)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["level"], "error")
        self.assertEqual(results[1]["level"], "warn")
        self.assertEqual(results[2]["level"], "info")


if __name__ == "__main__":
    unittest.main()
