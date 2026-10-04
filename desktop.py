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


def _lifepilot_deadline_boundary_self_test() -> None:
    from datetime import date

    from docpilot.lifepilot import next_action_for_document

    today = date(2026, 10, 4)
    cases = [
        ("2026-10-03", "overdue", -1),
        ("2026-10-04", "today", 0),
        ("2026-10-05", "urgent", 1),
        ("2026-10-07", "urgent", 3),
        ("2026-10-08", "soon", 4),
        ("2026-10-18", "soon", 14),
        ("2026-10-19", "normal", 15),
    ]
    for deadline, expected_priority, expected_days in cases:
        result = next_action_for_document(
            {
                "metadata": {
                    "deadline": deadline,
                    "confidence": 0.95,
                    "manual_verified": True,
                    "document_type": "official-letter",
                },
                "action_required": "to-reply",
            },
            today=today,
        )
        if result.get("priority") != expected_priority:
            raise RuntimeError(
                f"LifePilot deadline boundary failed for {deadline}: "
                f"{result.get('priority')} != {expected_priority}."
            )
        if result.get("days_remaining") != expected_days:
            raise RuntimeError(
                f"LifePilot deadline day count failed for {deadline}: "
                f"{result.get('days_remaining')} != {expected_days}."
            )


def _lifepilot_calendar_self_test() -> None:
    from docpilot.exporters import ics_for_documents

    secret_path = r"C:\Users\Private\Documents\secret-case\deadline.pdf"
    calendar = ics_for_documents(
        [
            {
                "id": 901,
                "source_name": "spring-deadline.pdf",
                "path": secret_path,
                "action_required": "to-reply",
                "metadata": {"deadline": "2026-03-29"},
            },
            {
                "id": 902,
                "source_name": "autumn-deadline.pdf",
                "path": secret_path,
                "action_required": "to-reply",
                "metadata": {"deadline": "2026-10-25"},
            },
        ]
    )
    required = (
        "DTSTART;VALUE=DATE:20260329",
        "DTEND;VALUE=DATE:20260330",
        "DTSTART;VALUE=DATE:20261025",
        "DTEND;VALUE=DATE:20261026",
    )
    if not all(item in calendar for item in required):
        raise RuntimeError("LifePilot calendar self-test failed DST-boundary all-day export.")
    if "TZID=" in calendar:
        raise RuntimeError("LifePilot calendar self-test introduced timezone-sensitive DTSTART.")
    if secret_path in calendar or "secret-case" in calendar:
        raise RuntimeError("LifePilot calendar self-test exposed a local file path.")


def _lifepilot_pack_privacy_self_test(
    pack_path: Path,
    *,
    temp_root: Path,
    forbidden_ocr_fragment: str,
) -> None:
    import zipfile

    if not zipfile.is_zipfile(pack_path):
        raise RuntimeError("LifePilot privacy self-test received a non-ZIP pack.")
    forbidden_path = str(temp_root)
    with zipfile.ZipFile(pack_path, "r") as archive:
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            if name.startswith("original/") or name.startswith("documents/") or name.endswith("/"):
                continue
            if info.file_size > 4 * 1024 * 1024:
                continue
            try:
                text = archive.read(info.filename).decode("utf-8")
            except UnicodeDecodeError:
                continue
            if forbidden_path in text:
                raise RuntimeError(f"LifePilot pack privacy self-test exposed a local path in {info.filename}.")
            if forbidden_ocr_fragment in text:
                raise RuntimeError(f"LifePilot pack privacy self-test exposed full OCR text in {info.filename}.")


def _lifepilot_recovery_self_test(temp_settings, document_id: int) -> None:
    from docpilot.db import SCHEMA, connect, get_document
    from docpilot.db_maintenance import (
        create_database_checkpoint,
        database_health,
        restore_database_from_point,
    )

    db_path = temp_settings.state / "docpilot.sqlite3"
    with connect(temp_settings) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings(key,value) VALUES('lifepilot-self-test-recovery','before')"
        )

    checkpoint = create_database_checkpoint(db_path)
    if checkpoint.get("integrity") != "ok":
        raise RuntimeError("LifePilot recovery self-test did not create a verified checkpoint.")

    with connect(temp_settings) as conn:
        conn.execute(
            "UPDATE settings SET value='after' WHERE key='lifepilot-self-test-recovery'"
        )
        conn.execute(
            "UPDATE documents SET case_name='Mutated After Checkpoint' WHERE id=?",
            (document_id,),
        )

    restored = restore_database_from_point(db_path, str(checkpoint["name"]), SCHEMA)
    if (restored.get("database") or {}).get("integrity") != "ok":
        raise RuntimeError("LifePilot recovery self-test restored an unhealthy database.")

    with connect(temp_settings) as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key='lifepilot-self-test-recovery'"
        ).fetchone()
        if not row or row[0] != "before":
            raise RuntimeError("LifePilot recovery self-test did not restore pre-change settings.")

    document = get_document(temp_settings, document_id)
    if not document or document.get("case_name") != "Release Self Test":
        raise RuntimeError("LifePilot recovery self-test did not restore the document state.")
    if database_health(db_path).get("integrity") != "ok":
        raise RuntimeError("LifePilot recovery self-test left the active database unhealthy.")


def _lifepilot_functional_self_test() -> None:
    from docpilot.config import get_settings
    from docpilot.db import init_db
    from docpilot.lifepilot import verify_lifepilot_pack
    from docpilot.models import LifePilotCorrectionRequest
    import docpilot.app as app_module

    original_settings = app_module.settings
    with tempfile.TemporaryDirectory(prefix="docpilot-self-test-") as temp_root:
        temp_settings = get_settings(Path(temp_root) / "DocPilotData")
        init_db(temp_settings)
        app_module.settings = temp_settings
        try:
            source = temp_settings.inbox / "lifepilot-self-test.txt"
            source.write_text(
                "ACME Faktura VAT\n"
                "Data: 04.10.2026\n"
                "Termin platnosci: 10.10.2026\n"
                "Do zaplaty 100 PLN\n",
                encoding="utf-8",
            )
            payload = app_module._analyze_and_index(source)
            doc_id = int(payload.get("id") or 0)
            if doc_id <= 0:
                raise RuntimeError("LifePilot self-test analyze did not return a document id.")

            corrected = app_module.lifepilot_correct_fields(
                doc_id,
                LifePilotCorrectionRequest(
                    case_name="Release Self Test",
                    issuer="ACME",
                    deadline="2026-10-10",
                    action_required="to-pay",
                ),
            )
            if int(corrected.get("id") or 0) != doc_id:
                raise RuntimeError("LifePilot self-test correction returned an unexpected document.")

            _lifepilot_deadline_boundary_self_test()
            _lifepilot_calendar_self_test()
            _lifepilot_recovery_self_test(temp_settings, doc_id)

            history_payload = app_module.lifepilot_document_history(doc_id, limit=100)
            if not any(
                item.get("event") == "lifepilot-fields-corrected"
                for item in history_payload.get("events", [])
            ):
                raise RuntimeError("LifePilot self-test Decision Trail did not record the correction.")
            serialized_history = json.dumps(history_payload, ensure_ascii=False)
            if str(temp_settings.root) in serialized_history:
                raise RuntimeError("LifePilot self-test Decision Trail exposed a local path.")

            readiness_payload = app_module.lifepilot_case_readiness("Release Self Test")
            if readiness_payload.get("document_count") != 1:
                raise RuntimeError("LifePilot self-test Case Readiness returned an unexpected document count.")
            if (readiness_payload.get("counts") or {}).get("missing_originals") != 0:
                raise RuntimeError("LifePilot self-test unexpectedly reported a missing original.")

            proofpack_response = app_module.lifepilot_proofpack(doc_id)
            proofpack_path = Path(str(proofpack_response.path))
            if not proofpack_path.exists() or proofpack_path.stat().st_size <= 0:
                raise RuntimeError("LifePilot self-test ProofPack was not created.")
            proofpack_verification = verify_lifepilot_pack(proofpack_path)
            if not proofpack_verification.get("valid") or proofpack_verification.get("pack_type") != "proofpack":
                raise RuntimeError("LifePilot self-test ProofPack verification did not pass.")
            _lifepilot_pack_privacy_self_test(
                proofpack_path,
                temp_root=temp_settings.root,
                forbidden_ocr_fragment="Do zaplaty 100 PLN",
            )

            casepack_response = app_module.lifepilot_casepack("Release Self Test")
            casepack_path = Path(str(casepack_response.path))
            if not casepack_path.exists() or casepack_path.stat().st_size <= 0:
                raise RuntimeError("LifePilot self-test CasePack was not created.")
            verification = verify_lifepilot_pack(casepack_path)
            if not verification.get("valid") or verification.get("pack_type") != "casepack":
                raise RuntimeError("LifePilot self-test CasePack verification did not pass.")
            _lifepilot_pack_privacy_self_test(
                casepack_path,
                temp_root=temp_settings.root,
                forbidden_ocr_fragment="Do zaplaty 100 PLN",
            )

            source.unlink()
            missing_readiness = app_module.lifepilot_case_readiness("Release Self Test")
            if missing_readiness.get("status") != "incomplete":
                raise RuntimeError("LifePilot self-test did not mark a missing-original case as incomplete.")
            if (missing_readiness.get("counts") or {}).get("missing_originals") != 1:
                raise RuntimeError("LifePilot self-test missing-original count is incorrect.")
            missing_preview = app_module.lifepilot_casepack_preview("Release Self Test")
            if missing_preview.get("missing_originals") != 1:
                raise RuntimeError("LifePilot self-test CasePack preview did not expose the missing original.")

            marked = app_module.lifepilot_mark_done(doc_id)
            if not marked.get("done"):
                raise RuntimeError("LifePilot self-test handled state failed.")
            active_queue = app_module.lifepilot_action_queue(limit=200, include_done=False)
            if any(int(item.get("id") or 0) == doc_id for item in active_queue):
                raise RuntimeError("LifePilot self-test handled document remained in the active queue.")

            case_history = app_module.lifepilot_case_history("Release Self Test", limit=250)
            if not any(
                item.get("event") == "lifepilot-mark-done"
                for item in case_history.get("events", [])
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
