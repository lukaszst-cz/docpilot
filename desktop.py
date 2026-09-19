from __future__ import annotations

import threading
import time
import webbrowser

import uvicorn


def _serve() -> None:
    uvicorn.run("docpilot.app:app", host="127.0.0.1", port=8765, log_level="warning")


def main() -> None:
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
