with open('bundled_server/AssettoCorsaEVOServer.exe', 'rb') as f:
    data = f.read()

pos = data.find(b'allowed_cars_list_full')
print('pos:', pos)
if pos != -1:
    chunk = data[pos-200:pos+800]
    import re
    strings = re.findall(b'[\x20-\x7E]{2,}', chunk)
    for s in strings:
        print(s.decode('latin1'))
