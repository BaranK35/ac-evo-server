import os

path = r"C:\trvps\frp\frpc.toml"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace ac_http4 type = "udp" with type = "tcp"
old_block = """[[proxies]]
name = "ac_http4"
type = "udp"
localIP = "127.0.0.1"
localPort = 8080
remotePort = 8080"""

new_block = """[[proxies]]
name = "ac_http4"
type = "tcp"
localIP = "127.0.0.1"
localPort = 8080
remotePort = 8080"""

if old_block in content:
    content = content.replace(old_block, new_block)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("SUCCESS: Replaced ac_http4 udp with tcp!")
else:
    print("Old block not found directly, checking regex")
    import re
    new_content = re.sub(r'(name\s*=\s*"ac_http4"\s*\ntype\s*=\s*)"udp"', r'\1"tcp"', content)
    if new_content != content:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("SUCCESS via regex: Replaced ac_http4 udp with tcp!")
    else:
        print("Nothing changed or already tcp")
