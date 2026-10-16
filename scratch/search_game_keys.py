import re

with open('bundled_server/AssettoCorsaEVOServer.exe', 'rb') as f:
    data = f.read()

# Look for json keys specifically in protobuf / json schemas
keys = set()
for match in re.finditer(rb'"([a-zA-Z0-9_]{3,45})"', data):
    k = match.group(1).decode('ascii', errors='ignore')
    if any(x in k.lower() for x in ['penalt', 'wrong', 'pit', 'rule', 'warn', 'cut', 'speed', 'limit', 'box', 'disq', 'fuel', 'tyre', 'tire', 'grip', 'flag', 'track', 'layout']):
        keys.add(k)

print('Specific keys found in AssettoCorsaEVOServer.exe:')
for k in sorted(keys):
    if len(k) > 3:
        print(' ', k)
