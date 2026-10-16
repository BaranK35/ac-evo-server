import sys
sys.path.insert(0, '.')
from api import Api
import json

a = Api()
res = a.console('server_1', 0)
s = json.dumps(res).replace('\\', '\\\\').replace("'", "\\'")
print('Serialized length:', len(s))
print('Has newline:', '\n' in s, 'Has CR:', '\r' in s)

# Test whether this string is valid JavaScript:
# In JS: ({value: '...'})
js_code = f"({{{repr('value')}: '{s}'}})"
print('Test JS code length:', len(js_code))

# Let's test evaluating this js_code with node:
import subprocess
p = subprocess.run(['node', '-e', f"console.log('Valid JS? ' + typeof {js_code})"], capture_output=True, text=True)
print('Node return code:', p.returncode)
print('Node stdout:', p.stdout)
print('Node stderr:', p.stderr[:300])
