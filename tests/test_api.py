"""API katmanı (api.py) birim testleri."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

# Test ortamı için izole dizin ayarı
tmp_env = Path(tempfile.mkdtemp())
os.environ["EVO_MANAGER_HOME"] = str(tmp_env / "home")

from api import Api, Job, safe
from evo_core.servers import SERVER_EXE, ServerError


class TestApi(unittest.TestCase):
    def setUp(self):
        self.api = Api()

    def test_safe_decorator(self):
        class Dummy:
            @safe
            def success(self):
                return "ok_result"

            @safe
            def server_error(self):
                err = ServerError("Sunucu hatası")
                err.code = "err_code"
                raise err

            @safe
            def unhandled(self):
                raise RuntimeError("beklenmeyen durum")

        d = Dummy()
        res_ok = d.success()
        self.assertTrue(res_ok["ok"])
        self.assertEqual(res_ok["data"], "ok_result")

        res_serr = d.server_error()
        self.assertFalse(res_serr["ok"])
        self.assertEqual(res_serr["error"], "Sunucu hatası")
        self.assertEqual(res_serr["code"], "err_code")

        res_unh = d.unhandled()
        self.assertFalse(res_unh["ok"])
        self.assertIn("Beklenmeyen hata: beklenmeyen durum", res_unh["error"])

    def test_job_lifecycle(self):
        job = Job("Test Job")
        self.assertEqual(job.title, "Test Job")
        self.assertEqual(job.cur, 0)
        self.assertFalse(job.done)

        job.progress(25, 100, "İlerliyor...")
        self.assertEqual(job.percent, 25.0)
        self.assertEqual(job.msg, "İlerliyor...")

        job.pct(50.0, "Yarısı tamamlandı")
        self.assertEqual(job.percent, 50.0)

        for i in range(100):
            job.log(f"Log {i}")
        self.assertEqual(len(job.logs), 80)
        self.assertEqual(job.logs[-1], "Log 99")

        v = job.view()
        self.assertEqual(v["id"], job.id)
        self.assertEqual(v["title"], "Test Job")
        self.assertEqual(v["percent"], 50.0)

    def test_boot(self):
        res = self.api.boot()
        self.assertTrue(res["ok"])
        data = res["data"]
        self.assertIn("version", data)
        self.assertIn("app", data)
        self.assertIn("ip", data)

    def test_admin_actions(self):
        res = self.api.admin_action("server_1", "kick", "42")
        self.assertTrue(res["ok"])
        self.assertEqual(res["data"]["command"], r"\kick 42")
        self.assertEqual(res["data"]["alt_command"], "/kick 42")
        self.assertIn("admin_command", res["data"])

        res_pit = self.api.admin_action("server_1", "to_pit", "7")
        self.assertEqual(res_pit["data"]["command"], r"\to_pit 7")
        self.assertEqual(res_pit["data"]["alt_command"], "/to_pit 7")

        res_ballast = self.api.admin_action("server_1", "ballast", "12", "30")
        self.assertEqual(res_ballast["data"]["command"], r"\ballast 12 30")

        res_pen = self.api.admin_action("server_1", "penalty", "5", "dt")
        self.assertEqual(res_pen["data"]["command"], r"\add_penalty 5 dt")

        res_time = self.api.admin_action("server_1", "penalty", "5", "10")
        self.assertEqual(res_time["data"]["command"], r"\add_time 5 10")

        # del_penalty requires <car_number> <penalty> (AC EVO requirement)
        res_del = self.api.admin_action("server_1", "del_penalty", "0")
        self.assertEqual(res_del["data"]["command"], r"\del_penalty 0 1")

        res_del_custom = self.api.admin_action("server_1", "del_penalty", "0", "2")
        self.assertEqual(res_del_custom["data"]["command"], r"\del_penalty 0 2")

        res_adm = self.api.toggle_player_admin("server_1", "5")
        self.assertTrue(res_adm["ok"])

    def test_open_paths_safety(self):
        # Var olmayan dizin False döner
        res_nonexistent = self.api.open_server_folder("nonexistent_sid")
        self.assertTrue(res_nonexistent["ok"])
        self.assertFalse(res_nonexistent["data"])

        # Geçerli klasör True döner
        res_folder = self.api.open_folder(str(tmp_env))
        self.assertTrue(res_folder["ok"])
        self.assertTrue(res_folder["data"])

        # Boş parametre varsayılan data_root'a açılır
        res_default = self.api.open_folder("")
        self.assertTrue(res_default["ok"])
        self.assertTrue(res_default["data"])

    def test_innovations_api(self):
        # 1. SimLab Presets
        res_presets = self.api.list_presets()
        self.assertTrue(res_presets["ok"])
        self.assertGreaterEqual(len(res_presets["data"]), 4)

        # 2. AI Race Director report
        res_steward = self.api.get_steward_report("server_1")
        self.assertTrue(res_steward["ok"])
        self.assertIn("fair_play_score", res_steward["data"])
        self.assertIn("recent_incidents", res_steward["data"])

        # 3. Share card (dummy server)
        server_dir = self.api._store.path("server_1")
        server_dir.mkdir(parents=True, exist_ok=True)
        (server_dir / "server.json").write_text('{"name": "Apex Test GP", "tcp_port": 9700}', encoding="utf-8")
        res_card = self.api.get_server_share_card("server_1")
        self.assertTrue(res_card["ok"])
        self.assertIn("steam://connect/", res_card["data"]["steam_url"])
        self.assertIn("discord_markdown", res_card["data"])
        self.assertIn("svg_card", res_card["data"])

    def test_admin_and_ban(self):
        sid = "server_1"
        server_dir = self.api._store.path(sid)
        server_dir.mkdir(parents=True, exist_ok=True)
        (server_dir / "server.json").write_text('{"name": "Test Server", "tcp_port": 9700}', encoding="utf-8")

        ms = self.api._runner.get(sid)
        ms.players["1"] = {"car_number": "1", "driver_name": "TestPilot", "steam_id": "76561198000000001", "ip": "192.168.1.15"}
        
        # Admin toggle
        adm_res = self.api.toggle_player_admin(sid, "1")
        self.assertTrue(adm_res["ok"])
        self.assertTrue(adm_res["data"]["is_admin"])
        
        # entry_list.json should exist and have admin driver
        entry_list_file = server_dir / "entry_list.json"
        self.assertTrue(entry_list_file.is_file())
        el_data = json.loads(entry_list_file.read_text(encoding="utf-8"))
        self.assertEqual(len(el_data["entries"]), 1)
        self.assertTrue(el_data["entries"][0]["isAdmin"])
        self.assertTrue(el_data["entries"][0]["isServerAdmin"])
        self.assertEqual(el_data["entries"][0]["drivers"][0]["steamId"], "76561198000000001")

        # Kick player
        ms.players["2"] = {"car_number": "2", "driver_name": "Racer2", "steam_id": "76561198000000002"}
        kick_res = self.api.kick_player(sid, "2", "76561198000000002")
        self.assertTrue(kick_res["ok"])
        self.assertNotIn("2", ms.players)
        
        # Ban player host
        ban_res = self.api.ban_player_host(sid, "1", "76561198000000001", "192.168.1.15")
        self.assertTrue(ban_res["ok"])
        self.assertEqual(ban_res["data"]["kick_command"], "\\kick 1")
        self.assertEqual(ban_res["data"]["steam_id"], "76561198000000001")
        self.assertNotIn("1", ms.players)
        
        # Blacklist should now contain the steam_id
        bl = self.api.get_blacklist(sid)
        self.assertTrue(bl["ok"])
        self.assertIn("76561198000000001", bl["data"])

        # entry_list.json should have removed the banned player
        el_data_banned = json.loads(entry_list_file.read_text(encoding="utf-8"))
        banned_entries = [e for e in el_data_banned["entries"] if e["drivers"][0]["steamId"] == "76561198000000001"]
        self.assertEqual(len(banned_entries), 0)


if __name__ == "__main__":
    unittest.main()

