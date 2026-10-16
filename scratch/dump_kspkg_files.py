import sys
sys.path.insert(0, "acevo-server-Zino1337'nun yaptığı/scripts")
import kspkg
from pathlib import Path

pkg_path = Path("bundled_server/content.kspkg")
entries = kspkg.read_entries(pkg_path)
entry_map = {e.path.replace("/", "\\").lower(): e for e in entries}

targets = [
    r"content\seasondefinitions\test_wrong_way.seasondefinition",
    r"content\seasondefinitions\free_roam.seasondefinition",
    r"content\data\practice.seasondefinition",
    r"system\defaults\timeattack.penaltyinvestigations",
]

for t in targets:
    e = entry_map.get(t.lower())
    if e:
        data = kspkg._read_entry(pkg_path, e)
        print(f"=== {t} (len: {len(data)}) ===")
        try:
            print(data.decode("utf-8"))
        except Exception:
            print(repr(data[:200]))
    else:
        print(f"NOT FOUND: {t}")
