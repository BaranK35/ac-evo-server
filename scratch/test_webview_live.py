import os
import sys
import time
import webview
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api import Api

def run_test():
    api = Api()
    win = webview.create_window(
        "Live Test",
        url=str(Path("web/index.html").resolve()),
        js_api=api,
        width=1200,
        height=800
    )
    api.attach(win)

    def test_logic():
        time.sleep(2)
        print("Navigating to server_1...")
        win.evaluate_js("go('server', { sid: 'server_1', tab: 'Konsol' });")
        
        # Wait for pollConsole to run
        for i in range(6):
            time.sleep(0.5)
            term_children = win.evaluate_js("document.querySelector('.term') ? document.querySelector('.term').childElementCount : 0")
            print(f"Tick {i}: term children count = {term_children}")
            if term_children > 1:
                break
        
        first_line_text = win.evaluate_js("document.querySelector('.term .ln') ? document.querySelector('.term .ln').textContent : 'NO LN'")
        print("FIRST LINE IN TERM:", first_line_text)
        
        last_line_text = win.evaluate_js("document.querySelectorAll('.term .ln').length ? document.querySelectorAll('.term .ln')[document.querySelectorAll('.term .ln').length - 1].textContent : 'NO LAST LN'")
        print("LAST LINE IN TERM:", last_line_text)

        time.sleep(1)
        win.destroy()

    webview.start(test_logic, debug=False, private_mode=True)

if __name__ == "__main__":
    run_test()
