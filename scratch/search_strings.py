import re

with open('bundled_server/AssettoCorsaEVOServer.exe', 'rb') as f:
    data = f.read()

# Look for json keys
keys = set()
for match in re.finditer(rb'"([a-zA-Z0-9_]{3,40})"\s*:', data):
    k = match.group(1).decode('ascii', errors='ignore')
    if any(x in k.lower() for x in ['penalt', 'wrong', 'pit', 'rule', 'warn', 'cut', 'speed', 'limit', 'time', 'lap', 'drive', 'flag', 'steer', 'fuel', 'tyre', 'tire', 'grip']):
        keys.add(k)
print('JSON keys in server binary:')
for k in sorted(keys):
    print(' ', k)

# Look for chat commands
cmds = set()
for m in re.finditer(rb'\\([a-zA-Z0-9_]{2,25})', data):
    cmds.add('\\' + m.group(1).decode('ascii', errors='ignore'))
print('\nChat/console commands in server binary:')
for c in sorted(cmds):
    print(' ', c)

# Look for command-line arguments like -serverconfig
args = set()
for m in re.finditer(rb'-([a-zA-Z0-9_]{3,30})', data):
    args.add('-' + m.group(1).decode('ascii', errors='ignore'))
print('\nCLI args in server binary:')
for a in sorted(args):
    print(' ', a)
