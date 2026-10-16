"""Kodlama (encoding) modülü birim testleri."""
from __future__ import annotations

import unittest
from evo_core.encoding import (
    encode_evo_payload,
    decode_evo_payload,
    build_serverconfig,
    build_seasondefinition,
)


class TestEncoding(unittest.TestCase):
    def test_roundtrip_ascii_and_unicode(self):
        data = {
            "name": "Apex Türkçe Server ÇÖĞÜŞİ",
            "port": 9700,
            "sub": {"flag": True, "list": [1, 2, "üç"]},
        }
        encoded = encode_evo_payload(data)
        self.assertIsInstance(encoded, str)
        decoded = decode_evo_payload(encoded)
        self.assertEqual(data, decoded)

    def test_decode_invalid_inputs(self):
        with self.assertRaises(ValueError):
            decode_evo_payload("")
        with self.assertRaises(ValueError):
            decode_evo_payload("   ")
        with self.assertRaises(ValueError):
            decode_evo_payload("!!!invalid_base64!!!")
        with self.assertRaises(ValueError):
            decode_evo_payload("AA==")  # < 4 bytes
        # 4 bytes length header but corrupt zlib body
        import base64, struct
        fake = base64.b64encode(struct.pack(">I", 100) + b"corrupt").decode("ascii")
        with self.assertRaises(ValueError):
            decode_evo_payload(fake)

    def test_build_serverconfig_defaults_and_merge(self):
        server = {
            "tcp_port": 9700,
            "udp_port": 9700,
            "http_port": 8080,
            "name": "Test Server",
            "max_players": 12,
            "serverconfig_extra": {
                "max_players": 16,
                "custom_field": "custom_val",
            },
        }
        sc = build_serverconfig(server)
        self.assertEqual(sc["server_tcp_listener_port"], 9700)
        self.assertEqual(sc["server_udp_listener_port"], 9700)
        self.assertEqual(sc["server_http_port"], 8080)
        self.assertEqual(sc["max_players"], 16)
        self.assertEqual(sc["custom_field"], "custom_val")

    def test_build_seasondefinition_practice(self):
        server = {
            "game_type": "GameModeType_PRACTICE",
            "track": "Imola",
            "layout": "GP",
            "practice_length": 600,
            "penalties": True,
            "car_damage": True,
            "wrong_way_penalty": True,
        }
        sd = build_seasondefinition(server)
        self.assertEqual(sd["game_type"], "GameModeType_PRACTICE")
        self.assertEqual(sd["event"]["track"], "Imola")
        self.assertEqual(sd["event"]["layout"], "GP")
        self.assertEqual(sd["game_config"]["practice_duration"], 600)
        self.assertTrue(sd["game_config"]["enable_custom_penalities"])
        # Protobuf root filtering verification
        self.assertNotIn("wrong_way_penalty", sd)
        self.assertNotIn("car_damage", sd)

    def test_build_seasondefinition_race_weekend_pitstop(self):
        server = {
            "game_type": "GameModeType_RACE_WEEKEND",
            "race_length": 1500,  # > 1200 allows pitstop
            "race_duration_type": "GameModeSelectionDuration_TIME",
            "mandatory_pitstop": True,
            "mandatory_pitstop_refuel": True,
            "mandatory_pitstop_tyre_change": True,
            "pit_window_time": 600,
        }
        sd = build_seasondefinition(server)
        gc = sd["game_config"]
        self.assertTrue(gc.get("mandatory_pit_stop"))
        self.assertTrue(gc.get("requires_refuelling"))
        self.assertTrue(gc.get("requires_tyre_change"))
        self.assertEqual(gc.get("pit_window"), 600)

    def test_build_seasondefinition_wrong_way_and_penalties_disabled(self):
        server = {
            "game_type": "GameModeType_PRACTICE",
            "track": "BrandsHatch",
            "layout": "Indy",
            "penalties": False,
            "wrong_way_penalty": False,
        }
        sd = build_seasondefinition(server)
        gc = sd["game_config"]
        # Custom penalties must be True so server reads the disabled countdown
        self.assertTrue(gc.get("enable_custom_penalities"))
        self.assertEqual(gc.get("warning_trigger_countdown"), 2000000)
        self.assertEqual(gc.get("car_cut_tyres_out"), 10)
        self.assertEqual(gc.get("time_penalty_ms"), 0)


if __name__ == "__main__":
    unittest.main()
