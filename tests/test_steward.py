"""AI Race Director & Telemetry Sentinel birim testleri."""
from __future__ import annotations

import unittest
from evo_core.steward import StewardSentinel


class TestSteward(unittest.TestCase):
    def setUp(self):
        self.steward = StewardSentinel("server_test")
        self.players = {
            "12": {
                "car_number": "12",
                "car_id": "12",
                "driver_name": "Max Verstappen",
                "name": "Max Verstappen",
            },
            "44": {
                "car_number": "44",
                "car_id": "44",
                "driver_name": "Lewis Hamilton",
                "name": "Lewis Hamilton",
            }
        }

    def test_track_limits_progressive_penalties(self):
        # 1. ihlal - uyarı
        inc1 = self.steward.analyze_line("Car 12 cut track at sector 2", self.players)
        self.assertIsNotNone(inc1)
        self.assertEqual(inc1.severity, "low")
        self.assertEqual(inc1.recommended_action, "warning")

        # 2. ihlal - uyarı
        inc2 = self.steward.analyze_line("Track limits exceeded by car 12", self.players)
        self.assertEqual(inc2.severity, "low")

        # 3. ihlal - +5s süre cezası tavsiyesi
        inc3 = self.steward.analyze_line("Car 12 tyres out of bounds", self.players)
        self.assertEqual(inc3.severity, "medium")
        self.assertEqual(inc3.recommended_action, "add_time")
        self.assertEqual(inc3.recommended_param, "5")

        # 4. ihlal - Drive-Through cezası tavsiyesi
        inc4 = self.steward.analyze_line("Car 12 cut track again", self.players)
        self.assertEqual(inc4.severity, "high")
        self.assertEqual(inc4.recommended_action, "add_penalty")
        self.assertEqual(inc4.recommended_param, "dt")

    def test_wrong_way_critical_incident(self):
        inc = self.steward.analyze_line("Warning wrong way car 12 on main straight", self.players)
        self.assertIsNotNone(inc)
        self.assertEqual(inc.severity, "critical")
        self.assertEqual(inc.recommended_action, "to_pit")
        self.assertEqual(inc.incident_type, "wrong_way")

    def test_collision_detection(self):
        inc = self.steward.analyze_line("Collision between Car 12 and Car 44 at Turn 1", self.players)
        self.assertIsNotNone(inc)
        self.assertEqual(inc.severity, "medium")
        self.assertEqual(inc.incident_type, "collision")
        self.assertIn("Max Verstappen", inc.description)
        self.assertIn("Lewis Hamilton", inc.description)

    def test_steward_report_and_mark_applied(self):
        inc = self.steward.analyze_line("Car 12 speed limit exceeded in pitlane: 85 km/h", self.players)
        self.assertIsNotNone(inc)
        rep = self.steward.get_report()
        self.assertLess(rep["fair_play_score"], 100)
        self.assertEqual(len(rep["recent_incidents"]), 1)

        ok = self.steward.mark_applied(inc.id)
        self.assertTrue(ok)
        rep2 = self.steward.get_report()
        self.assertTrue(rep2["recent_incidents"][0]["applied"])


if __name__ == "__main__":
    unittest.main()
