from __future__ import annotations

import ctypes
import json
import sys
import tempfile
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


def _lifepilot_functional_self_test() -> None:
    from fastapi.testclient import TestClient

    from docpilot.config import get_settings
    from docpilot.db import init_db
    import docpilot.app as app_module

    original_settings = app_module.settings
    with tempfile.TemporaryDirectory(prefix="docpilot-self-test-") as temp_root:
        temp_settings = get_settings(Path(temp_root) / "DocPilotData")
        init_db(temp_settings)
        app_module.settings = temp_settings
        try:
            with TestClient(app_module.app) as client:
                analyzed = client.post(
                    "/api/analyze",
                    files={
                        "upload": (
                            "lifepilot-self-test.txt",
                            (
                                b"ACME Faktura VAT\n"
                                b"Data: 04.10.2026\n"
                                b"Termin platnosci: 10.10.2026\n"
                                b"Do zaplaty 100 PLN\n"
                            ),
                            "text/plain",
                        )
                    },
                )
                if analyzed.status_code != 200:
                    raise RuntimeError(f"LifePilot self-test analyze failed: {analyzed.status_code}")
                payload = analyzed.json()
                doc_id = int(payload.get("id") or 0)
                if doc_id <= 0:
                    raise RuntimeError("LifePilot self-test analyze did not return a document id.")

                corrected = client.patch(
                    f"/api/lifepilot/{doc_id}/fields",
                    json={
                        "case_name": "Release Self Test",
                        "issuer": "ACME",
                        "deadline": "2026-10-10",
                        "action_required": "to-pay",
                    },
                )
                if corrected.status_code != 200:
                    raise RuntimeError(f"LifePilot self-test correction failed: {corrected.status_code}")

                history = client.get(f"/api/lifepilot/{doc_id}/history")
                if history.status_code != 200:
                    raise RuntimeError(f"LifePilot self-test history failed: {history.status_code}")
                history_payload = history.json()
                if not any(
                    item.get("event") == "lifepilot-fields-corrected"
                    for item in history_payload.get("events", [])
                ):
                    raise RuntimeError("LifePilot self-test Decision Trail did not record the correction.")
                serialized_history = json.dumps(history_payload, ensure_ascii=False)
                if str(temp_settings.root) in serialized_history:
                    raise RuntimeError("LifePilot self-test Decision Trail exposed a local path.")

                readiness = client.get(
                    "/api/lifepilot/case-readiness",
                    params={"case_name": "Release Self Test"},
                )
                if readiness.status_code != 200:
                    raise RuntimeError(f"LifePilot self-test readiness failed: {readiness.status_code}")
                readiness_payload = readiness.json()
                if readiness_payload.get("document_count") != 1:
                    raise RuntimeError("LifePilot self-test Case Readiness returned an unexpected document count.")
                if (readiness_payload.get("counts") or {}).get("missing_originals") != 0:
                    raise RuntimeError("LifePilot self-test unexpectedly reported a missing original.")

                casepack = client.get(
                    "/api/lifepilot/casepack",
                    params={"case_name": "Release Self Test"},
                )
                if casepack.status_code != 200 or not casepack.content:
                    raise RuntimeError(f"LifePilot self-test CasePack failed: {casepack.status_code}")

                verified = client.post(
                    "/api/lifepilot/proofpack/verify",
                    files={"upload": ("Release-Self-Test-CasePack.zip", casepack.content, "application/zip")},
                )
                if verified.status_code != 200:
                    raise RuntimeError(f"LifePilot self-test pack verification failed: {verified.status_code}")
                verification = verified.json()
                if not verification.get("valid") or verification.get("pack_type") != "casepack":
                    raise RuntimeError("LifePilot self-test CasePack verification did not pass.")

                marked = client.post(f"/api/lifepilot/{doc_id}/done")
                if marked.status_code != 200:
                    raise RuntimeError(f"LifePilot self-test handled state failed: {marked.status_code}")
                active_queue = client.get("/api/lifepilot/queue")
                if active_queue.status_code != 200:
                    raise RuntimeError(f"LifePilot self-test queue failed: {active_queue.status_code}")
                if any(int(item.get("id") or 0) == doc_id for item in active_queue.json()):
                    raise RuntimeError("LifePilot self-test handled document remained in the active queue.")

                case_history = client.get(
                    "/api/lifepilot/case-history",
                    params={"case_name": "Release Self Test"},
                )
                if case_history.status_code != 200:
                    raise RuntimeError(f"LifePilot self-test case history failed: {case_history.status_code}")
                if not any(
                    item.get("event") == "lifepilot-mark-done"
                    for item in case_history.json().get("events", [])
                ):
                    raise RuntimeError("LifePilot self-test case Decision Trail did not record handled state.")
        finally:
            app_module.settings = original_settings


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
    _lifepilot_functional_self_test()


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
        webview.create_window("DocPilot", "http://127.0.0.1:8765/?client=desktop", width=1280, height=820, min_size=(900, 620))
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
