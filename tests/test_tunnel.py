"""Tünel yöneticisi (tunnel) modülü birim testleri."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from evo_core.tunnel import TunnelManager


class TestTunnel(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.mock_config = {
            "tunnel_enabled": True,
            "tunnel_vps_ip": "89.144.10.75",
            "tunnel_vps_user": "root",
            "tunnel_frp_token": "secret_token_123",
            "tunnel_socks_port": 1088,
        }
        self.tm = TunnelManager(self.tmp_dir, config_getter=lambda: self.mock_config)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_properties(self):
        self.assertEqual(self.tm.vps_ip, "89.144.10.75")
        self.assertEqual(self.tm.vps_user, "root")
        self.assertEqual(self.tm.frp_token, "secret_token_123")
        self.assertEqual(self.tm.socks_port, 1088)
        self.assertTrue(self.tm.is_enabled())

    def test_disabled_when_empty_ip(self):
        cfg = dict(self.mock_config, tunnel_vps_ip="")
        tm = TunnelManager(self.tmp_dir, config_getter=lambda: cfg)
        self.assertFalse(tm.is_enabled())

    def test_write_frpc_config(self):
        toml_path = self.tm._write_frpc_config(9700, 9700, 8080)
        self.assertTrue(toml_path.is_file())
        content = toml_path.read_text(encoding="utf-8")
        self.assertIn('serverAddr = "89.144.10.75"', content)
        self.assertIn('auth.token = "secret_token_123"', content)
        self.assertIn('localPort = 9700', content)
        self.assertIn('remotePort = 9700', content)
        self.assertIn('localPort = 8080', content)
        self.assertIn('type = "udp"', content)
        self.assertIn('type = "tcp"', content)

    def test_find_frpc_exe(self):
        # Should find system/frpc.exe in repository if present
        found = self.tm._find_frpc_exe()
        if found:
            self.assertTrue(Path(found).is_file())

    def test_status_and_stop(self):
        st = self.tm.get_status()
        self.assertTrue(st["enabled"])
        self.assertEqual(st["vps_ip"], "89.144.10.75")
        self.assertIn("socks_active", st)
        self.assertIn("frpc_active", st)
        self.tm.stop()


if __name__ == "__main__":
    unittest.main()
