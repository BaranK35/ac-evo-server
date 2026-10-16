import re

with open('bundled_server/AssettoCorsaEVOServer.exe', 'rb') as f:
    data = f.read()

# Look for null-terminated ASCII strings
strings = re.findall(b'[\x20-\x7E]{4,60}\x00', data)
clean = [s[:-1].decode('latin1') for s in strings]

print('Strings matching penalty/cut/pit/wrong:')
matched = [s for s in clean if any(x in s.lower() for x in ['penalt', 'wrong_way', 'cut_tyre', 'warning_trigger', 'pit_limiter', 'pit_speed', 'pit_window', 'mandatory_pit', 'simplegameconfig'])]
for s in sorted(set(matched)):
    print(' ', s)
