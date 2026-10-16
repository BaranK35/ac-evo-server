import re

with open('bundled_server/AssettoCorsaEVOServer.exe', 'rb') as f:
    data = f.read()

# find all occurrences of GameModeType_
types = set(re.findall(rb'GameModeType_[a-zA-Z0-9_]+', data))
for t in sorted(types):
    print(t.decode('latin1'))

print('\nGameModeSelectionWeatherType:')
wtypes = set(re.findall(rb'GameModeSelectionWeatherType_[a-zA-Z0-9_]+', data))
for w in sorted(wtypes):
    print(w.decode('latin1'))

print('\nInitialGrip:')
grips = set(re.findall(rb'InitialGrip_[a-zA-Z0-9_]+', data))
for g in sorted(grips):
    print(g.decode('latin1'))
