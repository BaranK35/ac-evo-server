with open('bundled_server/AssettoCorsaEVOServer.exe', 'rb') as f:
    pos = f.read().find(b'BuildServerConfigRequest')
    f.seek(pos - 600)
    chunk = f.read(1500)

import re
strings = re.findall(b'[\x20-\x7E]{2,}', chunk)
for s in strings:
    print(s.decode('latin1'))
