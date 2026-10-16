"""Sunucu yapılandırması (servers) modülü birim testleri."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from evo_core.servers import (
    SERVER_EXE,
    ServerError,
    ServerStore,
    server_number,
    validate_server_folder,
)


class TestServers(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.evo_dir = self.tmp_dir / "evo_source"
        self.evo_dir.mkdir()
        (self.evo_dir / SERVER_EXE).write_text("dummy binary")
        (self.evo_dir / "cars.json").write_text(json.dumps({"cars": [{"car_name": "car1"}]}))
        self.store = ServerStore(self.tmp_dir / "servers")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_validate_server_folder(self):
        ok, msg = validate_server_folder("")
        self.assertFalse(ok)
        ok, msg = validate_server_folder(self.tmp_dir / "nonexistent")
        self.assertFalse(ok)
        empty_dir = self.tmp_dir / "empty"
        empty_dir.mkdir()
        ok, msg = validate_server_folder(empty_dir)
        self.assertFalse(ok)
        ok, msg = validate_server_folder(self.evo_dir)
        self.assertTrue(ok)

    def test_server_number(self):
        self.assertEqual(server_number("server_1"), 1)
        self.assertEqual(server_number("srv_42"), 42)
        self.assertEqual(server_number("custom_server"), 10**9)

    def test_store_crud_and_clone(self):
        sid = self.store.create(str(self.evo_dir))
        self.assertEqual(sid, "server_1")
        self.assertTrue(self.store.path(sid).is_dir())
        self.assertTrue((self.store.path(sid) / SERVER_EXE).is_file())

        cfg = self.store.load(sid)
        self.assertEqual(cfg["tcp_port"], 9700)
        cfg["name"] = "Modified Name"
        self.store.save(sid, cfg)
        self.assertEqual(self.store.load(sid)["name"], "Modified Name")

        clone_id = self.store.clone(sid)
        self.assertEqual(clone_id, "server_2")
        clone_cfg = self.store.load(clone_id)
        self.assertEqual(clone_cfg["tcp_port"], 9701)
        self.assertIn("Kopya", clone_cfg["name"])

        self.store.delete(sid)
        self.assertFalse(self.store.path(sid).exists())
        self.assertEqual(self.store.ids(), [clone_id])

    def test_build_command_and_quote_resilience(self):
        sid = self.store.create(str(self.evo_dir))
        cfg = self.store.load(sid)

        cmd = self.store.build_command(sid, cfg)
        self.assertTrue(cmd[0].endswith(SERVER_EXE))
        self.assertIn("-serverconfig", cmd)
        self.assertIn("-seasondefinition", cmd)
        self.assertIn("-log_file", cmd)

        # Unclosed quotation in custom command should not crash with shlex ValueError
        cfg["custom_command"] = 'AssettoCorsaEVOServer.exe "unclosed quotation'
        resilient_cmd = self.store.build_command(sid, cfg)
        self.assertTrue(len(resilient_cmd) >= 2)

        # Unclosed quotation in extra_arguments
        cfg["custom_command"] = ""
        cfg["extra_arguments"] = '-extra "unclosed argument'
        extra_cmd = self.store.build_command(sid, cfg)
        self.assertTrue(len(extra_cmd) >= 4)

    def test_preflight_validations(self):
        sid = self.store.create(str(self.evo_dir))
        cfg = self.store.load(sid)

        # Normal valid server
        self.assertEqual(self.store.preflight(sid, cfg), [])

        # Missing cars
        cfg_no_cars = dict(cfg, cars=[])
        self.assertTrue(any("araç seçilmemiş" in p for p in self.store.preflight(sid, cfg_no_cars)))

        # Invalid port
        cfg_bad_port = dict(cfg, tcp_port=70000)
        self.assertTrue(any("Port numaraları 1-65535" in p for p in self.store.preflight(sid, cfg_bad_port)))

        # Port collision: TCP == HTTP
        cfg_collision = dict(cfg, tcp_port=9700, http_port=9700)
        self.assertTrue(any("TCP Portu ile HTTP Portu aynı olamaz" in p for p in self.store.preflight(sid, cfg_collision)))

        # Empty track
        cfg_no_track = dict(cfg, track="")
        self.assertTrue(any("Pist seçilmemiş" in p for p in self.store.preflight(sid, cfg_no_track)))


if __name__ == "__main__":
    unittest.main()
