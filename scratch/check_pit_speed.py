with open('bundled_server/AssettoCorsaEVOServer.exe', 'rb') as f:
    data = f.read()

import re
matches = set(re.findall(rb'[\w.]{3,35}(?:pit|speed|limit|cut|penalt)[\w.]{0,25}', data, re.I))
for m in sorted(matches):
    print(m.decode('latin1'))
