with open('bundled_server/AssettoCorsaEVOServer.exe', 'rb') as f:
    f.seek(32057000)
    chunk = f.read(2000)

import re
strings = re.findall(b'[\x20-\x7E]{2,}', chunk)
for s in strings:
    print(s.decode('latin1'))
