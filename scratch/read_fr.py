import sys
sys.path.insert(0, "acevo-server-Zino1337'nun yaptığı/scripts")
import kspkg, re
from pathlib import Path

pkg_path = Path("bundled_server/content.kspkg")
entries = kspkg.read_entries(pkg_path)
entry_map = {e.path.replace("/", "\\").lower(): e for e in entries}

e = entry_map[r"content\seasondefinitions\free_roam.seasondefinition"]
data = kspkg._read_entry(pkg_path, e)
strings = re.findall(b'[\x20-\x7E]{2,}', data)
for s in strings:
    print(s.decode('latin1'))
