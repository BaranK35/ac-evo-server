import sys
sys.path.insert(0, '.')
from api import Api
import json
import subprocess

a = Api()
res = a.console('server_1', 0)

# Exact pywebview logic from util.py:
result = json.dumps(res).replace('\\', '\\\\').replace("'", "\\'")
retval = f"{{value: '{result}'}}"
js_code = f"""
const returnObj = {retval};
try {{
    const parsed = JSON.parse(returnObj.value);
    console.log('SUCCESS PARSING! Lines count:', parsed.data.lines.length);
}} catch(e) {{
    console.log('FAILED TO PARSE IN JS:', e.message);
}}
"""

p = subprocess.run(['node', '-e', js_code], capture_output=True, text=True)
print("Node return code:", p.returncode)
print("Node stdout:", p.stdout)
print("Node stderr:", p.stderr)
