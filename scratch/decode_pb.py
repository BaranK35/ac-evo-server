import sys
sys.path.insert(0, "acevo-server-Zino1337'nun yaptığı/scripts")
import kspkg
from pathlib import Path

pkg_path = Path("bundled_server/content.kspkg")
entries = kspkg.read_entries(pkg_path)
entry_map = {e.path.replace("/", "\\").lower(): e for e in entries}

e = entry_map[r"content\seasondefinitions\test_wrong_way.seasondefinition"]
data = kspkg._read_entry(pkg_path, e)

# parse raw protobuf fields
def parse_pb(data, prefix=""):
    offset = 0
    while offset < len(data):
        key, offset = kspkg._read_varint(data, offset)
        fn, wt = key >> 3, key & 7
        if wt == 0:
            val, offset = kspkg._read_varint(data, offset)
            print(f"{prefix}Field {fn} (varint): {val}")
        elif wt == 1:
            val = data[offset:offset+8]
            offset += 8
            print(f"{prefix}Field {fn} (64-bit): {val}")
        elif wt == 2:
            length, offset = kspkg._read_varint(data, offset)
            sub = data[offset:offset+length]
            offset += length
            # try to parse sub as string or sub-message
            try:
                s = sub.decode('utf-8')
                if s.isprintable():
                    print(f"{prefix}Field {fn} (str): '{s}'")
                    continue
            except:
                pass
            print(f"{prefix}Field {fn} (sub len={length}):")
            if length < 500:
                try:
                    parse_pb(sub, prefix + "  ")
                except:
                    print(f"{prefix}  <bytes>")
            else:
                print(f"{prefix}  <large>")
        elif wt == 5:
            val = data[offset:offset+4]
            offset += 4
            import struct
            fval = struct.unpack('<f', val)[0]
            ival = struct.unpack('<i', val)[0]
            print(f"{prefix}Field {fn} (32-bit): int={ival}, float={fval}")
        else:
            print(f"Unknown wt {wt}")
            break

parse_pb(data)
