"""SimLab Senaryo & Hazır Şablon Yöneticisi birim testleri."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from evo_core.presets import (
    apply_preset,
    delete_custom_preset,
    list_presets,
    save_custom_preset,
)


class TestPresets(unittest.TestCase):
    def test_list_builtin_presets(self):
        presets = list_presets()
        self.assertGreaterEqual(len(presets), 4)
        ids = [p["id"] for p in presets]
        self.assertIn("gt3_sprint", ids)
        self.assertIn("endurance_wet", ids)
        self.assertIn("midnight_drift", ids)
        self.assertIn("time_attack_hotlap", ids)

    def test_apply_preset_gt3_sprint(self):
        server = {
            "name": "Evo Test",
            "track": "Monza",
            "penalties": False,
        }
        updated, name = apply_preset(server, "gt3_sprint")
        self.assertEqual(name, "GT3 Championship Sprint")
        self.assertEqual(updated["track"], "Imola")
        self.assertTrue(updated["penalties"])
        self.assertTrue(updated["wrong_way_penalty"])
        self.assertEqual(updated["game_type"], "GameModeType_RACE_WEEKEND")

    def test_apply_preset_midnight_drift(self):
        server = {
            "name": "Drift Zone",
            "penalties": True,
            "wrong_way_penalty": True,
        }
        updated, name = apply_preset(server, "midnight_drift")
        self.assertFalse(updated["wrong_way_penalty"])
        self.assertFalse(updated["penalties"])
        self.assertEqual(updated["car_cut_tyres_out"], 4)

    def test_custom_preset_lifecycle(self):
        server = {
            "track": "CustomRing",
            "layout": "South",
            "penalties": True,
            "wrong_way_penalty": True,
        }
        saved = save_custom_preset("Benim Ligim", "Lig şablonu", server)
        self.assertIn("custom_", saved["id"])

        all_p = list_presets()
        self.assertTrue(any(p["id"] == saved["id"] for p in all_p))

        # Silme işlemi
        deleted = delete_custom_preset(saved["id"])
        self.assertTrue(deleted)

        all_p_after = list_presets()
        self.assertFalse(any(p["id"] == saved["id"] for p in all_p_after))


if __name__ == "__main__":
    unittest.main()
