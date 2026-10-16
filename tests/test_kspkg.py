import unittest
from pathlib import Path
from evo_core.kspkg import inspect_package, scan_kspkg_mods, ModPackage
from evo_core.paths import bundled_server_dir

class TestKspkg(unittest.TestCase):
    def test_bundled_kspkg_if_present(self):
        kspkg_path = bundled_server_dir() / "content.kspkg"
        if not kspkg_path.exists():
            self.skipTest("bundled_server/content.kspkg not found")
        pkg = inspect_package(kspkg_path)
        self.assertIsInstance(pkg, ModPackage)
        self.assertEqual(pkg.filename, "content.kspkg")
        self.assertGreater(pkg.size, 0)

if __name__ == "__main__":
    unittest.main()
