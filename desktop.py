from __future__ import annotations

import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn


def _serve() -> None:
    uvicorn.run("docpilot.app:app", host="127.0.0.1", port=8765, log_level="warning")


def _self_test() -> None:
    from docpilot import __version__
    from docpilot.app import BASE_DIR, app, _demo_source_path

    required = [
        BASE_DIR / "templates" / "index.html",
        BASE_DIR / "static" / "app.css",
        BASE_DIR / "static" / "app.js",
        BASE_DIR / "static" / "manifest.webmanifest",
        BASE_DIR / "static" / "service-worker.js",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError("Missing packaged assets: " + ", ".join(missing))
    if app.version != __version__:
        raise RuntimeError(f"Version mismatch: app={app.version}, package={__version__}")
    demo = Path(_demo_source_path())
    if not demo.exists():
        raise RuntimeError("Bundled demo document is missing.")


def main() -> None:
    if "--self-test" in sys.argv:
        try:
            _self_test()
        except Exception:
            raise SystemExit(1)
        raise SystemExit(0)

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    time.sleep(1.0)
    try:
        import webview
        webview.create_window("DocPilot", "http://127.0.0.1:8765", width=1280, height=820, min_size=(900, 620))
        webview.start()
    except Exception:
        webbrowser.open("http://127.0.0.1:8765")
        try:
            while thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
