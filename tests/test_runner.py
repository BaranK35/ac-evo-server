"""Süreç yöneticisi (runner) modülü birim testleri."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from evo_core.runner import ManagedServer, Runner
from evo_core.servers import ServerStore


class TestRunner(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.store = ServerStore(self.tmp_dir / "servers")
        self.runner = Runner(self.store, settings=lambda: {"auto_restart": False})

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_managed_server_buffer_and_since(self):
        ms = ManagedServer("server_1")
        self.assertEqual(ms.seq, 0)
        ms.add("out", "First line")
        ms.add("err", "Second line")
        self.assertEqual(ms.seq, 2)
        self.assertEqual(len(ms.lines), 2)

        newer, cur_seq = ms.since(1)
        self.assertEqual(cur_seq, 2)
        self.assertEqual(len(newer), 1)
        self.assertEqual(newer[0][3], "Second line")

        ms.clear()
        self.assertEqual(ms.seq, 0)
        self.assertEqual(len(ms.lines), 0)
        self.assertTrue(ms.cleared)

    def test_player_events_parsing(self):
        ms = ManagedServer("server_1")

        # 1. Connection
        ms.add("out", "[server] Connection with user Pilot_01 was successful")
        players = ms.get_players()
        self.assertEqual(len(players), 1)
        self.assertEqual(players[0]["id"], "Pilot_01")
        self.assertEqual(players[0]["state"], "Pistte")
        self.assertEqual(players[0]["penalties"], [])

        # 2. Penalty
        ms.add("out", "[server] Applied penalty DriveThrough to Pilot_01")
        players = ms.get_players()
        self.assertIn("DriveThrough", players[0]["penalties"])

        # 3. Pit
        ms.add("out", "[server] Pilot_01 has been forcefully sent to pits")
        players = ms.get_players()
        self.assertEqual(players[0]["state"], "Pitte")

        # 4. Disconnect
        ms.add("out", "[server] Destroying Car(Pilot_01)")
        players = ms.get_players()
        self.assertEqual(len(players), 0)

    def test_evo_authentic_player_events_parsing(self):
        ms = ManagedServer("server_evo")

        # 1. Join with real AC EVO pattern: Car [model] #car_num for driver Name [steam_id]
        ms.add("out", "[2026-10-14 13:00:01] [net] Car [preset_m4gt3_mech_1] #12 for driver Max Verstappen [76561198012345678]")
        players = ms.get_players()
        self.assertEqual(len(players), 1)
        p = players[0]
        self.assertEqual(p["car_number"], "12")
        self.assertEqual(p["driver_name"], "Max Verstappen")
        self.assertEqual(p["steam_id"], "76561198012345678")
        self.assertEqual(p["car_model"], "preset_m4gt3_mech_1")
        self.assertEqual(p["state"], "Pistte")

        # 2. Pit slot assignment / pit entry
        ms.add("out", "assigning pit slot 4 to competitor 2 car_number 12")
        players = ms.get_players()
        self.assertEqual(players[0]["state"], "Pitte")

        # 3. Penalty assignment
        ms.add("out", "Applied penalty DriveThrough to car 12")
        players = ms.get_players()
        self.assertIn("DriveThrough", players[0]["penalties"])

        # 4. Disconnect via competitor removal
        ms.add("out", "Removing registered competitor 2 car_number 12")
        players = ms.get_players()
        self.assertEqual(len(players), 0)

    def test_no_ghost_players_on_server_startup(self):
        ms = ManagedServer("server_clean")
        # Server booting up and initializing car slots and pitboxes
        ms.add("out", "event pitboxes used: 8 assigning pit slot 0 to competitor 0 car_number 0")
        ms.add("out", "assigning pit slot 4 to competitor 4 car_number 4")
        ms.add("out", "Connecting Car 0")
        ms.add("out", "Connecting Car 4")
        # Must not report any ghost players
        self.assertEqual(len(ms.get_players()), 0)

        # Real player joins
        ms.add("out", "Car [bmw_m4] #0 for driver Baran K [76561198000000001]")
        players = ms.get_players()
        self.assertEqual(len(players), 1)
        self.assertEqual(players[0]["driver_name"], "Baran K")
        self.assertEqual(players[0]["car_number"], "0")
        self.assertFalse(players[0].get("is_admin", False))

        # Admin toggle
        is_adm = ms.toggle_admin("0")
        self.assertTrue(is_adm)
        self.assertTrue(ms.get_players()[0]["is_admin"])

        # Server reset to 0 players
        ms.add("out", "[server] [info] Server updated: 0 players")
        self.assertEqual(len(ms.get_players()), 0)

    def test_runner_instance_lifecycle(self):
        ms = self.runner.get("server_1")
        self.assertIsInstance(ms, ManagedServer)
        self.assertFalse(self.runner.is_running("server_1"))
        self.assertEqual(self.runner.running_ids(), [])


if __name__ == "__main__":
    unittest.main()
