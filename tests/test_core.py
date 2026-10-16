import json, os, sys, tempfile, time, zipfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
tmp = Path(tempfile.mkdtemp()); os.environ["EVO_MANAGER_HOME"] = str(tmp / "home")
from evo_core.encoding import encode_evo_payload, decode_evo_payload, build_seasondefinition, build_serverconfig
from evo_core.paths import servers_dir, data_root
from evo_core.servers import ServerStore, SERVER_EXE, ServerError, validate_server_folder
from evo_core.mods import ModManager, analyze_paths
from evo_core.runner import Runner, probe_candidates
from evo_core.diagnose import diagnose
from evo_core.steam import classify


class TestCoreIntegration(unittest.TestCase):
    def test_full_pipeline(self):
        self.assertEqual(decode_evo_payload(encode_evo_payload({"a": "ş"})), {"a": "ş"})
        # kullanıcının gerçek mod yapısı (7z içinde ek_tsukub_qu/...)
        paths = ["ek_tsukub_qu/ek_tsukub_qu.track", "ek_tsukub_qu/ek_tsukub_qu.scene", "ek_tsukub_qu/containers/layout_freeroam.scene", "ek_tsukub_qu/ui/map.svg"]
        items = analyze_paths(paths)
        self.assertEqual([(i.kind, i.name, i.root) for i in items], [("track", "ek_tsukub_qu", "ek_tsukub_qu")])
        self.assertEqual(analyze_paths(["mods/content/cars/my_car/my_car.car", "mods/content/cars/my_car/x.mesh"])[0].kind, "car")
        self.assertEqual(analyze_paths(["readme.txt"]), [])

        evo = tmp / "evo"; evo.mkdir(exist_ok=True); (evo / SERVER_EXE).write_text("x")
        (evo / "events_practice.json").write_text(json.dumps({"events": [{"track": "Imola", "layout": "GP", "event_name": "GP", "track_length": 4909, "max_pit_slot": 29, "spawns": []}]}))
        (evo / "events_race_weekend.json").write_text(json.dumps({"events": []}))
        (evo / "cars.json").write_text(json.dumps({"cars": [{"name": "c1", "display_name": "C1", "performance_indicator": 10.0, "property_1": 1, "property_2": 2, "property_3": 3}]}))
        store = ServerStore(servers_dir()); sid = store.create(str(evo))

        # mod: oyun klasörüne daha önce elle kurulmuş (kullanıcının durumu) -> sunucu klasöründe YOK
        game, server = tmp / "ACE" / "mods", tmp / "ACE-Server" / "mods"
        pre = game / "content" / "tracks" / "ek_tsukub_qu"; (pre / "containers").mkdir(parents=True, exist_ok=True)
        (pre / "ek_tsukub_qu.track").write_text('{"layout":"freeroam"}\r\n'); (pre / "containers" / "layout_freeroam.scene").write_text("s")
        mods = ModManager(game, server, data_root() / "mods.json", True)
        t = mods.scan("track")[0]
        self.assertTrue(t["in_game"] and not t["in_server"] and t["layouts"] == ["freeroam"])
        self.assertEqual(mods.sync_to_server(), ["ek_tsukub_qu"])          # çökmenin düzeltmesi
        self.assertTrue((server / "content" / "tracks" / "ek_tsukub_qu" / "ek_tsukub_qu.track").is_file())
        self.assertEqual(mods.sync_to_server(), [])
        self.assertTrue(mods.scan("track")[0]["in_server"])

        # zip kurulum: iki hedefe
        src = tmp / "pk" / "newtrack"; src.mkdir(parents=True, exist_ok=True); (src / "newtrack.track").write_text("{}")
        z = tmp / "m.zip"
        with zipfile.ZipFile(z, "w") as zf: zf.write(src / "newtrack.track", "newtrack/newtrack.track")
        res = mods.install(z)
        self.assertEqual(res, [{"kind": "track", "name": "newtrack"}])
        self.assertTrue(all((r / "content" / "tracks" / "newtrack").is_dir() for r in (game, server)))
        info = mods.inspect_source(z)
        self.assertTrue(info["items"][0]["name"] == "newtrack" and info["items"][0]["installed"])
        self.assertTrue(mods.inspect_source(tmp / "evo")["error"])
        with self.assertRaises(ServerError):
            mods.install(tmp / "evo")

        # kayıt + enjeksiyon
        e = mods.entry_for("track", "ek_tsukub_qu", t); e["track_length"] = 2045; mods.set_entry("track", "ek_tsukub_qu", e)
        mods.set_entry("car", "mycar", {"name": "mycar", "display_name": "My Car", "performance_indicator": 55.0, "property_1": 1, "property_2": 1, "property_3": 1})
        ev = [x for x in mods.track_events() if x["track"] == "ek_tsukub_qu"][0]
        self.assertEqual(ev["track_length"], 2045)
        self.assertGreaterEqual(mods.inject_events(store.path(sid)), 2)
        self.assertEqual(mods.inject_events(store.path(sid)), 0)
        mods.set_entry("car", "mycar", mods.registry["cars"]["mycar"])
        (game / "content" / "cars" / "mycar").mkdir(parents=True, exist_ok=True)
        self.assertEqual(mods.inject_cars(store.path(sid)), 1)
        self.assertTrue(any(c["name"] == "mycar" for c in store.cars(sid)))
        mods.remove("track", "newtrack")
        self.assertFalse((server / "content" / "tracks" / "newtrack").exists())
        self.assertEqual(mods.probe_candidates("ek_tsukub_qu")[0], ("ek_tsukub_qu", "freeroam"))

        # ham ek ayarlar
        d = store.load(sid); d["serverconfig_extra"] = {"max_players": 3}
        self.assertEqual(build_serverconfig(d)["max_players"], 3)
        self.assertIn("event", build_seasondefinition(d))

        # teşhis
        lines = ["[error] Exception thrown: Trying to load a message with an empty path", "CRASH DETECTED"]
        self.assertTrue(diagnose(lines)[0]["title"].startswith("Sunucu seçilen"))
        self.assertEqual(classify("Steam Guard")[0], "need_guard")

        # süreç + pist testi (sahte sunucu: 'bad' pist adıyla çöker, 'good' ile ayakta kalır)
        fake = tmp / "fake.py"
        fake.write_text("import sys,time,json\nprint('hi',flush=True)\nif 'bad' in sys.argv[1]:\n    print('CRASH DETECTED',flush=True); sys.exit(1)\ntime.sleep(30)\n")
        store.preflight = lambda s, dd: []
        store.build_command = lambda s, dd: [sys.executable, str(fake), dd["track"]]
        r = Runner(store, lambda: {"auto_restart": False})
        found = probe_candidates(r, sid, [("bad1", "x"), ("bad2", "y"), ("good", "z")], lambda *a: None, lambda: False, settle=1.5)
        self.assertEqual(found, {"track": "good", "layout": "z"})
        self.assertEqual(store.load(sid)["track"], d["track"])
        self.assertFalse(r.is_running(sid))     # ayarlar geri yüklendi

        # proto şema doğrulaması: kök dizinde geçersiz protobuf alanları olmamalı (sunucuyu çökertir)
        d["penalties"] = True
        d["car_damage"] = True
        d["pit_limiter"] = True
        d["wrong_way_penalty"] = True
        sd = build_seasondefinition(d)
        self.assertNotIn("wrong_way_penalty", sd)
        self.assertNotIn("car_damage", sd)
        self.assertNotIn("pit_limiter", sd)
        self.assertTrue(sd["game_config"]["enable_custom_penalities"])

        # api testleri
        from api import Api
        api = Api()
        self.assertTrue(api.open_server_folder(sid)["ok"])
        self.assertTrue(api.open_server_folder(sid)["data"])
        self.assertFalse(api.open_server_folder("gecersiz_sid")["data"])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestCoreIntegration)
    runner = unittest.TextTestRunner()
    result = runner.run(suite)
    if result.wasSuccessful():
        print("TÜM ÇEKİRDEK TESTLER GEÇTİ")
    else:
        sys.exit(1)
