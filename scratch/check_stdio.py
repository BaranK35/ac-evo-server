import re

with open('bundled_server/AssettoCorsaEVOServer.exe', 'rb') as f:
    data = f.read()

pos = 0
while True:
    pos = data.find(b'stdio', pos)
    if pos == -1:
        break
    start = max(0, pos - 100)
    end = min(len(data), pos + 100)
    print(f'stdio at {pos}:', data[start:end])
    pos += 5

for word in [b'console', b'admin_password', b'entry_list']:
    p = data.find(word)
    print(f'{word} at {p}')
