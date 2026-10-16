import sys
sys.path.insert(0, "acevo-server-Zino1337'nun yaptığı/scripts")
import kspkg
from pathlib import Path

entries = kspkg.read_entries(Path("bundled_server/content.kspkg"))
print(f"Total entries in content.kspkg: {len(entries)}")
pen_entries = [e for e in entries if any(x in e.path.lower() for x in ['penalt', 'rule', 'investigat', 'season', 'practice'])]
print("Matching entries in content.kspkg:")
for e in pen_entries[:50]:
    print(f"  {e.path} (size: {e.size}, flags: {e.flags})")
