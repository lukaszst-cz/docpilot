from __future__ import annotations

import ctypes
import json
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn


def _serve() -> None:
    uvicorn.run("docpilot.app:app", host="127.0.0.1", port=8765, log_level="warning")


def _wait_until_ready(timeout: float = 20.0) -> bool:
    from docpilot import __version__

    deadline = time.monotonic() + timeout
    url = "http://127.0.0.1:8765/api/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("status") == "ok" and payload.get("version") == __version__:
                return True
        except (OSError, ValueError, urllib.error.URLError):
            pass
        time.sleep(0.2)
    return False


def _show_startup_error() -> None:
    message = (
        "DocPilot could not start its local service.\n\n"
        "Try closing any other DocPilot window and start the application again. "
        "If the problem repeats, check docpilot.log."
    )
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.MessageBoxW(0, message, "DocPilot", 0x10)
            return
        except Exception:
            pass
    print(message, file=sys.stderr)


def _self_test() -> None:
    from docpilot import __version__
    from docpilot.app import STATIC_DIR, TEMPLATE_DIR, app, _demo_source_path

    required = [
        TEMPLATE_DIR / "index.html",
        STATIC_DIR / "app.css",
        STATIC_DIR / "app.js",
        STATIC_DIR / "manifest.webmanifest",
        STATIC_DIR / "service-worker.js",
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
    if not _wait_until_ready():
        _show_startup_error()
        return
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
