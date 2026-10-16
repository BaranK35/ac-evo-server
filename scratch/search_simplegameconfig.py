import re

with open('bundled_server/AssettoCorsaEVOServer.exe', 'rb') as f:
    data = f.read()

pos = 0
while True:
    pos = data.find(b'SimpleGameConfig', pos)
    if pos == -1:
        break
    start = max(0, pos - 200)
    end = min(len(data), pos + 400)
    snippet = data[start:end]
    # find all strings in snippet
    found = re.findall(b'[\x20-\x7E]{3,}', snippet)
    print(f'Offset {pos}: {[s.decode("latin1") for s in found]}')
    pos += 16
