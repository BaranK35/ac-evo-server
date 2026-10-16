with open('bundled_server/AssettoCorsaEVOServer.exe', 'rb') as f:
    data = f.read()

pos = 0
matches = []
while True:
    pos = data.find(b'warning_trigger_countdown', pos)
    if pos == -1:
        break
    matches.append(pos)
    pos += 25
print('warning_trigger_countdown occurrences:', matches)
