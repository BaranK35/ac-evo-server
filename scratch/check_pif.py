with open('bundled_server/AssettoCorsaEVOServer.exe', 'rb') as f:
    data = f.read()

pos = 0
while True:
    pos = data.find(b'penalty_investigations_file', pos)
    if pos == -1:
        break
    start = max(0, pos - 150)
    end = min(len(data), pos + 250)
    import re
    strings = re.findall(b'[\x20-\x7E]{2,}', data[start:end])
    print(f'At {pos}: {[s.decode("latin1") for s in strings]}')
    pos += 25
