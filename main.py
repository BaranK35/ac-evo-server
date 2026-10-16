"""Apex Server Manager - giriş noktası (tek pencere, tarayıcı/port/şifre yok)."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def resource(rel: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / rel


def main() -> None:
    try:
        import webview
    except ImportError:
        print("pywebview yüklü değil. Çalıştırın: pip install -r requirements.txt")
        sys.exit(1)
    from api import Api
    from evo_core.paths import APP_NAME, data_root

    import shutil
    for p in [
        data_root() / "webview",
        data_root() / "cache",
        Path(os.environ.get("LOCALAPPDATA", "")) / "app.slipstream.desktop",
    ]:
        try:
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
        except Exception:
            pass

    api = Api()
    window = webview.create_window(APP_NAME, url=str(resource("web/index.html")), js_api=api, width=1380, height=880,
                                   min_size=(1180, 750), background_color="#090b10", text_select=True)
    api.attach(window)

    def on_loaded():
        """Sürükle-bırak: bırakılan dosyaların tam yolunu yalnızca Python tarafı alabilir."""
        try:
            from webview.dom import DOMEventHandler

            def on_drop(event):
                files = (event.get("dataTransfer") or {}).get("files") or []
                paths = [f.get("pywebviewFullPath") for f in files if f.get("pywebviewFullPath")]
                if paths:
                    api._handle_drop(paths)

            window.dom.document.events.drop += DOMEventHandler(on_drop, True, True)
            window.dom.document.events.dragover += DOMEventHandler(lambda e: None, True, False)
        except Exception as exc:  # noqa: BLE001
            print("Sürükle-bırak etkinleştirilemedi:", exc)

    def on_closing():
        count = api.running_count()
        if count and not window.create_confirmation_dialog("Çıkış", f"{count} sunucu çalışıyor. Durdurulup uygulama kapatılsın mı?"):
            return False
        api.shutdown()
        return True

    window.events.loaded += on_loaded
    window.events.closing += on_closing
    webview.start(debug="--debug" in sys.argv, private_mode=True)


if __name__ == "__main__":
    main()

